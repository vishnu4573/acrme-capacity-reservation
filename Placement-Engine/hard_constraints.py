"""ACRME Placement Engine — Hard Constraint Gates.

Implements HC-1 through HC-11 per Hard Constraints Reference v1.1.
Each function returns an HCResult with pass/fail and detail.
"""
from __future__ import annotations

from models import (
    Customer, Environment, HCResult, PlacementPolicy,
    RegionClassification, RegionSnapshot,
)


def clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


# ---------------------------------------------------------------------------
# Individual HC checks
# ---------------------------------------------------------------------------

def hc1_capacity_available(region: RegionSnapshot, env: Environment,
                           demand_vcpu: int) -> HCResult:
    """HC-1: Region must have non-zero capacity for the environment."""
    if env == Environment.PROD:
        free = region.prod_free
    elif env == Environment.CVAL:
        free = region.cval_free
    else:
        free = region.dr_free + region.fnd_dr_free

    passed = free > 0
    return HCResult(
        hc_id="HC-1",
        description="Region must have non-zero capacity",
        passed=passed,
        detail=f"{env.value} free={free} vcpu (demand={demand_vcpu})"
    )


def hc2_capacity_sufficient(region: RegionSnapshot, env: Environment,
                            demand_vcpu: int) -> HCResult:
    """HC-2: Region must have sufficient free capacity for demand."""
    if env == Environment.PROD:
        free = region.prod_free
    elif env == Environment.CVAL:
        free = region.cval_free
    else:
        free = region.dr_free + region.fnd_dr_free

    passed = free >= demand_vcpu
    return HCResult(
        hc_id="HC-2",
        description="Region must have sufficient free capacity",
        passed=passed,
        detail=f"{env.value} free={free} vs demand={demand_vcpu}"
    )


def hc3_quota_sufficient(region: RegionSnapshot, env: Environment,
                         demand_vcpu: int) -> HCResult:
    """HC-3: Subscription must have sufficient quota."""
    if env == Environment.PROD:
        headroom = region.prod_quota_headroom
    elif env == Environment.CVAL:
        headroom = region.cval_quota_headroom
    else:
        headroom = region.dr_quota_headroom

    passed = headroom >= demand_vcpu
    return HCResult(
        hc_id="HC-3",
        description="Subscription must have sufficient quota",
        passed=passed,
        detail=f"{env.value} quota_headroom={headroom} vs demand={demand_vcpu}"
    )


def hc4_prod_not_dr_dest(region: RegionSnapshot,
                         customer_prod_region: str | None) -> HCResult:
    """HC-4: Prod region must not be the DR destination for the same customer."""
    passed = True  # gate — evaluated contextually during selection
    return HCResult(
        hc_id="HC-4",
        description="Prod region ≠ DR destination",
        passed=passed,
        detail="Checked during DR selection"
    )


def hc5_zone_support(region: RegionSnapshot, min_zones: int = 2) -> HCResult:
    """HC-5: Region must have ≥ min_zones availability zones."""
    passed = region.availability_zones >= min_zones
    return HCResult(
        hc_id="HC-5",
        description=f"Region must have ≥ {min_zones} availability zones",
        passed=passed,
        detail=f"zones={region.availability_zones}"
    )


def hc6_dr_coverage_floor(region: RegionSnapshot,
                          dr_demand: int) -> HCResult:
    """HC-6: DR destination must have sufficient coverage floor."""
    usable = region.dr_free + region.fnd_dr_free
    # Also count releasable CVAL capacity for co-located scenarios
    if region.cval_free > 0:
        usable += region.cval_free  # available via CVAL sacrifice
    passed = usable >= dr_demand if dr_demand > 0 else True
    return HCResult(
        hc_id="HC-6",
        description="DR destination coverage floor",
        passed=passed,
        detail=f"usable_dr={usable} (dr_free={region.dr_free} + fnd={region.fnd_dr_free} + cval_releasable={region.cval_free}) vs demand={dr_demand}"
    )


def hc7_dr_floor_integrity(region: RegionSnapshot) -> HCResult:
    """HC-7: DR Foundation must not be depleted by routine workloads."""
    passed = region.fnd_dr_free >= 0
    return HCResult(
        hc_id="HC-7",
        description="DR Foundation integrity",
        passed=passed,
        detail=f"fnd_dr_reserved={region.fnd_dr_reserved}, fnd_dr_allocated={region.fnd_dr_allocated}, fnd_dr_free={region.fnd_dr_free}"
    )


def hc8_geography_match(region: RegionSnapshot,
                        customer_geography: str) -> HCResult:
    """HC-8: Region must belong to the customer's geography."""
    passed = region.geography == customer_geography
    return HCResult(
        hc_id="HC-8",
        description="Region must be in customer geography",
        passed=passed,
        detail=f"region_geo={region.geography} vs customer_geo={customer_geography}"
    )


def hc9_standard_only(region: RegionSnapshot) -> HCResult:
    """HC-9: Only Standard regions are auto-selectable."""
    passed = region.classification == RegionClassification.STANDARD
    return HCResult(
        hc_id="HC-9",
        description="Only Standard regions are auto-selectable",
        passed=passed,
        detail=f"classification={region.classification.value}"
    )


def hc10_cross_geo_eligible(region: RegionSnapshot,
                            allowed_geos: list[str] | None = None) -> HCResult:
    """HC-10: Cross-geo region must be in an approved destination geography."""
    if allowed_geos is None:
        allowed_geos = ["Europe"]  # default per DR-020
    passed = region.geography in allowed_geos
    return HCResult(
        hc_id="HC-10",
        description="Cross-geo destination in approved geography",
        passed=passed,
        detail=f"region_geo={region.geography}, allowed={allowed_geos}"
    )


def hc11_env_separation(env: Environment,
                        region_hosts_prod: bool) -> HCResult:
    """HC-11: Prod region cannot host CVAL/DR for same customer (ENV-003)."""
    if env in (Environment.CVAL, Environment.DR):
        passed = not region_hosts_prod
    else:
        passed = True
    return HCResult(
        hc_id="HC-11",
        description="Prod region cannot host CVAL/DR (ENV-003)",
        passed=passed,
        detail=f"env={env.value}, region_hosts_prod={region_hosts_prod}"
    )


# ---------------------------------------------------------------------------
# Composite gate — CRV scope (customer aggregate)
# ---------------------------------------------------------------------------

def run_crv_hc_gate(
    region: RegionSnapshot,
    customer: Customer,
    env: Environment,
    demand_vcpu: int,
    prod_region_id: str | None = None,
    cross_geo_dr: bool = False,
) -> list[HCResult]:
    """Run HC checks relevant to CRV selection."""
    results = []

    if cross_geo_dr and env == Environment.DR:
        # Cross-geo DR: region is in a different geography by design (PLC-010b)
        # Replace HC-8 with HC-10 (cross-geo eligibility)
        # The allowed geos come from the source (ME) region's dr_destination_geography
        results.append(hc10_cross_geo_eligible(region))
    else:
        results.append(hc8_geography_match(region, customer.geography))
    results.append(hc9_standard_only(region))
    results.append(hc5_zone_support(region))
    results.append(hc1_capacity_available(region, env, demand_vcpu))

    if env == Environment.PROD:
        results.append(hc2_capacity_sufficient(region, env, demand_vcpu))
        results.append(hc3_quota_sufficient(region, env, demand_vcpu))
    elif env == Environment.CVAL:
        results.append(hc2_capacity_sufficient(region, env, demand_vcpu))
        # HC-11: cannot be in the Prod region
        if prod_region_id:
            results.append(hc11_env_separation(
                env, region.region_id == prod_region_id))
    elif env == Environment.DR:
        results.append(hc6_dr_coverage_floor(region, demand_vcpu))
        results.append(hc7_dr_floor_integrity(region))
        # HC-4: DR region ≠ Prod region
        if prod_region_id:
            passed = region.region_id != prod_region_id
            results.append(HCResult(
                hc_id="HC-4",
                description="DR region ≠ Prod region",
                passed=passed,
                detail=f"dr_candidate={region.region_id}, prod={prod_region_id}"
            ))
        # HC-11: cannot be in the Prod region
        if prod_region_id:
            results.append(hc11_env_separation(
                env, region.region_id == prod_region_id))

    return results


# ---------------------------------------------------------------------------
# DPB scope (per domain)
# ---------------------------------------------------------------------------

def run_dpb_hc_gate(
    region: RegionSnapshot,
    env: Environment,
    domain_demand_vcpu: int,
) -> list[HCResult]:
    """Run HC checks at DPB scope (per domain group)."""
    results = []
    results.append(hc2_capacity_sufficient(region, env, domain_demand_vcpu))
    results.append(hc3_quota_sufficient(region, env, domain_demand_vcpu))
    if env == Environment.DR:
        results.append(hc6_dr_coverage_floor(region, domain_demand_vcpu))
        results.append(hc7_dr_floor_integrity(region))
    return results
