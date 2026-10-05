"""
Per-phone-number language preference: asked once, via a numbered text
"poll", on a number's first-ever message to MIRA — then reused for every
subsequent message from that number instead of re-detecting language on
each message individually (which could drift message to message, e.g. one
message in English, the next in Hindi, giving an inconsistent experience).

In-memory (module-level dict) — same limitation as mira/session_store.py:
a process restart drops every stored preference and each number gets
asked again on its next message. Safe failure mode (one extra question at
worst), never a silently-wrong-language failure.
"""
from __future__ import annotations

from typing import Optional

_PENDING = "__pending__"

_preferences: dict[str, str] = {}


def has_been_contacted(phone_number: str) -> bool:
    """True once this number has been sent the poll at least once, whether
    or not they've answered yet — distinguishes "never messaged before"
    (send the poll) from "mid-poll, awaiting their reply"."""
    return phone_number in _preferences


def is_poll_pending(phone_number: str) -> bool:
    return _preferences.get(phone_number) == _PENDING


def mark_poll_pending(phone_number: str) -> None:
    _preferences[phone_number] = _PENDING


def set_preference(phone_number: str, language_code: str) -> None:
    _preferences[phone_number] = language_code


def get_preference(phone_number: str) -> Optional[str]:
    """Returns the stored language code, or None if never set (including
    while a poll reply is still pending — check is_poll_pending for that
    distinction explicitly rather than inferring it from None)."""
    value = _preferences.get(phone_number)
    return None if value == _PENDING else value


def clear_all() -> None:
    """Test helper."""
    _preferences.clear()
