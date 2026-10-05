# Paper draft

`mira_paper_draft.html` is a skeleton draft populated with real data from
`eval/results/final/`. Every `[EXPAND]` marker is prose the authors still
need to write — the structure, tables, and numbers are real; the narrative
around them isn't written yet.

**Do not submit or circulate this as-is** — see the draft banner at the top
of the document, and `eval/results/final/summary.md`'s caveats. Clinical
review (sent to Dr. Zia, see `docs/clinical_review_export.md` and
`docs/clinical_review_worksheet.csv`) has not been incorporated yet, and
the Sonnet-primary and GPT-4o benchmark runs referenced in Section 8 have
not been run.

## Regenerating the PDF

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless --disable-gpu --no-sandbox \
  --print-to-pdf="paper/mira_paper_draft.pdf" \
  --no-pdf-header-footer \
  "file://$(pwd)/paper/mira_paper_draft.html"
```

## Updating the data tables

The per-case table (Table 4) and per-group table (Table 3) in the HTML are
hand-injected from `eval/results/final/raw_results.jsonl` — if that file
changes (e.g. after a Sonnet or GPT-4o benchmark run), regenerate the rows
rather than hand-editing the table, to avoid transcription drift between
the paper and the underlying data.
