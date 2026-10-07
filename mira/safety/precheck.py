"""
Deterministic, LLM-free emergency pre-screen on the raw message.

Why this exists: in v1.3 the eight red-flag rules ran only at the Triage
stage, on tags produced by the Language agent AFTER Intake. A message that
Intake stopped for a missing field (17/30 synthetic cases) therefore got a
clarifying question and no safety message at all, even when it described an
obvious emergency. This module closes that gap conservatively:

* It works on text only (no model call, no network), so it runs even if
  every LLM provider is down.
* It emits tags from the closed vocabulary in mira/knowledge/symptom_tags.py
  and reuses the SAME rule list (mira/safety/red_flags.py) -- no second,
  divergent rule set.
* It is deliberately over-sensitive (a false emergency costs a clinic
  visit; a missed one can cost a life). It only ever ESCALATES.

Scope, stated honestly: keyword matching over a small curated list of
English plus romanized Hindi/Telugu phrases. It will miss paraphrases,
misspellings and other languages. The romanized terms were written by the
first author and are NOT yet reviewed by a native-speaking clinician;
treat the list as provisional (see docs/V2_PROTOCOL.md). It is a safety
net under the pipeline, not a triage model.
"""
from __future__ import annotations

import re

from ..knowledge.symptom_tags import SYMPTOM_TAGS
from .red_flags import evaluate_red_flags

# tag -> regex fragments (matched case-insensitively on word-ish boundaries).
_PATTERNS: dict[str, list[str]] = {
    "chest_pain": [
        r"chest\s+(pain|tightness|pressure)", r"pain\s+in\s+(the\s+)?chest",
        r"seene\s+(me|mein|mai)\s+(dard|jakdan)", r"gundelo\s+noppi", r"chhati\s+(me|mein)\s+dard",
    ],
    "shortness_of_breath": [
        r"short(ness)?\s+of\s+breath", r"can'?t\s+breathe", r"cannot\s+breathe",
        r"difficulty\s+(in\s+)?breathing", r"breathless", r"struggling\s+to\s+breathe",
        r"saans\s+(lene\s+)?(me|mein|mai)?\s*(takleef|dikkat|phool)", r"saans\s+nahi",
        r"oopiri\s+(ada|tiyyadam)", r"oopiri\s+teesukovadam\s+kashtam",
    ],
    "seizure": [
        r"seizure", r"convulsion", r"\bfits\b", r"\bfitting\b", r"\bdaura\b", r"mirgi", r"\bmoorcha\b",
    ],
    "loss_of_consciousness": [
        r"unconscious", r"not\s+responding", r"unresponsive", r"passed\s+out", r"fainted",
        r"collapsed", r"behosh", r"hosh\s+nahi", r"spruha\s+lekunda", r"spruha\s+ledu",
    ],
    "one_sided_weakness": [
        r"one[-\s]sided\s+weakness", r"(one|left|right)\s+side.{0,25}(weak|numb|paraly)",
        r"(face|arm|leg).{0,20}(drooping|droop)", r"lakwa", r"paralysis",
    ],
    "slurred_speech": [r"slurred\s+speech", r"speech\s+is\s+slurred", r"cannot\s+speak", r"can'?t\s+speak"],
    "vaginal_bleeding_heavy": [
        r"heavy\s+(vaginal\s+)?bleeding", r"bleeding\s+(a\s+lot|heavily|too\s+much|non[-\s]?stop)",
        r"soaking\s+(through\s+)?(pads?|cloth)", r"bahut\s+khoon",
    ],
    "postpartum_bleeding_heavy": [
        r"(after|post).{0,15}(delivery|birth|childbirth).{0,40}bleed",
        r"bleed.{0,40}(after|post).{0,15}(delivery|birth|childbirth)",
    ],
    "external_bleeding_heavy": [
        r"bleeding\s+(will\s+not|won'?t|does\s+not|doesn'?t)\s+stop", r"blood\s+(is\s+)?(pouring|gushing)",
        r"severe\s+bleeding", r"profuse\s+bleeding", r"khoon\s+nahi\s+ruk",
    ],
    "vomiting_blood": [
        r"vomit(ing|ed)?\s+(of\s+)?blood", r"blood\s+in\s+(the\s+)?vomit", r"khoon\s+ki\s+ulti", r"raktam\s+vanti",
    ],
    "black_or_bloody_stool": [
        r"black\s+(stool|tarry|motion)", r"blood\s+in\s+(the\s+)?(stool|motion)", r"bloody\s+stool",
    ],
    "stiff_neck": [r"stiff\s+neck", r"neck\s+stiff", r"gardan\s+akad"],
    "bulging_fontanelle": [r"bulging\s+(soft\s+spot|fontanelle)", r"fontanelle.{0,15}bulg"],
    "fever": [r"fever", r"bukhar", r"jwaram", r"temperature"],
    "high_fever": [r"high\s+fever", r"very\s+high\s+temperature", r"tez\s+bukhar"],
    "pregnant": [r"pregnan", r"garbh", r"garbhavati", r"gharbini", r"\bexpecting\b"],
    "severe_headache": [r"severe\s+headache", r"worst\s+headache", r"terrible\s+headache"],
    "visual_disturbance": [r"blurr?(ed|y)\s+vision", r"vision\s+(is\s+)?blurr", r"seeing\s+spots", r"can'?t\s+see"],
    "epigastric_pain": [r"upper\s+(stomach|abdominal)\s+pain", r"pain\s+in\s+(the\s+)?upper\s+stomach"],
    "swelling_edema": [r"swollen\s+(face|feet|legs|hands)", r"swelling\s+(of|in)\s+(the\s+)?(face|feet|legs|hands)"],
    "hypertension_known_or_suspected": [r"high\s+(blood\s+pressure|bp)", r"\bhypertension\b"],
    "trauma_injury": [r"road\s+accident", r"\baccident\b", r"fell\s+from", r"head\s+injury"],
    "fracture_suspected": [r"fracture", r"bone\s+(is\s+)?(broken|sticking)", r"broken\s+(bone|leg|arm)"],
}

# Generic phrasing variants (word-window co-occurrence). Added after the
# first replay showed the exact-phrase list missed ordinary wordings.
# NOTE: the 30 eval cases were visible while these were written, so they are
# a DEVELOPMENT set for this module and not evidence of its recall; see
# docs/V2_PROTOCOL.md for the fresh held-out set.
_EXTRA: dict[str, list[str]] = {
    "chest_pain": [r"(pain|tight|tightness|pressure|crushing|squeez\w*).{0,25}\bchest\b", r"\bchest\b.{0,25}(pain|tight|pressure|hurts?)"],
    "shortness_of_breath": [r"(hard|difficult|trouble|struggl\w*|unable|fast|rapid|labou?red)\s+(\w+\s+){0,2}(to\s+)?(breath\w*|breathing)", r"breath\w*.{0,15}(hard|difficult|fast|rapid|laboured|labored)", r"\bgasping\b"],
    "postpartum_bleeding_heavy": [r"deliver\w*.{0,60}bleed\w*", r"bleed\w*.{0,60}deliver\w*"],
    "vaginal_bleeding_heavy": [r"bleed\w*\s+(very\s+)?(heavily|badly)", r"(soaked|soaking).{0,30}(cloth|pad|sari)"],
    "external_bleeding_heavy": [r"bleed\w*\s+(very\s+)?(heavily|badly)", r"deep\s+cut.{0,30}bleed"],
    "stiff_neck": [r"neck\s+(feels\s+|is\s+|has\s+become\s+)?(stiff|rigid)", r"(stiff|rigid)\s+neck"],
    "vomiting_blood": [r"(vomit\w*|throw\w*\s+up|threw\s+up).{0,30}\bblood", r"\bblood.{0,20}(vomit|throw\w*\s+up)"],
    "black_or_bloody_stool": [r"(stool|motion|poop|faeces|feces).{0,30}(black|blood)", r"(black|tarry|bloody).{0,15}(stool|motion)"],
    "hypertension_known_or_suspected": [r"\bBP\b.{0,10}(high|raised)"],
    "visual_disturbance": [r"eyes?\s+(are\s+|is\s+)?blurr\w*", r"dhundhl\w*", r"vision\s+problem"],
    "swelling_edema": [r"(hands?|face|feet|legs?).{0,30}swoll?en", r"swoll?en.{0,30}(hands?|face|feet|legs?)", r"sujan"],
    "severe_headache": [r"(severe|very\s+bad|terrible|worst|intense).{0,12}(headache|sar\s*dard|head\s+pain)", r"headache.{0,20}(severe|terrible|worst)", r"bahut\s+tez\s+sar\s*dard"],
    "high_fever": [r"(severe|very\s+high|high|burning).{0,15}(fever|temperature)", r"fever.{0,20}(very\s+high|severe)"],
}
for _t, _p in _EXTRA.items():
    _PATTERNS.setdefault(_t, []).extend(_p)

_COMPILED: dict[str, re.Pattern] = {
    tag: re.compile("|".join(f"(?:{p})" for p in pats), re.IGNORECASE) for tag, pats in _PATTERNS.items()
}
assert set(_COMPILED) <= SYMPTOM_TAGS, "precheck emits tags outside the closed vocabulary"

_NEGATION = re.compile(r"\b(no|not|without|denies|nahi|nahin|ledu)\s+(\w+\s+){0,2}$", re.IGNORECASE)


def screen_tags(*texts: str | None) -> set[str]:
    """Tags whose pattern appears in any text. Negation is handled only for
    the immediately preceding words ("no chest pain"); anything unclear is
    treated as present, because the cost asymmetry favors escalation."""
    tags: set[str] = set()
    for text in texts:
        if not text:
            continue
        for tag, rx in _COMPILED.items():
            for m in rx.finditer(text):
                if _NEGATION.search(text[max(0, m.start() - 24):m.start()]):
                    continue
                tags.add(tag)
                break
    return tags


def screen(*texts: str | None) -> list[str]:
    """rule_ids of the existing red-flag rules that fire on the text alone.
    Age is unknown here, so the infant rule can fire only via the text."""
    tags = screen_tags(*texts)
    ir = {"symptom_tags": sorted(tags), "patient": {}}
    fired = evaluate_red_flags(ir)
    if not fired and "fever" in tags and tags & {"stiff_neck", "bulging_fontanelle"}:
        # Age is not known at this stage; fever + meningism signs is
        # escalated regardless of age (conservative superset of the infant rule).
        fired = ["precheck_fever_meningism_age_unknown"]
    return fired
