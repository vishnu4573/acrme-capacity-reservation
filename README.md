# ACRME — Azure Capacity Reservation & Management Enablement

This repository is the consolidated, production-ready design unit for the **ACRME Capacity
Reservation** initiative. It brings together the requirements baseline, the design and
architecture documentation, the canonical POC test workbook, and a fully runnable test
automation suite that implements every POC test case.

---

## Repository layout

The repository is organised into purpose-named top-level areas. Every narrative document is
provided as `.md` (source), `.docx` (editable), and `.pdf` (print-ready) unless noted. See
[`docs/README.md`](docs/README.md) for the folder-to-purpose index.

```
acrme-capacity-reservation/
├── README.md                          # This file
├── docs/README.md                     # Navigation index → top-level areas
├── Requirements/                      # WHAT the system must do (v2.4, current)
│   ├── acrme_requirements_baseline_v2_4.*     # single source of truth (v2.4)
│   └── acrme_complete_requirements_reference.*
├── Design/                            # HOW it is designed (current design of record)
│   ├── acrme_functional_design_document.*
│   ├── acrme_technical_design_document.*
│   ├── acrme_uml_class_diagrams_summary.*
│   └── uml_01..04_*.md                          # UML source (Markdown + Mermaid)
├── Architecture/                      # ADRs + all architecture diagrams
│   ├── adr/                           # Standalone ADR-001..005 (+ diagrams/, README)
│   ├── diagrams/                      # Core view PNG/SVG + fdd/ tdd/ + architecture deck
│   └── tools/                         # ADR/doc-build helper scripts
├── POC-Test-Scripts/                  # Executable suite + canonical spec workbook
│   ├── README.md                      # Full suite usage guide
│   ├── requirements.txt
│   ├── config.yaml.template
│   ├── runner.py                      # CLI: preflight / run / report / gate / list
│   ├── acrme_suite/                   # Engine, config, az client, reporter, preflight
│   ├── test_region_model.py           # Offline region-model checks
│   ├── test_v24_reservation_model.py  # Offline v2.4 logic checks
│   └── acrme_poc_workbook_v2_4.*      # Canonical v2.4 POC workbook of record
├── Test-Results/                      # Generated execution evidence (reports land here)
├── Reference-Material/                # Supporting material
│   ├── reference/                     # Calculation / rules quick-reference
│   ├── guides/                        # Operator-facing guides (Security & RBAC)
│   ├── rbac/                          # Custom role JSONs + deploy scripts
│   ├── backlog/                       # Epics→Stories→Tasks + Jira CSV (generated)
│   └── presentation/                  # Executive slide deck (.pptx/.pdf)
├── Archive/                           # Superseded / historical (do not delete)
│   ├── design/                        # Exec DD, PRR, FDD/TDD plan (superseded)
│   ├── adr/                           # Consolidated ADR (superseded by split ADRs)
│   ├── requirements/                  # Requirements v2.1 + deviation analysis
│   ├── research/                      # Pre-baseline research inputs + research workbook
│   ├── testing/                       # Binary v2.0 POC workbook (.docx/.pdf)
│   └── README_PHASE3.md / README_PHASE4.md
├── src/acrme/                         # Engine implementation skeleton (installable pkg)
└── examples/
```

> **Restructured (Phase 4).** Archived and current documents are no longer interleaved. All
> moves used `git mv`, so `git log --follow <path>` shows full history across the restructure.

---

## Requirements (`Requirements/`)

| Artifact | Description |
|---|---|
| **Requirements Baseline v2.4** ([`Requirements/acrme_requirements_baseline_v2_4.md`](Requirements/acrme_requirements_baseline_v2_4.md)) | The single source of truth (v2.4). Five geographies: US (three-region) plus Europe / Australia / Asia Pacific / Middle East (two-region, with ENV-003 CVAL/DR co-location; Middle East is the sole `DR_NOT_OFFERED` case). |
| **Complete Requirements Reference** | Consolidates all requirements (FR/NFR/R/Must/Should/Could) with evidence of design coverage, maturity ratings, critical POC blockers, and backlog cross-reference — the traceable source of record for ACRME requirements. |

---

## Design (`Design/`)

| Artifact | Description |
|---|---|
| **Functional Design Document (FDD)** | Current functional design of record. |
| **Technical Design Document (TDD)** | Current technical design of record. |
| **UML Class Diagrams Summary** ([`Design/acrme_uml_class_diagrams_summary.md`](Design/acrme_uml_class_diagrams_summary.md)) | Design-first UML class diagrams (4 sets) for domain model, operation tracking, service layer, and state machines — with explicit gap analysis. UML sources are `Design/uml_01..04_*.md`. |

#### UML Class Diagrams (`Design/uml_*.md`)

**Design-first tool** — identifies gaps and unresolved design questions:

| # | Diagram | Coverage | Status |
|---|---|---|---|
| 1 | Core Domain Model | CRG, Assignment, Policy, QuotaGroup, Snapshot, Increase, Transfer entities | Entity outlines complete; property types & Cosmos schemas TBD |
| 2 | Operation Tracking Model | Saga pattern, OperationRecord, compensation chains, VM_ImpactRecord, audit | Saga defined; compensation lambda structure TBD |
| 3 | Service Layer Model | PlacementEngine, Reconciliation, Transfer, Quota, Sharing, Zone services | Service boundaries clear; FastAPI contracts & DTOs TBD |
| 4 | State Machines | engine_mode, IncreaseRequest lifecycle, Transfer workflow (Tier 1/2/3) | High-level states defined; transition guards TBD (G-15/B-3 blocker) |

---

## Architecture (`Architecture/`)

| Artifact | Description |
|---|---|
| **Architecture Decision Records (ADRs)** | Formal, **self-contained** ADRs (`.md` / `.docx` / `.pdf`) capturing the load-bearing decisions with Context / Decision / Consequences / Alternatives-considered. Each record is reference-free and includes **rendered architecture diagrams**. The **four individual standalone ADRs** live in [`Architecture/adr/`](Architecture/adr/): ADR-001 Region Selection, ADR-002 Quota & Capacity Management, ADR-003 Capacity Management during DR, ADR-004 Forecast & Increase of Capacity and Quota, ADR-005 Distributed DR Reference Model. Diagram sources and PNGs live in [`Architecture/adr/diagrams/`](Architecture/adr/diagrams/). The earlier **consolidated** ADR document is archived at [`Archive/adr/`](Archive/adr/). |
| **Architecture Diagrams Deck** | Presentation / infographic deck (`.pptx` + `.pdf`, `Architecture/diagrams/`) covering the six core architecture views. |

#### Architecture diagrams (`Architecture/diagrams/`)

Full-resolution source images for each of the six core views, in raster (`.png`) and vector (`.svg`) form:

| # | View | Purpose |
|---|---|---|
| 1 | System Architecture Overview | Control plane across Prod / NonProd / DR regions |
| 2 | Quota Group Architecture | Two quota groups per region; Tier-3 quota-neutrality |
| 3 | Placement Engine Flow | Hard-constraint filters + weighted scoring |
| 4 | Steady-State Capacity Lifecycle | Auto-increase triggers, debounce, Phase A/B |
| 5 | Emergency Capacity Transfer | Three-tier crisis response (DR_EVENT_ACTIVE) |
| 6 | VM Disassociation Sequence | Tier-3 execution: Path B default, Path A fallback |

---

## POC test scripts & workbook (`POC-Test-Scripts/`)

The single home for the executable suite **and** its spec of record.

- **Canonical v2.4 POC workbook** ([`POC-Test-Scripts/acrme_poc_workbook_v2_4.md`](POC-Test-Scripts/acrme_poc_workbook_v2_4.md)) — the **POC workbook of record**: 49 test cases across groups G1–G12 (G9–G12 are the v2.4 additions), kept in lock-step with the executable suite. The prior binary v2.0 workbook is archived at [`Archive/testing/`](Archive/testing/).
- **Executable suite** — a fully runnable Python suite implementing every POC case.

### Key design decisions
- **Azure CLI only** — all commands execute via `az` and `az rest`; no Azure Python SDK.
- **Geography-aware region model (v2.4, PLC-010a)** — configuration validation is per-geography:
  three distinct regions are required **only** for three-region geographies (US is the only one
  today); **two-region geographies co-locate CVAL + DR** in the non-prod region while the other
  region hosts Production (ENV-003 / PLC-010a). Middle East is the sole `DR_NOT_OFFERED` case
  (DEC-001). A configuration that co-locates DR in a two-region geography **passes** pre-flight.
- **Dry-run mode** — every command can be logged without live execution for review.
- **Phase-gate evaluation** — gate reports block progression until required tests pass.
- **Resume support** — results persist to JSON; interrupted runs resume without re-running passes.
- **Safe isolation** — all resource names are prefixed `acrme-poc-`, with cleanup notes per test.

### Quick start
```bash
cd POC-Test-Scripts
pip install -r requirements.txt
cp config.yaml.template config.yaml   # then fill in your Azure details

python runner.py preflight            # validate environment prerequisites
python runner.py run --all            # execute the suite
python runner.py gate --phase 1       # evaluate a phase gate
python runner.py report               # generate HTML + Markdown + JSON reports
python runner.py list                 # list all registered tests

python test_region_model.py           # offline region-model checks (no Azure)
python test_v24_reservation_model.py  # offline v2.4 logic checks (no Azure)
```

See [`POC-Test-Scripts/README.md`](POC-Test-Scripts/README.md) for the complete usage guide.
Generated execution evidence is collected under [`Test-Results/`](Test-Results/).

---

## Reference material (`Reference-Material/`)

| Artifact | Description |
|---|---|
| **Calculation Logic Reference** | Every calculation logic organised by the scenarios in which it fires — region-selection scoring (`PS_Prod`/`PS_NonProd`/`PS_DR`), hard-constraint arithmetic, quota-group sizing, DR-floor accounting, forecast, auto-increase, and the scaling/API-budget model — each traced to its source with evidence tags. |
| **Hard Constraints Reference** | Specification of the hard constraints governing regional placement — definitions, formulas, rationale, enforcement pipeline, POC blockers, and validation rules. |
| **Plain-English Walkthrough** | Narrative walkthrough of the engine behaviour for non-specialist readers. |
| **Scoring Weights Explained** | The region-scoring weight model and its rationale. |
| **Security & RBAC Guide** ([`Reference-Material/guides/acrme_security_and_rbac_guide.md`](Reference-Material/guides/acrme_security_and_rbac_guide.md)) | Complete authorization model: every engine operation mapped to Azure permissions, 5 least-privilege custom roles (JSON in [`Reference-Material/rbac/`](Reference-Material/rbac/)), deploy scripts, separation-of-duties, and the G-14 (Tier 3) consent/revocation model. |
| **Executive Presentation** | 14-slide leadership deck (`.pptx` + `.pdf`, [`Reference-Material/presentation/`](Reference-Material/presentation/)). |

#### Product backlog (`Reference-Material/backlog/`)

The full Agile delivery backlog — **19 Epics → 66 Stories → 175 Tasks (426 story points)** — derived from the Production Readiness Review. Epics, Stories (with acceptance criteria), and Tasks are generated from a single Python data module so the Markdown and the Jira-import CSV never drift. See [`Reference-Material/backlog/`](Reference-Material/backlog/).

| Backlog file | Description |
|---|---|
| [`acrme_epics_stories_tasks.md`](Reference-Material/backlog/acrme_epics_stories_tasks.md) | Human-readable backlog (also `.docx` / `.pdf`). |
| [`acrme_backlog_jira_import.csv`](Reference-Material/backlog/acrme_backlog_jira_import.csv) | Jira-importable issue list with Issue ID / Parent ID / Epic Link columns. |
| [`backlog_data.py`](Reference-Material/backlog/backlog_data.py) | Single source of truth; `generate_markdown.py` and `generate_csv.py` render the outputs. |

---

## Archive (`Archive/`)

Superseded / historical documents, retained (not deleted) and isolated from current content.
All carry explicit archive/supersede banners.

| Location | Contents |
|---|---|
| [`Archive/design/`](Archive/design/) | Executive Design Document, Production Readiness Review & Architecture (retained engineering-source narrative), Design-Change & FDD/TDD plan. |
| [`Archive/adr/`](Archive/adr/) | Consolidated Architecture Decision Records (superseded by the split ADRs in `Architecture/adr/`). |
| [`Archive/requirements/`](Archive/requirements/) | Requirements v2.1 (`capacity_and_quota_management_requirements_v2.*`) and the v2.1 deviation analysis. |
| [`Archive/research/`](Archive/research/) | Pre-baseline research inputs — engine design v1.0, multi-region placement design v1.0, design-change summary, traceability review, and the exploratory research POC workbook. |
| [`Archive/testing/`](Archive/testing/) | Binary v2.0 POC workbook (`.docx`/`.pdf`) — content consolidated into the canonical v2.4 workbook. |
| `Archive/README_PHASE3.md`, `Archive/README_PHASE4.md` | Point-in-time build notes. |

---

## Hard constraints (carried across all artifacts)

1. **Geography-aware region placement (PLC-010a).** Production, the non-Production region, and DR
   must be placed per the geography's `distribution_model`: three distinct regions for
   three-region geographies (US only today); CVAL + DR co-located in the single non-Production
   region for two-region geographies. This is enforced programmatically in the suite's
   configuration loader and pre-flight gates. Middle East is the sole `DR_NOT_OFFERED` case (DEC-001).
2. **Azure CLI (`az` / `az rest`) only** — no Azure Python SDK.
3. **All POC resource names are prefixed `acrme-poc-`** for isolation and safe cleanup.
