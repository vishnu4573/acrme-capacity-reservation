# ACRME — Azure Capacity Reservation & Management Enablement

This repository is the consolidated, production-ready design unit for the **ACRME Capacity
Reservation** initiative. It brings together the design documentation, the POC test workbook,
the production-readiness architecture review, and a fully runnable test automation suite that
implements every POC test case.

---

## Repository layout

```
acrme-capacity-reservation/
├── README.md                          # This file
├── docs/                              # Production-ready design artifacts
│   ├── acrme_executive_design_document.docx / .pdf
│   ├── acrme_poc_workbook_v2.docx / .pdf
│   ├── acrme_production_readiness_review_and_architecture.md / .docx / .pdf
│   ├── acrme_security_and_rbac_guide.md / .docx / .pdf
│   ├── research/                      # Source research documents (inputs to the PRR)
│   │   ├── azure_cr_management_engine_design.md
│   │   ├── multi_region_placement_design.md
│   │   ├── design_change_summary.md
│   │   ├── acrme_requirements_traceability_review.md
│   │   └── azure_cr_poc_test_workbook.md
│   └── rbac/                          # Custom role JSONs + deploy scripts
│       ├── custom_roles/*.json        # 5 least-privilege custom roles
│       ├── deploy_custom_roles.sh
│       └── deploy_role_assignments.sh
└── test_suite/                       # Runnable Python test automation suite
    ├── README.md                     # Full suite usage guide
    ├── requirements.txt
    ├── config.yaml.template
    ├── runner.py                     # CLI: preflight / run / report / gate / list
    ├── acrme_suite/                  # Engine, config, az client, reporter, preflight
    └── reports/                      # Generated reports land here (git-ignored)
```

---

## Design artifacts (`docs/`)

| Artifact | Description |
|---|---|
| **Executive Design Document** | Architecture narrative for the ACRME Capacity Reservation initiative — WAF pillars, ADR decisions, DR model, quota governance, and implementation roadmap. |
| **Executive Presentation** | 14-slide leadership deck (`.pptx` + `.pdf`, `docs/presentation/`) distilling the Executive Design Document — the position in one slide, capacity model, automation safety tiers, placement & cross-geo DR, honest what's-working / what's-still-validated split, risks, and the three decisions leadership must make. Each slide is traceable to its source document section. |
| **Complete Requirements Reference** | Consolidates all 89 requirements (FR-1..8, NFR-1..7, R1..8, NFR-R1..3, Must/Should/Could) with evidence of design coverage, maturity ratings, critical POC blockers, and backlog cross-reference — the single traceable source of record for ACRME requirements. |
| **Hard Constraints Reference** | Comprehensive specification of all 10 hard constraints (HC-1..HC-10) governing regional placement — definitions, formulas, rationale, enforcement pipeline (Stage 1 pre-filtering + Stage 2 gate), POC blockers, validation rules (VR-1..VR-11), policy configuration, and implementation checklist with backlog cross-reference. |
| **Calculation Logic Reference** | Consolidates every calculation logic (`.md` / `.docx` / `.pdf`) organised by the 15 scenarios in which they fire — region-selection scoring (`PS_Prod` / `PS_NonProd` / `PS_DR`), hard-constraint arithmetic (HC-3/6/7), quota-group sizing, DR-floor accounting, forecast, auto-increase triggers, tier-escalation quota math, and the scaling/API-budget model — each formula traced to its source section with evidence tags and a consolidated policy-constant table. |
| **POC Workbook v2** | Test workbook covering all 8 POC groups and 35 test cases, with pass/fail criteria, evidence tables, risk ratings, and phase-gate checklists. |
| **Production Readiness Review & Architecture** | The finalized architecture and production-readiness review that the executive document and workbook are derived from. |
| **Architecture Diagrams Deck** | Presentation / infographic deck (`.pptx` + `.pdf`) covering the six core architecture views, each with an infographic key-facts slide plus the full diagram. |
| **UML Class Diagrams Summary** | Design-first UML class diagrams (4 diagram sets) for domain model, operation tracking, service layer, and state machines — with explicit gap analysis. |
| **Security & RBAC Guide** | Complete authorization model: every engine operation mapped to exact Azure permissions, 5 least-privilege custom roles (JSON), deploy scripts, separation-of-duties, and the G-14 (Tier 3) consent/revocation model. |

Each document is provided in editable (`.docx` / `.md` / `.pptx`) and print-ready (`.pdf`) form.

#### Product backlog (`docs/backlog/`)

The full Agile delivery backlog — **19 Epics → 66 Stories → 175 Tasks (426 story points)** — derived directly from the Production Readiness Review. Epics, Stories (each with acceptance criteria), and Tasks are generated from a single Python data module so the Markdown and the Jira-import CSV never drift. See [`docs/backlog/`](docs/backlog/).

| Backlog file | Description |
|---|---|
| [`acrme_epics_stories_tasks.md`](docs/backlog/acrme_epics_stories_tasks.md) | Human-readable backlog (also `.docx` / `.pdf`) — epic index, per-epic story tables, and per-story detail with acceptance criteria and task checklists. |
| [`acrme_backlog_jira_import.csv`](docs/backlog/acrme_backlog_jira_import.csv) | Jira-importable issue list (Epics, Stories, Sub-tasks) with Issue ID / Parent ID / Epic Link linking columns. |
| [`backlog_data.py`](docs/backlog/backlog_data.py) | Single source of truth; `generate_markdown.py` and `generate_csv.py` render the outputs from it. |

#### Research documents (`docs/research/`)

The source research documents that the Production Readiness Review reconciles are published under [`docs/research/`](docs/research/). They are the raw design and test inputs; the PRR is the authoritative, finalized synthesis derived from them.

| Research document | Description |
|---|---|
| [Azure CR Management Engine Design](docs/research/azure_cr_management_engine_design.md) | Original engine design — microservice architecture, CR lifecycle, sharing, quota, placement, DR, forecasting, and the initial backlog. |
| [Multi-Region Placement Design](docs/research/multi_region_placement_design.md) | Final placement design — three-CRG model, quota groups, sequential Prod→NonProd→DR selection, and the `PS_Prod`/`PS_NonProd`/`PS_DR` scoring formulas (HC-1 through HC-8). |
| [Design Change Summary](docs/research/design_change_summary.md) | Consolidated record of design decisions (D1–D9) and the changes they introduced across the architecture. |
| [Requirements Traceability Review](docs/research/acrme_requirements_traceability_review.md) | Coverage analysis mapping functional/non-functional requirements to design elements, with gap identification. |
| [Azure CR POC Test Workbook](docs/research/azure_cr_poc_test_workbook.md) | Full POC test workbook (POC groups and test cases) with pass/fail criteria and evidence tables. |

#### Architecture diagrams (`docs/diagrams/`)

Full-resolution source images for each of the six core views, in both raster (`.png`)
and vector (`.svg`, infinitely zoomable) form:

| # | View | Purpose |
|---|---|---|
| 1 | System Architecture Overview | Control plane across Prod / NonProd / DR regions |
| 2 | Quota Group Architecture | Two quota groups per region; Tier-3 quota-neutrality |
| 3 | Placement Engine Flow | 7 hard-constraint filters + weighted scoring |
| 4 | Steady-State Capacity Lifecycle | Auto-increase triggers, debounce, Phase A/B |
| 5 | Emergency Capacity Transfer | Three-tier crisis response (DR_EVENT_ACTIVE) |
| 6 | VM Disassociation Sequence | Tier-3 execution: Path B default, Path A fallback |

#### UML Class Diagrams (`docs/diagrams/uml_*.md`)

**Design-first tool (70% complete)** — identifies gaps and unresolved design questions:

| # | Diagram | Coverage | Status |
|---|---|---|---|
| 1 | Core Domain Model | CRG, Assignment, Policy, QuotaGroup, Snapshot, Increase, Transfer entities | Entity outlines complete; property types & Cosmos schemas TBD |
| 2 | Operation Tracking Model | Saga pattern, OperationRecord, compensation chains, VM_ImpactRecord, audit | Saga defined; compensation lambda structure TBD |
| 3 | Service Layer Model | PlacementEngine, Reconciliation, Transfer, Quota, Sharing, Zone services | Service boundaries clear; FastAPI contracts & DTOs TBD |
| 4 | State Machines | engine_mode, IncreaseRequest lifecycle, Transfer workflow (Tier 1/2/3) | High-level states defined; transition guards TBD (G-15/B-3 blocker) |

**Purpose:** Visual design tool that explicitly surfaces the 30% of design work still required. Each diagram includes a "Known Gaps" section calling out unresolved questions for focused design sessions.

**Key blockers identified:**
- **G-14:** Consumer credential model for Tier 3 VM disassociation
- **G-15/B-3:** Engine mode state machine (transition guards, concurrency, recovery)
- **Entity schemas:** Cosmos DB partition keys, indexes, TTL for all entities
- **Service contracts:** FastAPI DTOs, RBAC, endpoints for all services

See [`docs/acrme_uml_class_diagrams_summary.md`](docs/acrme_uml_class_diagrams_summary.md) for full analysis and next steps.

---

## Test automation suite (`test_suite/`)

A fully runnable Python suite implementing all 35 POC test cases across 8 groups.

### Key design decisions
- **Azure CLI only** — all commands execute via `az` and `az rest`; no Azure Python SDK.
- **Region distinctness enforced** — configuration load fails if Production, Non-Prod, and DR
  share a region (a hard architectural constraint).
- **Dry-run mode** — every command can be logged without live execution for review.
- **Phase-gate evaluation** — gate reports block progression until required tests pass.
- **Resume support** — results persist to JSON; interrupted runs resume without re-running passes.
- **Safe isolation** — all resource names are prefixed `acrme-poc-`, with cleanup notes per test.

### Quick start
```bash
cd test_suite
pip install -r requirements.txt
cp config.yaml.template config.yaml   # then fill in your Azure details

python runner.py preflight            # validate environment prerequisites
python runner.py run --all            # execute the suite
python runner.py gate --phase 1       # evaluate a phase gate
python runner.py report               # generate HTML + Markdown + JSON reports
python runner.py list                 # list all registered tests
```

See [`test_suite/README.md`](test_suite/README.md) for the complete usage guide.

---

## Hard constraints (carried across all artifacts)

1. **Production, Non-Prod, and DR must not all reside in the same region.** This is enforced
   programmatically in the test suite's configuration loader.
2. **Azure CLI (`az` / `az rest`) only** — no Azure Python SDK.
3. **All POC resource names are prefixed `acrme-poc-`** for isolation and safe cleanup.
