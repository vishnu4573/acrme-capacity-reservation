"""ACRME Placement Engine — Data Models.

Defines the data structures for regions, capacity, quota, customers,
domain groups, and placement results used by the engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RegionClassification(str, Enum):
    STANDARD = "standard"
    RESTRICTED = "restricted"


class DistributionModel(str, Enum):
    THREE_REGION = "three_region"
    TWO_REGION = "two_region"
    CROSS_GEO_DR = "cross_geography_dr"


class Environment(str, Enum):
    PROD = "Prod"
    CVAL = "CVAL"
    DR = "DR"


class PlacementDecision(str, Enum):
    SELECTED = "SELECTED"
    REJECTED_HC = "REJECTED_HC"
    REJECTED_SCORING = "REJECTED_SCORING"
    DETERMINISTIC = "DETERMINISTIC"  # 2-region co-location
    CROSS_GEO = "CROSS_GEO"         # ME DR in Europe
    NOT_EVALUATED = "NOT_EVALUATED"


class CRGSetType(str, Enum):
    PROD_DEDICATED = "crg-pr"
    CVDR_SHARED = "crg-cvdr"
    DR_FOUNDATION = "crg-drf"


# ---------------------------------------------------------------------------
# Zone-level data
# ---------------------------------------------------------------------------

@dataclass
class ZoneCapacity:
    """Capacity snapshot for a single availability zone."""
    zone_id: int
    reserved_quantity: int = 0
    allocated_vms: int = 0
    available_slots: int = 0  # reserved - allocated

    def __post_init__(self):
        self.available_slots = max(0, self.reserved_quantity - self.allocated_vms)


@dataclass
class ZoneQuota:
    """Quota snapshot for a zone (derived from subscription-level quota)."""
    zone_id: int
    family_quota_limit: int = 0
    family_quota_used: int = 0
    regional_vcpu_limit: int = 0
    regional_vcpu_used: int = 0

    @property
    def family_available(self) -> int:
        return max(0, self.family_quota_limit - self.family_quota_used)

    @property
    def regional_available(self) -> int:
        return max(0, self.regional_vcpu_limit - self.regional_vcpu_used)


# ---------------------------------------------------------------------------
# Region-level data
# ---------------------------------------------------------------------------

@dataclass
class RegionSnapshot:
    """Complete capacity/quota snapshot for a region."""
    region_id: str             # e.g. "westus3"
    region_name: str           # e.g. "West US 3"
    geography: str             # e.g. "US"
    classification: RegionClassification = RegionClassification.STANDARD
    distribution_model: DistributionModel = DistributionModel.THREE_REGION
    availability_zones: int = 3
    auto_selectable: bool = True

    # Per-environment aggregates (all domain groups combined)
    prod_reserved: int = 0
    prod_allocated: int = 0
    prod_free: int = 0

    cval_reserved: int = 0
    cval_allocated: int = 0
    cval_free: int = 0

    dr_reserved: int = 0
    dr_allocated: int = 0
    dr_free: int = 0

    # Foundation DR (separate from workload DR)
    fnd_dr_reserved: int = 0
    fnd_dr_allocated: int = 0
    fnd_dr_free: int = 0

    # Quota
    prod_quota_limit: int = 0
    prod_quota_used: int = 0
    cval_quota_limit: int = 0
    cval_quota_used: int = 0
    dr_quota_limit: int = 0
    dr_quota_used: int = 0

    # Customer counts
    prod_customer_count: int = 0
    cval_customer_count: int = 0
    dr_customer_count: int = 0
    total_customers_geography: int = 0  # shared across envs in geography

    # DR coverage
    dr_coverage_ratio: float = 0.0
    dr_coverage_target: float = 1.0  # configurable normalisation ref

    # Zone-level detail (keyed by zone_id)
    zone_capacities: dict[int, ZoneCapacity] = field(default_factory=dict)
    zone_quotas: dict[int, ZoneQuota] = field(default_factory=dict)

    # Cross-geo DR fields
    dr_destination_geography: Optional[str] = None   # e.g. "Europe" for ME
    dr_offered: bool = True

    @property
    def prod_quota_headroom(self) -> int:
        return max(0, self.prod_quota_limit - self.prod_quota_used)

    @property
    def cval_quota_headroom(self) -> int:
        return max(0, self.cval_quota_limit - self.cval_quota_used)

    @property
    def dr_quota_headroom(self) -> int:
        return max(0, self.dr_quota_limit - self.dr_quota_used)


# ---------------------------------------------------------------------------
# Customer / Domain model
# ---------------------------------------------------------------------------

@dataclass
class DomainGroup:
    """A workload-domain grouping (e.g. TMS, WMS)."""
    token: str          # e.g. "wl-tms"
    display_name: str   # e.g. "TMS"
    prod_vcpu_demand: int = 0
    cval_vcpu_demand: int = 0
    dr_vcpu_demand: int = 0
    sku_family: str = "Dadsv5"  # primary SKU family
    prod_subscription_id: Optional[str] = None
    cval_subscription_id: Optional[str] = None
    dr_subscription_id: Optional[str] = None


@dataclass
class Customer:
    """A customer with one or more domain groups."""
    customer_id: str
    customer_name: str
    geography: str
    supplied_prod_region: Optional[str] = None  # exact-region path input
    domain_groups: list[DomainGroup] = field(default_factory=list)

    @property
    def total_prod_demand(self) -> int:
        return sum(d.prod_vcpu_demand for d in self.domain_groups)

    @property
    def total_cval_demand(self) -> int:
        return sum(d.cval_vcpu_demand for d in self.domain_groups)

    @property
    def total_dr_demand(self) -> int:
        return sum(d.dr_vcpu_demand for d in self.domain_groups)


# ---------------------------------------------------------------------------
# Placement Policy
# ---------------------------------------------------------------------------

@dataclass
class PlacementPolicy:
    """Configurable scoring weights and thresholds."""
    # Scoring weights (must sum to 1.0)
    alpha: float = 0.30   # capacity / headroom
    beta: float = 0.20    # quota headroom
    gamma: float = 0.25   # distribution fairness
    delta: float = 0.15   # DR readiness / overflow integrity
    epsilon: float = 0.10  # zone diversity

    # Thresholds
    zone_skew_tolerance: int = 2  # C-13
    combined_load_alert_threshold: float = 0.85  # C-15
    quota_group_replenish_threshold: float = 0.85  # QUA-015
    quota_sub_replenish_threshold: float = 0.85    # QUA-015

    # DR
    dr_sizing_method: str = "max_not_sum"  # or "sum"

    # Version
    policy_version: str = "v4.0-mock"

    def validate(self) -> bool:
        """Weight-sum invariant (F.10 note)."""
        total = self.alpha + self.beta + self.gamma + self.delta + self.epsilon
        return abs(total - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# Result structures
# ---------------------------------------------------------------------------

@dataclass
class HCResult:
    """Result of a single hard-constraint check."""
    hc_id: str
    description: str
    passed: bool
    detail: str = ""


@dataclass
class ScoringDetail:
    """Detailed scoring breakdown for a region."""
    region_id: str
    environment: Environment
    alpha_raw: float = 0.0
    alpha_clamped: float = 0.0
    beta_raw: float = 0.0
    beta_clamped: float = 0.0
    gamma_raw: float = 0.0
    gamma_clamped: float = 0.0
    delta_raw: float = 0.0
    delta_clamped: float = 0.0
    epsilon_raw: float = 0.0
    epsilon_clamped: float = 0.0
    total_score: float = 0.0
    hc_results: list[HCResult] = field(default_factory=list)
    hc_passed: bool = False
    decision: PlacementDecision = PlacementDecision.NOT_EVALUATED
    rejection_reasons: list[str] = field(default_factory=list)


@dataclass
class CRVResult:
    """Customer Region Vector — output of Phase 1."""
    customer_id: str
    geography: str
    distribution_model: DistributionModel
    prod_region: Optional[str] = None
    cval_region: Optional[str] = None
    dr_region: Optional[str] = None
    path_used: str = "exact_region"   # or "geography"
    prod_scoring: list[ScoringDetail] = field(default_factory=list)
    cval_scoring: list[ScoringDetail] = field(default_factory=list)
    dr_scoring: list[ScoringDetail] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ZonePlacement:
    """Zone-level placement detail for a domain's DPB."""
    zone_id: int
    target_vms: int = 0
    current_vms: int = 0
    skew: int = 0
    rebalance_needed: bool = False
    crg_name: str = ""
    crg_set_type: CRGSetType = CRGSetType.PROD_DEDICATED
    available_slots: int = 0
    quota_available: int = 0


@dataclass
class DPBResult:
    """Domain Placement Binding — output of Phase 2 for one domain x env."""
    domain_token: str
    environment: Environment
    region: str
    instance_group: str = ""
    subscription_id: str = ""
    crg_set_type: CRGSetType = CRGSetType.PROD_DEDICATED
    target_reserved: int = 0
    headroom: int = 0
    deficit: int = 0
    available_quota: int = 0
    quota_deficit: int = 0
    zone_placements: list[ZonePlacement] = field(default_factory=list)
    hc_results: list[HCResult] = field(default_factory=list)
    passed: bool = True
    rejection_reasons: list[str] = field(default_factory=list)
    quota_replenish_needed: bool = False


@dataclass
class PlacementReport:
    """Full placement result for a customer."""
    customer: Customer
    policy: PlacementPolicy
    crv: CRVResult
    dpb_results: list[DPBResult] = field(default_factory=list)
    overall_status: str = "PENDING"
    timestamp: str = ""
