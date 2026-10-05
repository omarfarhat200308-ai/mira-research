# MIRA 30-case paper evaluation -- summary

- Run timestamp (UTC): 2026-09-11T20:20:14.025302+00:00
- Git commit: decc25b
- LLM provider path: nvidia
- MIRA_DATA_SOURCE used for run: simulated (doctor-handoff real sends are hard-gated off)
- Cases run: 30 / 30

## Overall triage accuracy

- 10/30 = 33.3% of scorable cases (excludes group F clarification cases, scored separately below)

## Confusion matrix (expected -> actual final_triage)

| expected \\ actual | emergency | urgent | routine | null/other |
|---|---|---|---|---|
| emergency | 4 | 3 | 0 | 5 |
| urgent | 2 | 3 | 0 | 3 |
| routine | 0 | 3 | 1 | 4 |

## Rule-engine vs LLM decision correctness

- decided_by matched expectation: 8/28
- expected specific rule_id fired (group A + g2): 4/10

## Group F (clarification) outcomes

- f1_vague_sick_since_morning: pipeline_status=awaiting_clarification, intake_status=needs_clarification, expected_park=yes, match=True
- f2_missing_severity: pipeline_status=awaiting_clarification, intake_status=needs_clarification, expected_park=yes, match=True
- f3_ambiguous_ok_to_proceed: pipeline_status=degraded, intake_status=complete, expected_park=no, match=False

## Reliability

- Groq/Gemini fallback triggered on: 0/30 cases
- Pipeline degraded (agent failure -> fail-safe) on: 12/30 cases
- Latency: mean 53.40s, median 27.08s, max 183.36s

## Per-case results

| key | group | expected | actual | match | decided_by (exp/act) | latency (s) |
|---|---|---|---|---|---|---|
| a1_chest_pain_dyspnea | A | emergency | None | ✗ | rule_override/None | 28.077 |
| a2_preeclampsia | A | emergency | urgent | ✗ | rule_override/failsafe_degraded | 62.316 |
| a3_postpartum_bleeding | A | emergency | emergency | ✓ | rule_override/rule_override | 93.121 |
| a4_infant_meningitis | A | emergency | urgent | ✗ | rule_override/failsafe_degraded | 26.084 |
| a5_seizure | A | emergency | None | ✗ | rule_override/None | 11.156 |
| a6_stroke | A | emergency | emergency | ✓ | rule_override/rule_override | 122.051 |
| a7_trauma_bleeding | A | emergency | emergency | ✓ | rule_override/rule_override | 115.849 |
| a8_gi_bleeding | A | emergency | None | ✗ | rule_override/None | 12.033 |
| b1_severe_weakness_breathing | B | emergency | urgent | ✗ | llm/failsafe_degraded | 183.363 |
| b2_reduced_fetal_movement | B | urgent | None | ✗ | llm/None | 12.862 |
| c1_child_fast_breathing | C | urgent | urgent | ✓ | llm/failsafe_degraded | 20.229 |
| c2_newborn_not_feeding | C | urgent | emergency | ✗ | llm/llm | 118.402 |
| c3_child_dehydration | C | urgent | urgent | ✓ | llm/failsafe_degraded | 45.889 |
| c4_newborn_breathing | C | emergency | None | ✗ | llm/None | 21.109 |
| c5_chronic_cough_weightloss | C | urgent | None | ✗ | llm/None | 18.981 |
| c6_infant_persistent_fever | C | urgent | emergency | ✗ | llm/llm | 103.421 |
| d1_child_mild_cough | D | routine | urgent | ✗ | llm/failsafe_degraded | 39.423 |
| d2_child_fever_well | D | routine | routine | ✓ | llm/llm | 106.851 |
| d3_child_diarrhea_no_dehydration | D | routine | None | ✗ | llm/None | 8.66 |
| d4_adult_sprain | D | routine | None | ✗ | llm/None | 11.124 |
| d5_adult_sore_throat | D | routine | None | ✗ | llm/None | 18.493 |
| d6_adult_mild_headache | D | routine | urgent | ✗ | llm/failsafe_degraded | 18.707 |
| e1_romanized_hindi_preeclampsia | E | emergency | emergency | ✓ | rule_override/rule_override | 89.349 |
| e2_romanized_telugu_child_breathing | E | urgent | urgent | ✓ | llm/llm | 116.546 |
| e3_romanized_hindi_mild_cold | E | routine | None | ✗ | llm/None | 30.443 |
| f1_vague_sick_since_morning | F | None | None | ✓ | None/None | 15.019 |
| f2_missing_severity | F | None | None | ✓ | None/None | 19.104 |
| f3_ambiguous_ok_to_proceed | F | routine | urgent | ✗ | llm/failsafe_degraded | 107.117 |
| g1_elderly_chest_pain_alone | G | urgent | None | ✗ | llm/None | 16.706 |
| g2_nonpostpartum_heavy_bleeding | G | emergency | None | ✗ | rule_override/None | 9.603 |

## Caveats for the paper (copy into methodology/limitations verbatim)

- **LLM provider**: this run used `MIRA_LLM_PROVIDER=nvidia` as primary This is a local-test-only override (mira/llm_client.py:build_default_client), not the documented Sonnet-primary production policy -- do not present these results as representative of Sonnet's reasoning quality without re-running with a real ANTHROPIC_API_KEY.
- **RAG corpus provenance**: mira/knowledge/protocol_corpus/{imnci,nhm,who_chw}.md are explicitly paraphrased placeholder text written to exercise the retrieval mechanism, NOT the licensed IMNCI/NHM/WHO CHW source documents. Any retrieval-quality or citation-accuracy claim in the paper must state this corpus is a stand-in, not the real guideline text.
- **Rule-engine coverage gap**: the red-flag rule engine's tag vocabulary has no tags for pediatric/newborn/dehydration danger signs (no fast_breathing, sunken_eyes, not_feeding_well, etc.), so every IMNCI-grounded child/newborn case in this bank (group C) is decided by the LLM alone, never the deterministic safety net -- a real limitation of the current rule set, not an artifact of this run.
- **Sample provenance**: all 30 cases are synthetic, written for this evaluation (see eval/cases_30.py docstring), not real patient transcripts -- no IRB/DHS-IEC concern for this run, but also not evidence of real-world input distribution beyond what's documented in eval/cases_30.py per case.
- **Expected labels**: expected_final_triage/expected_decided_by per case were authored by us ahead of the run (see eval/cases_30.py), not derived from a clinical reviewer -- per README.md, a clinical co-advisor review of these judgment calls is still outstanding before any pilot or paper claim relies on them as ground truth.