# ACRME - Functional Design Document (FDD)

| Field | Value |
|---|---|
| Version | 2.0 reconciliation draft |
| Date | 16 October 2026 |
| Status | v4.0 reconciliation draft - pending Architect decisions and POC validation; not ratified |
| Baseline | [Requirements baseline v4.0](../Requirements/acrme_requirements_baseline_v4_0.md) |
| Owner | Principal Cloud Architect |
| Audience | Business, architecture, product platforms, AEP, operations, audit, FinOps |
| Companion | [Technical Design Document](acrme_technical_design_document.md) |
| Change history | 1.0: historical v2.4 design. 2.0: two scopes, domains, Foundation, readiness and quota corrections; current traceability. Historical versions remain in Git. |

**Type:** Design Note. **Phases touched:** P1 visibility/protection, P2 quota, P3 placement, P4 DR, P5 multi-domain binding.

This document states **what** ACRME must do. The TDD owns components, detailed contracts, algorithms and implementation choices. Requirements govern over this draft. Historical ADRs are contextual, not current authority where they conflict with baseline v4.0.

**Evidence:** `[Documented]` identifies baseline requirements or official platform behavior; `[Decided]` identifies a baseline programme decision; `[Derived]` identifies design consequences; `[Assumed]` identifies a proposal requiring approval. No live POC completion is implied by this reconciliation.

## 1. Purpose, scope and vocabulary

[Decided] ACRME protects production first, maintains allocated-plus-buffer reservations, governs quota separately and supplies explainable, fresh readiness to AEP. Policy is configurable; idle cost and lean DR matter. Actual workload deployment belongs to AEP. No live environment change is authorized by this document.

| Term | Functional meaning |
|---|---|
| Customer Region Vector (CRV) | One customer/geography binding of distribution model, Prod, CVAL and DR regions; reused by every domain (PLC-013). |
| Domain group | Customer-owned workload grouping such as TMS/WMS, with separate capacity ownership (DOM-001). Taxonomy is configurable C-14; DEC-004 remains open. |
| Instance group (ig) | Domain/environment/region subscription-bound capacity set; no ig spans domains (DOM-002). |
| Domain Placement Binding (DPB) | Deterministic lookup/binding of ig, subscription, CRG sets, sizing, zones and quota inside an already bound CRV region (PLC-014). |
| CRG / reservation | Regional group with reservations for exact VM sizes and zones. Family identity alone cannot select a reservation (CAP-016/023). |
| Seed record / seed reservation | Seed record persists customer placement/CRV and DPB references. A seed reservation is a retained count-0 resource, not a placement decision (PLC-003/CAP-022). |
| Customer quota group | Governed membership of the customer's domain ig subscriptions; regional/family cells are accounting and operation scopes, not separate memberships (QUA-004/015). |
| DR Foundation | Always-present, domain-specific bootstrap set with pre-staged quota; independent of sharing (DR-021). |

**In scope:** REG, ENV, CAP, QUA, RDY, PLC, DOM, DR, FIN, INT, DAT, OBS, GOV, NFR and OPS requirements. Forward forecasting/optimization remains phased, not an implicit commitment to runtime automation (baseline section 28).

**Out of scope:** workload deployment, automatic live migration, simultaneous failures beyond an approved guarantee, multi-cloud DR, and relaxed hard constraints. Infrastructure provisioning is separate from engine runtime logic.

## 2. Functional architecture and actors

The ordered control path is:

1. AEP submits customer/domain intent.
2. Resolve or reuse **customer CRV**; select regions only if the seed is absent or an approved migration changes it.
3. Resolve **domain DPB** deterministically within those regions.
4. Evaluate exact deployment readiness and acquire a concurrency-safe intent.
5. AEP associates/deploys against validated references; ACRME confirms or compensates the outcome.

[Decided] PLC-015 ordering is mandatory. Adding WMS to an existing TMS customer reuses the CRV but creates a separate DPB/ig, never another region-selection run.

| Actor | Responsibility |
|---|---|
| Onboarding/product team | Supplies exact Prod region, customer/domain, workload requirements and approved budget. |
| AEP | Calls the placement/readiness contract before initial and capacity-changing deployment; reports deployment outcome (INT-001/008). |
| Platform operator | Manages scoped config, approvals, pause/overrides and remediation. |
| DR coordinator | Authorizes declarations/exercises, CVAL release and business-priority recovery/failback. |
| FinOps | Reviews buffers, idle cost, source/domain attribution and expansion justification. |
| Auditor/security | Reviews least privilege, policy exceptions and immutable decision/change evidence. |
| Architect/business/Legal | Closes design/guarantee decisions, including cross-geo scenario scope and residency clearance. |

Canonical flow: [two-scope pipeline](diagrams/acrme_v4_pipeline.mmd). It replaces the old F1/F4/T7 pipeline views. Canonical sources are local `.mmd`, not a stale rendered historical image.

## 3. Policy and region classifications

[Decided] The versioned catalogue drives REG-001/002/003, not hard-coded environment-to-region mappings.

| Classification/model | Functional rule |
|---|---|
| Standard | Eligible for automated scoring after HC/readiness checks. Any Standard region can host permitted Prod, CVAL or DR roles. |
| Restricted | Never enters automated CVAL/DR scoring; exact Prod requests route through approved exception workflow. |
| US three-region | Prod anchored; CVAL/DR selected among eligible remaining regions; co-location optional under PLC-010, not universally forbidden. |
| Europe/Australia/Asia Pacific two-region | CVAL and DR co-locate deterministically in the remaining non-Prod region (PLC-010a). |
| Middle East cross-geo | Prod/CVAL co-locate locally in separate capacity sets; DR weighted-selected in Europe, with dedicated DR capacity, not local CVAL sacrifice (PLC-010b/DR-020). |
| Country DR_NOT_OFFERED | Overrides DR assignment before scoring; persist no DR region and an explicit reason (DR-014). No silent substitution. |

[Assumed] A-ME1 residency clearance is not established by this design. Legal approval and HC-10 remain required for applicable customers. Japan East is pending catalogue confirmation, not automatically eligible.

## 4. Functional capabilities

### 4.1 Capacity and topology (CAP-001 through CAP-025, ENV-001 through ENV-007)

- [Decided] Managed scope includes customer/domain, subscription, region, zone, exact SKU/family, environment, resources, policies and config version. Out-of-scope resources are not mutated (CAP-001/GOV-003).
- [Decided] All workloads in a shared core subscription receive production classification (CAP-001a); non-production must not run there.
- [Decided] Create/validate resources in Azure before activating their config (CAP-002). Reactive discovery of an in-scope allocated unmanaged SKU/AZ protects at `allocated + buffer` while simultaneously raising governance/budget ratification (CAP-024). It does not authorize mutation outside managed scope.
- [Decided] Per domain/environment/region and exact SKU/zone, desired target is **allocated VM count + approved buffer** (CAP-003/F.1). Deallocated associations do not increase that desired target; their quota and restart risk remain separately visible.
- [Decided] CAP-004 currently prevents executable shrink below associated count until dissociation. Preserve that programme guard and report desired versus constrained quantity/cost/remediation; its relationship with acceptance criterion 3 is a pending clarification (section 8, B4). Do not silently dissociate workloads.
- [Decided] Reconcile toward target at the configurable cadence (six-minute reference, CAP-006). Failure to restore a buffer holds a safe state and alerts the deficit; it is not success.
- [Decided] A legitimate approved target of zero may retain a count-0 resource under CAP-009 when all guards permit. Intentional retirement, deletion and scope removal require the separate CAP-010 approved workflow. Zero demand never implies permission to delete or implicitly zero DR bootstrap.
- [Decided] Availability-Set VMs are ineligible; exclude them from target-driving counts and surface remediation. Eligible zonal placement is preferred; non-zonal placement is the permitted exception for unsupported zonal SKUs. No automatic running-workload migration (CAP-020/021).
- [Decided] Initialize the approved exact-SKU/AZ seed matrix under product budget governance (CAP-022).

| Set class | Ownership and isolation |
|---|---|
| `prod` / `crg-pr-*` | [Decided] Domain-specific Prod capacity only; never shared with CVAL/DR or another domain (CAP-025). |
| `cvdr` / `crg-cvdr-*` | Same-domain CVAL/DR extension; no cross-domain sharing. Release is declaration-gated. |
| `drf` / `crg-drf-*` | Domain DR Foundation; always present and quota-prestaged, separate from live CVAL. |

[Documented] CAP-023 defaults to one zonal CRG per applicable domain/set/subscription/region, with zones declared at creation and one reservation per exact VM size per zone. Optional per-zone groups are distinct from the default; no-zone `reg` is an exception pinned to one Azure-selected zone, not a region-wide pool. CAP-025 permits the explicit same-domain cvdr exception to general environment separation.

[Decided] Production uses a reservation in the **deploying subscription** until sharing is GA for the approved version (CAP-013). Preview sharing requires explicit approval, same-domain authorization, same region, supported tenant/trust, explicit consumers (at most 100), and physical-zone mapping. Authorization is not allocation; shared capacity is counted once (CAP-014/015). A matching logical zone number in two subscriptions is not sufficient (CAP-016).

Topology: [domain sets and quota ownership](diagrams/acrme_v4_topology.mmd).

### 4.2 Quota governance (QUA-001 through QUA-015)

[Documented] Quota and reserved capacity are independent. A subscription belongs to one Quota Group; that object spans multiple regional/family cells. Actual deployment checks the subscription's quota, not the group's transferable balance (QUA-003/004).

- Customer domain ig subscriptions use the customer's central group; never another customer's group. Cell accounting covers Prod/CVAL/DR with protected logical earmarks, not separate per-family group memberships.
- Inventory both **VM-family** and **total-regional vCPU** assigned/used/remaining values. Available quota is their lesser remaining value (QUA-007); deallocated usage is not assumed free.
- Keep observed approved group balance, subscription assignments, engine commitments, protected floors and desired increase requests distinct.
- Allocation/reclamation is justified and audited. Do not allocate merely because a group has spare quota; never reclaim below usage, committed demand, Prod growth buffer or approved DR need.
- Confirm transfers on the target subscription before relying on them. An accepted request or pool earmark is not deployable quota.
- Configurable group/subscription replenishment thresholds default to **85%** under QUA-015; their numeric utilization basis and zero-limit handling require an explicit policy contract (TDD section 8).
- Quota in a failed region is not a destination capacity/quota source.
- Provider creation/growth and shared consumer deployment require their respective quota (QUA-013). POC-001 confirms the selected API behavior; it does not make this check optional.

### 4.3 Readiness (RDY-001 through RDY-004)

[Decided] Readiness is evaluated per DPB and intended incremental demand. It requires approved region/zone/SKU and policy, matching resources/authorization, allocatable residual reservation capacity or explicitly approved over-allocation, both quota caps, fresh records and no HC/policy block. Concurrent requests must not spend the same capacity or regional quota twice.

| State | Functional meaning |
|---|---|
| READY | Every required gate passes for the recorded intent/snapshot; not an unlimited or perpetual permission. |
| READY_WITH_RISK | Only an explicitly permitted risk path, such as approved unguaranteed over-allocation. Does not override quota, isolation, stale-state or approval failures. |
| QUOTA_DEFICIT | Required deployable subscription quota/commitment cannot be established. |
| RESERVATION_DEFICIT | Required residual reserved coverage is insufficient. |
| CAPACITY_UNAVAILABLE | [Documented] Azure cannot supply requested additional capacity (RDY-002). |
| STALE_STATE | Records exceed max age and refresh cannot restore validity. |
| POLICY_BLOCKED | Scope, HC, authorization or required approval blocks the operation. |
| VALIDATION_REQUIRED | Essential behavior, mapping, policy term or evidence is unresolved; not a deployment approval. |

[Derived] Return all blocking reasons; a single state does not hide additional failures. A quota shortage is not downgraded to risk simply because a reservation exists. Readiness must be revalidated when intent, snapshot or policy changes.

### 4.4 Placement, domains and zone distribution (PLC, DOM, REG)

[Decided] Exact Prod region is the default validated input; geography-only derivation requires explicit approval and customer acknowledgement (PLC-001/002). Seed changes require approved migration, not upgrades/rebuilds (PLC-003/004/005).

1. Resolve/reuse `CRV(customer,geography)` using the distribution rules in section 3.
2. Score only customer-aggregate candidates using current capacity, quota, buffers, expected DR, zone support, freshness and fairness (PLC-007/008, F.10/F.11).
3. Bind each domain's DPB in CRV regions; resolve ig/shard and sets, F.1 sizing, F.9 zone spread and quota draw (F.12). Domain shortage blocks/remediates the DPB, not customer region re-selection.
4. Check readiness and hold commitments before deployment (PLC-015/INT-006).

[Decided] Fairness counts distinct customers per geography with at least one provisioned/deploying environment; the same live denominator is shared by all scores. F.10 fairness is 1 at zero customers (PLC-012), never a fixed forecast.

[Decided] Per-domain/environment zone target is `round(VMs / zone_count)`; skew is the VM-count difference per F.9. Prefer the eligible least-populated zone; recommend governed rebalancing when configured count-skew tolerance is exceeded. No fixed percentage tolerance is introduced. Rounding/ties and empty-workload policy must be explicit before executable decisions. Combined `RegionZoneLoad = sum across domains` is an observation/alert only, never cross-domain reserve sizing (PLC-016/C-15).

### 4.5 DR Foundation, extension and activation (DR-001 through DR-021)

[Decided] DR planning protects workload **portions** attributed to domain, source and destination, not a complete copy at every destination. For a defined isolated capacity partition, aggregate all demand from one failed source, then take **MAX across non-concurrent source regions** (DR-017/F.6). C-11 is an explicit approved conservative override. Do not net capacity across domains, SKUs or physical zones.

- **Foundation:** dedicated `drf` bootstrap sized by approved product/domain/region/zone/family policy, always present with pre-staged quota. Control planes then business-priority P0/P-1 waves start independently of Preview sharing (DR-007/008/021, C-16).
- **Extension:** same-domain `cvdr` capacity is released only after authorized declaration/exercise and required action approval. Do not count active CVAL simultaneously as immediately free DR capacity.
- **Cross-geo:** ME customers use dedicated Europe DR capacity; local CVAL is not sacrificed for European recovery. Country Legal overrides remain effective. Cross-geography concurrent-failure coverage is unresolved B3, not proven by a single-source MAX.
- [Decided] **Staging (DR-006):** (1) approved bootstrap; (2) already available destination reservation and quota; (3) approved CVAL shutdown/disassociation; (4) supported sharing/reassignment; (5) confirmed pooled quota allocation; (6) Azure quota/capacity requests; (7) report unrecoverable gaps. Earlier stages still require readiness; no zero-latency API guarantee.
- **Activation:** source->destination index selects the failed source's exact customer/domain standby sets. Activate in authoritative business-priority order; audit partial failure and wave state, preserve seed/lineage and support governed reversal.
- **Failback/drills:** support extended operation and earlier failback policies without losing identity/history; DEC-002 decides duration. Annual rotation is governed, not inferred from a restored snapshot.

### 4.6 FinOps, observability, governance and operations

[Decided] FIN-001 through FIN-008 require measured idle cost, justification before expansion and customer/domain/environment/region attribution. Single-count shared cvdr cost and per-domain drf cost. Cost-only optimization cannot breach production or bootstrap protection.

[Decided] OBS-001 through OBS-005 include per-domain ig utilization/zone distribution, quota cells, Foundation coverage, max-source coverage, activation, snapshot age, API throttling and combined region-load alerting. Alerts include domain/subscription/SKU/zone, desired/actual, owner, correlation and remediation.

[Decided] GOV-001 through GOV-009 require managed/workload identity, least privilege, separate approval/execution/review, classified customer metadata, time-bound exceptions/overrides and audited break-glass. No secrets in config/logs. OPS-001 through OPS-006 require pause retaining inventory/alerts, maintenance awareness, expiring override protection, ownership/escalation and deterministic config-driven naming. Domain token belongs in subscription identity, not a cross-domain CRG registry key.

### 4.7 AEP contract (INT-001 through INT-008)

[Decided] Input includes customer/realm, domain, product, environment, exact Prod region or approved geography exception, subscription, exact SKU/count, zone requirement, priority, requested time and correlation ID. Output includes CRV and DPB references, ig subscription, domain sets, zone spread, quota-draw route/status, available/required quantities, reasons, exceptions, snapshot timestamp and decision ID.

Idempotency is based on correlation/key plus desired state; a changed payload must not reuse a prior approval. AEP polls tracked operations, associates only validated references and returns deployment outcomes. On partial failure, record and compensate safely or raise a recoverable task (INT-007). Provider quota is never proof of consumer deployability.

## 5. End-to-end operating flows and phases

| Flow | Required order / boundary |
|---|---|
| New or existing customer/domain deployment | CRV resolve/reuse -> DPB -> fresh readiness/atomic commitments -> validated AEP deployment -> confirmation/compensation. |
| Steady state | Read fresh scoped observations -> desired allocated+buffer -> guards/approvals -> confirm quota if needed -> resize retained reservation -> confirm actual -> audit/snapshot. Inventory continues during pause/hold. |
| DR declaration | Authorize declaration -> pending mode/activation approval -> active incident -> source index -> readiness-gated staged waves -> governed failback. |
| Drill | Authorized exercise, scoped CVAL actions and rehearsed reversal; no implicit production teardown. |

[Decided] Baseline delivery phases are P1 visibility/Prod protection, P2 quota automation, P3 seed/placement, P4 distributed DR and P5 multi-domain/two-scope binding. This target design covers all five; a partial phase implementation must not claim the complete target. Preserve legacy Phase 1 operator-gated decrease and prohibition on destructive association transfers; changed autonomy requires approval.

## 6. State and data

Five engine modes remain `STEADY_STATE`, `DR_DECLARATION_PENDING`, `DR_EVENT_ACTIVE`, `FAILBACK_PENDING`, `INCIDENT_HOLD`. Steady-state mutation runs only in steady state; DR transfer only in active approved incident scope. CVAL action keeps its own authorization.

[Assumed] The [guarded mode diagram](diagrams/acrme_v4_engine_modes.mmd) proposes retaining interrupted mode/incident identity and returning from hold only through explicit authorized resumption. Freshness restoration alone cannot complete failback or clear DR. Exact resumption approval remains Architect-pending; inventory/alerts continue while blocked.

[Decided] DAT-001 through DAT-006 require durable authoritative state separate from transient responses: customer seed/CRV, domain and ig registries, DPBs, per-domain sets, exact reservations, sharing/zone mappings, quota membership/cells/subscription assignments, DR index/earmarks, deployment intents, activation/operation records, config versions, audit and history. Every decision references its observations and policy. API/schema transitions are versioned with an approved compatibility period, not implicit reinterpretation of legacy records.

## 7. Acceptance mapping

These are required demonstrations, **not executed test results**. Numbers match baseline section 22.

| Baseline acceptance | Required evidence | Functional location |
|---|---|---|
| 1 | Scoped inventory of reservations, VM states, quota, sharing and config | 4.1/4.2/6 |
| 2 | Allocated+buffer target and reconciliation | 4.1/5 |
| 3 | Associated VM desired/executable distinction and approved remediation; B4 closure | 4.1/8 |
| 4 | Missing config resource blocked before deployment | 4.1/4.3 |
| 5 | Consumer shortage fails safely on either quota cap | 4.2/4.3 |
| 6 | Allocate/reclaim without breaching protection | 4.2 |
| 7 | Concurrent intents cannot double-spend capacity/quota | 4.3/4.7 |
| 8 | Fresh machine-readable AEP readiness | 4.3/4.7 |
| 9 | Seed creation/reuse and controlled change | 4.4 |
| 10 | Single-source simulation computes per-partition MAX | 4.5 |
| 11 | Releasable CVAL and authorized impact | 4.5 |
| 12 | Idle cost/protection deficit reporting | 4.6 |
| 13 | Complete automated/manual audit | 4.6/6 |
| 14 | Throttling produces safe stale/degraded behavior | 4.3/6 |
| 15 | Read-only/dry-run intended changes | 5, TDD section 14 |
| 16 | Correct source/domain standby activation from index | 4.5 |
| 17 | Availability-Set exclusion/remediation | 4.1 |
| 18 | Budgeted count-0 seed matrix/reactive governance | 4.1 |
| 19 | Default zonal structure, exact-size/zone uniqueness, names | 4.1 |
| 20 | Per-domain under-represented zone preference/skew action | 4.4 |
| 21 | Right-size versus intentional retirement workflow | 4.1/5 |
| 22 | Exact/geography CRV paths with TMS/WMS separate DPBs | 2/4.4 |
| 23 | Domain prod/cvdr/drf sets and isolation | 4.1 |
| 24 | Foundation-only bootstrap, then gated extension | 4.5 |
| 25 | Central customer quota draws/85% replenishment | 4.2 |
| 26 | Forward forecast/optimization dry-run at customer/domain grain | 1/5, TDD section 14 |

## 8. Decisions, evidence and approval blockers

| Item | Current treatment / closure |
|---|---|
| B1 - displayed F.4 | Follow QUA-007/F.12's explicit two-cap requirement; proposed formula correction not applied to baseline. |
| B2 - F.8 explanation | Equal positive portions give ratio equal to number of sources, not 1; zero-demand reporting convention pending. |
| B3 - cross-geo failure set | Architect/business must decide global versus per-geography concurrent guarantee; affected cross-geo coverage cannot be certified. |
| B4 - shrink precedence | Preserve CAP-004 association guard, report constrained target; acceptance wording awaits Architect clarification. |
| State resumption | TDD section 7 proposes guards; not a new approved ADR. |
| Formula policy gaps | TDD sections 8/9 define required rounding, normalization, replenishment and quota-charge evidence; unresolved terms return VALIDATION_REQUIRED. |
| POC-001 | Consumer quota documented; selected API-version confirmation remains. |
| POC-002/003/004/005 | Sharing order, physical zones, throttle behavior and VM-state semantics remain open. |
| POC-006/007/008/009/010 | DR topology, bootstrap, quota/reservation buffers and production cadence remain open. |
| POC-011/012/013 | Overcommit safety, domain-bounded sharing and live two-scope multi-domain flow remain open. |
| DEC-002/003/004 | Failback duration, geography-exception approver and domain taxonomy pending. |
| DEP-001 / A-ME1 | Reservation Sharing Preview maturity and Legal residency approval; neither is quota-group maturity. |

## 9. Requirement traceability and release gate

| Current baseline codes | FDD sections |
|---|---|
| REG-001/002/003; ENV-001 through ENV-007 | 1/3/4.1/4.5 |
| CAP-001, CAP-001a, CAP-002 through CAP-025 | 4.1/4.3/5 |
| QUA-001 through QUA-015; RDY-001 through RDY-004 | 4.2/4.3 |
| PLC-001 through PLC-005, PLC-007 through PLC-016 | 2/3/4.4; PLC-006 is retired, not an active stage |
| DOM-001 through DOM-004 | 1/2/4.1/4.4/6 |
| DR-001 through DR-021 | 4.5/5/6/8 |
| FIN-001 through FIN-008; OBS-001 through OBS-005 | 4.6 |
| INT-001 through INT-008; DAT-001 through DAT-006 | 4.7/6 |
| GOV-001 through GOV-009; OPS-001 through OPS-006 | 4.6/5 |
| NFR-001 through NFR-010 | 4.3/4.7/5/6; technical details in TDD section 14 |
| C-1 through C-16; POC-001 through POC-013; DEC-001 through DEC-004; DEP-001 | 3/4/5/8 |

[Derived] **Document consistency is not production ratification.** The TDD section 17 contains per-HC, formula, DR and WAF gates and counterexamples. Baseline clarifications, design approvals and POCs remain release blockers for affected guarantees. No baseline amendment or runtime behavior is approved by this document.
