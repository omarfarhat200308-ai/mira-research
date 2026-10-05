"""
Language agent. Implemented as two operations run at two points in the
pipeline (see mira/pipeline.py) — normalize on the way in, translate on the
way out — but conceptually the single "Language agent" from the design:

- LanguageNormalizeAgent: detects the patient's language and normalizes
  Intake's (possibly non-English, possibly loose free-text) symptom
  descriptions onto the fixed canonical tag vocabulary
  (mira/knowledge/symptom_tags.py) that Diagnostic and the red-flag rule
  engine consume. This is what makes Diagnostic/Triage language-agnostic.
- LanguageTranslateAgent: translates the final triage/referral result back
  into the patient's detected language, without altering any clinical
  content — only wording.

Known scope limitation (documented, not silently ignored): if Intake halts
for clarification, the clarifying question is not yet translated, since
language detection happens after Intake in this pipeline ordering. Given
this session's scope is architecture/safety/audit, not full localization
polish, that's left as a follow-up rather than solved here.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from .. import config
from ..knowledge.drug_dosage_filter import check_referral_text
from ..knowledge.symptom_tags import SYMPTOM_TAGS, is_valid_tag
from ..message_formatting import format_patient_message
from ..state import PatientCase
from .base import BaseAgent


class LanguageNormalizeResponse(BaseModel):
    detected_language: str
    symptom_tags: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class LanguageNormalizeAgent(BaseAgent):
    name = "language_normalize"
    response_model = LanguageNormalizeResponse

    def build_prompt(self, case: PatientCase) -> tuple[str, str]:
        if case.preferred_language:
            # Same override rationale as intake.py's build_prompt — an
            # explicit, one-time preference (mira/language_poll.py) beats
            # re-detecting per message.
            lang_name = config.LANGUAGE_NAMES.get(case.preferred_language, "English")
            language_instruction = (
                f"The patient/ASHA worker has already told MIRA they want "
                f"to communicate in {lang_name} — respond with "
                f"detected_language='{case.preferred_language}' regardless "
                "of what script or language this message happens to use."
            )
        else:
            language_instruction = (
                "Detect which language the patient is communicating in "
                f"(respond with one of these codes: {', '.join(config.SUPPORTED_LANGUAGES)} "
                "— use 'en' if English or unclear)."
            )
        system_prompt = (
            "You are the Language agent in MIRA, operating in normalization "
            f"mode. {language_instruction}\n\n"
            "Then map the patient's reported symptoms onto this FIXED "
            "canonical tag vocabulary only — do not invent new tags, and "
            "only include a tag if it is clearly supported by what the "
            "patient actually said:\n"
            + ", ".join(sorted(SYMPTOM_TAGS))
        )
        symptom_desc = "\n".join(
            f"- {s.name} (onset={s.onset}, duration={s.duration}, severity={s.severity})"
            for s in case.symptoms
        )
        user_content = (
            f"Original patient message:\n{case.raw_input_text}\n\n"
            f"Extracted symptoms:\n{symptom_desc}"
        )
        return system_prompt, user_content

    def input_snapshot(self, case: PatientCase) -> dict:
        return {
            "raw_input_text": case.raw_input_text,
            "symptoms": [s.model_dump() for s in case.symptoms],
        }

    def apply(self, case: PatientCase, parsed: LanguageNormalizeResponse) -> PatientCase:
        updated = case.model_copy(deep=True)
        valid_tags = [t for t in parsed.symptom_tags if is_valid_tag(t)]

        # A preference on file is a hard override — never let this agent's
        # own (possibly different) detection clobber it, same rationale as
        # intake.py's apply().
        if case.preferred_language:
            detected = case.preferred_language
        elif parsed.detected_language in config.SUPPORTED_LANGUAGES:
            detected = parsed.detected_language
        else:
            detected = "en"

        updated.detected_language = detected
        updated.normalized_ir = {
            "symptom_tags": valid_tags,
            "patient": {
                "age": case.patient.age,
                "sex": case.patient.sex.value if case.patient.sex else None,
                "is_pregnant": case.patient.is_pregnant,
            },
        }
        # Sanity check: if Intake recorded symptoms but none survived tag
        # mapping, that's a translation/normalization consistency problem
        # worth flagging in the audit trail (not on its own a hard failure —
        # Triage's red-flag rules and LLM judgment still run against
        # whatever mapped).
        updated.translation_consistency_ok = bool(valid_tags) or not case.symptoms
        return updated


class LanguageTranslateResponse(BaseModel):
    # Structured, matching Referral's output shape — see referral.py and
    # message_formatting.py, which assembles these into the final templated
    # message. Translated one-for-one; same count as the English originals.
    translated_next_steps: list[str] = Field(min_length=1)
    translated_warning_signs: list[str] = Field(default_factory=list)
    translated_doctor_handoff_script: str = ""
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class LanguageTranslateAgent(BaseAgent):
    name = "language_translate"
    response_model = LanguageTranslateResponse

    def build_prompt(self, case: PatientCase) -> tuple[str, str]:
        lang_code = case.detected_language or "en"
        lang_name = config.LANGUAGE_NAMES.get(lang_code, "English")
        romanize_instruction = ""
        if lang_code in config.ROMANIZE_LANGUAGES:
            romanize_instruction = (
                f"\n\nIMPORTANT: write {lang_name} in ROMANIZED (Latin-script) "
                "form, as commonly typed on WhatsApp (e.g. \"ambulance ko "
                "turant bulayen\") — NOT native script. ASHA workers in this "
                "deployment read/type romanized text day to day, not native "
                "script, even though they speak this language fluently."
            )
        system_prompt = (
            f"You are the Language agent in MIRA, operating in translation "
            f"mode. Translate the following triage next-steps, warning "
            f"signs, and doctor-handoff script into {lang_name}, simply and "
            "clearly, for a patient/caregiver/ASHA worker with limited "
            "medical literacy. Do not add, remove, soften, or alter any "
            "clinical content, urgency level, or facility recommendation — "
            "translate faithfully only, one item for one item (same count "
            "in, same count out). Never add a drug name or dosage."
            f"{romanize_instruction}"
        )
        user_content = (
            "Next steps:\n" + "\n".join(f"- {s}" for s in case.next_steps_bullets)
            + "\n\nWarning signs:\n"
            + ("\n".join(f"- {s}" for s in case.warning_signs) or "(none)")
            + f"\n\nDoctor handoff script:\n{case.doctor_handoff_script or '(none)'}"
        )
        return system_prompt, user_content

    def input_snapshot(self, case: PatientCase) -> dict:
        return {
            "final_triage": case.final_triage.value if case.final_triage else None,
            "facility_type": case.facility_type,
            "next_steps_bullets": case.next_steps_bullets,
            "warning_signs": case.warning_signs,
            "doctor_handoff_script": case.doctor_handoff_script,
            "detected_language": case.detected_language,
        }

    def apply(self, case: PatientCase, parsed: LanguageTranslateResponse) -> PatientCase:
        # Defense-in-depth: the same drug/dosage backstop that gates
        # Referral's English output also gates the translated output —
        # cheap/no-op for native-script languages the regex can't match,
        # genuinely useful for the romanized-Latin-script languages where
        # a drug name could slip through translation unchanged.
        combined_text = "\n".join([
            *parsed.translated_next_steps,
            *parsed.translated_warning_signs,
            parsed.translated_doctor_handoff_script,
        ])
        check_referral_text(combined_text)

        updated = case.model_copy(deep=True)
        updated.next_steps_bullets = parsed.translated_next_steps
        updated.warning_signs = parsed.translated_warning_signs
        updated.doctor_handoff_script = parsed.translated_doctor_handoff_script or None
        updated.next_steps = "; ".join(parsed.translated_next_steps)
        updated.patient_facing_reply = format_patient_message(updated)
        return updated
