"""
TRIAGE-SCOPE: backstop guard preventing the Referral agent from ever
emitting drug or dosage language.

This is deliberately NOT solely relying on prompting the LLM to "not
recommend medication" — prompts can be ignored or reasoned around under
certain phrasings. This module scans generated referral text and raises if
it matches drug-name or dosage patterns, so the pipeline can fall back to
the hardcoded safe text instead of ever sending the tainted output to a
patient.

This list is intentionally conservative (prefers false positives over false
negatives) given the stakes. Extend the drug name list as needed.
"""
from __future__ import annotations

import re

from .guards import GuardViolation

# Common formulation/dosage language. Deliberately broad.
_DOSAGE_PATTERNS = [
    r"\bmg\b",
    r"\bmilligrams?\b",
    r"\bml\b",
    r"\bmillilit(?:er|re)s?\b",
    r"\btablet(?:s)?\b",
    r"\bcapsule(?:s)?\b",
    r"\bdose(?:s|age)?\b",
    r"\btwice\s+(?:a|per)\s+day\b",
    r"\bthrice\s+(?:a|per)\s+day\b",
    r"\bonce\s+(?:a|per)\s+day\b",
    r"\b\d+\s*(?:x|times)\s*(?:a|per)\s*day\b",
    r"\bsyrup\b",
    r"\binjection\b",
    r"\bIV\s+fluids?\b",
    # Treatment-class recommendations are also out of scope — "take an
    # antibiotic" is a treatment decision that belongs to the facility.
    r"\bantibiotics?\b",
    r"\bpainkillers?\b",
    r"\bpain\s+relievers?\b",
    r"\bointment\b",
    r"\bantacids?\b",
]

# A representative (non-exhaustive) list of common generic/brand drug names
# relevant to primary-care presentations in this context. Extend with
# clinical co-advisor input rather than ad hoc.
_DRUG_NAMES = [
    "paracetamol", "acetaminophen", "ibuprofen", "aspirin", "amoxicillin",
    "azithromycin", "ciprofloxacin", "metronidazole", "ors", "ondansetron",
    "domperidone", "cetirizine", "prednisolone", "insulin", "metformin",
    "amlodipine", "atenolol", "losartan", "diazepam", "artesunate",
    "chloroquine", "doxycycline", "rifampicin", "isoniazid",
]

_COMPILED_DOSAGE = re.compile("|".join(_DOSAGE_PATTERNS), re.IGNORECASE)
_COMPILED_DRUGS = re.compile(
    r"\b(" + "|".join(re.escape(d) for d in _DRUG_NAMES) + r")\b",
    re.IGNORECASE,
)


class DrugDosageViolation(GuardViolation):
    """Raised when referral text contains drug-name, dosage, or
    treatment-recommendation language."""


def check_referral_text(text: str) -> None:
    """
    Raises DrugDosageViolation if `text` matches any drug-name or dosage
    pattern. Callers (mira/agents/referral.py) should catch this and treat
    it as an agent failure, triggering the pipeline's fail-safe fallback —
    never attempt to silently strip and continue, since that risks
    passing through a mangled but still-unsafe message.
    """
    if _COMPILED_DOSAGE.search(text) or _COMPILED_DRUGS.search(text):
        raise DrugDosageViolation(
            "Referral text matched a drug-name or dosage pattern and was "
            "rejected before being sent to the patient."
        )
