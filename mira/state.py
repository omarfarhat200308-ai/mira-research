"""
The PatientCase state object: the single source of truth passed explicitly
between agents in the pipeline.

Design intent: nothing about a triage decision should live only inside an
LLM's chat history. Every field below is written by exactly one named agent
(noted in each field's description) and is inspectable after a pipeline run
— this is what makes the system auditable for clinical review and for the
paper. Agents receive a PatientCase and return an updated copy; they never
mutate shared conversational state.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


def _new_case_id() -> str:
    return f"case_{uuid.uuid4().hex[:12]}"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Sex(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class IntakeStatus(str, Enum):
    COMPLETE = "complete"
    NEEDS_CLARIFICATION = "needs_clarification"


class Urgency(str, Enum):
    EMERGENCY = "emergency"
    URGENT = "urgent"
    ROUTINE = "routine"


class TriageDecidedBy(str, Enum):
    RULE_OVERRIDE = "rule_override"
    LLM = "llm"
    FAILSAFE_DEGRADED = "failsafe_degraded"


class PipelineStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    FAILED = "failed"
    AWAITING_CLARIFICATION = "awaiting_clarification"


class DataSource(str, Enum):
    """Simulated (intern/synthetic test traffic) vs. pilot (real patient
    interaction under the approved DHS/IEC-cleared protocol). Set once at
    case creation (mira/pipeline.py) from an explicit deploy-time flag —
    never inferred — and carried on every log line so simulated and pilot
    results can never be blended in analysis or in the paper. See
    mira/logging_store.py for the read-side filter."""

    SIMULATED = "simulated"
    PILOT = "pilot"


class InputKind(str, Enum):
    TEXT = "text"
    VOICE = "voice"


class ClarificationRound(BaseModel):
    question: str
    answer: Optional[str] = None  # filled in when the patient replies


class ProtocolReference(BaseModel):
    """One retrieved passage that grounded a Diagnostic/Triage call — the
    audit trail entry that makes a classification traceable back to a
    specific protocol line rather than just 'the model decided'. See
    mira/knowledge/rag.py."""

    source: str          # which of the 3 corpus documents (see knowledge/rag.py)
    chunk_id: str
    snippet: str
    retrieved_for_agent: str


class Patient(BaseModel):
    name: Optional[str] = None  # optional; never a required/blocking field
    age: Optional[int] = None
    sex: Optional[Sex] = None
    is_pregnant: Optional[bool] = None


class Symptom(BaseModel):
    name: str
    onset: Optional[str] = None       # e.g. "3 days ago", free text is fine
    duration: Optional[str] = None    # e.g. "ongoing", "2 hours"
    severity: Optional[str] = None    # descriptive (mild/moderate/severe) or 1-10
    notes: Optional[str] = None


class DifferentialCandidate(BaseModel):
    condition: str                    # must be a member of knowledge.conditions.CONDITIONS
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)


class TriageAssessment(BaseModel):
    urgency: Urgency
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)


class PatientCase(BaseModel):
    # --- pipeline bookkeeping ---
    case_id: str = Field(default_factory=_new_case_id)
    created_at: datetime = Field(default_factory=_utcnow)
    raw_input_text: str
    source_phone_number: Optional[str] = None
    # The ASHA worker's own identifier for continuity-of-care messages
    # (Stage 5 doctor handoff). No separate ASHA-worker registry exists yet,
    # so this defaults to source_phone_number in pipeline.run_pipeline.
    asha_worker_id: Optional[str] = None
    input_kind: InputKind = InputKind.TEXT

    # simulated (intern/synthetic) vs pilot (real patient, DHS/IEC-cleared
    # protocol) — set once at case creation, never inferred. See DataSource.
    data_source: DataSource = DataSource.SIMULATED

    # Set once, at case creation, from mira/language_preference_store.py's
    # one-time per-phone-number poll (see mira/language_poll.py) — an
    # explicit choice that overrides Intake/LanguageNormalize's own
    # per-message auto-detection, so language never drifts message to
    # message for the same ASHA worker. None means no preference is on
    # file yet (webhook.py's poll gate handles that before the pipeline
    # ever runs) or this case predates the poll feature.
    preferred_language: Optional[str] = None

    # Set by the romanization-normalization pre-processing step
    # (mira/language/romanization.py), which runs before Intake. Holds the
    # script-detected + glossed version of raw_input_text; Intake reads this
    # when present, raw_input_text otherwise. Kept separate from
    # raw_input_text so the original patient message is always preserved
    # verbatim in the audit trail.
    normalized_input_text: Optional[str] = None
    detected_script: Optional[str] = None  # "latin" | "devanagari" | "telugu" | "mixed"
    romanized_terms_glossed: list[str] = Field(default_factory=list)

    pipeline_status: PipelineStatus = PipelineStatus.OK
    failed_agent: Optional[str] = None
    failure_reason: Optional[str] = None

    # --- written by Intake agent ---
    patient: Patient = Field(default_factory=Patient)
    symptoms: list[Symptom] = Field(default_factory=list)
    missing_critical_fields: list[str] = Field(default_factory=list)
    pending_clarifying_question: Optional[str] = None
    intake_status: Optional[IntakeStatus] = None
    # Full Q/A history across WhatsApp round-trips, kept on the same case
    # (same case_id) so the audit trail shows exactly what was asked and
    # answered before the pipeline proceeded. Length is capped by
    # config.MAX_CLARIFICATION_ROUNDS in pipeline.py.
    clarification_history: list[ClarificationRound] = Field(default_factory=list)

    # --- written by Language agent ---
    detected_language: Optional[str] = None       # ISO code, e.g. "hi"
    normalized_ir: Optional[dict] = None           # language-agnostic structured symptoms
    translation_consistency_ok: Optional[bool] = None
    patient_facing_reply: Optional[str] = None     # final reply, translated to detected_language

    # --- written by Diagnostic agent ---
    # DIAGNOSTIC-SCOPE: this is a bounded differential feeding urgency
    # estimation only. It is never presented to the patient as a diagnosis.
    differential: list[DifferentialCandidate] = Field(default_factory=list)

    # --- written by Triage agent ---
    red_flags_triggered: list[str] = Field(default_factory=list)
    llm_triage_assessment: Optional[TriageAssessment] = None
    final_triage: Optional[Urgency] = None
    triage_decided_by: Optional[TriageDecidedBy] = None

    # --- written by Referral agent ---
    # TRIAGE-SCOPE: facility type + next steps only. Never a drug or dosage.
    facility_type: Optional[str] = None
    # Flat, semicolon-joined form of next_steps_bullets — kept for backward
    # compatibility with the fail-safe/translation-failure fallback paths
    # in pipeline.py, which predate the structured message format below.
    next_steps: Optional[str] = None
    referral_reasoning: Optional[str] = None

    # Structured content for the patient/ASHA-worker-facing message
    # (mira/message_formatting.py assembles these into the final templated
    # reply). English as written by Referral; overwritten in place with
    # translated text by Language(translate) — the audit trail for the
    # English originals lives in the per-call agent log, not here.
    next_steps_bullets: list[str] = Field(default_factory=list)
    warning_signs: list[str] = Field(default_factory=list)
    doctor_handoff_script: Optional[str] = None

    # --- RAG grounding audit trail (Diagnostic + Triage) ---
    # Which protocol passage(s) informed each reasoning call — see
    # mira/knowledge/rag.py. Populated regardless of provider.
    protocol_references: list[ProtocolReference] = Field(default_factory=list)

    # --- model provenance / cost audit (every agent call) ---
    # agent_name -> "provider:model", e.g. "anthropic:claude-sonnet-5" or
    # "groq:llama-3.3-70b-versatile" after a fallback. Per-call token counts
    # live in the append-only agent-call log (mira/logging_store.py), not
    # here, to keep this a compact summary.
    model_provenance: dict[str, str] = Field(default_factory=dict)
    # Human-readable record of any Anthropic->Groq failover that happened
    # during this case, so "which model produced which output" is visible
    # on the case itself, not just buried in the per-call log.
    fallback_events: list[str] = Field(default_factory=list)

    # --- Stage 5: doctor handoff (RED/YELLOW only) ---
    doctor_handoff_status: Optional[str] = None  # see mira/notifications/doctor_handoff.py
    doctor_handoff_detail: Optional[str] = None
    doctor_handoff_sent_at: Optional[datetime] = None

    model_config = {
        "use_enum_values": False,
    }
