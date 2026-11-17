# ACRME CRV & DPB Technical Documentation

**Customer Region Vector and Domain Placement Binding — Calculation Reference**

| | |
|---|---|
| **Document version** | 1.0 |
| **Date** | 17 November 2026 |
| **Audience** | Azure Principal Architect / Platform Engineering / Capacity & Placement Team |
| **Requirements baseline** | Requirements Baseline v4.0.2 (17 Nov 2026) |
| **Deployment config** | environment_v2.yaml (deployment standard as of 2026-11-17) |
| **Calculation reference** | Calculation Logic Reference v2.4 |

> **Note on mock data.** Mock data sets in this document are explicitly labelled and illustrative of formula behaviour. They are not production inventory. Buffer, bootstrap, and growth values are configurable policy inputs — never fixed normative percentages unless an approved baseline default is cited as such.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Glossary of Key Terms](#2-glossary-of-key-terms)
3. [Pipeline Overview — Why Two Scopes?](#3-pipeline-overview--why-two-scopes)
4. [Geography & Distribution Models](#4-geography--distribution-models)
5. [CRV Calculation — Customer Region Vector](#5-crv-calculation--customer-region-vector)
6. [DPB Calculation — Domain Placement Binding](#6-dpb-calculation--domain-placement-binding)
7. [DR Sizing — Max-Not-Sum (F.6–F.8)](#7-dr-sizing--max-not-sum-f6f8)
8. [Quota Group Model (F.4–F.5)](#8-quota-group-model-f4f5)
9. [Zone Distribution (F.9)](#9-zone-distribution-f9)
10. [End-to-End Pipeline Example](#10-end-to-end-pipeline-example)
11. [Distribution Model Variations](#11-distribution-model-variations)
12. [Capacity Reservation Policy Reference](#12-capacity-reservation-policy-reference)
13. [Requirement Traceability Matrix](#13-requirement-traceability-matrix)
14. [Source References](#14-source-references)

---

## 1. Executive Summary

ACRME uses a **two-scope placement model** to separate customer-level region decisions from domain-level capacity provisioning:

| Scope | Mechanism | Decided by | Operates on |
|-------|-----------|------------|-------------|
| **Customer** | Customer Region Vector (CRV) | Placement Engine — CRV scope | Customer × Geography |
| **Domain** | Domain Placement Binding (DPB) | Placement Engine — DPB scope | Domain Group × Environment × Region |

**CRV** resolves which Azure regions a customer uses for Prod, CVAL, and DR — once per customer per geography. Every domain group of that customer shares the same CRV.

**DPB** resolves the capacity envelope for each domain group — subscription, CRG set, reservation sizing, zone targets, and quota draw — deterministically, with no region scoring at domain scope.

The two-phase gate (**PLC-015**) enforces strict ordering: CRV is always resolved before any DPB. A domain group never re-runs region selection.

**Ownership boundary:** DPB outputs the capacity envelope. It does **not** determine Instance Group — that is a service-deployment decision made by the Service Owner / Product Automation downstream of the placement engine.

---

## 2. Glossary of Key Terms

| Term | Definition |
|------|------------|
| **Customer Region Vector (CRV)** | Customer-scoped, cached region binding `(geography, distribution_model, prod, cval, dr)` decided once per customer × geography and reused by all domain groups (PLC-013). |
| **Domain Placement Binding (DPB)** | Deterministic per-domain capacity binding `DPB(D,E)` that resolves subscription, CRG set, CR sizing, zone distribution, and quota draw for one domain × environment × region, using the pre-bound CRV region (PLC-014). Outputs the capacity envelope; does **not** determine Instance Group. |
| **Domain Group** | A workload-domain grouping of a customer's capacity (`wl-*` token, e.g. TMS, WMS) sharing one customer seed row but owning separate capacity envelopes per environment/region (DOM-001). |
| **Seed Record** | Authoritative customer record holding: customer/realm identifier, geography, distribution model, production region, CVAL region, DR region (or `NOT_OFFERED`), CRV vector, domain groups and their DPB references, products covered, decision timestamp, policy/engine version, capacity-snapshot reference, exception reference, and approval metadata (PLC-003). |
| **Capacity Reservation Group (CRG)** | Azure construct holding reservations for one region. The engine organises CRGs per domain × environment × region (CAP-025). |
| **Instance Group (IG)** | Deployment-time grouping that materialises a service within a domain × environment × region. IG is **not** determined by the placement engine — it is an output of service deployment (Service Owner / Product Automation). |
| **Quota Group** | Azure Quota Group that moves unused quota onto a member subscription. All of a customer's domain subscriptions belong to a centrally managed quota group per region × VM-family cell (QUA-015). |
| **DR Foundation CRG set** | Dedicated DR-bootstrap CRG set in the domain's DR compute subscription — structural base capacity, always present with pre-staged quota; extendable on failover via the domain's CVAL/DR shared CRG (CAP-025, DR-021). |

---

## 3. Pipeline Overview — Why Two Scopes?

The engine flow is:

```
AEP intent → S1 resolve/reuse CRV → S2 resolve DPB → S3 readiness (RDY-001/CAP-016) → S4 associate/deploy (INT-005)
```

### 3.1 Why CRV is customer-scoped

> "Their production is their production for all domain groups in that geography." — PLC-004

Region selection is bound **once per customer × geography**. All domain groups (TMS, WMS, etc.) deploy in the same regions. This prevents:

- Domain groups landing in different regions for the same environment
- Redundant scoring that would waste capacity-snapshot cycles
- Inconsistent DR topology across a customer's workloads

### 3.2 Why DPB is domain-scoped

Each domain group owns **separate** subscriptions, CRG sets, reservations, zone targets, and quota draws. TMS and WMS have different capacity needs even though they share the same CRV regions. DPB resolves the capacity envelope independently per domain so that:

- Each domain sizes its reservations to its own workload (F.1)
- Domains scale, fail over, or rebalance independently (DOM-003)
- Sharing is domain-bounded — a CVAL/DR shared CRG never crosses domain boundaries (DOM-004)

### 3.3 Ownership boundary

| Concept | Role | Decided by |
|---------|------|------------|
| Region placement (CRV) | **Input** to service deployment | Placement Engine |
| Capacity envelope (DPB) | **Input** to service deployment | Placement Engine |
| Instance Group | **Output** of service deployment | Service Owner / Product Automation |
| Service → IG association | Registration after deployment | Service Owner → Gravity |

---

## 4. Geography & Distribution Models

### Mock Data Set 1 — Geography Configuration

Source: `environment_v2.yaml`

| Geography | Alias | Distribution Model | Standard Regions | Restricted Regions |
|-----------|-------|-------------------|-----------------|--------------------|
| United States | US | `three_region` | West US 3, Central US, Canada Central | East US 2 |
| Europe | EU | `two_region` | Switzerland North, Sweden Central | North Europe, West Europe |
| Australia | AU | `two_region` | Australia East, Australia Southeast² | — |
| Asia Pacific | APAC | `two_region` | East Asia, Southeast Asia | — |
| Middle East | ME | `cross_geography_dr` | Saudi Arabia Central¹, UAE North | — |

> ¹ **Data-quality note — "Saudi Arabia Central":** `environment_v2.yaml` lists the region as *Saudi Arabia Central*. No Azure region by that name exists; the actual Azure region in the Eastern Province is **Saudi Arabia East** (scheduled GA November 2026, 3 AZs). The name in the config file should be treated as a placeholder pending alignment with the Azure region catalogue.
>
> ² **Data-quality note — Australia Southeast:** `environment_v2.yaml` lists Australia Southeast as a Standard `auto_selectable: true` region. However, Australia Southeast has **0 availability zones** in the Azure region catalogue. This means HC-5 / CAP-011 (`az_count ≥ 1`) would fail, making it ineligible for zonal CRG placement and ε zone-density scoring. The config entry may need review.

**Field explanations:**

- **Geography** — business grouping of Azure regions.
- **Distribution Model** — determines how many regions are used and how environments map to them.
- **Standard** — `auto_selectable: true`; engine may score and select these regions.
- **Restricted** — `auto_selectable: false`; never engine-derived; require exception approval (EC-1..EC-4).

### Three distribution models

| Model | Geographies | Region mapping | CVAL/DR selection |
|-------|-------------|---------------|-------------------|
| `three_region` | US only | R_p, R_c, R_d are all different regions | CVAL and DR scored independently; optional separation (PLC-010) |
| `two_region` | EU, AU, APAC | Only two Standard regions | CVAL and DR co-locate deterministically in the single remaining non-Prod region (PLC-010a). No argmax needed. |
| `cross_geography_dr` | ME | Prod + CVAL co-locate in a weighted-selected ME region (separate CRGs); DR placed cross-geo in a weighted-selected Europe Standard region | CVAL co-locates with Prod (not with DR). CVAL-sacrifice bootstrap (DR-005/006) does not apply; ME DR uses dedicated reserved capacity in Europe (PLC-010b, DR-020). |

---

## 5. CRV Calculation — Customer Region Vector

### 5.1 Two input paths

CRV resolution follows one of two paths (PLC-013):

| Path | ID | Trigger | Engine determines | Usage |
|------|-----|---------|-------------------|-------|
| **Exact-Region** | PLC-001 | Customer supplies exact production region | CVAL and DR only | **Default** |
| **Geography** | PLC-002 | Customer supplies geography only | All three (Prod, CVAL, DR) | **Exception** — requires approval |

Both paths apply the same weighted capacity placement model (PLC-007/008) and the same Hard Constraints (HC-1..HC-10), then converge on DPB (PLC-014) via the PLC-015 gate.

### 5.2 Scoring weights (PlacementPolicy)

#### Mock Data Set 2 — Scoring Weights

| Weight | Symbol | Value | Signal |
|--------|--------|-------|--------|
| Capacity / headroom | α (alpha) | 0.30 | NonProd CRG effective free capacity relative to reserved quantity |
| Quota headroom | β (beta) | 0.20 | Quota headroom relative to quota limit |
| Distribution fairness | γ (gamma) | 0.25 | Customer distribution fairness across regions in the geography |
| DR readiness | δ (delta) | 0.15 | DR coverage ratio health |
| Zone diversity | ε (epsilon) | 0.10 | Availability zone count relative to 3 |

**Rules:**

- All five weights **must sum to exactly 1.0** (invariant enforced at policy load time; tolerance ±0.001 for IEEE 754 rounding only).
- Each factor is **clamped to [0, 1]** before weighting, so the final score is always in [0, 1].
- Weights are configurable per `PlacementPolicy` version and are stored as config-as-code.
- Status: `[Assumed]` — not empirically validated.

### 5.3 Scoring formulas

#### PS_Prod(r) — Geography Path selection; Exact-Region Path audit

```
PS_Prod(r) =
    0.30 × Clamp(nonprod_crg.effective_free / prod_crg.quantity)     ← α: NonProd headroom signal
  + 0.20 × Clamp(prod_crg.quota_headroom  / prod_crg.quota_limit)    ← β: Prod quota headroom
  + 0.25 × Clamp(1 - prod_customer_count  / total_customers(g))      ← γ: distribution fairness
  + 0.15 × Clamp(dr_crg.coverage_ratio)                              ← δ: DR readiness signal
  + 0.10 × Clamp(az_count / 3)                                       ← ε: zone diversity
```

`PS_Prod` is dual-purpose: derives the Prod region in the Geography Path (Scenario 1) and is reused for post-selection validation/audit in the Exact-Region Path (Scenario 2). Every candidate score and the policy version are written to the `OperationRecord` for deterministic replay.

#### PS_NonProd(r) — determines CVAL region

```
PS_NonProd(r) =
    0.30 × Clamp(nonprod_crg.effective_free / nonprod_crg.quantity)      ← α: effective NonProd headroom
  + 0.20 × Clamp(nonprod_crg.quota_headroom / nonprod_crg.quota_limit)   ← β: NonProd quota headroom
  + 0.25 × Clamp(1 - nonprod_customer_count / total_customers(g))        ← γ: distribution fairness
  + 0.15 × Clamp(nonprod_crg.effective_free / nonprod_crg.quantity)      ← δ: overflow capacity health
  + 0.10 × Clamp(az_count / 3)                                           ← ε: zone diversity
```

> **Known design gap:** α and δ use the same signal (`nonprod_crg.effective_free / nonprod_crg.quantity`), giving NonProd headroom an effective weight of 0.45. A corrected pilot variant exists (PRR-recommended: 0.35 Capacity + 0.25 Quota + 0.25 Distribution + 0.05 DR_Overflow + 0.10 Zones) but is not empirically validated. The design-of-record formula above is the approved baseline.

#### PS_DR(r) — determines DR region

```
PS_DR(r) =
    0.30 × Clamp(dr_crg.free_slots / dr_crg.quantity)                   ← α: DR CRG headroom
  + 0.20 × Clamp(dr_crg.quota_headroom / dr_crg.quota_limit)            ← β: DR quota headroom
  + 0.25 × Clamp(1 - dr_customer_count / total_customers(g))            ← γ: distribution fairness
  + 0.15 × min(1.0, dr_crg.coverage_ratio / dr_coverage_target)         ← δ: coverage-ratio health
  + 0.10 × Clamp(az_count / 3)                                          ← ε: zone diversity
```

> Note on δ in PS_DR: `dr_coverage_target` is a configurable scoring-normalisation reference (per customer/product), not a fixed DR percentage. `dr_crg.coverage_ratio` uses the max-not-sum denominator `Destination_DR_Requirement(region) = MAX(source portions)` (F.6/DR-017).

### 5.4 γ (Gamma) fairness — detailed explanation

F.10 / PLC-012 define the geography customer count and the γ fairness term:

```
Total_Customers(g)   = COUNT DISTINCT customers c
                       where c has ≥ 1 environment (Prod, CVAL or DR)
                       provisioned or being deployed in any region r ∈ g

γ(r,env) = 1                                                    if Total_Customers(g) = 0
         = Clamp(1 − Env_Customers(r,env) / Total_Customers(g),
                 0, 1)                                           otherwise
```

The denominator is **one live count per geography**, shared by PS_Prod, PS_NonProd and PS_DR. The numerator is the **environment-specific** customer count for the region being scored.

#### Mock Data Set 3 — γ Fairness Calculation

| Field | Value | Meaning |
|-------|-------|---------|
| Geography | US | Geography being scored |
| total_customers(US) | 50 | Distinct customers with any environment in any US region |
| Region under score | West US 3 | Candidate for Prod placement |
| prod_customer_count (WUS3) | 12 | Distinct customers with Prod in West US 3 |
| **γ(WUS3, Prod)** | **Clamp(1 − 12/50) = 0.76** | Higher γ steers new customers toward less-loaded regions |
| Zero rule | If total_customers(g) = 0 → γ = 1 | Perfectly fair — no existing customers to distribute around |

### 5.5 Worked example — Exact-Region Path (US, three-region)

Customer **Contoso** supplies Prod = **West US 3** (Exact-Region Path, default). Engine validates WUS3 against HC-1..HC-10 (PASS), then scores CVAL and DR candidates among the remaining Standard regions: **Central US** and **Canada Central**.

#### Mock Data Set 4 — Regional Capacity Snapshot for CRV Scoring

| Field | Central US | Canada Central | Meaning |
|-------|-----------|---------------|----------|
| nonprod_crg.effective_free | 40 VMs | 55 VMs | Unreserved VM slots in the NonProd CRG set |
| nonprod_crg.quantity | 100 VMs | 100 VMs | Total reserved quantity in the NonProd CRG |
| nonprod_crg.quota_headroom | 320 vCPU | 400 vCPU | Remaining NonProd vCPU quota (assigned − used) |
| nonprod_crg.quota_limit | 500 vCPU | 500 vCPU | Total NonProd vCPU quota assigned in this region |
| nonprod_customer_count | 18 | 10 | Distinct customers with CVAL in this region |
| total_customers(US) | 50 | 50 | Shared γ denominator for the US geography |
| dr_crg.free_slots | 30 VMs | 45 VMs | Available DR standby slots |
| dr_crg.quantity | 80 VMs | 80 VMs | Total DR reserved quantity |
| dr_crg.quota_headroom | 200 vCPU | 300 vCPU | DR quota remaining |
| dr_crg.quota_limit | 400 vCPU | 400 vCPU | DR quota limit |
| dr_customer_count | 15 | 8 | Distinct customers with DR in this region |
| dr_crg.coverage_ratio | 0.75 | 0.90 | dr_crg.quantity / Destination_DR_Requirement (max-not-sum) |
| dr_coverage_target | 1.0 | 1.0 | Configurable normalisation reference for δ |
| az_count | 3 | 3 | Availability zones in the region |

#### CVAL scoring (PS_NonProd)

**Central US:**

```
α = 0.30 × Clamp(40/100)       = 0.30 × 0.40 = 0.120
β = 0.20 × Clamp(320/500)      = 0.20 × 0.64 = 0.128
γ = 0.25 × Clamp(1 − 18/50)    = 0.25 × 0.64 = 0.160
δ = 0.15 × Clamp(40/100)       = 0.15 × 0.40 = 0.060
ε = 0.10 × Clamp(3/3)          = 0.10 × 1.00 = 0.100
────────────────────────────────────────────────────────
PS_NonProd(CUS) = 0.568
```

**Canada Central:**

```
α = 0.30 × Clamp(55/100)       = 0.30 × 0.55 = 0.165
β = 0.20 × Clamp(400/500)      = 0.20 × 0.80 = 0.160
γ = 0.25 × Clamp(1 − 10/50)    = 0.25 × 0.80 = 0.200
δ = 0.15 × Clamp(55/100)       = 0.15 × 0.55 = 0.0825
ε = 0.10 × Clamp(3/3)          = 0.10 × 1.00 = 0.100
────────────────────────────────────────────────────────
PS_NonProd(CAC) = 0.7075
```

**Result:** R_c = **Canada Central** (higher score).

*Why:* Canada Central wins because it has more NonProd capacity (55 vs 40 VMs), better quota headroom (80% vs 64%), and fewer existing CVAL customers (10 vs 18 → better γ fairness of 0.80 vs 0.64).

#### DR scoring (PS_DR) and three-region separation

**Central US:**

```
α = 0.30 × Clamp(30/80)        = 0.30 × 0.375  = 0.1125
β = 0.20 × Clamp(200/400)      = 0.20 × 0.50   = 0.100
γ = 0.25 × Clamp(1 − 15/50)    = 0.25 × 0.70   = 0.175
δ = 0.15 × min(1.0, 0.75/1.0)  = 0.15 × 0.75   = 0.1125
ε = 0.10 × Clamp(3/3)          = 0.10 × 1.00   = 0.100
────────────────────────────────────────────────────────
PS_DR(CUS) = 0.600
```

**Canada Central:**

```
α = 0.30 × Clamp(45/80)        = 0.30 × 0.5625 = 0.1688
β = 0.20 × Clamp(300/400)      = 0.20 × 0.75   = 0.150
γ = 0.25 × Clamp(1 − 8/50)     = 0.25 × 0.84   = 0.210
δ = 0.15 × min(1.0, 0.90/1.0)  = 0.15 × 0.90   = 0.135
ε = 0.10 × Clamp(3/3)          = 0.10 × 1.00   = 0.100
────────────────────────────────────────────────────────
PS_DR(CAC) = 0.7638
```

In the US three-region model, CVAL and DR may occupy separate remaining regions (PLC-010 optional separation). For this worked example the engine assigns DR to the **remaining** Standard region after CVAL is placed — **Central US** — enforcing separation so that Contoso's environments span three distinct regions.

> If policy elects CVAL/DR co-location instead, DR could also land on Canada Central; the `CVALEarmarkRecord` then prevents double-counting earmarked CVAL capacity as both live CVAL headroom and available DR headroom.

#### CRV output

```
CRV(Contoso, US) = (US, three_region, West US 3, Canada Central, Central US)
```

| Field | Value |
|-------|-------|
| geography | US |
| distribution_model | three_region |
| prod (R_p) | West US 3 |
| cval (R_c) | Canada Central |
| dr (R_d) | Central US |
| input_mode | SPECIFIC_REGION (Exact-Region Path) |

### 5.6 Seed record output

The first approved placement writes the authoritative Customer Seed Record (PLC-003, Scenario 20). Subsequent domain groups and environments for the same customer × geography read this record — the engine is not re-invoked for region selection (PLC-004).

```
CustomerSeedRecord {
    customer_realm_id       = "contoso-realm-001"
    geography               = "US"
    production_region       = "West US 3"
    cval_region             = "Canada Central"
    dr_region               = "Central US"
    products_covered        = ["ProductA", "ProductB"]
    decision_timestamp      = "2026-11-17T10:30:00Z"
    policy_version          = "v2.4.1"
    capacity_snapshot_ref   = "snap-20261117-103000"
    exception_ref           = null
    input_mode              = "SPECIFIC_REGION"
    // CRV vector and DPB references are stored on / linked from this record (PLC-013/014)
}
```

| Field | Meaning |
|-------|---------|
| customer_realm_id | Authoritative customer / realm identifier |
| geography | Business geography of the binding (US, EU, AU, APAC, ME) |
| production_region / cval_region / dr_region | Exact Azure region names (or `NOT_OFFERED` for DR) |
| products_covered | All products seeded by this record |
| decision_timestamp | When the placement decision was committed |
| policy_version | PlacementPolicy version used for scoring |
| capacity_snapshot_ref | Snapshot ID that drove the decision |
| exception_ref | Approval ID if Restricted region or geography-exception path; null otherwise |
| input_mode | `SPECIFIC_REGION` (Exact-Region Path) or `GEOGRAPHY_EXCEPTION` |

---

## 6. DPB Calculation — Domain Placement Binding

### 6.1 What DPB does

After the CRV is resolved, each domain group resolves its own **capacity envelope** per (domain × environment × CRV region). The DPB is deterministic — no region weighting at domain scope; the region always comes from the CRV (PLC-015 gate).

**DPB inputs (all fixed before DPB starts):**

| Input | Source | Scope |
|-------|--------|-------|
| Customer (C) | Commercial onboarding | — |
| Domain Group (D) | DOM-001 taxonomy (`wl-tms`, `wl-wms`, …) | Customer's domain portfolio |
| Environment (E) | `{Prod, CVAL, DR}` | Per deployment |
| Region (R) | CRV(C,G).E — **locked, not re-scored** | Customer × Geography |
| Policy version | PlacementPolicy config (versioned, deterministic) | Platform-wide |

DPB iterates once per **(D, E)** pair. For a two-domain customer (TMS + WMS) with three environments, that is **six** DPB executions, all using the same CRV regions.

**DPB outputs five items:**

1. **Subscription** — the domain subscription for (D, E, R)
2. **CRG set** — Prod-dedicated, CVAL/DR shared, or DR Foundation
3. **CR sizing** — reservation target, headroom, deficit per SKU × zone
4. **Zone targets** — per-domain zone distribution and skew
5. **Quota draw** — quota from the central quota group per region × family cell

### 6.2 The five DPB steps

Using CRV(Contoso, US) = `(US, three_region, West US 3, Canada Central, Central US)`.

#### Mock Data Set 5 — Domain Configuration (TMS Prod, West US 3)

| Field | Value | Explanation |
|-------|-------|-------------|
| Domain Group | TMS | Transport Management System domain |
| Environment | Prod | Production environment |
| Region | West US 3 | From CRV — Prod region |
| Allocated VMs | 24 | Currently running/allocated VMs in this domain/env/region |
| Buffer Target | 6 VMs | Configurable headroom (not a fixed %) |
| Reserved Quantity | 28 VMs | Current reservation quantity in the CRG |
| Zone Count | 3 | West US 3 has 3 availability zones |

#### Step ① — Subscription resolution

```
Sub(TMS, Prod) = Resolve(Contoso, TMS, Prod, WUS3)
               = "sub-jda-cld-cr-prod-wl-tms-wus3-01"
```

**Selection criteria:**

| # | Criterion | Requirement | Detail |
|---|-----------|-------------|--------|
| 1 | One subscription per Domain × Environment | DOM-002 | TMS-Prod and WMS-Prod are never in the same subscription |
| 2 | Deterministic naming | OPS-006, C-12 | `sub-<org>-<product>-<purpose>-<env>-<domain>-<region>-<shard>` |
| 3 | Shard registry lookup | ADR-007 §10, DOM-003 | If primary subscription is at capacity, shard registry returns next shard (`-02`, `-03`) |
| 4 | Management group membership | QUA-015 | Subscription must be enrolled so the central quota group can govern it |
| 5 | Already exists vs. create | CAP-002, REG-001 | Reuse if exists; create under naming convention and enrol in quota group if not |

#### Step ② — CRG set binding

```
CRG_set(TMS, Prod) = Prod-dedicated CRG set per CAP-025
                     e.g. crg-pr-wus3-zonal, crg-pr-wus3-az1, crg-pr-wus3-az2, crg-pr-wus3-az3
```

**Selection criteria:**

| # | Criterion | Requirement | Detail |
|---|-----------|-------------|--------|
| 1 | Environment determines set type | CAP-025, ENV-003 | E = Prod → **Prod CRG set** (dedicated, never shared) |
| | | | E = CVAL → **CVAL/DR shared CRG set** (`crg-cvdr-*`) |
| | | | E = DR → **DR Foundation CRG set** (`crg-drf-*`) + access to `crg-cvdr` on DR declaration |
| 2 | Domain-bounded isolation | DOM-004 | CRG set belongs to exactly one domain. No cross-domain sharing. |
| 3 | Zone structure | CAP-023 | One zonal CRG (default) + one per-AZ CRG per zone + optional `reg` CRG for non-zonal SKUs |
| 4 | Naming convention | OPS-006, C-12 | `crg-<env_token>-<region>-<zone_token>`. Domain token in subscription name, not CRG name. |
| 5 | Already exists vs. create | CAP-002, CAP-022 | Bind if exists; create full set with seed-at-0 reservations per eligible SKU/AZ matrix if not |
| 6 | Foundation domain (wl-fnd) | DR-021 | Foundation Services domain gets both Foundation CVAL and Foundation DR CRG sets |

#### Step ③ — CR sizing (F.1–F.3)

```
Target Reserved Capacity(TMS, Prod) = Allocated VM Count + Buffer Target
                                    = 24 + 6 = 30 VMs                     ← F.1

Reservation Headroom(TMS, Prod)     = Reserved Quantity − Allocated VM Count
                                    = 28 − 24 = 4 VMs                     ← F.2

Reservation Deficit(TMS, Prod)      = max(0, Target − Reserved)
                                    = max(0, 30 − 28) = 2 VMs             ← F.3
```

**Interpretation:** The TMS Prod reservation is **2 VMs short** of its target. Reconciliation (CAP-005) will raise the reservation from 28 to 30. The 4 VMs of headroom are reserved capacity above allocated demand, but insufficient to cover the full buffer target.

**DR sizing (when E = DR):** Uses F.6 max-not-sum instead of simple `allocated + buffer`. See [Section 7](#7-dr-sizing--max-not-sum-f6f8).

#### Step ④ — Zone targets (F.9)

#### Mock Data Set 6 — Zone Distribution for TMS Prod (West US 3)

| Zone | Current VMs | Target (round(24/3) = 8) | Skew |
|------|------------|--------------------------|------|
| az1 | 10 | 8 | +2 (over-represented) |
| az2 | 8 | 8 | 0 (balanced) |
| az3 | 6 | 8 | −2 (under-represented) |

```
zone_target_share  = 1/3 = 0.333
max_drift          = |10/24 − 0.333| = |0.417 − 0.333| = 0.084
zone_balance_tolerance = 0.10 (C-13)
0.084 < 0.10 → rebalance_needed = false (within tolerance)

Next VM placement → az3 (argmax zone_deficit = az3 at +0.083)
```

**Combined-load observation (alert only):**

```
RegionZoneLoad(WUS3, Prod, z) = Σ_D VMs(D, Prod, WUS3, z)
```

This is computed across all domains (TMS + WMS) in the region. It is **observability only** (OBS-001/002, C-15) — it never triggers reservation sizing or rebalancing actions across domains.

#### Step ⑤ — Quota draw (F.4–F.5)

#### Mock Data Set 7 — Quota State for TMS Prod (West US 3, Dsv3 family)

| Field | Value | Explanation |
|-------|-------|-------------|
| VM Family | Dsv3 | VM family (e.g. D4s_v3 = 4 vCPU each) |
| Assigned VM-Family Quota | 160 vCPU | Regional quota assigned to this subscription for Dsv3 |
| Current VM-Family Usage | 96 vCPU | Currently consumed (24 VMs × 4 vCPU) |
| **Available Quota (F.4)** | **64 vCPU** | 160 − 96 = 64 vCPU remaining |
| Requested Deployment | 8 vCPU | Deploying 2 more VMs (2 × 4 vCPU) |
| **Quota Deficit (F.5)** | **0 vCPU** | max(0, 8 − 64) = 0 — sufficient quota |
| Central Quota Group | QG-Contoso-WUS3-Dsv3 | QUA-015: customer's central group for this region × family |
| GROUP_REPLENISH_THRESHOLD | 85% | Proactive replenishment trigger at the group cell level |
| SUB_REPLENISH_THRESHOLD | 85% | Proactive replenishment trigger at the subscription level |
| Current Group Utilization | 60% (96/160) | Below 85% — no replenishment triggered |

**Quota enforcement boundary:** At deploy time, Azure enforces quota against the **subscription**, not the group (QUA-007, QUA-003). The group is a transfer mechanism; the subscription is the enforcement boundary.

### 6.3 DPB for a second domain (WMS) — same regions, different envelope

#### Mock Data Set 8 — WMS Prod DPB Comparison

| DPB Output | TMS Prod (WUS3) | WMS Prod (WUS3) |
|------------|----------------|------------------|
| Subscription | sub-...-wl-tms-wus3-01 | sub-...-wl-wms-wus3-01 |
| CRG Set | Prod-dedicated (TMS) | Prod-dedicated (WMS) |
| Allocated VMs | 24 | 16 |
| Buffer Target | 6 | 4 |
| Target Reserved | 30 | 20 |
| Reserved Quantity | 28 | 22 |
| Deficit | 2 (under-provisioned) | 0 (over-provisioned by 2) |

**Key point:** TMS and WMS share the same CRV regions but have completely different capacity envelopes. This is why DPB is domain-scoped.

---

## 7. DR Sizing — Max-Not-Sum (F.6–F.8)

### 7.1 Why max-not-sum?

Under the **single-region-failure assumption** (DR-001), only one production region fails at a time. The destination only needs capacity for its **largest** protected source, not the sum of all.

```
Destination_DR_Requirement(d)
  = MAX over each non-concurrent source region s protected by d (
        Workload_Portion(s → d)
    )
```

### 7.2 Worked example

#### Mock Data Set 9 — DR Max-Not-Sum Sizing

*(From Requirements Appendix D / Calculation Logic Reference Scenario 17)*

Region 2 (Central US) holds DR standby for customers from two source regions:

| Source protected by R2 | Failover portion in R2 |
|----------------------|------------------------|
| Region 1 (West US 3) — Cust1 + Cust5 | 120 cores |
| Region 3 (Canada Central) — Cust6 | 80 cores |

```
Old (SUM) sizing:  Requirement(R2) = 120 + 80 = 200 cores   ← over-provisions; superseded
New (MAX) sizing:  Requirement(R2) = max(120, 80) = 120 cores

Saving at R2: 200 → 120 = 80 cores (40%) removed with no loss of protection.

Overcommit_Ratio(R2) = 200 / 120 ≈ 1.67
→ R2's shared standby is 1.67× oversubscribed.
→ Platform-wide extrapolation: ~40–50% standby reduction.
```

**Why this is safe:** If Region 1 fails, R2 needs 120 cores. If Region 3 fails instead, R2 needs only 80 cores. They never fail simultaneously (DR-001), so R2 reserves for the worst case (120), not both.

### 7.3 Supporting formulas

```
DR_Capacity_Gap(d)  = max(0, Destination_DR_Requirement(d) − Usable_Destination_Capacity(d))  ← F.7

Overcommit_Ratio(d) = SUM(Workload_Portion(s → d) for all s)
                    / MAX(Workload_Portion(s → d))                                           ← F.8
```

**Conservative SUM override (C-11):** Available per-scope in `PlacementPolicy` where a customer/contract explicitly requires concurrent-failure protection. No code change required.

---

## 8. Quota Group Model (F.4–F.5)

### 8.1 Single-pool model (primary — QUA-004)

#### Mock Data Set 10 — Quota Pool Sizing

| Component | Value | Derivation |
|-----------|-------|------------|
| Prod CRG quantity | 32 VMs | Current Prod reserved |
| vCPU per VM | 4 | D4s_v3 |
| Prod vCPU | 128 | 32 × 4 |
| prod_growth_buffer | 0.20 | Policy constant |
| Prod contribution | 153.6 vCPU | 128 × 1.20 |
| NonProd CRG quantity | 20 VMs | Current NonProd reserved |
| NonProd vCPU | 80 | 20 × 4 |
| nonprod_growth_buffer | 0.20 | Policy constant |
| NonProd contribution | 96 vCPU | 80 × 1.20 |
| DR_Earmark_vCPU | 120 vCPU | Destination_DR_Requirement × vCPU (from F.6) |
| emergency_transfer_pct | 0.30 | Policy constant |
| emergency_transfer_headroom | 36 vCPU | 120 × 0.30 |
| **Pool_Limit** | **405.6 vCPU** | Sum of all components |

```
Pool_Limit = Prod_contribution + NonProd_contribution + DR_Earmark_vCPU + emergency_transfer_headroom
           = 153.6 + 96 + 120 + 36 = 405.6 vCPU
```

**Prod protection inside the shared pool** (logical earmarks):

```
Prod_Reserved_Floor  = Prod_Used_vCPU + Prod_Growth_Buffer_vCPU
Allocatable_NonProd  = Pool_Limit − Prod_Reserved_Floor − DR_Earmark_vCPU − NonProd_Used_vCPU
Pool_Headroom        = Pool_Limit − Pool_Used
```

`Prod_Reserved_Floor` and `DR_Earmark_vCPU` are never allocatable to NonProd.

### 8.2 Exception two-group model

Used only when Azure Quota Group limits or mandatory Prod-isolation governance make one pool impossible.

```
Prod_Group_Limit     = Prod_CRG_quantity × vCPU × (1 + prod_growth_buffer)
                     = 128 × 1.20 = 153.6 vCPU

NonProdDR_Group_Limit = NonProd_CRG_quantity × vCPU × (1 + nonprod_growth_buffer)
                      + DR_CRG_quantity × vCPU
                      + emergency_transfer_headroom
                      = 96 + 120 + 36 = 252 vCPU
```

**Worked topology example** (from Calculation Logic Reference):

| Component | Value |
|-----------|-------|
| Prod group | 128 vCPU (32 × D4s_v3, 4 vCPU each) |
| NonProdDR group | 80 vCPU |
| DR floor | 32 vCPU (= Destination_DR_Requirement for this region) |
| **Effective NonProd ceiling** | **48 vCPU** (80 − 32) |

---

## 9. Zone Distribution (F.9)

### Worked example

#### Mock Data Set 11 — Zone Distribution (from Calculation Logic Reference Scenario 21)

3-zone region, 30 VMs, current distribution:

| Zone | VM Count | Zone Share | Zone Deficit (target − share) |
|------|----------|------------|-------------------------------|
| az1 | 14 | 0.467 | −0.133 (over-target) |
| az2 | 9 | 0.300 | +0.033 (slightly under-target) |
| az3 | 7 | 0.233 | +0.100 (most under-target) |

```
zone_target_share       = 1/3 = 0.333
max_drift               = |0.467 − 0.333| = 0.134 (az1)
zone_balance_tolerance  = 0.10 (C-13)
0.134 > 0.10 → rebalance_needed = true

Next placement → az3 (argmax zone_deficit = +0.100)
Balanced target: each zone holds 10 VMs (0.333 share, max_drift = 0)
```

Rebalancing never violates capacity, quota, restriction, or zone-alignment constraints and never forces a live migration outside an approved workflow.

---

## 10. End-to-End Pipeline Example

### Mock Data Set 12 — Complete Pipeline (Customer "Contoso", US Geography)

**Step 1 — AEP Intent:**

Contoso requests deployment in US geography, supplies Prod = West US 3, domain groups TMS and WMS.

**Step 2 — CRV Resolution (S1):**

1. Check seed record: none exists (first deployment).
2. Validate West US 3 against hard constraints HC-1..HC-10: **PASS**.
3. Score CVAL candidates (Central US, Canada Central) with PS_NonProd.
   - Canada Central: 0.7075 | Central US: 0.568 → R_c = **Canada Central**.
4. In 3-region model, DR goes to remaining region → R_d = **Central US**.
5. CRV(Contoso, US) = `(US, three_region, West US 3, Canada Central, Central US)`
6. Write seed record.

**Step 3 — DPB Resolution (S2):**

For each (domain × environment × region):

| Domain | Env | Region | Subscription | CRG Set Type | Sizing |
|--------|-----|--------|-------------|-------------|--------|
| TMS | Prod | WUS3 | sub-...-prod-wl-tms-wus3-01 | Prod-dedicated | allocated + buffer (F.1) |
| TMS | CVAL | CAC | sub-...-cval-wl-tms-cac-01 | CVAL/DR shared | allocated + buffer (F.1) |
| TMS | DR | CUS | sub-...-dr-wl-tms-cus-01 | DR Foundation + shared CVAL/DR | max-not-sum (F.6) |
| WMS | Prod | WUS3 | sub-...-prod-wl-wms-wus3-01 | Prod-dedicated | allocated + buffer (F.1) |
| WMS | CVAL | CAC | sub-...-cval-wl-wms-cac-01 | CVAL/DR shared | allocated + buffer (F.1) |
| WMS | DR | CUS | sub-...-dr-wl-wms-cus-01 | DR Foundation + shared CVAL/DR | max-not-sum (F.6) |

> Note: TMS and WMS share the same CRV regions but have completely separate subscriptions, CRG sets, reservations, and quota draws. Sharing is domain-bounded (DOM-004).

**Step 4 — Readiness (S3):**

RDY-001 checks all nine gates per deployment:

1. `target_region ∈ approved_region_catalogue (REG-001)`
2. `az_count ≥ 1 in target_region (CAP-011)`
3. `sku ∈ supported_skus(target_region)`
4. Reservation policy known for (subscription, region, zone, SKU)
5. Reservation exists (if required by policy)
6. `reserved_quantity ≥ requested_count OR approved_over_allocation active`
7. `consumer_subscription_quota ≥ requested_units (QUA-013)`
8. `snapshot_age ≤ max_snapshot_age_seconds (RDY-004)`
9. No blocking policy exception or hard constraint violation

All gates pass → `READY`.

**Step 5 — Associate/Deploy (S4):**

VMs are associated with CRGs and deployed (INT-005). Service Owner / Product Automation determines the Instance Group using the DPB capacity envelope as context, deploys the service, and registers the Service → IG association in Gravity.

---

## 11. Distribution Model Variations

### 11.1 Two-region (EU example)

Customer supplies Prod = **Switzerland North** (Exact-Region Path). Only one other Standard region exists (Sweden Central). Per PLC-010a, CVAL selection is deterministic — the remaining in-geo Standard region — and DR must co-locate there with CVAL. No argmax is required.

```
CRV = (EU, two_region, Switzerland North, Sweden Central, Sweden Central)
```

Restricted regions (North Europe, West Europe) never enter scoring. Co-located CVAL and DR still use separate CRG sets (ENV-003). CVAL capacity earmarked for DR activation is tracked by `CVALEarmarkRecord` to prevent double-counting.

### 11.2 Cross-geography DR (ME example)

Middle East uses the `cross_geography_dr` model (DEC-001 resolved, DR-020, PLC-010b).

```
1. Prod/CVAL candidates in-geo = { Saudi Arabia Central*, UAE North }
2. Score both with PS_Prod; Prod = argmax(PS_Prod) → e.g. Saudi Arabia Central*
3. CVAL = co-located with Prod in Saudi Arabia Central* (separate CRG)
4. DR   = weighted selection over Europe Standard regions → e.g. Switzerland North

CRV = (ME, cross_geography_dr, Saudi Arabia Central, Saudi Arabia Central, Switzerland North)
```

> ¹ See data-quality note in Section 4: "Saudi Arabia Central" is a placeholder — the actual Azure region name is **Saudi Arabia East**.

**Key differences:**

- CVAL co-locates with Prod (not with DR).
- CVAL-sacrifice DR bootstrap (DR-005/006) does **not** apply to ME customers.
- ME DR uses **dedicated reserved capacity** in Europe (`capacity: dedicated_reserved`, `source_region_cval_capacity_shared: false`).
- A `SourceDestinationDRIndex` entry and `DR_Earmark_vCPU` are created at the Europe destination, sizing DR max-not-sum (DR-017).

---

## 12. Capacity Reservation Policy Reference

Summary of `capacity_reservation_policies.standard` from `environment_v2.yaml`.

| Topic | Rule |
|-------|------|
| Sharing enabled | Yes — for CVAL and DR only |
| Sharing scope | Domain group and region; cross-subscription allowed |
| Cross-domain sharing | Not permitted |
| Cross-region sharing | Not permitted |
| Production capacity shared | Never |
| Accounting | Count shared capacity once |
| Activation | Approved DR declaration and CVAL capacity release |
| Feature maturity | Preview; `production_dependency_allowed: false` |
| Fallback | Reservation in the deploying subscription until sharing is GA |
| Validation gates | POC-001, POC-003, POC-012, DEP-001 |
| DR Foundation subscription | Dedicated DR compute subscription |
| DR Foundation capacity | Dedicated reserved bootstrap; always present; pre-staged quota |
| DR Foundation depends on sharing | No |
| Cross-geography DR capacity | Dedicated reserved in destination region (not shared from source CVAL) |

> **No invented approved values.** Buffer targets, DR Foundation bootstrap sizing, and growth buffers are configurable policy inputs (C-2, C-16, ENV-005, POC-007). This document never elevates illustrative constants (e.g. 0.20 growth buffers, 0.30 emergency_transfer_pct, 85% replenishment thresholds) into fixed normative policy. Where a baseline default is cited (e.g. `GROUP_REPLENISH_THRESHOLD` 85% in QUA-015), it is labelled as a configurable reference value.

---

## 13. Requirement Traceability Matrix

Each formula maps to one or more requirement IDs in baseline v4.0.2.

| Formula | Description | Requirement IDs |
|---------|-------------|----------------|
| F.1 | Reservation target = Allocated + Buffer | CAP-003, C-2 |
| F.2 | Reservation headroom = Reserved − Allocated | CAP-003 |
| F.3 | Reservation deficit = max(0, Target − Reserved) | CAP-003, CAP-005 |
| F.4 | Available subscription quota | QUA-002, QUA-015, DOM-002 |
| F.5 | Deployment quota deficit | QUA-007, RDY-001 |
| F.6 | DR destination requirement (max-not-sum) | DR-017, DR-001, C-11 |
| F.7 | DR capacity gap | DR-017, DR-006, DR-021 |
| F.8 | Shared-DR overcommit ratio | DR-017, FIN-008, OBS-001 |
| F.9 | Zone distribution target & skew | PLC-011, PLC-016, C-13 |
| F.10 | γ fairness / total_customers(g) | PLC-012 |
| F.11 | CRV two-scope formula sets | PLC-013, PLC-001, PLC-002, PLC-010/010a/010b |
| F.12 | DPB five-step capacity envelope | PLC-014, CAP-025, DOM-002, QUA-015 |
| F.13 | Formula lineage / audit | DAT-001 |
| PLC-015 | Two-phase gate: CRV before DPB | PLC-015, INT-008 |
| DR-021 | DR Foundation dedicated bootstrap | DR-021, ENV-005, CAP-025, QUA-015 |
| DOM-004 | Domain-bounded sharing | DOM-004, CAP-013, ENV-003 |

---

## 14. Source References

| Source | Version / Date | Role in this document |
|--------|---------------|----------------------|
| ACRME Requirements Baseline | v4.0.2 — 17 Nov 2026 | Normative requirements, glossary, F.1–F.13, PLC/DOM/CAP/QUA/DR IDs |
| environment_v2.yaml | Deployment standard as of 2026-11-17 | Geography catalogue, distribution models, capacity reservation policies, environment profiles |
| Calculation Logic Reference | v2.4 | PS_Prod / PS_NonProd / PS_DR formulas, weights, Scenarios 8/9/17/20/21 worked examples |
| Capacity Partition Model diagram | Page 8 | Domain-group CRG set structure (prod / cvdr / drf) |
| Ownership function table | Session artefact | Function / owner / point-in-flow demarcation for IG vs placement |

---

*Hard Constraints HC-1..HC-11 are unchanged across v3.0 → v4.0.2 and are preconditions to scoring and acceptance. This document does not restate them in full; any region that fails an HC gate is ineligible before PS_\* is evaluated.*

*Document control: Technical Documentation v1.0 for ACRME CRV & DPB, dated 17 November 2026.*
