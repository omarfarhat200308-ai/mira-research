"""
DIAGNOSTIC-SCOPE: fixed, enumerable differential taxonomy.

The Diagnostic agent (mira/agents/diagnostic.py) may only select conditions
from this closed list — it cannot invent new labels. This is a deliberate
scope/liability boundary: MIRA produces a bounded set of candidates useful
for urgency estimation, not an open-ended diagnosis. Each entry's
`typical_urgency` is a prior, not a rule — the Triage agent still runs the
hardcoded red-flag rules and its own LLM assessment; this field only helps
the Diagnostic agent's LLM call ground its reasoning against a known
clinical prior instead of reasoning about urgency from scratch.

Extending this list is a clinical-content decision (co-advisor review), not
a code change to be made lightly.
"""
from dataclasses import dataclass

from .symptom_tags import SYMPTOM_TAGS  # noqa: F401  (documents the tag vocabulary conditions draw on)


@dataclass(frozen=True)
class Condition:
    name: str
    typical_urgency_prior: str  # "emergency" | "urgent" | "routine" — a prior, not a decision


CONDITIONS: list[Condition] = [
    Condition("acute_coronary_syndrome", "emergency"),
    Condition("pre_eclampsia_eclampsia", "emergency"),
    Condition("postpartum_hemorrhage", "emergency"),
    Condition("pediatric_meningitis", "emergency"),
    Condition("stroke", "emergency"),
    Condition("gastrointestinal_hemorrhage", "emergency"),
    Condition("severe_trauma", "emergency"),
    Condition("sepsis_suspected", "emergency"),
    Condition("pneumonia", "urgent"),
    Condition("suspected_tuberculosis", "urgent"),
    Condition("dehydration_moderate_severe", "urgent"),
    Condition("urinary_tract_infection", "urgent"),
    Condition("cellulitis_skin_infection", "urgent"),
    Condition("gastroenteritis", "urgent"),
    Condition("hypertension_uncontrolled", "urgent"),
    Condition("viral_upper_respiratory_infection", "routine"),
    Condition("minor_musculoskeletal_strain", "routine"),
    Condition("mild_localized_pain", "routine"),
    Condition("uncomplicated_seasonal_allergy", "routine"),
    Condition("unspecified_mild_symptoms", "routine"),
]

CONDITION_NAMES: set[str] = {c.name for c in CONDITIONS}


def is_valid_condition(name: str) -> bool:
    return name in CONDITION_NAMES
