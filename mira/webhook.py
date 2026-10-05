"""
Minimal FastAPI + Twilio glue. This is intentionally thin — it exists only
to invoke mira.pipeline.run_pipeline and reply, not to add logic of its
own. `Body` is Twilio's transcribed-or-not text field; when the inbound
message was voice, Twilio delivers `MediaUrl0`/`MediaContentType0` instead
(and an empty/absent `Body`), routed here through Sarvam Saaras STT
(mira/speech/stt.py) rather than assuming it's already been transcribed
upstream.

Reply timing: Twilio expects the synchronous webhook response within a
short window (its own timeout, not something MIRA controls) — a full
pipeline run is 6 sequential LLM calls, each with its own retry/backoff
budget, and can comfortably exceed that window (observed live: Twilio gave
up and delivered nothing to the patient, even though MIRA's HTTP response
eventually arrived and was a valid 200). So the synchronous reply is now
always a fixed, instant acknowledgement; the real work (transcription if
needed, then the pipeline) runs in a FastAPI background task, and the real
result is delivered as a SEPARATE outbound WhatsApp message via Twilio's
REST API — not the TwiML reply. This mirrors the pattern
mira/notifications/doctor_handoff.py already uses for its own outbound
send, just generalized to any recipient here.

data_source (simulated vs pilot — see state.DataSource) is an explicit,
deploy-time environment flag, MIRA_DATA_SOURCE, never inferred from
request content — this is what gates Stage 5's real doctor-handoff sends
(mira/notifications/doctor_handoff.py). Defaults to "simulated" so a
misconfigured deploy fails safe (no real doctor paging) rather than
fails open.
"""
from __future__ import annotations

import concurrent.futures
import logging
import os
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, Form
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse

from . import language_preference_store, session_store
from .language_poll import LANGUAGE_POLL_MESSAGE, LANGUAGE_POLL_RETRY_MESSAGE, confirmation_text, parse_choice
from .pipeline import run_pipeline
from .speech.common import SpeechServiceError
from .state import DataSource, PatientCase, PipelineStatus

app = FastAPI(title="MIRA WhatsApp Triage Webhook")

logger = logging.getLogger("mira.webhook")

THINKING_MESSAGE = "MIRA is reviewing the case now — this takes a little while, please hold on..."

# Safety net on top of the "thinking" ack: that message just buys time for
# a slow-but-eventually-successful pipeline run. If the 6-agent pipeline
# hasn't produced a triage/diagnosis within this window, waiting longer is
# itself the unsafe choice for a patient who may need urgent care — so a
# hardcoded, non-LLM instruction to refer manually goes out instead. This
# is a stopgap, not a replacement: the pipeline keeps running in its own
# thread after the timeout fires, and if it eventually finishes, its real
# result is still delivered as a normal follow-up message (see
# _run_pipeline_with_safety_timeout below).
PIPELINE_TIMEOUT_SECONDS = 180

SAFETY_TIMEOUT_MESSAGE = (
    "MIRA is taking longer than expected to complete this assessment. "
    "As a safety precaution, please do NOT wait any further — refer this "
    "case manually or contact the nearest doctor/health facility now. "
    "MIRA will still send its assessment separately if it completes."
)


def _configured_data_source() -> DataSource:
    raw = os.environ.get("MIRA_DATA_SOURCE", "simulated").strip().lower()
    try:
        return DataSource(raw)
    except ValueError:
        # Fail safe on a typo/misconfiguration, never fail open into pilot.
        return DataSource.SIMULATED


def _twilio_media_auth() -> tuple[str, str] | None:
    """Twilio's MediaUrl0 is NOT publicly fetchable — it requires the same
    Basic Auth as any other Twilio REST call. Prefers an API Key SID/Secret
    pair (TWILIO_API_KEY_SID/SECRET) since that's what's actually
    provisioned here; falls back to Account SID/Auth Token if that's what's
    set instead. Twilio accepts either pair as Basic Auth credentials.
    Returns None (caller then gets an auth failure, not a silent wrong
    fetch) if neither pair is configured."""
    api_key_sid = os.environ.get("TWILIO_API_KEY_SID")
    api_key_secret = os.environ.get("TWILIO_API_KEY_SECRET")
    if api_key_sid and api_key_secret:
        return (api_key_sid, api_key_secret)
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    if account_sid and auth_token:
        return (account_sid, auth_token)
    return None


def _build_twilio_rest_client():
    """Same credential resolution as _twilio_media_auth, but constructs an
    actual REST client (twilio.rest.Client) for sending the real,
    asynchronous outbound reply. Returns None if nothing is configured —
    callers must handle that (log loudly, never crash the background
    task silently)."""
    from twilio.rest import Client

    api_key_sid = os.environ.get("TWILIO_API_KEY_SID")
    api_key_secret = os.environ.get("TWILIO_API_KEY_SECRET")
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")

    if api_key_sid and api_key_secret and account_sid:
        return Client(api_key_sid, api_key_secret, account_sid)
    if account_sid and auth_token:
        return Client(account_sid, auth_token)
    return None


def _send_whatsapp_message(to_number: str, body: str) -> None:
    """Delivers the REAL result as a new outbound message (not a TwiML
    reply — the synchronous webhook response is already spent on the
    "thinking" acknowledgement by the time this runs). Never raises: a
    delivery failure here is logged, not thrown into the background-task
    machinery where nothing would surface it."""
    client = _build_twilio_rest_client()
    from_number = os.environ.get("TWILIO_WHATSAPP_FROM")
    if client is None or not from_number:
        logger.error(
            "Cannot send async WhatsApp reply to %s — Twilio REST credentials "
            "or TWILIO_WHATSAPP_FROM not configured. Reply was: %r",
            to_number, body,
        )
        return

    from_whatsapp = from_number if from_number.startswith("whatsapp:") else f"whatsapp:{from_number}"
    try:
        client.messages.create(from_=from_whatsapp, to=to_number, body=body)
    except Exception:
        logger.exception("Failed to send async WhatsApp reply to %s", to_number)


def _run_pipeline_with_safety_timeout(
    *,
    raw_input_text: str,
    source_phone_number: str,
    resume_case: Optional[PatientCase],
    data_source: DataSource,
    preferred_language: Optional[str],
) -> Optional[PatientCase]:
    """Runs run_pipeline on its own worker thread so a slow pipeline can be
    abandoned-from-the-caller's-perspective at PIPELINE_TIMEOUT_SECONDS
    without killing the underlying call — deliberately NOT using
    `with ThreadPoolExecutor() as executor:`, since that context manager's
    __exit__ blocks until the submitted call finishes, which would defeat
    the timeout entirely. Returns None (having already sent the safety
    fallback message itself) on timeout; the pipeline thread is left
    running and will still deliver its real result via the normal
    _process_and_reply path whenever it finishes."""
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(
        run_pipeline,
        raw_input_text=raw_input_text,
        source_phone_number=source_phone_number,
        resume_case=resume_case,
        data_source=data_source,
        preferred_language=preferred_language,
    )
    try:
        return future.result(timeout=PIPELINE_TIMEOUT_SECONDS)
    except concurrent.futures.TimeoutError:
        logger.warning(
            "Pipeline exceeded %ss for %s — sending safety fallback and "
            "letting it finish in the background.",
            PIPELINE_TIMEOUT_SECONDS, source_phone_number,
        )
        _send_whatsapp_message(source_phone_number, SAFETY_TIMEOUT_MESSAGE)

        def _deliver_late_result(done_future: concurrent.futures.Future) -> None:
            try:
                case = done_future.result()
            except Exception:
                logger.exception(
                    "Pipeline failed after already timing out for %s", source_phone_number
                )
                return
            if case.pipeline_status == PipelineStatus.AWAITING_CLARIFICATION:
                session_store.park_case(source_phone_number, case)
                reply_text = case.pending_clarifying_question or "Could you share a few more details?"
            else:
                reply_text = case.patient_facing_reply or case.next_steps or (
                    "MIRA could not complete the assessment. Please go to your "
                    "nearest clinic or health facility so a health worker can "
                    "examine the patient in person."
                )
            _send_whatsapp_message(source_phone_number, reply_text)

        future.add_done_callback(_deliver_late_result)
        return None
    finally:
        executor.shutdown(wait=False)


def _process_and_reply(
    *,
    message_text: str,
    is_audio: bool,
    media_url: Optional[str],
    source_phone_number: str,
    resume_case: Optional[PatientCase],
    data_source: DataSource,
    preferred_language: Optional[str],
) -> None:
    """The actual slow work (transcription + the 6-agent pipeline),
    run as a FastAPI background task — i.e. after the synchronous
    "thinking" TwiML reply has already been sent. Sync function
    deliberately: run_pipeline and the Sarvam/Twilio clients are all
    synchronous (httpx.Client, not AsyncClient), and FastAPI runs a sync
    background task in a threadpool automatically, so this never blocks
    the event loop or other requests."""
    if is_audio:
        from .speech.stt import transcribe_voice_note
        import httpx

        try:
            with httpx.Client(timeout=20.0) as http_client:
                media_resp = http_client.get(media_url, auth=_twilio_media_auth())
                media_resp.raise_for_status()
            message_text = transcribe_voice_note(media_resp.content)
        except (SpeechServiceError, httpx.HTTPError) as exc:
            _send_whatsapp_message(
                source_phone_number,
                "MIRA can't process voice messages right now — please "
                "type your message as text instead. (Voice transcription "
                f"is not currently available: {exc})",
            )
            return

    case = _run_pipeline_with_safety_timeout(
        raw_input_text=message_text,
        source_phone_number=source_phone_number,
        resume_case=resume_case,
        data_source=data_source,
        preferred_language=preferred_language,
    )
    if case is None:
        # Timed out — the safety message has already been sent by
        # _run_pipeline_with_safety_timeout; nothing left to reply here.
        return

    if case.pipeline_status == PipelineStatus.AWAITING_CLARIFICATION:
        session_store.park_case(source_phone_number, case)
        reply_text = case.pending_clarifying_question or "Could you share a few more details?"
    else:
        reply_text = case.patient_facing_reply or case.next_steps or (
            "MIRA could not complete the assessment. Please go to your "
            "nearest clinic or health facility so a health worker can "
            "examine the patient in person."
        )

    _send_whatsapp_message(source_phone_number, reply_text)


@app.post("/whatsapp")
async def whatsapp_webhook(
    background_tasks: BackgroundTasks,
    Body: str = Form(""),
    From: str = Form(...),
    NumMedia: str = Form("0"),
    MediaUrl0: str = Form(None),
    MediaContentType0: str = Form(None),
):
    message_text = Body.strip()

    # One-time language poll gate — runs before anything else, even before
    # media validation, so a number's very first-ever contact (text OR
    # voice) always gets the numbered menu first. See
    # mira/language_preference_store.py and mira/language_poll.py.
    if not language_preference_store.has_been_contacted(From):
        language_preference_store.mark_poll_pending(From)
        reply = MessagingResponse()
        reply.message(LANGUAGE_POLL_MESSAGE)
        return Response(content=str(reply), media_type="application/xml")

    if language_preference_store.is_poll_pending(From):
        choice = parse_choice(message_text)
        reply = MessagingResponse()
        if choice is None:
            reply.message(LANGUAGE_POLL_RETRY_MESSAGE)
        else:
            language_preference_store.set_preference(From, choice)
            reply.message(confirmation_text(choice))
        return Response(content=str(reply), media_type="application/xml")

    preferred_language = language_preference_store.get_preference(From)

    has_media = int(NumMedia or "0") > 0 and bool(MediaUrl0)
    is_audio = has_media and bool(MediaContentType0) and MediaContentType0.startswith("audio/")

    if has_media and not is_audio:
        # Unsupported media type — fast, deterministic, no LLM/STT call
        # involved, so this can just reply synchronously; no need for the
        # "thinking" + background-task path.
        reply = MessagingResponse()
        reply.message(
            "MIRA can only process text or voice messages right now — "
            "please send your message as text or a voice note."
        )
        return Response(content=str(reply), media_type="application/xml")

    if not message_text and not is_audio:
        reply = MessagingResponse()
        reply.message("MIRA: please send a symptom description to receive a triage classification.")
        return Response(content=str(reply), media_type="application/xml")

    # Everything from here involves slow work (transcription and/or the
    # 6-agent pipeline) that can exceed Twilio's webhook response timeout.
    # Pop any parked clarification case now (fast, in-memory) so the
    # background task has it, then acknowledge immediately and do the real
    # work after the response is sent.
    pending = session_store.pop_pending_case(From)
    background_tasks.add_task(
        _process_and_reply,
        message_text=message_text,
        is_audio=is_audio,
        media_url=MediaUrl0 if is_audio else None,
        source_phone_number=From,
        resume_case=pending,
        data_source=_configured_data_source(),
        preferred_language=preferred_language,
    )

    reply = MessagingResponse()
    reply.message(THINKING_MESSAGE)
    return Response(content=str(reply), media_type="application/xml")


@app.get("/health")
async def health():
    return {"status": "ok", "framing": "Verifiable Workflow Automator"}


@app.post("/status-callback")
async def status_callback():
    """Twilio's WhatsApp Sandbox requires its own configured
    "Status callback URL" to be a valid, reachable URL — an unset/invalid
    one makes EVERY outbound send from the sandbox number fail with error
    21609 ("StatusCallback URL none is not a valid URL"), even sends that
    have nothing to do with delivery-status tracking. This endpoint exists
    purely to be a syntactically valid target for that Sandbox setting;
    MIRA doesn't currently act on delivery-status callbacks, so this is a
    deliberate no-op, not an oversight."""
    return {"status": "ok"}
