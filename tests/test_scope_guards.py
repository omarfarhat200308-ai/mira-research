"""
Scope-guard tests: the diagnostic-claim blocklist (Diagnostic must never
assert a diagnosis, even in internal reasoning), the treatment-class terms
in the Referral filter, and the retry-once-then-fail-safe semantics shared
by both guards.
"""
from __future__ import annotations

import copy

import pytest

from mira import config
from mira.knowledge.diagnostic_claim_filter import (
    DiagnosticClaimViolation,
    check_diagnostic_text,
)
from mira.knowledge.drug_dosage_filter import DrugDosageViolation, check_referral_text
from mira.pipeline import run_pipeline
from mira.state import PipelineStatus, Urgency

from .fixtures.cases import CASES_BY_KEY

BASE_CASE = CASES_BY_KEY["chest_pain_sob"]

CLAIMING_DIAGNOSTIC = {
    "differential": [
        {
            "condition": "acute_coronary_syndrome",
            "reasoning": "The patient has acute coronary syndrome.",  # diagnostic claim
            "confidence": 0.8,
        },
    ],
    "confidence": 0.8,
    "reasoning": "This is a case of acute coronary syndrome.",
}


# --- unit level: the filter itself ---

@pytest.mark.parametrize(
    "text",
    [
        "You have pneumonia.",
        "The patient has tuberculosis and needs treatment.",
        "This is a case of meningitis.",
        "Diagnosis: pre-eclampsia.",
        "She is definitely suffering from sepsis.",
    ],
)
def test_claim_filter_rejects_diagnostic_language(text):
    with pytest.raises(DiagnosticClaimViolation):
        check_diagnostic_text(text)


@pytest.mark.parametrize(
    "text",
    [
        "Symptom pattern is consistent with acute coronary syndrome.",
        "Presentation raises concern for pre-eclampsia and warrants evaluation.",
        "Prolonged cough with weight loss warrants TB workup.",
        "Classic warning pattern; urgent in-person evaluation recommended.",
    ],
)
def test_claim_filter_accepts_concern_area_framing(text):
    check_diagnostic_text(text)  # must not raise


@pytest.mark.parametrize(
    "text",
    [
        "Take antibiotics for a week.",
        "A painkiller should help with the discomfort.",
        "Apply this ointment twice daily.",
    ],
)
def test_referral_filter_rejects_treatment_class_language(text):
    with pytest.raises(DrugDosageViolation):
        check_referral_text(text)


def test_referral_filter_accepts_facility_direction():
    check_referral_text(
        "Please go to the nearest hospital emergency department right now. "
        "Do not wait, and bring someone with you if possible."
    )


# --- pipeline level: retry-once, then fail-safe ---

def test_diagnostic_claim_retry_succeeds_when_model_rephrases():
    """First Diagnostic output asserts a diagnosis (rejected), the retry
    rephrases as a concern area (accepted) — pipeline completes normally."""
    client = BASE_CASE.build_client()
    good = copy.deepcopy(BASE_CASE.agent_responses["diagnostic"])
    client.register("diagnostic", [copy.deepcopy(CLAIMING_DIAGNOSTIC), good])

    result = run_pipeline(BASE_CASE.raw_input_text, llm_client=client)

    assert result.pipeline_status == PipelineStatus.OK
    assert result.final_triage == Urgency.EMERGENCY


def test_diagnostic_claim_on_both_attempts_degrades_to_failsafe():
    client = BASE_CASE.build_client()
    client.register("diagnostic", copy.deepcopy(CLAIMING_DIAGNOSTIC))  # same output every attempt

    result = run_pipeline(BASE_CASE.raw_input_text, llm_client=client)

    assert result.pipeline_status == PipelineStatus.DEGRADED
    assert result.failed_agent == "diagnostic"
    assert result.next_steps == config.FAILSAFE_REFERRAL_TEXT
    # The claiming text never lands in the case's differential.
    assert result.differential == []


def test_referral_treatment_language_retry_then_failsafe():
    client = BASE_CASE.build_client()
    client.register(
        "referral",
        {
            "next_steps": "Go to the hospital, and meanwhile take a painkiller for the chest pain.",
            "reasoning": "Simulated unsafe output.",
            "confidence": 0.9,
        },
    )
    result = run_pipeline(BASE_CASE.raw_input_text, llm_client=client)

    assert result.pipeline_status == PipelineStatus.DEGRADED
    assert result.failed_agent == "referral"
    assert "painkiller" not in (result.next_steps or "")
    assert result.next_steps == config.FAILSAFE_REFERRAL_TEXT
