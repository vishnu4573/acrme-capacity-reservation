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
│   └── acrme_production_readiness_review_and_architecture.md / .docx / .pdf
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
| **POC Workbook v2** | Test workbook covering all 8 POC groups and 35 test cases, with pass/fail criteria, evidence tables, risk ratings, and phase-gate checklists. |
| **Production Readiness Review & Architecture** | The finalized architecture and production-readiness review that the executive document and workbook are derived from. |
| **Architecture Diagrams Deck** | Presentation / infographic deck (`.pptx` + `.pdf`) covering the six core architecture views, each with an infographic key-facts slide plus the full diagram. |

Each document is provided in editable (`.docx` / `.md` / `.pptx`) and print-ready (`.pdf`) form.

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
