"""
Placement Scoring Algorithms — ACRME v2.3

Weighted placement scoring (TDD Section 8.2, ADR-001, T15).

PS = α·Clamp(α_component) + β·Clamp(β_component) + γ·Clamp(γ_component) 
     + δ·Clamp(δ_component) + ε·Clamp(ε_component)

Default weights (α=0.30, β=0.20, γ=0.25, δ=0.15, ε=0.10) sum to 1.0.
All components clamped to [0,1] before weighting.

Components:
    α: NonProd headroom (pool_limit - prod_floor - dr_earmark) / pool_limit
    β: Prod quota headroom (assigned_quota - usage) / assigned_quota
    γ: Distribution fairness (1 - customer_fraction_in_region)
    δ: DR readiness (dr_capacity_available / dr_capacity_required)
    ε: Zone diversity (distinct_zones / max_zones)
"""

from typing import Dict, Any


def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """
    Clamp value to [min_val, max_val] (TDD Section 8.2).
    
    Clamp(x) = max(0, min(1, x)) for default bounds.
    """
    return max(min_val, min(max_val, value))


class PlacementScorer:
    """
    Placement scoring engine (TDD Section 8.2, T15).
    
    Computes PS_Prod, PS_DR, PS_NonProd for region candidates using five weighted
    components. All components clamped [0,1] before weighting. Weights configurable
    via PlacementPolicy.
    
    Phase 3 skeleton: component computation structure defined, integration with
    live snapshots pending full State Store implementation.
    """
    
    def __init__(self, scoring_weights: Dict[str, float]):
        """
        Initialize scorer with weights from PlacementPolicy.
        
        Args:
            scoring_weights: Dict with keys alpha, beta, gamma, delta, epsilon
        """
        self.alpha = scoring_weights.get("alpha", 0.30)
        self.beta = scoring_weights.get("beta", 0.20)
        self.gamma = scoring_weights.get("gamma", 0.25)
        self.delta = scoring_weights.get("delta", 0.15)
        self.epsilon = scoring_weights.get("epsilon", 0.10)
        
        # Validate weights sum to 1.0
        total = self.alpha + self.beta + self.gamma + self.delta + self.epsilon
        assert abs(total - 1.0) < 1e-6, f"Weights must sum to 1.0, got {total}"
    
    def compute_ps_prod(self, region: str, snapshot_ref: str) -> float:
        """
        Compute PS_Prod for production region selection (TDD Section 8.2).
        
        PS_Prod prioritizes:
            - Prod quota headroom (β)
            - Distribution fairness (γ) — avoid concentration
            - Zone diversity (ε)
            - NonProd headroom (α) for CVAL/DR co-location potential
            - DR readiness (δ) less critical for Prod selection
        
        Args:
            region: Candidate region
            snapshot_ref: Capacity snapshot ID for deterministic scoring
        
        Returns:
            Placement score [0,1]
        """
        # Phase 3 skeleton: fetch components from snapshot
        components = self._fetch_scoring_components(region, snapshot_ref, "Prod")
        
        # Clamp and weight
        alpha_c = clamp(components["nonprod_headroom"])
        beta_c = clamp(components["prod_quota_headroom"])
        gamma_c = clamp(components["distribution_fairness"])
        delta_c = clamp(components["dr_readiness"])
        epsilon_c = clamp(components["zone_diversity"])
        
        ps = (
            self.alpha * alpha_c
            + self.beta * beta_c
            + self.gamma * gamma_c
            + self.delta * delta_c
            + self.epsilon * epsilon_c
        )
        
        return ps
    
    def compute_ps_dr(self, region: str, snapshot_ref: str) -> float:
        """
        Compute PS_DR for DR region selection (TDD Section 8.2).
        
        PS_DR prioritizes:
            - DR readiness (δ) — can absorb the protected Prod portion
            - NonProd headroom (α) — co-location with CVAL if needed
            - Distribution fairness (γ) — spread DR load
            - Zone diversity (ε)
            - Prod quota (β) less critical for DR
        
        Args:
            region: Candidate DR region
            snapshot_ref: Capacity snapshot ID
        
        Returns:
            Placement score [0,1]
        """
        components = self._fetch_scoring_components(region, snapshot_ref, "DR")
        
        alpha_c = clamp(components["nonprod_headroom"])
        beta_c = clamp(components["prod_quota_headroom"])
        gamma_c = clamp(components["distribution_fairness"])
        delta_c = clamp(components["dr_readiness"])
        epsilon_c = clamp(components["zone_diversity"])
        
        # DR-focused weighting: emphasize delta (DR readiness)
        ps = (
            self.alpha * alpha_c
            + self.beta * beta_c
            + self.gamma * gamma_c
            + self.delta * delta_c
            + self.epsilon * epsilon_c
        )
        
        return ps
    
    def compute_ps_nonprod(self, region: str, snapshot_ref: str) -> float:
        """
        Compute PS_NonProd for CVAL/NonProd region selection (TDD Section 8.2).
        
        PS_NonProd prioritizes:
            - NonProd headroom (α) — primary consideration
            - Distribution fairness (γ)
            - Zone diversity (ε)
            - DR readiness (δ) if co-location with DR
            - Prod quota (β) less relevant for NonProd
        
        Args:
            region: Candidate CVAL/NonProd region
            snapshot_ref: Capacity snapshot ID
        
        Returns:
            Placement score [0,1]
        """
        components = self._fetch_scoring_components(region, snapshot_ref, "NonProd")
        
        alpha_c = clamp(components["nonprod_headroom"])
        beta_c = clamp(components["prod_quota_headroom"])
        gamma_c = clamp(components["distribution_fairness"])
        delta_c = clamp(components["dr_readiness"])
        epsilon_c = clamp(components["zone_diversity"])
        
        ps = (
            self.alpha * alpha_c
            + self.beta * beta_c
            + self.gamma * gamma_c
            + self.delta * delta_c
            + self.epsilon * epsilon_c
        )
        
        return ps
    
    def _fetch_scoring_components(
        self,
        region: str,
        snapshot_ref: str,
        environment: str,
    ) -> Dict[str, float]:
        """
        Fetch scoring components from capacity snapshot (TDD Section 8.2).
        
        Components (TDD Section 8.2):
            nonprod_headroom: (pool_limit - prod_floor - dr_earmark) / pool_limit
            prod_quota_headroom: (assigned_quota - usage) / assigned_quota
            distribution_fairness: 1 - (customer_fraction_in_region)
            dr_readiness: dr_capacity_available / dr_capacity_required
            zone_diversity: distinct_zones / max_zones
        
        Phase 3 skeleton: placeholder values until State Store integration.
        Full implementation would:
            1. Read snapshot from StateStore by snapshot_ref
            2. Compute each component from live reservation/quota/customer state
            3. Return dict with exact numeric values
        
        Returns:
            Dict[str, float] with component values (raw, pre-clamp)
        """
        # Placeholder: return mid-range values for skeleton
        # Real implementation integrates with StateStore and InventoryCollector
        return {
            "nonprod_headroom": 0.6,
            "prod_quota_headroom": 0.7,
            "distribution_fairness": 0.8,
            "dr_readiness": 0.5,
            "zone_diversity": 0.75,
        }
