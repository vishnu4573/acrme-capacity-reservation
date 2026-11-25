# Proposed Changes — ACRME E2E Deployment Flow Diagrams

**Type:** Review / Proposed Changes

**Baseline:** v4.0.2 (17 November 2026), resolved with `check_grounding.py`

**Related flow:** [ACRME End-to-End Deployment Flow v2.0](./ACRME_End_to_End_Deployment_Flow_v2.md)

**Diagram document reviewed:** [ACRME E2E Deployment Flow Diagrams v1.0](./archive/ACRME_E2E_Deployment_Flow_Diagrams.md)

**Status:** Implemented in [diagram document v2.0](./archive/ACRME_E2E_Deployment_Flow_Diagrams_v2.md); v1.0 remains preserved

**Phases touched:** P1 Visibility & Prod Protection; P3 Placement & Seed; P4 Distributed DR; P5 Multi-Domain Model & Two-Scope Binding

## Purpose

Record the content corrections needed to align the diagrams with the v2.0 deployment flow and the v4.0.2 requirements baseline. These recommendations are implemented in the linked v2.0 diagram document; the v1.0 source remains unchanged.

## Proposed Changes

### 1. Diagram 1 — Onboarding and CRV

- **Show the correct placement input paths.** Make an exact production region the default input. Show geography-based production selection only as an exception requiring approval and customer acknowledgement; keep the approver as an open item under DEC-003 (PLC-001/002).
- **Separate CRV gates from DPB gates.** Keep region-level HC-1, HC-4, HC-5, HC-8, HC-9, and HC-10 in CRV. Move HC-2, HC-3, HC-6, and HC-7 to per-domain DPB/readiness; do not show those domain floors as CRV pass criteria (PLC-013..016).
- **Correct HC-5.** Replace `az_count ≥ 1` with the non-dev requirement for at least two physical availability zones, subject to the applicable policy (HC-5).
- **Make scoring conditional and policy-driven.** Do not score or replace Prod on the default exact-region path. On the approved geography exception, score eligible Prod candidates; score CVAL/DR candidates as required by the distribution model. Remove the hard-coded α/β/γ/δ/ε/ζ coefficients and show configured, approved policy instead (PLC-007/008, F.10/F.11).
- **Scope the cross-geography gate.** Apply HC-10 only to the Middle East cross-geography DR path, not as a generic gate for every region (DEC-001, PLC-010b, DR-020).

### 2. Diagram 2 — DPB Resolution

- **Clarify the CRG topology.** Keep Prod reservations dedicated. Show the dedicated, always-present DR Foundation and its pre-staged quota for each domain group. Show same-domain CVAL/DR sharing only as a conditional extension after authorized declaration and applicable gates; it must not be a prerequisite for the Foundation (CAP-025, DR-021).
- **Make the zone structure precise.** The default is one zonal CRG with one reservation per VM size per zone. Per-zone CRGs are optional where configured. A no-zone `reg` CRG is not a region-wide pool; it is pinned to one zone (CAP-023).
- **Correct the buffer reference.** Production reservation buffer is C-2. Keep C-1 for DR bootstrap and C-16 for the DR Foundation bootstrap policy (CAP-003, DR-021).
- **Represent quota thresholds as configurable.** Replace a fixed `Group ≥ 85%?` decision with configured group and subscription thresholds, noting 85% as the default rather than an invariant (QUA-015).
- **Constrain subscription scale-out.** Retain shard resolution only behind the applicable configured subscription/cluster-limit and rollout-headroom policy; do not imply that any capacity condition authorizes an unconditional new shard.
- **Complete the DPB output.** Include the separate resource-subscription reference where the standard profile requires it. Continue to state that DPB does not output an Instance Group (PLC-014/015, DOM-002).

### 3. Diagram 3 — Readiness and Platform Foundation

- **Keep baseline readiness distinct from deployment-standard policy.** Retain the baseline capacity, reservation-integrity, freshness, and both-quota-cap checks. Add a separate conditional policy-gates lane for:
  - exact VM-size/series eligibility and business/finance approval for new capacity requests;
  - blue/green current-plus-replacement overlap and configured cluster limits;
  - the open DR/rollout-headroom conflict policy; and
  - sharing’s Preview, authorization, POC, provider-quota, consumer-quota, and physical-zone checks.
- **Do not turn request approval into a universal deployment gate.** New-capacity approval applies to the defined new-request path; it does not retroactively block protective reconciliation or replace technical readiness.
- **Resolve the `CAP-023` platform-HA citation.** CAP-023 describes zonal CRG structure. Unless another platform requirement supports the in-region HA step, label that step as platform-owned and cite its actual source rather than using CAP-023 for platform HA.
- **Preserve readiness outcomes.** Show `READY_WITH_RISK` as distinct from `READY`, with blocking and manual-validation states leading to the corresponding remediation path (RDY-001..004).

### 4. Diagram 4 — Service Deployment, IG Lifecycle, and Go-Live

- **Move initial IG provisioning into Phase 5.** After receiving CRV/DPB, show the Service Owner defining the IG and service deployment automation selecting and initially provisioning it, before workload deployment and reservation association. Keep Phase 6 for ongoing IG lifecycle and scaling (PLC-014, DOM-002).
- **Complete the integration input contract.** Include the subscription alongside the domain, environment, region, SKU/count, zone, priority, and correlation ID inputs (INT-003, INT-008).
- **Constrain scale-out.** Keep subscription/cluster scale-out conditional on configured limits and rollout-headroom policy; do not make a generic “primary sub at limits” decision an automatic shard-creation trigger.
- **Label service-owned go-live checks.** Health, dependency, synthetic, and business checks belong to the service SLO/runbook. Treat one-writer-per-realm as a platform-specific policy unless its ACRME requirement source is established.
- **Make DR readiness conditional on the DR offer.** Replace “onboarding rejected if failover capacity is not reserved” with a check that certifies the domain’s DR Foundation when DR is offered. Record `DR_NOT_OFFERED` where applicable; do not make lack of an offer a blanket onboarding rejection (DR-014, DR-021).

### 5. Diagram 5 — Steady State and DR

- **Show safe reconciliation and retirement boundaries.** Include reserved, allocated, associated, and buffer quantities; create Azure resources before config activation; right-size toward allocated plus buffer; and make clear that a target of zero does not delete a CRG/CR. Intentional retirement, deletion, or scope removal belongs to the separate approved decommission workflow (CAP-005, CAP-008..010, CAP-019, CAP-024).
- **Correct steady-state policy labels.** Use C-2 for production buffer, and describe quota replenishment thresholds as configurable with 85% defaults (QUA-015).
- **Branch CVAL release by applicable DR model.** Show it only after authorized declaration and only for the applicable same-domain CVAL/DR model. Middle East CVAL is local with Prod; Middle East DR uses dedicated European capacity and does not use CVAL sacrifice (PLC-010b, DR-020/021).
- **Constrain sharing.** Do not depict “share/reassign” as guaranteed capacity or imply cross-region reassignment. Sharing is Preview, same-region/domain-scoped, requires explicit authorization, physical-zone alignment, provider and consumer quota, and applicable POC/DEP gates; production must not depend on it. Do not encode a guaranteed sharing-consumption order while POC-002 remains open (CAP-013, QUA-013, POC-001/002/003/012, DEP-001).
- **Preserve CRV during recovery.** Replace “Update placement” with activation-state and traffic-routing updates. Do not rewrite the immutable placement seed; region changes use the approved migration path (PLC-005, DR-019).
- **Mark platform-specific recovery steps as runbook-owned.** Service-0 and APIM steps should be identified as service/platform recovery-runbook steps, not universal ACRME requirements.
- **Complete failback.** Add restored-region readiness and approval, guarded reverse activation/routing, and preservation of CRV, DR index, capacity history, activation records, and audit trail (DR-012/013/019; DEC-002 remains open).

### 6. Cross-Cutting Diagram, Traceability, and Version

- Replace “Availability-Set VMs rejected at onboarding” with the VM-level eligibility rule and its CAP-021 remediation; ACRME does not automatically migrate a running workload (HC-11, CAP-020/021).
- Replace “config-driven policy (no code changes)” with “policy inputs are configuration-driven”; configuration does not prove runtime enforcement.
- Replace “Prod uses deploying sub until sharing is GA” with the durable rule: [Documented] CAP-013 / DEP-001 — production must not depend on sharing; use the deploying-subscription reservation as the fallback. Any future GA status does not by itself remove policy gates.
- Update the traceability table so CRV and DPB requirements are not conflated, deployment-standard checks are visible, and Phase 5 initial IG provisioning is distinguished from Phase 6 lifecycle.
- Align the diagram document’s version and baseline metadata with the v2.0 flow and v4.0.2 baseline. Preserve v1.0 as the historical copy if a v2 diagram file is created.

## Deployment-Standard Compliance

`environment_v2.yaml` is the owner-confirmed deployment standard, effective 2026-10-23. Its values document intended policy, not runtime enforcement. The following settings remain relevant to the diagram changes:

**Deployment-standard compliance: OPEN** for unresolved policy items. These open items block only the dependent readiness claim until closed.

| YAML key / decision | Proposed diagram treatment | Status |
|---|---|---|
| `capacity_request_policy.allowed_vm_series` and `capacity_request_policy.approval` | Show as new-capacity-request eligibility/approval gates, separate from technical readiness; retain open mapping/workflow details | OPEN |
| `compute_subscription_policies.standard.deployment.rollout` | Show current-plus-replacement validation before traffic cutover | ALIGNED in flow; add to diagram |
| `compute_subscription_policies.standard.cluster_capacity` and `.dr_clusters` | Show configured cluster/DR limits and scale rules | ALIGNED in flow; add to diagram |
| `compute_subscription_policies.standard.dr_clusters.rollout_headroom_conflict_policy` | Do not assume rollout headroom is available to DR | OPEN |
| `capacity_reservation_policies.standard.sharing` | [Documented] CAP-013 / DEP-001: Preview only; provider ownership pending; retain same-subscription fallback and all applicable checks | OPEN |
| `capacity_reservation_policies.standard.dr_foundation` and `.cross_geography_dr` | Show dedicated DR Foundation and dedicated Middle East destination capacity | ALIGNED |

Differences between `environment.yaml` and `environment_v2.yaml` are historical what-if drift, not an authority conflict. Open items block only the dependent readiness claim until closed.

## Alignment Gate

- **Baseline compliance:** ALIGNED to v4.0.2 for this proposal; apply the changes against the baseline, not superseded baseline copies.
- **Hard constraints:** The principal correction is restoring HC scope: region-level checks in CRV, domain-level capacity/quota floors in DPB, and HC-11 at VM eligibility.
- **Formula check:** N/A — this proposal changes diagram representation, not formulas.
- **DR sizing:** Preserve DR-017 / F.6–F.8 MAX-not-SUM sizing across non-concurrent sources.
- **Open items touched:** DEC-001/002/003; POC-001/002/003/007/011/012; DEP-001; deployment-standard pending decisions.

## Source References

- [Requirements baseline v4.0.2](../../Archive/requirements/baselines/acrme_requirements_baseline_v4_0_2.md)
- [Deployment flow v2.0](./ACRME_End_to_End_Deployment_Flow_v2.md)
- [Deployment-standard configuration](../../environment_v2.yaml)
- [Series and financial-approval proposal](../../Requirements/acrme_sku_financial_approval_baseline_change.md)
