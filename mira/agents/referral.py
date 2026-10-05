"""
Referral agent.

TRIAGE-SCOPE: outputs next steps, warning signs to watch for, a short
doctor-handoff script, and a facility type — never a specific drug or
dosage recommendation. The facility_type itself is not an LLM choice at
all; it's looked up directly from final_triage via the fixed taxonomy in
mira/knowledge/facilities.py, so urgency->facility mapping is
deterministic. The LLM writes the human-readable content (next steps,
warning signs, doctor script), and every piece of that text is passed
through knowledge/drug_dosage_filter.py as a hard backstop before being
accepted — if it matches a drug-name or dosage pattern, `apply` raises,
which mira/agents/base.py turns into an AgentFailure and the pipeline
degrades to the safe fallback rather than ever sending the tainted text to
a patient.

Output is structured (lists + a script string) rather than one free-text
paragraph specifically so mira/message_formatting.py can assemble a
consistent templated message (decision header, bullets, warning signs,
doctor script, footer) regardless of what the LLM produced — the STRUCTURE
is fixed in code, the CONTENT is LLM-generated per case.

Positioning/first-aid guidance (e.g. "lay the patient on their left side"),
what NOT to give (food/water before a possible procedure), and general
logistics (call an ambulance, bring pregnancy/medical records) are
in-scope here — these are non-drug actions, same category as facility
direction. Like everything clinical in this codebase, this content has NOT
been reviewed by a clinician yet (see docs/clinical_review_export.md) —
implementing the mechanism correctly doesn't substitute for that review.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..knowledge.drug_dosage_filter import check_referral_text
from ..knowledge.facilities import facility_for_urgency
from ..state import PatientCase
from .base import BaseAgent


class ReferralResponse(BaseModel):
    # Short, imperative action items — e.g. "Call 108 ambulance immediately",
    # "Keep her in a dark, quiet room". At least one is required; the
    # pipeline should never accept an empty next-steps set.
    next_steps: list[str] = Field(min_length=1)
    # Symptoms/signs that mean the situation has gotten worse and the
    # caregiver should act immediately (e.g. call the ambulance again,
    # go straight to the hospital). Optional — routine/mild cases may
    # not need one.
    warning_signs: list[str] = Field(default_factory=list)
    # A short, quotable sentence or two the ASHA worker/caregiver can read
    # or relay verbatim to a doctor by phone or in person — continuity-of-
    # care information (what's wrong, what's needed), not a diagnosis
    # asserted as fact. Required for EMERGENCY/URGENT; may be empty for
    # ROUTINE.
    doctor_handoff_script: str = ""
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)


class ReferralAgent(BaseAgent):
    name = "referral"
    response_model = ReferralResponse

    def build_prompt(self, case: PatientCase) -> tuple[str, str]:
        assert case.final_triage is not None, "Referral requires final_triage to be set"
        facility = facility_for_urgency(case.final_triage.value)
        system_prompt = (
            "You are the Referral agent in MIRA.\n\n"
            "TRIAGE-SCOPE: output next-steps guidance, warning signs, and a "
            "doctor-handoff script only. NEVER recommend a specific drug, "
            "medication, or dosage — not even a common over-the-counter "
            "suggestion — even if the symptoms seem to call for one. "
            "Non-drug actions (positioning, what not to give, calling for "
            "transport, bringing records) are in scope.\n\n"
            f"The urgency has already been decided as: {case.final_triage.value}. "
            f"The facility to direct the patient to is fixed: "
            f"{facility.facility_type} — {facility.description}\n\n"
            "Produce:\n"
            "1. next_steps — a short list of clear, imperative actions "
            "consistent with this facility and urgency (e.g. call for "
            "transport, positioning, what to bring, what NOT to give). "
            "At least one item, required.\n"
            "2. warning_signs — signs that mean things have gotten worse "
            "and the caregiver must act immediately. Leave empty for a "
            "routine, mild case if there's nothing meaningful to watch for.\n"
            "3. doctor_handoff_script — one or two sentences the ASHA "
            "worker/caregiver can read directly to a doctor by phone or in "
            "person: what's wrong (as a concern, not a diagnosis), how "
            "urgent, what's needed. Leave empty for routine cases with no "
            "doctor involved.\n\n"
            "Do not name any medicine or dose anywhere in any of these "
            "three fields."
        )
        tags = (case.normalized_ir or {}).get("symptom_tags", [])
        user_content = f"Symptom tags: {tags}\nUrgency: {case.final_triage.value}"
        return system_prompt, user_content

    def input_snapshot(self, case: PatientCase) -> dict:
        return {
            "final_triage": case.final_triage.value if case.final_triage else None,
            "normalized_ir": case.normalized_ir,
        }

    def apply(self, case: PatientCase, parsed: ReferralResponse) -> PatientCase:
        # One combined check across all three fields — a violation in any
        # of them must reject the whole response, never strip-and-continue.
        combined_text = "\n".join(
            [*parsed.next_steps, *parsed.warning_signs, parsed.doctor_handoff_script]
        )
        check_referral_text(combined_text)  # raises DrugDosageViolation on match

        updated = case.model_copy(deep=True)
        facility = facility_for_urgency(case.final_triage.value)
        updated.facility_type = facility.facility_type
        updated.next_steps_bullets = parsed.next_steps
        updated.warning_signs = parsed.warning_signs
        updated.doctor_handoff_script = parsed.doctor_handoff_script or None
        updated.next_steps = "; ".join(parsed.next_steps)  # flat form, see state.py
        updated.referral_reasoning = parsed.reasoning
        return updated
