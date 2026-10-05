# evaluation/recovered — index

Everything here was derived read-only from files already on this machine. Originals were not modified.

| Path | What it is |
|---|---|
| `mira_outputs.csv`, `mira_outputs_recovered.csv` | Per-case MIRA output of the `final` aggregate (30 rows), joined to verbatim agent logs. The second file adds models/decided_by. |
| `mira_outputs_all_runs.csv` | Every case record from all 17 run directories. |
| `case_mapping.csv` | Paper case ID ↔ `case_key` ↔ case UUID ↔ runs ↔ text hash. |
| `run_metadata.json`, `EVALUATED_RUN_METADATA.md` | Run facts, each tagged VERIFIED/UNVERIFIED. |
| `prompts/` | Candidate source snapshots (see its README). |
| `raw/` | Copies of the git-ignored `logs/*.jsonl` + SHA256SUMS. Verified identical to `~/mira/logs`; a second copy is in `~/mira-evidence-backups/<timestamp>/`. |
| `raters/` | Preserved original Rater-1 workbook (+ byte-identical re-download) and the extracted/canonical tables. |
| `rater1_ratings_canonical.csv` | Per-case Rater-1 entries, interpretation basis stated per row. |
| `DENOMINATOR_RECONCILIATION.md` | Traces 14/29 and 11/29 to case IDs; states what can't be traced. |
| `rater_data_inventory.md` | What rater evidence exists / does not. |
| `RECOVERY_REPORT.md` | First-pass forensic inventory (partly superseded; see MIRA_FINAL_STATUS.md). |
