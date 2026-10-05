Drop your real voice recordings here (.wav/.mp3/.ogg/.m4a), then edit
`GROUND_TRUTH` in `../evaluate_real_recordings.py` to say what you actually
said in each one, and run `python -m eval.evaluate_real_recordings` from
the repo root.

For this to actually test dialect robustness (not just "does the pipeline
work"), aim for:
- A mix of standard and regional/colloquial phrasing in Hindi and Telugu
- Real phone-mic recording conditions (not a studio mic) — background
  noise, distance from mic, whatever a real ASHA worker's phone would
  produce
- A few different speakers/accents if you can get them, not just one voice
