<!--
PLACEHOLDER CORPUS — this is NOT the real National Health Mission (NHM)
protocol document set. It is a short, originally-written stand-in so the
RAG retrieval mechanism (mira/knowledge/rag.py) is testable end to end
before real source-document text is licensed/ingested. Replace this file
with actual NHM protocol content (properly chunked, with attribution)
before any pilot or paper result relies on retrieval quality. Every
paragraph below is a general, publicly-known referral/triage concept
paraphrased in plain language — none of it should be cited as NHM
document text.
-->

## The referral facility ladder

Rural primary care in India is typically organized in tiers: a Sub-Centre
or ASHA-worker level for routine, low-acuity care and follow-up; a Primary
Health Centre (PHC) for cases needing a doctor's evaluation within hours to
a day; a Community Health Centre (CHC) with broader capability for more
involved urgent care; and a District Hospital or higher facility for true
emergencies requiring immediate in-person intervention, ambulance
transport, or specialist care. A triage tool's referral output should map
to this ladder rather than to a single undifferentiated "see a doctor."

## Maternal danger signs warranting immediate referral

Heavy vaginal bleeding (soaking through pads quickly), severe headache
with visual disturbance in pregnancy, convulsions in pregnancy or shortly
after delivery, high fever with foul-smelling discharge after delivery,
and severe abdominal pain in pregnancy are all treated as emergencies
requiring immediate transport to a facility capable of obstetric
emergency care — not a routine antenatal visit.

## Postpartum hemorrhage as a leading cause of maternal mortality

Bleeding after childbirth that soaks more than one pad in fifteen minutes,
or that continues heavily beyond the immediate delivery period, is treated
as a time-critical emergency. Blood loss in this setting can escalate
faster than it may initially appear, so the threshold for "heavy" bleeding
in referral guidance is deliberately conservative rather than requiring a
precise volume estimate from a non-clinical reporter.

## Pre-eclampsia / eclampsia warning pattern

The combination of pregnancy with a severe headache, visual disturbance
(blurred or spotty vision), or pain under the ribs, together with known or
suspected high blood pressure or new swelling (especially of the face or
hands), is a recognized pattern that can progress to seizures (eclampsia)
within hours if untreated. This combination is treated as an emergency
referral regardless of how the pregnancy has progressed otherwise.

## The role of the ASHA worker in the referral chain

An ASHA (Accredited Social Health Activist) worker is typically the first
point of contact in a village and is not expected to make a clinical
diagnosis. Her role is to recognize danger signs using a simple, taught
checklist, communicate what she has observed clearly to the receiving
facility or clinician, and support the family in reaching care promptly.
A decision-support tool used by an ASHA worker should therefore produce
output that is directive and actionable ("go now" / "go within X hours" /
"can wait"), not open-ended clinical reasoning she is not trained to
interpret.

## Why time-to-care windows matter more than diagnostic precision at this level

At the community level, the practical question is rarely "what exact
condition is this" but "how urgently does this person need to reach a
higher level of care." Two different underlying conditions that both
carry a similar near-term risk of deterioration should generally receive
the same urgency-band referral, even if their eventual diagnosis and
treatment differ substantially once the patient reaches a facility with a
clinician.
