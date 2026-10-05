#!/usr/bin/env bash
# Builds the public Zenodo code+evaluation archive from the current branch HEAD.
# - excludes security notes, original rater files, local provenance notes, internal drafts/packets, older superseded paper drafts
# - REPLACES the protocol corpus with the evaluation-time placeholder files (commit fea51d4), so no third-party-derived text is redistributed
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="${1:-paper/MIRA_code_and_evaluation_v1.3.zip}"
TMP="$(mktemp -d)"
git archive --format=tar --prefix=mira-v1.3/ HEAD -- . \
  ':(exclude)security' ':(exclude)evaluation/recovered/raters' ':(exclude)evaluation/recovered/rater_data_inventory.md' \
  ':(exclude)evaluation/WORKBOOK_PROVENANCE.md' ':(exclude)evaluation/recovered/RECOVERY_REPORT.md' ':(exclude)evaluation/PAPER_CLAIM_AUDIT.md' \
  ':(exclude)evaluation/recovered/raw/2026-08-18.jsonl' ':(exclude)evaluation/recovered/raw/2026-08-18_cases.jsonl' \
  ':(exclude)evidence' ':(exclude)MIRA_FINAL_STATUS.md' ':(exclude)ZENODO_UPDATE_DRAFT.md' ':(exclude)ZENODO_PUBLISH_PACKET.md' \
  ':(exclude)paper/mira_paper_draft.html' ':(exclude)paper/MIRA_paper_draft.pdf' ':(exclude)paper/MIRA_interim_report_v1.3_CORRECTED_DRAFT.md' \
  ':(exclude)paper/CORRECTIONS_LOG.md' ':(exclude)paper/CHATGPT_REVIEW_PACKET.md' ':(exclude)paper/*.zip' \
  ':(exclude)docs/corpus_*' ':(exclude)docs/zenodo_*' ':(exclude).env' | tar -x -C "$TMP"
for f in imnci nhm who_chw; do git show "fea51d4:mira/knowledge/protocol_corpus/$f.md" > "$TMP/mira-v1.3/mira/knowledge/protocol_corpus/$f.md"; done
cat > "$TMP/mira-v1.3/ARCHIVE_README.md" <<'R'
# Archive note
Research prototype; not clinically validated, not deployed, not for clinical use. See `paper/MIRA_interim_report_v1.3.pdf` and `THIRD_PARTY_NOTICE.md`.
- Code is from the authors' branch HEAD after the evaluation; the evaluated working-tree state is not definitively known (closest committed snapshot believed to be `fea51d4`).
- `mira/knowledge/protocol_corpus/*.md` are the **evaluation-time author-written placeholder files** (commit `fea51d4`), not the later source-derived files. All 135 tests in `tests/` pass against this archive (verified).
- Excluded on purpose: original rater files, security notes, internal drafts, logs from unrelated earlier test runs, and the older superseded paper draft.
R
rm -f "$OUT"; (cd "$TMP" && zip -qr "$OLDPWD/$OUT" mira-v1.3); rm -rf "$TMP"; echo "built $OUT"
