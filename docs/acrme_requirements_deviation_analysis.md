# ACRME — Requirements v2.1 vs Production-Ready Design: Deviation Analysis

**Document:** Requirements Baseline v2.1 (27 Aug 2026) vs ACRME ADRs v1.2  
**Analyst:** Azure Capacity & Platform Architect  
**Date:** August 2026  
**Classification:** Principal Cloud Architect — Architecture Governance

---

## Executive Summary

Requirements v2.1 represents a significant pivot from the earlier design baseline. The pivot introduces **lean DR bootstrapping**, **distributed/reciprocal DR hosting**, the **max-not-sum sizing formula**, and **exact-region-first onboarding** — all of which are absent from or directly contradict the current ADR design.

**17 deviations identified** across four severity tiers:

| Severity | Count | Areas |
|---|---|---|
| **Critical** | 3 | DR sizing model, DR bootstrap target, Quota group preference |
| **Significant** | 5 | Reciprocal multi-source DR, Source→Destination DR index, Standby activation, Customer seed record, Input-mode priority |
| **Moderate** | 6 | Double-count guard, Reservation formula, Zero-capacity/no-delete, Readiness states, DR_NOT_OFFERED flag, Quota-as-governor |
| **Minor** | 3 | Reconciliation mechanics, Three-region minimum, Configurable region catalogue |

**Recommended action:** Update ADR-001, ADR-002, ADR-003, and ADR-004 to reflect the v2.1 direction. A new ADR-005 (Distributed DR Reference Model) is warranted for the §12A topology. The two-group quota model deviation has a documented design justification — confirm whether QUA-004's preference overrides it before resolving.

---

## Deviation Register

---

### DEV-001 — DR Reserve Sizing: 30–40% Fixed vs Lean Bootstrap

**Severity:** 🔴 Critical  
**Requirement:** ENV-005, DR-007, C-1, C-11  
**Current ADR:** ADR-003, line: `dr_ratio_min=0.30, dr_ratio_max=0.40, dr_ratio_target=0.35`

**Conflict:**

The requirements explicitly pivot away from the 30–40% static reserve model:

> "DR must NOT default to a fixed 30–40% copy of production. Support a configurable bootstrap target. Discussed 30–40% → 10–20% → ~5% → used-is-free. DR starts lean." (ENV-005, DR-007, C-1)

ADR-003 hardcodes `dr_ratio_min=0.30`, `dr_ratio_max=0.40`, `dr_ratio_target=0.35` as normative constants and uses `dr_ratio_max` to size the DR floor. This is the exact v1 model the v2.0 pivot discards. Cost modelling shows this approach runs to **$1.5M–$5M/year** at platform scale — the primary reason leadership required the pivot (§13, Appendix B).

**Required ADR update:**
- Replace fixed `dr_ratio_*` constants with a **configurable bootstrap target** per product/workload/SKU.
- ADR-003 must document that bootstrap capacity = minimum to stand up control planes and begin recovery, not a percentage clone of Prod.
- DR floor formula in ADR-002 (`DR_Floor_vCPU = potential_dr_demand × vCPU_per_instance × dr_ratio_max`) must be rederived against the max-not-sum formula (see DEV-002) rather than a fixed ratio.
- Document the `C-11` configurable override: max-not-sum is default; SUM is available per scope.

---

### DEV-002 — DR Sizing Formula: Percentage-of-Prod vs Max-Not-Sum (A.6)

**Severity:** 🔴 Critical  
**Requirement:** DR-017, Appendix A.6, Appendix D, C-11, POC-011  
**Current ADR:** ADR-003 uses `prod_vm_count × dr_ratio_max`; ADR-004 uses `Forecast_Peak × (1 + Growth_Buffer) + DR_Buffer`

**Conflict:**

Requirements v2.1 introduce a fundamentally different DR destination sizing formula:

```
Destination DR Requirement(d)
  = MAX over non-concurrent source regions s protected by d (
        Workload Portion of s assigned to destination d
    )
```

The current design sizes DR as a percentage of Prod (`30–40% × prod_vm_count`). The requirements replace this with a **distributed, max-over-sources** formula derived from the single-failure assumption (DR-001): because only one region fails at a time, a destination need only hold standby capacity for its **largest** protected source, not the sum.

The requirements quantify the saving: ~40–50% standby reduction, **$0.6M–$2.5M/year** at platform scale (Appendix D.4). The old formula reintroduces exactly the idle-reserve cost the lean bootstrap model was created to eliminate.

ADRs do not mention this formula at all. The current ADR-003 formula (`prod_vm_count × dr_ratio_max`) effectively implements the **sum** approach at a per-region level, which the requirements explicitly mark as incorrect (❌ in Appendix D).

**Required ADR update:**
- ADR-003: Replace the `dr_ratio_*` sizing with Appendix A.6 max-not-sum formula.
- ADR-002: Update `DR_Floor_vCPU` accounting formula to align with distributed portions, not a fixed percentage.
- ADR-004: The `Forecast_Quantity` formula should explicitly separate the Prod growth forecast path from the DR sizing path — they are now governed by different formulas.
- Add POC-011 as a required validation gate before production dependency on the overcommitted model.
- Document the `SUM` override (C-11) as the conservative alternative for specific customer/geography contracts.

---

### DEV-003 — Quota Group Preference: Two-Group Model vs One-Pool Preference

**Severity:** 🔴 Critical (requires explicit decision)  
**Requirement:** QUA-004  
**Current ADR:** ADR-002 — Two groups per region (isolated Prod + shared NonProd+DR)

**Conflict:**

The requirements state:

> "Prefer ONE governed quota group per applicable regional/quota-family scope (prod, non-prod, and DR together) to maximise manipulation flexibility, unless Azure limits or governance boundaries require separation. Final grouping stays configuration-driven." (QUA-004)

The current ADR-002 explicitly **rejects** the single-pool model:

> "Single shared quota pool (all three CRGs) — Breaks Prod isolation — a NonProd surge can consume Prod's quota. [Decided]"

and selects the two-group model.

**Assessment:** This is not a clear error — the ADR documents a reasoned rejection of the single pool. However, the requirements document does not acknowledge or reference this decision. There is a conflict in stated preference that needs a recorded resolution.

**Required action:**
- Determine whether QUA-004 was written with knowledge of the two-group ADR decision or whether it represents a newer business preference.
- If the two-group model is confirmed: update QUA-004 to document that the governance isolation requirement IS the justification for separation, and the "unless governance boundaries require separation" clause applies. ADR-002 already documents this — the requirements need a note that the ADR's two-group model is the approved implementation of QUA-004.
- If one pool is required: ADR-002 must be revised to remove Prod isolation via quota groups and find an alternative Prod protection mechanism.
- Either way, the tension must be **explicitly resolved and recorded** — the current state has the requirement and the ADR pointing in opposite directions with no cross-reference.

---

### DEV-004 — Reciprocal Multi-Source DR Hosting (DR-016): Absent from ADRs

**Severity:** 🟠 Significant  
**Requirement:** DR-016, §12A (Distributed DR Reference Model)  
**Current ADR:** ADR-003 describes NonProd/DR co-location and the state machine, but not the many-to-many topology.

**Gap:**

Requirements v2.1 formalise that every region simultaneously performs three roles:

> "Every region may concurrently perform three roles: (a) Production for its own customers, (b) CVAL host for customers whose production is elsewhere, and (c) standby DR host for customers originating in multiple different source regions." (DR-016)

The worked example in §12A confirms Region 1 simultaneously holds:
- Prod: Cust1, Cust3, Cust5
- CVAL: Cust2, Cust7
- DR standby: Cust2 (source R2), Cust7 (source R3)

ADR-003 only describes the NonProd/DR co-location for a single customer's perspective. It does not model the **bidirectional many-to-many topology** where one destination serves DR for multiple independent source regions concurrently. This is architecturally distinct from the current ADR scope and has major implications for capacity planning (max-not-sum sizing) and state modelling (the DR index, DEV-005).

**Required action:** New ADR-005 or a §12A section in ADR-003 formalising the distributed DR reference topology. Must cover: three-role region model, bidirectional mapping structure, relationship to max-not-sum sizing, and the constraint that single-failure assumption (DR-001) is what permits the overcommitted standby model.

---

### DEV-005 — Source→Destination DR Index (DR-018): Not in ADRs or Data Model

**Severity:** 🟠 Significant  
**Requirement:** DR-018, DAT-002, OBS-004, §12A.1  
**Current ADR:** No mention of a DR index entity.

**Gap:**

The requirements mandate an authoritative bidirectional mapping:

> "Maintain a bidirectional mapping that records, for each source region, which destination regions hold its customers' DR instances and in what quantity/SKU. On a regional failure the engine uses this index to determine exactly which standby instances to activate and where." (DR-018)

The index is also listed as a **minimum required entity** in `DAT-002` and must drive the standby activation workflow (DR-019). No ADR mentions this data entity — neither the structure, cardinality, freshness requirements, nor its relationship to the customer seed record (PLC-003).

**Required action:**
- ADR-003 or a new ADR-005: Define the `SourceDestinationDRIndex` entity — fields: source region, destination region, customer/realm ID, standby instance set, SKU/quantity, activation state, last-updated, policy version reference.
- Cross-reference to seed record (DEV-006 below).
- Must include the observability requirement: dashboard view of source↔destination mapping, per-destination max-source coverage (OBS-004).

---

### DEV-006 — Customer Placement Seed Record (PLC-003 to PLC-005): Absent from ADR-001

**Severity:** 🟠 Significant  
**Requirement:** PLC-003, PLC-004, PLC-005, DAT-002  
**Current ADR:** ADR-001 describes the two input modes (Scenario 1/2) and scoring pipeline. No seed record.

**Gap:**

The requirements define:

> "The first placement decision creates an authoritative seed record: customer/realm identifier, geography, production region, CVAL region, DR region (or NOT_OFFERED), products covered, decision timestamp, policy/engine version, capacity-snapshot reference, exception reference, and approval metadata." (PLC-003)

> "Subsequent products/environments for the same customer + geography read the seed record instead of re-selecting production." (PLC-004)

> "The seed is never regenerated on upgrades, rebuilds, or routine deployments; changes require an approved migration/exception workflow." (PLC-005)

ADR-001 describes how a placement decision is made per invocation but does not model the **persistent, authoritative seed** that makes the first decision binding for all subsequent products. This is a materially different architectural concept — the engine is not re-invoked per product once seeded (PLC-004). The current ADR-001 implies the pipeline runs per-request, which would allow drift across products.

**Required action:**
- ADR-001: Add a `CustomerSeedRecord` entity definition (PLC-003 fields).
- Document the seed-reuse policy (PLC-004) and the controlled-seed-change governance workflow (PLC-005).
- Cross-reference to the DR index (DEV-005) as the reverse view.

---

### DEV-007 — Input Mode Priority: Scenario 1 and 2 Treated Equally vs Exact Region as Primary

**Severity:** 🟠 Significant  
**Requirement:** PLC-001, PLC-002, DEC-003  
**Current ADR:** ADR-001 treats Scenario 1 (geography) and Scenario 2 (specific region) as two equal, equivalent input modes.

**Conflict:**

Requirements v2.1 reverse the priority:

> "PLC-001 — Production region is the primary input. The default onboarding requires selecting the exact Azure production region, not just a broad geography."

> "PLC-002 — Geography-based selection is exceptional. Geography-only selection is retained as an auxiliary path behind exception approval, with documented customer acknowledgement."

The current ADR-001 presents Scenario 1 and Scenario 2 symmetrically — both are standard documented modes. Historically, geography was the dominant path. Under v2.1, geography selection requires an exception process with an approver and binding customer acknowledgement (DEC-003). This reverses the operational default and substantially changes the pipeline entry point.

**Required action:**
- ADR-001: Reframe Scenario 2 (specific region) as the **primary/default** path.
- Reframe Scenario 1 (geography) as an **exception path** requiring approval workflow and customer acknowledgement (add to Exception Deployment Workflow section alongside Restricted region exceptions).
- Update Figure 2 (input modes diagram) to reflect this priority reversal.

---

### DEV-008 — Standby Activation Per Customer in Priority Waves (DR-019): Not in ADR-003

**Severity:** 🟠 Significant  
**Requirement:** DR-019, DR-009, DR-006  
**Current ADR:** ADR-003 defines the five-state machine and three-tier transfer. DR activation semantics documented at the mode level, not per-customer.

**Gap:**

The requirements define a per-customer activation workflow:

> "On an authorised DR declaration, the engine shall transition the failed region's customers' pre-placed DR instances from associated → allocated (inactive/standby → active) in approved business-priority order, acquiring capacity via the staged sequence in DR-006. Activation state per customer must be tracked, auditable, and reversible on failback." (DR-019)

ADR-003's DR Activation Semantics section covers mode-level gating ("entering DR_EVENT_ACTIVE only establishes the operating mode") but does not specify:
- The per-customer `associated → allocated` transition mechanics
- Priority wave sequencing (P0/P-1 first via bootstrap, then rebalancing)
- Per-customer activation state tracking and auditability
- The staged DR-006 acquisition sequence (bootstrap → available quota → CVAL sacrifice → sharing → pooled quota → Azure request)
- Reversibility guarantee on failback (DR-013)

**Required action:**
- ADR-003: Add a normative subsection "Per-Customer DR Activation Workflow" covering the six-stage DR-006 acquisition sequence, priority wave model, `associated → allocated` mechanics, per-customer activation entity fields, and failback reversal.

---

### DEV-009 — CVAL Double-Count Guard (PLC-010): Not Explicitly in ADRs

**Severity:** 🟡 Moderate  
**Requirement:** PLC-010  
**Current ADR:** ADR-003 covers NonProd/DR co-location and HC-6 coverage floor.

**Gap:**

PLC-010 adds a constraint that the current ADR does not make explicit:

> "When CVAL and DR co-locate, the engine must record that the CVAL capacity is earmarked as releasable toward that customer's DR activation, and must not double-count it as both live CVAL and available DR headroom." (PLC-010)

The HC-6 floor formula (`dr_crg_free_slots + nonprod_crg_effective_free ≥ prod_vm_count × dr_ratio_max`) treats `nonprod_crg_effective_free` as headroom — which implies it counts co-located CVAL toward DR. But the **earmarking** (CVAL flagged as committed releasable capacity for a specific customer's DR activation) and the **no-double-count rule** (do not credit it simultaneously as live CVAL AND available DR) are not documented.

**Required action:**
- ADR-003: Add a `CVALEarmarkRecord` entity or field on the seed record indicating which CVAL slots are committed to DR activation. Clarify that earmarked CVAL is counted toward DR headroom only — not toward live CVAL capacity.

---

### DEV-010 — Reservation Target Formula (CAP-003): Not in ADRs

**Severity:** 🟡 Moderate  
**Requirement:** CAP-003, CAP-004, CAP-008  
**Current ADR:** ADR-004 has `Forecast_Quantity = ceil(Forecast_Peak × (1 + Growth_Buffer) + DR_Buffer)`

**Gap:**

Requirements define the fundamental reservation floor formula:

```
Target Reserved Capacity = Allocated VM Count + Configured Buffer
```

explicitly from **allocated (running)** VMs, not associated-but-deallocated. CAP-004 states associated-but-deallocated VMs do not automatically force reservation retention.

The ADR-004 formula is a **forecast-based growth formula** — correct for long-horizon capacity planning, but it is not the same as the continuous **floor reconciliation target** (CAP-003). The two are complementary but distinct. ADRs do not document:
- The `allocated + buffer` floor formula
- The distinction between allocated vs associated VMs in reconciliation
- The policy that associated-but-deallocated VMs are reported separately, not used to size reservations

**Required action:**
- ADR-004: Add the `Target Reserved Capacity = Allocated VM Count + Buffer` floor formula alongside the forecast formula. Clarify that the reconciliation loop uses the floor formula, while the forecast formula drives proactive growth ahead of demand. Document the allocated/associated distinction as normative.

---

### DEV-011 — Zero-Capacity Support and No-Auto-Delete Policy (CAP-009/010): Not in ADRs

**Severity:** 🟡 Moderate  
**Requirement:** CAP-009, CAP-010, FIN-005  
**Current ADR:** Not mentioned.

**Gap:**

Requirements mandate:
- **CAP-009:** Reduce an unused managed reservation to **zero** rather than deleting the reservation object ("set it to zero, don't delete it").
- **CAP-010:** Normal reconciliation never deletes CRGs or reservation definitions; deletion uses a separate approved decommissioning workflow.

These are operationally critical — without them, the reconciliation loop may delete CRGs, which triggers deployment failures when the resource is referenced in the scope file (CAP-002). The FIN-005 note ("the cost-optimisation team already chases orphaned reservations left behind after maintenance — set to zero, don't delete") indicates this is a known operational pattern.

**Required action:**
- ADR-003 or ADR-004: Document zero-capacity policy and no-auto-delete as normative reconciliation constraints.

---

### DEV-012 — Deployment Readiness States (RDY-002): Not in ADRs

**Severity:** 🟡 Moderate  
**Requirement:** RDY-001, RDY-002, RDY-004  
**Current ADR:** Not mentioned.

**Gap:**

The requirements define a machine-readable readiness state for the deployment gate:

```
READY | READY_WITH_RISK | QUOTA_DEFICIT | RESERVATION_DEFICIT |
CAPACITY_UNAVAILABLE | STALE_STATE | POLICY_BLOCKED | VALIDATION_REQUIRED
```

No ADR defines this API surface, the stale-state cut-off (RDY-004), or the readiness gate logic (RDY-001). This is the primary output of the capacity engine to AEP/provisioning.

**Required action:**
- ADR-001 or a new ADR section on the placement output contract: define the readiness state enum, the staleness threshold, and the gate conditions for each state.

---

### DEV-013 — DR_NOT_OFFERED Regional Flag (DR-014): Not in ADRs

**Severity:** 🟡 Moderate  
**Requirement:** DR-014, REG-001, DEC-001  
**Current ADR:** ADR-001 mentions Middle East geo has insufficient Standard regions but does not define a `DR_NOT_OFFERED` policy flag.

**Gap:**

Requirements mandate a per-region/country flag:

> "Support DR_NOT_OFFERED per country/region where legal/data-sovereignty prevents an acceptable DR design (current legal position for Middle East)." (DR-014)

This flag must appear in the region catalogue (`REG-001`), the customer seed record (PLC-003), and the placement pipeline (output: DR region or `NOT_OFFERED`). ADR-001 does not mention it.

**Required action:**
- ADR-001: Add `DR_NOT_OFFERED` as a first-class region attribute in `PlacementPolicy`, document its effect on seed record generation and placement pipeline output, and reference DEC-001 as the pending decision on which geographies carry this flag.

---

### DEV-014 — Quota-as-Governor Strategy (QUA-005): Not Explicitly in ADRs

**Severity:** 🟡 Moderate  
**Requirement:** QUA-005, §2 Strategic Drivers  
**Current ADR:** ADR-002 governs quota groups and accounting. The strategic framing is absent.

**Gap:**

The requirements establish quota-as-governor as a first-class design principle:

> "Use quota allocation to cap deployable capacity by product, environment, subscription, region, and VM family. Do NOT increase a subscription's quota merely because unallocated pooled quota exists — teams must justify need." (QUA-005)

ADR-002 handles the mechanics of quota group accounting but does not document the **governance intent**: quota is a deliberate consumption governor, not just a technical constraint. This matters because it affects auto-increase gating, quota allocation triggers, and the justification model for quota increase requests (QUA-010).

**Required action:**
- ADR-002: Add a context/principle statement documenting the quota-as-governor strategy (Melvin's model) as the strategic basis for the two-group design and the approval-gated increase model.

---

### DEV-015 — Reconciliation Mechanics (CAP-005/CAP-006): Not in ADRs

**Severity:** 🟢 Minor  
**Requirement:** CAP-005, CAP-006, CAP-007, CAP-008  
**Current ADR:** ADR-003/004 mention the reconciliation loop in passing.

**Gap:**

Requirements specify: automated reconciliation every 6 minutes (configurable, production interval TBD), comparing reserved quantity vs allocated vs associated vs available, with raise/lower actions. CAP-007 (alert on scale-up failure) and CAP-008 (scale-down policy with minimum-hold interval and DR protection) are not documented.

**Required action:**
- ADR-004: Add a normative subsection for the reconciliation engine: frequency, comparison inputs (reserved/allocated/associated/available/buffer), raise/lower decision logic, scale-up failure alerting, and scale-down guards.

---

### DEV-016 — Three-Region Minimum as Normative Requirement (REG-003): Not in ADRs

**Severity:** 🟢 Minor  
**Requirement:** REG-003  
**Current ADR:** ADR-001 mentions the Middle East geo issue in context but does not state three-region minimum as a normative design gate.

**Gap:**

Requirements state:

> "Three-to-four regions per geography is a design goal. A two-region model is explicitly identified as problematic — it cannot guarantee sufficient failover capacity if all production concentrates in one location." (REG-003)

**Required action:**
- ADR-001: Document the three-region minimum as a normative constraint on the placement pipeline. A two-region geography is a known limitation (Middle East) requiring explicit governance approval and a `DR_NOT_OFFERED` or cross-geo exception.

---

### DEV-017 — Configurable Region Catalogue with Version Control (REG-001/REG-002): Not Explicit

**Severity:** 🟢 Minor  
**Requirement:** REG-001, REG-002, DAT-005  
**Current ADR:** ADR-001 mentions `PlacementPolicy` as config-as-code. REG-002 (region examples sourced from authoritative config, not slideware) is not mentioned.

**Gap:**

Requirements add two governance requirements not in ADR-001: the region catalogue must be **versioned and configuration-driven** (REG-001) and region examples must be sourced from authoritative configuration only (REG-002 — "Belgium was corrected to Switzerland North during review"). DAT-005 requires scope file version control with decision traceability.

**Required action:**
- ADR-001: Document `PlacementPolicy` as the authoritative, versioned config source; add REG-002 as a governance constraint on documentation and example accuracy.

---

## Alignment Confirmed (No Deviation)

These areas in the requirements are well-covered by the current ADRs:

| Area | Requirements | ADR coverage |
|---|---|---|
| Sequential Prod → CVAL → DR placement | PLC-006 | ADR-001: explicit pipeline |
| Hard separation: Prod ≠ CVAL ≠ DR capacity | ENV-003 | ADR-001: HC-1/HC-4 + ADR-002: two-group model |
| Exception workflow for Restricted regions | PLC-002 (partial) | ADR-001: EC-1..EC-4, VR-3, Exception Deployment Workflow |
| Two-group quota model design rationale | QUA-007 | ADR-002: all three alternatives considered and rejected |
| DR floor accounting formulas | DR-004, DR-005 | ADR-002: DR_Floor_vCPU, Effective_NonProd_Ceiling, NonProd_Headroom, Group_Headroom |
| groupType preview dependency | DEP-001 (partial) | ADR-002: FC-11 preview, version-pin requirement |
| NonProd/DR co-location (HC-1 relaxed) | ENV-003 (note: DR may share with non-prod) | ADR-003: decision item 1 |
| Five-state engine state machine | (overall DR ops) | ADR-003: full state machine table |
| Three-tier emergency transfer | DR-006 stages 1-3 | ADR-003: Tier 1/2/3 with quota-neutral math |
| Approval-gated forecast growth | CAP-007 (partial) | ADR-004: 10-step lifecycle, Phase-1 approval gate |
| Auto-decrease exclusion (Phase 1) | CAP-008 (partial) | ADR-004: explicit exclusion with rationale |
| 80% quota lead-time alerting | OBS-002 | ADR-004: ForecastApproachingQuotaLimit at 14-day lead |
| Capacity sharing scope and POC-001 | CAP-013, QUA-013 | ADR-002: groupType POC dependency documented |
| Middle East geographic constraint | DR-014 (partial) | ADR-001: Middle East geo → cross-geo DR path |
| Region classification tiers | REG-001 (partial) | ADR-001: Standard/Restricted table |
| Weighted placement scoring | PLC-007 | ADR-001: α/β/γ/δ/ε weights, PS_Prod/NonProd/DR |

---

## Summary: ADR Update Workplan

| ADR | Changes Required |
|---|---|
| **ADR-001** | (1) Reframe Scenario 2 (specific region) as primary default; Scenario 1 (geography) as exception path. (2) Add `CustomerSeedRecord` entity and seed-reuse/seed-change governance. (3) Add `DR_NOT_OFFERED` flag in `PlacementPolicy`. (4) Add three-region minimum as normative constraint. (5) Add deployment readiness state enum (RDY-002). (6) Version `PlacementPolicy` config with REG-002 discipline. |
| **ADR-002** | (1) Add quota-as-governor strategic framing. (2) Add explicit cross-reference resolving the QUA-004 vs two-group tension. (3) Update `DR_Floor_vCPU` formula to align with max-not-sum distributed portions rather than fixed ratio. |
| **ADR-003** | (1) Replace `dr_ratio_*` constants with configurable bootstrap target. (2) Replace DR sizing formula with Appendix A.6 max-not-sum. (3) Add per-customer activation workflow (DR-019): associated→allocated transition, priority waves, DR-006 staged acquisition, failback reversal. (4) Add `CVALEarmarkRecord` / double-count guard (PLC-010). (5) Add zero-capacity and no-auto-delete policy (CAP-009/010). (6) Add reciprocal multi-source DR topology (DR-016) and reference to DR index. (7) Add POC-011 as a required validation gate. |
| **ADR-004** | (1) Add `Target = Allocated + Buffer` floor formula alongside forecast formula; clarify allocated/associated distinction. (2) Add reconciliation engine normative spec (frequency, inputs, raise/lower logic, scale-down guards). |
| **ADR-005 (new)** | Distributed DR Reference Model — formalise §12A topology: three-role region model, `SourceDestinationDRIndex` entity definition, bidirectional mapping, max-not-sum relationship, single-failure assumption boundary, observability requirements. |

---

*Generated August 2026. Review cycle: next ADR update pass.*
