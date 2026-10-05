"""
Aggregates the best CLEAN result per case across every eval/results/*/
run directory produced so far, and reports which of the 30 cases in
cases_30.py still have no clean result.

"Clean" excludes only infra-contamination (an agent's LLM call exhausting
its retry budget -- rate limits, timeouts, transient 5xx/4xx -- landing
the case on the hardcoded pipeline_status=degraded fail-safe path
instead of reflecting real model reasoning). A degraded case caused by a
genuine content-quality guard (e.g. the diagnostic-claim-language filter
correctly rejecting output) is NOT infra contamination -- it's the
pipeline working as designed and is kept as a legitimate result.
Likewise pipeline_status=awaiting_clarification is kept as-is (a real
outcome), never treated as needing a retry.

Usage:
    python -m eval.aggregate                 # report pending keys
    python -m eval.aggregate --write-final    # also write eval/results/final/
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from datetime import datetime, timezone

from eval.cases_30 import CASES
from eval.run_eval import _write_summary

RESULTS_ROOT = os.path.join(os.path.dirname(__file__), "results")


def _is_infra_contaminated(record: dict) -> bool:
    if record.get("pipeline_status") != "degraded":
        return False
    fc = record.get("full_case") or {}
    reason = fc.get("failure_reason") or ""
    return "API call failed" in reason


def load_all_records() -> list[dict]:
    records = []
    for path in sorted(glob.glob(os.path.join(RESULTS_ROOT, "*", "raw_results.jsonl"))):
        run_id = os.path.basename(os.path.dirname(path))
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                rec["_run_id"] = run_id
                records.append(rec)
    return records


def best_clean_per_case(records: list[dict]) -> dict[str, dict]:
    # cases_30.py has been hand-edited several times today (severity/duration/
    # age fixes) -- a record from an earlier run may have answered a STALE
    # version of a case's raw_input_text that no longer exists on disk.
    # Trusting such a record would silently attribute a model's answer to
    # input it never actually saw. Only accept a record whose stored
    # full_case.raw_input_text exactly matches the CURRENT cases_30.py text
    # for that key -- everything else is discarded regardless of how clean
    # its pipeline_status looked.
    current_text = {c.key: c.raw_input_text for c in CASES}

    # Within cases matching current text, prefer a fully-completed result
    # (pipeline_status == "ok") over one merely not-infra-degraded (e.g.
    # awaiting_clarification) -- both count as "clean" for contamination
    # purposes, but an "ok" completion is strictly more informative for a
    # case that isn't in group F (which is SUPPOSED to park). Ties within
    # the same status level go to the latest run.
    def status_rank(rec: dict) -> int:
        status = rec.get("pipeline_status")
        return {"ok": 2, "degraded": 1}.get(status, 1) if status != "ok" else 2

    best: dict[str, dict] = {}
    for rec in records:
        if rec.get("harness_error"):
            continue
        if _is_infra_contaminated(rec):
            continue
        key = rec["key"]
        fc = rec.get("full_case") or {}
        if fc.get("raw_input_text") != current_text.get(key):
            continue
        if key not in best:
            best[key] = rec
            continue
        incumbent = best[key]
        # group F cases are supposed to park -- don't prefer "ok" there
        is_group_f = any(c.key == key and c.group == "F" for c in CASES)
        if is_group_f:
            if rec["_run_id"] > incumbent["_run_id"]:
                best[key] = rec
            continue
        new_rank, old_rank = status_rank(rec), status_rank(incumbent)
        if new_rank > old_rank or (new_rank == old_rank and rec["_run_id"] > incumbent["_run_id"]):
            best[key] = rec
    return best


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-final", action="store_true")
    args = parser.parse_args()

    records = load_all_records()
    best = best_clean_per_case(records)
    all_keys = [c.key for c in CASES]
    pending = [k for k in all_keys if k not in best]

    print(f"Clean results: {len(best)}/{len(all_keys)}")
    if pending:
        print("Pending:", " ".join(pending))
    else:
        print("All 30 cases have a clean result.")

    if args.write_final:
        final_dir = os.path.join(RESULTS_ROOT, "final")
        os.makedirs(final_dir, exist_ok=True)
        raw_path = os.path.join(final_dir, "raw_results.jsonl")
        ordered_records = [best[key] for key in all_keys if key in best]
        with open(raw_path, "w", encoding="utf-8") as f:
            for rec in ordered_records:
                f.write(json.dumps(rec, default=str) + "\n")
        print(f"Wrote {len(best)} clean records to {raw_path}")

        providers_used = set()
        for rec in ordered_records:
            fc = rec.get("full_case") or {}
            for v in (fc.get("model_provenance") or {}).values():
                providers_used.add(v.split(":", 1)[0])
        provider_desc = " + ".join(sorted(providers_used)) if providers_used else "unknown"
        provider_desc += " (mixed across cases -- see per-agent model_provenance in raw_results.jsonl for exactly which provider/model answered each case)"

        _write_summary(ordered_records, final_dir, provider_override=provider_desc, mock=False)

        summary_path = os.path.join(final_dir, "summary.md")
        with open(summary_path, encoding="utf-8") as f:
            body = f.read()

        if pending:
            banner = (
                f"# ⚠ INTERIM RESULT — {len(best)}/{len(all_keys)} cases complete\n\n"
                f"This is a partial run, aggregated from multiple attempts across "
                f"{datetime.now(timezone.utc).date().isoformat()}. **{len(pending)} "
                f"cases still need a clean (non-quota-contaminated) real-LLM run:** "
                f"{', '.join(pending)}.\n\nEvery number below reflects only the "
                f"{len(best)} completed cases — do not extrapolate the accuracy "
                f"percentage to the full 30 until the remaining cases are in.\n\n"
                "---\n\n"
            )
        else:
            banner = (
                f"# ✅ COMPLETE — 30/30 cases\n\n"
                f"Aggregated from multiple attempts across "
                f"{datetime.now(timezone.utc).date().isoformat()}, combining results "
                f"across providers ({provider_desc.split(' (')[0]}) after Groq's daily "
                f"token quota and other free-tier limits were exhausted mid-session -- "
                f"see per-case `model_provenance` in raw_results.jsonl for exactly which "
                f"provider/model answered each individual case. Every case here is a real "
                f"model completion (or a genuine pipeline fail-safe/clarification outcome), "
                f"never a quota-exhaustion artifact -- see eval/aggregate.py's "
                f"contamination filter for exactly what was excluded and why.\n\n"
                "---\n\n"
            )
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(banner + body)
        print(f"Wrote summary to {summary_path}")


if __name__ == "__main__":
    main()
