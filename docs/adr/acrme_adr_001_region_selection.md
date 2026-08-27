**Project:** Azure Capacity Reservation Management Engine (ACRME)  
**Classification:** Principal Cloud Architect — Architecture Governance  
**Version:** 1.1  
**Date:** August 2026  
**Status:** Accepted  
**Part of:** ACRME Architecture Decision Records — this is one of four standalone ADRs split from the consolidated ADR set.

> **About ADRs.** An Architecture Decision Record captures a single significant architectural decision, the context that forced it, the options considered, the choice made, and its consequences. ADRs are immutable once accepted — a superseding decision is recorded as a new ADR rather than editing the original. Evidence tags: `[Documented]`, `[Decided]`, `[Derived]`, `[Assumed]` (see Appendix).

---

# ADR-001 — Region Selection

**Status:** Accepted  
**Date:** August 2026  
**Deciders:** Principal Cloud Architect, Platform Engineering, DR Owner  
**Related decisions:** D1, D4, D5, D8, D9; HC-1..HC-10; VR-1..VR-11  
**Source:** `multi_region_placement_design.md` §27–28; `acrme_production_readiness_review_and_architecture.md` §27

### Context

Customers request capacity by supplying either a specific Azure region or an Azure geography (e.g. "US", "Europe", "Middle East"). The engine must derive three environment regions — **Prod**, **NonProd/CVAL**, and **DR** — that satisfy isolation, resilience, capacity, quota, and data-residency requirements.

Forces at play:

- Azure regions differ in SKU availability, zone count, capacity headroom, and quota posture. A naive "pick the nearest region" approach silently produces single-zone or capacity-starved placements.
- Some regions are **Restricted Capacity Regions** (sovereign clouds, limited-SKU regions) that must never be selected by automated placement.
- Certain geographies (notably the **Middle East**, with only UAE North and Saudi Arabia Central) do not have enough Standard regions to satisfy a three-region model in-geo, forcing a governed cross-geo DR path.
- Placement decisions must be **deterministic, auditable, and replayable** — the same inputs must always produce the same output, and every decision must be reconstructable for compliance.

### Decision

Adopt a **staged, constraint-then-score placement pipeline** driven by environment-type-specific scoring formulas:

1. **Stage 1 — Eligibility pre-filtering.** Reduce all Azure regions to Standard Capacity Regions within the customer's geography.
   - **HC-9 STANDARD_REGION_ONLY** excludes Restricted regions before scoring. `[Decided — D9]`
   - **HC-8 GEOGRAPHY_CONTAINMENT** confines the Prod anchor to the customer's chosen geography. `[Derived]`

2. **Stage 2 — Hard-constraint gate.** Each surviving region must pass **HC-1..HC-7 and HC-10** (region separation, capacity floor, quota floor, DR separation class, zone availability, DR coverage floor, DR floor integrity, cross-geo extension approval). Any failure excludes the region from scoring entirely — hard constraints are binary gates, never scored penalties. `[Decided — D4]`

3. **Stage 3 — Environment-type-specific scoring.** Rank survivors using three formulas sharing default weights (α=0.30, β=0.20, γ=0.25, δ=0.15, ε=0.10) but with env-type-specific semantics for α (capacity signal) and δ (DR readiness): `[Decided — D9]`
   ```
   alpha (α) = 0.30   # capacity / headroom signal
   beta  (β) = 0.20   # quota headroom signal
   gamma (γ) = 0.25   # capacity-weighted distribution
   delta (δ) = 0.15   # DR-coverage / overflow-integrity signal
   epsilon(ε)= 0.10   # zone diversity
   Clamp(x)  = max(0, min(1, x))       # every component clamped to [0,1] before weighting
   
   ```
   - **Prod:** `Prod_region = argmax(PS_Prod(r))` over eligible Standard regions in-geo.
   - **NonProd/CVAL:** `argmax(PS_NonProd(r))` over survivors, excluding the Prod region.
   - **DR:** `argmax(PS_DR(r))` over survivors, excluding the Prod region (but **may** share with NonProd per D8).

4. **Selection order is sequential — Prod → NonProd → DR** — not joint optimization. With 3–4 regions the greedy sequential result equals the joint-optimal result in nearly all practical cases, while remaining transparent and auditable. `[Decided — D1]`

5. **Middle East special handling.** Prod and NonProd are chosen in-geo via `argmax(PS_Prod)` over {UAE North, Saudi Arabia Central}; DR is assigned to **Belgium Central** via the only approved Cross-Geo Extension paths (Saudi Arabia → Belgium Central, UAE North → Belgium Central). Belgium Central must itself pass HC-1..HC-10; if it fails, the placement is rejected with an ops alert — the engine never silently substitutes another region. `[Decided — D8; Documented — §27]`

6. **Determinism & audit.** All candidate sets, sub-scores, the winning score, and the active `PlacementPolicy` version are written to the `OperationRecord` for replay (VR-8, VR-9). Even the 3-region edge case (single eligible candidate) runs the full scoring path so the score is logged as a capacity-health signal. `[Decided — D5]`

7. **Operating mode.** In Phase 1 the engine runs region selection in **recommendation/shadow mode** — it produces and logs the ranked recommendation but does not autonomously place. Autonomous placement is gated on POC validation of the scoring formulas.

#### Region Classification Model (normative)

Every Azure region carries exactly one classification tier, stored in `PlacementPolicy` as config-as-code (versioned, auditable, replayable) — classification is a **governance decision, not a live capability query**. `[Documented — §27]`

| Tier | Eligibility | Regions |
|---|---|---|
| **Standard Capacity Region** | Eligible for dynamic selection, scoring, and all env assignments (Prod/CVAL/DR) — the only regions that enter the pipeline | NA: West US 3, Central US, Canada Central · EU: Sweden Central, Belgium Central · ME: Saudi Arabia, UAE North · APAC: Japan East, Southeast Asia, Australia East |
| **Restricted Capacity Region** | Exception-only (Scenario 2 + Prod + approval); never scored, ranked, or recommended | East US 2, North Europe, West Europe, East Asia, Australia Southeast (all: Azure physical capacity constraint) |
| **Cross-Geo Extension Region** | DR-only, for geographies that cannot meet the 3-region minimum in-geo | Saudi Arabia → Belgium Central; UAE North → Belgium Central (Middle East only) |

Restricted regions are excluded by a **pre-filter ahead of all hard constraints** (HC-9), never as a scoring penalty.

#### Prod Region Input Modes

The Prod region is the anchor; CVAL and DR are selected sequentially from it. The customer supplies the anchor one of two ways, and both converge on a single validated Prod anchor: `[Documented — §27]`

- **Scenario 1 — geography supplied.** The engine derives Prod via `argmax(PS_Prod)` over Standard Capacity Regions **in that geography only**. Ties break deterministically by the Standard-region list order for the geography; the first-listed region is the deterministic cold-start default when no snapshot exists. Geography exhaustion → reject (never silently cross-geo or use a Restricted region).
- **Scenario 2 — specific region supplied.** If Standard, validate against HC-1..HC-10 and adopt as the anchor (`PS_Prod` used only for post-selection validation). If Restricted, route to the Exception Deployment Workflow.

#### Exception Deployment Workflow (Scenario 2 — Restricted region)

A Restricted region is used only if **all four** conditions hold; failure rejects at the first failing gate: `[Documented — §27]`

| # | Condition | Check |
|---|---|---|
| **EC-1** | Explicit request | Customer named the region; engine never recommended it |
| **EC-2** | Production only | CVAL and DR may **never** use a Restricted region |
| **EC-3** | Exception approval | A named, revocable approval record exists for the customer–region pair |
| **EC-4** | Scenario 2 input | Restricted regions can never be engine-derived |

On success the region becomes the **Exception Prod Anchor**, the placement is marked an **Exception Deployment**, a capacity-constraint warning is emitted to the caller, and the approval ID + restriction status are mandatory `OperationRecord` fields (commit blocked if absent). CVAL/DR still select from Standard regions via normal scoring.

#### Validation Rule Framework (VR-1..VR-11)

| Rule | Check | Failure action |
|---|---|---|
| VR-1 | Region exists in classification list | Reject if unknown |
| VR-2 | Automated placement uses Standard only | Exclude before scoring if Restricted |
| VR-3 | Scenario 2 Restricted: EC-1..EC-4 all met | Reject at first failing condition |
| VR-4 | Scenario 1 derived Prod in-geo Standard | Geography-scoped exhaustion error |
| VR-5 | Standard region passes HC-1..HC-10 | Exclude; exhaustion error if all excluded |
| VR-6 | Middle East DR = Belgium Central via approved path | Block with ops alert if Belgium Central fails HC-1..HC-10 |
| VR-7 | Exception approval ID persisted before commit | Block commit if absent |
| VR-8 | Capacity-constraint warning emitted | Block commit if suppressed |
| VR-9 | Snapshot age within policy limit | Trigger targeted ARM refresh |
| VR-10 | Capacity hold acquired before commit | Block commit if hold absent |
| VR-11 | Restricted regions absent from all recommendation outputs | Post-scoring filter (defence-in-depth) |

#### Capacity Holds & Concurrency

Before returning a committed assignment the engine creates a **capacity hold** keyed by region, SKU, zone, environment, and policy version, using **optimistic concurrency**; the hold expires if Azure provisioning does not begin. This closes the concurrent-placement race (B-7). `[Documented — §29]`

#### Corrected Scoring Model (pilot)

- Default weights retained for pilot comparison: `α=0.30, β=0.20, γ=0.25, δ=0.15, ε=0.10`; every component is clamped `Clamp(x) = max(0, min(1, x))`. `[Assumed]`
- To avoid double-counting the same signal under α and δ, the CVAL/NonProd formula is proposed as `PS_NonProd = 0.35·Capacity + 0.25·Quota + 0.25·Distribution + 0.05·DR_Overflow_Integrity + 0.10·Zones`. `[Undocumented — §28]`
- Distribution uses **demand units, not customer count**: `Distribution = 1 − Region_Assigned_Demand / Total_Assigned_Demand`. `[Undocumented — §28]`
- Revised weights are proposed, not empirically validated — advisory until pilot measurement.

#### Governance & Compliance Controls

- The classification list lives in `PlacementPolicy`; any change requires a policy-version increment, a Decision Log entry, and **replay of the prior 30 days of placements** against the new classification before activation. `[Documented — §27]`
- Exception approval records are revocable engine artefacts; a revoked approval blocks future exception deployments for the customer–region pair with no code change.
- Every classification change is audited with approver identity, timestamp, previous/new classification, and affected geography.
- Belgium Central's regional capacity-planning targets must include potential Middle East DR demand on top of in-geo Europe demand.

### Consequences

**Positive:**
- Deterministic, replayable placement with a complete audit trail satisfies compliance and post-incident review.
- Hard constraints guarantee no placement ever violates isolation, zone, quota, or residency rules regardless of score.
- Restricted regions are structurally impossible to select automatically; exceptions flow through a governed Scenario 2 workflow with a persisted, revocable approval ID.
- Env-type-specific formulas let Prod optimise for capacity/isolation while DR optimises for overflow readiness.

**Negative / trade-offs:**
- Three formulas plus 16 per-CRG-type `RegionalSnapshot` fields increase implementation and snapshot-maintenance cost (backlog E07-S16, E03-S10).
- Sequential selection is greedy; if the region count ever exceeds 6, joint optimization should be revisited (D1 review trigger).
- Cross-geo extension paths are a manual governance artefact — adding a path requires a PlacementPolicy update, governance approval, and a Decision Log entry.
- Worked scoring examples remain a known gap (G-7) until per-CRG-type inputs are finalised.

**Neutral:**
- CRG_Score (RCW) is demoted from a primary scoring input to a monitoring-only signal (D9).

### Alternatives Considered

| Alternative | Why Rejected |
|---|---|
| **Joint optimization** (select all three regions simultaneously) | Higher combinatorial complexity; opaque and harder to audit; identical result to sequential for 3–4 regions. `[D1]` |
| **Single generic PS(r, env_type) formula** | α and δ have fundamentally different meanings per env type; a single formula needs so many branches it becomes three formulas anyway. `[D9]` |
| **Geographic distance as a scored soft objective** | Operators already choose geographically independent region sets at design time; HC-4 as a hard constraint is sufficient and simpler. `[D4]` |
| **Silent fallback region for failed Middle East DR** | Violates governance and residency guarantees; the engine must fail loudly and require an approved extension path. `[§27]` |

---

---

## Appendix — Decision Log Cross-Reference

| ADR | Primary Decisions | Hard Constraints | Key Gaps/Blockers |
|---|---|---|---|
| ADR-001 Region Selection | D1, D4, D5, D8, D9 | HC-1, HC-4, HC-5, HC-8, HC-9, HC-10 | G-7 (worked examples) |

## Appendix — Status Legend

| Status | Meaning |
|---|---|
| **Proposed** | Under discussion; not yet ratified |
| **Accepted** | Ratified and in force |
| **Deprecated** | No longer recommended but not yet replaced |
| **Superseded** | Replaced by a later ADR (referenced explicitly) |

## Appendix — Evidence Tag Taxonomy

| Tag | Meaning |
|---|---|
| `[Documented]` | Traceable to Azure platform documentation or a formal FR/NFR |
| `[Decided]` | Explicit design choice in the Decision Log (D1–D11) |
| `[Derived]` | Logical consequence of a documented constraint or decision |
| `[Assumed]` | Architectural judgement pending POC validation |

## Related ADRs

- **ADR-002 — Quota and Capacity Management** (`acrme_adr_002_quota_and_capacity_management.md`)
- **ADR-003 — Capacity Management during Disaster Recovery (DR)** (`acrme_adr_003_capacity_management_during_dr.md`)
- **ADR-004 — Forecast and Increase of Capacity and Quota** (`acrme_adr_004_forecast_and_increase_of_capacity_and_quota.md`)

---

**Document Status:** Accepted  
**Next Review:** After POC-30 (Quota Groups GA) and POC-31 (quota release latency), and on resolution of G-14 / G-15.

