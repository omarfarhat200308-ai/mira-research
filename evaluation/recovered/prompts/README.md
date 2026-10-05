# Prompt/source snapshots (CANDIDATES — not proven to be what executed)

The executed prompt per run was never stored (logs hold only structured input/output snapshots).
These are the agent source files (which embed the prompts) and rule/config files as committed at:

- `f4fc9ef` — HEAD recorded in most run summaries (predates the NVIDIA client).
- `fea51d4` — first commit containing the eval harness + NVIDIA client; best candidate for the evaluated code.

The only agent file that differs between them is `intake.py` (an age-in-months/days instruction added). Per verbatim logs, the intake edit
happened at 2026-09-11 12:56 UTC; 2 of the 30 final records (D1, G1) ran before it, 28 after.
`mira/` files at HEAD differ from `fea51d4` only in llm_client.py, protocol corpus, romanization.py, message_formatting.py, speech/tts.py (post-evaluation edits).
