"""
TRIAGE-SCOPE: fixed facility taxonomy for the Referral agent.

Referral (mira/agents/referral.py) may only select a facility_type from
this list, keyed by final urgency. This keeps referral output a small,
auditable, closed choice rather than free text — and keeps it clearly a
"where to go" decision, not a diagnostic or treatment one.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Facility:
    facility_type: str
    description: str


FACILITIES_BY_URGENCY: dict[str, Facility] = {
    "emergency": Facility(
        "Emergency / Ambulance / District Hospital Emergency Department",
        "Immediate in-person emergency care — call for ambulance transport "
        "if available, otherwise go now, do not wait.",
    ),
    "urgent": Facility(
        "Community Health Centre (CHC) or nearest Primary Health Centre (PHC) with a doctor",
        "Should be seen by a health worker within the next few hours to "
        "a day — do not wait for symptoms to worsen.",
    ),
    "routine": Facility(
        "Primary Health Centre (PHC) / Sub-centre / ASHA worker follow-up",
        "Can be seen at the next routine opportunity; seek care sooner if "
        "symptoms worsen.",
    ),
}


def facility_for_urgency(urgency: str) -> Facility:
    return FACILITIES_BY_URGENCY[urgency]
