"""
DPDP Act 2023-compliant consent/audit trail (Stage 6) — a first-class table,
not an afterthought field. Two distinct consent scopes are modeled
separately (TRIAGE_SUPPORT vs DOCTOR_REFERRAL_SHARE) because Stage 5's
doctor handoff is a genuinely different data flow than triage support
itself and needs its own explicit consent statement, not a blended one —
see mira/notifications/doctor_handoff.py.

patient_ref is ALWAYS a hash (see mira/consent/store.py:hash_patient_ref),
never a raw identifier — enforced by construction: record_consent() in
store.py is the only place a ConsentRecord gets created, and it hashes
before writing. There is no code path in this module that accepts a raw
identifier.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ConsentScope(str, Enum):
    TRIAGE_SUPPORT = "triage_support"
    DOCTOR_REFERRAL_SHARE = "doctor_referral_share"
    DEIDENTIFIED_RESEARCH = "deidentified_research"


def _new_consent_id() -> str:
    return f"consent_{uuid.uuid4().hex[:12]}"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ConsentRecord(Base):
    __tablename__ = "consent_records"

    consent_id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_consent_id)
    patient_ref: Mapped[str] = mapped_column(String, nullable=False, index=True)  # hashed, never raw
    asha_worker_id: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    consent_scope: Mapped[str] = mapped_column(String, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
