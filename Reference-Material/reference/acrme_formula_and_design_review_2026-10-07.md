# ACRME requirements and design review — formula correctness

**Type:** Review
**Baseline:** v2.5 (amended 7 Oct 2026) — resolved via check_grounding.py on 2026-10-07
**Phases touched:** P1, P2, P3, P4 (downstream impact: a wrong quota or scoring formula in P1/P2 changes DR earmark and placement in P4)
**Codes in scope:** CAP-003, CAP-004, CAP-009, CAP-018, CAP-023, QUA-002, QUA-007, QUA-013, PLC-007, PLC-011, PLC-012, DR-001, DR-017, A.1–A.10
**Status:** For review

Capacity Reservation Sharing remains Preview (CAP-013, DEP-001). That limitation is accepted and is not a finding. Archive material (August 2026 fixed-percentage DR and the isolated Prod quota group) was read only to see what the current baseline already replaced. Archived decisions are not recommendations.

## 1. Question

Which live formulas are mathematically correct for the job the baseline assigns them, which contradict a higher-ranked source, and which simpler formula should replace them?

## 2. Findings

| # | Finding | Tag | Source |
|---|---|---|---|
| F1 | A.1, A.3, A.6, A.7, and A.8 are the right shapes for their stated jobs, with the guards in §4 | [Decided] | Baseline Appendix A; DR-001, DR-017, CAP-003 |
| F2 | A.4 counts only the VM-family cap. QUA-007 and Microsoft Learn require the lesser of family remaining and total regional vCPU remaining. Learn also counts a regional VM-count quota, which no formula includes | [Documented] | QUA-002, QUA-007; https://learn.microsoft.com/azure/virtual-machines/quotas accessed 2026-10-07 |
| F3 | A.5 treats every requested unit as new quota. Learn omits the quota check for VM deployments up to the reserved quantity, because the reservation already consumed that quota | [Documented] | https://learn.microsoft.com/azure/virtual-machines/capacity-reservation-overview accessed 2026-10-07 |
| F4 | Baseline A.9 `round(count / zones)` does not conserve VM count. The calculation-logic share formula does, and the two documents disagree | [Derived] | Baseline A.9 vs Calculation Logic Reference Scenario 21 |
| F5 | γ’s shared denominator (PLC-012, A.10) does not measure environment fairness when customers do not all have that environment. The “increment the count” sentence contradicts COUNT DISTINCT | [Derived] | PLC-012, A.10 |
| F6 | PS_NonProd adds the same headroom ratio twice (weight 0.45). PS_Prod divides NonProd free slots by Prod quantity and is undefined at seed quantity 0. ε = az_count/3 is constant inside a 3-zone geography, so it cannot change argmax | [Decided] | Calculation Logic Reference Scenarios 1, 5, 6; CAP-022 |
| F7 | Utilisation thresholds of 0.20 and 0.35 are a second sizing rule that fights Target = Allocated + Buffer. The walkthrough divides 208 by 500 while the example reservation is 200 | [Derived] | Scenario 12; comprehensive walkthrough |
| F8 | The quota pool multiplies a reservation quantity that already includes the reservation buffer by another (1 + 0.20), and the emergency term is 0.30 times summed source demand | [Derived] | Scenario 8; DR-017 |
| F9 | Shrink has three floors (target, allocated, associated). Learn says a well-formed decrease succeeds regardless of how many VMs are associated | [Documented] | CAP-004; Scenario 16; https://learn.microsoft.com/azure/virtual-machines/capacity-reservation-modify accessed 2026-10-07 |
| F10 | Scenario 14’s Compute limits (250 reads / 5 min, 1,200 writes / hour) are not the current ARM token-bucket limits or the current Compute token-bucket limits | [Documented] | https://learn.microsoft.com/azure/azure-resource-manager/management/request-limits-and-throttling and https://learn.microsoft.com/azure/virtual-machines/compute-throttling-limits accessed 2026-10-07 |
| F11 | Appendix B’s $54k/month for 150 idle VMs and $78k/year for a 5% reserve are not the same unit price. Appendix D’s 40–50% platform saving assumes every destination protects two sources; a two-region geography has one source, so A.8 equals 1 | [Derived] | Appendix B, Appendix D, A.8 |
| F12 | The TDD names the PS_DR divisor `dr_ratio_target`, which is the retired Scenario 15 constant. The calculation reference calls the same input `dr_coverage_target` | [Decided] | TDD §8.2; Scenario 6 vs Scenario 15 |

## 3. Baseline position

ALIGNED for A.1, A.3, A.6, A.7, A.8 under DR-001, CAP-023 (one reservation per VM size per zone; zones fixed at creation; a no-zone group is pinned to one zone), and QUA-013 (consumer quota). Those match Learn as of 2026-10-07: [capacity reservation overview](https://learn.microsoft.com/azure/virtual-machines/capacity-reservation-overview), [create considerations](https://learn.microsoft.com/azure/virtual-machines/capacity-reservation-create), [quotas](https://learn.microsoft.com/azure/virtual-machines/quotas).

CONFLICT: A.4 versus QUA-007; A.9 versus Scenario 21; CAP-004 shrink floor versus the modify article; Scenario 14 versus current throttle docs; PLC-012’s increment sentence versus A.10.

NOT COVERED: behaviour of the regional VM-count quota against a capacity reservation; cross-geography customer counting (already `[Assumed]` for Middle East DR).

## 4. Conflicts and gaps

- CONFLICT: A.4 is family-only. QUA-007 already states the correct rule: available quota is the lesser of remaining VM-family vCPU and remaining total regional vCPU on the deploying subscription. Learn adds a third cap, the regional VM count ([quotas](https://learn.microsoft.com/azure/virtual-machines/quotas), accessed 2026-10-07). `[Documented]`
- CONFLICT: Learn quota usage includes cores in use both allocated and deallocated. A.4 says “current usage” and does not name which VM states count. `[Documented]`
- CONFLICT: Baseline A.9 uses absolute VM skew after `round`. Scenario 21 uses share drift with tolerance 0.10 (10 percentage points) and greatest-deficit-first among eligible zones. Rank order says the baseline wins until it is changed. The baseline formula is the one that fails a conservation check.
- CONFLICT: CAP-004 refuses to lower reserved quantity below the associated count. The modify article says a well-formed reduction succeeds no matter how many VMs are associated, and those VMs then sit outside the SLA (overallocation, CAP-018). `[Documented]`
- SPEC GAP: zero denominators. α, β, `coverage_ratio`, A.8, and Quota_Score_DR divide by `quantity`, `quota_limit`, `Destination_DR_Requirement`, or `dr_coverage_target`. Seed reservations are created at quantity 0 (CAP-022). No formula states the result. γ’s zero case is defined (PLC-012, A.10): γ = 1.
- SPEC GAP: `utilisation` in Scenario 12 has no definition (allocated/reserved, allocated/target, or headroom fraction) and no unit. The walkthrough uses 208/500 while reserved quantity in that example is 200.
- SPEC GAP: C-13 tolerance unit. Baseline A.9 compares a VM-count skew to the tolerance. Scenario 21 compares a share in the range 0–1 to 0.10. The same config value means different triggers.
- POC needed: POC-005 (association and power state versus shrink), POC-006 (whether Tier 2 is quota-neutral on the deploying subscription or only on the group), POC-011 (max-not-sum when two regions fail).

### Worked checks

**A.6 / A.8 (passes).** Portions 120 and 80. Requirement = max(120, 80) = 120. Ratio = (120+80)/120 = 1.667. One source of 120 gives requirement 120 and ratio 1. There is no max-versus-total saving in a two-region geography.

**A.9 (fails conservation).** 10 VMs, 3 zones. `round(10/3) = 3`, and 3+3+3 = 9. The distribution 4, 3, 3 is optimal and still has max absolute skew 1 against those targets, so a tolerance of 0 never settles. Largest remainder assigns 4, 3, 3. Scenario 21 shares for 4/10, 3/10, 3/10 have max drift 0.067, which is under a 0.10 share tolerance, so it correctly does not rebalance an optimal layout.

**γ (defined, wrong population).** 100 distinct customers in the geography, 20 of them with CVAL, all 20 in one region. A.10 γ = clamp(1 − 20/100, 0, 1) = 0.80. An environment-scoped denominator gives clamp(1 − 20/20, 0, 1) = 0. The region holds every CVAL customer and still scores as mostly fair. PLC-012, A.10.

**Quota stack (illustrative).** Allocated 100, reservation buffer 20, so reserved quantity = 120 (A.1). Pool term = 120 × (1 + 0.20) = 144, which is 1.44 × allocated, not 1.20 × allocated.

**Appendix B (does not scale).** 150 VMs at $54,000/month is $360 per VM-month. 5% of 500 VMs is 25 VMs, which at that rate is $108,000/year. The appendix states about $78,000/year. Both figures cannot be the same price.

**Throttle (stale).** Current ARM public-cloud reads are a bucket of 250 with refill 25 per second, per subscription and service principal, not 250 reads per 5 minutes. Writes are a bucket of 200 with refill 10 per second, not 1,200 per hour. Compute adds its own per-region token buckets (for example Low-cost Get VM refills 8,000 per minute at subscription scope). `[Documented]`

## 5. Implications for design

Replace A.4 and A.5 with one quota function. Family remaining and regional-vCPU remaining are both required (QUA-002). For a VM deployed into an existing reservation, quota is required only for the quantity above reserved capacity. For a reservation create or grow, quota is required for the increase in `capacity`. `[Documented]`

Replace baseline A.9’s `round` with largest-remainder targets so the targets sum to the VM count, or adopt Scenario 21’s share formula and state the tolerance as a fraction. `argmin` of VM count is equivalent to greatest deficit when every zone has the same target; keep the eligibility filter from Scenario 21, which baseline A.9 omits.

Score γ with the count of customers who have that environment in the geography. Keep the zero rule from PLC-012, A.10 (γ = 1 when the denominator is 0). Delete the “increment on each environment” sentence; A.10 is a distinct-customer count, and a second environment for the same customer must not add another customer. Cross-geo DR counting stays `[Assumed]` until specified.

For PS_NonProd, drop the duplicated δ term and renormalise. The pilot variant in Scenario 5 already does this. For PS_Prod, α should be prod free capacity divided by the requested size (or by max(quantity, 1)), computed on the pre-placement snapshot. Measuring NonProd free over Prod quantity prefers a small Prod reservation with a large NonProd surplus over a large Prod reservation, and it divides by zero on every CAP-022 seed. The rationale that Prod headroom would be circular is incorrect: the score is a snapshot taken before the placement (design principle 8). Inside a geography where every candidate has 3 zones, drop ε or replace it with a per-zone free-capacity fraction that can differ by region.

Delete Scenario 12’s 0.20 / 0.35 utilisation triggers. Scale up when Reserved Quantity < Target (A.3 > 0) and scale down only when Reserved Quantity > Target and the CAP-009 guards pass. One rule, no second threshold.

Size the quota pool from allocated demand plus the quota buffer, not from reserved quantity times another growth factor. Set the DR earmark to A.6. Keep emergency headroom as an explicit extra, and define it as a fraction of the max portion, not of the summed portions, unless the scope has the C-11 override.

State one shrink floor. If the programme wants deallocated associated VMs to keep a guarantee, the floor is the associated count and the achievable target is max(Allocated + Buffer, Associated Count). If it follows Learn, quantity may fall below the associated count and those VMs are overallocated (CAP-018). Do not leave both in force.

Replace Scenario 14’s fixed 250/1,200 figures with the ARM token bucket plus the Compute policy that matches the API being called, and read `Retry-After` (POC-004). `[Documented]`

Rename the TDD PS_DR divisor to `dr_coverage_target` so it cannot be implemented as the retired 0.30–0.40 ratio.

## 6. Open questions

1. Does the regional VM-count quota bind capacity-reservation quantity, or only VM instances? Owner: POC Validation. Close with a usage read on a test subscription.
2. Which VM power states does “current usage” in A.4 include? Learn includes deallocated cores for vCPU quota. Owner: Architect. Close against the quotas article and POC-005.
3. Is Tier 2 quota-neutral on the deploying subscription? Group-level arithmetic can net to zero while the DR subscription still lacks local quota (QUA-007). Owner: POC-006.
4. What is the numeric default of `dr_coverage_target`? It is named and not given a value. Owner: Architect.

## 7. Gates

**Baseline compliance (SK-01):** BLOCKED until A.4 matches QUA-007 and A.9 has one formula.

| Code | Baseline statement | This review | Status |
|---|---|---|---|
| CAP-003 | Target = Allocated + Buffer | A.1 is correct; Scenario 12 adds a conflicting trigger | CONFLICT |
| QUA-007 | Available quota is the lesser of the two vCPU remainings | A.4 implements only the family term | CONFLICT |
| PLC-011 | Even share 1/zone_count | Two incompatible formulas (A.9 and Scenario 21) | CONFLICT |
| PLC-012 | Distinct customers per geography; γ = 1 at zero | Formula is defined; increment sentence disagrees; denominator dilutes fairness | EXTENDS |
| DR-017 | Destination requirement is the max portion | A.6 is correct; emergency quota term uses summed demand | CONFLICT |
| CAP-004 | Do not shrink below associated count | Stricter than Learn’s modify rule | CONFLICT |
| CAP-023 | Zonal CRG structure | Matches Learn | ALIGNED |

**Hard constraints (HC reference Part 2):** COMPLIANT for this review (no design change is being adopted here).

| HC | Name | Affected | PASS/FAIL/N/A | Evidence |
|---|---|---|---|---|
| HC-1 | REGION_SEPARATION | Placement scoring | N/A | Review only |
| HC-2 | CAPACITY_FLOOR | A.1 target | PASS | Formula matches CAP-003; trigger conflict is separate |
| HC-3 | QUOTA_FLOOR | A.4 | FAIL | Family-only available quota can pass HC-3 while the regional vCPU cap is exhausted (QUA-002) |
| HC-4 | DR_SEPARATION_CLASS | DR earmark | N/A | Not re-derived |
| HC-5 | ZONE_AVAILABILITY | A.9 | PASS | Zone isolation still required; the skew formula is the defect |
| HC-6 | DR_COVERAGE_FLOOR | A.6 | PASS | Max portion, not a fixed ratio |
| HC-7 | DR_FLOOR_INTEGRITY | Pool formula | PASS | Earmark is present; the emergency term is the defect |
| HC-8 | GEOGRAPHY_CONTAINMENT | γ scope | N/A | Cross-geo count remains `[Assumed]` |
| HC-9 | STANDARD_REGION_ONLY | Scoring candidates | N/A | Unchanged |
| HC-10 | CROSS_GEO_EXTENSION_PATH_APPROVED | Middle East DR | N/A | DEC-001 stands |
| HC-11 | AVAILABILITY_SET_INELIGIBLE | CAP-020 | PASS | Matches Learn: availability sets are not supported on capacity reservations |

**Formula check (SK-06):** A.6 recomputed as max(120, 80) = 120. A.8 = 200/120 ≈ 1.67. A.9 conservation check fails (targets sum to 9 for 10 VMs). γ dilution check: 0.80 versus 0.
**DR sizing (SK-09):** max-not-sum holds for A.6. It does not hold for `emergency_transfer_headroom`, which scales summed source demand by 0.30.
**Open items touched:** POC-004, POC-005, POC-006, POC-011. Sharing preview (DEP-001) is accepted and not treated as a defect.

### WAF

| Pillar | Assessment | Risk | Mitigation |
|---|---|---|---|
| Reliability | Quota and capacity are separate checks, which matches the capacity-resilience guide (https://learn.microsoft.com/azure/well-architected/design-guides/capacity-resilience, accessed 2026-10-07). A.6 matches the single-region failure assumption | A.4 can report ready when the other vCPU cap is exhausted. Shrink-floor disagreement can drop a deallocated VM out of the reservation SLA | Use the min of both caps. Pick one shrink floor |
| Security | No new identity or secret finding in the formulas | N/A | N/A |
| Cost Optimization | A.6 avoids paying for simultaneous failures the model excludes | Stacked buffers and a 20% utilisation trigger grow idle reservations. Appendix B prices do not support the dollar claims as stated | Size from A.1 and A.6 only. Reprice Appendix B from a price sheet |
| Operational Excellence | Weight-sum validation is a sound gate for scores that must stay in [0, 1] | Two A.9 formulas and two names for the DR coverage divisor will be implemented differently | One formula, one name |
| Performance Efficiency | Reconciliation every 6 minutes is configurable (CAP-006) | The API budget uses retired throttle ceilings, so the call plan is not grounded | Budget against the current token buckets |

## 8. Traceability

| Requirement | Section here | Test / POC |
|---|---|---|
| CAP-003, A.1–A.3 | F1, F7, F9 | Recompute target, deficit, and the utilisation example |
| QUA-002, QUA-007, A.4–A.5 | F2, F3 | Deploy at the family cap with regional vCPU exhausted; deploy inside existing reserved quantity |
| PLC-011, A.9 | F4 | 10 VMs across 3 zones |
| PLC-012, A.10 | F5 | 20 CVAL customers inside 100 geography customers |
| DR-017, A.6–A.8 | F1, F8, F11 | 120 and 80 portions; single-source ratio |
| Scenario 14 | F10 | Compare a read burst with current ARM headers |

## 9. Baseline-change candidates

Do not edit the baseline in this review. Proposed replacements:

1. A.4 becomes `Available Quota = min(family limit − family usage, regional vCPU limit − regional vCPU usage)`, with usage including deallocated cores, matching Learn.
2. A.5 becomes `Quota Deficit = max(0, Uncovered Units − Available Quota)`, where uncovered units are the part of the request above the reservation’s current capacity.
3. A.9 becomes largest-remainder zone targets, or the Scenario 21 share formula, with tolerance declared as a fraction of VMs.
4. PLC-012 operational text drops “incremented” and states that the count is recomputed as the distinct-customer count in A.10.
5. Scenario 12 utilisation thresholds are removed in favour of A.3.
