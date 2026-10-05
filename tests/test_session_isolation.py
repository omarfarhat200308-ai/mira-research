"""
Session isolation / restart / concurrency for mira.session_store.

These pin the CURRENT behaviour. They do not claim a historical
"session-mixing" bug was reproduced: no such bug or fix commit was found in
the git history of this repo or of tabib-v1 (see MIRA_FINAL_STATUS.md).
"""
import importlib
import threading

from mira import session_store
from mira.state import PatientCase


def _case(text: str) -> PatientCase:
    return PatientCase(raw_input_text=text)


def setup_function(_):
    session_store._pending.clear()


def test_two_phones_do_not_mix():
    session_store.park_case("whatsapp:+10000000001", _case("case A"))
    session_store.park_case("whatsapp:+10000000002", _case("case B"))
    a = session_store.pop_pending_case("whatsapp:+10000000001")
    b = session_store.pop_pending_case("whatsapp:+10000000002")
    assert a.raw_input_text == "case A" and b.raw_input_text == "case B"
    assert a.case_id != b.case_id


def test_pop_consumes_the_session():
    session_store.park_case("p1", _case("x"))
    assert session_store.pop_pending_case("p1") is not None
    assert session_store.pop_pending_case("p1") is None


def test_same_phone_second_park_replaces_first_documented_behaviour():
    session_store.park_case("p1", _case("old"))
    session_store.park_case("p1", _case("new"))
    assert session_store.pop_pending_case("p1").raw_input_text == "new"


def test_expired_session_is_not_resumed(monkeypatch):
    session_store.park_case("p1", _case("stale"))
    real = session_store.time.time()
    monkeypatch.setattr(session_store.time, "time", lambda: real + session_store.SESSION_TTL_SECONDS + 5)
    assert session_store.pop_pending_case("p1") is None


def test_restart_drops_pending_sessions_documented_limitation():
    session_store.park_case("p1", _case("before restart"))
    importlib.reload(session_store)          # simulates a process restart
    assert session_store.pop_pending_case("p1") is None


def test_concurrent_sessions_keep_their_own_case():
    n = 200
    results = {}

    def worker(i):
        phone = f"p{i}"
        session_store.park_case(phone, _case(f"text-{i}"))
        got = session_store.pop_pending_case(phone)
        results[i] = got.raw_input_text if got else None

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    [t.start() for t in threads]; [t.join() for t in threads]
    assert all(results[i] == f"text-{i}" for i in range(n))
