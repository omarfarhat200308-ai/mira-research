# Denominator reconciliation (first-pass; superseded by ../EVALUATION_RECONSTRUCTION.md — numbers here remain valid, rater-status lines updated there)

Inputs: recovered MIRA outputs (`mira_outputs_recovered.csv`, = `eval/results/final`, joined to verbatim logs), the recovered Rater-1 workbook (`rater1_ratings_canonical.csv`), `eval/cases_30.py`. Scoring code: `eval/scoring.py` (tested). Nothing was chosen to match the paper; where the paper's figure can be reproduced the exact case sets are listed so they can be judged.

## 1. Bottom line

| Figure | Result |
|---|---|
| **14/29 (Rater 1 exact match, 48.3%)** | **Arithmetically reproducible, methodologically inconsistent.** One partition reproduces it exactly (§3), but it needs classification choices that contradict the paper's own text and the worksheet. A rule-consistent strict match gives **8/23 (34.8%, Wilson 95% CI 18.8–55.1%)**. |
| **11/29 (Rater 1 no-decision, 37.9%)** | **Reproducible** from the same partition, including the paper's 6 Emergency / 3 Urgent / 2 Routine split — *only if G2 is counted as Emergency*, i.e. not applying the G2→Urgent correction the paper describes. |
| **10/27, 13/27** | **UNTRACEABLE.** They are Rater-2 figures; no Rater-2 data exists locally. |
| **Inter-rater** | **NOT COMPUTABLE.** |
| **B2 "MIRA = not run"** | **Contradicted by run data** (see `B2_C1_AND_CASE_ID_AUDIT.md`). |

## 2. Why the evaluated outputs are the Sep-11 run
The 29 non-B2 MIRA cells in the Rater-1 workbook equal the recovered `final` aggregate case-for-case (the d5 cell reads "urgent" = the failsafe-degraded output). The rater therefore reviewed the Groq/NVIDIA aggregate; no other MIRA run is evidenced anywhere on disk.

## 3. The reproducing partition (denominator 29 = 30 − B2)
- **No-decision (11):** a6, a8, c2, c3, c4, c5, d6, e1, e2, e3, g2 — parked, non-F, excluding d2/d3/d4.
- **Tier mismatch (3):** c1 (routine vs urgent), d5 (failsafe urgent vs routine), g1 (emergency vs routine/urgent).
- **Acceptable over-triage (1):** c6 (paper's separate "1/29").
- **Match (14):** a1, a2, a3, a4, a5, a7, b1, d1, d2, d3, d4, f1, f2, f3. 14+11+3+1 = 29 ✓.
- Split of the 11 by correct tier: Emergency a6,a8,c2,c4,e1,g2 = **6**; Urgent c3,c5,e2 = **3**; Routine d6,e3 = **2** ✓ (G2 as Emergency; if G2→Urgent is applied the split is 5/4/2).
- Wilson 95% CI: 14/29 = 31.4–65.6%; 11/29 = 22.7–56.0%.

**This is a fit, not a recovered method.** I did not find the author's scoring rule; this partition is consistent with every figure in the paper, nothing more. Its problems:
1. d2, d3, d4 (MIRA parked) are counted as **matches**, yet d6/e3 (also parked, routine) are counted as no-decision, and the paper text says two routine cases were unnecessary clarifications. Rater wrote "agree" in J on d2–d4, but also on a6 and c3, which the partition counts as no-decision/misses.
2. f1/f2 (parked, "need more information") counted as matches — defensible, but then F is inside the 29 while the harness's own denominators exclude F.
3. b1 is a match although the rater row is **blank**.
4. G2 is Emergency in the split but described as corrected to Urgent in the text.
5. 4 of the 29 rows (a8, b1, e1, g2) have no rater entry, contradicting "all 29 assessed".

## 4. Rule-consistent recomputation (code-derived)
Rule: truth = rater tier (explicit, or "agree"→author-expected, flagged inferred); match = MIRA tier equals truth; parked is never a match; rows with no usable rater tier are listed, not counted.

| Scope | n | matches | parked | 95% CI |
|---|---|---|---|---|
| all rows with a usable rater tier | 23 | 8 | 12 | 18.8–55.1% |
| same, excluding group F | 22 | 7 | 12 | 16.4–52.8% |

Matches: a1 a2 a3 a4 a5 a7 d1 f3. Excluded because the rater gave no usable tier (7): a8 b1 e1 f1 f2 g1 g2.
B2 is **inside** the 23: the rater tier is Emergency and the recovered MIRA output is `parked`, so it is a miss. (`eval/scoring.py` would put B2 in `not_run` only if its MIRA cell were blank, as it is in the xlsx; against the recovered run outputs it is `parked`.)

## 5. Other denominator facts
- Author-expected labels vs MIRA (no rater): 9/30, 8/27 non-F strict; repo "11/30" = 9 + F1/F2 parks.
- 30 = A8 + B2 + C6 + D6 + E3 + F3 + G2, all IDs unique and consistent with the PDFs.
- Two different 30-case banks exist (A–G in `cases_30.py`/`Full30_Blind_Validation.pdf`; dengue/pregnancy/respiratory/GI in `SecondRater.pdf`) with colliding IDs (D1–D7, G1–G7). Any Rater-2 figure must name its bank; the second bank has no MIRA outputs at all.

## 6. Still needed to close this
The author's actual scoring rule, the missing Rater-1 entries (a8, b1, e1, g2, g1 tier), and all Rater-2 data.
