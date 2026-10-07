"""
Proves the "graceful degradation" build requirement: if any agent fails or
returns malformed output, the pipeline must default to the hardcoded
"refer to nearest clinic" fallback rather than guessing, and must never
leave final_triage unset or silently at ROUTINE.
"""
from __future__ import annotations

import pytest

from mira import config
from mira.llm_client import MockLLMClient
from mira.notifications import doctor_handoff
from mira.pipeline import run_pipeline
from mira.state import DataSource, PipelineStatus, Urgency

from .fixtures.cases import CASES_BY_KEY

BASE_CASE = CASES_BY_KEY["chest_pain_sob"]


def _client_with_malformed(agent_name: str) -> MockLLMClient:
    client = BASE_CASE.build_client()
    client.register(agent_name, MockLLMClient.MALFORMED)
    return client


@pytest.mark.parametrize(
    "agent_name",
    ["intake", "language_normalize", "diagnostic", "triage", "referral"],
)
def test_malformed_output_at_any_stage_degrades_to_failsafe(agent_name):
    client = _client_with_malformed(agent_name)
    result = run_pipeline(BASE_CASE.raw_input_text, llm_client=client)

    assert result.pipeline_status == PipelineStatus.DEGRADED
    assert result.failed_agent == agent_name
    assert result.next_steps == config.FAILSAFE_REFERRAL_TEXT
    assert result.patient_facing_reply == config.FAILSAFE_REFERRAL_TEXT
    # Never left unset, never silently downgraded to routine.
    assert result.final_triage is not None
    assert result.final_triage != Urgency.ROUTINE


def test_failsafe_degraded_urgent_case_still_reaches_doctor_handoff_evaluation():
    """A degraded case lands on URGENT (see _apply_failsafe_degradation),
    which is exactly the band Stage 5 doctor handoff exists for — the
    receiving facility should know an unassessed, MIRA-referred case is
    coming. This must not be skipped just because the pipeline took the
    early-return degradation path rather than completing normally."""
    client = _client_with_malformed("diagnostic")
    result = run_pipeline(
        BASE_CASE.raw_input_text, llm_client=client, data_source=DataSource.PILOT
    )

    assert result.pipeline_status == PipelineStatus.DEGRADED
    # v2: BASE_CASE text contains a deterministic red flag, so a degraded run
    # escalates to EMERGENCY (non-red-flag text still lands on URGENT; see
    # tests/test_precheck_and_interim_safety.py).
    assert result.final_triage == Urgency.EMERGENCY
    # Handoff was evaluated (not silently skipped by an early return) — in
    # this test env it's skipped only because ENABLE_DOCTOR_HANDOFF_SEND
    # isn't set, never because the degraded path bypassed evaluation.
    assert result.doctor_handoff_status == doctor_handoff.STATUS_SKIPPED_NOT_CONFIGURED


def test_agent_raising_exception_also_degrades_to_failsafe():
    client = BASE_CASE.build_client()
    client.register("diagnostic", RuntimeError("simulated network timeout"))
    result = run_pipeline(BASE_CASE.raw_input_text, llm_client=client)

    assert result.pipeline_status == PipelineStatus.DEGRADED
    assert result.failed_agent == "diagnostic"
    assert result.next_steps == config.FAILSAFE_REFERRAL_TEXT
    assert result.final_triage is not None
    assert result.final_triage != Urgency.ROUTINE


def test_referral_drug_dosage_violation_degrades_to_failsafe_not_sent_to_patient():
    """Referral text that slips in a drug/dosage recommendation must never
    reach the patient — the filter should reject it and the pipeline
    should fall back, not strip-and-continue."""
    client = BASE_CASE.build_client()
    client.register(
        "referral",
        {
            "next_steps": "Take 500mg of paracetamol twice a day and rest.",
            "reasoning": "Simulated unsafe LLM output for testing the filter.",
            "confidence": 0.9,
        },
    )
    result = run_pipeline(BASE_CASE.raw_input_text, llm_client=client)

    assert result.pipeline_status == PipelineStatus.DEGRADED
    assert result.failed_agent == "referral"
    assert "paracetamol" not in (result.next_steps or "")
    assert "mg" not in (result.next_steps or "")
    assert result.next_steps == config.FAILSAFE_REFERRAL_TEXT


def test_translation_failure_alone_does_not_erase_correct_triage():
    """A Language(translate) failure after a correct triage/referral should
    not throw away the already-correct urgency decision — only the
    patient-facing translation is affected."""
    client = BASE_CASE.build_client()
    client.register("language_translate", MockLLMClient.MALFORMED)
    result = run_pipeline(BASE_CASE.raw_input_text, llm_client=client)

    assert result.final_triage == BASE_CASE.expected_final_triage
    assert result.triage_decided_by == BASE_CASE.expected_decided_by
    assert result.pipeline_status == PipelineStatus.DEGRADED
    assert result.failed_agent == "language_translate"
    # Referral text itself should be untouched/correct, just not translated.
    assert result.next_steps is not None
    assert result.next_steps != config.FAILSAFE_REFERRAL_TEXT
