# ACRME End-to-End Deployment Flow

**Customer Onboarding → Placement → Service Deployment → Readiness → Steady State → DR**

| | |
|---|---|
| **Document version** | 1.0 |
| **Date** | 17 November 2026 |
| **Requirements baseline** | v4.0.2 (17 Nov 2026) |
| **Hard Constraints reference** | v1.1 (HC-1..HC-11) |

> This document traces a customer deployment from first contact to production-live and through DR activation. Every gate and check is cited to its normative requirement.

---

## Ownership Summary

| Function | Owner | Point in Flow |
|----------|-------|---------------|
| Customer exists check | Onboarding / upstream workflow | Beginning |
| Geography selection | Customer / onboarding | Beginning |
| Prod / Non-Prod / DR region selection | Placement engine | Placement |
| Capacity / reservation validation | Capacity / placement engine | Placement |
| Regional PIN | Placement engine | Placement |
| Persist customer placement | Platform workflow / system of record | After placement |
| Instance Group definition | **Service Owner** | **Service domain** |
| Instance Group selection | **Service deployment automation** | **During service deployment** |
| Instance Group provisioning / scaling | **Product / Service DevOps pipeline** | **Service lifecycle** |
| Service ↔ Instance Group registration | Service deployment / registration | Post-deployment |
| Central visibility | Gravity | Global system of record |

> **Ownership boundary (v4.0.1):** Region placement and the capacity envelope (CRV + DPB) are **inputs** to service deployment, decided by the Placement Engine. Instance Group is an **output** of service deployment, decided by the Service Owner / Product Automation. Service → IG association is registered in Gravity after deployment.

---

## Phase 0 — Commercial / Customer Onboarding

### Step 0.1 — Customer Exists Check

| Item | Detail |
|------|--------|
| **Owner** | Onboarding / upstream workflow |
| **Action** | Determine if the customer already has a seed record (PLC-003) |
| **Check** | Query the authoritative state store (DAT-001) for existing seed |
| **If exists** | Fetch CRV from cached seed — skip to Phase 2 (DPB) |
| **If new** | Proceed to Step 0.2 |

### Step 0.2 — Geography Selection

| Item | Detail |
|------|--------|
| **Owner** | Customer / onboarding |
| **Action** | Determine the customer's geography from the region catalogue (REG-001) |
| **Input** | Customer's business location, legal requirements, data residency |
| **Output** | Geography code (US, EU, AU, APAC, ME) → determines distribution model (REG-003) |
| **Config** | Region catalogue is configuration-driven and versioned (REG-001) |

**Distribution model selected here:**

| Geography | Model | Behaviour |
|-----------|-------|-----------|
| US | `three_region` | Prod, CVAL, DR each in a distinct region |
| EU, AU, APAC | `two_region` | Prod in one region; CVAL + DR co-locate in the other (PLC-010a) |
| ME | `cross_geography_dr` | Prod + CVAL co-locate in ME; DR cross-geo in Europe (PLC-010b, DR-020) |

---

## Phase 1 — CRV Resolution (Customer Region Vector)

**Scope:** Customer × Geography — resolved **once**, cached, reused by all domain groups (PLC-013, PLC-015).

**Owner:** Placement Engine (Capacity & Placement Team).

**Trigger:** AEP intent for a new customer, or first deployment in a new geography (PLC-009).

### Step 1.1 — Candidate Set Formation (Pre-Filtering)

Before any scoring, the region catalogue is filtered down to eligible candidates.

| Gate | ID | Type | Check | Fail action |
|------|----|------|-------|-------------|
| Geography containment | **HC-8** | Hard constraint | Region must belong to the customer's selected geography | Exclude from candidates |
| Standard region only | **HC-9** | Hard constraint | Only Standard-class regions are eligible for engine selection; Restricted regions require approved exception (EC-1..EC-4) | Exclude from candidates |

**Output:** candidate set of Standard regions within the geography.

### Step 1.2 — Hard Constraint Gate (Binary Pass/Fail)

Every candidate region is tested against the full HC gate. Any failure eliminates the region entirely — it is never penalised with a lower score.

| Gate | ID | Type | What it checks | Scope |
|------|----|------|----------------|-------|
| Region separation | **HC-1** | Hard constraint | Prod ≠ DR region; Prod ≠ CVAL region; CVAL/DR co-location only under approved policy | Per environment pair |
| Capacity floor | **HC-2** | Hard constraint | Region has sufficient reservable capacity to meet minimum demand + buffer | Per region |
| Quota floor | **HC-3** | Hard constraint | Region has sufficient quota headroom (VM-family vCPU + total regional vCPU) after protecting Prod floor and DR earmark | Per region |
| DR separation class | **HC-4** | Hard constraint | DR region class ≥ Prod region class; DR never in a "lesser" region than Prod | Per DR candidate |
| Zone availability | **HC-5** | Hard constraint | Region must have ≥ 1 availability zone (az_count ≥ 1); 0-AZ regions are ineligible for zonal CRG placement (CAP-011) | Per region |
| DR coverage floor | **HC-6** | Hard constraint | Destination region can absorb the domain's protected Prod portion for DR; combined CVAL+DR capacity in a co-located region is sufficient | Per DR destination |
| DR floor integrity | **HC-7** | Hard constraint | DR floor within the quota group is not consumed by NonProd placement; NonProd placement that would breach the DR earmark is blocked | Per NonProd placement |
| Cross-geo extension approved | **HC-10** | Hard constraint | Cross-geography DR assignment has an approved extension path (DEC-001 for ME→EU) | Per cross-geo DR candidate |

**Output:** subset of candidate regions that pass all HCs.

### Step 1.3 — Scoring (Weighted Capacity Placement Model)

Surviving candidates are scored per environment using the placement scoring formulas (PLC-007/008, F.11):

| Environment | Formula | Weights | Key components |
|-------------|---------|---------|----------------|
| Prod | PS_Prod(C,R) | α=0.30, β=0.25, γ=0.20, δ=0.15, ε=0.10 | α=NP headroom, β=reservation util, γ=fairness, δ=DR readiness, ε=zone density |
| NonProd/CVAL | PS_NonProd(C,R) | α=0.15, β=0.25, γ=0.20, δ=0.30, ε=0.10 | Same components, different weights |
| DR | PS_DR(C,R) | α=0.30, β=0.20, γ=0.15, δ=0.15, ε=0.10, ζ=0.10 | +ζ overcommit ratio (DR-017) |

Scoring operates at **customer-aggregate** scope (PLC-007/008), not per-domain.

### Step 1.4 — Region Assignment

Assignment follows the distribution model and sequential order (Prod → CVAL → DR):

| Distribution model | Prod | CVAL | DR |
|--------------------|------|------|----|
| `three_region` (US) | argmax(PS_Prod) | argmax(PS_NonProd) over remaining regions | argmax(PS_DR) over remaining regions |
| `two_region` (EU/AU/APAC) | argmax(PS_Prod) | Co-located with DR in the remaining region (PLC-010a) — deterministic | Same as CVAL — the only remaining region |
| `cross_geography_dr` (ME) | argmax(PS_Prod) over ME regions | Co-located with Prod in ME (separate CRGs, PLC-010b) | argmax(PS_DR) over **Europe** Standard regions (DR-020) |

### Step 1.5 — CRV Output & Persistence

| Item | Detail |
|------|--------|
| **CRV** | `(geography, distribution_model, R_p, R_c, R_d)` |
| **Seed record** | Written to authoritative state store (DAT-001, PLC-003) with: customer ID, realm, geography, distribution model, CRV, domain groups, decision timestamp, policy version, capacity snapshot ref, exception ref, approval metadata |
| **Freshness** | Seed record has a configured max age; stale reads trigger `STALE_STATE` (RDY-004) |
| **Immutability** | CRV is resolved once per customer × geography; a change requires the approved migration/exception workflow (PLC-005) |

---

## Phase 2 — DPB Resolution (Domain Placement Binding)

**Scope:** Per Domain Group (D) × Environment (E) × CRV Region (R) — resolved each time capacity is needed (PLC-014).

**Owner:** Platform Engineering Team.

**Gate:** PLC-015 — CRV resolution **strictly precedes** DPB. A domain group never re-runs region selection.

### Step 2.1 — Subscription Resolution

| Check | Requirement | Detail |
|-------|-------------|--------|
| One subscription per Domain × Environment | DOM-002 | TMS-Prod and WMS-Prod are never in the same subscription |
| Deterministic naming | OPS-006, C-12 | `sub-<org>-<product>-<purpose>-<env>-<domain>-<region>-<shard>` |
| Shard registry | ADR-007 §10, DOM-003 | If primary subscription is at capacity limits, the shard registry provides the next shard |
| Management group enrollment | QUA-015 | Subscription must be enrolled in the correct MG hierarchy for quota group governance |
| Create-or-bind | CAP-002 | Azure resource must exist before config activation; create subscription if new |

### Step 2.2 — CRG Set Assignment

| Check | Requirement | Detail |
|-------|-------------|--------|
| Environment determines set type | CAP-025, ENV-003 | Prod → `crg-pr-*` (dedicated); CVAL → `crg-cvdr-*` (shared with DR within domain); DR → `crg-drf-*` (Foundation) + `crg-cvdr-*` access on DR declaration |
| Domain-bounded isolation | DOM-004, VR-12 | A CRG set belongs to exactly one domain; cross-domain sharing is rejected |
| CRG-set separation | CAP-025, VR-13 | Prod / CVAL-DR / DR Foundation set types are never mixed within a domain |
| Zone structure | CAP-023, CAP-011 | One zonal CRG (default) + one per-AZ CRG per zone + optional `reg` CRG for non-zonal SKUs; zones fixed at creation |
| Deterministic naming | OPS-006, C-12 | `crg-<env_token>-<region>-<zone_token>` |
| Seed-at-0 matrix | CAP-022 | New CRG set is created with count-0 reservations per eligible SKU/AZ (product-team budget governed) |
| DR Foundation (wl-fnd) | DR-021 | Foundation Services domain group gets dedicated Foundation CRG sets per environment |

### Step 2.3 — CR Sizing (Reservation Target)

| Check | Requirement | Detail |
|-------|-------------|--------|
| Target formula | CAP-003, F.1 | `TargetReserved(D,E) = AllocatedVMs(D,E) + Buffer(D,E)` per SKU × zone |
| Buffer is configurable | CAP-003, C-1 | Never a fixed percentage; driven by policy |
| DR sizing (max-not-sum) | DR-017, F.6 | `DR_Requirement(d) = MAX_s(portion_of_s_assigned_to_d)` — single-failure assumption |
| DR Foundation baseline | DR-021, ENV-005, C-16 | Configurable bootstrap; minimum capacity for DR readiness testing and recovery sequence |
| Headroom tracking | F.2 | `Headroom = Reserved − Allocated` |
| Deficit detection | F.3 | `Deficit = max(0, Target − Reserved)` → triggers reservation increase |
| No double counting | CAP-015, PLC-010 | CVAL earmark for DR extension is not simultaneously counted as CVAL headroom |

### Step 2.4 — Zone Distribution Targets

| Check | Requirement | Detail |
|-------|-------------|--------|
| Even distribution target | PLC-011, PLC-016, F.9 | `TargetVMs(D,E,z) = round(VMs(D,E) / ZoneCount(R))` per domain |
| Preferred zone | F.9 | `PreferredZone = argmin_z VMs(D,E,z)` — new VMs to most under-represented zone |
| Rebalance trigger | F.9, C-13 | `max_z |VMs(D,E,z) − Target| > SkewTolerance` → rebalance recommendation |
| Combined-load observation | PLC-016, OBS-002, C-15 | `RegionZoneLoad(R,E,z) = Σ_D VMs(D,E,R,z)` — **alert only**, never triggers sizing |

### Step 2.5 — Quota Draw

| Check | Requirement | Detail |
|-------|-------------|--------|
| Central quota group | QUA-015 | All domain subscriptions in one customer-scoped group per region × VM-family |
| Two-cap check | QUA-002, RDY-001 | VM-family vCPU cap **and** total regional vCPU cap; lower governs |
| Available quota | F.4 | `AvailableQuota(D,E,f) = min(FamilyCap − FamilyUsed, RegionalCap − RegionalUsed)` |
| Deficit detection | F.5 | `QuotaDeficit = max(0, Requested − Available)` → triggers quota transfer from group |
| Group replenishment | QUA-015 | Group cell ≥ 85% utilization → quota increase request |
| Subscription replenishment | QUA-015 | Subscription ≥ 85% utilization → quota transfer from group |
| DR proactive pre-positioning | QUA-015, DR-021 | DR quota pre-staged from production demand signals; not at incident time |
| Deploy-time enforcement | QUA-007, QUA-003 | Azure enforces quota at the **subscription**, not the group |
| Auditability | QUA-014 | Every allocation/transfer logged with before/after, actor, reason, correlation ID, timestamp |

### DPB Output

The DPB emits a **capacity envelope** per (D, E, R):

| Output | Content |
|--------|---------|
| Subscription | Subscription ID and name for (D, E, R) |
| CRG set | CRG object IDs (Prod-dedicated / CVAL-DR shared / DR Foundation) |
| CR sizing | Target reservation count per SKU × zone |
| Zone targets | Per-zone VM target, preferred placement zone, rebalance flag |
| Quota draw | Available quota, replenishment actions |

> **DPB does NOT output Instance Group.** IG is determined downstream by Service Owner / Product Automation.

---

## Phase 3 — Readiness Gate (Pre-Deploy)

**Owner:** Capacity / Placement Engine.

**Gate:** RDY-001 (combined capacity & quota readiness). A deployment proceeds only when **all** of the following pass:

| # | Check | Requirement | Detail |
|---|-------|-------------|--------|
| 1 | Target region approved | RDY-001 | Region is in the approved catalogue and CRV is valid |
| 2 | Zone supported | RDY-001, CAP-016 | Physical zone is available; logical-to-physical zone mapping is resolved (CAP-016 — zone numbers are per-subscription) |
| 3 | SKU supported | RDY-001 | VM SKU is in the eligible scope file for this region/zone |
| 4 | Reservation policy known | RDY-001 | Whether reservation is required (Prod = mandatory per CAP-017) or configurable (ENV-002) |
| 5 | Reservation exists | RDY-001, CAP-016 | If policy requires a reservation: reservation exists, SKU matches, region matches, zone matches |
| 6 | Consumer subscription authorised | CAP-016, CAP-013 | If shared: consumer subscription is in the authorised list (≤100 subs, same tenant or trusted, domain-bounded per DOM-004) |
| 7 | Sufficient reservation or approved over-allocation | RDY-001, CAP-016 | Reserved quantity ≥ demand, or over-allocation is explicitly approved |
| 8 | Sufficient quota (VM-family cap) | RDY-001, QUA-002 | Deploying subscription's VM-family vCPU usage + requested ≤ cap |
| 9 | Sufficient quota (regional vCPU cap) | RDY-001, QUA-002 | Deploying subscription's total regional vCPU usage + requested ≤ cap |
| 10 | Records fresh enough | RDY-004 | Capacity snapshot age ≤ configured max age; stale → `STALE_STATE` |
| 11 | No blocking policy/exception | RDY-001 | No active policy block (e.g., DR_NOT_OFFERED, subscription freeze) |
| 12 | Capacity and quota balanced | RDY-003 | Capacity and quota correlated by region, zone, SKU, subscription, environment, domain |

### Readiness States (RDY-002)

| State | Meaning |
|-------|---------|
| `READY` | All checks pass; deployment may proceed |
| `READY_WITH_RISK` | Passes with identified risk (e.g., approaching threshold) |
| `QUOTA_DEFICIT` | Insufficient quota; replenishment in progress |
| `RESERVATION_DEFICIT` | Insufficient reserved capacity; increase request raised |
| `CAPACITY_UNAVAILABLE` | No reservable capacity in the target region/zone/SKU |
| `STALE_STATE` | Data snapshot too old; refresh required before proceeding |
| `POLICY_BLOCKED` | Active policy prevents deployment |
| `VALIDATION_REQUIRED` | Pre-conditions incomplete; manual review needed |

### Pre-Deploy Reservation Integrity (CAP-016)

Before associating a VM with a reservation, validate:

| # | Validation | Detail |
|---|------------|--------|
| 1 | Reservation exists | CRG and CR are present in the target subscription |
| 2 | SKU match | VM SKU matches the reservation's VM size |
| 3 | Region match | VM region matches the reservation's region |
| 4 | Zone match (physical) | VM physical zone matches the reservation's physical zone — logical zone numbers are per-subscription (CAP-016); on a shared zonal reservation, translate consumer logical zone to provider physical zone |
| 5 | Consumer authorised (if shared) | Consumer subscription is in the sharing grant list |
| 6 | Quantity sufficient | Reserved quantity ≥ allocated demand, or approved over-allocation |
| 7 | Quota available | Deploying subscription has headroom on both VM-family and regional vCPU caps |

---

## Phase 4 — Platform Foundation (Regional Preparation)

**Owner:** Platform Team.

**Trigger:** DPB output is available and readiness gate is `READY`.

| Step | Action | Detail |
|------|--------|--------|
| 4.1 | Product cell provisioning | Region-specific infrastructure: networking, control plane, operators |
| 4.2 | Desired state application | Platform operators apply the target configuration per the DPB envelope |
| 4.3 | In-region HA setup | High availability within the region (zone redundancy per CAP-023) |

---

## Phase 5 — Service Deployment

**Owner:** Service Owner / Product Automation.

**Inputs received from Placement Engine:**
- CRV: region binding (R_p, R_c, R_d)
- DPB capacity envelope: subscription, CRG set, CR sizing, zone targets, quota draw

> **Ownership boundary:** The Service Owner receives the capacity envelope and determines the appropriate Instance Group. IG is an **output** of service deployment, not an input from the Placement Engine.

| Step | Action | Owner | Detail |
|------|--------|-------|--------|
| 5.1 | Receive placement context | Service deployment automation | CRV + DPB capacity envelope provided to the deployment pipeline |
| 5.2 | Instance Group definition | **Service Owner** | Service Owner defines which IG this service belongs to, based on domain, service type, and operational requirements |
| 5.3 | Instance Group selection | **Service deployment automation** | Deployment automation selects the target IG for this deployment using the Service Owner's definition |
| 5.4 | VM association | Deployment pipeline | Associate VM / VMSS instances with the validated reservation reference (INT-005); Anu's pipeline supplies the reservation-group name when SKU + subscription match |
| 5.5 | Concurrent deployment control | Deployment pipeline | Prevent two concurrent decisions from consuming the same last unit of capacity/quota (INT-006) — reservation-of-intent or optimistic concurrency |
| 5.6 | Partial-failure handling | Deployment pipeline | If quota allocated but deployment/association fails → record partial state, compensate or raise recoverable operational task (INT-007) |
| 5.7 | Service ↔ IG registration | Service deployment/registration | Register the Service → Instance Group association in Gravity (global system of record) |

### Deployment Integration Checks (INT-001..INT-008)

| Check | Requirement | Detail |
|-------|-------------|--------|
| Capacity API called before first deployment | INT-001 | AEP calls capacity+placement service before first relevant environment deployment |
| Idempotent operations | INT-002 | Repeated calls with same correlation ID + desired state do not duplicate |
| Required input present | INT-003, INT-008 | Customer/realm, domain group token, product, environment, region, subscription, SKU+count, zone, priority, correlation ID |
| Required output returned | INT-004, INT-008 | CRV, DPB capacity envelope, readiness status, reservation ref, quota status, blocking reasons, trace/decision ID |
| Two-scope ordering enforced | INT-008, PLC-015 | CRV resolution precedes DPB resolution; CRV treated as cached input |

---

## Phase 6 — Instance Group Provisioning / Scaling

**Owner:** Product / Service DevOps Pipeline.

**Point in flow:** Service lifecycle (ongoing).

| Step | Action | Detail |
|------|--------|--------|
| 6.1 | IG provisioning | Product/Service DevOps pipeline provisions the IG with the DPB capacity envelope context |
| 6.2 | IG scaling | Scale-out uses the shard registry (ADR-007 §10, DOM-003) if the primary subscription reaches capacity limits |
| 6.3 | Reactive SKU/AZ discovery | New SKU/AZ combinations discovered during deployment are reconciled with governance within the SLA (CAP-024, CAP-019) |
| 6.4 | Seed reservation scaling | Count-0 seed reservations scale up from baseline when allocated demand appears (CAP-022) |

---

## Phase 7 — Production Readiness & Go-Live

**Owner:** SRE / Operations.

| Step | Check | Detail |
|------|-------|--------|
| 7.1 | Health endpoint | Service exposes a health endpoint for monitoring |
| 7.2 | Dependency validation | All upstream/downstream dependencies are reachable and healthy |
| 7.3 | Synthetic checks | Automated synthetic transactions verify end-to-end flow |
| 7.4 | Business checks | Business-level acceptance criteria validated |
| 7.5 | One-writer-per-realm | Production runs with one writer per realm — partition safety |
| 7.6 | DR readiness certification | DR Foundation tests complete successfully with recorded evidence (ENV-005, DR-021) |
| 7.7 | Failover capacity reserved | Warm data replicas established in the failover PIN; onboarding is **rejected or delayed** if failover capacity is not reserved |
| 7.8 | Production-live gate | All above pass → customer is production-live |

---

## Phase 8 — Steady State Operations

**Owner:** SRE / Operations + Capacity Platform.

| Activity | Requirement | Detail |
|----------|-------------|--------|
| Reconciliation | CAP-019, CAP-024 | Periodic reconciliation of reservations, quota, and scope file; discrepancies resolved within governance SLA |
| Buffer management | CAP-003, C-1 | Buffer policy evaluated continuously; buffer never a fixed percentage |
| Quota monitoring | QUA-015 | Group-level and subscription-level replenishment at 85% thresholds |
| Zone rebalancing | PLC-016, C-13 | Per-domain zone distribution drift monitored; rebalance recommendations when skew exceeds tolerance |
| Combined-load observation | PLC-016, OBS-002 | Cross-domain regional load monitored for alerting (not enforcement) |
| Idle cost measurement | FIN-001 | Cost of unused reserved capacity tracked by region, SKU, subscription, environment, domain, owner |
| Audit trail | QUA-014, DAT-002 | All capacity/quota operations logged with full audit trail |
| DR drill rotation | DR-012 | Periodic DR drills without losing seed, capacity state, or audit trail |

---

## Phase 9 — Disaster Recovery Activation

**Owner:** SRE / DR Operations.

**Trigger:** Authorised DR declaration (DR-010).

### Step 9.1 — Failure Detection & Declaration

| Check | Requirement | Detail |
|-------|-------------|--------|
| Region unavailability confirmed | DR-001 | Single-region failure basis; multi-region failure outside default model unless funded |
| DR declaration authorised | DR-010 | Destructive/CVAL-impacting actions only after authorised declaration |
| Source region capacity excluded | DR-011 | Do not count reservations/quota from the unavailable source region |

### Step 9.2 — DR Index Lookup

| Action | Requirement | Detail |
|--------|-------------|--------|
| Source→destination DR index query | DR-018 | Bidirectional mapping: for each source region, which destinations hold DR instances, in what quantity/SKU, with domain attribution |
| Affected customers/realms identified | DR-019 | Per the index, determine exactly which standby instances to activate and where |

### Step 9.3 — Staged Capacity Acquisition (DR-006)

| Stage | Action | Detail |
|-------|--------|--------|
| 1 | Use approved bootstrap / pre-staged headroom | DR Foundation CRG set (`crg-drf-*`) — always present, pre-staged quota (DR-021) |
| 2 | Allocate available reservation + quota | Existing reservation headroom and available quota in the destination |
| 3 | Shut down / disassociate eligible CVAL workloads | CVAL-sacrifice bootstrap (DR-005/DR-006) — releases capacity from `crg-cvdr-*` for DR VMs |
| 4 | Share or reassign reservations | Within supported region/zone boundaries (CAP-013, domain-bounded per DOM-004) |
| 5 | Allocate pooled quota to DR subscriptions | Draw from central quota group (QUA-015) |
| 6 | Request additional Azure quota/capacity | Where stages 1–5 are insufficient |
| 7 | Report unrecoverable capacity gaps | Transparent gap reporting for operational decision |

> This staging lets P0/P-1 customers start immediately from bootstrap headroom (DR-008 control plane first, DR-009 prioritised waves) while rebalancing proceeds.

### Step 9.4 — Standby Activation (DR-019)

| Action | Requirement | Detail |
|--------|-------------|--------|
| Transition DR instances | DR-019 | Associated → allocated (standby → active) in business-priority order (DR-009) |
| Control plane first | DR-008 | Platform control planes and recovery orchestration before customer workload waves |
| Domain-scoped activation | DOM-003, DR-021 | Each domain fails over independently; a domain's DR Foundation + CVAL extension |
| Activation state tracked | DR-019 | Per customer, per domain — auditable and reversible on failback |

### Step 9.5 — Routing & Recovery

| Action | Detail |
|--------|--------|
| Stop routing to failed region | Traffic routing updated |
| Identify affected realms and PINs | From the DR index |
| Promote replicas | Warm data replicas promoted to primary |
| Update placement and APIM routing | Seed records updated; APIM reconfigured |
| Deploy Service-0 in failover PIN | Minimum viable service in the DR region |

### Step 9.6 — Failback (DR-013)

| Check | Requirement | Detail |
|-------|-------------|--------|
| Failback policy | DR-013, C-5 | Configurable: extended DR run (~1 year, preferred) or earlier failback (~30 days) |
| Duration is a business decision | DR-013 | Not an engine-automated decision |
| Seed/state preservation | DR-012 | Historical capacity state and audit trail preserved through failback |

---

## Cross-Cutting Checks

These checks apply across multiple phases:

| Check | Requirement | Where it applies |
|-------|-------------|------------------|
| VM-level eligibility | **HC-11** | Onboarding: Availability-Set VMs are ineligible for zonal reservations (CAP-020); must deallocate/redeploy to AZ (CAP-021) |
| Idempotency | INT-002 | All capacity/reservation operations |
| Concurrent deployment control | INT-006 | All deployment operations |
| Partial-failure handling | INT-007 | All deployment operations |
| Stale-state prevention | RDY-004 | CRV reads and DPB resolution |
| Deterministic naming | OPS-006, C-12 | Subscriptions, CRGs, resource groups |
| Config-driven policy | REG-001, C-1..C-16 | Buffer, bootstrap, thresholds, region catalogue, DR policy, zone tolerance — all configurable without code changes |
| Preview-feature awareness | CAP-013, DEP-001 | Sharing is Preview; production placement uses deploying subscription until GA |

---

## End-to-End Pipeline Summary

```
Phase 0 ─ Customer Onboarding
 │  Customer exists check → seed record lookup
 │  Geography selection → distribution model
 ▼
Phase 1 ─ CRV Resolution (Customer scope, once per customer × geography)
 │  HC-8/HC-9 pre-filter → candidate set
 │  HC-1..HC-7, HC-10 gate → eligible regions
 │  PS_Prod / PS_NonProd / PS_DR scoring → region assignment
 │  CRV output → seed record persisted
 ▼
Phase 2 ─ DPB Resolution (Domain scope, per D × E × R)
 │  ① Subscription resolution (DOM-002, OPS-006)
 │  ② CRG set assignment (CAP-025, ENV-003)
 │  ③ CR sizing (CAP-003, F.1–F.3, DR-017)
 │  ④ Zone targets (PLC-016, F.9)
 │  ⑤ Quota draw (QUA-015, F.4–F.5)
 │  Capacity envelope output
 ▼
Phase 3 ─ Readiness Gate (RDY-001..004, CAP-016)
 │  12-point readiness check
 │  7-point reservation integrity validation
 │  Readiness state assigned
 ▼
Phase 4 ─ Platform Foundation
 │  Product cell, desired state, in-region HA
 ▼
Phase 5 ─ Service Deployment (Service Owner scope)
 │  Receive context → IG definition → IG selection
 │  VM association → concurrent control → partial-failure handling
 │  Service ↔ IG registration in Gravity
 ▼
Phase 6 ─ IG Provisioning / Scaling (DevOps lifecycle)
 │  Scaling, shard registry, reactive discovery
 ▼
Phase 7 ─ Production Readiness
 │  Health, dependencies, synthetics, business checks
 │  DR readiness certification
 │  Production-live gate
 ▼
Phase 8 ─ Steady State
 │  Reconciliation, buffer, quota monitoring
 │  Zone rebalancing, idle cost, DR drills
 ▼
Phase 9 ─ DR Activation (on authorised declaration)
    Failure detection → DR index → staged acquisition
    → standby activation → routing → failback
```

---

## Traceability: Every Check to Its Requirement

| Phase | Checks applied | Requirement IDs |
|-------|---------------|-----------------|
| 0 — Onboarding | Seed lookup, geography selection | PLC-003, PLC-009, REG-001, REG-003 |
| 1 — CRV | HC gate (HC-1..HC-10), scoring (PS_Prod/NonProd/DR) | HC-1..HC-10, PLC-007/008, PLC-013, F.10, F.11 |
| 2 — DPB | Subscription, CRG, CR sizing, zone, quota | DOM-002, CAP-025, CAP-003, PLC-016, QUA-015, F.1–F.5, F.9 |
| 3 — Readiness | 12-point readiness, reservation integrity | RDY-001..004, CAP-016 |
| 4 — Foundation | Product cell, HA | — (platform operational) |
| 5 — Service Deployment | IG determination, VM association, concurrency | INT-001..INT-008, PLC-014 (ownership boundary) |
| 6 — IG Lifecycle | Scaling, shard registry, reactive discovery | ADR-007 §10, DOM-003, CAP-022, CAP-024 |
| 7 — Prod Readiness | Health, DR certification, failover reservation | ENV-005, DR-021 |
| 8 — Steady State | Reconciliation, quota monitoring, zone balance | CAP-019, QUA-015, PLC-016, FIN-001, DR-012 |
| 9 — DR | Declaration, staged acquisition, activation, failback | DR-001..DR-021, F.6–F.8 |
| Cross-cutting | HC-11, idempotency, stale-state, naming, preview | HC-11, INT-002/006/007, RDY-004, OPS-006, DEP-001 |
