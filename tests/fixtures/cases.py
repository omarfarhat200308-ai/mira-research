"""
The regression fixture for the test harness: the pre-eclampsia case
(RECOVERED 2026-09-12 — this is now the real hackathon transcript, found
in github.com/omarfarhat200308-ai/tabib-v1 (TABIB, the Band of Agents
Hackathon 2026 project this codebase originated from), src/test_tabib.py
— see NOTE below for what changed from the reconstructed placeholder it
replaces), 5 synthetic cases spanning emergency/urgent/routine, and 2
romanized-Hindi/Telugu cases that
exercise the romanization-normalization pre-processing step
(mira/language/romanization.py) end to end through the full pipeline —
part of replaying the pilot's expected input distribution (mixed-script,
not just English) before this touches a real patient interaction.

Each Case bundles the raw patient message with scripted, deterministic
mock responses for every agent the pipeline will call — this is what makes
test_pipeline_cases.py reproducible without an API key or network access.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mira.llm_client import MockLLMClient
from mira.state import TriageDecidedBy, Urgency


@dataclass
class Case:
    key: str
    label: str
    raw_input_text: str
    expected_final_triage: Urgency
    expected_decided_by: TriageDecidedBy
    agent_responses: dict[str, dict[str, Any]] = field(default_factory=dict)

    def build_client(self) -> MockLLMClient:
        client = MockLLMClient()
        for agent_name, response in self.agent_responses.items():
            client.register(agent_name, response)
        return client


CASES: list[Case] = [
    # NOTE (2026-09-12): this is the REAL hackathon transcript, recovered
    # from github.com/omarfarhat200308-ai/tabib-v1/blob/main/src/test_tabib.py
    # (the TABIB Band of Agents Hackathon 2026 project MIRA was rebuilt
    # from) -- replacing a reconstructed placeholder that had been in this
    # slot since the rebuild, on the record as clinically plausible but NOT
    # the patient's actual words. Two real, clinically meaningful
    # differences from that placeholder: this transcript has a HIGH FEVER
    # (not in the placeholder) and explicit "no fetal movement since
    # morning" (not in the placeholder at all -- a distinct maternal danger
    # sign, not part of the classic pre-eclampsia triad). It does NOT
    # mention blurred vision or epigastric pain, which the placeholder had
    # invented. The original TABIB prompt's own red-flag list treated
    # "pregnancy with bleeding, severe headache, fits, OR no fetal
    # movement" as red-flag-worthy on ANY ONE of those alone (see
    # shared_prompts/prompts.py in that repo) -- broader than MIRA's
    # current rule 2 (obstetric_preeclampsia_pattern), which requires
    # severe headache/visual disturbance/epigastric pain AND hypertension/
    # edema together. This real transcript still triggers MIRA's rule 2
    # (severe headache + swelling_edema satisfies both required clauses),
    # but "no fetal movement" alone reaching this case is itself a live
    # instance of the reduced_fetal_movement-has-no-rule gap already
    # tracked as eval case b2_reduced_fetal_movement (eval/cases_30.py) --
    # this real transcript is evidence that gap isn't hypothetical.
    Case(
        key="pre_eclampsia_regression",
        label="Pre-eclampsia (regression, real hackathon transcript)",
        raw_input_text=(
            "35 year old pregnant woman, 8 months pregnant. "
            "High fever since 2 days, severe headache, "
            "swelling on face and hands. "
            "No fetal movement since morning."
        ),
        expected_final_triage=Urgency.EMERGENCY,
        expected_decided_by=TriageDecidedBy.RULE_OVERRIDE,
        agent_responses={
            "intake": {
                "age": 35,
                "sex": "female",
                "is_pregnant": True,
                "symptoms": [
                    {"name": "high fever", "onset": "2 days ago", "duration": "2 days", "severity": "severe"},
                    {"name": "severe headache", "onset": "2 days ago", "duration": "2 days", "severity": "severe"},
                    {"name": "swelling on face and hands", "duration": "2 days", "severity": "moderate"},
                    {"name": "no fetal movement", "onset": "this morning", "duration": "since morning", "severity": "severe"},
                ],
                "confidence": 0.9,
                "reasoning": "Clear report of age, sex, pregnancy status, and four distinct symptoms with duration/severity.",
            },
            "language_normalize": {
                "detected_language": "en",
                "symptom_tags": ["pregnant", "high_fever", "severe_headache", "swelling_edema", "reduced_fetal_movement"],
                "confidence": 0.9,
                "reasoning": "Symptoms map onto pre-eclampsia/maternal-danger-sign warning tags.",
            },
            "diagnostic": {
                "differential": [
                    {"condition": "pre_eclampsia_eclampsia", "reasoning": "Pregnancy with severe headache and edema is consistent with pre-eclampsia; fever and absent fetal movement raise additional concern for superimposed infection or fetal compromise.", "confidence": 0.8},
                ],
                "confidence": 0.8,
                "reasoning": "Presentation is consistent with pre-eclampsia but the fever and absent fetal movement mean this isn't a textbook-clean case -- multiple serious differentials apply.",
            },
            "triage": {
                "urgency": "emergency",
                "reasoning": "Pre-eclampsia warning signs plus reduced fetal movement in a pregnant patient require immediate evaluation regardless of exact differential.",
                "confidence": 0.85,
            },
            "referral": {
                "next_steps": ["Go to the nearest hospital emergency department right now.", "Do not travel alone if possible.", "Bring any antenatal/pregnancy cards or reports."],
                "warning_signs": ["Convulsions/fits", "Loss of consciousness", "Severe abdominal pain", "Baby not moving"],
                "doctor_handoff_script": "8 months pregnant with high fever, severe headache, facial/hand swelling, and no fetal movement since morning -- possible severe pre-eclampsia and/or fetal compromise, needs urgent evaluation.",
                "reasoning": "Emergency urgency requires immediate facility-level care.",
                "confidence": 0.9,
            },
            "language_translate": {
                "translated_next_steps": ["Go to the nearest hospital emergency department right now.", "Do not travel alone if possible.", "Bring any antenatal/pregnancy cards or reports."],
                "translated_warning_signs": ["Convulsions/fits", "Loss of consciousness", "Severe abdominal pain", "Baby not moving"],
                "translated_doctor_handoff_script": "8 months pregnant with high fever, severe headache, facial/hand swelling, and no fetal movement since morning -- possible severe pre-eclampsia and/or fetal compromise, needs urgent evaluation.",
                "confidence": 0.9,
                "reasoning": "Source language is already English; no translation needed.",
            },
        },
    ),
    Case(
        key="chest_pain_sob",
        label="Chest pain + shortness of breath, adult male",
        raw_input_text=(
            "My father is 55 years old, male. He suddenly has chest pain "
            "and is having trouble breathing since about 30 minutes ago."
        ),
        expected_final_triage=Urgency.EMERGENCY,
        expected_decided_by=TriageDecidedBy.RULE_OVERRIDE,
        agent_responses={
            "intake": {
                "age": 55,
                "sex": "male",
                "is_pregnant": None,
                "symptoms": [
                    {"name": "chest pain", "onset": "30 minutes ago", "duration": "ongoing", "severity": "severe"},
                    {"name": "shortness of breath", "onset": "30 minutes ago", "duration": "ongoing", "severity": "severe"},
                ],
                "confidence": 0.92,
                "reasoning": "Age, sex, and two clear acute symptoms with onset/duration/severity given.",
            },
            "language_normalize": {
                "detected_language": "en",
                "symptom_tags": ["chest_pain", "shortness_of_breath"],
                "confidence": 0.92,
                "reasoning": "Direct symptom mentions.",
            },
            "diagnostic": {
                "differential": [
                    {"condition": "acute_coronary_syndrome", "reasoning": "Chest pain with dyspnea in an older adult male.", "confidence": 0.8},
                ],
                "confidence": 0.8,
                "reasoning": "Classic ACS presentation.",
            },
            "triage": {
                "urgency": "emergency",
                "reasoning": "Chest pain with shortness of breath is a time-critical cardiac/pulmonary emergency pattern.",
                "confidence": 0.88,
            },
            "referral": {
                "next_steps": ["Call for emergency transport or go to the nearest hospital emergency department immediately.", "This cannot wait."],
                "warning_signs": ["Loss of consciousness", "Worsening breathing difficulty"],
                "doctor_handoff_script": "55-year-old male with sudden chest pain and breathlessness for 30 minutes — possible cardiac emergency, needs immediate evaluation.",
                "reasoning": "Emergency-level cardiopulmonary presentation.",
                "confidence": 0.9,
            },
            "language_translate": {
                "translated_next_steps": ["Call for emergency transport or go to the nearest hospital emergency department immediately.", "This cannot wait."],
                "translated_warning_signs": ["Loss of consciousness", "Worsening breathing difficulty"],
                "translated_doctor_handoff_script": "55-year-old male with sudden chest pain and breathlessness for 30 minutes — possible cardiac emergency, needs immediate evaluation.",
                "confidence": 0.9,
                "reasoning": "Already English.",
            },
        },
    ),
    Case(
        key="infant_fever_stiff_neck",
        label="Infant with fever and stiff neck",
        raw_input_text=(
            "My baby is 8 months old. She has had a high fever since this "
            "morning, and her neck feels stiff. She is very fussy and won't "
            "settle."
        ),
        expected_final_triage=Urgency.EMERGENCY,
        expected_decided_by=TriageDecidedBy.RULE_OVERRIDE,
        agent_responses={
            "intake": {
                "age": 0,
                "sex": "female",
                "is_pregnant": None,
                "symptoms": [
                    {"name": "high fever", "onset": "this morning", "duration": "several hours", "severity": "severe"},
                    {"name": "stiff neck", "onset": "this morning", "duration": "several hours", "severity": "moderate"},
                ],
                "confidence": 0.85,
                "reasoning": "Infant age given in months, converted to 0 years; two acute symptoms with duration/severity.",
            },
            "language_normalize": {
                "detected_language": "en",
                "symptom_tags": ["fever", "high_fever", "stiff_neck"],
                "confidence": 0.85,
                "reasoning": "Direct mapping of fever and neck stiffness.",
            },
            "diagnostic": {
                "differential": [
                    {"condition": "pediatric_meningitis", "reasoning": "Infant with high fever and stiff neck is a classic meningitis warning pattern.", "confidence": 0.75},
                ],
                "confidence": 0.75,
                "reasoning": "Fits pediatric meningitis pattern.",
            },
            "triage": {
                "urgency": "emergency",
                "reasoning": "Infant fever with stiff neck requires immediate evaluation for meningitis.",
                "confidence": 0.8,
            },
            "referral": {
                "next_steps": ["Take the baby to the nearest hospital emergency department right now.", "Do not wait for the fever to break."],
                "warning_signs": ["Baby becomes unresponsive or very difficult to wake", "Bulging soft spot on the head"],
                "doctor_handoff_script": "8-month-old with high fever and stiff neck since this morning — possible meningitis warning pattern, needs urgent assessment.",
                "reasoning": "Emergency pediatric presentation.",
                "confidence": 0.85,
            },
            "language_translate": {
                "translated_next_steps": ["Take the baby to the nearest hospital emergency department right now.", "Do not wait for the fever to break."],
                "translated_warning_signs": ["Baby becomes unresponsive or very difficult to wake", "Bulging soft spot on the head"],
                "translated_doctor_handoff_script": "8-month-old with high fever and stiff neck since this morning — possible meningitis warning pattern, needs urgent assessment.",
                "confidence": 0.85,
                "reasoning": "Already English.",
            },
        },
    ),
    Case(
        key="postpartum_hemorrhage",
        label="Postpartum heavy bleeding",
        raw_input_text=(
            "I am 30 years old, I gave birth 2 days ago and now I am "
            "bleeding very heavily, soaking pads within minutes."
        ),
        expected_final_triage=Urgency.EMERGENCY,
        expected_decided_by=TriageDecidedBy.RULE_OVERRIDE,
        agent_responses={
            "intake": {
                "age": 30,
                "sex": "female",
                "is_pregnant": False,
                "symptoms": [
                    {"name": "heavy postpartum bleeding", "onset": "today", "duration": "ongoing", "severity": "severe"},
                ],
                "confidence": 0.9,
                "reasoning": "Clear acute severe symptom with duration and severity given.",
            },
            "language_normalize": {
                "detected_language": "en",
                "symptom_tags": ["postpartum_bleeding_heavy"],
                "confidence": 0.9,
                "reasoning": "Direct mapping of heavy postpartum bleeding.",
            },
            "diagnostic": {
                "differential": [
                    {"condition": "postpartum_hemorrhage", "reasoning": "Heavy bleeding 2 days postpartum.", "confidence": 0.85},
                ],
                "confidence": 0.85,
                "reasoning": "Fits postpartum hemorrhage.",
            },
            "triage": {
                "urgency": "emergency",
                "reasoning": "Postpartum hemorrhage is a leading cause of maternal mortality and requires immediate care.",
                "confidence": 0.9,
            },
            "referral": {
                "next_steps": ["Go to the nearest hospital emergency department immediately.", "This is time-critical."],
                "warning_signs": ["Dizziness or fainting", "Soaking more than one pad within minutes"],
                "doctor_handoff_script": "30-year-old, 2 days postpartum, heavy bleeding soaking pads within minutes — possible postpartum hemorrhage, needs urgent evaluation.",
                "reasoning": "Emergency obstetric bleeding.",
                "confidence": 0.9,
            },
            "language_translate": {
                "translated_next_steps": ["Go to the nearest hospital emergency department immediately.", "This is time-critical."],
                "translated_warning_signs": ["Dizziness or fainting", "Soaking more than one pad within minutes"],
                "translated_doctor_handoff_script": "30-year-old, 2 days postpartum, heavy bleeding soaking pads within minutes — possible postpartum hemorrhage, needs urgent evaluation.",
                "confidence": 0.9,
                "reasoning": "Already English.",
            },
        },
    ),
    Case(
        key="persistent_cough_weight_loss",
        label="Persistent cough 3 weeks + weight loss, adult",
        raw_input_text=(
            "I am 40 years old, male. I've had a cough for about 3 weeks "
            "that won't go away, and I've lost some weight without trying."
        ),
        expected_final_triage=Urgency.URGENT,
        expected_decided_by=TriageDecidedBy.LLM,
        agent_responses={
            "intake": {
                "age": 40,
                "sex": "male",
                "is_pregnant": None,
                "symptoms": [
                    {"name": "persistent cough", "onset": "3 weeks ago", "duration": "3 weeks", "severity": "moderate"},
                    {"name": "unintentional weight loss", "duration": "several weeks", "severity": "moderate"},
                ],
                "confidence": 0.85,
                "reasoning": "Both symptoms have clear duration/severity.",
            },
            "language_normalize": {
                "detected_language": "en",
                "symptom_tags": ["cough", "weight_loss"],
                "confidence": 0.85,
                "reasoning": "Direct mapping.",
            },
            "diagnostic": {
                "differential": [
                    {"condition": "suspected_tuberculosis", "reasoning": "Prolonged cough with weight loss warrants TB workup.", "confidence": 0.6},
                ],
                "confidence": 0.6,
                "reasoning": "Chronic cough plus weight loss pattern.",
            },
            "triage": {
                "urgency": "urgent",
                "reasoning": "Prolonged cough with weight loss should be seen within the day but is not immediately life-threatening.",
                "confidence": 0.75,
            },
            "referral": {
                "next_steps": ["Visit a health centre with a doctor within the next day.", "Mention the cough duration and weight loss."],
                "warning_signs": ["Coughing up blood", "High fever develops"],
                "doctor_handoff_script": "40-year-old male with cough for 3 weeks and unintentional weight loss — possible TB workup needed, not immediately life-threatening.",
                "reasoning": "Urgent but not emergency presentation.",
                "confidence": 0.8,
            },
            "language_translate": {
                "translated_next_steps": ["Visit a health centre with a doctor within the next day.", "Mention the cough duration and weight loss."],
                "translated_warning_signs": ["Coughing up blood", "High fever develops"],
                "translated_doctor_handoff_script": "40-year-old male with cough for 3 weeks and unintentional weight loss — possible TB workup needed, not immediately life-threatening.",
                "confidence": 0.8,
                "reasoning": "Already English.",
            },
        },
    ),
    Case(
        key="mild_cold",
        label="Mild cold/cough, 2 days, low severity, healthy adult",
        raw_input_text=(
            "I am 25 years old, woman. I have a mild runny nose and a "
            "slight cough for the past 2 days, nothing severe."
        ),
        expected_final_triage=Urgency.ROUTINE,
        expected_decided_by=TriageDecidedBy.LLM,
        agent_responses={
            "intake": {
                "age": 25,
                "sex": "female",
                "is_pregnant": None,
                "symptoms": [
                    {"name": "runny nose", "onset": "2 days ago", "duration": "2 days", "severity": "mild"},
                    {"name": "slight cough", "onset": "2 days ago", "duration": "2 days", "severity": "mild"},
                ],
                "confidence": 0.9,
                "reasoning": "Clear mild symptoms with duration/severity.",
            },
            "language_normalize": {
                "detected_language": "en",
                "symptom_tags": ["runny_nose", "cough"],
                "confidence": 0.9,
                "reasoning": "Direct mapping.",
            },
            "diagnostic": {
                "differential": [
                    {"condition": "viral_upper_respiratory_infection", "reasoning": "Mild runny nose and cough for 2 days.", "confidence": 0.8},
                ],
                "confidence": 0.8,
                "reasoning": "Classic mild URI pattern.",
            },
            "triage": {
                "urgency": "routine",
                "reasoning": "Mild, short-duration URI symptoms with no red-flag features.",
                "confidence": 0.85,
            },
            "referral": {
                "next_steps": ["Rest at home and monitor symptoms."],
                "warning_signs": ["Fever develops", "Worsening cough or difficulty breathing"],
                "doctor_handoff_script": "",
                "reasoning": "Routine self-limited presentation.",
                "confidence": 0.85,
            },
            "language_translate": {
                "translated_next_steps": ["Rest at home and monitor symptoms."],
                "translated_warning_signs": ["Fever develops", "Worsening cough or difficulty breathing"],
                "translated_doctor_handoff_script": "",
                "confidence": 0.85,
                "reasoning": "Already English.",
            },
        },
    ),
    Case(
        key="romanized_hindi_chest_pain",
        label="Romanized Hindi: chest pain + breathlessness, adult male",
        raw_input_text=(
            "mera pita 55 saal ke hain, unko seene mein dard ho raha hai aur "
            "saans lene mein takleef ho rahi hai, karib 30 minute se"
        ),
        expected_final_triage=Urgency.EMERGENCY,
        expected_decided_by=TriageDecidedBy.RULE_OVERRIDE,
        agent_responses={
            "intake": {
                "age": 55,
                "sex": "male",
                "is_pregnant": None,
                "symptoms": [
                    {"name": "chest pain", "onset": "30 minutes ago", "duration": "ongoing", "severity": "severe"},
                    {"name": "shortness of breath", "onset": "30 minutes ago", "duration": "ongoing", "severity": "severe"},
                ],
                "confidence": 0.88,
                "reasoning": "Romanized Hindi input glossed by the pre-processing step (chest pain / shortness of breath); age and sex explicitly stated.",
            },
            "language_normalize": {
                "detected_language": "hi",
                "symptom_tags": ["chest_pain", "shortness_of_breath"],
                "confidence": 0.85,
                "reasoning": "Glossed terms map directly onto the canonical tags.",
            },
            "diagnostic": {
                "differential": [
                    {"condition": "acute_coronary_syndrome", "reasoning": "Chest pain with dyspnea in an older adult male.", "confidence": 0.8},
                ],
                "confidence": 0.8,
                "reasoning": "Classic ACS presentation.",
            },
            "triage": {
                "urgency": "emergency",
                "reasoning": "Chest pain with shortness of breath is a time-critical cardiac/pulmonary emergency pattern.",
                "confidence": 0.88,
            },
            "referral": {
                "next_steps": ["Call for emergency transport or go to the nearest hospital emergency department immediately.", "This cannot wait."],
                "warning_signs": ["Loss of consciousness", "Worsening breathing difficulty"],
                "doctor_handoff_script": "55-year-old male with sudden chest pain and breathlessness for 30 minutes — possible cardiac emergency, needs immediate evaluation.",
                "reasoning": "Emergency-level cardiopulmonary presentation.",
                "confidence": 0.9,
            },
            "language_translate": {
                "translated_next_steps": ["Aapke pitaji ko turant hospital emergency le jaayein.", "Yeh intezaar nahi kar sakta."],
                "translated_warning_signs": ["Behoshi", "Saans lene mein taklif badhna"],
                "translated_doctor_handoff_script": "55 saal ke purush, seene mein achanak dard aur 30 minute se saans lene mein takleef — possible cardiac emergency, turant evaluation chahiye.",
                "confidence": 0.85,
                "reasoning": "Translated to romanized Hindi per detected_language and ROMANIZE_LANGUAGES.",
            },
        },
    ),
    Case(
        key="romanized_telugu_mild_cough",
        label="Romanized Telugu: mild cough, 2 days, healthy adult",
        raw_input_text=(
            "naaku rendu rojula nunchi konchem daggu undi, jwaram ledu, "
            "baga tinagalanu, pani cheyagalanu"
        ),
        expected_final_triage=Urgency.ROUTINE,
        expected_decided_by=TriageDecidedBy.LLM,
        agent_responses={
            "intake": {
                "age": 25,
                "sex": "female",
                "is_pregnant": None,
                "symptoms": [
                    {"name": "mild cough", "onset": "2 days ago", "duration": "2 days", "severity": "mild"},
                ],
                "confidence": 0.8,
                "reasoning": "Romanized Telugu input glossed by the pre-processing step (cough); no fever, patient reports eating/working normally.",
            },
            "language_normalize": {
                "detected_language": "te",
                "symptom_tags": ["cough"],
                "confidence": 0.8,
                "reasoning": "Glossed cough term maps directly onto the canonical tag; no other symptoms reported.",
            },
            "diagnostic": {
                "differential": [
                    {"condition": "viral_upper_respiratory_infection", "reasoning": "Mild isolated cough for 2 days, no other symptoms.", "confidence": 0.75},
                ],
                "confidence": 0.75,
                "reasoning": "Classic mild URI pattern.",
            },
            "triage": {
                "urgency": "routine",
                "reasoning": "Mild, short-duration, isolated cough with no red-flag features.",
                "confidence": 0.85,
            },
            "referral": {
                "next_steps": ["Rest at home and monitor."],
                "warning_signs": ["Fever develops", "Worsening cough or breathing difficulty"],
                "doctor_handoff_script": "",
                "reasoning": "Routine self-limited presentation.",
                "confidence": 0.85,
            },
            "language_translate": {
                "translated_next_steps": ["Intlo visranti teesukoni jagratha ga undandi."],
                "translated_warning_signs": ["Jwaram vaste", "Daggu ekkuva gaani breathing problem gaani vaste"],
                "translated_doctor_handoff_script": "",
                "confidence": 0.8,
                "reasoning": "Translated to romanized Telugu per detected_language and ROMANIZE_LANGUAGES.",
            },
        },
    ),
]

CASES_BY_KEY: dict[str, Case] = {c.key: c for c in CASES}
