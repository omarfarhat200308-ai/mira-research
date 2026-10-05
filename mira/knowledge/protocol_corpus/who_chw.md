<!--
PLACEHOLDER CORPUS — this is NOT the real WHO community health worker (CHW)
guideline document. It is a short, originally-written stand-in so the RAG
retrieval mechanism (mira/knowledge/rag.py) is testable end to end before
real source-document text is licensed/ingested. Replace this file with
actual WHO CHW guideline content (properly chunked, with attribution)
before any pilot or paper result relies on retrieval quality. Every
paragraph below is a general, publicly-known community-health-worker
triage concept paraphrased in plain language — none of it should be cited
as WHO guideline text.
-->

## Scope of practice for a non-clinician triage tool

Guidance aimed at community health workers is deliberately bounded: it
supports recognition and referral decisions, not diagnosis or treatment
selection. A digital tool built for this role should mirror that
boundary — producing a referral urgency and a facility direction, never a
named condition presented as fact or a medication recommendation, since
neither the CHW nor the tool is positioned to safely make that call
without an in-person clinical exam.

## Erring toward caution under uncertainty

When information reported by a caregiver is incomplete or ambiguous — for
example, a vague description of "sick since morning" with no further
detail — CHW-facing guidance consistently favors asking a clarifying
question or defaulting to a more urgent referral band, rather than
defaulting to "not serious." The asymmetry is deliberate: the cost of an
unnecessary clinic visit is far lower than the cost of missing a
deteriorating case.

## Danger signs that generalize across age groups

Certain signs are treated as high-priority regardless of the specific
illness suspected: seizures or loss of consciousness, inability to
drink or keep anything down, severe or unusual weakness, difficulty
breathing at rest, heavy uncontrolled bleeding from any source, and skin
or lips that appear unusually pale or blue. A rule-based safety layer that
checks for these signs independently of any single free-text symptom
description is a recommended pattern precisely because caregivers may not
volunteer them unprompted.

## Communication design for low-literacy, field-based users

Guidance intended for a CHW working in the field, often without reliable
connectivity or extended reading time, should be short, use plain
non-technical language, state the action clearly before the reasoning,
and avoid jargon that requires clinical training to interpret. Voice
delivery, where available, should be understandable well within the time
a busy field worker can realistically spend listening to a single message.

## Escalation pathways and follow-up accountability

Where a referral is made, guidance recommends that the referring worker
have a way to confirm the case was actually seen, and that the receiving
facility have enough context (what was observed, when, by whom) to act
efficiently without re-collecting the same history from scratch. A digital
tool that automates the CHW-to-facility handoff should preserve this
continuity-of-care information rather than leaving it to verbal recall.

## Consent and appropriate use of patient information

Even in a low-resource field setting, guidance is consistent that a
patient or caregiver should understand, in plain language, what
information is being collected, who it will be shared with (including a
receiving clinician if referred), and for what purpose, with an
opportunity to decline. This does not need to slow down urgent care, but
it does mean consent language should be specific about each distinct use
of the data rather than a single blanket statement.
