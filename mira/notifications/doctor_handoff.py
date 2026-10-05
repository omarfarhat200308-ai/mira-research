"""
Stage 5: doctor handoff. On a RED/YELLOW (EMERGENCY/URGENT) triage, sends a
second, distinct outbound WhatsApp message to the on-duty doctor's
registered number — via Twilio's REST API (a new outbound message the
system initiates), NOT the TwiML reply used for the ASHA-facing response in
mira/webhook.py, which can only reply to the inbound sender.

Real sends require ALL of:
  1. final_triage in {EMERGENCY, URGENT} (never GREEN/routine)
  2. case.data_source == "pilot" (never page a real doctor from
     simulated/dev/intern test traffic)
  3. config.ENABLE_DOCTOR_HANDOFF_SEND == True (explicit opt-in)
  4. TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_WHATSAPP_FROM /
     DOCTOR_WHATSAPP_NUMBER all set

Message content includes patient identifiers (name, age, referring ASHA
worker ID) — this is a treatment-purpose data flow where identifiable data
is appropriate and expected, unlike the de-identified research export path
(mira/consent/store.py). It requires its own separate consent statement
(ConsentScope.DOCTOR_REFERRAL_SHARE) distinct from triage-support consent —
see mira/consent/models.py.

A failed send is never silently dropped: it's queued in
mira/notifications/outbox.py for retry, and the caller (mira/pipeline.py)
is expected to append a verbal-follow-up note to the ASHA-facing reply.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from .. import config, reliability
from ..state import DataSource, PatientCase, Urgency
from . import outbox

HANDOFF_TRIGGER_URGENCIES = {Urgency.EMERGENCY, Urgency.URGENT}

# Every possible return status, so callers can pattern-match exhaustively
# rather than string-guessing:
STATUS_SKIPPED_NOT_TRIGGERED = "skipped_not_triggered"     # final_triage was GREEN/routine
STATUS_SKIPPED_SIMULATED_DATA = "skipped_simulated_data"   # data_source != pilot
STATUS_SKIPPED_NOT_CONFIGURED = "skipped_not_configured"   # flag/creds missing
STATUS_SENT = "sent"
STATUS_FAILED_QUEUED = "failed_queued"                     # send failed, queued in outbox for retry


def should_trigger_handoff(case: PatientCase) -> bool:
    return case.final_triage in HANDOFF_TRIGGER_URGENCIES


def build_handoff_message(case: PatientCase) -> str:
    symptoms_text = (
        "; ".join(
            f"{s.name} (onset={s.onset}, duration={s.duration}, severity={s.severity})"
            for s in case.symptoms
        )
        or "not recorded"
    )
    urgency_label = case.final_triage.value.upper() if case.final_triage else "UNKNOWN"
    lines = [
        "MIRA REFERRAL — new case requiring your attention",
        f"Classification: {urgency_label}",
        f"Patient name: {case.patient.name or 'not provided'}",
        f"Age: {case.patient.age if case.patient.age is not None else 'not provided'}",
        f"Sex: {case.patient.sex.value if case.patient.sex else 'not provided'}",
        f"Pregnant: {case.patient.is_pregnant if case.patient.is_pregnant is not None else 'n/a'}",
        f"Referring ASHA worker: {case.asha_worker_id or case.source_phone_number or 'unknown'}",
        f"Reported symptoms: {symptoms_text}",
        f"MIRA rationale: {case.referral_reasoning or 'not recorded'}",
        f"Case ID: {case.case_id}",
        f"Timestamp: {datetime.now(timezone.utc).isoformat()}",
    ]
    return "\n".join(lines)


def _send_via_twilio_rest(to_number: str, body: str) -> None:
    from twilio.rest import Client  # local import: only required if a real send is attempted

    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    if not account_sid or not auth_token:
        raise reliability.ExternalCallFailed(
            "twilio_rest_doctor_handoff", 0,
            RuntimeError("TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN not set"),
        )

    client = Client(account_sid, auth_token)

    def _call():
        return client.messages.create(
            from_=f"whatsapp:{config.TWILIO_WHATSAPP_FROM}",
            to=f"whatsapp:{to_number}",
            body=body,
        )

    reliability.call_with_retries(_call, call_name="twilio:doctor_handoff")


def send_doctor_handoff(case: PatientCase) -> tuple[str, str]:
    """Returns (status, detail) — see the STATUS_* constants above. Never
    raises: every failure mode is represented as a status the caller can
    branch on."""
    if not should_trigger_handoff(case):
        return STATUS_SKIPPED_NOT_TRIGGERED, "final_triage is not EMERGENCY/URGENT"

    if case.data_source != DataSource.PILOT:
        return STATUS_SKIPPED_SIMULATED_DATA, (
            "case.data_source is 'simulated' — real doctor-handoff sends "
            "are gated to data_source='pilot' so dev/intern test traffic "
            "never pages a real doctor"
        )

    if not config.ENABLE_DOCTOR_HANDOFF_SEND:
        return STATUS_SKIPPED_NOT_CONFIGURED, "MIRA_ENABLE_DOCTOR_HANDOFF_SEND is not set to 1"

    if not config.DOCTOR_WHATSAPP_NUMBER or not config.TWILIO_WHATSAPP_FROM:
        return STATUS_SKIPPED_NOT_CONFIGURED, (
            "DOCTOR_WHATSAPP_NUMBER and/or TWILIO_WHATSAPP_FROM not set"
        )

    message_body = build_handoff_message(case)

    try:
        _send_via_twilio_rest(config.DOCTOR_WHATSAPP_NUMBER, message_body)
    except reliability.ExternalCallFailed as exc:
        outbox.init_db()
        outbox.enqueue(
            case_id=case.case_id,
            kind="doctor_handoff",
            to_number=config.DOCTOR_WHATSAPP_NUMBER,
            body=message_body,
        )
        return STATUS_FAILED_QUEUED, str(exc)

    return STATUS_SENT, "delivered via Twilio REST"
