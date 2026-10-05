# MIRA Clinical Review — Plain-Language Export

> **Note (2026-10-04):** this export was written on 2026-09-12, before any clinical review; its statement that nothing had been clinically reviewed was true then. A partial, non-blind review by one co-author followed (see the v1.3 report). The system has still not been clinically validated.

**What this is:** MIRA is a prototype tool that reads a WhatsApp message from a
patient or caregiver (in rural India) and decides how urgently they need
care, then tells them where to go. This document lays out every piece of
clinical judgment currently built into it, in plain language, so it can be
reviewed by someone with clinical training before it's trusted with real
patients. **Nothing here has been clinically reviewed yet.** Everything
below was written by an engineer (with general medical references) and
needs a clinician's sign-off, correction, or rejection.

**Status:** prototype only. Runs on simulated/scripted conversations. No
real patient data has touched this system. Not connected to real WhatsApp.

---

## 1. How the safety net works

Every message goes through 5 steps:

1. **Intake** — pulls out the basic facts: age, sex, whether the patient is
   pregnant, and what symptoms they're describing (with how long they've
   had them and how bad they are). If key facts are missing, MIRA asks a
   follow-up question instead of guessing — but only asks twice before
   giving up and defaulting to "go to a clinic," so it can't get stuck in
   an endless question loop with someone who can't answer.
2. **Language** — figures out what language the message was in and maps
   the free-text symptoms onto a fixed list of recognized symptoms (see
   Section 3). If a symptom doesn't map cleanly onto the list, it's simply
   not flagged — this is a real limitation, discussed in Section 7.
3. **Diagnostic** — proposes a short list of possible conditions from a
   fixed list (Section 4), just to help judge urgency. It is explicitly
   never allowed to tell the patient "you have X" — see Section 5.
4. **Triage** — decides how urgent the case is: **emergency**, **urgent**,
   or **routine**. This is the most important step. It works in two layers:
   - **Layer 1 — hardcoded rules (Section 2).** A fixed checklist of
     dangerous symptom combinations. If any one of them matches, the case
     is *always* emergency — a computer model's opinion cannot overrule
     this, ever. This layer is plain rules, not AI, specifically so it's
     predictable and can't be talked out of it.
   - **Layer 2 — AI judgment, but only if it's confident.** If none of the
     hardcoded rules fire, the AI's own assessment is used — but only if it
     says it's reasonably confident. If it isn't confident, or gives a
     garbled answer, MIRA doesn't shrug and say "routine" — it bumps the
     urgency up a level instead (routine→urgent, or urgent/unclear→emergency).
     The system is deliberately built to over-worry rather than
     under-worry when it's unsure.
5. **Referral** — turns the urgency level into a plain instruction: which
   type of facility to go to and how soon (Section 6). It is never allowed
   to name a drug or a dose — see Section 5.

If any step breaks, times out, or produces something malformed, MIRA does
not guess — it falls back to one fixed message: *"We were not able to
complete a full assessment. To be safe, please go to your nearest clinic or
health facility as soon as possible so a health worker can examine the
patient in person."* This is literal fixed text, not AI-generated, and it's
the same message every time regardless of the failure.

---

## 2. The hardcoded red-flag rules (the part that can't be overruled)

These are the only things in MIRA that are *guaranteed* to trigger
"emergency" no matter what the AI thinks. **This is the highest-priority
section to review** — everything else is a judgment aid, this is the
actual safety guarantee.

| # | Fires when... | Why it's here |
|---|---|---|
| 1 | Chest pain **and** shortness of breath | Classic pattern for a heart attack or blood clot in the lung; time to treatment matters a lot. |
| 2 | Patient is pregnant **and** has (severe headache **or** blurry/disturbed vision **or** pain under the ribs) **and** (known/suspected high blood pressure **or** swelling) | Classic warning pattern for pre-eclampsia/eclampsia — can progress to seizures and death within hours if untreated. |
| 3 | Heavy vaginal bleeding, or heavy bleeding after childbirth | Obstetric hemorrhage is a leading cause of maternal death and can worsen very fast. |
| 4 | Baby under 2 years old **and** has (fever or high fever) **and** (stiff neck or bulging soft spot on the head) | Classic infant meningitis warning signs; infants decline faster than adults. |
| 5 | Seizure, or loss of consciousness | Could mean a serious brain, metabolic, or heart problem — treated as emergency by default pending in-person exam. |
| 6 | One-sided weakness, or slurred speech | Possible stroke; the treatment window is narrow. |
| 7 | Heavy external bleeding, OR (an injury **and** a suspected fracture together) | Risk of shock from blood loss. |
| 8 | Vomiting blood, or black/bloody stool | Signs of internal bleeding in the gut; can be life-threatening. |

**Known gap, flagged for review:** this list is a first pass and is *not*
claimed to be exhaustive. Things like diabetic emergencies, poisoning,
severe allergic reaction/anaphylaxis, breathing difficulty in a child
without a fever, or dehydration severe enough to be an emergency in a
young child are **not currently on this list** and would currently rely on
the AI's own judgment rather than a hardcoded guarantee. Whether to add
rules for these (and what the exact trigger conditions should be) is a
clinical call.

---

## 3. Symptoms MIRA can currently recognize

The Language step can only tag a message with symptoms from this fixed
list (43 total, `mira/knowledge/symptom_tags.py`) — anything a patient
says that doesn't match one of these is effectively invisible to the rules
above. Grouped for readability:

- **Heart / breathing:** chest pain, shortness of breath, palpitations,
  cough, coughing up blood
- **Brain / nerve:** severe headache, visual disturbance, seizure, loss of
  consciousness, confusion, stiff neck, bulging soft spot (infants),
  one-sided weakness, slurred speech
- **Stomach / gut:** abdominal pain, pain under the ribs, vomiting,
  vomiting blood, diarrhea, black or bloody stool
- **Pregnancy / childbirth:** pregnant, heavy vaginal bleeding, heavy
  bleeding after birth, reduced baby movement, labor pain
- **General / infection:** fever, high fever, chills, rash, swelling,
  known/suspected high blood pressure, weight loss, fatigue, signs of
  dehydration
- **Injury / bleeding:** heavy external bleeding, injury/trauma, burn,
  suspected fracture, sprain/strain
- **Minor:** joint pain, sore throat, runny nose, mild pain

**Question for reviewer:** does this list miss anything commonly seen in
this population that should route into the rules above (e.g. specific
diabetic, allergic, or pediatric respiratory-distress symptoms)?

---

## 4. Conditions MIRA can consider (for urgency estimation only)

The Diagnostic step can only pick from this fixed list — it can't invent a
new condition name. Each has a "typical urgency" used only as a starting
point; the actual decision still goes through the rules and confidence
check in Section 1.

**Treated as typically emergency:** heart attack/acute coronary syndrome,
pre-eclampsia/eclampsia, bleeding after childbirth, infant meningitis,
stroke, gut bleeding, severe trauma, suspected sepsis (whole-body
infection response).

**Treated as typically urgent:** pneumonia, suspected tuberculosis,
moderate-to-severe dehydration, urinary tract infection, skin
infection/cellulitis, gastroenteritis, uncontrolled high blood pressure.

**Treated as typically routine:** common cold/viral upper respiratory
infection, minor muscle/joint strain, mild localized pain, seasonal
allergy, unspecified mild symptoms.

**Question for reviewer:** is 20 conditions too narrow, and does the
emergency/urgent/routine grouping above match clinical reality for this
setting?

---

## 5. What MIRA is never allowed to say

Two automatic text filters exist independent of anything the AI is told to
do — if AI output matches these, it's rejected and MIRA falls back to safe
text rather than sending it to a patient:

- **Never a diagnosis.** Phrases like "you have X," "she has developed X,"
  "this is a case of X," "diagnosed with," "confirmed to be," "suffering
  from" are all blocked. The system may only say things like "consistent
  with X" or "raises concern for X" — never a definitive statement.
- **Never a drug or dose.** Any mention of a medicine (a list of ~24 common
  drug names like paracetamol, ibuprofen, amoxicillin, ORS, insulin, etc.),
  any dosage language (mg, ml, tablet, "twice a day"), or even a treatment
  category ("take an antibiotic," "use a painkiller") is blocked. MIRA only
  ever says *where* to go, never *what* to take.

**Question for reviewer:** is the drug-name list (Section 8) missing
anything commonly relevant in this setting?

---

## 6. Where MIRA tells people to go

|Urgency|Where|Message|
|---|---|---|
|Emergency|Emergency dept / ambulance / district hospital|"Immediate in-person emergency care — call for ambulance transport if available, otherwise go now, do not wait."|
|Urgent|Community Health Centre or nearest Primary Health Centre with a doctor|"Should be seen by a health worker within the next few hours to a day — do not wait for symptoms to worsen."|
|Routine|Primary Health Centre / Sub-centre / ASHA worker follow-up|"Can be seen at the next routine opportunity; seek care sooner if symptoms worsen."|

---

## 7. Confidence thresholds (how cautious the AI layer is)

- Triage: if the AI says it's less than **60% confident**, its answer isn't
  trusted at face value — the case gets bumped up a level instead.
- Diagnostic: if the AI is less than **50% confident** in its differential,
  that's flagged in the log (for later review) but doesn't block anything
  by itself — Triage doesn't require diagnostic certainty to run.
- A patient gets at most **2 follow-up questions** before MIRA stops asking
  and defaults to "go to a clinic."
- Every agent has a **20-second** timeout; a hang is treated exactly like a
  failure (safe fallback).

**Question for reviewer:** are 60%/50% the right thresholds, or too
permissive/strict for this use case?

---

## 8. Test cases used to exercise the system so far (not clinical validation)

Two separate case sets exist, serving different purposes:

**(a) `tests/fixtures/cases.py`** — 8 cases with scripted, deterministic AI
responses, run on every code change to catch regressions. Fast, free,
always the same answer — good for "did we break something," not useful for
judging real AI reasoning quality. Includes the pre-eclampsia case flagged
below.

**(b) `eval/cases_30.py`** — **this is the one that needs your review.** 30
synthetic cases run through the *real* AI (not scripted), specifically
built for evaluating whether MIRA's reasoning is any good, and what its
weak spots are. Every case is written to test a specific rule, protocol
concept, or edge case — see each case's `source_protocol` field for exactly
which section of Section 2/our reference material it's checking. Full
results: `eval/results/final/summary.md` (human-readable) and
`eval/results/final/raw_results.jsonl` (complete audit trail per case —
what MIRA extracted, which rule fired if any, latency, which AI model
answered).

**→ A companion spreadsheet, `docs/clinical_review_worksheet.csv`, has all
30 cases already filled in with the patient message, our expected answer,
and MIRA's actual answer — three blank columns are yours to fill in:
agree/disagree/uncertain, what you think the correct triage is if you
disagree, and any comments.** Please don't feel obligated to write
anything for a case where you simply agree — the disagreements and
uncertain calls are what matters most here.

> **Superseded (2026-10-04, v1.3 report):** the "11/30" below combines 9 tier agreements with 2 appropriate clarification stops and is **not** an accuracy estimate. The characterization of stopped cases as "correctly pausing" is withdrawn: 17 of 30 cases stopped at Intake, none reached Triage, and none received a safety or referral message. Treat the paragraph below as historical.

**Headline result (2026-09-12 run, not yet clinically validated; corrected
2026-09-19):** 11/30 cases matched our expected label exactly (36.7%). Of
the 8 hardcoded emergency rules (Section 2 — the part that *can't* be
overruled by AI judgment), **6 of 8 fired correctly on their target case;
the other 2 (stroke pattern, GI bleeding) never reached the rule engine at
all** — Intake parked both cases asking for a missing field before triage
ran, so the rule itself was never exercised on those two cases in this run
(see `a6_stroke` / `a8_gi_bleeding` in `eval/results/final/raw_results.jsonl`;
an earlier version of this document incorrectly said all 8 fired). The
rule logic for both patterns passes its unit tests in isolation
(`tests/test_red_flags.py`) — this is specifically an end-to-end gap, not
evidence the rule logic itself is wrong. Most of the other "misses" were
MIRA correctly pausing to ask a clarifying question rather than giving a
wrong answer — one specific AI model we used for part of this run kept
failing to figure out a patient's sex even when it was stated plainly ("my
daughter"), which inflated that number; full explanation in
`eval/results/final/summary.md`'s caveats section.

**Update (2026-09-12) on the pre-eclampsia case (in the 8-case regression
set, `tests/fixtures/cases.py`):** the real hackathon transcript has been
recovered from github.com/omarfarhat200308-ai/tabib-v1 (the original TABIB
project) and now replaces the reconstructed placeholder that stood in for
it. The real transcript is: *"35 year old pregnant woman, 8 months
pregnant. High fever since 2 days, severe headache, swelling on face and
hands. No fetal movement since morning."* — notably different from the
placeholder it replaces: it includes a high fever and explicit absent
fetal movement (neither in the placeholder), and does NOT mention blurred
vision or epigastric pain (which the placeholder had invented). Please
review this real transcript's handling specifically — it still triggers
MIRA's pre-eclampsia rule (severe headache + swelling), but the absent
fetal movement is a second, independent danger sign the current rule
engine has no dedicated trigger for (see `eval/cases_30.py`'s
`b2_reduced_fetal_movement` case, which surfaces the same gap). (The
30-case set has its own, differently-worded pre-eclampsia case, also
synthetic — see `a2_preeclampsia` and `e1_romanized_hindi_preeclampsia`
in the worksheet.)

**Question for reviewer:** beyond filling in the worksheet — do the 30
cases cover the right ground, or are there other borderline cases
(routine-that's-actually-urgent, or urgent-that's-actually-routine) worth
adding specifically because they're easy to get wrong?

---

## 9. Full drug/dosage word list currently blocked

paracetamol, acetaminophen, ibuprofen, aspirin, amoxicillin, azithromycin,
ciprofloxacin, metronidazole, ORS, ondansetron, domperidone, cetirizine,
prednisolone, insulin, metformin, amlodipine, atenolol, losartan,
diazepam, artesunate, chloroquine, doxycycline, rifampicin, isoniazid —
plus generic dosage words (mg, ml, tablet, capsule, dose, "twice a day,"
syrup, injection, IV fluids) and treatment-category words (antibiotics,
painkillers, ointment, antacids).

---

## 10. Summary of open questions for the reviewer

1. Are the 8 hardcoded emergency rules (Section 2) complete enough, or are
   there other dangerous combinations that must never depend on AI
   judgment alone?
2. Does the symptom list (Section 3) miss anything important for this
   population?
3. Is the 20-condition list and its urgency grouping (Section 4) accurate?
4. Are the 60%/50% confidence thresholds (Section 7) appropriately
   cautious?
5. Do the 6 test cases (Section 8) have the right expected answers, and
   what other borderline cases should be added?
6. Is the drug/dosage blocklist (Section 9) missing anything relevant
   locally?
7. The real pre-eclampsia transcript has been recovered (Section 8 update
   above) — does MIRA's current handling of it (and the "no fetal
   movement" coverage gap it exposes) look right to you?
8. **`docs/clinical_review_worksheet.csv`** — the 30-case evaluation
   spreadsheet described in Section 8: for each case, do you agree with
   MIRA's actual answer? If not, what should it have been?

Nothing in this system goes live with real patients until these questions
have answers.
