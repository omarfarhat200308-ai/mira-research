"""LLM-free tests for the v2 conservative-escalation fix: a case that Intake
halts must never leave the sender with only a question."""
import copy

import pytest

from mira import config
from mira.llm_client import MockLLMClient
from mira.pipeline import run_pipeline
from mira.safety import precheck
from mira.state import PipelineStatus, TriageDecidedBy, Urgency

from .fixtures.cases import CASES_BY_KEY
from .test_clarification_flow import INCOMPLETE_INTAKE, _client_with_intake_sequence


@pytest.mark.parametrize("text", [
    "chest pain and cannot breathe",
    "my father has chest tightness, short of breath",
    "she had a seizure just now",
    "baby is unconscious and not responding",
    "bahut khoon aa raha hai delivery ke baad",
    "he is vomiting blood",
    "black stool since morning",
    "pregnant, severe headache, blurred vision, swollen feet",
    "seene mein dard aur saans nahi aa rahi",
    "he fainted and collapsed",
])
def test_precheck_fires_on_emergencies(text):
    assert precheck.screen(text), text


@pytest.mark.parametrize("text", [
    "mild cold and runny nose for two days",
    "no chest pain, only a sore throat",
    "knee pain after walking",
    "headache since yesterday",
    "",
])
def test_precheck_quiet_on_benign_or_negated(text):
    assert precheck.screen(text) == [], text


def test_only_emits_known_tags():
    from mira.knowledge.symptom_tags import SYMPTOM_TAGS
    assert set(precheck._COMPILED) <= SYMPTOM_TAGS


def test_halted_emergency_gets_emergency_message_and_stays_resumable():
    client = _client_with_intake_sequence(INCOMPLETE_INTAKE)
    r = run_pipeline("chest pain, cannot breathe", llm_client=client)
    assert r.pipeline_status == PipelineStatus.AWAITING_CLARIFICATION
    assert r.final_triage == Urgency.EMERGENCY
    assert r.triage_decided_by == TriageDecidedBy.RULE_OVERRIDE
    assert r.red_flags_triggered
    assert config.INTERIM_EMERGENCY_TEXT in r.patient_facing_reply
    assert INCOMPLETE_INTAKE["clarifying_question"] in r.patient_facing_reply


def test_halted_nonemergency_gets_generic_safety_line_not_a_triage_call():
    intake = copy.deepcopy(INCOMPLETE_INTAKE)
    intake["symptoms"] = [{"name": "cough", "onset": "2 days", "duration": "2 days", "severity": "mild"}]
    client = _client_with_intake_sequence(intake)
    r = run_pipeline("cough for two days", llm_client=client)
    assert r.pipeline_status == PipelineStatus.AWAITING_CLARIFICATION
    assert r.final_triage is None            # we do not invent a tier
    assert config.INTERIM_SAFETY_TEXT in r.patient_facing_reply
    assert intake["clarifying_question"] in r.patient_facing_reply


def test_resume_still_completes_and_triage_overrides_interim_value():
    complete = CASES_BY_KEY["chest_pain_sob"].agent_responses["intake"]
    client = _client_with_intake_sequence(INCOMPLETE_INTAKE, complete)
    first = run_pipeline("chest pain, cannot breathe", llm_client=client)
    second = run_pipeline("55 years, male", llm_client=client, resume_case=first)
    assert second.pipeline_status == PipelineStatus.OK
    assert second.final_triage == Urgency.EMERGENCY


def test_intake_agent_failure_with_red_flag_text_degrades_to_emergency():
    from mira.pipeline import _apply_failsafe_degradation
    from mira.state import PatientCase
    case = PatientCase(raw_input_text="he is unconscious and having a seizure")
    out = _apply_failsafe_degradation(case, "intake", "timeout")
    assert out.final_triage == Urgency.EMERGENCY


def test_intake_agent_failure_without_red_flag_still_urgent():
    from mira.pipeline import _apply_failsafe_degradation
    from mira.state import PatientCase
    out = _apply_failsafe_degradation(PatientCase(raw_input_text="mild cold"), "intake", "timeout")
    assert out.final_triage == Urgency.URGENT
