# ACRME — Requirements Traceability & Design Review
## Pre-Engineering Gate Assessment

**Classification:** Principal Cloud Architect — Design Gate Review  
**Version:** 1.0 — Pre-POC Scripting Gate  
**Date:** August 2026  
**Source Documents:**  
- `azure_cr_management_engine_design.md` v1.0 (original engine design — 1,662 lines, FR/NF source of record)  
- `multi_region_placement_design.md` v1.0 Pass 3 (final design — 1,612 lines, architecture deliverable)  
- `design_change_summary.md` (gap tracking — Pass 1 through Pass 3 complete)  
- `azure_cr_poc_test_workbook.md` (POC-01 through POC-33)  
**Review Scope:** Requirements completeness, gap identification, document consolidation decision  

> **Gate Purpose:** This review is the final gate before POC test scripting begins. Engineering implementation does not start until this review is signed off and all Critical/High blockers are resolved or accepted as risks.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Functional Requirements Traceability Matrix](#2-functional-requirements-traceability-matrix)
3. [Non-Functional Requirements Traceability Matrix](#3-non-functional-requirements-traceability-matrix)
4. [Placement-Specific Requirements Traceability](#4-placement-specific-requirements-traceability)
5. [Outstanding Gaps — Beyond Blockers B-1 through B-7](#5-outstanding-gaps)
6. [Blockers Registry](#6-blockers-registry)
7. [Document Consolidation Recommendation](#7-document-consolidation-recommendation)
8. [Summary Coverage Statistics](#8-summary-coverage-statistics)
9. [Decision Log](#9-decision-log)

---

## 1. Executive Summary

### 1.1 Review Outcome

The requirements traceability review of the **Azure Capacity Reservation Management Engine (ACRME)** design against both the original Design Requirements Specification (`azure_cr_management_engine_design.md`) and the final architecture document (`multi_region_placement_design.md`) finds the design is **substantially complete and ready for POC test planning**, with the following qualification:

- **49 of 49 functional requirement sub-items** (FR-1.1 through FR-8.6) have design coverage — either in the original engineering backlog (EPIC-01 through EPIC-12) or the extended placement and lifecycle design (Pass 3).
- **27 of 29 NFR sub-items** are covered. Two areas (NFR-3 scalability testing, NFR-7.1 sovereign cloud) have no dedicated backlog story and are flagged as gaps.
- **2 of 2 Critical blockers** (B-1, B-2) are POC-gated — no engineering can proceed on the Two-Group Quota Architecture or Tier 2 Emergency Transfer until POC-30 and POC-31 are executed and pass.
- **9 new pending items** (G-16 through G-24) are identified in this review beyond the known gap table (G-7, G-13 partial, G-14, G-15).
- **Document consolidation:** Recommended — create a single **Master Consolidated Design Document** with all diagrams embedded, while retaining the two working documents as engineering references.

### 1.2 Coverage Summary

| Category | Requirements | Fully Covered | Partially Covered | Not Covered |
|---|---|---|---|---|
| Functional (FR-1 through FR-8) | 49 sub-items | **48** | **1** (FR-7.5) | 0 |
| Non-Functional (NFR-1 through NFR-7) | 29 sub-items | **24** | **3** | **2** |
| Placement Functional (R1–R8) | 8 | **8** | 0 | 0 |
| Placement Non-Functional (NFR-R1–R3) | 3 | **3** | 0 | 0 |
| **Total** | **89** | **83** | **4** | **2** |

### 1.3 Design Maturity Assessment

| Design Area | Maturity | Gate Status |
|---|---|---|
| CR/CRG Lifecycle (FR-1) | ✅ Architecture Complete | Ready for POC |
| Sharing Management (FR-2) | ✅ Architecture Complete | Ready for POC — Preview dependency |
| Zone Mapping (FR-3) | ✅ Architecture Complete | Ready for POC |
| Quota Management (FR-4) | ✅ Architecture Complete — extended by Quota Groups | Blocked — POC-30 required |
| DR Failover (FR-5) | ✅ Architecture Complete | Blocked — G-15 (engine_mode) |
| Regional Placement (FR-6) | ✅ Architecture Complete — Pass 3 | Ready for POC |
| Capacity Forecasting (FR-7) | 🔶 Substantially Complete — FR-7.5 gap | G-16 to resolve |
| Cost Optimization (FR-8) | ✅ Architecture Complete | Ready for POC |
| Emergency Transfer | ✅ Tier 1/2/3 model complete — G-14 open | Blocked — G-14 for Tier 3 |
| Steady State Lifecycle | ✅ Architecture Complete | Ready for POC |

---

## 2. Functional Requirements Traceability Matrix

### Coverage Legend
- ✅ **COVERED** — Explicit backlog story, API endpoint, and/or data model entity present
- 🔶 **PARTIALLY COVERED** — Concept present but implementation detail incomplete
- ❌ **NOT COVERED** — No design artifact addresses this requirement
- 🔴 **BLOCKED** — Covered in design but execution blocked by external dependency

---

### FR-1 — Capacity Reservation Lifecycle Management

| Req ID | Requirement Summary | Coverage | Design Location | Gap / Notes |
|---|---|---|---|---|
| FR-1.1 | CRG CRUD via Azure Compute REST API `2024-03-01` | ✅ COVERED | E02-S01, E02-S02; API `POST/GET/PATCH/DELETE /crgs`; ARM API table (Section 5.2) | None |
| FR-1.2 | CR CRUD with quantity modification without VM disruption | ✅ COVERED | E02-S03, E02-S04; `PATCH /crgs/{id}/reservations/{cr_id}` | None |
| FR-1.3 | Zero-size reservation pattern (`quantity=0`) | ✅ COVERED | E02-S07 (P1); CapacityReservation.desired_quantity allows 0 | P1 — deferred to post-MVP critical path |
| FR-1.4 | Track `allocated` vs `quantity` independently; overallocation alert | ✅ COVERED | CapacityReservation data model (`allocated_count`, `is_overallocated`); E05-S06; `GET .../utilization` API | None |
| FR-1.5 | CR deletion sequencing — disassociate VMs → delete CRs → delete CRG | ✅ COVERED | E02-S05, E02-S06; cascade validation guard | None |
| FR-1.6 | CR quantity reduction with floor constraint (`qty ≥ allocated`) | ✅ COVERED | E02-S04; floor guard in Provisioning Service | None |

**FR-1 Verdict: ✅ FULLY COVERED (6/6)**

---

### FR-2 — Capacity Reservation Sharing Management

| Req ID | Requirement Summary | Coverage | Design Location | Gap / Notes |
|---|---|---|---|---|
| FR-2.1 | Manage `sharingProfile.subscriptionIds` — add, remove, list | ✅ COVERED | E04-S01, E04-S03; `POST/GET/DELETE /crgs/{id}/consumers` | Preview dependency — `api-version=2024-03-01` |
| FR-2.2 | Three-step RBAC orchestration for Provider-Consumer setup | ✅ COVERED | E04-S02, E04-S03, E04-S04; SharingRelationship entity (`rbac_step1/2/3_complete`) | Preview dependency |
| FR-2.3 | 100 Consumer subscription limit enforcement | ✅ COVERED | E04-S09; pre-check in `POST /consumers` | None |
| FR-2.4 | Microsoft.Compute registration validation before sharing setup | ✅ COVERED | E01-S08 (resource provider validation on subscription onboarding) | None |
| FR-2.5 | Safe unsharing — active VM check before Consumer removal | ✅ COVERED | E04-S06; `DELETE /crgs/{id}/consumers/{sub_id}` with active VM guard | None |
| FR-2.6 | Force-unsharing warning with silent hazard documentation | ✅ COVERED | E04-S07; `ForcedUnsharingWithActiveVMs` audit event | None |
| FR-2.7 | Historical sharing profile record with timestamps | ✅ COVERED | SharingRelationship entity (`created_at`, `removed_at`, `removed_by`) | None |

**FR-2 Verdict: ✅ FULLY COVERED (7/7)** — All 7 items covered. Preview dependency acknowledged.

---

### FR-3 — Availability Zone Mapping Management

| Req ID | Requirement Summary | Coverage | Design Location | Gap / Notes |
|---|---|---|---|---|
| FR-3.1 | Discover and store logical-to-physical zone mapping via `list-locations` API | ✅ COVERED | E06-S01; ZoneMappingRecord entity | None |
| FR-3.2 | Use Check Zone Peers API for cross-subscription zone equivalence | ✅ COVERED | E06-S02; `Microsoft.Resources/checkZonePeers` in ARM API table | None |
| FR-3.3 | Zone mapping registry keyed by `(provider_sub, region, provider_zone)` → Consumer zones | ✅ COVERED | ZoneMappingRecord data model; E06-S03 (Redis cache); dual index structure | None |
| FR-3.4 | Automatic Consumer zone resolution for VM deployment requests | ✅ COVERED | E06-S04; `POST /zones/resolve` API | None |
| FR-3.5 | Reject VM deployments where Consumer zone mismatches physical zone | ✅ COVERED | E06-S06 (zone mismatch guard in Placement Engine) | None |
| FR-3.6 | Configurable zone mapping refresh schedule + refresh on new subscription | ✅ COVERED | E06-S05 (hourly refresh worker); E06-S01 (refresh on onboarding event) | None |

**FR-3 Verdict: ✅ FULLY COVERED (6/6)**

---

### FR-4 — Quota Management

| Req ID | Requirement Summary | Coverage | Design Location | Gap / Notes |
|---|---|---|---|---|
| FR-4.1 | Query and store quota (`currentValue`, `limit`) for all tracked SKUs | ✅ COVERED | E03-S01; QuotaRecord entity; `Microsoft.Capacity/serviceLimits` GET | None |
| FR-4.2 | Derived quota metrics: available, committed, deployment headroom, overcommit flag | ✅ COVERED | E03-S02; QuotaRecord fields; Extended by Quota Group fields in RegionalSnapshot | None |
| FR-4.3 | Pre-validation before CR creation — block on quota exhaustion | ✅ COVERED | E03-S03 (shared pre-validation utility); E02-S03 calls it | None |
| FR-4.4 | Initiate quota increase via `Microsoft.Capacity/serviceLimits` PUT | ✅ COVERED | E03-S06, E03-S07; `POST /quota/{sub_id}/request` | B-5: endpoint correctness unvalidated — POC-33 required |
| FR-4.5 | Consumer quota tracking — warn on insufficient Consumer quota | ✅ COVERED | E03-S08 (P2); Consumer quota check in Placement Engine | P2 priority — post-MVP |
| FR-4.6 | Unified quota dashboard across all managed subscriptions | ✅ COVERED | E03-S04 (`GET /quota`); E11-S02 (Grafana dashboard); NFR-6.2 metrics | None |

**FR-4 Verdict: ✅ FULLY COVERED (6/6)** — B-5 and POC-33 gate the quota increase API correctness.

---

### FR-5 — Disaster Recovery Failover Management

| Req ID | Requirement Summary | Coverage | Design Location | Gap / Notes |
|---|---|---|---|---|
| FR-5.1 | DR capacity pair definition `(primary_crg, dr_crg)` | ✅ COVERED | E08-S01; DRCapacityPair entity; `POST/GET /dr/pairs` | None |
| FR-5.2 | DR sharing profiles and RBAC pre-positioned (not on-demand) | ✅ COVERED | E08-S03 (DR health monitor validates sharing active); E04-S04 (RBAC Step 3) | None |
| FR-5.3 | Failover trigger — validate DR capacity, deploy VMs, record metadata | ✅ COVERED | E08-S04, E08-S05, E08-S06; `POST /dr/pairs/{id}/failover`; OperationRecord | B-3: engine_mode declaration mechanism not designed (G-15) |
| FR-5.4 | Failback trigger — deallocate DR VMs, restore primary, record metadata | ✅ COVERED | E08-S07; `POST /dr/pairs/{id}/failback` | None |
| FR-5.5 | DR CRG utilization monitoring — alert if `allocated > 0` in steady state | ✅ COVERED | E08-S03 (daily `allocated=0` validation); DRCapacityPair.dr_status | None |
| FR-5.6 | DR capacity buffer enforcement — configurable per DR pair, alert on violation | ✅ COVERED | E08-S02; HC-6 (DR_COVERAGE_FLOOR); `dr_crg_coverage_ratio` in RegionalSnapshot | None |
| FR-5.7 | Cross-region DR pair definitions with independent CRGs per region | ✅ COVERED | DRCapacityPair.primary_region + dr_region; per-region CRG model | None |

**FR-5 Verdict: ✅ FULLY COVERED (7/7)** — B-3 (G-15) gates the failover trigger path.

---

### FR-6 — Regional Placement Decisions

| Req ID | Requirement Summary | Coverage | Design Location | Gap / Notes |
|---|---|---|---|---|
| FR-6.1 | Multi-constraint evaluation: zone alignment, CR headroom, quota, SKU availability, cost, DR buffer | ✅ COVERED | E07-S01 through E07-S06; HC-1 through HC-7 in `multi_region_placement_design.md` | None |
| FR-6.2 | Ranked placement options ordered by configurable policy | ✅ COVERED | E07-S08; PS_Prod/PS_NonProd/PS_DR formulas; `POST /placement/evaluate` | None |
| FR-6.3 | Placement policies as code — structured policy DAG | ✅ COVERED | E07-S07; PlacementPolicy entity with `rules` JSON array | None |
| FR-6.4 | Single-zone dependency detection and warning | ✅ COVERED | E07-S09 (P2); `PlacementPolicy.max_single_zone_pct` | P2 — post-MVP |
| FR-6.5 | SKU availability via `Microsoft.Compute/skus` GET | ✅ COVERED | E07-S06 (P2); ARM API table entry | P2 — post-MVP |

**FR-6 Verdict: ✅ FULLY COVERED (5/5)** — Two items at P2 priority.

---

### FR-7 — Capacity Forecasting

| Req ID | Requirement Summary | Coverage | Design Location | Gap / Notes |
|---|---|---|---|---|
| FR-7.1 | Historical pattern analysis → demand forecasts (30/60/90 day) | ✅ COVERED | E09-S01, E09-S02; CapacityForecast entity | None |
| FR-7.2 | Quantity increase/decrease recommendations from forecast | ✅ COVERED | E09-S03; `recommendation_status` in CapacityForecast | None |
| FR-7.3 | Buffer formula: `recommended_qty = peak × (1+buffer_pct) + dr_buffer` | ✅ COVERED | E09-S03; formula explicitly stated in both documents | None |
| FR-7.4 | Quota approach alert with 14-day lead time | ✅ COVERED | E09-S06; configurable threshold (default 80%) | None |
| FR-7.5 | Workload tagging — per-workload capacity forecasts | 🔶 PARTIALLY COVERED | `tags` field on CRG entity; no dedicated backlog story for per-workload forecasting | **G-16: No story for workload-tagged forecast — Medium priority** |
| FR-7.6 | Raw forecast API for external tools | ✅ COVERED | E09-S05; `GET /forecasts`, `GET /forecasts/{cr_id}` | None |

**FR-7 Verdict: 🔶 SUBSTANTIALLY COVERED (5/6)** — FR-7.5 has a structural gap (no backlog story).

---

### FR-8 — Cost Optimization

| Req ID | Requirement Summary | Coverage | Design Location | Gap / Notes |
|---|---|---|---|---|
| FR-8.1 | Utilization monitoring — flag CRs below threshold for sustained period | ✅ COVERED | E10-S01; default 60% threshold / 7-day window | None |
| FR-8.2 | Daily/monthly cost of unused capacity per CR, CRG, subscription, workload | ✅ COVERED | E10-S01, E10-S06; cost API surface | None |
| FR-8.3 | Right-sizing recommendations with cost delta and DR risk assessment | ✅ COVERED | E10-S03; considers DR buffer proximity | None |
| FR-8.4 | Chargeback and showback reporting by Consumer workload | ✅ COVERED | E10-S04; average utilization ratio attribution | None |
| FR-8.5 | Idle CR detection and deletion alerts | ✅ COVERED | E10-S02; `IdleCRDetected` event | None |
| FR-8.6 | Cost Management API integration — validate engine estimates vs. billing actuals | ✅ COVERED | E10-S05; `Microsoft.CostManagement/query` in ARM API table | None |

**FR-8 Verdict: ✅ FULLY COVERED (6/6)**

---

## 3. Non-Functional Requirements Traceability Matrix

### NFR-1 — Availability

| Req ID | Requirement Summary | Coverage | Design Location | Gap / Notes |
|---|---|---|---|---|
| NFR-1.1 | 99.9% availability target (≤ 8.7 h downtime/year) | 🔶 PARTIALLY COVERED | E11-S06 (SLA reporting); no uptime SLA enforcement mechanism defined | No story for SLA budget tracking or error budget policy |
| NFR-1.2 | Multi-AZ deployment across ≥ 2 AZs | ✅ COVERED | E01-S01 (AKS 3-node pool across 3 AZs) | None |
| NFR-1.3 | Zone-redundant storage + cross-region replication for DR | ✅ COVERED | E01-S02 (Cosmos DB zone-redundant), E01-S03 (PostgreSQL zone-redundant) | None |
| NFR-1.4 | Circuit breakers on all outbound ARM API calls | ✅ COVERED | E01-S12 (ARM API client library with circuit breaker) | None |

**NFR-1 Verdict: ✅ COVERED (3/4 fully; 1 partial)** — NFR-1.1 monitoring exists but no enforcement mechanism.

---

### NFR-2 — Performance

| Req ID | Requirement Summary | Coverage | Design Location | Gap / Notes |
|---|---|---|---|---|
| NFR-2.1 | Read API ≤ 500ms P95 | ✅ COVERED | Redis cache architecture; consistent with NFR-R1 in placement design | No load testing story — verify during performance testing phase |
| NFR-2.2 | Write API accepted within 2s; async ARM tracking | ✅ COVERED | E01-S11 (saga framework with async polling) | None |
| NFR-2.3 | Reconciliation cycle ≤ 5 min for ≤ 500 CRGs | ✅ COVERED | E05-S01 (5-min loop); E05-S05 (cycle duration metric) | None |
| NFR-2.4 | Forecast computation ≤ 10 min (background job) | ✅ COVERED | E09-S02 (daily background job — size M) | None |
| NFR-2.5 | ≥ 200 concurrent API clients without degradation | 🔶 PARTIALLY COVERED | APIM rate limiting in E01-S07; no explicit load testing or autoscale story | No NFT (non-functional testing) story in backlog |

**NFR-2 Verdict: ✅ COVERED (4/5 fully; 1 partial)** — NFR-2.5 needs explicit load testing backlog item.

---

### NFR-3 — Scalability

| Req ID | Requirement Summary | Coverage | Design Location | Gap / Notes |
|---|---|---|---|---|
| NFR-3.1 | Scale to 100 Provider subs / 10,000 Consumer relationships | ❌ NOT COVERED | Architecture supports it (AKS horizontal scaling) but no dedicated story, load test, or HPA config | **G-17: No scalability testing story** |
| NFR-3.2 | 5,000 CRGs / 50,000 CRs / 500,000 VM associations | ❌ NOT COVERED | Cosmos DB partition keys are correct; no capacity test against these targets | **G-17: No capacity test story** |
| NFR-3.3 | Independent scalability of reconciliation and forecasting | 🔶 PARTIALLY COVERED | E01-S01 implies separate worker pools; no autoscaling policy or story | **G-17: No autoscale policy defined** |

**NFR-3 Verdict: ❌ NOT COVERED (0/3 fully; 1 partial)** — **G-17 required.** Largest NFR gap in the design.

---

### NFR-4 — Reliability

| Req ID | Requirement Summary | Coverage | Design Location | Gap / Notes |
|---|---|---|---|---|
| NFR-4.1 | All state-mutating operations are idempotent | ✅ COVERED | E01-S11 (idempotency key in saga framework) | None |
| NFR-4.2 | Exponential backoff with jitter, max 5 retries, dead-letter state | ✅ COVERED | E01-S12 (ARM API client); E01-S05 (dead-letter queue) | None |
| NFR-4.3 | Drift detection within 2 reconciliation cycles | ✅ COVERED | E05-S01, E05-S02; `DriftDetected` event on delta | None |
| NFR-4.4 | Operation audit log ≥ 90-day retention | ✅ COVERED | E11-S04 (audit log API with 90-day retention) | None |

**NFR-4 Verdict: ✅ FULLY COVERED (4/4)**

---

### NFR-5 — Security

| Req ID | Requirement Summary | Coverage | Design Location | Gap / Notes |
|---|---|---|---|---|
| NFR-5.1 | TLS 1.2 minimum in transit | ✅ COVERED | E12-S01 (private endpoints); E12-S02 (firewall egress control) | None |
| NFR-5.2 | All secrets in Key Vault; none in config files | ✅ COVERED | E01-S06 (Key Vault deployment); E12-S03 (90-day cert rotation) | None |
| NFR-5.3 | Managed Identity for on-Azure; SPN + cert for cross-sub | ✅ COVERED | E01-S10 (MI provisioning automation) | None |
| NFR-5.4 | Azure AD Bearer token auth on API surface | ✅ COVERED | E01-S07 (APIM JWT validation policy) | None |
| NFR-5.5 | Engine-level RBAC: `Admin`, `Operator`, `DROperator`, `Reader`, `Consumer` | ✅ COVERED | E01-S15; PlacementPolicy WAF assessment (Reader/Operator role check) | None |
| NFR-5.6 | Security event logging — auth failures, authorization denials, privilege escalations | ✅ COVERED | E11-S05 (Azure Sentinel integration); `ForcedUnsharingWithActiveVMs` audit event | None |

**NFR-5 Verdict: ✅ FULLY COVERED (6/6)**

---

### NFR-6 — Observability

| Req ID | Requirement Summary | Coverage | Design Location | Gap / Notes |
|---|---|---|---|---|
| NFR-6.1 | Structured JSON logs with correlation ID, sub ID, resource ID, duration, outcome | ✅ COVERED | E01-S13 (structured logging + OpenTelemetry) | None |
| NFR-6.2 | Azure Monitor metrics: API rate, error rate, reconciliation duration, ARM latency, quota, CR utilization, DR buffer compliance | ✅ COVERED | E01-S13; E11-S02 (Grafana dashboards); E05-S05 (reconciliation metrics) | None |
| NFR-6.3 | OpenTelemetry distributed tracing across all services and ARM calls | ✅ COVERED | E01-S13 | None |
| NFR-6.4 | `/health` and `/metrics` Prometheus endpoints | ✅ COVERED | E01-S14 (all services) | None |

**NFR-6 Verdict: ✅ FULLY COVERED (4/4)**

---

### NFR-7 — Compliance and Governance

| Req ID | Requirement Summary | Coverage | Design Location | Gap / Notes |
|---|---|---|---|---|
| NFR-7.1 | Deployable in Azure sovereign clouds (Government, China) | ❌ NOT COVERED | No backlog story; no API compatibility check for sovereign endpoints | **G-18: Sovereign cloud story required (P3)** |
| NFR-7.2 | All data remains within designated Azure region pair; no external transmission | 🔶 PARTIALLY COVERED | Zone-redundant Cosmos DB and PostgreSQL infer regional containment; no explicit data residency enforcement story or network egress audit | **G-19: Data residency enforcement story (P2)** |
| NFR-7.3 | Azure Policy integration for placement and sharing decisions | ✅ COVERED | E12-S04 (Azure Policy initiative); PlacementPolicy WAF assessment | None |

**NFR-7 Verdict: 🔶 PARTIALLY COVERED (1/3 fully; 1 partial; 1 not covered)**

---

## 4. Placement-Specific Requirements Traceability

*(Source: `multi_region_placement_design.md` — Requirements section)*

### Functional (R1–R8)

| Req ID | Requirement | Coverage | Design Location | Notes |
|---|---|---|---|---|
| R1 | Customer selects Prod region | ✅ COVERED | Selection algorithm Step 1; PS_Prod validation | None |
| R2 | Engine selects NonProd and DR automatically; NonProd and DR may share region | ✅ COVERED | D8 (HC-1 updated); selection algorithm Steps 2-3 | None |
| R3 | 3 regions: all three used, one per environment | ✅ COVERED | 3-region example (Example A) | None |
| R4 | 4 regions: engine selects optimal 2 from remaining 3 | ✅ COVERED | 4-region example (Example B); sequential algorithm | None |
| R5 | Selection weighted against live CR/CRG capacity | ✅ COVERED | RegionalSnapshot per-CRG-type fields (Pass 2, D9) | None |
| R6 | Quota headroom, zone diversity, DR buffer in selection | ✅ COVERED | HC-3 (quota), HC-5 (zone), HC-6 (DR floor) | None |
| R7 | Configurable formula via PlacementPolicy | ✅ COVERED | PlacementPolicy.rules; weights α–ε stored and configurable | None |
| R8 | Region exhaustion detection and handling | ✅ COVERED | `RegionExhaustedError`; `CapacityExhaustedAlert`; pending queue | None |

**R1–R8 Verdict: ✅ FULLY COVERED (8/8)**

### Non-Functional (NFR-R1–R3)

| Req ID | Requirement | Coverage | Design Location | Notes |
|---|---|---|---|---|
| NFR-R1 | Selection ≤ 500ms | ✅ COVERED | Redis snapshot cache; O(R×C) sub-millisecond on cache | None |
| NFR-R2 | Regional state ≤ 5 min old | ✅ COVERED | 5-min reconciliation cycle; 10-min fallback to Cosmos DB | None |
| NFR-R3 | Deterministic from same snapshot | ✅ COVERED | Jitter logged in OperationRecord; formula is pure function of snapshot | None |

**NFR-R1–R3 Verdict: ✅ FULLY COVERED (3/3)**

---

## 5. Outstanding Gaps

This section identifies all open items **beyond the seven active blockers (B-1 through B-7)** already known.

### 5.1 Carried from Pass 3 Gap Table

These items were identified in prior passes and remain unresolved.

| Gap ID | Category | Description | Priority | Action Required |
|---|---|---|---|---|
| G-7 | Design | Worked examples reference superseded formula (`PS(r,E)`); no worked example with per-CRG-type state and D9 formula | High | Add worked examples C and D using per-CRG-type fields for a 3-region and 4-region scenario. Next design pass. |
| G-13 (partial) | Emergency Transfer | VMSS emergency disassociation path not designed | Medium | Phase 1 limitation formally accepted. Requires dedicated design session for VMSS scale-set group disassociation (different ARM operation from single-VM PATCH). |
| G-14 | Emergency Transfer | Consumer credential model for Tier 3 Step 2 not resolved | **High — Tier 3 Engineering Blocker** | Managed Identity vs. cross-subscription SP for consumer-side CR PATCH operation. Must be resolved before E08 Tier 3 can be engineered. |
| G-15 | Engine State | `engine_mode` state entity (STEADY_STATE / DR_EVENT_ACTIVE) not formally defined | Medium | Define as a Cosmos DB singleton entity. Include state machine transitions: STEADY_STATE → DR_EVENT_ACTIVE (trigger: failover trigger API call or ARM event), DR_EVENT_ACTIVE → FAILBACK_PENDING → STEADY_STATE. |

### 5.2 New Gaps Identified in This Review

| Gap ID | Category | Source | Description | Priority | Action Required |
|---|---|---|---|---|---|
| G-16 | FR-7.5 | Traceability check | Workload tagging for per-workload capacity forecasts — no dedicated backlog story | Medium (P2) | Add story: **E09-S08** — Implement workload tagging model: tag CRGs and VMs with `workload_name`; extend CapacityForecast to aggregate per-workload; add `GET /forecasts/workloads/{workload_name}` API. |
| G-17 | NFR-3 | Traceability check | No scalability testing stories for NFR-3.1 / NFR-3.2 / NFR-3.3 targets | Medium (P2) | Add three stories: **E11-S07** — Load test for 200 concurrent clients; **E11-S08** — Capacity test at 5,000 CRG / 50,000 CR targets; **E01-S16** — Horizontal Pod Autoscaler (HPA) configuration for Reconciliation and Forecasting workers. |
| G-18 | NFR-7.1 | Traceability check | No sovereign cloud deployment story (Azure Government, Azure China) | Low (P3) | Add story: **E12-S06** — Sovereign cloud deployment guide: identify API endpoint differences, document feature availability gaps, test ARM API compatibility in Azure Government. |
| G-19 | NFR-7.2 | Traceability check | No explicit data residency enforcement story; regional containment assumed not verified | Medium (P2) | Add story: **E12-S07** — Data residency audit: confirm Cosmos DB replication region pair, validate no telemetry leaves region, document network egress control (E12-S02) coverage. |
| G-20 | Data Model | Schema review | `CustomerRegionAssignment` entity used in selection algorithm pseudocode but not defined as a formal Cosmos DB entity | Medium | Add `CustomerRegionAssignment` to the Data Model (Section 4) of `multi_region_placement_design.md`. Fields: `customer_id`, `prod_region`, `nonprod_region`, `dr_region`, `scores` (JSON), `policy_id`, `assigned_at`, `status`, `is_active`. |
| G-21 | Data Model | Schema review | `IncidentRecord` referenced in `EmergencyCapacityTransferRequest.correlation_id` as the DR incident link but not defined | Medium | Define `IncidentRecord` entity or clarify this is a reference to an external ITSM ticket ID (ServiceNow incident number). If external: document the expected format and validation rules. |
| G-22 | Engineering Backlog | Backlog review | Final design references **E03-S09** and **E03-S10** (Quota Sync Worker extensions for Quota Group field population) but only E03-S01 through E03-S08 exist in the backlog | **High** | Add missing stories: **E03-S09** — Extend Quota Sync Worker to populate Quota Group entity fields (arm_group_resource_id, group_limit_vcpu, group_used_vcpu, per-env metrics) from `Microsoft.Quota/groupQuotas`; **E03-S10** — Extend RegionalSnapshot Redis cache with all 16+ Quota Group and per-CRG-type fields. Mark both P0 (blocking placement engine). |
| G-23 | API Surface | API review | `POST /api/v1/capacity/emergency-transfer` (defined in Pass 3) is not listed in the original API surface (Section 5.1 of original design) | High | Backport the emergency transfer API endpoint to Section 5.1 of `azure_cr_management_engine_design.md`. Also add corresponding Engineering Backlog story: **E08-S11** — Implement `POST /api/v1/capacity/emergency-transfer` endpoint with tier escalation logic and approval gate. |
| G-24 | Data Model | Schema review | `CapacityIncreaseRequest` entity (defined in Pass 3 Steady State section) is not in the original data model (Section 4.1) | Medium | Backport `CapacityIncreaseRequest` entity definition to Section 4.1 of `azure_cr_management_engine_design.md`. Add corresponding backlog story: **E02-S10** — Implement CapacityIncreaseRequest CRUD and lifecycle state machine. |

### 5.3 New Backlog Stories Required (Consolidated)

The gaps above require the following net-new backlog stories to be added to the engineering backlog:

| Story ID | Epic | Title | Priority | Resolves |
|---|---|---|---|---|
| E01-S16 | EPIC-01 | HPA configuration for Reconciliation and Forecasting worker pools | P2 | G-17 |
| E02-S10 | EPIC-02 | `CapacityIncreaseRequest` entity CRUD + lifecycle state machine | P1 | G-24 |
| E03-S09 | EPIC-03 | Quota Sync Worker extension — Quota Group ARM entity population | P0 | G-22 |
| E03-S10 | EPIC-03 | RegionalSnapshot Redis cache extension — Quota Group + per-CRG-type fields | P0 | G-22 |
| E08-S11 | EPIC-08 | Implement `POST /api/v1/capacity/emergency-transfer` endpoint | P1 | G-23 |
| E09-S08 | EPIC-09 | Workload tagging model + per-workload forecast API | P2 | G-16 |
| E11-S07 | EPIC-11 | Load test — 200 concurrent API clients + P95 latency validation | P2 | G-17 |
| E11-S08 | EPIC-11 | Capacity test — 5,000 CRGs / 50,000 CRs / 500,000 VM associations | P2 | G-17 |
| E12-S06 | EPIC-12 | Sovereign cloud deployment guide and API compatibility test | P3 | G-18 |
| E12-S07 | EPIC-12 | Data residency audit and network egress verification | P2 | G-19 |

**Impact on backlog totals:**

| Metric | Before This Review | After This Review |
|---|---|---|
| Total stories | 99 | **109** |
| P0 stories | 38 | **40** (+2: E03-S09, E03-S10) |
| P1 stories | 39 | **41** (+2: E02-S10, E08-S11) |
| P2 stories | 19 | **25** (+6: E01-S16, E09-S08, E11-S07, E11-S08, E12-S07, G-17 variant) |
| P3 stories | 3 | **4** (+1: E12-S06) |
| MVP (P0+P1) | 77 | **83** |

---

## 6. Blockers Registry

These seven items (B-1 through B-7) were identified prior to this review. Status confirmed here.

| Blocker ID | Category | Description | Severity | POC | Status |
|---|---|---|---|---|---|
| **B-1** | Quota Group GA | `Microsoft.Quota/groupQuotas` GA availability unvalidated in target regions — the entire Two-Group Quota Architecture (D6/D7) is at risk if feature is Preview-only or regionally restricted | 🔴 Critical | POC-30 | ⏳ POC pending |
| **B-2** | Quota-neutral claim | The Tier 2 "quota-neutral transfer" claim (reduction of NonProd CR qty releases quota back to group pool) is unvalidated — Tier 2 Emergency Transfer design assumes this behavior | 🔴 Critical | POC-31 | ⏳ POC pending |
| **B-3** | DR event declaration | The mechanism that transitions `engine_mode` to `DR_EVENT_ACTIVE` is not designed. Referenced in Steady State and Emergency Transfer sections but no API, event trigger, or ARM signal is defined | 🔴 High | None — G-15 design gap | ⏳ Design gap |
| **B-4** | `potential_dr_demand` maintenance | The `potential_dr_demand(region)` field in RegionalSnapshot is computed as `Σ prod_allocated for customers where dr_region = this region` but no reconciliation loop step describes how it is updated when customers deallocate Prod VMs (churn path) | 🟠 High | None — design gap | ⏳ Design gap |
| **B-5** | Quota increase endpoint | `POST Microsoft.Quota/groupQuotas/{id}/quota` — the group-level quota increase endpoint used by Phase B auto-increase — is unvalidated. REST API documentation for Quota Groups is immature; endpoint may differ | 🟠 High | POC-33 | ⏳ POC pending |
| **B-6** | Quota propagation latency | The latency between NonProd CR `quantity→0` and the released vCPU becoming available to DR expansion (Tier 2 RTO denominator) is unbounded by documentation | 🟡 Medium | POC-32 | ⏳ POC pending |
| **B-7** | Concurrent placement race | Two concurrent `POST /placement/evaluate` calls for the same DR region could both pass HC-6 at the same snapshot state, resulting in over-assignment. No distributed lock or optimistic concurrency guard is designed | 🟡 Medium | None — design gap | ⏳ Design gap |

### Blocker Resolution Path

```
B-1  → Execute POC-30 first (gates B-2, B-5, B-6 as well)
B-2  → Execute POC-31 after B-1 passes
B-3  → Design G-15 engine_mode state machine (design session required)
B-4  → Add reconciliation loop step for potential_dr_demand recalculation
B-5  → Execute POC-33 in parallel with B-1
B-6  → Execute POC-32 in parallel with B-1
B-7  → Design distributed locking strategy for Placement Engine (Redis SETNX or Cosmos DB optimistic concurrency)
```

**Gate rule:** No engineering work on Two-Group Quota Architecture (EPIC-03 E03-S09, E03-S10) begins until B-1 is resolved. No engineering work on Emergency Transfer (E08-S11) begins until B-2 is resolved.

---

## 7. Document Consolidation Recommendation

### 7.1 Current State

| Document | Lines | Purpose | Audience |
|---|---|---|---|
| `azure_cr_management_engine_design.md` | 1,662 | Original system design — FR/NF requirements, data model, API surface, engineering backlog | Engineering teams — implementation reference |
| `multi_region_placement_design.md` | 1,612 | Final architecture — placement scoring, quota group model, DR lifecycle, emergency transfer | Architecture reviewers, senior engineers, data engineers |
| `design_change_summary.md` | 772 | Change tracking across 3 passes — gap registry, decision log | Design team — internal reference |
| `acrme_diagrams/` | 6 diagrams | System architecture, quota group, placement flow, lifecycle, emergency transfer, VM disassociation | All stakeholders |

**Total design artifact: ~4,000+ lines across 3 documents, 6 diagrams — no single document provides a complete view.**

### 7.2 Recommendation: Create a Master Consolidated Design Document

**Decision: YES — create a consolidated master document. The two working documents are retained as engineering references.**

#### Rationale

1. **No single document is self-contained.** A reviewer of the original design does not see the Quota Group architecture, the placement scoring formulas, or the Emergency Transfer tiers — all of which are in `multi_region_placement_design.md`. A reviewer of the placement design does not see the full data model, API surface, or engineering backlog.

2. **Diagrams have no home.** The 6 architecture diagrams in `acrme_diagrams/` are not referenced by either document. The master document will embed them inline at the relevant sections.

3. **Executive presentation requires a canonical artifact.** The upcoming executive presentation should be built from a single authoritative document. The current split makes source-of-truth ambiguous.

4. **Gap and decision tracking is fragmented.** The gap table and decision log are in `design_change_summary.md`, separate from both design documents.

#### Recommended Document Structure

The consolidated document should be structured as:

```
# ACRME — Master Design Document

1. Executive Summary (from original design + extended)
2. Problem Statement and Engine Purpose
3. Scope — In / Out of Scope
4. Requirements
   4.1 Functional Requirements (FR-1 through FR-8)
   4.2 Non-Functional Requirements (NFR-1 through NFR-7)
   4.3 Placement-Specific Requirements (R1–R8, NFR-R1 through NFR-R3)
5. Architecture Overview
   5.1 System Context Diagram [Diagram 1 — embedded]
   5.2 Quota Group Architecture [Diagram 2 — embedded]
6. Placement Engine Design
   6.1 Hard Constraint Model (HC-1 through HC-7)
   6.2 Placement Score Formulas (PS_Prod / PS_NonProd / PS_DR)
   6.3 Selection Algorithm
   6.4 Placement Flow [Diagram 3 — embedded]
7. Capacity Lifecycle Management
   7.1 Steady State Lifecycle [Diagram 4 — embedded]
   7.2 Emergency Capacity Transfer [Diagram 5 — embedded]
   7.3 VM Disassociation Sequence [Diagram 6 — embedded]
8. Data Model (consolidated — all entities including Quota Group, CapacityIncreaseRequest)
9. API Surface (consolidated — including Emergency Transfer API)
10. Engineering Backlog (consolidated — EPIC-01 through EPIC-12 + new stories)
11. Outstanding Gaps and Blockers Registry
12. Decision Log (D1 through D11 + new decisions)
13. Appendices
    A: ARM API Reference Table
    B: POC Test Requirements (reference to poc_test_workbook.md)
```

#### What Changes From Current Documents

| Current Document | Action |
|---|---|
| `azure_cr_management_engine_design.md` | Retained as **engineering backlog reference**; backlog stories are the primary use case. The master document includes a summarised version of Section 4 (data model) and Section 14 (backlog) with new stories. |
| `multi_region_placement_design.md` | Retained as **placement algorithm reference**; formula derivations and worked examples are the primary use case. The master document embeds the formulas and diagrams; the detailed examples remain in the placement design. |
| `design_change_summary.md` | Content is **absorbed** into the master document (gap registry → Section 11; decision log → Section 12). The change summary is retired as an active document after the master is created. |
| `acrme_diagrams/*.png` | **Embedded** into the master document at their relevant sections. |

### 7.3 What This Is Not

The consolidated document is **not** a code-level engineering specification. It does not replace the engineering backlog (which teams use sprint-by-sprint) or the POC test workbook (which is the implementation validation artifact). It is the **architecture review document** — the single artifact that a Principal Architect, CTO, or senior stakeholder reads to understand the entire ACRME system.

---

## 8. Summary Coverage Statistics

### Functional Requirements

| Domain | Sub-requirements | Fully Covered | Partial | Not Covered |
|---|---|---|---|---|
| FR-1 CR Lifecycle | 6 | 6 | 0 | 0 |
| FR-2 Sharing | 7 | 7 | 0 | 0 |
| FR-3 Zone Mapping | 6 | 6 | 0 | 0 |
| FR-4 Quota | 6 | 6 | 0 | 0 |
| FR-5 DR Failover | 7 | 7 | 0 | 0 |
| FR-6 Placement | 5 | 5 | 0 | 0 |
| FR-7 Forecasting | 6 | 5 | 1 | 0 |
| FR-8 Cost Optimization | 6 | 6 | 0 | 0 |
| **Subtotal FR** | **49** | **48 (98%)** | **1 (2%)** | **0** |

### Non-Functional Requirements

| Domain | Sub-requirements | Fully Covered | Partial | Not Covered |
|---|---|---|---|---|
| NFR-1 Availability | 4 | 3 | 1 | 0 |
| NFR-2 Performance | 5 | 4 | 1 | 0 |
| NFR-3 Scalability | 3 | 0 | 1 | 2 |
| NFR-4 Reliability | 4 | 4 | 0 | 0 |
| NFR-5 Security | 6 | 6 | 0 | 0 |
| NFR-6 Observability | 4 | 4 | 0 | 0 |
| NFR-7 Compliance | 3 | 1 | 1 | 1 |
| **Subtotal NFR** | **29** | **22 (76%)** | **4 (14%)** | **3 (10%)** |

### Placement Requirements

| Domain | Sub-requirements | Fully Covered | Partial | Not Covered |
|---|---|---|---|---|
| R1–R8 Functional | 8 | 8 | 0 | 0 |
| NFR-R1–R3 Performance | 3 | 3 | 0 | 0 |
| **Subtotal Placement** | **11** | **11 (100%)** | **0** | **0** |

### Overall

| Category | Total | Covered (Full+Partial) | Not Covered |
|---|---|---|---|
| All requirements | 89 | **87 (98%)** | **2 (2%)** |
| Fully covered only | 89 | **83 (93%)** | 6 (7%) |

### Gap Summary

| Gap Range | Count | Highest Priority | Status |
|---|---|---|---|
| G-7, G-13 (partial), G-14, G-15 | 4 | G-14 = High | Carried from Pass 3 |
| G-16 through G-24 (new) | 9 | G-22 = High | Identified in this review |
| B-1 through B-7 (blockers) | 7 | B-1, B-2 = Critical | POC-gated |
| **Total open items** | **20** | | |

---

## 9. Decision Log

*(Decisions made in this review session — additive to D1 through D11 in main design)*

| Decision ID | Decision | Rationale | Alternatives Considered | Impact |
|---|---|---|---|---|
| D-TR-1 | NFR-3 (scalability) confirmed as the largest NFR gap in the design — three new stories required (G-17) | No load testing or autoscaling story exists despite specific numeric targets in NFR-3.1/3.2/3.3. Architecture is designed to scale but never verified | Option: Accept as architecture assumption — rejected; numeric targets in requirements need validation | Add E01-S16, E11-S07, E11-S08 to backlog |
| D-TR-2 | E03-S09 and E03-S10 designated P0 (MVP blockers) | The Quota Sync Worker extension is the data pipeline that feeds all Quota Group fields in RegionalSnapshot. Without it, HC-3, HC-7, Quota_Score, and the entire placement formula are non-functional. No placement can execute without this data | Option: P1 — rejected; placement engine (EPIC-07) has a data dependency on E03-S09/S10 | Backlog updated: 40 P0 stories (was 38) |
| D-TR-3 | Consolidated master document recommended over further expansion of either existing document | Both existing documents are >1,600 lines; no single document is self-contained; diagrams have no home; executive presentation needs a canonical artifact | Option: Keep documents split, add index document — rejected (does not resolve the self-containment problem for executive reviewers) | Master design document to be created after this review is signed off |
| D-TR-4 | B-3 (engine_mode declaration) and G-15 (engine_mode entity) to be resolved in same design session | They are the same design problem: the state machine governing how the engine declares and exits a DR event. Treating them as separate work items would produce an inconsistent design | Option: Resolve separately — rejected | Both to be designed together; model includes STEADY_STATE, DR_EVENT_ACTIVE, FAILBACK_PENDING transitions |
| D-TR-5 | POC-30 execution must be the first POC gate before any engineering begins on EPIC-03 extension stories | E03-S09 and E03-S10 (new P0) depend on `Microsoft.Quota/groupQuotas` being available and working in target regions. If POC-30 fails, the entire Quota Group architecture must be redesigned | Option: Begin E03-S09/S10 in parallel with POC-30 — rejected; risk of engineering rework on GA availability failure | POC sequencing: POC-30 → POC-31, POC-33 (parallelizable) → E03-S09/S10 → E07-S01 |

---

*Requirements Traceability Review v1.0 — August 2026*  
*ACRME — Azure Capacity Reservation Management Engine*  
*Pre-POC Scripting Gate Assessment*  
*Classification: Principal Cloud Architect*
