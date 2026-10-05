"""Shared exception hierarchy + API-key check for mira/speech/stt.py and
mira/speech/tts.py — both call the same Sarvam account/key, so this is the
one place that check lives."""
from __future__ import annotations

import os


class SpeechServiceError(Exception):
    """Base for speech-service failures — callers (mira/webhook.py) can
    catch this alone to mean "voice isn't available right now for any
    reason," or catch the two subclasses separately to distinguish a
    deploy-time misconfiguration from a runtime call failure."""


class SpeechServiceNotConfigured(SpeechServiceError):
    """Raised immediately (not a silent no-op) when a Sarvam call is
    attempted without SARVAM_API_KEY set."""


class SpeechServiceCallFailed(SpeechServiceError):
    """Raised when SARVAM_API_KEY is set but the call itself failed (after
    the retry budget in mira/reliability.py) or returned an unusable
    response."""


def require_sarvam_api_key() -> str:
    api_key = os.environ.get("SARVAM_API_KEY")
    if not api_key:
        raise SpeechServiceNotConfigured(
            "SARVAM_API_KEY is not set — Sarvam speech services are "
            "unavailable. Set SARVAM_API_KEY to enable Saaras STT / Bulbul "
            "TTS, and confirm access via https://docs.sarvam.ai first if "
            "this hasn't been provisioned yet."
        )
    return api_key
