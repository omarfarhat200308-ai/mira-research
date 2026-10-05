"""
Deterministic assembly of the final patient/ASHA-worker-facing message.

Content (next steps, warning signs, doctor handoff script) is LLM-generated
per case by Referral + Language(translate) — see their docstrings. The
STRUCTURE (branding, decision header/emoji, section order, footer) is
fixed here in plain Python so every message looks consistent regardless of
what the LLM produced, matching the agreed format (originally prototyped
under MIRA's earlier name, "TABIB").

Deliberately NOT used for the fail-safe degradation path
(pipeline.py::_apply_failsafe_degradation) or the translation-failure
fallback — those stay maximally simple, hardcoded, LLM-independent text,
on purpose, since they're the last line of defense when something else
has already gone wrong.
"""
from __future__ import annotations

from .state import PatientCase, Urgency

_DECISION_LABELS: dict[Urgency, tuple[str, str]] = {
    Urgency.EMERGENCY: ("REFER NOW", "⚠️ EMERGENCY"),
    Urgency.URGENT: ("REFER SOON", "🟡 URGENT"),
    Urgency.ROUTINE: ("MANAGE LOCALLY", "🟢 ROUTINE"),
}

# DRAFT — NEEDS LEGAL REVIEW before any real patient data flows through
# this system. Written 2026-09-19 as a reasonable starting point for DPDP
# Act 2023 notice-at-collection language, not reviewed by counsel. Replace
# "[grievance officer contact — fill in before pilot use]" with a real
# contact before this is anything but a placeholder. None (rather than
# this constant) means no notice is prepended; nothing else about message
# formatting depends on this being set, so leaving it None is always safe.
DPDP_COMPLIANCE_NOTICE: str | None = (
    "🔒 Privacy notice: MIRA collects the symptoms and details you share "
    "here to provide this triage assessment and, if urgent, to coordinate "
    "your care with a doctor. It is not used for any other purpose and is "
    "not sold or shared beyond care coordination. You may ask to see, "
    "correct, or delete your data at any time by contacting "
    "[grievance officer contact — fill in before pilot use]."
)


def format_patient_message(case: PatientCase) -> str:
    """Assembles case.next_steps_bullets / warning_signs /
    doctor_handoff_script (whatever language they're currently in — English
    if called right after Referral, translated if called after
    Language(translate)) into the final structured message."""
    decision, tag = _DECISION_LABELS.get(case.final_triage, ("ASSESSMENT", ""))
    header = f"Decision: {decision} {tag}".strip()

    lines = ["🏥 MIRA Assessment", "", header, ""]

    if case.next_steps_bullets:
        lines.append("Next steps:")
        lines.extend(f"• {step}" for step in case.next_steps_bullets)
        lines.append("")

    if case.warning_signs:
        lines.append("⚠️ Watch for these warning signs:")
        lines.extend(f"• {sign}" for sign in case.warning_signs)
        lines.append("")

    if case.doctor_handoff_script:
        lines.append("Tell the doctor:")
        lines.append(f'"{case.doctor_handoff_script}"')
        lines.append("")

    lines.append("---")
    lines.append("MIRA | AI Triage Support | Not a substitute for medical advice")

    message = "\n".join(lines).rstrip()
    if DPDP_COMPLIANCE_NOTICE:
        message = DPDP_COMPLIANCE_NOTICE.strip() + "\n\n" + message
    return message
