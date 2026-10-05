# MIRA 30-case paper evaluation -- summary

- Run timestamp (UTC): 2026-09-11T18:18:30.956029+00:00
- Git commit: f4fc9ef
- LLM provider path: groq
- MIRA_DATA_SOURCE used for run: simulated (doctor-handoff real sends are hard-gated off)
- Cases run: 25 / 30

## Overall triage accuracy

- 9/25 = 36.0% of scorable cases (excludes group F clarification cases, scored separately below)

## Confusion matrix (expected -> actual final_triage)

| expected \\ actual | emergency | urgent | routine | null/other |
|---|---|---|---|---|
| emergency | 2 | 2 | 0 | 3 |
| urgent | 0 | 7 | 1 | 0 |
| routine | 0 | 6 | 0 | 2 |

## Rule-engine vs LLM decision correctness

- decided_by matched expectation: 3/23
- expected specific rule_id fired (group A + g2): 1/5

## Group F (clarification) outcomes

- f1_vague_sick_since_morning: pipeline_status=degraded, intake_status=None, expected_park=yes, match=False
- f2_missing_severity: pipeline_status=degraded, intake_status=None, expected_park=yes, match=False
- f3_ambiguous_ok_to_proceed: pipeline_status=degraded, intake_status=None, expected_park=no, match=False

## Reliability

- Groq/Gemini fallback triggered on: 0/25 cases
- Pipeline degraded (agent failure -> fail-safe) on: 17/25 cases
- Latency: mean 23.00s, median 14.77s, max 76.38s

## Per-case results

| key | group | expected | actual | match | decided_by (exp/act) | latency (s) |
|---|---|---|---|---|---|---|
| a6_stroke | A | emergency | None | ✗ | rule_override/None | 5.437 |
| a7_trauma_bleeding | A | emergency | emergency | ✓ | rule_override/rule_override | 75.306 |
| a8_gi_bleeding | A | emergency | None | ✗ | rule_override/None | 9.291 |
| b1_severe_weakness_breathing | B | emergency | emergency | ✓ | llm/llm | 76.014 |
| b2_reduced_fetal_movement | B | urgent | urgent | ✓ | llm/failsafe_degraded | 50.711 |
| c1_child_fast_breathing | C | urgent | routine | ✗ | llm/llm | 76.376 |
| c2_newborn_not_feeding | C | urgent | urgent | ✓ | llm/failsafe_degraded | 28.813 |
| c3_child_dehydration | C | urgent | urgent | ✓ | llm/failsafe_degraded | 14.815 |
| c4_newborn_breathing | C | emergency | urgent | ✗ | llm/failsafe_degraded | 15.055 |
| c5_chronic_cough_weightloss | C | urgent | urgent | ✓ | llm/failsafe_degraded | 14.769 |
| c6_infant_persistent_fever | C | urgent | urgent | ✓ | llm/failsafe_degraded | 14.76 |
| d1_child_mild_cough | D | routine | urgent | ✗ | llm/failsafe_degraded | 14.738 |
| d2_child_fever_well | D | routine | None | ✗ | llm/None | 13.496 |
| d3_child_diarrhea_no_dehydration | D | routine | urgent | ✗ | llm/failsafe_degraded | 14.774 |
| d4_adult_sprain | D | routine | urgent | ✗ | llm/failsafe_degraded | 14.734 |
| d5_adult_sore_throat | D | routine | urgent | ✗ | llm/failsafe_degraded | 14.762 |
| d6_adult_mild_headache | D | routine | None | ✗ | llm/None | 8.151 |
| e1_romanized_hindi_preeclampsia | E | emergency | None | ✗ | rule_override/None | 9.484 |
| e2_romanized_telugu_child_breathing | E | urgent | urgent | ✓ | llm/failsafe_degraded | 14.819 |
| e3_romanized_hindi_mild_cold | E | routine | urgent | ✗ | llm/failsafe_degraded | 14.729 |
| f1_vague_sick_since_morning | F | None | urgent | ✗ | None/failsafe_degraded | 14.734 |
| f2_missing_severity | F | None | urgent | ✗ | None/failsafe_degraded | 14.771 |
| f3_ambiguous_ok_to_proceed | F | routine | urgent | ✗ | llm/failsafe_degraded | 14.899 |
| g1_elderly_chest_pain_alone | G | urgent | urgent | ✓ | llm/failsafe_degraded | 14.731 |
| g2_nonpostpartum_heavy_bleeding | G | emergency | urgent | ✗ | rule_override/failsafe_degraded | 14.925 |

## Caveats for the paper (copy into methodology/limitations verbatim)

- **LLM provider**: this run used `MIRA_LLM_PROVIDER=groq` as primary This is a local-test-only override (mira/llm_client.py:build_default_client), not the documented Sonnet-primary production policy -- do not present these results as representative of Sonnet's reasoning quality without re-running with a real ANTHROPIC_API_KEY.
- **RAG corpus provenance**: mira/knowledge/protocol_corpus/{imnci,nhm,who_chw}.md are explicitly paraphrased placeholder text written to exercise the retrieval mechanism, NOT the licensed IMNCI/NHM/WHO CHW source documents. Any retrieval-quality or citation-accuracy claim in the paper must state this corpus is a stand-in, not the real guideline text.
- **Rule-engine coverage gap**: the red-flag rule engine's tag vocabulary has no tags for pediatric/newborn/dehydration danger signs (no fast_breathing, sunken_eyes, not_feeding_well, etc.), so every IMNCI-grounded child/newborn case in this bank (group C) is decided by the LLM alone, never the deterministic safety net -- a real limitation of the current rule set, not an artifact of this run.
- **Sample provenance**: all 30 cases are synthetic, written for this evaluation (see eval/cases_30.py docstring), not real patient transcripts -- no IRB/DHS-IEC concern for this run, but also not evidence of real-world input distribution beyond what's documented in eval/cases_30.py per case.
- **Expected labels**: expected_final_triage/expected_decided_by per case were authored by us ahead of the run (see eval/cases_30.py), not derived from a clinical reviewer -- per README.md, a clinical co-advisor review of these judgment calls is still outstanding before any pilot or paper claim relies on them as ground truth.