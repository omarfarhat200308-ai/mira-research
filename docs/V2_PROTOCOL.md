# MIRA v2 evaluation protocol (DRAFT, to be frozen and timestamped BEFORE any v2 run)

Status: draft written 2026-10-08. Nothing below has been run. This document is
the pre-registration: once frozen (git tag + Zenodo/OSF timestamp) it may not be
edited except by dated amendment.

## 0. Why v2 exists
v1.3 reported honestly that 17/30 synthetic cases stopped at the Intake gate and
received no safety message, and that tier agreement was 1/13 (explicit) to 8/23
(inferred) against a single non-blind rater who is a co-author's relative. v1.3
cannot support any accuracy or safety claim. v2 is designed so that it can fail.

## 1. System change under test (already implemented, LLM-free tests in repo)
* `mira/safety/precheck.py`: deterministic text screen reusing the existing 8 rules.
* `pipeline.py`: a halted case now returns a safety message (EMERGENCY text if the
  screen fires, else a generic danger-sign line + the clarifying question); a failed
  stage degrades to EMERGENCY (not URGENT) if the screen fires.
* Known limits: keyword recall is incomplete (replay on the v1 set: 9/12 emergency
  cases caught, 0/18 non-emergency flagged; that set is a DEVELOPMENT set because the
  patterns were written while it was visible, so these numbers are NOT evidence).
  Romanized Hindi/Telugu terms are unreviewed by a native-speaking clinician.

## 2. Case set (held out)
* N >= 60 cases (draft packets in docs/v2_cases/; pediatric 20, obstetric 20, general medicine 20 to come), written or sourced BEFORE freeze, never viewed during any code change after freeze.
* Source: >= 50% from external material not authored by the first author (public
  IMNCI/WHO CHW/NHM scenario banks, published vignettes with citation, or cases
  written by a clinician who does not see the system). First-author-written cases
  allowed up to 50% and flagged as such.
* Strata: adult emergency, obstetric, pediatric/newborn, benign/self-care,
  incomplete-information (missing age/sex/duration), romanized Hindi, romanized
  Telugu, English, code-mixed. >= 8 cases per stratum where feasible.
* Reference label: consensus tier (Emergency / Urgent / Routine) by raters below;
  disagreements resolved by discussion, original ratings retained and published.
* Case files are frozen as a hashed bundle (SHA-256 published in the registration).

## 3. Raters
* >= 3 licensed clinicians, none related to the first author. Co-authors who are not relatives may rate if
  disclosed, and a sensitivity analysis excludes co-author raters. The first author's mother does NOT rate.
* Specialty coverage: general medicine (adult cases), pediatrics (child/newborn), obstetrics-gynaecology
  (maternal); each case set is rated by the matching specialist, adult cases by general medicine.
* Credentials of each rater are stated in the report, with permission.
* Blind to system output and to each other. Rate from case text only.
* Report inter-rater agreement (Fleiss kappa, with CI) BEFORE comparing to system.
* If recruitment of >= 3 external raters fails, v2 reports "unrated" and makes no
  accuracy claim; it does not fall back to family raters.

## 4. Systems compared (same cases, same temperature/seed policy)
1. MIRA-v2 (this repo, tagged commit).
2. MIRA-v1.3 behavior (pre-patch commit 78931e6) to isolate the patch.
3. Single-prompt LLM baseline (one call, same base model, fixed documented prompt).
4. Rules-only baseline (precheck + 8 rules, default to Urgent when no rule fires).
5. Trivial baseline: always-Urgent.
For every system, log model ID, provider, date, full prompt text, sampling settings,
and raw outputs (the v1.3 gaps). No retrospective selection of attempts: every run
counts; infrastructure failures are reported as failures, not re-rolled.

## 5. Clarification handling
Cases with missing fields are scored in two modes: (a) one-shot (system output after
the first message, including the interim safety message) and (b) simulated-reply, where
a scripted answer is supplied. Primary analysis is (a), since a real sender may never reply.

## 6. Primary outcomes (pre-specified)
P1. Under-triage rate on reference-Emergency cases: system tier < Emergency. 
    Report count/n with Wilson 95% CI. This is the safety-critical number.
P2. Over-triage rate on reference-Routine cases.
P3. No-decision rate: cases ending with no tier AND no safety message (target 0).
Secondary: weighted kappa vs consensus; per-stratum results; latency; cost per case;
red-flag-rule firing vs reference; language-stratum gap (English vs romanized).

## 7. Decision rules (set now)
* MIRA-v2 is called "not worse than baselines on safety" only if P1 upper CI bound <=
  that of the single-prompt baseline AND P3 = 0. Otherwise report as failing.
* No claim of clinical validity, safety, or readiness for deployment is made from
  this study regardless of result; at best it supports "performed X on a retrospective
  synthetic benchmark".
* Negative or mixed results are published with the same prominence.

## 8. Ethics and honesty
* No real patient data. Any future pilot requires institutional ethics approval
  (IEC/DHS) before data collection; this protocol does not substitute for it.
* Disclose authors' relationships, AI-assistance, and that the first author is a
  high-school-age independent researcher.
* Do not tune prompts, rules, or keyword lists on the held-out set. Any change after
  freeze creates a new version and re-runs everything.

## 9. Amendment log
(empty)
