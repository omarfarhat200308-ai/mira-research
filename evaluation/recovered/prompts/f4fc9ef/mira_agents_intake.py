"""
Intake agent: extracts structured symptom data from the raw WhatsApp
message. Must not let the pipeline proceed on incomplete critical data
(duration, severity, patient age/sex) — this is enforced independently of
whatever the LLM claims (see `apply` below), not merely by asking the LLM
to self-report completeness.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from .. import config
from ..state import (
    ClarificationRound,
    IntakeStatus,
    Patient,
    PatientCase,
    PipelineStatus,
    Sex,
    Symptom,
)
from .base import BaseAgent


class IntakeSymptom(BaseModel):
    name: str
    onset: Optional[str] = None
    duration: Optional[str] = None
    severity: Optional[str] = None
    notes: Optional[str] = None


class IntakeResponse(BaseModel):
    # Optional, never a blocking/critical field — an ASHA worker may not
    # state a name, and the pipeline must not stall waiting for one. Used
    # only to enrich the Stage 5 doctor-handoff message when available.
    name: Optional[str] = None
    age: Optional[int] = None
    sex: Optional[str] = None
    is_pregnant: Optional[bool] = None
    symptoms: list[IntakeSymptom] = Field(default_factory=list)
    clarifying_question: Optional[str] = None
    # Detected here (not only later in LanguageNormalizeAgent) specifically
    # so a clarifying question can be asked in the patient's own language
    # instead of defaulting to English — see the clarifying_question prompt
    # instruction below. A real usability blocker in live testing, not a
    # theoretical gap: an ASHA worker/caregiver who doesn't read English
    # got an English-only question and had no way to answer it.
    detected_language: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class IntakeAgent(BaseAgent):
    name = "intake"
    response_model = IntakeResponse

    def build_prompt(self, case: PatientCase) -> tuple[str, str]:
        if case.preferred_language:
            # The ASHA worker already told us their language once (see
            # mira/language_poll.py) — use it directly, don't re-guess per
            # message. Language can genuinely drift message to message if
            # left to auto-detection (one message in English, the next in
            # Hindi); an explicit preference must win over that every time.
            lang_name = config.LANGUAGE_NAMES.get(case.preferred_language, "English")
            language_instruction = (
                f"The patient/ASHA worker has already told MIRA they want to "
                f"communicate in {lang_name} — set detected_language to "
                f"'{case.preferred_language}' regardless of what script or "
                "language this particular message happens to be written in, "
                f"and write clarifying_question in {lang_name}."
            )
        else:
            language_instruction = (
                "Also detect which language the patient's message is "
                f"written in (respond with one of these codes: "
                f"{', '.join(config.SUPPORTED_LANGUAGES)} — use 'en' if "
                "English, romanized-but-clearly-English, or genuinely "
                "unclear), and write clarifying_question in that SAME "
                "language — never default to English for it. The person "
                "reading it may not read English at all; a question they "
                "can't understand is as useless as no question."
            )
        system_prompt = (
            "You are the Intake agent in MIRA, a WhatsApp clinical triage "
            "system for rural India. Extract structured data from the "
            "patient's raw message: the patient's name if stated (do not "
            "ask for it if not given — never treat it as missing/blocking), "
            "age (years), sex (male/female/other), whether pregnant if "
            "relevant, and a list of symptoms — each with a name, onset, "
            "duration, and severity (mild/moderate/severe or a short "
            "description).\n\n"
            f"{language_instruction}\n\n"
            "If age, sex, or the primary symptom's duration/severity is "
            "missing or unclear from the message, do NOT guess or "
            "infer it — leave that field null and instead propose one "
            "short, direct clarifying question asking for exactly the "
            "missing information. Only ask about what's actually missing.\n\n"
            "CRITICAL: for Hindi, Telugu, or Urdu specifically "
            f"({', '.join(sorted(config.ROMANIZE_LANGUAGES))}), write "
            "clarifying_question in ROMANIZED (Latin-script) form as "
            "commonly typed on WhatsApp (e.g. \"bacche ki umar kitni hai?\"), "
            "NOT native script — ASHA workers in this deployment read/type "
            "romanized text day to day, not native script, even though "
            "they speak these languages fluently."
        )
        # Reads normalized_input_text (romanization-glossed, see
        # mira/language/romanization.py) when the pre-processing step
        # produced one; falls back to the verbatim message otherwise
        # (native-script input, or nothing recognized to gloss).
        message_for_intake = case.normalized_input_text or case.raw_input_text
        user_content = f"Patient message:\n{message_for_intake}"
        if case.clarification_history:
            qa_lines = []
            for round_ in case.clarification_history:
                qa_lines.append(f"We asked: {round_.question}")
                if round_.answer is not None:
                    qa_lines.append(f"Patient answered: {round_.answer}")
            user_content += "\n\nClarification exchange so far:\n" + "\n".join(qa_lines)
        return system_prompt, user_content

    def input_snapshot(self, case: PatientCase) -> dict:
        return {
            "raw_input_text": case.raw_input_text,
            "normalized_input_text": case.normalized_input_text,
            "clarification_history": [r.model_dump() for r in case.clarification_history],
        }

    def apply(self, case: PatientCase, parsed: IntakeResponse) -> PatientCase:
        symptoms = [
            Symptom(
                name=s.name,
                onset=s.onset,
                duration=s.duration,
                severity=s.severity,
                notes=s.notes,
            )
            for s in parsed.symptoms
        ]

        sex: Sex | None = None
        if parsed.sex:
            try:
                sex = Sex(parsed.sex.strip().lower())
            except ValueError:
                sex = None

        patient = Patient(name=parsed.name, age=parsed.age, sex=sex, is_pregnant=parsed.is_pregnant)

        # Hardcoded critical-field check — independent of whatever the LLM
        # thinks it captured. This is the "must not proceed on incomplete
        # critical data" guarantee.
        missing: list[str] = []
        if patient.age is None:
            missing.append("age")
        if patient.sex is None:
            missing.append("sex")
        if not symptoms:
            missing.append("primary_symptom")
        else:
            primary = symptoms[0]
            if not primary.duration:
                missing.append("duration")
            if not primary.severity:
                missing.append("severity")

        updated = case.model_copy(deep=True)
        updated.patient = patient
        updated.symptoms = symptoms
        updated.missing_critical_fields = missing

        # Set early (before LanguageNormalizeAgent, which only runs once
        # Intake is COMPLETE) specifically so a clarifying question can be
        # asked in the patient's own language — see build_prompt above.
        # A preference on file wins outright — hard override, not just an
        # instruction the model might not follow — since the whole point
        # of the poll is to stop language drifting message to message.
        if case.preferred_language:
            updated.detected_language = case.preferred_language
        elif parsed.detected_language in config.SUPPORTED_LANGUAGES:
            updated.detected_language = parsed.detected_language

        if missing:
            updated.intake_status = IntakeStatus.NEEDS_CLARIFICATION
            # The English fallback text below only fires if the LLM omitted
            # clarifying_question entirely despite being asked for one —
            # a residual, hardcoded-English gap for that specific
            # fallback-of-a-fallback case (real translation isn't possible
            # for static Python text without another LLM call, and this
            # path should be rare). The normal path is parsed.clarifying_question,
            # which is instructed to already be in the patient's language.
            updated.pending_clarifying_question = parsed.clarifying_question or (
                "Could you please share the patient's " + ", ".join(missing) + "?"
            )
            updated.pipeline_status = PipelineStatus.AWAITING_CLARIFICATION
            # Record the question in the audit trail; the answer is filled
            # in by pipeline.run_pipeline when the patient's reply resumes
            # this case. Round-count capping is enforced by the pipeline
            # (config.MAX_CLARIFICATION_ROUNDS), not here.
            updated.clarification_history.append(
                ClarificationRound(question=updated.pending_clarifying_question)
            )
        else:
            updated.intake_status = IntakeStatus.COMPLETE
            updated.pending_clarifying_question = None

        return updated
