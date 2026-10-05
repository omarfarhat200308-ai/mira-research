# Evaluated run metadata

Rule used: a field is **VERIFIED** only if a file on this machine states or directly proves it. Anything else is **UNVERIFIED**. Nothing is inferred.

See also `../SYSTEM_PROVENANCE.md` (authoritative provenance table).

Scope: the recoverable run is the 2026-09-11 30-case harness run (`eval/results/*`, `eval/results/final`, verbatim logs in `logs/2026-09-11*.jsonl`, preserved under `raw/`). The paper (`MIRA_v1_interim_report.pdf`) describes a system that differs from it; see the bottom section.

## A. The Sep-11 harness run (recovered)

| Field | Status | Value / evidence |
|---|---|---|
| 5-agent source exists in git | VERIFIED | Agents `intake, language, diagnostic, triage, referral` present since commit `661b2ab` (2026-07-04); `mira/pipeline.py` runs 6 invocations (Intake, Language-normalize, Diagnostic, Triage, Referral, Language-translate). |
| Commit SHA recorded in run summaries | VERIFIED (as recorded) | `f4fc9ef` (most runs) and `decc25b` (runs `T194652Z`, `T195113Z`). `run_eval._git_commit()` records `git rev-parse HEAD` only. |
| Recorded SHA equals the code that actually ran | **UNVERIFIED — and contradicted** | Working tree was dirty. `fea51d4` (committed 2026-09-12 00:53 IST, after the last run) is the first commit containing the NVIDIA client, `run_eval.py`, `aggregate.py`, `cases_30.py`; the final aggregate used NVIDIA calls. `f4fc9ef` contains none of these. |
| Best candidate committed snapshot | UNVERIFIED | `fea51d4` for `mira/` + `eval/`. Not provable: `intake.py` was modified at 2026-09-11 18:26 IST (12:56 UTC) between the early and later runs; `cases_30.py` last modified 22:10 IST (16:40 UTC), i.e. after runs up to `T145921Z` and before `T174539Z` onward (see note 1). Case text therefore differed between early and late runs. |
| Evaluation date | VERIFIED | Agent-call timestamps 2026-09-11T12:31:59Z – 2026-09-11T20:20:04Z; `final` records span 12:32Z – 19:19Z. |
| Case ordering | VERIFIED | `eval/cases_30.py` `CASES` order (A1..G2). Per-run order recorded in each `raw_results.jsonl`. |
| Models used (final aggregate) | VERIFIED | Mixed per case, from `logs/2026-09-11.jsonl`: Groq `openai/gpt-oss-120b` (all agents, 11 cases), NVIDIA `nvidia/nemotron-3.5-lightning-30b-a3b` (all agents for C6; Intake only for 9 parked cases), Groq `gpt-oss-120b` Intake only (8 parked cases); 1 case has empty provenance. Across all runs the logs also show `openai/gpt-oss-20b`, `deepseek-ai/deepseek-v4-flash-0731`, `gemini-flash-latest`. |
| Anthropic/Claude used | **VERIFIED NOT USED** | 0 calls with provider `anthropic` in `logs/2026-09-11.jsonl` (groq 165, nvidia 105, gemini 3). `eval/README.md` also states no Anthropic key was configured. |
| Exact model *versions* / API revisions | UNVERIFIED | Only the model strings above are logged; no provider-side version/fingerprint. `gemini-flash-latest` is a moving alias. |
| Prompt text / prompt version | UNVERIFIED | Prompts live in `mira/agents/*.py` and changed over the day (intake prompt edit confirmed in `fea51d4` diff). The prompt as executed per run is not stored; only `input_snapshot`/`output_snapshot` per call. |
| API configuration | PARTIAL | `max_tokens` 1024/2048 in `llm_client.py` (current file); retries `MIRA_EXTERNAL_CALL_MAX_RETRIES` default 2. Temperature not set in code. Values at run time UNVERIFIED (`.env` mtime 2026-09-12 23:28, after the run). |
| Dependency versions | UNVERIFIED (current only) | Current `.venv`: Python 3.14.6, anthropic 0.116.0, fastapi 0.139.0, pydantic 2.13.4, SQLAlchemy 2.0.52, httpx 0.28.1, twilio 9.10.9. No lockfile; `pyproject.toml` uses lower bounds only. |
| Runtime / host | UNVERIFIED | Local Mac; no host record in artifacts. |
| Retry / fallback behaviour | VERIFIED (design), run-level VERIFIED via logs | `fallback_used`/`fallback_reason` fields in each agent log; `final/summary.md`: fallback triggered 0/30, degraded 1/30. |
| Per-case outputs | VERIFIED | `mira_outputs_recovered.csv`; joined 30/30 by `case_id` to verbatim agent logs. |
| Selection method of the `final` table | VERIFIED | `eval/aggregate.py`: per case, best clean record across runs; excludes infra-degraded records and records whose stored text differs from current `cases_30.py`. This is best-of-many selection across runs and models, not a single run. |
| Single coherent run | **VERIFIED NO** | `final` mixes at least 8 runs, 2 providers, 3 models; 2 of 30 records (D1, G1) ran before the 12:56 UTC intake-prompt edit, 28 after. |
| Outputs reviewed by Rater 1 = this run | VERIFIED | 29/29 non-B2 MIRA cells in the recovered Rater-1 workbook equal the `final` aggregate (B2 cell blank in the xlsx, parked in the repo CSV). |
| Run stability | VERIFIED | Three complete 30-case runs gave 11, 12, 10 "matches" with 11, 21, 12 degraded cases respectively; infra failures (rate limits) dominated. |

Note 1: run IDs are UTC; file mtimes are local (IST, UTC+5:30). `intake.py` mtime 18:26 IST = 12:56 UTC.

## B. What the paper claims vs. what is verified

| Paper statement | Status |
|---|---|
| "five-node pipeline (Intake→Language→Diagnostic→Triage→Referral)" | PARTIAL — 5 roles; 6 invocations (Language runs twice). |
| Claude (Anthropic API) | NOT VERIFIED — code supports it (`AnthropicLLMClient`, `claude-sonnet-5`) but no recovered run used it. |
| PostgreSQL case storage and audit logs | NOT VERIFIED — default is SQLite (`mira_consent.db`) and flat JSONL logs; no Postgres data for MIRA exists on this machine. |
| Docker / docker-compose | NOT VERIFIED — no Dockerfile or compose file in the repo; no MIRA container or volume exists. |
| IndicTrans2 and Aksharamukha | NOT VERIFIED — zero references in code, `pyproject.toml`, or README; not installed in `.venv`. |
| Twilio webhook | PARTIAL — webhook code exists (`mira/webhook.py`); eval ran with `DataSource.SIMULATED`, not live WhatsApp. |
| "I ran every case through the deployed MIRA pipeline" | NOT VERIFIED — recovered run is a local harness, not a deployment. |
| B2 "not yet executed" | CONTRADICTED by run files (see `../B2_C1_AND_CASE_ID_AUDIT.md`). |
| 14/29, 11/29 | Reproducible only via an internally inconsistent partition (see DENOMINATOR_RECONCILIATION.md). |
| Single rater, rater saw MIRA output | PARTLY VERIFIED — a partially filled Rater-1 workbook was recovered (`raters/`); it displays MIRA output beside each case (non-blind). Rater identity UNVERIFIED; 4 rows blank. Rater 2: only blank forms. |
| Three-node TABIB hackathon prototype | PARTIAL — `~/Projects/tabib-v1` contains intake/diagnostic/triage agents plus a Band coordinator and WhatsApp bridge; its own commit message says "4-agent". |
