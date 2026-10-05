# Actual system specification (evidence-bound)

Scope: the system that produced the 2026-09-11 evaluation outputs that Rater 1 reviewed. Every line is backed by a primary artifact (code at `fea51d4`/HEAD, run records, verbatim logs, README). Anything not evidenced is marked **UNSPECIFIED**. Companion: `SYSTEM_PROVENANCE.md` (claim-by-claim), `recovered/EVALUATED_RUN_METADATA.md`.

## Explicit negatives
**NO CLAUDE. NO ANTHROPIC** (0 of 273 logged model calls; no Anthropic key in the environment; README: "every real evaluation run to date used Groq or NVIDIA NIM"). **NO POSTGRESQL. NO DOCKER. NO INDICTRANS2. NO AKSHARAMUKHA** (no import, dependency or file; romanization is a hand-written dictionary, below). **NO LOCAL MODEL INFERENCE** — NVIDIA models were called as *hosted* NVIDIA NIM API endpoints; "NVIDIA locally" is inaccurate. **NOT A DEPLOYMENT**: no WhatsApp/Twilio traffic; input was synthetic text fed to the pipeline function with `data_source=simulated` (doctor-handoff real sends hard-gated off).

## Architecture
A **fixed sequential pipeline** over a typed shared state object (`PatientCase`). **Five agent roles, six invocations**, run in this order by `mira/pipeline.py`:
1. **Intake** — LLM extracts structured fields; **halts the pipeline and returns a clarifying question** if age, sex (male/female/other) or the primary symptom's duration/severity is missing (max 2 clarification rounds; session parked in an in-memory dict keyed by phone, TTL 1 h).
2. **Language (normalize)** — LLM identifies language/script (restricted to en, hi, mr, ta, te, gu, ur) and maps symptoms to a fixed tag vocabulary.
3. **Diagnostic** — LLM proposes a bounded differential from a fixed condition taxonomy, grounded by retrieval; internal only; output rejected (one retry) if it contains diagnosis-claim language (regex blocklist); confidence floor 0.5.
4. **Triage** — (a) 8 hardcoded red-flag rules over the tag vocabulary; **any hit forces EMERGENCY** (`rule_override`); (b) otherwise the LLM urgency is used if confidence ≥ 0.6 (`llm`); (c) low-confidence or malformed output is escalated one band and marked `failsafe_degraded`.
5. **Referral** — facility type chosen by deterministic lookup from the final tier; LLM writes next steps/warning signs/doctor-handoff script; text rejected if it matches a drug-name/dosage pattern.
6. **Language (translate)** — LLM translates the reply (romanized output for hi/te/ur).

No planner, delegator, critic or inter-agent negotiation exists. **"Multi-stage" is the accurate term**; the code and README call the stages "agents".
Failure handling: every external call has bounded retries (code default 2; the current `.env` overrides it, so the value in force during the evaluation is **UNSPECIFIED**); an agent failure degrades to a hardcoded safe fallback (non-ROUTINE tier + fixed "go to your nearest clinic" text). In the evaluation this fired 1/30 (D5).
**Because Intake runs first, a case parked at Intake never reaches the red-flag rules.**

### Romanization (precise)
`mira/language/romanization.py`: script detection by Unicode block; a **62-entry hand-curated dictionary** of romanized Hindi/Telugu symptom terms (e.g. `jwaram → fever`); for Latin/mixed-script text only, words are matched case-insensitively against the dictionary (multi-word phrases first, longest match wins; repeated letters are collapsed for matching), and an English gloss is **inserted inline in brackets** after each recognised term (e.g. `tez bukhar [high fever]`); all other text and punctuation are preserved verbatim. It is not a transliteration or translation model, performs no conversion to native script, and has no learned component.

### Retrieval
Dependency-free **TF-IDF cosine** over locally chunked markdown protocol files (no embeddings). At evaluation time the corpus was **placeholder paraphrase text**, not real IMNCI/NHM/WHO documents (since partly replaced; results predate that).

## Models (from verbatim logs; versions/revisions UNSPECIFIED)
| Provider (hosted API) | Model string | Logged calls (2026-09-11) |
|---|---|---|
| Groq | `openai/gpt-oss-120b` | 165 |
| NVIDIA NIM | `openai/gpt-oss-20b` | 76 |
| NVIDIA NIM | `nvidia/nemotron-3.5-lightning-30b-a3b` | 15 |
| NVIDIA NIM | `deepseek-ai/deepseek-v4-flash-0731` | 14 |
| Google | `gemini-flash-latest` (moving alias) | 3 |
(90 further log entries have no model: failed after retries.) The reported final table mixes these per case (mostly gpt-oss-120b; nemotron for C6 and for Intake-only parks of 9 cases).

## Infrastructure
Hosted inference APIs called from a local macOS workstation via the repo's Python harness (`eval/run_eval.py`). Python 3.14 in a local venv (versions at run time UNSPECIFIED; current: pydantic 2.13, SQLAlchemy 2.0.52, fastapi 0.139).

## Storage and logging
- Cases/consent/outbox: **SQLite** (`sqlite:///mira_consent.db` default); PostgreSQL is a documented *future* option only.
- Audit: append-only **JSONL** (`logs/<date>.jsonl`, one record per agent call: agent, provider, model, tokens, latency, status, error, fallback flags, **structured** input/output snapshot, reasoning; plus `<date>_cases.jsonl` full case snapshots). **Raw prompt text and raw model responses are not stored.**
- Run outputs: `eval/results/<ts>/raw_results.jsonl` + `summary.md`; the "final" table is a best-infrastructure-clean-record-per-case aggregate over 17 runs (`eval/aggregate.py`).

## UNSPECIFIED (cannot be reconstructed)
Executed prompt text per run; provider-side model revisions; temperature/sampling; library versions at run time; runtime retry settings; which commit executed (recorded `f4fc9ef`/`decc25b` are not the executed code; candidate `fea51d4`); any Claude-based, PostgreSQL-based or Dockerised run (none evidenced).
