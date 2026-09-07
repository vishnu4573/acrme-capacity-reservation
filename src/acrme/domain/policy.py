"""
Placement Policy & Region Catalogue — ACRME v2.3

Configuration-driven policy and region model (TDD Section 3, 6.2; REG-001, ADR-001).
All geographies, regions, distribution models, and scoring weights are versioned config.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ScoringWeights:
    """
    Placement scoring weights (TDD Section 8.2, ADR-001).
    
    Components (must sum to 1.0):
        α (alpha): NonProd headroom weight (default 0.30)
        β (beta): Prod quota weight (default 0.20)
        γ (gamma): Distribution fairness weight (default 0.25)
        δ (delta): DR readiness weight (default 0.15)
        ε (epsilon): Zone diversity weight (default 0.10)
    
    All components clamped [0,1] before weighting: Clamp(x) = max(0, min(1, x))
    """
    alpha: float = 0.30  # NonProd headroom
    beta: float = 0.20   # Prod quota
    gamma: float = 0.25  # Distribution fairness
    delta: float = 0.15  # DR readiness
    epsilon: float = 0.10  # Zone diversity
    
    def __post_init__(self):
        total = self.alpha + self.beta + self.gamma + self.delta + self.epsilon
        assert abs(total - 1.0) < 1e-6, f"Weights must sum to 1.0, got {total}"


@dataclass
class RegionEntry:
    """
    Single region entry in the catalogue (TDD Section 6.2, REG-001).
    
    Attributes:
        name: Azure region name (e.g. "West US 3", "Switzerland North")
        geography: Parent geography (US | Europe | Australia | "Asia Pacific" | "Middle East")
        is_standard: True if eligible for auto-selection (Standard capacity)
        is_restricted: True if production-only, needs exception (Restricted deployment)
        dr_not_offered: True if DR cannot be placed here (Middle East today per DEC-001)
        zone_support: True if availability zones are supported
        pending_confirmation: True if region is staged but not yet business-approved
                              (e.g. Japan East in Asia Pacific as of v2.3)
    """
    name: str
    geography: str
    is_standard: bool
    is_restricted: bool = False
    dr_not_offered: bool = False
    zone_support: bool = True
    pending_confirmation: bool = False
    
    @property
    def class_name(self) -> str:
        """Region class label (Standard | Restricted)."""
        if self.is_restricted:
            return "Restricted"
        return "Standard"


@dataclass
class RegionCatalogue:
    """
    Five-geography region model (TDD Section 6.2, 18; Baseline v2.3 Section 6).
    
    Region scope (v2.3):
        - US: 3-region (West US 3, Central US, Canada Central; Restricted: East US 2)
        - Europe: 2-region (Switzerland North, Sweden Central; Restricted: North/West Europe)
        - Australia: 2-region (Australia East, Australia Southeast)
        - Asia Pacific: 2-region (East Asia, Southeast Asia; Japan East PENDING)
        - Middle East: 2-region (UAE North, Saudi Arabia Central; DR_NOT_OFFERED per DEC-001)
    
    Distribution model (REG-003):
        - US: "3-region" (Prod, CVAL, DR each in distinct region)
        - All others: "2-region" (Prod in one, CVAL+DR co-located in other per PLC-010a)
    
    Configurable (REG-001): adding/removing/reclassifying a region or changing a
    geography's distribution model is a config change, NOT a code change.
    """
    
    version: str  # e.g. "2.3"
    entries: list[RegionEntry]
    distribution_models: dict[str, str]  # geography → "3-region" | "2-region"
    
    def get_standard_regions(self, geography: str) -> list[RegionEntry]:
        """Return Standard capacity regions for a geography (auto-selectable)."""
        return [
            r for r in self.entries
            if r.geography == geography and r.is_standard and not r.pending_confirmation
        ]
    
    def get_restricted_regions(self, geography: str) -> list[RegionEntry]:
        """Return Restricted deployment regions for a geography (exception-only)."""
        return [
            r for r in self.entries
            if r.geography == geography and r.is_restricted
        ]
    
    def get_distribution_model(self, geography: str) -> str:
        """Return distribution model for geography ("3-region" | "2-region")."""
        return self.distribution_models.get(geography, "2-region")
    
    def is_two_region_geography(self, geography: str) -> bool:
        """True if geography runs 2-region model (CVAL+DR must co-locate per PLC-010a)."""
        return self.get_distribution_model(geography) == "2-region"
    
    def validate_region(self, region: str, geography: str) -> tuple[bool, Optional[str]]:
        """
        Validate a region is in the catalogue and matches the geography.
        Returns (is_valid, error_message).
        """
        matching = [r for r in self.entries if r.name == region]
        if not matching:
            return False, f"Region {region} not in catalogue"
        
        entry = matching[0]
        if entry.geography != geography:
            return False, f"Region {region} belongs to {entry.geography}, not {geography}"
        
        if entry.pending_confirmation:
            return False, f"Region {region} pending business confirmation"
        
        return True, None


@dataclass
class PlacementPolicy:
    """
    Versioned placement policy (TDD Section 3, 6.2; ADR-001, REG-001).
    
    Governs:
        - Scoring weights (α/β/γ/δ/ε)
        - Region catalogue and distribution models
        - Thresholds (auto-increase, DR coverage floor, etc.)
        - Hard constraint rules (HC-1..HC-10)
    
    Every placement decision records the policy_version that drove it (DAT-005, GOV-003).
    """
    
    version: str  # e.g. "v2.3"
    scoring_weights: ScoringWeights
    region_catalogue: RegionCatalogue
    
    # Thresholds (TDD Section 8.4, T16)
    auto_increase_threshold_prod: float = 0.20
    auto_increase_threshold_nonprod: float = 0.20
    auto_increase_threshold_dr: float = 0.35  # Higher for lean bootstrap
    max_snapshot_age_seconds: float = 600.0  # 10 minutes (RDY-004, NFR-002)
    
    # DR coverage floor (HC-6, HC-7)
    dr_coverage_floor: float = 1.0  # 100% of Prod must be DR-protected
    
    def get_auto_increase_threshold(self, environment: str) -> float:
        """Return threshold for environment (Prod | NonProd | DR)."""
        thresholds = {
            "Prod": self.auto_increase_threshold_prod,
            "NonProd": self.auto_increase_threshold_nonprod,
            "CVAL": self.auto_increase_threshold_nonprod,
            "DR": self.auto_increase_threshold_dr,
        }
        return thresholds.get(environment, 0.20)
