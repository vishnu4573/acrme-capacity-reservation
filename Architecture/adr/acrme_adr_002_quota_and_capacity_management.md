**Project:** Azure Capacity Reservation Management Engine (ACRME)  
**Classification:** Principal Cloud Architect - Architecture Governance  
**Version:** 2.4  
**Date:** 7 September 2026  
**Status:** Accepted - supersedes ADR-002 v2.1 quota grouping content  
**Part of:** ACRME Architecture Decision Records - aligned to Capacity & Quota Management Requirements Baseline v2.4.

> **About ADRs.** An Architecture Decision Record captures a significant architectural decision, the context that forced it, the options considered, the choice made, and its consequences. This ADR adopts the **single governed quota pool** as the primary model per QUA-004 and updates quota and capacity accounting to match Requirements Baseline v2.4. Evidence tags: `[Documented]`, `[Decided]`, `[Derived]`, `[Assumed]`.

> **v2.4 update — reservation-model gaps.** This revision folds the reviewed architecture-diagram gaps into the capacity-management decision: **reservation eligibility** now explicitly excludes Availability-Set VMs (**CAP-020**) and requires a deallocate/redeploy-to-AZ onboarding precondition (**CAP-021**); the managed estate is initialised as a **seed matrix of count-0 reservations** per eligible SKU×region×AZ under per-product-team budget governance (**CAP-022**, extending CAP-009), reconciled with **reactive SKU/AZ discovery** that auto-creates a reservation and simultaneously raises a scope-file governance item (**CAP-024**, reconciling CAP-019); reservations are organised into an explicit **regional + per-AZ CRG structure per environment** (**CAP-023**, extending CAP-011); VMs are placed toward an **even ≈1/zone_count per-zone distribution with a rebalancing action** (**PLC-011**); a shared **core subscription is classified entirely production** (**CAP-001a**); the **decommissioning-workflow boundary** is made explicit (**CAP-008/CAP-010**); and a deterministic **RG/CRG/subscription naming convention + counter** is adopted (**OPS-006**, config **C-12**; zone tolerance config **C-13**). See the new *Capacity Reservation Model (v2.4)* section below.

---

# ADR-002 - Quota and Capacity Management

**Status:** Accepted  
**Date:** 27 August 2026  
**Deciders:** Principal Cloud Architect, Platform Engineering, FinOps, Quota Owner  
**Related requirements:** CAP-001, CAP-001a, CAP-002..CAP-024, QUA-001..QUA-014, RDY-001..RDY-004, PLC-011, OPS-006, FIN-001..FIN-006, GOV-001..GOV-006 (config C-12/C-13)  
**Related POCs:** POC-001, POC-002, POC-003, POC-008, POC-011, DEP-001

## Context

Capacity reservations and VM-family quota are independent Azure control-plane resources. ACRME must validate both before deployment because a reservation without deployable consumer-subscription quota can still fail, and quota without reserved capacity does not guarantee physical capacity. `[Documented]`

Requirements Baseline v2.2 also changes quota from a passive limit to a governed resource pool. Quota is deliberately used as a cost and consumption governor: teams must justify quota increases, and unused regional quota can be pooled and reallocated only under policy. `[Decided]`

The earlier two-quota-group model (a Prod-only group plus a shared NonProd/DR group) protected Prod from NonProd consumption but fragments quota and forces separate, more frequent quota-increase requests to Microsoft. QUA-004 resolves this in favour of **one governed quota pool per applicable regional/quota-family scope covering Prod, NonProd/CVAL, and DR together**, because a single pool collects all otherwise-stranded default per-region quota (QUA-003 hoarding) into one manipulable balance and lets ACRME allocate it wherever it is needed on demand — maximising manipulation flexibility, improving utilisation, and avoiding frequent quota requests to Microsoft. This ADR therefore **adopts the single governed pool as the primary model**; a two-group (or multi-group) topology is retained only as a narrow, configuration-driven governance exception invoked when Azure Quota Group limits or a mandatory Prod-isolation governance boundary make a single pool impossible. `[Decided]`

## Decision

Adopt a **separate-but-correlated capacity and quota control plane**:

1. **Capacity and quota are separate domains.** ACRME maintains reservation state and quota state independently but correlates them by subscription, region, zone, VM/quota family, SKU, environment, product, and intended demand. `[Decided]`

2. **Quota is a consumption governor.** Unallocated pooled quota is not a reason to increase a subscription automatically. Every increase records owner, workload, region, SKU/family, amount, existing usage, target date, and business justification. `[Decided]`

3. **One governed quota pool is the primary model.** Prod, NonProd/CVAL, and DR share **one** governed quota pool per applicable region and quota family (QUA-004). All eligible default per-region quota is hoarded into this pool (QUA-003) and allocated on demand to whichever environment needs it, maximising manipulation flexibility, improving utilisation, and minimising quota-increase requests to Microsoft. Prod protection inside the shared pool is enforced by engine controls (reserved Prod headroom floor, DR floor earmark, and priority ordering at allocation/reclamation time), not by physical group separation. `[Decided]`

4. **Multi-group topology is a narrow governance exception only.** A two-group (Prod-only + shared NonProd/DR) or multi-group topology is used **only** when Azure Quota Group limits or a mandatory Prod-isolation governance boundary make a single pool impossible. Each such exception is recorded in the Decision Log with the specific limit/boundary that forced it, and reverts to the single pool when the constraint is lifted. This is the configured implementation of the "unless Azure limits or governance boundaries require separation" clause in QUA-004, not a competing default design. `[Decided]`

5. **Consumer quota validation is mandatory and POC-gated.** Until POC-001 and authoritative Azure guidance prove otherwise, ACRME assumes the deploying/consumer subscription must hold sufficient quota even when consuming a provider-owned shared reservation. `[Assumed]`

6. **DR quota is sized by distributed DR demand.** DR floor accounting uses the ADR-003 max-not-sum formula, not a fixed percentage of production. `[Decided]`

## Managed Scope and Capacity Controls

ACRME modifies only resources declared in the approved scope file. The scope includes tenant/management scope, subscription, region, zone, resource group, CRG, reservation, SKU/family, environment, buffer policy, enabled state, effective date, and policy version. `[Decided]`

Capacity controls:

```text
Target Reserved Capacity = Allocated VM Count + Configured Buffer
```

`Allocated VM Count` means running/allocated demand. Associated-but-deallocated VMs are reported separately and do not automatically preserve paid reservation quantity. `[Decided]`

Azure resource creation must precede config activation: create/update the Azure CRG/reservation first, validate it, then activate deployment configuration that references it. `[Decided]`

Normal reconciliation never deletes CRGs or reservation definitions. **Decommissioning-workflow boundary (CAP-008/CAP-010).** Automatic reconciliation only ever **right-sizes a reservation down to its `Allocated + Buffer` floor** — it never reduces a reservation to zero and never deletes a CRG or reservation on its own. Reducing an unused managed reservation to **zero (returning it to a `seed`)**, and any subsequent **retirement or deletion**, are **gated actions in the approved decommissioning workflow** (operator approval, cost/DR/maintenance guards, immutable audit), not part of the automatic loop. `[Decided]`

## Capacity Reservation Model (v2.4)

This section records the reservation-model decisions folded in for Baseline v2.4. They refine, and are consistent with, the single-pool quota decision above.

**Reservation eligibility (CAP-020/CAP-021).** Only **zonal, non-Availability-Set** VMs are eligible for the zonal on-demand capacity reservations ACRME manages. **Availability-Set VMs are ineligible** (**CAP-020**) — an Availability Set and a zonal capacity reservation are mutually exclusive Azure placement constructs, so such VMs are rejected from the zonal reservation path. A VM that is not already zone-pinned must first satisfy the **deallocate/redeploy-to-AZ precondition** (**CAP-021**): it is deallocated and redeployed into a target availability zone through the governed onboarding/migration workflow before it can be associated with a per-AZ reservation. `[Decided]`

**Seed matrix + product-team budget governance (CAP-022, extends CAP-009).** The managed estate is initialised as a **seed matrix**: a **count-0 (`seed`) reservation for every eligible SKU × region × availability-zone combination** in scope. Seeds hold no paid capacity but make every eligible placement target pre-modelled, so a scale-up is a right-size of an existing seed rather than a create-from-nothing. The breadth of the seed matrix and the capacity any team may draw from it are bounded by **per-product-team budget governance** recorded in the scope file. `[Decided]`

**Reactive SKU/AZ discovery reconciled with governance (CAP-024, reconciles CAP-019).** When a VM is observed for a SKU×region×AZ combination not yet in the seed matrix, ACRME **reactively auto-creates** the backing reservation so live workloads are protected, and **simultaneously raises a scope-file governance item** so the newly discovered combination is brought under explicit, budgeted governance (CAP-019). Discovery therefore never bypasses governance — it creates capacity and a governance action in the same step. `[Decided]`

**Regional + per-AZ CRG structure (CAP-023, extends CAP-011).** Reservations are organised, per environment (Prod, NonProd/CVAL, DR-standby) and per region, into **one regional CRG plus one CRG per availability zone**. The regional CRG anchors region-scoped (non-zone-pinned) reservations and governance; the per-AZ CRGs hold the zonal seed matrix and zone-pinned reservations. Naming follows OPS-006 (e.g. `crg-pr-eus2-reg`, `crg-pr-eus2-az1/az2/az3`). `[Decided]`

**Even per-zone distribution + rebalancing (PLC-011).** Within a placement region ACRME drives the per-zone VM distribution toward an **even target of ≈1/zone_count per zone** (≈33% for a three-zone region), selecting the eligible zone with the greatest deficit at placement time and raising a **rebalancing action** when the observed distribution drifts beyond the configurable tolerance band. Target and tolerance are configuration-driven (**C-13**); the algorithm and worked example are in the TDD Section 8.5 and Baseline Appendix A.9. `[Decided]`

**Core subscription classification (CAP-001a).** A shared **core subscription is classified entirely as production** for capacity, buffer, and protection purposes — every reservation it holds is governed under production rules regardless of the individual workload's label. `[Decided]`

**Naming convention + counter (OPS-006, C-12).** Resource groups, CRGs, and subscriptions follow a deterministic naming convention with an incrementing counter — e.g. RG `rg-odcr-<env>-<region>-<NN>` (`rg-odcr-prod-eus2-01`), subscription `sub-<org>-<domain>-<purpose>-<NN>` (`sub-jda-cld-core-01`), CRG per the CAP-023 examples. The pattern is configuration-driven (**C-12**) so it can be adjusted without code change. `[Decided]`

## Quota Pooling and Allocation

| Control | Decision |
|---|---|
| Inventory | Maintain subscription, region, VM/quota family, assigned quota, used quota, available quota, pooled quota, and pending increase records. |
| Pooling | Eligible subscriptions contribute unused regional VM-family quota to the governed pool when policy permits. |
| Allocation | Allocate quota to target subscriptions for deployment demand, production buffer, and approved DR need. |
| Reclamation | Reclaim quota only when it will not drop a subscription below current usage, committed demand, production buffer, or approved DR need. |
| Audit | Log all allocation, reclamation, request, approval, rejection, and failure events with before/after values and correlation IDs. |

Production subscriptions maintain configurable quota headroom above current usage to support growth and the next approved deployment. `[Decided]`

## DR Floor Accounting

DR floor is destination-, SKU-, zone-, and policy-scoped:

```text
Destination_DR_Requirement(d, sku, zone)
  = MAX over non-concurrent source regions s protected by destination d (
      Workload_Portion(s -> d, sku, zone)
    )
```

```text
DR_Floor_vCPU(d, sku, zone)
  = Destination_DR_Requirement(d, sku, zone) * vCPU_Per_Instance(sku)
```

`MAX` is valid only because the baseline assumes a single failed source region at a time. A configured `SUM` basis is available where a customer contract or geography requires simultaneous source-region failure coverage. `[Decided]`

### Single-pool accounting (primary model)

In the single governed pool, Prod, NonProd/CVAL, and DR draw from one `Pool_Limit`. ACRME protects Prod and DR **inside** the shared balance using logical earmarks rather than physical groups:

```text
Pool_Headroom            = Pool_Limit - Pool_Used
Prod_Reserved_Floor      = Prod_Used_vCPU + Prod_Growth_Buffer_vCPU
DR_Earmark_vCPU          = SUM over destinations d in scope ( DR_Floor_vCPU(d, sku, zone) )
Allocatable_NonProd      = Pool_Limit - Prod_Reserved_Floor - DR_Earmark_vCPU - NonProd_Used_vCPU
Emergency_DR_Available   = Pool_Headroom + reclaimable NonProd above committed demand
```

- `Prod_Reserved_Floor` is never allocatable to NonProd; NonProd allocation stops at `Allocatable_NonProd` reaching zero (fail-safe). `[Decided]`
- `DR_Earmark_vCPU` reserves the max-not-sum DR requirement inside the pool so live NonProd usage cannot consume the standby-activation headroom (see ADR-003 CVAL/DR double-count guard). `[Decided]`
- During a declared DR event the DR orchestrator may draw `Emergency_DR_Available` — pool headroom first, then reclaimable NonProd above committed demand — because all three environments share one pool, no cross-group transfer is required. This is the flexibility gain that motivates the single-pool model. `[Decided]`

### Two-group accounting (exception topology only)

Where the QUA-004 exception applies (Azure limit / mandatory Prod isolation), ACRME falls back to per-group accounting:

```text
Effective_NonProd_Ceiling = NonProd_DR_Group_Limit - DR_Floor_vCPU
NonProd_Headroom          = Effective_NonProd_Ceiling - NonProd_Used_vCPU
Group_Headroom            = Group_Limit - Group_Used
```

These are engine accounting controls in both models. They do not create a native Azure sub-reservation unless Azure later provides and ACRME validates that capability. `[Assumed]`

## Readiness and Enforcement

For every managed deployment, ACRME validates:

- target region/geography policy is approved;
- zone and SKU are supported;
- reservation exists when required;
- reservation SKU, region, zone, and sharing authorization match;
- sufficient reserved capacity exists or over-allocation is explicitly approved;
- consumer/deploying subscription quota is sufficient;
- quota and reservation state are fresh enough;
- no policy, exception, or maintenance block is active. `[Decided]`

Quota and capacity readiness states are defined in ADR-001. Reserved capacity greater than deployable quota must produce `READY_WITH_RISK` or `QUOTA_DEFICIT` depending on policy; it must not be reported as fully ready. `[Decided]`

## Quota Group Preview Dependency

Azure Quota Groups and `groupType` semantics remain feature-maturity dependencies. ACRME must pin API versions, monitor version drift, and retain subscription-level quota checks until POC-001 and DEP-001 explicitly approve otherwise. `[Assumed]`

## Consequences

**Positive**

- Single governed pool maximises manipulation flexibility: all stranded default per-region quota is collected once and allocated where needed, improving utilisation and cutting the number of quota-increase requests to Microsoft (QUA-003/QUA-004). `[Decided]`
- Emergency DR draw needs no cross-group transfer — Prod, NonProd/CVAL, and DR share one balance — so declared-event capacity acquisition is faster and simpler. `[Derived]`
- Preserves production protection via logical earmarks (`Prod_Reserved_Floor`, `DR_Earmark_vCPU`) instead of physical group separation. `[Decided]`
- Treats quota as an auditable governance/cost control, not just a technical limit. `[Decided]`
- Avoids the old fixed 30-40% DR floor and aligns quota planning with distributed DR demand. `[Decided]`
- Makes capacity/quota readiness explicit for AEP/provisioning. `[Derived]`

**Negative / trade-offs**

- Single-pool topology requires strong engine controls (earmark enforcement, priority ordering, fail-safe stop) to prevent NonProd or DR from consuming Prod headroom; the protection is only as good as those controls. `[Derived]`
- The exception two-group topology reduces manipulation flexibility and remains dependent on POC evidence for quota-neutral transfers; it is used only when Azure limits or Prod-isolation governance force it. `[Assumed]`
- Consumer quota behavior under shared reservations remains a top technical unknown until POC-001 completes. `[Assumed]`
- Max-not-sum DR floor under-protects simultaneous source-region failures unless the SUM override is configured. `[Derived]`

## Alternatives Considered

| Alternative | Disposition |
|---|---|
| Fixed two-group model for every region | Rejected as the default; it fragments quota and multiplies quota-increase requests. Single governed pool is the primary model; two-group is a narrow governance exception. `[Decided]` |
| Single pool with no Prod guard | Rejected; quota remains a consumption governor and Prod protection is first priority — enforced by logical earmarks inside the shared pool. `[Decided]` |
| Three separate groups | Allowed only by exception; it can make emergency DR transfer non-atomic. `[Derived]` |
| DR floor as `prod * dr_ratio_max` | Rejected by requirements v2.1; replaced by max-over-non-concurrent-sources sizing. `[Decided]` |
| Provider quota as proof of consumer deployability | Rejected pending POC-001; validate consumer quota. `[Assumed]` |

---

## Appendix - ADR Summary

| ADR | Requirements Applied | Key Open Items |
|---|---|---|
| ADR-002 Quota and Capacity Management | CAP-001/001a, CAP-002..024, QUA-001..014, RDY-001..004, PLC-011, OPS-006 (C-12/C-13) | POC-001 consumer quota; POC-008 production quota buffer; POC-011 max-not-sum safety; DEP-001 feature maturity |

## Appendix - Status Legend

| Status | Meaning |
|---|---|
| **Proposed** | Under discussion; not yet ratified |
| **Accepted** | Ratified and in force |
| **Deprecated** | No longer recommended but not yet replaced |
| **Superseded** | Replaced by a later ADR |

## Appendix - Evidence Tag Taxonomy

| Tag | Meaning |
|---|---|
| `[Documented]` | Traceable to Azure platform behaviour or documentation |
| `[Decided]` | An explicit ACRME design choice recorded in this ADR set |
| `[Derived]` | A logical consequence of a documented constraint or decision |
| `[Assumed]` | Architectural judgement pending proof-of-concept validation |

## Related ADRs

- **ADR-001 - Region Selection and Customer Placement** (`acrme_adr_001_region_selection.md`)
- **ADR-003 - Capacity Management during Disaster Recovery (DR)** (`acrme_adr_003_capacity_management_during_dr.md`)
- **ADR-004 - Forecast, Reconciliation, and Increase of Capacity and Quota** (`acrme_adr_004_forecast_and_increase_of_capacity_and_quota.md`)

---

**Document Status:** Accepted  
**Next Review:** After POC-001, POC-008, POC-011, quota-group feature review, and first end-to-end quota allocation/reclamation evidence.
