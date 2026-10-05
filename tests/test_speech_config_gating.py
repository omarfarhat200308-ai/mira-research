"""
Tests the one thing that's actually testable without a real SARVAM_API_KEY
or audio/network access: that mira/speech/stt.py and tts.py fail loudly
and immediately (SpeechServiceNotConfigured) when the key is absent, rather
than silently no-op'ing or raising some generic/unclear error a caller
might swallow.
"""
from __future__ import annotations

import pytest

from mira.speech import stt, tts
from mira.speech.common import SpeechServiceNotConfigured


def test_stt_raises_not_configured_without_api_key(monkeypatch):
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    with pytest.raises(SpeechServiceNotConfigured):
        stt.transcribe_voice_note(b"fake-audio-bytes")


def test_tts_synthesize_raises_not_configured_without_api_key(monkeypatch):
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    with pytest.raises(SpeechServiceNotConfigured):
        tts.synthesize_speech("hello", language_code="te-IN")


def test_tts_confirm_voice_available_raises_not_configured_without_api_key(monkeypatch):
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    with pytest.raises(SpeechServiceNotConfigured):
        tts.confirm_voice_available("te-IN")


def test_stt_and_tts_share_the_same_exception_hierarchy():
    # mira/webhook.py should be able to catch one base type for "voice
    # isn't available right now" regardless of which module raised it.
    assert issubclass(stt.SpeechServiceNotConfigured, stt.SpeechServiceError)
    assert issubclass(tts.SpeechServiceNotConfigured, tts.SpeechServiceError)
    assert stt.SpeechServiceError is tts.SpeechServiceError
