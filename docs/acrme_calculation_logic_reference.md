# ACRME Calculation Logic Reference — All Scenarios

This document consolidates **every calculation logic** used by the Azure Capacity Reservation
Management Engine (ACRME), organized by the scenario in which it fires. Each formula is traced to its
source document and carries the same evidence tag used in the source:

- `[Documented]` — backed by Microsoft Learn or platform documentation.
- `[Decided]` — an approved design decision recorded in the Decision Log.
- `[Derived]` — a logical consequence of the design; requires POC validation where noted.
- `[Assumed]` — a policy default or working hypothesis, tunable and not yet empirically validated.

**Sources:** `acrme_production_readiness_review_and_architecture.md` (PRR §26, §27, §28, §10),
`research/design_change_summary.md` (CR/CRG-1..9, QG-1..12), and the POC workbook topology (GP-06).

> **Convention.** `vCPU` = `vCPU_per_instance` for the SKU family. `CVAL` (Customer Validation) and
> `NonProd` are interchangeable; scoring identifiers keep the `NonProd` spelling for engineering
> consistency. All raw ratios are clamped with `Clamp(x) = max(0, min(1, x))` before weighting.

---

## Index of scenarios

| # | Scenario | Core calculation |
|---|---|---|
| 1 | Prod region derivation — customer picks a **geography** | `argmax(PS_Prod)` over Standard regions |
| 2 | Prod region validation — customer picks a **specific region** | HC-1..HC-10 gate + `PS_Prod` post-validation |
| 3 | Restricted region request | Exception workflow (no scoring) |
| 4 | Middle East three-region deployment | `argmax(PS_Prod)` over 2 in-geo regions + cross-geo DR |
| 5 | CVAL / NonProd region selection | `argmax(PS_NonProd)` |
| 6 | DR region selection | `argmax(PS_DR)` |
| 7 | Hard-constraint eligibility gate | HC-3, HC-6, HC-7 arithmetic |
| 8 | Quota group sizing | Prod & NonProd+DR group budgets |
| 9 | DR floor accounting | `DR_Floor_vCPU`, effective ceiling, headroom |
| 10 | Environment quota scoring | `Quota_Score_{Prod,NonProd,DR}` |
| 11 | Capacity forecast / CR sizing | `Forecast_Quantity` |
| 12 | Auto-increase trigger | utilisation thresholds + debounce |
| 13 | Emergency transfer & tier escalation | Tier 1/2/3, quota-neutral transfer |
| 14 | Scaling & API-budget model | CRG cardinality, request-per-cycle |
| 15 | DR ratio parameters | `dr_ratio_min/max/target` |

---

## Shared building blocks (used by several scenarios)

### Default scoring weights `[Assumed]` (PRR §28)

```
alpha (α) = 0.30   # capacity / headroom signal
beta  (β) = 0.20   # quota headroom signal
gamma (γ) = 0.25   # capacity-weighted distribution
delta (δ) = 0.15   # DR-coverage / overflow-integrity signal
epsilon(ε)= 0.10   # zone diversity
Clamp(x)  = max(0, min(1, x))       # every component clamped to [0,1] before weighting
```

### Named regional-snapshot quantities `[Decided]` / `[Derived]` (design_change_summary CR/CRG-4,5)

```
nonprod_crg.effective_free = nonprod_crg.free_slots - dr_overflow_reserve
dr_crg.coverage_ratio      = dr_crg.quantity / potential_dr_demand
potential_dr_demand(region)= Σ prod_allocated  for all customers whose dr_region = region
```

### DR ratio parameters `[Decided]` (design_change_summary G-8)

```
dr_ratio_min    = 0.30      # HC-6 floor
dr_ratio_max    = 0.40      # target ceiling — the engine always sizes toward the upper bound
dr_ratio_target = [0.30, 0.40]
```

---

## Scenario 1 — Prod region derivation (customer chooses an Azure *geography*)

**Trigger:** customer supplies a geography (e.g. "Europe"), not a specific region. (PRR §27 "Prod region
input modes", Scenario 1.)

**Logic:**

1. Build candidate set = **Standard Capacity Regions** in the chosen geography. Restricted regions are
   excluded *before* scoring and never receive a score. `[Undocumented — architectural judgement]`
2. Score every surviving candidate with `PS_Prod` from the versioned regional snapshot.
3. Select `derived Prod anchor = argmax(PS_Prod)`.
4. **Tie-break:** deterministic — first region in the Standard Capacity Region list order for that
   geography (also the cold-start default when no snapshot exists or all scores tie). `[Derived]`
5. Then run sequential **CVAL → DR** selection on the same Standard region pool (Scenarios 5 & 6),
   applying Middle East handling where required.

### `PS_Prod(r)` `[Decided]` (design_change_summary CR/CRG-7)

```
PS_Prod(r) =
    0.30 × Clamp(nonprod_crg.effective_free / prod_crg.quantity)     ← α: NonProd headroom signal
  + 0.20 × Clamp(prod_crg.quota_headroom  / prod_crg.quota_limit)    ← β: Prod quota headroom
  + 0.25 × Clamp(1 - prod_customer_count  / total_customers)         ← γ: distribution fairness
  + 0.15 × Clamp(dr_crg.coverage_ratio)                              ← δ: DR readiness of likely DR target
  + 0.10 × Clamp(az_count / 3)                                       ← ε: zone diversity
```

`PS_Prod` is **dual-purpose**: it derives the Prod region here, and it is reused for post-selection
validation in Scenario 2. `[Decided]`

**Determinism & audit:** derivation is deterministic given a snapshot; the derived region, every
candidate score, and the policy version are written to the `OperationRecord` for replay. `[Derived]`

---

## Scenario 2 — Prod region validation (customer supplies a *specific* region)

**Trigger:** customer names an exact Azure region. (PRR §27 Scenario 2.)

**Logic (branch on region class):**

- **Standard Capacity Region:** validate against **HC-1 … HC-10** (Scenario 7). If eligible, it becomes
  the Prod anchor directly; `PS_Prod` is computed only for **post-selection validation / audit** (not for
  selection). `[Derived]`
- **Restricted Capacity Region:** do **not** score — route to the Exception Deployment Workflow
  (Scenario 3). `[Derived]`

There is no `argmax` here — the customer's choice is authoritative once it passes the hard constraints.

---

## Scenario 3 — Restricted region request (exception path)

**Trigger:** the requested (or only feasible) region is a **Restricted Capacity Region**. (PRR §27
"Exception-Based Placement Workflow".)

**Logic:** **no scoring formula is evaluated.** The request is diverted to the manual Exception
Deployment Workflow (governance approval, validation rules VR-1..VR-11, HC-9/HC-10 governance controls).
Restricted regions never enter the scoring pipeline. `[Undocumented — architectural judgement]`

---

## Scenario 4 — Middle East three-region deployment

**Trigger:** a Middle East deployment requiring three environments. (PRR §27 "Middle East Special
Handling".)

**Logic:**

```
1. Candidate in-geo Standard regions = { Saudi Arabia, UAE North }   (both are Standard)
2. Score both with PS_Prod.
3. Prod  = argmax(PS_Prod) over the two.
4. CVAL  = the remaining in-geo region (deterministic — only one candidate left).
5. DR    = cross-geo extension region (e.g. Europe / Belgium Central) because no third
           in-geo Standard region exists to satisfy region separation.
```

Prod and CVAL use the **same** `PS_Prod` / `PS_NonProd` math as elsewhere; only the **DR leg** is special
(cross-geo). Cross-geo extension constraints from PRR §27 apply to the DR region. `[Decided]` / `[Undocumented — architectural judgement]`

---

## Scenario 5 — CVAL / NonProd region selection

**Trigger:** sequential step after the Prod anchor is fixed. Selects `argmax(PS_NonProd)` over eligible
Standard regions. (PRR §28.)

### `PS_NonProd(r)` — restructured model `[Decided]` (design_change_summary CR/CRG-7)

```
PS_NonProd(r) =
    0.30 × Clamp(nonprod_crg.effective_free / nonprod_crg.quantity)      ← α: effective NonProd headroom
  + 0.20 × Clamp(nonprod_crg.quota_headroom / nonprod_crg.quota_limit)   ← β: NonProd quota headroom
  + 0.25 × Clamp(1 - nonprod_customer_count / total_customers)           ← γ: distribution fairness
  + 0.15 × Clamp(nonprod_crg.effective_free / nonprod_crg.quantity)      ← δ: overflow capacity health
  + 0.10 × Clamp(az_count / 3)                                           ← ε: zone diversity
```

### Corrected pilot variant `[Undocumented — architectural judgement]` (PRR §28)

The PRR flags that the model above duplicates the same signal under α and δ (combined weight 0.45). The
PRR's corrected pilot formula removes the duplication:

```
PS_NonProd = 0.35 Capacity + 0.25 Quota + 0.25 Distribution
           + 0.05 DR_Overflow_Integrity + 0.10 Zones

Distribution = 1 - Region_Assigned_Demand / Total_Assigned_Demand   # demand units, not customer count
```

> Both variants are recorded. The restructured model (CR/CRG-7) is the design-of-record; the PRR
> corrected variant is the reviewer-recommended pilot refinement. Neither is empirically validated yet.

---

## Scenario 6 — DR region selection

**Trigger:** final sequential step. Selects `argmax(PS_DR)` over eligible Standard regions (or the
cross-geo region for Middle East). (PRR §28.)

### `PS_DR(r)` `[Decided]` (design_change_summary CR/CRG-7)

```
PS_DR(r) =
    0.30 × Clamp(dr_crg.free_slots / dr_crg.quantity)                   ← α: DR CRG headroom
  + 0.20 × Clamp(dr_crg.quota_headroom / dr_crg.quota_limit)           ← β: DR quota headroom
  + 0.25 × Clamp(1 - dr_customer_count / total_customers)              ← γ: distribution fairness
  + 0.15 × min(1.0, dr_crg.coverage_ratio / dr_ratio_target)          ← δ: coverage-ratio health
  + 0.10 × Clamp(az_count / 3)                                         ← ε: zone diversity
```

---

## Scenario 7 — Hard-constraint eligibility gate (arithmetic constraints)

Before any region is scored (Scenario 1) or accepted (Scenario 2), it must pass the hard constraints.
The calculation-bearing ones are below. (design_change_summary QG-5, CR/CRG-6, QG-6.)

### HC-3 QUOTA_FLOOR (per environment) `[Decided]`

```
Prod:    Prod_Group_headroom(R)  ≥ requested_vm_count × vCPU
NonProd: nonprod_headroom(R)     ≥ requested_vm_count × vCPU      # uses effective_nonprod_ceiling
DR:      dr_headroom(R)          ≥ target_dr_qty     × vCPU
```

### HC-6 DR_COVERAGE_FLOOR `[Decided]`

```
Region ineligible for DR if:
    (dr_crg.free_slots + nonprod_crg.effective_free) < customer_requested_dr_slots
```

### HC-7 DR_FLOOR_INTEGRITY `[Decided]`

```
REJECT NonProd placement in region R if:
    nonprod_quota_used(R) + (requested_vm_count × vCPU) > effective_nonprod_ceiling(R)
```

HC-3 checks raw group headroom; HC-7 additionally enforces floor compliance. Both must pass. On breach:
alert `DRFloorViolationDetected` (Critical).

### Minimum-headroom policy defaults `[Decided]` (design_change_summary QG-10)

```
min_prod_quota_headroom_vcpu    = 20
min_nonprod_quota_headroom_vcpu = 20
min_dr_headroom_vcpu            = 16
```

---

## Scenario 8 — Quota group sizing (per region)

Every managed region has exactly two Azure Quota Groups. (design_change_summary QG-1, QG-3; PRR §26.)

```
Prod_Group_Limit(region) =
    Prod_CRG_quantity × vCPU × (1 + prod_growth_buffer)
    prod_growth_buffer = 0.20

NonProd_DR_Group_Limit(region) =
      NonProd_CRG_quantity × vCPU × (1 + nonprod_growth_buffer)      # nonprod_growth_buffer = 0.20
    + DR_CRG_quantity      × vCPU
    + emergency_transfer_headroom_vcpu

emergency_transfer_headroom_vcpu = max_emergency_transfer_qty × vCPU
max_emergency_transfer_qty       = potential_dr_demand × emergency_transfer_pct   # emergency_transfer_pct = 0.30
```

`[Decided]` — the `emergency_transfer_headroom_vcpu` term is what makes Tier 3 DR expansion quota-neutral
(Scenario 13).

---

## Scenario 9 — DR floor accounting (engine-enforced sub-limit)

Azure Quota Groups have **no native intra-group sub-reservation**, so the engine enforces the DR floor by
arithmetic. (PRR §26 Formulas; design_change_summary CR/CRG-2, QG-4.)

```
DR_Floor_vCPU(region)        = potential_dr_demand × vCPU × dr_ratio_max        # dr_ratio_max = 0.40
Effective_NonProd_Ceiling    = NonProd_DR_Group_Limit - DR_Floor_vCPU
NonProd_Headroom             = Effective_NonProd_Ceiling - NonProd_Used_vCPU
Group_Headroom               = Group_Limit - Group_Used
dr_crg.coverage_ratio        = dr_crg.quantity / potential_dr_demand
```

**Dual-validation control:** a separate detector recomputes the DR floor from authoritative assignment
data; any disagreement between command-time and detector values disables automatic NonProd expansion.
`[Undocumented — architectural judgement]`

### Worked topology (POC GP-06) `[Decided]`

```
Prod group          = 128 vCPU  (32 × D4s_v3)
NonProdDR group     =  80 vCPU
DR floor            =  32 vCPU   (= 40% of 20 potential DR VMs × vCPU)
Effective NonProd ceiling = 48 vCPU  (80 - 32)
```

---

## Scenario 10 — Environment quota scoring (`β` component detail)

The generic `Quota_Score` is dispatched by environment type. (design_change_summary QG-7.)

```
Quota_Score_Prod(r)    = prod_group_headroom_vcpu   / prod_group_limit_vcpu
Quota_Score_NonProd(r) = nonprod_headroom_vcpu       / effective_nonprod_ceiling_vcpu
Quota_Score_DR(r)      = dr_headroom_vcpu            / dr_floor_vcpu
```

Semantics differ by type: a DR score of `1.0` means **maximum expansion room** (DR CRG at zero), not
maximum quota consumed. Zero-denominator guards apply. `[Decided]`

---

## Scenario 11 — Capacity forecast / CR sizing

Advisory forecast used to size CR quantity over a horizon. (PRR §28 Forecast formula.)

```
Forecast_Quantity = ceil( Forecast_Peak × (1 + Growth_Buffer) + DR_Buffer )

Forecast_Peak   = predicted peak associated-VM demand in the horizon   [Derived]
Growth_Buffer   = policy % for forecast uncertainty                    [Assumed]
DR_Buffer       = extra units required by approved recovery policy      [Assumed]
Forecast_Horizon∈ { 30, 60, 90 } days                                  [Assumed]
```

Forecast recommendations remain advisory until model accuracy and false-positive rates are measured.

---

## Scenario 12 — Auto-increase trigger (steady-state capacity lifecycle)

When utilisation crosses a threshold, an increase request is raised. (design_change_summary G-9;
PRR §30.)

```
Trigger auto-increase when utilisation ≥ threshold:
    dr_autoincrease_threshold           = 0.35
    prod_autoincrease_threshold         = 0.20
    nonprod_autoincrease_threshold      = 0.20

Debounce cooldown = 30 min per (region + CRG type) after a trigger
```

Phase 1 requires operator approval; target quantity is computed via the Steady-State Capacity Lifecycle
(re-read state → `CapacityIncreaseRequest` → calculate target → approve → submit quota → confirm). Auto-
decrease is excluded from Phase 1. `[Decided]` / `[Undocumented — architectural judgement]`

---

## Scenario 13 — Emergency transfer & tier escalation (DR event active)

During an active DR event, emergency capacity is obtained by tier. (PRR §32; design_change_summary
G-10..G-13, QG-9.)

```
Tier 1  DirectExpansion      — additive DR expansion using existing headroom. Automated.
Tier 2  QuotaNeutralTransfer — reduce NonProd reservation, expand DR within the SAME quota group.
                               Policy-gated. Quota-neutral (see below).
Tier 3  DestructiveTransfer  — changes VM associations. Operator dual-approval + elevated RBAC.
                               NOT automated in Phase 1.
```

### Quota-neutral math for Tier 2/3 `[Derived — POC-31/32]`

```
Because NonProd CR and DR CR draw from the SAME NonProd+DR quota group:
    NonProd CR reduction  → releases q × vCPU back to the GROUP pool
    DR CR expansion       → consumes q × vCPU from the SAME GROUP pool
    Net group headroom change ≈ 0   → no Azure quota-increase request needed
    Tier RTO gated only by ARM operation time (minutes), not quota approval (hours)

max_emergency_transfer_qty = potential_dr_demand × emergency_transfer_pct   # 0.30
```

Escalation order: `Tier 1 headroom? → else Tier 2 approved? → else Tier 3 allowed? → else manual`.

---

## Scenario 14 — Scaling & API-budget model

Used to size the estate and stay within Azure Resource Manager throttling budgets. (PRR §10.)

```
CRG_lower_bound = 3 × R                                              # 3 CRGs (Prod/NonProd/DR) per region
CRG_total       = R × Eclass × Z × SKUset × IsolationFactor         # Eclass = 3 environment classes

Requests_per_cycle       = CRG_reads + CR_reads + sharing_reads + quota_reads + association_reads
Average_requests_per_second = Requests_per_cycle / 300               # 5-minute (300 s) cycle
```

Where `R` = managed regions; `Z`, `SKUset`, `IsolationFactor` are measured estate multipliers. These are
illustrative sizing calculations, **not** platform commitments. `[Derived]`

### Documented ARM throttle baselines `[Documented]` (PRR §7, FC-16)

```
Compute RP read  limit = 250   requests / 5 min / subscription
Compute RP write limit = 1,200 requests / hour  / subscription
```

The adaptive throttle manager is **initialised** with these baselines (not hardcoded constants) and adapts
to observed 429/`Retry-After` responses.

### Reconciliation cadence `[Assumed]` / `[Derived]`

```
Reconciliation loop target       = 5 min for ≤ 500 managed CRGs
Critical targeted reconcile P95  < 2 min
Stable-resource state age  P95   < 15 min
Drift detection                  ≤ 2 reconciliation cycles
```

---

## Scenario 15 — DR ratio parameters (governs Scenarios 6, 9, 13)

```
dr_ratio_min    = 0.30      # HC-6 lower bound
dr_ratio_max    = 0.40      # used in DR_Floor_vCPU — engine always sizes to the ceiling
dr_ratio_target = [0.30, 0.40]
emergency_transfer_pct = 0.30
prod_growth_buffer     = 0.20
nonprod_growth_buffer  = 0.20
```

**Decision D7:** the DR floor always uses `dr_ratio_max` (not the current operating ratio) to prevent
undersizing if the ratio is later raised. `[Decided]`

---

## Consolidated policy-constant table

| Constant | Value | Used in scenario(s) |
|---|---|---|
| `alpha / beta / gamma / delta / epsilon` | 0.30 / 0.20 / 0.25 / 0.15 / 0.10 | 1, 5, 6 |
| `dr_ratio_min` | 0.30 | 7, 15 |
| `dr_ratio_max` | 0.40 | 9, 15 |
| `dr_ratio_target` | [0.30, 0.40] | 6, 15 |
| `prod_growth_buffer` | 0.20 | 8 |
| `nonprod_growth_buffer` | 0.20 | 8 |
| `emergency_transfer_pct` | 0.30 | 8, 13 |
| `min_prod_quota_headroom_vcpu` | 20 | 7 |
| `min_nonprod_quota_headroom_vcpu` | 20 | 7 |
| `min_dr_headroom_vcpu` | 16 | 7 |
| `dr_autoincrease_threshold` | 0.35 | 12 |
| `prod/nonprod_autoincrease_threshold` | 0.20 | 12 |
| debounce cooldown | 30 min | 12 |
| reconciliation loop target | 5 min (≤500 CRGs) | 14 |
| ARM read / write baseline | 250 per 5 min / 1,200 per hour | 14 |
| `Forecast_Horizon` | 30 / 60 / 90 days | 11 |

---

## Evidence & maturity note

Several placement formulas (`PS_Prod`, restructured `PS_NonProd`/`PS_DR`, HC-6, per-CRG-type snapshot
fields) are **`[Decided]` but were flagged in the PRR as not-yet-empirically-validated** — they are
suitable for **shadow / recommendation mode**, not autonomous placement, until normalized, versioned,
replay-tested, and compared against capacity-weighted alternatives (PRR §4 "Scoring formulas", §14
Scorecard: Placement engine = 5/10). The quota-neutral Tier 2/3 math depends on POC-31/POC-32 execution.
All constants above are policy defaults (`PlacementPolicy`, config-as-code, versioned) and are tunable.
