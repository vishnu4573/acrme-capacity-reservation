# ACRME Hard Constraints Reference

**Classification:** Principal Cloud Architect — Placement Engine Design  
**Version:** 1.0  
**Date:** August 2026  
**Status:** Production Ready

> **v2.2 reconciliation note (2 Sep 2026).** Under Requirements Baseline v2.2 and ADR-002 v2.2 the **single governed quota pool** is the **primary** model: one pool per region/quota family covers Prod + NonProd/CVAL + DR, with Prod and DR protected by **logical earmarks** (`Prod_Reserved_Floor`, `DR_Earmark_vCPU`) rather than physical group separation. The **Two-Group Quota Architecture** referenced by HC-3 and HC-7 below is retained as the sanctioned **exception topology** (used only when Azure Quota Group limits or a mandatory Prod-isolation boundary make one pool impossible). The HC-3/HC-7 arithmetic is unchanged and remains correct; in the single-pool model the terms map as `Effective_NonProd_Ceiling → Allocatable_NonProd`, `NonProd_DR_Group_Limit → Pool_Limit`, and `DR_Floor_vCPU → DR_Earmark_vCPU` (max-not-sum, DR-017). Also: the EU cross-geo DR extension region is **Switzerland North** (REG-002). See ADR-002 v2.2, the Calculation Logic Reference v2.2 (Scenario 8/9), the FDD §4.2, and the TDD §8.3.

> **⚠️ Middle East DR — current legal position is `DR_NOT_OFFERED` (DEC-001, under legal review).** Baseline v2.2 records that **Legal has taken ownership of the Middle East programme** and that, because a large share of Middle East customers are government/medical-associated, **data-sovereignty / data-residency laws mean cross-border DR cannot meet residency requirements — so DR is currently NOT offered in the Middle East** (baseline §2 Strategic Drivers, §5.2 Out of Scope, §6 Region Strategy, **DR-014**). This is a **pending legal/business decision (DEC-001)**, listed among the programme's remaining major architectural risks (baseline §25). Consequences for placement below:
> - **The current default for a Middle East geography is `dr_region = NOT_OFFERED`.** The engine records the seed with no DR region and **does not** auto-assign any cross-geo DR. Middle East **production may still exist** without DR (DR-014).
> - **Switzerland North is a *pre-configured, conditional* cross-geo extension path only.** It is held in `PlacementPolicy` so that DR *can* be turned on quickly **if and only if Legal explicitly approves Middle East DR via DEC-001**. Until that approval is recorded, the extension path is **inactive** and the HC-10 canonical example below is a *conditional* design, not a live placement.
> - The HC-10 Cross-Geo Extension mechanics and VR-6 below therefore describe the **approved-path behaviour that applies only after DEC-001 clears**; the **default legal state overrides them with `DR_NOT_OFFERED`**. See ADR-001, ADR-005, the FDD §4.4/§8, the TDD §2.2/§9, and the Calculation Logic Reference Scenario 4.

---

## Overview

This document consolidates all **Hard Constraints (HC-1 through HC-10)** governing regional placement decisions in the **Azure Capacity Reservation Management Engine (ACRME)**. Hard constraints are **binary pass/fail gates** — any region failing a hard constraint is excluded from scoring entirely, not penalized with a lower score.

### Enforcement Architecture

Hard constraints are enforced at two stages in the placement decision pipeline:

**Stage 1 — Pre-filtering (before candidate set formation):**
- **HC-8** GEOGRAPHY_CONTAINMENT
- **HC-9** STANDARD_REGION_ONLY

**Stage 2 — Hard Constraint Gate (after geography/class filtering, before scoring):**
- **HC-1** REGION_SEPARATION
- **HC-2** CAPACITY_FLOOR
- **HC-3** QUOTA_FLOOR
- **HC-4** DR_SEPARATION_CLASS
- **HC-5** ZONE_AVAILABILITY
- **HC-6** DR_COVERAGE_FLOOR
- **HC-7** DR_FLOOR_INTEGRITY
- **HC-10** CROSS_GEO_EXTENSION_PATH_APPROVED

Regions surviving both stages enter the **scoring pipeline** where soft objectives (`PS_Prod`, `PS_NonProd`, `PS_DR`) rank them.

### Source Documents

- **HC-1 through HC-7:** `multi_region_placement_design.md` §27 (Hard Constraints)
- **HC-8, HC-9, HC-10:** `acrme_production_readiness_review_and_architecture.md` §27 (Production-Ready Region Selection)
- **Design rationale:** `design_change_summary.md` (Decisions D1–D9)

---

## Part 1 — Hard Constraint Definitions

### HC-1: REGION_SEPARATION [UPDATED]

**Category:** Isolation  
**Source:** Multi-Region Placement Design §27; Decision D8  
**Status:** Updated in Pass 2 — NonProd/DR co-location now permitted

#### Definition

```
NonProd_region ≠ Prod_region
DR_region      ≠ Prod_region
[Constraint DR_region ≠ NonProd_region REMOVED — NonProd and DR may share a region]
```

#### Rationale

NonProd/DR co-location is permitted to allow **DR overflow capacity reuse** from the NonProd CRG. This change (Decision D8) enables the engine to leverage unused NonProd capacity as a DR buffer, reducing the minimum region count from 4 to 3.

**With 3 regions:**  
Prod is isolated; NonProd and DR both draw from the remaining 2 regions (they may land on the same region or on different ones — determined by HC-6 and PS score).

**With 4 regions:**  
Prod eliminates 1; NonProd selects from 3; DR may share with NonProd or use the remaining regions — whichever satisfies HC-6 and maximises PS_DR.

#### Implementation

- Prod region is excluded from NonProd candidate set
- Prod region is excluded from DR candidate set
- NonProd region is **not** excluded from DR candidate set (co-location allowed)
- CVAL (alias for NonProd) and Prod must not share a region
- CVAL and DR may share a region only under the approved policy (HC-1 update per D8)

#### Validation Rules (VR)

- **VR-1:** Prod and DR must not share a region
- **VR-2:** CVAL and Prod must not share a region
- **VR-3:** CVAL and DR may share a region only under the approved policy

#### Evidence Tag

`[Derived]` from Azure Well-Architected Framework (Reliability pillar)

---

### HC-2: CAPACITY_FLOOR

**Category:** Capacity  
**Source:** Multi-Region Placement Design §27  
**Status:** Stable

#### Definition

```
CR headroom in candidate region ≥ minimum_reservation_units

where:
  minimum_reservation_units = 2 × requested_vm_count × SKU_vCPU_count  (default multiplier: 2)
  
  CR headroom = total_free_slots (in the target CRG type: Prod/NonProd/DR)
```

#### Rationale

Ensures sufficient capacity buffer exists in the region before placement. The **2× multiplier** provides headroom for growth and prevents placement into near-exhaustion regions.

#### Implementation

- Read `RegionalSnapshot.prod_crg_free_slots`, `nonprod_crg_free_slots`, or `dr_crg_free_slots` (per environment type)
- Compare against `minimum_reservation_units` (configurable per PlacementPolicy)
- **Regions at capacity floor are excluded from scoring entirely**

#### Configuration

- **Default multiplier:** 2
- **Configurable via:** `PlacementPolicy.capacity_floor_multiplier`
- **Overridable per geography or SKU class**

#### Evidence Tag

`[Undocumented — architectural judgement]`

---

### HC-3: QUOTA_FLOOR [UPDATED]

**Category:** Quota  
**Source:** Multi-Region Placement Design §27; Design Change Summary QG-3  
**Status:** Updated in Pass 2 — now reads from Quota Groups, not per-subscription QuotaRecord

#### Definition

```
For Prod placement in region R:
  REJECT if: Prod_Group_headroom(R) < requested_vm_count × vCPU_per_instance

For NonProd placement in region R:
  REJECT if: nonprod_headroom(R) < requested_vm_count × vCPU_per_instance
             (nonprod_headroom uses effective_nonprod_ceiling — floor-adjusted, not raw group_limit)

For DR placement in region R:
  REJECT if: dr_headroom(R) < target_dr_qty × vCPU_per_instance
             (target_dr_qty = customer_prod_vm_count × dr_ratio)
```

#### Data Source

- **Primary:** `QuotaGroup` entity (Cosmos DB), synced to `RegionalSnapshot` (Redis)
- **Fields:**
  - `Prod_Group_headroom(R)` = Prod group available quota in region R
  - `nonprod_headroom(R)` = NonProd+DR group available quota **minus DR floor** (see HC-7)
  - `dr_headroom(R)` = DR portion of NonProd+DR group quota
- **Legacy field:** `QuotaRecord.deployment_headroom` is superseded for placement checks; retained for per-subscription quota monitoring only

#### Formulas

**Prod Group Headroom:**
```
Prod_Group_headroom(R) = Prod_Group_Limit(R) - Prod_Group_Used(R)

where:
  Prod_Group_Limit(R) = base_subscription_quota_limit × (1 + emergency_transfer_headroom_vcpu / base_limit)
  Prod_Group_Used(R)  = Σ (prod_crg.quantity × vCPU) for all Prod CRGs in region R
```

**NonProd Headroom (effective ceiling):**
```
nonprod_headroom(R) = effective_nonprod_ceiling(R) - nonprod_quota_used(R)

where:
  effective_nonprod_ceiling(R) = NonProd_DR_Group_Limit(R) - DR_Floor_vCPU(R)
  NonProd_DR_Group_Limit(R)    = base_subscription_quota_limit × (1 + emergency_transfer_headroom_vcpu / base_limit)
  DR_Floor_vCPU(R)              = potential_dr_demand(R) × vCPU × dr_ratio_max
  nonprod_quota_used(R)         = Σ (nonprod_crg.quantity × vCPU) for all NonProd CRGs in region R
```

**DR Headroom:**
```
dr_headroom(R) = DR_Floor_vCPU(R) - dr_quota_used(R)

where:
  dr_quota_used(R) = Σ (dr_crg.quantity × vCPU) for all DR CRGs in region R
```

#### Validation Sequence

1. **HC-3 (Quota Floor):** Check raw headroom availability
2. **HC-7 (DR Floor Integrity):** Check floor compliance (applies only to NonProd placements)

#### POC Blocker

**B-1:** Azure Quota Groups functionality must be GA-available in target tenant/region. If `Microsoft.Capacity/resourceProviders/.../groupQuotas` returns 404, escalate to Azure Support. **POC-30** gates this.

#### Evidence Tag

`[Documented]` — Azure Quota Groups Preview API documentation

---

### HC-4: DR_SEPARATION_CLASS

**Category:** Resilience  
**Source:** Multi-Region Placement Design §27  
**Status:** Stable (non-paired regions only)

#### Definition

```
DR_region must have Separation_Class(DR_region, Prod_region) = HIGH
```

#### Rationale

Ensures non-correlated failure domains between Prod and DR regions. This constraint applies **only to non-paired regions** (e.g., standalone configuration with 3-4 explicitly chosen regions). Paired regions (e.g., East US / West US) are assumed to have HIGH separation by Azure design.

#### Separation Class Matrix

| Prod Region | DR Region | Separation Class | Eligible? |
|---|---|---|---|
| East US | West US | HIGH | ✅ Yes (paired) |
| East US | Central US | MEDIUM | ❌ No |
| East US | West Europe | HIGH | ✅ Yes (cross-geo) |
| UAE North | Saudi Arabia Central | MEDIUM | ❌ No (same geography) |
| UAE North | Switzerland North | HIGH | ⚠️ Separation-eligible, but **inactive** — Middle East DR is `DR_NOT_OFFERED` pending DEC-001 (DR-014); usable only after legal approval |

#### Implementation

- Read `SeparationClassRegistry` (static config or Azure metadata service)
- For non-paired regions, validate `Separation_Class(DR, Prod) = HIGH`
- Paired regions bypass this check (assumed HIGH by default)

#### Evidence Tag

`[Undocumented — architectural judgement]`

---

### HC-5: ZONE_AVAILABILITY

**Category:** Resilience  
**Source:** Multi-Region Placement Design §27  
**Status:** Stable

#### Definition

```
Candidate region must have ≥ 2 physical Availability Zones
```

#### Rationale

Single-zone regions are excluded for all non-dev environments. Multi-zone deployment is a **Well-Architected Framework Reliability pillar** requirement.

#### Implementation

- Read `RegionalSnapshot.zone_count` (populated from Azure metadata)
- Reject regions where `zone_count < 2`
- **Applies to:** Prod, CVAL, DR placements
- **Exemption:** Dev environments may bypass this constraint (configurable via `PlacementPolicy.allow_single_zone_dev`)

#### Examples

| Region | Zone Count | Eligible? |
|---|---|---|
| East US | 3 | ✅ Yes |
| West Europe | 3 | ✅ Yes |
| Central India | 3 | ✅ Yes |
| Brazil South | 1 | ❌ No |
| West US 3 | 3 | ✅ Yes |

#### Evidence Tag

`[Undocumented — architectural judgement]`

---

### HC-6: DR_COVERAGE_FLOOR [NEW]

**Category:** DR Capacity  
**Source:** Multi-Region Placement Design §27; Design Change Summary CR/CRG-1; Decision D8  
**Status:** New in Pass 2 — operationalises NonProd/DR co-location

#### Definition

```
REJECT DR placement in region R if combined DR + NonProd overflow capacity
is insufficient to absorb the new customer's DR demand:

  dr_crg_free_slots(R) + nonprod_crg_effective_free(R) < customer_requested_dr_slots

where:
  customer_requested_dr_slots = prod_vm_count × dr_ratio_max
  nonprod_crg_effective_free  = nonprod_crg_free_slots - nonprod_crg_dr_overflow_reserve
  
  dr_ratio_max = 0.40  (policy constant — upper bound for DR-to-Prod ratio)
```

#### Rationale

Since DR and NonProd may share a region (HC-1 constraint removed per D8), the engine must verify that the **combined capacity pool** can absorb the customer's DR need — either from the DR CRG directly, or from the NonProd CRG's reserved overflow headroom.

This constraint operationalises HC-1 co-location at the capacity selection level.

#### Data Requirements

Per-CRG-type snapshot fields (added in Pass 2):
- `nonprod_crg_free_slots(R)` — available NonProd CR capacity
- `nonprod_crg_effective_free(R)` — NonProd capacity minus DR overflow reserve
- `nonprod_crg_dr_overflow_reserve(R)` — capacity earmarked for DR failover absorption
- `dr_crg_free_slots(R)` — available DR CR capacity

#### Implementation Pseudocode

```python
def validate_HC6_DR_coverage_floor(region, customer_prod_vm_count):
    snapshot = get_regional_snapshot(region)
    
    customer_requested_dr_slots = customer_prod_vm_count * DR_RATIO_MAX  # 0.40
    
    combined_dr_capacity = (snapshot.dr_crg_free_slots + 
                            snapshot.nonprod_crg_effective_free)
    
    if combined_dr_capacity < customer_requested_dr_slots:
        return REJECT, "HC-6 DR_COVERAGE_FLOOR: Insufficient combined DR+NonProd overflow capacity"
    
    return PASS
```

#### Policy Constants

- **dr_ratio_min:** 0.30 (minimum DR-to-Prod ratio)
- **dr_ratio_max:** 0.40 (maximum DR-to-Prod ratio, used in HC-6 floor calculation)
- **dr_ratio_target:** 0.35 (recommended ratio)

#### Evidence Tag

`[Derived]` from Decision D8 (NonProd/DR co-location)

---

### HC-7: DR_FLOOR_INTEGRITY [NEW]

**Category:** Quota Protection  
**Source:** Multi-Region Placement Design §27; Design Change Summary QG-4  
**Status:** New in Pass 2 — enforces DR floor within Two-Group Quota Architecture

#### Definition

```
REJECT NonProd placement in region R if placing the requested quantity
would push nonprod_quota_used above effective_nonprod_ceiling:

  nonprod_quota_used(R) + (requested_vm_count × vCPU_per_instance) > effective_nonprod_ceiling(R)

where:
  effective_nonprod_ceiling(R) = NonProd_DR_Group_Limit(R) - DR_Floor_vCPU(R)
```

#### Rationale

Prevents NonProd allocation from **encroaching on the protected DR quota floor**. Within the Two-Group Quota Architecture, the NonProd+DR group has a shared limit; the DR floor reserves a portion for DR use only.

#### Evaluation Order

1. **HC-3 (Quota Floor):** Check raw headroom (`nonprod_headroom ≥ requested`)
2. **HC-7 (DR Floor Integrity):** Check floor compliance (`used + requested ≤ effective_ceiling`)

HC-3 checks availability; HC-7 checks compliance.

#### Formulas

**Effective NonProd Ceiling:**
```
effective_nonprod_ceiling(R) = NonProd_DR_Group_Limit(R) - DR_Floor_vCPU(R)
```

**DR Floor (per region):**
```
DR_Floor_vCPU(R) = potential_dr_demand(R) × vCPU_per_instance × dr_ratio_max

where:
  potential_dr_demand(R) = Σ prod_crg.quantity for all Prod CRGs that could fail over to region R
  dr_ratio_max           = 0.40
```

#### POC Example (GP-06 Topology)

**Inputs:**
- Prod demand: 80 VMs × 2 vCPU = 160 vCPU
- Base subscription quota limit: 200 vCPU

**Group Limits:**
- **Prod Group:** 200 × 1.28 = 256 vCPU (28% emergency headroom)
- **NonProd+DR Group:** 200 × 1.28 = 256 vCPU

**DR Floor Calculation:**
```
DR_Floor_vCPU = 80 VMs × 2 vCPU × 0.40 = 64 vCPU
```

**Effective NonProd Ceiling:**
```
effective_nonprod_ceiling = 256 - 64 = 192 vCPU
```

**Enforcement:**
```
If nonprod_quota_used = 150 vCPU:
  New NonProd request for 60 vCPU × 2 = 120 vCPU
  150 + 120 = 270 > 192  ❌ REJECT (HC-7 violation)
  
If nonprod_quota_used = 100 vCPU:
  New NonProd request for 40 vCPU × 2 = 80 vCPU
  100 + 80 = 180 ≤ 192  ✅ PASS
```

#### POC Blocker

**B-2:** Quota pool release behavior on CR reduction (Tier 2/3 quota-neutral claim) must be validated. **POC-31** measures release latency; confirm < 5 min for Tier RTO compliance.

#### Evidence Tag

`[Derived]` from Two-Group Quota Architecture design

---

### HC-8: GEOGRAPHY_CONTAINMENT [IMPLIED]

**Category:** Geography  
**Source:** Production Readiness Review §27  
**Status:** Implied constraint (no standalone definition block)

#### Definition

```
In Scenario 1 (geography-based placement), derived Prod region must be within
the Standard Capacity Regions for the customer's chosen geography.
```

#### Rationale

When a customer supplies an Azure geography (e.g., "US", "Europe", "Middle East") rather than a specific region, the engine derives the Prod anchor via `argmax(PS_Prod)` over Standard Capacity Regions **within that geography only**. This constraint ensures the derived Prod region respects the customer's geographic preference.

#### Enforcement Stage

**Stage 1 — Pre-filtering** (before candidate set formation)

#### Validation Rules (VR)

- **VR-4:** Derived Prod region must be within the Standard Capacity Regions for the customer's chosen geography

#### Implementation

```python
def get_prod_candidates(geography):
    all_regions = get_all_azure_regions()
    
    # Stage 1: Geography containment (HC-8)
    geo_filtered = [r for r in all_regions 
                    if r.geography == geography and 
                       r.region_class == "Standard"]
    
    # Stage 2: Apply HC-1..HC-7, HC-10
    hc_filtered = apply_hard_constraints(geo_filtered)
    
    # Stage 3: Score and rank
    return argmax(hc_filtered, key=lambda r: PS_Prod(r))
```

#### Examples

| Customer Geography | Eligible Regions | Ineligible (HC-8) |
|---|---|---|
| US | East US, West US, Central US, ... | West Europe, UK South, ... |
| Europe | West Europe, North Europe, UK South, ... | East US, Australia East, ... |
| Middle East | UAE North, Saudi Arabia Central | East US, Switzerland North* |

*Switzerland North becomes eligible only via **HC-10 Cross-Geo Extension Path** for DR, not for Prod — and that path is **inactive** for the Middle East while ME DR is `DR_NOT_OFFERED` (DR-014, pending DEC-001 legal approval).

#### Evidence Tag

`[Undocumented — architectural judgement]`

---

### HC-9: STANDARD_REGION_ONLY [NEW]

**Category:** Region Class  
**Source:** Production Readiness Review §27  
**Status:** New gate for production-ready region classification

#### Definition

```
Automated placement, scoring, recommendation, and all environment assignments
(Prod, CVAL, DR) must use Standard Capacity Regions only.
```

#### Rationale

**Restricted Capacity Regions** (sovereign clouds, government regions, regions with SKU limitations) are excluded from automated placement. Their exclusion is enforced at **Stage 1 of the eligibility decision tree**, not as a scoring penalty.

Exception deployments (customer explicitly requests a Restricted region) proceed via the **Scenario 2 exception path** only, requiring operator approval.

#### Region Classification

**Standard Capacity Regions:**
- Commercial Azure public cloud regions with full SKU availability
- No sovereign cloud restrictions
- No special approval required for CRG creation
- Examples: East US, West Europe, Australia East, Japan East, Brazil South

**Restricted Capacity Regions:**
- Azure Government (US DoD, US Gov)
- Azure China (21Vianet)
- Regions with limited SKU availability (flagged in Azure metadata)
- Regions requiring special tenant approval (sovereign cloud onboarding)

#### Enforcement Stage

**Stage 1 — Pre-filtering** (before candidate set formation)

#### Validation Rules (VR)

- **VR-5:** All automated placement paths (Scenario 1 geography-based, Prod derivation, NonProd/DR selection) must use Standard Capacity Regions only
- **VR-6:** CVAL and DR must not use Restricted Capacity Regions under any condition, including exception deployments

#### Implementation

```python
def get_eligible_regions_stage1(geography, customer_request):
    all_regions = get_all_azure_regions()
    
    # HC-9: Standard regions only (Stage 1 pre-filter)
    standard_regions = [r for r in all_regions if r.region_class == "Standard"]
    
    # If customer explicitly requests a Restricted region → Scenario 2 exception path
    if customer_request.region_override and customer_request.region_override.region_class == "Restricted":
        return handle_exception_deployment(customer_request)
    
    # HC-8: Geography containment
    geo_filtered = [r for r in standard_regions if r.geography == geography]
    
    return geo_filtered
```

#### Exception Deployment Workflow (Scenario 2)

**Trigger:** Customer explicitly requests a Restricted Capacity Region

**Workflow:**
1. Operator receives request via exception deployment queue
2. Validate customer has required tenant permissions (sovereign cloud registration)
3. Validate SKU availability in target Restricted region
4. Manual approval gate (ops team review)
5. If approved: Create Prod CRG in Restricted region; **CVAL and DR must still use Standard regions** (VR-6)
6. Record exception in `OperationRecord` with approval metadata

#### Evidence Tag

`[Undocumented — architectural judgement]`

---

### HC-10: CROSS_GEO_EXTENSION_PATH_APPROVED [NEW]

**Category:** Cross-Geo DR  
**Source:** Production Readiness Review §27  
**Status:** New governance control for cross-geography DR assignments

#### Definition

```
Any DR assignment to a region outside the customer's chosen geography must match
an explicitly enumerated Cross-Geo Extension path in the active PlacementPolicy.
```

#### Rationale

Cross-geography DR introduces data residency, compliance, and latency considerations that require explicit approval. The engine does not autonomously select cross-geo DR regions; it only accepts pre-approved extension paths defined in the active `PlacementPolicy`.

#### Enforcement

DR assignments to Standard Capacity Regions in a **different geography** are rejected if no approved extension path exists for the source geography.

#### Approved Cross-Geo Extension Paths (Example)

| Source Geography | Approved DR Geographies | Primary DR Region | Rationale |
|---|---|---|---|
| Middle East | Europe | Switzerland North **(inactive — gated by DEC-001)** | Middle East has only 2 regions (UAE North, Saudi Arabia); a 3-region model *would* need cross-geo DR, but ME DR is currently **`DR_NOT_OFFERED`** (data-sovereignty/residency, DR-014). Path stays inactive until Legal approves DR (DEC-001). |
| Australia | Asia Pacific | Singapore | Regional pair fallback |
| India | Asia Pacific | Singapore | Regional pair fallback |

#### Middle East Three-Region Placement (Conditional Example — gated by DEC-001)

> **This example applies ONLY if Legal approves Middle East DR (DEC-001).** As it stands, the current legal position is **`DR_NOT_OFFERED`** for the Middle East (data-sovereignty/residency; see the ⚠️ note at the top of this document and DR-014). Under the default legal state the placement is: **Prod** in-geo, **CVAL/NonProd** in-geo, and **`dr_region = NOT_OFFERED`** — steps 3 below are **not executed** and no cross-geo DR is assigned. The steps below describe the pre-configured behaviour that becomes live **only after** DEC-001 records an approval.

**Inputs:**
- Customer geography: Middle East
- Available Middle East Standard regions: UAE North, Saudi Arabia Central (2 only)
- **Middle East DR policy flag (DR-014):** default `DR_NOT_OFFERED = true` (pending DEC-001)

**Default placement (current legal position — `DR_NOT_OFFERED`):**
1. **Prod:** `argmax(PS_Prod)` over {UAE North, Saudi Arabia Central} → e.g., UAE North
2. **CVAL/NonProd:** Remaining Middle East region → Saudi Arabia Central
3. **DR:** **`NOT_OFFERED`** — seed records no DR region; engine does not assign Switzerland North or any other cross-geo region. Middle East production may still exist without DR.

**Conditional placement (only if DEC-001 approves ME DR — sets `DR_NOT_OFFERED = false`):**
1. **Prod:** `argmax(PS_Prod)` over {UAE North, Saudi Arabia Central} → e.g., UAE North
2. **CVAL/NonProd:** Remaining Middle East region → Saudi Arabia Central
3. **DR:** Cross-Geo Extension to **Switzerland North** (pre-approved path, now activated)

**Validation (conditional path only):**
- Switzerland North must pass **HC-1 through HC-10** including DR coverage floor (HC-6)
- If Switzerland North fails any HC, the placement is **rejected with an ops alert**
- The engine does **not** silently select any alternative outside the approved extension paths

#### Validation Rules (VR)

- **VR-8 (default):** For a Middle East geography with `DR_NOT_OFFERED = true` (current legal position, DEC-001), the seed **must** record `dr_region = NOT_OFFERED`; the engine must **not** auto-assign Switzerland North or any cross-geo DR.
- **VR-8a (conditional):** *Only if* DEC-001 approval has cleared the `DR_NOT_OFFERED` flag, the Middle East DR region must be Switzerland North via the approved Cross-Geo Extension path.
- **VR-11:** Cross-Geo Extension DR path must be explicitly approved in active `PlacementPolicy` **and** (for the Middle East) gated by a recorded DEC-001 approval.

#### Implementation

```python
def resolve_dr_region(customer_geography, candidate_dr_region):
    policy = get_active_placement_policy()

    # DR-014 / DEC-001: honour the per-geography DR_NOT_OFFERED legal flag FIRST.
    # For the Middle East this defaults to True (current legal position) until Legal
    # records a DEC-001 approval that clears it.
    if policy.dr_not_offered.get(customer_geography, False):
        return "NOT_OFFERED"  # seed records no DR; no cross-geo substitution (VR-6)

    return candidate_dr_region


def validate_HC10_cross_geo_extension(customer_geography, dr_region):
    policy = get_active_placement_policy()

    # DR_NOT_OFFERED short-circuits HC-10: no DR region to validate.
    if dr_region == "NOT_OFFERED":
        return PASS  # legal no-DR outcome (DR-014, DEC-001)

    # Check if DR region is in same geography as customer
    if dr_region.geography == customer_geography:
        return PASS  # Same-geo DR, HC-10 does not apply
    
    # Cross-geo DR → validate against approved extension paths
    approved_paths = policy.cross_geo_extension_paths.get(customer_geography, [])
    
    if dr_region not in approved_paths:
        return REJECT, f"HC-10 CROSS_GEO_EXTENSION_PATH_APPROVED: DR region {dr_region.name} not in approved extension paths for {customer_geography}"

    # DEC-001 gate for the Middle East: even a configured extension path stays
    # inactive until a recorded legal approval clears DR_NOT_OFFERED.
    if customer_geography == "Middle East" and policy.dr_not_offered.get("Middle East", True):
        return REJECT, "HC-10 DEC-001 PENDING: Middle East DR is DR_NOT_OFFERED pending legal approval; Switzerland North extension is inactive"

    return PASS
```

#### PlacementPolicy Configuration (Example)

```json
{
  "policy_version": "2026-08-Q3",
  "dr_not_offered": {
    "Middle East": true
  },
  "dr_not_offered_rationale": {
    "Middle East": "Legal-owned programme (DEC-001, under review). Data-sovereignty/residency laws for a largely government/medical customer base mean cross-border DR cannot meet residency requirements; DR is currently NOT offered (baseline §2/§5.2/§6, DR-014). Production may still exist without DR. Set to false ONLY when Legal records a DEC-001 approval."
  },
  "cross_geo_extension_paths": {
    "Middle East": {
      "approved_dr_regions": ["Switzerland North"],
      "activation_gated_by": "DEC-001 (dr_not_offered['Middle East'] must be false)",
      "rationale": "Pre-configured, CONDITIONAL path. Middle East has only 2 Standard regions, so a 3-region model would need cross-geo DR — but this path is inactive while DR_NOT_OFFERED is true."
    },
    "Australia": {
      "approved_dr_regions": ["Singapore", "Japan East"],
      "rationale": "Regional pair fallback for Australia East / Australia Southeast"
    }
  }
}
```

#### Evidence Tag

`[Undocumented — architectural judgement]`

---

## Part 2 — Hard Constraint Summary Table

| HC | Name | Type | Enforcement Stage | Primary Impact | Updated in Pass |
|---|---|---|---|---|---|
| **HC-1** | REGION_SEPARATION | Isolation | Stage 2 | Prod isolated from NonProd/DR; NonProd=DR co-location allowed | Pass 2 (D8) |
| **HC-2** | CAPACITY_FLOOR | Capacity | Stage 2 | Minimum CR headroom required | Stable |
| **HC-3** | QUOTA_FLOOR | Quota | Stage 2 | Minimum quota headroom per environment type (Prod/NonProd/DR) | Pass 2 (QG-3) |
| **HC-4** | DR_SEPARATION_CLASS | Resilience | Stage 2 | DR region must have HIGH separation class from Prod | Stable |
| **HC-5** | ZONE_AVAILABILITY | Resilience | Stage 2 | Minimum 2 availability zones required | Stable |
| **HC-6** | DR_COVERAGE_FLOOR | DR Capacity | Stage 2 | Combined DR+NonProd capacity must absorb DR demand | Pass 2 (D8) |
| **HC-7** | DR_FLOOR_INTEGRITY | Quota Protection | Stage 2 | NonProd placement cannot encroach on DR quota floor | Pass 2 (QG-4) |
| **HC-8** | GEOGRAPHY_CONTAINMENT | Geography | Stage 1 | Prod region must be within customer's chosen geography (Scenario 1) | Implied |
| **HC-9** | STANDARD_REGION_ONLY | Region Class | Stage 1 | Only Standard Capacity Regions eligible for automated placement | PRR §27 |
| **HC-10** | CROSS_GEO_EXTENSION_PATH_APPROVED | Cross-Geo DR | Stage 2 | Cross-geography DR requires explicit approval path | PRR §27 |

---

## Part 3 — Enforcement Pipeline

### Stage 1 — Pre-filtering (Eligibility Decision Tree)

**Applied before candidate set formation:**

```
All Azure Regions
    ↓
[HC-9: STANDARD_REGION_ONLY filter]
    ↓
Standard Capacity Regions
    ↓
[HC-8: GEOGRAPHY_CONTAINMENT filter] (if Scenario 1)
    ↓
Standard Regions in Customer Geography
    ↓
Candidate Set for Stage 2
```

### Stage 2 — Hard Constraint Gate

**Applied to each candidate region before scoring:**

```python
def apply_hard_constraints_stage2(region, environment_type, customer_context):
    """
    Returns: (PASS, None) or (REJECT, reason)
    """
    # HC-1: Region separation
    if not validate_HC1_region_separation(region, environment_type, customer_context):
        return REJECT, "HC-1 REGION_SEPARATION"
    
    # HC-2: Capacity floor
    if not validate_HC2_capacity_floor(region, environment_type):
        return REJECT, "HC-2 CAPACITY_FLOOR"
    
    # HC-3: Quota floor
    if not validate_HC3_quota_floor(region, environment_type, customer_context):
        return REJECT, "HC-3 QUOTA_FLOOR"
    
    # HC-4: DR separation class (DR only)
    if environment_type == "DR" and not validate_HC4_dr_separation_class(region, customer_context.prod_region):
        return REJECT, "HC-4 DR_SEPARATION_CLASS"
    
    # HC-5: Zone availability
    if not validate_HC5_zone_availability(region):
        return REJECT, "HC-5 ZONE_AVAILABILITY"
    
    # HC-6: DR coverage floor (DR only)
    if environment_type == "DR" and not validate_HC6_dr_coverage_floor(region, customer_context):
        return REJECT, "HC-6 DR_COVERAGE_FLOOR"
    
    # HC-7: DR floor integrity (NonProd only)
    if environment_type == "NonProd" and not validate_HC7_dr_floor_integrity(region, customer_context):
        return REJECT, "HC-7 DR_FLOOR_INTEGRITY"
    
    # HC-10: Cross-geo extension path (cross-geo DR only)
    if environment_type == "DR" and region.geography != customer_context.geography:
        if not validate_HC10_cross_geo_extension(customer_context.geography, region):
            return REJECT, "HC-10 CROSS_GEO_EXTENSION_PATH_APPROVED"
    
    return PASS, None
```

### Stage 3 — Scoring Pipeline

Regions surviving HC-1..HC-10 enter scoring:

- **Prod:** Ranked by `PS_Prod(r)` = argmax over survivors
- **NonProd:** Ranked by `PS_NonProd(r)` = argmax over survivors (excluding Prod region)
- **DR:** Ranked by `PS_DR(r)` = argmax over survivors (excluding Prod region; may include NonProd region per HC-1)

---

## Part 4 — Validation Rules (VR) Cross-Reference

The Production Readiness Review defines **11 Validation Rules (VR-1..VR-11)** that enforce hard constraints:

| VR | Description | Enforced HCs |
|---|---|---|
| **VR-1** | Prod and DR must not share a region | HC-1 |
| **VR-2** | CVAL and Prod must not share a region | HC-1 |
| **VR-3** | CVAL and DR may share a region only under approved policy | HC-1 (D8 update) |
| **VR-4** | Derived Prod region must be within customer's chosen geography | HC-8 |
| **VR-5** | All automated placement paths must use Standard Capacity Regions only | HC-9 |
| **VR-6** | CVAL and DR must not use Restricted Capacity Regions under any condition | HC-9 |
| **VR-7** | Standard region passes HC-1 through HC-10 → if all excluded, exhaustion error | HC-1..10 |
| **VR-8** | For Middle East geography, DR defaults to `NOT_OFFERED` (DR-014, DEC-001 legal position); Switzerland North via approved cross-geo path applies **only after** a recorded DEC-001 approval clears `DR_NOT_OFFERED` | HC-10 |
| **VR-9** | Only on the DEC-001-approved conditional path: if Switzerland North fails HC-1..HC-10, block placement with ops alert | HC-1..10 |
| **VR-10** | Restricted region requested by customer → Scenario 2 exception path only | HC-9 |
| **VR-11** | Cross-Geo Extension DR path must be explicitly approved in active PlacementPolicy | HC-10 |

---

## Part 5 — POC Blockers & Testing

### Critical POC Blockers

| ID | Issue | Blocked HCs | POC Gate | Resolution |
|---|---|---|---|---|
| **B-1** | Azure Quota Groups functionality in target tenant/region | HC-3, HC-7 | POC-30 | GA availability check; if 404 → escalate to Azure Support |
| **B-2** | Quota pool release behavior on CR reduction (Tier 2/3 quota-neutral claim) | HC-7 | POC-31 | Measure release latency; confirm < 5 min for Tier RTO |

### POC Test Coverage

**POC-01 through POC-10:** Hard constraint validation (HC-1..HC-10)  
**POC-11:** Middle East cross-geo DR (HC-10) — **blocked pending DEC-001**; ME DR is `DR_NOT_OFFERED` today, so this POC runs only if/when Legal approves ME DR  
**POC-30:** Quota Groups API integration (HC-3, HC-7)  
**POC-31:** Quota pool release latency (HC-7 emergency transfer dependency)

---

## Part 6 — Configuration & Policy

### PlacementPolicy Schema (Hard Constraint Section)

```json
{
  "policy_version": "2026-08-Q3",
  "hard_constraints": {
    "capacity_floor_multiplier": 2,
    "dr_ratio_min": 0.30,
    "dr_ratio_max": 0.40,
    "dr_ratio_target": 0.35,
    "allow_single_zone_dev": false,
    "cross_geo_extension_paths": {
      "Middle East": {
        "approved_dr_regions": ["Switzerland North"],
        "rationale": "Middle East has only 2 Standard regions; 3-region model requires cross-geo DR"
      }
    },
    "separation_class_overrides": {}
  }
}
```

### Policy Constants

| Constant | Default Value | Configurable? | Affected HCs |
|---|---|---|---|
| **capacity_floor_multiplier** | 2 | ✅ Yes (per geography/SKU) | HC-2 |
| **dr_ratio_min** | 0.30 | ✅ Yes | HC-6, HC-7 |
| **dr_ratio_max** | 0.40 | ✅ Yes | HC-6, HC-7 |
| **dr_ratio_target** | 0.35 | ✅ Yes | Scoring (not HC) |
| **min_zone_count** | 2 | ✅ Yes | HC-5 |
| **allow_single_zone_dev** | false | ✅ Yes | HC-5 |
| **cross_geo_extension_paths** | {} | ✅ Yes | HC-10 |

---

## Part 7 — Implementation Checklist

### Engineering Backlog Cross-Reference

| HC | Primary Epic | Stories | Tasks |
|---|---|---|---|
| HC-1..HC-8 | EPIC-07 (Regional Snapshot), EPIC-08 (Placement) | S0702, S0703, S0704, S0705 | T070201 |
| HC-9, HC-10 | EPIC-07 (Regional Snapshot), EPIC-08 (Placement) | S0702 | T070202 |
| HC-3, HC-7 (Quota Groups) | EPIC-03 (Quota Management) | S0310, S0311, S0314 | T031001..T031006 |
| HC-6 (DR Coverage) | EPIC-06 (DR Management), EPIC-08 (Placement) | S0601, S0704 | T060101, T070401 |

### Pre-Deployment Validation

- [ ] HC-1..HC-10 validation functions implemented (unit tested)
- [ ] Stage 1 pre-filtering logic (HC-8, HC-9) validated
- [ ] Stage 2 hard constraint gate logic (HC-1..HC-7, HC-10) validated
- [ ] RegionalSnapshot schema extended with HC-6 fields (nonprod_crg_effective_free, dr_crg_free_slots)
- [ ] QuotaGroup integration (HC-3, HC-7) validated via POC-30
- [ ] Cross-Geo Extension paths configured in PlacementPolicy (Middle East path present but **inactive** — `dr_not_offered["Middle East"] = true` pending DEC-001)
- [ ] Middle East default placement validated: `dr_region = NOT_OFFERED` (DR-014, current legal position)
- [ ] Middle East conditional three-region placement (Switzerland North, HC-10) validated **only after** DEC-001 legal approval
- [ ] Exception deployment workflow (HC-9 Restricted region override) tested
- [ ] HC rejection reasons logged to OperationRecord for audit
- [ ] Validation Rules VR-1..VR-11 traced to HC enforcement points

---

## Appendix A — Decision Log Cross-Reference

| Decision | HCs Affected | Change |
|---|---|---|
| **D8** | HC-1, HC-6 | Removed `DR_region ≠ NonProd_region` constraint; added HC-6 to operationalise co-location |
| **D1, D2** | HC-3, HC-7 | Introduced Two-Group Quota Architecture; HC-3 now reads from Quota Groups; HC-7 enforces DR floor |
| **D9** | HC-9, HC-10 | Introduced Standard/Restricted region classification; added HC-9 and HC-10 governance gates |

---

## Appendix B — Evidence Tags

All hard constraints carry one of four evidence tags:

- **[Documented]** — Derived from Azure platform documentation (e.g., Quota Groups API)
- **[Derived]** — Logical consequence of a documented constraint or design decision
- **[Decided]** — Explicit design choice (traceable to Decision Log D1–D9)
- **[Undocumented — architectural judgement]** — Azure Well-Architected Framework best practice, not explicitly documented by Microsoft

---

**Document Status:** Production Ready  
**Next Review:** After POC-30 and POC-31 completion (Quota Groups GA validation)

