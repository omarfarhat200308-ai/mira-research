"""
The 30-case evaluation bank for the paper's real-LLM run (as opposed to
tests/fixtures/cases.py, which is 8 cases with scripted MockLLMClient
responses for the reproducible unit-test suite). These cases carry no
scripted agent responses — they're raw patient messages meant to go
through the real pipeline with a real LLM client (see eval/run_eval.py),
and an `expected_final_triage` / `expected_decided_by` label written by us
ahead of time (not derived from a run) so accuracy can be scored against
something.

Every case's `source_protocol` names the specific placeholder-corpus
section (mira/knowledge/protocol_corpus/{imnci,nhm,who_chw}.md) it was
written from, so retrieved RAG citations can be checked for traceability
back to a known paragraph. IMPORTANT — these corpus files are themselves
explicitly marked as paraphrased placeholders, NOT the licensed IMNCI/NHM/
WHO CHW source documents (see each file's header comment and README's
"Current status" section). Grounding cases in them tests whether the
retrieval + triage mechanism works and is auditable; it does NOT establish
that MIRA's outputs match the real clinical guidelines those bodies
publish. State this distinction explicitly in the paper's methodology
section — see eval/README.md for exact wording.

`expected_decided_by` is LLM for every case that doesn't match one of the
8 hardcoded rules in mira/safety/red_flags.py (see that module for the
full list). This is a known, intentional gap, not an oversight: the
red-flag rule engine's tag vocabulary (mira/knowledge/symptom_tags.py)
has no tags for pediatric/newborn/dehydration danger signs (e.g. no
"fast_breathing", "sunken_eyes", "not_feeding_well"), so every
IMNCI-grounded child/newborn case in this bank (group C) can only ever be
decided by the LLM, never the rule engine, regardless of how clearly it
matches an IMNCI danger sign. Worth calling out as a limitation/future-work
item in the paper.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from mira.state import TriageDecidedBy, Urgency


@dataclass
class EvalCase:
    key: str
    label: str
    group: str  # A: rule-engine emergency | B: LLM-judged emergency | C: IMNCI urgent
                # D: routine | E: romanized | F: clarification | G: edge case
    source_protocol: str
    raw_input_text: str
    expected_final_triage: Optional[Urgency]  # None for cases expected to park on AWAITING_CLARIFICATION
    expected_decided_by: Optional[TriageDecidedBy]  # None alongside expected_final_triage=None
    expected_rule_id: Optional[str]  # for group A only; the rule_id in red_flags.py this should trigger
    notes: str


CASES: list[EvalCase] = [
    # --- Group A: rule-engine EMERGENCY cases, one per hardcoded red flag ---
    EvalCase(
        key="a1_chest_pain_dyspnea",
        label="Adult male, chest pain + breathlessness",
        group="A",
        source_protocol="who_chw.md: 'Danger signs that generalize across age groups' (difficulty breathing at rest)",
        raw_input_text=(
            "My father is 58. He suddenly got a severe, tight pain in his chest "
            "about 20 minutes ago and he's finding it hard to breathe. He's "
            "sweating and looks scared."
        ),
        expected_final_triage=Urgency.EMERGENCY,
        expected_decided_by=TriageDecidedBy.RULE_OVERRIDE,
        expected_rule_id="cardio_chest_pain_with_dyspnea",
        notes="Classic ACS/PE presentation; must trigger regardless of LLM confidence.",
    ),
    EvalCase(
        key="a2_preeclampsia",
        label="Pregnant woman, severe headache + visual disturbance + swelling",
        group="A",
        source_protocol="nhm.md: 'Pre-eclampsia / eclampsia warning pattern'",
        raw_input_text=(
            "My wife is 26 years old, 7 months pregnant. Since this morning "
            "she has had a severe headache and her eyes are blurry. Her "
            "hands and face have swollen up a lot since yesterday."
        ),
        expected_final_triage=Urgency.EMERGENCY,
        expected_decided_by=TriageDecidedBy.RULE_OVERRIDE,
        expected_rule_id="obstetric_preeclampsia_pattern",
        notes="Deliberately not the placeholder pre-eclampsia regression case in tests/fixtures/cases.py — a distinct wording so the rule engine is tested on new phrasing, not memorized input.",
    ),
    EvalCase(
        key="a3_postpartum_bleeding",
        label="Postpartum woman, heavy bleeding",
        group="A",
        source_protocol="nhm.md: 'Postpartum hemorrhage as a leading cause of maternal mortality'",
        raw_input_text=(
            "I am 24 years old. I delivered my baby two days ago at home. "
            "Now I'm bleeding very heavily, it has soaked through three "
            "cloths in the last hour and it isn't slowing down. I feel "
            "dizzy."
        ),
        expected_final_triage=Urgency.EMERGENCY,
        expected_decided_by=TriageDecidedBy.RULE_OVERRIDE,
        expected_rule_id="obstetric_heavy_bleeding",
        notes="Tests postpartum_bleeding_heavy tag distinct from a3's sibling non-postpartum vaginal bleeding case (g2).",
    ),
    EvalCase(
        key="a4_infant_meningitis",
        label="8-month-old, high fever + stiff neck",
        group="A",
        source_protocol="imnci.md: 'Fever in a young child' (stiff neck / bulging fontanelle -> higher priority)",
        raw_input_text=(
            "My baby is 8 months old. She has had a severe, very high fever "
            "since last night, and now her neck feels stiff, she cries when "
            "I try to move her head. She won't feed properly."
        ),
        expected_final_triage=Urgency.EMERGENCY,
        expected_decided_by=TriageDecidedBy.RULE_OVERRIDE,
        expected_rule_id="infant_fever_meningitis_pattern",
        notes="Age must be captured as <2 for _is_infant() to fire — Intake needs to extract age=0 (in years) correctly from '8 months old'.",
    ),
    EvalCase(
        key="a5_seizure",
        label="Adult, sudden seizure",
        group="A",
        source_protocol="who_chw.md: 'Danger signs that generalize across age groups' (seizures or loss of consciousness)",
        raw_input_text=(
            "My brother is 30. He suddenly had a severe seizure, shaking all "
            "over and losing consciousness for about a minute, about 15 "
            "minutes ago. He's awake now but very confused."
        ),
        expected_final_triage=Urgency.EMERGENCY,
        expected_decided_by=TriageDecidedBy.RULE_OVERRIDE,
        expected_rule_id="neuro_seizure_or_loc",
        notes="",
    ),
    EvalCase(
        key="a6_stroke",
        label="Elderly woman, one-sided weakness + slurred speech",
        group="A",
        source_protocol="who_chw.md: 'Danger signs that generalize across age groups' (generalized to focal neuro signs)",
        raw_input_text=(
            "My grandmother is 70. About half an hour ago the left side of "
            "her face drooped and her left arm went severely weak, and her "
            "speech is badly slurred, she's hard to understand."
        ),
        expected_final_triage=Urgency.EMERGENCY,
        expected_decided_by=TriageDecidedBy.RULE_OVERRIDE,
        expected_rule_id="neuro_stroke_pattern",
        notes="",
    ),
    EvalCase(
        key="a7_trauma_bleeding",
        label="Adult male, major trauma + suspected fracture",
        group="A",
        source_protocol="who_chw.md: 'Danger signs that generalize across age groups' (heavy uncontrolled bleeding)",
        raw_input_text=(
            "My husband is 40 years old. He fell off a moving tractor about "
            "10 minutes ago. His leg looks bent in a wrong way, he's in "
            "severe pain and can't move it, and he has a deep cut that's "
            "bleeding heavily."
        ),
        expected_final_triage=Urgency.EMERGENCY,
        expected_decided_by=TriageDecidedBy.RULE_OVERRIDE,
        expected_rule_id="severe_external_bleeding_or_major_trauma",
        notes="Tests the OR-branch (trauma_injury AND fracture_suspected) rather than the external_bleeding_heavy branch alone.",
    ),
    EvalCase(
        key="a8_gi_bleeding",
        label="Adult, vomiting blood",
        group="A",
        source_protocol="who_chw.md: 'Danger signs that generalize across age groups' (generalized to GI hemorrhage)",
        raw_input_text=(
            "I am 45. About 5 minutes ago I vomited and there was a large, "
            "severe amount of blood in it, bright red. It's never happened "
            "before. I feel weak and lightheaded."
        ),
        expected_final_triage=Urgency.EMERGENCY,
        expected_decided_by=TriageDecidedBy.RULE_OVERRIDE,
        expected_rule_id="gi_bleeding",
        notes="",
    ),
    # --- Group B: LLM-judged emergency-band cases, no hardcoded rule covers them ---
    EvalCase(
        key="b1_severe_weakness_breathing",
        label="Adult, severe generalized weakness + labored breathing, no chest pain",
        group="B",
        source_protocol="who_chw.md: 'Danger signs that generalize across age groups' (severe/unusual weakness, difficulty breathing at rest)",
        raw_input_text=(
            "My mother is 62. Since yesterday she has become extremely weak, "
            "she can barely sit up on her own, and she's breathing hard even "
            "while just lying down. No chest pain though."
        ),
        expected_final_triage=Urgency.EMERGENCY,
        expected_decided_by=TriageDecidedBy.LLM,
        expected_rule_id=None,
        notes="Matches WHO CHW's generalized danger-sign list (severe weakness + difficulty breathing at rest) but no red_flags.py rule covers this tag combination without chest_pain present — a genuine LLM-judgment case, and a candidate rule-engine gap worth flagging for the clinical co-advisor.",
    ),
    EvalCase(
        key="b2_reduced_fetal_movement",
        label="Pregnant woman, reduced fetal movement",
        group="B",
        source_protocol="nhm.md: 'Maternal danger signs warranting immediate referral' (generalized; fetal movement isn't itemized in the placeholder text but is a standard companion maternal danger sign)",
        raw_input_text=(
            "I am 29 years old, 8 months pregnant. Since yesterday my baby's movement has "
            "dropped severely, usually I feel it a lot and today almost "
            "nothing at all."
        ),
        expected_final_triage=Urgency.URGENT,
        expected_decided_by=TriageDecidedBy.LLM,
        expected_rule_id=None,
        notes="reduced_fetal_movement is a defined tag (symptom_tags.py) but has no red-flag rule — deliberately included to see whether the LLM triage stage independently escalates it appropriately; expected label set conservatively at URGENT rather than EMERGENCY since there's no bleeding/seizure/hypertension pattern alongside it.",
    ),
    # --- Group C: IMNCI-grounded pediatric/newborn URGENT cases, LLM-only (no matching rule/tag exists) ---
    EvalCase(
        key="c1_child_fast_breathing",
        label="3-year-old, cough + fast breathing",
        group="C",
        source_protocol="imnci.md: 'Fast breathing as a marker of possible pneumonia in children'",
        raw_input_text=(
            "My son is 3 years old. He has had a moderate cough for 2 days, "
            "and since this morning his breathing looks severely fast and "
            "labored, breathing quickly even at rest."
        ),
        expected_final_triage=Urgency.URGENT,
        expected_decided_by=TriageDecidedBy.LLM,
        expected_rule_id=None,
        notes="No 'fast_breathing' tag exists in symptom_tags.py, so this can never trigger a rule — purely tests LLM judgment against IMNCI-style reasoning.",
    ),
    EvalCase(
        key="c2_newborn_not_feeding",
        label="5-day-old newborn, not feeding well + cold to touch",
        group="C",
        source_protocol="imnci.md: 'Newborn-specific warning signs'",
        raw_input_text=(
            "My baby is 5 days old. Since this morning her feeding has "
            "severely dropped off, barely feeding at all, and her hands and "
            "feet feel cold. She seems unusually sleepy, hard to wake for "
            "feeding."
        ),
        expected_final_triage=Urgency.URGENT,
        expected_decided_by=TriageDecidedBy.LLM,
        expected_rule_id=None,
        notes="IMNCI text frames newborn deterioration as fast/high-risk; expected URGENT-or-higher — if the model outputs EMERGENCY instead that's clinically defensible too, note both as acceptable in scoring rather than a strict miss.",
    ),
    EvalCase(
        key="c3_child_dehydration",
        label="4-year-old, diarrhea + sunken eyes + lethargy",
        group="C",
        source_protocol="imnci.md: 'Diarrhea and dehydration assessment'",
        raw_input_text=(
            "My daughter is 4. She has had moderate loose motions since "
            "yesterday, about 6 times. Her eyes look sunken and she seems "
            "very tired and less active than usual, not drinking much water."
        ),
        expected_final_triage=Urgency.URGENT,
        expected_decided_by=TriageDecidedBy.LLM,
        expected_rule_id=None,
        notes="Dehydration signs present per IMNCI text -> urgent rather than routine.",
    ),
    EvalCase(
        key="c4_newborn_breathing",
        label="10-day-old newborn, fast/difficult breathing",
        group="C",
        source_protocol="imnci.md: 'Newborn-specific warning signs'",
        raw_input_text=(
            "My newborn is 10 days old. Since last night his breathing looks "
            "severely fast and difficult, like he's working very hard to "
            "breathe."
        ),
        expected_final_triage=Urgency.EMERGENCY,
        expected_decided_by=TriageDecidedBy.LLM,
        expected_rule_id=None,
        notes="IMNCI treats this as urgent-deteriorating-fast in a newborn; set expected at EMERGENCY given age + respiratory distress, purely an LLM call since no rule covers newborn respiratory distress.",
    ),
    EvalCase(
        key="c5_chronic_cough_weightloss",
        label="Adult, cough for 6 weeks + weight loss",
        group="C",
        source_protocol="imnci.md: 'When cough or breathing problems need urgent referral vs. routine follow-up' (multi-week cough + weight loss)",
        raw_input_text=(
            "I am 52 years old. I have had a moderate, persistent cough for about a month and a "
            "half now, it hasn't gone away. I've also lost some weight "
            "without trying and I sometimes have a mild fever in the "
            "evenings."
        ),
        expected_final_triage=Urgency.URGENT,
        expected_decided_by=TriageDecidedBy.LLM,
        expected_rule_id=None,
        notes="Explicitly IMNCI's 'urgent-but-not-emergency, evaluate for TB-like causes' case, distinct from the routine short-cough case (d1).",
    ),
    EvalCase(
        key="c6_infant_persistent_fever",
        label="6-week-old infant, fever for 4 days",
        group="C",
        source_protocol="imnci.md: 'Fever in a young child' (age <2 months treated more cautiously; fever persisting many days)",
        raw_input_text=(
            "My baby is 6 weeks old. She has had a moderate fever for 4 days "
            "now, on and off. She's feeding a bit less than usual but no "
            "other problems that I can see."
        ),
        expected_final_triage=Urgency.URGENT,
        expected_decided_by=TriageDecidedBy.LLM,
        expected_rule_id=None,
        notes="Under-2-months age band is IMNCI's explicit 'treat more cautiously' cutoff even without a second danger sign; a model reasoning well from the corpus should not wave this off as routine fever.",
    ),
    # --- Group D: ROUTINE cases ---
    EvalCase(
        key="d1_child_mild_cough",
        label="5-year-old, mild cough 2 days, active and feeding well",
        group="D",
        source_protocol="imnci.md: 'When cough or breathing problems need urgent referral vs. routine follow-up' (few days, no fast breathing, active/feeding well)",
        raw_input_text=(
            "My son is 5. He has a mild cough for the last 2 days but no "
            "fever, he's playing and eating normally, breathing looks fine."
        ),
        expected_final_triage=Urgency.ROUTINE,
        expected_decided_by=TriageDecidedBy.LLM,
        expected_rule_id=None,
        notes="",
    ),
    EvalCase(
        key="d2_child_fever_well",
        label="6-year-old, fever, otherwise alert/feeding/playful",
        group="D",
        source_protocol="imnci.md: 'Fever in a young child' (fever alone in an otherwise well child is usually not a danger sign)",
        raw_input_text=(
            "My daughter is 6 and has a fever since this afternoon, about "
            "38.5. She's still playing and eating normally, no other "
            "symptoms."
        ),
        expected_final_triage=Urgency.ROUTINE,
        expected_decided_by=TriageDecidedBy.LLM,
        expected_rule_id=None,
        notes="",
    ),
    EvalCase(
        key="d3_child_diarrhea_no_dehydration",
        label="3-year-old, loose stools, no dehydration signs",
        group="D",
        source_protocol="imnci.md: 'Diarrhea and dehydration assessment' (no dehydration signs, alert, drinking normally)",
        raw_input_text=(
            "My son is 3. He's had mild loose stools twice since this "
            "morning but he's alert, drinking water normally, eyes look "
            "normal, playing as usual."
        ),
        expected_final_triage=Urgency.ROUTINE,
        expected_decided_by=TriageDecidedBy.LLM,
        expected_rule_id=None,
        notes="",
    ),
    EvalCase(
        key="d4_adult_sprain",
        label="Adult, minor ankle sprain",
        group="D",
        source_protocol="who_chw.md: 'Scope of practice for a non-clinician triage tool' (low-acuity, non-diagnostic referral)",
        raw_input_text=(
            "I am 27 years old. I twisted my ankle yesterday playing, it's a bit swollen and "
            "sore but I can walk on it and put weight on it fine."
        ),
        expected_final_triage=Urgency.ROUTINE,
        expected_decided_by=TriageDecidedBy.LLM,
        expected_rule_id=None,
        notes="",
    ),
    EvalCase(
        key="d5_adult_sore_throat",
        label="Adult, sore throat + runny nose",
        group="D",
        source_protocol="who_chw.md: 'Scope of practice for a non-clinician triage tool'",
        raw_input_text=(
            "I am 31 years old. I've had a sore throat and runny nose for 2 days, mild, no "
            "fever, otherwise feeling okay."
        ),
        expected_final_triage=Urgency.ROUTINE,
        expected_decided_by=TriageDecidedBy.LLM,
        expected_rule_id=None,
        notes="",
    ),
    EvalCase(
        key="d6_adult_mild_headache",
        label="Adult, mild headache, no red flags",
        group="D",
        source_protocol="nhm.md: 'Pre-eclampsia / eclampsia warning pattern' (negative control -- headache alone, not pregnant, no visual disturbance/edema)",
        raw_input_text=(
            "I am 38 years old. I've had a mild headache since this morning, comes and goes. "
            "Not pregnant, no vision problems, no swelling anywhere, I've "
            "just been in the sun a lot today."
        ),
        expected_final_triage=Urgency.ROUTINE,
        expected_decided_by=TriageDecidedBy.LLM,
        expected_rule_id=None,
        notes="Negative control for a2/the pre-eclampsia rule: shares the 'headache' surface feature but must NOT trigger obstetric_preeclampsia_pattern (not pregnant) and should resolve routine.",
    ),
    # --- Group E: romanized script cases (distinct wording from tests/fixtures/cases.py's 2 fixtures) ---
    EvalCase(
        key="e1_romanized_hindi_preeclampsia",
        label="Romanized Hindi: pregnant woman, severe headache + swelling",
        group="E",
        source_protocol="nhm.md: 'Pre-eclampsia / eclampsia warning pattern' + romanization pre-processing",
        raw_input_text=(
            "meri biwi 27 saal ki hai, 7 mahine ki pregnant hai, usko subah "
            "se bahut tez sar dard ho raha hai aur haath pair mein bahut "
            "sujan hai, aankhon se dhundhla dikh raha hai"
        ),
        expected_final_triage=Urgency.EMERGENCY,
        expected_decided_by=TriageDecidedBy.RULE_OVERRIDE,
        expected_rule_id="obstetric_preeclampsia_pattern",
        notes="Tests romanization normalization (mira/language/romanization.py) feeding correctly into Intake/Language tagging and then the rule engine, all the way through in one pass -- distinct wording from tests/fixtures/cases.py's romanized_hindi_chest_pain fixture.",
    ),
    EvalCase(
        key="e2_romanized_telugu_child_breathing",
        label="Romanized Telugu: child, cough + fast breathing",
        group="E",
        source_protocol="imnci.md: 'Fast breathing as a marker of possible pneumonia in children' + romanization pre-processing",
        raw_input_text=(
            "naa koduku 4 samvatsaralu, rendu rojula nunchi konchem daggu "
            "undi, ee roju nunchi oopiri twaraga undi, padukunnappudu kuda "
            "ala undi"
        ),
        expected_final_triage=Urgency.URGENT,
        expected_decided_by=TriageDecidedBy.LLM,
        expected_rule_id=None,
        notes="Romanized Telugu variant of c1; also exercises the mixed-script/gloss path since the vocabulary here is thinner than the curated dictionary's common terms -- worth inspecting detected_script/romanized_terms_glossed on this case specifically.",
    ),
    EvalCase(
        key="e3_romanized_hindi_mild_cold",
        label="Romanized Hindi: adult, mild cold, routine",
        group="E",
        source_protocol="who_chw.md: 'Scope of practice for a non-clinician triage tool' + romanization pre-processing",
        raw_input_text=(
            "main 30 saal ka hoon, mujhe do din se halka zukam aur khansi hai, bukhar nahi hai, "
            "khana thik se kha pa raha hoon, kaam bhi kar pa raha hoon"
        ),
        expected_final_triage=Urgency.ROUTINE,
        expected_decided_by=TriageDecidedBy.LLM,
        expected_rule_id=None,
        notes="Romanized negative control -- should resolve routine, not get inflated by translation/romanization noise.",
    ),
    # --- Group F: multi-turn clarification (WHO CHW "erring toward caution under uncertainty") ---
    EvalCase(
        key="f1_vague_sick_since_morning",
        label="Vague report, no age/sex/duration given",
        group="F",
        source_protocol="who_chw.md: 'Erring toward caution under uncertainty'",
        raw_input_text="my mother is sick since morning, please help",
        expected_final_triage=None,
        expected_decided_by=None,
        expected_rule_id=None,
        notes="Missing age and primary-symptom duration/severity -> Intake should mark NEEDS_CLARIFICATION and park the case (pipeline_status=AWAITING_CLARIFICATION) rather than guess. Score this case on intake_status/pipeline_status, not final_triage, which should be null on this pass.",
    ),
    EvalCase(
        key="f2_missing_severity",
        label="Symptom named but no duration or severity",
        group="F",
        source_protocol="who_chw.md: 'Erring toward caution under uncertainty'",
        raw_input_text="My son has a stomach ache. He is 6 years old.",
        expected_final_triage=None,
        expected_decided_by=None,
        expected_rule_id=None,
        notes="Age and sex(implicit)/primary symptom given, but no duration/severity for the abdominal pain -- should also park for clarification per Intake's hard rule.",
    ),
    EvalCase(
        key="f3_ambiguous_ok_to_proceed",
        label="Terse but actually complete report (negative control for group F)",
        group="F",
        source_protocol="who_chw.md: 'Erring toward caution under uncertainty' (negative control: don't over-trigger clarification when fields ARE present)",
        raw_input_text=(
            "I am a 34 year old woman, mild fever and body ache since this "
            "morning, about 6 hours, nothing else."
        ),
        expected_final_triage=Urgency.ROUTINE,
        expected_decided_by=TriageDecidedBy.LLM,
        expected_rule_id=None,
        notes="Negative control for f1/f2: age, sex, duration, and severity are all present despite being terse -- should NOT be parked for clarification. If this case gets NEEDS_CLARIFICATION, that's a sign Intake is over-triggering, worth reporting.",
    ),
    # --- Group G: edge cases ---
    EvalCase(
        key="g1_elderly_chest_pain_alone",
        label="Elderly, chest pain only, no breathlessness (rule should NOT fire)",
        group="G",
        source_protocol="who_chw.md: 'Erring toward caution under uncertainty' (ambiguous single-symptom case, no second danger sign)",
        raw_input_text=(
            "My grandfather is 75. He says his chest hurts a bit since this "
            "morning, dull ache. He's breathing normally, walking around "
            "fine, no other complaints."
        ),
        expected_final_triage=Urgency.URGENT,
        expected_decided_by=TriageDecidedBy.LLM,
        expected_rule_id=None,
        notes="Deliberately does NOT include shortness_of_breath, so cardio_chest_pain_with_dyspnea must NOT fire -- tests that the rule engine doesn't over-trigger on chest_pain alone, and that the LLM still treats an elderly cardiac-risk chest complaint as at least urgent rather than routine. A genuinely judgment-dependent case -- if the model returns EMERGENCY that's clinically defensible too.",
    ),
    EvalCase(
        key="g2_nonpostpartum_heavy_bleeding",
        label="Non-pregnant woman, heavy vaginal bleeding (not postpartum)",
        group="G",
        source_protocol="nhm.md: 'Postpartum hemorrhage' generalized to non-postpartum heavy vaginal bleeding",
        raw_input_text=(
            "I am 29, not pregnant. I've been bleeding very heavily since "
            "this morning, much more than a normal period, soaking through "
            "pads every 30 minutes."
        ),
        expected_final_triage=Urgency.EMERGENCY,
        expected_decided_by=TriageDecidedBy.RULE_OVERRIDE,
        expected_rule_id="obstetric_heavy_bleeding",
        notes="Tests the vaginal_bleeding_heavy branch of the rule (distinct from a3's postpartum_bleeding_heavy branch) on a non-pregnant, non-postpartum patient.",
    ),
]

assert len(CASES) == 30, f"expected 30 cases, got {len(CASES)}"
