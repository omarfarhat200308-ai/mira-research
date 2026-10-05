"""
DIAGNOSTIC-SCOPE: backstop guard against diagnostic-claim language.

The Diagnostic agent's output is internal (never patient-facing) and drawn
from a fixed condition taxonomy, but its free-text reasoning could still
phrase things as a definitive diagnosis ("you have pneumonia", "this is
TB"). That language would poison the audit trail's clinical defensibility —
the paper's claim is that MIRA never diagnoses — so it's rejected
structurally here, not just discouraged in the prompt.

Same pattern as drug_dosage_filter.py: conservative regexes, prefer false
positives, raise rather than strip. Callers get one retry (see
mira/agents/base.py) before the fail-safe path takes over.
"""
from __future__ import annotations

import re

from .guards import GuardViolation

_CLAIM_PATTERNS = [
    r"\byou\s+have\b",
    r"\byou'?ve\s+got\b",
    r"\bthe\s+patient\s+has\b",
    r"\bshe\s+has\s+(?:developed\s+)?[a-z_\- ]*(?:eclampsia|meningitis|pneumonia|tuberculosis|stroke|sepsis|hemorrhage)\b",
    r"\bhe\s+has\s+(?:developed\s+)?[a-z_\- ]*(?:eclampsia|meningitis|pneumonia|tuberculosis|stroke|sepsis|hemorrhage)\b",
    r"\bthis\s+is\s+(?:a\s+case\s+of\s+)?[a-z_\- ]*(?:eclampsia|meningitis|pneumonia|tuberculosis|stroke|sepsis|hemorrhage)\b",
    r"\bdiagnos(?:is|ed|e)\b",
    r"\bconfirmed\s+(?:case|to\s+be)\b",
    r"\bdefinitely\s+(?:has|have|is)\b",
    r"\bcertainly\s+(?:has|have|is)\b",
    r"\bsuffering\s+from\b",
]

_COMPILED = re.compile("|".join(_CLAIM_PATTERNS), re.IGNORECASE)

# Phrasings the Diagnostic agent SHOULD use instead; kept here so the
# prompt in mira/agents/diagnostic.py and this filter stay aligned.
ACCEPTABLE_FRAMING_EXAMPLES = [
    "consistent with",
    "raises concern for",
    "pattern fits",
    "warrants evaluation for",
]


class DiagnosticClaimViolation(GuardViolation):
    """Raised when internal reasoning text asserts a diagnosis."""


def check_diagnostic_text(text: str) -> None:
    match = _COMPILED.search(text)
    if match:
        raise DiagnosticClaimViolation(
            f"Diagnostic reasoning contained diagnostic-claim language "
            f"({match.group(0)!r}) and was rejected; concern-area framing "
            f"(e.g. 'consistent with', 'raises concern for') is required."
        )
