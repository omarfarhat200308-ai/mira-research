# MIRA 30-case paper evaluation

This directory is the eval harness for the paper's 30-case run, separate
from `tests/` (the mocked-LLM regression suite that gives fast, free,
reproducible CI). Everything in here makes real LLM calls and costs real
time/API usage.

## Files

- `cases_30.py` — the 30 raw patient-message cases plus our expected
  `final_triage`/`triage_decided_by` labels. Each case names the specific
  `mira/knowledge/protocol_corpus/*.md` paragraph it's grounded in.
- `run_eval.py` — runs the cases through `mira.pipeline.run_pipeline` with
  whatever real client `build_default_client()` resolves to from the
  current `.env`, and writes `results/<timestamp>/raw_results.jsonl` +
  `summary.md`.

## Run it

```bash
cd ~/mira
source .venv/bin/activate
python -m eval.run_eval --limit 2      # smoke test first — 2 cases, real API calls
python -m eval.run_eval                # full 30-case run
```

Every case runs with `data_source=DataSource.SIMULATED`, which hard-gates
`mira/notifications/doctor_handoff.py`'s real-send path closed — this
cannot page a real doctor's WhatsApp regardless of triage outcome. It's
still a real LLM run: expect on the order of 100–150 real API calls total
(each case makes 4–5 agent calls), so re-running the full 30 repeatedly
has a real (if small) cost.

## What must go in the paper's methodology/limitations section

These are not optional footnotes — each is a specific, verified gap
between what this run demonstrates and what the paper's framing (Sonnet-
primary, RAG-grounded against IMNCI/NHM/WHO CHW guidance) claims:

1. **LLM provider used for this run is not Claude Sonnet.** No
   `ANTHROPIC_API_KEY` is configured; `.env` sets
   `MIRA_LLM_PROVIDER=groq`, which `mira/llm_client.py:build_default_client`
   explicitly logs as *"a local-test-only override... do not treat this
   run's reasoning quality as representative of Sonnet."* If the paper
   reports these numbers as characterizing MIRA's intended architecture,
   that's inaccurate; report them as characterizing this specific
   Groq-backed configuration, or re-run with a real Anthropic key first.
2. **The RAG corpus was author-written placeholder text at evaluation time,
   and it is the corpus included in this release.** Every file in
   `mira/knowledge/protocol_corpus/` opens with a comment stating it's
   originally-written paraphrase, "NOT the real IMNCI/NHM/WHO CHW [...]
   document." The 30 cases were deliberately written to align with specific
   paragraphs in that placeholder corpus (see each case's `source_protocol`
   field) so retrieval mechanics and citation traceability can be evaluated
   — this tests the *mechanism*, not agreement with any published guidance.
   The corpus carries no clinical authority and implies no WHO, NHM, or
   IMNCI validation.
3. **The rule-engine safety net doesn't cover pediatric/newborn/
   dehydration danger signs.** `mira/knowledge/symptom_tags.py`'s closed
   vocabulary has no tags for signs like fast breathing, sunken eyes, or
   poor feeding, so `mira/safety/red_flags.py`'s 8 hardcoded rules can
   never fire for any IMNCI-style child/newborn case (group C in
   `cases_30.py`) — those are decided by the LLM alone. This is a real,
   pre-existing gap in the current rule set (not caused by this
   evaluation) and is worth reporting as future clinical-review work.
4. **All 30 cases are synthetic**, authored for this evaluation, not real
   patient transcripts or the (still-missing) real pre-eclampsia hackathon
   transcript referenced in the main README. No IRB/DHS-IEC concern
   applies to this run, but the cases should not be presented as a sample
   of real-world input distribution.
5. **Expected labels are author-assigned, not clinically adjudicated.**
   Per the main README, a clinical co-advisor review of the red-flag
   rules, confidence floors, and (once real) corpus content is still
   outstanding. Treat `expected_final_triage` in `cases_30.py` as a
   reasonable-effort baseline for measuring pipeline consistency, not as
   validated clinical ground truth, until that review happens.

`run_eval.py`'s `summary.md` output restates items 1–5 automatically at
the bottom of every run so they can't be silently left out when pulling
numbers into the paper.
