"""
Shared retry/backoff wrapper applied to every external call this system
makes (Anthropic, Groq, Sarvam STT/TTS, Twilio REST) — this runs in a live
casualty ward; a transient network blip must not surface as a hard failure
on the first try, but every call must still fail (never hang indefinitely)
past a bounded retry budget. See mira/config.py for the tunables.
"""
from __future__ import annotations

import logging
import time
from typing import Callable, TypeVar

from . import config

logger = logging.getLogger("mira.reliability")

T = TypeVar("T")


class ExternalCallFailed(Exception):
    """Raised when an external call still fails after exhausting retries.
    Wraps the last underlying exception; callers decide what "graceful
    degradation" means for their specific call site (e.g. llm_client.py
    raises LLMCallError, doctor_handoff.py records a 'failed' status rather
    than raising)."""

    def __init__(self, call_name: str, attempts: int, last_error: Exception):
        self.call_name = call_name
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(
            f"{call_name} failed after {attempts} attempt(s): {last_error}"
        )


def call_with_retries(
    fn: Callable[[], T],
    *,
    call_name: str,
    max_retries: int = config.EXTERNAL_CALL_MAX_RETRIES,
    base_delay_seconds: float = 0.5,
    retry_on: tuple[type[Exception], ...] = (Exception,),
) -> T:
    """Calls `fn()`, retrying up to `max_retries` additional times on any
    exception matching `retry_on`, with exponential backoff. Raises
    ExternalCallFailed (never the raw last exception) once the budget is
    exhausted, so every call site has one failure contract to handle."""
    attempts = 0
    last_error: Exception | None = None

    while attempts <= max_retries:
        attempts += 1
        try:
            return fn()
        except retry_on as exc:  # noqa: PERF203 - clarity over micro-perf here
            last_error = exc
            if attempts > max_retries:
                break
            delay = base_delay_seconds * (2 ** (attempts - 1))
            logger.warning(
                "%s: attempt %d/%d failed (%s), retrying in %.1fs",
                call_name, attempts, max_retries + 1, exc, delay,
            )
            time.sleep(delay)

    assert last_error is not None
    raise ExternalCallFailed(call_name, attempts, last_error)
