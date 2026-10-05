# MIRA voice pipeline round-trip probe -- live results

Run: 2026-09-12 (real Sarvam API calls, TTS bulbul:v3 -> STT saaras:v3, no mocking)

| label | register | TTS (s) | STT (s) | total (s) | input | transcript |
|---|---|---|---|---|---|---|
| hindi_standard_fever | standard | 0.783 | 0.318 | 1.1 | mujhe bukhar hai | मुझे बुखार है। |
| hindi_colloquial_fever | colloquial/regional | 1.062 | 0.586 | 1.648 | mereko bahut tez bukhar aa raha hai do din se | मेरे को बहुत तेज़ बुख़ार आ रहा है दो दिन से। |
| hindi_standard_breathing | standard | 1.168 | 0.515 | 1.683 | unko saans lene mein bahut takleef ho rahi hai | उनको सांस लेने में बहुत तकलीफ़ हो रही है। |
| telugu_standard_fever | standard | 0.891 | 0.464 | 1.355 | naaku jwaram undi rendu rojula nunchi | నాకు జ్వరం ఉంది రెండు రోజుల నుంచి |
| telugu_standard_cough | standard | 0.779 | 0.352 | 1.132 | naaku daggu undi konchem | నాకు దగ్గు ఉంది కొంచెం. |

**Mean round-trip latency: 1.384s over 5/5 successful calls.**

**Caveats**: (1) this is synthesized speech, not a real phone recording -- no background noise, no real accent, no Twilio OGG/Opus compression artifacts, so real-world latency and accuracy are likely worse than this. (2) Transcription fidelity was checked by eye (native-script output vs. romanized input meaning), not a formal word-error-rate against native-speaker-verified ground truth -- this probe establishes that the pipeline *works end-to-end with real latency numbers*, not a validated dialect-accuracy benchmark. (3) Only 5 phrases, 2 languages, from one synthetic TTS voice each -- not a claim about robustness across Sarvam's full voice/dialect range.