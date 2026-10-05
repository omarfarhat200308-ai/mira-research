"""
Proves the core safety claim directly: a hardcoded red flag, once fired,
decides final_triage regardless of what the LLM concludes. A single model
failure (or an adversarially wrong LLM output) cannot silently downgrade an
emergency.
"""
from mira.llm_client import MockLLMClient
from mira.pipeline import run_pipeline
from mira.state import PipelineStatus, TriageDecidedBy, Urgency

from .fixtures.cases import CASES_BY_KEY

RULE_FIRING_CASE = CASES_BY_KEY["chest_pain_sob"]  # chest_pain + shortness_of_breath


def test_red_flag_wins_even_when_llm_says_routine():
    client = RULE_FIRING_CASE.build_client()
    # Adversarially override the triage LLM call: it will insist this is
    # routine, despite chest pain + shortness of breath being present.
    client.register(
        "triage",
        {
            "urgency": "routine",
            "reasoning": "Adversarial/incorrect model output for testing: claims this is nothing to worry about.",
            "confidence": 0.95,
        },
    )

    result = run_pipeline(RULE_FIRING_CASE.raw_input_text, llm_client=client)

    assert result.pipeline_status == PipelineStatus.OK
    assert result.final_triage == Urgency.EMERGENCY
    assert result.triage_decided_by == TriageDecidedBy.RULE_OVERRIDE
    # The LLM's (wrong) assessment is still recorded for audit, not hidden.
    assert result.llm_triage_assessment is not None
    assert result.llm_triage_assessment.urgency == Urgency.ROUTINE


def test_red_flag_wins_even_when_llm_confidently_says_low_urgency_with_high_confidence():
    client = RULE_FIRING_CASE.build_client()
    client.register(
        "triage",
        {
            "urgency": "urgent",  # still wrong — should be emergency
            "reasoning": "Adversarial: downplays severity.",
            "confidence": 0.99,
        },
    )
    result = run_pipeline(RULE_FIRING_CASE.raw_input_text, llm_client=client)
    assert result.final_triage == Urgency.EMERGENCY
    assert result.triage_decided_by == TriageDecidedBy.RULE_OVERRIDE


def test_no_red_flag_case_does_defer_to_llm():
    """Sanity check for the flip side: when no rule fires, the LLM's
    well-formed, confident assessment IS what decides final_triage — the
    override only ever escalates, it doesn't replace LLM judgment when
    there's nothing to override."""
    mild_case = CASES_BY_KEY["mild_cold"]
    client = mild_case.build_client()
    result = run_pipeline(mild_case.raw_input_text, llm_client=client)

    assert result.final_triage == Urgency.ROUTINE
    assert result.triage_decided_by == TriageDecidedBy.LLM
