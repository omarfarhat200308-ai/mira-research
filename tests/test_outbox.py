"""
Tests for mira/notifications/outbox.py: enqueue/flush semantics for the
intermittent-connectivity retry queue — a successful send marks the
message SENT, a failing send keeps it PENDING (until MAX_SEND_ATTEMPTS) and
records the error, never silently drops it.
"""
from __future__ import annotations

import pytest

from mira.notifications import outbox


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test_outbox.db"
    monkeypatch.setattr(outbox.config, "DATABASE_URL", f"sqlite:///{db_path}")
    outbox._engine = None
    outbox.init_db()
    yield
    outbox._engine = None


def test_enqueue_creates_pending_message():
    msg = outbox.enqueue(case_id="case_1", kind="doctor_handoff", to_number="+911111111111", body="hello")
    assert msg.status == outbox.OutboxStatus.PENDING.value
    assert msg.attempts == 0
    pending = outbox.pending_messages()
    assert len(pending) == 1
    assert pending[0].id == msg.id


def test_flush_pending_marks_successful_send_as_sent():
    outbox.enqueue(case_id="case_1", kind="doctor_handoff", to_number="+911111111111", body="hello")

    summary = outbox.flush_pending(lambda to, body: None)  # succeeds

    assert summary == {"sent": 1, "failed": 0, "still_pending": 0}
    assert outbox.pending_messages() == []


def test_flush_pending_keeps_failed_send_pending_until_max_attempts():
    outbox.enqueue(case_id="case_1", kind="doctor_handoff", to_number="+911111111111", body="hello")

    def always_fails(to, body):
        raise RuntimeError("network down")

    for _ in range(outbox.MAX_SEND_ATTEMPTS - 1):
        summary = outbox.flush_pending(always_fails)
        assert summary["still_pending"] == 1

    # Final attempt exhausts the budget -> moves to FAILED, not retried forever.
    summary = outbox.flush_pending(always_fails)
    assert summary["failed"] == 1
    assert outbox.pending_messages() == []


def test_flush_pending_records_last_error():
    outbox.enqueue(case_id="case_1", kind="doctor_handoff", to_number="+911111111111", body="hello")

    def always_fails(to, body):
        raise RuntimeError("simulated failure detail")

    outbox.flush_pending(always_fails)

    from sqlalchemy.orm import Session

    with Session(outbox.get_engine()) as session:
        rows = session.query(outbox.OutboundMessage).all()
        assert len(rows) == 1
        assert "simulated failure detail" in rows[0].last_error
