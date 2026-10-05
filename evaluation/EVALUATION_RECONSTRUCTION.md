# Evaluation reconstruction

Code: `evaluation/analysis_reconstruct.py` (read-only on inputs, regenerates every table below). Inputs: Rater-1 workbook (preserved original), `eval/results/final`, verbatim logs. **Rater 2 metrics were deliberately not computed**: Rater 2's ratings were not recovered (blank forms only; Gmail search denied by the permission classifier).

Which paper: the **published Zenodo v1.2-interim** (DOI 10.5281/zenodo.23120740, 2026-10-03, PDF sha256 `3d4199bb…`) is the current paper. Its Rater-1 figures are identical to the 9/30 draft (14/29, 11/29); it adds Rater-2 figures (10/27, 13/27, 22/28) that cannot be checked here.

## Rater-1 tier provenance (`recovered/rater1_ratings_canonical.csv`)
| Label | Rows | Meaning |
|---|---|---|
| DIRECTLY WRITTEN | 15 | A tier word (or "need more information") typed by the rater: A4, B2, C1, C2, C4, C5, D2, D3, D4, D5, D6, E2, E3 (+ F1, F2 non-tier). For D2–D6, E2, E3 the text sits in the wrong column (`MIRA_decision_path`). |
| INFERRED FROM TEXT | 10 | Only "agree"/"correct" written; tier assumed = author-assigned tier: A1, A2, A3, A5, A6, A7, C3, C6, D1, F3. "Agree" could equally refer to MIRA's output. **Not direct physician tiers.** |
| UNVERIFIED | 5 | A8, B1, E1, G2 blank; G1 "not agree" with no tier. Nothing was filled in. |

## Analysis A — published scoring rule, reconstructed (`ANALYSIS_A_published_rule.csv`)
Denominator 29 = all cases except B2. Reproduces **14/29 (48.3%, Wilson 31.4–65.6%)**, **11/29 no-decision (37.9%, 22.7–56.0%)**, 3 tier mismatches, 1 acceptable over-triage (14+11+3+1 = 29), and the **6 Emergency / 3 Urgent / 2 Routine** split of the 11.

| Bucket | Cases |
|---|---|
| Match (14) | A1 A2 A3 A4 A5 A7 B1 D1 D2 D3 D4 F1 F2 F3 |
| No decision (11) | A6 A8 C2 C3 C4 C5 D6 E1 E2 E3 G2 |
| Tier mismatch (3) | C1 D5 G1 |
| Acceptable over-triage (1) | C6 |

This is the only partition found that reproduces every published figure; it is **not shown to be the author's actual rule**. It is internally inconsistent: D2/D3/D4 and F1/F2 were parked yet counted as matches (while D6/E3, also parked routine cases, are "no decision"); B1 counts as a match with a **blank** rater row; A6/C3 carry "agree" yet count as no-decision; the 6/3/2 split needs G2 = Emergency, not the Urgent correction the paper describes (with G2 Urgent: 5/4/2); and the 11 includes A8, E1 and G2, which have no rater tier (author label used).

## Analysis B — one consistent rule (`ANALYSIS_B_consistent_rule.csv`)
Rule: truth = Rater-1 triage tier (directly written or inferred, flagged); a case is scored only if it has such a tier; match = MIRA's decided tier equals the truth; **parked/no tier is a non-match**; B2 is included (parked, rater Emergency); F1/F2 ("need more information") and the 5 UNVERIFIED rows are excluded and listed.

| Variant | n | Matches | Parked | Wilson 95% CI |
|---|---|---|---|---|
| **B (direct + inferred tiers)** | **23** | **8** (A1 A2 A3 A4 A5 A7 D1 F3) | 12 | **18.8–55.1%** (8/23 = 34.8%) |
| B-direct (direct tiers only) | 13 | 1 (A4) | 10 | 1.4–33.3% |

Independently re-derived by a separate code path (raw xlsx + raw results only, no shared helpers): n = 23, matches = 8 ✓. (Also unit-tested via `eval/scoring.py`.)

**This is a corrected/reconstructed figure under a different inclusion rule — it does not replace the published 14/29, and the two answer different questions** (B scores strict tier agreement among rated cases; A counts a mixture of matches, appropriate parks, and parked-but-agreed cases).

## Not reconstructable
10/27, 13/27, 78.6% (22/28), "48.1%" (Rater 2); every Rater-2 tier; the six named disagreements; Rater-1 tiers for A8, B1, E1, G2, G1. Not computed, by instruction.

## Parked cases — `PARKED_CASE_AUDIT.csv` (17 of 30)
- **All 17 stopped at Intake** (only an Intake call completed); **0 reached Triage**, so no red-flag rule was evaluated for any — including the 4 with a mapped rule (A6 stroke, A8 GI bleeding, E1 pre-eclampsia, G2 heavy bleeding).
- **0/17** have a patient-facing reply, next steps, warning signs, or a referral/facility; the webhook sends **only the clarifying question** (`mira/webhook.py` L187-189, L251-253). No safety or referral message.
- **Why they parked: 11 asked for the patient's sex** (A8, B2, C2, C3, C4, C5, D4, D6, E2, E3, G2) — Intake hard-requires age, **sex** and duration/severity — and 6 asked for duration/severity (A6, D2, D3, E1, F1, F2). A6's question ("how severe is the facial drooping?") was asked although the text says "severely weak … badly slurred".
- Consequence for the paper: the no-decision rate is mostly an **Intake completeness gate** (a missing sex field), not evidence about romanization (E2/E3 asked for sex; E1 for duration) or clinical reasoning. 10 of the 17 have an author-assigned (and, where present, rater) tier of Emergency or Urgent (A6 A8 B2 C2 C3 C4 C5 E1 E2 G2); none was handled safely merely by being parked.

---
## Update 2026-10-04 — Rater 2 partial data (author-recorded; source not recovered)
Seven Rater 2 ratings now exist as personally recorded observations; analysis in `RATER2_PARTIAL_ANALYSIS.md` (MIRA vs Rater 2 on those seven: 3/7). **Analysis A (14/29, 11/29) and Analysis B (8/23, CI 18.8–55.1%) are Rater-1-based and are unchanged.** The Rater 2 aggregates published in v1.2 are withdrawn (source sheet unrecovered); no restated or adjusted aggregate is provided. The 6E/3U/2R split of the 11 is consistent with two assignments, not one (see that file §C).
