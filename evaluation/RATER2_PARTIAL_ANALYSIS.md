# Rater 2 — partial analysis from author-recorded ratings

**Provenance limitation (applies to every number here):** the seven Rater 2 ratings (A1, A2, A8, B1, E1 = Emergency; G1, G2 = Urgent) are the **author's direct recorded observations (USER-REPORTED / PERSONALLY RECORDED)**. **The original Rater 2 source document has not been recovered.** No other Rater 2 rating is asserted or inferred. Record: `recovered/raters/rater2_user_supplied_corrected.csv`; the first, erroneous entry (G1/G2 as Emergency) is preserved in `rater2_user_supplied_partial.csv`; see `RATER2_CORRECTION_NOTE.md`. Script: `evaluation/analysis_rater2_partial.py`.

## A. What the seven ratings support directly
**MIRA vs Rater 2 on these 7 cases only — denominator 7 (not representative; chosen by availability):**
| Case | Rater 2 | MIRA (recovered run) | Match |
|---|---|---|---|
| A1 | Emergency | Emergency (rule override) | ✓ |
| A2 | Emergency | Emergency (rule override) | ✓ |
| A8 | Emergency | parked at Intake (asked sex) | ✗ |
| B1 | Emergency | Emergency (LLM) | ✓ |
| E1 | Emergency | parked at Intake (asked duration) | ✗ |
| G1 | Urgent | Emergency (LLM) | ✗ (over-triage by one tier) |
| G2 | Urgent | parked at Intake (asked sex) | ✗ |
**3/7 (42.9%, Wilson 95% CI 15.8–75.0%).** The four misses are three parked cases (A8, E1, G2) and one over-triage (G1). A8 and E1 are Emergency cases that MIRA never triaged.

**Rater 1 ∩ Rater 2 on these 7:** only A1 and A2 have a Rater 1 tier (both *inferred from "agree"*, not directly written); both agree with Rater 2 (2/2). A8, B1, E1, G1, G2 have no usable Rater 1 tier, so no inter-rater statistic can be formed for them. **Not meaningful as an agreement estimate.**

## B. Published v1.2 Rater 2 statements
v1.2 stated that A1 and A2 were "left unmarked" by Rater 2. The author's recorded observations show **both were rated Emergency**; that v1.2 statement was an error. The Rater 2 aggregate statistics published in v1.2 (exact match, no-decision rate, and Rater 1–Rater 2 agreement) are **withdrawn**: their source rating sheet cannot be recovered, and **no restated, adjusted, or hypothetical replacement aggregate is provided anywhere in this release**.

| Item | v1.2 | Author-recorded observation |
|---|---|---|
| A1, A2 (Rater 2) | "unmarked" | **Emergency** (v1.2 was wrong) |
| G1 (Rater 2) | Urgent | **Urgent** (consistent) |
| G2 (Rater 2) | not stated | **Urgent** |

v1.2 is also internally inconsistent about B2 for Rater 2 (§4.3 "both raters confirm Emergency"; §5 "Rater 2 did not review B2"; §4.4.2 "B2 not run"); this is not resolved here.

## C. Reassessment of the other figures
- **Withdrawn Rater 2 aggregates** → no restated value is offered; the numerators were never verified and the source sheet is unrecovered.
- **11/29** (Rater-1 no-decision, published split 6E/3U/2R): derived from Rater 1/MIRA data and the author-expected labels; **not changed by Rater 2 data** (A1, A2 are not in it). The corrected observation **G2 = Urgent (Rater 2)** shows the published split is not unique: with G2 = Urgent the split reproduces only if one of C3/E2 is counted Emergency (as Rater 2 reportedly did, per v1.2), e.g. E = {A6, A8, C2, C3, C4, E1}, U = {C5, E2, G2}. So 6/3/2 is consistent with **two** assignments (G2 = Emergency by author label, or a mix of Rater-1 and Rater-2 tiers); the published text does not say which. 11/29 itself still stands as a count under the reconstructed convention.
- **8/23** (Analysis B, Rater-1 tiers, strict match): **unchanged** — Rater 2 ratings are not Rater 1 ratings and are not used to fill Rater 1's blank rows (A8, B1, E1, G2, G1 remain UNVERIFIED for Rater 1). CI 18.8–55.1% stands.

## D. G2 attribution
v1.2 §4.2.6 says "the clinical rater's assessment" corrected a non-pregnant heavy-bleeding case from Emergency to Urgent. The recovered **Rater 1** sheet has a blank G2 row, but **Rater 2 = Urgent** (author-recorded). The correction is therefore supported as a **Rater 2** judgement (provenance as above), not a Rater 1 one; the paper's attribution must be fixed. The case ID is G2 (not A4), in Group G (not E).
