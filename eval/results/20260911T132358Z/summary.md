# MIRA 30-case paper evaluation -- summary

- Run timestamp (UTC): 2026-09-11T13:39:10.778195+00:00
- Git commit: f4fc9ef
- LLM provider path: groq
- MIRA_DATA_SOURCE used for run: simulated (doctor-handoff real sends are hard-gated off)
- Cases run: 30 / 30

## Overall triage accuracy

- 12/30 = 40.0% of scorable cases (excludes group F clarification cases, scored separately below)

## Confusion matrix (expected -> actual final_triage)

| expected \\ actual | emergency | urgent | routine | null/other |
|---|---|---|---|---|
| emergency | 5 | 4 | 0 | 3 |
| urgent | 0 | 7 | 0 | 1 |
| routine | 0 | 8 | 0 | 0 |

## Rule-engine vs LLM decision correctness

- decided_by matched expectation: 5/28
- expected specific rule_id fired (group A + g2): 5/10

## Group F (clarification) outcomes

- f1_vague_sick_since_morning: pipeline_status=degraded, intake_status=None, expected_park=yes, match=False
- f2_missing_severity: pipeline_status=degraded, intake_status=None, expected_park=yes, match=False
- f3_ambiguous_ok_to_proceed: pipeline_status=degraded, intake_status=None, expected_park=no, match=False

## Reliability

- Groq/Gemini fallback triggered on: 0/30 cases
- Pipeline degraded (agent failure -> fail-safe) on: 21/30 cases
- Latency: mean 25.57s, median 14.75s, max 87.00s

## Per-case results

| key | group | expected | actual | match | decided_by (exp/act) | latency (s) |
|---|---|---|---|---|---|---|
| a1_chest_pain_dyspnea | A | emergency | emergency | ✓ | rule_override/rule_override | 80.845 |
| a2_preeclampsia | A | emergency | emergency | ✓ | rule_override/rule_override | 86.995 |
| a3_postpartum_bleeding | A | emergency | emergency | ✓ | rule_override/rule_override | 81.045 |
| a4_infant_meningitis | A | emergency | emergency | ✓ | rule_override/rule_override | 81.348 |
| a5_seizure | A | emergency | emergency | ✓ | rule_override/rule_override | 82.451 |
| a6_stroke | A | emergency | None | ✗ | rule_override/None | 9.445 |
| a7_trauma_bleeding | A | emergency | None | ✗ | rule_override/None | 9.14 |
| a8_gi_bleeding | A | emergency | None | ✗ | rule_override/None | 9.07 |
| b1_severe_weakness_breathing | B | emergency | urgent | ✗ | llm/failsafe_degraded | 14.755 |
| b2_reduced_fetal_movement | B | urgent | None | ✗ | llm/None | 16.321 |
| c1_child_fast_breathing | C | urgent | urgent | ✓ | llm/failsafe_degraded | 14.802 |
| c2_newborn_not_feeding | C | urgent | urgent | ✓ | llm/failsafe_degraded | 14.751 |
| c3_child_dehydration | C | urgent | urgent | ✓ | llm/failsafe_degraded | 14.741 |
| c4_newborn_breathing | C | emergency | urgent | ✗ | llm/failsafe_degraded | 14.751 |
| c5_chronic_cough_weightloss | C | urgent | urgent | ✓ | llm/failsafe_degraded | 14.735 |
| c6_infant_persistent_fever | C | urgent | urgent | ✓ | llm/failsafe_degraded | 14.731 |
| d1_child_mild_cough | D | routine | urgent | ✗ | llm/failsafe_degraded | 14.8 |
| d2_child_fever_well | D | routine | urgent | ✗ | llm/failsafe_degraded | 15.155 |
| d3_child_diarrhea_no_dehydration | D | routine | urgent | ✗ | llm/failsafe_degraded | 14.791 |
| d4_adult_sprain | D | routine | urgent | ✗ | llm/failsafe_degraded | 14.774 |
| d5_adult_sore_throat | D | routine | urgent | ✗ | llm/failsafe_degraded | 14.729 |
| d6_adult_mild_headache | D | routine | urgent | ✗ | llm/failsafe_degraded | 14.769 |
| e1_romanized_hindi_preeclampsia | E | emergency | urgent | ✗ | rule_override/failsafe_degraded | 14.741 |
| e2_romanized_telugu_child_breathing | E | urgent | urgent | ✓ | llm/failsafe_degraded | 14.903 |
| e3_romanized_hindi_mild_cold | E | routine | urgent | ✗ | llm/failsafe_degraded | 14.739 |
| f1_vague_sick_since_morning | F | None | urgent | ✗ | None/failsafe_degraded | 14.753 |
| f2_missing_severity | F | None | urgent | ✗ | None/failsafe_degraded | 14.744 |
| f3_ambiguous_ok_to_proceed | F | routine | urgent | ✗ | llm/failsafe_degraded | 14.743 |
| g1_elderly_chest_pain_alone | G | urgent | urgent | ✓ | llm/failsafe_degraded | 14.754 |
| g2_nonpostpartum_heavy_bleeding | G | emergency | urgent | ✗ | rule_override/failsafe_degraded | 14.752 |

## Caveats for the paper (copy into methodology/limitations verbatim)

- **LLM provider**: this run used `MIRA_LLM_PROVIDER=groq` as primary This is a local-test-only override (mira/llm_client.py:build_default_client), not the documented Sonnet-primary production policy -- do not present these results as representative of Sonnet's reasoning quality without re-running with a real ANTHROPIC_API_KEY.
- **RAG corpus provenance**: mira/knowledge/protocol_corpus/{imnci,nhm,who_chw}.md are explicitly paraphrased placeholder text written to exercise the retrieval mechanism, NOT the licensed IMNCI/NHM/WHO CHW source documents. Any retrieval-quality or citation-accuracy claim in the paper must state this corpus is a stand-in, not the real guideline text.
- **Rule-engine coverage gap**: the red-flag rule engine's tag vocabulary has no tags for pediatric/newborn/dehydration danger signs (no fast_breathing, sunken_eyes, not_feeding_well, etc.), so every IMNCI-grounded child/newborn case in this bank (group C) is decided by the LLM alone, never the deterministic safety net -- a real limitation of the current rule set, not an artifact of this run.
- **Sample provenance**: all 30 cases are synthetic, written for this evaluation (see eval/cases_30.py docstring), not real patient transcripts -- no IRB/DHS-IEC concern for this run, but also not evidence of real-world input distribution beyond what's documented in eval/cases_30.py per case.
- **Expected labels**: expected_final_triage/expected_decided_by per case were authored by us ahead of the run (see eval/cases_30.py), not derived from a clinical reviewer -- per README.md, a clinical co-advisor review of these judgment calls is still outstanding before any pilot or paper claim relies on them as ground truth.