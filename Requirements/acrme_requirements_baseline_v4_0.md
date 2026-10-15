# Azure Capacity & Quota Management — Consolidated Requirements Baseline

> **Working document — coauthored baseline for the SaaS Design Services
> capacity & DR programme.** This is a living requirements document. It
> captures the agreed architectural direction while explicitly
> separating confirmed baseline requirements from items that remain
> configurable, need proof-of-concept (POC) validation, await a business
> decision, or depend on an external Azure capability.

## Document Control

| Field                   | Value                                                                                                                             |
|-------------------------|-----------------------------------------------------------------------------------------------------------------------------------|
| **Title**               | Azure Capacity & Quota Management — Consolidated Requirements Baseline                                                            |
| **Version**             | **4.0 — unified clean-slate rewrite (harmonises all v2.x carried-forward text with the v3.0 multi-domain customer model; unified formula reference; removes legacy single-scope ambiguity)** |
| **Status**              | Working baseline — single self-consistent voice; no legacy amendment layers           |
| **Baseline date**       | 14 October 2026 (supersedes v3.0 / 8 Oct 2026)                                                                            |
| **Owners**              | Vishnuvardhan Reddy (design/requirements), Roy Szabady (strategy/business alignment)                                              |
| **Contributors**        | Azure Platform Support (Anu — deployment pipeline), Jason (quota tooling/code), Melvin Stephen (CVP — quota-as-governor strategy) |
| **Primary consumers**   | Exosphere, Stratosphere, AEP, product platform teams, operations, FinOps, security & governance                                   |
| **Collaboration space** | Atlassian Confluence (space: **PI**, folder *Azure Capacity Reservation*) — chosen as the shared coauthoring workspace            |
| **Source baseline**     | v3.0 requirements baseline (8 Oct 2026); all prior versions (v1.0–v2.5) folded in and reconciled                  |

### Version History

| Version | Date           | Change                                                                                                                                                                                                                                                                                                                                             |
|---------|----------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **4.0** | **14 Oct 2026** | **Clean-slate rewrite.** All v2.x carried-forward requirements rewritten in unified v3.0/multi-domain vocabulary. Redundancies removed: PLC-006 retired (subsumed by PLC-013); PLC-004/PLC-009 amended to reference domain groups and PLC-015 pipeline; PLC-003 seed-record fields updated with CRV/DPB/domain token; PLC-007/008 explicitly state customer-aggregate scope; PLC-011 amended with per-domain scope note (PLC-016); DR-002/003/004/018 re-scoped with domain qualifier; CAP-023 reconciled with CAP-025; FIN-001/004 include domain dimension; A.1–A.9 reconciled with A.12 in unified Formulas & Calculation Reference section. No requirement content added or removed — only harmonised. Hard Constraints unchanged (HC-1..HC-11). |
| 3.0 | 8 Oct 2026 | Multi-domain customer model folded in. Domain-group CRGs per environment & region; two-scope region selection (CRV customer-scoped, DPB domain-scoped); DR Foundation; forward-items evaluation. Added PLC-013..016, DOM-001..004, CAP-025, DR-021, QUA-015, C-14/C-15/C-16. Carried-forward requirements verbatim from v2.5; only Section 11 and dependent sections amended. |
| 2.5     | 24 Sep 2026    | Foundation aligned to Microsoft Learn. Sharing stays Preview; QUA-013 documented; two-cap quota model; CAP-023 zonal CRG structure; CAP-016 logical zone numbers per subscription. |
| 2.5 (amended) | 7 Oct 2026 | γ fairness denominator defined — PLC-012 geography customer count. |
| 2.4 (amended) | 11 Sep 2026 | Middle East DR offering resolved — cross-geography DR to Europe. DEC-001 decided. Added DR-020, PLC-010b. |
| 2.4     | 7 Sep 2026     | Reservation-model gaps folded in. Added CAP-020..024, PLC-011, OPS-006, C-12/C-13. |
| 2.3     | 7 Sep 2026     | Region scope expanded to five geographies. PLC-010a generalised to all two-region geographies. |
| 2.2     | 27 Aug 2026    | EU cross-geo DR region corrected to Switzerland North. |
| 2.1     | 27 Aug 2026    | Reciprocal multi-source DR hosting, non-concurrent max-sizing, DR index, standby activation, CVAL/DR co-location. |
| 2.0     | 27 Aug 2026    | Pivot to minimal bootstrap + dynamic reconciliation; separated capacity vs quota; distributed DR; seed-record model. |
| 1.0     | 22–26 Aug 2026 | Initial capacity reservation design flow. |

---

## Table of Contents

1.  Purpose & Business Context
2.  Strategic Drivers & Constraints
3.  Design Principles
4.  Terminology
5.  Scope
6.  Region Strategy & Classification
7.  Environment Policy Requirements (ENV-001..007)
8.  Capacity Reservation Management Requirements (CAP-001..025)
9.  Quota Management Requirements (QUA-001..015)
10. Combined Capacity & Quota Readiness (RDY-001..004)
11. Region Selection & Customer Placement (PLC-001..005, PLC-007..016)
12. Domain Group Model (DOM-001..004)
13. Disaster Recovery Capacity Requirements (DR-001..021)

    - 13A. Distributed DR Reference Model

14. Cost Economics & FinOps Requirements (FIN-001..008)
15. Provisioning & AEP Integration (INT-001..008)
16. State & Data Requirements (DAT-001..006)
17. Observability & Alerting (OBS-001..005)
18. Governance, Security & Compliance (GOV-001..009)
19. Reliability & Non-Functional Requirements (NFR-001..010)
20. Operational Requirements (OPS-001..006)
21. **Formulas & Calculation Reference** *(unified)*

    - 21.1 Capacity Sizing Formulas (F.1–F.3)
    - 21.2 Quota Formulas (F.4–F.5)
    - 21.3 DR Sizing Formulas (F.6–F.8)
    - 21.4 Zone Distribution Formulas (F.9)
    - 21.5 Placement Scoring Formulas (F.10)
    - 21.6 Two-Scope Region Selection — CRV (F.11)
    - 21.7 Domain Placement Binding — DPB (F.12)
    - 21.8 Formula Reconciliation Note

22. Acceptance Criteria
23. Delivery Phases
24. Configurable Items Register (C-1..C-16)
25. Pending Decisions & Mandatory POCs
26. Assumptions, Constraints & Risks
27. Final Requirement Summary
28. Forward-Items Impact Evaluation
29. Appendix A — Worked Cost Examples
30. Appendix B — Requirement Status Labels
31. Appendix C — DR Sizing Formula Correction (Max vs Sum)

---

## 1. Purpose & Business Context

This document defines the functional, operational, governance, security,
observability, cost, and non-functional requirements for managing
**Azure VM capacity reservations** and **regional VM quota** across the
platform estate.

The target solution is a **Capacity & Quota Management Engine** that:

-   protects production deployment capacity as the first priority;
-   provides a **configurable bootstrap** position for disaster recovery
    instead of a fixed large reserve;
-   **dynamically reconciles** reserved capacity against actual running
    (allocated) demand;
-   **pools and allocates** regional quota across hundreds of
    subscriptions;
-   supports **distributed DR** across multiple regions in a geography;
-   supplies **fresh capacity state** to the region-selection and AEP
    provisioning workflows;
-   minimises idle reservation cost without weakening required
    production and DR controls;
-   treats each customer as **one placement identity with many capacity
    lanes** — region selection is bound once per customer (Customer
    Region Vector, CRV), while Instance Groups and capacity are
    domain-group-scoped (Domain Placement Binding, DPB); and
-   produces auditable evidence for operations and compliance (e.g., SOC
    2 DR assertions).

**Why this document exists.** The prior write-up was a *design flow*,
not a *requirements document*. Because business direction changes
frequently — regions, DR scope, and customer commitments shift regularly
— the team agreed to maintain a **working requirements document** as the
authoritative reference that the capacity engine is built against,
evolving it as decisions firm up.

**v4.0 — clean-slate rationale.** v3.0 folded the multi-domain customer
model into the baseline but carried v2.x requirements verbatim, creating
redundancies (e.g., PLC-006 subsumed by PLC-013, formulas A.1–A.9
restated at different granularity in A.12, DR-002..004 written at customer
scope rather than domain scope). v4.0 rewrites every requirement in a
single, unified voice — no legacy amendment layers, no version-tagged
caveats — while preserving every requirement ID for traceability.

## 2. Strategic Drivers & Constraints

These drivers shape every requirement below.

-   **Cost is a primary constraint.** Leadership is in a
    cost-reduction cycle; improving margins (and, ultimately, EBITDA
    ahead of an IPO) is an explicit organisational goal. Large idle DR
    reservations (estimated in the **millions of dollars per year**)
    will not receive business approval, so DR must start lean and scale
    on demand.
-   **Quota as a governor.** Per Melvin's strategy, **quota is used as a
    cost and consumption governor** — it caps how much capacity a team
    can consume. Production maintains a quota buffer to support growth;
    DR quota strategy must align to the capacity-sharing model.
-   **Business volatility.** Requirements evolve continually (region
    scope has both narrowed and re-expanded over time — e.g., Japan East
    is currently pending confirmation, while Australia and Asia Pacific
    are now back in scope; DHL-dedicated and Apple lost). The design must
    be **flexible and configuration-driven** rather than optimised for a
    single fixed scenario — the in-scope region catalogue (Section 6) is
    a configurable item (REG-001).
-   **Legal ownership of Middle East — DR now offered cross-geo (DEC-001
    resolved).** Legal has taken charge of the Middle East programme.
    Following legal/business direction, **DR is now offered for Middle
    East via a cross-geography model**: Prod and CVAL are provisioned in
    a selected **Middle East** Standard region and **DR is placed in a
    selected Europe Standard region**, both chosen by the weighted
    capacity placement model (DR-020, PLC-010b). Data-sovereignty
    constraints remain material — the per-country/region
    `DR_NOT_OFFERED` flag (DR-014) remains available where legal still
    prevents an acceptable DR design.
-   **Region strategy (current).** Five geographies are in scope — **US,
    Europe, Australia, Asia Pacific, and Middle East** (Section 6). US
    runs a three-region distribution model; Europe, Australia, and Asia
    Pacific run a two-region (CVAL/DR co-located) model; **Middle East
    runs a cross-geography DR model** (Prod+CVAL local in Middle East,
    DR in Europe — DR-020, PLC-010b). The catalogue is
    configuration-driven and expected to keep changing.
-   **Multi-domain customer model.** A customer may own multiple
    **domain groups** (e.g., TMS, WMS). Region selection is customer-scoped
    (one CRV per customer × geography, reused by all domains). Capacity
    and instance groups are domain-scoped (one DPB per domain × environment
    × region). This two-scope separation is the structural core of the
    engine's placement pipeline.
-   **No multi-cloud.** Multi-cloud DR has been repeatedly rejected at
    the ELT level; "all of Azure down" is explicitly out of scope.
-   **Preview-feature dependency.** **Capacity Reservation Sharing**
    is a preview feature. Production placement does not depend on it.
    Until sharing is generally available for the API version in use, a
    production VM is placed on a reservation in the **deploying
    subscription** (CAP-013, DEP-001).

## 3. Design Principles

1.  **Production protection first.** Prioritise production availability
    and the *next* approved production deployment above all else.
2.  **Quota and capacity are separate resources.** Manage them
    independently, but validate their relationship before any
    deployment.
3.  **Allocated demand drives reservations.** Reservation targets are
    computed from **allocated (running)** VMs plus a buffer — never from
    associated-but-deallocated VMs alone.
4.  **Buffers are configurable.** Production and DR buffer values are
    policy inputs, not hard-coded constants.
5.  **DR starts lean.** DR holds only the approved **bootstrap**
    capacity (enough to stand up control planes and begin recovery), not
    a fixed percentage copy of production.
6.  **CVAL is a DR capacity source.** On a declared disaster, CVAL
    capacity may be shut down, disassociated, or reassigned per the
    approved runbook.
7.  **Regional & zonal isolation.** Reservations and quota are region-
    and zone-bound; capacity in an unavailable region is not assumed
    reusable elsewhere.
8.  **Placement uses current state.** Region selection uses a recent,
    authoritative capacity/quota snapshot; stale state must not drive
    placement.
9.  **Cost is a first-class constraint.** Idle reservation spend is
    measured, attributable, reviewed, and tunable.
10. **Automation with guardrails.** Automated changes are scoped by
    approved configuration, validated before execution, logged, and
    reversible where Azure permits.
11. **Customer placement is seeded once.** The first approved
    production-region decision becomes the authoritative seed for all
    later domain groups and environments for that customer.
12. **Design for changing policy.** Geography scope, DR sizing,
    buffers, SKUs, regions, domain taxonomy, and environment rules are all
    configuration-driven.
13. **Two-scope separation.** Region selection is customer-scoped
    (CRV); capacity binding is domain-scoped (DPB). A domain never
    re-runs region selection; a customer-level region change occurs only
    via the approved migration/exception workflow.

## 4. Terminology

| Term                                 | Meaning in this document                                                                                   |
|--------------------------------------|------------------------------------------------------------------------------------------------------------|  
| **Allocated VM**                     | A running VM currently consuming compute capacity.                                                         |
| **Associated VM**                    | A VM linked to a Capacity Reservation Group, whether running or deallocated.                               |
| **Availability Set**                 | Legacy Azure fault-/update-domain VM grouping. **Mutually exclusive with Capacity Reservations** — Availability-Set VMs are ineligible for reservation management (CAP-020) and must be redeployed into an availability zone before onboarding (CAP-021). |
| **Available reserved capacity**      | Reserved capacity not currently consumed by allocated VMs.                                                 |
| **Buffer target**                    | Approved capacity held above current allocated demand for a defined scope.                                 |
| **Capacity Reservation Group (CRG)** | Azure construct holding reservations for one region. A group is either **zonal** (zones declared at creation, immutable; one reservation per VM size per zone) or **non-zonal** (Azure pins the group to one zone at first reservation; VMs deploy without a zone). The engine organises CRGs per domain × environment × region (CAP-025). |
| **Core subscription**                | A shared platform/"core" subscription whose VMs are **all classified production** for reservation and buffer purposes (CAP-001a); non-production workloads must not run there (ENV-003). |
| **Customer Region Vector (CRV)**     | Customer-scoped, cached region binding `(geography, distribution model, prod, cval, dr)` decided once per customer × geography and reused by **all** domain groups (PLC-013). |
| **CVAL**                             | Customer validation environment; its capacity may contribute to DR readiness.                              |
| **Domain group**                     | A workload-domain grouping of a customer's capacity (`wl-*` token, e.g. TMS, WMS) sharing one customer seed row but owning **separate instance groups** (ig) per environment/region (PLC-014, DOM-001/002). Domain is the unit of ig/capacity binding; the customer is the unit of region binding (PLC-013). |
| **Domain Placement Binding (DPB)**   | The deterministic per-domain capacity binding `DPB(D,E)` that resolves ig subscription, CRG set, CR sizing, zone distribution, and quota draw for one domain × environment × region, using the pre-bound CRV region (PLC-014). |
| **DR bootstrap capacity**            | Minimum deployed/reserved platform capacity required to initiate recovery orchestration.                   |
| **DR Foundation CRG set**            | The dedicated DR-bootstrap CRG set of a domain in its DR region — structural base capacity, always present with pre-staged quota; extendable on failover via the domain's own CVAL/DR shared CRG (CAP-025, DR-021). |
| **Instance group (ig)**              | The subscription-bound capacity set that materialises **one domain × environment × region**: its subscription(s), CRG set (CAP-025), and quota draw. ig is domain-group-scoped; the region of an ig always comes from the customer's CRV (PLC-014). |
| **Seed reservation**                 | A managed reservation created at reserved quantity **0** for an eligible SKU × region × availability zone, as part of the initial **seed matrix** (CAP-022); reconciliation scales it up from 0 when allocated demand first appears. *Distinct from the placement **seed record** below.* |
| **Seed matrix**                      | The full set of count-0 **seed reservations** across every eligible SKU/AZ combination in the scope file (CAP-022), governed by product-team budget approval. |
| **Consumer subscription**            | Subscription where a VM deploys and consumes a *shared* reservation owned elsewhere.                       |
| **Provider subscription**            | Subscription that owns a reservation shared with other subscriptions.                                      |
| **Quota pool / quota group**         | An Azure Quota Group moves unused quota onto a member subscription. Deploy-time checks that subscription's **VM-family** vCPU and **total regional** vCPU, not the group limit. One subscription belongs to one group; each transfer is scoped to one region and one VM family (QUA-003, QUA-004). All of a customer's domain ig subscriptions belong to a centrally managed quota group per region × VM-family cell (QUA-015). |
| **Quota hoarding**                   | Governance practice of collecting default per-region quota into a family pool for controlled reallocation. |
| **Seed record** (a.k.a. **placement seed**) | Authoritative customer record holding: customer/realm identifier, geography, distribution model, production region, CVAL region, DR region (or `NOT_OFFERED`), CRV vector (PLC-013), domain groups and their DPB references (PLC-014), products covered, decision timestamp, policy/engine version, capacity-snapshot reference, exception reference (if any), and approval metadata. *Distinct from a **seed reservation** — "seed record" is about **where** a customer is placed; "seed reservation" is a **zero-count reservation object** waiting to scale.* |
| **Total customers (geography)** | Count of distinct customers with at least one environment (Prod, CVAL or DR) provisioned or being deployed in any region of a geography. Denominator of the γ distribution-fairness term; one live count per geography, shared by all environments (PLC-012, F.10). |
| **SKU scope**                        | The SKU/VM-family × region × zone × subscription × environment combination managed by policy.              |
| **AEP**                              | The provisioning/automation entry point that triggers region selection and deployment. AEP deployments carry a domain group token (DOM-001) in addition to customer/realm, product, environment, and region inputs (INT-003/INT-008). |
| **Source region**                    | A production region whose workload fails over on outage.                                                   |
| **Destination (DR) region**          | A surviving region hosting standby DR instances for one or more source regions.                            |
| **Non-concurrent sources**           | Multiple source regions that (per DR-001) are assumed never to fail simultaneously.                        |

## 5. Scope

### 5.1 In Scope

-   Azure VM Capacity Reservations and Capacity Reservation Groups.
-   Regional and VM-family quota inventory, pooling, allocation,
    reclamation, and monitoring.
-   Production, CVAL, and DR compute-capacity policies.
-   Cross-subscription capacity reservation **sharing** where supported
    and approved.
-   Capacity/quota state consumed by region selection and AEP
    provisioning.
-   Multi-domain customer model: customer-scoped region selection (CRV)
    and domain-scoped capacity binding (DPB).
-   Automated reservation reconciliation.
-   Cost, compliance, and operational evidence.
-   Alerting, dashboards, audit records, and exception workflows.
-   Capacity rebalancing for new deployments, growth, shutdowns, and DR
    exercises.

### 5.2 Out of Scope (this baseline)

-   Application-level data replication / failover implementation.
-   Database and non-VM PaaS capacity mechanisms.
-   Multi-cloud disaster recovery.
-   Full AEP redesign beyond the required integration contracts.
-   Per-country legal exceptions *within* Middle East that may still
    warrant `DR_NOT_OFFERED` (DR-014) despite the geography-level
    cross-geo DR offering now in scope.
-   Permanent R&D reservations (short-lived POC reservations may be
    supported).
-   "Entire Azure region-set / global Azure outage" as an addressable
    failure mode.

## 6. Region Strategy & Classification

The estate is organised into two capacity classes across the in-scope
regions. Five geographies are in scope: **US, Europe, Australia, Asia
Pacific, and Middle East**. **US** operates a **three-region
distribution model**; **Europe, Australia, and Asia Pacific** operate a
**two-region distribution model** (see REG-003 and the ENV-003 CVAL/DR
co-location mechanism). **Middle East** uses a **cross-geography DR
model** (DR-020, PLC-010b) — Prod and CVAL in a selected Middle East
Standard region and **DR in a selected Europe Standard region**.

| Class                             | Behaviour                                                                                   | Notes                                                          |
|-----------------------------------|---------------------------------------------------------------------------------------------|----------------------------------------------------------------|
| **Standard capacity regions**     | Eligible for automatic selection by the placement/region-selection engine.                  | Default provisioning targets for production, CVAL, and DR.     |
| **Restricted deployment regions** | Production-only; **not** auto-selected unless explicitly provided as the production region. | Used only when a customer/contract specifies the exact region. |

### In-Scope Region Catalogue (configurable — see REG-001)

| Geography         | Distribution model | Standard capacity regions (engine-selectable) | Restricted regions (exception only)      | Notes                                                                                   |
|-------------------|--------------------|-----------------------------------------------|------------------------------------------|-----------------------------------------------------------------------------------------|
| **US**            | 3-region           | West US 3 · Central US · Canada Central        | East US 2 *(exception required)*         | Only geography with full Prod / CVAL / DR region separation.                              |
| **Europe**        | 2-region           | Switzerland North · Sweden Central             | North Europe · West Europe *(exception)* | Also serves as the **cross-geo DR destination geography for Middle East** (DR-020); the specific Europe DR region is weighted-selected, not fixed (REG-002). |
| **Australia**     | 2-region           | Australia East · Australia Southeast           | —                                        | In scope as of v2.2.                                                                      |
| **Asia Pacific**  | 2-region           | East Asia · Southeast Asia                     | —                                        | **Japan East** — pending business confirmation before inclusion as a Standard region.    |
| **Middle East**   | Cross-geo DR       | Saudi Arabia Central · UAE North *(host Prod+CVAL, co-located)* | —                        | **DR offered cross-geo to Europe** (DEC-001 resolved; DR-020, PLC-010b). Per-country `DR_NOT_OFFERED` (DR-014) retained for legal carve-outs. |

All Standard capacity regions in every geography are eligible to host
**Prod, CVAL/NonProd, and DR** environments; region selection is driven
by the placement scoring pipeline (PLC-007/PLC-008 at **customer-aggregate**
scope per F.11) over the regions currently available in that geography.

**REG-001 — Configurable region catalogue.** The region classification,
eligibility, distribution model, and per-region flags (e.g.,
`DR_NOT_OFFERED`, zone support, restricted) must be configuration-driven
and versioned. Adding, removing, or reclassifying a region is a
configuration change, not a code or design change.

**REG-002 — Example correction discipline / cross-geo DR region is
weighted-selected.** Region examples must be sourced from authoritative
configuration, not slideware. The Middle East cross-geo DR destination is
not fixed to any single region; the engine selects it via the weighted
capacity placement model (DR-020).

**REG-003 — Distribution model.** Three distribution models are in
scope, selected per geography by configuration (REG-001):

1.  **Three-region model (US).** Prod, CVAL, and DR each occupy a
    distinct region — best distributes customer workloads and minimises
    the DR capacity reserved per region.
2.  **Two-region co-located model (Europe, Australia, Asia Pacific).** A
    two-region geography cannot separate all three environments, so
    Prod occupies one region and **CVAL + DR co-locate in the other**
    (PLC-010/PLC-010a). This is a supported, normative configuration
    provided co-location capacity accounting (HC-6, HC-7, PLC-010) is
    honoured.
3.  **Cross-geography DR model (Middle East).** Prod and CVAL co-locate
    in a selected **Middle East** Standard region (separate CRGs per
    ENV-003), and **DR is placed in a selected Europe Standard region**
    chosen by the weighted capacity placement model. CVAL co-locates with
    **Prod locally**, not with DR; the CVAL-sacrifice DR bootstrap
    (DR-005/DR-006) does **not** apply, and Middle East DR is served by
    **dedicated reserved DR capacity in Europe** (DR-020, PLC-010b).

Expanding a geography to three-plus regions remains a design goal.

## 7. Environment Policy Requirements

**ENV-001 — Production reservation coverage.** Manage approved
production VM SKUs via CRGs wherever production protection is enabled.

**ENV-002 — Production-only initial enforcement.** Mandatory
reservations apply to **production** first. Non-production reservation
enforcement stays configurable because non-prod VMs may be deallocated
for cost savings. The design must avoid a state where non-prod
reservations block cost-driven deallocation.

**ENV-003 — Hard separation constraints.** The following placement
constraints are baseline:

- Non-prod and prod **cannot** share capacity.
- DR and prod **cannot** share capacity.
- DR **may** share with non-prod.

*Clarification:* these constraints govern **capacity sharing** (a shared
CRG / reservation pool), **not** region co-residency. Prod and CVAL may
live in the **same region** (as in the Middle East cross-geo DR model,
PLC-010b) provided they use **separate CRGs / subscriptions** and never
share a reservation pool. Co-location in a *region* is not capacity
*sharing*. Isolation boundary under the multi-domain model = **domain**
(DOM-004): a CVAL/DR shared CRG never crosses domain boundaries.

**ENV-004 — CVAL treatment.** Treat CVAL as a potential DR capacity
source. The system identifies CVAL reservations, allocated/associated
CVAL VMs, releasable capacity, the production portion depending on that
CVAL location, and the actions required to free capacity for DR — all
tracked **per domain** (DOM-001).

**ENV-005 — DR bootstrap, not full duplicate.** DR must **not** default
to a fixed 30–40% copy of production. Support a configurable bootstrap
target by workload, product, domain, region, zone, VM family, and
subscription model. DR Foundation (DR-021) is sized per this requirement.

**ENV-006 — DR bootstrap cannot be implicitly zero.** A zero DR target
is allowed only via explicit approved policy. Separately identify any
already-running DR control-plane/skeleton capacity that satisfies the
bootstrap requirement.

**ENV-007 — R&D policy.** No permanent R&D reservations by default;
support time-bound reservations for POCs, latency testing across US
regions, DR exercises, and engineering tests.

## 8. Capacity Reservation Management Requirements

**CAP-001 — Authoritative managed scope.** The engine operates **only**
on resources declared in an approved configuration source (the "scope
file"). Scope includes: tenant/management scope, subscription, region,
availability zone, resource group, CRG, reservation name, SKU/VM-family,
environment, domain group, buffer policy, enabled/disabled state, and
effective date/version. Anything outside scope is never modified
automatically.

**CAP-001a — Core subscription = all production.** VMs deployed into a
shared **core** subscription are classified **production** for
reservation, buffer, and seed-matrix purposes regardless of any
individual workload label. Non-production workloads must not run in the
core/production subscription (ENV-003). The engine applies production
buffer policy (C-2) and production reservation coverage (ENV-001) to
every managed SKU/AZ in a core subscription.

**CAP-002 — Azure resource must precede config activation.** A managed
reservation is not activated in deployment config until the
corresponding Azure reservation and CRG exist and validate. **Any change
starts in Azure first, then the config** — never the reverse.

**CAP-003 — Reservation target formula.** Per domain × environment ×
region:

    Target Reserved Capacity(D,E) = Allocated VM Count(D,E) + Configured Buffer(D,E)

The target is **never** computed from associated VM count alone. See
formula F.1 in Section 21.

**CAP-004 — Associated-but-deallocated VMs.** Two checks, kept separate.

1. **Capacity target.** These VMs do not raise Target Reserved Capacity.
   Target stays Allocated + Buffer (CAP-003). Report them separately so
   teams can see restart risk and cost.
2. **Quota and shrink.** `virtualMachinesAssociated` includes
   deallocated VMs. That association still consumes the quota charged
   to the reservation until the VM is dissociated. Reconciliation does
   not treat that quota as free, and it does not lower reserved
   quantity below the associated count until those VMs are dissociated.

**CAP-005 — Automated reconciliation.** Periodically compare reserved
quantity, allocated VMs, associated VMs, available reserved capacity,
and buffer target per domain × environment × region; then raise or lower
the reservation toward the approved target, subject to Azure
availability, policy, and change controls.

**CAP-006 — Reconciliation frequency (configurable).** The reference
implementation is a container-app job packaged as a Docker image that
runs **every 6 minutes**; the production interval must be tunable
against API throttling, operational risk, cost, and deployment
responsiveness.

**CAP-007 — Scale-up behaviour.** When allocated demand rises, attempt
to raise reserved capacity to restore the buffer. If Azure cannot supply
it, hold the current safe state, **raise an alert**, and expose the
buffer deficit.

**CAP-008 — Scale-down behaviour.** When allocated demand falls, reduce
excess reservation **toward the approved buffer target** (`allocated +
buffer`), after applying any minimum-hold interval, DR protection,
approved maintenance exclusion, and cost policy. Scale-down is
**right-sizing a retained reservation**, not retirement: it never
deletes a CRG or reservation object and does not remove a SKU/AZ from
management. A **decommissioning** event legitimately drives automatic
buffer-tracking scale-down, but reducing the reservation **to 0 as an
intentional retirement**, deleting the object, or removing it from the
scope file is a **decommissioning action governed by CAP-010**.

**CAP-009 — Zero-capacity support.** Where Azure permits, reduce an
unused managed reservation to **zero** rather than deleting the
reservation object. Reaching 0 because allocated demand is legitimately
0 is a normal reconciliation outcome and is also the initial state of
every **seed reservation** in the seed matrix (CAP-022); deliberately
retiring a reservation is a decommissioning action (CAP-010).

**CAP-010 — No automatic deletion by default; decommissioning-workflow
boundary.** Normal reconciliation never deletes CRGs or reservation
definitions and never infers teardown intent from a transient drop in
allocated VMs. Each of the following requires the **separate approved
decommissioning workflow** with explicit approval, impact analysis, and
audit: (a) reducing a managed reservation to **0 as an intentional
retirement**; (b) deleting a CRG or reservation definition; (c) removing
a SKU/AZ from the scope file (CAP-019).

**CAP-011 — Availability-zone isolation.** Track and manage reservations
by region **and** availability zone; zone-1 capacity is not counted as
available in another zone. Reservations are physically organised into
the CRG structure defined in **CAP-023/CAP-025** so that zone isolation
is enforced structurally.

**CAP-012 — Regional isolation.** Reservations are never counted, moved,
or shared across regions. DR planning models destination-region capacity
independently.

**CAP-013 — Capacity sharing.** Cross-subscription reservation sharing
is a **preview** feature (DEP-001). **Production placement uses a
reservation in the deploying subscription** until sharing is generally
available. The preview path, once explicitly enabled, stays inside
Azure's supported scope: same region, an explicit consumer subscription
list, up to 100 subscriptions, same tenant or a trusted tenant. Sharing
is **domain-bounded** (DOM-004) — a provider CRG never crosses domain
boundaries.

**CAP-014 — Shared capacity visibility.** For each shared reservation,
show owning subscription, authorised consumers, consuming VMs, consumed
quantity, remaining quantity, region/zone, SKU, domain, and sharing state.

**CAP-015 — No double counting.** Capacity shared to multiple
subscriptions is counted once at the provider and apportioned by actual
consumer allocation; *authorisation to consume* is not treated as
*allocated* capacity.

**CAP-016 — Reservation integrity validation (pre-deploy).** Before
deploying against a reservation, validate: reservation exists; SKU
matches; region matches; zone matches; consumer subscription authorised
(if shared); sufficient reserved capacity or approved over-allocation;
and required quota available in the deploying subscription (both the
VM-family cap and the total regional vCPU cap, QUA-002).

**Zone match** is the same physical zone. Azure assigns logical zone
numbers per subscription, so Zone 1 in the consumer subscription and
Zone 1 in the provider subscription can be different datacentres. On a
shared zonal reservation the engine stores the **provider** logical
zone and translates the consumer logical zone to that provider zone
before deploy.

**CAP-017 — Deployment failure policy.** If reservation enforcement is
mandatory and validation fails, the deployment **fails safely** with a
clear reason. No silent deployment without the required reservation
unless an approved break-glass policy is invoked.

**CAP-018 — Over-allocation policy.** Support an explicit policy to
associate more VMs than reserved where operationally required,
distinguishing **guaranteed allocated** capacity from
**associated-but-unguaranteed** capacity.

**CAP-019 — Scope-file governance.** Adding a SKU to management requires
(a) creating the Azure reservation and (b) adding it to the scope file;
removing a SKU from the file removes it from engine management. Where
the engine **reactively discovers** an allocated SKU/AZ not yet in the
scope file, CAP-024 governs how the Azure-first creation and the
scope-file entry are reconciled.

**CAP-020 — Availability-Set VMs are ineligible for reservations.**
Azure Capacity Reservations cannot be associated with VMs deployed in an
**Availability Set**. Therefore the engine: (a) **excludes**
Availability-Set VMs from reservation eligibility and from the
`allocated`/`associated` counts that drive reservation targets (CAP-003);
(b) surfaces any managed-scope VM found in an Availability Set as a
**non-eligible exception** with the CAP-021 remediation action; and (c)
never attempts to create, associate, or size a reservation for such a VM.

**CAP-021 — Deallocate-or-migrate-to-AZ onboarding precondition.**
Before a VM can be brought under reservation management it must occupy a
**reservation-eligible placement** — an availability zone (preferred),
or regional placement where the SKU has no zonal support. The engine
records the required remediation action and treats the reservation as
manageable only once the VM is confirmed in an eligible placement; it
**does not auto-migrate running workloads**.

**CAP-022 — Seed-at-0 eligible-SKU/AZ matrix & budget governance.**
The managed set of SKU/VM-family × region × availability-zone
combinations is initialised as a **seed matrix of count-0 reservations**
inside the zonal CRG for that zone (CAP-023/CAP-025), so reconciliation
can scale each up from a known baseline the instant allocated demand
appears. Populating this matrix is governed by **product-team budget
approval**.

**CAP-023 — Zonal CRG structure (base).** For each **domain × environment**
(Prod, CVAL/NonProd, DR) within a subscription and region, the default is
**one zonal Capacity Reservation Group**. Its zones are declared at
creation and cannot be changed later. Inside that group there is **one
reservation per VM size per zone**. Zone isolation (CAP-011) is structural
at the reservation level. A group created **with no zones** is not a
region-wide pool — Azure pins it to a single zone. Environments are
**never** mixed within a CRG (ENV-003). Names follow OPS-006 / C-12.

*CAP-023 defines the base CRG structure. CAP-025 extends it to the
per-domain CRG-set organisation.*

**CAP-024 — Reactive SKU/AZ discovery reconciled with governance.** When
reconciliation or a deployment detects an **allocated VM of a SKU/AZ
combination not yet in the seed matrix**, the engine **auto-creates the
corresponding reservation** — CRG (if absent) plus reservation sized at
`allocated + buffer` — so production is protected immediately, **and
simultaneously raises a scope-file governance item** (CAP-019).

**CAP-025 — Domain-group CRG structure per Domain × Environment ×
Region.** For each **domain group** (DOM-001) and each **environment**
(Prod, CVAL/NonProd, DR) in each **region** of the customer's CRV
(PLC-013), the engine maintains a dedicated CRG set on that domain's ig
subscription (PLC-014), which is **never mixed with another domain's CRG
set**:

-   **Prod CRG set** — dedicated to Prod only: `crg-pr-<region>-*` per
    CAP-023. Prod capacity is never shared, per ENV-003.
-   **CVAL/DR shared CRG set** — one CRG set shared **between CVAL and
    DR within the same domain**: ENV-003 permits DR to share with
    non-prod, so `crg-cvdr-<region>-*` may hold both CVAL and DR
    capacity of that domain. Sharing is domain-bounded (DOM-004). The
    CVAL-sacrifice bootstrap (DR-005/DR-006) is implemented through
    this set.
-   **DR Foundation CRG set** — dedicated DR-bootstrap CRGs
    (`crg-drf-<region>-*`) sized per ENV-005/DR-007 bootstrap and always
    present with pre-staged quota (QUA-015); never shared with CVAL
    until an approved DR declaration triggers CVAL release (DR-010,
    DR-021).

Example (domain TMS, region EUS2, three zones):
`crg-pr-eus2-zonal`, `crg-pr-eus2-az1/2/3`, `crg-cvdr-eus2-zonal`,
`crg-cvdr-eus2-az1/2/3`, `crg-drf-eus2-zonal`. Names follow
OPS-006/C-12; the environment token (`pr`/`cvdr`/`drf`) is part of the
naming convention.

## 9. Quota Management Requirements

**QUA-001 — Separate quota domain.** Manage quota as a separate control
plane from reservations. A reservation is **not** proof that deployment
quota exists.

**QUA-002 — Regional & family scope.** Maintain quota inventory by
subscription, region, VM/quota family, assigned quota, usage, available
quota, pooled quota, and pending increases. Every region has **two**
caps: the **VM-family vCPU** quota and the **total regional vCPU**
quota. Both are consumed when a reservation is created and when a VM is
deployed.

**QUA-003 — Central pooling ("quota hoarding").** Where Azure Quota
Groups support the scope, eligible subscriptions contribute **unused**
quota into a governed group so it can be transferred to the subscription
that will deploy. The group limit is **not** what a VM create checks.
Quota does not move to another region when collected (QUA-012).

**QUA-004 — One Quota Group, operations per region and family.** A
subscription belongs to **one** Azure Quota Group. Each transfer or
increase is scoped to **one region and one VM family**. The engine's
accounting grain is that region × family cell, covering prod, non-prod,
and DR together, with logical earmarks so NonProd cannot spend Prod or
DR quota (HC-7).

**QUA-005 — Quota as cost/consumption governor.** Use quota allocation
to cap deployable capacity by product, environment, subscription,
region, and VM family. Do **not** increase a subscription's quota merely
because unallocated pooled quota exists.

**QUA-006 — Production growth buffer.** Production subscriptions
maintain a configurable quota headroom above current usage to support
growth and the next deployment.

**QUA-007 — Quota–reservation validation.** For each managed scope,
validate that quota is sufficient to deploy against the intended
reservation. "Available quota" is the **lesser** of remaining VM-family
vCPU and remaining total regional vCPU on that subscription (QUA-002).
See formula F.4 in Section 21.

**QUA-008 — Dynamic allocation.** Allocate quota from the pool to a
target subscription per policy, deployment demand, production buffer,
and DR need.

**QUA-009 — Quota reclamation.** Reclaim unused subscription quota into
the pool when policy permits, never dropping a subscription below
current usage, committed demand, production buffer, or approved DR need.

**QUA-010 — Quota request governance.** Increase requests record
justification, target workload, SKU/family, region, amount, existing
usage, target date, and owner.

**QUA-011 — Quota source discovery.** Discover reusable quota assigned
by default to subscriptions in regions where they will not deploy,
subject to safe-reclamation checks.

**QUA-012 — Region-failure assumption.** Quota bound to a failed region
is **not** assumed transferable to the DR region. DR destination quota
must be planned and present in the destination region.

**QUA-013 — Consumer-subscription quota (documented).** A VM deployment
requires quota in the **consumer/deploying** subscription even when
capacity is shared from a provider subscription. Sharing itself remains
Preview (CAP-013), so this rule applies on the preview path and the
same-subscription production path alike.

**QUA-014 — Quota allocation audit.** Log every allocation, reclamation,
request, approval, rejection, and failed change with before/after
values, actor/workload identity, policy reason, correlation ID, and
timestamp.

**QUA-015 — Central quota group across domain subscriptions.** All of a
customer's **domain ig subscriptions** (DOM-002) are members of the
customer's **centrally managed quota group**, per region × VM-family
cell (QUA-004): one governed group per customer-scoped regional/family
scope, with subscription-level draws. Replenishment is governed by
configured thresholds: `GROUP_REPLENISH_THRESHOLD` (default 85%) at the
group cell level and `SUB_REPLENISH_THRESHOLD` (default 85%) at the
subscription level. TRANSFER mechanics, deploy-time checks, and the
two-cap rule follow QUA-003/QUA-004/QUA-007 exactly. Domain ig
subscriptions never belong to another customer's group.

## 10. Combined Capacity & Quota Readiness

**RDY-001 — Deployment readiness gate.** A deployment is capacity-ready
only when all pass: target region approved; zone supported (physical
zone, CAP-016); SKU supported; reservation policy known; reservation
exists (if required); sufficient reservation or approved
over-allocation; sufficient consumer-subscription quota on **both** the
VM-family cap and the total regional vCPU cap; records fresh enough;
and no blocking policy/exception. Per-domain readiness is checked via
the DPB (PLC-014).

**RDY-002 — Readiness states.** Expose a machine-readable state:
`READY`, `READY_WITH_RISK`, `QUOTA_DEFICIT`, `RESERVATION_DEFICIT`,
`CAPACITY_UNAVAILABLE`, `STALE_STATE`, `POLICY_BLOCKED`,
`VALIDATION_REQUIRED`.

**RDY-003 — Capacity and quota must understand each other.** Though
controlled separately, correlate them by region, zone, SKU/family,
subscription, environment, domain, and intended demand — capacity and
quota must be **balanced**.

**RDY-004 — No stale placement.** Region selection/provisioning must not
use a snapshot older than the configured max age; if stale, refresh
synchronously or stop with `STALE_STATE`. This applies to both CRV
reads (PLC-015) and DPB resolution (PLC-014).

---

## 11. Region Selection & Customer Placement

Region selection binds a customer's environments to Azure regions.
It is **customer-scoped** — one binding per customer × geography,
shared by all domain groups (PLC-013). Instance groups and capacity
are **domain-group-scoped** (PLC-014). The pipeline resolves the
Customer Region Vector first, then the Domain Placement Binding
(PLC-015 ordering gate).

**PLC-001 — Production region is the primary input (exact-region
path).** The default onboarding path requires the customer or
platform workflow to supply the exact Azure production region. ACRME
validates the supplied region against Hard Constraints and
placement-policy rules instead of deriving a region from a broad
geography. Rationale: requiring a precise region avoids "I picked
North America but meant East Coast" churn and the contract rewrites
it causes.

**PLC-002 — Geography-based selection is exceptional (geography
path).** Geography-only selection (US / Europe / Australia / Asia
Pacific / Middle East → engine derives the region) is an exceptional
path. It requires explicit exception approval and customer
acknowledgement that the derived production region becomes fixed
until an approved migration changes the seed. Without an approved
exception, the exact-region default (PLC-001) applies.

**PLC-003 — Customer seed record.** The first placement decision
creates an authoritative seed record: customer/realm identifier,
geography, production region, CVAL region, DR region (or
`NOT_OFFERED`), domain groups covered, CRV reference (PLC-013), DPB
references (PLC-014), decision timestamp, policy/engine version,
capacity-snapshot reference, exception reference (if any), and
approval metadata.

**PLC-004 — Reuse across domain groups.** Subsequent domain
groups/environments for the same customer + geography read the seed
record instead of re-selecting production ("their production is
their production for all domain groups in that geography"). The
engine is **not** re-invoked per domain group once seeded (PLC-013
CRV reuse).

**PLC-005 — Controlled seed change.** The seed is never regenerated
on upgrades, rebuilds, or routine deployments; changes require an
approved migration/exception workflow with impact analysis.

> *PLC-006 — RETIRED. Previously described CVAL & DR selection as a
> separate step; this is now fully subsumed by PLC-013 (CRV
> resolution via either the exact-region or geography path) and the
> distribution model rules in PLC-010/010a/010b.*

**PLC-007 — Live weighting.** Placement weighting considers, at
customer-aggregate scope (per F.10): allocated capacity, available
reservation, quota availability, buffers, prod/CVAL distribution,
expected DR contribution, zone support, regional restrictions, γ
fairness (PLC-012), and state freshness.

**PLC-008 — Lowest suitable load.** Select the lowest-**risk**
suitable location per the weighted policy — the lowest-consumption
subscription for the new customer's CVAL/DR — not merely the lowest
raw utilisation, evaluated at customer-aggregate scope (per F.10).
If the chosen production region lacks capacity, raise an
alarm/exception while still placing CVAL/DR appropriately.

**PLC-009 — AEP-triggered pipeline.** Region selection is the
**first** pipeline AEP triggers; it emits production → derives DR
(and CVAL) and writes the seed. Implementation is a function-app
flow (not a logic app) invoked via API or GitHub Actions. The
pipeline enforces the two-phase gate (PLC-015): CRV resolution
precedes DPB resolution.

**PLC-010 — CVAL/DR co-location.** A customer's CVAL and DR **may
co-locate in the same destination region** to support the
CVAL-sacrifice bootstrap pattern (DR-005/DR-006). When co-located,
the engine must record that the CVAL capacity is earmarked as
releasable toward that customer's DR activation, and must not
double-count it as both live CVAL and available DR headroom.

**PLC-010a — Co-location is mandatory in two-region geographies.**
Co-location is *optional* only where a geography has enough regions
to separate all three environments (currently **US**, the
three-region model). In a **two-region** geography (currently
**Europe, Australia, Asia Pacific**), once Prod is anchored in one
region only a single region remains, so **CVAL and DR co-locate
there deterministically** — this is the normal, required outcome,
not an exception. The engine must:

-   derive the co-location automatically whenever the geography's
    available Standard-region count is two (do not fail placement for
    lack of a third region);
-   apply the HC-6 (DR coverage floor) and HC-7 (DR floor integrity)
    combined-capacity checks against the co-located region so the
    shared CVAL/DR pool can absorb the customer's DR demand; and
-   record `cval_region == dr_region` in the seed record and flag the
    co-location so downstream accounting never double-counts the
    shared capacity.

This rule is driven by the configured distribution model per
geography (REG-001/REG-003) and applies to the **two-region
co-located model** (Europe, Australia, Asia Pacific). **Middle East
is carved out**: it now uses the **cross-geography DR model**
(PLC-010b), in which CVAL co-locates with **Prod** in the local
Middle East region and DR is placed cross-geo in Europe — so
PLC-010a's CVAL/DR co-location does **not** apply to Middle East.
Any Middle East country still under a legal `DR_NOT_OFFERED`
carve-out (DR-014) is assigned no DR region at all; that remains a
country-level legal override, not a property of the distribution
model.

**PLC-010b — Cross-geography DR override (Middle East).** Where a
geography is configured for the cross-geography DR model (REG-003
item 3; currently Middle East), the engine must:

-   place **Prod and CVAL** in a single selected **Middle East**
    Standard region, co-located in that region but in **separate
    CRGs** (ENV-003 — capacity is not shared), selecting the region
    via the **weighted capacity placement model**;
-   place **DR** in a **Europe** Standard region selected
    **independently via the same weighted capacity placement model**
    (DR-020) — DR is **not** co-located with CVAL and is **not**
    bootstrapped by CVAL-sacrifice (DR-005/DR-006 do not apply here);
    Middle East DR is served by **dedicated reserved DR capacity** in
    the Europe destination;
-   record `prod_region == cval_region` (Middle East) and
    `dr_region ∈ Europe`, `dr_geography == "Europe"` in the seed
    record, and mark the placement as cross-geo so DR accounting, the
    source→destination DR index (DR-018), and HC checks treat the
    Europe DR region as the protection destination for the Middle East
    source;
-   apply the standard DR sizing (DR-002/DR-017 max-not-sum) against
    the Europe destination and contribute to Europe's destination
    distribution (DR-003, DR-016 reciprocal multi-source hosting);
-   honour any per-country `DR_NOT_OFFERED` flag (DR-014): if set, no
    Europe DR region is assigned for that country and only Prod+CVAL
    are placed locally.

PLC-010b is configuration-driven: if the Middle East catalogue later
gains an acceptable in-geography DR region, the geography can be
reconfigured to a local model without a code change (REG-001).

**PLC-011 — Even zone-distribution target & rebalancing.** Placement
targets an **even spread of a domain workload's VMs across the
region's availability zones** — approximately `1 / zone_count` per
zone (≈ **33%** each in a three-zone region). This is a placement
**target**, not merely the zone-diversity scoring *signal* used in
PLC-007 weighting (the ε zone-diversity term). When a new deployment
or a growth event would skew a domain workload's zone distribution
beyond a **configurable tolerance** from the even target, the engine
must:

-   **prefer the under-represented zone(s)** for new placement (fill
    the most under-represented zone first); and
-   raise a **rebalancing recommendation/action** — subject to
    approval and Azure feasibility — to move the distribution back
    toward even.

Even distribution bounds per-zone failover exposure and keeps the
per-AZ CRG sizing under CAP-023 balanced. The target ratio and skew
tolerance are configuration-driven (`PlacementPolicy`, C-13).
Per-domain zone distribution is further detailed in PLC-016. See
F.9 for the skew formula and the Calculation Logic Reference for a
worked three-zone scenario. *(Rationale: the Reservation-Creation
flow checks that a new VM does not push any zone above the even
share before placing it; without an explicit target the ε
zone-diversity term only nudges scoring and cannot trigger a
rebalance.)*

**PLC-012 — Geography customer count (γ fairness denominator).** The
distribution-fairness term γ in the placement scores (PS_Prod,
PS_NonProd, PS_DR; PLC-007 live weighting) divides a region's
environment customer count by `total_customers(g)`, defined as
follows:

-   **Definition:** the total number of customers in geography *g* —
    the count of **distinct customers** (one seed record per
    customer, PLC-003) with at least one environment (Prod, CVAL or
    DR) **provisioned or being deployed** in any region of *g*.
-   **Scope and unit:** a count (integer ≥ 0) calculated **per
    geography**, so that environment distribution across the regions
    of a geography stays fair. One count per geography is shared by
    all three scores; only the numerator is environment-specific (the
    region's Prod, CVAL or DR customer count).
-   **Source and refresh:** derived live from the authoritative
    placement state (seed records, DAT-002). When a new customer
    environment is provisioned or is being deployed in any region of
    the geography, the count is incremented. It is not a configurable
    constant or a forecast.
-   **Zero rule:** when `total_customers(g) = 0`, **γ = 1** for
    every region of *g* (a geography with no customers is perfectly
    fair).

See F.10 for the formula. *(Rationale: without a defined denominator
the γ term could not be computed consistently; a geography-scoped
count keeps the fairness signal comparable between candidate regions
of the same geography.)*

**PLC-013 — Customer Region Vector (CRV): region selection is
customer-scoped.** The engine binds a customer's regions **once per
customer × geography** into a Customer Region Vector
`CRV(C,G) = (geography, distribution model, prod, cval, dr)` stored
on the seed record (PLC-003) and **reused by every domain group of
that customer** (PLC-004: "their production is their production for
all domain groups in that geography"). Region selection follows
**two input paths** (identical scoring pipeline, different unknowns):

1.  **Exact-Region Path (PLC-001, default)** — customer supplies the
    exact production region; the algorithm determines **CVAL and DR
    only** (two environment regions). Prod is a validated input
    constant (frozen until approved migration, PLC-005).
2.  **Geography Path (PLC-002, exception)** — customer supplies a
    geography (exception-approved, customer-acknowledged); the
    algorithm determines **all three environment regions** (Prod,
    CVAL, DR).

Both paths apply the same weighted capacity placement model
(PLC-007/008) per the distribution model (REG-003,
PLC-010/010a/010b) and the same Hard Constraints, then converge on
the Domain Placement Binding step (PLC-014). See F.11 for the two
formula sets.

**PLC-014 — Domain Placement Binding (DPB): ig and capacity are
domain-scoped.** After the CRV is resolved (or reused), each
**domain group** (DOM-001) binds its capacity per
(domain × environment × CRV region) via a **Domain Placement
Binding** `DPB(D,E)`: (a) resolves the ig subscription (DOM-002,
C-12 + shard registry); (b) ensures the **domain CRG set** per
CAP-025 (Prod-dedicated, CVAL/DR shared, DR Foundation sets);
(c) sizes CRs at `allocated + buffer` (CAP-003, F.1–F.3);
(d) applies the per-domain zone distribution (PLC-016); and
(e) draws quota from the customer's central quota group per
region × VM-family cell (QUA-015). The DPB is deterministic — no
region weighting at domain scope; the region always comes from the
CRV. The domain token lives in the subscription name (C-12/OPS-006),
never in the CRG registry identity.

**PLC-015 — Two-phase resolution gate: CRV strictly precedes DPB.**
Region selection (PLC-013) is resolved **once** and cached; every
deployment then reads the CRV and runs the DPB (PLC-014). A domain
group never re-runs region selection; a customer-level region change
occurs only via the approved migration/exception workflow (PLC-005).
Engine flow: "AEP intent → S1 resolve/reuse CRV → S2 resolve DPB →
S3 readiness (RDY-001/CAP-016) → S4 associate/deploy (INT-005)".

**PLC-016 — Per-domain zone distribution + combined region
observation.** The even zone-distribution target (F.9) is applied
**per domain workload** (each domain targets ≈ `1/zone_count` for
its own VMs; rebalancing actions are raised per domain). The region
maintains a **combined-load observation** across all domains of the
customer — `RegionZoneLoad(R,E,z) = Σ_D VMs(D,E,R,z)` — as an
**observation/alerting unit only** (OBS-001/002); it never triggers
reservation actions across domains (no sum-reserving; F.6/F.7 sizing
unchanged).

---

## 12. Domain Group Model

*(Domain-group taxonomy for multi-domain customers. Customer X
reference model: domains **TMS** and **WMS**; same region selection
for both domain groups; different ig per domain; per-domain
subscriptions; DR Foundation as separate base capacity extended by
CVAL sharing; centrally managed quota.)*

**DOM-001 — Domain group definition & taxonomy.** A **domain group**
is a workload-domain grouping of a customer's capacity (`wl-*`
token, e.g. TMS, WMS; function-group `<fn>` per C-12). A customer
may own multiple domain groups; all of them share the customer's
seed record and CRV (PLC-013) but keep separate instance groups
(DOM-002). The domain taxonomy (`wl-*` vs function-group tokens) is
a configurable item (C-14), resolved per DEC-004.

**DOM-002 — Instance-group (ig) binding & subscription ownership.**
One **Instance Group (ig)** exists per (domain × environment ×
region) on a subscription per (domain × environment) — e.g.
`sub-jda-cld-cr-prod-wl-tms-wus2-01` vs `...-wl-wms-wus2-01`
(C-12/OPS-006). igs never span domains; domains never share an ig.
The ig owns the domain's CRG set (CAP-025), its CRs, and its quota
draw (QUA-015). Scale-out beyond ig limits uses the shard registry
(DOM-003).

**DOM-003 — Cross-domain placement independence within bound
regions.** All of a customer's domain groups deploy inside the
customer's CRV regions (e.g. Prod WUS2 for both TMS and WMS); each
domain resolves its own DPB (PLC-014) and may scale, fail over, or
rebalance independently without affecting another domain's ig
(PLC-016). A domain requesting a region outside the CRV requires an
approved customer-level migration (PLC-005).

**DOM-004 — Domain-bounded sharing.** Sharing (CAP-013) is granted
**within a domain only**: the CVAL/DR shared CRG set (CAP-025)
serves that domain's CVAL and DR; cross-domain sharing is not
permitted (ENV-003 isolation; isolation boundary = domain).
Provider/consumer relationships (consumer subscriptions, consumption,
revocation) are tracked per CAP-013/014/015 with the domain token in
the audit record.

---

## 13. Disaster Recovery Capacity Requirements

**DR-001 — Single-region failure basis.** The default model plans
for failure of **one** production region within a geography.
Simultaneous multi-region failure is outside the default guaranteed
model unless separately funded/approved ("if we have DR in two
regions in a geography, we're in serious trouble").

**DR-002 — Distributed DR.** DR capacity is computed per domain from
the **portion** of the source region's production workload assigned
to each destination — not by reserving the full source workload in
every destination. In a multi-region geography a customer's domain
workload is distributed across the available regions, so only that
domain's *portion* needs protecting per destination. In a
**two-region** geography (Europe, Australia, Asia Pacific) the single
non-Prod region absorbs the full protected portion for the Prod
region, with CVAL and DR co-located there per ENV-003/PLC-010. In
the **cross-geography DR model** (Middle East, PLC-010b) the
protected portion of the Middle East Prod region is reserved in the
selected **Europe** destination region as dedicated DR capacity —
CVAL stays local with Prod and is **not** a DR source for that
customer (DR-020).

**DR-003 — Destination distribution.** Record how each source
region's recoverable workload distributes across eligible destination
subscriptions, regions, zones, SKUs, and domains.

**DR-004 — CVAL target contribution.** Normal CVAL placement per
domain should contribute toward the capacity needed for the
production portion expected to fail over to that location ("CVAL
only needs to support a *portion* of a production failover, not all
of it").

**DR-005 — CVAL may exceed DR need.** CVAL capacity may exceed the
minimum DR contribution (it's "free" while running); excess running
CVAL is potentially reusable during a declared disaster, subject to
shutdown/disassociation rules.

**DR-006 — Staged DR capacity acquisition.** The recovery process
supports staged expansion: 1. Use approved **bootstrap / pre-staged
headroom**. 2. Allocate available reservation + quota already in the
destination. 3. **Shut down / disassociate** eligible CVAL workloads
to free capacity. 4. Share or reassign reservations within supported
region/zone boundaries. 5. Allocate pooled quota to DR
subscriptions. 6. Request additional Azure quota/capacity where
required. 7. Report unrecoverable capacity gaps.

This staging lets priority (P0/P-1) customers start immediately from
bootstrap headroom while rebalancing proceeds, rather than waiting
on deallocation/disassociation APIs that will be **throttled**
industry-wide during a regional event.

**DR-007 — DR target is configurable.** Bootstrap quantity may be a
node count, SKU-specific quantity, vCPU value, workload tier, or
approved percentage; configurable by product, domain, and region
(C-16). (Design started at ~30–40%, then discussed 10–20%, then ~5%,
converging on "whatever is needed to bootstrap and is used =
effectively free.")

**DR-008 — Control plane first.** Bootstrap prioritises required
platform control planes and recovery orchestration before customer
workload waves ("without a control plane, nothing else runs").

**DR-009 — Recovery prioritisation.** Support prioritised
customer/workload recovery waves using **authoritative** business
priorities; the engine does not invent priority.

**DR-010 — DR declaration guardrail.** Destructive/service-impacting
actions against CVAL occur only after an authorised DR declaration or
approved DR exercise trigger.

**DR-011 — Source region not a capacity source during outage.**
During a destination recovery decision, do not count
reservations/quota from the unavailable source region. Cross-region
reuse does not work, and a down region's VMs/quota remain bound as
left (validated behaviour, incl. the Australia outage where VMs were
not truly deallocated behind the scenes).

**DR-012 — DR drill rotation.** Support periodic DR drills and role
swaps (active ↔ recovery) without losing the seed, historical
capacity state, or audit trail. CVAL capacity "flips around" per
region during the annual drill.

**DR-013 — Failback policy (configurable).** Support both an
**extended DR run (~1 year, preferred)** and an **earlier failback
(~30 days)** model to prove failback. Duration/execution is a
business/operations decision (C-5).

**DR-014 — Per-country DR policy flag.** Support `DR_NOT_OFFERED`
per country/region where legal/data-sovereignty prevents an
acceptable DR design. **The geography-level Middle East position is
no longer `DR_NOT_OFFERED`** — DR is now offered cross-geo to Europe
(DEC-001 resolved; DR-020, PLC-010b). The flag is **retained** as a
granular, per-country/region override: any specific Middle East
country whose legal posture still forbids cross-border DR is flagged
`DR_NOT_OFFERED`, in which case its production/CVAL are placed
locally and no Europe DR region is assigned for it.

**DR-015 — Future active-active consideration.** Note (out of
baseline scope) that LLM/APM may move from active-passive to
active-active multi-region in future; the capacity model should not
preclude it.

**DR-016 — Reciprocal multi-source hosting.** Every region may
concurrently perform **three roles**: (a) Production for its own
customers, (b) CVAL host for customers whose production is
elsewhere, and (c) standby **DR host for customers originating in
multiple *different* source regions**. The design must support this
many-to-many topology — e.g., Region 1's DR block simultaneously
holds Cust2 (prod in R2) and Cust7 (prod in R3). DR distribution is
therefore **bidirectional**, not a single source→destination
fan-out.

**DR-017 — Non-concurrent capacity sharing (max, not sum).** Because
only one region fails at a time (DR-001), a region that serves as
DR target for several source regions must be sized to absorb the
**largest single source** it protects, **not the sum of all of
them**. This permits **shared / overcommitted DR capacity** across
mutually-exclusive failure events and is the primary mechanism that
keeps the lean DR model affordable (see F.6 and Appendix D).
Reserving the sum would over-provision and negate the cost savings
that justified the bootstrap model (FIN-006).

**DR-018 — Source→destination DR index.** Maintain an authoritative
**bidirectional mapping** that records, for each source region, which
destination regions hold its customers' DR instances and in what
quantity/SKU, with domain attribution. On a regional failure the
engine uses this index to determine exactly which standby instances
to activate and where. The index is the reverse view of the
per-customer seed record (PLC-003) and is a required entity in the
state store (DAT-002).

**DR-019 — Standby activation on declaration.** On an authorised DR
declaration (DR-010), the engine shall transition the failed region's
customers' pre-placed DR instances from **associated → allocated**
(inactive/standby → active) in approved business-priority order
(DR-009), acquiring capacity via the staged sequence in DR-006
(bootstrap headroom → available reservation/quota → CVAL sacrifice →
sharing/reassignment → pooled quota → Azure request). Activation
state per customer and domain must be tracked, auditable, and
reversible on failback (DR-013).

**DR-020 — Cross-geography DR (Middle East → Europe).** For
geographies configured with the cross-geography DR model (REG-003
item 3; currently Middle East), DR capacity is placed in a
**different geography** from Prod/CVAL:

-   **Source:** the customer's Middle East Prod region (with CVAL
    co-located locally per PLC-010b).
-   **Destination:** a **Europe Standard** region selected by the
    **weighted capacity placement model** — the same scoring pipeline
    used for Prod selection (readiness, capacity weighting,
    separation, zone availability), scoped to Europe Standard
    regions. The destination is **not** hard-coded (REG-002); the
    default example is illustrative only.
-   **Capacity basis:** dedicated reserved DR capacity sized per
    DR-002 (protected portion) and DR-017 (max-not-sum across
    non-concurrent sources). Middle East sources contribute to
    Europe's destination distribution (DR-003) and participate in
    reciprocal multi-source hosting (DR-016).
-   **Accounting:** the source→destination DR index (DR-018) records
    the Middle-East→Europe mapping; the Europe destination's HC-6/
    HC-7 DR floor must include the Middle East protected portion so
    it is not double-counted against Europe-local DR demand.
-   **Cost/ownership:** cross-geo DR capacity in Europe is
    funded/approved under the Middle East programme (legal-owned);
    FinOps attribution follows the source customer, not the Europe
    host.
-   **Data residency (A-ME1):** cross-border DR to Europe is
    predicated on legal clearance of residency for the applicable
    customer classes; where clearance is absent, DR-014 applies.

**DR-021 — DR Foundation: dedicated bootstrap base + CVAL
extension.** Each **domain group** (DOM-001) maintains a two-layer
DR capacity model in the customer's DR region (CRV, PLC-013):

1.  **DR Foundation** — a **dedicated** CRG set
    (`crg-drf-<region>-*`, CAP-025) sized per ENV-005/DR-007
    bootstrap (configurable per product/domain/region/zone/VM-family;
    C-16 — never a fixed percentage). It bootstraps control planes
    and P0 recovery waves (DR-008/DR-009), is **always present** with
    pre-staged quota (QUA-015), and does not depend on sharing
    availability.
2.  **CVAL Extension** — on an approved DR declaration (DR-010), the
    domain's **CVAL/DR shared CRG set** (CAP-025) is released (CVAL
    sacrifice, DR-005/DR-006) and DR VMs of that domain scale into
    it, providing the elastic failover layer. This extension is gated
    on sharing behaviour validation (POC-001) and Preview maturity
    (DEP-001); the Foundation works without it.

Lifecycle: Foundation is structural (always exists); Extension is
event-driven (activated at declaration). DR accounting (DR-018 index,
HC-6/HC-7 floors) covers both layers per domain and never
double-counts the shared CVAL/DR set (PLC-010, ENV-003).

### 13A. Distributed DR Reference Model

This section formalises the failover topology reviewed against the
distribution diagram. It is the canonical picture the engine
(DR-002/003/016/017/018/019) implements.

#### 13A.1 Topology

-   A **geography** contains **N regions** (target: 3–4; minimum
    viable: 3 for safe distribution — see REG-003).
-   Each region simultaneously hosts three stacked blocks: **Prod**,
    **CVAL**, and **DR** (DR-016).
-   A customer's **Prod**, **CVAL**, and **DR** live in **different**
    regions per the separation rules (ENV-003), though **CVAL and DR
    of a given customer may co-locate** (PLC-010).
-   Each region's **DR block is a standby (associated, not
    allocated)** landing zone for customers whose **Prod is in other
    regions** (green = active/allocated; red = inactive/associated in
    the diagram).

#### 13A.2 Worked example (from the reviewed diagram)

| Region       | Prod customers      | CVAL hosted         | DR standby hosted (source region)  |
|--------------|---------------------|---------------------|------------------------------------|
| **Region 1** | Cust1, Cust3, Cust5 | Cust2, Cust7        | Cust2 (R2), Cust7 (R3)             |
| **Region 2** | Cust2, Cust4        | Cust1, Cust6, Cust5 | Cust1 (R1), Cust6 (R3), Cust5 (R1) |
| **Region 3** | Cust6, Cust7        | Cust3, Cust4        | Cust3 (R1), Cust4 (R2)             |

#### 13A.3 Failover behaviour (Region 1 goes down)

1.  Region 1's **production** customers (Cust1, Cust3, Cust5) are
    activated on their **pre-placed DR** instances in the surviving
    regions (DR-018 index lookup): Cust1 → R2, Cust5 → R2,
    Cust3 → R3.
2.  Standby DR instances flip **associated → allocated** in priority
    order (DR-019), acquiring capacity via the staged sequence
    (DR-006), including **sacrificing CVAL** in the destination if
    required (DR-005/DR-010).
3.  **Capacity and quota shift** across regions accordingly; the
    state store is updated and feeds the next selection cycle
    (DAT-001, RDY-004).
4.  Region 1's own **DR-standby** duties for other regions (it was
    holding Cust2/Cust7 standby) are understood to be **temporarily
    unavailable** while Region 1 is down — acceptable under the
    single-failure assumption (DR-001), because R2/R3 are not
    simultaneously failing.

#### 13A.4 Annual mock DR

During the yearly drill (DR-012), **CVAL capacity per region is
reshuffled** to validate the failover paths and to keep destination
reservations right-sized for the production portion each region
protects.

---

## 14. Cost Economics & FinOps Requirements

**FIN-001 — Idle cost measurement.** Calculate/ingest the cost of
unused reserved capacity by region, SKU, subscription, environment,
domain, and owner.

**FIN-002 — Configurable economic policy.** Buffer and bootstrap
values are adjustable **without code changes** to balance risk,
deployment speed, audit needs, and cost.

**FIN-003 — Cost before expansion.** Before increasing a persistent
buffer or DR target, expose expected incremental cost and require
justification.

**FIN-004 — Cost allocation.** Reservation cost is attributable to
the owning platform/product/environment/domain or centrally funded
DR function per approved tagging/chargeback policy. FinOps
attribution keys are (customer, domain, environment, region); shared
CVAL/DR CRG cost is single-counted per domain; DR Foundation cost is
attributed to the DR function per domain.

**FIN-005 — Underutilisation review.** Long-running underutilised
reservations create a review item rather than being silently
retained. (The cost-optimisation team already chases orphaned
reservations left behind after maintenance — set to zero, don't
delete.)

**FIN-006 — No cost-only unsafe reduction.** Cost optimisation never
reduces reservations/quota below allocated demand, committed
production buffer, or authorised DR bootstrap without an approved
exception.

**FIN-007 — Audit-friendly flexibility.** Buffer/bootstrap numbers
must be adjustable to satisfy SOC 2 DR assertions ("here's how we
ensure DR capacity") while still optimising cost — the number is a
tunable governance lever, not a fixed architectural constant.

**FIN-008 — Shared-DR overcommit accounting.** Where DR-017 sizing
(max-not-sum) relies on non-concurrent sharing, the cost model must
reflect the **shared/overcommitted** reservation as a single cost,
not per-source duplication, and must flag the residual risk if the
single-failure assumption is ever violated.

> **Why lean DR won.** Cost modelling during review showed a 30%
> empty DR reserve is prohibitively expensive at platform scale — on
> the order of **millions per year** — and would likely cause
> leadership to cancel multi-region entirely. See Appendix B for
> worked examples and Appendix D for the max-vs-sum saving.

---

## 15. Provisioning & AEP Integration

**INT-001 — Capacity API/workflow.** AEP calls a
capacity+placement service/pipeline before the first relevant
environment deployment and before any later deployment that changes
capacity demand.

**INT-002 — Idempotent interface.** Capacity checks and reservation
operations are idempotent; repeated calls with the same correlation
ID + desired state do not duplicate allocations or records.

**INT-003 — Required input.** customer/realm; domain group token
(DOM-001); product; environment; production region (or approved
exception input); subscription; SKU + count; zone requirement;
deployment priority; requested time; correlation ID.

**INT-004 — Required output.** resolved prod/CVAL/DR placement
(CRV, PLC-013); DPB reference (PLC-014) including ig subscription,
domain CRG set (CAP-025), zone spread; readiness status; approved
reservation/CRG reference; quota status and quota-draw route
(QUA-015); available vs required quantities; blocking reasons;
exception requirements; snapshot timestamp; trace/decision ID.

**INT-005 — Deployment reservation association.** When policy
requires it, associate the VM / VM scale-set instance configuration
with the validated reservation reference (Anu's pipeline supplies
the reservation-group name when SKU + subscription match).

**INT-006 — Concurrent deployment control.** Prevent two concurrent
decisions from consuming the same last unit of capacity/quota via
reservation-of-intent, optimistic concurrency, or equivalent.

**INT-007 — Partial-failure handling.** If quota is allocated but
deployment/association fails, record the partial state and either
compensate safely or raise a recoverable operational task.

**INT-008 — Two-scope inputs & outputs.** AEP deployments carry a
**domain group token** (DOM-001) in addition to customer/realm,
product, environment, and region inputs (INT-003). The required
output (INT-004) includes the resolved **CRV** (PLC-013) and **DPB**
(PLC-014): ig subscription, domain CRG set (CAP-025), zone spread,
quota-draw reference route (QUA-015). The pipeline enforces PLC-015
ordering — CRV resolution precedes DPB resolution — and treats the
CRV as cached input thereafter.

---

## 16. State & Data Requirements

**DAT-001 — Authoritative state store.** Maintain an authoritative
operational store (e.g., a storage-account table) separate from
transient API responses; it becomes the input to the next
region-selection cycle.

**DAT-002 — Minimum entities.** subscriptions; regions/zones;
SKUs/quota families; CRGs/reservations; provider/consumer sharing
relationships; allocated/associated VMs; quota pools + subscription
assignments; buffers/policies; customer seed records; Customer Region
Vector (CRV, PLC-013) per seed record; Domain Placement Binding
(DPB, PLC-014) per (domain × environment × region); domain registry
/ ig registry (DOM-001/002); per-domain CRG-set inventory mapped to
CAP-025 classes (prod / cvdr / drf); quota-group membership per
QUA-015; **source→destination DR index (DR-018)**; DR distribution
plans; deployment intents; reconciliation runs; alerts/exceptions;
audit events. *Derived value:* the per-geography customer count
`total_customers(g)` (PLC-012) is computed from customer seed records
and deployment intents; it is not stored as a configurable constant.

**DAT-003 — Freshness metadata.** Every observation carries
collection time, source, region, subscription, and status; derived
readiness references the source observations used.

**DAT-004 — Historic state.** Retain history sufficient to explain
capacity growth, quota changes, reservation cost, failed placements,
DR readiness, and policy changes. Forecasting extensions (FWD-001)
require per-domain ig trend records keyed
(domain × environment × region).

**DAT-005 — Configuration versioning.** Scope files/policies are
version-controlled; each reconciliation/deployment decision records
the config version used. (Reference repo:
`plat-saasa-azure-capacity-dev`.)

**DAT-006 — Schema compatibility.** API/config schema changes are
versioned and backward compatible for an approved transition period.

---

## 17. Observability & Alerting

**OBS-001 — Core metrics.** reserved quantity; allocated VM count;
associated VM count; available reserved; configured buffer; buffer
deficit/surplus; quota assigned/used/available; pooled quota
available; reservation utilisation %; estimated unused reservation
cost; reconciliation success/failure; Azure API throttling/latency;
state age; deployment blocks; DR capacity coverage;
**per-destination DR max-source coverage (DR-017)**;
**per-domain ig utilisation and zone distribution (PLC-016)**.

**OBS-002 — Required alerts.** production buffer below target; DR
bootstrap below target; quota below required/growth buffer;
reservation quantity > deployable quota; inability to raise a
reservation (needs Microsoft); Azure throttling causing stale state;
config references missing Azure resources;
unauthorised/unexpected sharing; reconciliation failures; stale
placement data; prolonged unused reservation cost;
desired-vs-actual divergence; **destination DR coverage below its
max protected source**; **combined region-load across a customer's
domains deviating beyond the PLC-016 observation threshold (C-15)**.

**OBS-003 — Alert context.** region, zone, subscription, SKU/family,
environment, domain, desired value, actual value, detection time,
correlation ID, and recommended owning team.

**OBS-004 — Dashboards.** regional, product, domain, subscription,
SKU, environment, and DR views; production readiness, DR readiness,
quota-pool health, and idle cost separately visible;
**source↔destination DR mapping view**;
**per-domain zone-distribution view**.

**OBS-005 — SLO reporting.** availability, reconciliation latency,
data freshness, decision latency, and failed-automation rates against
approved SLOs.

---

## 18. Governance, Security & Compliance

**GOV-001 — Least privilege.** Workload identities receive only the
roles/permissions required for inventory, quota management,
reservation management, sharing, and deployment validation.

**GOV-002 — Separation of duties.** Policy approval, production
execution, exception approval, and audit review are separable roles.

**GOV-003 — Scoped automation.** Automation is constrained by
tenant, management group, subscription, resource group, region,
zone, SKU, and the scope file.

**GOV-004 — Change approval.** High-impact changes — reducing
production protection, setting DR bootstrap to zero, deleting
reservations, broad sharing, reclaiming committed quota — require
approval.

**GOV-005 — Break-glass controls.** Break-glass requires authorised
identity, reason, bounded scope, expiry, and full audit logging.

**GOV-006 — Audit evidence.** Produce evidence of how production/DR
capacity is maintained, how deficiencies are detected, and how
changes are controlled (SOC 2-ready).

**GOV-007 — Policy exceptions.** Each exception has an owner, reason,
approved scope, start/expiry dates, compensating controls, and
review status.

**GOV-008 — Secrets & credentials.** No secrets in config files or
logs; prefer managed/workload identity.

**GOV-009 — Data classification.** Customer placement/workload
metadata is classified and protected per enterprise standards;
telemetry avoids unnecessary customer-sensitive content.

---

## 19. Reliability & Non-Functional Requirements

**NFR-001 — Availability.** The capacity decision path is not an
uncontrolled single point of failure for production provisioning;
degraded-mode behaviour is defined.

**NFR-002 — Consistency.** Concurrency control prevents
double-committing capacity/quota.

**NFR-003 — Performance.** Readiness responses meet an approved
latency target; long Azure changes return a tracked operation state
rather than blocking.

**NFR-004 — Scale.** Operates across **hundreds** of subscriptions,
multiple regions/zones, VM families, products, domains, and seed
records.

**NFR-005 — API-throttling resilience.** Use batching, caching,
backoff, jitter, retry limits, and per-scope rate control; avoid API
storms during a regional event.

**NFR-006 — Recoverability.** State store, config, and audit trail
support backup/restore and reconstruction of desired state.

**NFR-007 — Idempotency.** All mutating operations are idempotent or
protected by a durable operation key.

**NFR-008 — Testability.** Policies, formulas, reconciliation,
weighting, failover distribution, and compensation are independently
testable.

**NFR-009 — Simulation mode.** Support read-only/dry-run showing
intended reservation/quota/placement/cost changes without applying
them — including **DR failover simulation** per 13A.

**NFR-010 — Explainability.** Every decision exposes policy inputs,
state snapshot, formula, and reason code.

---

## 20. Operational Requirements

**OPS-001 — Runbooks** for: production buffer deficit; quota
exhaustion; reservation scale-up failure; stale state; deployment
blocked by missing reservation; DR declaration; CVAL
shutdown/disassociation; quota allocation to DR; reservation sharing
activation/revocation; reconciliation rollback/pause; manual
emergency override; regional recovery and failback; **standby DR
activation sequence (DR-019)**; **per-domain ig scaling events**.

**OPS-002 — Safe pause.** Operators can pause mutation while
retaining inventory and alerting.

**OPS-003 — Manual override.** Authorised operators set temporary
desired values with expiry + reason; the engine never overwrites an
active approved override.

**OPS-004 — Maintenance-window awareness.** Planned maintenance
changing VM allocation/association is visible to the engine to avoid
inappropriate scaling or alert noise.

**OPS-005 — Ownership.** Every region, subscription, reservation
scope, quota pool, alert, and exception has an owning team and
escalation route.

**OPS-006 — Naming convention & counter.** All managed **resource
groups, CRGs, and subscriptions** follow a deterministic, parseable
naming convention carrying an environment token, geography/region
token, purpose/scope token, domain token, and a zero-padded instance
**counter**, so resources are unambiguously identifiable and
enumerable. Reference patterns:

-   **Resource group:** `rg-odcr-<env>-<region>-<NN>` — e.g.
    `rg-odcr-prod-eus2-01`
-   **CRG:** `crg-<env>-<region>-<scope>`. The default scope is
    `zonal` (one group; zones are declared on the Azure resource, not
    in the name). Optional per-zone groups use `az1`, `az2`, `az3`.
    `reg` is only the no-zone exception in CAP-023 — e.g.
    `crg-pr-eus2-zonal`, `crg-pr-eus2-az1`, `crg-pr-eus2-reg`
-   **Subscription:** `sub-<org>-<domain>-<purpose>-<NN>` — e.g.
    `sub-jda-cld-cr-prod-wl-tms-wus2-01`

The convention, tokens, and counter width are configuration-driven
(**C-12**); the engine validates managed resources against it and
flags non-conforming names as governance exceptions. The default name
is the zonal group in CAP-023. `reg` names the no-zone exception
only.

---

## 21. Formulas & Calculation Reference

This section consolidates every calculation the engine uses into a
single reference. Formulas are numbered F.1–F.13. Where a formula
appears in v3.0's Appendix A under a legacy number (A.1–A.12), the
mapping is noted for traceability.

### 21.1 Capacity Sizing (per Domain × Environment)

These three formulas operate on a **(D, E)** operand — a single
domain group in a single environment within a region. Each domain's
ig (DOM-002) owns its own reservation and the reconciliation loop
(CAP-005) runs them independently per domain.

**F.1 — Reservation target** *(was A.1)*

    Target Reserved Capacity(D,E)
      = Allocated VM Count(D,E) + Buffer Target(D,E)

**Explanation.** The engine reserves enough capacity for every VM
currently running in the domain's ig **plus** a configurable buffer
(C-2) that covers deployment headroom, scale-out spikes, and
Azure-side reservation lead time. The buffer is never a fixed global
percentage — it is set per product/region/environment/SKU via the
scope file.

**F.2 — Reservation headroom** *(was A.2)*

    Reservation Headroom(D,E)
      = Reserved Quantity(D,E) − Allocated VM Count(D,E)

**Explanation.** Headroom is the unused portion of an existing
reservation. Positive headroom means spare capacity exists; zero or
negative headroom (possible during rapid scale-out) means the
reservation has not caught up to demand and the deficit formula (F.3)
triggers a reconciliation action.

**F.3 — Reservation deficit** *(was A.3)*

    Reservation Deficit(D,E)
      = max(0, Target Reserved Capacity(D,E) − Reserved Quantity(D,E))

**Explanation.** A deficit > 0 means the reservation is below its
target and must be increased. Reconciliation (CAP-005) acts on this
value: if > 0, it raises or creates a reservation in the domain's
CRG set (CAP-025); if 0, no action is needed. The `max(0, …)` guard
ensures the result is never negative — an over-provisioned
reservation is handled by the underutilisation review (FIN-005), not
by this formula.

### 21.2 Quota (per Domain × Environment)

**F.4 — Available subscription quota** *(was A.4)*

    Available Quota(D,E)
      = Assigned Regional VM-Family Quota(D,E)
        − Current Regional VM-Family Usage(D,E)

**Explanation.** Computed per ig subscription (DOM-002) against the
subscription's regional quota for the relevant VM family. Both the
VM-family cap and the total regional vCPU cap must be checked
(QUA-002). The ig draws quota from the customer's central quota
group (QUA-015) per region × VM-family cell.

**F.5 — Deployment quota deficit** *(was A.5)*

    Quota Deficit(D,E)
      = max(0, Requested Deployment Units(D,E)
              − Available Quota(D,E))

**Explanation.** A deficit > 0 blocks the deployment until additional
quota is allocated (from the pooled group, QUA-003, or requested
from Azure). The readiness gate (RDY-001) checks both quota caps
before returning `READY`.

### 21.3 DR Sizing

**F.6 — DR destination requirement (max, not sum)** *(was A.6)*

    Destination DR Requirement(d)
      = MAX over each non-concurrent source region s protected by d (
            Workload Portion of s assigned to destination d
        )

**Explanation.** Under the single-region-failure assumption
(DR-001), destination `d` never has to host more than one source
region's failover at a time, so it need only be sized for its
**largest** protected source — not the arithmetic sum of all of
them. The workload portions are domain-attributed. A conservative
`SUM` override is available (C-11) only where a customer/contract
explicitly requires protection against concurrent failures. See
Appendix D for the full derivation and worked example.

**F.7 — DR capacity gap** *(was A.7)*

    DR Capacity Gap(d)
      = max(0, Destination DR Requirement(d)
              − Usable Destination Capacity(d))

**Explanation.** A gap > 0 means the destination cannot absorb its
worst-case single-source failover; the staged acquisition sequence
(DR-006) is initiated. *Usable destination capacity* may include
approved bootstrap (DR Foundation, DR-021), available reservations,
releasable CVAL capacity, and capacity acquired through approved
sharing/expansion.

**F.8 — Shared-DR overcommit ratio (informational)** *(was A.8)*

    Overcommit Ratio(d)
      = SUM(source portions on d) / MAX(source portions on d)

**Explanation.** A ratio > 1 quantifies the capacity (and cost)
saved by max-not-sum sizing at destination `d`; it also equals the
exposure if the single-failure assumption is violated. Reported as
an observability metric (OBS-001) and flagged in the cost model
(FIN-008). A ratio of 1.0 means no overcommitment (single source
only or all sources equal).

### 21.4 Zone Distribution (per Domain)

**F.9 — Even zone-distribution target & skew** *(was A.9)*

    Even Zone Share            = 1 / Zone Count
                                 (e.g. 1/3 ≈ 33% in a 3-zone region)
    Target VMs per Zone(D,E,z) = round( VMs(D,E) / Zone Count )
    Zone Skew(D,E,z)           = VMs(D,E,z) − Target VMs per Zone(D,E,z)
    Max Skew(D,E)              = MAX over zones z of | Zone Skew(D,E,z) |
    Rebalance Trigger          = Max Skew(D,E) > Configured Skew Tolerance  (C-13)
    Preferred Placement Zone   = argmin over zones z of ( VMs(D,E,z) )
                                 # under-represented zone

**Explanation.** Placement first fills the **most under-represented**
zone so the domain workload trends toward `1/zone_count` per zone. A
deployment or growth event that would push `Max Skew` beyond the
configured tolerance (C-13) triggers a **rebalancing**
recommendation/action (PLC-011), subject to approval and Azure
feasibility. Even distribution bounds per-zone failover exposure and
keeps per-zone reservation sizing (CAP-023) balanced.

The zone distribution is applied **per domain** (PLC-016). The
region maintains a **combined-load observation** across all domains:

    RegionZoneLoad(R,E,z) = Σ_D VMs(D,E,R,z)

This combined load is an **observation/alerting unit only**
(OBS-001/002, C-15) — it never triggers reservation actions across
domains.

### 21.5 Placement Scoring (Customer Aggregate)

**F.10 — Geography customer count & γ fairness term** *(was A.10)*

    Total Customers(g)   = COUNT DISTINCT customers c
                           where c has ≥ 1 environment (Prod, CVAL or DR)
                           provisioned or being deployed in any region r ∈ g
    Env Customers(r,env) = customers with environment env in region r
                           (prod / nonprod / dr customer count)

    γ(r,env) = 1                                                       if Total Customers(g) = 0
             = Clamp( 1 − Env Customers(r,env) / Total Customers(g),
                      0, 1 )                                           otherwise

**Explanation.** The denominator is one geography-level count, shared
by PS_Prod, PS_NonProd and PS_DR; the numerator is the
environment-specific count for the region being scored, and *g* is
the geography of that region. The count increments when a new
customer environment is provisioned or deployed in the geography
(PLC-012). The `Clamp(…, 0, 1)` ensures the term stays in [0, 1].

**Placement scores** (PLC-007/008) use a weighted combination at
customer-aggregate scope:

    Score_Pool(C,R) = Σ_f  w_f · norm_f(Pool_f(C,R))

where the factors `Pool_f` include: allocated capacity, available
reservation, quota availability, buffers, expected DR contribution
(F.6), zone support, state freshness, and γ fairness (above). The
weights `w_f` are configurable (`PlacementPolicy`) and must sum to
1.0. Scoring weights are validated at policy load time (sum ≠ 1.0
→ reject).

### 21.6 Two-Scope CRV Resolution

**F.11 — Two-scope region-selection formula sets** *(was A.11)*

**Formula Set 1 — Exact-Region Path (PLC-001 default):**

    INPUT   : (C, G, R_p supplied)
    1. VALIDATE R_p against HC + PlacementPolicy
       # Prod is input constant, not scored
    2. Score_Pool(C,R) = Σ_f w_f · norm_f(Pool_f(C,R))
       # PLC-007 at CUSTOMER aggregate
       Pool_f ∈ {allocated, availableRes, quotaAvail, buffers,
                 expectedDR (F.6), zoneSupport, freshness,
                 γ fairness (F.10)}
       # Σ over customer's domains
    3. Apply distribution model (REG-003):
       2-region   → R_c = R_d = single remaining region  (PLC-010a)
       3-region   → R_c, R_d weighted among remaining;
                    optional separation              (PLC-010)
       cross-geo  → R_c = R_p (ME, separate CRGs);
                    R_d ∈ Europe weighted              (PLC-010b)
    OUTPUT  : CRV(C,G) = (G, mod, INPUT R_p, R_c, R_d)
              # determines CVAL + DR only

**Formula Set 2 — Geography Path (PLC-002 exception):**

    INPUT   : (C, G) only (exception-approved, customer-acknowledged)
    1. CANDIDATES(G) = in-scope regions of G (REG-001) filtered by HC
    2. R_p = argmin-risk suitable candidate over CANDIDATES
       # same Score_Pool(C,R) at customer aggregate — determines PROD
       if R_p lacks capacity → alarm/exception, still place CVAL/DR
       (PLC-008)
    3. Derive R_c, R_d per distribution model
       (identical to Set 1 step 3)
    OUTPUT  : CRV(C,G) = (G, mod, R_p, R_c, R_d)
              # determines ALL THREE regions

**Explanation.** Both paths apply the same weighted capacity
placement model and the same Hard Constraints. Set 1 scores only
CVAL and DR candidates (Prod is a validated input); Set 2 scores all
three. Both converge on the Domain Placement Binding (F.12) via the
PLC-015 gate.

### 21.7 Domain Placement Binding (DPB)

**F.12 — Domain Placement Binding formulas** *(was A.12)*

    For each (D, E) with R ≡ CRV(C,G).E pre-bound (PLC-015 gate):
      ig(D,E)             = Lookup(C, D, E, R)
                            # C-12 + shard registry; deterministic
      CRG set(D,E)        = CAP-025 per-domain sets
                            (prod-dedicated | cvdr shared | drf)
      TargetReserved(D,E) = AllocatedVMs(D,E) + Buffer(D,E)        # F.1
      Headroom(D,E)       = Reserved(D,E) − AllocatedVMs(D,E)      # F.2
      Deficit(D,E)        = max(0, TargetReserved − Reserved)       # F.3
      TargetVMs(D,E,z)    = round( VMs(D,E) / ZoneCount(R) )       # F.9
                            per-DOMAIN operand (PLC-016)
      RegionZoneLoad(R,E,z) = Σ_D VMs(D,E,R,z)
                            # region OBSERVER only — no action
      AvailableQuota(D,E) = min(VM-family cap, total regional cap)
                            of ig(D,E)                              # F.4/QUA-002
      QuotaDeficit(D,E)   = max(0, Requested(D,E) − AvailableQuota) # F.5
      Draw(D,E)           = central quota group (QUA-015),
                            region × family cell
      Replenish           = utilization ≥ GROUP_REPLENISH_THRESHOLD (85%)
                            or ≥ SUB_REPLENISH_THRESHOLD (85%)

**Explanation.** The DPB is deterministic — no region weighting
occurs at domain scope; the region always comes from the CRV
(PLC-015 gate). Each formula in F.12 re-parameterises the generic
single-operand formulas (F.1–F.5, F.9) with the domain×environment
scope `(D,E)`. The replenishment thresholds (85%) are configurable
reference values from the system configuration; they trigger
proactive quota replenishment before the ig runs dry.

### 21.8 Reconciliation Note

**F.13 — Formula lineage.** Formulas F.1–F.9 are the **generic
single-operand** forms (reservation target, headroom, deficit, quota
availability, quota deficit, DR sizing, overcommit ratio, zone
distribution). F.12 (DPB) **re-parameterises** every generic formula
with the domain×environment scope `(D,E)` and wires them into the
deployment pipeline. F.10–F.11 operate at **customer aggregate**
scope (fairness scoring and CRV resolution). There is no conflict
between the generic and domain-scoped forms — F.12 is the
domain-specific instantiation of F.1–F.9, not a separate set.

---

## 22. Acceptance Criteria

The baseline is implementable when all are demonstrated:

1.  Inventory of reservations, allocated VMs, associated VMs, quota,
    sharing, and configuration across an approved scope.
2.  Engine computes `allocated + buffer` and reconciles reservation
    quantity.
3.  A deallocated-but-associated VM does not unnecessarily preserve
    reservation quantity unless policy requires.
4.  Detects a missing Azure reservation referenced in config
    **before** production deployment.
5.  Blocks or safely handles a deployment with insufficient
    consumer-subscription quota.
6.  Allocates and reclaims pooled quota without dropping any
    subscription below protected requirements.
7.  Prevents concurrent requests from double-committing capacity or
    quota.
8.  Exposes a fresh, machine-readable readiness result to
    AEP/provisioning.
9.  Creates and reuses a customer placement seed record.
10. Simulates a single-region DR event and computes **distributed
    destination requirements using max-not-sum sizing (DR-017)**.
11. Identifies releasable CVAL capacity for DR and requires an
    authorised trigger before service-impacting action.
12. Reports idle reservation cost and protection deficits.
13. Records complete audit events for automated and manual changes.
14. Enters a safe degraded state during Azure API throttling and
    reports stale data.
15. Supports dry-run evaluation before applying policy changes.
16. **Maintains and queries the source→destination DR index (DR-018)
    and activates the correct standby set (DR-019) for a simulated
    single-region failure.**
17. **Excludes Availability-Set VMs from reservation management and
    records the deallocate/redeploy-to-AZ onboarding precondition
    (CAP-020/CAP-021).**
18. **Initialises a seed matrix of count-0 reservations per eligible
    SKU/AZ under product-team budget governance (CAP-022) and, on
    reactive discovery of an unmanaged allocated SKU/AZ,
    auto-creates the reservation while raising a scope-file
    governance item (CAP-024).**
19. **Maintains one zonal CRG per environment, with one reservation
    per VM size per zone (CAP-023), and validates resources against
    the naming convention (OPS-006/C-12).** A no-zone group is the
    exception for SKUs that cannot take a zonal reservation.
20. **Places new VMs toward an even ≈1/zone_count per-zone
    distribution and raises a rebalancing action when zone skew
    exceeds the configured tolerance (PLC-011).**
21. **Right-sizes a retained reservation to `allocated + buffer`
    after a decommission automatically, while routing
    retirement/deletion/scope-removal through the approved
    decommissioning workflow (CAP-008/CAP-010).**
22. **Resolves the two-scope flow end-to-end:** builds/reuses the
    Customer Region Vector (PLC-013) via the exact-region path
    (CVAL+DR derived) and the geography path (Prod+CVAL+DR derived),
    then resolves Domain Placement Bindings (PLC-014) for a
    multi-domain customer (TMS + WMS) with identical CRV regions and
    separate igs.
23. **Maintains per-domain CRG sets per CAP-025** — prod-dedicated,
    CVAL/DR shared, and DR Foundation sets — for the same
    domain×region combination, and validates domain isolation
    (DOM-004).
24. **Bootstraps DR solely from the DR Foundation** (DR-021) in a
    simulated single-region event and then demonstrates
    CVAL-extension scaling into the domain's CVAL/DR shared CRG
    (gated on POC-001/DEP-001).
25. **Draws quota for every domain ig from the customer's central
    quota group** (QUA-015) and triggers replenishment when
    `GROUP_REPLENISH_THRESHOLD`/`SUB_REPLENISH_THRESHOLD` (85%) are
    hit.
26. **Runs the forward-item evaluation** (Section 28) as a dry-run:
    capacity forecast at customer aggregate × domain ig and placement
    optimization re-scored under the two-scope model.

---

## 23. Delivery Phases

### Phase 1 — Capacity Visibility & Production Protection

Read-only capacity/quota inventory · managed scope file · production
reservation reconciliation (`allocated + buffer`) · missing-resource
validation · alerts, audit logging, dashboards, dry-run · AEP
readiness API. **Objective:** protect production first.

### Phase 2 — Quota Pool Automation

Quota-group inventory · dynamic allocation & reclamation · production
growth buffer · quota-request workflow · correlated
quota–reservation readiness. **Objective:** treat quota as a
centrally governed resource (quota-as-governor).

### Phase 3 — Placement & Customer Seed

Exact production-region input · seed-record creation & reuse ·
CVAL/DR weighted placement · **CVAL/DR co-location (PLC-010)** ·
concurrent-deployment controls · capacity commitment workflow.
**Objective:** deterministic customer placement.

### Phase 4 — Distributed DR Capacity Management

Destination workload distribution · **source→destination DR index
(DR-018)** · **reciprocal multi-source hosting (DR-016)** ·
**max-not-sum sizing (DR-017)** · CVAL release modelling · bootstrap
& recovery waves · **standby activation (DR-019)** · DR declaration
workflow · capacity sharing + DR quota allocation (post-POC) · DR
simulation & compliance evidence. **Objective:** enterprise-scale DR
capacity governance.

### Phase 5 — Multi-Domain Model & Two-Scope Binding

Domain-group taxonomy registry (DOM-001, DEC-004) · per-domain ig
and subscription provisioning (DOM-002, C-12 extension) · per-domain
CRG sets (CAP-025) · Customer Region Vector build/reuse with the two
input paths (PLC-013) · Domain Placement Binding resolution
(PLC-014) · central quota group membership across domain
subscriptions (QUA-015) · DR Foundation provisioning per domain +
CVAL/DR shared set (DR-021) · combined region-load observation
(PLC-016, OBS). **Objective:** one customer, many domains — region
once, capacity per domain.

---

## 24. Configurable Items

| #    | Item                                          | Current direction                                                                    | Status                                 |
|------|-----------------------------------------------|--------------------------------------------------------------------------------------|----------------------------------------|
| C-1  | **DR bootstrap capacity**                     | Lean, "enough to bootstrap"; discussed 30–40% → 10–20% → ~5% → used-is-free          | Configurable — no fixed value          |
| C-2  | **Production reservation buffer**             | `allocated + buffer`; ref impl buffer = 1 in dev                                     | Configurable by product/region/env/SKU |
| C-3  | **Production quota buffer**                   | Headroom above usage to support growth                                               | Configurable — value TBD               |
| C-4  | **Reconciliation frequency**                  | Ref impl every 6 minutes                                                             | Configurable — prod value TBD          |
| C-5  | **Failback model**                            | Prefer ~1 year run; ~30-day failback alternative                                     | Business decision                      |
| C-6  | **Onboarding selection mode**                 | Exact production region (default); geography (exception)                             | Configurable + exception policy        |
| C-7  | **Quota grouping model**                      | One Quota Group object per subscription; each transfer is one region × one VM family; accounting covers prod, non-prod, and DR in that cell | Configurable within Azure limits       |
| C-8  | **Region catalogue & flags**                  | Five geographies (US 3-region; Europe/Australia/Asia Pacific 2-region; **Middle East cross-geo DR** — Prod+CVAL local, DR in Europe, DR-020/PLC-010b); restricted/standard classes; distribution model; per-country `DR_NOT_OFFERED` (DR-014) | Configurable                           |
| C-9  | **Reservation over-allocation**               | Track allocated; allow over-association                                              | Configurable policy                    |
| C-10 | **DR drill duration/rotation**                | Annual drill; role flip                                                              | Business decision                      |
| C-11 | **DR sizing basis**                           | **Max over non-concurrent sources** (DR-017); sum available as conservative override | Configurable — max is default          |
| C-12 | **Resource naming convention & counter**      | Deterministic RG/CRG/subscription naming with env/region/purpose/domain tokens + zero-padded instance counter (OPS-006). Default CRG is zonal (`az` set at creation). The `reg` token is only the no-zone exception in CAP-023, not a region-wide pool | Configurable                           |
| C-13 | **Zone-distribution target & tolerance**      | Even ≈`1/zone_count` per zone (≈33% in three-zone regions) with configurable skew tolerance before rebalancing (PLC-011; per-domain under PLC-016) | Configurable                           |
| C-14 | **Domain-group taxonomy tokens**              | `wl-*` workload-domain tokens (e.g. TMS, WMS) per customer; optional function-group `<fn>` refinement; resolved per DEC-004 | Configurable                           |
| C-15 | **Combined region-load observation threshold** | Deviation threshold at which the engine raises a combined region-load alert across a customer's domains (PLC-016) | Configurable                           |
| C-16 | **DR Foundation sizing basis**                | Configurable bootstrap per product/domain/region/zone/SKU per ENV-005/DR-007 (never a fixed percentage) | Configurable                           |

---

## 25. Pending Decisions & Mandatory POCs

| ID          | Item                                             | Required outcome                                                                                                                                                         |
|-------------|--------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **POC-001** | Capacity Reservation **Sharing quota behaviour** | **Documented (24 Sep 2026):** the consumer subscription must hold its own quota to deploy into a shared group; the provider must hold quota to create or grow the reservation. Remaining work: confirm behaviour on the API version in use. Sharing stays Preview (CAP-013, DEP-001). |
| POC-002     | Sharing **consumption order**                    | How Azure allocates shared capacity when multiple consumers request the same SKU.                                                                                        |
| POC-003     | **Zone/subscription boundaries**                 | Confirm logical-to-physical zone mapping when a consumer deploys into a provider's zonal reservation (CAP-016). Sharing combinations stay inside the preview limits in CAP-013. |
| POC-004     | **Change under throttling**                      | Safe reconciliation + retry behaviour during Azure API throttling.                                                                                                       |
| POC-005     | **VM association/shutdown states**               | Reservation/guarantee behaviour across allocated/stopped/deallocated/associated/disassociated.                                                                           |
| POC-006     | **DR subscription topology**                     | Dedicated DR subscription+cluster vs shared production subscription model.                                                                                               |
| POC-007     | **Bootstrap sizing**                             | Minimum bootstrap per product incl. required control-plane nodes/SKUs.                                                                                                   |
| POC-008     | **Production quota buffer**                      | Initial buffer policies by product/VM family.                                                                                                                            |
| POC-009     | **Production reservation buffer**                | Initial reserved-capacity buffer by product/region/zone/SKU.                                                                                                             |
| POC-010     | **Reconciliation interval**                      | Production interval after API + cost testing.                                                                                                                            |
| POC-011     | **Max-not-sum overcommit safety**                | Validate that shared/overcommitted DR reservations (DR-017) behave correctly when a standby set activates, and quantify residual risk if two regions ever fail together. |
| POC-012     | **Domain-scoped CRG sharing**                    | Validate same-domain CVAL/DR-shared CRG consumption (CAP-025, DOM-004): consumer-subscription quota, logical-zone mapping (CAP-016), and revocation within the 100-consumer scope; confirm cross-domain isolation. |
| POC-013     | **Two-scope flow against a live multi-domain customer** | End-to-end PLC-013/PLC-014 on a TMS+WMS customer: exact-region and geography paths converge identically; DPB per domain isolates ig/CRG/quota; readiness gates hold per domain. |
| **DEC-001** | **Middle East DR offering — RESOLVED**           | **Decided (11 Sep 2026):** DR is offered for Middle East cross-geo to Europe (DR-020, PLC-010b) — Prod+CVAL local, DR in a weighted-selected Europe Standard region. Per-country `DR_NOT_OFFERED` (DR-014) retained; data-residency clearance assumed (A-ME1). |
| DEC-002     | **DR drill duration & failback**                 | Extended run vs earlier failback.                                                                                                                                        |
| DEC-003     | **Geography exception approval**                 | Approver + binding customer acknowledgement for geography-only onboarding.                                                                                               |
| DEC-004     | **Domain-group taxonomy**                        | Decide `wl-*` workload-domain token set per customer (TMS, WMS, …) and whether function-group `<fn>` tokens are required; controls C-14 and the DPB key (PLC-014). |
| **DEP-001** | **Azure feature maturity**                       | Track Capacity Reservation Sharing preview→GA status and approved enterprise-usage conditions.                                                                           |

---

## 26. Assumptions, Constraints & Risks

### Assumptions

-   Quota lives on the **deploying subscription**, not on the
    reservation group or the Quota Group limit (QUA-013, documented).
    Both the VM-family cap and the total regional vCPU cap must be
    free.
-   A down region's VMs/quota/reservations remain bound as left and
    are not reusable during the outage.
-   Customer workloads distribute across 3–4 regions per geography,
    enabling portion-based DR.
-   **Only one region in a geography fails at a time** — the basis
    for max-not-sum DR sizing (DR-001/DR-017).
-   A customer's **region binding (CRV) is shared by all its domain
    groups** (PLC-013); each domain's ig/capacity is isolated
    (DOM-002/004). DR Foundation bootstrap is sized per
    ENV-005/DR-007 and does **not** depend on sharing availability
    (DR-021). Central quota group covers all domain subscriptions per
    region × family cell (QUA-015).
-   **A-ME1 — Middle East cross-geo DR residency clearance.** The
    Middle East cross-geography DR model (DR-020, PLC-010b) assumes
    Legal has cleared cross-border replication/failover of the
    applicable Middle East customer classes to Europe. Where residency
    clearance is absent for a given country, the per-country
    `DR_NOT_OFFERED` flag (DR-014) applies and no Europe DR region is
    assigned. *Risk: if clearance is narrower than assumed, the
    served Middle East DR population shrinks and some customers revert
    to Prod+CVAL-only local placement.*

### Constraints

-   Reservations cannot be shared across regions or availability
    zones.
-   Any reservation change must start in Azure before the scope file.
-   Non-prod/prod and DR/prod cannot share capacity; DR may share
    with non-prod.
-   No multi-cloud DR; global Azure outage is not an addressable
    failure mode.

### Key Risks

| Risk                                     | Impact                                      | Mitigation                                                                                           |
|------------------------------------------|---------------------------------------------|------------------------------------------------------------------------------------------------------|
| Sharing still Preview                    | Production must not depend on cross-subscription sharing | Same-subscription reservation is the production path (CAP-013); track GA on DEP-001               |
| Cost of DR reserve                       | Multi-region may be cancelled               | Lean bootstrap + configurable buffers + distributed DR + max-not-sum sizing                          |
| **Two concurrent region failures**       | Overcommitted DR (DR-017) cannot cover both | Accept under DR-001; quantify via POC-011; conservative sum override (C-11) if a customer demands it |
| API throttling during regional event     | Slow recovery                               | Bootstrap headroom + staged acquisition + backoff                                                    |
| Business volatility                      | Requirements churn                          | Configuration-driven design + living document                                                        |
| Two-region concentration                 | Cannot guarantee failover                   | Push for 3–4 regions per geography                                                                   |
| Preview-feature dependency               | Design lock delayed                         | Track DEP-001; design to work with and without sharing                                               |
| **Middle East cross-geo DR residency** (A-ME1) | Some ME customers cannot legally DR to Europe | Per-country `DR_NOT_OFFERED` (DR-014); confirm Legal clearance per customer class                  |
| **Europe absorbs Middle East DR load**   | Europe DR capacity/quota pressure            | Include ME protected portion in Europe HC-6/HC-7 floors; weighted destination selection; capacity forecasting |
| **Domain-group proliferation**           | CRG/subscription/ig sprawl                  | Domain registry governance (DOM-002), deterministic naming (C-12), CAP-025 structure; POC-013        |
| **Cross-domain sharing mis-grant**       | ENV-003 violation / isolation breach        | Domain-bounded grants only (DOM-004), audit with domain token, reconciliation (CAP-005)              |
| **Two-scope drift**                      | Domain ig placed outside customer CRV       | PLC-015 gate + RDY-004 freshness on CRV reads; PLC-005 migration workflow                           |
| **DR Foundation under-sized**            | Bootstrap insufficient for P0 waves         | Configurable sizing (C-16) with structured validation (POC-007); staged acquisition (DR-006)         |

---

## 27. Final Requirement Summary

The approved direction is a **dynamic, policy-driven Capacity &
Quota Management Engine**, not a static pool of large DR
reservations. The engine shall:

-   protect production with **configurable** reservation and quota
    buffers;
-   base reservations on **allocated VMs + buffer**;
-   manage quota and reservations **separately** but correlate them
    before deployment;
-   **pool and allocate** quota under central governance
    (quota-as-governor);
-   maintain a **minimal, approved DR bootstrap** rather than a full
    production copy;
-   use **CVAL and distributed regional capacity** to support
    single-region failover, with **reciprocal multi-source hosting**
    and **max-not-sum sizing**;
-   provide **fresh state** to region selection and AEP;
-   persist an authoritative **customer placement seed** and a
    **source→destination DR index**;
-   support **reservation sharing** only after POC + enterprise
    approval;
-   prevent **stale, double-committed, or unaudited** decisions;
-   expose **cost, readiness, risk, and compliance** evidence; and
-   retain **configuration flexibility** because regional, legal,
    product, and business policies change.

The engine treats a customer as **one placement identity with many
capacity lanes**: region selection is bound once per customer into a
**Customer Region Vector** (PLC-013 — exact-region path determines
CVAL+DR; geography path determines all three), while **Instance
Groups and capacity are domain-group-scoped** (PLC-014) with
per-domain CRG sets (CAP-025), domain-bounded sharing (DOM-004), a
**DR Foundation** bootstrap layer extended by same-domain CVAL/DR
shared capacity (DR-021), and a **central quota group** across all
domain subscriptions replenished at configurable thresholds
(QUA-015). Hard Constraints are unchanged. Forward items (capacity
forecasting, placement optimization) are evaluated in Section 28.

The remaining major architectural risks are **Capacity Reservation
Sharing still in Preview (DEP-001; production uses a
same-subscription reservation)**, **DR subscription topology
(POC-006)**, **bootstrap sizing (POC-007)**, and **max-not-sum
overcommit safety (POC-011)**. Consumer quota on a shared
reservation is documented (QUA-013). **Middle East DR policy
(DEC-001) is resolved** — DR is offered cross-geo to Europe
(DR-020, PLC-010b); the residual item is legal residency clearance
per customer class (A-ME1) and any per-country `DR_NOT_OFFERED`
carve-outs (DR-014).

---

## 28. Forward-Items Impact Evaluation

*(Assesses how the multi-domain/two-scope model changes the forward
roadmap items. Status labels follow Appendix C.)*

**FWD-001 — Capacity forecasting (extends DAT-004).** The two-scope
model changes the forecasting **grain**: forecasts are computed at
**customer aggregate (CRV)** for region-level demand and at **domain
ig (DPB)** for CRG/quota sizing. Forecasting therefore requires:
per-domain ig trend records (allocated, buffer, utilisation) keyed
(domain × environment × region); roll-up to customer and region
aggregate; and feed into PLC-016 combined region-load observation and
QUA-015 replenishment planning. Status: **Baseline-design change
required** (amendments to DAT-004; extends forward forecast model).

**FWD-002 — Placement optimization (extends PLC-007/008 scoring).**
The weighted placement model is **re-scoped to the customer scope
only** (CRV selection: run once per customer × geography —
exact-region path scores CVAL/DR candidates; geography path scores
all three). Domain scope (DPB) is **deterministic**, so optimisation
levers move to: (a) customer aggregate weighting factors (allocated,
available reservation, quota, buffers, expected DR, zone support, γ
fairness — PLC-012 remains the fairness term); (b) per-domain
zone-balancing (PLC-016); and (c) load distribution across a
customer's domains within the CRV regions. Status:
**Configurable/design change**; the Calculation Logic Reference must
be re-scoped to two-scope operands.

**FWD-003 — Automated quota management (extends QUA-010).** Central
quota group across domain subscriptions (QUA-015) is the substrate
for automating intergroup transfers at configurable thresholds;
forward item is unchanged in principle but now operates per
region × family cell with domain-aware draws. Status: **Unchanged
direction; grain updated**.

**FWD-004 — Cost modelling (extends FIN-001/004/008).** Multi-domain
ig splits cost attribution by domain while CRV binds regions once;
FinOps attribution keys become (customer, domain, environment,
region). Shared CVAL/DR CRG cost is single-counted per domain; DR
Foundation cost is attributed to the DR function per domain
(FIN-004). Status: **Configurable — attribution grain extended**.

**FWD-005 — Placement engine / hard-coded loops (forward
architecture).** The two-phase CRV→DPB pipeline (PLC-015) becomes
the placement engine's core loop; forward optimisation (e.g.,
migration window planning, PLC-005) operates on the CRV + DPB state
store (DAT-002). Status: **Design input to forward placement
engine**.

**FWD-006 — Exosphere / Stratosphere integration (forward).**
Platform consumers consume the AEP contract (INT-008): CRV + DPB
resolution, readiness (RDY-001), and per-domain outputs. No change
to integration mechanism; payload shape updated with domain token.
Status: **External dependency — payload contract change**.

**FWD-007 — Capacity buffer calculation (extends CAP-003).** Buffer
policy remains `allocated + buffer` per domain ig (CAP-025); region
aggregate buffers are **observed, not reserved** (PLC-016). Status:
**Configurable — scoped to domain**.

---

## Appendix A — Worked Cost Examples (illustrative)

These are the review-time back-of-envelope figures that drove the
shift to a lean DR model. They are **illustrative planning
numbers**, not billing quotes.

| Scenario                               | Basis                                                 | Approx. cost               |
|----------------------------------------|-------------------------------------------------------|-----------------------------|
| Reference block                        | 500 × E32 ≈ 16,000 cores ≈ 2 production subscriptions | —                          |
| 30% empty DR reserve (reference block) | 150 VMs held idle                                     | ~$54K/month for the block  |
| 10% DR reserve (reference block)       | 50 VMs                                                | lower, but still material  |
| 5% DR reserve (reference block)        | ~$78K/year for 16,000 cores / 500×E32                 | "used = effectively free"  |
| Heritage skeleton                      | 1 VM of a specific SKU kept warm                      | ~$500K/year                |
| Platform-wide 30% DR reserve           | Scaled across ~10× the reference subscriptions        | **~$1.5M–$5M/year**        |

**Takeaway:** a fixed 30–40% empty DR reserve is prohibitive at
platform scale and would risk cancellation of multi-region. Bootstrap
capacity that is *actually used* to stand up control planes is
effectively free, so DR should hold only the minimum needed to
bootstrap and scale via staged acquisition (DR-006).

---

## Appendix B — Requirement Status Labels

-   **Baseline** — agreed direction, suitable for design.
-   **Configurable** — required capability; numeric value/policy not
    fixed.
-   **POC validation required** — behaviour must be verified before
    production dependency.
-   **Business decision required** — design must support alternatives
    until policy is approved.
-   **External dependency** — depends on Azure feature maturity,
    Microsoft clarification, legal direction, or another platform
    team.

---

## Appendix C — DR Sizing Formula Correction (Max vs Sum)

### C.1 The problem with the original formula

Version 2.0 stated the destination requirement as:

    Destination DR Requirement
      = Sum of Source Workload Portions Assigned to Destination
      ❌ over-provisions

This **sum** implicitly assumes that *every* source region a
destination protects could fail **at the same time**, so the
destination must hold enough standby capacity for **all of them
simultaneously**. That directly contradicts the programme's own
planning assumption (DR-001): **only one region in a geography fails
at a time.**

Sizing for the sum therefore buys capacity that, by our own design
assumption, will **never be used concurrently** — reintroducing
exactly the idle-reserve cost the lean bootstrap model was created to
eliminate (FIN-006).

### C.2 The corrected formula

    Destination DR Requirement(d)
      = MAX over non-concurrent sources s protected by d
            ( portion(s → d) )
      ✅ right-sized

Under single-failure, destination `d` only ever absorbs **one**
source at a time, so it needs standby capacity for the **largest**
source it protects — never the total. The standby "slots" are
**shared** (overcommitted) across the mutually-exclusive failure
events. This is the DR analogue of overbooking a resource that can
only be claimed by one tenant at a time.

### C.3 Worked example (from the reviewed diagram)

Suppose destination **Region 2** holds DR standby for customers
whose production is in **Region 1** and **Region 3**:

| Source protected by R2   | Failover portion landing in R2 (E32 cores) |
|--------------------------|--------------------------------------------|
| Region 1 (Cust1 + Cust5) | 120                                        |
| Region 3 (Cust6)         | 80                                         |

**Old (sum) sizing:**

    Requirement(R2) = 120 + 80 = 200 cores reserved as standby

**New (max) sizing:**

    Requirement(R2) = max(120, 80) = 120 cores reserved as standby

**Saving at R2:** 200 → 120 = **80 cores (40%) removed** with no
loss of protection, because R1 and R3 do not fail together (DR-001).

**Overcommit ratio (F.8):**

    Overcommit Ratio(R2) = 200 / 120 ≈ 1.67

i.e., R2's shared standby is 1.67× oversubscribed — the measure of
both the saving *and* the exposure if two regions ever failed at
once.

### C.4 Scaling the saving

Extrapolating the Appendix A economics: if the naïve sum model
implied ~$1.5M–$5M/year of platform-wide idle DR reserve, then in a
3-region geography where each destination protects two roughly
comparable sources, max-not-sum sizing removes on the order of
**~40–50% of the standby reserve** — potentially
**$0.6M–$2.5M/year** — while still satisfying the single-failure
SLA.

### C.5 Guardrails on the correction

1.  **Assumption-bound.** The max model is valid **only** while
    DR-001 (single-region failure) holds. If the business ever
    mandates concurrent-failure protection for a specific
    customer/geography, use the `SUM` override (C-11) for that
    scope.
2.  **Quantify residual risk.** POC-011 validates activation
    behaviour of overcommitted standby and quantifies the exposure
    (= overcommit ratio) so leadership signs off knowingly.
3.  **Observe coverage.** OBS-001/002 must alert when a
    destination's usable capacity drops below its **max protected
    source**, not below the sum.
4.  **Zone/region integrity preserved.** Max-not-sum changes only
    *how much* standby to hold per destination; it does **not**
    relax the region/zone isolation rules (CAP-011/CAP-012) or the
    separation constraints (ENV-003).
5.  **Reversibility.** Because the basis is configurable (C-11), the
    estate can move between max and sum per scope without code
    changes (FIN-002).

---

*End of ACRME Requirements Baseline v4.0*
