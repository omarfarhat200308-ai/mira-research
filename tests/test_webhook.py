"""
Tests for mira/webhook.py.

Reply contract (see webhook.py's module docstring for why): every message
that needs real processing (text with content, or a voice note) gets an
IMMEDIATE synchronous "thinking" acknowledgement as the TwiML reply, then
the actual result is delivered separately via a mocked
`_send_whatsapp_message` call (standing in for the real Twilio REST send) —
this is what makes it possible for MIRA's real reply to arrive even when a
full pipeline run exceeds Twilio's webhook response timeout. Only fast,
deterministic paths (unsupported media type, empty message) still reply
synchronously with the real content.
"""
from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from mira import language_preference_store, webhook
from mira.language_poll import LANGUAGE_POLL_MESSAGE, LANGUAGE_POLL_RETRY_MESSAGE
from mira.speech.common import SpeechServiceNotConfigured
from mira.state import DataSource

# All the pre-existing tests below predate the language-preference poll
# (see mira/language_preference_store.py, mira/language_poll.py) and
# exercise pipeline/reply-timing behavior, not the poll itself — they all
# use this one phone number, so it's given a standing "en" preference here
# rather than updating every test to first answer the poll. The poll gate
# itself is tested separately below with a fresh, never-contacted number.
_ESTABLISHED_NUMBER = "whatsapp:+911111111111"


@pytest.fixture(autouse=True)
def _language_prefs():
    language_preference_store.clear_all()
    language_preference_store.set_preference(_ESTABLISHED_NUMBER, "en")
    yield
    language_preference_store.clear_all()


@pytest.fixture
def client():
    return TestClient(webhook.app)


@pytest.fixture
def captured_sends(monkeypatch):
    """Replaces the real Twilio REST send with a list-capturing stub, since
    that's how the real (background-task-delivered) reply is observed in
    tests now — the synchronous HTTP response is just the "thinking" ack."""
    sent = []
    monkeypatch.setattr(
        webhook, "_send_whatsapp_message", lambda to, body: sent.append((to, body))
    )
    return sent


def test_health_endpoint_states_the_workflow_automator_framing(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["framing"] == "Verifiable Workflow Automator"


def test_status_callback_endpoint_exists_and_is_a_noop(client):
    # Exists purely so Twilio's Sandbox "Status callback URL" setting has
    # a valid target — without one, error 21609 blocks EVERY outbound send
    # from the sandbox number, not just delivery-status tracking.
    resp = client.post("/status-callback", data={"MessageStatus": "delivered"})
    assert resp.status_code == 200


def test_text_message_gets_immediate_thinking_ack(client, captured_sends, monkeypatch):
    monkeypatch.setattr(webhook, "run_pipeline", lambda **kwargs: _mock_case(**kwargs))

    resp = client.post("/whatsapp", data={"Body": "mild cold for 2 days", "From": "whatsapp:+911111111111"})
    assert resp.status_code == 200
    assert webhook.THINKING_MESSAGE in resp.text


def test_text_message_real_result_delivered_via_async_send(client, captured_sends, monkeypatch):
    captured = {}

    def fake_run_pipeline(**kwargs):
        captured.update(kwargs)
        return _mock_case(**kwargs, patient_facing_reply="Please rest and monitor symptoms.")

    monkeypatch.setattr(webhook, "run_pipeline", fake_run_pipeline)

    client.post("/whatsapp", data={"Body": "mild cold for 2 days", "From": "whatsapp:+911111111111"})

    assert captured["raw_input_text"] == "mild cold for 2 days"
    assert captured["data_source"] == DataSource.SIMULATED  # default
    assert len(captured_sends) == 1
    to, body = captured_sends[0]
    assert to == "whatsapp:+911111111111"
    assert body == "Please rest and monitor symptoms."


def test_data_source_env_flag_is_threaded_through(client, captured_sends, monkeypatch):
    monkeypatch.setenv("MIRA_DATA_SOURCE", "pilot")
    captured = {}

    def fake_run_pipeline(**kwargs):
        captured.update(kwargs)
        return _mock_case(**kwargs, patient_facing_reply="ok")

    monkeypatch.setattr(webhook, "run_pipeline", fake_run_pipeline)

    client.post("/whatsapp", data={"Body": "test", "From": "whatsapp:+911111111111"})
    assert captured["data_source"] == DataSource.PILOT


def test_clarification_flow_delivers_question_via_async_send(client, captured_sends, monkeypatch):
    def fake_run_pipeline(**kwargs):
        from mira.state import PipelineStatus

        return _mock_case(
            **kwargs,
            pipeline_status=PipelineStatus.AWAITING_CLARIFICATION,
            pending_clarifying_question="How old is the patient?",
        )

    monkeypatch.setattr(webhook, "run_pipeline", fake_run_pipeline)
    parked = {}
    monkeypatch.setattr(webhook.session_store, "park_case", lambda number, case: parked.update({"number": number}))

    client.post("/whatsapp", data={"Body": "baby is sick", "From": "whatsapp:+911111111111"})

    assert parked["number"] == "whatsapp:+911111111111"
    assert len(captured_sends) == 1
    _, body = captured_sends[0]
    assert body == "How old is the patient?"


def test_voice_note_gets_immediate_thinking_ack_then_transcribed_result(client, captured_sends, monkeypatch):
    monkeypatch.setattr("mira.speech.stt.transcribe_voice_note", lambda audio_bytes, **kw: "transcribed: mild fever")
    monkeypatch.setattr(httpx, "Client", _fake_sync_client_ok)
    captured = {}
    monkeypatch.setattr(
        webhook, "run_pipeline",
        lambda **kwargs: (captured.update(kwargs), _mock_case(**kwargs, patient_facing_reply="ok"))[1],
    )

    resp = client.post(
        "/whatsapp",
        data={
            "Body": "", "From": "whatsapp:+911111111111", "NumMedia": "1",
            "MediaUrl0": "https://api.twilio.com/fake-media-url", "MediaContentType0": "audio/ogg",
        },
    )
    assert resp.status_code == 200
    assert webhook.THINKING_MESSAGE in resp.text
    assert captured["raw_input_text"] == "transcribed: mild fever"
    assert len(captured_sends) == 1


def test_voice_note_without_sarvam_configured_replies_gracefully_via_async_send(client, captured_sends, monkeypatch):
    def fake_transcribe(audio_bytes, **kwargs):
        raise SpeechServiceNotConfigured("SARVAM_API_KEY is not set")

    monkeypatch.setattr("mira.speech.stt.transcribe_voice_note", fake_transcribe)
    monkeypatch.setattr(httpx, "Client", _fake_sync_client_ok)

    pipeline_called = {"value": False}

    def fake_run_pipeline(**kwargs):
        pipeline_called["value"] = True
        raise AssertionError("pipeline must not run when voice transcription failed")

    monkeypatch.setattr(webhook, "run_pipeline", fake_run_pipeline)

    resp = client.post(
        "/whatsapp",
        data={
            "Body": "", "From": "whatsapp:+911111111111", "NumMedia": "1",
            "MediaUrl0": "https://api.twilio.com/fake-media-url", "MediaContentType0": "audio/ogg",
        },
    )
    assert resp.status_code == 200
    assert webhook.THINKING_MESSAGE in resp.text
    assert pipeline_called["value"] is False
    assert len(captured_sends) == 1
    _, body = captured_sends[0]
    assert "can't process voice messages" in body


def test_twilio_media_fetch_401_degrades_gracefully_via_async_send(client, captured_sends, monkeypatch):
    """Regression test: Twilio's MediaUrl0 requires Basic Auth to fetch.
    Before this was wired up, a missing/wrong auth produced a raw 401 from
    httpx that wasn't caught, crashing the request with a 500 and leaving
    the ASHA worker with no reply at all (observed live). This must
    degrade to the graceful "can't process voice" async message instead."""

    class _FakeSyncClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, auth=None):
            return httpx.Response(401, content=b"Unauthorized", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "Client", _FakeSyncClient)

    pipeline_called = {"value": False}

    def fake_run_pipeline(**kwargs):
        pipeline_called["value"] = True
        raise AssertionError("pipeline must not run when media fetch failed")

    monkeypatch.setattr(webhook, "run_pipeline", fake_run_pipeline)

    resp = client.post(
        "/whatsapp",
        data={
            "Body": "", "From": "whatsapp:+911111111111", "NumMedia": "1",
            "MediaUrl0": "https://api.twilio.com/fake-media-url", "MediaContentType0": "audio/ogg",
        },
    )
    assert resp.status_code == 200
    assert webhook.THINKING_MESSAGE in resp.text
    assert pipeline_called["value"] is False
    assert len(captured_sends) == 1
    _, body = captured_sends[0]
    assert "can't process voice messages" in body


def test_twilio_media_fetch_uses_api_key_credentials_when_available(monkeypatch):
    monkeypatch.setenv("TWILIO_API_KEY_SID", "SKtestkeysid")
    monkeypatch.setenv("TWILIO_API_KEY_SECRET", "testkeysecret")
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    assert webhook._twilio_media_auth() == ("SKtestkeysid", "testkeysecret")


def test_twilio_media_fetch_falls_back_to_account_sid_auth_token(monkeypatch):
    monkeypatch.delenv("TWILIO_API_KEY_SID", raising=False)
    monkeypatch.delenv("TWILIO_API_KEY_SECRET", raising=False)
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACtestaccountsid")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "testauthtoken")
    assert webhook._twilio_media_auth() == ("ACtestaccountsid", "testauthtoken")


def test_twilio_media_fetch_auth_none_when_unconfigured(monkeypatch):
    monkeypatch.delenv("TWILIO_API_KEY_SID", raising=False)
    monkeypatch.delenv("TWILIO_API_KEY_SECRET", raising=False)
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    assert webhook._twilio_media_auth() is None


def test_send_whatsapp_message_logs_not_crashes_when_unconfigured(monkeypatch, caplog):
    monkeypatch.delenv("TWILIO_API_KEY_SID", raising=False)
    monkeypatch.delenv("TWILIO_API_KEY_SECRET", raising=False)
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("TWILIO_WHATSAPP_FROM", raising=False)

    webhook._send_whatsapp_message("whatsapp:+911111111111", "hello")  # must not raise
    assert "Cannot send async WhatsApp reply" in caplog.text


def test_unsupported_media_type_replies_synchronously_and_gracefully(client, captured_sends, monkeypatch):
    monkeypatch.setattr(
        webhook,
        "run_pipeline",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("pipeline must not run")),
    )
    resp = client.post(
        "/whatsapp",
        data={
            "Body": "", "From": "whatsapp:+911111111111", "NumMedia": "1",
            "MediaUrl0": "https://api.twilio.com/fake-media-url", "MediaContentType0": "image/jpeg",
        },
    )
    assert resp.status_code == 200
    assert "can only process text or voice" in resp.text
    assert captured_sends == []  # synchronous path never touches the async send


def test_empty_text_message_replies_synchronously(client, captured_sends, monkeypatch):
    monkeypatch.setattr(
        webhook,
        "run_pipeline",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("pipeline must not run")),
    )
    resp = client.post("/whatsapp", data={"Body": "   ", "From": "whatsapp:+911111111111"})
    assert resp.status_code == 200
    assert "please send a symptom description" in resp.text
    assert captured_sends == []


def test_first_ever_message_from_a_number_gets_the_language_poll_not_triage(client, captured_sends, monkeypatch):
    monkeypatch.setattr(
        webhook, "run_pipeline",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("pipeline must not run before the poll is answered")),
    )
    resp = client.post(
        "/whatsapp", data={"Body": "28F headache nausea", "From": "whatsapp:+922222222222"}
    )
    assert resp.status_code == 200
    assert resp.text.count(LANGUAGE_POLL_MESSAGE) == 1
    assert captured_sends == []
    assert language_preference_store.is_poll_pending("whatsapp:+922222222222")


def test_valid_poll_choice_is_stored_and_confirmed_without_running_pipeline(client, captured_sends, monkeypatch):
    monkeypatch.setattr(
        webhook, "run_pipeline",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("pipeline must not run on the poll-answer message")),
    )
    number = "whatsapp:+933333333333"
    client.post("/whatsapp", data={"Body": "hi", "From": number})  # triggers the poll

    resp = client.post("/whatsapp", data={"Body": "1", "From": number})
    assert resp.status_code == 200
    assert "Hindi" in resp.text or "hindi" in resp.text.lower()
    assert language_preference_store.get_preference(number) == "hi"
    assert captured_sends == []


def test_invalid_poll_choice_is_reasked(client, captured_sends, monkeypatch):
    monkeypatch.setattr(
        webhook, "run_pipeline",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("pipeline must not run")),
    )
    number = "whatsapp:+944444444444"
    client.post("/whatsapp", data={"Body": "hi", "From": number})  # triggers the poll

    resp = client.post("/whatsapp", data={"Body": "banana", "From": number})
    assert resp.status_code == 200
    assert resp.text.count(LANGUAGE_POLL_RETRY_MESSAGE) == 1
    assert language_preference_store.is_poll_pending(number)


def test_message_after_poll_answered_runs_pipeline_with_preferred_language(client, captured_sends, monkeypatch):
    number = "whatsapp:+955555555555"
    client.post("/whatsapp", data={"Body": "hi", "From": number})
    client.post("/whatsapp", data={"Body": "2", "From": number})  # Telugu

    captured = {}

    def fake_run_pipeline(**kwargs):
        captured.update(kwargs)
        return _mock_case(**kwargs, patient_facing_reply="ok")

    monkeypatch.setattr(webhook, "run_pipeline", fake_run_pipeline)

    resp = client.post("/whatsapp", data={"Body": "28F headache nausea", "From": number})
    assert resp.status_code == 200
    assert webhook.THINKING_MESSAGE in resp.text
    assert captured["preferred_language"] == "te"


def test_pipeline_exceeding_timeout_sends_safety_fallback(client, captured_sends, monkeypatch):
    """PIPELINE_TIMEOUT_SECONDS is set to a fraction of a second here so the
    test doesn't actually wait 3 minutes — a slow (or hung) pipeline must
    trigger the hardcoded refer-manually message rather than leaving the
    ASHA worker with no reply at all."""
    monkeypatch.setattr(webhook, "PIPELINE_TIMEOUT_SECONDS", 0.05)

    release = __import__("threading").Event()

    def slow_run_pipeline(**kwargs):
        release.wait(timeout=2)  # simulates a pipeline run that outlives the timeout
        return _mock_case(**kwargs, patient_facing_reply="finally done")

    monkeypatch.setattr(webhook, "run_pipeline", slow_run_pipeline)

    resp = client.post(
        "/whatsapp", data={"Body": "mild cold for 2 days", "From": _ESTABLISHED_NUMBER}
    )
    assert resp.status_code == 200
    assert webhook.THINKING_MESSAGE in resp.text

    assert len(captured_sends) == 1
    to, body = captured_sends[0]
    assert to == _ESTABLISHED_NUMBER
    assert "refer this case manually" in body

    # Let the late-finishing pipeline's own delivery happen, then confirm
    # it lands as a second, separate message rather than being dropped.
    release.set()
    import time
    for _ in range(50):
        if len(captured_sends) >= 2:
            break
        time.sleep(0.05)
    assert len(captured_sends) == 2
    assert captured_sends[1][1] == "finally done"


def _mock_case(*, raw_input_text, pipeline_status=None, pending_clarifying_question=None,
                patient_facing_reply=None, **_ignored):
    from mira.state import PatientCase, PipelineStatus

    return PatientCase(
        raw_input_text=raw_input_text,
        pipeline_status=pipeline_status or PipelineStatus.OK,
        pending_clarifying_question=pending_clarifying_question,
        patient_facing_reply=patient_facing_reply,
    )


class _fake_sync_client_ok:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, auth=None):
        return httpx.Response(200, content=b"fake-audio-bytes", request=httpx.Request("GET", url))
