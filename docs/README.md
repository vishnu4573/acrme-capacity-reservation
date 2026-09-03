# ACRME Documentation Index

All ACRME design and reference documentation, grouped by purpose. Every narrative document is
provided in three synchronized formats — `.md` (authoritative source), `.docx` (editable), and
`.pdf` (print-ready) — generated from the Markdown source, unless noted otherwise.

> **Single source of truth:** [`requirements/acrme_requirements_baseline_v2_2.md`](requirements/acrme_requirements_baseline_v2_2.md)
> is the authoritative living requirements baseline (v2.2). All other documents reconcile to it.

---

## `requirements/` — WHAT the system must do

| Document | Purpose |
|---|---|
| [`acrme_requirements_baseline_v2_2`](requirements/acrme_requirements_baseline_v2_2.md) | **Authoritative** consolidated requirements baseline (v2.2). Single source of truth. |
| [`acrme_complete_requirements_reference`](requirements/acrme_complete_requirements_reference.md) | All 89 requirements (FR/NFR/R) with Must-Should-Could classification and design-coverage evidence. |
| [`acrme_requirements_deviation_analysis`](requirements/acrme_requirements_deviation_analysis.md) | Deviation analysis between requirements and the production-ready design (17 deviations, 4 severity tiers). |
| [`capacity_and_quota_management_requirements_v2.md`](requirements/capacity_and_quota_management_requirements_v2.md) | Earlier v2 requirements input (historical). |

## `design/` — HOW it is designed

| Document | Purpose |
|---|---|
| [`acrme_executive_design_document`](design/acrme_executive_design_document.md) | Architecture narrative — WAF pillars, ADR decisions, DR model, quota governance, roadmap. |
| [`acrme_functional_design_document`](design/acrme_functional_design_document.md) | Functional design (FDD) — behaviour, flows, functional requirements. |
| [`acrme_technical_design_document`](design/acrme_technical_design_document.md) | Technical design (TDD) — services, schemas, validation gates (incl. weight-sum gate). |
| [`acrme_production_readiness_review_and_architecture`](design/acrme_production_readiness_review_and_architecture.md) | Finalized architecture + Production Readiness Review (authoritative synthesis). |
| [`acrme_design_change_and_fdd_tdd_plan`](design/acrme_design_change_and_fdd_tdd_plan.md) | Design-change log and the FDD/TDD planning bridge. |
| [`acrme_architecture_decision_records`](design/acrme_architecture_decision_records.md) | Consolidated ADRs (also available as standalone records in [`adr/`](adr/)). |
| [`acrme_uml_class_diagrams_summary`](design/acrme_uml_class_diagrams_summary.md) | UML class diagrams (4 sets) with explicit gap analysis. |

## `reference/` — Calculation & rules quick-reference

| Document | Purpose |
|---|---|
| [`acrme_calculation_logic_reference`](reference/acrme_calculation_logic_reference.md) | Every calculation organised by the scenarios where it fires — scoring, HC arithmetic, quota/DR sizing, forecast. |
| [`acrme_hard_constraints_reference`](reference/acrme_hard_constraints_reference.md) | The 10 hard constraints (HC-1..HC-10) and the VR-1..VR-11 validation framework. |
| [`acrme_plain_english_walkthrough`](reference/acrme_plain_english_walkthrough.md) | Plain-English walkthrough of region selection, quota, and capacity logic, with worked examples. |
| [`ACRME_Scoring_Weights_Explained`](reference/ACRME_Scoring_Weights_Explained.md) | Focused explainer on the α/β/γ/δ/ε scoring weights. |

## `guides/` — Operator-facing guides

| Document | Purpose |
|---|---|
| [`acrme_security_and_rbac_guide`](guides/acrme_security_and_rbac_guide.md) | Authorization model: operations → Azure permissions, 5 custom roles, separation-of-duties. Deploy artifacts live in [`rbac/`](rbac/). |

## `testing/` — POC validation

| Document | Purpose |
|---|---|
| [`acrme_poc_workbook_v2`](testing/acrme_poc_workbook_v2.pdf) | POC test workbook — 8 groups, 35 cases, pass/fail criteria (`.docx` / `.pdf`). |

---

## Supporting folders

| Folder | Contents |
|---|---|
| [`adr/`](adr/) | Individual standalone ADR-001..005 (`.md`/`.docx`/`.pdf`) plus rendered diagrams under `adr/diagrams/`. |
| [`backlog/`](backlog/) | Agile delivery backlog — Epics → Stories → Tasks + Jira-import CSV, generated from `backlog_data.py`. |
| [`diagrams/`](diagrams/) | Source architecture diagrams (`.png`/`.svg`/`.mmd`) and the architecture diagrams deck (`.pptx`/`.pdf`). |
| [`presentation/`](presentation/) | Executive slide deck (`.pptx`/`.pdf`) and its build script. |
| [`rbac/`](rbac/) | Custom role JSONs and deployment scripts referenced by the Security & RBAC guide. |
| [`research/`](research/) | Source research documents (raw inputs the Production Readiness Review reconciles). |
| [`tools/`](tools/) | Documentation build/transform helper scripts. |

---

## Conventions

- **Edit the `.md`; the `.docx`/`.pdf` regenerate from it.** Never hand-edit the `.docx`/`.pdf` — they are derived artifacts.
- **`*_preview/` directories are git-ignored** — they are transient HTML preview artifacts, not deliverables.
- **Diagram sources are `.mmd` (Mermaid) / `.svg`; PNGs are rendered outputs.**
