# Allowed VM Series and Financial Approval - Baseline-Change Proposal

**Type:** Design Note / baseline-change proposal
**Baseline:** v4.0 (14 October 2026), resolved on 23 October 2026
**Phases touched:** P1 visibility/protection, P2 quota, P3 placement, P4 DR, P5 domain binding
**Codes in scope:** CAP-001, CAP-016, CAP-017, CAP-019, CAP-022, CAP-024, QUA-002, FIN-003, GOV-002, GOV-003, GOV-006
**Status:** User-confirmed policy input; baseline incorporation and runtime implementation pending.

## 1. Decision and authority

[Decided] On 23 October 2026 the programme owner supplied the allowed VM-series list and required teams to submit new capacity requests through Jira for business and finance approval. Follow-up clarification confirmed:

- All sizes within each listed series are policy-allowed; no separate exact-size allowlist is required.
- The policy covers VMs and VM Scale Sets (VMSS) used by AKS clusters. The same series allowlist and Jira business/finance approval requirements apply to both.
- Jira business and finance approval applies to new capacity requests.
- Existing protective reconciliation remains unchanged.
- Record the policy in [environment.yaml](../environment.yaml) and this proposal without editing the [v4.0 baseline](acrme_requirements_baseline_v4_0.md).

[Decided] The submitted list contained 32 entries and 31 unique series. `Standard_Lasv4` appeared twice and is recorded once. Names are preserved as supplied; this is a programme series catalogue, not an Azure quota-family identifier list or a list of exact deployable VM sizes.

## 2. Allowed series

[Decided] The machine-readable source is `capacity_request_policy.allowed_vm_series` in [environment.yaml](../environment.yaml), effective 23 October 2026.

| Group | Allowed series labels |
|---|---|
| D v5 | Standard_Ddv5, Standard_Ddsv5, Standard_Dasv5, Standard_Dadsv5 |
| D v6 | Standard_Dsv6, Standard_Ddsv6, Standard_Dldv6, Standard_Dldsv6, Standard_Dalsv6, Standard_Daldsv6 |
| D v7 | Standard_Dsv7, Standard_Ddsv7, Standard_Dldv7, Standard_Dldsv7, Standard_Dalsv7, Standard_Daldsv7 |
| E v5 | Standard_Edv5, Standard_Edsv5, Standard_Easv5, Standard_Eadsv5 |
| E v6 | Standard_Esv6, Standard_Edsv6, Standard_Easv6, Standard_Eadsv6 |
| E v7 | Standard_Esv7, Standard_Edsv7, Standard_Easv7, Standard_Eadsv7 |
| L | Standard_Lsv3, Standard_Lasv4, Standard_Lsv4 |

## 3. Proposed normative requirements

[Decided] The following text captures the user-confirmed policy for incorporation into the baseline; it does not assign new requirement codes.

1. New capacity requests must use a VM size belonging to one of the listed series. All sizes within a listed series are policy-allowed. Unlisted series are not eligible through this standard request path.
2. Teams must submit new capacity requests in Jira. Both business and finance approval are required; neither approval substitutes for the other.
3. Approval evidence must retain the Jira request reference and both approval records. Missing or unconfirmed required approval does not authorize new capacity.
4. Exact VM size is still required before technical readiness can be established. Series membership is an allowlist decision, not a VM-size selection or reservation identity.
5. Business/finance approval does not establish platform availability, quota, reservation eligibility, or readiness, and does not waive existing hard constraints or exception approvals.
6. Existing protective reconciliation, including allocated-plus-buffer tracking and CAP-024 discovery/governance behavior within approved managed scope, remains unchanged. This proposal does not introduce retroactive approval gates or authorize new out-of-scope mutations.
7. Apply this policy to VM capacity requests and to VMSS node capacity requests for AKS clusters. For AKS requests, apply series eligibility to the VM size used by each requested node pool, not to the cluster name or Kubernetes version.

[Derived] Future integration should resolve exact VM size to catalogue series membership rather than use substring/prefix matching. Approved-series membership, request approval and technical readiness are separate gates. The YAML records policy only; it does not implement a Jira integration or runtime enforcement.

## 4. Platform evidence and limitations

[Documented] Azure capacity reservations target a specific VM size and location; support is limited to eligible series/sizes. The Compute Resource SKUs list advertises supported sizes. A business allowlist therefore cannot certify every listed size for every subscription, region or zone.

Source: [On-demand capacity reservation overview](https://learn.microsoft.com/en-us/azure/virtual-machines/capacity-reservation-overview), accessed 23 October 2026 using Microsoft Learn search/fetch and Azure MCP documentation search. Conceptual documentation, not an API-version certification; runtime adapter versions remain to be selected and validated. No live subscriptions were queried and no POC was executed.

[Documented] The fetched overview labels several Intel v7 reservation entries as Preview, including Dsv7, Ddsv7, Esv7 and Edsv7. Inclusion in this programme allowlist does not promote platform features to GA or approve a Preview production dependency.

## 5. Open decisions

| Item | Required closure / owner |
|---|---|
| SPEC GAP: Jira workflow | Workflow states, approver roles/delegation, authoritative approval evidence and integration contract; business/finance/platform owners. |
| SPEC GAP: Approval scope | Quantity, cost, customer/domain/environment/region coverage, validity, revocation and which changes require reapproval; business/finance owners. No approval ordering or unlimited spending is inferred. |
| SPEC GAP: Series mapping | Authoritative mapping of exact VM sizes to the supplied series labels and API quota-family names; platform/Architect. Preserve labels until verified, do not silently rename them. |
| SPEC GAP: Preview eligibility | Applicable size/region/zone support and enterprise production policy for Preview offerings; Architect/platform governance. No production eligibility certification is made here. |

## 6. Acceptance checks

- [Derived] The catalogue has exactly the 31 unique supplied labels, with no extra or missing series.
- [Derived] A size in a listed series passes policy eligibility without needing a second size allowlist, but not technical readiness automatically.
- [Derived] A size in an unlisted series is rejected by the standard new-request policy.
- [Derived] Business-only, finance-only or missing approval cannot authorize a new request.
- [Derived] Both approvals allow the request to proceed to existing readiness gates, not bypass them.
- [Derived] VM requests and AKS VMSS node-pool requests use the same series catalogue and both required approvals; each requested node-pool VM size is evaluated.
- [Derived] CAP-024 protective reconciliation retains its current behavior; encountering a disallowed series does not silently remove production protection.
- [Derived] All existing geography, blue/green and subscription policies are preserved.

These are required future demonstrations, not executed Jira/runtime tests. The configuration catalogue and preserved-policy checks can be validated offline.

## 7. Gates and traceability

**Baseline compliance:** EXTENDS CAP-022/FIN-003/GOV-002/006 with an explicit series catalogue and Jira approval path; ALIGNED with CAP-001/016/017/019 and QUA-002; preserves CAP-024. Baseline text unchanged. Runtime enforcement is BLOCKED on the affected open decisions.

| Hard constraint | Review result and evidence |
|---|---|
| HC-1 REGION_SEPARATION | PASS - existing region rules unchanged. |
| HC-2 CAPACITY_FLOOR | PASS - approval does not bypass capacity checks. |
| HC-3 QUOTA_FLOOR | PASS - approval does not bypass either quota cap. |
| HC-4 DR_SEPARATION_CLASS | PASS - no placement change. |
| HC-5 ZONE_AVAILABILITY | PASS - series approval does not certify zone support. |
| HC-6 DR_COVERAGE_FLOOR | PASS - DR sizing/coverage policy unchanged. |
| HC-7 DR_FLOOR_INTEGRITY | PASS - no floor release or quota reallocation authorized. |
| HC-8 GEOGRAPHY_CONTAINMENT | PASS - existing geography rules unchanged. |
| HC-9 STANDARD_REGION_ONLY | PASS - no new region exception. |
| HC-10 CROSS_GEO_EXTENSION_PATH_APPROVED | PASS - financial approval does not replace legal/geography approval. |
| HC-11 AVAILABILITY_SET_INELIGIBLE | PASS - series membership does not override VM placement eligibility. |

PASS denotes preservation of constraints in this proposal, not certification of any deployment.

**Formula check:** N/A - no sizing, scoring or quota formula changes.
**DR sizing:** N/A - no protected portions, bootstrap quantities or MAX-not-SUM rules changed.
**Open items touched:** POC-008/009 buffer policies remain unchanged; DEP-001 sharing maturity remains independently gated.

| WAF pillar | Assessment / mitigation |
|---|---|
| Reliability | Keep protective reconciliation and require technical readiness after approval. |
| Security | Separate business/finance approvals from execution; resolve approver roles before enforcement. |
| Cost Optimization | Require both approvals; define quantitative approval scope before automation. |
| Operational Excellence | Retain Jira/approval evidence and versioned catalogue; define revocation and change handling. |
| Performance Efficiency | Validate series membership separately from fresh capacity/quota observations; no new polling cadence assumed. |
