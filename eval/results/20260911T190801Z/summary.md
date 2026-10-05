# MIRA 30-case paper evaluation -- summary

- Run timestamp (UTC): 2026-09-11T19:20:24.172533+00:00
- Git commit: f4fc9ef
- LLM provider path: nvidia
- MIRA_DATA_SOURCE used for run: simulated (doctor-handoff real sends are hard-gated off)
- Cases run: 10 / 30

## Overall triage accuracy

- 0/10 = 0.0% of scorable cases (excludes group F clarification cases, scored separately below)

## Confusion matrix (expected -> actual final_triage)

| expected \\ actual | emergency | urgent | routine | null/other |
|---|---|---|---|---|
| emergency | 0 | 0 | 0 | 1 |
| urgent | 1 | 0 | 0 | 5 |
| routine | 0 | 1 | 0 | 2 |

## Rule-engine vs LLM decision correctness

- decided_by matched expectation: 1/10
- expected specific rule_id fired (group A + g2): 0/0

## Group F (clarification) outcomes


## Reliability

- Groq/Gemini fallback triggered on: 0/10 cases
- Pipeline degraded (agent failure -> fail-safe) on: 1/10 cases
- Latency: mean 61.02s, median 42.09s, max 188.44s

## Per-case results

| key | group | expected | actual | match | decided_by (exp/act) | latency (s) |
|---|---|---|---|---|---|---|
| b2_reduced_fetal_movement | B | urgent | None | ✗ | llm/None | 28.732 |
| c2_newborn_not_feeding | C | urgent | None | ✗ | llm/None | 94.781 |
| c3_child_dehydration | C | urgent | None | ✗ | llm/None | 25.896 |
| c4_newborn_breathing | C | emergency | None | ✗ | llm/None | 41.769 |
| c5_chronic_cough_weightloss | C | urgent | None | ✗ | llm/None | 42.406 |
| c6_infant_persistent_fever | C | urgent | emergency | ✗ | llm/llm | 188.439 |
| d4_adult_sprain | D | routine | None | ✗ | llm/None | 26.52 |
| d5_adult_sore_throat | D | routine | urgent | ✗ | llm/failsafe_degraded | 14.049 |
| e2_romanized_telugu_child_breathing | E | urgent | None | ✗ | llm/None | 92.337 |
| e3_romanized_hindi_mild_cold | E | routine | None | ✗ | llm/None | 55.26 |

## Caveats for the paper (copy into methodology/limitations verbatim)

- **LLM provider**: this run used `MIRA_LLM_PROVIDER=nvidia` as primary This is a local-test-only override (mira/llm_client.py:build_default_client), not the documented Sonnet-primary production policy -- do not present these results as representative of Sonnet's reasoning quality without re-running with a real ANTHROPIC_API_KEY.
- **RAG corpus provenance**: mira/knowledge/protocol_corpus/{imnci,nhm,who_chw}.md are explicitly paraphrased placeholder text written to exercise the retrieval mechanism, NOT the licensed IMNCI/NHM/WHO CHW source documents. Any retrieval-quality or citation-accuracy claim in the paper must state this corpus is a stand-in, not the real guideline text.
- **Rule-engine coverage gap**: the red-flag rule engine's tag vocabulary has no tags for pediatric/newborn/dehydration danger signs (no fast_breathing, sunken_eyes, not_feeding_well, etc.), so every IMNCI-grounded child/newborn case in this bank (group C) is decided by the LLM alone, never the deterministic safety net -- a real limitation of the current rule set, not an artifact of this run.
- **Sample provenance**: all 30 cases are synthetic, written for this evaluation (see eval/cases_30.py docstring), not real patient transcripts -- no IRB/DHS-IEC concern for this run, but also not evidence of real-world input distribution beyond what's documented in eval/cases_30.py per case.
- **Expected labels**: expected_final_triage/expected_decided_by per case were authored by us ahead of the run (see eval/cases_30.py), not derived from a clinical reviewer -- per README.md, a clinical co-advisor review of these judgment calls is still outstanding before any pilot or paper claim relies on them as ground truth.