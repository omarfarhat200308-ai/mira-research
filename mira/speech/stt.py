"""
Speech-to-text for inbound WhatsApp voice notes, via Sarvam AI Saaras — NOT
a generic Whisper/GPT-4o-class pipeline. Saaras is chosen specifically for
Telugu + Hindi + code-mixed (Tenglish/Hinglish) speech accuracy, which
generic STT models handle poorly; see mira/language/romanization.py for the
matching text-side rationale.

Model/endpoint shape verified live against a real Sarvam key (2026-08-18):
saaras:v3 with mode="transcribe" (default) returns text in the ORIGINAL
spoken language/script — not saaras:v2 (doesn't exist; the API rejects it
with a list of current valid model strings) and not mode="translate"
(would silently convert non-English speech to English, which would break
downstream language detection in mira/agents/language.py). Indian AI API
surfaces move fast; re-verify against https://docs.sarvam.ai if this starts
failing again.

Fails loudly, never silently: if SARVAM_API_KEY isn't set, every call
raises SpeechServiceNotConfigured immediately rather than returning an
empty transcript or a generic error a caller might swallow. mira/webhook.py
turns this into an explicit "voice notes aren't available yet" reply to the
ASHA worker, never a dropped message.
"""
from __future__ import annotations

from typing import Optional

from .. import config, reliability
from .common import SpeechServiceCallFailed, SpeechServiceError, SpeechServiceNotConfigured, require_sarvam_api_key

__all__ = [
    "SpeechServiceError",
    "SpeechServiceNotConfigured",
    "SpeechServiceCallFailed",
    "transcribe_voice_note",
]


def transcribe_voice_note(
    audio_bytes: bytes,
    *,
    filename: str = "voice_note.ogg",
    language_hint: Optional[str] = None,
) -> str:
    """Transcribes a WhatsApp voice note (typically OGG/Opus from Twilio
    media) in its original language/script. `language_hint` (e.g. "hi-IN")
    is optional — Saaras auto-detects language, but passing a hint measurably
    improves script/language accuracy when the caller already has a good
    guess (verified empirically, not just per docs)."""
    import httpx  # local import: only required once this path is actually used

    api_key = require_sarvam_api_key()

    def _call():
        with httpx.Client(timeout=config.EXTERNAL_CALL_TIMEOUT_SECONDS) as client:
            resp = client.post(
                "https://api.sarvam.ai/speech-to-text",
                headers={"api-subscription-key": api_key},
                files={"file": (filename, audio_bytes, "audio/ogg")},
                data={
                    "model": "saaras:v3",
                    "mode": "transcribe",
                    **({"language_code": language_hint} if language_hint else {}),
                },
            )
            resp.raise_for_status()
            return resp.json()

    try:
        data = reliability.call_with_retries(_call, call_name="sarvam:stt")
    except reliability.ExternalCallFailed as exc:
        raise SpeechServiceCallFailed(f"Sarvam STT call failed: {exc}") from exc

    transcript = data.get("transcript")
    if not transcript:
        raise SpeechServiceCallFailed(
            f"Sarvam STT returned no transcript field in response: {data!r}"
        )
    return transcript
