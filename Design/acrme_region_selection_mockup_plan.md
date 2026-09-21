# ACRME Region Selection — Interactive Mockup: Design Plan

**Status:** Draft — Awaiting Approval  
**Date:** 2026-09-21  
**Author:** ACRME Design Session  
**Sources:** `acrme_calculation_logic_comprehensive_walkthrough.md`, `acrme_requirements_baseline_v2_4.md`, `acrme_plain_english_walkthrough.md`

---

## Executive Summary

This plan defines an **interactive functional prototype** of the ACRME Region Selection engine. It is not a design wireframe — it is a working simulation backed by mock data that faithfully reproduces:

- The Hard Constraint Gate (HC-1..HC-10 subset, arithmetic-critical ones)
- All three placement scoring formulas (PS_Prod, PS_NonProd, PS_DR)
- The sequential Prod → CVAL → DR selection logic
- The geography distribution models (3-region US, 2-region co-located EU/AU/APAC, Middle East cross-geo DR)
- The DR max-not-sum sizing model (A.6, DR-017)

The tool's primary purpose is to **validate and communicate the algorithm** — enabling the team to test edge cases, tune weights, and demonstrate the selection logic without needing a live Azure environment.

---

## 1. Requirements

### 1.1 Functional Requirements

| ID | Requirement |
|---|---|
| FR-01 | User selects a geography and a customer SKU + VM count |
| FR-02 | User can optionally supply an exact Prod region (default path) or leave it to engine selection (exception path) |
| FR-03 | Tool runs HC-3, HC-6, HC-7 gates on every candidate region — displays pass/fail per constraint per region |
| FR-04 | Tool scores all HC-passing candidates with PS_Prod, PS_NonProd, PS_DR — shows each component value (α, β, γ, δ, ε) and weighted contribution |
| FR-05 | Tool selects CVAL and DR regions via argmax after Prod is fixed |
| FR-06 | Tool shows final placement as a `CustomerSeedRecord` (Prod / CVAL / DR) |
| FR-07 | Tool displays readiness state: `READY`, `QUOTA_DEFICIT`, `CAPACITY_UNAVAILABLE`, `POLICY_BLOCKED` |
| FR-08 | User can edit scoring weights (α, β, γ, δ, ε) in a policy panel; tool enforces sum = 1.0 (±0.001) and re-scores live |
| FR-09 | Tool highlights which factor most influenced the winning region ("α headroom drove this choice") |
| FR-10 | Mock data is editable (region snapshot values) — changes re-trigger the full scoring run |
| FR-11 | Tool supports all five geographies: US (3-region), EU, AU, APAC, ME (with cross-geo DR) |
| FR-12 | Tool surface the `total_customers` design gap with a selectable denominator mode |

### 1.2 Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-01 | All formulas implemented exactly as specified in baseline — no approximations |
| NFR-02 | Components clamped to [0, 1] before weighting |
| NFR-03 | Displayed arithmetic should be reproducible from the visible input values — no hidden state |
| NFR-04 | The tool is a simulation only — no calls to Azure APIs |
| NFR-05 | Weights editable via UI panel — config-driven as the baseline specifies |

---

## 2. Mock Data Model

### 2.1 Geography Registry

The five in-scope geographies (REG-001, PLC-010a, PLC-010b):

| Geography | Distribution Model | Standard Regions | DR Exception |
|---|---|---|---|
| US | 3-region | West US 3 · Central US · Canada Central | None |
| EU | 2-region co-located | Switzerland North · Sweden Central | None |
| Australia | 2-region co-located | Australia East · Australia Southeast | None |
| Asia Pacific | 2-region co-located | East Asia · Southeast Asia | None |
| Middle East | 2-region cross-geo DR | UAE North · Saudi Arabia Central | DR → EU (weighted) |

### 2.2 Regional Snapshot Schema

Each region carries the following snapshot fields (the engine's runtime inputs — all editable in the mockup):

```typescript
interface RegionSnapshot {
  region_id: string;                     // e.g. "westus3"
  region_name: string;                   // e.g. "West US 3"
  geography: Geography;
  az_count: number;                      // 2 or 3 (ε component)

  // Prod CRG
  prod_crg: {
    quantity: number;                    // total reserved vCPU (α denominator for PS_Prod)
    allocated: number;                   // vCPU in use by running VMs
    free_slots: number;                  // quantity - allocated
    quota_limit: number;                 // subscription vCPU cap (β denominator)
    quota_headroom: number;              // quota_limit - current_usage (β numerator)
  };

  // NonProd CRG
  nonprod_crg: {
    quantity: number;
    allocated: number;
    effective_free: number;              // free after DR overflow reserve is deducted
    quota_used: number;
    quota_limit: number;
    quota_headroom: number;
  };

  // DR CRG (max-not-sum sized)
  dr_crg: {
    quantity: number;                    // max-not-sum of source workloads' vCPU
    free_slots: number;                  // usable standby capacity
    coverage_ratio: number;             // δ component (clamped [0,1])
    bootstrap_qty: number;              // HC-6 floor: min dr_crg.free + nonprod_eff_free
    dr_coverage_target: number;         // scoring-only normalization (not a sizing ratio)
  };

  // Customer distribution
  prod_customer_count: number;          // γ numerator
  // total_customers is geography-scoped (see Section 2.5)

  // Minimum floors (HC-3 absolute minimums)
  min_prod_headroom_vcpu: number;       // default 20
  min_nonprod_headroom_vcpu: number;    // default 20
  min_dr_headroom_vcpu: number;         // default 16
}
```

### 2.3 Mock Region Data — US Geography

Pre-loaded starter values (derived from the comprehensive walkthrough document):

| Field | West US 3 | Central US | Canada Central |
|---|---|---|---|
| `az_count` | 3 | 3 | 2 |
| `prod_crg.quantity` | 200 | 200 | 200 |
| `prod_crg.allocated` | 120 | 160 | 80 |
| `prod_crg.free_slots` | 80 | 40 | 120 |
| `prod_crg.quota_limit` | 1000 | 1000 | 1000 |
| `prod_crg.quota_headroom` | 700 | 550 | 300 |
| `nonprod_crg.quantity` | 120 | 100 | 80 |
| `nonprod_crg.allocated` | 80 | 100 | 60 |
| `nonprod_crg.effective_free` | 130 | 80 | 40 |
| `nonprod_crg.quota_headroom` | 240 | 160 | 328 |
| `nonprod_crg.quota_used` | 80 | 100 | 60 |
| `dr_crg.quantity` | 120 | 80 | 60 |
| `dr_crg.free_slots` | 100 | 60 | 60 |
| `dr_crg.coverage_ratio` | 0.50 | 0.45 | 0.60 |
| `dr_crg.bootstrap_qty` | 60 | 60 | 40 |
| `dr_crg.dr_coverage_target` | 0.80 | 0.80 | 0.80 |
| `prod_customer_count` | 40 | 25 | 20 |

### 2.4 Mock Region Data — EU Geography

| Field | Switzerland North | Sweden Central |
|---|---|---|
| `az_count` | 3 | 3 |
| `prod_crg.quantity` | 150 | 150 |
| `prod_crg.allocated` | 100 | 80 |
| `prod_crg.quota_limit` | 600 | 600 |
| `prod_crg.quota_headroom` | 400 | 420 |
| `nonprod_crg.effective_free` | 80 | 90 |
| `nonprod_crg.quota_headroom` | 100 | 138 |
| `dr_crg.quantity` | 80 | 80 |
| `dr_crg.free_slots` | 60 | 65 |
| `dr_crg.coverage_ratio` | 0.60 | 0.65 |
| `dr_crg.bootstrap_qty` | 40 | 40 |
| `prod_customer_count` | 6 | 4 |

### 2.5 Mock Region Data — Middle East + EU DR Destination

Middle East regions carry their own snapshot (Prod/CVAL only — DR goes cross-geo):

| Field | UAE North | Saudi Arabia Central |
|---|---|---|
| `az_count` | 3 | 2 |
| `prod_crg.quantity` | 100 | 100 |
| `prod_crg.allocated` | 40 | 30 |
| `prod_crg.quota_headroom` | 200 | 180 |
| `prod_customer_count` | 3 | 2 |

For Middle East DR: the tool runs PS_DR scoring over the **EU Standard regions** (Switzerland North · Sweden Central) as cross-geo DR candidates (PLC-010b, DR-020).

### 2.6 Australia and Asia Pacific — Default Starter Values

Both follow the same 2-region co-location pattern as EU. Pre-loaded with symmetric starter values (quantity=150, quota_limit=500, moderate utilization ~50%, 2–4 customers). These are illustrative and fully editable.

### 2.7 SKU Registry

| SKU | vCPU per VM | Pre-loaded |
|---|---|---|
| E16ads_v5 | 16 | ✅ |
| E8ads_v5 | 8 | ✅ |
| D8s_v5 | 8 | ✅ |
| D16s_v5 | 16 | ✅ |

### 2.8 The `total_customers` Design Gap — UI Treatment

The `total_customers` denominator in the γ component is **undefined in the baseline** (documented open issue in all three source documents). The mockup exposes this ambiguity explicitly and gives the user a chooser:

| Mode | Denominator | Behaviour |
|---|---|---|
| **Live geography total** (default) | Sum of `prod_customer_count` across all Standard regions in the geography | Changes with every new placement; derived from snapshot — no external input |
| **Policy constant** | Configurable integer (e.g. 20 for US, 15 for EU) | Static target; represents maximum intended customers per geography |
| **Manual entry** | User types a value | Useful for reproducing the walkthrough examples exactly |

A yellow annotation in the UI labels γ calculations with a footnote: _"⚠ total_customers is an unresolved design term — see baseline open issue."_

---

## 3. Formulas to Implement

### 3.1 PS_Prod(r) — Production Placement Score

```
α_component = Clamp(nonprod_crg.effective_free / prod_crg.quantity)
β_component = Clamp(prod_crg.quota_headroom / prod_crg.quota_limit)
γ_component = Clamp(1 − prod_customer_count / total_customers)
δ_component = Clamp(dr_crg.coverage_ratio)
ε_component = Clamp(az_count / 3)

PS_Prod(r) = α×α_component + β×β_component + γ×γ_component + δ×δ_component + ε×ε_component
```

### 3.2 PS_NonProd(r) — CVAL/NonProd Placement Score

```
α_component = Clamp(nonprod_crg.effective_free / nonprod_crg.quantity)
β_component = Clamp(nonprod_crg.quota_headroom / nonprod_crg.quota_limit)  [reuse NonProd quota pool]
γ_component = Clamp(1 − prod_customer_count / total_customers)             [same γ — known design gap]
δ_component = Clamp(nonprod_crg.effective_free / nonprod_crg.quantity)     [duplicate of α — known design gap]
ε_component = Clamp(az_count / 3)

PS_NonProd(r) = α×α_component + β×β_component + γ×γ_component + δ×δ_component + ε×ε_component
```

> **Design gap (surfaced in UI):** For PS_NonProd, the δ component duplicates α (both use nonprod_crg.effective_free / quantity). The plain-english walkthrough flags this as "duplicate of α in design-of-record." The mockup displays a note alongside the δ row.

### 3.3 PS_DR(r) — DR Placement Score

```
α_component = Clamp(dr_crg.free_slots / dr_crg.quantity)
β_component = Clamp(dr_crg_quota_headroom / dr_quota_limit)
γ_component = Clamp(1 − prod_customer_count / total_customers)
δ_component = Clamp(dr_crg.coverage_ratio / dr_crg.dr_coverage_target)
ε_component = Clamp(az_count / 3)

PS_DR(r) = α×α_component + β×β_component + γ×γ_component + δ×δ_component + ε×ε_component
```

### 3.4 Clamp Function

```
Clamp(x) = max(0, min(1, x))
```

All components are clamped before weighting. The mockup shows the raw ratio AND the clamped value when they differ.

### 3.5 Hard Constraint Gate

The tool checks these three arithmetic HCs before scoring. Regions that fail any are excluded:

**HC-3 (Quota Floor):**

```
For Prod:    prod_crg.quota_headroom ≥ (vm_count × vcpu_per_vm)
             AND prod_crg.quota_headroom − requested_vcpu ≥ min_prod_headroom_vcpu

For NonProd: nonprod_crg.effective_free ≥ (vm_count × vcpu_per_vm)
             AND nonprod_crg.quota_headroom − requested_vcpu ≥ min_nonprod_headroom_vcpu

For DR:      dr_crg.free_slots ≥ dr_bootstrap_qty (DR-007)
```

**HC-6 (DR Coverage Floor):**

```
dr_crg.free_slots + nonprod_crg.effective_free ≥ dr_crg.bootstrap_qty
```

**HC-7 (DR Floor Integrity — NonProd gate):**

```
nonprod_crg.quota_used + requested_vcpu ≤ nonprod_quota_ceiling − dr_crg.bootstrap_qty
```

> HC-1, HC-2, HC-4, HC-5, HC-8, HC-9, HC-10, HC-11 are non-arithmetic (governance, policy, restricted-region checks). They are represented in the mockup as **toggle switches** on each region ("Restricted region?", "Exception approval on file?", "CRG sealed?") — defaulting to values that represent the happy path.

### 3.6 DR Requirement: Max-Not-Sum (A.6, DR-017)

For any DR destination region, the DR capacity requirement is:

```
Destination_DR_Requirement(dr_region) = MAX over all source regions routing to dr_region of:
    (source_region_customer_count × vcpu_per_deployment)
```

This value is shown in the DR sizing panel alongside the `dr_crg.quantity` and the gap/surplus.

### 3.7 Weight Invariant Validation

```
if |α + β + γ + δ + ε − 1.0| > 0.001:
    → PolicyValidationError: "Weights must sum to 1.0 ± 0.001"
    → Scoring is blocked until corrected
```

---

## 4. UI Design

### 4.1 Screen Flow

```
┌─────────────────────────────────────────┐
│  SCREEN 1: Customer & Workload Setup    │  ← Geography picker, SKU picker,
│                                         │    VM count, Prod region (optional)
└──────────────────────┬──────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────┐
│  SCREEN 2: Hard Constraint Gate         │  ← HC-3, HC-6, HC-7 pass/fail table
│                                         │    Per region, per environment type
└──────────────────────┬──────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────┐
│  SCREEN 3: Scoring — Prod               │  ← Component breakdown for each
│                                         │    passing region; winner highlighted
└──────────────────────┬──────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────┐
│  SCREEN 4: Scoring — CVAL               │  ← Remaining regions after Prod fixed
└──────────────────────┬──────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────┐
│  SCREEN 5: Scoring — DR                 │  ← Remaining regions; co-location
│                                         │    or cross-geo logic applied
└──────────────────────┬──────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────┐
│  SCREEN 6: CustomerSeedRecord + Status  │  ← Final Prod/CVAL/DR triple;
│                                         │    readiness state; DR sizing panel
└─────────────────────────────────────────┘
```

There is also a persistent **Policy Panel** (collapsible sidebar) available from any screen that exposes scoring weights (with live validation), `total_customers` mode, and the auto-increase threshold reference values.

### 4.2 Screen 1 — Customer & Workload Setup

**Inputs:**
- Geography (dropdown): US · EU · Australia · Asia Pacific · Middle East
- SKU (dropdown): E16ads_v5 · E8ads_v5 · D8s_v5 · D16s_v5
- VM count (stepper, default 3): vCPU = vm_count × vcpu_per_vm is computed and shown inline
- Prod region (optional text/dropdown):
  - If supplied → default path (validate only, audit-score only)
  - If blank → exception path (governance toggle must be enabled)
- Customer ID (free text, for seed record display)

**Output:** Workload summary card shown at top of all subsequent screens.

### 4.3 Screen 2 — Hard Constraint Gate

A table with one row per candidate region and columns for each HC check:

| Region | HC-3 Prod | HC-6 DR Floor | HC-7 DR Integrity | Restricted? | Exception? | **ELIGIBLE?** |
|---|---|---|---|---|---|---|
| West US 3 | ✅ 700≥48 | ✅ 160≥60 | ✅ pass | ❌ No | — | **✅ ELIGIBLE** |
| Central US | ✅ 550≥48 | ✅ 140≥60 | ✅ pass | ❌ No | — | **✅ ELIGIBLE** |
| Canada Central | ❌ 300<48* | — (skipped) | — (skipped) | ❌ No | — | **❌ EXCLUDED** |

_*HC-3 fails → remaining HCs are skipped (short-circuit evaluation)._

Clicking any cell opens a drawer showing the full arithmetic:

```
HC-3 Prod: Canada Central
  Requested:         48 vCPU (3 × E16ads_v5)
  Quota headroom:   300 vCPU
  Min floor:         20 vCPU
  Check:            300 ≥ 48 → PASS
  Post-allocation:  300 - 48 = 252 ≥ 20 → PASS
```

> (This example uses the baseline walkthrough data, where Canada Central actually passes HC-3. The mock data above is set up to show a mix of passes and failures.)

For each excluded region, the UI shows the readiness state that would be returned: `QUOTA_DEFICIT`, `CAPACITY_UNAVAILABLE`, etc.

### 4.4 Screen 3 — Prod Scoring Table

For all HC-passing regions, the scoring table shows components side by side:

| | West US 3 | Central US |
|---|---|---|
| **α** (headroom) | 130/200 → **0.65** × 0.30 = **0.195** | 80/200 → **0.40** × 0.30 = **0.120** |
| **β** (quota) | 700/1000 → **0.70** × 0.20 = **0.140** | 550/1000 → **0.55** × 0.20 = **0.110** |
| **γ** (fairness) | 1−40/100 → **0.60** × 0.25 = **0.150** | 1−25/100 → **0.75** × 0.25 = **0.188** |
| **δ** (DR ready) | **0.50** × 0.15 = **0.075** | **0.45** × 0.15 = **0.068** |
| **ε** (zones) | 3/3 → **1.00** × 0.10 = **0.100** | 3/3 → **1.00** × 0.10 = **0.100** |
| **PS_Prod** | **0.660** ← **WINNER** | **0.586** |

A bar chart shows all five weighted contributions stacked for each region.

A "Margin of victory" line shows the score gap and which component most influenced the outcome.

If the user supplied a Prod region (default path), that region is shown in gold with the label "Customer-supplied — validated only" and the score is computed for audit.

### 4.5 Screen 4 & 5 — CVAL and DR Scoring

Same layout as Screen 3, but:
- CVAL scoring excludes the Prod winner from the candidate pool
- DR scoring applies PLC-010a co-location logic (2-region geographies: DR must land in the same region as CVAL) or PLC-010b cross-geo (Middle East: DR candidate pool = EU Standard regions)
- DR scoring uses PS_DR formula, showing the δ component as `coverage_ratio / dr_coverage_target`

For a 2-region geography (EU/AU/APAC) where CVAL is deterministic (only one region left), the scoring table is replaced by a notice: _"CVAL: deterministic — Sweden Central is the only remaining Standard region."_

### 4.6 Screen 6 — CustomerSeedRecord + Readiness

```
╔══════════════════════════════════════════════════╗
║  CustomerSeedRecord                              ║
║  Customer: CUST-0042                             ║
║  Geography: US                                   ║
╠══════════════════════════════════════════════════╣
║  🟢 Prod:  West US 3       (48 vCPU, score 0.66) ║
║  🟢 CVAL:  Canada Central  (48 vCPU, score 0.69) ║
║  🟢 DR:    Central US      (48 vCPU, score 0.60) ║
╠══════════════════════════════════════════════════╣
║  Readiness State:  READY                         ║
║  Policy Version:   v2.4.0-alpha                  ║
╚══════════════════════════════════════════════════╝
```

**DR Sizing Panel** (below the seed record):
```
DR Capacity Sizing (max-not-sum, A.6):
  Source: Central US → DR: West US 3
    Customers in Central US: 25 × 48 vCPU = 1200 vCPU at risk
  Source: Canada Central → DR: West US 3
    Customers in Canada Central: 20 × 48 vCPU = 960 vCPU at risk

  DR_Requirement(West US 3) = MAX(1200, 960) = 1200 vCPU
  DR CRG quantity:             120 vCPU (starter — scaled for illustration)
  Gap: 1200 − 120 = 1080 vCPU ⚠ (auto-increase would trigger)
  Overcommit ratio: (1200 + 960) / 1200 = 1.80
```

> Note: the DR sizing numbers above use illustrative scale. The mockup will calculate from the actual mock data — showing the formula and its inputs.

---

## 5. Demo Scenarios

The tool pre-loads five scenarios accessible via a "Scenarios" button. Each sets the mock data state so the chosen path is immediately visible:

### Scenario A — US Happy Path (3-region, all separate)

- Geography: US, SKU: E16ads_v5 × 3 VMs
- All three US Standard regions pass all HCs
- Result: Prod/CVAL/DR in three separate regions (full separation)
- Shows: scoring margin, the α component driving the winner

### Scenario B — US Quota Deficit (HC-3 fail)

- Central US quota_headroom artificially set to 12 vCPU
- Central US fails HC-3; excluded from Prod scoring pool
- Two-candidate scoring race; readiness state = `QUOTA_DEFICIT` for that region

### Scenario C — EU 2-Region Co-location (PLC-010a)

- Geography: EU, SKU: E8ads_v5 × 3 VMs
- Shows: Prod scoring, deterministic CVAL, mandatory DR co-location with CVAL
- Highlights co-location risk note (both CVAL and DR lost if Sweden Central fails)

### Scenario D — EU Capacity Unavailable (both regions too small)

- Switzerland North headroom = 30 vCPU, E16ads_v5 needs 48 vCPU → HC-3 fail
- Sweden Central takes Prod; but CVAL check on Switzerland North also fails
- Readiness: `CAPACITY_UNAVAILABLE`

### Scenario E — Middle East Cross-Geo DR (PLC-010b)

- Geography: Middle East, SKU: E8ads_v5 × 3 VMs
- Prod/CVAL co-locate in UAE North or Saudi Arabia Central (weighted selection)
- DR scores EU Standard regions via PS_DR
- Shows: how the cross-geo DR candidate pool differs from the ME pool

### Scenario F — Weight Tuning (Distribution-First)

- Same data as Scenario A (US Happy Path)
- User opens Policy Panel and shifts weights to γ=0.35, α=0.25 (distribution-first Option 1)
- Tool re-scores live; winner may change
- Demonstrates how weight policy changes affect placement

---

## 6. Implementation Approach

### 6.1 Architecture Decision

**Recommended: Next.js functional prototype with JSON mock data**

Rationale:
- Platform-hosted preview available (Abacus.AI infrastructure)
- No Azure API calls needed — all data is in-memory from JSON mock files
- React state management handles live re-scoring when weights or data change
- The engine logic (HC gate + scoring formulas) runs client-side in TypeScript — fast, reproducible
- The mockup can be shared with stakeholders as a URL, not a local file

**Not recommended:**
- Pure HTML/JS single-file: fine for simple demos, but the five-screen flow and live re-scoring need proper state
- Python backend: adds latency for what is pure computation; unnecessary for a prototype

### 6.2 Project Structure

```
/acrme-region-selection-mockup
  /data
    regions.json         ← mock RegionSnapshot for all 5 geographies
    skus.json            ← SKU registry
    scenarios.json       ← pre-loaded scenario configurations
    policy.json          ← default PlacementPolicy (weights, floors, etc.)
  /lib
    engine/
      hardConstraints.ts ← HC-3, HC-6, HC-7 implementations
      scoring.ts         ← PS_Prod, PS_NonProd, PS_DR + Clamp
      selectionLogic.ts  ← Prod→CVAL→DR sequential selection + geography rules
      drSizing.ts        ← max-not-sum DR requirement calculation
      policyValidator.ts ← weight-sum invariant check (±0.001)
    types.ts             ← RegionSnapshot, PlacementPolicy, SeedRecord interfaces
  /components
    WorkloadSetup.tsx    ← Screen 1
    HCGateTable.tsx      ← Screen 2
    ScoringTable.tsx     ← Screens 3, 4, 5
    SeedRecord.tsx       ← Screen 6 + DR sizing panel
    PolicyPanel.tsx      ← Collapsible sidebar: weight editor, total_customers mode
    ComponentBreakdown.tsx ← Stacked bar chart per component
  /app
    page.tsx             ← Main orchestration
```

### 6.3 Data Flow

```
User Input (Screen 1)
    │
    ▼
policyValidator.ts   ─── validates weight sum
    │
    ▼
hardConstraints.ts   ─── filters candidate pool per HC check (returns pass/fail + reason per region)
    │
    ▼
scoring.ts           ─── computes PS_Prod/NonProd/DR for passing candidates
    │
    ▼
selectionLogic.ts    ─── Prod = argmax(PS_Prod); CVAL = argmax(PS_NonProd) over remaining; DR = argmax(PS_DR) over remaining (or co-location rule for 2-region)
    │
    ▼
drSizing.ts          ─── max-not-sum DR_Requirement for the selected DR region
    │
    ▼
CustomerSeedRecord   ─── {production_region, cval_region, dr_region, readiness_state, policy_version}
```

All computation is synchronous and runs on state change — no async calls.

### 6.4 Mock Data Editability

The **Policy Panel** sidebar allows:

1. **Weight editor**: α, β, γ, δ, ε sliders (0.00–1.00, step 0.01) with a live sum display. Weight sum validation runs on every change; error banner shown if out of tolerance.
2. **total_customers mode**: radio buttons (Live Geography Total / Policy Constant / Manual Entry)
3. **Region data editor**: expandable cards for each region with editable snapshot fields. All arithmetic in Screens 2–6 re-runs on field change.
4. **Scenario loader**: dropdown that resets all mock data to a named scenario state.

### 6.5 Design Gaps Surfaced in UI

The following known gaps from the source documents are **annotated inline**, not hidden:

| Gap | Location in UI | Display Treatment |
|---|---|---|
| `total_customers` undefined | γ component row in scoring table | Yellow ⚠ icon with tooltip linking to the open issue description |
| PS_NonProd δ duplicates α | δ row in NonProd scoring table | Blue ℹ icon: "Known design gap — δ mirrors α for NonProd. Baseline v2.4 does not yet resolve this." |
| `dr_bootstrap_qty` is TBD | HC-6 gate row | Field shows default (configurable), annotation: "Baseline value is TBD per workload" |
| `dr_coverage_target` is TBD | δ row in PS_DR table | Same annotation pattern |

---

## 7. Data Dimensions

| Dimension | Count | Rationale |
|---|---|---|
| Geographies | 5 | All in-scope (US, EU, AU, APAC, ME) |
| Total Standard regions | 11 | US(3) + EU(2) + AU(2) + APAC(2) + ME(2) |
| Mock customers per region | 2–40 | Enough to make γ non-trivial |
| SKUs | 4 | E16ads_v5, E8ads_v5, D8s_v5, D16s_v5 |
| Pre-loaded scenarios | 6 | A–F (see Section 5) |
| VM count options | 1–10 (stepper) | vCPU = vm_count × vcpu_per_vm |

This is **sufficient to exercise all formula paths** without overwhelming the UI. If the team wants to extend to more regions or customer volumes later, the JSON data file can be expanded without code changes.

---

## 8. Open Questions (Require Resolution Before or During Build)

| # | Question | Impact | Recommendation |
|---|---|---|---|
| OQ-1 | `total_customers` definition — which interpretation does the team want modelled as the **default** in the mockup? | γ values change materially | Default to "Live Geography Total" (sum of region_customer_counts); expose all modes via the chooser |
| OQ-2 | PS_NonProd δ component — is the duplicate of α intentional or a spec gap to be resolved? | Affects NonProd scoring fidelity | Show duplicate as-is with annotation; flag as design gap for discussion |
| OQ-3 | `dr_bootstrap_qty` concrete values — what should the mock data use? | HC-6 pass/fail depends on this | Use 40–60 vCPU range in mock data (lean, per baseline guidance ~5–20%); make configurable |
| OQ-4 | `dr_coverage_target` concrete values — what normalization target for δ in PS_DR? | δ_component = coverage_ratio / target | Use 0.80 as starter in mock data (editable) |
| OQ-5 | Middle East DR destination set — exact EU Standard regions the engine selects from? | DR scoring candidate pool | Use {Switzerland North, Sweden Central} as the mock EU destination set |
| OQ-6 | Should the mockup include the quota pool arithmetic (Part 2 of walkthroughs) as a separate panel? | Scope increase | Out of scope for v1 — Region Selection only; quota management is a follow-on mockup |

---

## 9. Delivery Plan

### Phase 1 — Region Selection Prototype (this build)

- All 5 geographies loaded with mock data
- HC gate (HC-3, HC-6, HC-7)
- PS_Prod / PS_NonProd / PS_DR scoring
- Prod → CVAL → DR sequential selection
- CustomerSeedRecord + readiness state output
- Policy Panel (weights, total_customers mode)
- 6 pre-loaded demo scenarios
- Design gaps annotated inline

### Phase 2 — Quota Management Panel (follow-on)

- Pool_Limit calculation
- Allocatable_NonProd
- HC-7 pool arithmetic
- `QUOTA_DEFICIT` / `CAPACITY_UNAVAILABLE` simulation

### Phase 3 — Capacity Reconciliation Simulator (follow-on)

- Target vs reserved comparison
- Auto-increase threshold triggers
- Max-not-sum DR requirement calculator (extended)
- Reconciliation loop visualization

---

## 10. Decision Log

| Decision | Alternative Considered | Rationale | Trade-off |
|---|---|---|---|
| Next.js functional prototype (not wireframes) | Figma/design mockup | User requested a "mock selection tool based on mocked up data" — implies interactive computation, not static screens | Slightly more build time; produces a demo that actually runs the formulas |
| All computation client-side | Python/Node API backend | No async latency; mock data fits in memory; no Azure calls needed | Cannot simulate real Azure API delays (acceptable for a prototype) |
| JSON mock data files | Hardcoded constants in components | Makes mock data editable from the UI without code changes | Requires a JSON schema; small overhead |
| 6 pre-loaded scenarios | User-defined scenarios only | Ensures core paths are always demonstrable; reduces setup friction | Scenarios may not cover every edge case the team invents |
| Design gap annotations inline | Silent gaps (pretend they don't exist) | The team needs to see where the spec is incomplete during prototyping — hiding gaps delays resolution | Slightly more complex UI |
| Scope: Region Selection only (Phase 1) | Include Quota + Capacity in one build | Quota and Capacity add substantial complexity; Region Selection can be validated independently first | Follow-on builds required for full ACRME coverage |

---

*End of Plan — Awaiting approval before implementation begins.*
