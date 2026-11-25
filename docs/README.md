# ACRME Documentation Index

> **Repository restructured (Phase 4).** Documentation is now organised into purpose-named
> **top-level** areas rather than under `docs/`. All moves used `git mv`, so
> `git log --follow <path>` shows full history across the restructure. This page is the
> navigation index to the new locations.

Markdown is the source of truth for repository documentation. Some documents also have
`.docx`/`.pdf` exports; those derived copies may lag the Markdown and must be regenerated after
source changes.

> **Single source of truth:** [`acrme_requirements_baseline_v4_0_3.md`](../Requirements/acrme_requirements_baseline_v4_0_3.md)
> is the authoritative requirements baseline. The v2.4 and v3.0 baseline files are historical
> snapshots. The FDD/TDD are v4.0 reconciliation drafts, pending decisions and POC evidence.
> The POC workbook/suite, glossary, calculation reference, and several
> mockups/reference documents still contain older-baseline content and are **not verified as
> reconciled to v4.0.3**. On conflict, v4.0.3 wins.

---

## Current areas

### [`/Requirements`](../Requirements/) — WHAT the system must do

| Document | Purpose |
|---|---|
| [`acrme_requirements_baseline_v4_0_3`](../Requirements/acrme_requirements_baseline_v4_0_3.md) | **Authoritative** consolidated working requirements baseline. Single source of truth. |
| [`Requirements/README.md`](../Requirements/README.md) | Current requirements folder index and lifecycle rules. |
| [`Archive/requirements/`](../Archive/requirements/) | Superseded baselines, incorporated proposals, audits, and the legacy expanded reference. |

### [`/Design`](../Design/) — design artefacts (older baseline; reconciliation pending)

| Document | Purpose |
|---|---|
| [`acrme_functional_design_document`](../Design/acrme_functional_design_document.md) | v4.0 reconciliation draft v2.0; customer CRV/domain DPB, Foundation and acceptance mapping; not ratified. |
| [`acrme_technical_design_document`](../Design/acrme_technical_design_document.md) | v4.0 reconciliation draft v2.0; schemas/contracts/algorithms, canonical Mermaid sources and explicit remaining gates. |
| [`acrme_uml_class_diagrams_summary`](../Design/acrme_uml_class_diagrams_summary.md) | Legacy UML/gap-analysis material; verify against v4.0 before treating as current. |

### [`/Architecture`](../Architecture/) — ADRs + architecture diagrams

| Item | Purpose |
|---|---|
| [`adr/`](../Architecture/adr/) | Individual ADRs and rendered diagrams. Their v2.4 reconciliation notes are historical; see the ADR index for the v4.0 authority caveat. |
| [`diagrams/`](../Architecture/diagrams/) | Source architecture diagrams (`.png`/`.svg`/`.mmd`), the `fdd/`+`tdd/` diagram sources, and the architecture diagrams deck (`.pptx`/`.pdf`). |
| [`tools/`](../Architecture/tools/) | ADR/doc build-transform and Markdown-format helpers; see [`tools/README.md`](../Architecture/tools/README.md). |

### [`/POC-Test-Scripts`](../POC-Test-Scripts/) — executable suite + spec workbook

| Item | Purpose |
|---|---|
| [`acrme_poc_workbook_v2_4`](../POC-Test-Scripts/acrme_poc_workbook_v2_4.md) | Historical v2.4 POC workbook; not yet reconciled to v4.0. |
| [`README.md`](../POC-Test-Scripts/README.md) | Usage guide for the legacy suite; case coverage requires reconciliation to v4.0. |

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
| [`testing/`](../Archive/testing/) | Binary v2.0 POC workbook (`.docx`/`.pdf`) — historical predecessor to the v2.4 workbook. |

---

## Conventions

- **Edit the `.md`; the `.docx`/`.pdf` regenerate from it.** Never hand-edit the `.docx`/`.pdf` — they are derived artifacts.
- **Diagram sources are `.mmd` (Mermaid) / `.svg`; PNGs are rendered outputs.**
