# ACRME Requirements Code Glossary & Master Index

**Azure Capacity Reservation Management Engine (ACRME)**
**Version:** 1.0 — aligned to Requirements Baseline v2.4
**Date:** 2026-09-08
**Author:** Principal Cloud Architect

---

## Document Purpose

This glossary is the **single lookup point** for every requirements code used across the ACRME design corpus.
Each entry provides:

- The **code** and its full name
- A **one-line definition** of what it means
- A **direct link** to the source document and section where the full normative detail lives

It does not reproduce the full specification — it tells you exactly where to find it.

---

## Code Family Quick Reference

| Family | Prefix | Count | What it covers | Primary source |
|--------|--------|-------|----------------|----------------|
| [Region strategy](#reg---region-strategy-requirements) | `REG-` | 4 | Region catalogue, distribution model, geography classification | Requirements Baseline §6 |
| [Strategic decisions](#dec---strategic-decisions) | `DEC-` | 3 | Mandatory business/legal decisions that gate design | Requirements Baseline §23 |
| [Environment policy](#env---environment-policy-requirements) | `ENV-` | 7 | Prod / CVAL / DR environment separation rules | Requirements Baseline §7 |
| [Capacity reservation](#cap---capacity-reservation-management-requirements) | `CAP-` | 25 | Reservation lifecycle, sharing, scaling, naming, zone structure | Requirements Baseline §8 |
| [Quota management](#qua---quota-management-requirements) | `QUA-` | 14 | Quota pooling, allocation, reclamation, governance | Requirements Baseline §9 |
| [Combined readiness](#rdy---combined-capacity--quota-readiness) | `RDY-` | 4 | Deployment readiness gate and state model | Requirements Baseline §10 |
| [Placement](#plc---region-selection--customer-placement-requirements) | `PLC-` | 12 | Customer placement, seed record, scoring, zone distribution | Requirements Baseline §11 |
| [Disaster recovery](#dr---disaster-recovery-capacity-requirements) | `DR-` | 19 | DR sizing, failover, failback, co-location, standby activation | Requirements Baseline §12 |
| [FinOps & cost](#fin---cost-economics--finops-requirements) | `FIN-` | 8 | Idle cost, buffer economics, shared-DR overcommit accounting | Requirements Baseline §13 |
| [AEP integration](#int---provisioning--aep-integration-requirements) | `INT-` | 7 | Provisioning contract, idempotency, output spec | Requirements Baseline §14 |
| [State & data](#dat---state--data-requirements) | `DAT-` | 6 | State store, entity model, freshness, config versioning | Requirements Baseline §15 |
| [Observability](#obs---observability--alerting-requirements) | `OBS-` | 5 | Metrics, alerts, dashboards, SLO reporting | Requirements Baseline §16 |
| [Governance & security](#gov---governance-security--compliance-requirements) | `GOV-` | 9 | RBAC, audit, break-glass, secrets, data classification | Requirements Baseline §17 |
| [Non-functional](#nfr---reliability--non-functional-requirements) | `NFR-` | 10 | Availability, consistency, performance, idempotency | Requirements Baseline §18 |
| [Operational](#ops---operational-requirements) | `OPS-` | 6 | Runbooks, safe pause, override, naming convention | Requirements Baseline §19 |
| [Hard constraints](#hc---hard-constraints) | `HC-` | 11 | Hard blocking rules that gate every placement decision | Hard Constraints Reference |
| [Validation rules](#vr---validation-rules) | `VR-` | 12 | Named enforcement checks derived from hard constraints | Hard Constraints Reference |
| [Core formulas](#a---core-formulas-appendix-a) | `A.` | 9 | Calculation formulas for reservations, quota, DR, zone distribution | Requirements Baseline Appendix A |
| [Configurable items](#c---configurable-items-register-appendix-c) | `C-` | 13 | Values and policies that are configurable (not fixed) | Requirements Baseline §22 |
| [Pending decisions / POCs](#poc--dep---pending-decisions--mandatory-pocs) | `POC-` / `DEP-` | 12 | Azure behaviour that must be validated before production dependency | Requirements Baseline §23 |
| [Functional requirements](#fr---functional-requirements) | `FR-` | 8 | Top-level functional capability areas | Complete Requirements Reference |
| [Non-functional requirements (placement)](#nfr-r---placement-non-functional-requirements) | `NFR-R` | 3 | Latency, freshness, determinism for placement API | Complete Requirements Reference |
| [Placement requirements](#r---regional-placement-requirements) | `R` | 8 | Specific placement behaviours derived from placement design | Complete Requirements Reference |
| [Architecture decisions](#adr---architecture-decision-records) | `ADR-` | 5 | Formal load-bearing architectural decisions | Architecture/adr/ |
| [Design gaps](#g---design-gaps) | `G-` | 4 | Explicitly documented open design items (30% gap) | UML Class Diagrams Summary |
| [Backlog epics](#acrme-e---backlog-epics) | `ACRME-E` | 20 | Top-level delivery epics in the engineering backlog | Backlog Epics/Stories/Tasks |

---

## REG — Region Strategy Requirements

**Primary source:** [Requirements Baseline v2.4 — §6 Region Strategy & Classification](../../Requirements/acrme_requirements_baseline_v2_4.md#6-region-strategy--classification)

| Code | Name | One-line definition |
|------|------|---------------------|
| **REG-001** | Configurable region catalogue | Region classification, eligibility, distribution model, and per-region flags are all configuration-driven and versioned; no hard-coded catalogue in engine code. |
| **REG-002** | Cross-geo DR extension region | Switzerland North is the authoritative cross-geography DR extension region (Europe geography); cross-geo DR path requires explicit policy approval (HC-10). |
| **REG-003** | Distribution model | US uses a three-region distribution model (Prod / CVAL / DR fully separated); all other geographies (Europe, Australia, Asia Pacific, Middle East) use a two-region model. |
| **REG-005** | Japan East pending | Japan East is pending business confirmation before inclusion as a Standard region in the Asia Pacific geography. |

---

## DEC — Strategic Decisions

**Primary source:** [Requirements Baseline v2.4 — §23 Pending Decisions & Mandatory POCs](../../Requirements/acrme_requirements_baseline_v2_4.md#23-pending-decisions--mandatory-pocs)

| Code | Name | One-line definition |
|------|------|---------------------|
| **DEC-001** | Middle East DR offering | Legal/business decision on Middle East DR (`DR_NOT_OFFERED` is the current default until this decision records an approval per country/geography). Highest-priority gating decision. |
| **DEC-002** | DR drill duration & failback | Choice between extended ~1-year DR run and earlier ~30-day failback model. |
| **DEC-003** | Geography exception approval | Who approves geography-only customer onboarding (exception path) and the format of binding customer acknowledgement. |

---

## ENV — Environment Policy Requirements

**Primary source:** [Requirements Baseline v2.4 — §7 Environment Policy Requirements](../../Requirements/acrme_requirements_baseline_v2_4.md#7-environment-policy-requirements)

| Code | Name | One-line definition |
|------|------|---------------------|
| **ENV-001** | Production reservation coverage | Manage approved production VM SKUs with reservations to guarantee compute availability. |
| **ENV-002** | Production-only initial enforcement | Production reservation coverage is mandatory; CVAL/DR reservation is a phased follow-on, not day-one scope. |
| **ENV-003** | Hard separation constraints | Prod, CVAL, and DR must each be in a different region (US three-region); in two-region geographies CVAL and DR co-locate in the non-Prod region (PLC-010a — mandatory, not an exception). |
| **ENV-004** | CVAL treatment | CVAL is treated as a potential DR capacity source (its capacity can contribute to DR readiness). |
| **ENV-005** | DR bootstrap, not full duplicate | DR capacity is a lean bootstrap (enough to start recovery orchestration), not a full production duplicate. |
| **ENV-006** | DR bootstrap cannot be implicitly zero | A zero DR target must be an explicit approved configuration, not an accidental default. |
| **ENV-007** | R&D policy | No permanent R&D reservations by default; short-lived POC reservations may be supported under governance. |

---

## CAP — Capacity Reservation Management Requirements

**Primary source:** [Requirements Baseline v2.4 — §8 Capacity Reservation Management Requirements](../../Requirements/acrme_requirements_baseline_v2_4.md#8-capacity-reservation-management-requirements)

| Code | Name | One-line definition |
|------|------|---------------------|
| **CAP-001** | Authoritative managed scope | The engine operates only on subscriptions, regions, SKUs, and environments declared in its versioned scope file. |
| **CAP-001a** | Core subscription = all production | VMs deployed into a shared platform/core subscription are all classified production for reservation and buffer purposes; non-production workloads must not run there. |
| **CAP-002** | Azure resource must precede config activation | A managed subscription/CRG must exist as a real Azure resource before the engine activates management of it. |
| **CAP-003** | Reservation target formula | Reserved quantity = allocated demand + approved buffer; see formula A.1. |
| **CAP-004** | Associated-but-deallocated VMs | Deallocated VMs associated to a CRG still consume reserved capacity; they must not be silently ignored in demand accounting. |
| **CAP-005** | Automated reconciliation | Periodically compare reserved quantity against current demand; trigger scale-up or flag scale-down. |
| **CAP-006** | Reconciliation frequency (configurable) | Reference implementation reconciles every 6 minutes; production interval is configurable (C-4) and validated by POC-010. |
| **CAP-007** | Scale-up behaviour | When allocated demand rises, attempt to increase reservation immediately; log failure with alert if Azure rejects. |
| **CAP-008** | Scale-down behaviour | When allocated demand falls, reduce reservation only after the decommissioning workflow completes; not automatic. |
| **CAP-009** | Zero-capacity support | Where Azure permits, reduce a reservation to `quantity = 0` (not delete it) to preserve the CRG structure; extends CAP-022 seed matrix. |
| **CAP-010** | No automatic deletion by default | CRGs and reservations are never automatically deleted; decommissioning is a gated workflow (CAP-008). |
| **CAP-011** | Availability-zone isolation | Reservations are managed per availability zone; zone counts and zone-level capacity are tracked and reported independently (extends to CAP-023 per-AZ CRG structure). |
| **CAP-012** | Regional isolation | Reservations are never counted, moved, or shared across regions without explicit policy. |
| **CAP-013** | Capacity sharing | Support cross-subscription reservation sharing where approved; governed by the three-tier sharing model (Tier 1/2/3). |
| **CAP-014** | Shared capacity visibility | For each shared reservation, expose provider-side quantity, consumer-side allocated count, and net available capacity. |
| **CAP-015** | No double counting | Capacity shared to multiple consumers is counted once at the provider; consumer-allocated demand is tracked separately. |
| **CAP-016** | Reservation integrity validation (pre-deploy) | Validate capacity availability before accepting a deployment request; block if insufficient. |
| **CAP-017** | Deployment failure policy | If reservation enforcement fails at deploy time, the engine follows a defined policy (block / warn / allow with alert) — configurable per environment. |
| **CAP-018** | Over-allocation policy | Support an explicit policy to permit VM association beyond reserved quantity (with alert); not silent. |
| **CAP-019** | Scope-file governance | Adding a SKU to management requires a scope-file change with approval; reconciles with CAP-024 reactive discovery. |
| **CAP-020** | Availability-Set VMs ineligible | VMs in an Availability Set are mutually exclusive with Capacity Reservations and must be excluded from all reservation management (maps to HC-11). |
| **CAP-021** | Deallocate-or-migrate-to-AZ onboarding precondition | Before onboarding an AV-Set VM, it must be deallocated and redeployed into an availability zone — this is a pre-condition, not an engine action. |
| **CAP-022** | Seed-at-0 eligible-SKU/AZ matrix & budget governance | Maintain a governed matrix of eligible SKU × region × AZ combinations with seed reservations created at `quantity = 0`; resizing from 0 requires product-team budget approval. Extends CAP-009. |
| **CAP-023** | Regional and per-AZ CRG structure | For each environment, the engine maintains one regional CRG (non-zonal SKUs) plus one per-AZ CRG for each availability zone (`crg-<env>-<region>-az1/az2/az3`). Extends CAP-011. |
| **CAP-024** | Reactive SKU/AZ discovery reconciled with governance | Reactive discovery auto-creates CRGs for new SKU/AZ combinations observed in demand; governed by the scope-file approval workflow (CAP-019). |

---

## QUA — Quota Management Requirements

**Primary source:** [Requirements Baseline v2.4 — §9 Quota Management Requirements](../../Requirements/acrme_requirements_baseline_v2_4.md#9-quota-management-requirements)

| Code | Name | One-line definition |
|------|------|---------------------|
| **QUA-001** | Separate quota domain | Manage quota as a separate control plane from reservations; quota failure does not silently mask reservation success. |
| **QUA-002** | Regional & family scope | Maintain quota inventory by region and VM family for every managed subscription. |
| **QUA-003** | Central pooling ("quota hoarding") | Where Azure quota is per-subscription by default, centralise it into a governed pool for controlled reallocation (quota hoarding governance practice). |
| **QUA-004** | Single governed pool per supported scope | Prefer one governed quota pool per region/VM-family scope rather than fragmented per-subscription pools. |
| **QUA-005** | Quota as cost/consumption governor | Quota allocation is a cost-control gate, not just a technical limit; changes require business justification. |
| **QUA-006** | Production growth buffer | Production subscriptions hold a quota buffer above current usage to absorb growth without an increase request per deployment. |
| **QUA-007** | Quota–reservation validation | For every managed scope, quota available ≥ reserved quantity (or alert); a reservation without supporting quota is flagged `READY_WITH_RISK`. |
| **QUA-008** | Dynamic allocation | Allocate quota from the pool to a subscription on demand; reclaim when no longer needed. |
| **QUA-009** | Quota reclamation | Reclaim unused subscription quota into the pool on scope reduction, subscription offboarding, or environment retirement. |
| **QUA-010** | Quota request governance | Increase requests record reason, approver, business justification, and cost exposure before submission to Azure. |
| **QUA-011** | Quota source discovery | Discover reusable quota assigned to decommissioned or lightly used subscriptions before requesting new quota from Azure. |
| **QUA-012** | Region-failure assumption | Quota bound to a failed region cannot be assumed available; failover planning must not depend on failed-region quota. |
| **QUA-013** | Consumer-subscription quota (POC-gated) | Assume a VM deploying against a shared reservation still requires quota in the consumer subscription — but this behaviour must be confirmed by POC-001 before production dependency. |
| **QUA-014** | Quota allocation audit | Log every allocation, reclamation, increase request, and approval with timestamp, actor, and justification. |

---

## RDY — Combined Capacity & Quota Readiness

**Primary source:** [Requirements Baseline v2.4 — §10 Combined Capacity & Quota Readiness](../../Requirements/acrme_requirements_baseline_v2_4.md#10-combined-capacity--quota-readiness)

| Code | Name | One-line definition |
|------|------|---------------------|
| **RDY-001** | Deployment readiness gate | A deployment is capacity-ready only when reservation exists, quota is sufficient, and state is fresh — all three must be satisfied. |
| **RDY-002** | Readiness states | The engine exposes a machine-readable readiness state: `READY`, `READY_WITH_RISK`, `QUOTA_DEFICIT`, `CAPACITY_DEFICIT`, `STALE_STATE`, `NOT_MANAGED`. |
| **RDY-003** | Capacity and quota must agree | A reservation without sufficient deployable consumer quota is never `READY`; it is at minimum `READY_WITH_RISK` or `QUOTA_DEFICIT`. |
| **RDY-004** | No stale placement | Region selection and provisioning must not use state older than the configured maximum freshness threshold; stale state fails safe (`STALE_STATE`). |

---

## PLC — Region Selection & Customer Placement Requirements

**Primary source:** [Requirements Baseline v2.4 — §11 Region Selection & Customer Placement](../../Requirements/acrme_requirements_baseline_v2_4.md#11-region-selection--customer-placement)

| Code | Name | One-line definition |
|------|------|---------------------|
| **PLC-001** | Production region is the primary input | The default onboarding path starts with the customer supplying an exact production region; geography-only is an exception requiring approval. |
| **PLC-002** | Geography-based selection is exceptional | If a customer supplies only a geography (not an exact region), the engine selects via `argmax(PS_Prod)` but requires explicit exception approval (DEC-003). |
| **PLC-003** | Customer seed record | The first placement decision creates an authoritative seed record holding Prod, CVAL, and DR regions; subsequent placements reuse it. |
| **PLC-004** | Reuse across products | All products/environments for the same customer reuse the same seed record regions; no per-product re-selection. |
| **PLC-005** | Controlled seed change | The seed record is never regenerated automatically; changes require an explicit operator action with reason and approval. |
| **PLC-006** | CVAL & DR selection | Once production is fixed, the engine selects CVAL and DR regions automatically, subject to hard constraints and separation rules. |
| **PLC-007** | Live weighting | Placement scoring considers live allocated demand (demand units, not customer count) and capacity headroom to prevent hotspots. |
| **PLC-008** | Lowest suitable load | Select the lowest-risk suitable region; avoid regions at or near capacity ceiling. |
| **PLC-009** | AEP-triggered pipeline | Region selection is the first step in every AEP provisioning call; the pipeline is synchronous for the recommendation, async for the reservation action. |
| **PLC-010** | CVAL/DR co-location | A customer's CVAL and DR *may* share a region — this is the normal outcome in two-region geographies, not an exception. |
| **PLC-010a** | Co-location mandatory in two-region geographies | In any two-region geography, CVAL and DR **must** co-locate in the non-Prod region — there is no third region available. |
| **PLC-011** | Even zone-distribution target & rebalancing | Maintain an approximately even `≈ 1/zone_count` zone distribution for all placements; trigger rebalancing when skew exceeds the C-13 tolerance (formula A.9). |

---

## DR — Disaster Recovery Capacity Requirements

**Primary source:** [Requirements Baseline v2.4 — §12 Disaster Recovery Capacity Requirements](../../Requirements/acrme_requirements_baseline_v2_4.md#12-disaster-recovery-capacity-requirements)

| Code | Name | One-line definition |
|------|------|---------------------|
| **DR-001** | Single-region failure basis | The default model plans for one region failing at a time; simultaneous multi-region failure is out of scope. |
| **DR-002** | Distributed DR | DR capacity is computed from the distributed multi-source, multi-destination reference model (Section 12A). |
| **DR-003** | Destination distribution | Record how each source region's workload is distributed across destination regions; maintain the source→destination DR index (DR-018). |
| **DR-004** | CVAL target contribution | Normal CVAL placement should land in the same region as the planned DR destination so CVAL capacity earmarks DR bootstrap slots. |
| **DR-005** | CVAL may exceed DR need | CVAL capacity may exceed the DR bootstrap requirement; the excess earmark is tracked but not wasted. |
| **DR-006** | Staged DR capacity acquisition | DR capacity is acquired in waves (CVAL earmark → bootstrap top-up → full demand) rather than reserved all-at-once. |
| **DR-007** | DR target is configurable | Bootstrap quantity may be a node count, core count, percentage of source, or formula result; all are configurable (C-1). |
| **DR-008** | Control plane first | Bootstrap prioritises the required control-plane nodes and SKUs needed to run recovery orchestration before general workload capacity. |
| **DR-009** | Recovery prioritisation | Support prioritised recovery: critical workloads recover first, lower-priority workloads recover in sequence. |
| **DR-010** | DR declaration guardrail | Destructive/service-impacting failover actions require an explicit authorised DR declaration; no silent auto-failover. |
| **DR-011** | Source region not a capacity source during outage | During a declared outage, the failed source region's capacity is unavailable and must not be counted in failover planning. |
| **DR-012** | DR drill rotation | Support periodic DR drills with role-flip (source becomes destination and vice versa) and role restoration after the drill. |
| **DR-013** | Failback policy (configurable) | Support extended-run failback (~1 year) and shorter failback (~30 days); configurable per customer/geography (C-5, DEC-002). |
| **DR-014** | Middle East policy flag | Support `DR_NOT_OFFERED` per geography; when set, no DR region is assigned and cross-geo DR substitution does not apply. See DEC-001. |
| **DR-015** | Future active-active consideration | Note that active-active DR is out of current baseline scope; architecture should not block its future addition. |
| **DR-016** | Reciprocal multi-source hosting | Every region may simultaneously be a source (hosting live workloads) and a destination (hosting standby for another region). |
| **DR-017** | Non-concurrent capacity sharing (max, not sum) | Because DR-001 assumes only one region fails at a time, a destination's DR capacity requirement is the **maximum** over its non-concurrent sources — not the sum (Appendix D). |
| **DR-018** | Source→destination DR index | Maintain an authoritative index recording which source regions each destination protects and the failover portion size. |
| **DR-019** | Standby activation on declaration | On an authorised DR declaration, the engine activates the pre-positioned standby capacity in the destination region in priority waves. |

---

## FIN — Cost Economics & FinOps Requirements

**Primary source:** [Requirements Baseline v2.4 — §13 Cost Economics & FinOps Requirements](../../Requirements/acrme_requirements_baseline_v2_4.md#13-cost-economics--finops-requirements)

| Code | Name | One-line definition |
|------|------|---------------------|
| **FIN-001** | Idle cost measurement | Calculate and surface the cost of unused reserved capacity (idle reservations) per scope. |
| **FIN-002** | Configurable economic policy | Buffer and bootstrap values are configurable so cost exposure can be tuned without code changes. |
| **FIN-003** | Cost before expansion | Before increasing a persistent reservation, expose the projected monthly cost increase so the operator can approve with cost awareness. |
| **FIN-004** | Cost allocation | Reservation cost is attributable to the owning team/product/environment for chargeback. |
| **FIN-005** | Underutilisation review | Long-running underutilised reservations trigger a review notification rather than automatic deletion. |
| **FIN-006** | No cost-only unsafe reduction | Cost optimisation never overrides a safety floor (HC-2, HC-6, HC-7); cost savings are bounded by capacity commitments. |
| **FIN-007** | Audit-friendly flexibility | Buffer/bootstrap values are versioned and traceable; historical cost decisions are explainable. |
| **FIN-008** | Shared-DR overcommit accounting | Where DR-017 max-not-sum sizing overcommits a destination, the overcommit ratio is calculated and exposed per destination for leadership sign-off. |

---

## INT — Provisioning & AEP Integration Requirements

**Primary source:** [Requirements Baseline v2.4 — §14 Provisioning & AEP Integration](../../Requirements/acrme_requirements_baseline_v2_4.md#14-provisioning--aep-integration)

| Code | Name | One-line definition |
|------|------|---------------------|
| **INT-001** | Capacity API/workflow | AEP calls a capacity+placement API or triggers a workflow; ACRME returns a readiness verdict and placement recommendation. |
| **INT-002** | Idempotent interface | Capacity checks and reservation actions are idempotent; AEP may retry without side effects. |
| **INT-003** | Required input | The AEP call must supply: customer/realm; product; environment; exact region or geography; SKU/VM family; intended demand. |
| **INT-004** | Required output | ACRME returns: resolved Prod/CVAL/DR placement; readiness state; capacity available; quota available; operation handle for async tracking. |
| **INT-005** | Deployment reservation association | When policy requires it, ACRME associates the newly deployed VM to the reservation after AEP confirms deployment. |
| **INT-006** | Concurrent deployment control | Prevent two concurrent AEP calls from double-committing the same capacity; use optimistic locking or a deployment lock. |
| **INT-007** | Partial-failure handling | If quota is allocated but reservation fails, the engine compensates (rolls back the quota allocation) and returns a structured error. |

---

## DAT — State & Data Requirements

**Primary source:** [Requirements Baseline v2.4 — §15 State & Data Requirements](../../Requirements/acrme_requirements_baseline_v2_4.md#15-state--data-requirements)

| Code | Name | One-line definition |
|------|------|---------------------|
| **DAT-001** | Authoritative state store | Maintain an authoritative desired-state store (Cosmos DB) as the single source of truth; Azure is the observed-state source. |
| **DAT-002** | Minimum entities | The state store must hold: subscriptions; regions/zones; SKUs/quota families; CRGs/reservations; seed records; assignments; snapshots; operation records; audit trail. |
| **DAT-003** | Freshness metadata | Every observation record carries a collection timestamp and a staleness flag; stale records block placement (RDY-004). |
| **DAT-004** | Historic state | Retain history sufficient to explain any past placement or sizing decision; minimum retention configurable. |
| **DAT-005** | Configuration versioning | Scope files and policies are versioned; every decision record references the policy version in force at decision time. |
| **DAT-006** | Schema compatibility | API and config schema changes follow a compatibility policy (additive changes only; breaking changes require version bump). |

---

## OBS — Observability & Alerting Requirements

**Primary source:** [Requirements Baseline v2.4 — §16 Observability & Alerting](../../Requirements/acrme_requirements_baseline_v2_4.md#16-observability--alerting)

| Code | Name | One-line definition |
|------|------|---------------------|
| **OBS-001** | Core metrics | Emit: reserved quantity; allocated VM count; associated VM count; quota available; DR floor headroom; idle cost; reconciliation latency; staleness age. |
| **OBS-002** | Required alerts | Alert on: production buffer below target; DR capacity below floor; quota exhaustion; stale state; deployment blocked; unauthorised DR consumption; failed reconciliation. |
| **OBS-003** | Alert context | Every alert includes: region; zone; subscription; SKU/family; policy version; last-known-good timestamp; remediation link. |
| **OBS-004** | Dashboards | Provide dashboards at: regional; product; subscription; SKU; and DR-pair granularity. |
| **OBS-005** | SLO reporting | Expose SLO metrics: availability of the placement decision path; reconciliation latency P99; data freshness percentage. |

---

## GOV — Governance, Security & Compliance Requirements

**Primary source:** [Requirements Baseline v2.4 — §17 Governance, Security & Compliance](../../Requirements/acrme_requirements_baseline_v2_4.md#17-governance-security--compliance)

| Code | Name | One-line definition |
|------|------|---------------------|
| **GOV-001** | Least privilege | Workload identities receive only the minimum permissions required; no standing owner/contributor on managed subscriptions. |
| **GOV-002** | Separation of duties | Policy approval, production mutations, and audit-log access are held by different roles; no single identity can approve and execute a high-impact change. |
| **GOV-003** | Scoped automation | Automation is constrained by tenant, management group, and subscription scope; no accidental cross-tenant or cross-geography blast radius. |
| **GOV-004** | Change approval | High-impact changes (reducing production reservations, deleting a CRG, emergency override) require a named approver and a tracked approval record. |
| **GOV-005** | Break-glass controls | Break-glass access requires an authorised request with time limit, reason, and post-action audit review. |
| **GOV-006** | Audit evidence | Every decision and mutation writes an immutable audit record with before/after values, actor, timestamp, and correlation ID. |
| **GOV-007** | Policy exceptions | Each exception (geography-only onboarding, over-allocation, cross-geo DR) has an owner, reason, expiry, and renewal process. |
| **GOV-008** | Secrets & credentials | No secrets in config files or logs; all credentials managed via Azure Key Vault and Managed Identity. |
| **GOV-009** | Data classification | Customer placement and workload metadata is classified and handled per organisational data-classification policy. |

---

## NFR — Reliability & Non-Functional Requirements

**Primary source:** [Requirements Baseline v2.4 — §18 Reliability & Non-Functional Requirements](../../Requirements/acrme_requirements_baseline_v2_4.md#18-reliability--non-functional-requirements)

> Note: The complete requirements reference uses `NFR-1..NFR-7` for the top-level functional NFR areas and `NFR-001..NFR-010` for the baseline detailed items. Both refer to the same concepts at different granularities.

| Code | Name | One-line definition |
|------|------|---------------------|
| **NFR-001** | Availability | The capacity decision path is not an uncontrolled single point of failure; degraded-mode behaviour is defined and tested. |
| **NFR-002** | Consistency | Concurrency control prevents double-committing capacity or quota; optimistic locking on all state-changing operations. |
| **NFR-003** | Performance | Readiness responses meet an approved latency target; long-running Azure operations return a tracked async handle rather than blocking the caller. |
| **NFR-004** | Scale | Operates across hundreds of subscriptions, multiple regions/zones, VM families, products, and seed records without degradation. |
| **NFR-005** | API-throttling resilience | Use batching, caching, exponential backoff with jitter, retry limits, and per-scope rate control; avoid Azure API storms during a regional event. |
| **NFR-006** | Recoverability | State store, configuration, and audit trail support backup/restore and reconstruction of desired state after data-layer failure. |
| **NFR-007** | Idempotency | All mutating operations are idempotent or protected by a durable operation key; replayed calls have no additional effect. |
| **NFR-008** | Testability | Policies, formulas, reconciliation logic, weighting, failover distribution, and compensation are independently unit-testable without Azure dependency. |
| **NFR-009** | Simulation mode | Support read-only/dry-run that shows intended reservation/quota/placement/cost changes without applying them — including DR failover simulation. |
| **NFR-010** | Explainability | Every placement and sizing decision exposes the policy inputs, state snapshot, formula applied, and human-readable reason code. |

---

## OPS — Operational Requirements

**Primary source:** [Requirements Baseline v2.4 — §19 Operational Requirements](../../Requirements/acrme_requirements_baseline_v2_4.md#19-operational-requirements)

| Code | Name | One-line definition |
|------|------|---------------------|
| **OPS-001** | Runbooks | Runbooks exist for: production buffer deficit; quota exhaustion; reservation scale-up failure; stale state; blocked deployment; DR declaration; CVAL shutdown; quota allocation to DR; reservation sharing activation/revocation; reconciliation rollback/pause; manual emergency override; regional recovery and failback; standby DR activation sequence (DR-019). |
| **OPS-002** | Safe pause | Operators can pause the engine's mutation actions while retaining inventory collection and alerting (read-only mode). |
| **OPS-003** | Manual override | Authorised operators can set temporary desired values with an expiry timestamp and reason; the engine never overwrites an active approved override. |
| **OPS-004** | Maintenance-window awareness | Planned maintenance that changes VM allocation or association is visible to the engine to prevent inappropriate scaling triggers or alert noise. |
| **OPS-005** | Ownership | Every region, subscription, reservation scope, quota pool, alert, and exception has a named owning team and documented escalation route. |
| **OPS-006** | Naming convention & counter | All managed resource groups, CRGs, and subscriptions follow a deterministic, parseable naming convention. Pattern: RG `rg-odcr-<env>-<region>-<NN>`; CRG `crg-<env>-<region>-<scope>` (scope ∈ {reg, az1, az2, az3}); Subscription `sub-<org>-<domain>-<purpose>-<NN>`. See C-12 for configurability. |

---

## HC — Hard Constraints

**Primary source:** [Hard Constraints Reference](../../Reference-Material/reference/acrme_hard_constraints_reference.md)

Hard constraints are **blocking rules** applied by the placement pipeline before any scoring. A candidate region that fails any HC is eliminated — scoring is not applied to it.

| Code | Name | One-line definition |
|------|------|---------------------|
| **HC-1** | REGION_SEPARATION | Prod, CVAL, and DR must be in distinct regions (US three-region model). In two-region geographies, CVAL and DR co-locate in the non-Prod region under PLC-010a. |
| **HC-2** | CAPACITY_FLOOR | Reserved capacity must not be reduced below the allocated VM count; the floor is `quantity ≥ allocated`. |
| **HC-3** | QUOTA_FLOOR | Available quota in the target scope must be ≥ the vCPU count of the proposed reservation or deployment. |
| **HC-4** | DR_SEPARATION_CLASS | DR regions must carry a different environment classification from Prod; a region designated Prod cannot simultaneously serve as DR. |
| **HC-5** | ZONE_AVAILABILITY | A target availability zone must exist and be usable in the target subscription/region before a zonal placement is accepted. |
| **HC-6** | DR_COVERAGE_FLOOR | NonProd/CVAL placement in a DR-designated region must not reduce available capacity below the region's DR floor (the bootstrap reserved for failover). |
| **HC-7** | DR_FLOOR_INTEGRITY | The engine must enforce the DR floor continuously; any reconciliation action that would bring available capacity below the floor is blocked. |
| **HC-8** | GEOGRAPHY_CONTAINMENT | A derived Prod region must fall within the Standard Capacity Regions for the customer's chosen geography (not in a different geography). |
| **HC-9** | STANDARD_REGION_ONLY | All automated placement paths (geography-based, Prod derivation, NonProd/DR selection) must use Standard Capacity Regions only; Restricted regions are exception-path only. |
| **HC-10** | CROSS_GEO_EXTENSION_PATH_APPROVED | A cross-geography DR extension (e.g., Middle East Prod → Switzerland North DR) must be explicitly approved in the active PlacementPolicy before it is used. |
| **HC-11** | AVAILABILITY_SET_INELIGIBLE | VMs in an Azure Availability Set cannot be associated with a Capacity Reservation; they must be excluded from all reservation management (CAP-020). |

---

## VR — Validation Rules

**Primary source:** [Hard Constraints Reference — Validation Rules table](../../Reference-Material/reference/acrme_hard_constraints_reference.md)

Validation rules are named enforcement checks that implement hard constraints in the placement pipeline code. They are the testable, auditable expression of the HC rules.

| Code | Name | One-line definition | Enforces |
|------|------|---------------------|----------|
| **VR-1** | Prod ≠ DR region | Prod and DR must not share a region. | HC-1 |
| **VR-2** | Prod ≠ CVAL region | CVAL and Prod must not share a region. | HC-1 |
| **VR-3** | CVAL/DR co-location policy | CVAL and DR may share a region only under the approved PLC-010a co-location policy (two-region geographies). | HC-1 |
| **VR-4** | Prod within chosen geography | The derived Prod region must be within the Standard Capacity Regions for the customer's chosen geography. | HC-8 |
| **VR-5** | Automated paths use Standard regions only | All automated placement paths must use Standard Capacity Regions only. | HC-9 |
| **VR-6** | CVAL/DR never in Restricted regions | CVAL and DR must not use Restricted Capacity Regions under any condition, including exception deployments. | HC-9 |
| **VR-7** | Exhaustion handling | If all Standard regions for a geography are eliminated by HC-1..HC-10, the engine returns a capacity exhaustion error with an ops alert. | HC-1..HC-10 |
| **VR-8** | Middle East DR default | For Middle East geography with `DR_NOT_OFFERED = true` (current legal position, DEC-001), the seed record **must** record `dr_region = NOT_OFFERED`; no auto-assignment of Switzerland North. | HC-10 |
| **VR-8a** | Middle East conditional cross-geo | Only after a recorded DEC-001 approval clears `DR_NOT_OFFERED`: Switzerland North may be used as a cross-geo DR; if it then fails HC-1..HC-10, block with an ops alert (VR-9 applies). | HC-10 |
| **VR-9** | Cross-geo fallback exhaustion | On the DEC-001-approved conditional path only: if Switzerland North fails HC-1..HC-10, block placement with an ops alert. | HC-1..HC-10 |
| **VR-10** | Restricted region exception path | A Restricted region requested by a customer triggers the Scenario 2 exception path only; it is never auto-selected. | HC-9 |
| **VR-11** | Cross-geo extension approval | A cross-geography DR extension must be explicitly approved in the active PlacementPolicy before it can be used. | HC-10 |

---

## A. — Core Formulas (Appendix A)

**Primary source:** [Requirements Baseline v2.4 — Appendix A — Core Formulas](../../Requirements/acrme_requirements_baseline_v2_4.md#appendix-a--core-formulas)

| Code | Name | One-line definition |
|------|------|---------------------|
| **A.1** | Reservation target | `reserved_target = allocated + buffer`; the approved buffer is configurable per product/region/env/SKU (C-2). |
| **A.2** | Reservation headroom | `headroom = reserved - allocated`; positive headroom means spare committed capacity. |
| **A.3** | Reservation deficit | `deficit = allocated - reserved`; a positive deficit means the reservation is under-sized for current demand. |
| **A.4** | Available subscription quota | `available_quota = quota_limit - quota_current_value`; the raw Azure-reported available quota. |
| **A.5** | Deployment quota deficit | `quota_deficit = committed_vCPUs - available_quota`; positive means the reservation cannot be backed by deployable quota. |
| **A.6** | DR destination requirement (CORRECTED) | `DR_req(dest) = MAX over non-concurrent sources s protected by dest ( portion(s → dest) )`; max-not-sum because DR-001 assumes only one source fails at a time (Appendix D). |
| **A.7** | DR capacity gap | `dr_gap(dest) = DR_req(dest) - dr_reserved(dest)`; positive gap means the destination needs more DR bootstrap capacity. |
| **A.8** | Shared-DR overcommit ratio | `overcommit_ratio(dest) = sum_of_portions / max_portion`; measures how oversubscribed the shared standby is; used in FIN-008 cost accounting. |
| **A.9** | Even zone-distribution target & skew | `target_per_zone = round(total / zone_count)`; `skew = max_count - min_count`; rebalance triggered when skew > C-13 tolerance. Implements PLC-011. |

---

## C — Configurable Items Register (Appendix C)

**Primary source:** [Requirements Baseline v2.4 — §22 Configurable Items Register](../../Requirements/acrme_requirements_baseline_v2_4.md#22-configurable-items-register)

These are items where the *capability* is required but the *specific value or policy* is not fixed in the baseline — they are driven by `PlacementPolicy` configuration.

| Code | Name | Current direction | Status |
|------|------|-------------------|--------|
| **C-1** | DR bootstrap capacity | Lean "enough to bootstrap"; discussed 30–40% → 10–20% → ~5% → used-is-free model | Configurable — no fixed value |
| **C-2** | Production reservation buffer | `allocated + buffer`; ref impl buffer = 1 in dev | Configurable by product/region/env/SKU |
| **C-3** | Production quota buffer | Headroom above usage to support growth | Configurable — value TBD |
| **C-4** | Reconciliation frequency | Ref impl every 6 minutes | Configurable — prod value TBD (POC-010) |
| **C-5** | Failback model | Prefer ~1-year run; ~30-day failback alternative | Business decision (DEC-002) |
| **C-6** | Onboarding selection mode | Exact production region (default); geography (exception) | Configurable + exception policy (DEC-003) |
| **C-7** | Quota grouping model | One governed pool preferred | Configurable |
| **C-8** | Region catalogue & flags | Five geographies (US 3-region; Europe/Australia/Asia Pacific/Middle East 2-region); restricted/standard classes; `DR_NOT_OFFERED` | Configurable (REG-001) |
| **C-9** | Reservation over-allocation | Track allocated; allow over-association with alert | Configurable policy (CAP-018) |
| **C-10** | DR drill duration/rotation | Annual drill; role flip | Business decision (DEC-002) |
| **C-11** | DR sizing basis | **Max over non-concurrent sources** (DR-017); sum available as conservative per-scope override | Configurable — max is default (Appendix D) |
| **C-12** | Resource naming convention & counter | Deterministic RG/CRG/subscription naming with env/region/purpose tokens + zero-padded counter (OPS-006); CRG scope tokens `reg/az1/az2/az3` per CAP-023 | Configurable |
| **C-13** | Zone-distribution target & tolerance | Even ≈`1/zone_count` per zone (≈33% in three-zone regions) with configurable skew tolerance before rebalancing (PLC-011, A.9) | Configurable |

---

## POC / DEP — Pending Decisions & Mandatory POCs

**Primary source:** [Requirements Baseline v2.4 — §23 Pending Decisions & Mandatory POCs](../../Requirements/acrme_requirements_baseline_v2_4.md#23-pending-decisions--mandatory-pocs)

POC items are Azure behaviours that **must be validated** before a production dependency can be declared. DEP items are external dependencies gating design decisions.

| Code | Name | Required outcome |
|------|------|-----------------|
| **POC-001** | Capacity reservation sharing quota behaviour | Confirm whether the consumer subscription must hold its own quota when consuming a shared reservation. **(Top technical unknown.)** |
| **POC-002** | Sharing consumption order | How Azure allocates shared capacity when multiple consumers request the same SKU simultaneously. |
| **POC-003** | Zone/subscription boundaries | Validate supported sharing combinations for the selected feature version (Preview or GA). |
| **POC-004** | Change under throttling | Safe reconciliation and retry behaviour during Azure API throttling. |
| **POC-005** | VM association/shutdown states | Reservation and guarantee behaviour across allocated/stopped/deallocated/associated/disassociated states. |
| **POC-006** | DR subscription topology | Dedicated DR subscription+cluster vs shared production subscription model for DR bootstrap. |
| **POC-007** | Bootstrap sizing | Minimum bootstrap per product including required control-plane nodes and SKUs. |
| **POC-008** | Production quota buffer | Initial buffer policies by product/VM family. |
| **POC-009** | Production reservation buffer | Initial reserved-capacity buffer by product/region/zone/SKU. |
| **POC-010** | Reconciliation interval | Production interval after API throttling and cost testing (C-4). |
| **POC-011** | Max-not-sum overcommit safety | Validate that shared/overcommitted DR reservations (DR-017) behave correctly when a standby set activates; quantify residual risk. |
| **DEP-001** | Azure feature maturity | Track Capacity Reservation Sharing preview → GA status and approved enterprise-usage conditions. |

---

## FR — Functional Requirements

**Primary source:** [Complete Requirements Reference — Part 1](../../Requirements/acrme_complete_requirements_reference.md#part-1--functional-requirements-fr-1-through-fr-8)

FR codes are the eight top-level functional capability areas; each expands to sub-requirements (FR-N.M).

| Code | Name | One-line definition |
|------|------|---------------------|
| **FR-1** | Capacity Reservation Lifecycle Management | Full CRUD lifecycle of CRGs and CRs across the Azure estate at API version 2024-03-01+. |
| **FR-2** | Capacity Reservation Sharing Management | Orchestrates the three-step RBAC setup for Provider-Consumer CRG sharing; manages subscription membership and 100-consumer limit. |
| **FR-3** | Availability Zone Mapping Management | Discovers, stores, and resolves logical-to-physical zone mappings across Provider-Consumer subscription pairs. |
| **FR-4** | Quota Management | Queries, tracks, and enforces quota constraints across managed subscriptions and quota groups. |
| **FR-5** | Disaster Recovery Failover Management | Manages pre-positioned DR capacity pairs, failover triggering, and failback orchestration. |
| **FR-6** | Regional Placement Decisions | Scores and selects Prod/CVAL/DR regions using placement scoring pipeline; creates and manages seed records. |
| **FR-7** | Capacity Forecasting | Forecasts demand growth and triggers proactive quota/reservation increase requests. |
| **FR-8** | Cost Optimization | Surfaces idle reservation cost, overcommit ratios, and FinOps metrics; supports configurable economic policy. |

---

## NFR-R — Placement Non-Functional Requirements

**Primary source:** [Complete Requirements Reference — Part 3](../../Requirements/acrme_complete_requirements_reference.md#placement-non-functional-requirements-nfr-r1nfr-r3)

| Code | Name | One-line definition |
|------|------|---------------------|
| **NFR-R1** | Placement API latency | Placement recommendation API P99 latency < 2 seconds for datasets with 100+ CRGs. |
| **NFR-R2** | Regional state freshness | Regional state used for placement must be ≤ 5 minutes old (via 5-min reconciliation or 10-min Cosmos DB fallback). |
| **NFR-R3** | Placement determinism | Placement scoring is deterministic and repeatable: same inputs always produce the same output; versioned policy enables replay. |

---

## R — Regional Placement Requirements

**Primary source:** [Complete Requirements Reference — Part 3, Regional Placement Requirements](../../Requirements/acrme_complete_requirements_reference.md#regional-placement-requirements-r1r8)

| Code | Name | One-line definition |
|------|------|---------------------|
| **R1** | Geography → Prod region derivation | Customer-supplied geography → engine derives Prod region via `argmax(PS_Prod)` over Standard regions in that geography. |
| **R2** | Automatic NonProd/DR selection | Engine selects NonProd and DR regions automatically; never same as Prod; allows NonProd=DR co-existence (PLC-010a). |
| **R3** | Hard constraints gate eligibility | Hard constraints HC-1..HC-10 gate all region eligibility before scoring. |
| **R4** | Automatic zone resolution | Automatic zone resolution via stored zone mapping registry on VM deployment against a shared CRG. |
| **R5** | Capacity-weighted distribution | Cost and capacity-weighted distribution prevent hotspots; uses demand units (vCPUs), not customer count. |
| **R6** | DR floor enforcement | NonProd placement is blocked if it would encroach on the `dr_floor_vcpu` of the target region (HC-7). |
| **R7** | Middle East special handling | `argmax(PS_Prod)` over Saudi Arabia Central + UAE North; cross-geo DR path conditional on DEC-001 clearance. |
| **R8** | Placement auditability | Placement is deterministic and auditable: all scores, candidate sets, and policy version are written to an OperationRecord for replay. |

---

## ADR — Architecture Decision Records

**Primary source:** [Architecture/adr/](../../Architecture/adr/)

ADRs are formal, self-contained records of the load-bearing architectural decisions with Context / Decision / Consequences / Alternatives-considered sections. Each includes rendered architecture diagrams.

| Code | Name | One-line summary | Full document |
|------|------|-----------------|---------------|
| **ADR-001** | Region Selection & Placement | Geography-aware placement scoring pipeline (PS_Prod / PS_NonProd / PS_DR), HC-1..HC-10 filter pipeline, validation rules VR-1..VR-11, and the CustomerSeedRecord model. | [acrme_adr_001_region_selection.md](../../Architecture/adr/acrme_adr_001_region_selection.md) |
| **ADR-002** | Quota & Capacity Management | Single governed quota pool, two-group model (Provider + Consumer), DR-floor accounting formula, max-not-sum sizing, and quota increase workflow. | [acrme_adr_002_quota_and_capacity_management.md](../../Architecture/adr/acrme_adr_002_quota_and_capacity_management.md) |
| **ADR-003** | Capacity Management During DR | Distributed DR reference model, three-tier sharing model, DR activation sequence, CVAL earmark, engine state machine, and no-double-count rule. | [acrme_adr_003_capacity_management_during_dr.md](../../Architecture/adr/acrme_adr_003_capacity_management_during_dr.md) |
| **ADR-004** | Forecast & Increase of Capacity & Quota | 10-step steady-state lifecycle, 5-phase auto-increase trigger model, forecast horizon, debounce/settle policy, and auto-decrease exclusion rule. | [acrme_adr_004_forecast_and_increase_of_capacity_and_quota.md](../../Architecture/adr/acrme_adr_004_forecast_and_increase_of_capacity_and_quota.md) |
| **ADR-005** | Distributed DR Reference Model | Multi-source multi-destination DR topology, overcommit accounting, annual mock DR drill, failback orchestration, and the max-not-sum sizing correction. | [acrme_adr_005_distributed_dr_reference_model.md](../../Architecture/adr/acrme_adr_005_distributed_dr_reference_model.md) |

---

## G — Design Gaps

**Primary source:** [UML Class Diagrams Summary — Known Gaps](../../Design/acrme_uml_class_diagrams_summary.md)

G-codes identify **explicitly documented open design items** — the "30% gap" declared in the UML class diagrams summary. These are design decisions, not research tasks.

| Code | Name | One-line definition | Impact |
|------|------|---------------------|--------|
| **G-14** | Consumer credential model (Tier 3) | No decision yet on how ACRME authenticates to a consumer-owned resource group to forcibly disassociate a VM (customer-provisioned UAMI? Cross-tenant SPN? Delegated consent?). | Tier 3 VM disassociation cannot be implemented until resolved. |
| **G-15 / B-3** | Engine mode state machine incomplete | `engine_mode` transition guards, concurrency model, crash-recovery sequence, and operator API contracts are not yet fully specified. | Reconciliation loop and runner core cannot be production-hardened. |
| **G-20** | Cosmos DB entity schemas | Partition key strategy, secondary indexes, TTL policies, and consistency levels for all entities are not yet designed. | Data-layer implementation cannot begin; partition keys are irreversible after production data is written. |
| **G-21** | FastAPI service contracts | Request/response DTOs, RBAC enforcement middleware, API versioning, and endpoint specifications for all services are not yet defined. | Inter-service integration cannot be coded or tested. |

---

## ACRME-E — Backlog Epics

**Primary source:** [Backlog Epics, Stories & Tasks — Epic Index](../../Reference-Material/backlog/acrme_epics_stories_tasks.md)

Each epic contains stories (`ACRME-S####`) and tasks (`ACRME-T######`). 20 epics / 72 stories / 193 tasks / 457 story points total.

| Code | Epic name | Stories | Points | Phase |
|------|-----------|---------|--------|-------|
| **ACRME-E01** | Foundation & Platform Infrastructure | 5 | 39 | P1 |
| **ACRME-E02** | Subscription & Onboarding Lifecycle | 4 | 34 | P1 |
| **ACRME-E03** | CRG & Capacity Reservation Management | 3 | 21 | P1 |
| **ACRME-E04** | CRG Sharing & Consumer Authorization | 4 | 21 | P1 |
| **ACRME-E05** | Quota Group Management | 4 | 21 | P1 |
| **ACRME-E06** | Cross-Subscription Zone Alignment | 2 | 13 | P1 |
| **ACRME-E07** | Region Selection & Placement Engine | 8 | 49 | P1 |
| **ACRME-E08** | Placement Scoring & Forecasting | 4 | 23 | P1/P2 |
| **ACRME-E09** | State Model & Concurrency Controls | 2 | 21 | P1 |
| **ACRME-E10** | DR Activation & Failback | 3 | 24 | P1 |
| **ACRME-E11** | Tier Escalation (Emergency Capacity) | 3 | 19 | P1 |
| **ACRME-E12** | AKS & VMSS Integration | 2 | 13 | P2 |
| **ACRME-E13** | Data Architecture & Entity Model | 2 | 13 | P1 |
| **ACRME-E14** | API Architecture | 3 | 16 | P1 |
| **ACRME-E15** | Security, RBAC & Managed Identity | 3 | 19 | P1 |
| **ACRME-E16** | Observability, Dashboards & Alerts | 3 | 15 | P1 |
| **ACRME-E17** | Reconciliation & Scaling | 4 | 23 | P1 |
| **ACRME-E18** | POC & Validation Program | 4 | 29 | P1 |
| **ACRME-E19** | Production Readiness Gates & Governance | 3 | 13 | P1 |
| **ACRME-E20** | v2.4 Reservation-Model Reconciliation | 6 | 31 | P1 |

---

## Complete Code Inventory (Alphabetical)

Quick-scan index of every code in the corpus, in alphabetical/numerical order.

| Code | Family | One-liner |
|------|--------|-----------|
| A.1 | Formulas | Reservation target: `reserved = allocated + buffer` |
| A.2 | Formulas | Reservation headroom: `headroom = reserved - allocated` |
| A.3 | Formulas | Reservation deficit: `deficit = allocated - reserved` |
| A.4 | Formulas | Available subscription quota: `quota_limit − quota_current_value` |
| A.5 | Formulas | Deployment quota deficit: `committed_vCPUs − available_quota` |
| A.6 | Formulas | DR destination requirement (max, not sum) |
| A.7 | Formulas | DR capacity gap: `DR_req − dr_reserved` |
| A.8 | Formulas | Shared-DR overcommit ratio |
| A.9 | Formulas | Even zone-distribution target and skew (PLC-011) |
| ACRME-E01..E20 | Backlog | Foundation → Production Readiness (20 delivery epics) |
| ADR-001 | Architecture | Region selection and placement decision record |
| ADR-002 | Architecture | Quota and capacity management decision record |
| ADR-003 | Architecture | Capacity management during DR decision record |
| ADR-004 | Architecture | Forecast and increase of capacity decision record |
| ADR-005 | Architecture | Distributed DR reference model decision record |
| C-1 | Configurable | DR bootstrap capacity |
| C-2 | Configurable | Production reservation buffer |
| C-3 | Configurable | Production quota buffer |
| C-4 | Configurable | Reconciliation frequency |
| C-5 | Configurable | Failback model |
| C-6 | Configurable | Onboarding selection mode |
| C-7 | Configurable | Quota grouping model |
| C-8 | Configurable | Region catalogue and flags |
| C-9 | Configurable | Reservation over-allocation policy |
| C-10 | Configurable | DR drill duration/rotation |
| C-11 | Configurable | DR sizing basis (max vs sum) |
| C-12 | Configurable | Resource naming convention and counter |
| C-13 | Configurable | Zone-distribution target and tolerance |
| CAP-001 | Capacity | Authoritative managed scope |
| CAP-001a | Capacity | Core subscription = all production |
| CAP-002 | Capacity | Azure resource must precede config activation |
| CAP-003 | Capacity | Reservation target formula |
| CAP-004 | Capacity | Associated-but-deallocated VMs |
| CAP-005 | Capacity | Automated reconciliation |
| CAP-006 | Capacity | Reconciliation frequency |
| CAP-007 | Capacity | Scale-up behaviour |
| CAP-008 | Capacity | Scale-down behaviour |
| CAP-009 | Capacity | Zero-capacity support |
| CAP-010 | Capacity | No automatic deletion |
| CAP-011 | Capacity | Availability-zone isolation |
| CAP-012 | Capacity | Regional isolation |
| CAP-013 | Capacity | Capacity sharing |
| CAP-014 | Capacity | Shared capacity visibility |
| CAP-015 | Capacity | No double counting |
| CAP-016 | Capacity | Reservation integrity validation |
| CAP-017 | Capacity | Deployment failure policy |
| CAP-018 | Capacity | Over-allocation policy |
| CAP-019 | Capacity | Scope-file governance |
| CAP-020 | Capacity | Availability-Set VMs ineligible (v2.4) |
| CAP-021 | Capacity | Deallocate-or-migrate-to-AZ precondition (v2.4) |
| CAP-022 | Capacity | Seed-at-0 matrix and budget governance (v2.4) |
| CAP-023 | Capacity | Regional and per-AZ CRG structure (v2.4) |
| CAP-024 | Capacity | Reactive SKU/AZ discovery (v2.4) |
| DAT-001..006 | Data | State store, entities, freshness, history, versioning |
| DEC-001 | Decision | Middle East DR offering |
| DEC-002 | Decision | DR drill duration and failback |
| DEC-003 | Decision | Geography exception approval |
| DEP-001 | Dependency | Azure feature maturity (CR Sharing Preview→GA) |
| DR-001 | DR | Single-region failure basis |
| DR-002 | DR | Distributed DR model |
| DR-003 | DR | Destination distribution |
| DR-004 | DR | CVAL target contribution |
| DR-005 | DR | CVAL may exceed DR need |
| DR-006 | DR | Staged DR capacity acquisition |
| DR-007 | DR | DR target is configurable |
| DR-008 | DR | Control plane first |
| DR-009 | DR | Recovery prioritisation |
| DR-010 | DR | DR declaration guardrail |
| DR-011 | DR | Source region unavailable during outage |
| DR-012 | DR | DR drill rotation |
| DR-013 | DR | Failback policy |
| DR-014 | DR | Middle East DR_NOT_OFFERED flag |
| DR-015 | DR | Future active-active note |
| DR-016 | DR | Reciprocal multi-source hosting |
| DR-017 | DR | Non-concurrent max-not-sum sizing |
| DR-018 | DR | Source→destination DR index |
| DR-019 | DR | Standby activation on declaration |
| ENV-001..007 | Environment | Production through R&D environment policy rules |
| FIN-001..008 | FinOps | Idle cost, buffer, overcommit accounting |
| FR-1..8 | Functional | Top-level functional capability areas |
| G-14 | Design gap | Consumer credential model (Tier 3) unresolved |
| G-15/B-3 | Design gap | Engine mode state machine incomplete |
| G-20 | Design gap | Cosmos DB entity schemas not yet designed |
| G-21 | Design gap | FastAPI service contracts not yet defined |
| GOV-001..009 | Governance | Least privilege through data classification |
| HC-1..11 | Hard constraints | Blocking placement rules (region, capacity, quota, zone) |
| INT-001..007 | Integration | AEP contract, idempotency, input/output spec |
| NFR-001..010 | Non-functional | Availability, consistency, performance, idempotency |
| NFR-R1..3 | Placement NFR | Latency, freshness, determinism |
| OBS-001..005 | Observability | Metrics, alerts, dashboards, SLO |
| OPS-001..006 | Operational | Runbooks, pause, override, naming convention |
| PLC-001..011 + PLC-010a | Placement | Seed record, scoring, zone distribution |
| POC-001..011 | POC | Azure behaviour validation gates |
| QUA-001..014 | Quota | Pooling, allocation, reclamation, governance |
| R1..8 | Placement | Specific placement behaviours |
| RDY-001..004 | Readiness | Deployment readiness gate and state model |
| REG-001..005 | Region | Region catalogue, distribution model, cross-geo |
| VR-1..11 + VR-8a | Validation | Named enforcement checks for hard constraints |

---

*This index is generated from the v2.4 baseline. When new codes are introduced, add them here first — this document is the master lookup point.*
