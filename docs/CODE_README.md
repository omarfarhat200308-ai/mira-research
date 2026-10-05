> **Status (updated 2026-10-04, v1.3 report): research prototype — NOT clinically validated, NOT deployed, NOT evaluated on real patients; must not be used for clinical decisions.**
> The only evaluation is a 30-case *synthetic* set written by the first author (provisional, author-assigned expected tiers). In the 2026-09-11 run, 17 of 30 cases stopped at the Intake completeness gate and never reached the Triage-stage red-flag layer, and none of those 17 received a safety or referral message. That is a system-level finding, not an accuracy estimate. Results are a retrospective selection of infrastructure-complete attempts and are not fully reproducible. Clinical review was partial and not blind. See the v1.3 report in `paper/` and `THIRD_PARTY_NOTICE.md` (the report is CC BY 4.0; code is MIT; some third-party/provider material is not covered by either). Text below that says Claude Sonnet is "primary" describes the configured default; **every evaluation run used Groq or NVIDIA NIM (plus three Gemini calls), not Claude.**

# MIRA — a Verifiable Workflow Automator for WhatsApp Clinical Triage

**Framing (read this first, non-negotiable):** MIRA is not described as "5
autonomous agents." It is a **Verifiable Workflow Automator** — a fixed,
auditable pipeline of deterministic steps with LLM-assisted reasoning at
specific, bounded checkpoints, where every decision is logged, traceable,
and human-overridable. This framing is deliberate (see `config.SYSTEM_FRAMING`):
"autonomous agents" overstates what this system does and invites safety
scrutiny the system can't yet substantiate; "Verifiable Workflow Automator"
is both more accurate and the framing used in code comments, logs, and any
paper/user-facing text. The internal module layout (`mira/agents/*.py`) is
an implementation detail and unaffected by this — code identifiers didn't
need renaming, only how the system is *described*.

MIRA takes a raw WhatsApp message (text or voice) from a patient/caregiver
in rural India and produces an auditable triage decision (emergency /
urgent / routine) plus a referral to an appropriate facility type. It runs
on FastAPI + Twilio, with each reasoning checkpoint calling Claude Sonnet 5
(primary) with a logged, transparent Groq fallback.

**Clinical scope boundary (read this too):** MIRA is a triage and referral
tool, not a diagnostic one. It never outputs a diagnosis to a patient and
never recommends a drug or dosage. Anywhere the codebase could be mistaken
for making a diagnostic claim is marked with a `DIAGNOSTIC-SCOPE:` comment;
everything patient-facing is marked `TRIAGE-SCOPE:`. See
`mira/agents/diagnostic.py` and `mira/agents/referral.py`.

**Deployment status (updated 2026-09-12):** the originally-planned pilot
with 5 ASHA workers at GMC Nagarkurnool, Telangana is **not proceeding**.
This is now a research/paper evaluation effort, not pre-pilot engineering
— see the note under "Current status vs. what's still required" below for
the full context. It has **not** touched real patient data at any point.

## Architecture

Six stages run in sequence, each reading and writing explicit fields on a
single `PatientCase` state object (`mira/state.py`) — never on implicit
chat history. Every field is attributable to exactly one stage, so a
pipeline run's structured inputs and outputs can be inspected after the fact (executed prompt text and raw model responses are not retained, so a call cannot be fully reconstructed).

```
Romanization-normalize -> Intake -> Language(normalize) -> Diagnostic (RAG-grounded)
    -> Triage (RAG-grounded, rule-engine safety net) -> Referral
    -> Language(translate) -> Doctor handoff (RED/YELLOW only)
```

- **Romanization normalization** (`mira/language/romanization.py`) runs
  before Intake on every new case. Romanized Telugu/Hindi (Latin script,
  e.g. "jwaram vachindi" instead of native script) makes up a large share
  of real Indian WhatsApp usage and, left unhandled, causes measurable
  symptom-classification degradation — **the specific figures previously
  cited here (73-83% / double-digit F1-point degradation) had no traceable
  source and have been removed rather than presented as a verified stat;
  see `mira/language/romanization.py`'s module docstring.** This is a
  practical gloss-normalization layer
  over a curated term dictionary — not a full transliteration model —
  documented honestly as such in the module docstring. It appends an
  English gloss next to recognized terms (e.g. "tez bukhar [high fever]")
  without altering or removing the original text.
- **Intake** (`mira/agents/intake.py`) extracts structured symptom data
  (from the romanization-normalized text when available) and refuses to
  let the pipeline continue if age, sex, or the primary symptom's
  duration/severity is missing — enforced independently of whatever the
  LLM claims it captured. Missing fields trigger a clarifying question; the
  case is parked in `mira/session_store.py` keyed by phone number, and the
  patient's next message resumes the same case. After
  `config.MAX_CLARIFICATION_ROUNDS` unanswered rounds, the pipeline stops
  asking and falls back to the safe referral.
- **Language** (`mira/agents/language.py`) runs twice: once to detect the
  patient's language and map free-text symptoms onto a fixed canonical tag
  vocabulary (`mira/knowledge/symptom_tags.py`), and once at the end to
  translate the final result back into the patient's language. Supported
  languages: English, Hindi, Marathi, Tamil, Telugu, Gujarati
  (`mira/config.py`).
- **Diagnostic** (`mira/agents/diagnostic.py`) — DIAGNOSTIC-SCOPE. Produces
  a bounded differential from a fixed taxonomy
  (`mira/knowledge/conditions.py`) for urgency estimation only, grounded in
  the retrieval-augmented protocol corpus (see "RAG grounding" below), not
  fine-tuned. Never a diagnosis, never patient-facing. Its reasoning text
  is guarded: output asserting a diagnosis is rejected by a blocklist
  (`mira/knowledge/diagnostic_claim_filter.py`) — one retry to rephrase,
  then fail-safe.
- **Triage** (`mira/agents/triage.py`) — the safety-critical stage. Runs a
  hardcoded, non-LLM red-flag rule engine (`mira/safety/red_flags.py`)
  first; if any rule fires, `final_triage = EMERGENCY` regardless of the
  LLM. Otherwise defers to the LLM's own (RAG-grounded) assessment, but
  escalates one urgency band if confidence is below
  `config.TRIAGE_LLM_CONFIDENCE_FLOOR` or output is malformed.
- **Referral** (`mira/agents/referral.py`) — TRIAGE-SCOPE. Outputs a
  facility type (deterministic lookup from `final_triage`, not an LLM
  choice) and next-steps text, passed through
  `mira/knowledge/drug_dosage_filter.py` as a hard backstop against any
  drug-name/dosage pattern.
- **Doctor handoff** (`mira/notifications/doctor_handoff.py`) — on
  EMERGENCY/URGENT only, sends a *second, distinct* outbound WhatsApp
  message (via Twilio's REST API, not the TwiML reply) to the receiving
  facility's on-duty doctor, with continuity-of-care detail (name, age,
  referring ASHA worker, symptoms, classification, MIRA's rationale). Real
  sends require an explicit opt-in flag, real Twilio/doctor-number config,
  AND `data_source == "pilot"` — see "Doctor handoff" below.

## Multi-provider LLM backend: Sonnet-primary, Groq emergency fallback

`mira/llm_client.py` provides `AnthropicLLMClient` (primary, used for
**every** stage including dev/test — never swap to a cheaper model for
testing; a smaller model reasons measurably worse on grounded clinical
inference, and testing on a different model than production means test
results don't validate production behavior) and `GroqLLMClient` (a **true
emergency fallback only**, reached exclusively through `FailoverLLMClient`
when the Anthropic call itself fails). Every failover is logged
(`logging.warning`, never silent) and stamped onto the case
(`PatientCase.model_provenance`, `.fallback_events`) so it's always
auditable which model produced which output. `build_default_client()`
wires this up automatically: mock (default, no key needed) -> Anthropic
alone if no `GROQ_API_KEY` -> Anthropic+Groq-fallback if both keys are set.

**Cost discipline:** the RAG protocol corpus (see below) is sent as a
separate Anthropic prompt-caching-eligible system block
(`BaseAgent.build_cache_prefix`, `cache_control: ephemeral`) instead of
being re-billed at full price on every Diagnostic/Triage call. Every agent
call's token spend (`input_tokens`/`output_tokens`) and provider/model is
recorded in the per-call audit log (`mira/logging_store.py`) so cost
concentration is visible before optimizing anything further.

## RAG grounding (Diagnostic + Triage)

`mira/knowledge/rag.py` provides a dependency-free TF-IDF-cosine retrieval
layer over `mira/knowledge/protocol_corpus/` (three sources: IMNCI, NHM,
WHO CHW). Diagnostic and Triage each retrieve the top-k passages most
relevant to the case's symptom tags, include them in the prompt as labeled
grounding material, and record which source/passage informed the call on
`PatientCase.protocol_references` — every classification is traceable back
to a specific passage, not just "the model decided." This is retrieval, not
fine-tuning, deliberately: fine-tuning would erase that traceability.

**Corpus status — read before citing anything from it:** the three files
in `mira/knowledge/protocol_corpus/` are currently **placeholder stand-ins**
(each file says so in its header), not the real IMNCI/NHM/WHO source
documents — this session had no licensed source text to ingest. The
retrieval *mechanism* is real and tested (`tests/test_rag.py`); the content
it retrieves is not yet authoritative. Swap the `.md` files with real,
properly-attributed source text before any pilot or paper result depends on
retrieval quality — no code change needed to do that.

## Romanization normalization

See `mira/language/romanization.py`'s module docstring for the full
rationale and honest scope statement (a curated-dictionary gloss layer, not
a transliteration model). Tested in `tests/test_romanization.py` and, end
to end through the full pipeline, in `tests/test_pilot_input_distribution.py`.

## Doctor handoff (Stage 5)

`mira/notifications/doctor_handoff.py`. A real send requires **all four**:
`final_triage` in `{EMERGENCY, URGENT}`, `PatientCase.data_source == "pilot"`
(never page a real doctor from simulated/dev/intern traffic),
`MIRA_ENABLE_DOCTOR_HANDOFF_SEND=1`, and real
`TWILIO_ACCOUNT_SID`/`TWILIO_AUTH_TOKEN`/`TWILIO_WHATSAPP_FROM`/
`DOCTOR_WHATSAPP_NUMBER`. A failed send is never silently dropped: it's
queued in `mira/notifications/outbox.py` for retry (a mechanism, not a
scheduler — a periodic job needs to call `outbox.flush_pending()`), and the
ASHA-facing reply gets an appended note that verbal follow-up is needed.

This is a distinct data flow from triage support and needs its own consent
statement — `ConsentScope.DOCTOR_REFERRAL_SHARE`, separate from
`ConsentScope.TRIAGE_SUPPORT` — see Consent/audit below.

## Consent/audit (Stage 6)

`mira/consent/` — a first-class SQLAlchemy table
(`mira/consent/models.py::ConsentRecord`), not an afterthought field.
`patient_ref` is **always** a salted SHA-256 hash
(`mira/consent/store.py::hash_patient_ref`), never a raw identifier — there
is no code path that writes a raw identifier to this table. Defaults to a
local SQLite file (`config.DATABASE_URL`) so it's runnable/testable without
provisioning Postgres; point `DATABASE_URL` at real Postgres for the pilot.
`CONSENT_HASH_SALT`'s dev default deliberately embeds "dev-only-insecure"
in its value — set a real secret before this handles real patient data.

## `simulated` vs `pilot` data

`PatientCase.data_source` (`mira/state.py::DataSource`) is set once, at
case creation, from the `MIRA_DATA_SOURCE` env var read in
`mira/webhook.py` — **never inferred**, and defaults to `simulated` (fails
safe: a misconfigured deploy doesn't accidentally page a doctor or write
pilot-labeled logs). Current testing uses simulated cases run by interns —
this is NOT real-patient data and is not subject to DHS/IEC/DPDP gating.
No real-patient testing has occurred and the pilot is not proceeding; the `pilot` data-source mode would require approvals that have not been obtained, with `MIRA_DATA_SOURCE=pilot` explicitly set.
`logging_store.read_case_records(date, data_source=...)` exists
specifically so results from the two can never be silently blended in
analysis or in the paper.

## Reliability

Every external call (Anthropic, Groq, Sarvam, Twilio REST) goes through
`mira/reliability.py::call_with_retries` — bounded retry with exponential
backoff, never an unbounded hang, never a silent first-try failure.
Outbound WhatsApp/doctor messages that still fail after that budget are
queued in `mira/notifications/outbox.py` rather than assumed delivered
(intermittent field connectivity is assumed, not treated as an edge case).
If **all** reasoning backends fail, the pipeline degrades to the hardcoded
fail-safe referral (see "Fail-safe behavior" below) — which itself is now
also evaluated for doctor handoff, since a fail-safe-degraded URGENT case
is exactly the kind of uncertain case Stage 5 exists for.

## Voice (Sarvam Saaras STT / Bulbul TTS)

`mira/speech/stt.py` and `tts.py` — chosen over generic Whisper/GPT-4o-class
models specifically for Telugu/Hindi/code-mixed accuracy. Both raise
`SpeechServiceNotConfigured` (a subclass of the shared
`mira.speech.common.SpeechServiceError`) immediately, not a silent no-op,
when `SARVAM_API_KEY` is unset — `mira/webhook.py` turns that into an
explicit "voice isn't available right now, please type instead" reply,
never a dropped message. **Not yet verified against a live Sarvam account**
in this environment (no key available) — endpoint shapes are per Sarvam's
public API as last understood; confirm against https://docs.sarvam.ai and
call `tts.confirm_voice_available("te-IN")` before assuming Telugu TTS
works.

## Fail-safe behavior

Any agent failure (exception, timeout, or output that fails schema
validation) is wrapped into `AgentFailure` (`mira/agents/base.py`) and
caught by `mira/pipeline.py`, which degrades the case to a hardcoded
fallback: a non-`ROUTINE` urgency and the literal
`config.FAILSAFE_REFERRAL_TEXT` — never an LLM-generated approximation, and
never a guess.

## Logging

Every agent call — input, output, confidence, reasoning, latency, status,
provider/model, token spend, fallback status, timestamp — is appended to
`logs/YYYY-MM-DD.jsonl` (`mira/logging_store.py`). The full final state of
every case is also persisted to `logs/YYYY-MM-DD_cases.jsonl`. JSONL was
chosen over a database for this phase so it's directly readable/diffable by
the clinical co-advisor without tooling.

## What was deliberately NOT built (per scope)

No voice cloning or ASHA-worker-specific voice personas. No autonomous
action-taking — every RED/YELLOW output requires human (ASHA worker or
receiving clinician) action; the doctor handoff *notifies*, it never
auto-books anything. No fine-tuning on medical content. This is what keeps
the "Verifiable Workflow Automator" framing true rather than aspirational.

## Running

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Tests (deterministic, mocked LLM, no API key, no external services required):
pytest -q

# See the case-by-case agree/disagree table:
pytest tests/test_pipeline_cases.py::test_print_agree_disagree_table -s

# Real Sonnet 5 calls instead of mocks (requires ANTHROPIC_API_KEY):
MIRA_MOCK_LLM=0 pytest -q

# Optional: Groq emergency fallback (requires GROQ_API_KEY, only engages on
# an Anthropic failure — does not change which model normally answers):
GROQ_API_KEY=... MIRA_MOCK_LLM=0 pytest -q

# Webhook (Twilio wiring is intentionally minimal — glue only):
uvicorn mira.webhook:app --reload
```

See `.env.example` for every environment variable this system reads,
grouped by what feature it gates.

## Test harness

`tests/fixtures/cases.py` holds 8 cases run end-to-end through the pipeline
by `tests/test_pipeline_cases.py`: the pre-eclampsia regression case
(**the real hackathon transcript**, recovered 2026-09-12 from
github.com/omarfarhat200308-ai/tabib-v1 — the original TABIB project this
codebase was rebuilt from — replacing a reconstructed placeholder that had
stood in for it), 5 synthetic cases spanning
emergency/urgent/routine, and 2 romanized-Hindi/Telugu cases exercising the
romanization-normalization step end to end. `tests/test_red_flags.py` tests
the rule engine in isolation. `tests/test_failsafe_degradation.py` and
`tests/test_override_not_reasonable_around.py` exercise the two safety
guarantees this system is built around. `tests/test_rag.py`,
`tests/test_llm_fallback.py`, `tests/test_doctor_handoff.py`,
`tests/test_outbox.py`, `tests/test_consent_store.py`,
`tests/test_speech_config_gating.py`, and `tests/test_webhook.py` cover the
newer stages. All are synthetic/mocked — see "Known limitations" below.

## Current status vs. what's still required

**Note (2026-09-12): the ASHA-worker pilot originally planned (5 workers,
GMC Nagarkurnool, Telangana) is not happening.** This project is now a
research/paper evaluation effort, not pre-pilot engineering — items below
about pilot-readiness are historical context for what the architecture was
originally built toward, not an active blocker list.

Real, tested, working: the full 6-stage pipeline, romanization
normalization, RAG retrieval mechanism + audit citations, the
Anthropic/Groq/NVIDIA multi-provider client contract (`mira/llm_client.py`
— Anthropic still untested live, Groq and an NVIDIA NIM fallback both
verified against real API calls, see `eval/`), the consent/audit store,
the doctor-handoff message construction + gating + outbox-retry-on-failure,
the speech-service config-gating fail-loud behavior (Sarvam TTS/STT
verified live 2026-09-12 — see `eval/voice_pipeline_probe.py`, 1.38s mean
round-trip latency on synthesized speech, real ASHA-worker recordings
still needed for a genuine accuracy claim), and the webhook's voice-note
routing.

**Still real gaps, no longer pilot-driven, worth closing for the paper:**
- `ANTHROPIC_API_KEY` — still not present; every real evaluation run to
  date used Groq or NVIDIA NIM as an explicit local-test override, not the
  documented Sonnet-primary configuration.
- The protocol corpus in this release (`mira/knowledge/protocol_corpus/`)
  is author-written placeholder/synthetic protocol material — the
  evaluation-time files. It is not the published IMNCI, NHM, or WHO
  guidance, carries no clinical authority, and implies no WHO/NHM/IMNCI
  validation; the evaluation says nothing about concordance with any
  guideline. Source-derived material is outside this release (see
  `THIRD_PARTY_NOTICE.md`).
- A clinical co-advisor review of every clinical judgment call in this
  codebase (the red-flag rules, the confidence floors, the corpus content)
  — see `docs/clinical_review_export.md`, sent for review, response
  pending. Note (2026-09-19): that document's headline result originally
  overstated that all 8 hardcoded rules fired correctly in the 30-case
  eval; corrected to reflect that 2 of 8 (stroke, GI bleeding) never
  reached the rule engine due to an upstream Intake clarification block —
  see the doc's changelog note and `eval/results/final/raw_results.jsonl`.
- DPDP Act 2023 notice wording (`mira/message_formatting.py::
  DPDP_COMPLIANCE_NOTICE`) — a draft was added 2026-09-19, explicitly
  marked as needing legal review and a real grievance-officer contact
  before pilot/production use; not yet reviewed by counsel.
- Real Twilio production credentials, a real `CONSENT_HASH_SALT`/
  `DATABASE_URL`, and an outbox-flush scheduler remain dev-only/absent —
  no longer urgent without an active pilot, but noted for completeness.

## Known limitations / follow-ups

- If Intake halts for clarification, the clarifying question is not yet
  translated (language detection happens after Intake in this pipeline
  ordering) — documented in `mira/agents/language.py`.
- The clarification session store is in-memory (single-process): a restart
  drops parked cases, and the patient's next message starts a fresh case —
  a safe failure mode. See `mira/session_store.py` for the swap-in point.
- The red-flag rule list (`mira/safety/red_flags.py`) is a v1 set and is
  expected to grow only with clinical co-advisor review.
- The RAG corpus's TF-IDF retrieval is a dependency-free placeholder method
  (no embeddings API key configured) — swap in a real embeddings API by
  replacing `_score` in `mira/knowledge/rag.py`; the retrieval interface and
  `protocol_references` audit shape don't need to change either way.
