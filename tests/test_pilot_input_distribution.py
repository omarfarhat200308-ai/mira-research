"""
Confirms the pipeline's romanization pre-processing (mira/language/
romanization.py) actually runs on romanized-script pilot-realistic input,
end to end through run_pipeline — not just in isolation (see
test_romanization.py). Voice-note-shaped input is covered separately in
test_webhook.py (STT routing, mocked — no real audio/key available in this
environment); this file covers the text-script side of "replay the pilot's
expected input distribution."
"""
from __future__ import annotations

from mira.pipeline import run_pipeline

from .fixtures.cases import CASES_BY_KEY


def test_romanized_hindi_case_triggers_gloss_normalization():
    case = CASES_BY_KEY["romanized_hindi_chest_pain"]
    result = run_pipeline(case.raw_input_text, llm_client=case.build_client())

    assert result.detected_script == "latin"
    assert result.romanized_terms_glossed  # non-empty
    assert "chest pain" in result.romanized_terms_glossed
    assert "shortness of breath" in result.romanized_terms_glossed
    assert "[chest pain]" in result.normalized_input_text
    assert result.final_triage == case.expected_final_triage


def test_romanized_telugu_case_triggers_gloss_normalization():
    case = CASES_BY_KEY["romanized_telugu_mild_cough"]
    result = run_pipeline(case.raw_input_text, llm_client=case.build_client())

    assert result.detected_script == "latin"
    # "jwaram" ("fever") is glossed even though negated ("jwaram ledu" = "no
    # fever") — negation-parsing is explicitly out of scope for this
    # gloss-only layer (see romanization.py's module docstring); it widens
    # what the reasoning stage sees, it doesn't interpret it.
    assert set(result.romanized_terms_glossed) == {"cough", "fever"}
    assert "[cough]" in result.normalized_input_text
    assert result.final_triage == case.expected_final_triage


def test_native_script_input_is_not_glossed_but_still_completes_pipeline():
    """A native-Devanagari-script case should pass straight through the
    romanization step untouched (nothing for it to do) and still complete
    normally — proves the pre-processing step is a no-op, not a blocker,
    for already-native-script input."""
    client = CASES_BY_KEY["mild_cold"].build_client()
    native_script_text = "मुझे 2 दिन से हल्की खांसी और नाक बह रही है, कुछ गंभीर नहीं।"

    result = run_pipeline(native_script_text, llm_client=client)

    assert result.detected_script == "devanagari"
    assert result.romanized_terms_glossed == []
    assert result.normalized_input_text == native_script_text
