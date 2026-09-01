**Project:** Azure Capacity Reservation Management Engine (ACRME)  
**Classification:** Principal Cloud Architect - Architecture Governance  
**Version:** 2.1  
**Date:** 27 August 2026  
**Status:** Accepted - supersedes ADR-002 v1.2 quota and DR-floor content  
**Part of:** ACRME Architecture Decision Records - aligned to Capacity & Quota Management Requirements v2.1.

> **About ADRs.** An Architecture Decision Record captures a significant architectural decision, the context that forced it, the options considered, the choice made, and its consequences. This v2.1 ADR updates quota and capacity accounting to match the consolidated requirements baseline. Evidence tags: `[Documented]`, `[Decided]`, `[Derived]`, `[Assumed]`.

---

# ADR-002 - Quota and Capacity Management

**Status:** Accepted  
**Date:** 27 August 2026  
**Deciders:** Principal Cloud Architect, Platform Engineering, FinOps, Quota Owner  
**Related requirements:** CAP-001..CAP-019, QUA-001..QUA-014, RDY-001..RDY-004, FIN-001..FIN-006, GOV-001..GOV-006  
**Related POCs:** POC-001, POC-002, POC-003, POC-008, POC-011, DEP-001

## Context

Capacity reservations and VM-family quota are independent Azure control-plane resources. ACRME must validate both before deployment because a reservation without deployable consumer-subscription quota can still fail, and quota without reserved capacity does not guarantee physical capacity. `[Documented]`

Requirements v2.1 also changes quota from a passive limit to a governed resource pool. Quota is deliberately used as a cost and consumption governor: teams must justify quota increases, and unused regional quota can be pooled and reallocated only under policy. `[Decided]`

The earlier two-quota-group model protected Prod from NonProd consumption but conflicts with the v2.1 preference for one governed pool per regional/quota-family scope unless governance boundaries require separation. This ADR resolves the tension by making the grouping model configuration-driven: one governed pool is the preferred baseline; a two-group topology is allowed where Prod isolation or Azure limits require it. `[Decided]`

## Decision

Adopt a **separate-but-correlated capacity and quota control plane**:

1. **Capacity and quota are separate domains.** ACRME maintains reservation state and quota state independently but correlates them by subscription, region, zone, VM/quota family, SKU, environment, product, and intended demand. `[Decided]`

2. **Quota is a consumption governor.** Unallocated pooled quota is not a reason to increase a subscription automatically. Every increase records owner, workload, region, SKU/family, amount, existing usage, target date, and business justification. `[Decided]`

3. **One governed quota pool is preferred.** Where Azure limits and governance allow, Prod, NonProd/CVAL, and DR share one governed pool per region and quota family to maximise operational flexibility. `[Decided]`

4. **Two groups remain an approved governance exception.** If Prod isolation cannot be safely enforced inside one pool, ACRME may use a Prod-only group plus a shared NonProd/DR group. This is the configured implementation of the "unless governance boundaries require separation" clause in QUA-004, not a competing untracked design. `[Decided]`

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

For a two-group topology:

```text
Effective_NonProd_Ceiling = NonProd_DR_Group_Limit - DR_Floor_vCPU
NonProd_Headroom          = Effective_NonProd_Ceiling - NonProd_Used_vCPU
Group_Headroom            = Group_Limit - Group_Used
```

These are engine accounting controls. They do not create a native Azure sub-reservation unless Azure later provides and ACRME validates that capability. `[Assumed]`

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

- Preserves production protection while aligning with v2.1's one-pool preference. `[Decided]`
- Treats quota as an auditable governance/cost control, not just a technical limit. `[Decided]`
- Avoids the old fixed 30-40% DR floor and aligns quota planning with distributed DR demand. `[Decided]`
- Makes capacity/quota readiness explicit for AEP/provisioning. `[Derived]`

**Negative / trade-offs**

- One-pool topology requires strong engine controls to prevent NonProd or DR from consuming Prod headroom. `[Derived]`
- Two-group topology reduces manipulation flexibility and remains dependent on POC evidence for quota-neutral transfers. `[Assumed]`
- Consumer quota behavior under shared reservations remains a top technical unknown until POC-001 completes. `[Assumed]`
- Max-not-sum DR floor under-protects simultaneous source-region failures unless the SUM override is configured. `[Derived]`

## Alternatives Considered

| Alternative | Disposition |
|---|---|
| Fixed two-group model for every region | Replaced by configuration-driven grouping; use only when governance isolation requires it. `[Decided]` |
| Single pool with no Prod guard | Rejected; quota remains a consumption governor and Prod protection is first priority. `[Decided]` |
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
