# ACRME — CR & CRG Deployment Layout Reference

## Document Control

| Field                   | Value                                                                                   |
|-------------------------|-----------------------------------------------------------------------------------------|
| **Title**               | ACRME — Capacity Reservation & CRG Deployment Layout Reference                          |
| **Version**             | 1.0                                                                                     |
| **Date**                | 9 Sep 2026                                                                              |
| **Status**              | Active                                                                                  |
| **Owner**               | Platform Engineering / Cloud Architecture                                               |
| **Source baseline**     | `acrme_requirements_baseline_v2_4.md` (CAP-023, OPS-006, REG-003, PLC-010/PLC-010a)    |
| **Purpose**             | Visual reference for CR & CRG deployment structure across all environments and geographies |

---

## 1. Purpose

This document provides the **authoritative deployment layout** for Azure Capacity Reservations (CR) and Capacity Reservation Groups (CRG) across all ACRME-managed environments. It translates the normative requirements (CAP-023, OPS-006/C-12, REG-003, ENV-003, PLC-010/PLC-010a) into concrete deployment patterns with examples for each geography.

**Use this document to:**
- Understand the structural organization of CRGs per environment and region
- See how the regional + per-AZ CRG structure is implemented
- Trace the naming convention for RGs, CRGs, and subscriptions
- Visualize the difference between 3-region (US), 2-region co-located (Europe/Australia/Asia Pacific) and **[Amended v2.4]** cross-geo DR (Middle East → Europe) geographies
- Understand provider/consumer subscription relationships for shared reservations

---

## 2. Core Structural Principles

### 2.1 CRG Structure per Environment (CAP-023)

For **each environment** (Prod, CVAL/NonProd, DR) within a subscription and region:

```
One environment in one region
    ├── One regional (non-zonal) CRG      ← holds SKUs without zonal reservation support
    └── One CRG per availability zone     ← holds zone-bound reservations
```

**Key rules:**
- **Per-AZ CRGs** enforce zone isolation (CAP-011) **structurally** — zone-1 capacity can never be counted in another zone
- **Regional CRG** holds only SKUs that don't support zonal reservations
- **Environments are never mixed within a CRG** (ENV-003)
- Each CRG sits inside a resource group following the OPS-006 naming convention

### 2.2 Naming Convention (OPS-006, C-12)

All managed resources follow deterministic, parseable patterns:

| Resource | Pattern | Example |
|---|---|---|
| **Resource Group** | `rg-odcr-<env>-<region>-<NN>` | `rg-odcr-prod-eus2-01` |
| **CRG** | `crg-<env>-<region>-<scope>` | `crg-pr-eus2-az1` |
| **Subscription** | `sub-<org>-<domain>-<purpose>-<NN>` | `sub-jda-cld-core-01` |

**CRG scope tokens:** `scope ∈ {reg, az1, az2, az3}`
- `reg` = regional (non-zonal) CRG
- `az1`, `az2`, `az3` = per-availability-zone CRGs

**Environment tokens:** `env ∈ {prod, pr, cval, cv, nonprod, np, dr}`
- Production: `prod` or `pr`
- CVAL/NonProd: `cval`, `cv`, `nonprod`, or `np`
- DR: `dr`

### 2.3 Environment Separation Rules (ENV-003)

**Hard separation constraints (enforced structurally via separate CRGs):**
- ❌ Non-prod and prod **cannot** share capacity
- ❌ DR and prod **cannot** share capacity
- ✅ DR **may** share with non-prod (where co-located, PLC-010)

---

## 3. Deployment Layout by Geography

### 3.1 US — Three-Region Model (REG-003)

**Distribution:** For a US geography deployment, **select 3 distinct regions** and **distribute** Prod, CVAL, and DR across them. Each region can host any/all environments; the "3-region model" describes the deployment distribution strategy, not inherent region capabilities.

**In-scope regions (current):**
- West US 3 (westus3)
- Central US (centralus)
- Canada Central (canadacentral)
- East US 2 (eastus2) — restricted, exception-only

**Example deployment distribution:**
- **Prod → placed in:** West US 3
- **CVAL → placed in:** Central US
- **DR → placed in:** Canada Central

> **Note:** Any of these regions can technically host all three environments simultaneously (each with separate subscriptions/RGs/CRGs per ENV-003). The distribution above shows a **deployment choice** for one customer, not a region capability limit.

#### 3.1.1 Production Environment — West US 3 (3 zones)

```
Subscription: sub-jda-cld-core-01 (provider subscription, owns shared reservations)
Region: West US 3 (westus3)
Environment: Production

Resource Group: rg-odcr-prod-wus3-01
    ├── crg-pr-wus3-reg        ← Regional CRG (non-zonal SKUs)
    │   └── Reservations:
    │       ├── res-pr-wus3-reg-StandardD4sv5-001 (qty: 10)
    │       └── res-pr-wus3-reg-StandardE8sv5-001 (qty: 5)
    │
    ├── crg-pr-wus3-az1        ← Zone 1 CRG
    │   └── Reservations:
    │       ├── res-pr-wus3-az1-StandardD16sv5-001 (qty: 25)
    │       ├── res-pr-wus3-az1-StandardE16sv5-001 (qty: 15)
    │       └── res-pr-wus3-az1-StandardF16sv2-001 (qty: 8)
    │
    ├── crg-pr-wus3-az2        ← Zone 2 CRG
    │   └── Reservations:
    │       ├── res-pr-wus3-az2-StandardD16sv5-001 (qty: 24)
    │       ├── res-pr-wus3-az2-StandardE16sv5-001 (qty: 15)
    │       └── res-pr-wus3-az2-StandardF16sv2-001 (qty: 9)
    │
    └── crg-pr-wus3-az3        ← Zone 3 CRG
        └── Reservations:
            ├── res-pr-wus3-az3-StandardD16sv5-001 (qty: 26)
            ├── res-pr-wus3-az3-StandardE16sv5-001 (qty: 15)
            └── res-pr-wus3-az3-StandardF16sv2-001 (qty: 8)

Sharing configuration (Tier 1/2):
    Provider: sub-jda-cld-core-01
    Consumers: sub-jda-cld-app-01, sub-jda-cld-app-02, ... (up to ~100)
```

**Zone distribution (PLC-011):**
- Target: ~33% per zone (1/3) in a 3-zone region
- Example: 75 total D16sv5 VMs → 25/24/26 distribution (within tolerance)
- Rebalance triggered when skew exceeds configured tolerance (C-13)

#### 3.1.2 CVAL Environment — Central US (3 zones)

```
Subscription: sub-jda-cld-nonprod-01
Region: Central US (centralus)
Environment: CVAL/NonProd

Resource Group: rg-odcr-cval-cus-01
    ├── crg-cv-cus-reg         ← Regional CRG (non-zonal SKUs)
    │   └── Reservations: (seed matrix, most at qty: 0)
    │
    ├── crg-cv-cus-az1         ← Zone 1 CRG
    │   └── Reservations:
    │       ├── res-cv-cus-az1-StandardD8sv5-001 (qty: 5)
    │       └── res-cv-cus-az1-StandardE8sv5-001 (qty: 3)
    │
    ├── crg-cv-cus-az2         ← Zone 2 CRG
    │   └── Reservations:
    │       ├── res-cv-cus-az2-StandardD8sv5-001 (qty: 5)
    │       └── res-cv-cus-az2-StandardE8sv5-001 (qty: 3)
    │
    └── crg-cv-cus-az3         ← Zone 3 CRG
        └── Reservations:
            ├── res-cv-cus-az3-StandardD8sv5-001 (qty: 5)
            └── res-cv-cus-az3-StandardE8sv5-001 (qty: 3)
```

**CVAL characteristics:**
- Separate subscription from Prod (ENV-003: prod ≠ non-prod)
- Lower buffer targets (C-2: configurable buffer policy)
- May be powered down for cost savings (ENV-002)
- In US 3-region model: CVAL is in a distinct region, **not co-located with DR**

#### 3.1.3 DR Environment — Canada Central (3 zones)

```
Subscription: sub-jda-cld-dr-01
Region: Canada Central (canadacentral)
Environment: DR

Resource Group: rg-odcr-dr-cac-01
    ├── crg-dr-cac-reg         ← Regional CRG (non-zonal SKUs)
    │   └── Reservations: (seed matrix, most at qty: 0 until DR event)
    │
    ├── crg-dr-cac-az1         ← Zone 1 CRG
    │   └── Reservations:
    │       ├── res-dr-cac-az1-StandardD16sv5-001 (qty: 0)  ← seed reservation
    │       └── res-dr-cac-az1-StandardE16sv5-001 (qty: 2)  ← bootstrap capacity
    │
    ├── crg-dr-cac-az2         ← Zone 2 CRG
    │   └── Reservations:
    │       ├── res-dr-cac-az2-StandardD16sv5-001 (qty: 0)  ← seed reservation
    │       └── res-dr-cac-az2-StandardE16sv5-001 (qty: 2)  ← bootstrap capacity
    │
    └── crg-dr-cac-az3         ← Zone 3 CRG
        └── Reservations:
            ├── res-dr-cac-az3-StandardD16sv5-001 (qty: 0)  ← seed reservation
            └── res-dr-cac-az3-StandardE16sv5-001 (qty: 2)  ← bootstrap capacity
```

**DR characteristics (US 3-region):**
- Separate region from Prod and CVAL
- Starts lean: bootstrap capacity only (DR-003, DR-004)
- Seed reservations at qty: 0 for eligible SKU/AZ matrix (CAP-022)
- Scales up on DR declaration (ADR-003, DR-009)
- Cannot share capacity with Prod (ENV-003), but **may** share with non-prod where policy permits

---

### 3.2 Europe — Two-Region Model with CVAL/DR Co-location (REG-003, PLC-010a)

**Distribution:** For a Europe geography deployment, **select 2 regions** and **distribute** environments: Prod in one region, CVAL + DR co-located in the other. Each region can host any/all environments; co-location is the deployment strategy for 2-region geographies.

**In-scope regions (current):**
- Switzerland North (switzerlandnorth) — default example of the weighted cross-geo DR destination for the Middle East (REG-002) **[Amended v2.4: weighted-selected, not fixed]**
- Sweden Central (swedencentral)
- North Europe (northeurope) — restricted, exception-only
- West Europe (westeurope) — restricted, exception-only

**Example deployment distribution:**
- **Prod → placed in:** Sweden Central
- **CVAL + DR → co-located in:** Switzerland North

> **Note:** Either region can technically host all three environments. The co-location pattern is required by PLC-010a for 2-region geographies (Prod isolation maintained; CVAL+DR share the second region to satisfy ENV-003 while delivering in-geo DR). **[Amended v2.4]** Europe is additionally a **cross-geo DR destination for the Middle East** (a weighted-selected Europe Standard region hosts ME DR CRGs); that Europe destination sizes DR **max-not-sum** across all sources failing over to it, including Middle East sources (DR-017, DR-020).

#### 3.2.1 Production Environment — Sweden Central (3 zones)

```
Subscription: sub-jda-cld-core-eu-01
Region: Sweden Central (swedencentral)
Environment: Production

Resource Group: rg-odcr-prod-sdc-01
    ├── crg-pr-sdc-reg         ← Regional CRG
    ├── crg-pr-sdc-az1         ← Zone 1 CRG
    ├── crg-pr-sdc-az2         ← Zone 2 CRG
    └── crg-pr-sdc-az3         ← Zone 3 CRG

(Structure identical to US Prod example above)
```

#### 3.2.2 CVAL + DR Co-located — Switzerland North (3 zones)

**CRITICAL:** In a 2-region geography, once Prod is anchored, only one region remains → **CVAL and DR co-locate deterministically** (PLC-010a). This is the **normal, required outcome**, not an error state.

```
Subscription: sub-jda-cld-nonprod-eu-01 (owns CVAL reservations)
             sub-jda-cld-dr-eu-01       (owns DR reservations)
Region: Switzerland North (switzerlandnorth)
Environments: CVAL + DR (co-located in same region, separate subscriptions)

──────────────────────────────────────────────────────────────────────
CVAL ENVIRONMENT
──────────────────────────────────────────────────────────────────────
Resource Group: rg-odcr-cval-swn-01
Subscription: sub-jda-cld-nonprod-eu-01

    ├── crg-cv-swn-reg         ← CVAL Regional CRG
    ├── crg-cv-swn-az1         ← CVAL Zone 1 CRG
    │   └── Reservations:
    │       ├── res-cv-swn-az1-StandardD8sv5-001 (qty: 10)
    │       └── res-cv-swn-az1-StandardE8sv5-001 (qty: 6)
    ├── crg-cv-swn-az2         ← CVAL Zone 2 CRG
    │   └── Reservations:
    │       ├── res-cv-swn-az2-StandardD8sv5-001 (qty: 10)
    │       └── res-cv-swn-az2-StandardE8sv5-001 (qty: 6)
    └── crg-cv-swn-az3         ← CVAL Zone 3 CRG
        └── Reservations:
            ├── res-cv-swn-az3-StandardD8sv5-001 (qty: 10)
            └── res-cv-swn-az3-StandardE8sv5-001 (qty: 6)

──────────────────────────────────────────────────────────────────────
DR ENVIRONMENT (co-located, separate subscription & CRGs)
──────────────────────────────────────────────────────────────────────
Resource Group: rg-odcr-dr-swn-01
Subscription: sub-jda-cld-dr-eu-01

    ├── crg-dr-swn-reg         ← DR Regional CRG
    ├── crg-dr-swn-az1         ← DR Zone 1 CRG
    │   └── Reservations:
    │       ├── res-dr-swn-az1-StandardD16sv5-001 (qty: 0)  ← seed
    │       └── res-dr-swn-az1-StandardE16sv5-001 (qty: 2)  ← bootstrap
    ├── crg-dr-swn-az2         ← DR Zone 2 CRG
    │   └── Reservations:
    │       ├── res-dr-swn-az2-StandardD16sv5-001 (qty: 0)  ← seed
    │       └── res-dr-swn-az2-StandardE16sv5-001 (qty: 2)  ← bootstrap
    └── crg-dr-swn-az3         ← DR Zone 3 CRG
        └── Reservations:
            ├── res-dr-swn-az3-StandardD16sv5-001 (qty: 0)  ← seed
            └── res-dr-swn-az3-StandardE16sv5-001 (qty: 2)  ← bootstrap
```

**Co-location accounting (HC-6, HC-7, PLC-010):**
- Seed record: `cval_region == dr_region` (Switzerland North) + co-location flag set
- **CVAL capacity is earmarked as releasable** toward DR activation (DR-005/DR-006)
- **Never double-counted** as both live CVAL *and* available DR headroom
- Combined-capacity checks: `DR_floor ≤ (CVAL_allocated + DR_allocated)` in the co-located region
- On DR declaration: CVAL may be shut down, disassociated, or reassigned per runbook

**Why co-location is mandatory here:**
- Geography has only 2 Standard regions (Sweden Central, Switzerland North)
- Prod anchored in Sweden Central → only Switzerland North remains
- Cannot separate all three environments → CVAL + DR co-locate deterministically
- This is the **normative outcome for any 2-region geography**, not an exception

---

### 3.3 Australia — Two-Region Model (same pattern as Europe)

**In-scope regions:**
- Australia East (australiaeast)
- Australia Southeast (australiasoutheast)

**Example deployment distribution:**
- **Prod → placed in:** Australia East
- **CVAL + DR → co-located in:** Australia Southeast

> **Note:** Either region can host all three environments. Distribution follows the same 2-region co-location pattern as Europe.

**Structure:** Identical to Europe example above (§3.2), substitute region codes.

---

### 3.4 Asia Pacific — Two-Region Model (same pattern as Europe)

**In-scope regions:**
- East Asia (eastasia)
- Southeast Asia (southeastasia)
- Japan East (japaneast) — **pending business confirmation before inclusion**

**Example deployment distribution (current 2-region):**
- **Prod → placed in:** East Asia
- **CVAL + DR → co-located in:** Southeast Asia

> **Note:** Either region can host all three environments. Distribution follows the same 2-region co-location pattern as Europe.

**Structure:** Identical to Europe example above (§3.2), substitute region codes.

---

### 3.5 Middle East — Cross-Geo DR Model (Prod+CVAL in ME, DR in Europe) — [Amended v2.4] (DR-020, PLC-010b, DEC-001 RESOLVED)

**In-scope regions (Prod + CVAL):**
- Saudi Arabia Central (saudiarabiacentral)
- UAE North (uaenorth)

**DR destination:** a **weighted-selected Europe Standard region** (e.g., Switzerland North — default example, not fixed).

**Legal position [Amended v2.4]:** DEC-001 is **RESOLVED** — DR is now **offered cross-geo** for the Middle East. Europe is an approved DR destination (assumption **A-ME1**); per-country data-residency carve-outs are handled via configuration and are out of engine scope.

**Example deployment distribution:**
- **Prod → placed in:** a weighted-selected Middle East region (e.g., UAE North)
- **CVAL → co-located with Prod** in the same Middle East region (separate CRG; co-location ≠ capacity sharing, ENV-003)
- **DR → placed cross-geo** in a weighted-selected Europe Standard region (e.g., Switzerland North)

> **Note:** Prod and CVAL co-locate in one Middle East region (separate subs/CRGs). DR environment CRGs are built **cross-geo** in the selected Europe region. Because CVAL co-locates with Prod locally (not with DR), the CVAL-sacrifice DR bootstrap (DR-005/006) does not apply to the Middle East — ME DR uses dedicated reserved capacity in Europe.

```
PRODUCTION ENVIRONMENT — UAE North (weighted-selected ME region)
Subscription: sub-jda-cld-core-me-01
Region: UAE North (uaenorth)
Resource Group: rg-odcr-prod-uan-01
    ├── crg-pr-uan-reg
    ├── crg-pr-uan-az1
    ├── crg-pr-uan-az2
    └── crg-pr-uan-az3

CVAL ENVIRONMENT — UAE North (co-located with Prod, separate sub/CRGs)
Subscription: sub-jda-cld-nonprod-me-01
Region: UAE North (uaenorth)
Resource Group: rg-odcr-cval-uan-01
    ├── crg-cv-uan-reg
    ├── crg-cv-uan-az1
    ├── crg-cv-uan-az2
    └── crg-cv-uan-az3

DR ENVIRONMENT — Switzerland North (weighted-selected Europe region, CROSS-GEO)
Subscription: sub-jda-cld-dr-eu-01
Region: Switzerland North (switzerlandnorth)   ← weighted-selected Europe Standard region (example)
Resource Group: rg-odcr-dr-swn-01
    ├── crg-dr-swn-reg
    ├── crg-dr-swn-az1
    ├── crg-dr-swn-az2
    └── crg-dr-swn-az3
Seed record: production_region = UAE North, cval_region = UAE North, dr_region = Switzerland North (cross-geo)
Europe destination sizes DR max-not-sum (DR-017) across all sources failing over to it.
```

**Configuration notes (v2.4):**
- The Middle East DR region is chosen by the **weighted capacity model** over Europe Standard regions (REG-002, DR-020, PLC-010b) — Switzerland North is the default example, not a fixed region
- Changing the Europe destination set is a config change, no code change (REG-001)
- The generic `DR_NOT_OFFERED` flag (DR-014) remains available for any future geography but is **not** set for the Middle East

---

## 4. Seed Matrix & Zero-Capacity Reservations (CAP-022)

Every **eligible SKU/family × region × availability zone** combination is initialized as a **seed reservation at quantity 0** inside the correct CRG, so reconciliation can scale it up instantly when demand appears.

**Example seed matrix (partial) — Prod West US 3:**

| CRG | Reservation Name | SKU | Initial Qty | Product Team | Budget Line | State |
|-----|------------------|-----|-------------|--------------|-------------|-------|
| crg-pr-wus3-az1 | res-pr-wus3-az1-StandardD2sv5-001 | Standard_D2s_v5 | 0 | Platform-Core | FY27-Q1-Compute-001 | Seed |
| crg-pr-wus3-az1 | res-pr-wus3-az1-StandardD4sv5-001 | Standard_D4s_v5 | 0 | Platform-Core | FY27-Q1-Compute-001 | Seed |
| crg-pr-wus3-az1 | res-pr-wus3-az1-StandardD8sv5-001 | Standard_D8s_v5 | 0 | Platform-Core | FY27-Q1-Compute-001 | Seed |
| crg-pr-wus3-az1 | res-pr-wus3-az1-StandardD16sv5-001 | Standard_D16s_v5 | 25 | Platform-Core | FY27-Q1-Compute-001 | Active (scaled from seed) |
| crg-pr-wus3-az1 | res-pr-wus3-az1-StandardE16sv5-001 | Standard_E16s_v5 | 15 | Data-Services | FY27-Q1-Compute-002 | Active (scaled from seed) |
| crg-pr-wus3-az1 | res-pr-wus3-az1-StandardF16sv2-001 | Standard_F16s_v2 | 8 | ML-Platform | FY27-Q1-Compute-003 | Active (scaled from seed) |
| ... | ... | ... | ... | ... | ... | ... |

**Seed matrix governance (CAP-022):**
- Entry requires: named owning **product team** + approved **budget line**
- Anything above qty: 0 incurs cost → budget approval gates expansion
- Matrix is configuration-driven (scope file, CAP-019) and versioned
- Reactive discovery (CAP-024): unmanaged allocated SKU/AZ → auto-create reservation + raise scope-file governance item

---

## 5. Cross-Subscription Sharing (Tier 1/2/3)

### 5.1 Provider/Consumer Model (CAP-013, CAP-014, CAP-015)

**Tier 1:** Single subscription owns and consumes its own reservations (no sharing).

**Tier 2 (Preview):** Provider subscription shares reservations with consumer subscriptions within the same region + AZ (up to ~100 consumers per tenant).

**Tier 3 (Preview):** Provider subscription can forcibly disassociate VMs from consumer subscriptions (requires G-14 consumer credential model — currently undesigned).

### 5.2 Sharing Layout Example — Prod West US 3, Zone 1

```
PROVIDER SUBSCRIPTION (owns the shared reservation)
──────────────────────────────────────────────────────────────────────
Subscription: sub-jda-cld-core-01
Region: West US 3, Zone 1
CRG: crg-pr-wus3-az1

Reservation: res-pr-wus3-az1-StandardD16sv5-001
    Reserved Quantity: 100
    Provider: sub-jda-cld-core-01
    Sharing enabled: YES
    Authorized consumers:
        - sub-jda-cld-app-01
        - sub-jda-cld-app-02
        - sub-jda-cld-app-03
        - ... (up to ~100)

CONSUMER SUBSCRIPTIONS (consume shared reservation, don't own it)
──────────────────────────────────────────────────────────────────────
Subscription: sub-jda-cld-app-01
    Allocated VMs consuming shared reservation:
        - 15 × Standard_D16s_v5 in Zone 1 (associated to provider's CRG)
    Quota required: YES (consumer subscription must have its own quota, QUA-013)

Subscription: sub-jda-cld-app-02
    Allocated VMs consuming shared reservation:
        - 22 × Standard_D16s_v5 in Zone 1 (associated to provider's CRG)

Subscription: sub-jda-cld-app-03
    Allocated VMs consuming shared reservation:
        - 18 × Standard_D16s_v5 in Zone 1 (associated to provider's CRG)

TOTAL CONSUMPTION ACCOUNTING (CAP-015 — no double counting)
──────────────────────────────────────────────────────────────────────
Provider reserves: 100
Consumer-1 allocated: 15
Consumer-2 allocated: 22
Consumer-3 allocated: 18
──────────────────────
Total allocated: 55 (counted once at provider)
Remaining: 45 (available for new allocations)
```

**Sharing constraints:**
- Same **region AND availability zone** only (CAP-011, CAP-012)
- Authorization to consume ≠ allocated capacity (CAP-015)
- Each consumer needs its own quota (QUA-013)
- Sharing state tracked: provider, authorized consumers, consuming VMs, consumed/remaining quantities (CAP-014)

### 5.3 CVAL/DR Shared-Reservation Model — Two CRG Groupings per Region

> **See diagram:** `Architecture/diagrams/diagram_9_cval_dr_shared_reservation_model.png`

Building on the provider/consumer model above, the **environment-grouping** view of a region resolves to **two CRG groupings** (justified by ENV-003):

| CRG grouping | Environments | Sharing rule (ENV-003) |
|---|---|---|
| **Grouping 1 — Production** | Prod only | Prod **cannot** share with non-prod or DR → fully isolated |
| **Grouping 2 — CVAL + DR** | CVAL + DR | DR **may** share with non-prod → CVAL and DR share one grouping |

> **Reconciliation with CAP-023 (important).** "Two CRG groupings per region" is the **environment-separation abstraction**, not a literal count of two Azure CRGs. Each grouping still expands into the **regional + per-AZ CRG structure** (1 regional + one per AZ) for structural zone isolation (CAP-011/CAP-023). So a 3-zone region yields 4 CRGs *per grouping* (8 total), while the *environment* boundary is the two groupings above.

#### 5.3.1 The steady-state ↔ DR-event consumer swap

The CVAL+DR grouping holds **one shared reservation per SKU** (provider-owned) whose **consumer subscriptions swap** between steady state and a declared disaster — the reservation object itself is unchanged:

**Steady state — CVAL keeps the pool warm:**
- **CVAL consumer subscriptions** consume the shared reservation (e.g., 30 + 40 + 25 = 95 of 100 units).
- The reservation is **not idle** — CVAL is "free while running" (**DR-005**) and CVAL is treated as a DR capacity source (**ENV-004**).
- This is *why lean DR won*: an empty 30% DR reserve costs **millions/year**; keeping it warm with CVAL avoids that (**DR-003/DR-004**, cost rationale).

**DR event — DR consumers replace CVAL on the SAME reservation** (staged sequence, **DR-006**):
1. Shut down / disassociate eligible CVAL VMs (**DR-005/DR-006** step 3) → frees reserved capacity.
2. Reserved capacity returns to "available" within the same reservation (quantity **unchanged**).
3. Authorize **DR consumer subscriptions** (production failover from the failed region).
4. Deploy prod-failover VMs against the **same** reservation (e.g., 80 of 100 units).

**Sizing & accounting:**
- **max-not-sum (DR-017):** because only one region fails at a time (**DR-001**), the pool is sized to absorb the **largest single source** it protects, not the sum → shared/overcommitted capacity.
- **FIN-008:** the shared/overcommit reservation is costed **once**, not per-source; steady-state CVAL cost and DR overcommit are the *same single cost*.
- **HC-6/HC-7:** co-located CVAL must not be double-counted as both live CVAL and available DR headroom.
- **Reversible on failback (DR-013):** DR consumers released, CVAL resumes consumption of the pool.

> **ENV-003 is not violated during DR.** The CVAL/DR pool lives in the **standby** region and is classified non-prod/DR. Production failover into that region's DR capacity is the pool's intended purpose. It never co-mingles with that region's *own* isolated Production grouping — the two groupings remain separate CRGs.

---

## 6. Reconciliation & Lifecycle

### 6.1 Target Formula (CAP-003)

```
Target Reserved Capacity = Allocated (running) VM Count + Configured Buffer
```

- **Allocated** = VMs currently consuming compute (running state)
- **Associated** (deallocated) VMs do **not** drive target (CAP-004)
- **Buffer** = configurable per environment (C-2: production buffer, DR buffer)

### 6.2 Reconciliation Loop (CAP-005, CAP-006)

```
Every 6 minutes (configurable, CAP-006):
    FOR each managed CRG:
        1. Query Azure: allocated VMs, associated VMs, reserved quantity
        2. Compute: target = allocated + buffer
        3. IF reserved < target:
            → Scale-up (CAP-007): attempt increase; alert if Azure cannot supply
        4. ELSE IF reserved > target:
            → Scale-down (CAP-008): reduce toward target (right-sizing retained reservation)
        5. Validate: quota sufficient for reserved capacity (QUA-007)
        6. Log: audit event (all changes tracked)
```

**Scale-down discipline (CAP-008, CAP-009, CAP-010):**
- Scale-down is **right-sizing** → reduce reservation toward `allocated + buffer`
- May reach qty: 0 if allocated legitimately drops to 0 (normal for seed reservations)
- **Never deletes** CRG or reservation object
- Intentional retirement/deletion → requires **separate decommissioning workflow** (CAP-010): approval + impact analysis + audit

### 6.3 Reactive Discovery (CAP-024)

```
IF (new allocated VM detected for SKU/AZ not in seed matrix):
    1. Auto-create CRG (if absent) + reservation at qty: (allocated + buffer)
       → Protects production immediately
    2. Raise scope-file governance item (CAP-019)
       → Product team + budget ratification required
    3. Scope file updated within governance SLA
       → Reactive addition becomes authoritative (or decommissioned if rejected)
```

---

## 7. Quick Reference Tables

### 7.1 CRG Count per Geography

| Geography | Distribution Model | Prod Regions | CVAL Regions | DR Regions | CRGs per Env | Total CRGs (3 envs) |
|-----------|-------------------|--------------|--------------|------------|--------------|---------------------|
| **US** | 3-region | 1 | 1 (distinct) | 1 (distinct) | 4 (1 reg + 3 AZ) | 12 |
| **Europe** | 2-region | 1 | 1 (co-located with DR) | 1 (co-located with CVAL) | 4 per env | 8 (Prod: 4, CVAL+DR co-located: 4+4 same region) |
| **Australia** | 2-region | 1 | 1 (co-located with DR) | 1 (co-located with CVAL) | 4 per env | 8 |
| **Asia Pacific** | 2-region | 1 | 1 (co-located with DR) | 1 (co-located with CVAL) | 4 per env | 8 |
| **Middle East** | **[v2.4]** cross-geo DR | 1 (ME) | 1 (ME, co-located w/ Prod) | ✅ Cross-geo in weighted Europe region | 4 (Prod), 4 (CVAL), 4 (DR in Europe) | 12 |

**Note:** 4 CRGs per environment assumes 3 availability zones per region (1 regional + 3 per-AZ). Adjust for regions with different zone counts.

### 7.2 Environment Separation Matrix (ENV-003)

| | Prod | CVAL/NonProd | DR |
|---|:---:|:---:|:---:|
| **Prod** | — | ❌ Cannot share | ❌ Cannot share |
| **CVAL/NonProd** | ❌ Cannot share | — | ✅ May share (where co-located) |
| **DR** | ❌ Cannot share | ✅ May share | — |

### 7.3 Naming Pattern Quick Reference

**3-zone region example (West US 3, Production):**

```
rg-odcr-prod-wus3-01
    ├── crg-pr-wus3-reg     (regional, non-zonal SKUs)
    ├── crg-pr-wus3-az1     (zone 1)
    ├── crg-pr-wus3-az2     (zone 2)
    └── crg-pr-wus3-az3     (zone 3)
```

**2-region co-located example (Switzerland North, CVAL + DR):**

```
rg-odcr-cval-swn-01
    ├── crg-cv-swn-reg
    ├── crg-cv-swn-az1
    ├── crg-cv-swn-az2
    └── crg-cv-swn-az3

rg-odcr-dr-swn-01
    ├── crg-dr-swn-reg
    ├── crg-dr-swn-az1
    ├── crg-dr-swn-az2
    └── crg-dr-swn-az3
```

---

## 8. Related Documents

- `acrme_requirements_baseline_v2_4.md` — normative source (CAP-001..024, OPS-006, REG-001..003, ENV-003, PLC-010/010a)
- `acrme_technical_design_document.md` — TDD service/schema detail
- `acrme_hard_constraints_reference.md` — HC-1..11 (zone isolation, DR coverage floor, etc.)
- `acrme_calculation_logic_reference.md` — 15-scenario calc logic, zone distribution formula (A.9)
- `acrme_security_and_rbac_guide.md` — custom roles, least-privilege UAMI model
- `Architecture/adr/acrme_adr_002_quota_management.md` — quota two-group model (ADR-002)
- `Architecture/adr/acrme_adr_003_capacity_management_during_dr.md` — DR capacity scaling (ADR-003)

---

## 9. Revision History

| Version | Date | Change Summary |
|---------|------|----------------|
| 1.0 | 9 Sep 2026 | Initial deployment layout reference; all geographies (US 3-region, Europe/Australia/Asia Pacific 2-region co-located, Middle East DR_NOT_OFFERED); CRG structure per CAP-023; naming per OPS-006; sharing model; seed matrix; reconciliation lifecycle. |
| 1.1 | 11 Sep 2026 | **[Amended v2.4]** Middle East changed from `DR_NOT_OFFERED` to **cross-geo DR**: Prod+CVAL co-located in a weighted-selected ME region, DR placed cross-geo in a weighted-selected Europe Standard region (DR-020, PLC-010b, DEC-001 RESOLVED, A-ME1); Europe destination sizes DR max-not-sum. |

---

*End of document.*
