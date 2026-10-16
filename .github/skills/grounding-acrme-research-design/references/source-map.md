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
| Repo baseline (v4.0) | `Requirements/acrme_requirements_baseline_v4_0.md` — authoritative |
| Legacy repo baseline (v2.5, filename historical) | `Requirements/acrme_requirements_baseline_v2_4.md` — superseded by v4.0 |
| Historical baseline (v3.0) | `Requirements/acrme_requirements_baseline_v3_0.md` — superseded by v4.0 |
| Optional external/uploaded copy | Supply its path with `check_grounding.py --uploaded-baseline <path>` or `ACRME_UPLOADED_BASELINE`; no host-specific path is assumed |
| Expanded reference | `Requirements/acrme_complete_requirements_reference.md` (rank 5 — explanatory, not normative) |
| Code glossary | `Reference-Material/reference/acrme_requirements_code_glossary.md` (one-line definitions + links) |
| Consistency audit | `Requirements/acrme_consistency_audit_2026-09-17.md` (precedent: uploaded copy drifted behind repo) |

Rule: the highest Document Control version wins. `scripts/check_grounding.py --baseline-only` resolves it. Section numbers below are from the v4.0 baseline; re-check them if the version changed.

The FDD, TDD, POC workbook/suite, glossary, calculation reference, and several mockups/reference
documents still contain earlier-baseline material. Unless an artefact explicitly records a
v4.0 reconciliation, treat it as historical or provisional; do not cite it as current normative
authority over the v4.0 baseline.

## Topic → baseline section → codes → repo artefact

| Topic | Baseline § | Codes | Primary repo artefact(s) |
|---|---|---|---|
| Business context, cost drivers, preview risk | §1, §2 | DEC-001, DEP-001 | — |
| Design principles | §3 | — | `Agents.md` principles |
| Terminology (seed record vs seed reservation, associated vs allocated) | §4 | — | glossary |
| Scope in/out | §5 | — | — |
| Region strategy, catalogue, geography models | §6 | REG-001..003, PLC-010/010a/010b, DR-020 | `Mockups/build_acrme_whatif_acrme_regions.py` (catalogue), `Mockups/acrme_4region_model_comparison.md` |
| Environment policy (Prod / CVAL / DR isolation, core sub) | §7 | ENV-001..007 | ADR-001, ADR-007 |
| Capacity reservation mgmt (target, reconcile, zero-not-delete, sharing, zonal CRG, seed matrix) | §8 | CAP-001..025, CAP-001a | ADR-002, ADR-007, `Reference-Material/reference/acrme_cr_crg_deployment_layout.md`, `acrme_crg_cr_foundation_provisioning_plan.md` |
| Quota (two caps, Quota Groups, earmarks, consumer quota) | §9 | QUA-001..015 | ADR-002, ADR-006 (`adrme_adr_006_quota_reservation_enforcement_boundary.md`) |
| Combined readiness | §10 | RDY-001..004 | `Mockups/acrme_sku_placement_whatif_user_guide.md` (6-state readiness) |
| Region selection & customer placement (CRV customer-scoped) | §11 | PLC-001..005, PLC-007..016 (PLC-006 retired) | ADR-001, `Design/acrme_region_selection_mockup_plan.md` |
| Domain group model (domain-scoped partitioning, DPB) | §12 | DOM-001..004 | — |
| DR capacity (bootstrap, CVAL sacrifice, max-not-sum, reciprocal hosting) | §13 | DR-001..021 | ADR-003, ADR-005 |
| Cost economics & FinOps | §14 | FIN-001..008 | `Reference-Material/reference/ps_prod_nonprod_headroom_design_rationale.md` (α headroom) |
| AEP / provisioning integration | §15 | INT-001..007 | TDD |
| State & data | §16 | DAT-001..006 | `Design/uml_01_core_domain_model.md`, `uml_02_operation_tracking_model.md` |
| Observability | §17 | OBS-001..008 | TDD |
| Governance, security, RBAC | §18 | GOV-001..009 | `Reference-Material/guides/acrme_security_and_rbac_guide.md`, `Reference-Material/rbac/` |
| NFRs | §19 | NFR-001..010 | TDD |
| Operations (runbooks, drills) | §20 | OPS-001..006 | — |
| Unified formulas & calculation reference | §21 | F.1..F.13 | calculation logic reference |
| Acceptance criteria | §22 | — | POC workbook |
| Delivery phases | §23 | — | `Reference-Material/backlog/acrme_epics_stories_tasks.md` |
| Configurable items | §24 | C-xx (C-01..C-16) | calculation logic reference (constants) |
| Pending decisions & POCs | §25 | POC-001..011, DEC-001..003, DEP-001 | `POC-Test-Scripts/acrme_poc_workbook_v2_4.md` |
| Assumptions, constraints, risks | §26 | A-ME1 | — |
| Requirement summary | §27 | — | — |
| Forward-items impact evaluation | §28 | — | — |
| DR sizing formula correction | App. C | — | — |

Design-level docs that cut across topics: `Design/acrme_functional_design_document.md` (FDD), `Design/acrme_technical_design_document.md` (TDD), `Design/acrme_sku_level_capacity_quota_design.md`, `Design/uml_03_service_layer_model.md`, `Design/uml_04_state_machines.md`.

## Formula and scoring sources

| Need | Source (rank order) |
|---|---|
| Reservation target, headroom, deficit, quota deficit, DR destination, γ fairness, CRV, DPB, lineage | Baseline §21 (F.1–F.13), App. C (max-vs-sum correction) |
| Score_Pool(C,R) scoring, α/β/γ/δ/ε terms, constants, scenarios | `Reference-Material/reference/acrme_calculation_logic_reference.md` |
| Worked numbers | `acrme_calculation_logic_comprehensive_walkthrough.md`, `acrme_plain_english_walkthrough.md`, `ACRME_Scoring_Weights_Explained.md` |
| α headroom design rationale | `ps_prod_nonprod_headroom_design_rationale.md` |

If a walkthrough disagrees with the calculation logic reference, the reference wins; if the reference disagrees with §21, the baseline wins.

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

Use Microsoft Learn MCP search/fetch and relevant Azure MCP documentation/service guidance according to SKILL.md Step 3. Discover tools before invocation; aliases differ between hosts. MCP transport does not change source rank or authorize live environment access. If tools are unavailable, disclose the limitation and use direct official documentation where possible.

Verify platform behaviour here before tagging `[Documented]`; record URL + access date.

- On-demand capacity reservation overview, limitations, supported SKUs — `learn.microsoft.com/azure/virtual-machines/capacity-reservation-overview`
- Capacity reservation sharing (Preview) — `learn.microsoft.com/azure/virtual-machines/capacity-reservation-group-share`
- Associate / remove VMs and VMSS, modify reservations — `learn.microsoft.com/azure/virtual-machines/capacity-reservation-associate-vm`, `…-modify`
- Quota Groups — `learn.microsoft.com/azure/quotas/quota-groups`
- vCPU quotas (family + regional caps) — `learn.microsoft.com/azure/virtual-machines/quotas`
- Availability zones / logical-to-physical mapping — `learn.microsoft.com/azure/reliability/availability-zones-overview`
- REST API versions — `learn.microsoft.com/rest/api/compute/capacity-reservation-groups`

URLs are starting points; if one has moved, search Learn rather than citing a stale link.
