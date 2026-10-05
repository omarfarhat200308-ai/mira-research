"""
Text-to-speech for outbound patient-facing replies, via Sarvam AI Bulbul —
for low-literacy accessibility, since ASHA workers and patients are field-
operating, not desk-reading (see config.SYSTEM_FRAMING / README for the
15-second-comprehension design constraint this feeds).

Endpoint/auth shape below is per Sarvam's public API as of last
verification (POST https://api.sarvam.ai/text-to-speech, header
api-subscription-key) — confirm against https://docs.sarvam.ai before
relying on this in production, and confirm Telugu is actually in Bulbul's
active voice list via confirm_voice_available() before wiring this into the
pipeline for a Telugu-speaking pilot; don't assume.
"""
from __future__ import annotations

from .. import config, reliability
from .common import SpeechServiceCallFailed, SpeechServiceError, SpeechServiceNotConfigured, require_sarvam_api_key

__all__ = [
    "SpeechServiceError",
    "SpeechServiceNotConfigured",
    "SpeechServiceCallFailed",
    "synthesize_speech",
    "confirm_voice_available",
]


def synthesize_speech(text: str, *, language_code: str, voice: str = "priya") -> bytes:
    """Returns raw audio bytes (WAV) for `text` in `language_code` (e.g.
    "te-IN", "hi-IN"). Raises SpeechServiceNotConfigured if SARVAM_API_KEY
    is unset, SpeechServiceCallFailed if the call itself fails — see
    stt.py's exception hierarchy, shared here rather than duplicated.

    Model/speaker verified live 2026-09-12: bulbul:v2 is deprecated (API
    now hard-rejects it, "Please use bulbul:v3 instead") and v3 uses a
    different, non-overlapping speaker roster -- "anushka" (the old
    default) doesn't exist under v3 and the call 400s. "priya" confirmed
    working. Sarvam's model/speaker lineup moves fast; re-verify against
    https://docs.sarvam.ai if this starts failing again, same caution as
    stt.py's saaras version note."""
    import httpx  # local import: only required once this path is actually used

    api_key = require_sarvam_api_key()

    def _call():
        with httpx.Client(timeout=config.EXTERNAL_CALL_TIMEOUT_SECONDS) as client:
            resp = client.post(
                "https://api.sarvam.ai/text-to-speech",
                headers={"api-subscription-key": api_key, "Content-Type": "application/json"},
                json={
                    "inputs": [text],
                    "target_language_code": language_code,
                    "speaker": voice,
                    "model": "bulbul:v3",
                },
            )
            resp.raise_for_status()
            return resp.json()

    try:
        data = reliability.call_with_retries(_call, call_name="sarvam:tts")
    except reliability.ExternalCallFailed as exc:
        raise SpeechServiceCallFailed(f"Sarvam TTS call failed: {exc}") from exc

    audio_b64_list = data.get("audios")
    if not audio_b64_list:
        raise SpeechServiceCallFailed(f"Sarvam TTS returned no audio in response: {data!r}")

    import base64

    return base64.b64decode(audio_b64_list[0])


def confirm_voice_available(language_code: str, voice: str = "anushka") -> bool:
    """Hits Sarvam's voice/model listing to confirm `language_code` (e.g.
    Telugu "te-IN") is actually in Bulbul's active voice list — call this
    once at deploy time before assuming Telugu TTS works; Sarvam's
    supported-language list is not guaranteed stable across versions."""
    import httpx  # local import: only required once this path is actually used

    api_key = require_sarvam_api_key()

    def _call():
        with httpx.Client(timeout=config.EXTERNAL_CALL_TIMEOUT_SECONDS) as client:
            resp = client.get(
                "https://api.sarvam.ai/text-to-speech/supported-languages",
                headers={"api-subscription-key": api_key},
            )
            resp.raise_for_status()
            return resp.json()

    try:
        data = reliability.call_with_retries(_call, call_name="sarvam:tts-voices")
    except reliability.ExternalCallFailed as exc:
        raise SpeechServiceCallFailed(f"Sarvam voice-list call failed: {exc}") from exc

    supported = data.get("languages", data.get("supported_languages", []))
    return language_code in supported
