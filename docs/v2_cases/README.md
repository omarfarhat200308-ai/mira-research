# MIRA v2 draft case packets (not frozen)

* `peds_rater_sheet.csv`: 20 pediatric/newborn messages (for a pediatrician).
* `ob_rater_sheet.csv`: 20 obstetric/gynaecologic messages (for an OB-GYN).
* `RATER_INSTRUCTIONS.md`: what raters see.
* `case_metadata_NOT_FOR_RATERS.csv`: language, missing-field flags, design strata. Do NOT send to raters.
* A third packet (about 20 general-medicine cases for Dr. Suneel Kumar) is still to be written.

Status and honesty notes
* Drafted by an AI assistant on 2026-10-08 and NOT yet reviewed by any clinician. A rater may edit or reject any case; edits are logged.
* No reference tier is stored anywhere. Reference labels will be rater consensus only.
* The MIRA system has NOT been run on these cases. They must not be used to tune rules, prompts or keyword lists before the protocol freeze.
* The Hindi/Telugu messages (P10, P11, O15, O16) are unreviewed by native-speaking clinicians.
* The protocol wants at least half of the final cases from sources other than the first author/AI. These packets alone do not meet that; add externally sourced cases before freeze.
