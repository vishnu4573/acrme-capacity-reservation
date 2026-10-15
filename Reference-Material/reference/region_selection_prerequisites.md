# Region Selection Prerequisites — Reference & Executive Briefing

**Baseline:** ACRME Requirements v4.0 (14 Oct 2026)
**Purpose:** Enumerate everything that must be in place before the region-selection engine can run, and explain the logic to a non-technical leader using concrete examples.

---

## Part 1 — Prerequisites List

Region selection is the first pipeline step that runs when a new customer is onboarded (PLC-009). Before the engine can evaluate candidate regions and produce a placement recommendation, the following inputs, configurations, data sources, and governance artefacts must exist.

---

### 1. Region Catalogue & Distribution-Model Configuration

| Prerequisite | Requirement ID | What it means |
|---|---|---|
| **Region catalogue is loaded and versioned** | REG-001 | Every Azure region the engine can consider must be registered in a configuration source with its class (Standard or Restricted), geography, zone count, and flags (e.g. `DR_NOT_OFFERED`). |
| **Distribution model is assigned per geography** | REG-003 | Each geography must have a configured distribution model — 3-region (US), 2-region co-located (EU/AU/AP), or cross-geography DR (ME) — so the engine knows how many regions it is filling and whether CVAL/DR co-locate. |
| **Restricted regions flagged** | REG-001 | Restricted regions (e.g. East US 2) are excluded from auto-selection unless the customer explicitly names one via the exact-region path. The flag must be in the catalogue. |

**Executive version:** *Think of this as the "menu of available locations." Before the engine can recommend where to put a customer, someone must have published the approved list of Azure regions we operate in, and tagged each geography with the layout pattern it uses (does it get three separate regions, two, or a cross-border arrangement?).*

**Example:** For Europe, the catalogue says: geography = Europe, model = 2-region, standard regions = Switzerland North + Sweden Central, restricted = North Europe + West Europe. Without this entry the engine literally does not know Europe exists.

---

### 2. Environment Policy Configuration

| Prerequisite | Requirement ID | What it means |
|---|---|---|
| **Environment separation rules loaded** | ENV-003 | The engine must know: Prod never shares capacity with NonProd or DR; DR may share with NonProd; co-location in a region is allowed but shared CRGs are not. |
| **DR bootstrap policy defined (not a fixed percentage)** | ENV-005 | A configurable DR target per workload/product/region must be set. The engine cannot size DR without it. Fixed percentages (e.g. "30–40% of Prod") are explicitly rejected. |
| **DR-zero policy explicit** | ENV-006 | If a workload has zero DR, that must be an explicit approved-policy decision, not an absent value. |

**Executive version:** *These are the "rules of the house." Before placing anyone, the engine needs to know which environments are allowed to share space and how much DR capacity to hold. We do not use a flat percentage for DR — every workload gets a right-sized bootstrap target agreed with the product team.*

**Example:** The policy says domain TMS gets a DR bootstrap target of X VMs per SKU per AZ (configurable, not a blanket "40%"). Without this policy the engine cannot score DR regions because it does not know how much DR capacity to look for.

---

### 3. Capacity Data (per Region × Environment)

| Prerequisite | Requirement ID | What it means |
|---|---|---|
| **Reserved capacity known** | CAP-003 | For each region and environment the engine needs: total reserved VMs, allocated (running) VMs, associated VMs, available (free) reserved capacity, and the configured buffer. |
| **Capacity freshness within max age** | RDY-004 | The snapshot must not be older than the configured maximum staleness. Stale data → engine refuses to run (`STALE_STATE`). |
| **Seed matrix populated** | CAP-022 | The set of managed SKU × AZ combinations must be seeded (even at count 0) so the engine knows which SKUs are eligible in each zone. |

**Executive version:** *This is the "how full are the shelves" data. The engine checks every candidate region to see how much capacity is reserved, how much is used, and how much is free. If the data is too old, the engine stops rather than making a decision on stale numbers.*

**Example — from the mock exercise:**

| Region | Prod Reserved | Prod Allocated | Prod Free | NP Reserved | NP Allocated | NP Free |
|---|---|---|---|---|---|---|
| West US 3 | 100 | 78 | 22 | 60 | 38 | 22 |
| Central US | 80 | 55 | 25 | 50 | 25 | 25 |
| Canada Central | 60 | 40 | 20 | 40 | 20 | 20 |

The engine reads these numbers to compute headroom scores. If the "Prod Reserved" column is empty for a region, that region cannot be scored.

---

### 4. Quota Data (per Region × VM-Family)

| Prerequisite | Requirement ID | What it means |
|---|---|---|
| **Quota limits and usage known** | QUA-002 | Per region and VM family: total quota limit, current quota usage, available quota. Both the VM-family cap and the total regional vCPU cap must be present. |
| **Central quota group defined** | QUA-015 | In the multi-domain model, quota is drawn from a customer-scoped central pool spanning all domain subscriptions. This pool must exist and its limits must be loaded. |
| **Quota freshness within max age** | RDY-004 | Same freshness rule as capacity data. |

**Executive version:** *Quotas are Azure's spending limits — Microsoft controls how many VMs of each type you can run in each region. The engine must know the current limits and how much is already used. If the numbers are stale, it stops.*

**Example:** Region Switzerland North has a quota limit of 500 vCPUs for the Eads_v5 family. Current usage is 380 vCPUs. Available = 120 vCPUs. The customer wants to deploy 10 × E32ads_v5 = 320 vCPUs. The engine checks: 120 < 320, so this region may fail the quota gate. Without the quota data the engine cannot make that check.

---

### 5. Hard Constraint Gate Inputs

| Prerequisite | Requirement ID | What it means |
|---|---|---|
| **Geography containment** | HC-8 | The engine must know which geography the customer belongs to, so it only considers regions in that geography (plus the cross-geo DR path for Middle East). |
| **Region class filter** | HC-9 | Standard vs Restricted flag per region (from the catalogue). |
| **Zone availability data** | HC-5 | The number of availability zones per region must be known. Regions with no zones are excluded for zonal workloads. |
| **Capacity floor threshold** | HC-2 | A minimum free-capacity threshold must be configured. Regions below this floor are eliminated before scoring. |
| **Quota floor threshold** | HC-3 | A minimum available-quota threshold must be configured. Checked separately for Prod, NonProd, and DR. |
| **DR coverage floor** | HC-6 | The combined CVAL + DR pool in a region must meet a minimum DR coverage threshold. |
| **DR floor integrity** | HC-7 | The DR earmark within the NonProd+DR pool must not be cannibalised by NonProd placement. |
| **Cross-geo approval flag** | HC-10 | For Middle East cross-geo DR: an approved extension path must be recorded. |
| **Availability-Set exclusion** | HC-11 | VMs in Availability Sets are ineligible for reservations (onboarding precondition, CAP-020/021). |

**Executive version:** *Before the engine even scores a region, it runs a set of pass/fail safety checks — like airport security before boarding. Each check has a threshold or rule. If ANY check fails for a region, that region is eliminated entirely — it does not get a lower score, it gets no score at all.*

**Example — HC-3 Quota Floor in action:**

Suppose the Prod quota floor threshold is 10% free. Region Canada Central has 400 vCPU limit and 390 used → only 2.5% free. **Result: Canada Central is eliminated for Prod** — it never reaches the scoring step.

Meanwhile Central US has 500 limit, 350 used → 30% free → passes. West US 3 has 600 limit, 450 used → 25% free → passes. Only Central US and West US 3 proceed to scoring for Prod.

---

### 6. Placement Policy & Scoring Weights

| Prerequisite | Requirement ID | What it means |
|---|---|---|
| **Weight vector loaded and validated** | PLC-007, C-10 | The scoring weights (α capacity headroom, β quota headroom, γ fairness, δ DR readiness, ε zone diversity) must be configured and must sum to 1.0. If the sum ≠ 1.0, the engine rejects the policy at load time. |
| **Weights defined per environment** | PLC-007 | Prod, CVAL, and DR use different weight vectors (e.g. DR gives more weight to DR readiness δ). |
| **Headroom thresholds** | C-10 | Thresholds for "good" vs "poor" headroom that normalise the raw ratios into 0–1 scores. |
| **Total customers count available** | PLC-012 | The γ fairness denominator requires a live count of distinct customers in the geography. Must be derivable from the placement-state database. |

**Executive version:** *These are the "judging criteria and their importance." The engine scores each region on five factors — like judges in a competition. Each factor gets a weight (e.g. capacity headroom might be 30%, quota headroom 25%, fairness 15%, DR readiness 15%, zone spread 15%). The weights must be set before the engine runs, and they must add up to 100%.*

**Example — from the mock exercise Policy sheet:**

| Factor | Prod Weight | CVAL Weight | DR Weight |
|---|---|---|---|
| α — Capacity headroom | 0.30 | 0.30 | 0.25 |
| β — Quota headroom | 0.25 | 0.25 | 0.20 |
| γ — Customer fairness | 0.15 | 0.15 | 0.15 |
| δ — DR readiness | 0.15 | 0.15 | 0.25 |
| ε — Zone diversity | 0.15 | 0.15 | 0.15 |
| **Total** | **1.00** | **1.00** | **1.00** |

If someone loads a policy where Prod weights sum to 0.95, the engine refuses to start.

---

### 7. Customer & Domain Inputs

| Prerequisite | Requirement ID | What it means |
|---|---|---|
| **Customer identity** | PLC-003 | A customer/realm identifier must be provided. |
| **Geography** | PLC-001/002 | The customer's target geography must be specified (always required). |
| **Production region (exact-region path)** | PLC-001 | If using the default onboarding path, the exact Prod region must be supplied. The engine does not guess it. |
| **Exception approval (geography path)** | PLC-002 | If the customer provides only a geography (no exact region), an explicit exception approval and customer acknowledgement must be on file. |
| **VM SKU and count** | PLC-007 | The SKU family and number of VMs the customer needs to deploy. Required for the demand-against-capacity checks. |
| **Domain group(s) identified** | DOM-001 | Which domain groups (e.g. TMS, WMS) the customer operates. Required for the DPB step but influences the CRV only via aggregate customer counts. |
| **Existing seed record (if any)** | PLC-003/004 | If the customer already has a seed record for this geography, the engine reuses it instead of re-running selection. The seed database must be checked. |

**Executive version:** *This is the "customer request form." The engine needs to know: Who is the customer? Where do they want to be (geography, and ideally the exact region)? What are they deploying (VM type and quantity)? And have we placed them before?*

**Example:** Customer "Contoso" requests onboarding in the US geography. They specify West US 3 as their production region and need 20 × E32ads_v5 VMs. The engine takes these inputs, validates West US 3 against the hard constraints, then scores Central US and Canada Central for CVAL and DR placement.

If Contoso later adds a second domain group (WMS), the engine does NOT re-run region selection — it reads Contoso's existing seed record and places WMS in the same regions, with its own separate subscriptions and CRGs (PLC-004).

---

### 8. CRG Structure & Subscription Setup

| Prerequisite | Requirement ID | What it means |
|---|---|---|
| **Domain subscriptions provisioned** | DOM-002 | Each domain × environment needs its own subscription (or shard), provisioned before the DPB can bind capacity. |
| **CRG sets created in Azure** | CAP-025, CAP-002 | The Prod CRG set, CVAL/DR shared CRG set, and DR Foundation CRG set must exist in Azure before the engine activates them in config. Azure resource first, config second — never the reverse. |
| **Naming convention applied** | OPS-006, C-12 | CRGs, subscriptions, and reservations must follow the naming convention so the engine can parse domain, environment, and region from the name. |

**Executive version:** *Before the engine can actually reserve capacity, the "shelves" (Azure resource groups and reservations) must physically exist. You cannot put inventory on a shelf that has not been built yet. And they must be labelled correctly so the engine knows which shelf belongs to which team and environment.*

---

### 9. Governance & Approval Artefacts

| Prerequisite | Requirement ID | What it means |
|---|---|---|
| **Scope file authorising managed resources** | CAP-001 | Only resources declared in the scope file are managed. The engine ignores everything else. |
| **Budget approval for seed matrix** | CAP-022 | Populating the seed matrix of SKU × AZ combinations requires product-team budget sign-off. |
| **DR-not-offered country flags** | DR-014 | If certain countries have a legal carve-out from DR, that must be flagged so the engine assigns no DR region for those customers. |
| **Migration/exception workflow available** | PLC-005 | The engine does not change seeds. If a customer needs to move regions, the migration workflow must exist. Without it, a bad initial placement is permanent. |

**Executive version:** *These are the "permissions and approvals." The engine only touches resources it has been told to manage. Budget must be approved before it reserves anything. Legal restrictions on DR must be recorded. And there must be a process for moving a customer if the initial placement turns out wrong.*

---

### 10. Pipeline Infrastructure

| Prerequisite | Requirement ID | What it means |
|---|---|---|
| **AEP trigger mechanism** | PLC-009 | The Automated Enrolment Process must be able to invoke the region-selection function app via API or GitHub Actions. |
| **State database for seed records** | DAT-002 | A persistent store for seed records, CRVs, DPBs, and customer placement state. |
| **Reconciliation job running** | CAP-005/006 | The capacity reconciliation job (≈ every 6 minutes) must be active so capacity data stays fresh. |
| **Alerting configured** | OBS-001/002 | The engine raises alarms when capacity is insufficient (CAP-007) or zones are skewed (PLC-011). Alert channels must be wired. |

**Executive version:** *The engine itself must be up and running — the trigger that starts it, the database that stores decisions, the background job that keeps capacity numbers fresh, and the alerting system that notifies people when something is wrong.*

---

## Part 2 — Executive Briefing: How Region Selection Works (Plain English)

### The Analogy: Assigning Office Space to New Tenants

Imagine you manage a company with five office campuses across different cities (geographies): one in the US, one in Europe, one in Australia, one in Asia Pacific, and one in the Middle East.

Each campus has 2–3 buildings (Azure regions). When a new business unit (customer) joins, you need to assign them:
- A **main office** (Production) — where they do their daily work.
- A **test lab** (CVAL/NonProd) — where they try new things.
- A **backup office** (DR) — where they go if the main office has a fire.

#### Before You Can Assign Anything, You Need:

1. **A map of your buildings** — which buildings exist, which are open for new tenants, and which are restricted. *(Region Catalogue)*

2. **Current occupancy data** — how many desks are reserved, how many are in use, how many are free in each building. If your occupancy report is a week old, you refuse to make assignments until you get a fresh one. *(Capacity & Quota Data, Freshness)*

3. **House rules** — the main office and test lab cannot share the same floor (safety regulation). The backup office can share with the test lab but never with the main office. *(Environment Separation — ENV-003)*

4. **Safety checks** — before sending anyone to a building: Is it in the right city? Does it have enough free desks? Is the fire escape (DR) big enough? Does it have the right number of floors (zones)? If any check fails, that building is off the list entirely. *(Hard Constraints)*

5. **Scoring criteria** — once the unsafe buildings are eliminated, you score the remaining ones: How much spare desk space? (capacity headroom) How much room under the lease cap? (quota headroom) Is the building already too crowded with tenants? (fairness) Could the backup handle an emergency? (DR readiness) Are tenants spread evenly across floors? (zone diversity) *(Placement Weights)*

6. **The tenant's request form** — who they are, which city they want, which building specifically (or "just put me in the US, you choose"), and how many desks they need. *(Customer Inputs)*

7. **The filing cabinet** — once you assign someone, the decision is recorded permanently and reused. If the same tenant adds a new department, they go to the same buildings — you do not re-run the whole process. *(Seed Record, CRV reuse)*

---

### Walkthrough: Placing "Contoso" in the US

**Contoso submits their request:**
- Geography: US
- Production region: West US 3 (they specified it — exact-region path)
- SKU: E32ads_v5
- VMs needed: 20

**Step 1 — Check prerequisites are met:**
✅ Region catalogue loaded: US has 3 Standard regions (West US 3, Central US, Canada Central)
✅ Distribution model: 3-region (US) — Prod, CVAL, and DR each get a separate region
✅ Capacity data: fresh (last refreshed 4 minutes ago, within the 15-minute max)
✅ Quota data: loaded for all 3 regions
✅ Hard constraint thresholds: configured
✅ Scoring weights: loaded, sum = 1.0 for all three environments
✅ No existing seed record for Contoso in US

**Step 2 — Validate the supplied Prod region (West US 3):**
- HC-8 Geography containment: West US 3 is in the US ✅
- HC-9 Standard region: West US 3 is Standard ✅
- HC-5 Zone availability: West US 3 has 3 zones ✅
- HC-2 Capacity floor: West US 3 has 22 free Prod VMs, above the floor ✅
- HC-3 Prod quota floor: sufficient available vCPUs ✅

West US 3 is validated as the Prod region. It is not scored — it is an input constant.

**Step 3 — Score the remaining regions for CVAL and DR:**
The engine considers Central US and Canada Central (West US 3 is taken by Prod, and HC-1 REGION_SEPARATION eliminates it from CVAL/DR).

For each candidate region, the engine:
1. Runs the hard constraint gate (HC-2, HC-3, HC-5, HC-6, HC-7)
2. If the region passes all gates, computes the five scoring factors
3. Multiplies each factor by its weight and sums to get a final score

| Factor | Central US Score | Canada Central Score |
|---|---|---|
| α capacity headroom (×0.30) | 0.83 × 0.30 = 0.249 | 0.67 × 0.30 = 0.201 |
| β quota headroom (×0.25) | 0.75 × 0.25 = 0.188 | 0.60 × 0.25 = 0.150 |
| γ fairness (×0.15) | 0.90 × 0.15 = 0.135 | 0.95 × 0.15 = 0.143 |
| δ DR readiness (×0.15) | 0.70 × 0.15 = 0.105 | 0.80 × 0.15 = 0.120 |
| ε zone diversity (×0.15) | 0.85 × 0.15 = 0.128 | 0.75 × 0.15 = 0.113 |
| **Total** | **0.805** | **0.727** |

Central US wins CVAL. For DR, the scoring uses DR-specific weights and component formulas (δ gets higher weight at 0.25), and Canada Central might score higher on DR readiness. Suppose Canada Central wins DR.

**Step 4 — Write the seed record:**

```
CRV(Contoso, US) = {
    geography:    US
    model:        3-region
    prod_region:  West US 3
    cval_region:  Central US
    dr_region:    Canada Central
}
```

This record is permanent. When Contoso later adds domain group WMS alongside TMS, the engine reads this CRV — it does not re-run region selection. WMS gets its own subscriptions and CRGs in the same three regions.

---

### How Does This Change for Europe? (2-Region Model)

**Customer "Fabrikam" onboards in Europe:**
- Geography: Europe
- Production region: Switzerland North (exact-region path)
- Standard regions available: Switzerland North, Sweden Central

**Key difference:** Europe uses the 2-region model. Once Prod takes Switzerland North, only Sweden Central remains. There is no choice to make — CVAL and DR both go to Sweden Central automatically (PLC-010a).

The engine still runs the hard constraint gate on Sweden Central:
- HC-6 DR coverage floor: Is the combined CVAL+DR pool in Sweden Central large enough? ✅
- HC-7 DR floor integrity: Will placing CVAL there not eat into the DR earmark? ✅

If Sweden Central fails either check, placement stops with an error — there is no fallback region.

```
CRV(Fabrikam, EU) = {
    geography:    Europe
    model:        2-region
    prod_region:  Switzerland North
    cval_region:  Sweden Central
    dr_region:    Sweden Central    ← CVAL/DR co-located
}
```

**Executive version:** *In Europe we only have two buildings. One is the main office, and the other automatically becomes both the test lab and the backup office. We just check that the second building is big enough to handle both roles.*

---

### How Does This Change for Middle East? (Cross-Geography DR)

**Customer "Adatum" onboards in Middle East:**
- Geography: Middle East
- Production region: Saudi Arabia Central (exact-region path)

**Key difference:** Middle East uses the cross-geography DR model (PLC-010b). Prod and CVAL both go to the local Middle East region (separate CRGs — they share the building but not the floor). DR goes to a selected Europe region.

The engine:
1. Validates Saudi Arabia Central for Prod ✅
2. Places CVAL in Saudi Arabia Central alongside Prod (separate CRGs per ENV-003) — no scoring needed, it is co-located
3. Scores Europe's Standard regions (Switzerland North, Sweden Central) for DR using the DR-specific scoring weights
4. Suppose Sweden Central wins the DR score

```
CRV(Adatum, ME) = {
    geography:    Middle East
    model:        cross-geo
    prod_region:  Saudi Arabia Central
    cval_region:  Saudi Arabia Central    ← co-located with Prod
    dr_region:    Sweden Central          ← cross-geo, in Europe
    dr_geography: Europe
}
```

**Executive version:** *In the Middle East, we only run a main office and test lab locally. The backup office is in Europe — because the Middle East campus does not have enough buildings to keep a backup separate. The engine picks the best European building for the backup using the same scoring process.*

**Important nuance for leaders:** In this model, the CVAL-sacrifice DR bootstrap (where the test lab's capacity is released to the backup office during an emergency) does NOT apply. The Middle East backup office has its own dedicated reserved capacity in Europe. This costs more but avoids the complexity of cross-border capacity handoffs.

---

### What Happens If a Prerequisite Is Missing?

| Missing Item | Engine Behaviour | Business Impact |
|---|---|---|
| Region catalogue not loaded | Engine cannot start | No customers can be onboarded |
| Capacity data is stale | Engine returns `STALE_STATE` and refuses to run | Onboarding delayed until data refreshes |
| Quota data missing for a region | That region fails HC-3 | Region excluded from candidacy — may force a suboptimal placement |
| DR bootstrap target not set | Engine cannot size DR | DR region selected but no capacity reserved — DR is paper-only |
| Scoring weights do not sum to 1.0 | Engine rejects policy at load time | All onboarding blocked until weights are fixed |
| No seed database | Engine cannot store decisions | Placements are ephemeral — every domain group triggers a new selection, risking inconsistency |
| Customer already has a seed | Engine skips selection and reuses CRV | Normal behaviour — not an error. New domain groups get the existing regions. |

---

### Summary for the Leadership Conversation

> **"Before we can tell a customer where their systems will run, we need five things in place:**
>
> 1. **A published map** of approved Azure regions and their layout patterns.
> 2. **Fresh numbers** on how full each region is — capacity and quota, updated every few minutes.
> 3. **Safety rules** that eliminate any region that does not meet minimum standards.
> 4. **Judging criteria** with agreed weights so the engine picks the best option objectively.
> 5. **The customer's request** — who they are, where they want to be, and what they are deploying.
>
> Once all five are in place, the engine runs a two-step process: eliminate the unsafe options, then score the survivors. The winning combination is recorded permanently and reused for every future deployment by that customer in that geography. The whole process takes seconds, but the prerequisites take planning."

---

*Document generated from ACRME Requirements Baseline v4.0, Hard Constraints Reference v1.1, and the Region Selection WHAT-IF mock exercise. All requirement IDs trace to the baseline; all example numbers are illustrative and derived from the mock exercise data structure.*

---

## Part 3 — Domain Placement Binding (DPB) Prerequisites

The DPB is the **second phase** of the two-scope architecture (PLC-015). After the CRV determines which regions a customer uses, the DPB binds each **domain group's** capacity in those regions. The DPB is deterministic — it does not score or weight regions. The region is a given (from the CRV); the DPB resolves subscriptions, CRG sets, reservation sizing, zone distribution, and quota draw.

### DPB-Specific Prerequisites

| # | Prerequisite | Requirement ID | What it means |
|---|---|---|---|
| D1 | **CRV resolved and cached** | PLC-015 | The DPB cannot run until a CRV exists for this customer × geography. The CRV is resolved once and cached; the DPB reads it. |
| D2 | **Domain group taxonomy loaded** | DOM-001, C-14 | The system must know which domain groups the customer operates (e.g. TMS, WMS) and their `wl-*` tokens. |
| D3 | **ig subscription provisioned per (domain × environment × region)** | DOM-002, C-12 | Each domain needs its own subscription in each environment and region. E.g. `sub-jda-cld-cr-prod-wl-tms-wus2-01` for TMS Prod in West US 3. |
| D4 | **Shard registry available** | DOM-002/003 | When a domain exceeds single-subscription limits, the shard registry maps the domain to its next available ig shard. |
| D5 | **CRG sets created in Azure per CAP-025** | CAP-025, CAP-002 | Three CRG set types must exist per (domain × environment × region): Prod-dedicated (`crg-pr-*`), CVAL/DR shared (`crg-cvdr-*`), and DR Foundation (`crg-drf-*`). Azure resources first, then config — never the reverse. |
| D6 | **Seed matrix populated** | CAP-022 | The SKU × AZ matrix must be seeded (even at count 0) in each CRG so the reconciliation engine has a baseline to scale from. Budget approval required. |
| D7 | **Per-domain capacity data loaded** | F.1–F.3 | For each (domain × environment × region): allocated VMs, reserved quantity, and configured buffer. The DPB computes Target Reserved = Allocated + Buffer. |
| D8 | **Zone count known per region** | CAP-023, HC-5 | The DPB computes Target VMs per Zone = round(VMs / ZoneCount). Zone count must be in the catalogue. |
| D9 | **Skew tolerance configured** | PLC-011, C-13 | The rebalancing trigger threshold must be set so the DPB can detect when a domain's zone distribution exceeds tolerance. |
| D10 | **Central quota group defined** | QUA-015 | The customer's central quota pool must exist, spanning all domain subscriptions. Quota is drawn per region × VM-family cell. |
| D11 | **Quota replenishment thresholds set** | QUA-015 | Group-level (85%) and subscription-level (85%) replenishment thresholds must be configured. When utilisation reaches these levels, proactive quota requests are triggered. |
| D12 | **Naming convention enforced** | OPS-006, C-12 | Subscriptions, CRGs, and reservations must follow the naming convention so the engine can parse domain token, environment, region, and zone from the name. |
| D13 | **DR Foundation CRG set created** | DR-021, CAP-025 | Dedicated DR bootstrap CRGs (`crg-drf-*`) must exist with pre-staged quota, sized per ENV-005/DR-007. These are always present and never shared with CVAL until an approved DR declaration triggers CVAL release. |
| D14 | **Combined-load observation configured** | PLC-016, OBS-001/002, C-15 | The region-level combined zone load across all domains (`RegionZoneLoad`) must be wired to observability/alerting. This is read-only — it never triggers cross-domain reservation actions. |

### CRV → DPB Handoff

```
CRV(C, G) resolved
  ↓
For each domain D ∈ customer's domain groups:
  For each environment E ∈ {Prod, CVAL, DR}:
    R ← CRV(C,G).E                       # region is pre-bound
    ig ← Lookup(C, D, E, R)              # subscription resolution (D3/D4)
    CRG_set ← CAP-025 per-domain sets    # Prod | CVDR | DRF (D5)
    TargetReserved ← Allocated + Buffer   # F.1 (D7)
    Deficit ← max(0, Target − Reserved)  # F.3 — triggers reconciliation
    TargetPerZone ← round(VMs / ZoneCount) # F.9 (D8)
    MaxSkew ← max |actual − target| per zone
    if MaxSkew > SkewTolerance → rebalance recommendation (D9)
    AvailableQuota ← min(VM-family cap, regional cap) of ig  # F.4 (D10)
    QuotaDeficit ← max(0, Requested − Available)  # F.5
    if quota utilisation ≥ 85% → replenishment trigger (D11)
```

---

### Worked DPB Example: Contoso — Domain TMS in US (3-Region)

**Given:** Contoso's CRV has already been resolved:

```
CRV(Contoso, US) = {
    geography:    US
    model:        3-region
    prod_region:  West US 3
    cval_region:  Central US
    dr_region:    Canada Central
}
```

Contoso operates two domain groups: **TMS** and **WMS**. We walk through the DPB for domain **TMS**.

#### Step 1 — Resolve ig subscriptions (DOM-002)

For each (domain × environment × region), the naming convention (C-12) determines the subscription:

| Domain | Environment | Region | Subscription Name |
|---|---|---|---|
| TMS | Prod | West US 3 | `sub-jda-cld-cr-prod-wl-tms-wus3-01` |
| TMS | CVAL | Central US | `sub-jda-cld-cr-cval-wl-tms-cus-01` |
| TMS | DR | Canada Central | `sub-jda-cld-cr-dr-wl-tms-cac-01` |

If the shard `-01` is at capacity, the shard registry (DOM-003) points to `-02`.

#### Step 2 — Verify CRG sets exist (CAP-025)

For TMS in West US 3 (Prod):

| CRG Set Type | CRG Name Pattern | Zones | Purpose |
|---|---|---|---|
| Prod dedicated | `crg-pr-wus3-az1`, `crg-pr-wus3-az2`, `crg-pr-wus3-az3` | 1, 2, 3 | Production reservations only |

For TMS in Central US (CVAL):

| CRG Set Type | CRG Name Pattern | Zones | Purpose |
|---|---|---|---|
| CVAL/DR shared | `crg-cvdr-cus-az1`, `crg-cvdr-cus-az2`, `crg-cvdr-cus-az3` | 1, 2, 3 | CVAL and DR capacity share this set (ENV-003: DR may share with non-prod) |
| DR Foundation | `crg-drf-cus-zonal` | All | Standing bootstrap capacity, always present |

For TMS in Canada Central (DR):

| CRG Set Type | CRG Name Pattern | Zones | Purpose |
|---|---|---|---|
| CVAL/DR shared | `crg-cvdr-cac-az1`, `crg-cvdr-cac-az2`, `crg-cvdr-cac-az3` | 1, 2, 3 | DR capacity (may host some CVAL if approved) |
| DR Foundation | `crg-drf-cac-zonal` | All | Standing bootstrap capacity |

**Critical:** These Azure resources must already exist (CAP-002). The DPB does not create them — it validates and binds to them.

#### Step 3 — Compute reservation targets (F.1–F.3)

TMS Prod in West US 3 — SKU E32ads_v5:

| Metric | Value | Source |
|---|---|---|
| Allocated VMs | 20 | Live Azure state |
| Buffer (configured) | 4 | Scope file: 20% buffer for E32ads_v5 in WUS3 |
| **Target Reserved** | **24** | F.1: 20 + 4 |
| Current Reserved | 18 | Azure CRG state |
| **Deficit** | **6** | F.3: max(0, 24 − 18) = 6 |
| **Headroom** | **−2** | F.2: 18 − 20 = −2 (reservation behind demand) |

→ Reconciliation action: increase reservation by 6 VMs to reach target of 24.

TMS CVAL in Central US — same SKU:

| Metric | Value | Source |
|---|---|---|
| Allocated VMs | 8 | Live Azure state |
| Buffer | 2 | Scope file |
| **Target Reserved** | **10** | F.1: 8 + 2 |
| Current Reserved | 10 | Azure CRG state |
| **Deficit** | **0** | F.3: max(0, 10 − 10) = 0 |
| **Headroom** | **2** | F.2: 10 − 8 = 2 |

→ No action needed. CVAL is at target.

#### Step 4 — Zone distribution (F.9, PLC-016)

TMS Prod in West US 3 (3 zones, 20 VMs):

| Zone | Target VMs | Actual VMs | Skew |
|---|---|---|---|
| AZ1 | round(20/3) = 7 | 9 | +2 |
| AZ2 | 7 | 6 | −1 |
| AZ3 | 6 | 5 | −1 |
| **Max Skew** | | | **2** |

If skew tolerance (C-13) is configured at 2, this is at the boundary. The next deployment would:
- Target AZ2 (most under-represented) for the new VM
- If it pushes AZ1 skew to +3, raise a rebalancing recommendation

**Combined-load observation** (PLC-016): If WMS also has 12 Prod VMs in West US 3 (5/4/3 across zones), the combined load is:

| Zone | TMS | WMS | Combined |
|---|---|---|---|
| AZ1 | 9 | 5 | 14 |
| AZ2 | 6 | 4 | 10 |
| AZ3 | 5 | 3 | 8 |

This combined view is reported to observability (OBS-001/002) but **never triggers cross-domain reservation actions**. TMS and WMS each manage their own zone balance independently.

#### Step 5 — Quota draw (F.4–F.5, QUA-015)

TMS Prod ig subscription in West US 3:

| Quota Metric | Value | Source |
|---|---|---|
| VM-family cap (Eads_v5) | 300 vCPU | Azure subscription quota |
| Current usage | 640 vCPU (20 × 32 vCPU) | Live Azure state |
| **Available** | **−340 vCPU** | F.4: 300 − 640 (deficit!) |
| Total regional vCPU cap | 2,000 vCPU | Azure subscription quota |
| Current regional usage | 1,200 vCPU | Live Azure state |
| Regional available | 800 vCPU | 2,000 − 1,200 |

Wait — the VM-family cap is 300 but usage is already 640? This means quota was previously increased from the central pool but the cap shown is the subscription-level assignment. The central quota group (QUA-015) holds the actual entitlement:

| Central Pool Metric | Value |
|---|---|
| Total pool: Eads_v5 in West US 3 | 1,500 vCPU |
| Allocated across all domain subs | 1,100 vCPU |
| Available in pool | 400 vCPU |
| TMS Prod subscription utilisation | 640 / 1,500 = 42.7% |
| Pool utilisation | 1,100 / 1,500 = 73.3% |

Pool utilisation is below the 85% replenishment threshold → no proactive quota request yet. But if the next domain's DPB pushes it to 86%, the replenishment trigger fires.

#### Step 6 — DPB record written

```
DPB(TMS, Prod) = {
    domain:       TMS (wl-tms)
    environment:  Prod
    region:       West US 3          ← from CRV
    ig:           sub-jda-cld-cr-prod-wl-tms-wus3-01
    crg_set:      crg-pr-wus3-*      (Prod dedicated)
    target_reserved: 24 VMs (E32ads_v5)
    deficit:      6 VMs              ← reconciliation action
    zone_target:  7/7/6 across AZ1/2/3
    quota_pool:   central Eads_v5 WUS3 cell
    status:       READY_WITH_RISK (reservation deficit being reconciled)
}
```

The same DPB resolution runs for TMS CVAL (Central US) and TMS DR (Canada Central), then repeats for domain WMS — all using the same CRV regions but with WMS's own subscriptions, CRG sets, and capacity targets.

---
