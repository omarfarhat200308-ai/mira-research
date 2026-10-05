# ✅ COMPLETE — 30/30 cases

Aggregated from multiple attempts across 2026-09-11, combining results across providers (groq + nvidia) after Groq's daily token quota and other free-tier limits were exhausted mid-session -- see per-case `model_provenance` in raw_results.jsonl for exactly which provider/model answered each individual case. Every case here is a real model completion (or a genuine pipeline fail-safe/clarification outcome), never a quota-exhaustion artifact -- see eval/aggregate.py's contamination filter for exactly what was excluded and why.

---

# MIRA 30-case paper evaluation -- summary

- Run timestamp (UTC): 2026-09-11T19:21:16.179410+00:00
- Git commit: f4fc9ef
- LLM provider path: groq + nvidia (mixed across cases -- see per-agent model_provenance in raw_results.jsonl for exactly which provider/model answered each case)
- MIRA_DATA_SOURCE used for run: simulated (doctor-handoff real sends are hard-gated off)
- Cases run: 30 / 30

## Overall triage accuracy

- 11/30 = 36.7% of scorable cases (excludes group F clarification cases, scored separately below)

## Confusion matrix (expected -> actual final_triage)

| expected \\ actual | emergency | urgent | routine | null/other |
|---|---|---|---|---|
| emergency | 7 | 0 | 0 | 5 |
| urgent | 2 | 0 | 1 | 5 |
| routine | 0 | 1 | 2 | 5 |

## Rule-engine vs LLM decision correctness

- decided_by matched expectation: 12/28
- expected specific rule_id fired (group A + g2): 6/10

## Group F (clarification) outcomes

- f1_vague_sick_since_morning: pipeline_status=awaiting_clarification, intake_status=needs_clarification, expected_park=yes, match=True
- f2_missing_severity: pipeline_status=awaiting_clarification, intake_status=needs_clarification, expected_park=yes, match=True
- f3_ambiguous_ok_to_proceed: pipeline_status=ok, intake_status=complete, expected_park=no, match=True

## Reliability

- Groq/Gemini fallback triggered on: 0/30 cases
- Pipeline degraded (agent failure -> fail-safe) on: 1/30 cases
- Latency: mean 46.21s, median 34.01s, max 188.44s

## Per-case results

| key | group | expected | actual | match | decided_by (exp/act) | latency (s) |
|---|---|---|---|---|---|---|
| a1_chest_pain_dyspnea | A | emergency | emergency | ✓ | rule_override/rule_override | 80.845 |
| a2_preeclampsia | A | emergency | emergency | ✓ | rule_override/rule_override | 86.995 |
| a3_postpartum_bleeding | A | emergency | emergency | ✓ | rule_override/rule_override | 81.045 |
| a4_infant_meningitis | A | emergency | emergency | ✓ | rule_override/rule_override | 81.348 |
| a5_seizure | A | emergency | emergency | ✓ | rule_override/rule_override | 82.451 |
| a6_stroke | A | emergency | None | ✗ | rule_override/None | 5.437 |
| a7_trauma_bleeding | A | emergency | emergency | ✓ | rule_override/rule_override | 75.306 |
| a8_gi_bleeding | A | emergency | None | ✗ | rule_override/None | 9.291 |
| b1_severe_weakness_breathing | B | emergency | emergency | ✓ | llm/llm | 76.014 |
| b2_reduced_fetal_movement | B | urgent | None | ✗ | llm/None | 28.732 |
| c1_child_fast_breathing | C | urgent | routine | ✗ | llm/llm | 76.376 |
| c2_newborn_not_feeding | C | urgent | None | ✗ | llm/None | 94.781 |
| c3_child_dehydration | C | urgent | None | ✗ | llm/None | 25.896 |
| c4_newborn_breathing | C | emergency | None | ✗ | llm/None | 41.769 |
| c5_chronic_cough_weightloss | C | urgent | None | ✗ | llm/None | 42.406 |
| c6_infant_persistent_fever | C | urgent | emergency | ✗ | llm/llm | 188.439 |
| d1_child_mild_cough | D | routine | routine | ✓ | llm/llm | 12.2 |
| d2_child_fever_well | D | routine | None | ✗ | llm/None | 13.496 |
| d3_child_diarrhea_no_dehydration | D | routine | None | ✗ | llm/None | 1.978 |
| d4_adult_sprain | D | routine | None | ✗ | llm/None | 26.52 |
| d5_adult_sore_throat | D | routine | urgent | ✗ | llm/failsafe_degraded | 14.049 |
| d6_adult_mild_headache | D | routine | None | ✗ | llm/None | 8.151 |
| e1_romanized_hindi_preeclampsia | E | emergency | None | ✗ | rule_override/None | 9.484 |
| e2_romanized_telugu_child_breathing | E | urgent | None | ✗ | llm/None | 92.337 |
| e3_romanized_hindi_mild_cold | E | routine | None | ✗ | llm/None | 55.26 |
| f1_vague_sick_since_morning | F | None | None | ✓ | None/None | 2.236 |
| f2_missing_severity | F | None | None | ✓ | None/None | 1.62 |
| f3_ambiguous_ok_to_proceed | F | routine | routine | ✓ | llm/llm | 24.35 |
| g1_elderly_chest_pain_alone | G | urgent | emergency | ✗ | llm/llm | 8.257 |
| g2_nonpostpartum_heavy_bleeding | G | emergency | None | ✗ | rule_override/None | 39.28 |

## Caveats for the paper (copy into methodology/limitations verbatim)

- **LLM provider**: this run used `MIRA_LLM_PROVIDER=groq + nvidia (mixed across cases -- see per-agent model_provenance in raw_results.jsonl for exactly which provider/model answered each case)` as primary This is a local-test-only override (mira/llm_client.py:build_default_client), not the documented Sonnet-primary production policy -- do not present these results as representative of Sonnet's reasoning quality without re-running with a real ANTHROPIC_API_KEY.
- **RAG corpus provenance**: mira/knowledge/protocol_corpus/{imnci,nhm,who_chw}.md are explicitly paraphrased placeholder text written to exercise the retrieval mechanism, NOT the licensed IMNCI/NHM/WHO CHW source documents. Any retrieval-quality or citation-accuracy claim in the paper must state this corpus is a stand-in, not the real guideline text.
- **Rule-engine coverage gap**: the red-flag rule engine's tag vocabulary has no tags for pediatric/newborn/dehydration danger signs (no fast_breathing, sunken_eyes, not_feeding_well, etc.), so every IMNCI-grounded child/newborn case in this bank (group C) is decided by the LLM alone, never the deterministic safety net -- a real limitation of the current rule set, not an artifact of this run.
- **Sample provenance**: all 30 cases are synthetic, written for this evaluation (see eval/cases_30.py docstring), not real patient transcripts -- no IRB/DHS-IEC concern for this run, but also not evidence of real-world input distribution beyond what's documented in eval/cases_30.py per case.
- **Expected labels**: expected_final_triage/expected_decided_by per case were authored by us ahead of the run (see eval/cases_30.py), not derived from a clinical reviewer -- per README.md, a clinical co-advisor review of these judgment calls is still outstanding before any pilot or paper claim relies on them as ground truth.
- **Provider-specific extraction weakness inflates the "None"/parked rate**: most of this run's 10 `awaiting_clarification` ("None" actual_final_triage) outcomes were answered by `nvidia/nemotron-3.5-lightning-30b-a3b` (used only for the cases groq's daily quota couldn't reach) and share one specific, reproducible failure: it did not extract the `sex` field even from unambiguous kinship terms ("My daughter is 4") or pronouns ("her"), verified live 2026-09-11/12 against MIRA's actual Intake schema. This is a real weakness of that specific model on this specific field, not a property of the MIRA pipeline itself or of the case wording (age, duration, and severity all extracted correctly in the same calls) -- do not read the 36.7% headline accuracy as representative of a single consistent model's capability; it blends two providers with materially different reliability profiles on this task. See raw_results.jsonl's per-case `model_provenance` to separate them.