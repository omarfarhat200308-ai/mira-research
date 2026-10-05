"""
Retryable outbound-message queue for Twilio sends (doctor handoff, and
available for the ASHA-facing reply too), because this runs in a field
setting with assumed-intermittent connectivity — a failed send must be
retried later, not silently dropped nor treated as a single-shot
best-effort.

This provides the mechanism (enqueue / flush / status tracking) as real,
testable code. It does NOT provide a scheduler — flush_pending() is a
function a periodic job (cron, a Cloudflare Worker Cron Trigger, a FastAPI
background task, whatever the deployment target uses) is expected to call
on an interval; wiring that scheduler up is an infra decision for actual
deployment, out of scope here.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Optional

from sqlalchemy import DateTime, Integer, String, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .. import config


class Base(DeclarativeBase):
    pass


class OutboxStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"  # exhausted MAX_SEND_ATTEMPTS; needs manual attention


MAX_SEND_ATTEMPTS = 5


def _new_id() -> str:
    return f"outbox_{uuid.uuid4().hex[:12]}"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OutboundMessage(Base):
    __tablename__ = "outbound_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    case_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)  # e.g. "doctor_handoff"
    to_number: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default=OutboxStatus.PENDING.value)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(String, nullable=True)


_engine = None


def get_engine():
    global _engine
    if _engine is None:
        from sqlalchemy import create_engine

        _engine = create_engine(config.DATABASE_URL, future=True)
    return _engine


def init_db() -> None:
    Base.metadata.create_all(get_engine())


def enqueue(*, case_id: str, kind: str, to_number: str, body: str) -> OutboundMessage:
    message = OutboundMessage(case_id=case_id, kind=kind, to_number=to_number, body=body)
    with Session(get_engine()) as session:
        session.add(message)
        session.commit()
        session.refresh(message)
        session.expunge(message)
    return message


def pending_messages() -> list[OutboundMessage]:
    with Session(get_engine()) as session:
        stmt = select(OutboundMessage).where(
            OutboundMessage.status == OutboxStatus.PENDING.value,
            OutboundMessage.attempts < MAX_SEND_ATTEMPTS,
        )
        rows = session.execute(stmt).scalars().all()
        for row in rows:
            session.expunge(row)
        return list(rows)


def flush_pending(send_fn: Callable[[str, str], None]) -> dict[str, int]:
    """Attempts every pending message via `send_fn(to_number, body)` (raise
    on failure, return normally on success). Meant to be invoked by an
    external periodic job — see module docstring. Returns a small summary
    dict for logging/observability, e.g. {"sent": 2, "failed": 1,
    "still_pending": 0}."""
    summary = {"sent": 0, "failed": 0, "still_pending": 0}
    with Session(get_engine()) as session:
        stmt = select(OutboundMessage).where(
            OutboundMessage.status == OutboxStatus.PENDING.value,
            OutboundMessage.attempts < MAX_SEND_ATTEMPTS,
        )
        for message in session.execute(stmt).scalars().all():
            message.attempts += 1
            message.last_attempt_at = _utcnow()
            try:
                send_fn(message.to_number, message.body)
            except Exception as exc:  # noqa: BLE001 - any send failure is a retry candidate
                message.last_error = str(exc)
                if message.attempts >= MAX_SEND_ATTEMPTS:
                    message.status = OutboxStatus.FAILED.value
                    summary["failed"] += 1
                else:
                    summary["still_pending"] += 1
            else:
                message.status = OutboxStatus.SENT.value
                summary["sent"] += 1
        session.commit()
    return summary
