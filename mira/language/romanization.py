"""
Romanization-normalization pre-processing, run before Intake
(mira/pipeline.py) on every inbound message.

Why this exists: romanized Telugu/Hindi (Latin script, e.g. "jwaram vachindi"
instead of "జ్వరం వచ్చింది" or "बुखार आया") is common in real Indian
WhatsApp usage, and leaving it unhandled causes measurable degradation in
downstream symptom classification, because neither a keyword-based rule
engine nor an LLM prompt written with script-only examples reliably
recognizes it. (An earlier version of this docstring cited specific figures
— "73-83% of usage" / "double-digit F1-point degradation" — for this claim;
those numbers had no traceable source and were removed 2026-09-19 rather
than left looking like a verified citation. If a real source is found, put
it back with a citation.) Do not assume script-only input in any prompt or
regex anywhere in this codebase — this module is the one place that widens
input before it reaches the reasoning stage.

Scope, stated honestly: this is a practical spelling/gloss-normalization
layer over a curated dictionary of common romanized Telugu/Hindi clinical
and symptom terms, NOT a full transliteration model (that would need a
trained model, e.g. an IndicNLP/AI4Bharat transliteration system, which
this codebase does not have a dependency on). It closes the most common,
highest-frequency gap — the symptom vocabulary that actually drives
red-flag/triage decisions — by appending an English gloss next to any
romanized term it recognizes, rather than attempting to reconstruct native
script. The original text is always preserved untouched; this only adds
information, never replaces it, consistent with the rest of the pipeline's
"never guess, always show your work" design.

Extending ROMANIZED_TERM_MAP is a clinical-content-adjacent decision (same
review bar as mira/knowledge/symptom_tags.py) since it feeds what Language
and Diagnostic ultimately reason about.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Unicode block ranges used for script detection.
_DEVANAGARI_RANGE = (0x0900, 0x097F)
_TELUGU_RANGE = (0x0C00, 0x0C7F)


def detect_script(text: str) -> str:
    """Returns "latin" | "devanagari" | "telugu" | "mixed" | "unknown"."""
    counts = {"latin": 0, "devanagari": 0, "telugu": 0}
    for ch in text:
        if not ch.isalpha():
            continue
        cp = ord(ch)
        if _DEVANAGARI_RANGE[0] <= cp <= _DEVANAGARI_RANGE[1]:
            counts["devanagari"] += 1
        elif _TELUGU_RANGE[0] <= cp <= _TELUGU_RANGE[1]:
            counts["telugu"] += 1
        elif unicodedata.category(ch).startswith("L") and cp < 0x0250:  # basic Latin + Latin-1 letters
            counts["latin"] += 1

    total = sum(counts.values())
    if total == 0:
        return "unknown"
    present = [k for k, v in counts.items() if v > 0]
    if len(present) > 1:
        # Require the minority script to be more than noise (e.g. a single
        # stray character) before calling it genuinely mixed.
        minority_share = min(v for v in counts.values() if v > 0) / total
        if minority_share >= 0.1:
            return "mixed"
    return max(counts, key=counts.get)


# Curated romanized Telugu (te) / Hindi (hi) clinical & symptom terms ->
# canonical English gloss. Deliberately flat and small: precision over
# recall, since a wrong gloss is worse than no gloss (the LLM still sees the
# original text either way). Common spelling variants are listed explicitly
# rather than attempting fuzzy matching, which would risk false positives on
# a safety-relevant term.
ROMANIZED_TERM_MAP: dict[str, str] = {
    # --- Telugu ---
    "jwaram": "fever", "jwara": "fever", "jwaramu": "fever",
    "vantulu": "vomiting", "vanthulu": "vomiting", "vaanthulu": "vomiting",
    "virechanalu": "diarrhea / loose stools", "virechanam": "diarrhea / loose stools",
    "daggu": "cough",
    "ooపiri aadakapovadam": "shortness of breath",  # unlikely to hit due to script mix; kept for completeness
    "oopiri aadakapovadam": "shortness of breath", "oopiri andakapovadam": "shortness of breath",
    "chatilo noppi": "chest pain", "chati noppi": "chest pain",
    "kadupu noppi": "abdominal pain", "kadupunoppi": "abdominal pain",
    "tala noppi": "headache", "talanoppi": "headache",
    "vodalu": "seizure / fits", "moorcha": "seizure / loss of consciousness",
    "balaheenata": "weakness / fatigue", "sustu": "weakness / fatigue",
    "garbhavathi": "pregnant", "garbhini": "pregnant",
    "vాndi": "swelling",  # left as-is if mixed script slips through
    "vapu": "swelling", "vaapu": "swelling",
    "rakthasravam": "bleeding", "raktha srаvam": "bleeding",
    "gaayam": "injury / trauma", "kshatam": "injury / trauma",
    # --- Hindi ---
    "bukhar": "fever", "bukhaar": "fever", "tez bukhar": "high fever",
    "ulti": "vomiting", "ulty": "vomiting", "kai": "vomiting",
    "dast": "diarrhea / loose stools", "dast lagna": "diarrhea",
    "khaansi": "cough", "khansi": "cough",
    "saans phoolna": "shortness of breath", "saans lene mein takleef": "shortness of breath",
    "seene mein dard": "chest pain",
    "pet dard": "abdominal pain", "pet mein dard": "abdominal pain",
    "sir dard": "headache", "sar dard": "headache",
    "daura": "seizure / fits", "mirgi ka daura": "seizure",
    "behoshi": "loss of consciousness", "behoshi aana": "loss of consciousness",
    "kamzori": "weakness / fatigue", "kamjori": "weakness / fatigue",
    "garbhvati": "pregnant", "pregnant hai": "pregnant",
    "sujan": "swelling", "sujan aana": "swelling",
    "khoon aana": "bleeding", "zyada khoon behna": "heavy bleeding",
    "chot": "injury / trauma", "chot lagna": "injury / trauma",
}

# Collapse simple repeated-character spelling variance ("bukharrr" ->
# "bukhar") before dictionary lookup — a light heuristic, not a full
# normalizer: any run of 2+ identical letters collapses to 1, used only as
# a fallback when the token doesn't match a dictionary entry directly.
_REPEATED_CHAR_RE = re.compile(r"(.)\1+")


@dataclass
class RomanizationResult:
    normalized_text: str
    detected_script: str
    glossed_terms: list[str]


def _collapse_repeats(token: str) -> str:
    return _REPEATED_CHAR_RE.sub(r"\1", token)


_WORD_RE = re.compile(r"[A-Za-z]+|[^A-Za-z\s]|\s+")


def normalize_romanized_text(text: str) -> RomanizationResult:
    """
    Appends an inline English gloss after any recognized romanized
    Telugu/Hindi term, e.g. "baby ki tez bukhar hai" ->
    "baby ki tez bukhar [high fever] hai". Case-insensitive. Multi-word
    phrases in ROMANIZED_TERM_MAP are tried first at each position (longest
    match wins) via explicit token consumption, so e.g. "tez bukhar" glosses
    once as "high fever" rather than also re-matching "bukhar" alone as
    "fever" inside the already-glossed span.
    """
    script = detect_script(text)

    if script not in ("latin", "mixed"):
        # Native-script or undetermined input: nothing for a *romanization*
        # layer to do. Devanagari/Telugu script text already reaches the
        # Language agent as-is.
        return RomanizationResult(normalized_text=text, detected_script=script, glossed_terms=[])

    # Split into words + non-word chunks (punctuation/whitespace), preserved
    # verbatim in the output so spacing/punctuation round-trips exactly.
    pieces = _WORD_RE.findall(text)
    word_positions = [i for i, p in enumerate(pieces) if p.isalpha()]

    # Longest phrase (by word count) matched at each starting word position
    # wins; phrases are pre-split into their word tuples for comparison.
    phrase_word_lists = sorted(
        ((tuple(phrase.split()), phrase) for phrase in ROMANIZED_TERM_MAP),
        key=lambda item: len(item[0]),
        reverse=True,
    )

    glossed: list[str] = []
    consumed_until = -1  # index into `pieces`; word positions <= this are already glossed

    for start_idx, pos in enumerate(word_positions):
        if pos <= consumed_until:
            continue

        matched_end_pos = None
        matched_gloss = None
        for phrase_words, phrase_key in phrase_word_lists:
            n = len(phrase_words)
            candidate_positions = word_positions[start_idx:start_idx + n]
            if len(candidate_positions) != n:
                continue
            candidate_words = tuple(pieces[p].lower() for p in candidate_positions)
            if candidate_words == phrase_words:
                matched_end_pos = candidate_positions[-1]
                matched_gloss = ROMANIZED_TERM_MAP[phrase_key]
                break

        if matched_gloss is None:
            # Fall back to repeated-character collapsing on this single
            # word (spelling variance like "bukharrr").
            collapsed = _collapse_repeats(pieces[pos].lower())
            if collapsed in ROMANIZED_TERM_MAP and collapsed != pieces[pos].lower():
                matched_end_pos = pos
                matched_gloss = ROMANIZED_TERM_MAP[collapsed]

        if matched_gloss is not None:
            pieces[matched_end_pos] = f"{pieces[matched_end_pos]} [{matched_gloss}]"
            consumed_until = matched_end_pos
            if matched_gloss not in glossed:
                glossed.append(matched_gloss)

    return RomanizationResult(
        normalized_text="".join(pieces), detected_script=script, glossed_terms=glossed
    )
