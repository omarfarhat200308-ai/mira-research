# MIRA: A Multi-Stage Triage Pipeline with a Triage-Stage Red-Flag Layer, Designed for WhatsApp-Based Use in Low-Resource, Multilingual Settings — An Interim Evaluation on a 30-Case Synthetic Set

*Interim system and evaluation report — Version 1.3 (corrected; supersedes v1.2-interim)*

Mohammed Omar Farhat¹, Syeda Fahada Zia² (co-author, clinical review), L. Sunil Kumar³ (co-author, clinical review)

¹ Independent researcher, Hyderabad, India · ² Professor of Microbiology, Government Medical College, Nagarkurnool, Telangana, India · ³ Professor & Head of Department, General Medicine, Gandhi Medical College & Hospital, Secunderabad, Telangana, India

Correspondence: omarfarhat200308@gmail.com · Concept DOI 10.5281/zenodo.23067418

**Status of this work.** MIRA is an implemented research prototype. It has **not** been clinically validated, **not** deployed, and **not** evaluated on real patients, and it **must not be used for clinical decisions**.

## Abstract

MIRA is a fixed, six-stage sequential pipeline of five LLM-backed agents (Intake → Language → Diagnostic → Triage → Referral, with the Language agent run again to translate the reply). It is designed to accept a WhatsApp-style message describing symptoms, in English or romanized Hindi/Telugu, and to return a triage tier (Emergency / Urgent / Routine) and a referral, for use in low-resource, multilingual settings. At the Triage stage, a deterministic layer of eight red-flag rules overrides the language model's tier when that stage is reached. This report is an interim evaluation on a **30-case synthetic evaluation set written by the first author**; the expected tiers were author-assigned, provisional, and not externally registered. The evaluation was run locally on 2026-09-11 against hosted open-weight models (Groq and NVIDIA NIM endpoints, plus three Gemini calls) with synthetic text as input. No real patient data, human participants, or clinical decisions were involved.

**The main verified finding is architectural.** In that run, **17 of 30 cases (56.7%) stopped at the Intake stage with a clarifying question and never reached Triage.** None of the 17 received a safety or referral message; 11 were stopped for a missing patient-sex field and 6 for missing duration or severity. Four cases that the author expected to trigger a red-flag rule (A6 stroke, A8 gastrointestinal bleeding, E1 pre-eclampsia, G2 heavy bleeding) were among them, so the Intake completeness gate prevented the Triage red-flag layer from ever evaluating them. Component-level correctness is not system-level safety. This is a run-level observation, not an accuracy estimate.

Clinical review was incomplete and not blinded. Rater 1 is a clinician co-author, the system's clinical co-advisor, and the first author's mother; she saw MIRA's output next to each case, and her recovered worksheet has four unrated cases. Of the 13 cases with an explicit, written Rater 1 tier, MIRA's decided tier agreed in 1 (7.7%; Wilson 95% CI 1.4–33.3%). If 10 further entries that only say "agree" are counted as agreement with the expected tier, agreement is 8 of 23 (34.8%; 18.8–55.1%). These are small-sample descriptive figures. A scoring convention used in v1.2 (14/29) was never written down and is reproducible only by a retrospective reconstruction; it is retained solely to document the correction. The aggregate statistics v1.2 attributed to a second rater are **withdrawn**, because the source rating sheet cannot be recovered. The reported results are a retrospective selection of infrastructure-complete attempts and are not fully reproducible (§5). Romanized-script input is **not** shown to have caused the Group E failures. This version also documents the methodological and reporting errors of v1.2.

## 1. Introduction

Rural India has a severe shortage of physicians relative to population, and Accredited Social Health Activist (ASHA) workers are frequently the first point of contact before any clinician is involved. WhatsApp is widely used in these communities. MIRA is designed to sit before a patient reaches a clinician, not to replace one. Its design is deliberately narrow: it does not diagnose; it estimates urgency and gives a referral instruction. This report describes the system as built and presents an interim evaluation on synthetic cases. It does not claim clinical validation, deployment readiness, or regulatory-grade performance, and its evaluation did not take place in a real low-resource setting.

## 2. System architecture

### 2.1 Pipeline

Each message passes through a fixed sequence of stages over a typed, structured state object. There is no planning, delegation, or critique between stages; the order is hard-coded.

1. **Intake** — an LLM extracts structured fields. If age, sex, or the primary symptom's duration/severity is missing, the pipeline stops and returns one clarifying question (at most two rounds).
2. **Language (normalize)** — an LLM identifies language and script and maps symptoms onto a fixed tag vocabulary. Before this, a dictionary-based step appends bracketed English glosses to recognised romanized Hindi/Telugu terms (§2.3).
3. **Diagnostic** — an LLM proposes a bounded differential from a fixed taxonomy, grounded by retrieval and used only to estimate urgency; output containing diagnosis-claim language is rejected.
4. **Triage** — eight hard-coded red-flag rules run first; any match forces Emergency. Otherwise the LLM tier is used if its confidence is at least 0.6; low-confidence or malformed output is escalated one band and marked fail-safe.
5. **Referral** — facility type is a deterministic lookup from the tier; an LLM writes next steps and warning signs, rejected if it contains drug names or dosage patterns.
6. **Language (translate)** — an LLM translates the reply (romanized for Hindi/Telugu).

After bounded retries, an agent failure degrades to a fixed fail-safe: a non-Routine tier and a standard instruction to go to the nearest clinic.

### 2.2 Scope of the red-flag layer; logging

- The deterministic red-flag layer operates **at the Triage stage only**. Because Intake runs first, any case that Intake stops never reaches it (§4.2).
- Low-confidence output is designed to escalate rather than default to Routine.
- Each agent call is logged with provider, model, latency, errors, fallback flags, and a **structured snapshot** of its input and output. Executed prompt text, raw model responses, and complete model configuration were **not** retained, so the log supports inspection of structured inputs and outputs, not full reconstruction of each call.
- The hackathon-stage prototype, TABIB (three agents coordinated through Band, using Claude, with red flags expressed in the prompt), preceded MIRA. The deterministic rule layer was introduced in MIRA. No logged comparison of a model-alone result against a rule-forced result on the pre-eclampsia test case was found, so this report makes no claim that TABIB validated the override mechanism.

### 2.3 Implementation and evaluation configuration

- **Language-model access:** hosted APIs only, called from a local workstation. Models in the 2026-09-11 logs: `gpt-oss-120b` (Groq); via NVIDIA NIM, `gpt-oss-20b`, `nemotron-3.5-lightning-30b-a3b`, and `deepseek-v4-flash-0731`; and three calls to `gemini-flash-latest`. The codebase contains an Anthropic client; it was not used in any evaluation run.
- **Romanization:** a hand-curated dictionary of 62 romanized Hindi/Telugu symptom terms inserts an inline English gloss after a recognised term (e.g. "tez bukhar [high fever]"). No learned transliteration model is used.
- **Retrieval corpus:** TF-IDF cosine over locally stored protocol text. **At evaluation time this corpus was placeholder paraphrase text written by the authors; it was not the published WHO, IMNCI, or National Health Mission guidance.** The evaluation therefore tests the retrieval mechanism only; it says nothing about concordance with any guideline.
- **Storage and logs:** SQLite for consent/case records; append-only JSONL files for the audit log.
- **Messaging:** a FastAPI/Twilio WhatsApp webhook is implemented and unit-tested but was **not exercised**. Evaluation inputs were synthetic text passed directly to the pipeline, with doctor-handoff sends disabled. MIRA was not deployed on WhatsApp.

## 3. Method

### 3.1 The 30-case synthetic evaluation set

The first author wrote 30 synthetic cases in seven groups: A (8) single-symptom presentations the author expected to trigger a deterministic emergency rule; B (2) emergencies without a rule; C (6) pattern-based conditions; D (6) routine negative controls; E (3) romanized Hindi/Telugu; F (3) under-specified input (one negative control); G (2) rule-generalisation edge cases. Each case is a single message with no multi-turn dialogue. This is the authors' own set, not an established or externally validated benchmark. The original expected tiers were **author-assigned and provisional**: they were fixed before clinical review (they appear in run records dated 2026-09-11 and in the repository from 2026-09-12), were not registered in any external registry, and were subject to clinical review. They are not ground truth.

### 3.2 Evaluation run and record selection

Cases were run through the pipeline with an evaluation harness on 2026-09-11. Several attempts were needed because provider rate limits and timeouts caused infrastructure failures (in one complete 30-case attempt, 21 cases ended in the fail-safe path for that reason). The reported per-case result is one record per case selected from 17 attempts by `eval/aggregate.py`. The criteria were **defined retrospectively, during and after the earlier attempts, not preregistered**: a record was excluded if the pipeline degraded because an LLM API call failed, or if its stored case text differed from that case's final text; among the remaining records, for cases outside Group F, a record in which the pipeline ran to completion was preferred over one that stopped for clarification, and ties went to the latest attempt. These criteria use neither the expected tiers nor any rater's assessment, so the selection was not made on clinical agreement. The preference for completed records can only reduce, not inflate, the number of cases reported as stopped at Intake. The selection nevertheless means the table combines different providers and models, and two cases (D1, G1) were run before an edit to the Intake prompt (an instruction to convert infant ages given in months or days to years). The commit recorded in the run summaries is not the executed code (§5).

### 3.3 Clinical assessment — Rater 1

The first rater, Dr. Zia, is a co-author, the system's clinical co-advisor, and the first author's mother. She received a worksheet listing each case, the author's expected tier, and MIRA's output. **Her review was therefore not blind and not independent.** Her assessment is treated here as a clinician-assigned reference assessment, not as ground truth. The recovered worksheet is incomplete: **four rows (A8, B1, E1, G2) have no entry; G1 reads "not agree" without a tier; F1 and F2 read "need more information"**. Of the 23 rows with a response usable as a tier, 13 contain a tier written by the rater (several typed into the wrong column) and 10 contain only "agree" or "correct", which I interpret as agreement with my expected tier — an interpretation, not an explicit rating. The workbook's metadata names an editor account, not the rater; I identify the file as Dr. Zia's worksheet, and that cannot be verified from the file itself.

### 3.4 Clinical assessment — Rater 2

Version 1.2 reported a second physician, Dr. L. Sunil Kumar, who reviewed the cases without seeing MIRA's output. **His completed rating sheet has not been recovered or archived.** All aggregate Rater 2 statistics in v1.2 are therefore withdrawn (§4.4). The only Rater 2 information used in this report is seven ratings that the first author personally recorded.

## 4. Results

### 4.1 System-level result (verified from run records)

In the 2026-09-11 run, **17 of 30 cases (56.7%) stopped at Intake with a clarifying question and never reached Triage.** For all 17, no patient-facing reply, next steps, warning signs, or facility recommendation was produced; the only message sent is the clarifying question. Eleven questions asked for the patient's sex and six for symptom duration or severity. This is a run-level observation about the system, **not an accuracy estimate**, and it is independent of any rater.

### 4.2 Findings

**4.2.1 Stroke presentation (A6).** The Intake completeness gate prevented the stroke presentation from reaching the Triage red-flag layer. Intake asked "how severe is the facial drooping?", although the message already described severe arm weakness and badly slurred speech. The rule was never evaluated; this is a failure of the system's stage ordering, not evidence about whether the stroke rule would have matched.

**4.2.2 Other cases that never reached the rules.** A8 (a large vomit of blood), E1 (pre-eclampsia pattern, romanized Hindi) and G2 (heavy bleeding) were also stopped at Intake, together with B2 (reduced fetal movement), C4 (newborn breathing difficulty) and others. Ten stopped cases carry an Emergency or Urgent expected tier. Each received a clarifying question and no safety message.

**4.2.3 Why the cases stopped.** Version 1.2 left open whether the clarification path sends a conservative fallback message. The run records answer it: it does not. In 11 of 17 cases the question asked for the patient's sex, a field the Intake stage hard-requires. This is a design decision about what must be known before triage, with a direct safety consequence for urgent presentations, and it is the highest-priority engineering issue identified.

**4.2.4 Romanized-script subset (Group E).** All three romanized-script cases (E1 Hindi, E2 Telugu, E3 Hindi) were parked at Intake — E1 for symptom duration, E2 and E3 for patient sex. These are the same gates that stopped English-language cases. This evaluation does **not** show that romanization caused these outcomes. Prior work (§6) found romanized input can degrade LLM triage performance, but that is the literature's evidence, not MIRA's.

**4.2.5 Decided under-triage (C1).** MIRA decided Routine (by the LLM, `gpt-oss-120b`) for a 3-year-old with fast labored breathing at rest; Rater 1 wrote "should be urgent". This is the only case where a decided tier was lower than Rater 1's tier. It is not the only unsafe outcome: see 4.2.2.

**4.2.6 Case G1.** MIRA decided Emergency (by the LLM) for isolated mild chest discomfort in a 75-year-old; the chest-pain rule did not fire, as designed. Rater 1's G1 entry is "not agree" with no tier, so the v1.2 statement that Rater 1 judged the correct tier Routine cannot be verified. The author-recorded Rater 2 rating is Urgent.

**4.2.7 Review-driven corrections to expected tiers.** Verified from Rater 1's worksheet: for B2 she wrote Emergency where my expected tier was Urgent. v1.2 also stated that a non-pregnant heavy-vaginal-bleeding case was corrected from Emergency to Urgent by "the clinical rater", and named it "A4". That case is **G2** (Group G; not A4, and not part of Group E). Rater 1's G2 row is blank, so the correction cannot be verified from her worksheet; the author-recorded Rater 2 rating for G2 is Urgent. For A4, Rater 1's comment says it must be Emergency, which matches the expected tier — no correction.

**4.2.8 Case B2.** B2 was run in eight attempts and, in the retained record, stopped at Intake (the question asked for the patient's sex), so it has no triage tier. It was not "not run", as v1.2 stated.

### 4.3 Tier agreement with the usable Rater 1 assessment

The term *agreement* is used deliberately: Rater 1's assessment is a non-blind, partly inferred clinician reference, not ground truth, and stopped cases count as non-agreement because no tier was produced. B2 is included (stopped; Rater 1 tier Emergency). Cases without a usable Rater 1 tier (A8, B1, E1, G1, G2 and the non-tier F1/F2) are excluded and listed.

| Analysis | Denominator | MIRA tier agrees | Wilson 95% CI | Notes |
|---|---|---|---|---|
| Explicit written Rater 1 tiers only (strict sensitivity analysis) | 13 | 1 (7.7%) | 1.4–33.3% | tier written by the rater; ten of the 13 denominator cases were stopped at Intake |
| Explicit or inferred usable tiers | 23 | 8 (34.8%) | 18.8–55.1% | 10 of the 23 are inferred from "agree"/"correct" and are **not** equivalent to explicit ratings |
| Reconstructed v1.2 scoring convention (historical only) | 29 | 14 (48.3%) | 31.4–65.6% | see below; **not** a performance result |

**On the reconstructed v1.2 convention.** v1.2 reported 14/29 and 11/29 without stating a scoring rule, and no contemporaneous written rule was recovered. The figures can be reproduced only by one retrospective partition of the 29 non-B2 cases (14 matches + 11 no-decision + 3 tier mismatches + 1 accepted over-triage). That partition counts D2, D3, D4, F1 and F2 (stopped at Intake) as matches, counts B1 as a match although the Rater 1 row is blank, and uses a particular handling of G2. It is therefore not presented as a performance or accuracy result and is retained only to document the correction. The 11/29 (37.9%) figure is the "no decision" component of that reconstruction; it is **not** the verified system-level count, which is 17/30 (§4.1).

### 4.4 Second rater: aggregates withdrawn; seven author-recorded observations

The Rater 2 aggregates published in v1.2 (exact match 10/27, no decision 13/27, Rater 1–Rater 2 agreement 22/28) are **withdrawn**, because the source rating sheet cannot be recovered and the figures cannot be verified. v1.2 also stated that A1 and A2 were left unmarked by Rater 2; that was an error.

The first author personally recorded the following Rater 2 ratings. The original rating document was not recovered. They are **author-recorded, incomplete, and non-representative observations**, not an independent Rater 2 evaluation, and no inter-rater statistic can be drawn from them.

| Case | Rater 2 (author-recorded) | MIRA (retained record) |
|---|---|---|
| A1 | Emergency | Emergency (rule override) |
| A2 | Emergency | Emergency (rule override) |
| A8 | Emergency | stopped at Intake (asked sex) |
| B1 | Emergency | Emergency (LLM) |
| E1 | Emergency | stopped at Intake (asked duration) |
| G1 | Urgent | Emergency (LLM) |
| G2 | Urgent | stopped at Intake (asked sex) |

MIRA's tier matched on 3 of these 7 (A1, A2, B1; 42.9%, Wilson 95% CI 15.8–75.0%); A8, E1 and G2 were stopped at Intake and G1 was over-triaged by one tier. This is descriptive only.

## 5. Limitations

- **Not validated, not deployed, synthetic.** No real patient data, no human participants, no clinical decisions, no ethics or regulatory clearance. The 30 cases are the first author's own synthetic set with provisional author-assigned labels.
- **Raters.** One clinician co-author (the first author's mother) provided the non-blind Rater 1 assessment; its rows are incomplete and 10 usable tiers are inferred. Rater 2 was reported to have reviewed as a favor arranged through the research team's network; his sheet is not archived. Neither rater is described as independent.
- **Not fully reproducible.** Exact reproduction is limited because executed prompts, provider/model revisions and sampling settings were not consistently preserved; the exact executed code state is not definitively known (the recorded commit is not the executed working tree; the closest committed snapshot is believed, not proven, to be `fea51d4`); and providers and models varied across cases and attempts. The per-case table is a retrospective selection of infrastructure-complete attempts (§3.2), and two cases ran before an Intake prompt edit.
- **Placeholder retrieval corpus** at evaluation time (§2.3); no guideline concordance is claimed.
- **Small samples** (7–29) support descriptive statements and failure-mode identification, not accuracy estimates.
- **Component vs system.** The red-flag layer was never run on the cases that Intake stopped; nothing here measures how often the rules would have fired correctly.
- **No messaging evaluation.** The WhatsApp webhook path was not exercised.

## 6. Related work

ASHABot [4] is a WhatsApp-based, LLM-powered, experts-in-the-loop chatbot that supports ASHA and other community health workers' information needs; it is worker-facing rather than a patient-intake triage system. eSanjeevani [5] is India's national telemedicine service, with doctor-to-doctor and patient-to-doctor teleconsultation models; MIRA is designed for the step before such a consultation. Agentic medical systems such as ArogyaSutra [2] (an actor–critic framework with iterative refinement for multimodal reasoning in Indic languages) and TriAgent [3] (a supervisor agent delegating queries to specialised sub-agents for acute-care triage biomarker discovery) use planning, delegation, or critique among agents. MIRA does none of these: it is a fixed sequence of stages, which is why this report calls it multi-stage.

Script Gap [1] is prior literature on a related question and is distinct from MIRA's own evidence. Using real maternal and newborn health queries, it reports that romanized messages account for 83% of Hindi and 73% of Telugu inputs in its dataset; that weighted F1 for romanized input falls 1–8 points below native script on average among top-tier models; that gaps reach up to 24 points across language–model pairs; and, in the full text, that some models lose 20–30 points of accuracy for Kannada and Telugu when switching from native script to Roman. MIRA's Group E observation (§4.2.4) is at most a possibly related phenomenon; this evaluation does not show that a script gap caused it.

**References**
[1] Khullar M., Desai U., Malviya P., Dalmia A., Shi Z. R. *Script Gap: Evaluating LLM Triage on Indian Languages in Native vs Romanized Scripts in a Real World Setting.* arXiv:2512.10780.
[2] *ArogyaSutra: A Multi-Agent Framework for Multimodal Medical Reasoning in Indic Languages.* arXiv:2606.13572.
[3] *TriAgent: Automated Biomarker Discovery with Deep Research Grounding for Triage in Acute Care by LLM-Based Multi-Agent Collaboration.* arXiv:2510.16080.
[4] Ramjee P., Chhokar M., Sachdeva B., Meena M., Abdullah H., Vashistha A., Nagar R., Jain M. *ASHABot: An LLM-Powered Chatbot to Support the Informational Needs of Community Health Workers.* CHI 2025; arXiv:2409.10913.
[5] Ministry of Health and Family Welfare, Government of India. *eSanjeevani national telemedicine service*; see also *Adoption and utilization of India's eSanjeevani national telemedicine service*, Oxford Open Digital Health, 2025, doi:10.1093/oodh/oqaf025.

## 7. Conclusion and next steps

MIRA is a working sequential pipeline with a deterministic red-flag layer at its Triage stage and a per-call structured log. This interim evaluation, on 30 synthetic cases, exposed an interaction between stages: an upstream Intake completeness gate stopped more than half of the cases before the red-flag layer could evaluate them, with no safety message sent. That is a systems-engineering finding; it says nothing about the clinical accuracy of MIRA's tiers. Priorities, in order:

1. Replace the silent clarification path with a conservative message (for example interim referral guidance), and relax or defer the hard sex requirement for presentations with emergency danger signs.
2. Evaluate the red-flag rules before, or independently of, the Intake completeness gate.
3. Re-run the full set in one configuration, with executed prompts, model versions, sampling settings and the exact code commit logged, and with rater-blinded review whose completed sheets are archived.
4. Resolve the B2, G1 and G2 labels with both raters and archive the signed ratings.
5. Expand the case set before any accuracy claim, and pursue ethics and regulatory steps before any real-patient data collection.

Voice input is not part of the evaluation. Speech-to-text and text-to-speech service code and a single synthetic-speech latency probe exist in the repository (v1.2 said voice "has not been built"); no voice accuracy claim is made.

## Ethics and human subjects

No real patient data were used. No human participants were enrolled. No clinical decisions were made using MIRA. All 30 cases are synthetic messages written by the first author. No clinical validation was performed. The clinician co-authors reviewed synthetic case text only. MIRA is an unvalidated research prototype and must not be used for clinical decisions. It is not medical advice.

## AI-assisted development disclosure

AI coding assistants (Claude Code) were used during software development and debugging, in the audit analysis scripts, and in drafting this corrected version. The first author directed the work and is responsible for the system design, experimental decisions, interpretation, and the final manuscript.

## Author contributions

M.O.F. designed and built the system, wrote the case set, ran the evaluation, recorded the ratings referred to in §4.4, and wrote the report. Dr. Zia reviewed and annotated the case worksheet (Rater 1). Dr. Kumar is reported by the author to have reviewed the case set as a second rater; his rating sheet is not archived.

## Competing interests and relationships

Dr. Zia (Rater 1, co-author, clinical co-advisor) is the first author's mother. Rater 2's review was arranged through the research team's network.

## Data, code, and licence availability

The MIRA source code, the 30-case synthetic set, run outputs, scoring scripts, derived evaluation tables, and per-agent structured logs for the evaluated run are archived in this Zenodo record. Licences are separate: the report is CC BY 4.0; the source code is MIT; the archive's `THIRD_PARTY_NOTICE.md` lists third-party and provider-generated material that is not covered by those licences. Original rater files are withheld pending the raters' consent. The repository linked in v1.2 (`github.com/omarfarhat200308-ai/mira-clinical-triage`) contains the TABIB hackathon prototype, which preceded MIRA, and not the evaluated code. An earlier hackathon repository exposed credentials in its commit history in June 2026; the public repository was rebuilt without them, and whether those credentials were misused was not independently verified, so they should be treated as exposed until revoked.

## Acknowledgments

I thank my mother and co-author, Dr. Syeda Fahada Zia, for her clinical review work, and Dr. L. Sunil Kumar for reviewing the case set. I also thank the participants of the Band of Agents Hackathon (lablab.ai), where the early three-agent prototype was built.

## Appendix: corrections relative to version 1.2-interim

Version 1.2 (DOI 10.5281/zenodo.23120740) is superseded. Its errors, corrected above and retained here for transparency:

1. **Technology stack.** v1.2 named Claude, PostgreSQL, Docker, IndicTrans2 and Aksharamukha. None was used in the evaluated system (hosted Groq/NVIDIA NIM/Gemini models, a hand-written romanization dictionary, SQLite and JSONL logs).
2. **"Deployed" / WhatsApp.** The evaluation was a local harness run on synthetic text; the messaging path was not exercised.
3. **Architecture wording.** "Five-node" and "multi-agent" overstated the design: it is a fixed six-stage sequence of five LLM-backed agents with no planning or delegation, and "unconditional" red-flag override applies only at Triage.
4. **Rater independence.** Raters were called independent; Rater 1 is the first author's mother and review was not blind for her; Rater 2's review was arranged through the team's network.
5. **Rater 2.** The aggregates (10/27, 13/27, 22/28) are withdrawn, and "A1 and A2 unmarked" was wrong.
6. **Scoring.** 14/29 and 11/29 had no recorded scoring rule and are presented only as a reconstruction; the verified system-level figure is 17/30 stopped at Intake.
7. **B2** was run in eight attempts, not "not run".
8. **G2/A4.** The heavy-bleeding case is G2 (Group G), not A4 or Group E; the claimed correction to Urgent is not verifiable from Rater 1's worksheet.
9. **No-decision pathway.** v1.2 left open what the clarification path sends; it sends only the clarifying question, and 11 of 17 stops were for a missing sex field.
10. **Code link.** The linked repository contained the TABIB prototype, not MIRA.
11. **Logging.** "Verbatim" logging overstated what was retained (structured snapshots only).
12. **Related-work characterisations** of ASHABot and eSanjeevani were unverified in v1.2 and are now referenced.
