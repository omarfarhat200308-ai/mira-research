"""
Central configuration. Every tunable safety threshold lives here, named and
commented, rather than as a magic number buried in an agent — this file is
the first thing a clinical reviewer should read to understand what's
adjustable and what isn't (the red-flag rule list is deliberately NOT here;
see mira/safety/red_flags.py).
"""
import os

from dotenv import load_dotenv

# Loaded here, at the top of the module every other module in mira/ pulls
# config from, so a plain `uvicorn mira.webhook:app` (no shell that has
# separately sourced .env) still picks up real credentials instead of
# silently defaulting to MockLLMClient below — that silent-mock failure
# mode happened live (server restarted from a shell that hadn't exported
# .env, every case degraded instantly with no real triage, no error
# visible to the ASHA worker). override=False: real environment variables
# (e.g. from a deploy platform) still win over .env.
load_dotenv(override=False)

# Framing (non-negotiable, per prior research audit): MIRA is described as a
# "Verifiable Workflow Automator" — a fixed, auditable pipeline of
# deterministic steps with LLM-assisted reasoning at specific checkpoints,
# every decision logged/traceable/human-overridable — never as "autonomous
# agents." Use this string wherever the system is described in user-facing
# text, docs, or the paper; internal module/class names (mira/agents/*) are
# an implementation detail and are unaffected.
SYSTEM_FRAMING = "Verifiable Workflow Automator"

# Model used for all real (non-mocked) agent calls. Sonnet stays primary for
# every stage, including pipeline/dev/intern testing — do not default to the
# Groq fallback model for testing just to save cost; a smaller model reasons
# measurably worse on grounded multi-step clinical inference, and testing on
# a different model than production means test results don't validate
# production behavior. Manage cost via prompt caching (see llm_client.py's
# cache_prefix support) and tight prompts, not model downgrade.
CLAUDE_MODEL = "claude-sonnet-5"

# If true (default), agents use MockLLMClient — deterministic, free, no API
# key required. Set MIRA_MOCK_LLM=0 to hit the real Anthropic API.
MOCK_LLM = os.environ.get("MIRA_MOCK_LLM", "1") != "0"

# Groq is a true emergency fallback ONLY — activated by llm_client.py's
# FailoverLLMClient when the Anthropic call itself fails (network error,
# timeout, API exhaustion), never chosen proactively for cost reasons. Every
# fallback trigger is logged explicitly (AgentLogEntry.fallback_used/
# fallback_reason) so it's auditable which model produced which output —
# see mira/llm_client.py.
#
# llama-3.3-70b-versatile (this default's previous value) has been removed
# from Groq's lineup entirely (404 model_not_found, confirmed live
# 2026-08-18) — openai/gpt-oss-120b verified working with forced
# function-calling against a real key on that date. Groq's free-tier
# lineup moves fast; re-verify against https://api.groq.com/openai/v1/models
# if this starts 404ing again.
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

# NVIDIA NIM (build.nvidia.com) — added 2026-09-11 as a third local-test
# override (see llm_client.py:build_default_client) after both groq (hard
# 8000 TPM account-wide cap) and gemini (frequent 503s/timeouts) proved
# unreliable for a real multi-call pipeline run. deepseek-ai/deepseek-v4-
# flash-0731 verified live: ~2-6s/call, correctly returns tool_calls with
# tool_choice="required" (NOT the named {"type":"function","function":
# {"name":...}} form used for Anthropic/Groq -- that form hangs/times out
# against this model on NIM, confirmed live 2026-09-11 up to 60s). The
# sibling deepseek-ai/deepseek-v4-pro-0813 model carries an NVIDIA
# deprecation header dated 2026-09-14 -- avoid it for anything meant to
# outlive that date.
NVIDIA_MODEL = os.environ.get("NVIDIA_MODEL", "deepseek-ai/deepseek-v4-flash-0731")

# Sarvam AI Saaras (STT) / Bulbul (TTS) — chosen specifically for Telugu +
# Hindi + code-mixed speech accuracy over generic Whisper/GPT-4o-class
# models. mira/speech/stt.py and tts.py raise SpeechServiceNotConfigured
# (not a silent no-op) when SARVAM_API_KEY is unset.

# Doctor handoff (Stage 5): a second, distinct outbound WhatsApp message via
# Twilio's REST API (not the TwiML reply used for the ASHA-facing response),
# sent only on RED/YELLOW (EMERGENCY/URGENT) triage. Off by default — real
# sends require both real credentials AND this flag AND
# PatientCase.data_source == "pilot" (never auto-page a doctor from
# simulated/dev traffic). See mira/notifications/doctor_handoff.py.
ENABLE_DOCTOR_HANDOFF_SEND = os.environ.get("MIRA_ENABLE_DOCTOR_HANDOFF_SEND", "0") == "1"
DOCTOR_WHATSAPP_NUMBER = os.environ.get("DOCTOR_WHATSAPP_NUMBER")
TWILIO_WHATSAPP_FROM = os.environ.get("TWILIO_WHATSAPP_FROM")

# Consent/audit store (Stage 6). Defaults to a local SQLite file so the
# schema and code path are runnable/testable without provisioning Postgres;
# point DATABASE_URL at a real Postgres instance for the pilot. Never store
# raw patient identifiers here — mira/consent/store.py hashes patient_ref
# before it reaches this table, using CONSENT_HASH_SALT.
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///mira_consent.db")
CONSENT_HASH_SALT = os.environ.get("CONSENT_HASH_SALT", "dev-only-insecure-salt-change-before-pilot")

# Bounded retry/backoff applied to every external call (Anthropic, Groq,
# Sarvam, Twilio REST) — see mira/reliability.py. An external call that
# hangs or errors transiently should not surface as a hard failure on the
# first try, but must still fail (never hang) past this budget.
EXTERNAL_CALL_MAX_RETRIES = int(os.environ.get("MIRA_EXTERNAL_CALL_MAX_RETRIES", "2"))
EXTERNAL_CALL_TIMEOUT_SECONDS = float(os.environ.get("MIRA_EXTERNAL_CALL_TIMEOUT_SECONDS", "20"))

# Below this confidence, the Triage agent does not trust the LLM's own
# urgency call and escalates one band instead (see agents/triage.py).
# Chosen conservatively: an LLM that isn't confident should not be the
# reason a patient is told "routine."
TRIAGE_LLM_CONFIDENCE_FLOOR = 0.6

# Same idea for the Diagnostic agent's differential — low-confidence
# differentials still flow to Triage (Triage doesn't require diagnostic
# certainty), but are flagged in the audit log.
DIAGNOSTIC_LLM_CONFIDENCE_FLOOR = 0.5

# Maximum clarification round-trips Intake may ask for before the pipeline
# stops waiting and falls back to the safe referral instead. Prevents an
# endless question loop with a patient who can't provide the missing
# fields — after this many rounds, "go to the nearest clinic" beats
# continuing to block on incomplete data.
MAX_CLARIFICATION_ROUNDS = 2

# Per-agent call timeout (seconds). An agent that hangs is treated the same
# as one that errors — see agents/base.py.
AGENT_CALL_TIMEOUT_SECONDS = 20

# Languages the Language agent must support end-to-end (detect on input,
# translate on output). English is the pipeline's internal working language.
# "ur" (Urdu) added for the GMC Nagarkurnool/Telangana pilot region.
SUPPORTED_LANGUAGES = ["en", "hi", "mr", "ta", "te", "gu", "ur"]
LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "mr": "Marathi",
    "ta": "Tamil",
    "te": "Telugu",
    "gu": "Gujarati",
    "ur": "Urdu",
}

# For these specific languages, patient/ASHA-worker-facing text (clarifying
# questions, translated triage results) must be written in ROMANIZED
# (Latin-script) form, not native script — confirmed with the clinical
# co-advisor/product owner: ASHA workers in this deployment read and type
# romanized text day-to-day, not native script, even though they speak
# these languages fluently. Scoped to exactly these three (not all of
# SUPPORTED_LANGUAGES) because they're what's relevant to this pilot's
# actual deployment region; Marathi/Tamil/Gujarati are left to the model's
# own judgment unless told otherwise.
ROMANIZE_LANGUAGES = {"hi", "te", "ur"}

# Hardcoded fallback text used whenever the pipeline degrades (any agent
# fails or returns malformed output). This is literal text, not
# LLM-generated — see agents/base.py AgentFailure handling and
# pipeline.py.
FAILSAFE_REFERRAL_TEXT = (
    "We were not able to complete a full assessment. To be safe, please "
    "go to your nearest clinic or health facility as soon as possible so "
    "a health worker can examine the patient in person."
)

LOG_DIR = os.environ.get("MIRA_LOG_DIR", "logs")


# Interim messages attached when Intake halts for clarification (see
# pipeline.py). Added in v2 after the v1.3 finding that halted cases got no
# safety message at all. English fallback text; the Language-translate stage
# is NOT run on halted cases, so these are intentionally short and plain.
INTERIM_SAFETY_TEXT = (
    "We need one more detail to finish assessing this. Meanwhile, if the "
    "patient has trouble breathing, chest pain, fits, is unconscious, is "
    "bleeding heavily, or is getting worse, go to the nearest health "
    "facility immediately."
)
INTERIM_EMERGENCY_TEXT = (
    "EMERGENCY: what you describe may be life-threatening. Take the "
    "patient to the nearest hospital or call 108 now. Do not wait for "
    "further questions."
)
