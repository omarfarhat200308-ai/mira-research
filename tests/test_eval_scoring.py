import math

import pytest

from eval.scoring import (
    NOT_RUN, PARKED, UNRATED, CaseRow, cohens_kappa, normalize_mira, score, wilson_ci,
)


def test_normalize_distinguishes_parked_from_not_run():
    assert normalize_mira("None (parked for clarification)") == PARKED
    assert normalize_mira("PARKED_CLARIFICATION") == PARKED
    assert normalize_mira("") == NOT_RUN          # blank cell != parked
    assert normalize_mira(None) == NOT_RUN
    assert normalize_mira("emergency") == "emergency"
    assert normalize_mira("DEGRADED_FAILSAFE:urgent") == "urgent"


def test_denominator_traced_to_case_ids():
    rows = [
        CaseRow("A1", "A", "emergency", "emergency"),   # match
        CaseRow("A2", "A", PARKED, "emergency"),        # in denominator, miss
        CaseRow("B2", "B", NOT_RUN, "emergency"),       # B2 handling: excluded, listed
        CaseRow("D1", "D", "routine", UNRATED),         # unrated: excluded, listed
        CaseRow("F1", "F", PARKED, "urgent"),           # excluded group
    ]
    r = score(rows, exclude_groups=["F"])
    assert r["denominator_ids"] == ["A1", "A2"]
    assert r["n"] == 2 and r["matches"] == 1 and r["parked"] == 1
    assert r["not_run_ids"] == ["B2"]
    assert r["unrated_ids"] == ["D1"]
    assert r["excluded_ids"] == ["F1"]


def test_missing_mira_output_never_counts_as_match_or_miss():
    only_missing = [CaseRow("B2", "B", NOT_RUN, "emergency")]
    r = score(only_missing)
    assert r["n"] == 0 and math.isnan(r["accuracy"])
    assert r["not_run_ids"] == ["B2"]


def test_wilson_ci_known_values():
    lo, hi = wilson_ci(14, 29)
    assert lo == pytest.approx(0.314, abs=0.01)
    assert hi == pytest.approx(0.658, abs=0.01)
    assert wilson_ci(0, 0)[0] != wilson_ci(0, 0)[0]  # NaN for empty
    lo0, hi0 = wilson_ci(0, 10)
    assert lo0 == 0.0 and 0 < hi0 < 0.35


def test_kappa_perfect_none_and_known():
    assert cohens_kappa(["a", "b", "a"], ["a", "b", "a"]) == pytest.approx(1.0)
    # 2x2 hand-computed: yy=25 yn=10 ny=5 nn=10 -> po=0.70,
    # pe=0.7*0.6+0.3*0.4=0.54, kappa=(0.70-0.54)/(1-0.54)=0.3478
    a = ["y"] * 25 + ["y"] * 10 + ["n"] * 5 + ["n"] * 10
    b = ["y"] * 25 + ["n"] * 10 + ["y"] * 5 + ["n"] * 10
    assert cohens_kappa(a, b) == pytest.approx(0.3478, abs=0.001)
    with pytest.raises(ValueError):
        cohens_kappa(["a"], ["a", "b"])
