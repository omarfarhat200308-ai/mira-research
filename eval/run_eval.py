"""
Runs the 30-case paper evaluation bank (eval/cases_30.py) through the real
MIRA pipeline (mira.pipeline.run_pipeline), using whatever LLM client
mira.llm_client.build_default_client() resolves to from the current
environment (see .env -- as of this writing that's MIRA_LLM_PROVIDER=groq,
NOT the documented Sonnet-primary path; see eval/README.md for why that
matters for the paper).

Every case runs with data_source=DataSource.SIMULATED, which is also what
gates mira/notifications/doctor_handoff.py's real-send path closed --
this run cannot send a real WhatsApp message to a doctor no matter what
triage outcome comes back.

Usage:
    python -m eval.run_eval                 # all 30 cases
    python -m eval.run_eval --limit 3        # smoke-test the harness on the first 3
    python -m eval.run_eval --keys a1_chest_pain_dyspnea a5_seizure

Output (per run, one timestamped subdirectory under eval/results/):
    raw_results.jsonl   -- one line per case: the full PatientCase dump,
                            our expected labels, whether it matched, and
                            wall-clock latency for the whole pipeline call.
    summary.md          -- aggregate accuracy / confusion matrix / rule-
                            trigger correctness / fallback rate / latency,
                            plus the paper caveats, ready to paste into a
                            methodology or limitations section.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from statistics import mean, median
from typing import Optional

from mira import config
from mira.llm_client import LLMClient, LLMCompletion, build_default_client
from mira.pipeline import run_pipeline
from mira.state import DataSource, PipelineStatus

from eval.cases_30 import CASES, EvalCase

RESULTS_ROOT = os.path.join(os.path.dirname(__file__), "results")


class PacedLLMClient:
    """Wraps a real LLMClient and sleeps `min_interval_s` since the last
    call before making the next one. Added after the first full 30-case
    run showed the configured Groq key/tier returning 429s on nearly every
    call -- reliability.py's per-call exponential backoff (0.5/1/2/4s, 5
    attempts) absorbs isolated blips fine, but a pipeline run makes 4-5
    sequential calls close together and routinely exhausted that budget,
    landing cases on the hardcoded fail-safe degradation path
    (triage_decided_by=failsafe_degraded) instead of a real model
    judgment -- 11/30 cases in that first run, which makes the accuracy
    number from it meaningless. This is eval-only pacing (not a change to
    mira/reliability.py's production retry policy), applied ACROSS calls
    rather than within one call's retry loop."""

    def __init__(self, inner: LLMClient, min_interval_s: float = 4.0):
        self._inner = inner
        self._min_interval_s = min_interval_s
        self._last_call_at: float = 0.0

    def complete(self, **kwargs) -> LLMCompletion:
        elapsed = time.monotonic() - self._last_call_at
        if elapsed < self._min_interval_s:
            time.sleep(self._min_interval_s - elapsed)
        try:
            return self._inner.complete(**kwargs)
        finally:
            self._last_call_at = time.monotonic()


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=os.path.dirname(__file__)
        ).decode().strip()
    except Exception:
        return "unknown"


def _run_case(case: EvalCase, llm_client: Optional[LLMClient] = None) -> dict:
    start = time.monotonic()
    result = run_pipeline(
        raw_input_text=case.raw_input_text,
        source_phone_number=f"eval:{case.key}",
        asha_worker_id="paper-eval",
        data_source=DataSource.SIMULATED,
        llm_client=llm_client,
    )
    latency_s = time.monotonic() - start

    actual_triage = result.final_triage.value if result.final_triage else None
    expected_triage = case.expected_final_triage.value if case.expected_final_triage else None
    actual_decided_by = result.triage_decided_by.value if result.triage_decided_by else None
    expected_decided_by = case.expected_decided_by.value if case.expected_decided_by else None

    if case.expected_final_triage is None:
        # Group F clarification cases are scored on pipeline_status instead.
        triage_match = result.pipeline_status == PipelineStatus.AWAITING_CLARIFICATION
    else:
        triage_match = actual_triage == expected_triage

    rule_match = (
        actual_decided_by == expected_decided_by if expected_decided_by is not None else None
    )
    rule_id_match = (
        case.expected_rule_id in (result.red_flags_triggered or [])
        if case.expected_rule_id
        else None
    )

    return {
        "key": case.key,
        "label": case.label,
        "group": case.group,
        "source_protocol": case.source_protocol,
        "expected_final_triage": expected_triage,
        "actual_final_triage": actual_triage,
        "triage_match": triage_match,
        "expected_decided_by": expected_decided_by,
        "actual_decided_by": actual_decided_by,
        "rule_match": rule_match,
        "expected_rule_id": case.expected_rule_id,
        "red_flags_triggered": result.red_flags_triggered,
        "rule_id_match": rule_id_match,
        "pipeline_status": result.pipeline_status.value if result.pipeline_status else None,
        "intake_status": result.intake_status.value if result.intake_status else None,
        "failed_agent": result.failed_agent,
        "detected_language": result.detected_language,
        "detected_script": result.detected_script,
        "romanized_terms_glossed": result.romanized_terms_glossed,
        "protocol_references": [pr.model_dump(mode="json") for pr in (result.protocol_references or [])],
        "model_provenance": result.model_provenance,
        "fallback_events": result.fallback_events,
        "doctor_handoff_status": result.doctor_handoff_status,
        "patient_facing_reply": result.patient_facing_reply,
        "latency_seconds": round(latency_s, 3),
        "case_id": result.case_id,
        "full_case": result.model_dump(mode="json"),
    }


def _write_summary(records: list[dict], run_dir: str, provider_override: str, mock: bool) -> None:
    scored = [r for r in records if r["triage_match"] is not None]
    n_correct = sum(1 for r in scored if r["triage_match"])
    accuracy = n_correct / len(scored) if scored else 0.0

    by_group: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_group[r["group"]].append(r)

    confusion: Counter = Counter()
    for r in records:
        if r["expected_final_triage"] is not None:
            confusion[(r["expected_final_triage"], r["actual_final_triage"])] += 1

    rule_scored = [r for r in records if r["rule_match"] is not None]
    rule_correct = sum(1 for r in rule_scored if r["rule_match"])

    rule_id_scored = [r for r in records if r["rule_id_match"] is not None]
    rule_id_correct = sum(1 for r in rule_id_scored if r["rule_id_match"])

    fallback_count = sum(1 for r in records if r["fallback_events"])
    latencies = [r["latency_seconds"] for r in records]

    lines: list[str] = []
    lines.append("# MIRA 30-case paper evaluation -- summary\n")
    lines.append(f"- Run timestamp (UTC): {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"- Git commit: {_git_commit()}")
    lines.append(f"- LLM provider path: {'MOCK' if mock else provider_override or 'anthropic-primary/groq-failover (default)'}")
    lines.append(f"- MIRA_DATA_SOURCE used for run: simulated (doctor-handoff real sends are hard-gated off)")
    lines.append(f"- Cases run: {len(records)} / 30\n")

    lines.append("## Overall triage accuracy\n")
    lines.append(f"- {n_correct}/{len(scored)} = {accuracy:.1%} of scorable cases (excludes group F clarification cases, scored separately below)\n")

    lines.append("## Confusion matrix (expected -> actual final_triage)\n")
    lines.append("| expected \\\\ actual | emergency | urgent | routine | null/other |")
    lines.append("|---|---|---|---|---|")
    for expected in ("emergency", "urgent", "routine"):
        row = [str(confusion.get((expected, actual), 0)) for actual in ("emergency", "urgent", "routine")]
        other = sum(v for (e, a), v in confusion.items() if e == expected and a not in ("emergency", "urgent", "routine"))
        lines.append(f"| {expected} | {row[0]} | {row[1]} | {row[2]} | {other} |")
    lines.append("")

    lines.append("## Rule-engine vs LLM decision correctness\n")
    lines.append(f"- decided_by matched expectation: {rule_correct}/{len(rule_scored)}")
    lines.append(f"- expected specific rule_id fired (group A + g2): {rule_id_correct}/{len(rule_id_scored)}\n")

    lines.append("## Group F (clarification) outcomes\n")
    for r in by_group.get("F", []):
        lines.append(f"- {r['key']}: pipeline_status={r['pipeline_status']}, intake_status={r['intake_status']}, expected_park={'yes' if r['expected_final_triage'] is None else 'no'}, match={r['triage_match']}")
    lines.append("")

    lines.append("## Reliability\n")
    lines.append(f"- Groq/Gemini fallback triggered on: {fallback_count}/{len(records)} cases")
    lines.append(f"- Pipeline degraded (agent failure -> fail-safe) on: {sum(1 for r in records if r['pipeline_status'] == 'degraded')}/{len(records)} cases")
    lines.append(f"- Latency: mean {mean(latencies):.2f}s, median {median(latencies):.2f}s, max {max(latencies):.2f}s\n" if latencies else "")

    lines.append("## Per-case results\n")
    lines.append("| key | group | expected | actual | match | decided_by (exp/act) | latency (s) |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in records:
        lines.append(
            f"| {r['key']} | {r['group']} | {r['expected_final_triage']} | {r['actual_final_triage']} | "
            f"{'✓' if r['triage_match'] else '✗'} | {r['expected_decided_by']}/{r['actual_decided_by']} | {r['latency_seconds']} |"
        )
    lines.append("")

    lines.append("## Caveats for the paper (copy into methodology/limitations verbatim)\n")
    lines.append(
        "- **LLM provider**: this run used "
        + ("a mocked LLM client (no real model calls -- harness smoke test only, not citable results)." if mock else
           f"`MIRA_LLM_PROVIDER={provider_override}` as primary" if provider_override else
           "Claude Sonnet as primary with Groq failover")
        + (" This is a local-test-only override (mira/llm_client.py:build_default_client), not the documented "
           "Sonnet-primary production policy -- do not present these results as representative of Sonnet's "
           "reasoning quality without re-running with a real ANTHROPIC_API_KEY." if (provider_override and not mock) else "")
    )
    lines.append(
        "- **RAG corpus provenance**: mira/knowledge/protocol_corpus/{imnci,nhm,who_chw}.md are explicitly "
        "paraphrased placeholder text written to exercise the retrieval mechanism, NOT the licensed IMNCI/NHM/"
        "WHO CHW source documents. Any retrieval-quality or citation-accuracy claim in the paper must state "
        "this corpus is a stand-in, not the real guideline text."
    )
    lines.append(
        "- **Rule-engine coverage gap**: the red-flag rule engine's tag vocabulary has no tags for pediatric/"
        "newborn/dehydration danger signs (no fast_breathing, sunken_eyes, not_feeding_well, etc.), so every "
        "IMNCI-grounded child/newborn case in this bank (group C) is decided by the LLM alone, never the "
        "deterministic safety net -- a real limitation of the current rule set, not an artifact of this run."
    )
    lines.append(
        "- **Sample provenance**: all 30 cases are synthetic, written for this evaluation (see eval/cases_30.py "
        "docstring), not real patient transcripts -- no IRB/DHS-IEC concern for this run, but also not evidence "
        "of real-world input distribution beyond what's documented in eval/cases_30.py per case."
    )
    lines.append(
        "- **Expected labels**: expected_final_triage/expected_decided_by per case were authored by us ahead of "
        "the run (see eval/cases_30.py), not derived from a clinical reviewer -- per README.md, a clinical "
        "co-advisor review of these judgment calls is still outstanding before any pilot or paper claim relies "
        "on them as ground truth."
    )

    with open(os.path.join(run_dir, "summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="Run only the first N cases (harness smoke test).")
    parser.add_argument("--keys", nargs="*", default=None, help="Run only these case keys.")
    parser.add_argument(
        "--pause", type=float, default=5.0,
        help="Seconds to sleep between cases on top of the per-call pacing below.",
    )
    parser.add_argument(
        "--call-interval", type=float, default=4.0,
        help="Minimum seconds between individual LLM calls WITHIN a case's pipeline run (default 4s). "
             "Added after the first full run showed the configured Groq key/tier 429ing on nearly every "
             "call -- reliability.py's per-call backoff alone wasn't enough to keep cases off the fail-safe "
             "degradation path. Set to 0 to disable (e.g. if using a higher-tier key or a different provider).",
    )
    args = parser.parse_args()

    cases = CASES
    if args.keys:
        wanted = set(args.keys)
        cases = [c for c in cases if c.key in wanted]
    elif args.limit:
        cases = cases[: args.limit]

    if not cases:
        print("No cases selected.", file=sys.stderr)
        sys.exit(1)

    mock = bool(config.MOCK_LLM)
    provider_override = os.environ.get("MIRA_LLM_PROVIDER", "").strip().lower()

    base_client = build_default_client()
    llm_client = (
        PacedLLMClient(base_client, min_interval_s=args.call_interval)
        if args.call_interval > 0
        else base_client
    )

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = os.path.join(RESULTS_ROOT, ts)
    os.makedirs(run_dir, exist_ok=True)

    print(f"Running {len(cases)} case(s); provider={'MOCK' if mock else provider_override or 'anthropic-default'}; call_interval={args.call_interval}s; output -> {run_dir}")

    records = []
    raw_path = os.path.join(run_dir, "raw_results.jsonl")
    with open(raw_path, "w", encoding="utf-8") as f:
        for i, case in enumerate(cases, 1):
            print(f"[{i}/{len(cases)}] {case.key} ... ", end="", flush=True)
            try:
                record = _run_case(case, llm_client=llm_client)
            except Exception as exc:  # noqa: BLE001 -- harness must not die mid-run
                record = {
                    "key": case.key,
                    "label": case.label,
                    "group": case.group,
                    "source_protocol": case.source_protocol,
                    "expected_final_triage": case.expected_final_triage.value if case.expected_final_triage else None,
                    "actual_final_triage": None,
                    "triage_match": False,
                    "expected_decided_by": case.expected_decided_by.value if case.expected_decided_by else None,
                    "actual_decided_by": None,
                    "rule_match": None,
                    "expected_rule_id": case.expected_rule_id,
                    "red_flags_triggered": [],
                    "rule_id_match": None,
                    "pipeline_status": "harness_exception",
                    "intake_status": None,
                    "failed_agent": None,
                    "detected_language": None,
                    "detected_script": None,
                    "romanized_terms_glossed": [],
                    "protocol_references": [],
                    "model_provenance": {},
                    "fallback_events": [],
                    "doctor_handoff_status": None,
                    "patient_facing_reply": None,
                    "latency_seconds": None,
                    "case_id": None,
                    "full_case": None,
                    "harness_error": repr(exc),
                }
                print(f"EXCEPTION: {exc!r}")
            else:
                print(f"triage={record['actual_final_triage']} (expected {record['expected_final_triage']}) match={record['triage_match']} [{record['latency_seconds']}s]")
            records.append(record)
            f.write(json.dumps(record, default=str) + "\n")
            f.flush()
            if i < len(cases) and args.pause > 0:
                time.sleep(args.pause)

    _write_summary(records, run_dir, provider_override, mock)
    print(f"\nDone. Raw results: {raw_path}\nSummary: {os.path.join(run_dir, 'summary.md')}")


if __name__ == "__main__":
    main()
