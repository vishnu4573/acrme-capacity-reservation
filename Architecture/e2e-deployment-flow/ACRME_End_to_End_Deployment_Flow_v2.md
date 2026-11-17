# ACRME End-to-End Deployment Flow

**Customer Onboarding → Placement → Service Deployment → Readiness → Steady State → DR**

| | |
|---|---|
| **Document version** | 2.0 |
| **Date** | 17 November 2026 |
| **Requirements baseline** | v4.0.2 (17 Nov 2026) |
| **Hard Constraints reference** | v1.1 (HC-1..HC-11) |

> This version preserves v1.0 and corrects its placement paths, hard-constraint scopes, CRG/DR representation, and alignment with the owner-confirmed deployment standard. A configured policy is not proof of runtime enforcement. The hard-constraints reference carries historical notes; the v4.0.2 baseline is authoritative where sources conflict.

| Version | Date | Change |
|---|---|---|
| 2.0 | 17 November 2026 | Clarifies exact-region default and geography exception; separates CRV and DPB gates; aligns compute, resource, rollout, CRG, DR Foundation, sharing, and reconciliation steps with baseline v4.0.2 and `environment_v2.yaml`. |

---

## Ownership Summary

| Function | Owner | Point in Flow |
|----------|-------|---------------|
| Customer exists check | Onboarding / upstream workflow | Beginning |
| Placement input | Customer / onboarding | Beginning |
| Prod / Non-Prod / DR region selection | Placement engine | Placement |
| Capacity / reservation validation | Capacity / placement engine | Placement |
| Regional PIN | Placement engine | Placement |
| Persist customer placement | Platform workflow / system of record | After placement |
| Instance Group definition | **Service Owner** | **Service domain** |
| Instance Group selection | **Service deployment automation** | **During service deployment** |
| Initial Instance Group creation | **Product / Service DevOps pipeline** | **During service deployment** |
| Instance Group scaling | **Product / Service DevOps pipeline** | **Service lifecycle** |
| Service ↔ Instance Group registration | Service deployment / registration | Post-deployment |
| Central visibility | Gravity | Global system of record |

> **Ownership boundary (v4.0.2):** CRV and DPB are placement-engine outputs consumed by service deployment. The Service Owner defines the Instance Group; service deployment automation selects and initially provisions it using the DPB context. IG is not a DPB output. The Service → IG association is registered in Gravity after deployment.

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

### Step 0.2 — Placement Input

| Item | Detail |
|------|--------|
| **Owner** | Customer / onboarding |
| **Action** | Collect the exact production region by default; collect geography only for the approved geography-selection exception (PLC-001/002) |
| **Input** | Default: exact Azure Prod region and customer geography. Exception: geography, explicit approval, and customer acknowledgement that the derived Prod region is fixed until approved migration |
| **Output** | Placement input plus geography code (US, EU, AU, APAC, ME), which determines the distribution model (REG-003) |
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

For automated selection, the region catalogue is filtered to eligible Standard candidates. The exact-region path validates the supplied Prod region rather than scoring it; an explicitly supplied Restricted Prod region is eligible only through its approved exception path. CVAL/DR auto-selected regions remain subject to the Standard-region rule.

| Gate | ID | Type | Check | Fail action |
|------|----|------|-------|-------------|
| Geography containment | **HC-8** | Hard constraint | On the geography path, selected regions must satisfy the customer's geography and configured cross-geography policy | Exclude ineligible candidates |
| Standard region only | **HC-9** | Hard constraint | Auto-selected regions must be Standard. Restricted Prod is not auto-selected; it may be accepted only when explicitly supplied with the required exception | Exclude ineligible auto-selection candidates; validate explicit Prod separately |

**Output:** candidate set of Standard regions for each region the engine must select. On the exact-region path, Prod is a validated input, not a candidate.

### Step 1.2 — CRV Region Hard Constraints (Binary Pass/Fail)

Apply region-level constraints during CRV resolution. Capacity and quota floor constraints are not finalized here: they are evaluated per domain during DPB. Their customer-aggregate state may inform scoring, but it does not replace DPB validation.

| Gate | ID | Type | What it checks | Scope |
|------|----|------|----------------|-------|
| Region separation | **HC-1** | Hard constraint | Prod is separate from CVAL and DR. CVAL/DR co-location is mandatory in two-region geographies, optional in the US three-region model, and does not apply to Middle East cross-geo DR | Per CRV and distribution model |
| DR separation class | **HC-4** | Hard constraint | DR region class meets the required separation from Prod | Per DR candidate |
| Zone availability | **HC-5** | Hard constraint | At least two physical availability zones for non-dev placement, per HC-5; resolve the applicable policy before allowing any exception | Per selected region |
| Cross-geo extension approved | **HC-10** | Hard constraint | Cross-geography DR has an approved extension path (currently Middle East → Europe; DEC-001) | Cross-geo DR only |

HC-8 and HC-9 are the pre-filters above. HC-2, HC-3, HC-6, and HC-7 are DPB/domain gates, and HC-11 is a VM eligibility gate; do not report the CRV as passing those checks.

### Step 1.3 — Scoring (Weighted Capacity Placement Model)

Eligible candidates are scored using the customer-aggregate weighted policy (PLC-007/008, F.10/F.11). Prod is scored only on the geography-exception path; on the default exact-region path the supplied Prod region is validated and held constant. Coefficients and normalization must come from an approved, versioned PlacementPolicy; the baseline does not fix the numerical weights shown in v1.

| Path / environment | Selection behavior | Scoring factors |
|--------------------|----------------------|-----------------|
| Exact-region / Prod | Validate the supplied region; do not score or replace it | Hard-constraint and readiness validation |
| Geography exception / Prod | Select the lowest-risk suitable Prod candidate | `Score_Pool(C,R)` with configured weights |
| CVAL and DR | Score eligible candidates per the geography distribution model | Capacity, reservation, quota, buffer, DR contribution, zone support, freshness, and γ fairness (PLC-007, F.10) |

Scoring operates at **customer-aggregate** scope (PLC-007/008), not per-domain.

### Step 1.4 — Region Assignment

After validating or selecting Prod according to the input path, derive CVAL and DR according to the configured distribution model:

| Distribution model | Prod | CVAL | DR |
|--------------------|------|------|----|
| `three_region` (US) | Exact input by default; scored only on approved geography path | Select from eligible non-Prod regions | Select from eligible non-Prod regions; distinct from CVAL in the current three-region model |
| `two_region` (EU/AU/APAC) | Exact input by default; scored only on approved geography path | Co-located with DR in the only remaining region (PLC-010a) | Same as CVAL |
| `cross_geography_dr` (ME) | Exact input by default; scored only on approved geography path | Co-located with Prod in ME using separate CRGs (PLC-010b) | Weighted-selected Europe Standard region with dedicated DR capacity (DR-020) |

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
| Compute subscription per Domain × Environment | DOM-002; `environment_profiles.standard.subscription_model` | DPB resolves the compute subscription that owns VM/VMSS capacity, CRGs, and quota draw. TMS-Prod and WMS-Prod are never in the same domain subscription |
| Resource subscription per Domain × Environment | `environment_profiles.standard` (deployment standard) | [Documented] The standard profile also provisions a separate resource subscription for Azure PaaS resources; do not conflate it with the DPB compute subscription |
| Deterministic naming | OPS-006, C-12 | `sub-<org>-<product>-<purpose>-<env>-<domain>-<region>-<shard>` |
| Compute subscription scale-out | `compute_subscription_policies.standard.when_limit_reached` | Scale out on active-cluster limit or insufficient rollout headroom; provision another compute subscription. Cluster-slot availability does not itself authorize consuming rollout headroom |
| Resource subscription scale-out | `resource_subscription_policies.standard.scale_out` | [Documented] Scale out only when an Azure subscription-level limit is reached; configured as non-proactive |
| Management group enrollment | QUA-015 | Subscription must be enrolled in the correct MG hierarchy for quota group governance |
| Create-or-bind | CAP-002 | Azure resource must exist before config activation; create subscription if new |

### Step 2.2 — CRG Set Assignment

| Check | Requirement | Detail |
|-------|-------------|--------|
| Environment determines set type | CAP-025, ENV-003 | Prod → `crg-pr-*` (dedicated); CVAL → `crg-cvdr-*` (shared with DR within domain); DR → `crg-drf-*` (Foundation) + `crg-cvdr-*` access on DR declaration |
| Domain-bounded isolation | DOM-004, VR-12 | A CRG set belongs to exactly one domain; cross-domain sharing is rejected |
| CRG-set separation | CAP-025, VR-13 | Prod / CVAL-DR / DR Foundation set types are never mixed within a domain |
| Zone structure | CAP-023, CAP-011, C-12 | One zonal CRG is the default; it contains one reservation per VM size per zone. Optional per-zone CRGs may be used where configured. A no-zone `reg` CRG is not a region-wide pool; Azure pins it to one zone |
| Deterministic naming | OPS-006, C-12 | `crg-<env_token>-<region>-<zone_token>` |
| Seed-at-0 matrix | CAP-022 | New CRG set is created with count-0 reservations per eligible SKU/AZ (product-team budget governed) |
| DR Foundation | DR-021, ENV-005 | Every domain group has an always-present DR Foundation CRG set in its dedicated DR compute subscription, with pre-staged quota; it does not depend on sharing |
| CVAL/DR extension | CAP-025, DR-021 | Same-domain CVAL/DR shared CRG is an extension only after authorized declaration and applicable sharing gates. It is not the Middle East DR path |

### Step 2.3 — CR Sizing (Reservation Target)

| Check | Requirement | Detail |
|-------|-------------|--------|
| Target formula | CAP-003, F.1 | `TargetReserved(D,E) = AllocatedVMs(D,E) + Buffer(D,E)` per SKU × zone |
| Buffer is configurable | CAP-003, C-2 | Production reservation buffer is policy-driven; never infer a fixed percentage |
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
| Group replenishment | QUA-015 | Configured group-cell threshold (default 85%) triggers replenishment review/request |
| Subscription replenishment | QUA-015 | Configured subscription threshold (default 85%) triggers quota transfer from the group |
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
| Resource subscription | Separate resource-subscription reference where required by the standard profile |

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
| 6 | Sharing authorization and quota (if enabled) | CAP-016, CAP-013, QUA-013 | Sharing is conditional on Preview/POC gates. Check the explicit consumer list (maximum 100 per CRG), domain scope, provider quota to create/grow the reservation, and consumer quota on both caps |
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

### Additional Deployment-Standard Gates

These are configured policy gates, separate from the baseline RDY-001 capacity/readiness checks. Configuration records intended policy, not proof that the workflow is implemented.

| Gate | Standard key / status | Flow behavior |
|------|------------------------|---------------|
| New capacity request eligibility | `capacity_request_policy.allowed_vm_series`, effective 2026-10-23 | For new VM or AKS VMSS node-pool capacity requests, check exact VM size and its series membership. Series mapping and Preview-series production policy are pending; do not treat allowlist membership as technical readiness |
| New capacity request approval | `capacity_request_policy.approval`, effective 2026-10-23 | Require Jira business and finance approval evidence for new capacity requests only. Workflow/roles and approval scope/validity are pending. Existing protective reconciliation is unchanged |
| Blue/green rollout | `compute_subscription_policies.standard.deployment.rollout`, effective 2026-10-23 | Keep current clusters serving; validate current + replacement overlap before traffic cutover and validate replacement before cutover |
| Cluster and DR slot limits | `compute_subscription_policies.standard.cluster_capacity` and `.dr_clusters`, effective 2026-10-23 | Enforce configured cluster limits; DR clusters are provisioned before DR, run reduced steady-state capacity, and scale only on approved declaration with capacity and quota checks. DR counts toward total and active limits |
| Rollout/DR headroom conflict | `compute_subscription_policies.standard.dr_clusters.rollout_headroom_conflict_policy` | **OPEN:** do not assume green rollout slots are available to DR until the owner closes this policy |
| Sharing provider and feature gates | `capacity_reservation_policies.standard.sharing`, effective 2026-10-23 | [Documented] **OPEN / Preview (CAP-013, DEP-001):** provider ownership is pending; sharing must not be a production dependency. Use a reservation in the deploying subscription as the fallback |

The standard also leaves post-cutover color convention, rollback retention, and Jira workflow details open. Those are not resolved by this flow.

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
| 4.4 | DR cluster foundation | Provision reduced-capacity DR clusters before an incident; record readiness tests and evidence before DR readiness certification (deployment standard; ENV-005, DR-021) |

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
| 5.3 | Instance Group selection and initial provisioning | **Service deployment automation / Product DevOps** | Select and initially provision the target IG using the Service Owner's definition and DPB capacity context. This is downstream of DPB and part of service deployment; IG is not a Placement Engine output |
| 5.4 | Workload deployment and VM association | Deployment pipeline | Deploy into the selected IG; associate VM / VMSS instances with the validated reservation reference when policy requires it (INT-005) |
| 5.5 | Concurrent deployment control | Deployment pipeline | Prevent two concurrent decisions from consuming the same last unit of capacity/quota (INT-006) — reservation-of-intent or optimistic concurrency |
| 5.6 | Partial-failure handling | Deployment pipeline | If quota allocated but deployment/association fails → record partial state, compensate or raise recoverable operational task (INT-007) |
| 5.7 | Service ↔ IG registration | Service deployment/registration | Register the Service → Instance Group association in Gravity after deployment |

### Deployment Integration Checks (INT-001..INT-008)

| Check | Requirement | Detail |
|-------|-------------|--------|
| Capacity API called before first deployment | INT-001 | AEP calls capacity+placement service before first relevant environment deployment |
| Idempotent operations | INT-002 | Repeated calls with same correlation ID + desired state do not duplicate |
| Required input present | INT-003, INT-008 | Customer/realm, domain group token, product, environment, region, subscription, SKU+count, zone, priority, correlation ID |
| Required output returned | INT-004, INT-008 | CRV, DPB capacity envelope, readiness status, reservation ref, quota status, blocking reasons, trace/decision ID |
| Two-scope ordering enforced | INT-008, PLC-015 | CRV resolution precedes DPB resolution; CRV treated as cached input |

---

## Phase 6 — Instance Group Lifecycle / Scaling

**Owner:** Product / Service DevOps Pipeline.

**Point in flow:** Service lifecycle (ongoing).

**Boundary:** Initial IG selection and provisioning occur in Phase 5. This phase covers ongoing operation and scale-out.

| Step | Action | Detail |
|------|--------|--------|
| 6.1 | IG scaling | Scale-out uses the resolved domain compute subscription; provision another compute subscription only under the configured cluster-limit/rollout-headroom policy |
| 6.2 | Reactive SKU/AZ discovery | New SKU/AZ combinations discovered during deployment are reconciled with governance within the SLA (CAP-024, CAP-019) |
| 6.3 | Seed reservation scaling | Count-0 seed reservations scale up from baseline when allocated demand appears (CAP-022) |

---

## Phase 7 — Production Readiness & Go-Live

**Owner:** SRE / Operations.

| Step | Check | Detail |
|------|-------|--------|
| 7.1 | Health endpoint | Service-specific operational gate; source it to the service SLO/runbook |
| 7.2 | Dependency validation | Service-specific operational gate; all upstream/downstream dependencies are checked |
| 7.3 | Synthetic checks | Service-specific operational gate; automated transactions verify the service flow |
| 7.4 | Business checks | Service-specific business acceptance criteria validated |
| 7.5 | One-writer-per-realm | Platform-specific partition-safety policy; identify its owner/source before treating it as an ACRME requirement |
| 7.6 | DR readiness certification | DR Foundation tests complete successfully with recorded evidence (ENV-005, DR-021) |
| 7.7 | DR offer and readiness state | If DR is offered, verify the domain's DR Foundation and record its tests/certification. If `DR_NOT_OFFERED` applies, record that policy outcome; this flow does not impose a blanket onboarding rejection solely because DR is not offered |
| 7.8 | Production-live gate | All above pass → customer is production-live |

---

## Phase 8 — Steady State Operations

**Owner:** SRE / Operations + Capacity Platform.

| Activity | Requirement | Detail |
|----------|-------------|--------|
| Reconciliation | CAP-005, CAP-019, CAP-024 | Periodically reconcile reserved, allocated, associated, and buffer quantities; create Azure resources before config activation and raise governance items for discovered scope |
| Scale-down and retirement boundary | CAP-008, CAP-009, CAP-010 | Right-size retained reservations toward allocated + buffer. A legitimate target of zero does not delete the CRG/CR; intentional retirement, deletion, or scope removal requires the separate approved decommissioning workflow |
| Buffer management | CAP-003, C-2 | Evaluate configured production buffer policy continuously; do not treat C-1 (DR bootstrap) as the production buffer |
| Quota monitoring | QUA-015 | Group-level and subscription-level replenishment uses configured thresholds (85% defaults), not an assumed immutable threshold |
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
| 1 | Use DR Foundation | Each domain's dedicated `crg-drf-*` and pre-staged quota are always present and independent of sharing (DR-021) |
| 2 | Allocate available destination reservation and quota | Use fresh, confirmed destination capacity/quota; exclude the failed source region (DR-011) |
| 3 | Release eligible CVAL extension, where applicable | Only after authorized declaration, and only for the same-domain CVAL/DR model. **Not applicable to Middle East**, whose CVAL is local with Prod and whose DR capacity is dedicated in Europe (PLC-010b, DR-020) |
| 4 | Use sharing only if all gates pass | Same-region/domain scope, explicit authorization, physical-zone alignment, provider and consumer quota, applicable POCs (POC-001/003/012), and DEP-001 maturity. Sharing is Preview and not a production dependency; no cross-region reassignment |
| 5 | Allocate pooled quota to DR subscriptions | Draw from the central quota group (QUA-015) after protected floors and policy gates |
| 6 | Request additional Azure quota/capacity | Where prior stages are insufficient; keep any new-capacity approval policy distinct from protective reconciliation |
| 7 | Report unrecoverable capacity gaps | Transparent gap reporting for operational decision |

> This staging lets P0/P-1 customers start immediately from bootstrap headroom (DR-008 control plane first, DR-009 prioritised waves) while rebalancing proceeds.

### Step 9.4 — Standby Activation (DR-019)

| Action | Requirement | Detail |
|--------|-------------|--------|
| Transition DR instances | DR-019 | Associated → allocated (standby → active) in business-priority order (DR-009) |
| Control plane first | DR-008 | Platform control planes and recovery orchestration before customer workload waves |
| Domain-scoped activation | DOM-003, DR-021 | Each domain fails over independently; use its DR Foundation and, where applicable, its same-domain CVAL extension. Middle East uses dedicated destination capacity, not CVAL extension |
| Activation state tracked | DR-019 | Per customer, per domain — auditable and reversible on failback |

### Step 9.5 — Routing & Recovery

| Action | Detail |
|--------|--------|
| Stop routing to failed region | Traffic routing updated |
| Identify affected realms and PINs | From the DR index |
| Promote replicas | Warm data replicas promoted to primary |
| Update active routing and DR state | Update activation state and routing. Do not silently rewrite the immutable CRV/placement seed; region changes require the approved migration workflow (PLC-005) |
| Deploy minimum viable service | Deploy the recovery service in the failover PIN according to the service recovery runbook; identify the source for any platform-specific Service-0/APIM steps |

### Step 9.6 — Failback (DR-013)

| Check | Requirement | Detail |
|-------|-------------|--------|
| Failback policy | DR-013, C-5 | Configurable: extended DR run (~1 year, preferred) or earlier failback (~30 days) |
| Duration is a business decision | DR-013 | Not an engine-automated decision |
| Failback readiness and approval | DR-013, DR-019 | Before routing back, validate the restored region's service, capacity, quota, and approved failback decision; exact runbook and approval steps remain operations-owned |
| Reverse activation and routing | DR-019 | Reverse standby activation and traffic changes through a guarded, auditable operation; do not infer failback from fresh state alone |
| Seed/state preservation | DR-012 | Preserve CRV, DR index, historical capacity state, activation records, and audit trail; update operational activation state without regenerating the seed |

---

## Cross-Cutting Checks

These checks apply across multiple phases:

| Check | Requirement | Where it applies |
|-------|-------------|------------------|
| VM-level eligibility | **HC-11** | Availability-Set VMs are ineligible for zonal reservations (CAP-020). Record the CAP-021 remediation; ACRME does not auto-migrate a running workload |
| Idempotency | INT-002 | All capacity/reservation operations |
| Concurrent deployment control | INT-006 | All deployment operations |
| Partial-failure handling | INT-007 | All deployment operations |
| Stale-state prevention | RDY-004 | CRV reads and DPB resolution |
| Deterministic naming | OPS-006, C-12 | Subscriptions, CRGs, resource groups |
| Config-driven policy | REG-001, C-1..C-16 | Buffer (C-2), bootstrap (C-1/C-16), thresholds, region catalogue, DR policy, and zone tolerance are policy inputs |
| Preview-feature awareness | CAP-013, DEP-001 | Sharing is Preview and not a production dependency; use the deploying-subscription reservation fallback. Sharing remains subject to POC-001/003/012 and DEP-001 |

---

## End-to-End Pipeline Summary

| Phase | Main flow |
|---|---|
| 0 — Onboarding | Check for an existing seed; collect exact Prod region by default, or an approved geography-path exception |
| 1 — CRV | Apply region-level gates; validate exact Prod input or score Prod on the approved geography path; derive CVAL/DR by distribution model; persist CRV |
| 2 — DPB | Resolve per-domain compute/resource subscriptions, CRG sets, sizing, zone targets, and quota |
| 3 — Readiness | Evaluate per-domain capacity/quota, reservation integrity, fresh state, policy eligibility, and any applicable rollout gates |
| 4 — Platform foundation | Provision platform and pre-incident DR cluster foundation; record DR readiness evidence |
| 5 — Service deployment | Receive CRV/DPB; Service Owner defines IG; automation selects and initially provisions it; deploy workload, associate reservation as required, then register Service → IG |
| 6 — IG lifecycle | Ongoing scaling, subscription-limit handling, reactive SKU/AZ governance, and seed-reservation scaling |
| 7 — Go-live | Complete service-owned readiness checks and DR certification where DR is offered |
| 8 — Steady state | Reconcile safely, manage buffer/quota, observe zone balance/cost, and conduct DR drills |
| 9 — DR/failback | On authorized declaration, query DR index, use Foundation and eligible capacity stages, activate standby, route recovery, and execute guarded failback |

---

## Alignment Gates

**Baseline compliance (SK-01): ALIGNED.** This flow is reconciled to baseline v4.0.2. CRV and DPB scopes, the exact-region default, Instance Group ownership, DR Foundation, sharing boundaries, and zero-not-delete are represented by their respective requirement codes below; this is a document alignment result, not evidence of runtime implementation.

**Deployment-standard compliance: OPEN for unresolved policy items.** `environment_v2.yaml` is the owner-confirmed standard, effective 2026-10-23. Its values document intended policy and do not prove enforcement. The historical `environment.yaml` differs (87 changed lines); treat it as configuration drift, not an authority conflict.

| YAML key / decision | Standard setting | Flow treatment | Status |
|---|---|---|---|
| `environment_profiles.standard` | Separate compute and resource subscriptions | DPB uses compute subscription for VM capacity, CRGs, and quota; resource subscription remains distinct | ALIGNED |
| `capacity_request_policy.allowed_vm_series` and `.approval` | VM-series mapping, Preview-series policy, approval workflow/scope have open details | New-request eligibility/approval is separate from technical readiness and does not gate protective reconciliation retroactively | OPEN |
| `compute_subscription_policies.standard.deployment.rollout` | Validate replacement and current-plus-replacement overlap before cutover | Explicit Phase 3 readiness gate | ALIGNED |
| `compute_subscription_policies.standard.dr_clusters.rollout_headroom_conflict_policy` | Owner decision pending | Do not assume rollout headroom is available to DR | OPEN |
| `capacity_reservation_policies.standard.sharing` | [Documented] CAP-013 / DEP-001: provider ownership pending; sharing is Preview | Conditional only; production fallback is a reservation in the deploying subscription | OPEN |

Open items block only the dependent readiness claim until their owners close them. Sharing is never a production dependency.

**Hard constraints: PASS for flow representation; runtime status not attested.** HC-1/4/5/8/9/10 are region-level CRV gates; HC-2/3/6/7 are per-domain DPB gates; HC-11 is a VM-eligibility gate. The flow does not claim that a deployment has passed them until the relevant checks run.

**Formula check (SK-06): N/A** — no capacity, quota, scoring, or DR formula changed. **DR sizing (SK-09): ALIGNED** — DR-017 / F.6–F.8 retain MAX-not-SUM sizing across non-concurrent sources.

**Open items touched:** DEC-001; POC-001/003/007/011/012; DEP-001; deployment-standard pending decisions in `environment_v2.yaml`.

## Traceability: Every Check to Its Requirement

| Phase | Checks applied | Requirement IDs |
|-------|---------------|-----------------|
| 0 — Onboarding | Seed lookup; exact-region default / approved geography exception | PLC-001..003, PLC-009, REG-001/003, DEC-003 |
| 1 — CRV | Region gates and customer-aggregate scoring; no DPB floor certification | HC-1, HC-4, HC-5, HC-8..10, PLC-007/008, PLC-013, F.10/F.11 |
| 2 — DPB | Per-domain subscriptions, CRGs, sizing, zone, quota and floor gates | HC-2/3/6/7, DOM-002, CAP-023/025, PLC-014/016, QUA-015, F.1–F.5/F.9 |
| 3 — Readiness | Baseline readiness + deployment-standard checks and open gates | RDY-001..004, CAP-016, `environment_v2.yaml` (effective 2026-10-23) |
| 4 — Foundation | Product cell, HA | — (platform operational) |
| 5 — Service Deployment | IG definition/selection/initial provisioning after DPB; workload association and registration | INT-001..INT-008, PLC-014, DOM-002 |
| 6 — IG Lifecycle | Ongoing scaling, subscription policies, reactive discovery | DOM-003, CAP-022, CAP-024, deployment standard |
| 7 — Prod Readiness | Service-owned gates and DR certification if offered | ENV-005, DR-021; service-specific checks require service policy |
| 8 — Steady State | Safe reconciliation, decommissioning boundary, quota monitoring, zone balance | CAP-005/008/009/010/019/024, QUA-015, PLC-016, FIN-001, DR-012 |
| 9 — DR | Declaration, gated staged acquisition, activation, guarded failback | DR-001..DR-021, F.6–F.8, POC-001/003/007/011/012, DEP-001 |
| Cross-cutting | HC-11, idempotency, stale-state, naming, Preview boundaries | HC-11, INT-002/006/007, RDY-004, OPS-006, CAP-013, DEP-001 |
