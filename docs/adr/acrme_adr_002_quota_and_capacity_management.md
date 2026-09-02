**Project:** Azure Capacity Reservation Management Engine (ACRME)  
**Classification:** Principal Cloud Architect - Architecture Governance  
**Version:** 2.2  
**Date:** 2 September 2026  
**Status:** Accepted - supersedes ADR-002 v2.1 quota grouping content  
**Part of:** ACRME Architecture Decision Records - aligned to Capacity & Quota Management Requirements Baseline v2.2.

> **About ADRs.** An Architecture Decision Record captures a significant architectural decision, the context that forced it, the options considered, the choice made, and its consequences. This v2.2 ADR adopts the **single governed quota pool** as the primary model per QUA-004 and updates quota and capacity accounting to match Requirements Baseline v2.2. Evidence tags: `[Documented]`, `[Decided]`, `[Derived]`, `[Assumed]`.

---

# ADR-002 - Quota and Capacity Management

**Status:** Accepted  
**Date:** 27 August 2026  
**Deciders:** Principal Cloud Architect, Platform Engineering, FinOps, Quota Owner  
**Related requirements:** CAP-001..CAP-019, QUA-001..QUA-014, RDY-001..RDY-004, FIN-001..FIN-006, GOV-001..GOV-006  
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

Normal reconciliation never deletes CRGs or reservation definitions. Where Azure permits, an unused managed reservation is reduced to zero instead of being deleted; deletion is a separate approved decommissioning workflow. `[Decided]`

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
| ADR-002 Quota and Capacity Management | CAP-001..019, QUA-001..014, RDY-001..004 | POC-001 consumer quota; POC-008 production quota buffer; POC-011 max-not-sum safety; DEP-001 feature maturity |

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
