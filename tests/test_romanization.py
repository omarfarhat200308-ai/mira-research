"""
Tests for the romanization-normalization pre-processing layer
(mira/language/romanization.py). Covers script detection, gloss insertion,
longest-phrase-first matching (no double-glossing when a short term is a
substring of a matched phrase), spelling-variance collapsing, and the
native-script no-op path.
"""
from __future__ import annotations

from mira.language.romanization import detect_script, normalize_romanized_text


def test_detect_script_latin():
    assert detect_script("high fever since yesterday") == "latin"


def test_detect_script_devanagari():
    assert detect_script("बुखार और खांसी है") == "devanagari"


def test_detect_script_telugu():
    assert detect_script("జ్వరం మరియు దగ్గు ఉంది") == "telugu"


def test_native_script_is_not_touched():
    text = "జ్వరం మరియు దగ్గు ఉంది"
    result = normalize_romanized_text(text)
    assert result.normalized_text == text
    assert result.glossed_terms == []


def test_romanized_hindi_single_term_glossed():
    result = normalize_romanized_text("2 saal ka baccha hai, pet dard aur ulti ho rahi hai")
    assert "abdominal pain" in result.glossed_terms
    assert "vomiting" in result.glossed_terms
    assert "pet dard [abdominal pain]" in result.normalized_text
    assert "ulti [vomiting]" in result.normalized_text


def test_romanized_telugu_single_term_glossed():
    result = normalize_romanized_text("naaku jwaram vachindi rendu rojula nunchi")
    assert result.glossed_terms == ["fever"]
    assert "jwaram [fever]" in result.normalized_text


def test_multiword_phrase_does_not_double_gloss_substring():
    # "tez bukhar" -> "high fever" as ONE phrase match; "bukhar" alone
    # ("fever") must not also match inside the already-glossed span.
    result = normalize_romanized_text("baby ko tez bukhar hai")
    assert result.glossed_terms == ["high fever"]
    assert result.normalized_text.count("[") == 1
    assert "[fever]" not in result.normalized_text


def test_repeated_character_spelling_variance_collapses():
    result = normalize_romanized_text("bukharrr hai baby ko do din se")
    assert result.glossed_terms == ["fever"]
    assert "bukharrr [fever]" in result.normalized_text


def test_english_text_glosses_nothing():
    text = "high fever since yesterday, no other symptoms"
    result = normalize_romanized_text(text)
    assert result.normalized_text == text
    assert result.glossed_terms == []


def test_original_text_never_mutated_only_appended():
    text = "seene mein dard ho raha hai"
    result = normalize_romanized_text(text)
    # Every word of the original still appears verbatim, in order.
    for word in text.split():
        assert word in result.normalized_text
