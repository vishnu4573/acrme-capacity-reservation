**Project:** Azure Capacity Reservation Management Engine (ACRME)  
**Classification:** Principal Cloud Architect - Architecture Governance  
**Version:** 1.0  
**Date:** 9 September 2026  
**Status:** Accepted  
**Part of:** ACRME Architecture Decision Records - aligned to Capacity & Quota Management Requirements Baseline v2.4.

> **About ADRs.** An Architecture Decision Record captures a significant architectural decision, the context that forced it, the options considered, the choice made, and its consequences. This ADR clarifies the **enforcement boundary** between quota-as-governor and capacity reservation, correcting a common over-generalization about their relationship to deployment strategy. Evidence tags: `[Documented]`, `[Decided]`, `[Derived]`, `[Assumed]`.

---

# ADR-006 - Quota and Reservation Enforcement Boundary

**Status:** Accepted  
**Date:** 9 September 2026  
**Deciders:** Principal Cloud Architect, Platform Engineering  
**Related requirements:** QUA-001, QUA-002, QUA-005, QUA-006, QUA-007, QUA-013, CAP-003, CAP-016, CAP-017, ENV-002  
**Related constraints:** Design Principle 2 (quota and capacity are separate resources)

## Context

A fundamental question arose during deployment-architecture review: **Should the quota-as-governor principle restrict deployment strategy (subscription topology), or should it operate only at the capacity definition/allocation layer?**

The baseline establishes that quota and capacity reservations are **parallel, independent control planes** (Design Principle 2, QUA-001): *"Manage quota as a separate control plane from reservations. A reservation is not proof that deployment quota exists — you can hold a reservation and still fail to deploy without quota."*

However, the relationship between these two control planes and their respective roles in *restricting deployments* was not explicitly bounded. Two over-generalizations needed correction:

1. **Misreading quota-as-governor as a bespoke ACRME deployment gate** — when in fact Azure enforces quota natively at the ARM layer, and ACRME only *validates* quota state for readiness.
2. **Assuming CR/CRG universally restricts deployment** — when in fact reservation enforcement is **mandatory only for production** (CAP-017) and **configurable for non-production** (ENV-002) to avoid blocking cost-driven deallocation.

The user's insight was directionally correct: *"Quota and CR/CRG are parallels — they have dependency at a different layer but both should not have deployment restrictions."* This ADR formalizes that principle with one precision: quota **inherently** restricts deployment (because Azure does), but ACRME does not re-gate it. `[Derived]`

## Decision

**Quota governs the definition and allocation of capacity; CR/CRG governs the guarantee of capacity. Their sole coupling is pre-deploy readiness validation, not dual enforcement.**

### 1. Quota's proper scope: Definition and allocation layer (QUA-005, QUA-006, QUA-008, QUA-009)

Quota-as-governor operates at the **budget/sizing/capping layer**:
- **How much** reservation may be sized per SKU × region × environment (feeds CAP-003 `allocated + buffer` formula)
- **Who** may consume capacity (per-product, per-environment, per-subscription caps)
- **Production growth buffer** (QUA-006) — dedicated headroom above current usage
- **Dynamic allocation and reclamation** from the central pool (QUA-008/QUA-009)
- **Budget governance** for the seed matrix (CAP-022 — SKU/AZ entry requires owning product team + approved budget line)

Quota is a **budget and allocation lever**, not a runtime traffic cop. `[Decided]`

### 2. Quota's deploy-time effect is Azure-native validation only (QUA-007, CAP-016)

Quota **is inherently a deploy-time hard limit**, but not because ACRME makes it one — **Azure enforces quota at the ARM layer natively**. If a VM-create call exceeds the subscription's regional family quota, Azure rejects it. There is no ACRME design choice that can make quota "non-restrictive" at deploy time.

What ACRME **does not do**: build a redundant second quota gate on top of Azure's enforcement.

What ACRME **does do**: validate quota state for **readiness** before deployment (QUA-007, CAP-016):
- **QUA-007:** For each managed scope, validate `Required Deployment Quota ≤ Available Quota in Deploying Subscription`. Surface `reserved capacity > deployable quota` as a readiness **risk** (reservation without quota cannot deploy).
- **CAP-016:** Pre-deploy validation checks include *"required quota available in the deploying subscription"* (among reservation exists, SKU/region/zone match, consumer authorization).

This is a **fail-fast safety check**, not a second independent throttle. ACRME reads quota state and warns; Azure enforces it. `[Decided]`

**Consequence:** Quota state naturally influences deployment strategy (subscription topology) because **quota lives at the subscription × region × family level** (QUA-002, QUA-013) — you cannot sub-divide quota below the subscription. A single-subscription model collapses per-environment quota governance (see deployment-layout reference §"Drawbacks of single-subscription model"). But that is a **design trade-off driven by Azure's quota scoping**, not ACRME imposing a deployment restriction. `[Derived]`

### 3. CR/CRG governs the guarantee — mandatory only where declared (CAP-017, ENV-002)

Capacity Reservations are **guarantees, not native gates**. Azure permits on-demand VM deployment without a reservation if capacity happens to exist. The reservation layer becomes a deployment restriction **only because ACRME deliberately chooses to make it mandatory for production** (CAP-017):

> **CAP-017 — Deployment failure policy.** If reservation enforcement is mandatory and validation fails, the deployment **fails safely** with a clear reason … No silent deployment without the required reservation unless an approved break-glass policy is invoked.

Crucially, that choice is **not universal**:

> **ENV-002 — Production-only initial enforcement.** Mandatory reservations apply to **production** first. Non-production reservation enforcement stays **configurable** because non-prod VMs may be deallocated for cost savings … The design must avoid a state where non-prod reservations block cost-driven deallocation.

So the reservation layer already behaves the correct way:
- **Hard gate where the business demands a guarantee** (production)
- **Configurable elsewhere** (non-prod can opt out to allow cost-driven deallocation)

`[Decided]`

### 4. The single coupling point: Pre-deploy readiness validation (CAP-016 + QUA-007)

The only place quota and CR/CRG touch is the **pre-deploy readiness check**:

**CAP-016 — Reservation integrity validation (pre-deploy):** Before deploying against a reservation, validate:
- Reservation exists
- SKU matches
- Region matches
- Zone matches
- Consumer subscription authorized (if shared)
- Sufficient reserved capacity or approved over-allocation
- **Required quota available in the deploying subscription** ← the quota/reservation seam

This is a **validation layer**, not dual enforcement. Both resources are independently defined; the check confirms they are aligned before committing a deployment. `[Decided]`

## Restated Principle

> **Quota governs the *definition and allocation* of capacity — how much reservation may be sized and consumed per SKU × region × environment.** Its deploy-time effect is Azure's own native hard limit, which ACRME only *validates for readiness*, never re-gates.
>
> **CR/CRG governs the *guarantee* of capacity.** It is a deployment gate **only where reservation enforcement is declared mandatory** (production, CAP-017); elsewhere it is configurable (ENV-002) and imposes no deployment restriction.
>
> The two are **parallel control planes**; their sole coupling is the **pre-deploy readiness validation** (CAP-016 + QUA-007), which is a fail-fast safety check, **not** a second independent throttle.

`[Decided]`

## Consequences

### Positive
- **Clarifies the division of responsibility:** quota = budget/allocation, CR/CRG = guarantee, validation = the seam.
- **Prevents redundant quota enforcement in ACRME** — Azure already does it; ACRME only reads quota state for readiness warnings.
- **Preserves non-prod flexibility** — ENV-002 keeps reservation enforcement configurable so deallocations for cost savings are never blocked.
- **Correctly frames subscription topology as a quota-scoping trade-off**, not an arbitrary ACRME restriction.

### Risks
- **Quota's native hard limit can still surprise users** who misread "quota-as-governor" as "ACRME shouldn't enforce quota." Reality: ACRME doesn't; Azure does. The governor metaphor applies to *allocation policy*, not *whether quota exists as a deploy-time gate*.

### Deployment Strategy Implications
- **Subscription topology** is shaped by quota scoping (QUA-002: subscription × region × family) because that's where Azure draws the boundary. Single-subscription-per-region collapses per-environment quota isolation — a **design trade-off**, not an ACRME deployment restriction.
- **The critical boundary to preserve:** Prod on its own subscription (CAP-001a — core subscription is all-production) so quota-as-governor and Prod isolation (ENV-003) both hold structurally.

## Alternatives Considered

| Alternative | Outcome | Reason Rejected |
|---|---|---|
| **Re-implement quota enforcement in ACRME** | ACRME becomes a second quota gate on top of Azure's native ARM enforcement | Redundant, adds latency, creates drift risk between ACRME state and Azure reality |
| **Make all reservation enforcement mandatory (no ENV-002 opt-out)** | Non-prod reservations block cost-driven deallocations | Violates baseline requirement ENV-002; non-prod must remain flexible for cost savings |
| **Treat quota validation as optional** | Deployments proceed without checking quota availability first | Violates fail-fast principle; leads to late-stage deployment failures at ARM layer |

None of these were viable. The chosen boundary (quota = allocation-layer governor + Azure-native enforcement, CR/CRG = configurable guarantee, validation = seam) is the only model that satisfies the baseline requirements and Azure's native behavior. `[Decided]`

## Related Documents

- `acrme_requirements_baseline_v2_4.md` — QUA-001..QUA-013 (quota management), CAP-001..CAP-024 (capacity reservation), ENV-002 (configurable non-prod enforcement), Design Principle 2
- `adrme_adr_002_quota_management.md` — two-group quota model (provider/consumer pool)
- `acrme_cr_crg_deployment_layout.md` — subscription topology trade-offs (§5 "Drawbacks of single-subscription model")
- `acrme_technical_design_document.md` — service contracts for quota validation and reservation readiness checks

---

*End of ADR-006.*
