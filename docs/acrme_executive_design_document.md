**INTERNAL — RESTRICTED**

# Azure Capacity Reservation Management Engine (ACRME)

**Executive Design Document — Prepared for Leadership Review**

Prepared from the Production-Readiness Review and Final Architecture and the independent Fact-Check Report. For leadership decision-making. **CONFIDENTIAL — Do not distribute outside authorised recipients.**

---

## 1. Executive Summary

### What ACRME Is

The Azure Capacity Reservation Management Engine (ACRME) is a central control system that books, shares, and protects cloud server capacity across many customer accounts and locations. Think of it as a reservation desk for cloud computing power: it ensures that when a customer needs to start servers — for everyday work or for disaster recovery — the capacity has already been secured, rather than hoping the cloud provider still has free capacity at that moment.

### The Business Problem

Cloud capacity is not guaranteed unless it is reserved in advance. Without a reservation, a customer can attempt to start servers and discover that none are available — especially during a regional outage when many organisations are competing for the same spare capacity. Reserving capacity costs money whether or not it is used, so over-reserving wastes budget and under-reserving creates service risk. Managing these trade-offs manually across dozens of customers and regions does not scale, and getting it wrong can mean failed disaster recoveries, service disruptions, and wasted cloud spend.

### What ACRME Does

ACRME solves this by acting as an intelligent reservation and allocation engine. It maintains shared pools of reserved capacity, decides which location is best for each customer, continuously monitors whether enough capacity is held, increases reservations when demand rises, and protects a dedicated floor of capacity for disaster recovery. High-risk actions require human approval. Every decision is recorded for audit.

### Where the Programme Stands

The architectural design is complete and has been independently reviewed. A fact-check against Microsoft's published documentation identified and corrected seven gaps. Validation testing is planned but has not yet been executed end-to-end. The Design Review Council's formal position is clear: ACRME is not ready for unrestricted, autonomous disaster-recovery automation. A conditional pilot for non-destructive, operator-approved scenarios is supportable once the pilot gates in this document are met. Overall readiness for full production automation is assessed at approximately four out of ten on the internal scorecard — strong on design coverage, weak on executed proof and unresolved blockers.

### Top Three Decisions Leadership Must Make

> **DECISION — Leadership Decision Required**
>
> - **Accept the Preview feature dependency.** The shared reservation capability that ACRME depends on is still a Microsoft Preview feature. Microsoft can change or withdraw it. Proceeding means formally accepting that risk — or waiting for general availability.
> - **Approve the permissions model approach.** ACRME needs controlled rights to act inside customer cloud accounts. The exact permissions model is the number-one unresolved production blocker and involves real security trade-offs. A security review and formal approval are required.
> - **Set the disaster recovery floor policy.** How much capacity is held in reserve for disaster recovery is a business decision, not an engineering one. The design currently uses a placeholder range of 30–40%. Leadership must set this based on customer service commitments and risk appetite.

### Overall Confidence

Confidence in the design quality is high. Confidence in production readiness for autonomous disaster recovery is low until validation is complete and the named blockers are closed. Confidence in a carefully bounded pilot — with human approval on every material action — is moderate and rising as gates are closed. This document does not overstate maturity. Where something is unproven, it is stated as unproven.

---

## 2. The Business Problem

Cloud computing gives organisations flexibility, but it does not automatically guarantee that servers will be available the moment they are needed. Microsoft Azure, like other major cloud providers, only guarantees capacity when it has been reserved in advance. Without a reservation, starting a server is a best-effort request. Under normal conditions this usually succeeds. Under stress — a regional outage, a surge in demand, or a large recovery exercise — it can fail.

### The Cost of Reserving Capacity

Reserved capacity is billed whether or not it is used. That creates a permanent tension. Reserve too much and the organisation pays for empty capacity. Reserve too little and a critical workload may be unable to start when it matters most. For a single team managing a handful of systems, this trade-off can be handled with spreadsheets and judgement. Across dozens of customers, multiple environments, and several geographic locations, manual management becomes unreliable and expensive.

### Why Disaster Recovery Makes This Harder

Disaster recovery depends on capacity being available in a different location from the one that failed. If no reservation exists in the recovery location, recovery may be delayed for hours or may fail entirely while competitors for the same spare capacity are also recovering. The organisation then faces a double problem: the original site is down, and the recovery site cannot absorb the load.

### What Goes Wrong Without a System

- Service disruptions when capacity is unavailable at the moment of need.
- Failed or severely delayed disaster recoveries because recovery capacity was never secured.
- Wasted cloud spend from over-reservation that nobody is systematically reviewing.
- Inconsistent practices across teams, making audit and compliance difficult.
- No single view of how much capacity is reserved, used, or protected for recovery.

ACRME exists to turn this fragmented, manual problem into a governed, auditable, and scalable operating model — without pretending that the underlying cloud platform risks have disappeared.

---

## 3. What ACRME Does

### The Hotel Room Analogy

Imagine a hotel chain that serves corporate travellers. Guests need rooms in specific cities on specific nights. The chain can either hope rooms are free when guests arrive, or it can pre-book blocks of rooms. Pre-booking costs money even if some rooms stay empty. Not pre-booking risks turning guests away.

ACRME is the booking management system for that chain. Cloud server capacity is the room. Customers are the guests. Locations are the cities. ACRME decides how many rooms to hold in each city, which guests may draw from a shared block, when to increase the block, and how many rooms must always be kept aside for emergency relocation if a city becomes unusable. It does this continuously, with rules, approvals, and a full record of every booking decision.

### The Three Types of Capacity

ACRME manages three distinct classes of reserved capacity in each managed location. Keeping them separate is deliberate: it prevents everyday demand from quietly consuming the capacity that disaster recovery depends on.

| Capacity Type | Business Purpose | How It Is Treated |
|---|---|---|
| Normal operations (Production) | Everyday customer workloads that must always be able to run | Always reserved and always paid for. Highest day-to-day priority for availability. |
| Non-production | Development, testing, and staging environments | Reserved but more flexible. Can be adjusted, but must not crowd out the disaster recovery share. |
| Disaster recovery | Protected floor of capacity in a different location for failover | Most carefully protected. Engine-enforced floor. Automatic actions that would breach this floor are blocked. |

A hard business rule underpins the model: a customer's production, non-production, and disaster recovery workloads must not all sit in the same geographic location. Production and disaster recovery must be in different locations. Non-production may share a location with disaster recovery only under an approved policy, and only when the customer accepts that a single regional event could affect both.

### How Reservations Are Shared

Instead of every customer owning a completely separate reservation, ACRME can manage a shared pool. Multiple customer accounts are explicitly authorised to draw capacity from a reservation that is owned and paid for on the provider side. This reduces fragmentation and can lower the total amount of capacity that must be reserved across the estate.

Sharing has clear benefits and clear risks. The benefit is efficiency: one well-managed pool can serve many customers more economically than dozens of isolated reservations. The risks include a hard ceiling of 100 customer accounts per shared pool (beyond which the pool must be split), more complex permissions, and the fact that the underlying sharing capability is still a Microsoft Preview feature. Sharing is never implicit or tenant-wide; every customer account must be explicitly added, and every relationship is recorded.

### The Automation Engine

In plain terms, the engine continuously does six things:

- Monitors reservation levels, usage, and headroom across all managed locations.
- Decides when capacity should be increased (and, in later phases, recommends when it could be reduced).
- Routes customers to the best available location based on capacity, recovery rules, and policy.
- Prevents any automatic action from destroying the protected disaster recovery floor.
- Requires human approval for the riskiest operations — and blocks the most destructive ones entirely in Phase 1.
- Keeps a complete audit trail of every decision, approval, and change.

Operations are deliberately tiered by risk:

| Tier | What It Means | Phase 1 Treatment |
|---|---|---|
| Tier 1 — Additive | Increase disaster recovery capacity using pre-staged headroom. Does not take capacity away from anyone else. | Allowed only during a declared disaster event, with fresh checks. Conditional automation after gates pass. |
| Tier 2 — Reallocation | Reduce non-production reservations to free budget for disaster recovery expansion. Changes guarantees for non-production. | Disabled until validation proves the behaviour. Approval required even after enablement. |
| Tier 3 — Disassociation | Change how running servers are linked to reservations. Highest blast radius; can affect restart behaviour. | Blocked. Not automated. Requires a resolved permissions model and separate board authorisation later. |

The design principle is simple: safety before automation. Additive actions are easier to reverse than destructive ones. The engine is built so that operators can still recover manually if the automation is unavailable.

---

## 4. How Customers Are Onboarded

Onboarding is a controlled sequence. No customer is placed onto shared capacity until every prerequisite check has passed and been recorded.

### Information Collected

Before technical setup begins, the programme collects the customer's cloud account details, the environments to be managed (production, non-production, disaster recovery), the server types and locations in scope, recovery objectives, and formal consent for ACRME to hold the minimum approved rights in those accounts. Cost and discount eligibility are also reviewed at this stage so commercial expectations are set correctly.

### Location Validation (Hard Requirement)

ACRME validates that the customer's production, non-production, and disaster recovery workloads are not all concentrated in one location. Production and disaster recovery must be in different locations. This is a hard constraint — onboarding does not proceed if the layout violates it. The engine also builds a zone-alignment map for every account and location pair. Different cloud accounts can label the same physical data-centre zone with different logical numbers; without this map, a reservation in one account can be useless to servers in another. If the map cannot be built and verified, onboarding is blocked.

### Reservation Created on the Customer's Behalf

Once validation passes, ACRME creates or links the appropriate capacity reservations, adds the customer account to the approved shared pool (subject to the 100-account ceiling), and records the relationship. Quantity is set according to policy and the customer's declared demand, including the disaster recovery floor calculation.

### Permissions the Customer Must Grant

The customer must grant ACRME narrowly scoped rights — preferably through a customer-consented managed identity — limited to the actions required for inventory, reservation management, and (only if later approved) association changes. Broad, subscription-wide administrator rights are not the default and should not be accepted as a shortcut. Every delegation is recorded with purpose, approver, and revocation path.

### Confirmation Before Go-Live on the System

- Zone map written and read back successfully for all managed locations.
- Sharing relationship read back and confirmed.
- Quota and eligibility checks passed at both the individual account and group level.
- Disaster recovery floor calculated and visible on operational dashboards.
- Customer acceptance of Preview-feature risk and any non-standard location strategy on record.
- Manual rollback path demonstrated for the onboarding actions taken.

Only after these confirmations is the customer marked ready on ACRME.

---

## 5. How Disaster Recovery Works

### What Failover Means Here

In this context, failover means moving or restarting customer workloads in a pre-chosen recovery location because the primary location is impaired or unavailable. ACRME does not replace application orchestration, data replication, networking recovery, or business-continuity governance. It ensures that the compute capacity those other disciplines need is reserved, authorised, and ready to be consumed when a disaster is declared.

### The Protected Capacity Floor

The disaster recovery floor is a calculated minimum amount of capacity that must remain available for recovery. It is derived from potential recovery demand and a business-set coverage ratio (currently a design placeholder of 30–40%). Critically, this floor is enforced by ACRME's own controls and monitoring — it is not a native sub-reservation created automatically by the cloud platform. That means a software defect, a stale calculation, or a bypass path could in theory consume it. For that reason the design requires an independent detector that recalculates the floor and blocks automatic non-production expansion if the two calculations disagree.

### When a Disaster Is Declared

- An authorised operator requests disaster declaration through the engine.
- Dual approval and state validation are required before the engine leaves normal operations mode.
- The engine enters disaster-event mode. Steady-state auto-scaling behaviour is suppressed where it could conflict.
- Capacity, sharing relationships, zone alignment, and quota are re-validated from authoritative sources.
- Approved failover deployments begin. Progress is observed per workload.
- If something critical fails or state conflicts appear, the engine can enter an incident-hold mode rather than continuing blindly.
- Tier 1 expansion may be evaluated if pre-staged headroom exists. Tier 2 and Tier 3 are not automatically authorised by the declaration alone.

### During Recovery (Failback)

Failback is the controlled return to the primary location once it is healthy. The engine requires explicit failback approval, validation that primary application, data, network, identity, and capacity are ready, restoration in waves, health checks, and only then the draining of recovery-site traffic. Disaster recovery resources are deallocated conservatively. Reservation policy and the disaster recovery floor are recalculated. The engine returns to normal operations only after all related operations have closed cleanly. Starting failback too early is treated as a critical risk and is gated.

### Safeguards Against Accidental Use of DR Capacity

- Separate capacity pools for production, non-production, and disaster recovery.
- Engine-enforced floor with an independent detector and fail-closed behaviour on disagreement.
- Automatic non-production expansion blocked when it would breach the floor.
- Disaster-event mode required before emergency capacity actions are even evaluated.
- Human approval for material reallocations; destructive association changes blocked in Phase 1.
- Full audit of mode transitions, approvals, and outcomes.

---

## 6. How Placement Decisions Are Made

When a customer needs a location assignment, ACRME does not pick at random or by simple round-robin. It evaluates managed locations against hard rules first, then scores the survivors. The final design includes a region classification model that separates business-ready regions from exception-only regions and addresses geography-specific constraints.

### Which Regions Are Eligible

Not all Azure regions are treated equally. The engine divides all managed regions into two classes:

**Standard Capacity Regions** — These are the business-ready regions that enter normal automated placement. The engine scores them, ranks them, and assigns them for production, non-production, and disaster recovery workloads. Regions in this group pass current Azure physical capacity health checks and are approved for automated operations.

| Geography | Standard Capacity Regions |
|---|---|
| North America | West US 3, Central US, Canada Central |
| Europe | Sweden Central, Belgium Central |
| Middle East | Saudi Arabia, UAE North |
| Asia Pacific | Japan East, Southeast Asia, Australia East |

**Restricted Capacity Regions** — These five regions are currently under Azure physical capacity constraints and are excluded from automated placement. They do not enter the scoring pipeline. They are eligible only through an exception process (see below).

| Restricted Region | Geography | Why restricted |
|---|---|---|
| East US 2 | North America | Azure physical capacity constraint |
| North Europe, West Europe | Europe | Azure physical capacity constraint |
| East Asia, Australia Southeast | Asia Pacific | Azure physical capacity constraint |

This classification prevents the engine from recommending a constrained region and discovering the problem at deployment time. If a customer must use a restricted region for production, an explicit exception workflow applies (see Exception Process below).

### Two Ways to Request a Location

Customers provide the production location anchor in one of two ways:

**Option 1 — Name a broad geography** ("North America", "Europe", "Middle East", "Asia Pacific"). The engine picks the best production region from the Standard Capacity Regions in that geography using a scoring formula that balances available capacity, quota headroom, disaster recovery coverage readiness, fair distribution, and zone diversity. The top-scoring region becomes the production anchor.

**Option 2 — Name a specific Azure region.** If the region is a Standard Capacity Region, the engine validates it against business rules (capacity floor, quota, zone support, separation constraints, disaster recovery integrity). If it passes, that region becomes the production anchor directly. If the customer names a Restricted Capacity Region, the request goes to the exception workflow.

Once the production region is fixed, the non-production and disaster recovery regions are selected from the remaining Standard Capacity Regions in the same geography. Middle East has special handling (see below).

### How the Engine Scores and Picks

The scoring model weighs five components:

1. **Available reserved capacity** for the required server type and zone.
2. **Quota headroom** at both the individual account and the shared budget group.
3. **Distribution fairness** — whether demand is balanced or one location is absorbing too much load.
4. **Disaster recovery coverage health** — whether the disaster recovery floor is intact.
5. **Zone diversity** — whether the region can support multiple physical availability zones.

Weights are versioned and recorded with every decision so results can be replayed. The engine uses live snapshots; if data is stale, it triggers a fresh read from Azure before committing. During the pilot, placement is recommendation-only: the engine advises, and a human commits. Autonomous placement is not enabled until concurrency controls and formula behaviour are proven under load.

### Middle East Special Handling

Middle East has only two Standard Capacity Regions: Saudi Arabia and UAE North. A three-region deployment (production, non-production, disaster recovery) cannot fit in two regions. The engine solves this using a **Cross-Geo Extension** rule: disaster recovery for Middle East production workloads goes to Belgium Central in Europe.

| Environment | Middle East region assignment |
|---|---|
| Production | Whichever of the two in-geography regions scores higher (Saudi Arabia or UAE North) |
| Non-production | The other in-geography region (deterministic — only one candidate remains) |
| Disaster recovery | Belgium Central (Europe) — the only approved cross-geography disaster recovery path |

Belgium Central must still pass capacity and quota health checks before being assigned. If it fails, the deployment is blocked with an operations alert — the engine does not silently substitute another region. Belgium Central remains available for normal Europe deployments; its cross-geography role for Middle East is additive, not exclusive.

The cross-geography extension is the only currently approved exception to the "disaster recovery must be in the same geography" rule. Any additional cross-geography paths require governance approval and a formal policy update before the engine uses them.

### Exception Process for Restricted Regions

If a customer explicitly requests a Restricted Capacity Region for production, all four of these conditions must be met before the engine proceeds:

1. **Explicit request** — The customer named the region; the engine did not recommend it.
2. **Production workload only** — Restricted regions are never used for non-production or disaster recovery.
3. **Exception approval on record** — A named exception approval exists for that customer–region pair.
4. **Specific region input** — The customer used Option 2 (named a region), not Option 1 (named a geography).

If all conditions pass, the engine assigns the restricted region as the production anchor, marks the deployment as an **Exception Deployment** in the audit trail, and selects non-production and disaster recovery from Standard Capacity Regions using normal scoring. A capacity-constraint warning is issued to the operator. The exception approval identifier is written to the operation record. If any condition fails, the request is rejected immediately.

This ensures that no Restricted Capacity Region enters production without explicit awareness and approval.

### Hard Separation Rules

Regardless of geography or region classification, ACRME enforces these separation rules:

- Production and disaster recovery must not share a location.
- Production and non-production must not share a location.
- Non-production may share a location with disaster recovery only under an approved policy, and only when the customer accepts that a single regional event could affect both.

These are pre-filters. A candidate region that violates separation is excluded before scoring begins.

### Shadow Testing

Shadow testing means the engine simultaneously runs two decision methods — the primary sequential method and an alternative joint-optimisation method — and compares whether they agree. Neither method changes live cloud resources during the comparison. Divergences are measured and reviewed. This builds evidence before either method is trusted for automatic commits.

### The Concept of a Hold

A hold is a short-lived, atomic reservation of a capacity slot inside the engine's own records. Before two customers can be assigned the same remaining capacity, one hold must win. If cloud provisioning does not begin in time, the hold expires and the capacity returns to the pool. This prevents a known race condition where two parallel decisions both see the same free capacity and both proceed.

---

## 7. Cost and Financial Considerations

### How Reserved Capacity Is Charged

Azure charges for capacity reservations whether or not virtual machines are running against them. The reservation is a guarantee of availability, and the price of that guarantee is ongoing cost. This is fundamentally different from paying only for servers that are switched on. Any financial model for ACRME must start from that fact.

### The Cost Benefit of Sharing

A shared pool can reduce the total reserved footprint because peaks across customers do not all require fully isolated buffers. Fewer fragmented reservations also reduce operational overhead. Those are real structural advantages — but they are not automatic savings on every invoice line.

> **ATTENTION — Critical Commercial Constraint: Reserved Instance Discounts**
>
> - When capacity is shared across customer accounts, prepaid discount instruments (Reserved Instances or Savings Plans) do not automatically flow to the customer's account. Discounts apply only when the provider account and the customer account share the correct billing or management-group scope, and only when that scope is configured correctly at purchase time.
> - Each customer's discount eligibility must be validated individually before any cost estimate is presented. Overstating cost benefits creates financial and commercial risk — including customer disputes and margin erosion.
> - FinOps must confirm shared enrollment or management-group scope per customer pair during onboarding and document the result in the capacity cost summary.

### Over-Reservation Versus Under-Reservation

| Direction | Financial Effect | Operational Effect |
|---|---|---|
| Over-reservation | Wasted budget on unused guaranteed capacity | Higher confidence that workloads can start; lower efficiency |
| Under-reservation | Lower direct reservation spend | Service risk, failed recoveries, emergency premium effort |
| Right-sized with headroom | Controlled, explainable spend | Balanced availability and efficiency with auditable policy |

### How Forecasting Helps

ACRME's forecasting aims to predict peak demand over a planning horizon and recommend a reservation quantity that includes growth and recovery buffers. During the pilot, forecasts are advisory only. They inform human decisions; they do not automatically shrink capacity. Model accuracy must be measured before forecasts influence spend at scale.

### Cost Decisions Still Open

- No automatic capacity reduction is allowed in Phase 1. Some over-reservation cost may therefore persist until reduction is proven safe and approved.
- The disaster recovery coverage ratio (placeholder 30–40%) and emergency headroom target (placeholder 30%) are business policy inputs with direct cost consequences. They need leadership values, not engineering defaults.
- Platform running costs for ACRME itself (hosting, data stores, monitoring) must be sized from measured pilot workload, not from day-one assumptions that every enterprise component is required at full scale.
- Cost estimates in design material are not billing facts until reconciled against actual invoices.

---

## 8. What Is Working Well

An honest assessment includes what is genuinely strong. The following points are working well and should give leadership confidence that the programme is being run with discipline.

### Comprehensive, Reviewed Architecture

The architectural design is broad, internally coherent, and has been through an independent production-readiness review. Requirements coverage is strong. The separation of steady-state operations from crisis operations is a mature design choice that many control planes lack.

### Complete and Understood Risk Register

Forty-four risks have been logged with likelihood, impact, mitigation, owner, and residual risk. Risks are grouped across technology, operations, commercial, and customer dimensions. Nothing material identified in the review has been left off the register.

### Phased Approach with Human Control

Phase 1 deliberately keeps dangerous operations under human approval or blocks them entirely. Destructive association changes and auto-scaling server-group emergency actions are out of scope for automation. This is the correct posture for a system that can affect customer production capacity.

### Strong Audit and Observability Design

Every accepted mutation is designed to produce an append-only audit record. Dashboards cover capacity, quota headroom, disaster recovery floor integrity, sharing relationships, placement decisions, engine mode, and failed operations. Alerting includes critical guards such as floor breaches, illegal mode transitions, and blocked emergency attempts.

### Fact-Check Corrections Applied

A live fact-check against Microsoft's published documentation confirmed the major platform claims (including Preview status of sharing, the 100-account limit, and consumer quota independence) and surfaced seven corrections. High-severity gaps — cross-account zone alignment and a Preview-only quota enforcement property — were written back into the architecture. The programme is not relying on unexamined assumptions where documentation was available.

### Manual Survivability

The design requires that operators can still perform recovery using documented manual procedures if the engine is unavailable. ACRME is not intended to become a single point of failure for business continuity.

---

## 9. What Is Still Being Validated

This section is intentionally complete and unvarnished. None of the items below should be described to customers or auditors as solved until the stated validation is done.

### Shared Reservation Feature Is Still in Preview

The core ability to share a capacity reservation across customer accounts is a Microsoft Preview feature. Preview features are not covered by the same contractual commitments as generally available features. Microsoft can change behaviour or withdraw the capability. Internal tests and design documents are not a Microsoft service level agreement. Go-live on this dependency requires a formal risk acceptance decision from leadership, plus feature flags and an exit path if the platform changes.

### The 100-Customer Limit per Shared Pool

Each shared reservation pool can serve at most 100 customer accounts. This is a hard platform limit, not a soft guideline. If the customer list grows beyond this, pools must be split (sharded). Splitting adds operational complexity, more relationships to monitor, and potentially more reserved capacity overall. Capacity planning must model this ceiling from day one rather than discovering it in production.

### Customer Discovery of Shared Reservations

There is a documented Microsoft known issue: a customer account cannot reliably list shared reservations that belong to someone else's account using the standard list operation, particularly when the customer has no local reservation in that region. ACRME's workaround is to treat the provider-side inventory as authoritative and use Microsoft's resource inventory query service only for diagnostics — never as the final check before a destructive change. The workaround must remain on the monitoring list because inventory lag is real.

### Zone Alignment Across Accounts

When servers must run in a specific physical availability zone, the shared reservation must sit in that exact same physical zone. Different cloud accounts often number zones differently even in the same region. Without a per-account translation map, deployments fail even though capacity appears to exist. Building and verifying this map is now a mandatory onboarding gate. It was identified as a high-severity gap in the fact-check and has been designed in; it still requires execution proof for every provider–customer pair.

### Quota Group Feature — Partial Preview Dependency

Grouping multiple accounts under a shared capacity budget is central to the two-budget-per-region model (one budget for production, one shared budget for non-production plus disaster recovery). Core quota group operations are broadly available, but the property that distinguishes advisory membership from enforced membership appears only in Preview programming interfaces. If the design relies on enforced group semantics from the platform, that is an additional Preview dependency requiring governance acceptance. Regardless, ACRME will continue to enforce its own account-level checks and will not treat group membership as proof that a specific account can deploy.

### Auto-Scaling Server Groups During a Disaster

If a customer uses auto-scaling server groups (scale sets) and a zone fails, Microsoft documents that reprovisioning those servers through a shared reservation during the outage is a Preview limitation and is not supported. This means auto-scaling disaster recovery via shared reservations is not fully supported yet. Phase 1 blocks automated emergency actions against these server groups. Phase 2 must either wait for Microsoft to resolve the limitation at general availability or provide a non-shared alternative path. Pilot customers who rely on scale sets for recovery must be told explicitly and must accept the limitation in writing.

### End-to-End Disaster Recovery Has Not Been Tested

Failover and failback have been designed, sequenced, and captured in runbooks. They have not been run end-to-end in a live environment that includes application deployment, data, network, domain name services, identity, quota, and capacity together. Until that exercise passes, no production claim about recovery time or recovery success rate is defensible. This is a go-live blocker for disaster-recovery automation.

> **ATTENTION — Honest Status: End-to-End DR Not Yet Tested**
>
> The disaster recovery workflow has been designed in detail, including runbooks for declaration, expansion, reallocation, and failback. It has not been executed end-to-end in a live environment with real application, data, network, and identity dependencies. This remains a go-live blocker for production disaster-recovery automation. No recovery time objective should be committed to customers until that exercise has passed.

### Permissions Model Is Unresolved (Critical Blocker)

> **CRITICAL — Critical Production Blocker: Permissions Model**
>
> - The exact permissions ACRME needs in a customer's account — especially for any future ability to change how running servers link to reservations — is the number-one unresolved production issue (tracked internally as the credential model gap).
> - The wrong model is both a security risk (excessive privilege) and an operational blocker (insufficient privilege or no governed consent and revocation path).
> - The preferred direction is a customer-consented managed identity with resource-group-scoped custom rights, not subscription-wide administrator access. Until security approves a model and it is tested, the highest-risk tier of operations remains blocked.

### Other Validation Still Outstanding

- Engine mode state machine (normal operations, disaster active, failback pending, incident hold) must be implemented with transition guards and fault-injection tests before any disaster automation.
- Quota-neutral reallocation (Tier 2) remains conditional on measured release and reuse behaviour — not on design assertion.
- Concurrent placement under load must prove that holds prevent double-assignment.
- Scale behaviour at hundreds to thousands of customers is unmeasured; full-scan every few minutes is already judged unsafe as a universal approach.
- Cost and utilisation models need reconciliation against real billing data.

---

## 10. The Risks — Plain English

Below are the material risks translated for a business audience. Likelihood and impact use the internal register's language. Mitigations are what the programme is actually doing — not aspirational controls.

### Technology Risks

| Risk | Likelihood | Impact | What We Are Doing |
|---|---|---|---|
| Microsoft changes or withdraws the shared reservation Preview feature | Medium | Critical | Feature flags, isolated adapters, formal governance acceptance before production dependency |
| Quota budget grouping unavailable or incomplete in a target scope | Medium | Critical | Gate test before engineering; fallback architecture required if the gate fails |
| Preview-only enforcement property for budget groups is relied on accidentally | Medium | High | Treat enforcement semantics as Preview; keep engine-side account checks mandatory |
| Platform inventory service returns stale data and a bad decision follows | High | High | Use inventory only for diagnostics; confirm with direct platform reads before any mutation |
| Auto-scaling server groups cannot reprovision via shared reservation during a zone outage | High | Critical | Documented Preview limitation; block automated Phase 1 use; require GA resolution or alternative path for Phase 2 |
| API throttling delays actions during a disaster | Medium | Critical | Per-account budgets, adaptive backoff, documented manual path that does not depend on the engine |

### Operational Risks

| Risk | Likelihood | Impact | What We Are Doing |
|---|---|---|---|
| Permissions model grants too much access — or not enough governed access | High | Critical | Scoped managed identity design, custom roles, customer consent, revocation testing; Tier 3 blocked until closed |
| End-to-end disaster recovery fails when first exercised for real | Medium | Critical | Full failover and failback exercise is a production entry gate; no customer RTO until passed |
| Engine mode allows illegal mixing of normal and crisis operations | Medium | Critical | Formal state machine with dual approval, conditional writes, and fault-injection tests — currently a blocker |
| Disaster recovery floor is bypassed by a bug or stale data | Medium | Critical | Independent detector; automatic expansion fails closed on disagreement |
| Failback starts before the primary location is truly ready | Medium | Critical | Readiness gate, explicit approval, wave-based restore, health validation before traffic drain |
| Manual cloud changes conflict with engine desired state | Medium | High | Maintenance mode, drift detection, and clear policy on when the engine may reverse manual changes |
| Customer revokes access during an incident | Medium | High | Lifecycle monitoring, revalidation, and incident procedures that include access failure |

### Commercial and Financial Risks

| Risk | Likelihood | Impact | What We Are Doing |
|---|---|---|---|
| Cost estimates assume discounts that do not apply to the customer account | Medium | Medium | Per-customer discount scope validation during onboarding; no shared-discount assumption by default |
| Over-reservation persists because automatic reduction is disallowed in Phase 1 | Medium | High | Accept as Phase 1 cost of safety; advisory right-sizing only; reduction requires later proof |
| Disaster recovery coverage ratio is set too low or too high | Medium | Critical / High | Treat 30–40% as placeholder; require workload-specific recovery analysis and leadership policy |
| Emergency headroom target is mis-sized | Medium | High | Scenario testing; tunable policy parameter; cost and recovery-time consequences reviewed together |
| Internal forecasts are mistaken for billing commitments | Medium | Medium | Reconcile against invoices; label estimates as estimates |
| Preview or lab results are presented as a contractual service level | Medium | Critical | Evidence labelling standards; governance review before external commitments |

### Customer Risks

| Risk | Likelihood | Impact | What We Are Doing |
|---|---|---|---|
| Zone mismatch makes a shared reservation useless to the customer | High | Critical | Mandatory zone map at onboarding; translation before every zonal deployment; hard fail if map missing |
| Customer cannot see shared reservations through standard tools | Medium | Medium | Provider inventory authoritative; communicate the known platform limitation to operators |
| Customer count breaches the 100-account pool ceiling | High | High | Shard pools; monitor relationship counts continuously, not only at create time |
| Forced removal from a shared pool strands server restarts | Medium | Critical | Default deny when active associations exist; customer approval; recovery runbook |
| Non-production and disaster recovery share a location and both are lost together | Medium | Critical | Allowed only with failure-domain review and explicit customer acceptance |
| Offboarding a customer with running servers creates restart hazard | Medium | High | Controlled offboarding checklist; association checks before sharing removal |

Residual risk remains even after controls: the cloud provider can still be out of physical capacity; quota updates can lag; authorisations can drift; and application recovery can fail for reasons unrelated to compute reservations. Those residuals must appear in customer recovery commitments and in regular operational exercises.

---

## 11. What Leadership Must Decide

Three decisions cannot be delegated to engineering. Until each is made explicitly, the programme should not represent itself as cleared for the corresponding scope.

> **DECISION 1 — Accept the Preview Feature Dependency**
>
> - **Context:** Shared capacity reservations are a Microsoft Preview capability. Preview is not a contractual commitment. Behaviour can change; the feature can be withdrawn.
> - **Options:** (a) Formally accept Preview risk for a bounded pilot with feature flags and an exit plan; (b) Wait for general availability before any customer dependency; (c) Accept Preview for pilot only and require a separate production decision later.
> - **Recommendation:** Option (c). Allow a constrained pilot after gates, and require a distinct production authorisation that revisits Preview status, executed test evidence, and residual risk.
> - **If deferred:** No customer should be sold a recovery commitment that depends on shared reservations.

> **DECISION 2 — Approve the Permissions Model Approach**
>
> - **Context:** ACRME must act inside customer cloud accounts. The credential and permissions model is the primary unresolved production blocker. It balances security (least privilege, consent, revocation) against operability (enough access to do the job during an incident).
> - **Options:** (a) Approve a customer-consented managed identity with narrow custom roles at resource-group scope as the standard; (b) Approve a more privileged model with compensating controls (time-bound access, dual control, heightened audit); (c) Keep highest-risk operations permanently manual and out of the engine.
> - **Recommendation:** Option (a) as the target standard, with Option (c) as the mandatory posture until (a) is security-approved and tested. Do not default to subscription-wide administrator rights.
> - **If deferred:** Tier 3 remains blocked; any emergency change to server–reservation links stays a manual, customer-involved procedure.

> **DECISION 3 — Set the Disaster Recovery Floor Policy**
>
> - **Context:** How much capacity is held for disaster recovery is a business decision tied to customer service commitments, risk appetite, and cost. The design's 30–40% range and 30% emergency headroom are placeholders, not proven universal requirements.
> - **Options:** Set a portfolio default ratio; allow customer-specific ratios within a governed band; or require a recovery analysis per critical customer before any floor is applied.
> - **Recommendation:** Require customer-specific recovery analysis for critical workloads, with a portfolio default used only for non-critical pilots. Publish the chosen figures as policy with a review cadence.
> - **If deferred:** Engineering will continue to use placeholders; cost and protection levels will not align to an approved risk appetite.

> **DECISION — Council Position (Unchanged)**
>
> - Approve a two-stage programme: constrained pilot now (when gates are met), controlled production later (when all gates close).
> - Do not approve unrestricted autonomous disaster recovery, destructive capacity transfer, or auto-scaling server-group emergency automation at this time.

### Additional Board Actions Already Identified

- Approve the Phase 1 prohibition on destructive automation and on auto-scaling server-group emergency automation.
- Assign executive owners for the permissions blocker and the engine mode blocker.
- Require executed validation evidence before budget-group engineering proceeds at scale.
- Require customer-specific recovery objectives where non-standard location strategies are used.
- Approve adaptive operational monitoring instead of naive full-estate scanning on a fixed short interval.
- Require a separate production authorisation after pilot completion — pilot success is not automatic production approval.

---

## 12. Recommended Go-Live Sequence

The programme should proceed in three stages. Each stage has entry conditions. Skipping gates to save time exports risk to customers.

### Phase 1 — Pilot (Constrained)

A small number of customers. Manually approved operations only for anything that changes capacity guarantees. No automation of high-risk steps. Full human oversight. Placement is recommendation-only. Disaster recovery automation is off. Destructive association changes are off. Auto-scaling server-group emergency actions are rejected by the system.

**Before Phase 1 begins:**

- Leadership accepts Preview risk for the bounded pilot scope.
- Pilot identity and permissions model approved for the non-destructive actions in scope.
- Sharing setup and safe removal tested with retained evidence logs.
- Zone alignment validated for every pilot provider–customer pair.
- Budget-group availability proven in every pilot scope, or an approved fallback is in place.
- Automatic increases remain approval-gated; reallocation and destructive tiers remain disabled.
- Manual rollback demonstrated.
- Pilot customers accept Preview risk and any non-standard location strategy in writing.

### Phase 2 — Controlled Automation

Automation of lower-risk operations after Phase 1 evidence. Disaster recovery automation remains gated. Reallocation may be enabled only after release-and-reuse behaviour is measured and approved. Highest-risk association changes remain blocked unless the permissions model and state machine blockers are fully closed and separately authorised.

**Before Phase 2 begins:**

- Phase 1 pilot objectives met with no open critical incidents attributable to the engine.
- Concurrency and replay tests show no double-assignment under parallel demand.
- Engine mode transitions proven under fault injection.
- Quota and reservation behaviours proven across the approved scenario matrix.
- Observability alerts and runbooks exercised, not merely documented.
- Any enablement of reallocation includes customer-impact preview and approval workflow.

### Production — Full Automation (Only After Gates)

Full automation is appropriate only after all production entry gates pass, all named blockers close, and disaster recovery has been tested end-to-end with application and data recovery objectives demonstrated. Even then, destructive tiers should require separate board authorisation rather than riding along on a general production approval.

**Before Production begins:**

- Sharing, budget groups, reservation updates, state machine, permissions, placement concurrency, disaster recovery exercise, scale-set scope, scale tests, and Preview governance decision all have recorded evidence and named approvers.
- Customer recovery commitments reconciled to what was actually demonstrated.
- Discount and cost model validated per customer against billing reality.
- Operational ownership, on-call, and manual fallback procedures staffed and drilled.
- Separate written authorisation for any future enablement of destructive automation.

---

## 13. Appendix: Glossary

Plain-English definitions of terms used in this document.

| Term | Plain-English Meaning |
|---|---|
| Capacity Reservation | A paid guarantee that a specific amount of cloud server capacity of a given type will be available in a location when needed, whether or not it is currently running workloads. |
| Capacity Reservation Group | A container that holds one or more capacity reservations, typically organised by location and purpose, and that can be shared with other cloud accounts when sharing is enabled. |
| Shared Capacity Reservation | A reservation owned in one account (the provider) that other authorised accounts (consumers) may use for their servers. Reduces fragmentation but adds permission and platform complexity. |
| Provider Subscription | The cloud account that owns the reservation and typically bears the reservation-side cost. |
| Consumer Subscription | The cloud account that runs servers using capacity from a shared reservation. Must still have its own permission (quota) to deploy those servers. |
| Availability Zone | A physically separate data-centre location within a broader cloud region. Used to survive the loss of a single building or zone, not the loss of an entire region. |
| Disaster Recovery | The ability to continue or restore service in another location after a serious incident. In this document, focused on having compute capacity ready for that restoration. |
| Failover | Switching workloads to the recovery location when the primary location is impaired. |
| Failback | Returning workloads to the primary location after it is healthy again, in a controlled sequence. |
| Reserved Instance / Reserved Capacity Discount | A prepaid discount instrument for cloud compute. Separate from capacity reservations. Discounts do not automatically apply across accounts unless billing scope is configured to allow it. |
| Quota | An account's permission from the cloud provider to deploy a certain amount of a resource type. Having a reservation does not remove the need for quota; both must be satisfied. |
| Preview Feature | A cloud platform capability that is available for use but not yet generally released. Subject to change or withdrawal; not covered by standard general-availability commitments. |
| VMSS (Auto-Scaling Server Group) | A managed group of servers that can grow and shrink automatically. Emergency behaviour with shared reservations during a zone outage is a known Preview limitation. |
| Placement Engine | The part of ACRME that chooses which location a customer should use, based on rules, scores, and available capacity. |
| Reconciliation | The ongoing process of comparing what ACRME believes should be true with what the cloud platform actually shows, and raising or correcting drift. |
| Audit Trail | A permanent, ordered record of decisions, approvals, and changes that allows an incident or decision to be reconstructed later. |
| Disaster Recovery Floor | The minimum capacity ACRME is configured to protect for recovery. Enforced by the engine and its monitors, not as a separate native cloud sub-product. |
| Hold | A short-lived internal lock on a capacity slot so two customers are not assigned the same remaining capacity at the same time. |
| Shadow Testing | Running a second decision method in parallel with the primary one to compare results, without applying the second method's output to live systems. |
| Tier 1 / Tier 2 / Tier 3 | A risk ladder for emergency capacity actions: add capacity; reallocate from non-production; change server–reservation links. Higher tiers mean higher blast radius and tighter control. |
| Engine Mode | The operating posture of ACRME — normal operations, disaster active, failback pending, or incident hold — which gates which actions are even eligible for evaluation. |

### Immediate Actions for Leadership

To keep the programme moving without overstating readiness, leadership should treat the following as the near-term decision agenda. None of these items is optional paperwork; each unlocks or blocks a concrete scope of work.

- Record a formal decision on Preview-feature use for the bounded pilot, including the named owner of residual risk and the date of the next production revisit.
- Commission the security review of the customer permissions model and set a target decision date. Until that decision is made, keep highest-risk automation blocked.
- Set interim disaster recovery floor and emergency headroom policy values for the pilot cohort, with a commitment to replace placeholders after the first recovery exercise.
- Confirm the pilot customer list, written acceptance of known limitations, and executive sponsors for the permissions and engine-mode blockers.
- Schedule the end-to-end disaster recovery exercise as a gated milestone on the production path, not as an informal engineering task.

This executive document summarises the approved architecture and readiness position for leadership review. It does not replace the detailed architecture, risk register, or validation workbook. The honest position remains: design complete, validation in progress, conditional pilot supportable, and unrestricted autonomous disaster-recovery automation not approved.

### Document Control

| Field | Value |
|---|---|
| Document title | ACRME — Executive Design Document |
| Version | 1.0 |
| Date | 21 August 2026 |
| Status | Design Complete — Validation In Progress |
| Classification | Internal — Restricted |
| Primary source | ACRME Production-Readiness Review and Final Architecture |
| Supporting source | ACRME Fact-Check Report (seven corrections applied upstream) |
| Audience | Executive leadership and business stakeholders |
| Language standard | Plain business English; no unexplained technical jargon |
