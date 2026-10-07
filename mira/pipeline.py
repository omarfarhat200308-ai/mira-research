"""
Pipeline orchestrator: Intake -> Language(normalize) -> Diagnostic ->
Triage -> Referral -> Language(translate).

Two hard rules enforced here, independent of any single agent's code:

1. If Intake determines critical data is missing, the pipeline halts and
   returns the case as-is (pipeline_status=AWAITING_CLARIFICATION) — it
   never proceeds to Diagnostic/Triage/Referral on incomplete data.
2. If any agent fails (exception, timeout, malformed/unvalidatable output),
   the pipeline does not guess or improvise. It degrades the case to a
   hardcoded safe fallback: a non-ROUTINE urgency and the literal
   "refer to nearest clinic" text from mira.config.FAILSAFE_REFERRAL_TEXT —
   never an LLM-generated approximation of it.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from . import config, logging_store
from .agents.base import AgentFailure
from .agents.diagnostic import DiagnosticAgent
from .agents.intake import IntakeAgent
from .agents.language import LanguageNormalizeAgent, LanguageTranslateAgent
from .agents.referral import ReferralAgent
from .agents.triage import TriageAgent
from .language.romanization import normalize_romanized_text
from .llm_client import LLMClient, build_default_client
from .notifications import doctor_handoff
from .safety import precheck
from .state import DataSource, IntakeStatus, PatientCase, PipelineStatus, TriageDecidedBy, Urgency


def _precheck_fired(case: PatientCase) -> list[str]:
    answers = [r.answer for r in case.clarification_history]
    return precheck.screen(case.raw_input_text, case.normalized_input_text, *answers)


def _apply_interim_safety(case: PatientCase) -> PatientCase:
    """Intake halted for a missing field. Never leave the sender with only a
    question: attach a safety message, and escalate to EMERGENCY (which also
    triggers Stage 5 handoff in _finalize) if the deterministic pre-screen
    fires. pipeline_status stays AWAITING_CLARIFICATION so the case can still
    resume; the Triage stage overwrites final_triage on resume."""
    updated = case.model_copy(deep=True)
    fired = _precheck_fired(updated)
    question = updated.pending_clarifying_question or ""
    if fired:
        updated.final_triage = Urgency.EMERGENCY
        updated.triage_decided_by = TriageDecidedBy.RULE_OVERRIDE
        updated.red_flags_triggered = fired
        head = config.INTERIM_EMERGENCY_TEXT
    else:
        head = config.INTERIM_SAFETY_TEXT
    updated.patient_facing_reply = f"{head}\n\n{question}".strip()
    return updated


def _apply_failsafe_degradation(case: PatientCase, failed_agent: str, reason: str) -> PatientCase:
    """The literal graceful-degradation path: any agent failure lands here,
    never on a guess. Overwrites referral output with the hardcoded
    fail-safe text regardless of what (if anything) was computed before the
    failure, and ensures final_triage is never left at ROUTINE or unset."""
    updated = case.model_copy(deep=True)
    updated.pipeline_status = PipelineStatus.DEGRADED
    updated.failed_agent = failed_agent
    updated.failure_reason = reason

    # v2: if the deterministic text pre-screen sees a red flag, a failed
    # stage must degrade to EMERGENCY, not merely URGENT.
    fired = _precheck_fired(updated)
    if fired and updated.final_triage != Urgency.EMERGENCY:
        updated.final_triage = Urgency.EMERGENCY
        updated.triage_decided_by = TriageDecidedBy.RULE_OVERRIDE
        updated.red_flags_triggered = fired
    elif updated.final_triage is None or updated.final_triage == Urgency.ROUTINE:
        updated.final_triage = Urgency.URGENT
        updated.triage_decided_by = TriageDecidedBy.FAILSAFE_DEGRADED

    updated.facility_type = (
        "Nearest available clinic or health facility (fail-safe default — "
        "full assessment could not be completed)"
    )
    updated.next_steps = config.FAILSAFE_REFERRAL_TEXT
    updated.referral_reasoning = f"Pipeline degraded at stage '{failed_agent}': {reason}"
    updated.patient_facing_reply = config.FAILSAFE_REFERRAL_TEXT
    return updated


def _finalize(case: PatientCase) -> PatientCase:
    """Every return point in run_pipeline funnels through here: Stage 5
    doctor handoff is always evaluated (send_doctor_handoff no-ops safely
    when final_triage isn't EMERGENCY/URGENT — e.g. still
    AWAITING_CLARIFICATION — so it's safe to call unconditionally rather
    than duplicating the gate logic at each call site), then the case is
    logged. A fail-safe-degraded case that landed on URGENT is exactly the
    kind of uncertain case Stage 5 exists for — the receiving facility
    should know an unassessed, MIRA-referred case is coming, same as a
    normally-completed URGENT case."""
    status, detail = doctor_handoff.send_doctor_handoff(case)
    case.doctor_handoff_status = status
    case.doctor_handoff_detail = detail
    if status == doctor_handoff.STATUS_SENT:
        case.doctor_handoff_sent_at = datetime.now(timezone.utc)
    elif status == doctor_handoff.STATUS_FAILED_QUEUED:
        case.patient_facing_reply = (
            (case.patient_facing_reply or "")
            + "\n\n[MIRA could not automatically notify the receiving "
            "doctor — please follow up verbally to confirm this referral "
            "was received.]"
        )

    logging_store.log_case_final_state(case)
    return case


def run_pipeline(
    raw_input_text: str,
    source_phone_number: Optional[str] = None,
    llm_client: Optional[LLMClient] = None,
    resume_case: Optional[PatientCase] = None,
    data_source: DataSource = DataSource.SIMULATED,
    asha_worker_id: Optional[str] = None,
    preferred_language: Optional[str] = None,
) -> PatientCase:
    """
    `resume_case`: a case previously parked awaiting clarification (see
    mira/session_store.py). When provided, `raw_input_text` is treated as
    the patient's ANSWER to the pending clarifying question, recorded on
    the same case (same case_id) so the audit trail stays contiguous, and
    Intake re-runs with the full Q/A history in view.

    `data_source`: simulated (default) vs pilot — an explicit, deploy-time
    decision (see mira/webhook.py), never inferred. Gates whether Stage 5's
    doctor handoff can actually send (mira/notifications/doctor_handoff.py).

    `preferred_language`: from mira/language_preference_store.py's one-time
    poll — when set, overrides Intake/LanguageNormalize's own per-message
    language auto-detection (see their build_prompt methods), so language
    stays consistent for a given ASHA worker across every message, not
    just within one case.
    """
    client = llm_client or build_default_client()
    if resume_case is not None:
        case = resume_case.model_copy(deep=True)
        if case.clarification_history and case.clarification_history[-1].answer is None:
            case.clarification_history[-1].answer = raw_input_text
        case.pending_clarifying_question = None
        case.pipeline_status = PipelineStatus.OK
    else:
        case = PatientCase(
            raw_input_text=raw_input_text,
            source_phone_number=source_phone_number,
            asha_worker_id=asha_worker_id or source_phone_number,
            data_source=data_source,
            preferred_language=preferred_language,
        )
        # Romanization pre-processing runs once, before Intake, on every
        # new case (not on clarification resumes — the original message
        # was already normalized on its first pass). See
        # mira/language/romanization.py for what this does and doesn't do.
        romanized = normalize_romanized_text(raw_input_text)
        case.normalized_input_text = romanized.normalized_text
        case.detected_script = romanized.detected_script
        case.romanized_terms_glossed = romanized.glossed_terms

    intake = IntakeAgent()
    language_normalize = LanguageNormalizeAgent()
    diagnostic = DiagnosticAgent()
    triage = TriageAgent()
    referral = ReferralAgent()
    language_translate = LanguageTranslateAgent()

    try:
        case = intake.run(case, client)
    except AgentFailure as exc:
        case = _apply_failsafe_degradation(case, exc.agent_name, exc.reason)
        return _finalize(case)

    if case.intake_status == IntakeStatus.NEEDS_CLARIFICATION:
        # Hard rule: never proceed on incomplete critical data. But also
        # never loop forever asking a patient who can't provide it — past
        # the round cap, "go to the nearest clinic" is the safer outcome
        # than continuing to block on missing fields.
        if len(case.clarification_history) > config.MAX_CLARIFICATION_ROUNDS:
            case = _apply_failsafe_degradation(
                case,
                "intake",
                f"critical fields still missing after "
                f"{config.MAX_CLARIFICATION_ROUNDS} clarification rounds: "
                f"{case.missing_critical_fields}",
            )
        else:
            case = _apply_interim_safety(case)
        return _finalize(case)

    for agent in (language_normalize, diagnostic, triage, referral):
        try:
            case = agent.run(case, client)
        except AgentFailure as exc:
            case = _apply_failsafe_degradation(case, exc.agent_name, exc.reason)
            return _finalize(case)

    try:
        case = language_translate.run(case, client)
    except AgentFailure as exc:
        # A translation failure alone shouldn't erase an already-correct
        # triage decision — fall back to an untranslated (English)
        # fail-safe-styled message instead of the full degradation path,
        # but never silently fabricate a translation.
        updated = case.model_copy(deep=True)
        updated.pipeline_status = PipelineStatus.DEGRADED
        updated.failed_agent = exc.agent_name
        updated.failure_reason = exc.reason
        urgency_str = case.final_triage.value if case.final_triage else "unknown"
        updated.patient_facing_reply = (
            f"[Translation unavailable] Urgency: {urgency_str}. "
            f"Facility: {case.facility_type}. {case.next_steps}"
        )
        case = updated

    return _finalize(case)
