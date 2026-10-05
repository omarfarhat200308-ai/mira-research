# MIRA 30-case paper evaluation -- summary

- Run timestamp (UTC): 2026-09-11T12:32:13.996607+00:00
- Git commit: f4fc9ef
- LLM provider path: groq
- MIRA_DATA_SOURCE used for run: simulated (doctor-handoff real sends are hard-gated off)
- Cases run: 2 / 30

## Overall triage accuracy

- 1/2 = 50.0% of scorable cases (excludes group F clarification cases, scored separately below)

## Confusion matrix (expected -> actual final_triage)

| expected \\ actual | emergency | urgent | routine | null/other |
|---|---|---|---|---|
| emergency | 0 | 0 | 0 | 1 |
| urgent | 0 | 0 | 0 | 0 |
| routine | 0 | 0 | 1 | 0 |

## Rule-engine vs LLM decision correctness

- decided_by matched expectation: 1/2
- expected specific rule_id fired (group A + g2): 0/1

## Group F (clarification) outcomes


## Reliability

- Groq/Gemini fallback triggered on: 0/2 cases
- Pipeline degraded (agent failure -> fail-safe) on: 0/2 cases
- Latency: mean 7.04s, median 7.04s, max 12.20s

## Per-case results

| key | group | expected | actual | match | decided_by (exp/act) | latency (s) |
|---|---|---|---|---|---|---|
| a1_chest_pain_dyspnea | A | emergency | None | ✗ | rule_override/None | 1.88 |
| d1_child_mild_cough | D | routine | routine | ✓ | llm/llm | 12.2 |

## Caveats for the paper (copy into methodology/limitations verbatim)

- **LLM provider**: this run used `MIRA_LLM_PROVIDER=groq` as primary This is a local-test-only override (mira/llm_client.py:build_default_client), not the documented Sonnet-primary production policy -- do not present these results as representative of Sonnet's reasoning quality without re-running with a real ANTHROPIC_API_KEY.
- **RAG corpus provenance**: mira/knowledge/protocol_corpus/{imnci,nhm,who_chw}.md are explicitly paraphrased placeholder text written to exercise the retrieval mechanism, NOT the licensed IMNCI/NHM/WHO CHW source documents. Any retrieval-quality or citation-accuracy claim in the paper must state this corpus is a stand-in, not the real guideline text.
- **Rule-engine coverage gap**: the red-flag rule engine's tag vocabulary has no tags for pediatric/newborn/dehydration danger signs (no fast_breathing, sunken_eyes, not_feeding_well, etc.), so every IMNCI-grounded child/newborn case in this bank (group C) is decided by the LLM alone, never the deterministic safety net -- a real limitation of the current rule set, not an artifact of this run.
- **Sample provenance**: all 30 cases are synthetic, written for this evaluation (see eval/cases_30.py docstring), not real patient transcripts -- no IRB/DHS-IEC concern for this run, but also not evidence of real-world input distribution beyond what's documented in eval/cases_30.py per case.
- **Expected labels**: expected_final_triage/expected_decided_by per case were authored by us ahead of the run (see eval/cases_30.py), not derived from a clinical reviewer -- per README.md, a clinical co-advisor review of these judgment calls is still outstanding before any pilot or paper claim relies on them as ground truth.