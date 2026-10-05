"""
Multi-turn clarification flow: Intake halts on missing critical fields, the
case is resumed with the patient's answer on the SAME case_id, and the
round cap prevents an endless question loop by degrading to the fail-safe
referral instead.
"""
from __future__ import annotations

import copy

from mira import config
from mira.llm_client import MockLLMClient
from mira.pipeline import run_pipeline
from mira.state import IntakeStatus, PipelineStatus, Urgency

from .fixtures.cases import CASES_BY_KEY

FULL_CASE = CASES_BY_KEY["chest_pain_sob"]

INCOMPLETE_INTAKE = {
    # Patient message gave symptoms but no age/sex.
    "age": None,
    "sex": None,
    "is_pregnant": None,
    "symptoms": [
        {"name": "chest pain", "onset": "30 minutes ago", "duration": "ongoing", "severity": "severe"},
        {"name": "shortness of breath", "onset": "30 minutes ago", "duration": "ongoing", "severity": "severe"},
    ],
    "clarifying_question": "How old is the patient, and are they male or female?",
    "confidence": 0.8,
    "reasoning": "Symptoms are clear but age and sex were not stated.",
}


def _client_with_intake_sequence(*intake_responses) -> MockLLMClient:
    client = FULL_CASE.build_client()
    client.register("intake", list(copy.deepcopy(intake_responses)))
    return client


def test_intake_halts_and_asks_without_proceeding():
    client = _client_with_intake_sequence(INCOMPLETE_INTAKE)
    result = run_pipeline("chest pain, cannot breathe", llm_client=client)

    assert result.pipeline_status == PipelineStatus.AWAITING_CLARIFICATION
    assert result.intake_status == IntakeStatus.NEEDS_CLARIFICATION
    assert result.pending_clarifying_question == INCOMPLETE_INTAKE["clarifying_question"]
    assert "age" in result.missing_critical_fields
    assert "sex" in result.missing_critical_fields
    # Nothing downstream ran.
    assert result.final_triage is None
    assert result.differential == []
    assert len(result.clarification_history) == 1


def test_resume_with_answer_completes_pipeline_on_same_case():
    complete_intake = FULL_CASE.agent_responses["intake"]
    client = _client_with_intake_sequence(INCOMPLETE_INTAKE, complete_intake)

    first = run_pipeline("chest pain, cannot breathe", llm_client=client)
    assert first.pipeline_status == PipelineStatus.AWAITING_CLARIFICATION

    second = run_pipeline("He is 55 years old, male", llm_client=client, resume_case=first)

    # Same case, contiguous audit trail: the question and its answer are
    # both recorded on the case that ultimately got triaged.
    assert second.case_id == first.case_id
    assert second.clarification_history[0].question == INCOMPLETE_INTAKE["clarifying_question"]
    assert second.clarification_history[0].answer == "He is 55 years old, male"

    assert second.pipeline_status == PipelineStatus.OK
    assert second.final_triage == Urgency.EMERGENCY  # red flag still fires as usual


def test_clarifying_question_is_asked_in_patients_detected_language():
    """Regression test: a clarifying question generated in English for a
    non-English-writing patient/ASHA worker is unusable, not just a
    theoretical gap (hit live in testing). Intake must both detect the
    language AND phrase clarifying_question in it, and that language must
    land on the case before LanguageNormalizeAgent would otherwise set it."""
    hindi_incomplete_intake = {
        "age": None,
        "sex": None,
        "is_pregnant": None,
        "symptoms": [
            {"name": "bukhar", "onset": "kal se", "duration": "1 din", "severity": "tez"},
        ],
        "clarifying_question": "मरीज़ की उम्र और लिंग क्या है?",
        "detected_language": "hi",
        "confidence": 0.8,
        "reasoning": "Symptom reported in Hindi; age and sex not stated.",
    }
    client = _client_with_intake_sequence(hindi_incomplete_intake)
    result = run_pipeline("mere bacche ko kal se tez bukhar hai", llm_client=client)

    assert result.pipeline_status == PipelineStatus.AWAITING_CLARIFICATION
    assert result.detected_language == "hi"
    assert result.pending_clarifying_question == "मरीज़ की उम्र और लिंग क्या है?"
    # Never silently falls back to an English-only question when the LLM
    # did its job and provided one in the right language.
    assert "age" not in result.pending_clarifying_question.lower()


def test_unrecognized_detected_language_is_not_stored():
    # Defensive: an out-of-vocabulary language code from the LLM must not
    # land on the case unvalidated (mirrors LanguageNormalizeAgent's own
    # validation of detected_language elsewhere in the pipeline).
    bad_language_intake = {**INCOMPLETE_INTAKE, "detected_language": "xx-not-a-real-code"}
    client = _client_with_intake_sequence(bad_language_intake)
    result = run_pipeline("chest pain, cannot breathe", llm_client=client)
    assert result.detected_language is None


def test_round_cap_degrades_to_failsafe_instead_of_looping():
    # Intake never gets what it needs, no matter how many times it asks.
    rounds_needed = config.MAX_CLARIFICATION_ROUNDS + 1
    client = _client_with_intake_sequence(*[INCOMPLETE_INTAKE] * rounds_needed)

    case = run_pipeline("chest pain, cannot breathe", llm_client=client)
    for _ in range(config.MAX_CLARIFICATION_ROUNDS):
        assert case.pipeline_status == PipelineStatus.AWAITING_CLARIFICATION
        case = run_pipeline("I don't know", llm_client=client, resume_case=case)

    # Past the cap: no more questions — safe referral instead.
    assert case.pipeline_status == PipelineStatus.DEGRADED
    assert case.failed_agent == "intake"
    assert case.next_steps == config.FAILSAFE_REFERRAL_TEXT
    assert case.final_triage is not None
    assert case.final_triage != Urgency.ROUTINE
