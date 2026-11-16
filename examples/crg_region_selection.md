# CRG Region Selection Starter

**Type:** Design Note
**Baseline:** v4.0 (14 Oct 2026), resolved on 2026-11-03.
**Phases touched:** P3 candidate selection; P5 downstream CRV/DPB integration.
**Codes in scope:** PLC-001, PLC-002, PLC-005, PLC-007, PLC-012, PLC-013, PLC-015, CAP-013, CAP-016, QUA-013.
**Status:** Draft example, not an approved engine implementation.

## Run

```bash
python3 examples/crg_region_selection.py
python3 -m unittest discover -s examples -p test_crg_region_selection.py -v
```

Python standard library only. No credentials, SDK calls, or Azure resources needed.
Start with `demo_inputs()` in [crg_region_selection.py](crg_region_selection.py),
replace the synthetic objects with typed inputs, then call `select_region()`.

## Scope

[Documented] Region binding is customer-scoped and precedes domain CRG binding
(PLC-013, PLC-015). This helper filters **one requested SKU/zone cell** against
existing same-subscription CRGs. It is an advisory component for that pipeline,
not the full customer-level region decision or a CRG creation planner.

[Derived] A CRG does not move between regions. Candidate CRGs describe existing
regional capacity; selecting one does not create, resize, or associate anything.
Do not invoke this helper independently per domain to generate customer bindings.

[Documented] Exact production region is the default (PLC-001). Supply
`fixed_region` from the exact Prod input, or from the existing CRV for the requested
environment. Geography-only Prod ranking requires both approval and customer
acknowledgement (PLC-002). Approval booleans are trusted adapter results, not an
approval system; DEC-003 still needs an authoritative approver/workflow.

If the fixed region cannot serve this request, the result retains that region,
has no selected CRG, and returns `BLOCKED`. Raise an operational alarm and continue
the independent CVAL/DR resolution where appropriate (PLC-008); never silently
substitute another production region or rewrite the seed (PLC-005).

## Inputs

| Input | Meaning / adapter responsibility |
|---|---|
| Request identity | Geography, environment, domain, deploying subscription, exact SKU, zone, instance count. Geography here is the **target** geography; the outer CRV resolver handles cross-geography DR. |
| `fixed_region` | Already-bound environment region, or supplied exact Prod region; not a soft preference. |
| CRG identity | Authoritative CRG resource ID in real inputs; the demo uses labels. Domain/environment are ownership metadata, not CRG-name parsing. |
| `available_instances` | Usable units for this exact SKU/zone, after allocated consumption, protected buffers, earmarks and outstanding placement claims. Never sum unrelated sizes, zones, or domains. |
| `observed_at`, `snapshot_id` | UTC-aware timestamp and authoritative snapshot reference covering all candidate inputs; future or stale state is rejected. |
| `family_quota_admitted`, `regional_quota_admitted` | [Derived] Effective admission for this demand, from a quota adapter, not simply raw unused quota or Quota Group totals. Both must pass; see Azure evidence below. |
| `reservation_supported` | Verified exact SKU/region/zone/subscription and deployment-type eligibility. Not inferred from series names. |
| `hard_constraints` | Every HC-1 through HC-11 explicitly evaluated for the proposed customer placement context; values PASS or justified N/A. FAIL, unresolved, or missing values block. N/A requires documented applicability in the upstream evaluator. |
| `normalized_factors` | Seven customer-aggregate suitability values in [0,1], larger is better: allocated, available_reservation, quota, buffers, expected_dr, zone_support, freshness. Upstream approved policy owns their normalization and aggregation across all customer domains. |
| Customer counts | Distinct customers in the target geography and the region's customer count for this environment, from the same authoritative placement snapshot (PLC-012). |
| `weights`, `max_age` | Configurable policy inputs. Exactly eight nonnegative finite weights summing to 1; positive snapshot age limit. |

This example trusts typed adapters; it is not an untrusted JSON/API validation
layer. A caller must verify customer identity, approved exception evidence, CRV
reuse, policy version, and common snapshot provenance before calling it.

## Scoring

[Documented] F.10 defines weighted normalized factors at customer aggregate:
`score = sum(weight[factor] * normalized_suitability[factor])`.
Fairness is computed here as `1 - environment_customers / geography_customers`,
or 1 when the geography has no customers (PLC-012). Other normalizers remain
explicit adapter inputs rather than invented baseline formulas.

[Assumed] Demonstration only: equal weights of 0.125, seven normalized factors
of 0.8, a five-minute freshness limit, and synthetic HC PASS verdicts.
The architecture/policy owner must replace these before integration.
East US 2 fairness is `1 - 2/10 = 0.8`, yielding `0.8` overall.
Central US fairness is `1 - 5/10 = 0.5`, yielding
`(7 * 0.8 + 0.5) / 8 = 0.7625`.
West US 2 has only one usable unit for three requested and is rejected before
scoring. Ties resolve by region name, then CRG ID for reproducibility.

## Azure Evidence

[Documented] Reservations match exact VM size, region and, when zonal, zone.
Same-subscription consumption up to already-reserved quantity omits additional
quota checks; over-allocation is different. Therefore do not implement the quota
adapter as `unused_vcpus >= requested_vcpus` without accounting for covered
reserved capacity. This starter excludes cross-subscription sharing (CAP-013).
Source: [On-demand capacity reservation](https://learn.microsoft.com/en-us/azure/virtual-machines/capacity-reservation-overview), accessed 2026-11-03.

[Documented] Family and total regional vCPU caps are separate, as are quota and
capacity. Source: [Check vCPU quotas](https://learn.microsoft.com/en-us/azure/virtual-machines/quotas), accessed 2026-11-03.

Evidence retrieved using Microsoft Learn MCP search and Azure MCP documentation
fetch; general Azure code-generation guidance also retrieved. No REST/SDK API
version is exercised, no live subscription queried, and no programme POC passed.
Integration must pin and validate its Compute API version and supported SKUs.

## Gates

**Baseline compliance (SK-01):** ALIGNED for this limited advisory helper;
full placement remains BLOCKED until customer-level integration is validated.
PLC-001/002/005/012 are exercised locally; PLC-007/013/015 depend on upstream
normalization, aggregate evaluation, persisted CRV and pipeline integration.

**Deployment policy:** N/A for this offline helper; it loads no
deployment configuration and makes no readiness assertion.

**Hard constraints:** BLOCKED for real placement until authoritative evaluation.

| HC | Local treatment | Real-placement gate |
|---|---|---|
| HC-1 REGION_SEPARATION | Consume upstream verdict | OPEN |
| HC-2 CAPACITY_FLOOR | Demand check plus upstream protected floor | OPEN |
| HC-3 QUOTA_FLOOR | Both admission verdicts plus upstream floor | OPEN |
| HC-4 DR_SEPARATION_CLASS | Consume upstream verdict | OPEN |
| HC-5 ZONE_AVAILABILITY | Exact zone match plus upstream diversity check | OPEN |
| HC-6 DR_COVERAGE_FLOOR | Consume upstream combined-capacity verdict | OPEN |
| HC-7 DR_FLOOR_INTEGRITY | Consume upstream protected-earmark verdict | OPEN |
| HC-8 GEOGRAPHY_CONTAINMENT | Target geography match plus upstream CRV check | OPEN |
| HC-9 STANDARD_REGION_ONLY | Check supplied classification | OPEN |
| HC-10 CROSS_GEO_EXTENSION_PATH_APPROVED | Consume upstream approval verdict | OPEN |
| HC-11 AVAILABILITY_SET_INELIGIBLE | Consume upstream eligibility verdict | OPEN |

**Formula check (SK-06):** Worked scores 0.8 and 0.7625 verified by unit tests.
**DR sizing (SK-09):** N/A; no sizing performed. Any expected-DR input must be
normalized upstream from approved max-not-sum sizing (DR-017), not invented here.
**Open items touched:** DEC-003 (approval workflow), POC-013 (full CRV/DPB flow).
The baseline resolver also reported older baseline copies; they were not used.

## Integration Boundaries

Before using ranked candidates to commit a placement, implement joint multi-SKU,
multi-zone and multi-domain feasibility without double-counting quota/capacity;
the distribution model (including two-region and Middle East rules), legal DR
carve-outs, dedicated DR Foundation, approved normalization, transactional seed
reuse and persistence, atomic capacity claims, and fresh deploy-time checks.
CRG provisioning/growth is a separate workflow requiring provider quota and actual
Azure allocation success; missing reserved capacity is not proof growth is impossible.

### WAF

| Pillar | Assessment / remaining risk |
|---|---|
| Reliability | Filters before scoring, never relocates a fixed binding; real HC evaluator and atomic claims still required. |
| Security | No credentials or live access; adapters must authorize identities and validate approvals. |
| Cost Optimization | No resources provisioned; protected buffers remain upstream policy inputs. |
| Operational Excellence | Rejection reasons and stable ranking; caller must persist snapshot, decision and policy evidence. |
| Performance Efficiency | Local linear evaluation plus ranking; no management-plane API calls. |