# ACRME Region Selection — Executive Reference with Granular Calculation Walkthrough

**Baseline:** ACRME Requirements v4.0 (14 Oct 2026)
**Mock Exercise:** `acrme_region_selection_whatif_acrme_regions.xlsx`
**Audience:** Executive leadership, solution architects, product owners
**Purpose:** Explain the complete region-selection and domain-placement pipeline from first principles, with every formula expanded to actual numbers.

---

## 1. What This Document Covers

This document walks through the **entire ACRME region-selection pipeline** — from customer request to final capacity binding — at three levels of detail:

1. **Executive summary** — what the system does and why, in one page
2. **Architecture overview** — the two-scope model (CRV + DPB) and how the pieces fit
3. **Granular calculation walkthrough** — every formula with real numbers, traced to the mock exercise

The calculations use data derived from the mock exercise workbook. All numbers are illustrative planning figures, not live Azure state.

---

## 2. Executive Summary

### The Business Problem

When a new customer is onboarded to the platform, the system must decide:
- **Which Azure region** hosts their production workload
- **Which region** hosts their customer-validation (CVAL/test) environment
- **Which region** hosts their disaster recovery (DR) capacity

These decisions are permanent (changeable only via approved migration), affect cost, performance, and resilience, and must be made consistently across hundreds of customers.

### The Solution: A Two-Phase Automated Engine

**Phase 1 — Customer Region Vector (CRV):** Determines the three regions for a customer. Done once per customer per geography. Shared by all of the customer's domain groups (product lines).

**Phase 2 — Domain Placement Binding (DPB):** For each domain group, binds subscriptions, capacity reservation groups, reservation targets, zone distribution, and quota within the CRV's regions. Deterministic — no region selection occurs here.

### Why Two Phases?

| Concern | CRV (Phase 1) | DPB (Phase 2) |
|---|---|---|
| **Scope** | Customer × geography | Domain × environment × region |
| **Question answered** | Which regions? | How much capacity in those regions? |
| **Frequency** | Once per customer (cached, reused) | Once per domain group deployment |
| **Involves scoring?** | Yes — weighted multi-factor placement | No — deterministic binding |
| **Changes require** | Approved migration workflow | Normal capacity reconciliation |

---

## 3. Architecture: The Complete Pipeline

```
Customer Request
    │
    ├── Geography: US
    ├── Prod Region: West US 3 (exact-region path)
    ├── SKU: E32ads_v5 (32 vCPU)
    ├── VM Count: 20 (= 640 vCPU)
    └── Domains: TMS, WMS
         │
         ▼
┌─────────────────────────────────────────────────┐
│  PHASE 1: CRV Resolution (PLC-013, F.11)        │
│                                                   │
│  1. Validate Prod region against Hard Constraints │
│  2. Filter candidate regions for CVAL and DR      │
│  3. Run HC gate (eliminate ineligible regions)     │
│  4. Score surviving candidates (5-factor model)    │
│  5. Apply distribution model (3-region US)         │
│  6. Output: CRV(C, G) = (US, 3-reg, WUS3, CUS, CAC) │
└─────────────────────────────────────────────────┘
         │
         ▼  CRV cached — reused by ALL domain groups
┌─────────────────────────────────────────────────┐
│  PHASE 2: DPB Resolution (PLC-014, F.12)         │
│  [Runs once per domain group]                     │
│                                                   │
│  For TMS:                                         │
│    1. Resolve ig subscription per (D, E, R)       │
│    2. Verify CRG sets exist (Prod/CVDR/DRF)       │
│    3. Compute reservation target = Alloc + Buffer  │
│    4. Compute zone distribution target             │
│    5. Check quota from central pool                │
│    6. Write DPB record                             │
│                                                   │
│  For WMS: (same steps, different subs/CRGs)       │
└─────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────┐
│  Readiness Gate (RDY-001)                         │
│  All pass? → READY → Deploy                       │
│  Any fail? → state code (QUOTA_DEFICIT, etc.)     │
└─────────────────────────────────────────────────┘
```

---

## 4. Granular Calculation Walkthrough

### 4.1 Scenario Setup

We place **Customer "Contoso"** in the **US geography** using the **exact-region path** (PLC-001). Contoso supplies **West US 3** as the production region.

| Input | Value | Source |
|---|---|---|
| Customer | Contoso | Onboarding request |
| Geography | US | Onboarding request |
| Distribution model | 3-region | REG-003 catalogue lookup |
| Prod region (supplied) | West US 3 | Customer-specified (PLC-001) |
| SKU | E32ads_v5 | Onboarding request |
| vCPU per VM | 32 | Catalogue lookup |
| VM count | 20 | Onboarding request |
| Requested vCPU | 640 | 20 × 32 |
| Domain groups | TMS, WMS | Customer taxonomy |

**Candidate regions for CVAL and DR** (3-region US — Prod takes West US 3, leaving two):

| Region | Geography | Class | AZ Count | Role |
|---|---|---|---|---|
| Central US | US | Standard | 3 | Candidate for CVAL and DR |
| Canada Central | US | Standard | 3 | Candidate for CVAL and DR |
| East US 2 | US | Restricted | 3 | Excluded unless explicitly named |

East US 2 is Restricted → AutoSelect = 0 → eliminated from candidates (unless Contoso explicitly names it).

---

### 4.2 Capacity & Quota Data (Capacity_Usage Sheet)

The mock exercise populates the following data for the three US Standard regions. All values represent the aggregate state across all current customers, not just Contoso.

#### Production Capacity

| Region | Prod Reserved (F) | Prod Alloc (G) | Prod Free (H) | Prod Q-Limit (I) | Prod Q-Used (J) | Prod Q-Headroom (K) |
|---|---|---|---|---|---|---|
| West US 3 | 38,208 | 34,630 | 3,578 | 200,000 | 24,896 | 175,104 |
| Central US | 25,792 | 22,208 | 3,584 | 200,000 | 14,656 | 185,344 |
| Canada Central | 14,400 | 12,256 | 2,144 | 200,000 | 8,256 | 191,744 |

**Reading the table:**
- `Prod Reserved` = total VMs reserved for Prod across all customers in this region
- `Prod Alloc` = VMs actually running (allocated)
- `Prod Free` = Reserved − Alloc = spare capacity available for new customers
- `Prod Q-Headroom` = Q-Limit − Q-Used = remaining quota in vCPUs

#### Non-Production (CVAL) Capacity

| Region | NP Reserved (L) | NP Alloc (M) | NP Eff-Free (N) | NP Q-Limit (O) | NP Q-Used (P) | NP Q-Headroom (Q) |
|---|---|---|---|---|---|---|
| West US 3 | 20,352 | 16,416 | 3,936 | 200,000 | 16,288 | 183,712 |
| Central US | 14,528 | 13,824 | 704 | 200,000 | 9,920 | 190,080 |
| Canada Central | 8,064 | 4,256 | 3,808 | 200,000 | 7,520 | 192,480 |

- `NP Eff-Free` = NP Reserved − NP Alloc = free reservation capacity for new CVAL/NonProd deployments

#### DR Capacity

| Region | DR Reserved (R) | DR Alloc | DR Free (S) | DR Coverage (T) |
|---|---|---|---|---|
| West US 3 | 10,000 | 2,200 | 7,800 | 0.60 |
| Central US | 8,500 | 1,700 | 6,800 | 0.55 |
| Canada Central | 7,200 | 1,100 | 6,100 | 0.70 |

- `DR Free` = DR Reserved − DR Alloc = available DR reservation
- `DR Coverage` = fraction of Prod workload covered by DR capacity (0.0–1.0)

#### Customer Distribution

| Region | Cust Count (U) | Geography Total |
|---|---|---|
| West US 3 | 95 | 226 |
| Central US | 78 | 226 |
| Canada Central | 53 | 226 |

- `Geography Total` = 226 distinct customers across all US regions (the γ fairness denominator, PLC-012)

---

### 4.3 Policy Configuration (Policy Sheet)

| Parameter | Cell | Value | Purpose |
|---|---|---|---|
| α weight (capacity headroom) | B2 | 0.30 | How much capacity headroom matters |
| β weight (quota headroom) | B3 | 0.20 | How much quota headroom matters |
| γ weight (distribution fairness) | B4 | 0.25 | How much customer distribution balance matters |
| δ weight (DR readiness) | B5 | 0.15 | How much DR coverage matters |
| ε weight (zone diversity) | B6 | 0.10 | How much zone count matters |
| **Weight sum** | B7 | **1.00** | Must equal 1.0 (validated) |
| γ zero rule | B11 | 1.0 | γ value when total_customers = 0 |
| DR bootstrap qty | B13 | 40 vCPU | Minimum DR headroom for HC-3 DR and HC-6 |
| DR coverage target | B14 | 0.80 | Target for δ normalisation in DR scoring |
| Min Prod headroom | B15 | 20 vCPU | Quota buffer after deployment for HC-3 Prod |
| Min NonProd headroom | B16 | 20 vCPU | Quota buffer after deployment for HC-3 NonProd |

---

### 4.4 Hard Constraint Gate — Step by Step

The HC gate eliminates regions before they reach the scoring engine. A region must pass ALL required checks for each environment.

#### 4.4.1 HC-3 Prod Quota Check

**Formula:** `Prod Q-Headroom ≥ Requested vCPU AND Prod Q-Headroom − Requested vCPU ≥ Min Prod Headroom`

| Region | Q-Headroom (K) | Requested | K ≥ 640? | K − 640 ≥ 20? | Result |
|---|---|---|---|---|---|
| West US 3 | 175,104 | 640 | ✅ 175,104 ≥ 640 | ✅ 174,464 ≥ 20 | **PASS** |
| Central US | 185,344 | 640 | ✅ | ✅ 184,704 ≥ 20 | **PASS** |
| Canada Central | 191,744 | 640 | ✅ | ✅ 191,104 ≥ 20 | **PASS** |

All three US Standard regions pass the Prod quota check.

#### 4.4.2 HC-3 NonProd Quota Check

**Formula:** `NP Eff-Free ≥ Requested vCPU AND NP Q-Headroom − Requested vCPU ≥ Min NonProd Headroom`

| Region | NP Eff-Free (N) | N ≥ 640? | NP Q-Head (Q) | Q − 640 ≥ 20? | Result |
|---|---|---|---|---|---|
| West US 3 | 3,936 | ✅ | 183,712 | ✅ 183,072 ≥ 20 | **PASS** |
| Central US | 704 | ✅ | 190,080 | ✅ 189,440 ≥ 20 | **PASS** |
| Canada Central | 3,808 | ✅ | 192,480 | ✅ 191,840 ≥ 20 | **PASS** |

**Key point:** Condition 1 checks **reservation** headroom (can the NP CRG accommodate the VMs?). Condition 2 checks **quota** headroom (does the subscription have enough vCPU quota?). Both must pass — they are independent resources.

#### 4.4.3 HC-3 DR Capacity Check

**Formula:** `DR Free ≥ DR Bootstrap Qty`

| Region | DR Free (S) | S ≥ 40? | Result |
|---|---|---|---|
| West US 3 | 7,800 | ✅ | **PASS** |
| Central US | 6,800 | ✅ | **PASS** |
| Canada Central | 6,100 | ✅ | **PASS** |

#### 4.4.4 HC-6 DR Coverage Floor (Combined Pool)

**Formula:** `DR Free + NP Eff-Free ≥ DR Bootstrap Qty`

This check matters most in 2-region co-located geographies where CVAL and DR share a region. In the 3-region US model, it is redundant with HC-3 DR but still evaluated.

| Region | DR Free (S) | NP Eff-Free (N) | S + N | S + N ≥ 40? | Result |
|---|---|---|---|---|---|
| West US 3 | 7,800 | 3,936 | 11,736 | ✅ | **PASS** |
| Central US | 6,800 | 704 | 7,504 | ✅ | **PASS** |
| Canada Central | 6,100 | 3,808 | 9,908 | ✅ | **PASS** |

#### 4.4.5 HC-7 DR Floor Integrity

**Formula:** `NP Q-Used + Requested vCPU ≤ NP Q-Limit − DR Bootstrap Qty`

Rearranged: Does deploying 640 vCPU of NonProd load still leave room for the DR bootstrap floor (40 vCPU) within the NP quota limit?

| Region | NP Q-Used (P) | P + 640 | NP Q-Limit (O) | O − 40 | P + 640 ≤ O − 40? | Result |
|---|---|---|---|---|---|---|
| West US 3 | 16,288 | 16,928 | 200,000 | 199,960 | ✅ | **PASS** |
| Central US | 9,920 | 10,560 | 200,000 | 199,960 | ✅ | **PASS** |
| Canada Central | 7,520 | 8,160 | 200,000 | 199,960 | ✅ | **PASS** |

#### 4.4.6 Eligibility Summary

| Region | Eligible Prod | Eligible NonProd | Eligible DR |
|---|---|---|---|
| | HC-3 Prod | HC-3 NP **AND** HC-7 | HC-3 DR **AND** HC-6 |
| West US 3 | **YES** | **YES** | **YES** |
| Central US | **YES** | **YES** | **YES** |
| Canada Central | **YES** | **YES** | **YES** |
| East US 2 | (not evaluated — Restricted, AutoSelect = 0) | | |

All three Standard US regions pass all gates. In this scenario, no region is eliminated by the hard constraints — the scoring engine receives all three as candidates.

**When would a region fail?** If Central US had NP Eff-Free of only 500 (below the 640 requested), HC-3 NonProd Condition 1 would fail, and Central US would be eliminated for CVAL placement. The engine would then have only Canada Central as a CVAL candidate.

---

### 4.5 Scoring — Production Environment

West US 3 is the customer's supplied Prod region (exact-region path). It is **validated** against the HC gate but **not scored** — it is an input constant. The scoring below is shown for completeness (the mock exercise does score all regions) but in the exact-region path, the Prod score is informational only.

#### 4.5.1 Component Calculations for Each Region

**α — Capacity Headroom**

Formula: `α_raw = NP Eff-Free / Prod Reserved`

*Design rationale:* For Prod scoring, α uses NP headroom relative to Prod footprint as a proxy for overall regional capacity health. A region with lots of unused NP capacity relative to its Prod commitment has room to grow.

| Region | NP Eff-Free (N) | Prod Reserved (F) | α_raw | α_c (clamped 0–1) |
|---|---|---|---|---|
| West US 3 | 3,936 | 38,208 | 3,936/38,208 = **0.1030** | 0.1030 |
| Central US | 704 | 25,792 | 704/25,792 = **0.0273** | 0.0273 |
| Canada Central | 3,808 | 14,400 | 3,808/14,400 = **0.2644** | 0.2644 |

Canada Central has the highest capacity headroom ratio — its NP free capacity is 26.4% of its Prod footprint.

**β — Quota Headroom**

Formula: `β_raw = Prod Q-Headroom / Prod Q-Limit`

| Region | Prod Q-Head (K) | Prod Q-Limit (I) | β_raw | β_c |
|---|---|---|---|---|
| West US 3 | 175,104 | 200,000 | 175,104/200,000 = **0.8755** | 0.8755 |
| Central US | 185,344 | 200,000 | 185,344/200,000 = **0.9267** | 0.9267 |
| Canada Central | 191,744 | 200,000 | 191,744/200,000 = **0.9587** | 0.9587 |

All three have substantial quota headroom (87–96%). Canada Central has the most room.

**γ — Distribution Fairness**

Formula: `γ_raw = 1 − Cust Count / Total Customers(geography)`

Total Customers(US) = 226

| Region | Cust Count (U) | γ_raw | γ_c |
|---|---|---|---|
| West US 3 | 95 | 1 − 95/226 = 1 − 0.4204 = **0.5796** | 0.5796 |
| Central US | 78 | 1 − 78/226 = 1 − 0.3451 = **0.6549** | 0.6549 |
| Canada Central | 53 | 1 − 53/226 = 1 − 0.2345 = **0.7655** | 0.7655 |

Canada Central has the fewest customers → highest fairness score. The γ term rewards under-populated regions to keep customer distribution balanced across the geography.

**δ — DR Readiness**

Formula (Prod scoring): `δ_raw = DR Coverage`

| Region | DR Coverage (T) | δ_raw | δ_c |
|---|---|---|---|
| West US 3 | 0.60 | **0.60** | 0.60 |
| Central US | 0.55 | **0.55** | 0.55 |
| Canada Central | 0.70 | **0.70** | 0.70 |

Canada Central has the highest DR coverage — 70% of its Prod workload is covered by DR reservations.

**ε — Zone Diversity**

Formula: `ε_raw = AZ Count / 3`

| Region | AZ Count | ε_raw | ε_c |
|---|---|---|---|
| West US 3 | 3 | 3/3 = **1.00** | 1.00 |
| Central US | 3 | 3/3 = **1.00** | 1.00 |
| Canada Central | 3 | 3/3 = **1.00** | 1.00 |

All three US Standard regions have 3 AZs → full zone diversity.

#### 4.5.2 Weighted Score Calculation

```
PS_Prod = α·α_c + β·β_c + γ·γ_c + δ·δ_c + ε·ε_c
        = 0.30·α_c + 0.20·β_c + 0.25·γ_c + 0.15·δ_c + 0.10·ε_c
```

**West US 3:**
```
PS = 0.30 × 0.1030 + 0.20 × 0.8755 + 0.25 × 0.5796 + 0.15 × 0.60 + 0.10 × 1.00
   = 0.0309 + 0.1751 + 0.1449 + 0.0900 + 0.1000
   = 0.5409
```

**Central US:**
```
PS = 0.30 × 0.0273 + 0.20 × 0.9267 + 0.25 × 0.6549 + 0.15 × 0.55 + 0.10 × 1.00
   = 0.0082 + 0.1853 + 0.1637 + 0.0825 + 0.1000
   = 0.5397
```

**Canada Central:**
```
PS = 0.30 × 0.2644 + 0.20 × 0.9587 + 0.25 × 0.7655 + 0.15 × 0.70 + 0.10 × 1.00
   = 0.0793 + 0.1917 + 0.1914 + 0.1050 + 0.1000
   = 0.6674
```

#### 4.5.3 Prod Ranking (informational — Prod is input-supplied in this path)

| Rank | Region | PS_Prod | Notes |
|---|---|---|---|
| 1 | Canada Central | **0.6674** | Would be the engine's choice if geography path were used |
| 2 | West US 3 | 0.5409 | Customer's actual supplied region |
| 3 | Central US | 0.5397 | |

In the **exact-region path**, West US 3 is the Prod region regardless of score. The scoring confirms it is viable (passed all HC gates). If the **geography path** (PLC-002) were used, the engine would have selected Canada Central.

---

### 4.6 Scoring — CVAL Environment

For CVAL scoring, West US 3 is excluded (Prod winner → ENV-003 separation). Only Central US and Canada Central are candidates.

#### 4.6.1 CVAL Component Formulas (Differences from Prod)

| Component | Prod Formula | CVAL Formula | Why different |
|---|---|---|---|
| α | NP Eff-Free / **Prod Reserved** | NP Eff-Free / **NP Reserved** | CVAL cares about NP capacity as a fraction of NP footprint, not Prod |
| β | **Prod** Q-Head / **Prod** Q-Limit | **NP** Q-Head / **NP** Q-Limit | CVAL uses NP quota, not Prod quota |
| γ | Same formula | Same formula | Geography-wide fairness applies equally |
| δ | DR Coverage | **NP Eff-Free / NP Reserved** | ⚠️ **Known gap**: identical to α (see §4.6.3) |
| ε | Same formula | Same formula | Zone count is environment-independent |

#### 4.6.2 Component Calculations

**α — NP Capacity Headroom**

Formula: `α_raw = NP Eff-Free / NP Reserved`

| Region | NP Eff-Free (N) | NP Reserved (L) | α_raw | α_c |
|---|---|---|---|---|
| Central US | 704 | 14,528 | 704/14,528 = **0.0485** | 0.0485 |
| Canada Central | 3,808 | 8,064 | 3,808/8,064 = **0.4722** | 0.4722 |

Canada Central has dramatically more NP headroom (47% vs 5%).

**β — NP Quota Headroom**

Formula: `β_raw = NP Q-Headroom / NP Q-Limit`

| Region | NP Q-Head (Q) | NP Q-Limit (O) | β_raw | β_c |
|---|---|---|---|---|
| Central US | 190,080 | 200,000 | 190,080/200,000 = **0.9504** | 0.9504 |
| Canada Central | 192,480 | 200,000 | 192,480/200,000 = **0.9624** | 0.9624 |

Both have excellent NP quota headroom. Near-identical.

**γ — Distribution Fairness** (same as Prod — geography-wide denominator)

| Region | Cust Count | γ_raw | γ_c |
|---|---|---|---|
| Central US | 78 | 1 − 78/226 = **0.6549** | 0.6549 |
| Canada Central | 53 | 1 − 53/226 = **0.7655** | 0.7655 |

**δ — DR Readiness (CVAL version)**

Formula: `δ_raw = NP Eff-Free / NP Reserved` ← **same as α**

| Region | δ_raw | δ_c |
|---|---|---|
| Central US | **0.0485** | 0.0485 |
| Canada Central | **0.4722** | 0.4722 |

⚠️ **This is the known design gap.** δ for CVAL is identical to α. See §4.6.3.

**ε — Zone Diversity**

| Region | ε_raw | ε_c |
|---|---|---|
| Central US | 1.00 | 1.00 |
| Canada Central | 1.00 | 1.00 |

#### 4.6.3 The δ = α Design Gap

In CVAL scoring, δ (DR readiness) uses the formula `NP Eff-Free / NP Reserved` — the exact same formula as α (NP capacity headroom). This means:

- α and δ are **perfectly correlated** (same number in every row)
- The **effective combined weight** of NP capacity headroom is: α_weight + δ_weight = 0.30 + 0.15 = **0.45** (45% of the total score)
- The remaining three factors (β, γ, ε) share only 55% of influence

This is documented in the mock exercise user guide §9 as a known limitation. A future baseline revision may define δ_CVAL as a distinct metric (e.g. DR coverage from the CVAL region's perspective, or the releasable-toward-DR ratio).

#### 4.6.4 Weighted CVAL Score

```
PS_CVAL = 0.30·α_c + 0.20·β_c + 0.25·γ_c + 0.15·δ_c + 0.10·ε_c
```

**Central US:**
```
PS = 0.30 × 0.0485 + 0.20 × 0.9504 + 0.25 × 0.6549 + 0.15 × 0.0485 + 0.10 × 1.00
   = 0.01455 + 0.19008 + 0.16373 + 0.00728 + 0.10000
   = 0.4756
```

**Canada Central:**
```
PS = 0.30 × 0.4722 + 0.20 × 0.9624 + 0.25 × 0.7655 + 0.15 × 0.4722 + 0.10 × 1.00
   = 0.14166 + 0.19248 + 0.19138 + 0.07083 + 0.10000
   = 0.6964
```

#### 4.6.5 CVAL Result

| Rank | Region | PS_CVAL | Margin |
|---|---|---|---|
| **1** | **Canada Central** | **0.6964** | +0.2208 |
| 2 | Central US | 0.4756 | |

**Canada Central wins CVAL** by a wide margin, driven primarily by its much higher NP capacity headroom (α = 0.47 vs 0.05).

---

### 4.7 Scoring — DR Environment

For DR scoring, both the Prod winner (West US 3) and the CVAL winner (Canada Central) are excluded. In a 3-region US model, this leaves **only Central US** as the DR candidate.

But let us walk through the DR scoring formulas anyway, as they differ significantly from Prod and CVAL.

#### 4.7.1 DR Component Formulas (Differences from Prod and CVAL)

| Component | DR Formula | Source |
|---|---|---|
| α | DR Free / DR Reserved | DR capacity headroom (not NP or Prod) |
| β | NP Q-Headroom / NP Q-Limit | Same as CVAL — DR uses NP quota pool |
| γ | Same geography-wide formula | Unchanged |
| δ | DR Coverage / DR Coverage Target (0.80) | How close to the 80% coverage goal |
| ε | Same zone formula | Unchanged |

#### 4.7.2 DR Component Calculations (Central US)

**α — DR Capacity Headroom**

```
α_raw = DR Free / DR Reserved = 6,800 / 8,500 = 0.8000
α_c = 0.8000
```

Central US has 80% of its DR reservation still available — good headroom.

**β — NP Quota Headroom**

```
β_raw = NP Q-Head / NP Q-Limit = 190,080 / 200,000 = 0.9504
β_c = 0.9504
```

**γ — Distribution Fairness**

```
γ_raw = 1 − 78/226 = 0.6549
γ_c = 0.6549
```

**δ — DR Coverage vs Target**

```
δ_raw = DR Coverage / DR Coverage Target = 0.55 / 0.80 = 0.6875
δ_c = 0.6875
```

Central US is at 55% DR coverage against a target of 80% → it scores 0.69 on δ. This means placing DR here would help close the gap toward the target.

**ε — Zone Diversity**

```
ε_raw = 3/3 = 1.00
ε_c = 1.00
```

#### 4.7.3 Weighted DR Score

```
PS_DR = 0.30 × 0.8000 + 0.20 × 0.9504 + 0.25 × 0.6549 + 0.15 × 0.6875 + 0.10 × 1.00
      = 0.24000 + 0.19008 + 0.16373 + 0.10313 + 0.10000
      = 0.7969
```

#### 4.7.4 DR Result

| Rank | Region | PS_DR | Notes |
|---|---|---|---|
| **1** | **Central US** | **0.7969** | Only candidate (3-region separation) |

Central US is the DR winner by default (the only remaining US Standard region after Prod and CVAL placements). Its high score (0.80) confirms it is a strong DR candidate — abundant DR headroom and good quota room.

---

### 4.8 CRV Output

Combining all three environment results:

```
CRV(Contoso, US) = {
    geography:          US
    distribution_model: 3-region
    prod_region:        West US 3        (input — validated, PS = 0.5409)
    cval_region:        Canada Central   (scored — PS = 0.6964)
    dr_region:          Central US       (scored — PS = 0.7969)
    decision_timestamp: 2026-10-15T09:30:00Z
    policy_version:     v4.0-weights-default
    engine_version:     ACRME-v1.0
}
```

This CRV is cached and reused by every domain group (TMS, WMS) that Contoso operates in the US geography.

---

### 4.9 Domain Placement Binding (DPB) — TMS Domain

Now the second phase: DPB binds TMS's capacity in each CRV region. The DPB is deterministic — no scoring.

#### 4.9.1 ig Subscription Resolution (DOM-002)

| Domain | Environment | CRV Region | Subscription | Naming Rule |
|---|---|---|---|---|
| TMS | Prod | West US 3 | `sub-jda-cld-cr-prod-wl-tms-wus3-01` | C-12/OPS-006 |
| TMS | CVAL | Canada Central | `sub-jda-cld-cr-cval-wl-tms-cac-01` | |
| TMS | DR | Central US | `sub-jda-cld-cr-dr-wl-tms-cus-01` | |

#### 4.9.2 CRG Set Verification (CAP-025)

**TMS Prod in West US 3 — Prod-dedicated CRG set:**

| CRG | Zones | SKUs Seeded | Status |
|---|---|---|---|
| `crg-pr-wus3-az1` | Zone 1 | E32ads_v5 @ 0 | Ready (seed matrix) |
| `crg-pr-wus3-az2` | Zone 2 | E32ads_v5 @ 0 | Ready |
| `crg-pr-wus3-az3` | Zone 3 | E32ads_v5 @ 0 | Ready |

**TMS CVAL in Canada Central — CVAL/DR shared CRG set:**

| CRG | Zones | Purpose |
|---|---|---|
| `crg-cvdr-cac-az1/2/3` | 1, 2, 3 | Shared between CVAL and DR capacity for TMS |
| `crg-drf-cac-zonal` | All | DR Foundation — standing bootstrap capacity |

**TMS DR in Central US — CVAL/DR shared CRG set:**

| CRG | Zones | Purpose |
|---|---|---|
| `crg-cvdr-cus-az1/2/3` | 1, 2, 3 | DR capacity for TMS |
| `crg-drf-cus-zonal` | All | DR Foundation |

#### 4.9.3 Reservation Target Calculation (F.1–F.3)

**TMS Prod — West US 3 — E32ads_v5:**

```
Allocated VMs      = 20
Buffer (configured) = 4        (scope file: 20% for this SKU/region)
Target Reserved     = 20 + 4 = 24 VMs                    [F.1]
Current Reserved    = 18 VMs   (existing CRG state)
Headroom           = 18 − 20 = −2                        [F.2]
Deficit            = max(0, 24 − 18) = 6 VMs             [F.3]
```

**Action:** Reconciliation engine increases reservation by 6 VMs in `crg-pr-wus3-az*`, distributed across zones per F.9.

**TMS CVAL — Canada Central — E32ads_v5:**

```
Allocated VMs      = 8
Buffer             = 2
Target Reserved    = 8 + 2 = 10 VMs
Current Reserved   = 10 VMs
Headroom           = 10 − 8 = 2
Deficit            = max(0, 10 − 10) = 0
```

**Action:** No reconciliation needed. CVAL is at target.

**TMS DR — Central US — E32ads_v5:**

```
Allocated VMs      = 0         (DR is bootstrap, no VMs running yet)
Buffer             = 2         (DR bootstrap buffer)
Target Reserved    = 0 + 2 = 2 VMs
Current Reserved   = 0 VMs    (seed matrix, count 0)
Headroom           = 0 − 0 = 0
Deficit            = max(0, 2 − 0) = 2 VMs
```

**Action:** Reconciliation creates 2-VM reservation in `crg-cvdr-cus-az*` (DR bootstrap capacity).

#### 4.9.4 Zone Distribution (F.9, PLC-016)

**TMS Prod — West US 3 — 20 VMs across 3 zones:**

```
Even Zone Share    = 1/3 = 33.3%
Target per Zone    = round(20/3)
  AZ1 target = round(6.67) = 7
  AZ2 target = round(6.67) = 7
  AZ3 target = 20 − 7 − 7 = 6     (remainder)
```

Current actual distribution (example):

| Zone | Target | Actual | Skew | |Skew| |
|---|---|---|---|---|
| AZ1 | 7 | 9 | +2 | 2 |
| AZ2 | 7 | 6 | −1 | 1 |
| AZ3 | 6 | 5 | −1 | 1 |
| **Max Skew** | | | | **2** |

```
Skew Tolerance (C-13) = 2
Max Skew = 2
Max Skew > Tolerance? → 2 > 2? → NO (at boundary, not exceeded)
```

No rebalancing triggered. But the next VM deployment should target **AZ3** (most under-represented, only 5 actual vs 6 target) or **AZ2** (6 actual vs 7 target) rather than AZ1 (already 2 over target).

**The reconciliation engine's 6 new VMs** (from the deficit) would be placed:
- 1 VM → AZ2 (bring it to 7, meeting target)
- 1 VM → AZ3 (bring it to 6, meeting target)
- Remaining 4 → distributed evenly: 2 to AZ2, 1 to AZ3, 1 to AZ1
- Final: AZ1 = 10, AZ2 = 9, AZ3 = 7 (targets for 26 VMs: 9/9/8)

#### 4.9.5 Quota Draw (F.4–F.5, QUA-015)

**TMS Prod ig in West US 3:**

```
Subscription VM-family cap (Eads_v5)  = 800 vCPU
Current usage (20 × 32 vCPU)          = 640 vCPU
Available quota (F.4)                  = 800 − 640 = 160 vCPU

Additional needed for 6 new VMs       = 6 × 32 = 192 vCPU
Quota deficit (F.5)                    = max(0, 192 − 160) = 32 vCPU
```

The subscription does not have enough VM-family quota for the 6 new reservation VMs. The central quota group is consulted:

```
Central Pool: Eads_v5 in West US 3
  Pool limit          = 5,000 vCPU
  Allocated to subs   = 3,200 vCPU
  Available in pool   = 1,800 vCPU
  Pool utilisation     = 3,200 / 5,000 = 64%
```

Pool has 1,800 vCPU available → can allocate 192 vCPU to TMS Prod subscription.

```
Post-allocation:
  Sub VM-family cap   = 800 + 192 = 992 vCPU
  Pool allocated      = 3,200 + 192 = 3,392 vCPU
  Pool utilisation    = 3,392 / 5,000 = 67.8%
```

67.8% is below the 85% replenishment threshold → no proactive Azure quota request triggered yet.

#### 4.9.6 DPB Records Written

```
DPB(TMS, Prod) = {
    domain:          TMS
    environment:     Prod
    region:          West US 3
    ig:              sub-jda-cld-cr-prod-wl-tms-wus3-01
    crg_set:         crg-pr-wus3-* (Prod dedicated)
    target_reserved: 24 VMs (E32ads_v5)
    current_reserved: 18 VMs
    deficit:         6 VMs → reconciliation action
    zone_target:     9/9/8 (post-reconciliation for 26 total)
    quota_source:    Central pool Eads_v5 WUS3
    status:          READY_WITH_RISK (reservation deficit being reconciled)
}

DPB(TMS, CVAL) = {
    domain:          TMS
    environment:     CVAL
    region:          Canada Central
    ig:              sub-jda-cld-cr-cval-wl-tms-cac-01
    crg_set:         crg-cvdr-cac-* (CVAL/DR shared)
    target_reserved: 10 VMs
    current_reserved: 10 VMs
    deficit:         0
    zone_target:     3/3/4
    status:          READY
}

DPB(TMS, DR) = {
    domain:          TMS
    environment:     DR
    region:          Central US
    ig:              sub-jda-cld-cr-dr-wl-tms-cus-01
    crg_set:         crg-cvdr-cus-* (CVAL/DR shared) + crg-drf-cus-* (Foundation)
    target_reserved: 2 VMs (bootstrap)
    current_reserved: 0 VMs
    deficit:         2 VMs → reconciliation action
    status:          READY_WITH_RISK (bootstrap provisioning)
}
```

---

### 4.10 WMS Domain — Same CRV, Different DPB

When domain WMS runs its DPB, it uses the **same CRV** (West US 3 / Canada Central / Central US) but gets:

- **Different subscriptions:** `sub-jda-cld-cr-prod-wl-wms-wus3-01` (not TMS's sub)
- **Different CRG sets:** `crg-pr-wus3-*` under WMS's ig (never mixed with TMS)
- **Different capacity targets:** WMS may have 15 VMs instead of 20, with a 10% buffer instead of 20%
- **Independent zone distribution:** WMS manages its own per-zone balance
- **Same central quota pool:** Both TMS and WMS draw from the same customer-level pool, but from their own cells

The combined-load observation (`RegionZoneLoad`) would report TMS + WMS VMs per zone to observability, but this is informational only — it never triggers cross-domain actions.

---

## 5. Distribution Model Variations — Worked Comparisons

### 5.1 Europe (2-Region Co-Located Model)

**Customer:** Fabrikam
**Geography:** Europe
**Prod Region:** Switzerland North (exact-region path)
**Candidate regions:** Switzerland North (Prod), Sweden Central (only remaining)

#### What Changes

1. **CRV resolution is trivial for CVAL/DR:** Only one region remains after Prod → CVAL and DR both go to Sweden Central. No scoring needed for CVAL or DR — the result is deterministic (PLC-010a).

2. **HC-6 and HC-7 are critical:** Since CVAL and DR share Sweden Central:
   - HC-6 checks that `DR Free + NP Eff-Free ≥ DR Bootstrap Qty` in Sweden Central
   - HC-7 checks that adding CVAL deployment does not cannibalise the DR quota floor
   - If either fails, **placement fails entirely** — there is no fallback region

3. **CVAL-sacrifice bootstrap applies:** In 2-region, the CVAL/DR shared CRG set's CVAL capacity is earmarked as releasable for DR (DR-005/DR-006). The engine records this in the seed and ensures no double-counting.

#### CRV Output

```
CRV(Fabrikam, EU) = {
    geography:          Europe
    distribution_model: 2-region
    prod_region:        Switzerland North
    cval_region:        Sweden Central
    dr_region:          Sweden Central     ← CVAL/DR co-located
}
```

#### DPB Difference

The DPB for domain X in Sweden Central binds both CVAL and DR to the same region but uses the CVAL/DR shared CRG set (`crg-cvdr-swc-*`). The engine must:
- Track CVAL capacity and DR capacity separately within the shared CRG
- Record the CVAL → DR release earmark
- Never count the same vCPU as both live CVAL and available DR headroom

---

### 5.2 Middle East (Cross-Geography DR Model)

**Customer:** Adatum
**Geography:** Middle East
**Prod Region:** Saudi Arabia Central (exact-region path)
**Distribution model:** Cross-geo DR (REG-003 item 3)

#### What Changes

1. **CVAL co-locates with Prod (not DR):** R_c = R_p = Saudi Arabia Central. Prod and CVAL share the region but use **separate CRGs** (ENV-003 — no capacity sharing between Prod and NonProd).

2. **DR goes to Europe:** R_d is selected from Europe's Standard regions (Switzerland North, Sweden Central) using the **same scoring pipeline** (weighted multi-factor). The DR scoring sheet sets `InScope = IF(geography = Setup!B11, 1, 0)` and B11 = "EU" for Middle East → only European regions are DR candidates.

3. **No CVAL-sacrifice bootstrap:** DR-005/DR-006 do not apply. Middle East DR is funded by **dedicated reserved DR capacity** in Europe, not by releasing CVAL. This costs more but avoids cross-border capacity handoffs.

4. **Source→destination DR index:** The seed records `dr_geography = "Europe"` so DR accounting treats Europe as the protection destination for Middle East source workloads (DR-018).

#### DR Scoring for Europe Regions

| Component | Switzerland North | Sweden Central |
|---|---|---|
| α (DR Free / DR Reserved) | 7,500/9,000 = 0.8333 | 6,200/7,800 = 0.7949 |
| β (NP Q-Head / NP Q-Limit) | 0.9200 | 0.9350 |
| γ (1 − CustCount/Total) | 1 − 45/120 = 0.6250 | 1 − 38/120 = 0.6833 |
| δ (DR Coverage / 0.80) | 0.72/0.80 = 0.9000 | 0.65/0.80 = 0.8125 |
| ε (AZ/3) | 1.00 | 1.00 |

```
PS_DR(SwN) = 0.30×0.833 + 0.20×0.920 + 0.25×0.625 + 0.15×0.900 + 0.10×1.00
           = 0.2499 + 0.1840 + 0.1563 + 0.1350 + 0.1000 = 0.8252

PS_DR(SwC) = 0.30×0.795 + 0.20×0.935 + 0.25×0.683 + 0.15×0.813 + 0.10×1.00
           = 0.2385 + 0.1870 + 0.1708 + 0.1220 + 0.1000 = 0.8183
```

Switzerland North wins DR (0.8252 vs 0.8183).

#### CRV Output

```
CRV(Adatum, ME) = {
    geography:          Middle East
    distribution_model: cross-geo
    prod_region:        Saudi Arabia Central
    cval_region:        Saudi Arabia Central   ← co-located with Prod
    dr_region:          Switzerland North       ← cross-geo, in Europe
    dr_geography:       Europe
}
```

#### DPB Difference

- **Prod + CVAL in Saudi Arabia Central:** Two separate ig subscriptions, two separate CRG sets (Prod-dedicated and CVAL), same physical region. The naming convention differentiates them: `crg-pr-sac-*` vs `crg-cvdr-sac-*`.
- **DR in Switzerland North:** DR ig subscription and CRG set in a different geography entirely. DR sizing uses the max-not-sum formula (F.6) with Middle East as the source and Europe as the destination.

---

## 6. End-to-End Readiness Gate (RDY-001)

After all DPBs are resolved, the readiness gate checks every dimension:

| Check | TMS Prod (WUS3) | TMS CVAL (CAC) | TMS DR (CUS) | Overall |
|---|---|---|---|---|
| Region approved | ✅ | ✅ | ✅ | ✅ |
| Zone supported | ✅ (3 AZ) | ✅ (3 AZ) | ✅ (3 AZ) | ✅ |
| SKU supported | ✅ | ✅ | ✅ | ✅ |
| Reservation exists | ✅ (deficit reconciling) | ✅ | ⚠️ (deficit: 2 VMs) | ⚠️ |
| Quota sufficient | ⚠️ (32 vCPU deficit → pool draw) | ✅ | ✅ | ⚠️ |
| State fresh | ✅ (< 15 min) | ✅ | ✅ | ✅ |
| No blocking policy | ✅ | ✅ | ✅ | ✅ |

**Overall readiness:** `READY_WITH_RISK` — all environments have paths to resolution (quota can be drawn from pool, reservations are being reconciled), but the reservation deficits mean capacity is not yet fully guaranteed.

The machine-readable state transitions to `READY` once:
1. The 6-VM reservation increase in WUS3 completes
2. The 2-VM DR bootstrap reservation in CUS is created
3. The 32-vCPU quota draw from the central pool is processed

---

## 7. Formula Quick Reference

| ID | Name | Formula | Scope | Used In |
|---|---|---|---|---|
| F.1 | Reservation target | Allocated + Buffer | Domain × Env | DPB |
| F.2 | Reservation headroom | Reserved − Allocated | Domain × Env | DPB, Monitoring |
| F.3 | Reservation deficit | max(0, Target − Reserved) | Domain × Env | DPB, Reconciliation |
| F.4 | Available quota | VM-family cap − Usage | Domain × Env | DPB, Readiness |
| F.5 | Quota deficit | max(0, Requested − Available) | Domain × Env | DPB, Readiness |
| F.6 | DR destination req | MAX over sources (workload portion) | Destination region | DR sizing |
| F.7 | DR capacity gap | max(0, DR Req − Usable capacity) | Destination region | DR acquisition |
| F.8 | Overcommit ratio | SUM(portions) / MAX(portions) | Destination region | Observability |
| F.9 | Zone distribution | round(VMs / ZoneCount) per zone | Domain × Env | DPB, Rebalancing |
| F.10 | γ fairness | 1 − EnvCust(r) / TotalCust(g) | Geography | CRV scoring |
| F.11 | CRV resolution | Exact-region or Geography path | Customer × Geo | CRV |
| F.12 | DPB binding | F.1–F.9 re-parameterised per (D,E) | Domain × Env × Region | DPB |
| F.13 | Lineage note | F.12 instantiates F.1–F.9 at domain scope | — | Documentation |

---

## 8. Scoring Component Comparison Across Environments

| Component | Prod Formula | CVAL Formula | DR Formula |
|---|---|---|---|
| **α** (capacity) | NP_Eff_Free / Prod_Reserved | NP_Eff_Free / NP_Reserved | DR_Free / DR_Reserved |
| **β** (quota) | Prod_Q_Head / Prod_Q_Limit | NP_Q_Head / NP_Q_Limit | NP_Q_Head / NP_Q_Limit |
| **γ** (fairness) | 1 − ProdCust/TotalCust | 1 − CVALCust/TotalCust | 1 − DRCust/TotalCust |
| **δ** (DR readiness) | DR_Coverage | NP_Eff_Free / NP_Reserved ⚠️ | DR_Coverage / DR_Target |
| **ε** (zone) | AZ_Count / 3 | AZ_Count / 3 | AZ_Count / 3 |
| **InScope filter** | geography match | geography match | DR scope geography |
| **Eligible flag** | HC-3 Prod | HC-3 NP AND HC-7 | HC-3 DR AND HC-6 |
| **Candidate exclusion** | none | excludes Prod winner | excludes Prod + CVAL winners |

---

*Document generated from ACRME Requirements Baseline v4.0, Hard Constraints Reference v1.1, and the Region Selection WHAT-IF mock exercise user guide. All requirement IDs trace to the baseline. Capacity and quota numbers are illustrative planning figures derived from the mock exercise data structure.*
