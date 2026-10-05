# Publication-readiness audit — MIRA v1.3 (2026-10-04)

Local edits only. Nothing was published or uploaded, and no DOI was created. Scope: paper, README, citation/Zenodo metadata, third-party notice, archive composition. Evidence sources: `evaluation/analysis_reconstruct.py` outputs, `eval/results/final`, `logs/2026-09-11*.jsonl` copies, `eval/aggregate.py`, git history, rater workbook extraction.

## 0. Verification of the source-of-truth facts (all confirmed, no discrepancy)
Recomputed from the data (`analysis_reconstruct.py`, `analysis_rater2_partial.py`): 14/29 = 48.3% (Wilson 31.4–65.6); 8/23 = 34.8% (18.8–55.1); 1/13 = 7.7% (1.4–33.3); 3/7 = 42.9% (15.8–75.0); 11/29 = 37.9% (22.7–56.0); partition 14+11+3+1 = 29. Parked cases: 17/30 = 56.7%; 0 reached Triage; 0 produced a reply; 11 asked sex, 6 duration/severity. Rater 1 provenance: 15 written (13 tiers + 2 "need more information"), 10 inferred, 5 unverified. `eval/aggregate.py` selection criteria do not read expected tiers or rater data. Ten of the 13 explicit-tier cases were stopped at Intake.

## 1. Files changed
`paper/MIRA_interim_report_v1.3.md` and `.pdf` (rewritten); `THIRD_PARTY_NOTICE.md` (rewritten); `README.md` (status banner + 2 sentences); `docs/clinical_review_export.md` (note, heading, superseded-headline note); `CITATION.cff`; `.zenodo.json`; `evaluation/build_public_archive.sh` (new); `paper/MIRA_code_and_evaluation_v1.3.zip` (rebuilt; 171 files, 218 archive entries including directories); this report.

## 2. Required fixes implemented
| # | Fix | Where | Old → new | Reason / evidence |
|---|---|---|---|---|
| 1 | Primary result = 17/30 stopped at Intake | Abstract, §4.1 | headline was "14/29 (48.3%) exact match" → "17 of 30 (56.7%) stopped at Intake… run-level observation, not an accuracy estimate" | `PARKED_CASE_AUDIT.csv` |
| 2 | 14/29 only as reconstructed v1.2 convention | Abstract, §4.3 | "exact match 14/29" → "reconstructed v1.2 scoring convention… never written down… historical only, not a performance result" | no contemporaneous rule found |
| 3 | Explicit vs inferred Rater 1 tiers | Abstract, §4.3 | one 8/23 number → 1/13 (strict sensitivity) listed first, 8/23 with "10 inferred" caveat | canonical table provenance |
| 4 | Hypothetical Rater 2 paragraph deleted | §4.4 | a paragraph that restated the withdrawn v1.2 Rater 2 aggregates with hypothetical adjusted values → removed; "aggregates withdrawn" | not a verified result |
| 5 | Rater 2 | §3.4, §4.4 | aggregates reported → withdrawn; seven ratings labelled "author-recorded, incomplete, non-representative… not an independent Rater 2 evaluation" | source sheet unrecovered |
| 6 | Rater 1 relationship | Abstract, §3.3, §5, new "Competing interests" | "independent clinical assessment" → "first author's mother… not blind and not independent… clinician-assigned reference assessment" | acknowledgments of v1.2; worksheet design |
| 7 | Expected labels | §3.1 | "pre-registered" → "author-assigned, provisional, not externally registered, subject to clinical review… not ground truth" | no registry/protocol |
| 8 | Stage boundary of red-flag layer | Title, Abstract, §2.2, §7 | an earlier title wording and "unconditionally" → "deterministic red-flag layer at the Triage stage" | `pipeline.py` order |
| 9 | A6 wording | §4.2.1 | "rule did not fire" → "Intake completeness gate prevented the stroke presentation from reaching the Triage red-flag layer… not evidence about whether the rule would have matched" | audit CSV |
| 10 | Romanization | §4.2.4, §6 | implied cause → "does not show that romanization caused these outcomes"; Script Gap labelled as literature | E1/E2/E3 questions |
| 11 | "30-case synthetic evaluation set" | throughout | "benchmark"/"case bank" → "evaluation set… not an established or externally validated benchmark" | — |
| 12 | "Infrastructure-clean" defined | §3.2 | undefined → exact criteria from `aggregate.py`; "defined retrospectively, not preregistered; do not use expected tiers or rater data; preference for completed records can only reduce the stopped count" | code read |
| 13 | Reproducibility | §5 | partial → full list (prompts, revisions, sampling, code state, provider/model variation) | metadata audit |
| 14 | Retrieval corpus | §2.3, §5 | "protocol text" → "placeholder paraphrase text… not the published WHO/IMNCI/NHM guidance… tests the mechanism only" | corpus headers |
| 15 | Low-resource | Title, Abstract, §1 | "…in Low-Resource Settings" → "designed for… evaluation did not take place in a real low-resource setting" | — |
| 16 | WhatsApp | §2.3 | deployed-sounding → "not exercised… MIRA was not deployed on WhatsApp" | harness inputs |
| 17 | Logging | §2.2, Appendix | "verbatim" → structured snapshots; prompts/responses/config not retained | log schema |
| 18 | Ethics/human subjects | new section | none → no real patient data, no participants, no clinical decisions, synthetic, no clinical validation | — |
| 19 | Not medical advice | status box, Ethics | kept and made prominent | — |
| 20 | Third-party content | `THIRD_PARTY_NOTICE.md`, archive build | archive shipped later WHO/NHM-derived corpus (one NC-SA section) → **archive now ships only the evaluation-time author-written placeholder corpus (commit `fea51d4`)**; later source-derived files stay in the private repo | corpus headers; 135/135 tests still pass on the archive |
| 21 | Metadata sync | `CITATION.cff`, `.zenodo.json` | single author "Omar Farhat", MIT, "grounded in IMNCI/NHM/WHO" → three authors with affiliations, report CC BY 4.0 vs code MIT stated separately, `isNewVersionOf` v1.2, `isDerivedFrom` TABIB repo; **no DOI invented** (concept DOI only) | Zenodo record |
| 22 | Co-author consent | this report §9 | no record exists → TODO flagged, nothing fabricated | repo search |
| 23 | AI-assistance disclosure | new section | none → "Claude Code used in development, debugging, audit scripts and drafting this corrected version; the first author directed the work and is responsible" | git trailers + this session |
| 24 | ASHABot / eSanjeevani | §6 + refs [4],[5] | unverified one-line claims → verified descriptions with references (ASHABot: CHI 2025, arXiv:2409.10913; eSanjeevani: MoHFW service with doctor-to-doctor and patient-to-doctor models) | web check 2026-10-04 |
| 25 | Correction appendix kept | Appendix | extended to 12 items | — |

## 3. Strongly recommended fixes implemented
README banner ("not validated… every evaluation run used Groq/NVIDIA, not Claude"); README "fully audited" → structured-snapshots wording; README pilot sentence updated; `docs/clinical_review_export.md`: heading "validate" → "exercise", and its 2026-09-12 headline "11/30" and "correctly pausing" marked superseded; older `paper/mira_paper_draft.*` and the Zenodo/PubMed-era guides excluded from the archive; competing-interests section; archive README note.

## 4. Optional fixes not implemented
Title in the Zenodo draft was not changed (draft still has the earlier title — see §11); LICENSE holder wording ("Omar Farhat") left unchanged; the private repo's later source-derived corpus files were not rewritten (clean-room replacement is optional now that they are not redistributed); `mira/config.py` `SYSTEM_FRAMING` ("Verifiable Workflow Automator") untouched; ORCIDs not added; code-level comments not audited.

## 5. Numbers changed or re-labelled
No result was changed or improved. Re-labelled: 14/29 (headline → historical reconstruction); 11/29 (headline no-decision → component of that reconstruction; verified count is 17/30); 8/23 (retained with inferred caveat); 1/13 (added as strict analysis; was computed, not previously in the paper); 3/7 (retained, descriptive). Deleted: the three hypothetical restated Rater 2 aggregates. Withdrawn: 10/27, 13/27, 22/28.

## 6. Claims weakened or removed
"Independent" raters; "ground truth"; "pre-registered"; "deployed"; "multi-agent"/"five-node"; "unconditionally"; "verbatim"; "benchmark"; romanization-as-cause; A6 "rule did not fire"; TABIB "validated the override"; the earlier "deployed"-style title wording; guideline-grounded retrieval; README "fully audited"; export "correctly pausing"; v1.2's unverified ASHABot/eSanjeevani characterisations (now referenced).

## 7. Remaining unsupported or author-reported claims
"Rater 2 reviewed blind / as a favor via the team's network" and that Dr. Kumar reviewed at all — author-reported, sheet not archived (stated as such). The seven Rater 2 observations — author-recorded. Identification of the workbook as Dr. Zia's — author-confirmed, not verifiable from the file. "Executed code ≈ `fea51d4`" — belief only. The old-repo credential statement — author-level, unverified. "Independent researcher" is the first author's own affiliation line.

## 8. Licensing / copyright items for human review
Archive now contains no third-party-derived corpus text (overlap check vs local WHO texts: 5 shared 8-word runs of one short clinical phrase, in the *later* files, which are excluded). Still: provider-generated model outputs in the logs (provider terms not individually checked); dependencies' own licences; the LICENSE copyright line names only the first author; the Zenodo record licence (CC BY 4.0) vs the code (MIT) — separated in the notice but a reader of the record sees one licence badge. The private repo's later corpus files remain third-party-derived and must not be published as-is.

## 9. Co-author consent issues (human action)
No consent record exists anywhere in the repository. **TODO — author must obtain explicit written approval from Dr. Zia and Dr. Kumar** for (a) the corrected v1.3 text under their names, including the competing-interests and rater-limitation statements, (b) the AI-assistance disclosure, and (c) any derived rating tables or rater-related text in the archive. Original rater files are excluded pending that consent.

## 10. Factual discrepancies found during this audit
`.zenodo.json`/`CITATION.cff` listed one author, MIT, and "grounded in IMNCI/NHM/WHO" paragraphs (corpus was placeholder at evaluation time) — fixed. README said Claude Sonnet is primary and "fully audited" — qualified. The review export's headline counted 2 clarification stops as matches and called stops "correct" — superseded. The archive previously contained HEAD's later corpus, not the evaluation-time one — fixed. My earlier archive note that `test_rag` might fail was wrong (all 135 pass) — corrected. The Zenodo draft's description still quotes 14/29 and 8/23 in the older framing.

## 11. Publication blockers
1. **The Zenodo draft is out of sync with these edits.** It still holds the previous PDF, zip and notice, the earlier title, and the earlier description (which leads with agreement figures). New files: `paper/MIRA_interim_report_v1.3.pdf` (sha256 `814ba19a…`), `paper/MIRA_code_and_evaluation_v1.3.zip` (checksum: see `ZENODO_PUBLISH_PACKET.md`, which is not part of the archive), `THIRD_PARTY_NOTICE.md`; new title and description in `ZENODO_PUBLISH_PACKET.md`.
2. **Co-author consent** (§9).
3. Author review of the author-reported items in §7, and of the AI-assistance wording.
4. Rater 2's source sheet and Rater 1's blank rows remain unrecovered — acceptable only because the paper now states exactly that; no further claims may be added without them.

**Verdict: NOT READY TO PUBLISH** — blockers 1–3 above.
