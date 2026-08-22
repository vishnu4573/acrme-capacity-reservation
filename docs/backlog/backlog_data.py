"""
ACRME Product Backlog — single source of truth.

Defines the full Epic -> Story -> Task hierarchy derived from the
Production-Readiness Review and Final Architecture (PRR). The generator
scripts (generate_markdown.py, generate_csv.py) consume this module so the
Markdown backlog and the Jira import CSV never drift.

Priority scale : Highest / High / Medium / Low  (Jira default names)
Points scale   : Fibonacci story points (1,2,3,5,8,13)
Phase          : P1 (Pilot), P2 (Controlled automation), P3 (Production/Future)
"""

# ---------------------------------------------------------------------------
# Each epic: id, name, goal, prr_refs, stories[]
# Each story: id, title, as_a/i_want/so_that, priority, points, phase,
#             prr_refs, depends_on[], acceptance[], tasks[]
# Each task:  id, title, note (optional)
# ---------------------------------------------------------------------------

EPICS = [
    # =====================================================================
    {
        "id": "ACRME-E01",
        "name": "Foundation & Platform Infrastructure",
        "goal": "Stand up the buildable core: CQRS command/query separation, saga "
                "orchestration, the command/event bus, the authoritative engine "
                "state store, and provider-isolated Azure adapters.",
        "prr_refs": ["§23 Logical Component Architecture", "§24 MG & Subscription Topology", "§38 WAF"],
        "stories": [
            {
                "id": "ACRME-S0101",
                "title": "CQRS Command and Query API skeleton behind API gateway",
                "as_a": "platform engineer",
                "i_want": "a Command API and a Query API fronted by an API gateway",
                "so_that": "state-changing and read operations are cleanly separated and independently scalable",
                "priority": "Highest", "points": 8, "phase": "P1",
                "prr_refs": ["§23", "§35"],
                "depends_on": [],
                "acceptance": [
                    "Command API and Query API are deployed as separate services behind the API gateway.",
                    "All mutations route only through the Command API; all reads only through the Query API.",
                    "Health/readiness probes return 200 for both services.",
                    "Requests are traced end-to-end with a correlation ID.",
                ],
                "tasks": [
                    {"id": "ACRME-T010101", "title": "Scaffold Command API service (routing, DI, config, health probes)"},
                    {"id": "ACRME-T010102", "title": "Scaffold Query API service (routing, DI, config, health probes)"},
                    {"id": "ACRME-T010103", "title": "Configure API gateway routes, request size limits, and correlation-ID propagation"},
                    {"id": "ACRME-T010104", "title": "Add structured logging and distributed tracing baseline"},
                ],
            },
            {
                "id": "ACRME-S0102",
                "title": "Saga orchestrator and command/event bus",
                "as_a": "platform engineer",
                "i_want": "a persisted saga orchestrator driving operation workers over a command/event bus",
                "so_that": "multi-step Azure operations run reliably with checkpoints and compensation",
                "priority": "Highest", "points": 13, "phase": "P1",
                "prr_refs": ["§23", "§38 Reliability"],
                "depends_on": ["ACRME-S0101"],
                "acceptance": [
                    "Sagas persist each step with a checkpoint and support compensation on failure (closes R-26).",
                    "Operation workers consume commands from the bus and publish events idempotently.",
                    "A partially failed saga can be resumed or compensated without duplicate side effects.",
                    "Saga state is queryable via the operation resource.",
                ],
                "tasks": [
                    {"id": "ACRME-T010201", "title": "Implement persisted saga state machine with checkpointing"},
                    {"id": "ACRME-T010202", "title": "Implement command/event bus abstraction and worker pool"},
                    {"id": "ACRME-T010203", "title": "Implement compensation handlers and partial-saga recovery"},
                    {"id": "ACRME-T010204", "title": "Add idempotent event publication and de-duplication"},
                ],
            },
            {
                "id": "ACRME-S0103",
                "title": "Authoritative engine state store and regional snapshot store",
                "as_a": "platform engineer",
                "i_want": "an authoritative engine-intent store plus a regional snapshot store",
                "so_that": "engine intent and cached Azure state are separated with clear ownership",
                "priority": "Highest", "points": 8, "phase": "P1",
                "prr_refs": ["§23", "§34", "R-33"],
                "depends_on": ["ACRME-S0101"],
                "acceptance": [
                    "Engine state store is authoritative for engine intent; Azure RPs remain authoritative for Azure state.",
                    "Regional snapshot store holds versioned snapshots consumed by placement.",
                    "Throughput is load-tested and autoscale target documented (closes R-33).",
                    "Optimistic concurrency (state version) is enforced on writes.",
                ],
                "tasks": [
                    {"id": "ACRME-T010301", "title": "Model and provision the authoritative state store with versioning"},
                    {"id": "ACRME-T010302", "title": "Model and provision the versioned regional snapshot store"},
                    {"id": "ACRME-T010303", "title": "Load-test throughput and set autoscale targets (R-33)"},
                ],
            },
            {
                "id": "ACRME-S0104",
                "title": "Provider-isolated Azure Resource Manager adapters",
                "as_a": "platform engineer",
                "i_want": "Azure API adapters isolated per resource provider behind a stable interface",
                "so_that": "preview APIs can be flag-gated and swapped without touching business logic",
                "priority": "High", "points": 5, "phase": "P1",
                "prr_refs": ["§23", "§21", "R-01"],
                "depends_on": ["ACRME-S0102"],
                "acceptance": [
                    "Compute, Reservations, Quota, and Resource Graph adapters sit behind stable interfaces.",
                    "Each adapter records API version used per call for evidence.",
                    "Adapters are individually mockable for unit tests.",
                ],
                "tasks": [
                    {"id": "ACRME-T010401", "title": "Define adapter interfaces per resource provider"},
                    {"id": "ACRME-T010402", "title": "Implement Compute/Reservations/Quota/ARG adapters with API-version capture"},
                    {"id": "ACRME-T010403", "title": "Add adapter-level mocks and contract fixtures"},
                ],
            },
            {
                "id": "ACRME-S0105",
                "title": "Management-group and subscription topology bootstrap",
                "as_a": "platform operator",
                "i_want": "the platform/customer MG and provider/consumer subscription topology provisioned as code",
                "so_that": "the engine UAMI and CRGs live in a governed, repeatable hierarchy",
                "priority": "High", "points": 5, "phase": "P1",
                "prr_refs": ["§24"],
                "depends_on": [],
                "acceptance": [
                    "Platform MG (provider + engine subs) and customer MG (prod/nonprod/dr subs) provisioned via IaC.",
                    "Engine UAMI created in the engine subscription and referenced by downstream role assignments.",
                    "Topology is parameterised so a customer need not share one hierarchy.",
                ],
                "tasks": [
                    {"id": "ACRME-T010501", "title": "Author IaC for management-group and subscription topology"},
                    {"id": "ACRME-T010502", "title": "Provision engine User-Assigned Managed Identity"},
                    {"id": "ACRME-T010503", "title": "Parameterise topology for per-customer variation"},
                ],
            },
        ],
    },
    # =====================================================================
    {
        "id": "ACRME-E02",
        "name": "Subscription & Onboarding Lifecycle",
        "goal": "Onboard and offboard customer subscriptions with provider/consumer "
                "authorization validation, location-separation enforcement, and full "
                "read-back before a customer is marked ready.",
        "prr_refs": ["§22 Must", "§26", "§43 Onboarding", "Runbook B"],
        "stories": [
            {
                "id": "ACRME-S0201",
                "title": "Subscription onboarding workflow with prerequisite gates",
                "as_a": "operations engineer",
                "i_want": "a gated onboarding workflow that collects inputs and validates every prerequisite",
                "so_that": "no customer reaches shared capacity until all checks pass and are recorded",
                "priority": "Highest", "points": 13, "phase": "P1",
                "prr_refs": ["§43 Onboarding", "§22 Must"],
                "depends_on": ["ACRME-S0102"],
                "acceptance": [
                    "Onboarding collects account details, environments, SKUs/regions, recovery objectives, and consent.",
                    "Workflow blocks progression until zone map, sharing read-back, quota, and DR-floor checks pass.",
                    "Customer marked ready only after all confirmation gates succeed.",
                    "Every gate result is persisted to the audit trail.",
                ],
                "tasks": [
                    {"id": "ACRME-T020101", "title": "Model ManagedSubscription entity and onboarding state machine"},
                    {"id": "ACRME-T020102", "title": "Implement input-collection and consent capture step"},
                    {"id": "ACRME-T020103", "title": "Wire prerequisite gates (zone, sharing, quota, DR floor) as blocking checks"},
                    {"id": "ACRME-T020104", "title": "Implement 'ready' marking with full read-back confirmation"},
                ],
            },
            {
                "id": "ACRME-S0202",
                "title": "Provider and consumer authorization validation",
                "as_a": "security-conscious operator",
                "i_want": "provider registration and consumer deployment rights validated during onboarding",
                "so_that": "sharing and deployment cannot proceed on an unauthorized subscription",
                "priority": "Highest", "points": 8, "phase": "P1",
                "prr_refs": ["§25", "§22 Must"],
                "depends_on": ["ACRME-S0201"],
                "acceptance": [
                    "Provider subscription and RP registration validated before any sharing action.",
                    "Consumer deployment identity rights on the target CRG validated and read back.",
                    "Validation failure blocks onboarding with a structured precondition error.",
                ],
                "tasks": [
                    {"id": "ACRME-T020201", "title": "Validate provider subscription + resource provider registration"},
                    {"id": "ACRME-T020202", "title": "Validate consumer deployment identity rights on CRG scope"},
                    {"id": "ACRME-T020203", "title": "Emit structured precondition failures on authorization gaps"},
                ],
            },
            {
                "id": "ACRME-S0203",
                "title": "Location separation enforcement (hard constraint) at onboarding",
                "as_a": "capacity architect",
                "i_want": "onboarding to reject layouts where Prod/NonProd/DR are not correctly separated",
                "so_that": "a single regional event cannot take out incompatible environments",
                "priority": "Highest", "points": 5, "phase": "P1",
                "prr_refs": ["§43 Onboarding", "HC separation"],
                "depends_on": ["ACRME-S0201"],
                "acceptance": [
                    "Prod and DR in the same location is rejected; Prod and NonProd in the same location is rejected.",
                    "NonProd co-located with DR is allowed only with recorded policy + customer acceptance.",
                    "Rejection reason is explicit and audited.",
                ],
                "tasks": [
                    {"id": "ACRME-T020301", "title": "Implement separation-rule validator for environment layout"},
                    {"id": "ACRME-T020302", "title": "Add NonProd/DR co-location policy exception with acceptance capture"},
                ],
            },
            {
                "id": "ACRME-S0204",
                "title": "Subscription lifecycle monitoring and offboarding",
                "as_a": "operations engineer",
                "i_want": "lifecycle monitoring plus a controlled offboarding checklist",
                "so_that": "suspension/transfer and offboarding never strand running VM restarts",
                "priority": "High", "points": 8, "phase": "P1",
                "prr_refs": ["Runbook B", "R-10", "R-28"],
                "depends_on": ["ACRME-S0202"],
                "acceptance": [
                    "Subscription suspension/transfer triggers revalidation and an alert (closes R-28).",
                    "Offboarding checks active associations before removing sharing (closes R-10).",
                    "Offboarding defaults to deny when active associations exist.",
                ],
                "tasks": [
                    {"id": "ACRME-T020401", "title": "Implement subscription lifecycle monitor + revalidation (R-28)"},
                    {"id": "ACRME-T020402", "title": "Implement offboarding checklist with association pre-checks (R-10)"},
                ],
            },
        ],
    },
    # =====================================================================
    {
        "id": "ACRME-E03",
        "name": "CRG & Capacity Reservation Management",
        "goal": "Inventory, create, and safely mutate Capacity Reservation Groups and "
                "Capacity Reservations modeled by SKU and zone, with guarded quantity "
                "changes and no unsafe auto-decrease in Phase 1.",
        "prr_refs": ["§25", "§30", "§5 CR quantity update"],
        "stories": [
            {
                "id": "ACRME-S0301",
                "title": "CRG and CR inventory by SKU and zone",
                "as_a": "capacity operator",
                "i_want": "authoritative inventory of CRGs and CRs modeled per SKU and zone",
                "so_that": "placement and scaling decisions run on accurate capacity state",
                "priority": "Highest", "points": 8, "phase": "P1",
                "prr_refs": ["§25", "§34"],
                "depends_on": ["ACRME-S0104"],
                "acceptance": [
                    "CRG hierarchy (Prod/NonProd/DR per region) inventoried with CRs by SKU and zone.",
                    "Provider-side inventory is authoritative; ARG used only for diagnostics (R-03).",
                    "Inventory refresh confirms against ARM before use for mutation (R-04).",
                ],
                "tasks": [
                    {"id": "ACRME-T030101", "title": "Model CapacityReservationGroup and CapacityReservation entities"},
                    {"id": "ACRME-T030102", "title": "Implement inventory sync with SKU/zone dimensioning"},
                    {"id": "ACRME-T030103", "title": "Mark provider inventory authoritative; ARG diagnostics-only (R-03/R-04)"},
                ],
            },
            {
                "id": "ACRME-S0302",
                "title": "Guarded CR quantity increase",
                "as_a": "capacity operator",
                "i_want": "approval-gated CR quantity increases via tracked operations",
                "so_that": "capacity grows safely without cost or capacity surprises",
                "priority": "High", "points": 8, "phase": "P1",
                "prr_refs": ["§30", "R-15", "G-24"],
                "depends_on": ["ACRME-S0301", "ACRME-S0902"],
                "acceptance": [
                    "CapacityIncreaseRequest entity with lifecycle, approval, retry, and cancellation (closes G-24).",
                    "Increase requires operator approval and enforces a policy maximum delta (R-15).",
                    "Quantity updated only after validated quota; actual quantity confirmed after change.",
                ],
                "tasks": [
                    {"id": "ACRME-T030201", "title": "Model CapacityIncreaseRequest entity + lifecycle (G-24)"},
                    {"id": "ACRME-T030202", "title": "Implement approval gate and max-delta guard (R-15)"},
                    {"id": "ACRME-T030203", "title": "Implement quota-validated update with post-change confirmation"},
                    {"id": "ACRME-T030204", "title": "Add retry and cancellation handling to the request lifecycle"},
                ],
            },
            {
                "id": "ACRME-S0303",
                "title": "Guarded CR reduction with zero-reduction and running-VM safety",
                "as_a": "capacity operator",
                "i_want": "CR reduction blocked for unknown/destructive scenarios",
                "so_that": "reductions never silently remove capacity relied on by running VMs",
                "priority": "High", "points": 5, "phase": "P1",
                "prr_refs": ["§5 CR quantity update", "R-09"],
                "depends_on": ["ACRME-S0301"],
                "acceptance": [
                    "Reduction below allocated/running usage is blocked with a scenario matrix (R-09).",
                    "Zero-size and unknown-behavior scenarios are blocked pending POC evidence.",
                    "Auto-decrease is disabled in Phase 1.",
                ],
                "tasks": [
                    {"id": "ACRME-T030301", "title": "Implement reduction floor validator against allocation/running usage"},
                    {"id": "ACRME-T030302", "title": "Encode CR reduction scenario matrix and block unknowns (R-09)"},
                ],
            },
        ],
    },
    # =====================================================================
    {
        "id": "ACRME-E04",
        "name": "CRG Sharing & Consumer Authorization",
        "goal": "Explicit, read-back-verified CRG sharing across subscriptions with the "
                "100-consumer ceiling handled by sharding, plus safe and forced unsharing.",
        "prr_refs": ["§25 Sharing", "§5 CRG sharing", "Runbook B", "R-02"],
        "stories": [
            {
                "id": "ACRME-S0401",
                "title": "Explicit CRG sharing workflow with full read-back",
                "as_a": "sharing operator",
                "i_want": "a sharing sequence that validates, adds, grants, and reads back every step",
                "so_that": "a relationship is only 'active' after confirmed state",
                "priority": "Highest", "points": 8, "phase": "P1",
                "prr_refs": ["§25 Sharing sequence"],
                "depends_on": ["ACRME-S0202"],
                "acceptance": [
                    "Sharing adds only explicitly named consumer subscriptions (never tenant-wide).",
                    "Sharing profile and role state are read back and recorded before returning success.",
                    "SharingRelationship entity persisted with active status.",
                ],
                "tasks": [
                    {"id": "ACRME-T040101", "title": "Model SharingRelationship entity"},
                    {"id": "ACRME-T040102", "title": "Implement validate->add->grant->readback sharing saga"},
                    {"id": "ACRME-T040103", "title": "Persist confirmed relationship and expose via Query API"},
                ],
            },
            {
                "id": "ACRME-S0402",
                "title": "100-consumer ceiling monitoring and CRG sharding",
                "as_a": "capacity architect",
                "i_want": "continuous relationship-count monitoring and a sharding path",
                "so_that": "the pool never silently breaches the 100-consumer platform limit",
                "priority": "High", "points": 5, "phase": "P1",
                "prr_refs": ["R-02", "§5 CRG sharing"],
                "depends_on": ["ACRME-S0401"],
                "acceptance": [
                    "Relationship count monitored continuously, not only at create time (R-02).",
                    "Approaching-limit alert fires before the ceiling is hit.",
                    "Documented sharding procedure splits a pool without downtime.",
                ],
                "tasks": [
                    {"id": "ACRME-T040201", "title": "Implement consumer-count monitor and threshold alert (R-02)"},
                    {"id": "ACRME-T040202", "title": "Document and script CRG sharding procedure"},
                ],
            },
            {
                "id": "ACRME-S0403",
                "title": "Safe and forced unsharing with restart-hazard protection",
                "as_a": "sharing operator",
                "i_want": "unsharing to default-deny when active associations exist",
                "so_that": "removing sharing never strands VM restarts",
                "priority": "High", "points": 5, "phase": "P1",
                "prr_refs": ["Runbook B", "R-10"],
                "depends_on": ["ACRME-S0401"],
                "acceptance": [
                    "Forced unsharing rejects by default when active associations exist (Runbook B).",
                    "Consumer owner approval captured before any forced action; impact record retained.",
                    "ForcedUnsharingRequested alert fires on active associations.",
                ],
                "tasks": [
                    {"id": "ACRME-T040301", "title": "Implement association enumeration + default-deny gate"},
                    {"id": "ACRME-T040302", "title": "Implement approval capture, read-back, and impact record"},
                ],
            },
            {
                "id": "ACRME-S0404",
                "title": "Sharing drift detection",
                "as_a": "SRE",
                "i_want": "detection when desired and actual sharing profiles differ",
                "so_that": "unauthorized or missing consumers are surfaced immediately",
                "priority": "High", "points": 3, "phase": "P1",
                "prr_refs": ["§37 Alerts", "R-03"],
                "depends_on": ["ACRME-S0401"],
                "acceptance": [
                    "SharingDrift alert on desired/actual mismatch; UnauthorizedConsumer alert on unapproved subscription.",
                    "Drift check runs on the adaptive reconciliation cadence.",
                ],
                "tasks": [
                    {"id": "ACRME-T040401", "title": "Implement desired-vs-actual sharing comparator"},
                    {"id": "ACRME-T040402", "title": "Wire SharingDrift and UnauthorizedConsumer alerts"},
                ],
            },
        ],
    },
    # =====================================================================
    {
        "id": "ACRME-E05",
        "name": "Quota Group Management",
        "goal": "Two-group-per-region quota model (Prod group; shared NonProd+DR group) "
                "with provider/consumer/group validation and Preview groupType handling.",
        "prr_refs": ["§26", "§5 Quota Groups", "FC-11", "R-05", "R-06", "R-43"],
        "stories": [
            {
                "id": "ACRME-S0501",
                "title": "Two-group-per-region quota model",
                "as_a": "quota owner",
                "i_want": "a Prod quota group and a shared NonProd+DR quota group per region",
                "so_that": "budgets are governed separately without DR starving on NonProd demand",
                "priority": "Highest", "points": 8, "phase": "P1",
                "prr_refs": ["§26"],
                "depends_on": ["ACRME-S0104"],
                "acceptance": [
                    "QuotaGroup entities model Prod and shared NonProd+DR groups per region.",
                    "Group formulas and exact controls implemented per §26.",
                    "Membership never treated as proof a specific subscription can deploy (R-06).",
                ],
                "tasks": [
                    {"id": "ACRME-T050101", "title": "Model QuotaGroup and SubscriptionQuotaRecord entities"},
                    {"id": "ACRME-T050102", "title": "Implement two-group-per-region provisioning + formulas"},
                    {"id": "ACRME-T050103", "title": "Enforce mandatory subscription-level checks (R-06)"},
                ],
            },
            {
                "id": "ACRME-S0502",
                "title": "Provider, consumer, and group quota validation",
                "as_a": "quota owner",
                "i_want": "independent validation of provider, consumer, and group quota",
                "so_that": "placement never assumes quota it does not have",
                "priority": "Highest", "points": 5, "phase": "P1",
                "prr_refs": ["§5", "R-39"],
                "depends_on": ["ACRME-S0501"],
                "acceptance": [
                    "Provider quota not double-counted; API semantics validated (R-39).",
                    "Consumer and group quota validated independently before commit.",
                    "QuotaStateUnknown alert on unavailable/stale reads.",
                ],
                "tasks": [
                    {"id": "ACRME-T050201", "title": "Implement provider/consumer/group quota validators"},
                    {"id": "ACRME-T050202", "title": "Validate quota API semantics to avoid double count (R-39)"},
                    {"id": "ACRME-T050203", "title": "Wire QuotaStateUnknown alert"},
                ],
            },
            {
                "id": "ACRME-S0503",
                "title": "Quota increase endpoint with propagation handling",
                "as_a": "quota owner",
                "i_want": "a tracked quota-increase submission that polls for confirmed state",
                "so_that": "the engine never assumes a propagation SLA",
                "priority": "High", "points": 5, "phase": "P1",
                "prr_refs": ["§30", "B-6", "R-08"],
                "depends_on": ["ACRME-S0502"],
                "acceptance": [
                    "Quota action submitted only when validated as required; polled to confirmed state (B-6).",
                    "Observed propagation distribution recorded; timeout + manual path in runbook.",
                ],
                "tasks": [
                    {"id": "ACRME-T050301", "title": "Implement quota-increase submission + async polling"},
                    {"id": "ACRME-T050302", "title": "Record propagation distribution; add timeout/manual path (B-6)"},
                ],
            },
            {
                "id": "ACRME-S0504",
                "title": "Quota Group groupType Preview status handling (FC-11 / R-43)",
                "as_a": "quota owner",
                "i_want": "enforced-vs-advisory groupType treated as a Preview dependency",
                "so_that": "the engine never silently relies on preview-only enforcement semantics",
                "priority": "Medium", "points": 3, "phase": "P1",
                "prr_refs": ["FC-11", "R-43"],
                "depends_on": ["ACRME-S0501"],
                "acceptance": [
                    "groupType enforcement semantics gated behind a Preview feature flag (FC-11).",
                    "POC-30 confirms required API version; governance acceptance recorded if needed (R-43).",
                ],
                "tasks": [
                    {"id": "ACRME-T050401", "title": "Flag-gate groupType enforcement reliance (FC-11)"},
                    {"id": "ACRME-T050402", "title": "Confirm required API version via POC-30 and record acceptance"},
                ],
            },
        ],
    },
    # =====================================================================
    {
        "id": "ACRME-E06",
        "name": "Cross-Subscription Zone Alignment",
        "goal": "Build and apply per-subscription physical-to-logical zone mapping so shared "
                "reservations land in the correct physical zone; reject on missing mapping.",
        "prr_refs": ["§5 FC-06", "§42 POC 6a", "R-11", "R-41"],
        "stories": [
            {
                "id": "ACRME-S0601",
                "title": "Zone mapping table built and verified at onboarding",
                "as_a": "placement owner",
                "i_want": "a physical-to-logical zone map per subscription and region built at onboarding",
                "so_that": "shared reservations align to the correct physical zone across accounts",
                "priority": "Highest", "points": 8, "phase": "P1",
                "prr_refs": ["FC-06", "R-41"],
                "depends_on": ["ACRME-S0104"],
                "acceptance": [
                    "availabilityZoneMappings read for provider and consumer subscriptions for all managed regions.",
                    "ZoneMappingRecord persisted per subscription/region and read back (FC-06).",
                    "Onboarding blocks if the map cannot be built and verified.",
                ],
                "tasks": [
                    {"id": "ACRME-T060101", "title": "Model ZoneMappingRecord entity"},
                    {"id": "ACRME-T060102", "title": "Implement Subscriptions-List-Locations zone-mapping fetch"},
                    {"id": "ACRME-T060103", "title": "Persist + read-back mapping; block onboarding on failure"},
                ],
            },
            {
                "id": "ACRME-S0602",
                "title": "Zone translation applied before every consumer deployment",
                "as_a": "placement engine",
                "i_want": "zone translation applied before every zonal deployment, rejecting on missing mapping",
                "so_that": "a logical/physical mismatch never causes a silent deployment failure",
                "priority": "Highest", "points": 5, "phase": "P1",
                "prr_refs": ["R-41", "POC 6a"],
                "depends_on": ["ACRME-S0601"],
                "acceptance": [
                    "Translation resolves the correct consumer logical zone for a provider physical zone.",
                    "Deployment rejected with ZoneMappingUnavailable when mapping is absent (R-41).",
                    "Targeted refresh on churn keeps mapping current (R-11).",
                ],
                "tasks": [
                    {"id": "ACRME-T060201", "title": "Implement zone-translation algorithm (physical<->logical)"},
                    {"id": "ACRME-T060202", "title": "Enforce ZoneMappingUnavailable rejection path (R-41)"},
                    {"id": "ACRME-T060203", "title": "Add event-triggered targeted mapping refresh (R-11)"},
                ],
            },
        ],
    },
    # =====================================================================
    {
        "id": "ACRME-E07",
        "name": "Region Selection & Placement Engine",
        "goal": "Production-ready region selection: classification model, two-stage "
                "eligibility filter, Scenario 1/2 input modes, Middle East cross-geo "
                "extension, and the restricted-region exception workflow.",
        "prr_refs": ["§27", "§43 Region selection", "HC-1..HC-10", "VR-1..VR-11"],
        "stories": [
            {
                "id": "ACRME-S0701",
                "title": "Region classification model (Standard / Restricted / Cross-Geo Extension)",
                "as_a": "placement owner",
                "i_want": "every managed region classified and Restricted regions pre-filtered before scoring",
                "so_that": "constrained regions never enter automated placement",
                "priority": "Highest", "points": 8, "phase": "P1",
                "prr_refs": ["§27 Classification"],
                "depends_on": ["ACRME-S0103"],
                "acceptance": [
                    "Standard, Restricted, and Cross-Geo Extension classes encoded in PlacementPolicy.",
                    "Restricted regions excluded as a pre-filter ahead of all hard constraints (HC-9).",
                    "Unknown region rejected (VR-1); Restricted excluded from scoring (VR-2).",
                ],
                "tasks": [
                    {"id": "ACRME-T070101", "title": "Model region classification in PolicyVersion/PlacementPolicy"},
                    {"id": "ACRME-T070102", "title": "Implement Stage 1 classification pre-filter (HC-9)"},
                    {"id": "ACRME-T070103", "title": "Implement VR-1/VR-2 validation rules"},
                ],
            },
            {
                "id": "ACRME-S0702",
                "title": "Two-stage eligibility decision tree (HC-1..HC-10)",
                "as_a": "placement engine",
                "i_want": "surviving candidates evaluated against hard constraints HC-1..HC-10 before scoring",
                "so_that": "only fully eligible Standard regions reach the scorer",
                "priority": "Highest", "points": 8, "phase": "P1",
                "prr_refs": ["§27 Decision tree", "§27 HC-1..HC-10"],
                "depends_on": ["ACRME-S0701"],
                "acceptance": [
                    "Stage 2 applies HC-1..HC-10 (capacity, quota, zone, separation, freshness, geo, DR floor, NonProd/DR integrity, ME cross-geo, extension-path approval).",
                    "Regions failing any HC are excluded from scoring with a recorded reason.",
                    "HC-9 STANDARD_REGION_ONLY and HC-10 CROSS_GEO_EXTENSION_PATH_APPROVED enforced.",
                ],
                "tasks": [
                    {"id": "ACRME-T070201", "title": "Implement HC-1..HC-8 constraint checks"},
                    {"id": "ACRME-T070202", "title": "Implement HC-9 and HC-10 constraint checks"},
                    {"id": "ACRME-T070203", "title": "Record per-region exclusion reasons for audit"},
                ],
            },
            {
                "id": "ACRME-S0703",
                "title": "Scenario 1 — geography-based Prod region derivation",
                "as_a": "customer",
                "i_want": "to supply an Azure geography and have the engine derive the Prod anchor",
                "so_that": "I get the best Standard region in my geography without naming one",
                "priority": "Highest", "points": 8, "phase": "P1",
                "prr_refs": ["§27 Prod input modes", "§28 PS_Prod", "VR-4"],
                "depends_on": ["ACRME-S0702", "ACRME-S0801"],
                "acceptance": [
                    "Candidate set = Standard regions in geography minus HC exclusions.",
                    "argmax(PS_Prod); deterministic tie-break by Standard-region list order; cold-start default = first listed.",
                    "Geography-scoped exhaustion error if none eligible (VR-4); never falls outside geography.",
                    "Derived region + all candidate scores + policy version persisted for replay.",
                ],
                "tasks": [
                    {"id": "ACRME-T070301", "title": "Implement geography candidate-set builder"},
                    {"id": "ACRME-T070302", "title": "Implement argmax(PS_Prod) selection + deterministic tie-break"},
                    {"id": "ACRME-T070303", "title": "Implement geography-scoped exhaustion error (VR-4)"},
                    {"id": "ACRME-T070304", "title": "Persist derivation trace to OperationRecord"},
                ],
            },
            {
                "id": "ACRME-S0704",
                "title": "Scenario 2 — specific region input validation",
                "as_a": "customer",
                "i_want": "to name a specific region and have it validated or routed to exception",
                "so_that": "a Standard region is used directly and a Restricted region needs approval",
                "priority": "Highest", "points": 5, "phase": "P1",
                "prr_refs": ["§27 Prod input modes"],
                "depends_on": ["ACRME-S0702"],
                "acceptance": [
                    "Standard region validated against HC-1..HC-10 then set as Prod anchor; PS_Prod used for post-validation only.",
                    "Restricted region routed to the Exception Deployment Workflow.",
                    "Both modes converge on a fixed, validated Prod anchor.",
                ],
                "tasks": [
                    {"id": "ACRME-T070401", "title": "Implement Standard-region direct validation path"},
                    {"id": "ACRME-T070402", "title": "Route Restricted region input to exception workflow"},
                ],
            },
            {
                "id": "ACRME-S0705",
                "title": "Sequential CVAL then DR selection from Prod anchor",
                "as_a": "placement engine",
                "i_want": "CVAL and DR selected sequentially from the fixed Prod anchor",
                "so_that": "the three-environment layout respects separation and scoring",
                "priority": "Highest", "points": 5, "phase": "P1",
                "prr_refs": ["§27", "§28 PS_NonProd/PS_DR"],
                "depends_on": ["ACRME-S0703", "ACRME-S0704"],
                "acceptance": [
                    "CVAL selected via PS_NonProd (=PS_CVAL); DR via PS_DR from Standard regions.",
                    "Separation constraints honored across the three environments.",
                    "All three environment scores persisted together for replay.",
                ],
                "tasks": [
                    {"id": "ACRME-T070501", "title": "Implement sequential CVAL selection (PS_NonProd)"},
                    {"id": "ACRME-T070502", "title": "Implement sequential DR selection (PS_DR)"},
                ],
            },
            {
                "id": "ACRME-S0706",
                "title": "Middle East cross-geo extension (Saudi Arabia/UAE North → Belgium Central)",
                "as_a": "placement owner",
                "i_want": "Middle East DR to use the approved Belgium Central extension path",
                "so_that": "the three-region minimum is met where only two in-geo regions exist",
                "priority": "High", "points": 5, "phase": "P1",
                "prr_refs": ["§27 Middle East", "HC-10", "R-12"],
                "depends_on": ["ACRME-S0705"],
                "acceptance": [
                    "Prod = argmax(PS_Prod) over Saudi Arabia/UAE North; CVAL = the other in-geo region.",
                    "DR = Belgium Central via the only approved extension path; validated against HC-1..HC-10 incl. DR floor.",
                    "If Belgium Central fails, placement is blocked with an ops alert (no silent substitution).",
                ],
                "tasks": [
                    {"id": "ACRME-T070601", "title": "Implement Middle East Prod/CVAL in-geo assignment"},
                    {"id": "ACRME-T070602", "title": "Implement Belgium Central cross-geo DR with HC validation"},
                    {"id": "ACRME-T070603", "title": "Block + alert on degraded extension path (no substitution)"},
                ],
            },
            {
                "id": "ACRME-S0707",
                "title": "Exception-based placement workflow for Restricted regions (EC-1..EC-4)",
                "as_a": "governance owner",
                "i_want": "restricted-region use gated behind four exception conditions",
                "so_that": "no Restricted region enters production without explicit approval",
                "priority": "High", "points": 5, "phase": "P1",
                "prr_refs": ["§27 Exception workflow", "VR-3"],
                "depends_on": ["ACRME-S0704"],
                "acceptance": [
                    "EC-1 explicit request, EC-2 Production-only, EC-3 approval record, EC-4 Scenario-2 input all required (VR-3).",
                    "On pass: assign Exception Prod Anchor, mark Exception Deployment, emit capacity-constraint warning.",
                    "CVAL/DR still chosen from Standard regions; exception approval ID mandatory in OperationRecord.",
                ],
                "tasks": [
                    {"id": "ACRME-T070701", "title": "Implement EC-1..EC-4 gate (VR-3)"},
                    {"id": "ACRME-T070702", "title": "Implement Exception Deployment marking + warning"},
                    {"id": "ACRME-T070703", "title": "Require exception approval ID in OperationRecord commit"},
                ],
            },
            {
                "id": "ACRME-S0708",
                "title": "Validation Rule Framework (VR-1..VR-11) and governance controls",
                "as_a": "governance owner",
                "i_want": "the full validation-rule framework and PlacementPolicy governance enforced",
                "so_that": "region-selection changes require approval and are auditable",
                "priority": "Medium", "points": 5, "phase": "P1",
                "prr_refs": ["§27 VR framework", "§27 Governance"],
                "depends_on": ["ACRME-S0701"],
                "acceptance": [
                    "VR-1..VR-11 implemented with the specified failure actions.",
                    "Classification/extension changes require PlacementPolicy update + governance approval + Decision Log entry.",
                    "Policy version referenced on every placement decision.",
                ],
                "tasks": [
                    {"id": "ACRME-T070801", "title": "Implement remaining VR-5..VR-11 rules"},
                    {"id": "ACRME-T070802", "title": "Enforce PlacementPolicy change governance + Decision Log"},
                ],
            },
        ],
    },
    # =====================================================================
    {
        "id": "ACRME-E08",
        "name": "Placement Scoring & Forecasting",
        "goal": "Implement the corrected, clamped scoring formulas (PS_Prod/PS_NonProd/"
                "PS_DR) with demand-weighted distribution, versioned weights, and "
                "advisory forecasting.",
        "prr_refs": ["§28", "§4 Scoring", "R-36", "R-37", "R-29"],
        "stories": [
            {
                "id": "ACRME-S0801",
                "title": "Corrected, clamped scoring formulas with versioned weights",
                "as_a": "placement owner",
                "i_want": "PS_Prod/PS_NonProd/PS_DR with clamped components and versioned weights",
                "so_that": "scores are bounded [0,1], replayable, and auditable",
                "priority": "Highest", "points": 8, "phase": "P1",
                "prr_refs": ["§28 Corrected scoring"],
                "depends_on": ["ACRME-S0103"],
                "acceptance": [
                    "Each component clamped via Clamp(x)=max(0,min(1,x)); score in [0,1].",
                    "Default weights (α0.30,β0.20,γ0.25,δ0.15,ε0.10) retained for pilot comparison; PS_NonProd uses revised weights.",
                    "Weights carry a PolicyVersion; inputs + version persisted per decision.",
                ],
                "tasks": [
                    {"id": "ACRME-T080101", "title": "Implement PS_Prod/PS_NonProd/PS_DR with clamping"},
                    {"id": "ACRME-T080102", "title": "Externalise weights into versioned PolicyVersion"},
                    {"id": "ACRME-T080103", "title": "Persist score inputs + policy version to OperationRecord"},
                ],
            },
            {
                "id": "ACRME-S0802",
                "title": "Demand-weighted distribution and SKU-dimensional model",
                "as_a": "placement owner",
                "i_want": "distribution computed from demand units and scoring per SKU/zone",
                "so_that": "fairness reflects real demand, not customer count",
                "priority": "High", "points": 5, "phase": "P1",
                "prr_refs": ["§28 Distribution", "R-36", "R-37"],
                "depends_on": ["ACRME-S0801"],
                "acceptance": [
                    "Distribution = 1 - Region_Assigned_Demand / Total_Assigned_Demand (R-37).",
                    "Scoring is SKU-dimensional to avoid simple-formula invalidation (R-36).",
                ],
                "tasks": [
                    {"id": "ACRME-T080201", "title": "Implement demand-weighted distribution signal (R-37)"},
                    {"id": "ACRME-T080202", "title": "Make scoring SKU/zone-dimensional (R-36)"},
                ],
            },
            {
                "id": "ACRME-S0803",
                "title": "Advisory forecasting with measured accuracy",
                "as_a": "capacity planner",
                "i_want": "forecast quantity recommendations that stay advisory until accuracy is measured",
                "so_that": "forecasts never drive unsafe automatic reduction",
                "priority": "Medium", "points": 5, "phase": "P2",
                "prr_refs": ["§28 Forecast", "R-29", "ForecastError alert"],
                "depends_on": ["ACRME-S0801"],
                "acceptance": [
                    "Forecast_Quantity = ceil(Forecast_Peak×(1+Growth_Buffer)+DR_Buffer) with 30/60/90-day horizons.",
                    "Recommendations advisory-only; reduction never automatic (R-29).",
                    "ForecastError alert when error exceeds policy; accuracy/false-positive tracked.",
                ],
                "tasks": [
                    {"id": "ACRME-T080301", "title": "Implement ForecastRecord entity + forecast formula"},
                    {"id": "ACRME-T080302", "title": "Keep forecast advisory; wire ForecastError alert (R-29)"},
                ],
            },
            {
                "id": "ACRME-S0804",
                "title": "Shadow joint-optimization comparison",
                "as_a": "placement owner",
                "i_want": "the sequential method compared against a shadow joint-optimization method",
                "so_that": "divergence evidence is gathered before trusting either for auto-commit",
                "priority": "Medium", "points": 5, "phase": "P2",
                "prr_refs": ["§4 Sequential placement", "§22 Should"],
                "depends_on": ["ACRME-S0801"],
                "acceptance": [
                    "Both methods run without mutating live resources; divergences measured and logged.",
                    "Comparison report available for governance review.",
                ],
                "tasks": [
                    {"id": "ACRME-T080401", "title": "Implement shadow joint-optimization evaluator"},
                    {"id": "ACRME-T080402", "title": "Log divergences + produce comparison report"},
                ],
            },
        ],
    },
    # =====================================================================
    {
        "id": "ACRME-E09",
        "name": "State Model & Concurrency Controls",
        "goal": "Implement the engine state machine (EngineModeState) with conditional "
                "transitions and dual approval, and atomic capacity holds to prevent "
                "over-assignment. Production blocker G-15 / B-7.",
        "prr_refs": ["§29", "G-15", "B-3", "B-7", "R-35"],
        "stories": [
            {
                "id": "ACRME-S0901",
                "title": "Engine state machine with conditional transitions and dual approval (G-15)",
                "as_a": "SRE",
                "i_want": "EngineModeState with guarded transitions, dual approval, and incident hold",
                "so_that": "normal and crisis operations can never illegally mix",
                "priority": "Highest", "points": 13, "phase": "P1",
                "prr_refs": ["§29 State machine", "G-15", "R-35"],
                "depends_on": ["ACRME-S0103"],
                "acceptance": [
                    "States STEADY_STATE, DR_DECLARATION_PENDING, DR_EVENT_ACTIVE, FAILBACK_PENDING, INCIDENT_HOLD implemented.",
                    "Transitions use conditional writes + state version; dual approval required to leave STEADY_STATE.",
                    "Fault-injection test shows no illegal transition (closes G-15/R-35); EngineModeConflict alert wired.",
                    "EngineModeState carries scope, mode, version, incident ID, approvers, lease owner/expiry, recovery checkpoint.",
                ],
                "tasks": [
                    {"id": "ACRME-T090101", "title": "Model EngineModeState entity with all required fields"},
                    {"id": "ACRME-T090102", "title": "Implement transition guards + conditional writes"},
                    {"id": "ACRME-T090103", "title": "Implement dual-approval and incident-hold transitions"},
                    {"id": "ACRME-T090104", "title": "Write fault-injection tests proving no illegal transition"},
                    {"id": "ACRME-T090105", "title": "Wire EngineModeConflict alert"},
                ],
            },
            {
                "id": "ACRME-S0902",
                "title": "Atomic capacity holds with optimistic concurrency (B-7 / G-20)",
                "as_a": "placement engine",
                "i_want": "an atomic hold keyed by region/SKU/zone/env/policy before returning an assignment",
                "so_that": "concurrent placements cannot double-assign the same capacity",
                "priority": "Highest", "points": 8, "phase": "P1",
                "prr_refs": ["§29 Capacity holds", "B-7", "R-23", "G-20"],
                "depends_on": ["ACRME-S0103"],
                "acceptance": [
                    "PlacementHold created before commit; expires if Azure provisioning does not begin.",
                    "Parallel placement test produces exactly one winner (closes B-7/R-23).",
                    "CustomerRegionAssignment linked to hold IDs (closes G-20); PlacementHoldConflict alert wired.",
                ],
                "tasks": [
                    {"id": "ACRME-T090201", "title": "Model PlacementHold + CustomerRegionAssignment entities (G-20)"},
                    {"id": "ACRME-T090202", "title": "Implement optimistic-concurrency hold create/expire"},
                    {"id": "ACRME-T090203", "title": "Write parallel-placement single-winner test (B-7)"},
                    {"id": "ACRME-T090204", "title": "Wire PlacementHoldConflict alert"},
                ],
            },
        ],
    },
    # =====================================================================
    {
        "id": "ACRME-E10",
        "name": "DR Activation & Failback",
        "goal": "Implement guarded DR declaration, per-workload failover orchestration, "
                "engine-enforced DR floor with independent detector, and wave-based failback.",
        "prr_refs": ["§31", "Runbook E", "§5 DR floor", "R-07", "R-27", "R-38"],
        "stories": [
            {
                "id": "ACRME-S1001",
                "title": "DR declaration and failover orchestration",
                "as_a": "DR operator",
                "i_want": "a guarded DR declaration that validates state then orchestrates approved failover",
                "so_that": "failover only runs in a validated DR_EVENT_ACTIVE mode",
                "priority": "High", "points": 8, "phase": "P2",
                "prr_refs": ["§31", "IncidentRecord G-21"],
                "depends_on": ["ACRME-S0901"],
                "acceptance": [
                    "Declaration validates approvals + state version before entering DR_EVENT_ACTIVE.",
                    "Quota, CR, and sharing re-validated from authoritative sources at declaration.",
                    "Per-workload failover status tracked; IncidentRecord persisted (closes G-21).",
                    "Declaration alone does not authorize Tier 2/Tier 3.",
                ],
                "tasks": [
                    {"id": "ACRME-T100101", "title": "Model IncidentRecord + DRCapacityPair entities (G-21)"},
                    {"id": "ACRME-T100102", "title": "Implement DR declaration validation + mode entry"},
                    {"id": "ACRME-T100103", "title": "Implement per-workload failover orchestration"},
                ],
            },
            {
                "id": "ACRME-S1002",
                "title": "Engine-enforced DR floor with independent detector",
                "as_a": "SRE",
                "i_want": "an engine-enforced DR floor plus an independent recalculating detector",
                "so_that": "NonProd expansion fails closed when the floor is at risk",
                "priority": "Highest", "points": 8, "phase": "P1",
                "prr_refs": ["§5 DR floor", "R-07", "R-38", "DRFloorViolation alert"],
                "depends_on": ["ACRME-S0901"],
                "acceptance": [
                    "Independent detector recomputes the floor from assignments/allocations (R-38).",
                    "Automatic NonProd expansion blocked on detector disagreement (fail-closed, R-07).",
                    "DRFloorViolation alert fires when NonProd use exceeds the effective ceiling.",
                ],
                "tasks": [
                    {"id": "ACRME-T100201", "title": "Implement primary DR-floor calculation from potential demand"},
                    {"id": "ACRME-T100202", "title": "Implement independent detector + fail-closed block (R-07)"},
                    {"id": "ACRME-T100203", "title": "Recompute floor from assignments to avoid staleness (R-38)"},
                    {"id": "ACRME-T100204", "title": "Wire DRFloorViolation alert"},
                ],
            },
            {
                "id": "ACRME-S1003",
                "title": "Wave-based failback with readiness gate",
                "as_a": "DR operator",
                "i_want": "failback gated on primary readiness and executed in waves",
                "so_that": "failback never starts before the primary is truly ready",
                "priority": "High", "points": 8, "phase": "P2",
                "prr_refs": ["Runbook E", "R-27"],
                "depends_on": ["ACRME-S1001"],
                "acceptance": [
                    "Readiness gate validates app/data/network/DNS/identity/capacity before failback (R-27).",
                    "Restore in waves with health checks; DR traffic drained only after validation.",
                    "DR floor + reservation policy recalculated; return to STEADY_STATE only after all ops close.",
                ],
                "tasks": [
                    {"id": "ACRME-T100301", "title": "Implement failback readiness gate + approval (R-27)"},
                    {"id": "ACRME-T100302", "title": "Implement wave-based restore + health validation"},
                    {"id": "ACRME-T100303", "title": "Implement conservative DR deallocation + floor recalculation"},
                ],
            },
        ],
    },
    # =====================================================================
    {
        "id": "ACRME-E11",
        "name": "Tier Escalation (Emergency Capacity)",
        "goal": "Implement the tiered emergency-capacity ladder: Tier 1 additive expansion "
                "(gated), Tier 2 quota-neutral transfer (disabled until proven), Tier 3 "
                "blocked in Phase 1.",
        "prr_refs": ["§32", "Runbook C", "Runbook D", "R-16", "R-17", "R-18"],
        "stories": [
            {
                "id": "ACRME-S1101",
                "title": "Tier 1 additive emergency expansion (incident-gated)",
                "as_a": "DR operator",
                "i_want": "Tier 1 expansion allowed only in DR_EVENT_ACTIVE with fresh checks",
                "so_that": "pre-staged headroom is used safely and never outside an incident",
                "priority": "High", "points": 8, "phase": "P2",
                "prr_refs": ["§32", "Runbook C", "R-16"],
                "depends_on": ["ACRME-S0901", "ACRME-S0302"],
                "acceptance": [
                    "Tier 1 rejected unless DR_EVENT_ACTIVE (engine-mode guard, R-16).",
                    "Fresh quota/capacity/sharing confirmed; delta bounded by policy maximum.",
                    "CR increase submitted with idempotency key, polled, and read back before VM deployment.",
                ],
                "tasks": [
                    {"id": "ACRME-T110101", "title": "Implement Tier 1 engine-mode guard (R-16)"},
                    {"id": "ACRME-T110102", "title": "Implement bounded additive expansion + read-back (Runbook C)"},
                ],
            },
            {
                "id": "ACRME-S1102",
                "title": "Tier 2 quota-neutral transfer (disabled until proven)",
                "as_a": "DR operator",
                "i_want": "Tier 2 reallocation behind a proven+approved flag with impact preview",
                "so_that": "NonProd guarantees are never removed unexpectedly",
                "priority": "Medium", "points": 8, "phase": "P2",
                "prr_refs": ["§32", "Runbook D", "B-2", "R-17"],
                "depends_on": ["ACRME-S1101", "ACRME-S0503"],
                "acceptance": [
                    "Tier 2 disabled until release-and-reuse behavior is measured (B-2) and enabled by flag.",
                    "Requires incident mode + approval + customer-impact preview (R-17).",
                    "DR expanded only after authoritative quota headroom is visible; timeout escalates manually.",
                    "EmergencyCapacityTransfer entity persisted (G-23) with NonProd assurance impact + restoration plan.",
                ],
                "tasks": [
                    {"id": "ACRME-T110201", "title": "Model EmergencyCapacityTransfer entity (G-23)"},
                    {"id": "ACRME-T110202", "title": "Implement Tier 2 flag + release-and-reuse gate (B-2)"},
                    {"id": "ACRME-T110203", "title": "Implement impact preview + approval + manual timeout (Runbook D)"},
                ],
            },
            {
                "id": "ACRME-S1103",
                "title": "Tier 3 disassociation blocked in Phase 1",
                "as_a": "security owner",
                "i_want": "Tier 3 calls rejected while disabled",
                "so_that": "no VM association change happens before the credential model is closed",
                "priority": "Highest", "points": 3, "phase": "P1",
                "prr_refs": ["§32", "R-18", "Tier3AttemptBlocked alert"],
                "depends_on": ["ACRME-S0901"],
                "acceptance": [
                    "Tier 3 request rejected while disabled; Tier3AttemptBlocked alert fires (R-18).",
                    "Feature is disabled-by-default and requires separate board authorization to enable.",
                ],
                "tasks": [
                    {"id": "ACRME-T110301", "title": "Implement Tier 3 disabled-by-default rejection"},
                    {"id": "ACRME-T110302", "title": "Wire Tier3AttemptBlocked alert (R-18)"},
                ],
            },
        ],
    },
    # =====================================================================
    {
        "id": "ACRME-E12",
        "name": "AKS & VMSS Integration",
        "goal": "Validate AKS node-pool/autoscaler integration with CRGs and enforce VMSS "
                "controls, including rejecting VMSS in emergency transfers (Preview limit).",
        "prr_refs": ["§33", "§6 AKS/VMSS", "FC-08", "R-20", "R-21", "R-22", "R-42"],
        "stories": [
            {
                "id": "ACRME-S1201",
                "title": "AKS node-pool and autoscaler validation",
                "as_a": "AKS owner",
                "i_want": "new node pools validated against zone/SKU/sharing/quota and bounded autoscaler",
                "so_that": "AKS never repeatedly requests unavailable nodes or exceeds reservation",
                "priority": "Medium", "points": 8, "phase": "P2",
                "prr_refs": ["§33 AKS", "R-21", "R-22"],
                "depends_on": ["ACRME-S0502", "ACRME-S0602"],
                "acceptance": [
                    "New node pool references a CRG only after zone/SKU/sharing/provider+consumer quota checks.",
                    "Autoscaler max bounded by validated reservation + policy over-allocation; retries bounded (R-21).",
                    "Existing node-pool change requires a replacement-impact plan (R-22); node identity separate from ACRME identity.",
                ],
                "tasks": [
                    {"id": "ACRME-T120101", "title": "Implement AKS node-pool pre-validation checks"},
                    {"id": "ACRME-T120102", "title": "Enforce bounded autoscaler max + bounded retries (R-21)"},
                    {"id": "ACRME-T120103", "title": "Require replacement-impact plan for pool updates (R-22)"},
                ],
            },
            {
                "id": "ACRME-S1202",
                "title": "VMSS controls and emergency-transfer rejection (FC-08)",
                "as_a": "compute owner",
                "i_want": "VMSS operations gated and VMSS excluded from emergency transfers",
                "so_that": "a Preview reprovisioning limitation cannot cause a failed DR",
                "priority": "High", "points": 5, "phase": "P1",
                "prr_refs": ["§33 VMSS", "FC-08", "R-20", "R-42", "VMSSEmergencyAttempt alert"],
                "depends_on": ["ACRME-S1103"],
                "acceptance": [
                    "VMSS included in an emergency transfer is rejected; VMSSEmergencyAttempt alert fires (R-20).",
                    "VMSS reprovisioning via shared CRG during a zone outage documented as Preview-limited (FC-08/R-42).",
                    "Uniform/Flexible create-with-CRG allowed only after mode-specific POC proof.",
                ],
                "tasks": [
                    {"id": "ACRME-T120201", "title": "Implement VMSS emergency-transfer rejection + alert (R-20)"},
                    {"id": "ACRME-T120202", "title": "Encode VMSS Uniform/Flexible control matrix (Phase 1 gating)"},
                ],
            },
        ],
    },
    # =====================================================================
    {
        "id": "ACRME-E13",
        "name": "Data Architecture & Entity Model",
        "goal": "Establish the canonical authoritative entity model and close data-model "
                "gaps (G-20, G-21, G-23, G-24) with schema, audit, and policy versioning.",
        "prr_refs": ["§34", "G-20", "G-21", "G-23", "G-24"],
        "stories": [
            {
                "id": "ACRME-S1301",
                "title": "Canonical authoritative entity schema and policy versioning",
                "as_a": "data owner",
                "i_want": "all authoritative entities modeled with a shared schema and PolicyVersion",
                "so_that": "engine intent is consistent, versioned, and replayable",
                "priority": "High", "points": 8, "phase": "P1",
                "prr_refs": ["§34 Authoritative entities"],
                "depends_on": ["ACRME-S0103"],
                "acceptance": [
                    "All §34 entities have a canonical schema with IDs, timestamps, and version fields.",
                    "PolicyVersion referenced by placement, scoring, and quota decisions.",
                    "Schema migrations are versioned and reversible.",
                ],
                "tasks": [
                    {"id": "ACRME-T130101", "title": "Author canonical schema for all authoritative entities"},
                    {"id": "ACRME-T130102", "title": "Implement PolicyVersion entity + references"},
                    {"id": "ACRME-T130103", "title": "Set up versioned, reversible migrations"},
                ],
            },
            {
                "id": "ACRME-S1302",
                "title": "Append-only audit model with completeness guarantee",
                "as_a": "compliance owner",
                "i_want": "every accepted mutation to produce an append-only audit record",
                "so_that": "incidents and decisions can always be reconstructed",
                "priority": "High", "points": 5, "phase": "P1",
                "prr_refs": ["§34", "R-31", "§37 Audit completeness SLI"],
                "depends_on": ["ACRME-S1301"],
                "acceptance": [
                    "Append-only audit for 100% of accepted mutations (audit completeness SLI, R-31).",
                    "OperationRecord captures before/after state, policy version, and evidence classification.",
                    "Audit is immutable and independently queryable.",
                ],
                "tasks": [
                    {"id": "ACRME-T130201", "title": "Implement append-only OperationRecord/audit store"},
                    {"id": "ACRME-T130202", "title": "Instrument all mutations to emit audit records (R-31)"},
                ],
            },
        ],
    },
    # =====================================================================
    {
        "id": "ACRME-E14",
        "name": "API Architecture",
        "goal": "Deliver the canonical async API: operation-resource responses, mandatory "
                "mutation metadata, dry-run for high-impact ops, and disabled-by-default "
                "emergency endpoints.",
        "prr_refs": ["§35", "G-23", "R-34"],
        "stories": [
            {
                "id": "ACRME-S1401",
                "title": "Core async endpoints returning operation resources",
                "as_a": "API consumer",
                "i_want": "state-changing endpoints to return an operation resource, not synchronous completion",
                "so_that": "callers poll for true Azure state instead of assuming completion",
                "priority": "Highest", "points": 8, "phase": "P1",
                "prr_refs": ["§35 Core endpoints"],
                "depends_on": ["ACRME-S0101"],
                "acceptance": [
                    "All §35 core endpoints implemented; mutations return an operation + polling URL.",
                    "/placement/select-regions accepts either a specific region (Scenario 2) or a geography (Scenario 1).",
                    "/operations/{id} returns current operation state.",
                ],
                "tasks": [
                    {"id": "ACRME-T140101", "title": "Implement core resource endpoints (subscriptions/crgs/quota/...)"},
                    {"id": "ACRME-T140102", "title": "Implement /placement/select-regions dual-input contract"},
                    {"id": "ACRME-T140103", "title": "Implement /operations/{id} polling resource"},
                ],
            },
            {
                "id": "ACRME-S1402",
                "title": "Mandatory mutation metadata and dry-run",
                "as_a": "API consumer",
                "i_want": "every mutation to require idempotency key, expected version, policy version, and support dry-run",
                "so_that": "high-impact operations are safe, idempotent, and previewable",
                "priority": "High", "points": 5, "phase": "P1",
                "prr_refs": ["§35 Every mutation"],
                "depends_on": ["ACRME-S1401"],
                "acceptance": [
                    "Mutations require idempotency key, caller identity, expected state version, policy version, incident ID where applicable.",
                    "Dry-run supported for high-impact operations; structured precondition failures returned.",
                ],
                "tasks": [
                    {"id": "ACRME-T140201", "title": "Enforce mandatory mutation metadata middleware"},
                    {"id": "ACRME-T140202", "title": "Implement dry-run + structured precondition failures"},
                ],
            },
            {
                "id": "ACRME-S1403",
                "title": "Emergency endpoints disabled-by-default with contract tests (G-23)",
                "as_a": "governance owner",
                "i_want": "emergency-transfer/increase endpoints in the canonical API but disabled by default",
                "so_that": "they exist in the contract and audit model before being enabled",
                "priority": "Medium", "points": 3, "phase": "P1",
                "prr_refs": ["§35", "G-23", "G-24"],
                "depends_on": ["ACRME-S1401"],
                "acceptance": [
                    "/capacity/emergency-transfer and /capacity/increase-requests in the canonical API + authorization matrix.",
                    "Emergency endpoint disabled-by-default via feature flag; contract test present (G-23).",
                ],
                "tasks": [
                    {"id": "ACRME-T140301", "title": "Add emergency + increase endpoints to contract + authz matrix"},
                    {"id": "ACRME-T140302", "title": "Flag-gate emergency endpoint + add contract test (G-23)"},
                ],
            },
        ],
    },
    # =====================================================================
    {
        "id": "ACRME-E15",
        "name": "Security, RBAC & Managed Identity",
        "goal": "Implement split UAMIs and application roles with least privilege, and close "
                "G-14 (customer-consented, RG-scoped Tier 3 credential model) or keep Tier 3 blocked.",
        "prr_refs": ["§36", "§11", "G-14", "R-19", "R-32"],
        "stories": [
            {
                "id": "ACRME-S1501",
                "title": "Split UAMIs and application roles (least privilege)",
                "as_a": "security owner",
                "i_want": "the RBAC matrix realized as narrow custom roles and separated identities",
                "so_that": "privilege is never concentrated and duties are separated",
                "priority": "Highest", "points": 8, "phase": "P1",
                "prr_refs": ["§36 RBAC matrix", "R-19"],
                "depends_on": ["ACRME-S0105"],
                "acceptance": [
                    "Reader/Capacity/Sharing/Consumer-Compute/Quota UAMIs + DR/Emergency/Policy-Admin/Auditor roles created per matrix.",
                    "Each role scoped narrowly; prohibited actions verified blocked in a least-privilege test (R-19).",
                    "Role-assignment authority isolated from capacity/VM mutation.",
                ],
                "tasks": [
                    {"id": "ACRME-T150101", "title": "Deploy custom role definitions per RBAC matrix"},
                    {"id": "ACRME-T150102", "title": "Assign UAMIs at narrowest scope + application roles"},
                    {"id": "ACRME-T150103", "title": "Write least-privilege prohibited-action tests (R-19)"},
                ],
            },
            {
                "id": "ACRME-S1502",
                "title": "G-14 credential model for Tier 3 (customer-consented, RG-scoped)",
                "as_a": "security owner",
                "i_want": "a customer-consented UAMI with RG-scoped custom rights for exact VM association ops",
                "so_that": "Tier 3 can eventually be enabled without subscription-wide VM Contributor",
                "priority": "Highest", "points": 8, "phase": "P2",
                "prr_refs": ["§36 MI scope", "G-14"],
                "depends_on": ["ACRME-S1501"],
                "acceptance": [
                    "Minimum custom action set for VM association defined + RG-scoped; no subscription-wide VM Contributor.",
                    "Customer consent + revocation path implemented and tested in a consumer subscription (closes G-14).",
                    "If the minimum action set cannot be established, Tier 3 stays blocked.",
                ],
                "tasks": [
                    {"id": "ACRME-T150201", "title": "Define minimum custom VM-association action set (G-14)"},
                    {"id": "ACRME-T150202", "title": "Implement customer consent + revocation flow"},
                    {"id": "ACRME-T150203", "title": "Test least-privilege + revocation in consumer subscription"},
                ],
            },
            {
                "id": "ACRME-S1503",
                "title": "Break-glass control with time-bound access and post-review",
                "as_a": "security owner",
                "i_want": "break-glass access to be time-bound, alerted, and post-reviewed",
                "so_that": "emergency bypass cannot be silently abused",
                "priority": "Medium", "points": 3, "phase": "P1",
                "prr_refs": ["§11", "R-32"],
                "depends_on": ["ACRME-S1501"],
                "acceptance": [
                    "Break-glass role is time-bound and auto-expires; activation raises an alert (R-32).",
                    "Mandatory post-use review recorded in audit.",
                ],
                "tasks": [
                    {"id": "ACRME-T150301", "title": "Implement time-bound break-glass role + auto-expiry"},
                    {"id": "ACRME-T150302", "title": "Wire activation alert + post-review record (R-32)"},
                ],
            },
        ],
    },
    # =====================================================================
    {
        "id": "ACRME-E16",
        "name": "Observability, Dashboards & Alerts",
        "goal": "Deliver SLI/SLO instrumentation, operational dashboards, and the full "
                "critical alert catalog so operators can see floor integrity, drift, and blocks.",
        "prr_refs": ["§37"],
        "stories": [
            {
                "id": "ACRME-S1601",
                "title": "SLI/SLO instrumentation",
                "as_a": "SRE",
                "i_want": "the proposed SLIs measured against SLO targets",
                "so_that": "engine health is observable and reportable",
                "priority": "High", "points": 5, "phase": "P1",
                "prr_refs": ["§37 SLI/SLO"],
                "depends_on": ["ACRME-S0101"],
                "acceptance": [
                    "Query success, mutation availability, placement latency, reconciliation age, and audit completeness measured.",
                    "SLO targets configured with breach reporting; labeled internal (not Microsoft guarantees).",
                ],
                "tasks": [
                    {"id": "ACRME-T160101", "title": "Instrument SLI metrics + emit to monitoring"},
                    {"id": "ACRME-T160102", "title": "Configure SLO targets + breach reporting"},
                ],
            },
            {
                "id": "ACRME-S1602",
                "title": "Operational dashboards",
                "as_a": "operator",
                "i_want": "dashboards for capacity, quota, DR floor, sharing, placement, engine mode, and failures",
                "so_that": "state is visible at a glance during steady state and incidents",
                "priority": "High", "points": 5, "phase": "P1",
                "prr_refs": ["§37 Dashboards"],
                "depends_on": ["ACRME-S1601"],
                "acceptance": [
                    "Dashboards cover capacity, quota headroom, DR floor integrity, sharing, placement decisions, engine mode, failed ops.",
                    "Dashboards render from live snapshots + engine state.",
                ],
                "tasks": [
                    {"id": "ACRME-T160201", "title": "Build capacity/quota/DR-floor dashboards"},
                    {"id": "ACRME-T160202", "title": "Build sharing/placement/engine-mode/failed-ops dashboards"},
                ],
            },
            {
                "id": "ACRME-S1603",
                "title": "Critical alert catalog",
                "as_a": "SRE",
                "i_want": "the full alert catalog wired with severities and triggers",
                "so_that": "critical guardrail violations page the right responders",
                "priority": "Highest", "points": 5, "phase": "P1",
                "prr_refs": ["§37 Alert catalog"],
                "depends_on": ["ACRME-S1601"],
                "acceptance": [
                    "All catalog alerts implemented with correct severity + trigger (Engine/DRFloor/Unauthorized/Tier3/VMSS/etc).",
                    "Critical alerts route to on-call; alert tests validate firing conditions.",
                ],
                "tasks": [
                    {"id": "ACRME-T160301", "title": "Implement Critical alerts (EngineModeConflict, DRFloorViolation, ...)"},
                    {"id": "ACRME-T160302", "title": "Implement High/Medium/Low alerts + routing + tests"},
                ],
            },
        ],
    },
    # =====================================================================
    {
        "id": "ACRME-E17",
        "name": "Reconciliation & Scaling",
        "goal": "Adaptive, delta-based reconciliation that stays within API budgets at "
                "hundreds–thousands of customers, with drift handling and throttle resilience.",
        "prr_refs": ["§10", "§7", "R-04", "R-24", "R-25", "R-40", "FC-16"],
        "stories": [
            {
                "id": "ACRME-S1701",
                "title": "Adaptive delta-based reconciliation within API budgets",
                "as_a": "SRE",
                "i_want": "targeted, event-triggered reconciliation instead of naive full scans",
                "so_that": "reconciliation stays within API budgets at scale",
                "priority": "High", "points": 8, "phase": "P1",
                "prr_refs": ["§10 Adaptive reconciliation", "R-24"],
                "depends_on": ["ACRME-S0103"],
                "acceptance": [
                    "Reconciliation is delta/event-triggered; full-estate short-interval scan is not used (R-24).",
                    "Critical targeted reconciliation P95 < 2 min; stable-resource age P95 < 15 min.",
                    "ReconciliationStale alert on age beyond policy; ARM confirmation before mutation (R-04).",
                ],
                "tasks": [
                    {"id": "ACRME-T170101", "title": "Implement adaptive/delta reconciliation scheduler"},
                    {"id": "ACRME-T170102", "title": "Implement event-triggered targeted refresh"},
                    {"id": "ACRME-T170103", "title": "Wire ReconciliationStale + ARGDiscoveryLag alerts"},
                ],
            },
            {
                "id": "ACRME-S1702",
                "title": "ARM throttling resilience with per-service budgets",
                "as_a": "SRE",
                "i_want": "per-service API budgets, adaptive backoff, and a manual path",
                "so_that": "throttling never blocks DR actions",
                "priority": "High", "points": 5, "phase": "P1",
                "prr_refs": ["§7 FC-16", "R-25", "ARMThrottling alert"],
                "depends_on": ["ACRME-S0104"],
                "acceptance": [
                    "Per-service budgets + adaptive backoff seeded from documented throttle baselines (FC-16).",
                    "ARMThrottling alert on retry-budget/throttle-ratio breach; documented manual path independent of engine (R-25).",
                ],
                "tasks": [
                    {"id": "ACRME-T170201", "title": "Implement per-service rate budgets + adaptive backoff (FC-16)"},
                    {"id": "ACRME-T170202", "title": "Wire ARMThrottling alert + manual fallback runbook (R-25)"},
                ],
            },
            {
                "id": "ACRME-S1703",
                "title": "Drift handling and maintenance mode",
                "as_a": "operations engineer",
                "i_want": "maintenance mode and a clear drift policy",
                "so_that": "manual Azure changes are not unexpectedly reverted",
                "priority": "Medium", "points": 5, "phase": "P1",
                "prr_refs": ["§10", "R-40"],
                "depends_on": ["ACRME-S1701"],
                "acceptance": [
                    "Maintenance mode suppresses reconciliation-driven reversal; drift policy documented (R-40).",
                    "Drift surfaced with a clear reconcile-or-accept decision.",
                ],
                "tasks": [
                    {"id": "ACRME-T170301", "title": "Implement maintenance mode + drift policy (R-40)"},
                    {"id": "ACRME-T170302", "title": "Implement drift surfacing + operator decision path"},
                ],
            },
            {
                "id": "ACRME-S1704",
                "title": "Capacity-exhaustion queue and handling",
                "as_a": "operator",
                "i_want": "a capacity-exhaustion queue with incident creation and re-evaluation on confirmed state",
                "so_that": "exhaustion is handled deterministically, not by elapsed time",
                "priority": "Medium", "points": 5, "phase": "P2",
                "prr_refs": ["Runbook A", "§22 Should", "CapacityExhausted alert"],
                "depends_on": ["ACRME-S0701"],
                "acceptance": [
                    "On no eligible region/CR: freeze holds, rank alternatives without committing, queue + create incident (Runbook A).",
                    "Re-evaluate only after confirmed state change; CapacityExhausted alert fires.",
                ],
                "tasks": [
                    {"id": "ACRME-T170401", "title": "Implement capacity-exhaustion queue + incident creation"},
                    {"id": "ACRME-T170402", "title": "Implement confirmed-state re-evaluation + alert (Runbook A)"},
                ],
            },
        ],
    },
    # =====================================================================
    {
        "id": "ACRME-E18",
        "name": "POC & Validation Program",
        "goal": "Execute the critical POC sequence and record structured evidence so preview "
                "behaviors and unknowns are proven before production, not asserted.",
        "prr_refs": ["§42", "B-1..B-7", "all FC items"],
        "stories": [
            {
                "id": "ACRME-S1801",
                "title": "POC harness with structured evidence capture",
                "as_a": "validation engineer",
                "i_want": "a POC harness that records API version, region, SKU, zone, IDs, timings, and evidence class",
                "so_that": "every result is production-grade evidence, not an assumption",
                "priority": "High", "points": 8, "phase": "P1",
                "prr_refs": ["§42 evidence fields"],
                "depends_on": ["ACRME-S0104"],
                "acceptance": [
                    "Harness captures all required evidence fields per run with before/after state + retry history.",
                    "Each result classified as documented/observed/assumed/judgement.",
                ],
                "tasks": [
                    {"id": "ACRME-T180101", "title": "Build POC harness + structured evidence store"},
                    {"id": "ACRME-T180102", "title": "Implement evidence classification + report export"},
                ],
            },
            {
                "id": "ACRME-S1802",
                "title": "Sharing, quota, and zone-alignment POCs (critical sequence 1–8, incl. 6a)",
                "as_a": "validation engineer",
                "i_want": "sharing/RBAC, unsharing, quota independence, quantity, and zone-alignment POCs executed",
                "so_that": "foundational platform behaviors are proven before pilot",
                "priority": "High", "points": 8, "phase": "P1",
                "prr_refs": ["§42 seq 1-8", "B-1", "B-2", "B-5", "FC-06"],
                "depends_on": ["ACRME-S1801"],
                "acceptance": [
                    "Sharing/RBAC, unauthorized-consumer rejection, safe+forced unsharing validated.",
                    "Provider/consumer/group quota independence + quantity/reduction/zero-size behavior validated (B-1/B-5).",
                    "Cross-subscription zone alignment (6a) validated with physical-to-logical tables for ≥2 subscriptions.",
                ],
                "tasks": [
                    {"id": "ACRME-T180201", "title": "Execute POC 1-3 (sharing/RBAC, rejection, unsharing)"},
                    {"id": "ACRME-T180202", "title": "Execute POC 4-5,7-8 (quota + quantity, group availability B-1)"},
                    {"id": "ACRME-T180203", "title": "Execute POC 6/6a (zone mapping + cross-sub alignment, FC-06)"},
                ],
            },
            {
                "id": "ACRME-S1803",
                "title": "DR, concurrency, engine-mode, and tier POCs (critical sequence 9–15)",
                "as_a": "validation engineer",
                "i_want": "DR-floor, concurrency, engine-mode, and Tier 1/2/3 POCs executed",
                "so_that": "safety-critical behaviors are proven before enabling automation",
                "priority": "High", "points": 8, "phase": "P2",
                "prr_refs": ["§42 seq 9-15", "B-7", "B-3"],
                "depends_on": ["ACRME-S1802", "ACRME-S0901", "ACRME-S0902"],
                "acceptance": [
                    "DR-floor enforcement, concurrent placement single-winner (B-7), and engine-mode transitions (B-3) validated.",
                    "Tier 1 + Tier 2 validated; Tier 3 confirmed to remain disabled.",
                ],
                "tasks": [
                    {"id": "ACRME-T180301", "title": "Execute POC 9-12 (DR floor, quota propagation, concurrency, engine mode)"},
                    {"id": "ACRME-T180302", "title": "Execute POC 13-15 (Tier 1, Tier 2, Tier 3-disabled)"},
                ],
            },
            {
                "id": "ACRME-S1804",
                "title": "VMSS, AKS, and scale POCs (critical sequence 16–18)",
                "as_a": "validation engineer",
                "i_want": "VMSS/AKS behavior and scale testing executed",
                "so_that": "workload integration and scale limits are measured, not assumed",
                "priority": "Medium", "points": 5, "phase": "P2",
                "prr_refs": ["§42 seq 16-18", "FC-08", "R-33"],
                "depends_on": ["ACRME-S1803"],
                "acceptance": [
                    "VMSS Uniform/Flexible + AKS node-pool/autoscaler behavior validated (or Preview limits documented).",
                    "Scale testing at target cardinality validates reconciliation + throughput budgets.",
                ],
                "tasks": [
                    {"id": "ACRME-T180401", "title": "Execute POC 16-17 (VMSS Uniform/Flexible, AKS)"},
                    {"id": "ACRME-T180402", "title": "Execute POC 18 (scale testing) + record budgets"},
                ],
            },
        ],
    },
    # =====================================================================
    {
        "id": "ACRME-E19",
        "name": "Production Readiness Gates & Governance",
        "goal": "Track gap-closure evidence, preview feature-flag governance, and the "
                "production entry gates so pilot→production transitions are evidence-based.",
        "prr_refs": ["§14", "§16", "§17", "§39", "§44", "R-01", "R-34"],
        "stories": [
            {
                "id": "ACRME-S1901",
                "title": "Preview feature-flag governance and exit paths",
                "as_a": "product owner",
                "i_want": "every preview dependency behind a flag with a governance acceptance + exit path",
                "so_that": "preview changes never silently break production",
                "priority": "Highest", "points": 5, "phase": "P1",
                "prr_refs": ["§21", "R-01", "R-34", "R-42", "R-43"],
                "depends_on": ["ACRME-S0104"],
                "acceptance": [
                    "CRG sharing, groupType enforcement, and VMSS reprovisioning gated behind feature flags (R-01/R-43/R-42).",
                    "Each flag has recorded governance acceptance + a documented exit path.",
                    "Preview/POC results are evidence-labeled and never presented as an SLA (R-34).",
                ],
                "tasks": [
                    {"id": "ACRME-T190101", "title": "Implement preview feature-flag framework + registry"},
                    {"id": "ACRME-T190102", "title": "Record governance acceptance + exit paths per flag"},
                    {"id": "ACRME-T190103", "title": "Enforce evidence-labeling standard (R-34)"},
                ],
            },
            {
                "id": "ACRME-S1902",
                "title": "Gap-closure evidence tracker (G-14/G-15/G-20/G-21/G-23/G-24, B-1..B-7)",
                "as_a": "program owner",
                "i_want": "a live tracker mapping each gap to its closure control and acceptance evidence",
                "so_that": "production gates are provably met, not assumed",
                "priority": "High", "points": 5, "phase": "P1",
                "prr_refs": ["§39 Gap closure"],
                "depends_on": [],
                "acceptance": [
                    "Every gap/blocker has closure control + acceptance evidence status tracked.",
                    "Tracker blocks phase advancement until required evidence is attached.",
                ],
                "tasks": [
                    {"id": "ACRME-T190201", "title": "Build gap-closure tracker mapping gaps->evidence"},
                    {"id": "ACRME-T190202", "title": "Gate phase advancement on evidence completeness"},
                ],
            },
            {
                "id": "ACRME-S1903",
                "title": "Production entry gates and conditional pilot checklist",
                "as_a": "council/board",
                "i_want": "the pilot and production entry gates encoded as an auditable checklist",
                "so_that": "pilot success is not mistaken for production approval",
                "priority": "High", "points": 3, "phase": "P1",
                "prr_refs": ["§16", "§17", "§44 Board actions"],
                "depends_on": ["ACRME-S1902"],
                "acceptance": [
                    "Pilot-entry and production-entry gate checklists encoded with named approvers.",
                    "Manual rollback demonstrated; separate production authorization required after pilot.",
                    "Destructive-automation enablement requires separate board authorization.",
                ],
                "tasks": [
                    {"id": "ACRME-T190301", "title": "Encode pilot + production entry-gate checklists"},
                    {"id": "ACRME-T190302", "title": "Record named approvers + separate-authorization rule"},
                ],
            },
        ],
    },
]
