"""
Evaluates MIRA's real STT path against real recordings -- unlike
eval/voice_pipeline_probe.py (synthesized speech round-trip), this takes
actual audio files you provide and measures real transcription latency +
lets you score accuracy against what you know you actually said.

## How to use this

1. Record yourself (or anyone) speaking patient-symptom sentences in
   Hindi/Telugu/English/code-mixed -- ideally including regional/
   colloquial phrasing, background noise, and a real phone mic, since
   that's what a real ASHA-worker voice note will look like (the
   synthesized-speech probe in voice_pipeline_probe.py deliberately can't
   test any of that).
2. Save each recording as a .wav, .mp3, or .ogg file in
   eval/real_voice_recordings/, named descriptively
   (e.g. "hindi_colloquial_fever_regional_accent.wav").
3. Edit GROUND_TRUTH below to map each filename to what you actually said
   and what language it's in -- this is what transcription gets scored
   against.
4. Run: python -m eval.evaluate_real_recordings

Results (latency + transcript vs. your ground truth, for you to judge
accuracy by eye -- see the note in the output about why this script
doesn't auto-score word-error-rate) go to
eval/results/real_voice_recordings/summary.md.
"""
from __future__ import annotations

import json
import os
import time

from mira.speech import stt

RECORDINGS_DIR = os.path.join(os.path.dirname(__file__), "real_voice_recordings")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results", "real_voice_recordings")

# Fill this in per recording you add to real_voice_recordings/. Filename
# (without extension) -> {text you actually said, language_hint, and any
# notes on accent/dialect/background noise worth recording alongside the
# result}.
GROUND_TRUTH: dict[str, dict] = {
    # "hindi_colloquial_fever_regional_accent": {
    #     "said": "mereko bahut tez bukhar aa raha hai do din se",
    #     "language_hint": "hi-IN",
    #     "notes": "Bihari-accented Hindi, recorded on phone speaker mic with room noise",
    # },
}


def main() -> None:
    if not os.path.isdir(RECORDINGS_DIR):
        os.makedirs(RECORDINGS_DIR, exist_ok=True)

    files = [
        f for f in os.listdir(RECORDINGS_DIR)
        if f.lower().endswith((".wav", ".mp3", ".ogg", ".m4a"))
    ]
    if not files:
        print(f"No audio files found in {RECORDINGS_DIR}. Add recordings there and re-run.")
        return

    os.makedirs(RESULTS_DIR, exist_ok=True)
    results = []
    for filename in sorted(files):
        key = os.path.splitext(filename)[0]
        meta = GROUND_TRUTH.get(key, {})
        path = os.path.join(RECORDINGS_DIR, filename)
        with open(path, "rb") as f:
            audio_bytes = f.read()

        print(f"Transcribing {filename} ({len(audio_bytes)} bytes)...", end=" ", flush=True)
        try:
            t0 = time.monotonic()
            transcript = stt.transcribe_voice_note(
                audio_bytes, filename=filename, language_hint=meta.get("language_hint"),
            )
            latency = round(time.monotonic() - t0, 3)
            print(f"{latency}s -> {transcript}")
            results.append({
                "filename": filename, "latency_s": latency, "transcript": transcript,
                "you_said": meta.get("said", "(not recorded in GROUND_TRUTH -- edit this script)"),
                "language_hint": meta.get("language_hint"), "notes": meta.get("notes", ""),
                "error": None,
            })
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: {exc!r}")
            results.append({
                "filename": filename, "latency_s": None, "transcript": None,
                "you_said": meta.get("said"), "language_hint": meta.get("language_hint"),
                "notes": meta.get("notes", ""), "error": repr(exc),
            })

    with open(os.path.join(RESULTS_DIR, "raw_results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    lines = ["# MIRA real-recording STT evaluation\n"]
    lines.append("| file | latency (s) | you said | Sarvam transcribed | notes |")
    lines.append("|---|---|---|---|---|")
    for r in results:
        lines.append(
            f"| {r['filename']} | {r['latency_s'] if r['latency_s'] is not None else 'ERROR: ' + str(r['error'])} "
            f"| {r['you_said']} | {r['transcript'] or ''} | {r['notes']} |"
        )
    lines.append(
        "\n**On scoring accuracy**: this script doesn't compute an automatic "
        "word-error-rate, because doing that correctly across Devanagari/Telugu "
        "transcript vs. romanized \"you said\" text needs a transliteration step "
        "this project doesn't have validated yet -- read the transcript column "
        "yourself and judge whether it captured what you actually said, "
        "especially any dialectal/colloquial phrasing. That's still real "
        "evaluation, just human-scored rather than automated."
    )
    with open(os.path.join(RESULTS_DIR, "summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\nWrote {RESULTS_DIR}/summary.md")


if __name__ == "__main__":
    main()
