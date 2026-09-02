# ACRME — Design Change Analysis & FDD / TDD Plan

**Against:** Azure Capacity & Quota Management — Consolidated Requirements Baseline **v2.2** (27 Aug 2026)
**Prepared:** 2 Sep 2026 · **Owner:** Vishnuvardhan Reddy
**Purpose:** (A) enumerate the changes required to the *original design* so it reconciles with Requirements Baseline v2.2, and (B) plan the creation of a new **Functional Design Document (FDD)** and **Technical Design Document (TDD)** with the diagrams each needs.

---

## 0. Method & Baseline Reconciliation

The uploaded *Consolidated Requirements Baseline* was compared line-by-line against the in-repo baseline (`acrme_requirements_baseline_v2_2.md`) and the existing design corpus.

- **Requirement set is identical to repo v2.2** — same requirement IDs (REG/ENV/CAP/QUA/RDY/PLC/DR/FIN/INT/DAT/OBS/GOV/NFR/OPS/POC/DEC/DEP and the C-/DEV- registers); no new or removed IDs. The uploaded file is therefore confirmed as the authoritative v2.2 requirements baseline, not a new revision.
- **The gap is design-side, not requirements-side.** The requirements pivot (lean DR bootstrap, distributed/reciprocal DR, max-not-sum sizing, exact-region-first onboarding, seed record, source→destination DR index, standby activation, CVAL earmarking, quota-as-governor) is fully expressed in the baseline but only **partially** reflected in the design artifacts.

**Current design corpus (the "original design")**

| Artifact | Alignment to v2.2 today |
|---|---|
| `acrme_production_readiness_review_and_architecture.md` (PRR + Final Architecture, §1–§45) | **Mostly aligned** — already adopted lean/distributed/max-not-sum/exact-region/seed/reciprocal/index/earmark/zero-capacity model. **One material stale item:** cross-geo DR still names **Belgium Central** (must be **Switzerland North**). |
| `acrme_architecture_decision_records.md` (ADR-001…004) | **Lagging** — still fixed-ratio DR, equal input modes, no seed record, no DR index, no standby-activation workflow, no reciprocal topology, no max-not-sum. Needs ADR-001…004 updates + **new ADR-005**. |
| `acrme_executive_design_document.md` | **Lagging** — region table names Belgium Central; DR/placement narrative predates max-not-sum, reciprocal hosting, seed reuse. |
| `acrme_calculation_logic_reference.md` (v2.2) | **Aligned** — already carries max-not-sum (DR-017) and Switzerland North. Verify all worked examples use Switzerland North + max-not-sum. |
| `acrme_hard_constraints_reference.md` | **Lagging** — HC-10 / Middle East DR path still Belgium Central. |
| `acrme_complete_requirements_reference.md` | Re-map to v2.2 IDs; confirm 100% coverage of DR-016…019, PLC-010. |
| `acrme_uml_class_diagrams_summary.md` | **Lagging** — no `CustomerSeedRecord`, `SourceDestinationDRIndex`, `CVALEarmarkRecord` classes. |
| `acrme_requirements_deviation_analysis.md` | Reference input — its 17-item register + ADR workplan drive Part A below. |

> **No FDD or TDD exists yet.** The nearest analogues are the Executive Design Document (business-facing) and the PRR/Final Architecture (engineering-facing). The plan in Parts B–C treats these as source material, not replacements.

---

## Part A — Changes Required to the Original Design

Changes are grouped by theme, each mapped to the driving **requirement IDs**, the existing **deviation IDs** (DEV-nn), affected **artifacts**, and **severity**. Status reflects what the PRR already absorbed versus what still needs work.

### A.1 Global correction — Cross-geo DR region (REG-002) — 🔴 blocking, mechanical

**Change:** Replace every operative use of **Belgium Central** with **Switzerland North** as the authoritative EU cross-geo DR extension region for Middle East deployments. Keep "Belgium" only where it appears as the *historical example of a corrected mistake* (REG-002 narrative).

**Affected (confirmed by scan):** PRR/architecture (§27 region tables, cross-geo extension paths, VR-6, HC-10 references, the Mermaid Middle-East decision tree, capacity-planning notes — ~15 occurrences), executive design (§6 region table), ADRs, hard constraints reference. Calc logic already corrected.

### A.2 DR sizing model — fixed-ratio → max-not-sum (DR-017, A.6, App. D) — 🔴 Critical — DEV-001, DEV-002

- Replace `dr_ratio_*` constants and any percentage-of-prod DR floor with the **max-not-sum** destination-sizing formula: `Destination DR Requirement(d) = MAX over non-concurrent sources s protected by d ( workload portion of s on d )`.
- Add the **overcommit ratio** (A.8) and **DR capacity gap** (A.7) as first-class engine outputs.
- Retain a configurable **SUM override** (C-11) for customers/contracts requiring concurrent-failure protection.
- Rederive **ADR-002 `DR_Floor_vCPU`** against distributed portions; update PRR §26 (formulas), §31 (DR activation), §12A linkage.

### A.3 Reciprocal multi-source DR hosting (DR-016) — 🟠 Significant — DEV-004

- Model the **many-to-many** topology: each region simultaneously acts as Prod, CVAL host, and DR standby for **multiple different** source regions. Add to ADR-003/new ADR-005 and to the logical architecture (PRR §23, §31).

### A.4 Source→destination DR index (DR-018) — 🟠 Significant — DEV-005

- Add `SourceDestinationDRIndex` as a **required state entity** (DAT-002) and to the data architecture (PRR §34), state model (§29), ADR-003/005, and UML summary. It is the reverse view of the seed record and drives standby activation.

### A.5 Standby activation on declaration (DR-019) — 🟠 Significant — DEV-008

- Specify per-customer **associated → allocated** transition in **business-priority waves** (DR-009), driven by the DR index, executed through the **staged acquisition** sequence (DR-006), reversible on failback (DR-013). Add to ADR-003 and PRR §31; add runbook (OPS-001).

### A.6 Customer placement seed record (PLC-003…005) — 🟠 Significant — DEV-006

- Add `CustomerSeedRecord` (prod/CVAL/DR regions, products, policy version, snapshot ref, exception + approval metadata), **seed-once/reuse-across-products**, and **governed seed-change** workflow. Add to ADR-001, PRR §29/§34, UML summary.

### A.7 Exact-region-first onboarding (PLC-001/002) — 🟠 Significant — DEV-007

- Make **exact production region the default validated input**; **geography-only** selection becomes an **exception path** (explicit approval + acknowledgement that the derived region is fixed until a governed migration). Reframe ADR-001 Scenario 1 as primary, Scenario 2 as exception. (PRR already reflects this; ADR + executive design do not.)

### A.8 CVAL/DR co-location & double-count guard (PLC-010) — 🟡 Moderate — DEV-009

- Add `CVALEarmarkRecord` and the rule that earmarked CVAL is **not** double-counted as both live CVAL and available DR headroom. ADR-003, PRR §31/§34.

### A.9 Quota grouping decision — two-group vs single governed pool (QUA-004) — 🔴 Critical (decision) — DEV-003

- The design's **two-quota-group** model conflicts with the baseline **single governed pool preference**. This needs an explicit **decision** recorded in ADR-002 (resolve the tension; document why the chosen model wins). *Requires confirmation — see Part F.*

### A.10 Remaining reconciliations (Moderate/Minor) — DEV-010…017

- **CAP-003** `Target = Allocated + Buffer` floor formula + allocated/associated distinction → ADR-004.
- **CAP-009/010** zero-capacity ("set to zero, don't delete") + no-auto-delete → ADR-003/004.
- **RDY-002** readiness-state enum (`READY`, `READY_WITH_RISK`, `QUOTA_DEFICIT`, `RESERVATION_DEFICIT`, `CAPACITY_UNAVAILABLE`, `STALE_STATE`, `POLICY_BLOCKED`, `VALIDATION_REQUIRED`) → ADR-001, API architecture §35.
- **DR-014** `DR_NOT_OFFERED` flag → ADR-001 `PlacementPolicy`.
- **QUA-005** quota-as-governor strategic framing → ADR-002.
- **CAP-005/006** reconciliation mechanics (6-min container-app job, raise/lower logic, scale-down guards) → ADR-004.
- **REG-003** three-region minimum as normative constraint; **REG-001/002** configurable, versioned region catalogue → ADR-001.

### A.11 New/updated ADRs (from deviation workplan)

| ADR | Action |
|---|---|
| ADR-001 | Exact-region-first; seed record; `DR_NOT_OFFERED`; three-region minimum; readiness enum; versioned region catalogue. |
| ADR-002 | Quota-as-governor; resolve QUA-004 vs two-group; rederive `DR_Floor_vCPU` to max-not-sum. |
| ADR-003 | Configurable bootstrap; max-not-sum; standby activation waves; CVAL earmark/double-count guard; zero-capacity/no-delete; reciprocal topology; POC-011 gate. |
| ADR-004 | `Allocated + Buffer` floor formula; reconciliation engine normative spec. |
| **ADR-005 (new)** | Distributed DR Reference Model — §12A topology, `SourceDestinationDRIndex`, bidirectional mapping, max-not-sum boundary, single-failure assumption, observability. |

### A.12 Cross-cutting artifact updates

- **UML class diagrams:** add `CustomerSeedRecord`, `SourceDestinationDRIndex`, `CVALEarmarkRecord`, readiness-state enum.
- **Observability:** add per-destination DR max-source coverage metric/alert (OBS-001/002) and source↔destination DR mapping dashboard view (OBS-004).
- **Complete Requirements Reference:** re-map to v2.2 IDs; confirm DR-016…019 + PLC-010 coverage.
- **Executive Design Document:** refresh region table, DR narrative (distributed + max-not-sum), placement narrative (exact-region + seed reuse), Switzerland North.

---

## Part B — Functional Design Document (FDD) Plan

**Goal:** describe *what* ACRME does — the functional behaviour, flows, states, and rules — traceable to every v2.2 requirement ID. Business/architecture/ops/audit audience; implementation-neutral.

**Primary sources:** Requirements Baseline v2.2; Executive Design Document; PRR Part II (§19–§22, §27, §30, §31); Calculation Logic Reference (functional formulas only).

### B.1 Proposed structure

1. Introduction — purpose, audience, scope (in/out per §5), definitions (§4), traceability approach.
2. Solution overview — capability map (Capacity, Quota, Placement/Seed, DR, Cost/FinOps, Observability, Governance) → requirement groups.
3. Actors & stakeholders — AEP, platform operator, DR coordinator, FinOps, onboarding, auditor, Microsoft dependency.
4. Functional capabilities (one sub-section per domain, each with rules + requirement IDs):
   4.1 Capacity reservation management (CAP-001…019) — allocated+buffer, reconciliation behaviour, zero-capacity, over-allocation, sharing.
   4.2 Quota management (QUA-001…014) — pooling / quota-as-governor / growth buffer / reclamation.
   4.3 Combined readiness (RDY-001…004) — deployment gate, readiness states, staleness.
   4.4 Region selection & customer placement (PLC-001…010, REG-001…003) — exact-region default, geography exception, seed lifecycle, weighting, co-location.
   4.5 Disaster recovery (DR-001…019) — distributed DR, reciprocal hosting, staged acquisition, standby activation waves, drills, failback, `DR_NOT_OFFERED`.
   4.6 Cost & FinOps (FIN-001…008) — idle cost, cost-before-expansion, shared-DR overcommit accounting.
   4.7 Provisioning & AEP integration (INT-001…007) — functional contract in/out, idempotency.
   4.8 Observability & governance (OBS, GOV, OPS) — metrics/alerts/dashboards, exceptions, break-glass, runbooks.
5. End-to-end functional flows — onboarding+placement, steady-state reconciliation, single-region DR event, DR drill/failback.
6. Functional states — deployment readiness states; engine mode machine (functional view).
7. Acceptance criteria mapping (§20 → FDD sections).
8. Assumptions, decisions, POC dependencies (§22–§24).
9. Requirement traceability matrix (every v2.2 ID → FDD section).

### B.2 FDD diagrams

| # | Diagram | Type |
|---|---|---|
| F1 | System context (ACRME ↔ AEP, Azure, operators, auditors) | Context |
| F2 | Capability map → requirement groups | Block |
| F3 | Actor / use-case overview | Use-case |
| F4 | Onboarding + placement flow (exact-region default; geography exception + seed) | Flowchart |
| F5 | Steady-state reconciliation behaviour (allocated+buffer, scale up/down guards) | Flowchart |
| F6 | Distributed DR Reference Model (§12A) | **Reuse** existing `acrme_three_region_capacity_model.png` |
| F7 | DR event → standby activation waves (functional sequence) | Sequence |
| F8 | Deployment readiness state model (RDY-002) | State |

---

## Part C — Technical Design Document (TDD) Plan

**Goal:** describe *how* ACRME is built — components, data, algorithms, interfaces, runtime, security, NFRs. Engineering audience.

**Primary sources:** PRR Part II (§23–§39) & Part III (§40–§43); ADRs (post-update, incl. ADR-005); Calculation Logic Reference; UML class diagrams; Hard Constraints; Security & RBAC guide.

### C.1 Proposed structure

1. Introduction — scope, relationship to FDD, decision records referenced.
2. Architecture overview — principles/rationale (§20), constraints (§21).
3. Logical component architecture (§23) — inventory collector, reconciler, placement/scoring engine, quota-pool manager, DR orchestrator, readiness API, state store, config/scope-file service.
4. Runtime & deployment — container-app reconciliation job (6-min, tunable, CAP-006), function-app placement flow (PLC-009), API surface.
5. Topology — management group/subscription model (§24); CRG hierarchy & sharing incl. zone-alignment FC-06 (§25); quota-group architecture + single-pool decision (§26, QUA-004).
6. Data architecture (§34, DAT-001…006) — entity model incl. `CustomerSeedRecord`, **`SourceDestinationDRIndex`**, `CVALEarmarkRecord`, DR distribution plans; freshness metadata; versioning.
7. State model & concurrency (§29, NFR-002/007) — five-state engine machine, optimistic concurrency, reservation-of-intent.
8. Placement scoring & forecasting (§28) — PS_Prod / PS_NonProd / PS_DR, weights α=0.30/β=0.20/γ=0.25/δ=0.15/ε=0.10, normalization, determinism/replay.
9. DR sizing & activation algorithms (§31, App. A.6/A.7/A.8, App. D) — max-not-sum, overcommit ratio, gap; standby activation waves; staged acquisition (DR-006); tier escalation (§32).
10. Steady-state capacity lifecycle (§30) — 10-step sequence.
11. API architecture (§35, INT-001…007) — request/response contracts, idempotency keys, error/readiness codes.
12. Security — RBAC & managed identity (§36, GOV-001…009), break-glass, secrets.
13. Observability implementation (§37, OBS-001…005) — metrics incl. per-destination DR max-source coverage; alerts; dashboards incl. source↔destination mapping.
14. NFRs & resilience (§38, NFR-001…010) — throttling resilience, degraded mode, simulation/dry-run incl. DR failover simulation.
15. Integration — AKS/VMSS & AEP (§33, §6 review).
16. POC & validation dependencies (§42) — POC-001 (sharing quota), POC-006 (DR topology), POC-007 (bootstrap sizing), POC-011 (max-not-sum overcommit safety); gating.
17. Traceability — requirement/deviation → component/algorithm/entity.

### C.2 TDD diagrams

| # | Diagram | Type | Source |
|---|---|---|---|
| T1 | Logical component architecture | Component | §23 |
| T2 | Management group / subscription topology | Deployment | §24 |
| T3 | CRG hierarchy & cross-subscription sharing (zone alignment FC-06) | Architecture | §25 |
| T4 | Quota-group / pool architecture (single-pool model) | Architecture | §26; reuse `adr002_quota_groups` |
| T5 | Data model / ERD incl. seed record + **SourceDestinationDRIndex** + CVAL earmark | ERD | §34, DAT-002 |
| T6 | Five-state engine machine | State | §29; reuse `adr003_state_machine` |
| T7 | Staged placement pipeline | Flow | reuse `adr001_pipeline` |
| T8 | Prod region input modes (exact vs geography exception) | Flow | reuse `adr001_input_modes` |
| T9 | Steady-state 10-step capacity lifecycle | Sequence | §30; reuse `adr004_lifecycle` |
| T10 | Three-tier emergency transfer escalation | Flow | §32; reuse `adr003_transfer_tiers` |
| T11 | DR standby activation sequence (index lookup → waves → staged acquisition) | Sequence | **new**, §31 |
| T12 | Max-not-sum sizing illustration (overcommit ratio) | Diagram | **new**, App. D |
| T13 | Distributed DR Reference Model (§12A) | **Reuse** `acrme_three_region_capacity_model.png` | §12A |
| T14 | Class diagrams (updated with new entities) | Class | UML summary |

---

## Part D — Diagram Inventory Summary

- **Reuse as-is (7):** staged placement pipeline, prod input modes, quota groups, transfer tiers, state machine, capacity lifecycle, distributed DR reference model.
- **New required (5):** F4 onboarding+placement (functional), F7/T11 DR standby activation sequence, F8 readiness state model, T5 data-model ERD with new entities, T12 max-not-sum/overcommit illustration.
- **Update (2):** T14 class diagrams (+3 entities), region tables/diagrams to Switzerland North.

---

## Part E — Work Plan & Sequencing

1. **Design reconciliation (Part A) — do first, unblocks FDD/TDD**
   a. Global Belgium→Switzerland North replacement (A.1).
   b. Update ADR-001…004 + author ADR-005 (A.11) — resolve QUA-004 decision (A.9) as a prerequisite.
   c. Refresh executive design, hard constraints, UML, complete-requirements mapping (A.12).
2. **Author FDD** (Part B) — MD → DOCX → PDF, diagrams F1–F8.
3. **Author TDD** (Part C) — MD → DOCX → PDF, diagrams T1–T14.
4. **Traceability pass** — every v2.2 ID mapped in FDD and TDD; deviation register closed.
5. **Commit** each stage to `master` (MD + DOCX + PDF), consistent with existing doc pipeline.

**Deliverable formats (assumed, per established convention):** Markdown source of truth + auto-generated DOCX + PDF, diagrams as self-contained HTML + high-res PNG, all committed to the repo.

---

## Part F — Open Decisions Needing Confirmation

1. **Quota grouping (A.9 / QUA-004 / DEV-003):** confirm whether the baseline's **single governed pool** preference overrides the design's **two-quota-group** model, or whether the two-group model is retained with documented justification. This changes ADR-002, TDD §5, and quota diagrams.
2. **FDD/TDD relationship to existing docs:** produce FDD and TDD as **net-new standalone documents** (recommended) that supersede the Executive Design Document (→ FDD) and consolidate PRR Part II (→ TDD)? Or keep all existing docs and add FDD/TDD as additional layers?
3. **Scope of this engagement now:** deliver **this plan only** for review, or proceed straight into Part A reconciliation + FDD/TDD authoring?
4. **Output formats:** confirm MD + DOCX + PDF committed to repo (assumed), or a different target (e.g., Confluence/single combined doc).
