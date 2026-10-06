# ACRME source map

## Contents
- Baseline location and version rule
- Topic → baseline section → codes → repo artefact
- Formula and scoring sources
- Mockups and their builders
- Decision and constraint registers
- Microsoft Learn starting points

## Baseline location and version rule

| Candidate | Path |
|---|---|
| Repo baseline | `Requirements/acrme_requirements_baseline_v2_4.md` (filename is historical — read the Document Control `Version` row) |
| Uploaded copy | `/home/ubuntu/Uploads/Azure Capacity & Quota Management- Consolidated Requirements Baseline.md` |
| Expanded reference | `Requirements/acrme_complete_requirements_reference.md` (rank 5 — explanatory, not normative) |
| Code glossary | `Reference-Material/reference/acrme_requirements_code_glossary.md` (one-line definitions + links) |
| Consistency audit | `Requirements/acrme_consistency_audit_2026-09-17.md` (precedent: uploaded copy drifted behind repo) |

Rule: the highest Document Control version wins. `scripts/check_grounding.py --baseline-only` resolves it. Section numbers below are from the baseline; re-check them if the version changed.

## Topic → baseline section → codes → repo artefact

| Topic | Baseline § | Codes | Primary repo artefact(s) |
|---|---|---|---|
| Business context, cost drivers, preview risk | §1, §2 | DEC-001, DEP-001 | — |
| Design principles | §3 | — | `Agents.md` principles |
| Terminology (seed record vs seed reservation, associated vs allocated) | §4 | — | glossary |
| Scope in/out | §5 | — | — |
| Region strategy, catalogue, geography models | §6 | REG-001..003, PLC-010/010a/010b, DR-020 | `Mockups/build_acrme_whatif_acrme_regions.py` (catalogue), `Mockups/acrme_4region_model_comparison.md` |
| Environment policy (Prod / CVAL / DR isolation, core sub) | §7 | ENV-001..007 | ADR-001, ADR-007 |
| Capacity reservation mgmt (target, reconcile, zero-not-delete, sharing, zonal CRG, seed matrix) | §8 | CAP-001..024, CAP-001a | ADR-002, ADR-007, `Reference-Material/reference/acrme_cr_crg_deployment_layout.md`, `acrme_crg_cr_foundation_provisioning_plan.md` |
| Quota (two caps, Quota Groups, earmarks, consumer quota) | §9 | QUA-001..014 | ADR-002, ADR-006 (`adrme_adr_006_quota_reservation_enforcement_boundary.md`) |
| Combined readiness | §10 | RDY-001..004 | `Mockups/acrme_sku_placement_whatif_user_guide.md` (6-state readiness) |
| Region selection & customer placement (seed record) | §11 | PLC-001..011 | ADR-001, `Design/acrme_region_selection_mockup_plan.md` |
| DR capacity (bootstrap, CVAL sacrifice, max-not-sum, reciprocal hosting) | §12, §12A, App. D | DR-001..020 | ADR-003, ADR-005 |
| FinOps | §13 | FIN-001..008 | `Reference-Material/reference/ps_prod_nonprod_headroom_design_rationale.md` (α headroom) |
| AEP / provisioning integration | §14 | INT-001..007 | TDD |
| State & data | §15 | DAT-001..006 | `Design/uml_01_core_domain_model.md`, `uml_02_operation_tracking_model.md` |
| Observability | §16 | OBS-001..005 | TDD |
| Governance, security, RBAC | §17 | GOV-001..009 | `Reference-Material/guides/acrme_security_and_rbac_guide.md`, `Reference-Material/rbac/` |
| NFRs | §18 | NFR-001..010 | TDD |
| Operations (runbooks, drills) | §19 | OPS-001..006 | — |
| Acceptance criteria | §20 | — | POC workbook |
| Delivery phases | §21 | — | `Reference-Material/backlog/acrme_epics_stories_tasks.md` |
| Configurable items | §22 | C-xx | calculation logic reference (constants) |
| Pending decisions & POCs | §23 | POC-001..011, DEC-001..003, DEP-001 | `POC-Test-Scripts/acrme_poc_workbook_v2_4.md` |
| Assumptions, constraints, risks | §24 | A-ME1 | — |
| Core formulas | App. A | A.1..A.6 | calculation logic reference |

Design-level docs that cut across topics: `Design/acrme_functional_design_document.md` (FDD), `Design/acrme_technical_design_document.md` (TDD), `Design/acrme_sku_level_capacity_quota_design.md`, `Design/uml_03_service_layer_model.md`, `Design/uml_04_state_machines.md`.

## Formula and scoring sources

| Need | Source (rank order) |
|---|---|
| Reservation target, headroom, deficit, quota deficit, DR destination | Baseline App. A (A.1–A.6), App. D |
| PS_Prod / PS_NonProd / PS_DR scoring, α/β/γ terms, constants, scenarios | `Reference-Material/reference/acrme_calculation_logic_reference.md` |
| Worked numbers | `acrme_calculation_logic_comprehensive_walkthrough.md`, `acrme_plain_english_walkthrough.md`, `ACRME_Scoring_Weights_Explained.md` |
| α headroom design rationale | `ps_prod_nonprod_headroom_design_rationale.md` |

If a walkthrough disagrees with the calculation logic reference, the reference wins; if the reference disagrees with App. A, the baseline wins.

## Mockups and their builders

Workbooks are generated — change the builder script, never hand-edit the `.xlsx`.

| Workbook | Builder | Guide |
|---|---|---|
| `acrme_region_selection_whatif_acrme_regions.xlsx` (Phase 1 region scoring) | `build_acrme_whatif_acrme_regions.py` | `…_acrme_regions_user_guide.md` |
| `acrme_sku_placement_whatif.xlsx` (Phase 2 multi-SKU, Meets-All MIN gate, 6-state readiness) | `build_acrme_sku_scoring_whatif.py` | `acrme_sku_placement_whatif_user_guide.md` |
| `acrme_aligned_placement_whatif.xlsx` | `build_acrme_aligned_placement.py` | `acrme_aligned_placement_whatif_user_guide.md` |
| `acrme_region_selection_whatif_4region.xlsx` | `build_acrme_whatif_4region.py` | `acrme_4region_model_comparison.md` |

All under `Mockups/`.

## Decision and constraint registers

| Register | Path |
|---|---|
| ADRs 001–007 (+ ADR-007 dual-path variance) | `Architecture/adr/` (index in `README.md` there) |
| Hard constraints HC-1..HC-11 (authoritative numbering: Part 2 table) | `Reference-Material/reference/acrme_hard_constraints_reference.md` |
| Skill procedures SK-01..SK-13 | `Skills.md` |
| Agent roster and boundary rules | `Agents.md` |
| Backlog (epics/stories/tasks) | `Reference-Material/backlog/` (generated from `backlog_data.py`) |

## Microsoft Learn starting points

Verify platform behaviour here before tagging `[Documented]`; record URL + access date.

- On-demand capacity reservation overview, limitations, supported SKUs — `learn.microsoft.com/azure/virtual-machines/capacity-reservation-overview`
- Capacity reservation sharing (Preview) — `learn.microsoft.com/azure/virtual-machines/capacity-reservation-group-share`
- Associate / remove VMs and VMSS, modify reservations — `learn.microsoft.com/azure/virtual-machines/capacity-reservation-associate-vm`, `…-modify`
- Quota Groups — `learn.microsoft.com/azure/quotas/quota-groups`
- vCPU quotas (family + regional caps) — `learn.microsoft.com/azure/virtual-machines/quotas`
- Availability zones / logical-to-physical mapping — `learn.microsoft.com/azure/reliability/availability-zones-overview`
- REST API versions — `learn.microsoft.com/rest/api/compute/capacity-reservation-groups`

URLs are starting points; if one has moved, search Learn rather than citing a stale link.
