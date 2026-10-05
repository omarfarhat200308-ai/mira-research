# B2, C1 and case-ID audit

Sources: recovered run outputs + verbatim logs, recovered Rater-1 workbook (`raters/`), `eval/cases_30.py`, `MIRA_v1_interim_report.pdf`. Rater 2 = blank PDFs only.

## B2 (reduced fetal movement, 8 months pregnant)
| Field | Stated | Evidence | Status |
|---|---|---|---|
| Rater 1 | Emergency | Workbook `b2` col K: "should be emergency" (author label was Urgent) | **VERIFIED** (single cell, free text) |
| Rater 2 | Emergency | Only blank forms exist | **UNVERIFIED** |
| MIRA | "not run" | Executed in **8** run directories (T125732Z, T132358Z, T134223Z, T145921Z, T150801Z, T174539Z, T190801Z, T195113Z); 3 with the current case text (T174539Z degraded→urgent failsafe; T190801Z and T195113Z `awaiting_clarification`); the `final` record is parked at Intake (nemotron-3.5-lightning). `docs/clinical_review_worksheet.csv` (commit `decc25b`) says "None (parked for clarification)". The only place B2 looks "not run" is the **blank MIRA cell in the xlsx**, which differs from the repo CSV it was derived from. | **CONTRADICTED** — B2 was run; correct label is "parked for clarification (no tier)" |

Consequence: the "29 scored of 30" framing rests on a blank cell. With B2 scored, the Rater-1 view is 30 cases, B2 a miss (Emergency vs parked).

## C1 (3-year-old, cough + fast breathing at rest)
| Field | Stated | Evidence | Status |
|---|---|---|---|
| MIRA | Routine | `final`: routine, `decided_by=llm`, model groq gpt-oss-120b, all stages `ok`; worksheet agrees | **VERIFIED** |
| Rater 1 | Urgent | Workbook: J="wrong", K="should be urgent" | **VERIFIED** |
| Rater 2 | Emergency | Blank form only | **UNVERIFIED** (and clinically differs from Rater 1; any kappa will reflect that once data exists) |

## The "heavy-bleeding correction"
Report §4.2.6: "In two cases (A4 and B2) … a case involving non-pregnant heavy vaginal bleeding pre-registered as Emergency was corrected to Urgent."

- Case that matches the *description*: **G2** (`g2_nonpostpartum_heavy_bleeding`, "I am 29, not pregnant … bleeding very heavily … soaking through pads every 30 minutes"; author label **Emergency**, matching the "pre-registered Emergency" part).
- **A4** is the 8-month-old with stiff neck/fever (infant meningitis pattern), author label Emergency; the rater's entry is a comment *agreeing* it must be Emergency ("need to be a emergency … rule over ride is required"). **No correction occurred on A4.** The "A4" in §4.2.6 is a wrong ID.
- Evidence for the G2 → Urgent correction itself: **none** — the G2 row in the workbook is entirely blank. **The correction is UNVERIFIED** (it may exist in a message/phone call/another file not found).
- Note the 6/3/2 no-decision split reproduces only with G2 = Emergency (reconciliation §3), i.e. the paper's own numbers do not apply that correction.
- Other heavy-bleeding cases (A3 postpartum, A7 trauma) are not candidates (both Emergency, agreed).

## All case IDs cited in the report
| Report statement | Check | Result |
|---|---|---|
| Group sizes A8 B2 C6 D6 E3 F3 G2 | `cases_30.py` | ✓ |
| A6 = stroke, rule mapped, no decision | A6 text, expected rule `neuro_stroke_pattern`, parked at Intake ("how severe is the facial drooping?"). Rule layer sits after Intake, so it never ran. | ✓ but the cause is Intake gating, not a rule failure |
| C1 under-triaged Routine (should be Urgent) | see above | ✓ |
| G1 model-level over-triage (Emergency; rule inactive) | `decided_by=llm`, no rule; MIRA emergency | ✓ ("correct tier Routine": rater wrote only "not agree" — tier **UNVERIFIED**; author label was Urgent) |
| "Group E … including a non-pregnant heavy-bleeding case" (§4.2.4) | Group E = E1 pre-eclampsia (Hindi), E2 child breathing (Telugu), E3 mild cold (Hindi). The heavy-bleeding case is **G2, Group G** | **✗ wrong group** |
| "A4 and B2 corrected" | see above | **✗ A4 wrong** |
| C6 over-triage "judged clinically acceptable by rater" | Workbook C6: J="agree" (author label Urgent, MIRA Emergency); no explicit "acceptable over-triage" wording | UNVERIFIED interpretation |
| "0/3 romanized cases produced a decision" | E1, E2, E3 all parked at Intake | ✓ |
| §4.2.3: 6 Emergency / 3 Urgent / 2 Routine of the 11 | reproduces only under the fit in reconciliation §3 | qualified |

---
## Update 2026-10-04 (author-recorded Rater 2 ratings; source document not recovered)
- **G2:** Rater 2 = **Urgent** (author-recorded). Rater 1's row is blank. The "Emergency → Urgent" correction in v1.2 §4.2.6 is therefore supported as a **Rater 2** judgement (not Rater 1), still without a recovered source document. Author-expected label was Emergency.
- **G1:** Rater 2 = Urgent (matches v1.2); Rater 1 = "not agree", no tier. MIRA = Emergency.
- **A1, A2:** Rater 2 = Emergency (v1.2 "unmarked" is wrong). **A8, B1, E1:** Rater 2 = Emergency.
- **B2:** unchanged — no Rater 2 tier is among the seven; v1.2's statements about Rater 2 and B2 are mutually inconsistent.
- **C1:** unchanged (MIRA Routine; Rater 1 Urgent verified from sheet; Rater 2 "Emergency" per v1.2 remains unverified).
