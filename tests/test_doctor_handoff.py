"""
Tests for Stage 5 doctor handoff (mira/notifications/doctor_handoff.py):
the three independent gates (triage band, data_source==pilot, explicit
config+creds) each block a real send on their own, message content includes
what continuity-of-care requires, and a failed send is queued in the
outbox rather than silently dropped.
"""
from __future__ import annotations

from mira.notifications import doctor_handoff, outbox
from mira.state import DataSource, Patient, PatientCase, Symptom, Urgency


def _pilot_emergency_case(**overrides) -> PatientCase:
    defaults = dict(
        raw_input_text="test",
        final_triage=Urgency.EMERGENCY,
        data_source=DataSource.PILOT,
        patient=Patient(name="Lakshmi", age=28, is_pregnant=True),
        symptoms=[Symptom(name="severe headache", onset="yesterday", duration="1 day", severity="severe")],
        asha_worker_id="whatsapp:+910000000000",
        referral_reasoning="pre-eclampsia warning pattern",
    )
    defaults.update(overrides)
    return PatientCase(**defaults)


def test_routine_case_never_triggers_handoff():
    case = _pilot_emergency_case(final_triage=Urgency.ROUTINE)
    status, detail = doctor_handoff.send_doctor_handoff(case)
    assert status == doctor_handoff.STATUS_SKIPPED_NOT_TRIGGERED


def test_simulated_data_source_blocks_real_send_even_if_urgent():
    case = _pilot_emergency_case(data_source=DataSource.SIMULATED)
    status, detail = doctor_handoff.send_doctor_handoff(case)
    assert status == doctor_handoff.STATUS_SKIPPED_SIMULATED_DATA


def test_pilot_urgent_case_blocked_without_config(monkeypatch):
    monkeypatch.setattr(doctor_handoff.config, "ENABLE_DOCTOR_HANDOFF_SEND", False)
    case = _pilot_emergency_case()
    status, detail = doctor_handoff.send_doctor_handoff(case)
    assert status == doctor_handoff.STATUS_SKIPPED_NOT_CONFIGURED


def test_pilot_urgent_case_blocked_without_doctor_number(monkeypatch):
    monkeypatch.setattr(doctor_handoff.config, "ENABLE_DOCTOR_HANDOFF_SEND", True)
    monkeypatch.setattr(doctor_handoff.config, "DOCTOR_WHATSAPP_NUMBER", None)
    monkeypatch.setattr(doctor_handoff.config, "TWILIO_WHATSAPP_FROM", "+911111111111")
    case = _pilot_emergency_case()
    status, detail = doctor_handoff.send_doctor_handoff(case)
    assert status == doctor_handoff.STATUS_SKIPPED_NOT_CONFIGURED


def test_message_includes_continuity_of_care_fields():
    case = _pilot_emergency_case()
    message = doctor_handoff.build_handoff_message(case)
    assert "Lakshmi" in message
    assert "28" in message
    assert "EMERGENCY" in message
    assert "pre-eclampsia warning pattern" in message
    assert case.case_id in message
    assert "severe headache" in message


def test_send_failure_is_queued_in_outbox_not_dropped(monkeypatch, tmp_path):
    db_path = tmp_path / "test_outbox.db"
    monkeypatch.setattr(outbox.config, "DATABASE_URL", f"sqlite:///{db_path}")
    outbox._engine = None

    monkeypatch.setattr(doctor_handoff.config, "ENABLE_DOCTOR_HANDOFF_SEND", True)
    monkeypatch.setattr(doctor_handoff.config, "DOCTOR_WHATSAPP_NUMBER", "+912222222222")
    monkeypatch.setattr(doctor_handoff.config, "TWILIO_WHATSAPP_FROM", "+911111111111")
    # No TWILIO_ACCOUNT_SID/AUTH_TOKEN in env -> _send_via_twilio_rest raises
    # ExternalCallFailed immediately, exercising the queue-on-failure path.
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)

    case = _pilot_emergency_case()
    status, detail = doctor_handoff.send_doctor_handoff(case)

    assert status == doctor_handoff.STATUS_FAILED_QUEUED
    pending = outbox.pending_messages()
    assert len(pending) == 1
    assert pending[0].case_id == case.case_id
    assert pending[0].kind == "doctor_handoff"
    assert pending[0].to_number == "+912222222222"

    outbox._engine = None
