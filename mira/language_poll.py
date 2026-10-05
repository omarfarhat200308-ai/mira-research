"""
The one-time numbered-text "poll" asked on a phone number's first-ever
message (see mira/language_preference_store.py for why: an explicit,
one-time choice beats re-detecting language per message). A true native
WhatsApp interactive poll (Meta's poll/button feature via Twilio Content
Templates) requires an approved WhatsApp Business number and isn't
available on the free Sandbox this is currently tested against — this is
the practical, immediately-usable equivalent: a numbered menu, parsed from
a plain-text reply (number OR the language name, case-insensitive).

Confirmation/prompt text below is engineer-approximated romanized Hindi/
Telugu/Urdu, NOT clinically or linguistically reviewed — same honesty bar
as everything else in this codebase (see docs/clinical_review_export.md).
It's a short, non-clinical UI string, so the stakes of an imperfect phrase
here are much lower than anywhere triage content is generated, but it
should still be corrected by a native speaker before real pilot use.
"""
from __future__ import annotations

from typing import Optional

# Order matters: this is the order shown in the poll message.
LANGUAGE_CHOICES: list[tuple[str, str, str]] = [
    ("1", "hi", "Hindi (Roman)"),
    ("2", "te", "Telugu (Roman)"),
    ("3", "ur", "Urdu (Roman)"),
    ("4", "en", "English"),
]

# Accepts the number OR the language name (case-insensitive) as a reply —
# more forgiving than requiring an exact digit, since a low-literacy user
# may naturally type the word instead.
_CHOICE_LOOKUP: dict[str, str] = {}
for _number, _code, _label in LANGUAGE_CHOICES:
    _CHOICE_LOOKUP[_number] = _code
    _CHOICE_LOOKUP[_code] = _code
    _CHOICE_LOOKUP[_label.split(" ")[0].lower()] = _code  # "hindi", "telugu", "urdu", "english"

LANGUAGE_POLL_MESSAGE = "Welcome to MIRA. Which language would you like to use?\n" + "\n".join(
    f"{number}. {label}" for number, _, label in LANGUAGE_CHOICES
) + "\n\nReply with the number."

LANGUAGE_POLL_RETRY_MESSAGE = "Sorry, I didn't understand that.\n\n" + LANGUAGE_POLL_MESSAGE

_CONFIRMATION_TEXT: dict[str, str] = {
    "hi": "Theek hai, Hindi mein baat karenge. Kripya mareez ke lakshan bataiye.",
    "te": "Sare, Telugu lo matladdam. Dayachesi patient symptoms cheppandi.",
    "ur": "Theek hai, Urdu mein baat karenge. Baraye meherbani mareez ki alamat bataiye.",
    "en": "Got it, we'll continue in English. Please describe the patient's symptoms.",
}


def parse_choice(text: str) -> Optional[str]:
    """Returns a language code ("hi"/"te"/"ur"/"en") if `text` matches a
    valid choice (number or language name), otherwise None."""
    return _CHOICE_LOOKUP.get(text.strip().lower())


def confirmation_text(language_code: str) -> str:
    return _CONFIRMATION_TEXT.get(language_code, _CONFIRMATION_TEXT["en"])
