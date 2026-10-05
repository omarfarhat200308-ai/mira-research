# MIRA 30-case paper evaluation -- summary

- Run timestamp (UTC): 2026-09-11T12:55:01.221805+00:00
- Git commit: f4fc9ef
- LLM provider path: groq
- MIRA_DATA_SOURCE used for run: simulated (doctor-handoff real sends are hard-gated off)
- Cases run: 7 / 30

## Overall triage accuracy

- 4/7 = 57.1% of scorable cases (excludes group F clarification cases, scored separately below)

## Confusion matrix (expected -> actual final_triage)

| expected \\ actual | emergency | urgent | routine | null/other |
|---|---|---|---|---|
| emergency | 1 | 0 | 0 | 1 |
| urgent | 1 | 2 | 0 | 0 |
| routine | 0 | 1 | 0 | 0 |

## Rule-engine vs LLM decision correctness

- decided_by matched expectation: 2/6
- expected specific rule_id fired (group A + g2): 1/2

## Group F (clarification) outcomes

- f1_vague_sick_since_morning: pipeline_status=awaiting_clarification, intake_status=needs_clarification, expected_park=yes, match=True

## Reliability

- Groq/Gemini fallback triggered on: 0/7 cases
- Pipeline degraded (agent failure -> fail-safe) on: 3/7 cases
- Latency: mean 13.25s, median 10.75s, max 25.68s

## Per-case results

| key | group | expected | actual | match | decided_by (exp/act) | latency (s) |
|---|---|---|---|---|---|---|
| a1_chest_pain_dyspnea | A | emergency | emergency | ✓ | rule_override/rule_override | 10.749 |
| a4_infant_meningitis | A | emergency | None | ✗ | rule_override/None | 9.248 |
| c1_child_fast_breathing | C | urgent | urgent | ✓ | llm/failsafe_degraded | 25.644 |
| d3_child_diarrhea_no_dehydration | D | routine | urgent | ✗ | llm/failsafe_degraded | 12.038 |
| e2_romanized_telugu_child_breathing | E | urgent | urgent | ✓ | llm/failsafe_degraded | 25.681 |
| f1_vague_sick_since_morning | F | None | None | ✓ | None/None | 1.163 |
| g1_elderly_chest_pain_alone | G | urgent | emergency | ✗ | llm/llm | 8.257 |

## Caveats for the paper (copy into methodology/limitations verbatim)

- **LLM provider**: this run used `MIRA_LLM_PROVIDER=groq` as primary This is a local-test-only override (mira/llm_client.py:build_default_client), not the documented Sonnet-primary production policy -- do not present these results as representative of Sonnet's reasoning quality without re-running with a real ANTHROPIC_API_KEY.
- **RAG corpus provenance**: mira/knowledge/protocol_corpus/{imnci,nhm,who_chw}.md are explicitly paraphrased placeholder text written to exercise the retrieval mechanism, NOT the licensed IMNCI/NHM/WHO CHW source documents. Any retrieval-quality or citation-accuracy claim in the paper must state this corpus is a stand-in, not the real guideline text.
- **Rule-engine coverage gap**: the red-flag rule engine's tag vocabulary has no tags for pediatric/newborn/dehydration danger signs (no fast_breathing, sunken_eyes, not_feeding_well, etc.), so every IMNCI-grounded child/newborn case in this bank (group C) is decided by the LLM alone, never the deterministic safety net -- a real limitation of the current rule set, not an artifact of this run.
- **Sample provenance**: all 30 cases are synthetic, written for this evaluation (see eval/cases_30.py docstring), not real patient transcripts -- no IRB/DHS-IEC concern for this run, but also not evidence of real-world input distribution beyond what's documented in eval/cases_30.py per case.
- **Expected labels**: expected_final_triage/expected_decided_by per case were authored by us ahead of the run (see eval/cases_30.py), not derived from a clinical reviewer -- per README.md, a clinical co-advisor review of these judgment calls is still outstanding before any pilot or paper claim relies on them as ground truth.