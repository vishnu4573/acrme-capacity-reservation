# Azure Capacity Reservation Management Engine

## Design Requirements Specification

**Classification:** Principal Cloud Architect — System Design  
**Version:** 1.0 — Draft for Engineering Review  
**Date:** August 2026  
**Source Basis:** Azure CR Sharing Research (`azure_cr_sharing_research.md`), POC Test Workbook (`azure_cr_poc_test_workbook.md`), Azure Well-Architected Framework  
**Feature Dependency:** Azure Capacity Reservation Sharing (Public Preview — `api-version=2024-03-01`)

> **Design Constraint:** This document assumes the production deployment of this engine is deferred until Azure Capacity Reservation Sharing reaches General Availability. Preview-dependent behaviors are flagged throughout. Engineering backlog items covering Preview-only capabilities are marked `[Preview Dependency]`.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Functional Requirements](#2-functional-requirements)
3. [Non-Functional Requirements](#3-non-functional-requirements)
4. [Data Model](#4-data-model)
5. [APIs Required](#5-apis-required)
6. [Azure Services Required](#6-azure-services-required)
7. [Event Sources](#7-event-sources)
8. [State Management](#8-state-management)
9. [Failure Handling](#9-failure-handling)
10. [Security Model](#10-security-model)
11. [Integration Points](#11-integration-points)
12. [System Context Diagram](#12-system-context-diagram)
13. [Component Model](#13-component-model)
14. [Engineering Backlog](#14-engineering-backlog)

---

## 1. Executive Summary

### 1.1 Problem Statement

Azure Capacity Reservations guarantee compute capacity in a specific region and availability zone for a named VM SKU. As organizations scale their Azure footprint across multiple subscriptions, the following operational challenges emerge:

- **Fragmentation:** Each subscription independently manages its own Capacity Reservations. There is no cross-subscription visibility, consolidation, or optimization layer.
- **Quota Opacity:** Provider quota (for reserved capacity) and Consumer quota (for deployed VMs) are tracked independently across subscriptions with no unified view.
- **Manual Sharing Lifecycle:** The three-step RBAC setup for Capacity Reservation Sharing, zone mapping resolution, and sharing profile maintenance are entirely manual operations today.
- **DR Complexity:** Pre-positioning capacity for Disaster Recovery across zones and regions requires coordinated quota, reservation, and sharing configuration that has no automated reconciliation.
- **Cost Leakage:** Unused reserved capacity is billed to the Provider subscription with no automated detection, rebalancing, or right-sizing feedback loop.
- **Zone Misalignment:** Logical-to-physical zone mapping divergence across subscriptions is a silent failure mode requiring explicit tooling (Check Zone Peers API) that is not integrated into any standard deployment workflow.

### 1.2 Engine Purpose

The **Azure Capacity Reservation Management Engine** (ACRME) is a control-plane automation system that provides:

- Unified lifecycle management of Capacity Reservations and Capacity Reservation Groups across a multi-subscription Azure estate
- Automated sharing profile management with RBAC orchestration and zone mapping resolution
- Quota tracking, forecasting, and automated increase workflow initiation
- DR capacity pre-positioning, failover triggering, and failback reconciliation
- Regional placement decision support based on capacity, cost, and policy constraints
- Demand forecasting with automated reservation right-sizing recommendations
- Cost optimization through utilization monitoring, idle reservation detection, and chargeback reporting

### 1.3 Scope Boundaries

**In Scope:**
- Standard On-Demand Capacity Reservations (ODCR) lifecycle management
- Capacity Reservation Sharing across subscriptions within the same Azure tenant
- Quota management for VM SKUs relevant to capacity reservations
- Availability Zone mapping and cross-subscription zone alignment
- DR failover and failback capacity orchestration
- Capacity forecasting and cost optimization recommendations
- REST API surface for programmatic consumers and platform integration

**Out of Scope (v1.0):**
- Block Capacity Reservation management (sharing not supported by Azure — Preview constraint)
- Cross-tenant capacity reservation sharing
- Non-compute resource quota management (Storage, Networking)
- Azure Reserved Instances (RI) purchase automation (separate billing plane)
- VM lifecycle management beyond association and disassociation with CRGs

---

## 2. Functional Requirements

### FR-1 — Capacity Reservation Lifecycle Management

**FR-1.1** The engine SHALL create, read, update, and delete Capacity Reservation Groups (CRGs) in designated Provider subscriptions via the Azure Compute REST API at `api-version=2024-03-01` or later.

**FR-1.2** The engine SHALL create, read, update, and delete Capacity Reservations (CRs) within managed CRGs, supporting quantity modification without VM disruption.

**FR-1.3** The engine SHALL support the zero-size reservation pattern — creating CRs at `quantity=0` and incrementally increasing quantity as Consumer VMs associate.

**FR-1.4** The engine SHALL track the `allocated` count (number of VMs currently associated with each CR) and the `quantity` (reserved capacity) independently, detecting and alerting on overallocated states (`allocated > quantity`).

**FR-1.5** The engine SHALL enforce CR deletion sequencing — disassociating all VMs, deleting all CRs, then deleting the CRG — and SHALL reject delete requests that would violate this order.

**FR-1.6** The engine SHALL support CR quantity reduction and enforce the platform floor constraint (quantity cannot be reduced below current allocated count).

---

### FR-2 — Capacity Reservation Sharing Management

**FR-2.1** The engine SHALL manage the `sharingProfile.subscriptionIds` property on CRGs, supporting add, remove, and list operations for Consumer subscriptions.

**FR-2.2** The engine SHALL orchestrate the complete three-step RBAC setup for each Provider-Consumer pair:
- Step 1: Grant Provider identity `deploy/action` permission on Consumer subscription scope
- Step 2: Add Consumer subscription to CRG `sharingProfile`
- Step 3: Grant Consumer identity read and `deploy/action` permissions on Provider CRG

**FR-2.3** The engine SHALL enforce the 100 Consumer subscription limit per CRG and SHALL return a structured error with remediation guidance when the limit is reached.

**FR-2.4** The engine SHALL verify that all Consumer subscriptions have `Microsoft.Compute` registered as a resource provider before completing sharing setup.

**FR-2.5** The engine SHALL support safe unsharing — detecting active Consumer VM associations before removing a Consumer from a sharing profile and requiring explicit force-override or prior VM disassociation before proceeding.

**FR-2.6** The engine SHALL warn operators when forced unsharing is requested with active Consumer VM associations, citing the documented silent hazard (VMs continue running but fail on next deallocation/restart).

**FR-2.7** The engine SHALL maintain a record of the current and historical sharing profile state for each CRG, including timestamps of add and remove operations.

---

### FR-3 — Availability Zone Mapping Management

**FR-3.1** The engine SHALL discover and store the logical-to-physical zone mapping for every managed subscription in every managed region using the `az account list-locations` API or equivalent.

**FR-3.2** The engine SHALL use the Check Zone Peers API (`Microsoft.Resources/checkZonePeers`) to compute cross-subscription zone equivalence tables for all Provider-Consumer pairs.

**FR-3.3** The engine SHALL maintain a zone mapping registry keyed by `(provider_sub_id, region, provider_logical_zone)` → `[(consumer_sub_id, consumer_logical_zone)]` for all managed subscription pairs.

**FR-3.4** The engine SHALL automatically resolve the correct Consumer logical zone when accepting VM deployment requests that reference a shared CRG, using the stored zone mapping registry.

**FR-3.5** The engine SHALL detect and reject VM deployment requests where the specified Consumer zone does not map to the same physical zone as the target CR, returning a structured error with the correct Consumer zone.

**FR-3.6** The engine SHALL refresh zone mappings on a configurable schedule and on any new subscription onboarding event.

---

### FR-4 — Quota Management

**FR-4.1** The engine SHALL query and store regional compute quota (`currentValue`, `limit`) for all tracked VM SKUs across all managed subscriptions.

**FR-4.2** The engine SHALL calculate and expose the following derived quota metrics per subscription, region, and SKU:
- Available quota = limit − currentValue
- Committed quota = sum of CR quantities × SKU vCPU count
- Deployment headroom = available quota − committed quota
- Overcommit flag = committed quota > available quota

**FR-4.3** The engine SHALL detect quota exhaustion conditions before CR creation attempts, blocking the operation and returning a pre-validation failure with remediation guidance (quota increase workflow).

**FR-4.4** The engine SHALL initiate Azure quota increase requests via the Azure Support REST API (`Microsoft.Capacity/resourceProviders/locations/serviceLimits`) when quota thresholds are breached, subject to operator approval workflow.

**FR-4.5** The engine SHALL track Consumer subscription quota independently and SHALL warn when a Consumer's available quota is insufficient to deploy the number of VMs implied by their allocation against a shared CRG.

**FR-4.6** The engine SHALL provide a unified quota dashboard across all managed subscriptions, aggregating reserved, consumed, and available capacity per region, zone, and SKU.

---

### FR-5 — Disaster Recovery Failover Management

**FR-5.1** The engine SHALL support the definition of DR capacity pairs: `(primary_crg, dr_crg)` where the DR CRG is a pre-positioned shared capacity reserve in a target region or zone.

**FR-5.2** The engine SHALL manage DR CRG sharing profiles, ensuring the DR Consumer subscription has the correct RBAC and zone mapping configuration at all times (pre-event, not on-demand).

**FR-5.3** The engine SHALL support a **failover trigger** operation that:
- Validates DR CRG capacity is available
- Initiates bulk VM deployment from the DR Consumer subscription against the DR CRG
- Records failover event metadata (trigger time, operator, VMs deployed, duration)

**FR-5.4** The engine SHALL support a **failback trigger** operation that:
- Deallocates DR VMs in the DR Consumer subscription
- Restores primary CRG to pre-failover capacity configuration
- Records failback event metadata

**FR-5.5** The engine SHALL monitor DR CRG capacity utilization continuously, alerting if DR reserved capacity has been consumed (allocated > 0 in steady-state — indicating unauthorized use of DR capacity).

**FR-5.6** The engine SHALL enforce minimum DR capacity buffers: configurable per DR pair as a percentage of primary capacity, and SHALL alert when Provider quota changes would violate the buffer.

**FR-5.7** The engine SHALL support cross-region DR pair definitions, maintaining separate CRGs per region with independent sharing profiles and zone mapping registries.

---

### FR-6 — Regional Placement Decisions

**FR-6.1** The engine SHALL evaluate VM placement requests against the following constraint dimensions before returning a placement recommendation:
- Availability Zone physical alignment with target CR
- CR available capacity (`quantity` − `allocated`)
- Consumer subscription quota headroom
- Region-specific SKU availability
- Cost (region-level pricing index for VM SKU)
- DR buffer compliance (primary capacity must maintain configured DR buffer after placement)

**FR-6.2** The engine SHALL return a ranked list of valid placement options when multiple CRGs or regions satisfy all constraints, ordered by a configurable placement policy (cost-first, availability-first, or DR-buffer-first).

**FR-6.3** The engine SHALL enforce placement policies as code — operators define placement rules as structured policy documents; the engine evaluates requests against the policy DAG before returning a recommendation.

**FR-6.4** The engine SHALL detect when a requested placement would create a single-zone dependency for a logical workload (all VMs in the same physical zone) and SHALL warn the operator.

**FR-6.5** The engine SHALL surface SKU availability constraints per region and zone, integrating with the Azure Compute SKU API to identify regions where a requested SKU is restricted or unavailable.

---

### FR-7 — Capacity Forecasting

**FR-7.1** The engine SHALL analyze historical CR allocation patterns (allocated count over time) and produce demand forecasts for the next configurable period (default: 30, 60, 90 days).

**FR-7.2** The engine SHALL produce capacity recommendations driven by forecast outputs:
- Increase CR quantity when forecast demand exceeds current reserved quantity within the forecast window
- Decrease CR quantity (right-size) when forecast demand is consistently below current reserved quantity, accounting for a configurable buffer percentage

**FR-7.3** The engine SHALL model capacity buffer requirements as: `recommended_quantity = forecast_peak_demand × (1 + buffer_pct) + dr_buffer`

**FR-7.4** The engine SHALL alert when forecast demand approaches quota limits (configurable threshold, default: 80% of quota limit) with lead time sufficient for quota increase processing (default: 14-day alert lead time).

**FR-7.5** The engine SHALL support workload tagging, allowing operators to associate VMs and CRs with named workloads, enabling per-workload capacity forecasts.

**FR-7.6** The engine SHALL expose raw forecast data (time series of predicted demand) and derived recommendations via API for consumption by external capacity planning tools.

---

### FR-8 — Cost Optimization

**FR-8.1** The engine SHALL continuously monitor the utilization ratio (`allocated / quantity`) for every CR and SHALL flag CRs where utilization falls below a configurable threshold (default: 60%) for a sustained period (default: 7 days).

**FR-8.2** The engine SHALL calculate the daily and monthly cost of unused reserved capacity per CR, per CRG, per Provider subscription, and per Consumer workload (via chargeback attribution).

**FR-8.3** The engine SHALL produce right-sizing recommendations: suggested `quantity` reductions for underutilized CRs, with projected cost savings and associated risk assessment (proximity to DR buffer).

**FR-8.4** The engine SHALL support chargeback and showback reporting: attributing the cost of reserved capacity to Consumer subscriptions or workloads based on their average allocated utilization over a billing period.

**FR-8.5** The engine SHALL identify idle CRs (quantity > 0, allocated = 0 for a configurable period) and SHALL generate automated alerts with deletion recommendations.

**FR-8.6** The engine SHALL integrate with Azure Cost Management APIs to retrieve actual billing data and validate engine-computed cost estimates against realized charges.

---

## 3. Non-Functional Requirements

### NFR-1 — Availability

**NFR-1.1** The engine SHALL target 99.9% availability (≤ 8.7 hours downtime/year) for its API surface and control plane operations.

**NFR-1.2** The engine SHALL be deployed across a minimum of two Availability Zones within the primary region to eliminate single-zone dependency.

**NFR-1.3** The engine's configuration store and state database SHALL use zone-redundant storage with asynchronous cross-region replication for DR.

**NFR-1.4** The engine SHALL implement circuit breakers on all outbound Azure ARM API calls, degrading gracefully when the ARM control plane is unavailable rather than propagating failures to callers.

---

### NFR-2 — Performance

**NFR-2.1** API read operations (GET quota, GET sharing profile, GET zone mapping) SHALL return within 500ms at the 95th percentile under normal load.

**NFR-2.2** API write operations (CR create, sharing profile update) SHALL return an accepted acknowledgment within 2 seconds; asynchronous ARM operations are tracked via polling and webhook.

**NFR-2.3** The state reconciliation loop (comparison of engine desired state vs. ARM actual state) SHALL complete a full cycle within 5 minutes for an estate of up to 500 managed CRGs.

**NFR-2.4** Forecast computation for a 90-day window across all managed CRGs SHALL complete within 10 minutes as a background job.

**NFR-2.5** The engine SHALL support a minimum of 200 concurrent API clients without performance degradation.

---

### NFR-3 — Scalability

**NFR-3.1** The engine SHALL scale horizontally to support up to 100 Provider subscriptions and 10,000 Consumer subscription relationships without architectural change.

**NFR-3.2** The engine SHALL support up to 5,000 managed CRGs, 50,000 managed CRs, and 500,000 VM association records.

**NFR-3.3** The engine's reconciliation and forecasting components SHALL be independently scalable (separate compute pools) to allow capacity-intensive operations to scale without affecting API latency.

---

### NFR-4 — Reliability

**NFR-4.1** All state-mutating operations SHALL be idempotent — retrying a failed operation SHALL produce the same outcome as a single successful operation.

**NFR-4.2** All ARM API interactions SHALL implement exponential backoff with jitter and a maximum of 5 retries before entering a dead-letter failure state.

**NFR-4.3** The engine SHALL detect and reconcile state drift — conditions where the ARM actual state diverges from the engine desired state — within two reconciliation cycles.

**NFR-4.4** The engine SHALL maintain an operation audit log with a minimum 90-day retention period, capturing: operator identity, operation type, resource target, before/after state, and outcome.

---

### NFR-5 — Security

**NFR-5.1** All communication between engine components SHALL be encrypted in transit (TLS 1.2 minimum, TLS 1.3 preferred).

**NFR-5.2** All secrets (service principal credentials, Managed Identity tokens) SHALL be stored in Azure Key Vault and retrieved at runtime; no secrets SHALL be stored in application configuration files or environment variables.

**NFR-5.3** The engine SHALL authenticate to Azure ARM using Managed Identity where deployed on Azure compute, and Service Principal with certificate authentication for cross-subscription operations.

**NFR-5.4** The engine's own API surface SHALL require Azure AD authentication. All API clients SHALL authenticate via Bearer token (Azure AD OAuth 2.0 flow).

**NFR-5.5** All API operations SHALL enforce Role-Based Access Control at the engine level (not solely at the ARM level), with the following minimum role set: `CRG.Admin`, `CRG.Operator`, `CRG.Reader`, `DR.Operator`.

**NFR-5.6** The engine SHALL log all security events (authentication failures, authorization denials, privilege escalations) to a dedicated security audit log stream, separate from the operational audit log.

---

### NFR-6 — Observability

**NFR-6.1** The engine SHALL emit structured logs (JSON) for every operation, including: correlation ID, subscription ID, resource ID, operation type, duration, and outcome.

**NFR-6.2** The engine SHALL emit metrics to Azure Monitor for: API request rate, API error rate, reconciliation cycle duration, ARM call latency, quota utilization percentage, CR utilization percentage, and DR buffer compliance status.

**NFR-6.3** The engine SHALL provide distributed tracing (OpenTelemetry) across all internal service boundaries and ARM API calls.

**NFR-6.4** The engine SHALL expose a `/health` endpoint returning liveness and readiness status, and a `/metrics` endpoint returning current operational metrics in Prometheus format.

---

### NFR-7 — Compliance and Governance

**NFR-7.1** The engine SHALL be deployable in Azure sovereign clouds (Azure Government, Azure China) subject to API availability in those environments.

**NFR-7.2** All data stored by the engine (configuration, state, audit logs) SHALL remain within the designated Azure region pair and SHALL not be transmitted to external services.

**NFR-7.3** The engine SHALL support Azure Policy integration — placement and sharing decisions SHALL be evaluated against applicable Azure Policies before execution.

---

## 4. Data Model

### 4.1 Core Entities

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ManagedSubscription                                                         │
├──────────────────────────────────────────────────────────────────────────────┤
│  subscription_id          : GUID (PK)                                        │
│  subscription_name        : String                                           │
│  tenant_id                : GUID                                             │
│  role                     : Enum [Provider, Consumer, Both]                  │
│  region                   : String[]                    — managed regions     │
│  compute_registered       : Boolean                                          │
│  zone_peering_registered  : Boolean                                          │
│  managed_identity_id      : String                                           │
│  onboarded_at             : DateTime                                         │
│  last_sync_at             : DateTime                                         │
│  status                   : Enum [Active, Suspended, Offboarding]            │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│  CapacityReservationGroup                                                    │
├──────────────────────────────────────────────────────────────────────────────┤
│  crg_id                   : GUID (PK, engine-assigned)                       │
│  arm_resource_id          : String (ARM resource path)                       │
│  crg_name                 : String                                           │
│  provider_subscription_id : GUID (FK → ManagedSubscription)                 │
│  resource_group           : String                                           │
│  region                   : String                                           │
│  supported_zones          : Int[]          — ARM-reported supported zones     │
│  purpose                  : Enum [Primary, DR, Burst, Test]                  │
│  dr_pair_id               : GUID (FK → DRCapacityPair, nullable)             │
│  desired_sharing_profile  : GUID[]         — desired Consumer sub IDs        │
│  actual_sharing_profile   : GUID[]         — last observed ARM state         │
│  profile_drift            : Boolean        — desired ≠ actual                │
│  arm_provisioning_state   : String                                           │
│  created_at               : DateTime                                         │
│  last_synced_at           : DateTime                                         │
│  tags                     : Map<String, String>                              │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│  CapacityReservation                                                         │
├──────────────────────────────────────────────────────────────────────────────┤
│  cr_id                    : GUID (PK, engine-assigned)                       │
│  arm_resource_id          : String                                           │
│  cr_name                  : String                                           │
│  crg_id                   : GUID (FK → CapacityReservationGroup)             │
│  vm_sku                   : String                                           │
│  vcpu_per_instance        : Int                                              │
│  availability_zone        : Int                                              │
│  desired_quantity         : Int                                              │
│  actual_quantity          : Int             — last ARM-observed quantity      │
│  allocated_count          : Int             — VMs currently associated        │
│  utilization_pct          : Float           — allocated / actual_quantity     │
│  is_overallocated         : Boolean         — allocated > actual_quantity     │
│  quantity_drift           : Boolean         — desired ≠ actual               │
│  arm_provisioning_state   : String                                           │
│  last_synced_at           : DateTime                                         │
│  created_at               : DateTime                                         │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│  SharingRelationship                                                         │
├──────────────────────────────────────────────────────────────────────────────┤
│  relationship_id          : GUID (PK)                                        │
│  crg_id                   : GUID (FK → CapacityReservationGroup)             │
│  consumer_subscription_id : GUID (FK → ManagedSubscription)                 │
│  status                   : Enum [Pending, Active, Suspended, Removed]       │
│  rbac_step1_complete      : Boolean    — Consumer grants Provider deploy/act  │
│  rbac_step2_complete      : Boolean    — Consumer in sharingProfile          │
│  rbac_step3_complete      : Boolean    — Consumer has read + deploy on CRG   │
│  active_vm_count          : Int        — Consumer VMs associated to this CRG │
│  created_at               : DateTime                                         │
│  last_validated_at        : DateTime                                         │
│  removed_at               : DateTime (nullable)                              │
│  removed_by               : String (nullable)                                │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│  ZoneMappingRecord                                                           │
├──────────────────────────────────────────────────────────────────────────────┤
│  mapping_id               : GUID (PK)                                        │
│  region                   : String                                           │
│  physical_zone_id         : String      — Azure internal physical zone label  │
│  subscription_id          : GUID (FK → ManagedSubscription)                  │
│  logical_zone             : Int         — subscription-local logical zone     │
│  discovered_at            : DateTime                                         │
│  last_verified_at         : DateTime                                         │
│                                                                              │
│  Index: (region, subscription_id) → physical_zone_id, logical_zone          │
│  Index: (region, physical_zone_id) → [(subscription_id, logical_zone)]      │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│  QuotaRecord                                                                 │
├──────────────────────────────────────────────────────────────────────────────┤
│  quota_id                 : GUID (PK)                                        │
│  subscription_id          : GUID (FK → ManagedSubscription)                  │
│  region                   : String                                           │
│  vm_sku_family            : String      — e.g., "standardDSv3Family"         │
│  quota_limit              : Int         — vCPU limit                         │
│  quota_used               : Int         — current vCPU consumption           │
│  committed_by_crs         : Int         — sum(cr.quantity × cr.vcpu_count)   │
│  deployment_headroom      : Int         — limit − used − committed_by_crs    │
│  alert_threshold_pct      : Float       — configurable, default 0.80         │
│  is_alert_active          : Boolean                                          │
│  last_synced_at           : DateTime                                         │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│  DRCapacityPair                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│  dr_pair_id               : GUID (PK)                                        │
│  pair_name                : String                                           │
│  primary_crg_id           : GUID (FK → CapacityReservationGroup)             │
│  dr_crg_id                : GUID (FK → CapacityReservationGroup)             │
│  primary_region           : String                                           │
│  dr_region                : String                                           │
│  dr_buffer_pct            : Float       — minimum DR capacity as % of primary│
│  dr_status                : Enum [Standby, FailoverActive, FailbackPending]  │
│  failover_triggered_at    : DateTime (nullable)                              │
│  failover_triggered_by    : String (nullable)                                │
│  failback_completed_at    : DateTime (nullable)                              │
│  last_validated_at        : DateTime                                         │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│  CapacityForecast                                                            │
├──────────────────────────────────────────────────────────────────────────────┤
│  forecast_id              : GUID (PK)                                        │
│  cr_id                    : GUID (FK → CapacityReservation)                  │
│  generated_at             : DateTime                                         │
│  forecast_horizon_days    : Int                                              │
│  model_type               : Enum [MovingAverage, ARIMA, ML]                 │
│  forecast_series          : TimeSeries<Date, Int>    — predicted demand       │
│  peak_demand_forecast     : Int                                              │
│  recommended_quantity     : Int                                              │
│  current_quantity         : Int                                              │
│  quantity_delta           : Int          — recommended − current             │
│  projected_cost_delta     : Float        — cost impact of recommendation     │
│  confidence_level         : Float                                            │
│  recommendation_status    : Enum [Pending, Approved, Rejected, Applied]     │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│  OperationRecord                                                             │
├──────────────────────────────────────────────────────────────────────────────┤
│  operation_id             : GUID (PK)                                        │
│  correlation_id           : GUID         — spans ARM + engine operations     │
│  operation_type           : Enum [CRCreate, CRUpdate, SharingAdd,           │
│                              SharingRemove, FailoverTrigger, ...]            │
│  target_resource_id       : String       — ARM resource ID of target         │
│  initiated_by             : String       — operator or system identity       │
│  initiated_at             : DateTime                                         │
│  completed_at             : DateTime (nullable)                              │
│  status                   : Enum [Pending, InProgress, Succeeded,           │
│                              Failed, Compensating, Compensated]              │
│  before_state             : JSON                                             │
│  after_state              : JSON (nullable)                                  │
│  error_code               : String (nullable)                                │
│  error_message            : String (nullable)                                │
│  retry_count              : Int                                              │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│  PlacementPolicy                                                             │
├──────────────────────────────────────────────────────────────────────────────┤
│  policy_id                : GUID (PK)                                        │
│  policy_name              : String                                           │
│  policy_version           : Int                                              │
│  applies_to_workloads     : String[]                                         │
│  optimization_objective   : Enum [CostFirst, AvailFirst, DRBufferFirst]     │
│  min_zone_spread          : Int          — minimum distinct physical zones   │
│  max_single_zone_pct      : Float        — max % of workload in one zone     │
│  dr_buffer_enforcement    : Boolean      — hard or advisory DR buffer check  │
│  allowed_regions          : String[]                                         │
│  allowed_skus             : String[]                                         │
│  rules                    : JSON[]       — structured policy rule DAG        │
│  created_by               : String                                           │
│  effective_from           : DateTime                                         │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Entity Relationships

```
ManagedSubscription ──────< CapacityReservationGroup (provider_subscription_id)
ManagedSubscription ──────< SharingRelationship      (consumer_subscription_id)
ManagedSubscription ──────< QuotaRecord              (subscription_id)
ManagedSubscription ──────< ZoneMappingRecord        (subscription_id)

CapacityReservationGroup ─< CapacityReservation      (crg_id)
CapacityReservationGroup ─< SharingRelationship      (crg_id)
CapacityReservationGroup ─  DRCapacityPair           (primary_crg_id or dr_crg_id)

CapacityReservation ──────< CapacityForecast         (cr_id)

DRCapacityPair ────────────  CapacityReservationGroup (primary_crg_id)
DRCapacityPair ────────────  CapacityReservationGroup (dr_crg_id)

All entities ─────────────< OperationRecord          (target_resource_id)
```

---

## 5. APIs Required

### 5.1 Engine-Exposed REST API

#### Subscription Management

```
POST   /api/v1/subscriptions                  Onboard a managed subscription
GET    /api/v1/subscriptions                  List all managed subscriptions
GET    /api/v1/subscriptions/{sub_id}         Get subscription detail + quota + zone mappings
PATCH  /api/v1/subscriptions/{sub_id}         Update subscription config (role, regions)
DELETE /api/v1/subscriptions/{sub_id}         Offboard subscription (requires no active CRGs)
POST   /api/v1/subscriptions/{sub_id}/sync    Trigger immediate sync with ARM
```

#### Capacity Reservation Group Management

```
POST   /api/v1/crgs                           Create CRG (triggers ARM provisioning)
GET    /api/v1/crgs                           List all managed CRGs (filterable by sub, region, purpose)
GET    /api/v1/crgs/{crg_id}                  Get CRG detail (sharing profile, state, drift)
PATCH  /api/v1/crgs/{crg_id}                  Update CRG configuration (tags, purpose)
DELETE /api/v1/crgs/{crg_id}                  Delete CRG (validates empty before execution)
GET    /api/v1/crgs/{crg_id}/drift            Get drift status between desired and actual state
POST   /api/v1/crgs/{crg_id}/reconcile        Trigger immediate reconciliation for this CRG
```

#### Capacity Reservation Management

```
POST   /api/v1/crgs/{crg_id}/reservations               Create CR within CRG
GET    /api/v1/crgs/{crg_id}/reservations                List CRs in CRG
GET    /api/v1/crgs/{crg_id}/reservations/{cr_id}        Get CR detail (quantity, allocated, utilization)
PATCH  /api/v1/crgs/{crg_id}/reservations/{cr_id}        Update CR quantity (validates quota first)
DELETE /api/v1/crgs/{crg_id}/reservations/{cr_id}        Delete CR (validates no associations)
GET    /api/v1/crgs/{crg_id}/reservations/{cr_id}/utilization  Historical utilization time series
```

#### Sharing Profile Management

```
GET    /api/v1/crgs/{crg_id}/consumers                   List all Consumer subscriptions for CRG
POST   /api/v1/crgs/{crg_id}/consumers                   Add Consumer to sharing profile
DELETE /api/v1/crgs/{crg_id}/consumers/{sub_id}          Remove Consumer (validates active VMs)
GET    /api/v1/crgs/{crg_id}/consumers/{sub_id}/status   Get RBAC setup status (Steps 1-3)
POST   /api/v1/crgs/{crg_id}/consumers/{sub_id}/setup    Trigger RBAC setup orchestration
GET    /api/v1/relationships                              List all sharing relationships
```

#### Zone Mapping

```
GET    /api/v1/zones/mappings                             All zone mappings across managed subs
GET    /api/v1/zones/mappings/{region}                    Zone mappings for a specific region
GET    /api/v1/zones/peers?provider={sub}&zone={z}&region={r}  Consumer zones for Provider zone
POST   /api/v1/zones/resolve                              Resolve correct Consumer zone for CRG reference
POST   /api/v1/zones/refresh                              Trigger zone mapping refresh
```

#### Quota Management

```
GET    /api/v1/quota                                      All quota records across managed subs
GET    /api/v1/quota/{sub_id}                             Quota detail for subscription
GET    /api/v1/quota/{sub_id}/{region}/{sku_family}       Specific quota record with headroom calculation
POST   /api/v1/quota/{sub_id}/request                     Initiate quota increase request
GET    /api/v1/quota/{sub_id}/requests                    List quota increase requests and status
POST   /api/v1/quota/refresh                              Force quota data refresh across all subs
```

#### DR Failover

```
POST   /api/v1/dr/pairs                                   Define DR capacity pair
GET    /api/v1/dr/pairs                                   List DR pairs with status
GET    /api/v1/dr/pairs/{pair_id}                         DR pair detail (capacity, buffer status)
POST   /api/v1/dr/pairs/{pair_id}/failover                Trigger failover (requires approval token)
POST   /api/v1/dr/pairs/{pair_id}/failback                Trigger failback
GET    /api/v1/dr/pairs/{pair_id}/events                  DR event history
GET    /api/v1/dr/health                                  Overall DR readiness across all pairs
```

#### Placement

```
POST   /api/v1/placement/evaluate                         Evaluate placement request against policies
GET    /api/v1/placement/policies                         List placement policies
POST   /api/v1/placement/policies                         Create/update placement policy
GET    /api/v1/placement/policies/{policy_id}             Get policy detail
GET    /api/v1/placement/recommendations/{sub_id}         Current placement recommendations
```

#### Forecasting and Cost

```
GET    /api/v1/forecasts                                  All active forecasts
GET    /api/v1/forecasts/{cr_id}                          Forecast for specific CR
POST   /api/v1/forecasts/{cr_id}/approve                  Approve forecast recommendation
POST   /api/v1/forecasts/{cr_id}/reject                   Reject forecast recommendation
GET    /api/v1/cost/summary                               Cost summary across all managed CRGs
GET    /api/v1/cost/idle                                  Idle CRs (allocated=0 for threshold period)
GET    /api/v1/cost/underutilized                         Underutilized CRs below threshold
GET    /api/v1/cost/chargeback/{billing_period}           Chargeback attribution report
```

#### Operations and Audit

```
GET    /api/v1/operations                                 List operations (filterable by resource, type)
GET    /api/v1/operations/{operation_id}                  Get operation status
GET    /api/v1/audit                                      Audit log (filterable, paginated)
GET    /api/v1/health                                     Engine health check
GET    /api/v1/metrics                                    Prometheus-format metrics endpoint
```

### 5.2 Azure ARM APIs Consumed

| ARM API | Version | Purpose |
|---|---|---|
| `Microsoft.Compute/capacityReservationGroups` — PUT, GET, DELETE | `2024-03-01` | CRG CRUD |
| `Microsoft.Compute/capacityReservationGroups/.../capacityReservations` — PUT, GET, DELETE | `2024-03-01` | CR CRUD |
| `Microsoft.Compute/capacityReservationGroups` — GET with `$expand=instanceView` | `2024-03-01` | Allocated count |
| `Microsoft.Compute/virtualMachines` — GET, PATCH | `2024-11-01` | VM CRG association |
| `Microsoft.Compute/skus` — GET | `2024-11-01` | SKU availability by region/zone |
| `Subscriptions/list-locations` with `availabilityZoneMappings` | `2024-01-01` | Zone mapping discovery |
| `Microsoft.Resources/checkZonePeers` — POST | `2022-12-01` | Cross-sub zone peering |
| `Microsoft.Capacity/resourceProviders/locations/serviceLimits` — GET, PUT | `2023-02-01` | Quota query and request |
| `Microsoft.Authorization/roleAssignments` — PUT, DELETE, GET | `2022-04-01` | RBAC management |
| `Microsoft.Authorization/roleDefinitions` — GET | `2022-04-01` | Custom role validation |
| `Microsoft.Resources/subscriptions/resourceGroups` | `2024-03-01` | Resource group management |
| `Microsoft.CostManagement/query` | `2023-11-01` | Billing data retrieval |
| `Microsoft.Insights/metrics` — GET | `2023-10-01` | VM metrics for utilization |
| `Microsoft.Resources/deployments` — PUT (ARM template deploys) | `2024-03-01` | Bulk VM deployment (failover) |

---

## 6. Azure Services Required

### 6.1 Compute and Hosting

| Azure Service | Purpose | SKU / Configuration |
|---|---|---|
| Azure Kubernetes Service (AKS) | Engine hosting — microservices container orchestration | Zone-redundant, minimum 3-node pool across 3 AZs |
| Azure Container Registry (ACR) | Container image registry for engine components | Geo-replicated, Premium tier |
| Azure API Management (APIM) | API gateway, rate limiting, authentication enforcement | Standard v2 tier, zone-redundant |

### 6.2 Data and State

| Azure Service | Purpose | SKU / Configuration |
|---|---|---|
| Azure Cosmos DB | Primary state store (entity model from Section 4) | Multi-region write, SQL API, zone-redundant |
| Azure Cosmos DB Change Feed | State change event propagation to downstream components | Enabled on all collections |
| Azure Database for PostgreSQL (Flexible) | Time-series utilization and audit log storage | Zone-redundant, read replica for reporting |
| Azure Cache for Redis | Distributed cache for zone mapping registry, quota data | Zone-redundant, Premium tier |
| Azure Blob Storage | Forecast data archives, cost reports, audit exports | Zone-redundant (ZRS), private endpoint |

### 6.3 Messaging and Eventing

| Azure Service | Purpose | SKU / Configuration |
|---|---|---|
| Azure Service Bus | Durable command queue for async operations | Premium tier, zone-redundant, geo-recovery |
| Azure Event Grid | ARM event subscriptions (VM events, quota alerts) | System topic per subscription |
| Azure Event Hubs | High-volume telemetry and metrics ingestion | Zone-redundant |

### 6.4 Security and Identity

| Azure Service | Purpose | SKU / Configuration |
|---|---|---|
| Azure Key Vault | Secret storage (service principal certs, API keys) | Premium tier, HSM-backed, soft-delete enabled |
| Azure Active Directory (Entra ID) | Engine authentication (Managed Identity + SPN) | — |
| Azure Private Link / Private Endpoints | Network isolation for all PaaS services | Per service |
| Azure Firewall | Egress control for ARM API calls | Premium tier |

### 6.5 Monitoring and Observability

| Azure Service | Purpose | SKU / Configuration |
|---|---|---|
| Azure Monitor | Metrics, alerts, dashboards | Log Analytics workspace (zone-redundant) |
| Azure Application Insights | Distributed tracing, APM | Workspace-based, same Log Analytics workspace |
| Azure Log Analytics | Centralized log aggregation and query | Dedicated cluster for security requirements |
| Azure Alerts | Quota threshold, DR buffer, idle CR notifications | Action groups per alert class |

### 6.6 Automation and Governance

| Azure Service | Purpose | SKU / Configuration |
|---|---|---|
| Azure Policy | Enforce governance on CRG/CR resources managed by engine | Initiative definitions for engine-managed resources |
| Azure Resource Graph | Cross-subscription resource discovery (Known Issue 2 workaround) | — |
| Azure Managed Grafana | Operational dashboards | Zone-redundant |

---

## 7. Event Sources

### 7.1 Azure ARM Events (via Azure Event Grid — Resource Group and Subscription system topics)

| Event Type | Source | Engine Action |
|---|---|---|
| `Microsoft.Resources.ResourceWriteSuccess` on `capacityReservationGroups` | ARM | Trigger CRG state sync |
| `Microsoft.Resources.ResourceDeleteSuccess` on `capacityReservationGroups` | ARM | Mark CRG as deleted; cascade updates |
| `Microsoft.Resources.ResourceWriteSuccess` on `capacityReservations` | ARM | Trigger CR state sync |
| `Microsoft.Resources.ResourceWriteSuccess` on `virtualMachines` | ARM | Detect VM CRG association changes |
| `Microsoft.Resources.ResourceDeleteSuccess` on `virtualMachines` | ARM | Update allocated counts |
| `Microsoft.Resources.ResourceWriteSuccess` on `roleAssignments` | ARM | Validate RBAC setup steps |

### 7.2 Azure Monitor Alerts (via Action Groups → Service Bus)

| Alert | Trigger Condition | Engine Action |
|---|---|---|
| Quota threshold alert | `quota_used / quota_limit >= threshold_pct` | Create QuotaAlert; trigger quota increase workflow |
| CR overallocation alert | `allocated > quantity` on any CR | Create OverallocationEvent; notify operator |
| Idle CR alert | `allocated == 0` for ≥ threshold days | Create IdleCREvent; publish cost recommendation |
| DR buffer violation | `dr_cr.quantity < primary_cr.quantity × dr_buffer_pct` | Create DRBufferViolationEvent; alert DR operator |

### 7.3 Engine Internal Events (via Service Bus topics)

| Event | Produced By | Consumed By |
|---|---|---|
| `CRGCreated` | Provisioning Service | Sharing Orchestrator, Zone Mapping Resolver |
| `SharingProfileUpdated` | Sharing Orchestrator | State Sync, Audit Service |
| `ZoneMappingRefreshed` | Zone Mapping Resolver | Placement Engine |
| `QuotaUpdated` | Quota Sync Service | Forecasting Engine, Placement Engine |
| `ForecastGenerated` | Forecasting Engine | Cost Optimization Service, Notification Service |
| `RecommendationApproved` | Workflow Approval | Provisioning Service |
| `FailoverTriggered` | DR Orchestrator | Provisioning Service, Audit Service |
| `ReconciliationCycleDone` | Reconciliation Engine | Observability Service |
| `DriftDetected` | Reconciliation Engine | Alert Service, Audit Service |
| `OperationFailed` | Any Service | Dead Letter Processor, Alert Service |

### 7.4 Scheduled Events (via AKS CronJob or Azure Functions timer trigger)

| Schedule | Trigger | Purpose |
|---|---|---|
| Every 5 minutes | Reconciliation loop | Compare desired vs. actual ARM state for all CRGs |
| Every 15 minutes | Quota sync | Refresh quota records for all managed subscriptions |
| Every 60 minutes | Zone mapping refresh | Re-discover zone mappings and zone peer data |
| Every 6 hours | Utilization snapshot | Record current allocated/quantity for time-series |
| Every 24 hours | Forecast job | Generate 30/60/90 day forecasts for all CRs |
| Every 24 hours | Cost report | Compute idle, underutilized, chargeback data |
| Every 24 hours | DR health check | Validate all DR pairs are in Standby state with correct capacity |

### 7.5 Operator-Initiated Events (via Engine REST API)

| Event | Source | Purpose |
|---|---|---|
| `OnboardSubscription` | API: `POST /subscriptions` | Add new subscription to managed estate |
| `TriggerFailover` | API: `POST /dr/pairs/{id}/failover` | Initiate DR failover with approval gate |
| `TriggerFailback` | API: `POST /dr/pairs/{id}/failback` | Initiate DR failback |
| `ApproveRecommendation` | API: `POST /forecasts/{cr_id}/approve` | Authorize capacity right-sizing |
| `ForceReconcile` | API: `POST /crgs/{id}/reconcile` | Out-of-band reconciliation for a specific CRG |
| `RequestQuotaIncrease` | API: `POST /quota/{sub_id}/request` | Initiate quota increase via Azure Support API |

---

## 8. State Management

### 8.1 Desired State vs. Actual State Model

The engine operates on a **desired state / actual state** reconciliation model:

```
Desired State (Engine)                 Actual State (ARM)
─────────────────────────────          ──────────────────────────────
CapacityReservationGroup.             ARM: capacityReservationGroups
  desired_sharing_profile         ←→   properties.sharingProfile.subscriptionIds
  
CapacityReservation.                  ARM: capacityReservations
  desired_quantity                ←→   properties.reservationId.sku.capacity
  
QuotaRecord.                          ARM: Microsoft.Capacity/serviceLimits
  committed_by_crs                ←→   (computed from CR quantities)
  
ZoneMappingRecord                ←→   ARM: list-locations + checkZonePeers API
```

**Reconciliation Logic:**
1. Reconciliation Engine reads desired state from Cosmos DB
2. Reconciliation Engine queries ARM for actual state (GET operations)
3. For each entity: compute delta between desired and actual
4. If delta exists: record drift in entity record; emit `DriftDetected` event
5. Depending on auto-remediation policy: either auto-remediate or alert operator

### 8.2 State Machine — CapacityReservation

```
         ┌─────────┐
         │ Desired │ ── Engine operator defines desired CR
         └────┬────┘
              │ Provisioning Service submits ARM PUT
              ▼
     ┌─────────────────┐
     │   Provisioning  │ ── ARM operation in-flight
     └────────┬────────┘
              │ ARM provisioningState == Succeeded
              ▼
         ┌─────────┐     QuantityIncrease     ┌───────────────┐
         │  Active │ ──────────────────────── │ UpdatingQty   │
         │ (Synced)│ ◄─────────────────────── └───────────────┘
         └────┬────┘     ARM confirms new qty
              │
    ┌─────────┴─────────┐
    │ Drift detected    │──── Reconciling ───► ARM PUT to correct
    └─────────┬─────────┘
              │
    ┌─────────┴────────────┐
    │ Overallocated        │ allocated > quantity
    │ (Alert Active)       │──── Notify ───► Operator increases quantity
    └──────────────────────┘
              │
    ┌─────────┴────────────┐
    │ Idle                 │ allocated == 0 for threshold period
    │ (Cost Alert)         │──── Recommend deletion or scale-to-zero
    └──────────────────────┘
              │ Delete requested + all VMs disassociated
              ▼
    ┌──────────────────────┐
    │   Deleting           │ ARM DELETE in-flight
    └────────┬─────────────┘
             │ ARM confirms deletion
             ▼
    ┌──────────────────────┐
    │   Deleted            │ Terminal state — soft-delete record retained for audit
    └──────────────────────┘
```

### 8.3 State Machine — SharingRelationship

```
         ┌──────────┐
         │ Requested│ ── Operator calls POST /consumers
         └────┬─────┘
              │ Validation: sub registered, <100 consumers, no duplicate
              ▼
     ┌──────────────────┐
     │  SetupPending    │ ── Three-step RBAC orchestration begins
     │  (Step 1 → 3)   │
     └────────┬─────────┘
              │ All three RBAC steps confirmed
              ▼
         ┌────────┐
         │ Active │ ── Consumer can deploy VMs against shared CRG
         └────┬───┘
              │ Operator requests removal
              ▼
    ┌─────────────────────┐
    │ RemovalPending      │ ── Check: active Consumer VM count
    │                     │    If > 0: require force OR VM disassociation
    └──────────┬──────────┘
               │ Safe removal confirmed (0 active VMs) or force-override
               ▼
    ┌──────────────────────┐
    │ Removed              │ ARM sharingProfile updated; RBAC revoked
    └──────────────────────┘
```

### 8.4 State Machine — DRCapacityPair

```
    ┌──────────┐
    │ Defined  │ ── DR pair registered; CRGs exist but sharing may not be configured
    └────┬─────┘
         │ DR sharing profile configured; RBAC complete; DR CRG provisioned
         ▼
    ┌──────────┐
    │ Standby  │ ── DR CR allocated=0; capacity reserved; buffer validated
    └────┬─────┘
         │ Failover triggered (operator + approval)
         ▼
    ┌────────────────┐
    │FailoverActive  │ ── DR VMs running in DR CRG; primary may be degraded
    └───────┬────────┘
            │ Primary region restored; operator triggers failback
            ▼
    ┌────────────────┐
    │FailbackPending │ ── DR VMs deallocation; primary CRG restoration in progress
    └───────┬────────┘
            │ All DR VMs deallocated; primary CRG at pre-failover state
            ▼
    ┌──────────┐
    │ Standby  │ ← Return to steady state
    └──────────┘
```

### 8.5 Idempotency and Saga Patterns

All multi-step operations (sharing setup, failover trigger, onboarding) are implemented as **compensatable sagas**:

- Each saga step is recorded in `OperationRecord` before execution
- Steps carry unique idempotency keys derived from `(operation_id, step_number)`
- On failure: compensation steps execute in reverse order
- Saga state is persisted in Cosmos DB — not in-memory — ensuring recovery after process restart
- Concurrent saga execution on the same resource is serialized via distributed lock (Redis SETNX)

---

## 9. Failure Handling

### 9.1 ARM API Failure Modes

| Failure | Detection | Handling |
|---|---|---|
| ARM 429 (throttled) | HTTP 429 response | Exponential backoff with jitter; retry up to 5 times; log throttle event |
| ARM 503 (unavailable) | HTTP 503 or timeout | Circuit breaker open; queue operation for deferred retry; alert operator |
| ARM 400 (validation) | HTTP 400 response | Abort operation; classify error (quota vs. zone vs. auth vs. capacity); return structured error to caller |
| ARM 403 (unauthorized) | HTTP 403 response | Alert security team; classify as RBAC gap; do not retry; require operator action |
| ARM 409 (conflict) | HTTP 409 response | Check if conflict is stale state (re-read ARM); if true state conflict: pause saga; alert operator |
| ARM async timeout | `provisioningState` stuck in `Updating` | Poll for maximum 30 minutes; emit `OperationTimeout` event; alert operator |
| CR creation capacity failure | HTTP 400 with capacity error code | Do not retry; raise capacity shortage alert; route to regional placement alternative |

### 9.2 State Drift Handling

| Drift Type | Detection | Auto-Remediation | Alert Threshold |
|---|---|---|---|
| Sharing profile missing Consumer | Reconcile: desired has consumer, ARM does not | Yes — re-add consumer if RBAC still valid | Immediate |
| Sharing profile has unauthorized Consumer | Reconcile: ARM has consumer not in desired | Yes — remove unauthorized consumer | Immediate + Security alert |
| CR quantity mismatch | Reconcile: desired_quantity ≠ actual_quantity | Yes if safe (increase); No if decrease (quota risk) | Immediate |
| CR deleted externally | Reconcile: ARM returns 404 for known CR | No — mark engine record as ExternallyDeleted | Immediate |
| CRG deleted externally | Reconcile: ARM returns 404 for known CRG | No — mark CRG ExternallyDeleted; cascade to CRs and SharingRelationships | Critical alert |
| Zone mapping change | Zone mapping refresh returns new mapping | Yes — update registry; validate existing CRG associations | Warn operator |
| Overallocation detected | allocated > quantity in instanceView | No (cannot auto-increase without quota validation) | Immediate |

### 9.3 Quota Failure Handling

```
Pre-operation Quota Check:
  1. Query QuotaRecord for target subscription, region, SKU family
  2. Calculate: headroom = limit − used − committed_by_crs
  3. Calculate: operation_demand = requested_quantity × sku_vcpu_count
  4. If operation_demand > headroom:
       → Abort operation
       → Return structured error: QUOTA_INSUFFICIENT with:
           - current limit
           - current usage
           - committed by CRs
           - required for this operation
           - deficit
           - remediation: link to quota increase API endpoint
  5. Optionally: auto-initiate quota increase request if auto_quota_increase is enabled
     → Create QuotaIncreaseRequest
     → Call Microsoft.Capacity/serviceLimits PUT
     → Track request ID; poll for approval
     → Notify operator of outcome
```

### 9.4 Zone Mismatch Failure Handling

```
On VM Placement Request (via Placement Engine):
  1. Identify target CRG and its physical zone (from engine zone mapping registry)
  2. Identify Consumer subscription
  3. Resolve Consumer logical zone: ZoneMappingRecord WHERE
       region = target_region AND
       subscription_id = consumer_sub_id AND
       physical_zone_id = crg_physical_zone
  4. If no matching ZoneMappingRecord:
       → Trigger zone mapping refresh for Consumer subscription
       → Retry after refresh
       → If still no match: return ZONE_MAPPING_UNAVAILABLE error
  5. If consumer_logical_zone ≠ requested_zone:
       → Return ZONE_MISMATCH error with:
           - requested zone (incorrect)
           - correct consumer zone
           - physical zone label (if available)
           - remediation: use engine /zones/resolve endpoint
```

### 9.5 Sharing Lifecycle Failure Handling

| Operation | Failure Scenario | Handling |
|---|---|---|
| Sharing setup (3-step) | Step 1 RBAC grant fails (insufficient permission) | Abort saga; return error; require operator to grant prerequisite permissions; do not proceed to Step 2 |
| Sharing setup | Step 2 API call fails (ARM error) | Abort saga; compensate Step 1 if already executed; alert operator |
| Sharing setup | Step 3 RBAC grant fails | Compensate Steps 1 and 2; alert operator; relationship remains in SetupPending |
| Forced unsharing with active VMs | operator force-override | Record operator acknowledgment; proceed with unsharing; emit `ForcedUnsharingWithActiveVMs` audit event; alert Consumer subscription owner |
| Consumer VM fails to start post-unsharing | ARM returns error on VM start | Engine cannot directly remediate Consumer VMs; emit advisory alert to Consumer subscription; suggest clearing `capacityReservationGroup` property |

### 9.6 DR Failover Failure Handling

| Scenario | Detection | Handling |
|---|---|---|
| DR CRG has insufficient capacity at failover time | `dr_cr.quantity < required_vm_count` | Block failover; alert; trigger emergency capacity request |
| DR Consumer quota insufficient at failover time | Pre-failover quota check fails | Alert immediately; trigger emergency quota request; do not proceed |
| DR VM deployment fails during failover | ARM deployment returns error | Continue deploying remaining VMs; record failed deployments; alert; partial failover state |
| Failover hangs — VMs stuck in Provisioning | Poll timeout after 30 min | Mark failover as PartiallyComplete; alert; require operator intervention |
| DR CRG in wrong zone for Consumer zone mapping | Zone mismatch detected during failover | Abort failover; this is a setup configuration error; immediate alert |

---

## 10. Security Model

### 10.1 Identity Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Engine Managed Identities (one per managed subscription)                  │
│                                                                            │
│  engine-mi-provider-sub:                                                   │
│    ├── Role: Contributor on rg-poc-capacity-eus2 (CRG resource group)     │
│    ├── Role: User Access Administrator on provider subscription            │
│    │         (required to execute RBAC Step 1 and 3)                       │
│    └── Role: Reader on all managed subscriptions                           │
│                                                                            │
│  engine-mi-consumer-{sub_id}:                                              │
│    ├── Role: Virtual Machine Contributor on Consumer subscription          │
│    └── Role: Reader on Consumer subscription                               │
│                                                                            │
│  engine-mi-platform:                                                       │
│    ├── Role: Reader on all subscriptions (zone mapping, quota queries)     │
│    └── Role: Azure Resource Graph Reader                                   │
└────────────────────────────────────────────────────────────────────────────┘
```

### 10.2 Engine API RBAC

| Engine Role | Permissions | Assignment Scope |
|---|---|---|
| `ACRME.Admin` | All operations including subscription onboarding, policy management, DR pair definition | Platform team only |
| `ACRME.Operator` | CRG/CR CRUD, sharing management, quota requests, DR operations | Engineering ops team |
| `ACRME.DROperator` | DR pair management and failover/failback triggers only | DR on-call team |
| `ACRME.Reader` | Read-only access to all state, forecasts, cost data | FinOps, capacity planning |
| `ACRME.Consumer` | Read sharing relationships relevant to their subscription | Tenant team per subscription |

### 10.3 Secret Management

```
All secrets stored in Azure Key Vault — naming convention: acrme-{secret-type}-{environment}

Secrets managed:
  - service-principal-cert-{subscription-id}  : SPN certificate per cross-sub managed identity
  - arm-api-key-{service}                     : Any third-party service API keys
  - db-connection-string-{component}          : Database connection strings
  - redis-connection-string                   : Cache connection string
  - servicebus-connection-string              : Service Bus namespace connection

Secret rotation:
  - Certificate rotation: 90-day automated rotation via Key Vault rotation policy
  - Connection strings: Rotated on-demand; engine hot-reloads via Key Vault references
  - No secrets in environment variables; all access via Key Vault SDK at runtime
```

### 10.4 Network Isolation

```
Engine VNet Architecture:
  ├── Engine API subnet (AKS node pool) ── Private Link to:
  │     ├── Azure Cosmos DB (private endpoint)
  │     ├── Azure Cache for Redis (private endpoint)
  │     ├── Azure Service Bus (private endpoint)
  │     ├── Azure Key Vault (private endpoint)
  │     └── Azure Container Registry (private endpoint)
  │
  ├── Egress via Azure Firewall:
  │     ├── Allowed: management.azure.com (ARM API)
  │     ├── Allowed: login.microsoftonline.com (Entra ID token)
  │     ├── Allowed: graph.microsoft.com (Resource Graph)
  │     └── Denied: all other internet destinations
  │
  └── APIM subnet (API gateway) ── TLS-only; Azure AD auth enforced
        └── Inbound: only from designated operator IP ranges
```

### 10.5 Audit and Non-Repudiation

Every state-mutating operation is recorded in the `OperationRecord` table with:
- Operator identity (from Azure AD token subject claim)
- Timestamp (UTC)
- Before and after state (JSON)
- ARM correlation ID
- Engine correlation ID (spans all saga steps)

Audit log is append-only (Cosmos DB immutability policy enabled on audit container).  
Audit log is replicated to Log Analytics with 90-day hot retention and 2-year archive tier.  
Security audit events (auth failures, privilege escalations) are additionally streamed to Microsoft Sentinel.

---

## 11. Integration Points

### 11.1 Azure ARM Control Plane

**Nature:** Synchronous REST API calls (GET/PUT/DELETE) and asynchronous ARM operations  
**Authentication:** Managed Identity or SPN certificate; per-subscription credentials  
**Rate Limiting:** ARM throttles at 1,200 reads and 1,200 writes per subscription per hour; engine implements per-subscription rate limiters with token bucket algorithm  
**Circuit Breaker:** Per-subscription circuit breaker; opens after 3 consecutive failures; 30-second open window before half-open probe

### 11.2 Azure Event Grid

**Nature:** Push-based event delivery for ARM resource lifecycle events  
**Subscription Scope:** Resource Group-level system topics per managed CRG resource group  
**Delivery:** Push to Service Bus queue (durable); dead-letter after 3 delivery failures  
**Events Consumed:** ResourceWriteSuccess, ResourceDeleteSuccess for Compute resource types

### 11.3 Azure Resource Graph

**Nature:** Cross-subscription query API for resource discovery  
**Use Cases:**  
  - CRG discovery for Consumer subscriptions (Known Issue 2 workaround)
  - Cross-subscription VM inventory for association auditing
  - Policy compliance reporting

### 11.4 Azure Cost Management

**Nature:** REST API for billing data retrieval  
**Authentication:** Managed Identity with `Cost Management Reader` role on billing scope  
**Data Retrieved:** Daily actual cost by subscription and resource type, filtered to CRG-related resource IDs  
**Latency:** Cost data available with 24–48 hour delay; engine aligns cost reporting cadence

### 11.5 Microsoft Capacity Portal (Quota API)

**Nature:** REST API for quota query and increase request submission  
**Endpoint:** `Microsoft.Capacity/resourceProviders/locations/serviceLimits`  
**Authentication:** Managed Identity with `Reader` and `Support Request Contributor` roles  
**Workflow:** Engine submits quota increase request → Azure processes (24–72 hours) → Engine polls for status → Notifies operator on approval or rejection

### 11.6 Internal Platform Systems (External to Engine)

| System | Integration Type | Direction | Data Exchanged |
|---|---|---|---|
| ITSM / ServiceNow | Webhook → ITSM ticket creation | Outbound | DR events, quota alerts, idle CR alerts |
| FinOps Platform | REST API pull or webhook push | Bidirectional | Chargeback reports, cost allocations, budget signals |
| Capacity Planning Tool | REST API | Outbound | Forecast time series, recommendation list |
| CMDB | REST API push | Outbound | CRG/CR resource inventory, subscription-subscription relationships |
| Deployment Automation (ADO / GitHub Actions) | Webhook → pipeline trigger | Outbound | Failover trigger → downstream VM deployment pipeline |
| PagerDuty / Alerting | Webhook | Outbound | DR buffer violations, overallocation alerts, quota exhaustion |

---

## 12. System Context Diagram

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                      SYSTEM CONTEXT DIAGRAM                                   ║
║            Azure Capacity Reservation Management Engine (ACRME)               ║
╚═══════════════════════════════════════════════════════════════════════════════╝

 EXTERNAL ACTORS                                                  AZURE PLATFORM
 ─────────────────                                               ────────────────

 ┌─────────────┐                                          ┌─────────────────────┐
 │  Platform   │  REST API (HTTPS + Azure AD)             │  Azure ARM          │
 │  Engineers  │ ─────────────────────────────────────►  │  management.azure   │
 │  (Operators)│ ◄─────────────────────────────────────  │  .com               │
 └─────────────┘                                          │  - Compute API      │
                                                          │  - Quota API        │
 ┌─────────────┐                                          │  - RBAC API         │
 │  DR On-Call │  REST API (ACRME.DROperator role)        │  - Cost API         │
 │  Team       │ ─────────────────────────────────────►  └──────────┬──────────┘
 └─────────────┘                                                     │ ARM Events
                                                                     │ (Event Grid)
 ┌─────────────┐                                                     ▼
 │  FinOps /   │  REST API (ACRME.Reader role)        ┌─────────────────────────┐
 │  Cost Teams │ ────────────────────────────────────►│                         │
 └─────────────┘  Cost reports / chargeback data      │     A C R M E           │
                                                       │                         │
 ┌─────────────┐                                       │  Azure Capacity         │
 │  Capacity   │  REST API (ACRME.Reader role)         │  Reservation            │
 │  Planning   │ ◄────────────────────────────────────│  Management Engine      │
 │  Tool       │  Forecast time series / recs          │                         │
 └─────────────┘                                       │  (AKS — Zone Redundant) │
                                                       │                         │
 ┌─────────────┐                                       └────────────┬────────────┘
 │  Deployment │  Webhook (failover trigger events)               │
 │  Automation │ ◄────────────────────────────────────────────────┤
 │  (ADO/GH)   │                                                   │
 └─────────────┘                                                   │
                                                                   │
 ┌─────────────┐                                                   │ Controls
 │  ITSM /     │  Webhook (alerts, tickets)                       │
 │  ServiceNow │ ◄────────────────────────────────────────────────┤
 └─────────────┘                                                   │
                                                                   │
 ┌─────────────┐                                                   │
 │  PagerDuty  │  Webhook (critical alerts)                        │
 │  / Alerting │ ◄────────────────────────────────────────────────┘
 └─────────────┘

 MANAGED AZURE ESTATE
 ─────────────────────────────────────────────────────────────────

 ┌────────────────────────────────────────────────────────────────────────────┐
 │  Provider Subscription(s)                                                  │
 │                                                                            │
 │  ┌────────────────────────────────────────────────────────┐               │
 │  │  Capacity Reservation Group (Primary)                  │ ◄─── ACRME   │
 │  │  ├── CR: Zone 1, SKU: D16s_v3, qty=20                 │     manages   │
 │  │  ├── CR: Zone 2, SKU: D16s_v3, qty=15                 │     lifecycle │
 │  │  └── sharingProfile → [Consumer-A, Consumer-B, DR-Sub]│               │
 │  └────────────────────────────────────────────────────────┘               │
 │                                                                            │
 │  ┌────────────────────────────────────────────────────────┐               │
 │  │  Capacity Reservation Group (DR)                       │ ◄─── ACRME   │
 │  │  ├── CR: Zone 2, SKU: D16s_v3, qty=8                  │     manages   │
 │  │  └── sharingProfile → [DR-Sub]                         │     DR pair  │
 │  └────────────────────────────────────────────────────────┘               │
 └────────────────────────────────────────────────────────────────────────────┘
                         │                 │
                         │ Zone-mapped     │ Zone-mapped
                         │ shared access  │ DR shared access
                         ▼                 ▼
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │  Consumer Subscription(s)                                                   │
 │                                                                             │
 │  ┌─────────────────────────────┐    ┌─────────────────────────────────────┐│
 │  │  Consumer-A                 │    │  Consumer-B                         ││
 │  │  VMs referencing Provider   │    │  VMs referencing Provider CRG       ││
 │  │  CRG via cross-sub resource │    │  (zone mapped to correct logical zone││
 │  │  ID (Zone: Logical 2        │    │   for Consumer-B sub)               ││
 │  │   → Physical B)             │    └─────────────────────────────────────┘│
 │  └─────────────────────────────┘                                            │
 │                                                                             │
 │  ┌─────────────────────────────┐                                            │
 │  │  DR-Sub                     │                                            │
 │  │  [No VMs in Standby]        │                                            │
 │  │  [DR VMs on Failover]       │                                            │
 │  └─────────────────────────────┘                                            │
 └─────────────────────────────────────────────────────────────────────────────┘
```

---

## 13. Component Model

### 13.1 Internal Component Architecture

```
╔══════════════════════════════════════════════════════════════════════════════════╗
║                    ACRME — INTERNAL COMPONENT MODEL                              ║
╚══════════════════════════════════════════════════════════════════════════════════╝

 ┌─────────────────────────────────────────────────────────────────────────────┐
 │  INGRESS LAYER                                                               │
 │                                                                             │
 │  ┌─────────────────────────────────────────────────────────────────────┐   │
 │  │  API Gateway (Azure APIM)                                           │   │
 │  │  - TLS termination          - Azure AD JWT validation               │   │
 │  │  - Rate limiting (per client)  - Request routing to services        │   │
 │  │  - Correlation ID injection    - API versioning enforcement         │   │
 │  └────────────────────────────────────┬────────────────────────────────┘   │
 └───────────────────────────────────────┼─────────────────────────────────────┘
                                         │
 ┌───────────────────────────────────────┼─────────────────────────────────────┐
 │  API SERVICES LAYER (AKS Deployments) │                                      │
 │                                       ▼                                      │
 │  ┌────────────────────────────────────────────────────────────────────────┐ │
 │  │  Subscription Service          Zone Mapping Service                    │ │
 │  │  - Onboarding workflow         - Zone discovery                        │ │
 │  │  - Resource provider checks    - Check Zone Peers API calls           │ │
 │  │  - MI provisioning trigger     - Zone registry CRUD                   │ │
 │  └────────────────────┬───────────┘  └──────────────────┬────────────────┘ │
 │                        │                                  │                  │
 │  ┌─────────────────────┴─────────────────────────────────┴──────────────┐  │
 │  │  Provisioning Service                                                  │  │
 │  │  - CRG / CR create, update, delete (ARM operations)                   │  │
 │  │  - Quota pre-validation before every mutating operation               │  │
 │  │  - Async ARM operation polling                                        │  │
 │  │  - Saga orchestration for multi-step operations                      │  │
 │  └─────────────────────────────────────┬──────────────────────────────── ┘  │
 │                                         │                                     │
 │  ┌──────────────────────────────────────▼──────────────────────────────────┐ │
 │  │  Sharing Orchestrator Service                                            │ │
 │  │  - Three-step RBAC saga management                                      │ │
 │  │  - sharingProfile ARM updates                                           │ │
 │  │  - Consumer limit enforcement (max 100)                                 │ │
 │  │  - Safe/forced unsharing logic                                          │ │
 │  │  - Active VM count check before removal                                 │ │
 │  └─────────────────────────────────────────────────────────────────────────┘ │
 │                                                                               │
 │  ┌────────────────────────────────────────────────────────────────────────┐  │
 │  │  Quota Service                      DR Orchestrator Service            │  │
 │  │  - Quota record sync                - DR pair CRUD                    │  │
 │  │  - Headroom calculation             - Failover saga orchestration      │  │
 │  │  - Quota increase request API       - Failback saga orchestration      │  │
 │  │  - Alert threshold monitoring       - DR buffer validation             │  │
 │  └────────────────────────────────────────────────────────────────────────┘  │
 │                                                                               │
 │  ┌────────────────────────────────────────────────────────────────────────┐  │
 │  │  Placement Engine Service           Forecasting Service               │  │
 │  │  - Policy-based placement eval      - Time-series analysis            │  │
 │  │  - Zone mapping resolution          - Demand forecast generation      │  │
 │  │  - SKU availability check           - Recommendation creation         │  │
 │  │  - Multi-constraint scoring         - Approval workflow               │  │
 │  └────────────────────────────────────────────────────────────────────────┘  │
 │                                                                               │
 │  ┌────────────────────────────────────────────────────────────────────────┐  │
 │  │  Cost Optimization Service          Notification Service              │  │
 │  │  - Utilization monitoring           - Alert routing                  │  │
 │  │  - Idle CR detection                - ITSM ticket creation           │  │
 │  │  - Chargeback attribution           - PagerDuty integration          │  │
 │  │  - Right-sizing recommendations     - Email/Teams notifications      │  │
 │  └────────────────────────────────────────────────────────────────────────┘  │
 └───────────────────────────────────────────────────────────────────────────────┘

 ┌───────────────────────────────────────────────────────────────────────────────┐
 │  BACKGROUND PROCESSING LAYER (AKS CronJobs / Workers)                        │
 │                                                                               │
 │  ┌──────────────────────────────────┐  ┌──────────────────────────────────┐  │
 │  │  Reconciliation Engine           │  │  ARM Event Processor             │  │
 │  │  - Every 5 min: full estate scan │  │  - Service Bus consumer          │  │
 │  │  - Desired vs. actual comparison │  │  - ARM event → state update      │  │
 │  │  - Drift detection and recording │  │  - Trigger targeted reconcile    │  │
 │  │  - Auto-remediation dispatch     │  │  - VM association change handler │  │
 │  └──────────────────────────────────┘  └──────────────────────────────────┘  │
 │                                                                               │
 │  ┌──────────────────────────────────┐  ┌──────────────────────────────────┐  │
 │  │  Quota Sync Worker               │  │  Utilization Snapshot Worker     │  │
 │  │  - Every 15 min: quota refresh   │  │  - Every 6h: record utilization  │  │
 │  │  - Alert threshold evaluation    │  │  - Feed forecasting time series  │  │
 │  │  - Headroom recalculation        │  │  - Persist to PostgreSQL         │  │
 │  └──────────────────────────────────┘  └──────────────────────────────────┘  │
 │                                                                               │
 │  ┌──────────────────────────────────┐  ┌──────────────────────────────────┐  │
 │  │  Forecast Worker                 │  │  Cost Report Worker              │  │
 │  │  - Daily: generate forecasts     │  │  - Daily: idle/underutil scan    │  │
 │  │  - Publish recommendations       │  │  - Daily: chargeback compute     │  │
 │  │  - Cost projection calculation   │  │  - Cost Management API pull     │  │
 │  └──────────────────────────────────┘  └──────────────────────────────────┘  │
 │                                                                               │
 │  ┌──────────────────────────────────┐  ┌──────────────────────────────────┐  │
 │  │  DR Health Monitor               │  │  Dead Letter Processor           │  │
 │  │  - Daily: DR pair validation     │  │  - Retry failed operations       │  │
 │  │  - Buffer compliance check       │  │  - Escalate unrecoverable ops    │  │
 │  │  - VMSS zone outage watch        │  │  - Notify on-call                │  │
 │  └──────────────────────────────────┘  └──────────────────────────────────┘  │
 └───────────────────────────────────────────────────────────────────────────────┘

 ┌───────────────────────────────────────────────────────────────────────────────┐
 │  DATA LAYER                                                                   │
 │                                                                               │
 │  ┌────────────────────────────┐  ┌─────────────────────────────────────────┐ │
 │  │  Azure Cosmos DB           │  │  Azure PostgreSQL (Flexible)            │ │
 │  │  (Primary State Store)     │  │  (Time-Series + Audit)                  │ │
 │  │  - ManagedSubscription     │  │  - Utilization snapshots (per CR/time)  │ │
 │  │  - CapacityReservationGroup│  │  - Forecast series (per CR/time)        │ │
 │  │  - CapacityReservation     │  │  - OperationRecord (audit log)          │ │
 │  │  - SharingRelationship     │  │  - QuotaRecord history                  │ │
 │  │  - DRCapacityPair          │  │  - Cost attribution records             │ │
 │  │  - PlacementPolicy         │  └─────────────────────────────────────────┘ │
 │  │  - ZoneMappingRecord       │                                               │
 │  │  - CapacityForecast        │  ┌─────────────────────────────────────────┐ │
 │  └────────────────────────────┘  │  Azure Cache for Redis                  │ │
 │                                  │  - Zone mapping registry (hot cache)    │ │
 │  ┌────────────────────────────┐  │  - Quota current values (hot cache)     │ │
 │  │  Azure Blob Storage        │  │  - Distributed saga locks               │ │
 │  │  - Cost report archives    │  │  - API response cache (60s TTL)        │ │
 │  │  - Forecast exports        │  └─────────────────────────────────────────┘ │
 │  │  - Audit log archives      │                                               │
 │  └────────────────────────────┘                                               │
 └───────────────────────────────────────────────────────────────────────────────┘

 ┌───────────────────────────────────────────────────────────────────────────────┐
 │  MESSAGING LAYER                                                              │
 │                                                                               │
 │  Azure Service Bus (Premium, Zone-Redundant)                                 │
 │  ├── Topic: arm-events          → Subscriptions: reconcile-filter, vm-filter │
 │  ├── Topic: engine-commands     → Subscriptions: per-service command queues  │
 │  ├── Topic: engine-events       → Subscriptions: notification, audit, cost   │
 │  ├── Queue:  failover-commands  → DR Orchestrator (serialized execution)     │
 │  └── Queue:  dead-letter        → Dead Letter Processor                      │
 └───────────────────────────────────────────────────────────────────────────────┘
```

### 13.2 Service Dependency Map

```
Placement Engine ──depends on──► Zone Mapping Service (zone resolution)
Placement Engine ──depends on──► Quota Service (headroom check)
Placement Engine ──depends on──► Provisioning Service (CR state read)

DR Orchestrator ──depends on──► Provisioning Service (failover VM deploy)
DR Orchestrator ──depends on──► Quota Service (pre-failover quota validation)
DR Orchestrator ──depends on──► Zone Mapping Service (DR Consumer zone)
DR Orchestrator ──depends on──► Sharing Orchestrator (DR sharing setup)

Forecasting ──depends on──► Utilization Snapshot Worker (time-series data)
Forecasting ──depends on──► Quota Service (quota limit context)

Cost Optimization ──depends on──► Forecasting (right-sizing recommendations)
Cost Optimization ──depends on──► Cost Management API (billing actuals)

Reconciliation Engine ──depends on──► ALL ARM APIs (actual state read)
Reconciliation Engine ──depends on──► Cosmos DB (desired state read)
Reconciliation Engine ──emits to──► Provisioning Service (auto-remediation)
Reconciliation Engine ──emits to──► Alert Service (drift notifications)
```

---

## 14. Engineering Backlog

### Backlog Structure

Each item follows: `[EPIC-ID] / [STORY-ID] | Title | Priority | Estimate | Dependencies`

Priority: `P0` (Critical — MVP blocker) · `P1` (High — MVP scope) · `P2` (Medium — Post-MVP) · `P3` (Low — Future)  
Estimate: `S` (1-3 days) · `M` (3-7 days) · `L` (7-14 days) · `XL` (>14 days)

---

### EPIC-01 — Platform Foundation and Subscription Onboarding

> Establish the core infrastructure, data layer, API gateway, and subscription management capability. No capacity management features until this epic is complete.

| Story ID | Title | Priority | Size | Dependencies |
|---|---|---|---|---|
| E01-S01 | Provision AKS cluster (zone-redundant, 3-node pool across 3 AZs) with ACR and private networking | P0 | L | None |
| E01-S02 | Deploy Azure Cosmos DB (multi-region, zone-redundant) and create all entity containers with partition keys and indexes | P0 | M | E01-S01 |
| E01-S03 | Deploy Azure PostgreSQL Flexible Server (zone-redundant) with schema: utilization snapshots, operation audit, cost records | P0 | M | E01-S01 |
| E01-S04 | Deploy Azure Cache for Redis (zone-redundant, Premium) with connection pool and TTL policies per cache key type | P0 | S | E01-S01 |
| E01-S05 | Deploy Azure Service Bus (Premium, zone-redundant) with topics, subscriptions, and dead-letter queue configuration | P0 | S | E01-S01 |
| E01-S06 | Deploy Azure Key Vault (Premium, HSM-backed) with access policies for engine Managed Identities | P0 | S | E01-S01 |
| E01-S07 | Deploy Azure API Management (APIM, Standard v2) with Azure AD JWT validation policy and rate limiting policies | P0 | M | E01-S01 |
| E01-S08 | Implement Subscription Service: `POST /subscriptions` onboarding flow including resource provider registration validation and `Microsoft.Compute` check | P0 | M | E01-S02 |
| E01-S09 | Implement Subscription Service: `GET /subscriptions`, `GET /subscriptions/{id}`, `PATCH`, `DELETE` with offboarding guard (no active CRGs) | P0 | S | E01-S08 |
| E01-S10 | Implement Managed Identity provisioning automation: create per-subscription MI and assign required RBAC roles at correct scopes | P0 | M | E01-S08 |
| E01-S11 | Implement distributed saga framework: OperationRecord persistence, saga step executor, compensation chain, idempotency key enforcement | P0 | L | E01-S02, E01-S05 |
| E01-S12 | Implement ARM API client library: retry with exponential backoff and jitter, per-subscription rate limiter, circuit breaker, correlation ID propagation | P0 | M | None |
| E01-S13 | Implement structured logging (JSON) with correlation ID, OpenTelemetry tracing, and Azure Monitor / Application Insights integration | P0 | M | E01-S01 |
| E01-S14 | Implement `/health` (liveness + readiness) and `/metrics` (Prometheus format) endpoints on all services | P0 | S | E01-S13 |
| E01-S15 | Implement ACRME RBAC model: `Admin`, `Operator`, `DROperator`, `Reader`, `Consumer` roles enforced at API Gateway layer | P0 | M | E01-S07 |

---

### EPIC-02 — Capacity Reservation Lifecycle Management

> Implement full CRG and CR CRUD operations through the engine with quota pre-validation, ARM operation management, and state persistence.

| Story ID | Title | Priority | Size | Dependencies |
|---|---|---|---|---|
| E02-S01 | Implement Provisioning Service: `POST /crgs` — CRG creation with ARM PUT, async operation polling, Cosmos DB state persist | P0 | M | E01-S11, E01-S12 |
| E02-S02 | Implement Provisioning Service: `GET /crgs`, `GET /crgs/{id}`, `PATCH`, `DELETE` (with empty-CRG guard) | P0 | M | E02-S01 |
| E02-S03 | Implement CR creation: `POST /crgs/{id}/reservations` with quota pre-validation, ARM CR PUT, async polling, state persist | P0 | L | E02-S01, E03-S01 |
| E02-S04 | Implement CR quantity update: `PATCH /crgs/{id}/reservations/{cr_id}` with quota validation (increase) and floor guard (decrease) | P0 | M | E02-S03 |
| E02-S05 | Implement CR deletion: `DELETE /crgs/{id}/reservations/{cr_id}` with association check guard (reject if allocated > 0) | P0 | S | E02-S04 |
| E02-S06 | Implement CRG deletion: `DELETE /crgs/{id}` with cascade validation (all CRs empty and deleted) | P0 | S | E02-S05 |
| E02-S07 | Implement zero-size CR support: allow `quantity=0` at creation; document that no quota or capacity is consumed | P1 | S | E02-S03 |
| E02-S08 | Implement drift detection: `GET /crgs/{id}/drift` and `GET /crgs/{id}/reservations/{cr_id}` returning desired vs. actual state comparison | P1 | M | E05-S01 |
| E02-S09 | Implement force-reconcile: `POST /crgs/{id}/reconcile` triggering immediate ARM GET + compare + auto-remediate for a single CRG | P1 | M | E05-S01 |

---

### EPIC-03 — Quota Management

> Implement quota tracking, headroom calculation, alerting, and increase request workflow.

| Story ID | Title | Priority | Size | Dependencies |
|---|---|---|---|---|
| E03-S01 | Implement Quota Sync Worker: periodic ARM `Microsoft.Capacity/serviceLimits` GET for all tracked SKU families in all managed subscriptions; persist to QuotaRecord | P0 | M | E01-S08, E01-S12 |
| E03-S02 | Implement quota headroom calculation: `available_quota`, `committed_by_crs`, `deployment_headroom` derived fields refreshed on every sync | P0 | S | E03-S01 |
| E03-S03 | Implement quota pre-validation utility: shared library called by Provisioning Service and DR Orchestrator before any mutating ARM operation | P0 | S | E03-S02 |
| E03-S04 | Implement Quota API: `GET /quota`, `GET /quota/{sub_id}`, `GET /quota/{sub_id}/{region}/{sku_family}` with headroom included | P0 | S | E03-S02 |
| E03-S05 | Implement quota alert threshold monitoring: alert when `quota_used / quota_limit >= threshold_pct`; emit `QuotaThresholdBreached` event | P1 | S | E03-S01, E01-S05 |
| E03-S06 | Implement quota increase request: `POST /quota/{sub_id}/request` calling `Microsoft.Capacity/serviceLimits` PUT; persist request and poll for status | P1 | M | E03-S04 |
| E03-S07 | Implement quota increase request status: `GET /quota/{sub_id}/requests` and individual request status endpoint | P1 | S | E03-S06 |
| E03-S08 | Implement Consumer quota validation: check Consumer sub quota before returning placement recommendations or accepting sharing setup | P2 | M | E03-S03, E06-S01 |

---

### EPIC-04 — Capacity Reservation Sharing

> Implement the complete sharing lifecycle: RBAC orchestration, sharing profile management, zone-aware Consumer onboarding, and safe unsharing.

| Story ID | Title | Priority | Size | Dependencies |
|---|---|---|---|---|
| E04-S01 | Implement Sharing Orchestrator: `POST /crgs/{id}/consumers` — validate Consumer sub (registered, not at limit), create SharingRelationship in Pending | P0 | M | E01-S11, E02-S01 |
| E04-S02 | Implement RBAC Step 1: engine grants Provider Managed Identity `deploy/action` on Consumer subscription scope via ARM RBAC API | P0 | M | E04-S01 |
| E04-S03 | Implement RBAC Step 2: engine updates CRG `sharingProfile.subscriptionIds` via ARM PUT at `api-version=2024-03-01` | P0 | M | E04-S02 |
| E04-S04 | Implement RBAC Step 3: engine grants Consumer identity `read` + `deploy/action` on Provider CRG resource | P0 | M | E04-S03 |
| E04-S05 | Implement sharing setup status: `GET /crgs/{id}/consumers/{sub_id}/status` returning step-by-step RBAC completion state | P0 | S | E04-S04 |
| E04-S06 | Implement consumer removal (safe): `DELETE /crgs/{id}/consumers/{sub_id}` — check active VM count; reject if > 0 without force flag | P1 | M | E04-S05, E05-S01 |
| E04-S07 | Implement consumer removal (forced): support `?force=true` with operator acknowledgment capture; emit `ForcedUnsharingWithActiveVMs` audit event | P1 | M | E04-S06 |
| E04-S08 | Implement sharing drift detection: detect unauthorized entries in ARM `sharingProfile` not in engine desired state; emit `UnauthorizedConsumerDetected` | P1 | M | E05-S01 |
| E04-S09 | Implement 100-consumer limit enforcement: pre-check before any `POST /consumers` and return structured error with multi-CRG remediation guidance | P1 | S | E04-S01 |
| E04-S10 | `[Preview Dependency]` Implement sharing profile validation end-to-end: automated test against ARM API confirming `api-version=2024-03-01` sharing capability is active in target region | P1 | S | E04-S03 |

---

### EPIC-05 — Reconciliation Engine

> Implement the continuous desired-state/actual-state reconciliation loop for all managed entities.

| Story ID | Title | Priority | Size | Dependencies |
|---|---|---|---|---|
| E05-S01 | Implement Reconciliation Engine: scheduled loop (5 min) iterating all managed CRGs and CRs; GET ARM state; compare to Cosmos DB desired state | P0 | L | E02-S01, E01-S05 |
| E05-S02 | Implement drift recording: on delta detected, update `profile_drift` and `quantity_drift` fields; emit `DriftDetected` event to Service Bus | P0 | M | E05-S01 |
| E05-S03 | Implement auto-remediation: for sharing profile drift (missing or unauthorized Consumer) auto-remediate if within policy; route non-auto cases to alert | P1 | M | E05-S02 |
| E05-S04 | Implement ARM Event Processor: Service Bus consumer for Event Grid ARM events; on resource change event, trigger targeted reconcile for that CRG/CR | P1 | M | E01-S05 |
| E05-S05 | Implement reconciliation observability: metrics for `reconciliation_cycle_duration`, `drift_count`, `auto_remediation_count`, `unresolved_drift_count` | P1 | S | E05-S01, E01-S13 |
| E05-S06 | Implement overallocation detection: during reconciliation, flag any CR where `allocated > quantity`; emit `OverallocationDetected` event | P1 | S | E05-S01 |

---

### EPIC-06 — Availability Zone Management

> Implement zone mapping discovery, zone peer API integration, and zone-aware routing for all placement operations.

| Story ID | Title | Priority | Size | Dependencies |
|---|---|---|---|---|
| E06-S01 | Implement Zone Mapping Service: on subscription onboarding, call `list-locations` API and persist ZoneMappingRecord per subscription/region/zone | P0 | M | E01-S08 |
| E06-S02 | Implement Check Zone Peers API integration: call `Microsoft.Resources/checkZonePeers` for all managed sub pairs; persist cross-sub zone equivalence table | P0 | L | E06-S01 |
| E06-S03 | Implement zone mapping cache: load ZoneMappingRecords into Redis on startup and on refresh; all zone resolution calls hit cache first | P0 | S | E06-S01, E01-S04 |
| E06-S04 | Implement zone resolution API: `POST /zones/resolve` — given (provider_sub, region, provider_zone, consumer_sub) → return correct consumer logical zone | P0 | S | E06-S02 |
| E06-S05 | Implement zone mapping refresh worker: hourly ARM list-locations re-query + delta detection; on change, update ZoneMappingRecords and cache | P1 | M | E06-S01 |
| E06-S06 | Implement zone mismatch guard: integrate with Placement Engine to reject or correct consumer zone before placement recommendation is issued | P1 | M | E06-S04, E07-S01 |
| E06-S07 | Implement `Microsoft.Resources/AvailabilityZonePeering` feature registration check: validate feature is registered in all managed subs before Check Zone Peers API calls | P1 | S | E06-S02 |
| E06-S08 | `[Preview Dependency]` Implement Bicep `toLogicalZones()` function integration for IaC template generation used by DR failover automation | P3 | M | E06-S02 |

---

### EPIC-07 — Regional Placement Engine

> Implement the multi-constraint placement evaluation engine with policy-based ranking.

| Story ID | Title | Priority | Size | Dependencies |
|---|---|---|---|---|
| E07-S01 | Implement Placement Engine: `POST /placement/evaluate` — evaluate VM placement request against all constraints (zone, capacity, quota, cost, DR buffer) | P1 | XL | E03-S03, E06-S04 |
| E07-S02 | Implement placement constraint: zone physical alignment (consumer zone must map to same physical zone as target CR) | P1 | S | E07-S01, E06-S04 |
| E07-S03 | Implement placement constraint: CR capacity headroom check (`quantity - allocated >= requested_count`) | P1 | S | E07-S01 |
| E07-S04 | Implement placement constraint: consumer quota headroom check | P1 | S | E07-S01, E03-S08 |
| E07-S05 | Implement placement constraint: DR buffer compliance (primary CR must retain DR buffer after placement) | P1 | M | E07-S01, E08-S01 |
| E07-S06 | Implement placement constraint: SKU availability per region/zone using `Microsoft.Compute/skus` GET | P2 | M | E07-S01 |
| E07-S07 | Implement placement policy CRUD: `GET/POST /placement/policies` — structured policy document storage and retrieval | P1 | M | E01-S02 |
| E07-S08 | Implement placement ranking: multi-objective scoring (cost-first, availability-first, DR-buffer-first) based on active policy | P2 | M | E07-S01 |
| E07-S09 | Implement single-zone concentration warning: detect placement requests that create all-in-one-physical-zone dependency | P2 | S | E07-S01 |

---

### EPIC-08 — Disaster Recovery Orchestration

> Implement DR pair management, pre-positioning validation, failover trigger with approval gate, and failback reconciliation.

| Story ID | Title | Priority | Size | Dependencies |
|---|---|---|---|---|
| E08-S01 | Implement DR pair CRUD: `POST/GET /dr/pairs` — persist DRCapacityPair; link primary and DR CRGs; validate both CRGs managed by engine | P1 | M | E02-S01 |
| E08-S02 | Implement DR buffer validation: calculate `dr_cr.quantity >= primary_cr.quantity × dr_buffer_pct`; alert on violation | P1 | M | E08-S01 |
| E08-S03 | Implement DR health monitor worker: daily validation of all DR pairs — buffer compliance, sharing profile active, zone mapping current, DR CRG allocated=0 | P1 | M | E08-S01, E04-S05 |
| E08-S04 | Implement failover trigger: `POST /dr/pairs/{id}/failover` — quota pre-check, approval gate, saga: validate DR capacity → deploy DR VMs → record event | P1 | XL | E08-S01, E03-S03, E04-S05 |
| E08-S05 | Implement failover approval gate: two-step approval (request + confirm) with configurable approval timeout and operator identity capture | P1 | M | E08-S04 |
| E08-S06 | Implement bulk VM deployment for failover: ARM template-based deployment of pre-defined VM configurations against DR CRG | P1 | L | E08-S04 |
| E08-S07 | Implement failback trigger: `POST /dr/pairs/{id}/failback` — deallocation of DR VMs → primary CRG restoration → DR pair returns to Standby | P1 | L | E08-S04 |
| E08-S08 | Implement DR event history: `GET /dr/pairs/{id}/events` returning all failover and failback events with metadata | P1 | S | E08-S04 |
| E08-S09 | Implement DR readiness API: `GET /dr/health` returning all pairs with Standby/FailoverActive/Degraded status | P1 | S | E08-S03 |
| E08-S10 | Implement VMSS zone outage monitoring: detect VMSS instances associated with shared CRGs; tag with `[Preview Risk]` flag; alert during zone outage signals | P2 | M | E05-S04 |

---

### EPIC-09 — Capacity Forecasting

> Implement time-series analysis, demand forecasting, and automated recommendation workflow.

| Story ID | Title | Priority | Size | Dependencies |
|---|---|---|---|---|
| E09-S01 | Implement Utilization Snapshot Worker: every 6 hours, record `(cr_id, timestamp, quantity, allocated)` to PostgreSQL time-series table | P1 | S | E02-S03 |
| E09-S02 | Implement Forecast Worker: daily job generating 30/60/90-day demand forecasts for all CRs using moving average; store as CapacityForecast records | P2 | L | E09-S01 |
| E09-S03 | Implement forecast recommendation generation: from peak forecast demand, compute `recommended_quantity = peak × (1 + buffer_pct) + dr_buffer` | P2 | M | E09-S02 |
| E09-S04 | Implement forecast approval workflow: `POST /forecasts/{cr_id}/approve` triggers CR quantity update via Provisioning Service | P2 | M | E09-S03, E02-S04 |
| E09-S05 | Implement forecast API: `GET /forecasts`, `GET /forecasts/{cr_id}` returning current forecast series and recommendation | P2 | S | E09-S03 |
| E09-S06 | Implement quota approach alert: from forecast, project date when quota limit will be reached; alert at 14-day lead time | P2 | M | E09-S02, E03-S05 |
| E09-S07 | Upgrade forecast model from moving average to ARIMA or ML-based model; A/B test against moving average baseline | P3 | XL | E09-S02 |

---

### EPIC-10 — Cost Optimization

> Implement utilization monitoring, idle CR detection, chargeback attribution, and right-sizing recommendations.

| Story ID | Title | Priority | Size | Dependencies |
|---|---|---|---|---|
| E10-S01 | Implement Cost Report Worker: daily job scanning all CRs for idle state (`allocated=0` for ≥ threshold days) and underutilization (`allocated/quantity < threshold`) | P1 | M | E09-S01 |
| E10-S02 | Implement idle CR alert: `IdleCRDetected` event → notification to operator with idle duration and estimated monthly cost savings from deletion | P1 | S | E10-S01 |
| E10-S03 | Implement right-sizing recommendation: from underutilization data, suggest `new_quantity = avg_allocated × (1 + buffer_pct) + dr_buffer`; show cost delta | P2 | M | E10-S01, E08-S02 |
| E10-S04 | Implement chargeback attribution: for each Consumer in a sharing relationship, calculate average `allocated_by_consumer / total_quantity` ratio; attribute proportional reservation cost | P2 | L | E09-S01 |
| E10-S05 | Implement Cost Management API integration: pull actual billing data per subscription; match to CRG/CR resource IDs; compare actuals vs. engine estimates | P2 | M | E01-S12 |
| E10-S06 | Implement cost API: `GET /cost/summary`, `GET /cost/idle`, `GET /cost/underutilized`, `GET /cost/chargeback/{period}` | P2 | M | E10-S03, E10-S04 |

---

### EPIC-11 — Observability and Operations

> Implement comprehensive monitoring, alerting, dashboards, and operational tooling.

| Story ID | Title | Priority | Size | Dependencies |
|---|---|---|---|---|
| E11-S01 | Implement Azure Monitor alert rules: quota threshold, overallocation, DR buffer violation, idle CR, sharing unauthorized consumer | P1 | M | E03-S05, E05-S06, E08-S02 |
| E11-S02 | Deploy Azure Managed Grafana with dashboards: CR utilization heatmap, quota consumption trend, sharing relationship map, DR readiness status, cost summary | P1 | L | E01-S13, E09-S01 |
| E11-S03 | Implement notification service: route engine events to ITSM/ServiceNow (ticket creation), PagerDuty (critical alerts), email/Teams (advisory) | P2 | M | E01-S05 |
| E11-S04 | Implement audit log API: `GET /audit` with filters (resource, operation type, operator, time range), pagination, and 90-day retention | P1 | M | E01-S02 |
| E11-S05 | Implement Azure Sentinel integration: stream security audit events (auth failures, unauthorized consumers, forced operations) to Sentinel workspace | P2 | M | E11-S01 |
| E11-S06 | Implement SLA reporting: uptime calculation, P95 API latency by endpoint, reconciliation cycle duration trend | P2 | M | E11-S02 |

---

### EPIC-12 — Security Hardening and Compliance

> Harden the engine for production use — secret rotation, network isolation, policy integration, and compliance tooling.

| Story ID | Title | Priority | Size | Dependencies |
|---|---|---|---|---|
| E12-S01 | Implement Private Endpoints for all PaaS services (Cosmos DB, PostgreSQL, Redis, Service Bus, Key Vault, ACR) with VNet integration | P0 | L | E01-S01 |
| E12-S02 | Implement Azure Firewall egress rules: allow management.azure.com, login.microsoftonline.com, graph.microsoft.com; deny all else | P0 | M | E12-S01 |
| E12-S03 | Implement Key Vault secret rotation: 90-day automated certificate rotation for all SPN credentials; hot reload in engine at runtime | P1 | M | E01-S06 |
| E12-S04 | Implement Azure Policy initiative: enforce required tags on engine-managed CRG resources; deny CRG creation outside approved resource groups | P2 | M | None |
| E12-S05 | Implement compliance export: generate SOC 2 / ISO 27001 evidence package from audit log (access records, change records, security events) for defined period | P3 | L | E11-S04 |

---

### Backlog Summary Statistics

| Epic | Stories | P0 | P1 | P2 | P3 | MVP (P0+P1) |
|---|---|---|---|---|---|---|
| EPIC-01 Foundation | 15 | 15 | 0 | 0 | 0 | ✅ 15 |
| EPIC-02 CR Lifecycle | 9 | 6 | 3 | 0 | 0 | ✅ 9 |
| EPIC-03 Quota | 8 | 4 | 3 | 1 | 0 | ✅ 7 |
| EPIC-04 Sharing | 10 | 5 | 5 | 0 | 0 | ✅ 10 |
| EPIC-05 Reconciliation | 6 | 2 | 4 | 0 | 0 | ✅ 6 |
| EPIC-06 Zone Management | 8 | 4 | 3 | 0 | 1 | ✅ 7 |
| EPIC-07 Placement | 9 | 0 | 5 | 4 | 0 | 5 |
| EPIC-08 DR Orchestration | 10 | 0 | 9 | 1 | 0 | 9 |
| EPIC-09 Forecasting | 7 | 0 | 1 | 5 | 1 | 1 |
| EPIC-10 Cost Optimization | 6 | 0 | 2 | 4 | 0 | 2 |
| EPIC-11 Observability | 6 | 0 | 3 | 3 | 0 | 3 |
| EPIC-12 Security | 5 | 2 | 1 | 1 | 1 | 3 |
| **Total** | **99** | **38** | **39** | **19** | **3** | **77 MVP stories** |

### MVP Definition

**MVP = EPIC-01 through EPIC-06 (all stories) + EPIC-07 (P1) + EPIC-08 (P1) + EPIC-09 (E09-S01) + EPIC-10 (P1) + EPIC-11 (P1) + EPIC-12 (P0+P1)**

MVP delivers: Subscription onboarding, full CR lifecycle, quota management, sharing lifecycle with RBAC orchestration, reconciliation engine, zone management, placement engine core, DR failover, utilization snapshots, idle CR detection, monitoring/alerting, and security foundation.

Post-MVP delivers: Advanced forecasting (ARIMA/ML), chargeback attribution, full cost reporting, compliance exports, VMSS zone outage monitoring.

---

*End of Azure Capacity Reservation Management Engine — Design Requirements Specification*  
*Version 1.0 — Draft for Engineering Review*  
*Classification: Principal Cloud Architect*
