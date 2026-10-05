"""
Scoring helpers for the 30-case evaluation: explicit denominators, a
distinct bucket for "MIRA produced no output / was never run", Wilson CIs,
and Cohen's kappa. Pure functions, no I/O, so every reported number can be
re-derived from per-case rows and unit-tested.

Design rule: a case with NO MIRA output (never run / blank) is NOT the same
as a case MIRA parked for clarification (a real, scoreable "no decision"
outcome). The two are kept apart so a blank cell can never silently shrink
or grow a denominator.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Optional

TIERS = ("emergency", "urgent", "routine")
PARKED = "parked"        # MIRA asked for clarification: a real outcome, no tier
NOT_RUN = "not_run"      # no MIRA output exists for the case
UNRATED = "unrated"      # rater gave no usable tier


def normalize_mira(output: Optional[str]) -> str:
    """Map recovered/raw MIRA output strings onto tier | PARKED | NOT_RUN."""
    if output is None or str(output).strip() == "":
        return NOT_RUN
    o = str(output).strip().lower()
    if o in TIERS:
        return o
    if o.startswith("none") or o in ("parked", "parked_clarification", "awaiting_clarification"):
        return PARKED
    if o.startswith("degraded_failsafe:"):
        tail = o.split(":", 1)[1]
        return tail if tail in TIERS else PARKED
    return NOT_RUN


@dataclass(frozen=True)
class CaseRow:
    case_id: str
    group: str
    mira: str      # tier | PARKED | NOT_RUN
    truth: str     # tier | UNRATED


def wilson_ci(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return (float("nan"), float("nan"))
    p = successes / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def score(rows: Iterable[CaseRow], exclude_groups: Iterable[str] = ()) -> dict:
    """Exact tier match with the denominator spelled out case by case.

    Denominator = cases that have a usable truth tier, are not in an
    excluded group, and have a MIRA output (tier or PARKED). NOT_RUN and
    UNRATED cases are listed, never silently counted either way.
    """
    ex = set(exclude_groups)
    in_den, not_run, unrated, excluded = [], [], [], []
    for r in rows:
        if r.group in ex:
            excluded.append(r.case_id); continue
        if r.truth not in TIERS:
            unrated.append(r.case_id); continue
        if r.mira == NOT_RUN:
            not_run.append(r.case_id); continue
        in_den.append(r)
    matches = [r.case_id for r in in_den if r.mira == r.truth]
    parked = [r.case_id for r in in_den if r.mira == PARKED]
    n = len(in_den)
    lo, hi = wilson_ci(len(matches), n)
    return dict(n=n, matches=len(matches), match_ids=matches, parked=len(parked),
                parked_ids=parked, denominator_ids=[r.case_id for r in in_den],
                not_run_ids=not_run, unrated_ids=unrated, excluded_ids=excluded,
                accuracy=(len(matches) / n if n else float("nan")), ci95=(lo, hi))


def cohens_kappa(a: list[str], b: list[str]) -> float:
    """Unweighted Cohen's kappa over paired labels (pairs with None dropped by caller)."""
    if len(a) != len(b):
        raise ValueError("label lists must be the same length")
    n = len(a)
    if n == 0:
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    cats = set(a) | set(b)
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)
