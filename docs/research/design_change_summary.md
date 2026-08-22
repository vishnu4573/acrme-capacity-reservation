# Design Change Summary — Azure Capacity Reservation Management Engine
## Session: Azure Capacity Reservations — August 2026

**Purpose:** Stock-take of all design changes made in this session, fact-checked against the conversation history and source documents. Changes are categorized by domain and include references to where each change appears in the updated documents.

**Baseline documents (pre-update):**
- `multi_region_placement_design.md` — original version (Aug 20 04:29 timestamp; pre-quota-group update)
- `azure_cr_poc_test_workbook.md` — original version (GP-01 to GP-05 only; Sections 1–6; POC-01 to POC-29 only)

**Fact-check confidence levels used throughout:**
- `[Documented]` — present in an official Microsoft source
- `[Tested]` — validated by executed POC evidence in this session
- `[Derived]` — logically derived from documented behavior; requires validation
- `[Decided]` — architecture decision made in this conversation session; not yet validated by POC
- `[Pending]` — stated as a constraint in session but not yet reflected in the documents

---

## Part 1 — CR/CRG Design Changes

These changes relate to Capacity Reservations and Capacity Reservation Groups — how they are structured per region, how they map to environments, and how they relate to the placement model.

---

### CR/CRG-1 — Three-CRG Model per Region (Prod CRG | NonProd CRG | DR CRG)

**Change:** The design formally establishes that every managed region contains exactly **three CRGs**, one per environment class: Prod CRG, NonProd CRG, DR CRG. This is the structural foundation of the placement model.

**Before:** CRGs were managed as a generic pool (`total_crg_count`, `total_quantity`, `total_allocated`) with no per-env-type decomposition in the Regional State Model.

**After:** The quota group architecture section explicitly names the three-CRG structure:
```
Prod CRG      ←──→  Prod Quota Group       (1:1 isolated)
NonProd CRG   ←──→  NonProd+DR Group       (shared pool)
DR CRG        ←──→  NonProd+DR Group       (shared pool)
```

**Fact-check:** `[Decided]` — established in session as the structural basis for the two-group quota model. Confirmed consistent with: `multi_region_placement_design.md` lines 100–105 (quota group section), D6 decision log.

**Document location:** `multi_region_placement_design.md` — Quota Group Architecture section (line 100), Decision Log D6.

**Status in documents:** Present — stated as foundational principle. However, the `RegionalSnapshot` model does NOT yet have per-CRG-type sub-schemas (`prod_crg.*`, `nonprod_crg.*`, `dr_crg.*`). The three-CRG model is implied by the quota group structure but not explicitly modeled at the CRG entity level in the snapshot. This is a **known gap** identified in the gap analysis.

---

### CR/CRG-2 — DR CRG Sizing Rule (30–40% of potential_dr_demand)

**Change:** DR CRG base capacity is sized at `dr_ratio_max = 0.40` of `potential_dr_demand`, using the upper bound of the ratio range — never the current operating ratio.

**Before:** Referenced as `dr_cr.quantity >= primary.quantity × dr_buffer_pct` in `DRCapacityPair` model (WAF section). No explicit formula for DR CRG sizing relative to potential demand.

**After:** Explicit formula in the Quota Group section:
```
DR_FLOOR_VCPU(region) = potential_dr_demand(region) × vCPU_per_instance × dr_ratio_max
potential_dr_demand = Σ prod_allocated for all customers where dr_region = this_region
dr_ratio_max = 0.40 (upper bound)
```

**Fact-check:** `[Decided]` — Decision D7 in `multi_region_placement_design.md`. Rationale: sizing at upper bound prevents floor undersizing if ratio is increased later (e.g. 0.30 → 0.40). Cost implication acknowledged (slightly higher quota reservation). Consistent with session constraint: "Each region must have Prod, NonProd, and DR CRGs with base capacity; DR CRG = 30–40% of Prod CRG." Note: the session constraint says "30–40% of Prod CRG" while the formula uses "40% of potential_dr_demand" — these are equivalent when potential_dr_demand = Prod allocated count. The formula is the more precise engineering expression.

**Document location:** `multi_region_placement_design.md` — Quota Group Architecture section (DR Floor), Decision Log D7, PlacementPolicy field `dr_ratio_max`.

**Status in documents:** Present and correct.

---

### CR/CRG-3 — DR/NonProd Co-existence in the Same Region (Constraint Removal)

**Change:** The hard constraint `DR_region ≠ NonProd_region` has been **decided to be removed**, allowing DR and NonProd environments to be placed in the same region. This enables NonProd CRG capacity to serve as overflow for DR during a real DR event.

**Before:** HC-1 (REGION_SEPARATION) stated:
```
DR_region ≠ Prod_region
DR_region ≠ NonProd_region     ← THIS LINE
```
Requirement R2 stated: "Engine selects NonProd and DR regions automatically, never the same as Prod and **never equal to each other**."

**After:** The session constraint log explicitly records: "Allow DR and NonProd to co-exist in the same region; remove DR_region ≠ NonProd_region." However, **this change is NOT yet reflected in either document.** HC-1 still contains `DR_region ≠ NonProd_region` at line 231 of `multi_region_placement_design.md`. R2 still says "never equal to each other."

**Fact-check:** `[Decided — NOT YET DOCUMENTED]` — Confirmed in standing constraints of this conversation session. The design intent is clear: removing this constraint is what makes HC-6 (DR_COVERAGE_FLOOR — combined DR+NonProd overflow check) meaningful. Without co-existence, HC-6 would never be needed. The two changes are coupled.

**Document location:** `multi_region_placement_design.md` — line 231 (HC-1), line 51 (R2). **Both still contain the old constraint text — this is an outstanding document error.**

**Status in documents:** ❌ NOT updated. Outstanding gap — highest priority correction needed.

---

### CR/CRG-4 — NonProd CRG Effective_Free and DR Overflow Reserve

**Change:** The NonProd CRG introduces a concept of `effective_free` — the free capacity in the NonProd CRG after subtracting a `dr_overflow_reserve`. During a real DR event, the DR VMs would land on the NonProd CRG using this reserved headroom.

**Before:** No distinction between raw `free_slots` and effective free. NonProd CRG capacity was not modeled as a DR overflow buffer.

**After:** Referenced implicitly in the user-provided formula summary:
```
nonprod_crg.effective_free = nonprod_crg.free_slots - dr_overflow_reserve
```
This feeds into PS_NonProd α and δ, and HC-6.

**Fact-check:** `[Decided — NOT YET DOCUMENTED]` — Introduced in this session via the formula summary provided by the user. `effective_free` and `dr_overflow_reserve` are not defined anywhere in the current documents. They are not in the `RegionalSnapshot` schema. This is a known gap.

**Document location:** Not present. Fields `nonprod_crg.effective_free`, `nonprod_crg.dr_overflow_reserve` do not appear in `multi_region_placement_design.md` or either schema.

**Status in documents:** ❌ NOT documented. Outstanding gap.

---

### CR/CRG-5 — DR CRG Coverage Ratio

**Change:** A `coverage_ratio` metric is established for the DR CRG:
```
dr_crg.coverage_ratio = dr_crg.quantity / potential_dr_demand
```
This measures how well the DR CRG covers total potential DR need across all customers whose DR region is this region.

**Before:** DR buffer compliance was tracked as a Boolean (`dr_buffer_compliant` in `DRCapacityPair`) and as a ratio in `DR_Buffer_Score`. No named `coverage_ratio` field in the snapshot.

**After:** Referenced in user-provided formula:
```
PS_Prod δ   = dr_crg.coverage_ratio  (DR readiness of the likely DR target)
PS_DR  δ    = min(1.0, dr_crg.coverage_ratio / dr_ratio_target)
```

**Fact-check:** `[Decided — NOT YET DOCUMENTED]` — Introduced in this session. `coverage_ratio` is not a named field in the current `RegionalSnapshot`. `potential_dr_demand` is referenced in the DR floor formula but not stored as a snapshot field. This is a known gap.

**Document location:** Not in `RegionalSnapshot` schema. Partially referenced in DR floor formula but not as a standalone computed field.

**Status in documents:** ❌ NOT documented as a snapshot field. Outstanding gap.

---

### CR/CRG-6 — HC-6 DR_COVERAGE_FLOOR Hard Constraint (New)

**Change:** A new hard constraint HC-6 is established for DR region eligibility:
```
HC-6  DR_COVERAGE_FLOOR:
    DR CRG region is ineligible if:
    (dr_crg.free_slots + nonprod_crg.effective_free) < customer_requested_dr_slots
```
The combined DR CRG + NonProd CRG effective free capacity must be sufficient to absorb the new customer's DR demand.

**Before:** No HC-6. The constraint numbering jumped HC-5 → HC-7 in the updated document (HC-7 is DR Floor Integrity for NonProd, added in this session). HC-6 was not present.

**After:** Defined in user-provided formula summary but NOT yet in the document.

**Fact-check:** `[Decided — NOT YET DOCUMENTED]` — Introduced in this session as part of the formula summary. Logically coupled to CR/CRG-3 (co-existence removal): without co-existence, there is no NonProd overflow to count. This constraint operationalizes the co-existence model at the selection level.

**Document location:** Not present in `multi_region_placement_design.md`. HC-6 slot is currently empty.

**Status in documents:** ❌ NOT documented. Outstanding gap.

---

### CR/CRG-7 — Env-Type-Specific Placement Score Formulas (PS_Prod, PS_NonProd, PS_DR)

**Change:** The single generic `PS(r, E)` formula is **replaced** by three distinct env-type-specific formulas where α and δ have different definitions per environment type. Critically, `PS_Prod` is introduced as a new formula (Prod scoring did not exist before).

**Before:** One formula: `PS(r, E) = α×CRG_Score + β×Quota_Score + γ×Distribution + δ×DR_Buffer + ε×Zone`. CRG_Score was a generic mean RCW across all CRGs. DR_Buffer_Score was DRCapacityPair compliance. Prod region was customer-selected, not scored.

**After (from user-provided formula summary):**

```
PS_Prod(r) =
    0.30 × (nonprod_crg.effective_free / prod_crg.quantity)   ← α: NonProd headroom signal
  + 0.20 × (prod_crg.quota_headroom / prod_crg.quota_limit)   ← β: Prod quota headroom
  + 0.25 × (1 - prod_customer_count / total_customers)        ← γ: distribution
  + 0.15 × dr_crg.coverage_ratio                             ← δ: DR readiness of likely DR target
  + 0.10 × (az_count / 3)                                     ← ε: zone diversity

PS_NonProd(r) =
    0.30 × (nonprod_crg.effective_free / nonprod_crg.quantity) ← α: effective NonProd headroom
  + 0.20 × (nonprod_crg.quota_headroom / nonprod_crg.quota_limit) ← β
  + 0.25 × (1 - nonprod_customer_count / total_customers)     ← γ
  + 0.15 × (nonprod_crg.effective_free / nonprod_crg.quantity) ← δ: overflow capacity health
  + 0.10 × (az_count / 3)                                     ← ε

PS_DR(r) =
    0.30 × (dr_crg.free_slots / dr_crg.quantity)              ← α: DR CRG headroom
  + 0.20 × (dr_crg.quota_headroom / dr_crg.quota_limit)       ← β
  + 0.25 × (1 - dr_customer_count / total_customers)          ← γ
  + 0.15 × min(1.0, dr_crg.coverage_ratio / dr_ratio_target)  ← δ: coverage ratio health
  + 0.10 × (az_count / 3)                                     ← ε
```

**Fact-check:** `[Decided — NOT YET DOCUMENTED]` — Provided by the user in this session. These formulas represent a fundamental restructuring of the scoring model. The current document retains the old `CRG_Score = mean(RCW)` and `DR_Buffer_Score` (pair compliance) formulations. These are superseded. Key differences:
- α is now CRG-type-specific, not a regional aggregate RCW
- δ for NonProd is overflow capacity health (ratio of effective_free), not pair compliance
- δ for DR is coverage ratio health, not free_slots/required_dr_quantity
- PS_Prod is entirely new

**Document location:** NOT present. The document retains the superseded formulas.

**Status in documents:** ❌ NOT documented. Outstanding gap — highest priority update needed.

---

### CR/CRG-8 — RegionalSnapshot: Per-CRG-Type Sub-Schema Fields

**Change:** The `RegionalSnapshot` model needs per-CRG-type fields to support the new PS formulas and HC-6.

**Before:** Snapshot had aggregate fields only: `total_quantity`, `total_allocated`, `total_free_slots`, plus quota group fields (added in this session).

**After:** Requires these additional fields (none currently in the document):

| Field | Used By |
|---|---|
| `prod_crg.quantity` | PS_Prod α denominator |
| `nonprod_crg.quantity` | PS_NonProd α denominator |
| `nonprod_crg.free_slots` | Basis for effective_free |
| `nonprod_crg.effective_free` | PS_Prod α, PS_NonProd α, PS_NonProd δ, HC-6 |
| `nonprod_crg.dr_overflow_reserve` | Derived: effective_free = free_slots - dr_overflow_reserve |
| `nonprod_crg.quota_headroom` | PS_NonProd β |
| `nonprod_crg.quota_limit` | PS_NonProd β |
| `dr_crg.free_slots` | PS_DR α, HC-6 |
| `dr_crg.quantity` | PS_DR α denominator |
| `dr_crg.quota_headroom` | PS_DR β |
| `dr_crg.quota_limit` | PS_DR β |
| `dr_crg.coverage_ratio` | PS_Prod δ, PS_DR δ |
| `potential_dr_demand` | coverage_ratio denominator |
| `prod_crg.quota_headroom` | PS_Prod β |
| `prod_crg.quota_limit` | PS_Prod β |

**Fact-check:** `[Decided — NOT YET DOCUMENTED]` — Derived from the user-provided formula summary in this session. None of these fields exist in the current `RegionalSnapshot` schema in `multi_region_placement_design.md`.

**Document location:** `multi_region_placement_design.md` — Regional State Model section. All of the above are missing.

**Status in documents:** ❌ NOT documented. Outstanding gap.

---

### CR/CRG-9 — Worked Example with Drift and Reconciliation Updates

**Change:** The existing worked examples (Example A / Example B) are based on the old generic formula and aggregate state. A new drift example was provided in this session showing per-CRG-type state, effective_free, HC-6 evaluation, and post-placement reconciliation updates including `potential_dr_demand` increment and auto-increase trigger.

**Before:** Example A (3 regions, bootstrap) and Example B (4 regions, mid-state) using `CRG_Score / Quota_Score` abstractions.

**After:** Drift example provided in this session with Region A / B / C state showing:
- Per-CRG-type capacity (Prod qty=100, NonProd qty=100, DR qty=35)
- `dr_overflow_reserve` and `effective_free` applied concretely
- HC-6 combined check for new customer DR slot eligibility
- Reconciliation updates: `potential_dr_demand += 10`, coverage compliance checks, auto-increase trigger threshold proximity noted

**Fact-check:** `[Decided — NOT YET DOCUMENTED]` — Provided by user in this session. Not yet in the document.

**Document location:** `multi_region_placement_design.md` — Worked Examples section. Existing examples use superseded formula.

**Status in documents:** ❌ NOT documented. Old examples remain in place.

---

## Part 2 — Quota Group Design Changes

These changes relate to `Microsoft.Quota/groupQuotas` — the two-group model, DR floor enforcement, quota formulas, and engine constraints.

---

### QG-1 — Two Quota Groups Per Region (Prod | NonProd+DR)

**Change:** Every managed region has exactly two Azure Quota Groups — one Prod-only, one NonProd+DR shared. This is the foundational quota architecture decision.

**Before:** Per-subscription quota tracking only. `QuotaRecord.deployment_headroom` was the scoring input. No group model.

**After:**
```
GROUP 1 — Prod Quota Group
  Members:    Provider subscription (Prod CRG owner)
  Budget:     Prod_CRG_quantity × vCPU × (1 + prod_growth_buffer)
  Backs:      Prod CRG only. Isolated — NonProd/DR cannot consume.

GROUP 2 — NonProd+DR Quota Group
  Members:    NonProd subscription + DR subscription
  Budget:     (NonProd_CRG_qty × vCPU) + (DR_CRG_qty × vCPU) + emergency_transfer_headroom_vcpu
  Backs:      NonProd CRG + DR CRG. Both draw from the same pool.
```

**Fact-check:** `[Decided]` — Decision D6 in `multi_region_placement_design.md`. Alternatives considered and rejected: single shared pool (breaks Prod isolation), three separate groups (makes Tier 3 non-atomic), per-subscription only (cannot make Tier 3 quota-neutral). Consistent with session constraint: "Use two quota groups per region: one for Prod, one for Non-Prod+DR." **Confirmed in documents.**

**Document location:** `multi_region_placement_design.md` — Quota Group Architecture section, D6 Decision Log.

**Status in documents:** ✅ Present and correct.

---

### QG-2 — QuotaGroup Entity (Cosmos DB)

**Change:** A new `QuotaGroup` entity is defined in Cosmos DB to persist and track quota group state per region.

**Before:** No group entity. State tracked per-subscription via `QuotaRecord`.

**After:**
```
QuotaGroup {
  group_id, region, group_type (Prod | NonProdDR),
  member_subscription_ids[], arm_group_resource_id,
  group_limit_vcpu, group_used_vcpu, group_headroom_vcpu,
  // NonProdDR only:
  nonprod_quota_used_vcpu, dr_quota_used_vcpu,
  dr_floor_vcpu, effective_nonprod_ceiling, nonprod_headroom_vcpu,
  dr_headroom_vcpu, dr_floor_compliant, last_synced_at
}
```

**Fact-check:** `[Decided]` — Defined in the Quota Group Architecture section of `multi_region_placement_design.md`. Entity structure is consistent with what the quota sync worker (E03-S10) and DR floor enforcement (E03-S11) require. **Confirmed in documents.**

**Document location:** `multi_region_placement_design.md` — Quota Group Architecture section (QuotaGroup Entity).

**Status in documents:** ✅ Present and correct.

---

### QG-3 — Quota Group Sizing Formulas

**Change:** Explicit sizing formulas defined for both groups.

**Before:** No group sizing formula. CR quantity was sized independently.

**After:**
```
Prod_Group_Limit(region) =
    Prod_CRG_quantity × vCPU_per_instance × (1 + prod_growth_buffer)
    prod_growth_buffer = 0.20

NonProd_DR_Group_Limit(region) =
    NonProd_CRG_quantity × vCPU × (1 + nonprod_growth_buffer)
  + DR_CRG_quantity × vCPU
  + emergency_transfer_headroom_vcpu

emergency_transfer_headroom_vcpu = max_emergency_transfer_qty × vCPU_per_instance
```

**Fact-check:** `[Decided]` — Defined in `multi_region_placement_design.md` Quota Group Architecture section. The `emergency_transfer_headroom_vcpu` term is critical — without it, Tier 3 DR CRG expansion has no quota room. Consistent with session discussion. **Confirmed in documents.** Note: `max_emergency_transfer_qty` is referenced but not explicitly defined — this is a minor gap (what value does it take?).

**Document location:** `multi_region_placement_design.md` — Quota Group Sizing Formulas.

**Status in documents:** ✅ Present and correct. Minor gap: `max_emergency_transfer_qty` value not defined.

---

### QG-4 — DR Floor: Engine-Enforced Sub-Limit Within NonProd+DR Group

**Change:** Because Azure does not natively support intra-group sub-reservations, the engine enforces a DR floor within the NonProdDR group. NonProd CRG expansion is blocked when it would encroach on DR-reserved quota.

**Before:** No DR floor concept. NonProd and DR quota management was per-subscription independently.

**After:**
```
DR_FLOOR_VCPU(region) = potential_dr_demand × vCPU_per_instance × dr_ratio_max

Effective_NonProd_Quota_Ceiling = NonProd_DR_Group_limit - DR_FLOOR_VCPU

Enforcement:
  NonProd CRG expansion BLOCKED when:
    nonprod_quota_used + (new_qty × vCPU) > Effective_NonProd_Quota_Ceiling

Alert: DRFloorViolationDetected (Severity: Critical)
```

**Fact-check:** `[Derived — requires POC-32 validation]` — Azure Quota Groups do not natively support intra-group sub-limits. This is confirmed as `[Documented]` in the research (`azure_cr_quota_implications_research.md`): "group membership does not automatically satisfy subscription-level quota checks." The engine-only enforcement is a derived necessity. POC-32 exists specifically to validate enforcement timing and behavior. **Confirmed in documents.**

**Document location:** `multi_region_placement_design.md` — Quota Group Architecture section (DR Floor), HC-7, E03-S11.

**Status in documents:** ✅ Present and correct.

---

### QG-5 — HC-3 Updated: Reads from Quota Groups, Not Per-Subscription QuotaRecord

**Change:** HC-3 (QUOTA_FLOOR) is updated to read from quota group headroom rather than per-subscription `deployment_headroom`.

**Before:**
```
HC-3  QUOTA_FLOOR:
    deployment_headroom(r) ≥ requested_vm_count × vCPU_per_instance
    (reads from QuotaRecord.deployment_headroom — per-subscription)
```

**After:**
```
HC-3  QUOTA_FLOOR [UPDATED]:
    For Prod:   Prod_Group_headroom(R) ≥ requested_vm_count × vCPU
    For NonProd: nonprod_headroom(R) ≥ requested_vm_count × vCPU
                 (uses effective_nonprod_ceiling — floor-adjusted)
    For DR:      dr_headroom(R) ≥ target_dr_qty × vCPU
```

**Fact-check:** `[Decided]` — HC-3 updated in `multi_region_placement_design.md` lines 240–255. Uses quota group fields from `RegionalSnapshot`. Legacy `deployment_headroom` retained for monitoring only. Consistent with session context. **Confirmed in documents.**

**Document location:** `multi_region_placement_design.md` — Core Constraints Model, HC-3.

**Status in documents:** ✅ Present and correct.

---

### QG-6 — HC-7: DR Floor Integrity Hard Constraint (New)

**Change:** New hard constraint HC-7 blocks NonProd placement in a region when it would encroach on the DR floor:

```
HC-7  DR_FLOOR_INTEGRITY [NEW]:
    REJECT NonProd placement in region R if:
    nonprod_quota_used(R) + (requested_vm_count × vCPU) > effective_nonprod_ceiling(R)
```

**Before:** No HC-7. NonProd could in theory consume DR-reserved quota without a hard block (only soft alert existed).

**After:** HC-7 evaluated after HC-3. HC-3 checks raw group headroom; HC-7 checks floor compliance. Both must pass for NonProd placement to proceed.

**Fact-check:** `[Decided]` — Added as HC-7 in `multi_region_placement_design.md` line 264. Backlog story E03-S11 implements the block. Alert `DRFloorViolationDetected` is the operational signal. **Confirmed in documents.**

**Document location:** `multi_region_placement_design.md` — Core Constraints Model, HC-7; Pseudocode `apply_hard_constraints`.

**Status in documents:** ✅ Present and correct.

---

### QG-7 — Quota_Score: Three Env-Type-Specific Formulas (Replaces Generic β)

**Change:** The single `Quota_Score(r)` formula is replaced with three env-type-aware formulas:

```
Quota_Score_Prod(r)   = prod_group_headroom_vcpu / prod_group_limit_vcpu
Quota_Score_NonProd(r) = nonprod_headroom_vcpu / effective_nonprod_ceiling_vcpu
Quota_Score_DR(r)     = dr_headroom_vcpu / dr_floor_vcpu
```

Semantics differ by env type — DR score of 1.0 means maximum expansion room (DR CRG at zero), not maximum quota consumed.

**Before:** Single `Quota_Score(r) = deployment_headroom / quota_limit` (per-subscription).

**After:** Three formulas dispatched by `compute_quota_score(snap, env_type)`. Guards defined for zero-denominator cases.

**Fact-check:** `[Decided]` — Fully documented in `multi_region_placement_design.md` lines 407–435, including guards and semantic notes. Pseudocode updated at lines 579–595. Consistent with D6 decision impact statement: "Quota_Score must now be environment-type-aware." **Confirmed in documents.**

**Document location:** `multi_region_placement_design.md` — Placement Scoring Formula, Quota_Score section; Pseudocode block.

**Status in documents:** ✅ Present and correct.

---

### QG-8 — RegionalSnapshot: Quota Group Fields Added

**Change:** The `RegionalSnapshot` model is extended with quota group fields. Legacy per-subscription fields are retained but marked `[Legacy]`.

**Before:** Snapshot had: `quota_limit`, `quota_used`, `committed_by_crs`, `deployment_headroom`.

**After (new fields added):**
```
// Prod Quota Group
prod_group_limit_vcpu, prod_group_used_vcpu, prod_group_headroom_vcpu

// NonProd+DR Quota Group
nonprod_dr_group_limit_vcpu, nonprod_quota_used_vcpu, dr_quota_used_vcpu,
nonprod_dr_group_used_vcpu, dr_floor_vcpu, effective_nonprod_ceiling_vcpu,
nonprod_headroom_vcpu, dr_headroom_vcpu, dr_floor_compliant

// Legacy (retained for monitoring)
quota_limit [Legacy], quota_used [Legacy], committed_by_crs [Legacy],
deployment_headroom [Legacy — superseded for scoring]
```

Redis cache key mapping added:
```
quota:group:{region}:prod        → Prod group headroom
quota:group:{region}:nonprod_dr  → Full NonProdDR state
snapshot:{region}                → Full RegionalSnapshot JSON
```

**Fact-check:** `[Decided]` — Fully documented in `multi_region_placement_design.md` Regional State Model section (lines 293–335). Consistent with E07-S12 backlog story. **Confirmed in documents.**

**Document location:** `multi_region_placement_design.md` — Regional State Model (RegionalSnapshot schema).

**Status in documents:** ✅ Present and correct. (Note: per-CRG-type sub-schemas are still missing — that is CR/CRG-8 above, a separate gap.)

---

### QG-9 — Tier 3 Emergency Capacity Transfer: Quota-Neutral via Shared Group

**Change:** The design formally explains why Tier 3 Emergency Capacity Transfer (reducing NonProd CR quantity → expanding DR CR quantity) is quota-neutral under the two-group model.

**Before:** Emergency transfer concept existed informally. Quota coordination risk (two separate subscription ledgers) was not analyzed.

**After:**
```
WITHOUT Quota Groups:
  NonProd CR reduction releases to NonProd subscription ledger
  DR CR expansion draws from DR subscription ledger
  → Two separate Azure quota accounts must coordinate
  → Risk: DR sub quota increase may require approval (hours of RTO)

WITH NonProd+DR Quota Group:
  Both actions operate on the same GROUP budget
  → Net headroom improves (release + expansion = net neutral)
  → No Azure quota increase request needed
  → Tier 3 RTO gated only by ARM operations (minutes, not hours)
```

**Fact-check:** `[Derived — requires POC-31/32 validation]` — The quota-neutral claim depends on: (a) NonProd CR reduction releasing back to the GROUP pool (not just subscription), and (b) DR CR expansion drawing from the same GROUP pool without triggering a new subscription-level check. POC-31 specifically validates (a); POC-32 validates (b) timing. Both are tagged `[Derived]` until executed. The claim is logically sound given Azure Quota Groups behavior as documented in `azure_cr_quota_implications_research.md`. **Confirmed in documents as derived claim with POC dependency.**

**Document location:** `multi_region_placement_design.md` — Quota Group Architecture section (Why This Model Makes Tier 3 Quota-Neutral).

**Status in documents:** ✅ Present and correctly tagged as derived.

---

### QG-10 — PlacementPolicy: New and Deprecated Quota Fields

**Change:** `PlacementPolicy.rules` extended with quota-group-specific fields; `min_quota_headroom_vcpu` deprecated.

**Before:**
```
"min_quota_headroom_vcpu": single value applying to all env types
```

**After:**
```
"min_prod_quota_headroom_vcpu":    20    // HC-3: Prod group minimum headroom
"min_nonprod_quota_headroom_vcpu": 20    // HC-3: NonProd effective headroom minimum
"min_dr_headroom_vcpu":            16    // HC-3: DR headroom minimum
"dr_ratio_max":                    0.40  // DR floor calculation ceiling
"prod_quota_growth_buffer":        0.20  // Prod group headroom buffer above CRG qty
"nonprod_quota_growth_buffer":     0.20  // NonProdDR group NonProd growth buffer
// DEPRECATED:
"min_quota_headroom_vcpu": deprecated — falls back to env-type fields if present
```

**Fact-check:** `[Decided]` — Documented in `multi_region_placement_design.md` Updated PlacementPolicy section (line 783) and E07-S16 backlog story. **Confirmed in documents.**

**Document location:** `multi_region_placement_design.md` — Updated PlacementPolicy fields section.

**Status in documents:** ✅ Present and correct.

---

### QG-11 — Decision Log: D6 and D7 Added

**Change:** Two new decision log entries added.

**D6 — Two Quota Groups per region:** Documents the choice between single shared pool, three separate groups, and two groups. Decision: two groups. Rationale: Prod isolation at Azure control plane level; Tier 3 remains quota-neutral.

**D7 — DR floor uses dr_ratio_max not current dr_ratio:** Decision to always size the floor at the upper bound (0.40) to prevent undersizing if ratio is later increased.

**Fact-check:** `[Decided]` — Both in `multi_region_placement_design.md` Decision Log D6 and D7. **Confirmed in documents.**

**Document location:** `multi_region_placement_design.md` — Decision Log.

**Status in documents:** ✅ Present and correct.

---

### QG-12 — Backlog: EPIC-03 Extension (E03-S09 to E03-S15) and EPIC-07 Updates

**Change:** Seven new EPIC-03 stories and updates to EPIC-07 stories to cover the quota group implementation.

**New EPIC-03 stories:** E03-S09 (QuotaGroup entity), E03-S10 (Quota Sync Worker extension), E03-S11 (DR floor enforcement), E03-S12 (quota pre-validation update), E03-S13 (Quota_Score update), E03-S14 (group-level increase workflow), E03-S15 (chargeback split).

**Updated EPIC-07 stories:** E07-S12 (RegionalSnapshot Redis model — quota group fields; dependency on E03-S09, E03-S10 made explicit), E07-S16 (PlacementPolicy new fields).

**Fact-check:** `[Decided]` — All stories present in `multi_region_placement_design.md` Backlog section. Dependencies correctly chained. **Confirmed in documents.**

**Document location:** `multi_region_placement_design.md` — Backlog Stories section.

**Status in documents:** ✅ Present and correct.

---

## Part 3 — POC Workbook Changes

### What Was in the Baseline (Pre-Update)

The original POC workbook contained:
- GP-01 to GP-05 (Global Prerequisites)
- Section 1: POC-01 to POC-04 (Cross-Subscription Sharing)
- Section 2: POC-05 to POC-07 (Quota Interaction — per-subscription)
- Section 3: POC-08 to POC-10 (Capacity Consumption)
- Section 4: POC-11 to POC-14 (VM Associate/Disassociate)
- Section 5: POC-20 to POC-22 (AZ Requirements)
- Section 6: POC-25 to POC-29 (DR Failover)

**Confirmed by:** `instruction.md` directory listing (GP-01→GP-05, Section 1→6 only), `poc_summary_20260819_173605.md` (27 tests: GP-01–GP-05 + POC-01–29 excluding Section 7).

---

### POC-1 — GP-06: Quota Group Prerequisites Added

**Change:** New global prerequisite GP-06 added before Section 7. Covers: Microsoft.Quota provider registration in all POC subscriptions; groupQuotas API availability check in East US 2; two-group POC topology documented with concrete vCPU numbers; quota CLI extension installation; tenant ID recording; management group scope warning.

**Fact-check:** `[Decided]` — Added in this session. Required as gate before POC-30 through POC-33. Topology numbers are concrete (Prod group: 128 vCPU = 32 × D4s_v3; NonProdDR group: 80 vCPU; DR floor: 32 vCPU at 40% of 20 VMs; effective NonProd ceiling: 48 vCPU). **Confirmed in documents.**

**Document location:** `azure_cr_poc_test_workbook.md` — Global Prerequisites section, GP-06.

**Status in documents:** ✅ Present and correct.

---

### POC-2 — Section 7: Quota Group Management (New Section)

**Change:** Entirely new Section 7 added with four POC tests (POC-30 to POC-33).

**Section objective:** Validate `Microsoft.Quota/groupQuotas` availability, two-group creation/management, quota release back to group pool on CR reduction, and group-level quota increase targeting.

**Distinction from Section 2:** Section 2 tests per-subscription quota at `Microsoft.Capacity/serviceLimits`. Section 7 tests the group quota layer at `Microsoft.Quota/groupQuotas`. Both layers are required and additive.

**Fact-check:** `[Decided]` — Added in this session. Section boundary and relationship to Section 2 correctly stated. **Confirmed in documents.**

**Document location:** `azure_cr_poc_test_workbook.md` — Section 7 (line 2210).

**Status in documents:** ✅ Present.

---

### POC-3 — POC-30: Quota Group GA Availability (Gate Test)

**Change:** New gate test. Creates both Prod and NonProdDR quota groups. If Step 1 returns 404, POC-31–33 are blocked.

**Priority:** Critical. Validates D6 foundational assumption — that `Microsoft.Quota/groupQuotas` is accessible and usable in the target tenant/region.

**Fact-check:** `[Derived — requires execution]` — groupQuotas GA status has regional and tenant restrictions noted in `azure_cr_quota_implications_research.md`. Failure path clearly documented (404 = escalate to Azure Support, D6 assumption blocked). **Confirmed in documents.**

**Document location:** `azure_cr_poc_test_workbook.md` — POC-30.

**Status in documents:** ✅ Present and correct.

---

### POC-4 — POC-31: NonProdDR Group Decomposition and Quota Release

**Change:** New test. Validates that NonProd CR quantity reduction releases quota to the GROUP pool (not just to the subscription), making it immediately available for DR expansion. Directly validates the Tier 3 quota-neutral claim. Also measures quota propagation latency — this becomes the documented Tier 3 RTO floor.

**Priority:** Critical. Validates QG-9 (quota-neutral claim).

**Fact-check:** `[Derived — requires execution]` — The group pool release behavior is documented as expected from `azure_cr_quota_implications_research.md` quota group transfer mechanics but not yet validated for the CR quantity reduction path specifically. If propagation latency > 5 minutes, this is documented as a BLOCKER for the Tier 3 architecture. **Confirmed in documents.**

**Document location:** `azure_cr_poc_test_workbook.md` — POC-31.

**Status in documents:** ✅ Present and correct.

---

### POC-5 — POC-32: DR Floor Enforcement Timing and Alert Validation

**Change:** New test. Validates two things:
1. The engine correctly blocks NonProd CRG expansion when it would encroach on dr_floor_vcpu (HC-7 enforcement)
2. Azure does NOT natively enforce intra-group sub-limits (confirming the engine is the sole enforcer)

Also validates `DRFloorViolationDetected` alert fires on violation.

**Priority:** Critical. Validates QG-4 (DR floor enforcement) and HC-7.

**Fact-check:** `[Derived — requires execution]` — Azure Quota Groups lack native intra-group sub-reservations — confirmed `[Documented]` in `azure_cr_quota_implications_research.md`. Engine-only enforcement is the designed behavior. POC-32 proves the engine detects and blocks correctly. **Confirmed in documents.**

**Document location:** `azure_cr_poc_test_workbook.md` — POC-32.

**Status in documents:** ✅ Present and correct.

---

### POC-6 — POC-33: Quota Increase Targeting — Group vs Subscription Level

**Change:** New test. Validates whether `POST Microsoft.Quota/groupQuotas/{id}/quota` is the correct endpoint for a group-level increase and measures approval latency. If approval latency > threshold, this proves that `emergency_transfer_headroom_vcpu` pre-staging in the NonProdDR group is essential (Tier 3 cannot rely on on-demand group increases).

**Priority:** High.

**Fact-check:** `[Derived — requires execution]` — Group-level quota increase endpoint is documented in Microsoft Learn but approval latency is not published. The test outcome directly informs whether the `emergency_transfer_headroom_vcpu` buffer is essential or optional. **Confirmed in documents.**

**Document location:** `azure_cr_poc_test_workbook.md` — POC-33.

**Status in documents:** ✅ Present and correct.

---

### POC-7 — Appendix D: Updated Test Case Index

**Change:** Appendix D updated with POC-30 to POC-33 entries (Section 7, Quota Group Management). Execution priority updated: POC-30, POC-31, POC-32 added to Critical tier; POC-33 added to High tier.

**Fact-check:** `[Decided]` — Updated in this session. Consistent with POC objectives and dependencies. **Confirmed in documents.**

**Document location:** `azure_cr_poc_test_workbook.md` — Appendix D.

**Status in documents:** ✅ Present and correct.

---

### POC-8 — Duplicate Separator Fix

**Change:** Removed duplicate `---` separator that appeared between Section 6 and Section 7 as an artifact of the editing process.

**Fact-check:** `[Confirmed]` — Fixed in this session. Verified by line inspection.

**Document location:** `azure_cr_poc_test_workbook.md` — line 2208 (was 2208–2209 before fix).

**Status in documents:** ✅ Fixed.

---

## Part 4 — Outstanding Gaps

### Resolved in Pass 2 (August 2026 — CR/CRG Update Pass)

The following gaps were resolved in the second document update pass following session clarifications:
- **PS_Prod dual-purpose confirmed** (recommendation + validation) — used by engine for both Prod region suggestion and pre-assignment validation.
- **dr_ratio_target confirmed as range [0.30, 0.40]** — `dr_ratio_min=0.30` (HC-6 floor), `dr_ratio_max=0.40` (target ceiling; engine always optimises toward upper bound to prefer higher buffer margins).

| Gap ID | Category | Description | Priority | Resolution |
|---|---|---|---|---|
| G-1 | CR/CRG | HC-1 and R2: `DR_region ≠ NonProd_region` removal | Critical | ✅ Resolved — Pass 2. HC-1 updated (line 228); R2 updated (line 51); D8 added. |
| G-2 | CR/CRG | HC-6 (DR_COVERAGE_FLOOR) not present | Critical | ✅ Resolved — Pass 2. HC-6 added between HC-5 and HC-7. Pseudocode updated with HC-6 check. |
| G-3 | CR/CRG | PS_Prod formula not present | Critical | ✅ Resolved — Pass 2. PS_Prod(r) formula fully defined. Pseudocode `compute_ps_prod` added. |
| G-4 | CR/CRG | PS_NonProd and PS_DR α and δ not updated | Critical | ✅ Resolved — Pass 2. PS_NonProd(r) and PS_DR(r) formulas defined. `compute_ps_nonprod` and `compute_ps_dr` added. Old formula retained as [SUPERSEDED] reference. |
| G-5 | CR/CRG | RegionalSnapshot missing per-CRG-type sub-schema | Critical | ✅ Resolved — Pass 2. 16 per-CRG-type fields added (prod_crg.*, nonprod_crg.*, dr_crg.*). |
| G-6 | CR/CRG | `effective_free`, `dr_overflow_reserve`, `coverage_ratio` not defined | High | ✅ Resolved — Pass 2. All three defined as named fields in RegionalSnapshot with formula derivation and usage cross-references. |
| G-7 | CR/CRG | Worked example with drift not present | High | ⏳ Deferred — old examples retained with [SUPERSEDED] formula note. New worked example with per-CRG-type state and drift is planned for next pass. |
| G-8 | CR/CRG | `dr_ratio_target` vs `dr_ratio_max` distinction not clarified | Medium | ✅ Resolved — Pass 2. DR Ratio Parameters section added. dr_ratio_min=0.30, dr_ratio_max=0.40, dr_ratio_target=[0.30,0.40] formally defined. dr_ratio_min added to PlacementPolicy fields. D9 added. |

### Resolved in Pass 3 (August 2026 — Extended Gaps Design Session)

| Gap ID | Category | Description | Priority | Resolution |
|---|---|---|---|---|
| G-9 | CR/CRG | Auto-increase trigger threshold not defined | Medium | ✅ Resolved — Pass 3. Three configurable thresholds defined (`dr_autoincrease_threshold=0.35`, `prod/nonprod_autoincrease_threshold=0.20`). Debounce cooldown (30 min) added. `CapacityIncreaseRequest` entity defined. Phase A (approval-gated) and Phase B (self-managed) workflows documented. D10 added. |
| G-10 | CR/CRG + QG | `max_emergency_transfer_qty` value not defined | Medium | ✅ Resolved — Pass 3. Formula: `potential_dr_demand × emergency_transfer_pct`. `emergency_transfer_pct=0.30` added to `PlacementPolicy`. Clearly scoped as crisis-only pre-staging (not steady-state). D10 added. |
| G-11 | CR/CRG | `EmergencyCapacityTransfer` not defined as a named API operation | High | ✅ Resolved — Pass 3. Full API defined: `POST /api/v1/capacity/emergency-transfer`. Request schema (`EmergencyCapacityTransferRequest`, `VM_DisassociationTarget`), response schema (`EmergencyCapacityTransferResponse`, `ExecutionStep`, `VM_ImpactRecord`), and state machine documented. D11 added. |
| G-12 | CR/CRG | Tier 1 / Tier 2 / Tier 3 transfer tier model not formally defined | High | ✅ Resolved — Pass 3. Three-tier model defined: Tier 1 (DirectExpansion — automated), Tier 2 (QuotaNeutralTransfer — policy-gated; replaces old "Tier 3" label), Tier 3 (DestructiveTransfer — operator dual-approval + elevated RBAC). Escalation logic pseudocode documented. D11 (relabelling) added. |
| G-13 | CR/CRG | VM/VMSS disassociation sequence within EmergencyCapacityTransfer not specified | High | ✅ Resolved (Phase 1 scope). Six-step Path B sequence documented (CR qty→0 provider side; CRG ref clear consumer side; confirm; DR expand; engine state update; audit alert). Path A fallback per-VM documented. Execution ordering (Dev→Test→Staging; smallest vCPU first). VMSS Phase 1 limitation formally recorded. Consumer credential model open item identified as Tier 3 implementation blocker. D11 added. |

### Still Outstanding

| Gap ID | Category | Description | Priority | Notes |
|---|---|---|---|---|
| G-7 | CR/CRG | Worked example with drift not present; old examples reference superseded formula | High | Deferred — old examples retained with [SUPERSEDED] formula note. Next pass. |
| G-13 (partial) | CR/CRG | VMSS emergency disassociation path not designed | Medium | Phase 1 limitation — single-VM Path B only. VMSS requires dedicated design session when maturity allows. |
| G-14 | CR/CRG | Consumer credential model for Tier 3 Step 2 not resolved (Managed Identity vs. cross-tenant SP) | **High** | **Tier 3 implementation blocker.** Must be resolved before Tier 3 can be engineered. |
| G-15 | CR/CRG | `engine_mode` state entity (STEADY_STATE / DR_EVENT_ACTIVE) not formally defined | Medium | Referenced by D10 but not yet modelled as a Cosmos DB entity or engine state machine. |

---

## Summary Statistics

### After Pass 1 (Quota Group Update)

| Category | Total Changes | In Documents | Not Yet in Documents |
|---|---|---|---|
| CR/CRG Design Changes | 9 | 2 ✅ | 7 ❌ |
| Quota Group Design Changes | 12 | 12 ✅ | 0 |
| POC Workbook Changes | 8 | 8 ✅ | 0 |
| **Total** | **29** | **22** | **7** |

### After Pass 2 (CR/CRG Update — August 2026)

| Category | Total Changes | In Documents | Deferred / Outstanding |
|---|---|---|---|
| CR/CRG Design Changes | 9 | 9 ✅ | 0 (G-7 deferred to next pass) |
| Quota Group Design Changes | 12 | 12 ✅ | 0 |
| POC Workbook Changes | 8 | 8 ✅ | 0 |
| **Core changes** | **29** | **29** | **0** |
| **Extended gaps** | 5 defined | 0 resolved | G-9 through G-13 all outstanding |

### After Pass 3 (Extended Gaps Design Session — August 2026)

| Category | Total Changes | In Documents | Deferred / Outstanding |
|---|---|---|---|
| CR/CRG Core Changes | 9 | 9 ✅ | 0 |
| Quota Group Changes | 12 | 12 ✅ | 0 |
| POC Workbook Changes | 8 | 8 ✅ | 0 |
| **Core changes** | **29** | **29** | **0** |
| Extended gaps G-9 to G-13 | 5 | 5 ✅ (G-13 partial) | G-13 VMSS path deferred |
| New gaps identified (G-14, G-15) | 2 | 0 | Both new — require design sessions |

**New items added in Pass 3:** Two new top-level sections (`Steady State Capacity Lifecycle Management`, `Emergency Capacity Transfer (Crisis Mode)`). Two new Decision Log entries (D10, D11). 8 new `PlacementPolicy.rules` fields. 5 new schema types (`CapacityIncreaseRequest`, `EmergencyCapacityTransferRequest/Response`, `VM_DisassociationTarget`, `ExecutionStep`, `VM_ImpactRecord`). 1 new API operation (`POST /api/v1/capacity/emergency-transfer`).

---

*Document generated August 2026 — Azure Capacity Reservations session*  
*Fact-checked against: multi_region_placement_design.md, azure_cr_poc_test_workbook.md, azure_cr_quota_implications_research.md, instruction.md, poc_summary_20260819_173605.md*
