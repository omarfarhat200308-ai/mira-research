"""
Consent store CRUD. Defaults to a local SQLite file (config.DATABASE_URL)
so this is runnable/testable without provisioning Postgres — point
DATABASE_URL at a real Postgres instance for the pilot; the SQLAlchemy Core
usage here is dialect-agnostic, no code change needed either way.

hash_patient_ref() is the ONLY sanctioned way a caller turns a raw patient
identifier (phone number, name, whatever) into what actually gets stored —
record_consent() calls it internally, so there is no code path that writes
a raw identifier to the table. CONSENT_HASH_SALT must be set to a real
secret (not the dev default) before this handles real patient data; the
dev default deliberately embeds "dev-only-insecure" in its value so it's
obvious in a config dump if it's still in use.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session

from .. import config
from .models import Base, ConsentRecord, ConsentScope

_engine: Optional[Engine] = None


def hash_patient_ref(raw_identifier: str) -> str:
    salted = f"{config.CONSENT_HASH_SALT}:{raw_identifier}"
    return hashlib.sha256(salted.encode("utf-8")).hexdigest()


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(config.DATABASE_URL, future=True)
    return _engine


def init_db() -> None:
    """Creates the consent_records table if it doesn't exist. Safe to call
    on every process start (idempotent, SQLAlchemy checks first)."""
    Base.metadata.create_all(get_engine())


def record_consent(
    *, patient_ref_raw: str, asha_worker_id: str, consent_scope: ConsentScope
) -> ConsentRecord:
    record = ConsentRecord(
        patient_ref=hash_patient_ref(patient_ref_raw),
        asha_worker_id=asha_worker_id,
        consent_scope=consent_scope.value,
    )
    with Session(get_engine()) as session:
        session.add(record)
        session.commit()
        session.refresh(record)
        session.expunge(record)
    return record


def has_active_consent(*, patient_ref_raw: str, consent_scope: ConsentScope) -> bool:
    patient_ref = hash_patient_ref(patient_ref_raw)
    with Session(get_engine()) as session:
        stmt = (
            select(ConsentRecord)
            .where(ConsentRecord.patient_ref == patient_ref)
            .where(ConsentRecord.consent_scope == consent_scope.value)
            .where(ConsentRecord.revoked_at.is_(None))
        )
        return session.execute(stmt).scalars().first() is not None


def revoke_consent(consent_id: str) -> bool:
    """Returns True if a matching, not-already-revoked record was found and
    revoked. Never deletes the row — revocation is itself part of the audit
    trail."""
    with Session(get_engine()) as session:
        record = session.get(ConsentRecord, consent_id)
        if record is None or record.revoked_at is not None:
            return False
        record.revoked_at = datetime.now(timezone.utc)
        session.commit()
        return True
