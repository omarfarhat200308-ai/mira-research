"""
Canonical symptom tag vocabulary.

The Language agent's job is to map whatever the patient said (in any
supported language, in free text) onto this fixed set of tags. The
Diagnostic agent and the red-flag rule engine (mira/safety/red_flags.py)
both consume only these tags — never raw text — so that rule matching is
deterministic and auditable rather than a fragile keyword search over
translated free text.

This list is deliberately a flat, closed vocabulary. Adding a tag is a
clinical decision (co-advisor review), not something an agent can do by
inventing a new label.
"""

SYMPTOM_TAGS: set[str] = {
    # cardio/respiratory
    "chest_pain",
    "shortness_of_breath",
    "palpitations",
    "cough",
    "cough_with_blood",
    # neuro
    "severe_headache",
    "visual_disturbance",
    "seizure",
    "loss_of_consciousness",
    "confusion",
    "stiff_neck",
    "bulging_fontanelle",
    "one_sided_weakness",
    "slurred_speech",
    # gi
    "abdominal_pain",
    "epigastric_pain",
    "vomiting",
    "vomiting_blood",
    "diarrhea",
    "black_or_bloody_stool",
    # obstetric
    "pregnant",
    "vaginal_bleeding_heavy",
    "postpartum_bleeding_heavy",
    "reduced_fetal_movement",
    "labor_pain",
    # general / infectious
    "fever",
    "high_fever",
    "chills",
    "rash",
    "swelling_edema",
    "hypertension_known_or_suspected",
    "weight_loss",
    "fatigue",
    "dehydration_signs",
    # trauma / bleeding / injury
    "external_bleeding_heavy",
    "trauma_injury",
    "burn",
    "fracture_suspected",
    "sprain_strain",
    # msk / minor
    "joint_pain",
    "sore_throat",
    "runny_nose",
    "mild_pain",
}


def is_valid_tag(tag: str) -> bool:
    return tag in SYMPTOM_TAGS
