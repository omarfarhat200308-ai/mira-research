"""
Hardcoded, non-LLM red-flag rule engine.

This module is the safety net referenced throughout MIRA's design: it is
plain Python — no prompt, no model call, no dependency on anything an LLM
said — and its output cannot be overridden by any agent downstream (see
mira/agents/triage.py, which runs this module FIRST and treats a triggered
rule as final regardless of what the LLM concludes).

Each rule carries a one-line clinical rationale in-code specifically so a
non-engineer clinical reviewer (co-advisor) can audit and amend this list
without reading the rest of the codebase. Rules should only be added or
changed with clinical sign-off — this is a v1 list, not exhaustive, and is
expected to grow.

Rules operate only on the canonical symptom tags in
mira/knowledge/symptom_tags.py and basic patient demographics — never on
raw or translated free text — so matching is deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class RedFlagRule:
    rule_id: str
    description: str
    clinical_rationale: str
    matches: Callable[[set[str], dict], bool]


def _tags(normalized_ir: dict) -> set[str]:
    return set(normalized_ir.get("symptom_tags", []) or [])


def _patient(normalized_ir: dict) -> dict:
    return normalized_ir.get("patient", {}) or {}


def _is_infant(patient: dict) -> bool:
    age = patient.get("age")
    # age is expected in years; callers should express infants as < 1 (e.g. 0)
    return age is not None and age < 2


RULES: list[RedFlagRule] = [
    RedFlagRule(
        rule_id="cardio_chest_pain_with_dyspnea",
        description="Chest pain with shortness of breath",
        clinical_rationale=(
            "Combination is a classic acute coronary syndrome / pulmonary "
            "embolism presentation; time-to-treatment materially affects "
            "outcome, so this is never downgraded regardless of model "
            "confidence."
        ),
        matches=lambda tags, patient: (
            "chest_pain" in tags and "shortness_of_breath" in tags
        ),
    ),
    RedFlagRule(
        rule_id="obstetric_preeclampsia_pattern",
        description=(
            "Pregnancy with severe headache, visual disturbance, or "
            "epigastric pain, plus hypertension or edema"
        ),
        clinical_rationale=(
            "Classic pre-eclampsia/eclampsia warning pattern in pregnancy; "
            "can progress to seizure and maternal/fetal death within hours "
            "if untreated."
        ),
        matches=lambda tags, patient: (
            ("pregnant" in tags or patient.get("is_pregnant") is True)
            and bool(
                tags & {"severe_headache", "visual_disturbance", "epigastric_pain"}
            )
            and bool(tags & {"hypertension_known_or_suspected", "swelling_edema"})
        ),
    ),
    RedFlagRule(
        rule_id="obstetric_heavy_bleeding",
        description="Heavy vaginal or postpartum bleeding",
        clinical_rationale=(
            "Obstetric hemorrhage is a leading cause of maternal mortality "
            "and can deteriorate very quickly; always treated as time-critical."
        ),
        matches=lambda tags, patient: bool(
            tags & {"vaginal_bleeding_heavy", "postpartum_bleeding_heavy"}
        ),
    ),
    RedFlagRule(
        rule_id="infant_fever_meningitis_pattern",
        description="Infant with fever and stiff neck or bulging fontanelle",
        clinical_rationale=(
            "Classic pediatric meningitis warning signs; infants "
            "deteriorate faster than adults and delayed care carries high "
            "mortality/morbidity risk."
        ),
        matches=lambda tags, patient: (
            _is_infant(patient)
            and bool(tags & {"fever", "high_fever"})
            and bool(tags & {"stiff_neck", "bulging_fontanelle"})
        ),
    ),
    RedFlagRule(
        rule_id="neuro_seizure_or_loc",
        description="Seizure or loss of consciousness",
        clinical_rationale=(
            "Both indicate a potential acute neurological, metabolic, or "
            "cardiac emergency; safest default is immediate emergency "
            "referral pending in-person evaluation."
        ),
        matches=lambda tags, patient: bool(
            tags & {"seizure", "loss_of_consciousness"}
        ),
    ),
    RedFlagRule(
        rule_id="neuro_stroke_pattern",
        description="One-sided weakness or slurred speech",
        clinical_rationale=(
            "Possible acute stroke; treatment window is narrow and "
            "time-sensitive, so this is never left to LLM judgment alone."
        ),
        matches=lambda tags, patient: bool(
            tags & {"one_sided_weakness", "slurred_speech"}
        ),
    ),
    RedFlagRule(
        rule_id="severe_external_bleeding_or_major_trauma",
        description="Heavy external bleeding or major trauma",
        clinical_rationale=(
            "Hemorrhagic shock risk; always treated as emergency pending "
            "in-person assessment."
        ),
        matches=lambda tags, patient: bool(
            tags & {"external_bleeding_heavy"}
        )
        or ("trauma_injury" in tags and "fracture_suspected" in tags),
    ),
    RedFlagRule(
        rule_id="gi_bleeding",
        description="Vomiting blood or black/bloody stool",
        clinical_rationale=(
            "Signs of active gastrointestinal hemorrhage; can be "
            "life-threatening and is not deprioritized based on model "
            "confidence."
        ),
        matches=lambda tags, patient: bool(
            tags & {"vomiting_blood", "black_or_bloody_stool"}
        ),
    ),
]


def evaluate_red_flags(normalized_ir: dict) -> list[str]:
    """
    Returns the list of rule_ids that fired for this case. An empty list
    means no hardcoded rule matched — it does NOT mean the case is safe;
    the LLM triage assessment is still consulted in that case (see
    mira/agents/triage.py).
    """
    tags = _tags(normalized_ir)
    patient = _patient(normalized_ir)
    return [rule.rule_id for rule in RULES if rule.matches(tags, patient)]


def rule_by_id(rule_id: str) -> RedFlagRule | None:
    for rule in RULES:
        if rule.rule_id == rule_id:
            return rule
    return None
