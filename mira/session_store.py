"""
Session store for cases awaiting clarification.

When Intake halts with a clarifying question, the case is parked here keyed
by the patient's phone number; the next inbound message from that number is
treated as the answer and resumes the SAME case (same case_id), so the
audit trail stays contiguous across WhatsApp round-trips.

This is a plain in-memory dict, which is sufficient for the July 20 - Aug 5
single-process testing phase. Known limitation (documented, not hidden): a
process restart drops pending sessions — the patient's next message then
simply starts a fresh case, which is a safe failure mode (worst case they
are asked again, never silently triaged on partial data). Swap for
SQLite/Redis behind these three functions if the deployment grows past one
process.

Sessions expire after SESSION_TTL_SECONDS: a clarification answer arriving
hours later shouldn't be merged into a stale clinical picture — symptoms
may have changed, so starting fresh is the safer interpretation.
"""
from __future__ import annotations

import time
from typing import Optional

from .state import PatientCase

SESSION_TTL_SECONDS = 60 * 60  # 1 hour

_pending: dict[str, tuple[float, PatientCase]] = {}


def park_case(phone_number: str, case: PatientCase) -> None:
    _pending[phone_number] = (time.time(), case)


def pop_pending_case(phone_number: str) -> Optional[PatientCase]:
    entry = _pending.pop(phone_number, None)
    if entry is None:
        return None
    stored_at, case = entry
    if time.time() - stored_at > SESSION_TTL_SECONDS:
        return None  # expired: safer to start a fresh case than merge stale data
    return case


def clear_all() -> None:
    """Test helper."""
    _pending.clear()
