"""
Runs the full 5-agent pipeline, end to end, over all 6 fixture cases (the
pre-eclampsia regression case + 5 new synthetic cases spanning
emergency/urgent/routine) and asserts the pipeline's actual final_triage
matches the clinically expected one. Prints a summary table so a human
reviewer can see exactly where the pipeline agrees or disagrees, and via
which path (rule_override vs llm) the decision was reached.
"""
from __future__ import annotations

import pytest

from mira.pipeline import run_pipeline
from mira.state import PipelineStatus

from .fixtures.cases import CASES


def _run_case(case):
    client = case.build_client()
    result = run_pipeline(case.raw_input_text, llm_client=client)
    return result


@pytest.mark.parametrize("case", CASES, ids=[c.key for c in CASES])
def test_case_matches_expected_triage(case):
    result = _run_case(case)

    assert result.pipeline_status == PipelineStatus.OK, (
        f"{case.label}: expected pipeline to complete OK, got "
        f"{result.pipeline_status} (failed_agent={result.failed_agent}, "
        f"reason={result.failure_reason})"
    )
    assert result.final_triage == case.expected_final_triage, (
        f"{case.label}: expected {case.expected_final_triage}, got {result.final_triage}"
    )
    assert result.triage_decided_by == case.expected_decided_by, (
        f"{case.label}: expected decided_by={case.expected_decided_by}, "
        f"got {result.triage_decided_by}"
    )


def test_print_agree_disagree_table():
    """Not an assertion-bearing test in itself (the per-case test above
    carries the pass/fail) — this exists to render the human-readable
    agree/disagree summary requested for clinical review."""
    rows = []
    all_agree = True
    for case in CASES:
        result = _run_case(case)
        agree = (
            result.final_triage == case.expected_final_triage
            and result.triage_decided_by == case.expected_decided_by
        )
        all_agree = all_agree and agree
        rows.append(
            (
                case.label,
                case.expected_final_triage.value,
                result.final_triage.value if result.final_triage else "None",
                case.expected_decided_by.value,
                result.triage_decided_by.value if result.triage_decided_by else "None",
                "AGREE" if agree else "DISAGREE",
            )
        )

    header = f"{'Case':<45} {'Expected':<10} {'Actual':<10} {'Exp. by':<15} {'Act. by':<18} {'Result'}"
    print("\n" + header)
    print("-" * len(header))
    for row in rows:
        print(f"{row[0]:<45} {row[1]:<10} {row[2]:<10} {row[3]:<15} {row[4]:<18} {row[5]}")

    assert all_agree, "One or more cases disagreed with expected triage — see table above"
