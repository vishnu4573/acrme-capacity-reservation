# ACRME - Technical Design Document (TDD)

| Field | Value |
|---|---|
| Version | 2.0 reconciliation draft |
| Date | 16 October 2026 |
| Status | v4.0 reconciliation draft - Architect decisions and POC validation pending; not ratified |
| Baseline | [Requirements baseline v4.0](../Requirements/acrme_requirements_baseline_v4_0.md) |
| Owner | Principal Cloud Architect |
| Companion | [Functional Design Document](acrme_functional_design_document.md) |
| Change history | 1.0: historical v2.4 design. 2.0: two-scope architecture, partitioned contracts, readiness/quota corrections, Foundation, guarded recovery and current validation gates. Historical text remains in Git. |

**Type:** Design Note. **Phases:** P1-P5. This target design is not a statement of implemented runtime behavior. `[Documented]` cites requirements/platform evidence; `[Decided]` cites baseline policy; `[Derived]` identifies consequences; `[Assumed]` identifies proposed implementation mechanics pending Architect approval. No live-tested claims.

## 1. Authority, scope and invariants

[Decided] Production protection, allocated-plus-buffer targets, independent capacity/quota controls, lean bootstrap, region/zone isolation, current-state decisions, zero-not-delete, config-driven policies and customer-CRV/domain-DPB separation follow baseline sections 2/3.

The [FDD](acrme_functional_design_document.md) defines behavior. This TDD specifies the technical contract. Historical ADRs/calculation material supply context, not an override of v4.0. Unresolved policy operands are **SPEC GAPs**, not defaults. Architecture approval is required before runtime implementation.

| Invariant | Enforcement |
|---|---|
| Regions once per customer/geography | CRV resolve/reuse precedes all DPBs; later domain shortage cannot trigger region re-selection (PLC-013/015). |
| Capacity per domain | ig, sets, holds, sizing, sharing, activation and cost remain domain attributed (DOM-001 through DOM-004). |
| Physical capacity matching | Exact VM size, provider subscription, region and physical zone; VM family only scopes quota (CAP-016). |
| No Preview production dependency | Prod reservations reside in the deploying subscription under CAP-013/DEP-001; Foundation also works without sharing. |
| No false READY | Fresh readiness checks residual capacity, both quota caps, outstanding intents and all HCs/approvals (RDY-001/INT-006). |
| No implicit teardown | Normal resize retains resources; CAP-010 separately gates retirement, deletion and scope removal. |
| No success-shaped fallback | Missing policy, stale/failed observations or ambiguous mappings produce reasons and tracked failure, never assumed free resources. |

## 2. Platform boundaries and evidence

Official pages accessed **2026-10-16**. Microsoft Learn search/fetch and Azure MCP documentation search were used; direct official-page fetches also refreshed evidence. Retrieval is not live POC execution. The deployment adapter's API versions remain to be pinned/validated; documentation example versions are not project certification.

| ID | Documented behavior and applicability | Source |
|---|---|---|
| S1 | Exact-size reservations; group zones, no-zone pinning, one size/zone reservation; same-subscription usage within reserved quantity must not be charged a second time; Availability Sets unsupported. SKU/region eligibility still requires validation. | [Capacity reservation overview](https://learn.microsoft.com/en-us/azure/virtual-machines/capacity-reservation-overview) |
| S2 | [Documented] Sharing is Preview; explicit consumers up to 100, same/trusted tenant, consumer quota and provider/consumer logical-to-physical remapping. Sharing examples use 2024-03-01 writes/2023-09-01 list; validate chosen adapter versions. | [Sharing](https://learn.microsoft.com/en-us/azure/virtual-machines/capacity-reservation-group-share) |
| S3 | One group membership per subscription; group spans regions/families, transfers scoped to cells; deploy-time subscription check. Requires management-group permissions/provider registrations; public cloud, IaaS and eligible agreement restrictions; quota does not confer regional/zonal access. | [Quota Groups](https://learn.microsoft.com/en-us/azure/quotas/quota-groups) |
| S4 | Both family and total-regional quota tiers; allocated and deallocated usage matters. | [vCPU quotas](https://learn.microsoft.com/en-us/azure/virtual-machines/quotas) |
| S5 | Well-formed reduction permitted regardless of associated count; increases can fail capacity/quota and require restoration of the previous quantity. CAP-004 remains a stricter programme guard. | [Modify reservations](https://learn.microsoft.com/en-us/azure/virtual-machines/capacity-reservation-modify) |
| S6 | ARM token buckets and Retry-After; Compute RP has additional independent limits. | [ARM throttling](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/request-limits-and-throttling) |

[Documented] S1's same-subscription reservation accounting and S2's shared-consumer quota requirement are distinct paths. A naive `requested VMs * vCPU` debit against already charged reservation usage can double-charge. Unknown charge/association semantics on the selected path/version block readiness with VALIDATION_REQUIRED, pending POC-001/005.

## 3. Logical components

| Component | Responsibility | Requirements |
|---|---|---|
| Inventory Collector | Scoped reservation, allocation/association, sharing, zone, subscription/group quota observations with status/freshness | CAP-001/002/014, DAT-001/003 |
| Placement & Scoring Engine | Customer aggregate CRV resolve/reuse and controlled seed change; no per-domain weighting | PLC-001 through PLC-005, PLC-007 through PLC-013 |
| Domain Manager | Deterministic DPB, domain/ig/shard lookup, set inventory, sizing/zone/quota-route binding | PLC-014/015/016, DOM-001 through DOM-004, F.12 |
| State Reconciler | Allocated+buffer desired target; guarded resize; no normal deletion | CAP-003 through CAP-010, CAP-024 |
| Quota Manager | Customer membership/cells, confirmed subscription assignments, protected commitments, allocation/reclamation/replenishment | QUA-001 through QUA-015 |
| Readiness API | Ordered two-scope validation, exact residual capacity/quota gate, durable intent and explainable result | RDY-001 through RDY-004, INT-001 through INT-008 |
| DR Index/Activation services | Domain-attributed source mapping, scenario sizing, Foundation/extension, staged activation/failback | DR-001 through DR-021 |
| Config Service | Scope, catalogue, taxonomy, weights, approval rules, buffers, naming, thresholds, schema versions | DAT-005/006, REG-001, C-1 through C-16 |
| State/Operation Store | Versioned authoritative entities, durable operation/intent records, audit and history | DAT-001 through DAT-006, INT-006/007 |
| Forecast/Increase service | Advisory customer/domain trend and governed proactive expansion, separate from reconciliation | FWD-001/007, FIN-003, NFR-009 |
| Governance/Observability | Scoped identity/approval, metrics/alerts, immutable changes, dry-run/runbooks | GOV, OBS, OPS |

[Derived] Boundaries are logical and can remain modules of one control application; adding the Domain Manager does not mandate a new deployed microservice. Existing runtime modules are not certified by this document.

## 4. Runtime and ordered pipeline

[Decided] The reference reconciliation execution is a container-app job packaged as a Docker image, scheduled every six minutes (CAP-006), not an always-running scheduler requirement. `reconcile_interval_seconds` is configurable; production interval awaits POC-010. Placement uses a function-app/API or GitHub Actions flow (PLC-009), not a logic-app runtime.

1. Validate request schema, ownership, policy/version and correlation/idempotency.
2. Read fresh customer seed. If absent, resolve exact-region/default or approved geography-exception CRV. Persist one authoritative CRV using optimistic concurrency; a competing creation re-reads the winner.
3. Read CRV, then resolve domain ig/shard and DPB. Reject requested subscription/region inconsistent with binding; no domain re-scoring.
4. Refresh observations synchronously if stale; if refresh fails return STALE_STATE.
5. Calculate readiness and acquire capacity/family/regional intent atomically or through a durable equivalent with no partial spend.
6. Return deployment decision or tracked asynchronous operation; no long Azure change is hidden behind a synchronous READY.
7. AEP associates/deploys, reports actual outcome; confirm holds or compensate safely. Unknown outcomes retain commitments until inventory proves resolution.

Canonical [pipeline](diagrams/acrme_v4_pipeline.mmd) replaces old runtime/onboarding diagrams. Snapshot freshness applies to CRV decision inputs, cached binding validation, DPB and readiness. Freshness refresh never regenerates a seed.

## 5. Subscription, CRG and quota topology

[Decided] Control identity runs in the platform subscription with scoped roles to domain ig subscriptions. One ig per `(customer,domain,environment,region)` resolves the subscription/shard registry; domains never share an ig. POC-006's physical DR subscription/cluster topology remains open, so do not manufacture a dedicated-cluster decision.

| Set | Ownership / usage |
|---|---|
| prod (`pr`) | Domain Prod ig in CRV Prod region; local deploying-subscription reservation, never shared capacity with CVAL/DR |
| cvdr | Same-domain CVAL/DR extension under CAP-025; service-impacting release only on authorized declaration/exercise |
| drf | Domain DR ig in CRV DR region; independent always-present Foundation with pre-staged quota |

[Documented] CAP-023/OPS-006 default to a zonal group with declared immutable zone set and exact-size/zone reservation children. Optional `az1/az2/az3` groups are policy variants, not a mandatory `1 regional + N` model. `reg` is a no-zone SKU exception and not a region-wide interchangeable pool (S1).

[Decided] Names are config-driven (OPS-006/C-12): RG `rg-odcr-<env>-<region>-<NN>`; CRG `crg-<pr|cvdr|drf>-<region>-<zonal|azN|reg>`; subscription carries customer/domain/function/shard lineage, e.g. `sub-jda-cld-cr-prod-wl-tms-wus2-01`. Domain lives in subscription/registry identity, not the CRG name; resolve uniqueness with subscription/resource ID, never name alone.

[Documented] The customer Quota Group is a management-group-scoped object spanning domain subscriptions; region/family cells are children of the accounting model, not new memberships (S3/QUA-004/015). Verify eligible subscriptions, provider registration, roles and region/zone access. Do not offer a multi-group fallback that places the same subscription in several groups.

[Decided] Preview sharing is explicitly opt-in, domain bounded, same-region and limited to authorized supported tenants/consumers. Record provider/consumer subscription, exact CRG/reservation, provider logical zone and physical ID plus consumer mapping/version. Validate mappings at deployment; matching logical strings are insufficient. Count provider capacity once, apportion actual allocations; authorization is not allocated quantity (CAP-013 through CAP-016, POC-003/012). Foundation and Prod coverage must not depend on Preview.

See [topology](diagrams/acrme_v4_topology.mmd). Historical ADR topology/PNGs are not the current implementation specification.

## 6. Data and compatibility contract

[Derived] The following logical fields make baseline DAT-002/INT-008 explicit; storage technology and wire schema are proposed pending Architect/API consumer approval. All persisted entities have `schema_version`, `record_version`, timestamps and ownership. Observation fields additionally carry source, collected time and collection status; derived decisions carry input snapshot references and policy/engine versions.

| Entity | Identity / required payload |
|---|---|
| CustomerSeedRecord | `(customer_realm_id, geography)`; `crv_ref`, domain/DPB references, products, input mode, decision/config/engine versions, exception/approval metadata |
| CustomerRegionVector | `(customer, geography, binding_version)`; distribution model, Prod/CVAL/DR (nullable only with NOT_OFFERED reason), country policy, policy/snapshot lineage |
| DomainRegistry | `(customer, domain)`; taxonomy/function token, owner, approved products/policy (DEC-004/C-14) |
| InstanceGroup | `(customer, domain, environment, region, shard)`; ig ID, subscription/resource scope, quota-group membership, enabled status |
| DomainPlacementBinding | `(customer, domain, environment, region, shard, binding_version)`; CRV reference, ig/subscription, set-class/resource IDs, zone plan, buffer/sizing policy and quota route |
| ReservationState | Full Azure reservation resource ID; DPB/set/domain, exact SKU, family, region, provider logical/physical zone or non-zonal marker, reserved/allocated/associated counts, provisioning state and snapshot |
| ZoneMappingRecord | Subscription pair, region, provider/consumer logical zones, physical-zone ID, mapping source/version/collection status |
| QuotaMembership | Customer/group resource ID and member subscription; region/family scope never forms a second membership |
| QuotaCell | `(group_id, region, family)`; observed available transferable quota, approved limit/assignment evidence, engine earmarks, pending operations |
| SubscriptionQuota | `(subscription, region, quota_name)`; family or total-regional limit/usage/headroom; no zone key for quota |
| SourceDestinationDRIndex | `(customer, domain, source_region, destination_ig, exact_sku, physical_zone, assignment_id)`; destination region/subscription/DPB, standby refs, count/vCPU, priority, plan/config version and activation state |
| CVALEarmarkRecord | `(customer, domain, cval_ig, reservation_id, assignment_id)`; CVAL capacity, releasable quantity, earmark beneficiaries/source scenarios, release prerequisites and confirmed release |
| DeploymentIntent | Durable ID; request digest, customer/domain/DPB, exact capacity claims, family AND regional quota claims, snapshot/policy, version, expiry/outcome state |
| ActivationRecord | `(incident_id, assignment_id, wave)`; customer/domain, source/destination, target/confirmed count, stage, approvals, state, deficit, failure/reversal history |
| OperationRecord | Operation/idempotency ID, canonical payload digest, expected versions, saga steps, external handles, approvals, compensation/status/error |
| AuditEvent | Append-only event ID, actor, before/after, scope/domain, reason, timestamp, correlation, operation/policy/snapshot links |

Never place multiple family/zone/domain assignments in one overwriteable customer/source/destination row. `quantity_vcpu` is not interchangeable with VM count; retain `exact_sku`, `vCPU_per_instance` and count.

[Assumed] Proposed intent lifecycle is `HELD -> DEPLOYING -> CONFIRMED`, or `HELD -> RELEASED` when proven unused; uncertain/failed deployment goes to `RECONCILE_REQUIRED`, not automatic free capacity. Release/debit keys are idempotent. Expiry alone is insufficient to release a claim after an external operation may have started.

[Decided] DAT-006 requires versioned schema/API compatibility for an approved transition period. Legacy requests lacking domain cannot be guessed into TMS/WMS. Use explicit version adapters only where a single unambiguous approved mapping exists; otherwise return VALIDATION_REQUIRED with migration reason. Migration drafts must preserve audit, old seed lineage, intent state and history, support replay/rollback and never reselect customer regions. Actual transition period and adapter rollout need AEP approval.

Class view: [domain and commitment model](diagrams/acrme_v4_domain_model.mmd).

## 7. Engine modes, pause and recovery

| Mode | Mutating behavior |
|---|---|
| STEADY_STATE | Scoped normal reconcile/governed increases; no incident transfer |
| DR_DECLARATION_PENDING | Declaration recorded, activation approval pending; no service-impacting CVAL release |
| DR_EVENT_ACTIVE | Approved incident source/waves only; separate CVAL action authorizations |
| FAILBACK_PENDING | Approved reversal/recovery work; no automatic seed regeneration |
| INCIDENT_HOLD | Inventory/audit/alerting retained; mutation blocked pending diagnosis/authorized resumption |

[Assumed] Proposed correction to historical T6: persist `interrupted_mode`, incident ID, approvals, outstanding operation versions and hold reason. Safety trips from any working mode enter hold. Restored freshness is necessary but not sufficient for resumption: revalidate policy/resources, reconcile in-flight operations and approve the exact target mode. Return to steady state only if the interrupted mode was steady and no unresolved incident/failback exists. Resume active DR/failback to its recorded mode; incident closure follows authorized completed failback.

The [mode diagram](diagrams/acrme_v4_engine_modes.mmd) labels this as proposed. Exact recovery authorization remains an Architect decision. No blanket `INCIDENT_HOLD -> STEADY_STATE` transition or declaration sequence bypasses pending/activation approval. OPS-002 pause is an operator mutation gate, not evidence an incident ended.

Concurrency uses optimistic versions plus durable intent/operation records (INT-006/NFR-002/007). Capacity claims lock the exact reservation partition; quota claims also protect the shared `(subscription,region)` cap across families. A storage transaction/serialized coordinator or equivalent must cover all claims; per-document CAS alone is not proof of multi-record atomicity. Implementation mechanism remains proposed until failure/recovery tests establish equivalent guarantees.

## 8. Placement, quota and zone algorithms

### 8.1 Customer CRV and domain DPB (F.10 through F.13)

```text
Exact-region path:
  validate supplied Prod against catalogue, HC and policy; Prod is NOT selected by scoring
  score customer-aggregate candidates for CVAL/DR, apply distribution model
Geography exception:
  require approval + acknowledgement
  select lowest-risk suitable Prod from eligible geography candidates; derive CVAL/DR
Both:
  persist/reuse CRV(C,G); for each domain D and environment E:
    R = CRV(C,G).region(E)
    ig = registry.lookup(C,D,E,R,shard)
    DPB = bind(ig, CAP-025 sets, F.1-F.3 sizing, F.9 zones, QUA-015 route)
    do not call region scoring at domain scope
```

[Decided] Two-region CVAL/DR co-location, optional US co-location, ME local Prod/CVAL and European DR, and per-country NOT_OFFERED follow the FDD. Restricted regions never enter automated scoring; exact restricted Prod uses governed exception processing.

```text
TotalCustomers(g) = count distinct customer with >=1 provisioned/deploying environment in g
gamma(r,env) = 1                                      if TotalCustomers(g)=0
             clamp(1 - EnvCustomers(r,env)/TotalCustomers(g), 0, 1) otherwise
Score_Pool(C,R) = sum_f(weight_f * normalized_factor_f(customer aggregate C,R))
```

[Decided] PLC-012/F.10/F.11 define this live denominator and customer scope. Required factors include allocated capacity, available reservations, quota, buffers, expected DR, zones, freshness and fairness. Weights must sum to 1.0 at policy load; reject/audit an invalid policy before publication.

**SPEC GAP:** Baseline does not fix each factor's normalization, weight vector, missing/zero-denominator handling, score direction or tie policy. The old alpha/beta/gamma/delta/epsilon values `0.30/0.20/0.25/0.15/0.10`, `PS_*` ratios and `0.001` sum tolerance are historical configurable proposals, not approved v4.0 formula substitutions. Do not use them as a production default or claim `PS_Prod` selects exact-region input. Config must specify finite nonnegative weights, precision, factor units/direction and ties; otherwise return VALIDATION_REQUIRED. Preserve shadow/recommendation evaluation until approved and validated. Retain every candidate's policy/snapshot/factor explanation.

### 8.2 Reservation quantities (F.1 through F.3)

For partition `p = (customer,domain,environment,ig,region,exact_sku,physical_zone,set_class)`:

```text
DesiredTarget(p) = Allocated(p) + Buffer(p)                         # F.1, VM instances
Headroom(p)      = Reserved(p) - Allocated(p)                       # F.2, signed
Deficit(p)       = max(0, DesiredTarget(p) - Reserved(p))            # F.3
```

[Decided] Buffer is configured by workload/product/region/environment/SKU; no universal percentage. Count each VM once under provider allocation, including consumer allocation if shared. Physical-zone capacity is never moved across zones by arithmetic.

### 8.3 Quota object, cells and accounting (QUA-002 through QUA-015)

```text
FamilyHeadroom(s,r,f) = observed_family_limit - observed_family_usage    # vCPU
RegionalHeadroom(s,r) = observed_regional_limit - observed_regional_usage
AvailableQuota(s,r,f) = min(FamilyHeadroom(s,r,f), RegionalHeadroom(s,r)) # QUA-007/F.12
```

[Decided] B1 accepted by the user on 22 October 2026: use the two-cap formula above with explicit subscription/shard scope, consistent with QUA-007/F.12. `s` is the actual subscription/shard resolved by the domain DPB, `r` the bound region and `f` the VM family; all limits, usage and headroom are vCPU. The baseline F.4 display amendment remains unapplied.

[Documented] Total-regional quota is per subscription and region, not a shared limit across domain subscriptions (QUA-002/007). Each shard is evaluated independently; spare quota in another shard does not make the bound subscription ready. Any shard reassignment requires the approved binding policy. Regional quota is shared across families within that subscription: compare the sum of the request's incremental regional debits against one regional residual, not each family independently. B1 does not approve outstanding API charge semantics or a new shard-routing policy.

[Derived] Keep these separate:

| Value | Meaning / invariant |
|---|---|
| `group_transferable_vcpu` | Observed unassigned quota available for a cell; never computed from CRG sizes |
| `subscription_limit/usage` | Observed assigned limit and charged usage, family and regional |
| `pending_transfer` | Durable submitted operation; no usable quota until confirmed subscription observation |
| `quota_intents` | Additional approved commitments not yet reflected in observed usage; settle once observed, not subtract twice |
| `protected_floor` | Usage/committed demand/Prod buffer/DR need protected by policy; no NonProd encroachment |
| `desired_procurement` | Forecast/policy need; not an approved limit or deployable balance |

For an internally consistent cell snapshot, transfers conserve observed allocated-plus-unassigned quota absent an approved increase/decrease. Never combine stale before/after observations into a fictitious conservation result. Verify source debit, target credit and operation ID; disagreement blocks automatic allocation and alerts.

[Derived] NonProd allocatable balance is the nonnegative remainder after the **union** of protected claims and outstanding holds, not a sum of overlapping usage, floor and earmark totals. Protected floor definitions must specify overlap and eligibility; missing definitions are VALIDATION_REQUIRED. Reclamation cannot lower a subscription below usage plus distinct uncharged commitments and applicable buffers/DR protection. Failed-region quota is not a transferable destination source.

Proposed tracked transfer lifecycle: `REQUESTED -> APPROVED -> SUBMITTED -> CONFIRMED`, with explicit `FAILED`/`RECONCILE_REQUIRED` and compensating operations. Every allocation/reclamation has actor/reason/before/after/correlation. No assumed propagation SLA.

[Decided] QUA-015 defaults group/subscription thresholds to 0.85, both Configurable. **SPEC GAP:** the baseline does not define whether group-cell utilization includes earmarks, assignments or charged use, nor total entitlement/zero-limit semantics. The approved policy must define numerator/denominator and subscription family/regional trigger combination before executable automation. An undefined/zero entitlement is reported for validation/request governance, never silently 0% healthy. Do not invent a numeric production default.

### 8.4 Forecasting versus reconciliation

[Decided] Reconciliation is F.1, not forecast demand (CAP-003/FWD-007). Customer-aggregate and per-domain ig trends feed forward forecasting (FWD-001). Forecasting remains advisory in the initial phase; cost/approval precedes persistent expansion.

The historical candidate `ForecastQuantity = ceil(ForecastPeak*(1+GrowthBuffer)+DRBuffer)` and horizons 30/60/90 days, alert 14 days at 80%, 30-minute cooldown and utilization thresholds 0.35/0.20 are **[Assumed] Configurable proposals**, not baseline defaults. Preserve them only as review inputs; automated `max(F.1,forecast)` targets need an approved independent expansion policy, never silent replacement of F.1. Scope cooldown by actual domain/reservation, not a cross-domain `(region,CRG type)` bucket.

### 8.5 Per-domain zone balancing (F.9/PLC-016)

```text
Target(D,E,z) = round(VMs(D,E)/ZoneCount)
Skew(D,E,z)   = VMs(D,E,z) - Target(D,E,z)             # integer VM-count units
MaxSkew(D,E)  = max_z(abs(Skew(D,E,z)))
Rebalance    = MaxSkew > configured_count_tolerance
PreferredZone = argmin eligible_z(VMs(D,E,z))
RegionZoneLoad(R,E,z) = sum_D VMs(D,E,R,z)             # observer only
```

Eligibility includes supported exact SKU, physical-zone mapping, capacity, subscription quota and HC-5's configured minimum zones (not a substitute `az_count>=1`). Evaluate prospective placement/growth skew; rebalancing is a recommendation/action subject to approval and feasibility, never automatic live migration.

**SPEC GAP:** rounding convention, residual assignment, equal-count ties and initial zero-workload placement order require policy approval. For zero VMs, report zero count/skew; do not divide by zero. Do not enforce rounded targets as a total-capacity invariant: e.g. rounding each of three `10/3` targets does not sum to ten. No fixed +/-10 percentage-point tolerance replaces C-13's count-skew policy.

## 9. DR algorithms, Foundation and activation

### 9.1 Partitioned source scenarios (F.6 through F.8)

Let `p` be an isolated destination domain/ig/exact-SKU/physical-zone capacity partition, and `q(s,p)` the sum of all protected assignments from source region `s` to that partition (VM instances, convertible to vCPU only via exact SKU).

```text
Requirement(p) = max_s q(s,p)                         # non-concurrent sources, F.6
Gap(p)         = max(0, Requirement(p) - Usable(p))    # F.7
Overcommit(p)  = sum_s q(s,p) / max_s q(s,p)           # F.8, positive demand only
```

[Decided] First aggregate concurrently failing assignments from the same source, then MAX across approved mutually exclusive source scenarios. Domain isolation means summing independently required domain reservations for estate reporting; do not reserve one aggregate MAX across domains. C-11 SUM override needs explicit approved policy and funding.

[Derived] Distinguish **confirmed usable now** (uncommitted Foundation/residual allocations and confirmed releases) from **conditional recovery potential** (CVAL still running, requested sharing, expansion or pending quota). F.7 scenario reports may include approved acquisition paths but must label prerequisites/stage/guarantee. Conditional potential never passes immediate readiness.

B2: equal positive source portions yield ratio n, not 1. Empty/all-zero demand has no defined ratio convention yet: emit an explicit unresolved metric/status rather than divide or present a risk score. This informational ambiguity need not block unrelated positive-demand readiness.

B3: ME contributions in Europe participate in domain-attributed sizing, but "one source failure globally" versus "one per geography" remains unresolved. Do not certify concurrent ME+Europe protection from a single-source MAX. Maintain scenario IDs and expose excluded/unapproved scenarios and deficits.

### 9.2 Two-layer lifecycle and staged acquisition

[Decided] Foundation is `drf`, always present per domain in its CRV DR region, sized by C-16/ENV-005/DR-007, with pre-staged quota. It starts control planes and business-approved priority waves independently of sharing. Zero bootstrap requires explicit approval (ENV-006); a count-0 seed matrix is not proof Foundation bootstrap exists.

Extension uses that domain's `cvdr` set on authorized release. Never borrow another domain's quota floor/capacity or double-count live CVAL. ME local CVAL is not a Europe DR source. Resolve POC-006 physical topology, POC-007 bootstrap, POC-011 overcommit and POC-012 sharing before affected production reliance.

| Stage | Required action / confirmation |
|---|---|
| 1 | Consume approved Foundation/bootstrap with confirmed target subscription quota and ready orchestration |
| 2 | Use already available destination residual reservation AND quota |
| 3 | Approve, shut down/deallocate/disassociate eligible CVAL per validated state semantics; confirm actual release |
| 4 | Apply approved supported same-domain sharing/reassignment, physical zones and consumer quota |
| 5 | Allocate pooled quota; confirm subscription state before further deployment |
| 6 | Request additional Azure quota/capacity, track asynchronous state/failure |
| 7 | Report unrecoverable gap and priority impact; never claim complete recovery |

[Derived] Stages are ordered acquisition preferences, not permission to deploy before needed quota arrives (DR-006/QUA-013); no "zero Azure wait" claim. No cross-group transfer does not imply quota is already assigned.

### 9.3 Activation, tiers and failback

[Decided] Authorized declaration records pending mode; activation approval enters active mode. Query the failed source's index and activate exact standby assignments in business priority (control planes, P0/P-1, later waves). Each `associated -> allocated` operation records counts, resource IDs, incident/domain, stage, approvals and outcome. Mere association or API acceptance is not confirmed allocation. Uncertain/failed actions are retried only under idempotent recovery or raised as tasks.

Historical tier concepts remain: additive direct expansion, governed reclaim/reallocate within the group, destructive association-changing escalation. **[Derived]** "Quota neutral" at group total does not remove target-subscription checks/transfer latency. Tier 2 approval and target quota confirmation remain required; destructive Tier 3 is blocked in Phase 1 and requires later explicit authorization, impact review and audit.

Failback preserves seed/CRV/DPB/index/history; track `ACTIVE -> FAILBACK_PENDING -> STANDBY` per assignment after verified reversal, with approved priority/dependency ordering. A simplistic reverse-wave order is a historical proposal, not an approved safety guarantee. DEC-002 chooses duration; incident closure requires all intended reversals/accepted exceptions recorded.

## 10. Steady-state capacity lifecycle

1. Run only when mode/pause/override policy permits; read current scoped observations.
2. Validate eligibility, freshness, resource identity and config; missing resources block activation.
3. Compute F.1 desired target and F.3 deficit per partition.
4. Apply association, allocated, minimum-hold, maintenance, active override, Prod buffer, Foundation and DR/CVAL protection guards. Record desired versus executable target and reason.
5. Obtain required approval (initial Phase 1 decreases remain operator-gated).
6. If quota action needed, submit only a justified delta; confirm both caps on the relevant subscription.
7. Resize retained reservation, track asynchronous state and confirm actual quantity; never assume requested equals actual.
8. If grow fails, expose deficit/alert; if resource enters Failed, track recovery/restoration to last safe quantity under S5, not a silent success.
9. Refresh observations, settle commitments, append audit and close or leave recoverable operation.

[Decided] Desired target may legitimately be 0. CAP-004's associated-count guard and other floors may constrain executable shrink; report that instead of redefining F.1 (B4). CAP-009 retains zero objects. CAP-010 intentional retirement/deletion/scope removal remains a separate approved workflow. No normal reconciliation deletes resources or infers teardown intent from transient allocation drops.

## 11. API architecture and readiness

### 11.1 Versioned contract

[Derived] Proposed vNext payload (requires DAT-006/AEP approval, not an assertion that current code implements it):

```text
POST /placement
  customer_realm_id, geography, domain_group, product, environment,
  production_region OR geography_exception{approval_ref,acknowledgement_ref},
  requested_subscription, demands[{exact_sku,count,zone_requirement}],
  priority, requested_at, correlation_id, idempotency_key, expected_version
  -> crv_ref, dpb_refs[], ig_subscription, crg_sets[], zone_spread,
     quota_draw_route, readiness_result, operation_handle, trace_id

POST /readiness
  customer_realm_id, geography, domain_group, environment, product,
  crv_ref, dpb_ref, subscription, region,
  demands[{exact_sku,count,zone_requirement}], priority, requested_at,
  correlation_id, idempotency_key, expected_version
  -> readiness_state, deployment_permitted, reasons[], required/available quantities,
     guaranteed/unguaranteed coverage, quota_status, snapshot_refs/timestamps,
     policy/engine/schema versions, decision_id, intent_ref, operation_handle

POST /capacity/increase, /quota/allocate, /sharing/activate
  -> tracked OperationRecord (scoped approval + desired-state idempotency)
POST /dr/declare, /dr/activate-wave, /dr/failback, /operations/resume
  -> incident-scoped OperationRecord / ActivationRecord
GET /operations/{id}, /audit, /state
  -> authorized read-only status/evidence
```

Validate nonnegative counts and defined exact SKU/vCPU mappings; zero count is an explicit no-growth operation, not an implicit retirement. Enforce identity, policy, supported scope and approved versions before mutation. Same idempotency key + identical desired state returns original operation; changed payload is a conflict, not replay of an earlier READY. AEP reports confirmed resource outcomes; failed deployment triggers INT-007 compensation/reconciliation.

### 11.2 Readiness algorithm

[Derived] `p` is an exact reservation partition. `H(p)` is other uncharged, still-valid capacity intents; `P(p)` is capacity protected from **this** request, excluding claims already represented in allocated or H. Approval policy must define overlap; do not blindly subtract the same DR floor and CVAL earmark twice.

```text
Allocatable(p) = max(0, Reserved(p) - Allocated(p) - H(p) - P(p))
CapacityDeficit(p) = max(0, RequestedIncrementalCount(p) - Allocatable(p))
FamilyResidual(s,r,f) = FamilyLimit - FamilyUsage - other_uncharged_family_claims
RegionalResidual(s,r) = RegionalLimit - RegionalUsage - other_uncharged_regional_claims
```

Request quota deltas are incremental, not already charged VM/reservation usage. Shared consumers must establish their own quota; same-subscription covered reservation use is not double-debited (S1/S2). Existing associated standby, over-allocation and CR growth need version-specific charge semantics; missing evidence produces VALIDATION_REQUIRED, not zero debit.

**READY requires all:**

1. Request/ownership/schema valid; CRV resolved/reused and DPB deterministic/consistent.
2. Region/catalogue/legal/model approved; HC-1 through HC-11 pass in their scopes.
3. Exact SKU eligible; physical zone supported/mapped; no Availability Set.
4. Policy known; required reservation exists, healthy, and matches subscription/region/SKU/zone/authorization.
5. Every partition's incremental demand fits allocatable capacity, or approved over-allocation goes through the explicit risk branch (not guaranteed READY).
6. Each family delta fits family residual; sum of request's regional deltas fits **one shared regional residual**.
7. No protected-floor encroachment or unconfirmed quota transfer used as supply.
8. Every source observation is fresh and consistent; policy/expected versions still current.
9. Acquire all capacity/family/regional claims without partial double-spend; on version conflict re-read/re-evaluate.

Return the eight FDD/RDY-002 states exactly. `deployment_permitted` is false for quota/reservation deficits, unavailable capacity, stale, policy blocked and validation-required. READY_WITH_RISK requires a named approved risk policy and cannot override quota/HC/freshness failures. Return all reasons; **[Assumed]** primary-state precedence needs AEP approval before wire-contract implementation, not an invented ordering here.

### 11.3 Durable concurrency and outcome

Do not atomically hold only a seed row while capacity/quota remain unprotected. Use version-checked multi-claim commit or equivalent serialized allocator with durable recovery. Lost updates, partial hold creation and retry/replay must be testable. Holds convert to observed usage once, with resource linkage; never leave both an observed debit and duplicate hold. Expiry/release depends on safe external outcome, not elapsed time alone (section 6).

## 12. Security and governance

[Decided] GOV-001 through GOV-009: managed/workload identity, least-privilege cross-subscription/resource scope; separate policy/exception approval from execution/audit. Explicit consumer authorization and domain/customer isolation apply to every read/write. Managed identity does not imply permission across arbitrary subscriptions.

High-impact changes require recorded scope, actor, reason, before/after, approval and audit. Break-glass is bounded, expires and retains evidence; it is never an undocumented readiness fallback. No credentials in source/config/logs. Customer placement metadata is classified; telemetry must avoid unnecessary sensitive content.

OPS-003 overrides include expiry/reason and are respected until expiry/revocation. Inventory and alerting continue under safe pause/hold; backup/restore and reconstruction protect state/config/audit (NFR-006).

## 13. Observability and operational evidence

| Signal | Required dimensions / action |
|---|---|
| Reservation target/deficit, allocated/associated, residual and constrained shrink | Customer/domain/ig/environment/region/exact SKU/zone/set, desired/actual and guard reason |
| Quota assigned/used/free, transferable balance, commitments and pending transfers | Group/cell/subscription/family plus shared regional cap; distinguish observed from desired |
| Foundation/extension and max-source coverage | Domain/partition/source scenario; confirmed-now versus conditional potential |
| Activation/partial failure/failback | Incident, assignment, stage, wave, approvals and confirmed counts |
| Region zone load | Combined customer-domain observation and C-15 alert; no aggregate reservation mutation |
| Idle cost | Customer/domain/environment/region/source attribution; cvdr single-count; drf DR function |
| State age/429/retries/latency | Source observation, subscription/provider/operation, configured freshness/SLO |
| Governance | Missing resources, unauthorized sharing, schema/policy failure, overrides and owner/escalation |

[Decided] OBS-001 through OBS-005 require dashboard/SLO reporting and contextual alerts; FIN-001/004/008 govern attribution and overcommit risk. Undefined ratio/coverage scenarios are visibly unresolved, not 100%-healthy gauges. Retain histories to explain decisions and support forward trends.

## 14. NFRs, performance and forward items

[Documented] ARM's documented subscription read bucket is 250 tokens with 25/second refill; writes 200 with 10/second refill (S6). Limits are per scoped principal/subscription/region/operation with additional global/tenant bounds; Compute RP limits are separate. These are platform reference values, not guaranteed sustained throughput for this engine. Configure conservative operation budgets and adapt to remaining-request headers/429/Retry-After, jitter, batching, retry caps and deadlines (NFR-005).

```text
GroupCount = count distinct planned (subscription,region,set_class,group_shard)
ReservationCount = sum over groups count(supported exact_sku, eligible zone) children
RequestsPerCycle = sum(operation reads/pages + due writes + confirmation polls + retries budget)
MeanRequestRate = RequestsPerCycle / configured_interval_seconds
```

[Derived] A VM size adds a reservation child, not automatically a group. Include customer/domains/igs, group variants, pagination and selected endpoints. Mean rate alone does not prove burst compliance; enforce per-provider/per-scope budgets. Six-minute reference means 360 seconds when selected, never a hard-coded 300-second denominator.

[Decided] NFR-001 through NFR-010 require decision-path degraded behavior, concurrency safety, tracked long operations, hundreds-of-subscriptions scale, throttle resilience, reconstructable state, idempotency, testable formulas, dry-run and explanations. Stale data blocks deployment; an unavailable store must not fabricate READY. Approval of exact latency/availability targets, backup recovery and production interval remains required.

Historical P95 proposals (<2-minute targeted reconcile, <15-minute stable age, <=2-cycle drift) are **[Assumed] Configurable**, not approved SLOs. Readiness still honors its configured max age, not the historical 15-minute value.

Dry-run covers reservation/quota changes, CRV/DPB placement, DR scenarios, costs and compensation without mutation. Forward items FWD-001 through FWD-007 remain scoped: customer-aggregate region forecast, domain-ig sizing/trends, domain zone optimization, quota replenishment planning, FinOps attribution, two-scope placement core and INT-008 consumer payloads. No advisory forecast/migration becomes automatic policy by inclusion here.

## 15. Decisions and POC dependency register

| Item | Required treatment |
|---|---|
| B1 | Accepted 22 October 2026: explicit subscription/shard two-cap formula in section 8.3; baseline F.4 display amendment unapplied; API charge semantics remain gated |
| B2 | Proposed baseline wording for F.8 arithmetic; baseline file unchanged; positive-demand math retained; zero-demand reporting approval pending |
| B3 | Architect/business approval of cross-geo scenario guarantee; no silent global-single-failure assumption |
| B4 | Preserve CAP-004 current guard; seek desired/executable/acceptance clarification |
| Design approvals | Mode resumption, factor normalization/ties, threshold utilization, zone rounding, incremental quota paths, multi-claim mechanism, API compatibility and primary-state precedence remain explicit |
| POC-001 | Consumer quota documented; validate approved adapter API version, not an optional gate |
| POC-002/003 | Sharing order and physical-zone mappings, within supported Preview scope |
| POC-004/005 | Throttling/failure recovery and association-state semantics |
| POC-006/007 | Physical DR topology and workload/control-plane bootstrap minima |
| POC-008/009/010 | Quota/reservation buffer policy and production cadence |
| POC-011 | MAX overcommit production safety and residual concurrent-failure risk |
| POC-012/013 | Domain sharing isolation and live two-scope TMS/WMS end-to-end validation |
| DEC-002/003/004 | Failback duration, geography-exception approver, taxonomy |
| DEP-001 / A-ME1 | Reservation Sharing maturity / country-specific residency approval |

Unresolved items block affected guarantees/automatic behavior, not unrelated document reconciliation. No POC was run here. Proposed wording is a review artifact, not a requirement amendment.

## 16. Requirement and acceptance traceability

| Baseline group | Component/algorithm/entity | TDD sections |
|---|---|---|
| REG-001/002/003; ENV-001 through ENV-007 | Config, CRV distribution/eligibility, set separation/Foundation | 1/4/5/8/9 |
| CAP-001, CAP-001a, CAP-002 through CAP-025 | Collector, reconciler, scope/seed matrix, partition targets, retained lifecycle | 1/3/5/8.2/10/11 |
| QUA-001 through QUA-015 | Membership/cells, subscription caps, confirmed transfer and protected claims | 5/6/8.3/11 |
| RDY-001 through RDY-004 | Readiness, snapshots, durable intent | 4/6/11 |
| PLC-001 through PLC-005; PLC-007 through PLC-016 | Customer scoring/CRV -> deterministic Domain Manager/DPB -> readiness | 3/4/8; PLC-006 retired |
| DOM-001 through DOM-004 | Domain/ig registry, DPB ownership, bounded sharing | 5/6/8/9 |
| DR-001 through DR-021 | Index/assignment, source-scenario MAX, Foundation, stages, activation/failback | 7/9/15 |
| FIN-001 through FIN-008 | Cost evidence, per-domain attribution, governed expansion | 8.4/13/14 |
| INT-001 through INT-008 | Versioned AEP contract, intents, operations/compensation | 4/6/11 |
| DAT-001 through DAT-006 | Versioned state/history/config/compatibility | 6/12 |
| OBS-001 through OBS-005 | Domain/source-aware metrics, alerting, SLOs | 13/14 |
| GOV-001 through GOV-009; OPS-001 through OPS-006 | Identity/scope/approval/audit, pause/overrides/runbooks/naming | 5/7/10/12/13 |
| NFR-001 through NFR-010 | Degraded path, multi-claim safety, throttling, restore, simulation/explanation | 6/7/11/14 |
| C-1 through C-16; POC-001 through POC-013; DEC-001 through DEC-004; DEP-001 | Config and open validation register | 5/8/9/14/15 |

FDD section 7 maps every baseline acceptance criterion 1-26. Technical evidence: inventory/targets (1-3), integrity/readiness (4/5/8), quotas/intents (6/7), seed (9), scenario/activation (10/11/16), metrics/audit (12/13), degraded/dry-run (14/15), eligibility/matrix/topology/zones/lifecycle (17-21), multi-domain paths/sets/Foundation/quota/forward simulation (22-26). These are required validation cases, not completed acceptance claims.

## 17. Worked checks and gates

| Case | Recomputed result / required decision |
|---|---|
| Reserved 10, allocated 9, request 2; no other claims | Residual 1, deficit 1; raw `10 >= 2` must not yield READY |
| Family limit/use 100/60; regional 200/196; new uncharged request 8 vCPU | Available min(40,4)=4; quota deficit 4 |
| Two family requests each 3 vCPU, regional free 4 | Aggregate request 6 blocks; independent family comparisons cannot approve both |
| Two concurrent requests for the last unit | One intent commits; other conflicts/re-evaluates; no double-spend |
| TMS/WMS same customer | Same CRV regions, separate DPB/ig/sets/quota claims; no domain re-scoring |
| Source portions 120/80 in one compatible partition | MAX=120, SUM=200, saving 80, ratio 1.6667 |
| Isolated domain portions TMS 120/80, WMS 20/60 | Requirements 120+60=180; aggregate MAX 140 cannot replace isolated protection |
| Source portions 100/100 | F.8 ratio 2, not 1 |
| No positive DR demand | No ratio division; unresolved reporting convention explicitly flagged |
| Domain zones 15/10/5 | Target 10 each, max count skew 5; percent drift 1/6 is not count tolerance |
| Allocated/buffer/associations all 0, no protected floor | Legitimate target 0 can retain object; DR requires separately approved bootstrap policy |
| Active DR interrupted by hold, inputs restored | No automatic steady-state exit; incident/resumption/failback guards remain |
| Foundation-only activation | Confirmed quota/capacity required without sharing; pending extension not immediate supply |
| Missing quota charge semantics or cross-geo scenario set | VALIDATION_REQUIRED/coverage blocker for affected claim, not assumed zero debit or guaranteed coverage |

### Baseline compliance

| Codes | Reconciliation status | Remaining gate |
|---|---|---|
| PLC-013/014/015, DOM-001/002/003/004, INT-008, DAT-002 | ALIGNED in design contract | API/storage detail approval, POC-013 |
| CAP-013/023/025, DR-021, DEP-001 | ALIGNED in topology/boundaries | POC-006/007/012 and applicable Preview approval |
| RDY-001, QUA-004/007/013/015 | ALIGNED in checks; automatic undefined operands NOT COVERED | Incremental charge and threshold policy validation |
| CAP-003/004/009/010 | ALIGNED with preserved guards | B4 acceptance clarification |
| PLC-012/016, F.9 through F.12 | ALIGNED in scopes; normalization/rounding NOT COVERED | Explicit policy approval |
| DR-017/F.6/F.8 | ALIGNED for approved positive-demand non-concurrent scenarios | B2/B3 and POC-011 |
| NFR-005 | ALIGNED mechanisms/reference limits | Per-endpoint budget and POC-004/010 |

**Overall ratification: BLOCKED**, not a claim of production compliance. Any missing evidence or conflict blocks the affected executable behavior.

### Hard constraints

PASS below means a documentary enforcement rule is specified, **not** a live validation or final implementation certification.

| HC | Name | Documentation gate | Evidence / remaining limitation |
|---|---|---|---|
| HC-1 | REGION_SEPARATION | PASS | Set/domain isolation; section 5 |
| HC-2 | CAPACITY_FLOOR | PASS | Residual exact-partition gate; sections 8.2/11 |
| HC-3 | QUOTA_FLOOR | PASS | Both caps, shared regional claims and confirmed transfers; sections 8.3/11 |
| HC-4 | DR_SEPARATION_CLASS | PASS | CRV/policy filtering retained; approved catalogue evidence needed |
| HC-5 | ZONE_AVAILABILITY | PASS | Configured minimum-zone HC, not az_count>=1; section 8.5 |
| HC-6 | DR_COVERAGE_FLOOR | FAIL | B3 scenario set/POC-007/011 unresolved; section 9 blocks unsupported coverage |
| HC-7 | DR_FLOOR_INTEGRITY | PASS | Distinct protected claims and no double counting; missing policy operands block section 11 |
| HC-8 | GEOGRAPHY_CONTAINMENT | PASS | Customer CRV validation before DPB |
| HC-9 | STANDARD_REGION_ONLY | PASS | Standard automated selection; restricted exception route |
| HC-10 | CROSS_GEO_EXTENSION_PATH_APPROVED | FAIL | Country Legal/A-ME1 evidence not established by this draft |
| HC-11 | AVAILABILITY_SET_INELIGIBLE | PASS | Explicit exclusion from eligibility/counts |

**Formula check:** Worked arithmetic above recomputed; unknown terms remain blocked. **DR sizing:** MAX verified only inside isolated partitions and admitted non-concurrent source scenarios. No hard constraint is relaxed.

### WAF

| Pillar | Design response | Outstanding evidence |
|---|---|---|
| Reliability | Residual gates, independent Foundation, durable claims and guarded incident mode | POC safety/charge semantics, scenario and resume approval |
| Security | Customer/domain scope, least privilege, explicit sharing/approvals, classified telemetry | Enterprise role/Legal review |
| Cost Optimization | Lean bootstrap, retained-zero lifecycle, exact group/reservation counts and source/domain cost | Approved bootstrap/buffer budgets |
| Operational Excellence | Explainable versions, operation recovery/audit, dry-run, runbooks and decision register | Approved migration/runbook exercise evidence |
| Performance Efficiency | Per-endpoint adaptive budgets, configured cadence, tracked async work | Production SLO/budget/scale testing |

No runtime, baseline or live Azure changes are authorized by this reconciliation. Approval of draft content, resolution of pending decisions and POC execution are separate gates.
