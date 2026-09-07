# ACRME Documentation Index

> **Repository restructured (Phase 4).** Documentation is now organised into purpose-named
> **top-level** areas rather than under `docs/`. All moves used `git mv`, so
> `git log --follow <path>` shows full history across the restructure. This page is the
> navigation index to the new locations.

Every narrative document is provided in three synchronized formats — `.md` (authoritative
source), `.docx` (editable), and `.pdf` (print-ready) — generated from the Markdown source,
unless noted otherwise.

> **Single source of truth:** [`/Requirements/acrme_requirements_baseline_v2_4.md`](../Requirements/acrme_requirements_baseline_v2_4.md)
> is the authoritative living requirements baseline (v2.4). All other documents reconcile to it.

---

## Current areas

### [`/Requirements`](../Requirements/) — WHAT the system must do

| Document | Purpose |
|---|---|
| [`acrme_requirements_baseline_v2_4`](../Requirements/acrme_requirements_baseline_v2_4.md) | **Authoritative** consolidated requirements baseline (v2.4). Single source of truth. |
| [`acrme_complete_requirements_reference`](../Requirements/acrme_complete_requirements_reference.md) | All requirements (FR/NFR/R) with Must-Should-Could classification and design-coverage evidence. |

### [`/Design`](../Design/) — HOW it is designed (current design of record)

| Document | Purpose |
|---|---|
| [`acrme_functional_design_document`](../Design/acrme_functional_design_document.md) | Functional design (FDD) — behaviour, flows, functional requirements. |
| [`acrme_technical_design_document`](../Design/acrme_technical_design_document.md) | Technical design (TDD) — services, schemas, validation gates. |
| [`acrme_uml_class_diagrams_summary`](../Design/acrme_uml_class_diagrams_summary.md) | UML class diagrams (4 sets) with explicit gap analysis. UML sources: `uml_01..04_*.md`. |

### [`/Architecture`](../Architecture/) — ADRs + architecture diagrams

| Item | Purpose |
|---|---|
| [`adr/`](../Architecture/adr/) | Individual standalone ADR-001..005 (`.md`/`.docx`/`.pdf`) plus rendered diagrams under `adr/diagrams/`. The consolidated ADR is archived (see below). |
| [`diagrams/`](../Architecture/diagrams/) | Source architecture diagrams (`.png`/`.svg`/`.mmd`), the `fdd/`+`tdd/` diagram sources, and the architecture diagrams deck (`.pptx`/`.pdf`). |
| [`tools/`](../Architecture/tools/) | ADR/doc build-transform helper scripts. |

### [`/POC-Test-Scripts`](../POC-Test-Scripts/) — executable suite + spec workbook

| Item | Purpose |
|---|---|
| [`acrme_poc_workbook_v2_4`](../POC-Test-Scripts/acrme_poc_workbook_v2_4.md) | **Canonical v2.4 POC workbook of record** — 49 cases across G1–G12, in lock-step with the suite. |
| [`README.md`](../POC-Test-Scripts/README.md) | Full test-suite usage guide. |

### [`/Test-Results`](../Test-Results/) — execution evidence

Generated HTML / Markdown / JSON reports from suite runs land here.

### [`/Reference-Material`](../Reference-Material/) — supporting material

| Folder | Contents |
|---|---|
| [`reference/`](../Reference-Material/reference/) | Calculation-logic reference, hard-constraints reference, plain-English walkthrough, scoring-weights explainer. |
| [`guides/`](../Reference-Material/guides/) | Operator-facing guides — Security & RBAC guide. |
| [`rbac/`](../Reference-Material/rbac/) | Custom role JSONs and deployment scripts referenced by the Security & RBAC guide. |
| [`backlog/`](../Reference-Material/backlog/) | Agile delivery backlog — Epics → Stories → Tasks + Jira-import CSV, generated from `backlog_data.py`. |
| [`presentation/`](../Reference-Material/presentation/) | Executive slide deck (`.pptx`/`.pdf`) and its build script. |

---

## [`/Archive`](../Archive/) — superseded / historical (retained, not deleted)

| Location | Contents |
|---|---|
| [`design/`](../Archive/design/) | Executive Design Document, Production Readiness Review & Architecture, Design-Change & FDD/TDD plan. |
| [`adr/`](../Archive/adr/) | Consolidated Architecture Decision Records (superseded by the split ADRs in `/Architecture/adr/`). |
| [`requirements/`](../Archive/requirements/) | Requirements v2.1 and the v2.1 deviation analysis. |
| [`research/`](../Archive/research/) | Pre-baseline research inputs and the exploratory research POC workbook. |
| [`testing/`](../Archive/testing/) | Binary v2.0 POC workbook (`.docx`/`.pdf`) — consolidated into the canonical v2.4 workbook. |

---

## Conventions

- **Edit the `.md`; the `.docx`/`.pdf` regenerate from it.** Never hand-edit the `.docx`/`.pdf` — they are derived artifacts.
- **Diagram sources are `.mmd` (Mermaid) / `.svg`; PNGs are rendered outputs.**
