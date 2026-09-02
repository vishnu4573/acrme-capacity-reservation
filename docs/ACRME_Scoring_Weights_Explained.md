# ACRME Placement Scoring Weights — Complete Reference

**Project:** Azure Capacity Reservation Management Engine (ACRME)  
**Classification:** Technical Reference  
**Version:** 1.0  
**Date:** August 2026

---

## Overview

The ACRME placement engine uses **three environment-type-specific scoring formulas** (PS_Prod, PS_NonProd, PS_DR) to rank Azure regions for Prod, NonProd/CVAL, and DR environment placement. All three formulas share the same **default weight values**:

```
α = 0.30  (CRG Capacity)
β = 0.20  (Quota Headroom)
γ = 0.25  (Distribution Fairness)
δ = 0.15  (DR/Overflow Health)
ε = 0.10  (Zone Diversity)
```

However, **α** and **δ** have **different semantic meanings** per environment type — they measure different signals depending on whether you're scoring a Prod, NonProd, or DR region.

---

## Weight Definitions by Component

### α (Alpha) — CRG Capacity Signal **[Weight: 0.30]**

**Purpose:** Measures available capacity in the region's CRG most relevant to the environment being placed.

**Semantic per environment:**

| Environment | α Measures | Formula |
|-------------|-----------|---------|
| **PS_Prod** | NonProd CRG overflow headroom relative to Prod CRG size. High α = the associated NonProd CRG has capacity to absorb overflow if Prod grows. | `nonprod_crg_effective_free / prod_crg_quantity` |
| **PS_NonProd** | Fraction of NonProd CRG that is truly available (free_slots minus dr_overflow_reserve). This is the **primary capacity signal** for NonProd placement. | `nonprod_crg_effective_free / nonprod_crg_quantity` |
| **PS_DR** | Fraction of DR CRG capacity that is uncommitted. High α = more room for additional DR assignments. | `dr_crg_free_slots / dr_crg_quantity` |

**Why α is the highest weight (0.30):** Capacity is the most critical constraint. A region with zero headroom cannot accept new placements regardless of quota or distribution. α is highest when capacity is tight; can be reduced to 0.20 once regions reach steady-state utilization (40–60%).

---

### β (Beta) — Quota Headroom **[Weight: 0.20]**

**Purpose:** Measures available Azure subscription/group quota headroom for the relevant CRG.

**Semantic per environment:**

| Environment | β Measures | Formula |
|-------------|-----------|---------|
| **PS_Prod** | Prod group quota headroom ratio | `prod_crg_quota_headroom_vcpu / prod_crg_quota_limit_vcpu` |
| **PS_NonProd** | NonProd floor-adjusted quota headroom (effective ceiling minus used) | `nonprod_crg_quota_headroom_vcpu / nonprod_crg_quota_limit_vcpu` |
| **PS_DR** | DR quota headroom within the DR floor allocation | `dr_crg_quota_headroom_vcpu / dr_crg_quota_limit_vcpu` |

**Why β = 0.20:** Quota exhaustion silently blocks CR creation and VM deployment. β ensures the engine directs placements toward regions with quota headroom. Lower than α because quota can be requested (takes time but is not a hard ceiling like physical capacity).

**Note:** All β calculations read from **quota-group-level fields** (two-group model: Prod-only group, shared NonProd+DR group), not legacy per-subscription quota. See ADR-002.

---

### γ (Gamma) — Distribution Fairness **[Weight: 0.25]**

**Purpose:** Acts as a **self-correcting load balancer**. Rewards regions with fewer customers already placed, driving even distribution across regions over time.

**Semantic (same for all environments):**

```
γ = 1 - (customer_count_in_this_region / total_customers)
```

| Environment | γ Measures | Formula |
|-------------|-----------|---------|
| **PS_Prod** | Prod region fairness | `1 - (consumer_count_prod / total_customers)` |
| **PS_NonProd** | NonProd region fairness | `1 - (consumer_count_nonprod / total_customers)` |
| **PS_DR** | DR region fairness | `1 - (consumer_count_dr / total_customers)` |

**Why γ = 0.25:** Equal to capacity in importance. As a region accumulates customers its γ score drops, redirecting future placements away from it until all regions reach roughly equal count (steady-state expected count per region per env type = `total_customers / 3`). Increase γ toward 0.35 if score convergence results in uneven loading; decrease toward 0.15 if capacity constraints should dominate fairness.

**Note:** The PRR (Section 28) updates Distribution to use **demand units** rather than customer count: `1 - (Region_Assigned_Demand / Total_Assigned_Demand)`.

---

### δ (Delta) — DR/Overflow Health **[Weight: 0.15]**

**Purpose:** Environment-specific **resilience signal** — measures DR coverage readiness (Prod/DR) or overflow capacity health (NonProd).

**Semantic per environment:**

| Environment | δ Measures | Formula | Intent |
|-------------|-----------|---------|--------|
| **PS_Prod** | DR CRG coverage readiness of this region's own DR CRG. When scoring a Prod region, δ captures the health of the region's DR CRG — a Prod region whose DR CRG is well-covered scores higher. | `dr_crg_coverage_ratio` | Prod placement favors regions with healthy DR capacity |
| **PS_NonProd** | Overflow capacity health — intentionally **shares the same ratio as α**. Rewards regions genuinely under-utilised from both a NonProd-placement and a DR-overflow perspective. | `nonprod_crg_effective_free / nonprod_crg_quantity` (same as α) | NonProd placement prioritizes regions with DR overflow headroom |
| **PS_DR** | Coverage ratio health relative to target. Scores 1.0 when coverage ≥ `dr_ratio_max` (0.40). Proportionally below 1.0 for coverage between `dr_ratio_min` (0.30) and `dr_ratio_max` (e.g. 0.35/0.40 = 0.875). | `min(1.0, dr_crg_coverage_ratio / dr_ratio_max)` | DR placement drives buffer margins toward target |

**Why δ is different per env:** Each environment has a distinct resilience need. Prod cares about its paired DR region's readiness; NonProd cares about overflow headroom it can yield to DR during a crisis; DR cares about its own coverage health.

**Why δ = 0.15:** Lower than α/β/γ because it's a forward-looking health signal rather than an immediate placement blocker. Increase δ toward 0.20 if DR buffer violations appear; decrease if capacity/distribution should dominate.

**Trade-off (PS_NonProd):** δ duplicates α intentionally — this was flagged in the PRR (Section 28) as double-counting. The corrected pilot formula proposes revised NonProd weights: `PS_NonProd = 0.35·Capacity + 0.25·Quota + 0.25·Distribution + 0.05·DR_Overflow_Integrity + 0.10·Zones` to reduce the duplication.

---

### ε (Epsilon) — Zone Diversity **[Weight: 0.10]**

**Purpose:** Rewards regions with more availability zones, ensuring placed workloads can leverage Azure's zone-redundancy features.

**Semantic (same for all environments):**

```
ε = az_count / 3
```

Normalizes to 1.0 for a 3-zone region (maximum diversity); proportionally lower for 2-zone (0.667) or 1-zone (0.333) regions.

| Environment | ε Measures | Formula |
|-------------|-----------|---------|
| **All (PS_Prod, PS_NonProd, PS_DR)** | Zone diversity | `az_count / 3` |

**Why ε = 0.10 (lowest weight):** Zone diversity is desirable but not a placement blocker. Hard constraint **HC-5 ZONE_AVAILABILITY** already enforces a minimum zone count — ε acts as a tiebreaker that favors 3-zone regions when all else is equal. Increase ε toward 0.15 if zone diversity is a critical operational requirement; keep at 0.10 if capacity/distribution dominate.

---

## Complete Formula Definitions

### PS_Prod(r) — Production Region Score

```
PS_Prod(r) =
    0.30 × (nonprod_crg_effective_free / prod_crg_quantity)             ← α: NonProd overflow headroom
  + 0.20 × (prod_crg_quota_headroom_vcpu / prod_crg_quota_limit_vcpu)  ← β: Prod quota headroom
  + 0.25 × (1 - consumer_count_prod / total_customers)                 ← γ: Prod distribution fairness
  + 0.15 × dr_crg_coverage_ratio                                       ← δ: DR readiness of likely DR target
  + 0.10 × (az_count / 3)                                              ← ε: zone diversity
```

**Guards:**
- If `prod_crg_quantity == 0` → `PS_Prod = 0.0`
- If `prod_crg_quota_limit_vcpu == 0` → β term = 0.0
- If `dr_crg_coverage_ratio is None` → δ term = 0.0 (no DR CRG established yet)

---

### PS_NonProd(r) — Non-Production / CVAL Region Score

**Current formula (with intentional α/δ duplication):**
```
PS_NonProd(r) =
    0.30 × (nonprod_crg_effective_free / nonprod_crg_quantity)              ← α: effective NonProd headroom
  + 0.20 × (nonprod_crg_quota_headroom_vcpu / nonprod_crg_quota_limit_vcpu) ← β: NonProd quota headroom
  + 0.25 × (1 - consumer_count_nonprod / total_customers)                   ← γ: NonProd distribution
  + 0.15 × (nonprod_crg_effective_free / nonprod_crg_quantity)              ← δ: overflow capacity health (same as α)
  + 0.10 × (az_count / 3)                                                   ← ε: zone diversity
```

**Proposed pilot formula (corrected to avoid double-counting):**
```
PS_NonProd(r) =
    0.35 × (nonprod_crg_effective_free / nonprod_crg_quantity)              ← α: capacity (increased)
  + 0.25 × (nonprod_crg_quota_headroom_vcpu / nonprod_crg_quota_limit_vcpu) ← β: quota headroom
  + 0.25 × (1 - consumer_count_nonprod / total_customers)                   ← γ: distribution
  + 0.05 × (nonprod_crg_effective_free / nonprod_crg_quantity)              ← δ: DR overflow integrity (reduced)
  + 0.10 × (az_count / 3)                                                   ← ε: zone diversity
```

**Guards:**
- If `nonprod_crg_quantity == 0` → `PS_NonProd = 0.0`
- If `nonprod_crg_quota_limit_vcpu == 0` → β term = 0.0

---

### PS_DR(r) — Disaster Recovery Region Score

```
PS_DR(r) =
    0.30 × (dr_crg_free_slots / dr_crg_quantity)                            ← α: DR CRG headroom
  + 0.20 × (dr_crg_quota_headroom_vcpu / dr_crg_quota_limit_vcpu)          ← β: DR quota headroom
  + 0.25 × (1 - consumer_count_dr / total_customers)                       ← γ: DR distribution
  + 0.15 × min(1.0, dr_crg_coverage_ratio / dr_ratio_max)                  ← δ: coverage ratio health
  + 0.10 × (az_count / 3)                                                  ← ε: zone diversity
```

**Guards:**
- If `dr_crg_quantity == 0` → `PS_DR = 0.0` (no DR CRG — region ineligible)
- If `dr_crg_quota_limit_vcpu == 0` → β term = 0.0
- If `dr_crg_coverage_ratio is None` → δ term = 0.0

---

## Weight Summary Table

| Component | Symbol | Weight | PS_Prod Measures | PS_NonProd Measures | PS_DR Measures |
|-----------|--------|--------|------------------|---------------------|----------------|
| **CRG Capacity** | **α** | **0.30** | NonProd overflow headroom | NonProd effective headroom | DR CRG free capacity |
| **Quota Headroom** | **β** | **0.20** | Prod group quota ratio | NonProd floor-adjusted quota | DR quota within floor |
| **Distribution** | **γ** | **0.25** | Prod region fairness | NonProd region fairness | DR region fairness |
| **DR/Overflow Health** | **δ** | **0.15** | DR coverage readiness | Overflow capacity (same as α) | Coverage vs target ratio |
| **Zone Diversity** | **ε** | **0.10** | `az_count / 3` | `az_count / 3` | `az_count / 3` |

---

## Clamping & Score Range

Every raw component ratio is **clamped** before weighting:

```
Clamp(x) = max(0, min(1, x))
```

This ensures each component contributes a value in the range `[0.0, 1.0]`, and the final weighted score for any region is:

```
PS(r) ∈ [0.0, 1.0]
```

A uniform jitter of ±0.01 is added as a tiebreaker.

---

## Tuning Guidance

### When to adjust α (Capacity)
- **Increase α toward 0.35–0.40** when capacity is tight and regions are unevenly provisioned.
- **Reduce α toward 0.20** once regions reach steady-state utilization (40–60%) and distribution becomes the primary concern.

### When to adjust γ (Distribution)
- **Increase γ toward 0.35** if score convergence results in uneven region loading (some regions accumulate too many customers).
- **Decrease γ toward 0.15** if capacity constraints should dominate fairness (tight capacity environments).

### When to adjust δ (DR/Overflow Health)
- **Increase δ toward 0.20** if DR buffer violations or coverage gaps appear frequently.
- **Reduce δ toward 0.10** if capacity/distribution should dominate and DR health is consistently good.

### When to adjust ε (Zone Diversity)
- **Increase ε toward 0.15** if zone diversity is a critical operational requirement (e.g., all placements must strongly favor 3-zone regions).
- **Keep ε at 0.10** (default) if capacity, quota, and distribution are the dominant concerns.

**Default recommendation:** Start with the default weights (`α=0.30, β=0.20, γ=0.25, δ=0.15, ε=0.10`) for the pilot. After 30–50 customer placements, analyze the score breakdown data in `OperationRecord` and adjust incrementally based on observed convergence behavior.

---

## Source References

- **Multi-Region Placement Design** (`docs/research/multi_region_placement_design.md`) — lines 449–531, full formula definitions + weight table
- **Design Change Summary** (`docs/research/design_change_summary.md`) — CR/CRG-7, lines 153–193, formula rationale
- **Production Readiness Review** (`docs/acrme_production_readiness_review_and_architecture.md`) — Section 28 lines 1095–1160, corrected scoring model
- **ADR-001 Region Selection** (`docs/adr/acrme_adr_001_region_selection.md`) — corrected scoring model section

---

## Evidence Tags

- `[Documented]` — Defined in Multi-Region Placement Design and PRR Section 28
- `[Decided]` — Decision Log D9 (env-type-specific formulas)
- `[Assumed]` — Default weights retained for pilot comparison; revised weights proposed but not empirically validated

---

**Document Status:** Reference  
**Next Review:** After pilot Phase 4 (policy tuning with 30–50 placements measured)
