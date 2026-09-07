"""
Config / Scope-File Service — ACRME v2.3

Versioned PlacementPolicy and region catalogue (TDD Section 3, REG-001, GOV-003, DAT-005).
"""

from ..domain import PlacementPolicy, RegionCatalogue, RegionEntry, ScoringWeights


class ConfigService:
    """
    Config / Scope-File Service (TDD Section 3).
    
    Loads versioned PlacementPolicy from config-as-code. Every placement decision
    records the policy_version that drove it (DAT-005, GOV-003).
    
    Region catalogue is configuration-driven (REG-001): adding/removing/reclassifying
    regions or changing distribution models is a config change, not a code change.
    
    Phase 3 skeleton: hardcoded v2.3 policy for bootstrap.
    """
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path
    
    def load_policy(self) -> PlacementPolicy:
        """
        Load PlacementPolicy (Phase 3 hardcoded v2.3).
        
        Real implementation:
            1. Read YAML/JSON config from config_path
            2. Validate schema
            3. Return PlacementPolicy
        """
        # Hardcoded v2.3 policy for Phase 3 skeleton
        catalogue = self._build_v2_3_catalogue()
        weights = ScoringWeights(
            alpha=0.30,
            beta=0.20,
            gamma=0.25,
            delta=0.15,
            epsilon=0.10,
        )
        
        return PlacementPolicy(
            version="v2.3",
            scoring_weights=weights,
            region_catalogue=catalogue,
            auto_increase_threshold_prod=0.20,
            auto_increase_threshold_nonprod=0.20,
            auto_increase_threshold_dr=0.35,
            max_snapshot_age_seconds=600.0,
            dr_coverage_floor=1.0,
        )
    
    def _build_v2_3_catalogue(self) -> RegionCatalogue:
        """Build v2.3 region catalogue (5 geographies, Baseline v2.3 Section 6)."""
        entries = [
            # US (3-region)
            RegionEntry("West US 3", "US", is_standard=True),
            RegionEntry("Central US", "US", is_standard=True),
            RegionEntry("Canada Central", "US", is_standard=True),
            RegionEntry("East US 2", "US", is_standard=False, is_restricted=True),
            
            # Europe (2-region)
            RegionEntry("Switzerland North", "Europe", is_standard=True),
            RegionEntry("Sweden Central", "Europe", is_standard=True),
            RegionEntry("North Europe", "Europe", is_standard=False, is_restricted=True),
            RegionEntry("West Europe", "Europe", is_standard=False, is_restricted=True),
            
            # Australia (2-region)
            RegionEntry("Australia East", "Australia", is_standard=True),
            RegionEntry("Australia Southeast", "Australia", is_standard=True),
            
            # Asia Pacific (2-region)
            RegionEntry("East Asia", "Asia Pacific", is_standard=True),
            RegionEntry("Southeast Asia", "Asia Pacific", is_standard=True),
            RegionEntry("Japan East", "Asia Pacific", is_standard=True, pending_confirmation=True),
            
            # Middle East (2-region, DR_NOT_OFFERED per DEC-001)
            RegionEntry("Saudi Arabia Central", "Middle East", is_standard=True, dr_not_offered=True),
            RegionEntry("UAE North", "Middle East", is_standard=True, dr_not_offered=True),
        ]
        
        distribution_models = {
            "US": "3-region",
            "Europe": "2-region",
            "Australia": "2-region",
            "Asia Pacific": "2-region",
            "Middle East": "2-region",
        }
        
        return RegionCatalogue(
            version="2.3",
            entries=entries,
            distribution_models=distribution_models,
        )
