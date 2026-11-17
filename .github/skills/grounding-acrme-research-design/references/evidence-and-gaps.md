# Evidence rules and open-items register

## Contents
- Evidence tags
- Tagging rules
- Azure facts locked by the baseline
- Deployment-standard facts and boundaries
- Open-items register
- Known repo inconsistencies
- Escalation

## Evidence tags

One tag per claim. The set unifies `Agents.md` (Documented/Tested/Decided/Derived/Assumed) and the hard-constraints reference (Documented/Derived/Decided/Undocumented).

| Tag | Meaning | Required citation |
|---|---|---|
| `[Documented]` | Stated by Microsoft Learn / Azure docs, a normative baseline requirement, or an explicit repository deployment-configuration value | Learn URL + access date for platform facts; baseline code for requirements; exact configuration path + effective date for settings |
| `[Tested]` | Observed in a POC run in this programme | POC ID + `Test-Results/` artefact |
| `[Decided]` | Explicit programme decision | DEC-xxx, ADR-xxx, or baseline version row |
| `[Derived]` | Logical consequence of tagged facts | The tagged facts it derives from |
| `[Assumed]` | Not documented, tested, or decided — lowest confidence | Owner + the POC/decision that would close it |

`[Undocumented — architectural judgement]` in older docs maps to `[Assumed]` (WAF best practice is guidance, not platform fact). A `[Documented]` configuration value documents intent in that file only; it does not prove approval, deployment, runtime enforcement, or Azure behavior. Use `[Decided]` only when a baseline, accepted ADR, or decision record confirms the decision.

## Tagging rules

1. Azure behaviour claims (limits, API semantics, quota consumption, zone mapping, sharing scope) are never untagged.
2. `[Documented]` from the baseline is acceptable for programme rules; for platform behaviour prefer a Learn citation as well — the baseline itself cites Learn (v4.0).
3. A `[Derived]` claim built on any `[Assumed]` input is `[Assumed]`.
4. Numbers (buffers, percentages, intervals, weights) are `Configurable` unless the baseline fixes them — cite the C-xx item or the calculation logic reference constant.
5. Preview features: tag the feature state explicitly (`Preview`, API version) and never make it a production dependency.
6. Undefined formula terms: write `SPEC GAP:` + term + where it is used + what is missing (source, scope, data type). Do not propose a definition as if decided; options may be listed, each tagged `[Assumed]`.
7. Microsoft Learn MCP and Azure MCP are retrieval/observation mechanisms, not evidence tiers. For documentation-backed claims retain the official URL, access date, applicable API version, scope restrictions, feature maturity, and capability used. Search snippets and generated best-practice advice do not prove platform behaviour or replace a fetched authoritative source.
8. A live read-only MCP observation is limited to its authorized scope and timestamp; it does not establish general behaviour or count as `[Tested]` without a POC ID and reproducible results artefact. Record failed/unavailable capabilities and official-documentation fallbacks explicitly; missing evidence never implies PASS.
9. For deployment policy, cite the exact `environment_v2.yaml` path and effective date (`2026-10-23`) and identify whether the value is configured, pending, or supported by a decision/proposal. Do not convert a configured value or user-confirmed proposal into an implemented control.

## Azure facts locked by the baseline

Current as of baseline v4.0.2 (17 Nov 2026). Re-read the baseline if its version moved.

| Fact | Code | Tag |
|---|---|---|
| Target = Allocated + Buffer; never associated-only | CAP-003 | Documented (baseline) |
| Deallocated associated VMs do not raise the target but still consume reservation quota until dissociated | CAP-004 | Documented |
| Reduce to 0, do not delete; retirement is a decommission workflow | CAP-009, CAP-010 | Decided |
| Sharing is Preview; production uses a reservation in the deploying subscription; preview scope = same region, explicit list, ≤100 subs, same/trusted tenant | CAP-013, DEP-001 | Documented |
| Logical zone numbers are per subscription | CAP-016 | Documented |
| Availability-Set VMs cannot use capacity reservations | CAP-020 | Documented |
| Seed matrix of count-0 reservations for every eligible SKU × AZ | CAP-022 | Decided |
| One zonal CRG per environment; zones fixed at creation; one reservation per VM size per zone; a CRG with no zones is pinned to a single zone | CAP-023 | Documented |
| Two quota caps: VM-family vCPU and total regional vCPU — both must be free | QUA-002, QUA-007 | Documented |
| A subscription belongs to one Quota Group; each transfer is one region × one family; deploy-time checks the subscription, not the group | QUA-003, QUA-004 | Documented |
| Consumer subscription must hold its own quota; provider needs quota to create/grow | QUA-013 | Documented |
| One region fails at a time; DR destination sized max-not-sum | DR-001, DR-017, App. C | Decided |
| Middle East DR is cross-geo into a weighted-selected Europe Standard region; dedicated DR capacity (not CVAL-sacrifice) | DEC-001, DR-020, PLC-010b, A-ME1 | Decided (residency clearance Assumed) |
| Reconciliation reference interval 6 min, configurable | CAP-006 | Configurable |
| No multi-cloud; all-of-Azure-down out of scope | §2, §26 | Decided |
| γ denominator `total_customers(g)` = distinct customers with any env (Prod/CVAL/DR) provisioned or deploying in geography g; one live count shared by all scoring; γ = 1 when the count is 0 | PLC-012, F.10 | Decided (7 Oct 2026; decrement on decommission and cross-geo DR counting Assumed) |
| Domain group model: capacity partitioned per (D,E) — domain group × environment | DOM-001..004 | Decided |
| Two-scope pipeline: CRV customer-scoped, DPB domain-group-scoped; PLC-015 gate | PLC-015 | Decided |
| Unified formulas F.1–F.13 replace former Appendix A / Appendix D | §21 | Decided |

## Deployment-standard facts and boundaries

The following are statements about the contents of `environment_v2.yaml` (effective 2026-10-23), not proof of Azure behavior or runtime enforcement. For each, cite the exact YAML key. Apply only when relevant to the deployment-policy question and check the linked pending decisions.

| Configured policy | YAML path / evidence | Review boundary |
|---|---|---|
| VM and AKS VMSS node-pool capacity requests use exact membership in the allowed-series list; unlisted series are excluded from the standard new-request path | `capacity_request_policy.deployment_scope`, `.allowed_vm_series` | The SKU/approval proposal says baseline incorporation and runtime implementation are pending. Series membership does not identify an exact VM size or establish technical readiness. |
| New capacity requests require Jira business and finance approval, with evidence of both approvals | `capacity_request_policy.approval` | Jira workflow/roles, approval scope/validity/change rules, exact size-to-series mapping, and Preview eligibility remain pending in the config/proposal. Do not apply this gate retroactively to protective reconciliation. |
| Deployment validation separately requires exact VM size, region/zone/subscription eligibility, reservation support when enforced, capacity, and both quota caps | `capacity_request_policy.deployment_validation` | Approval or allowlist membership cannot bypass any readiness check. |
| Standard compute subscriptions use blue/green rollout slots and require current/replacement capacity overlap validation before traffic cutover | `compute_subscription_policies.standard.cluster_capacity`, `.deployment` | Post-cutover color, rollback retention, and DR/rollout-headroom conflict handling are pending. |
| Compute and resource subscriptions scale out only when subscription-level limits are reached; DR clusters are provisioned before DR, run reduced steady-state capacity, and scale on approved declaration with capacity/quota validation | `compute_subscription_policies.standard`, `resource_subscription_policies.standard` | Do not assume unused rollout slots are available to DR or that scaling is authorized while conflict policy is pending. |
| CVAL/DR sharing is configured across subscriptions only within the same domain group and region; production capacity is excluded; sharing is Preview, not a production dependency, and the fallback is a reservation in the deploying subscription | `capacity_reservation_policies.standard.sharing` | Provider ownership is pending; POC-001/003/012 and DEP-001 gates remain relevant. Require physical-zone alignment and provider/consumer quota checks; do not infer sharing order or availability. |
| DR Foundation uses a dedicated DR compute subscription with always-present reserved bootstrap capacity and pre-staged quota, independent of sharing; cross-geography DR uses dedicated destination-region capacity | `capacity_reservation_policies.standard.dr_foundation`, `.cross_geography_dr` | Owner-confirmed production standard (17 Nov 2026). Require testing before readiness certification. POC-006 is for an alternate/exception topology only; see the baseline-change proposal. |
| Standard environment profiles are dedicated per environment and domain group; region eligibility is driven by geography entries and standard/restricted classifications | `environment_profiles.standard`, `geographies` | Region exceptions and pending catalogue decisions remain subject to baseline policy and approval; do not treat a configured region as live SKU/zone availability. |

## Open-items register

Any output touching these must flag them, not resolve them silently.

| ID | Item | State | Effect on design |
|---|---|---|---|
| POC-001 | Consumer quota behaviour on shared CRGs | Documented; version confirmation pending | Cite QUA-013; note the API-version check |
| POC-002 | Sharing consumption order | Open | No design may depend on a particular order |
| POC-003 | Logical↔physical zone mapping for consumer into provider zonal reservation | Open | Zone alignment must be validated per subscription pair |
| POC-004 | Reconciliation under throttling | Open | Retry/backoff design is `[Assumed]` until tested |
| POC-005 | Guarantee behaviour across VM states | Open | State-machine edges involving stop/deallocate are `[Assumed]` |
| POC-006 | Alternate DR subscription topology | Open — alternate/exception validation only | Dedicated DR compute subscription remains the production standard; POC results do not change it without a separate approved decision |
| POC-007 | Bootstrap sizing per product | Open | Bootstrap numbers are placeholders |
| POC-008 / 009 | Production quota / reservation buffers | Open | Buffers stay configurable inputs |
| POC-010 | Production reconciliation interval | Open | 6 min is reference only |
| POC-011 | Max-not-sum overcommit safety | Open | Quantify two-region-failure residual risk; C-11 sum override exists |
| POC-012 | Domain-scoped CRG sharing | Open | Validate same-domain CVAL/DR shared CRG consumption, consumer quota, logical-zone mapping, revocation within the consumer limit, and cross-domain isolation |
| POC-013 | Two-scope flow against a live multi-domain customer | Open | Validate CRV/DPB convergence, per-domain isolation, and readiness gates for a multi-domain customer |
| DEC-002 | DR drill duration & failback | Open | Support both extended run and early failback |
| DEC-003 | Geography-exception approver | Open | Model the approval as a pluggable step |
| DEP-001 | Sharing Preview → GA | External | Design must work with and without sharing |
| ENV-V2-002 | Deployment-standard pending decisions | Open | Keep sharing provider ownership, blue/green cutover/rollback conventions, rollout-headroom conflict handling, and listed `capacity_request_policy.pending_decisions` unresolved until authoritative closure evidence exists. POC-006 does not block the dedicated DR production standard. |
| ENV-V2-003 | Series/approval policy incorporation | Open | The linked proposal is user-confirmed policy input, but baseline incorporation and runtime implementation are pending; Jira workflow/scope, exact size-to-series mapping, and Preview eligibility are spec gaps in that proposal. |
| GAP-γ | `total_customers` in γ | **Closed 7 Oct 2026** — decided as PLC-012 / A.10 | Cite PLC-012; see the locked-facts table above |
| GAP-JPE | Japan East in-scope status | Pending confirmation | Treat as configurable catalogue entry |
| GAP-SAE | Saudi Arabia East (future region, GA target Q4 2026 per mockup builder) | `[Assumed]` timing | Keep future-dated; do not place customers |

## Known repo inconsistencies

Check these before citing; fix through the owning doc, not in your output.

| Where | Issue | Authoritative |
|---|---|---|
| Uploaded baseline vs repo baseline | Uploaded copy can lag the repo (seen 17 Sep and again at v2.5) | Highest Document Control version |
| Older design/reference/POC artefacts | Some still identify v2.4/v2.5/v3.0/v4.0/v4.0.1 as their normative basis and have not been reconciled to v4.0.2; see the current repository index for affected artefact groups | Current baseline (v4.0.2) |
| `Skills.md` / `Agents.md` | Programme instructions identify v4.0.2 as the current baseline | Current baseline |
| `environment.yaml` / `environment_v2.yaml` | Files differ because `environment.yaml` represents an earlier what-if process model | Owner confirmed `environment_v2.yaml` as the deployment standard on 17 Nov 2026; `environment.yaml` remains historical what-if input |

## Escalation

Stop and report (do not resolve in place) when you find: undocumented Azure behaviour a design depends on, a Learn-vs-baseline conflict, an HC conflict, a new spec gap, or a stale baseline copy. Report: what, where (file + section/code), evidence, proposed owner, and the POC/decision that would close it.
