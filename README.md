# MIRA

**A multi-stage clinical-triage research prototype, designed for WhatsApp-style use in multilingual, low-resource settings.**

> **Status:** research prototype. **Not clinically validated, not deployed, not evaluated on real patients, and not for clinical use.** All evaluation here uses 30 synthetic cases written by the first author.

## Research release
| | |
|---|---|
| **Title** | MIRA: A Multi-Stage Triage Pipeline with a Triage-Stage Red-Flag Layer, Designed for WhatsApp-Based Use in Low-Resource, Multilingual Settings — An Interim Evaluation on a 30-Case Synthetic Set |
| **Version** | v1.3-corrected (supersedes v1.0–v1.2-interim) |
| **Authors** | Mohammed Omar Farhat · Syeda Fahada Zia · L. Sunil Kumar |
| **DOI** | [10.5281/zenodo.23136983](https://doi.org/10.5281/zenodo.23136983) (all versions: [10.5281/zenodo.23067418](https://doi.org/10.5281/zenodo.23067418)) |
| **Record** | https://zenodo.org/records/23136983 |
| **Date** | 2026-10-04 |
| **Licenses** | Report: CC BY 4.0. Code: MIT. Third-party/provider material: see `THIRD_PARTY_NOTICE.md`. |

## Abstract
MIRA is a fixed, six-stage sequential pipeline of five LLM-backed agents (Intake → Language → Diagnostic → Triage → Referral, with Language run again to translate the reply). A deterministic layer of eight red-flag rules at the Triage stage overrides the language model's tier when that stage is reached. The report is an interim evaluation on a 30-case synthetic set run locally on 2026-09-11 against hosted open-weight models. The main verified finding is architectural: 17 of 30 cases (56.7%) stopped at the Intake completeness gate and never reached the Triage red-flag layer, and none of those received a safety or referral message. This is a system-level observation, not an accuracy estimate.

## Why MIRA?
Frontline health workers in many low-resource settings communicate in several languages, including romanized (Latin-script) Hindi and Telugu. The project explores whether a pipeline that separates information gathering from a deterministic safety layer can support triage decisions in such settings. It does not diagnose and makes no clinical claims.

## System overview
Fixed order, shared typed state, no planning or delegation between stages:
1. **Intake** — extracts structured fields; stops and asks one clarifying question if age, sex, or symptom duration/severity is missing.
2. **Language (normalize)** — language/script identification and symptom tagging; a 62-term dictionary adds glosses for romanized Hindi/Telugu terms.
3. **Diagnostic** — bounded differential, used only to estimate urgency; diagnosis-claim language is rejected.
4. **Triage** — eight hard-coded red-flag rules first (any match → Emergency); otherwise the LLM tier if confidence ≥ 0.6, else escalated one band.
5. **Referral** — deterministic facility lookup; LLM text filtered for drug names/dosages.
6. **Language (translate)** — translates the reply.

The red-flag layer operates **at the Triage stage only**. A case that Intake stops never reaches it.

## Research methodology
- **Evaluation set:** 30 synthetic messages written by the first author (groups A–G); expected tiers were author-assigned and provisional, not externally registered.
- **Run:** 2026-09-11, local harness, hosted models (Groq and NVIDIA NIM, plus three Gemini calls), synthetic text input. The reported per-case result is a retrospective selection of infrastructure-complete records across 17 attempts.
- **Clinical review:** partial and not blind. Rater 1 is a clinician co-author and the first author's mother; her worksheet leaves four cases unrated. A second rater's sheet was not recovered.
- **Retrieval corpus:** author-written placeholder text, not WHO/IMNCI/NHM guidance.

## Results (verified; see the report for full context)
| Finding | Value |
|---|---|
| Cases stopped at Intake (never reached Triage; no safety/referral message) | **17 / 30 (56.7%)** — 11 asked for sex, 6 for duration/severity |
| Tier agreement with usable Rater 1 assessments, explicit written tiers only | 1 / 13 (7.7%; Wilson 95% CI 1.4–33.3%) |
| Tier agreement, explicit plus 10 tiers inferred from "agree" | 8 / 23 (34.8%; 18.8–55.1%) |
| "14/29" | Reconstructed historical v1.2 scoring convention. **Not** a performance result; the original rule was never recorded. |

These are small, descriptive, non-blind, partly inferred figures. They are **not** accuracy estimates and do not establish clinical safety or validity.

## Methodological correction (v1.3-corrected)
An earlier interim report (v1.0–v1.2) described the system and evaluation inaccurately. v1.3 corrects, and documents in its appendix: the technology stack (no Claude, PostgreSQL, Docker, or learned transliteration was used), "deployed" (it was a local harness on synthetic text), "independent" raters (Rater 1 is the first author's mother and was not blind), a case mislabeled as "not run" (B2 ran and stopped at Intake), a mis-attributed case (G2 vs A4), the withdrawn second-rater statistics, and the unrecorded 14/29 scoring rule. The corrections are part of the record, not hidden.

## Limitations
Synthetic, author-written cases with provisional labels; small samples; incomplete, non-blind clinical review; placeholder retrieval corpus; no real-patient data; no deployment; the WhatsApp path was not exercised; results are a retrospective selection of attempts.

## Reproducibility
**Public in this repository:** source code, the 30 synthetic cases, run outputs and structured per-agent logs for the evaluated run, scoring scripts, derived tables, tests (135 passing).
**Not preserved, so exact reproduction is limited:** executed prompt text, provider model revisions, sampling settings, the exact executed code state; provider/model varied across cases. Original rater files are withheld; Rater 2's rating sheet was not recovered. This is not a fully reproducible evaluation.

## Repository structure
`mira/` pipeline code · `eval/` harness, 30 cases, results · `evaluation/` reconstruction scripts, audits, derived tables · `tests/` · `paper/` the v1.3 report · `THIRD_PARTY_NOTICE.md` · `LICENSE` (MIT).

## Earlier implementation
The June 2026 hackathon prototype, TABIB, is a different codebase: https://github.com/omarfarhat200308-ai/mira-clinical-triage. It is **not** the v1.3 release.

## Citation
> Farhat, M. O., Zia, S. F., & Kumar, L. S. (2026). *MIRA: A Multi-Stage Triage Pipeline with a Triage-Stage Red-Flag Layer, Designed for WhatsApp-Based Use in Low-Resource, Multilingual Settings — An Interim Evaluation on a 30-Case Synthetic Set* (v1.3-corrected) [Preprint]. Zenodo. https://doi.org/10.5281/zenodo.23136983

## Authors
Mohammed Omar Farhat (independent researcher, Hyderabad, India) — designed and built the system, wrote the evaluation set, ran the evaluation, wrote the report. Syeda Fahada Zia (Government Medical College, Nagarkurnool) — clinical review (Rater 1). L. Sunil Kumar (Gandhi Medical College & Hospital, Secunderabad) — reported second rater.

## AI assistance
AI coding assistants were used during development and in drafting the corrected report; the first author directed the work and is responsible for it.

## Contact
omarfarhat200308@gmail.com (as published in the report).
