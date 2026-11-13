"""ACRME Placement Engine — Mock Exercise Data.

Provides synthetic multi-domain, multi-subscription scenarios for three
distribution models:
  1. Contoso (US, three_region) — TMS + WMS, supplied prod region westus3
  2. Fabrikam (EU, two_region) — TMS only, no supplied prod region
  3. Litware  (ME, cross_geography_dr) — TMS only, supplied prod region
     qatarcentral

Capacity / quota numbers are *illustrative mock data* — not approved
defaults.  Buffer (C-3) is parameterised as 0; all scoring weights are
labelled [Assumed] in PlacementPolicy.
"""
from __future__ import annotations

from models import (
    Customer,
    DomainGroup,
    DistributionModel,
    PlacementPolicy,
    RegionClassification,
    RegionSnapshot,
    ZoneCapacity,
    ZoneQuota,
)


# ===================================================================
# Helper — build zone dicts
# ===================================================================

def _zones_cap(zone_data: list[tuple[int, int, int]]) -> dict[int, ZoneCapacity]:
    """Build zone-capacity dict from [(zone_id, reserved, allocated), ...]."""
    return {z: ZoneCapacity(zone_id=z, reserved_quantity=r, allocated_vms=a)
            for z, r, a in zone_data}


def _zones_quota(zone_data: list[tuple[int, int, int, int, int]]) -> dict[int, ZoneQuota]:
    """Build zone-quota dict from [(zone_id, fam_lim, fam_used, reg_lim, reg_used)]."""
    return {z: ZoneQuota(zone_id=z,
                         family_quota_limit=fl, family_quota_used=fu,
                         regional_vcpu_limit=rl, regional_vcpu_used=ru)
            for z, fl, fu, rl, ru in zone_data}


# ===================================================================
# US Geography — Three-Region (Contoso: TMS + WMS)
# ===================================================================

def build_us_regions() -> list[RegionSnapshot]:
    """West US 3, Central US, Canada Central (standard) + East US 2 (restricted)."""
    return [
        RegionSnapshot(
            region_id="westus3", region_name="West US 3", geography="US",
            classification=RegionClassification.STANDARD,
            distribution_model=DistributionModel.THREE_REGION,
            availability_zones=3, auto_selectable=True,
            # Capacity — moderate utilisation
            prod_reserved=640, prod_allocated=480, prod_free=160,
            cval_reserved=320, cval_allocated=200, cval_free=120,
            dr_reserved=320, dr_allocated=128, dr_free=192,
            fnd_dr_reserved=64, fnd_dr_allocated=32, fnd_dr_free=32,
            # Quota
            prod_quota_limit=800, prod_quota_used=520,
            cval_quota_limit=400, cval_quota_used=220,
            dr_quota_limit=400, dr_quota_used=160,
            # Customer counts
            prod_customer_count=12, cval_customer_count=10, dr_customer_count=8,
            total_customers_geography=30,
            dr_coverage_ratio=0.82, dr_coverage_target=1.0,
            # Zones — 3 zones
            zone_capacities=_zones_cap([
                (1, 220, 160), (2, 210, 160), (3, 210, 160),
            ]),
            zone_quotas=_zones_quota([
                (1, 280, 180, 800, 520),
                (2, 260, 170, 800, 520),
                (3, 260, 170, 800, 520),
            ]),
        ),
        RegionSnapshot(
            region_id="centralus", region_name="Central US", geography="US",
            classification=RegionClassification.STANDARD,
            distribution_model=DistributionModel.THREE_REGION,
            availability_zones=3, auto_selectable=True,
            prod_reserved=480, prod_allocated=400, prod_free=80,
            cval_reserved=256, cval_allocated=200, cval_free=56,
            dr_reserved=256, dr_allocated=180, dr_free=76,
            fnd_dr_reserved=64, fnd_dr_allocated=48, fnd_dr_free=16,
            prod_quota_limit=600, prod_quota_used=440,
            cval_quota_limit=320, cval_quota_used=210,
            dr_quota_limit=320, dr_quota_used=200,
            prod_customer_count=14, cval_customer_count=12, dr_customer_count=10,
            total_customers_geography=30,
            dr_coverage_ratio=0.65, dr_coverage_target=1.0,
            zone_capacities=_zones_cap([
                (1, 170, 140), (2, 160, 130), (3, 150, 130),
            ]),
            zone_quotas=_zones_quota([
                (1, 200, 150, 600, 440),
                (2, 200, 145, 600, 440),
                (3, 200, 145, 600, 440),
            ]),
        ),
        RegionSnapshot(
            region_id="canadacentral", region_name="Canada Central", geography="US",
            classification=RegionClassification.STANDARD,
            distribution_model=DistributionModel.THREE_REGION,
            availability_zones=3, auto_selectable=True,
            prod_reserved=320, prod_allocated=200, prod_free=120,
            cval_reserved=160, cval_allocated=80, cval_free=80,
            dr_reserved=160, dr_allocated=60, dr_free=100,
            fnd_dr_reserved=32, fnd_dr_allocated=16, fnd_dr_free=16,
            prod_quota_limit=500, prod_quota_used=240,
            cval_quota_limit=250, cval_quota_used=100,
            dr_quota_limit=250, dr_quota_used=80,
            prod_customer_count=6, cval_customer_count=5, dr_customer_count=4,
            total_customers_geography=30,
            dr_coverage_ratio=0.90, dr_coverage_target=1.0,
            zone_capacities=_zones_cap([
                (1, 110, 70), (2, 105, 65), (3, 105, 65),
            ]),
            zone_quotas=_zones_quota([
                (1, 170, 80, 500, 240),
                (2, 165, 80, 500, 240),
                (3, 165, 80, 500, 240),
            ]),
        ),
        RegionSnapshot(
            region_id="eastus2", region_name="East US 2", geography="US",
            classification=RegionClassification.RESTRICTED,
            distribution_model=DistributionModel.THREE_REGION,
            availability_zones=3, auto_selectable=False,
            prod_reserved=256, prod_allocated=240, prod_free=16,
            cval_reserved=128, cval_allocated=120, cval_free=8,
            dr_reserved=128, dr_allocated=120, dr_free=8,
            fnd_dr_reserved=32, fnd_dr_allocated=30, fnd_dr_free=2,
            prod_quota_limit=300, prod_quota_used=260,
            cval_quota_limit=160, cval_quota_used=130,
            dr_quota_limit=160, dr_quota_used=130,
            prod_customer_count=8, cval_customer_count=7, dr_customer_count=7,
            total_customers_geography=30,
            dr_coverage_ratio=0.55, dr_coverage_target=1.0,
            zone_capacities=_zones_cap([
                (1, 90, 80), (2, 83, 80), (3, 83, 80),
            ]),
            zone_quotas=_zones_quota([
                (1, 100, 88, 300, 260),
                (2, 100, 86, 300, 260),
                (3, 100, 86, 300, 260),
            ]),
        ),
    ]


# ===================================================================
# EU Geography — Two-Region (Fabrikam: TMS only)
# ===================================================================

def build_eu_regions() -> list[RegionSnapshot]:
    """Switzerland North, Sweden Central (standard) + restricted regions."""
    return [
        RegionSnapshot(
            region_id="switzerlandnorth", region_name="Switzerland North",
            geography="Europe", classification=RegionClassification.STANDARD,
            distribution_model=DistributionModel.TWO_REGION,
            availability_zones=3, auto_selectable=True,
            prod_reserved=400, prod_allocated=280, prod_free=120,
            cval_reserved=200, cval_allocated=120, cval_free=80,
            dr_reserved=200, dr_allocated=100, dr_free=100,
            fnd_dr_reserved=48, fnd_dr_allocated=24, fnd_dr_free=24,
            prod_quota_limit=500, prod_quota_used=310,
            cval_quota_limit=260, cval_quota_used=140,
            dr_quota_limit=260, dr_quota_used=120,
            prod_customer_count=8, cval_customer_count=7, dr_customer_count=6,
            total_customers_geography=18,
            dr_coverage_ratio=0.88, dr_coverage_target=1.0,
            zone_capacities=_zones_cap([
                (1, 140, 95), (2, 130, 93), (3, 130, 92),
            ]),
            zone_quotas=_zones_quota([
                (1, 170, 105, 500, 310),
                (2, 165, 103, 500, 310),
                (3, 165, 102, 500, 310),
            ]),
        ),
        RegionSnapshot(
            region_id="swedencentral", region_name="Sweden Central",
            geography="Europe", classification=RegionClassification.STANDARD,
            distribution_model=DistributionModel.TWO_REGION,
            availability_zones=3, auto_selectable=True,
            prod_reserved=320, prod_allocated=200, prod_free=120,
            cval_reserved=160, cval_allocated=90, cval_free=70,
            dr_reserved=160, dr_allocated=80, dr_free=80,
            fnd_dr_reserved=32, fnd_dr_allocated=16, fnd_dr_free=16,
            prod_quota_limit=420, prod_quota_used=230,
            cval_quota_limit=210, cval_quota_used=100,
            dr_quota_limit=210, dr_quota_used=100,
            prod_customer_count=6, cval_customer_count=6, dr_customer_count=5,
            total_customers_geography=18,
            dr_coverage_ratio=0.78, dr_coverage_target=1.0,
            zone_capacities=_zones_cap([
                (1, 110, 68), (2, 105, 66), (3, 105, 66),
            ]),
            zone_quotas=_zones_quota([
                (1, 140, 78, 420, 230),
                (2, 140, 76, 420, 230),
                (3, 140, 76, 420, 230),
            ]),
        ),
        RegionSnapshot(
            region_id="northeurope", region_name="North Europe",
            geography="Europe", classification=RegionClassification.RESTRICTED,
            distribution_model=DistributionModel.TWO_REGION,
            availability_zones=3, auto_selectable=False,
            prod_reserved=200, prod_allocated=180, prod_free=20,
            cval_reserved=100, cval_allocated=90, cval_free=10,
            dr_reserved=100, dr_allocated=88, dr_free=12,
            fnd_dr_reserved=24, fnd_dr_allocated=20, fnd_dr_free=4,
            prod_quota_limit=250, prod_quota_used=200,
            cval_quota_limit=130, cval_quota_used=100,
            dr_quota_limit=130, dr_quota_used=100,
            prod_customer_count=5, cval_customer_count=5, dr_customer_count=5,
            total_customers_geography=18,
            dr_coverage_ratio=0.60, dr_coverage_target=1.0,
            zone_capacities=_zones_cap([
                (1, 70, 60), (2, 65, 60), (3, 65, 60),
            ]),
            zone_quotas=_zones_quota([
                (1, 84, 68, 250, 200),
                (2, 83, 66, 250, 200),
                (3, 83, 66, 250, 200),
            ]),
        ),
    ]


# ===================================================================
# ME Geography — Cross-Geo DR (Litware: TMS only)
# ===================================================================

def build_me_regions() -> list[RegionSnapshot]:
    """UAE North + Qatar Central (standard, ME) for Prod/CVAL.
    DR destinations are Europe standard regions (reuse build_eu_regions).
    """
    return [
        RegionSnapshot(
            region_id="uaenorth", region_name="UAE North",
            geography="Middle East",
            classification=RegionClassification.STANDARD,
            distribution_model=DistributionModel.CROSS_GEO_DR,
            availability_zones=3, auto_selectable=True,
            prod_reserved=160, prod_allocated=100, prod_free=60,
            cval_reserved=80, cval_allocated=40, cval_free=40,
            dr_reserved=0, dr_allocated=0, dr_free=0,  # DR not hosted locally
            fnd_dr_reserved=0, fnd_dr_allocated=0, fnd_dr_free=0,
            prod_quota_limit=240, prod_quota_used=120,
            cval_quota_limit=120, cval_quota_used=50,
            dr_quota_limit=0, dr_quota_used=0,
            prod_customer_count=4, cval_customer_count=3, dr_customer_count=0,
            total_customers_geography=8,
            dr_coverage_ratio=0.0, dr_coverage_target=1.0,
            dr_destination_geography="Europe", dr_offered=True,
            zone_capacities=_zones_cap([
                (1, 55, 34), (2, 53, 33), (3, 52, 33),
            ]),
            zone_quotas=_zones_quota([
                (1, 80, 40, 240, 120),
                (2, 80, 40, 240, 120),
                (3, 80, 40, 240, 120),
            ]),
        ),
        RegionSnapshot(
            region_id="qatarcentral", region_name="Qatar Central",
            geography="Middle East",
            classification=RegionClassification.STANDARD,
            distribution_model=DistributionModel.CROSS_GEO_DR,
            availability_zones=3, auto_selectable=True,
            prod_reserved=120, prod_allocated=60, prod_free=60,
            cval_reserved=60, cval_allocated=20, cval_free=40,
            dr_reserved=0, dr_allocated=0, dr_free=0,
            fnd_dr_reserved=0, fnd_dr_allocated=0, fnd_dr_free=0,
            prod_quota_limit=200, prod_quota_used=80,
            cval_quota_limit=100, cval_quota_used=30,
            dr_quota_limit=0, dr_quota_used=0,
            prod_customer_count=3, cval_customer_count=2, dr_customer_count=0,
            total_customers_geography=8,
            dr_coverage_ratio=0.0, dr_coverage_target=1.0,
            dr_destination_geography="Europe", dr_offered=True,
            zone_capacities=_zones_cap([
                (1, 42, 20), (2, 40, 20), (3, 38, 20),
            ]),
            zone_quotas=_zones_quota([
                (1, 68, 28, 200, 80),
                (2, 66, 26, 200, 80),
                (3, 66, 26, 200, 80),
            ]),
        ),
    ]


# ===================================================================
# Customers
# ===================================================================

def build_customers() -> list[Customer]:
    """Three customers exercising all distribution models."""
    contoso = Customer(
        customer_id="cust-001",
        customer_name="Contoso Ltd",
        geography="US",
        supplied_prod_region="westus3",  # exact-region path
        domain_groups=[
            DomainGroup(
                token="wl-tms", display_name="TMS",
                prod_vcpu_demand=64, cval_vcpu_demand=32, dr_vcpu_demand=32,
                sku_family="Dadsv5",
                prod_subscription_id="sub-contoso-tms-prod-001",
                cval_subscription_id="sub-contoso-tms-cval-001",
                dr_subscription_id="sub-contoso-tms-dr-001",
            ),
            DomainGroup(
                token="wl-wms", display_name="WMS",
                prod_vcpu_demand=32, cval_vcpu_demand=16, dr_vcpu_demand=16,
                sku_family="Dadsv5",
                prod_subscription_id="sub-contoso-wms-prod-001",
                cval_subscription_id="sub-contoso-wms-cval-001",
                dr_subscription_id="sub-contoso-wms-dr-001",
            ),
        ],
    )

    fabrikam = Customer(
        customer_id="cust-002",
        customer_name="Fabrikam Inc",
        geography="Europe",
        supplied_prod_region=None,  # geography path — no supplied region
        domain_groups=[
            DomainGroup(
                token="wl-tms", display_name="TMS",
                prod_vcpu_demand=48, cval_vcpu_demand=24, dr_vcpu_demand=24,
                sku_family="Dadsv5",
                prod_subscription_id="sub-fabrikam-tms-prod-001",
                cval_subscription_id="sub-fabrikam-tms-cval-001",
                dr_subscription_id="sub-fabrikam-tms-dr-001",
            ),
        ],
    )

    litware = Customer(
        customer_id="cust-003",
        customer_name="Litware Corp",
        geography="Middle East",
        supplied_prod_region="qatarcentral",  # cross-geo path
        domain_groups=[
            DomainGroup(
                token="wl-tms", display_name="TMS",
                prod_vcpu_demand=32, cval_vcpu_demand=16, dr_vcpu_demand=16,
                sku_family="Dadsv5",
                prod_subscription_id="sub-litware-tms-prod-001",
                cval_subscription_id="sub-litware-tms-cval-001",
                dr_subscription_id="sub-litware-tms-dr-001",
            ),
        ],
    )

    return [contoso, fabrikam, litware]


# ===================================================================
# Default policy — all weights labelled [Assumed]
# ===================================================================

def default_policy() -> PlacementPolicy:
    """Return policy with [Assumed] weights and zero buffer."""
    return PlacementPolicy(
        alpha=0.30,    # [Assumed] capacity headroom
        beta=0.20,     # [Assumed] quota headroom
        gamma=0.25,    # [Assumed] distribution fairness
        delta=0.15,    # [Assumed] DR readiness
        epsilon=0.10,  # [Assumed] zone diversity
        zone_skew_tolerance=2,
        combined_load_alert_threshold=0.85,
        quota_group_replenish_threshold=0.85,
        quota_sub_replenish_threshold=0.85,
        dr_sizing_method="max_not_sum",
        policy_version="v4.0-mock",
    )


# ===================================================================
# Convenience: all regions keyed by geography
# ===================================================================

def build_all_regions() -> dict[str, list[RegionSnapshot]]:
    """Return {geography: [RegionSnapshot, ...]} for every mocked geography."""
    return {
        "US": build_us_regions(),
        "Europe": build_eu_regions(),
        "Middle East": build_me_regions(),
    }
