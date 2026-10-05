"""
Tests for mira/consent/store.py: record/check/revoke consent, the two
handoff-relevant scopes are tracked independently, and — the actual safety
property this table exists for — patient_ref is always hashed, never the
raw identifier, in what gets written to the database.
"""
from __future__ import annotations

import pytest

from mira.consent import store
from mira.consent.models import ConsentRecord, ConsentScope


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Each test gets its own throwaway SQLite file so tests can't see each
    other's consent records, and the module-level cached engine is reset."""
    db_path = tmp_path / "test_consent.db"
    monkeypatch.setattr(store.config, "DATABASE_URL", f"sqlite:///{db_path}")
    store._engine = None
    store.init_db()
    yield
    store._engine = None


def test_record_and_check_active_consent():
    store.record_consent(
        patient_ref_raw="+919876543210", asha_worker_id="asha_001", consent_scope=ConsentScope.TRIAGE_SUPPORT
    )
    assert store.has_active_consent(
        patient_ref_raw="+919876543210", consent_scope=ConsentScope.TRIAGE_SUPPORT
    )


def test_scopes_are_independent_not_blended():
    store.record_consent(
        patient_ref_raw="+919876543210", asha_worker_id="asha_001", consent_scope=ConsentScope.TRIAGE_SUPPORT
    )
    # Triage-support consent does NOT imply doctor-referral-share consent —
    # Stage 5's whole point is these are two distinct statements.
    assert not store.has_active_consent(
        patient_ref_raw="+919876543210", consent_scope=ConsentScope.DOCTOR_REFERRAL_SHARE
    )


def test_revoke_consent_marks_inactive_but_keeps_the_row():
    record = store.record_consent(
        patient_ref_raw="+919876543210", asha_worker_id="asha_001", consent_scope=ConsentScope.TRIAGE_SUPPORT
    )
    assert store.revoke_consent(record.consent_id) is True
    assert not store.has_active_consent(
        patient_ref_raw="+919876543210", consent_scope=ConsentScope.TRIAGE_SUPPORT
    )
    # Revocation is itself audit trail — the row must still exist.
    from sqlalchemy.orm import Session

    with Session(store.get_engine()) as session:
        row = session.get(ConsentRecord, record.consent_id)
        assert row is not None
        assert row.revoked_at is not None


def test_revoke_unknown_consent_id_returns_false():
    assert store.revoke_consent("consent_does_not_exist") is False


def test_patient_ref_is_never_stored_raw():
    raw_number = "+919876543210"
    record = store.record_consent(
        patient_ref_raw=raw_number, asha_worker_id="asha_001", consent_scope=ConsentScope.TRIAGE_SUPPORT
    )
    assert record.patient_ref != raw_number
    assert raw_number not in record.patient_ref
    assert record.patient_ref == store.hash_patient_ref(raw_number)


def test_hash_is_deterministic_for_same_input():
    assert store.hash_patient_ref("+919876543210") == store.hash_patient_ref("+919876543210")


def test_hash_differs_for_different_inputs():
    assert store.hash_patient_ref("+919876543210") != store.hash_patient_ref("+919876543211")
