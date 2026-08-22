# ACRME Product Backlog

Agile backlog — **Epics → Stories → Tasks** — derived directly from the
[Production-Readiness Review & Final Architecture](../acrme_production_readiness_review_and_architecture.md) (PRR).

## Contents

| File | Purpose |
|---|---|
| [`backlog_data.py`](./backlog_data.py) | **Single source of truth.** The full Epic/Story/Task model as Python data. |
| [`generate_markdown.py`](./generate_markdown.py) | Renders the Markdown backlog from `backlog_data.py`. |
| [`generate_csv.py`](./generate_csv.py) | Renders the Jira-import CSV from `backlog_data.py`. |
| [`acrme_epics_stories_tasks.md`](./acrme_epics_stories_tasks.md) | Human-readable backlog (also available as `.docx` / `.pdf`). |
| [`acrme_backlog_jira_import.csv`](./acrme_backlog_jira_import.csv) | Jira-importable issue list. |

Both outputs are generated from the same data module, so the Markdown and the CSV never drift.

## Rollup

- **19 Epics** · **66 Stories** · **175 Tasks** · **426 story points**
- Phased **P1 Pilot → P2 Controlled automation → P3 Production/Future**

## ID scheme

- Epics `ACRME-E##` (e.g. `ACRME-E07`)
- Stories `ACRME-S####` (epic number + story number, e.g. `ACRME-S0701`)
- Tasks `ACRME-T######` (epic + story + task, e.g. `ACRME-T070101`)

## Regenerating

```bash
cd docs/backlog
python3 generate_markdown.py
python3 generate_csv.py
```

Edit only `backlog_data.py`, then re-run the generators — never hand-edit the
`.md` or `.csv` outputs.

## Importing into Jira

1. **Jira → Settings → System → External System Import → CSV.**
2. Upload `acrme_backlog_jira_import.csv`.
3. Map the columns:
   - `Issue Type` → Issue Type
   - `Issue ID` → **Issue ID** (external id used for linking)
   - `Parent ID` → **Parent ID** (links Sub-tasks to their Story)
   - `Epic Link` → Epic Link (nests Stories under their Epic)
   - `Epic Name` → Epic Name (required on Epic rows)
   - `Summary`, `Priority`, `Story Points`, `Labels`, `Description`,
     `Acceptance Criteria` → the matching fields
   - `Phase`, `PRR Refs` → labels or custom fields as preferred
4. Run the import. Epics are created first, then Stories linked via *Epic Link*,
   then Sub-tasks linked via *Parent ID*.

> Tip: if your project uses *Tasks* instead of *Sub-tasks*, change the
> `Issue Type` value in `generate_csv.py` and re-run it.
