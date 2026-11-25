# Approved Baseline Change — DR Foundation and Deployment Standard

**Type:** Approved baseline-change record
**Baseline:** v4.0.2, approved and incorporated on 17 November 2026
**Phases touched:** P4 Distributed DR, P5 Multi-Domain Model & Two-Scope Binding
**Codes in scope:** ENV-005, DOM-002, DR-021, POC-006, C-16
**Status:** Approved by the programme owner; incorporated in v4.0.2

## 1. Purpose

Record the approved production DR topology and clarify the scope of POC-006. The changes are incorporated in the separate v4.0.2 baseline.

## 2. Confirmed decisions

- **[Decided] Deployment standard:** `environment_v2.yaml`, effective 23 October 2026, is the deployment-standard configuration. `environment.yaml` is retained as an earlier what-if model and is not the standard.
- **[Decided] Production DR topology:** The standard uses a dedicated DR compute subscription per domain group and environment, consistent with the standard environment profile.
- **[Decided] DR Foundation:** Each domain's DR Foundation is always present in the dedicated DR subscription, with pre-staged quota and the minimum configurable reserved bootstrap capacity needed to validate DR readiness and begin recovery. It is tested before readiness certification. It is not a full production duplicate or a fixed percentage.
- **[Decided] POC-006 scope:** POC-006 tests an alternate shared-production-subscription topology only as a secondary option or approved exception. It does not determine or block the dedicated-subscription production standard.

The relevant configured values are `capacity_reservation_policies.standard.dr_foundation.subscription`, `capacity_reservation_policies.standard.dr_foundation.capacity`, `capacity_reservation_policies.standard.dr_foundation.always_present`, `capacity_reservation_policies.standard.dr_foundation.quota`, and `compute_subscription_policies.standard.dr_clusters.provision` in `environment_v2.yaml` (effective 2026-10-23).

## 3. Changes incorporated in v4.0.2

### 3.1 ENV-005 / DR-021 — Dedicated DR subscription and Foundation readiness

The following normative clarification was added to ENV-005 and DR-021:

> The standard DR topology uses a dedicated DR compute subscription for each domain group and environment, consistent with DOM-002 and the approved environment profile. Each domain maintains its DR Foundation in that subscription with pre-staged quota. The Foundation is always present and sized as the minimum configurable bootstrap needed to test and certify DR readiness and begin the approved recovery sequence, including required control-plane and initial priority recovery capacity. It is not a full production duplicate and must not be assigned a fixed percentage. Readiness certification requires the configured DR setup and tests to complete successfully with recorded evidence. Foundation sizing remains configurable under C-16; zero capacity requires the explicit approval in ENV-006. The Foundation does not depend on CVAL/DR reservation sharing.

Retain the existing CVAL Extension and its sharing/POC gates. This change does not make Preview sharing a production dependency or change DR-017 max-not-sum sizing.

### 3.2 POC-006 — Alternative topology only

The POC-006 description was changed to:

> **POC-006 — Alternate DR subscription topology.** Evaluate a shared-production-subscription topology only as a secondary option or for an approved exception. The production baseline remains a dedicated DR compute subscription per domain group and environment. POC results do not change the production baseline; adopting an alternative requires a separately approved decision and documented exception.

### 3.3 Companion deployment-standard reference

The approved baseline identifies `environment_v2.yaml` as the authoritative companion deployment-standard configuration, effective 23 October 2026. It identifies `environment.yaml` as a historical what-if model, not an alternative standard. The configuration records policy intent and is not, by itself, evidence of runtime implementation or readiness certification.

## 4. Traceability

| Requirement / decision | Change | Evidence / validation |
|---|---|---|
| ENV-005, DR-021 | Dedicated DR subscription; always-present, tested minimum bootstrap; pre-staged quota | Verify the standard profile and DR Foundation configuration; readiness certification requires recorded test evidence |
| DOM-002 | Scope dedicated subscription ownership by domain group and environment | Confirm consistency with the environment profile |
| POC-006 | Test alternative topology only; not a production baseline gate | POC report records alternate scope and does not imply baseline adoption |
| C-16, ENV-006 | Keep sizing configurable; preserve explicit approval for zero | No fixed percentage or new bootstrap quantity introduced |
| CAP-013, DR-021 | Preserve same-domain sharing boundaries and the Foundation's independence from sharing | Existing POC and Preview gates remain in force |

## 5. Gates

**Baseline compliance:** EXTENDS ENV-005, DOM-002, and DR-021; clarifies the scope of POC-006. No formula or hard-constraint changes are proposed.

**Deployment-standard compliance:** ALIGNED with `environment_v2.yaml` (effective 2026-10-23) and the owner's confirmation on 2026-11-17. Existing unrelated pending decisions remain open.

**Hard constraints:** PASS — no HC-1..HC-11 relaxation or change.

**Formula check:** N/A — no numerical formula changes.

**DR sizing:** DR-017 max-not-sum is unchanged; C-16 remains configurable and no fixed bootstrap percentage is introduced.

**Open items touched:** POC-006 remains a validation item for an alternative/exception topology only; POC-007 remains relevant to product-specific minimum bootstrap sizing.

## 6. WAF

| Pillar | Assessment / mitigation |
|---|---|
| Reliability | Require DR setup and tests before readiness certification; retain dedicated bootstrap capacity. |
| Security | Keep DR capacity and access scoped to the domain and dedicated DR subscription. |
| Cost Optimization | Keep the Foundation at a configurable minimum; avoid a fixed production-sized duplicate. |
| Operational Excellence | Record test results and certification evidence; keep exception approval separate from the baseline. |
| Performance Efficiency | Preserve current DR scaling and quota-validation rules; no new API cadence is assumed. |
