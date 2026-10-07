# Evidence rules and open-items register

## Contents
- Evidence tags
- Tagging rules
- Azure facts locked by the baseline
- Open-items register
- Known repo inconsistencies
- Escalation

## Evidence tags

One tag per claim. The set unifies `Agents.md` (Documented/Tested/Derived/Assumed) and the hard-constraints reference (Documented/Derived/Decided/Undocumented).

| Tag | Meaning | Required citation |
|---|---|---|
| `[Documented]` | Stated by Microsoft Learn / Azure docs, or a normative baseline requirement | Learn URL + access date, or baseline code (e.g. `QUA-013`) |
| `[Tested]` | Observed in a POC run in this programme | POC ID + `Test-Results/` artefact |
| `[Decided]` | Explicit programme decision | DEC-xxx, ADR-xxx, or baseline version row |
| `[Derived]` | Logical consequence of tagged facts | The tagged facts it derives from |
| `[Assumed]` | Not documented, tested, or decided — lowest confidence | Owner + the POC/decision that would close it |

`[Undocumented — architectural judgement]` in older docs maps to `[Assumed]` (WAF best practice is guidance, not platform fact).

## Tagging rules

1. Azure behaviour claims (limits, API semantics, quota consumption, zone mapping, sharing scope) are never untagged.
2. `[Documented]` from the baseline is acceptable for programme rules; for platform behaviour prefer a Learn citation as well — the baseline itself cites Learn (v2.5).
3. A `[Derived]` claim built on any `[Assumed]` input is `[Assumed]`.
4. Numbers (buffers, percentages, intervals, weights) are `Configurable` unless the baseline fixes them — cite the C-xx item or the calculation logic reference constant.
5. Preview features: tag the feature state explicitly (`Preview`, API version) and never make it a production dependency.
6. Undefined formula terms: write `SPEC GAP:` + term + where it is used + what is missing (source, scope, data type). Do not propose a definition as if decided; options may be listed, each tagged `[Assumed]`.

## Azure facts locked by the baseline

Current as of baseline v2.5 (24 Sep 2026; amended 7 Oct 2026). Re-read the baseline if its version moved.

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
| One region fails at a time; DR destination sized max-not-sum | DR-001, DR-017, App. D | Decided |
| Middle East DR is cross-geo into a weighted-selected Europe Standard region | DEC-001, DR-020, PLC-010b, A-ME1 | Decided (residency clearance Assumed) |
| Reconciliation reference interval 6 min, configurable | CAP-006 | Configurable |
| No multi-cloud; all-of-Azure-down out of scope | §2, §24 | Decided |
| γ denominator `total_customers(g)` = distinct customers with any env (Prod/CVAL/DR) provisioned or deploying in geography g; one live count shared by PS_Prod/PS_NonProd/PS_DR; γ = 1 when the count is 0 | PLC-012, A.10 | Decided (7 Oct 2026; decrement on decommission and cross-geo DR counting Assumed) |

## Open-items register

Any output touching these must flag them, not resolve them silently.

| ID | Item | State | Effect on design |
|---|---|---|---|
| POC-001 | Consumer quota behaviour on shared CRGs | Documented; version confirmation pending | Cite QUA-013; note the API-version check |
| POC-002 | Sharing consumption order | Open | No design may depend on a particular order |
| POC-003 | Logical↔physical zone mapping for consumer into provider zonal reservation | Open | Zone alignment must be validated per subscription pair |
| POC-004 | Reconciliation under throttling | Open | Retry/backoff design is `[Assumed]` until tested |
| POC-005 | Guarantee behaviour across VM states | Open | State-machine edges involving stop/deallocate are `[Assumed]` |
| POC-006 | DR subscription topology | Open | Keep both topologies viable |
| POC-007 | Bootstrap sizing per product | Open | Bootstrap numbers are placeholders |
| POC-008 / 009 | Production quota / reservation buffers | Open | Buffers stay configurable inputs |
| POC-010 | Production reconciliation interval | Open | 6 min is reference only |
| POC-011 | Max-not-sum overcommit safety | Open | Quantify two-region-failure residual risk; C-11 sum override exists |
| DEC-002 | DR drill duration & failback | Open | Support both extended run and early failback |
| DEC-003 | Geography-exception approver | Open | Model the approval as a pluggable step |
| DEP-001 | Sharing Preview → GA | External | Design must work with and without sharing |
| GAP-γ | `total_customers` in γ | **Closed 7 Oct 2026** — decided as PLC-012 / A.10 | Cite PLC-012; see the locked-facts table above |
| GAP-JPE | Japan East in-scope status | Pending confirmation | Treat as configurable catalogue entry |
| GAP-SAE | Saudi Arabia East (future region, GA target Q4 2026 per mockup builder) | `[Assumed]` timing | Keep future-dated; do not place customers |

## Known repo inconsistencies

Check these before citing; fix through the owning doc, not in your output.

| Where | Issue | Authoritative |
|---|---|---|
| Uploaded baseline vs repo baseline | Uploaded copy can lag the repo (seen 17 Sep and again at v2.5) | Highest Document Control version |
| `Skills.md` SK-03 HC table | HC-1..HC-11 labels (CAP-003 … PLC-010b) do not match the hard-constraints reference names (REGION_SEPARATION … AVAILABILITY_SET_INELIGIBLE) | `acrme_hard_constraints_reference.md` Part 2 |
| `Skills.md` SK-01 Step 2 | Cites baseline §26–§32, which the current baseline does not contain | Current baseline ToC |
| Older docs | Say "baseline v2.4" for content now in v2.5 | Current baseline |

## Escalation

Stop and report (do not resolve in place) when you find: undocumented Azure behaviour a design depends on, a Learn-vs-baseline conflict, an HC conflict, a new spec gap, or a stale baseline copy. Report: what, where (file + section/code), evidence, proposed owner, and the POC/decision that would close it.
