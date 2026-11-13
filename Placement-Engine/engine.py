"""ACRME Placement Engine — Core CRV → DPB Pipeline.

Implements the two-scope placement pipeline:
  Phase 1: CRV (Customer Region Vector) — customer scope
  Phase 2: DPB (Domain Placement Binding) — domain scope

Per v4.0 baseline F.11/F.12, PLC-013..PLC-016.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Optional

from hard_constraints import run_crv_hc_gate, run_dpb_hc_gate
from models import (
    CRGSetType, CRVResult, Customer, DPBResult, DomainGroup,
    DistributionModel, Environment, HCResult, PlacementDecision,
    PlacementPolicy, PlacementReport, RegionSnapshot,
    ScoringDetail, ZonePlacement,
)
from scoring import score_region


# ---------------------------------------------------------------------------
# Phase 1 — CRV Resolution
# ---------------------------------------------------------------------------

def _eligible_regions(
    regions: list[RegionSnapshot],
    customer: Customer,
    env: Environment,
    demand_vcpu: int,
    prod_region_id: str | None = None,
    cross_geo_dr: bool = False,
) -> list[tuple[RegionSnapshot, list[HCResult]]]:
    """Filter regions through HC gate; return (region, hc_results) pairs."""
    eligible = []
    for r in regions:
        hc_results = run_crv_hc_gate(r, customer, env, demand_vcpu,
                                      prod_region_id, cross_geo_dr=cross_geo_dr)
        eligible.append((r, hc_results))
    return eligible


def _select_best(
    candidates: list[tuple[RegionSnapshot, list[HCResult]]],
    env: Environment,
    policy: PlacementPolicy,
) -> tuple[list[ScoringDetail], Optional[str]]:
    """Score eligible candidates and return (all_scores, best_region_id)."""
    all_scores: list[ScoringDetail] = []
    best_score = -1.0
    best_id = None

    for region, hc_results in candidates:
        detail = score_region(region, env, policy)
        detail.hc_results = hc_results
        all_pass = all(hc.passed for hc in hc_results)
        detail.hc_passed = all_pass

        if all_pass:
            detail.decision = PlacementDecision.NOT_EVALUATED  # will be set later
            if detail.total_score > best_score:
                best_score = detail.total_score
                best_id = region.region_id
        else:
            detail.decision = PlacementDecision.REJECTED_HC
            detail.rejection_reasons = [
                f"{hc.hc_id}: {hc.detail}" for hc in hc_results if not hc.passed
            ]

        all_scores.append(detail)

    # Mark selected / rejected_scoring
    for s in all_scores:
        if s.decision == PlacementDecision.REJECTED_HC:
            continue
        if s.region_id == best_id:
            s.decision = PlacementDecision.SELECTED
        else:
            s.decision = PlacementDecision.REJECTED_SCORING
            s.rejection_reasons = [f"Score {s.total_score:.4f} < winner {best_score:.4f}"]

    return all_scores, best_id


def resolve_crv(
    customer: Customer,
    regions: list[RegionSnapshot],
    policy: PlacementPolicy,
) -> CRVResult:
    """Phase 1: resolve the Customer Region Vector."""
    geo_regions = [r for r in regions if r.geography == customer.geography]
    if not geo_regions:
        return CRVResult(
            customer_id=customer.customer_id,
            geography=customer.geography,
            distribution_model=DistributionModel.THREE_REGION,
            warnings=["No regions found for geography"]
        )

    dist_model = geo_regions[0].distribution_model
    crv = CRVResult(
        customer_id=customer.customer_id,
        geography=customer.geography,
        distribution_model=dist_model,
    )

    # --- Prod selection ---
    if customer.supplied_prod_region:
        # Exact-region path (PLC-001 default)
        crv.path_used = "exact_region"
        prod_region = next(
            (r for r in geo_regions
             if r.region_id == customer.supplied_prod_region), None)
        if prod_region is None:
            crv.warnings.append(
                f"Supplied prod region {customer.supplied_prod_region} "
                f"not found in catalogue")
            return crv

        # HC gate only — PS_Prod recorded for audit, not used to select
        hc_results = run_crv_hc_gate(
            prod_region, customer, Environment.PROD,
            customer.total_prod_demand)
        prod_detail = score_region(prod_region, Environment.PROD, policy)
        prod_detail.hc_results = hc_results
        prod_detail.hc_passed = all(hc.passed for hc in hc_results)

        if prod_detail.hc_passed:
            prod_detail.decision = PlacementDecision.SELECTED
            crv.prod_region = prod_region.region_id
        else:
            prod_detail.decision = PlacementDecision.REJECTED_HC
            prod_detail.rejection_reasons = [
                f"{hc.hc_id}: {hc.detail}"
                for hc in hc_results if not hc.passed
            ]
            crv.warnings.append(
                f"Supplied prod region {prod_region.region_id} failed HC gate")
        crv.prod_scoring = [prod_detail]
    else:
        # Geography path (PLC-002 exception)
        crv.path_used = "geography"
        candidates = _eligible_regions(
            geo_regions, customer, Environment.PROD,
            customer.total_prod_demand)
        crv.prod_scoring, crv.prod_region = _select_best(
            candidates, Environment.PROD, policy)
        if crv.prod_region is None:
            crv.warnings.append(
                "No eligible Prod region found in geography")

    # --- CVAL / DR selection based on distribution model ---
    if dist_model == DistributionModel.TWO_REGION:
        # PLC-010a: deterministic co-location
        remaining = [
            r for r in geo_regions
            if r.region_id != crv.prod_region
            and r.classification.value == "standard"
        ]
        if remaining:
            co_region = remaining[0]
            crv.cval_region = co_region.region_id
            crv.dr_region = co_region.region_id

            cval_detail = score_region(co_region, Environment.CVAL, policy)
            cval_detail.decision = PlacementDecision.DETERMINISTIC
            cval_detail.hc_passed = True
            crv.cval_scoring = [cval_detail]

            dr_detail = score_region(co_region, Environment.DR, policy)
            dr_detail.decision = PlacementDecision.DETERMINISTIC
            dr_detail.hc_passed = True
            crv.dr_scoring = [dr_detail]
        else:
            crv.warnings.append(
                "2-region: no remaining standard region for CVAL/DR")

    elif dist_model == DistributionModel.CROSS_GEO_DR:
        # PLC-010b: CVAL co-locates with Prod (separate CRGs)
        crv.cval_region = crv.prod_region
        if crv.prod_region:
            cval_r = next(r for r in geo_regions
                          if r.region_id == crv.prod_region)
            cval_detail = score_region(cval_r, Environment.CVAL, policy)
            cval_detail.decision = PlacementDecision.CROSS_GEO
            cval_detail.hc_passed = True
            crv.cval_scoring = [cval_detail]

        # DR in destination geography (typically Europe)
        dest_geo = geo_regions[0].dr_destination_geography or "Europe"
        dr_candidates_raw = [
            r for r in regions
            if r.geography == dest_geo
            and r.classification.value == "standard"
        ]
        dr_candidates = _eligible_regions(
            dr_candidates_raw, customer, Environment.DR,
            customer.total_dr_demand, crv.prod_region,
            cross_geo_dr=True)
        crv.dr_scoring, crv.dr_region = _select_best(
            dr_candidates, Environment.DR, policy)
        for s in crv.dr_scoring:
            if s.decision == PlacementDecision.SELECTED:
                s.decision = PlacementDecision.CROSS_GEO

    else:  # THREE_REGION
        # CVAL selection
        cval_candidates_raw = [
            r for r in geo_regions
            if r.region_id != crv.prod_region
            and r.classification.value == "standard"
        ]
        cval_candidates = _eligible_regions(
            cval_candidates_raw, customer, Environment.CVAL,
            customer.total_cval_demand, crv.prod_region)
        crv.cval_scoring, crv.cval_region = _select_best(
            cval_candidates, Environment.CVAL, policy)

        # DR selection (must differ from both Prod and CVAL)
        dr_candidates_raw = [
            r for r in geo_regions
            if r.region_id != crv.prod_region
            and r.region_id != crv.cval_region  # 3-region: R_d ≠ R_c
            and r.classification.value == "standard"
        ]
        dr_candidates = _eligible_regions(
            dr_candidates_raw, customer, Environment.DR,
            customer.total_dr_demand, crv.prod_region)
        crv.dr_scoring, crv.dr_region = _select_best(
            dr_candidates, Environment.DR, policy)

    return crv


# ---------------------------------------------------------------------------
# Phase 2 — DPB Resolution
# ---------------------------------------------------------------------------

def _crg_set_type(env: Environment) -> CRGSetType:
    if env == Environment.PROD:
        return CRGSetType.PROD_DEDICATED
    else:
        return CRGSetType.CVDR_SHARED


def _crg_name(domain: DomainGroup, env: Environment,
              region_id: str, zone: int) -> str:
    env_tag = {
        Environment.PROD: "prod",
        Environment.CVAL: "cvdr",
        Environment.DR: "cvdr",
    }[env]
    short_region = region_id.replace(" ", "").lower()
    return f"crg-{domain.display_name.lower()}-{env_tag}-{short_region}-z{zone}"


def resolve_dpb(
    customer: Customer,
    crv: CRVResult,
    regions: list[RegionSnapshot],
    policy: PlacementPolicy,
) -> list[DPBResult]:
    """Phase 2: resolve DPB for each domain x environment."""
    results: list[DPBResult] = []

    env_region_map = {
        Environment.PROD: crv.prod_region,
        Environment.CVAL: crv.cval_region,
        Environment.DR: crv.dr_region,
    }

    for domain in customer.domain_groups:
        for env in [Environment.PROD, Environment.CVAL, Environment.DR]:
            region_id = env_region_map.get(env)
            if not region_id:
                results.append(DPBResult(
                    domain_token=domain.token,
                    environment=env,
                    region="NONE",
                    passed=False,
                    rejection_reasons=["No region assigned by CRV"],
                ))
                continue

            region = next((r for r in regions if r.region_id == region_id), None)
            if not region:
                results.append(DPBResult(
                    domain_token=domain.token,
                    environment=env,
                    region=region_id,
                    passed=False,
                    rejection_reasons=[f"Region {region_id} not in snapshot"],
                ))
                continue

            # Domain-specific demand
            if env == Environment.PROD:
                demand = domain.prod_vcpu_demand
                sub_id = domain.prod_subscription_id or f"sub-prod-{domain.token}"
            elif env == Environment.CVAL:
                demand = domain.cval_vcpu_demand
                sub_id = domain.cval_subscription_id or f"sub-cval-{domain.token}"
            else:
                demand = domain.dr_vcpu_demand
                sub_id = domain.dr_subscription_id or f"sub-dr-{domain.token}"

            # HC gate at domain scope
            hc_results = run_dpb_hc_gate(region, env, demand)
            all_pass = all(hc.passed for hc in hc_results)

            # Instance group
            ig = f"ig-{domain.display_name.lower()}-{env.value.lower()}-{region_id}"

            # CRG set
            crg_type = _crg_set_type(env)

            # Capacity sizing (F.1–F.3)
            buffer = 0  # C-3: TBD — parameterised, not assumed
            target_reserved = demand + buffer
            if env == Environment.PROD:
                current_reserved = region.prod_reserved
                current_allocated = region.prod_allocated
            elif env == Environment.CVAL:
                current_reserved = region.cval_reserved
                current_allocated = region.cval_allocated
            else:
                current_reserved = region.dr_reserved + region.fnd_dr_reserved
                current_allocated = region.dr_allocated + region.fnd_dr_allocated

            headroom = max(0, current_reserved - current_allocated)
            deficit = max(0, target_reserved - current_reserved)

            # Quota (F.4/F.5)
            if env == Environment.PROD:
                avail_quota = region.prod_quota_headroom
            elif env == Environment.CVAL:
                avail_quota = region.cval_quota_headroom
            else:
                avail_quota = region.dr_quota_headroom
            quota_deficit = max(0, demand - avail_quota)

            # Quota replenishment check (QUA-015)
            quota_replenish = False
            if env == Environment.PROD and region.prod_quota_limit > 0:
                util = region.prod_quota_used / region.prod_quota_limit
                quota_replenish = util >= policy.quota_group_replenish_threshold
            elif env == Environment.CVAL and region.cval_quota_limit > 0:
                util = region.cval_quota_used / region.cval_quota_limit
                quota_replenish = util >= policy.quota_group_replenish_threshold

            # Zone placement (F.9, PLC-016)
            zone_placements = []
            zone_count = region.availability_zones
            if zone_count > 0:
                target_per_zone = math.ceil(demand / zone_count)
                for z in range(1, zone_count + 1):
                    zc = region.zone_capacities.get(z)
                    zq = region.zone_quotas.get(z)
                    current_zone_vms = zc.allocated_vms if zc else 0
                    zone_avail = zc.available_slots if zc else 0
                    zone_quota = zq.family_available if zq else avail_quota

                    skew = current_zone_vms - target_per_zone
                    rebalance = abs(skew) > policy.zone_skew_tolerance

                    zone_placements.append(ZonePlacement(
                        zone_id=z,
                        target_vms=target_per_zone,
                        current_vms=current_zone_vms,
                        skew=skew,
                        rebalance_needed=rebalance,
                        crg_name=_crg_name(domain, env, region_id, z),
                        crg_set_type=crg_type,
                        available_slots=zone_avail,
                        quota_available=zone_quota,
                    ))

            rejection_reasons = []
            if not all_pass:
                rejection_reasons = [
                    f"{hc.hc_id}: {hc.detail}"
                    for hc in hc_results if not hc.passed
                ]

            results.append(DPBResult(
                domain_token=domain.token,
                environment=env,
                region=region_id,
                instance_group=ig,
                subscription_id=sub_id,
                crg_set_type=crg_type,
                target_reserved=target_reserved,
                headroom=headroom,
                deficit=deficit,
                available_quota=avail_quota,
                quota_deficit=quota_deficit,
                zone_placements=zone_placements,
                hc_results=hc_results,
                passed=all_pass,
                rejection_reasons=rejection_reasons,
                quota_replenish_needed=quota_replenish,
            ))

    return results


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

def run_placement(
    customer: Customer,
    regions: list[RegionSnapshot],
    policy: PlacementPolicy | None = None,
    dr_destination_regions: list[RegionSnapshot] | None = None,
) -> PlacementReport:
    """Run the full CRV → DPB placement pipeline for a customer."""
    if policy is None:
        policy = PlacementPolicy()
    if not policy.validate():
        raise ValueError(
            f"Policy weight-sum invariant violated: "
            f"{policy.alpha + policy.beta + policy.gamma + policy.delta + policy.epsilon:.4f} ≠ 1.0")

    crv = resolve_crv(customer, regions, policy)
    dpb = resolve_dpb(customer, crv, regions, policy)

    overall = "PASS"
    if crv.warnings:
        overall = "WARN"
    if any(not d.passed for d in dpb):
        overall = "FAIL"
    if crv.prod_region is None:
        overall = "FAIL"

    return PlacementReport(
        customer=customer,
        policy=policy,
        crv=crv,
        dpb_results=dpb,
        overall_status=overall,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
