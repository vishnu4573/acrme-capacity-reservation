"""
Placement & Scoring Engine — ACRME v2.3

Region selection via weighted placement scoring (TDD Section 3, 8; PLC-001..010, ADR-001).

Phase 3 scope:
    - Exact production-region input validation (default path, PLC-001)
    - Geography-only exception path (PLC-002, requires approval)
    - Seed record creation & reuse (PLC-003/004)
    - CVAL/DR scoring and selection (PS_DR, PS_NonProd)
    - CVAL/DR co-location in 2-region geographies (PLC-010a)
"""

from typing import Optional, Tuple
from datetime import datetime

from ..domain import (
    CustomerSeedRecord,
    PlacementPolicy,
    RegionCatalogue,
    ReadinessState,
    ReadinessCode,
)
from ..algorithms.scoring import PlacementScorer
from ..store.state_store import StateStore


class PlacementEngine:
    """
    Placement & Scoring Engine (TDD Section 3, 8).
    
    Validates exact region (default) or derives on exception approval (PLC-001/002).
    Computes PS_Prod/PS_DR/PS_NonProd over Standard regions. Writes seed record on
    first placement; reuses for subsequent products in same geography (PLC-003/004).
    
    Two-region geographies: CVAL+DR co-locate deterministically (PLC-010a, REG-003).
    Middle East: dr_region = "NOT_OFFERED" until DEC-001 clears (DR-014).
    """
    
    def __init__(
        self,
        state_store: StateStore,
        policy: PlacementPolicy,
        scorer: PlacementScorer,
    ):
        self.state_store = state_store
        self.policy = policy
        self.scorer = scorer
        self.catalogue = policy.region_catalogue
    
    def get_or_create_seed(
        self,
        customer_realm_id: str,
        geography: str,
        prod_region: Optional[str] = None,
        exception_ref: Optional[str] = None,
        capacity_snapshot_ref: str = "",
    ) -> Tuple[CustomerSeedRecord, bool]:
        """
        Get existing seed or create new one (PLC-003/004).
        
        Args:
            customer_realm_id: Customer identifier
            geography: US | Europe | Australia | "Asia Pacific" | "Middle East"
            prod_region: Exact production region (PLC-001 default path), or None
                        for geography-only exception path (PLC-002)
            exception_ref: Exception approval ID (required if prod_region is None)
            capacity_snapshot_ref: Snapshot ID for deterministic replay
        
        Returns:
            (seed_record, created): Seed record and whether it was newly created
        
        Logic:
            1. Check for existing seed (customer_realm_id + geography)
            2. If exists: return it (PLC-004 reuse)
            3. If not: validate/derive prod_region, select CVAL/DR, write seed (PLC-003)
        """
        # 1. Check for existing seed
        existing_seed = self.state_store.get_customer_seed(customer_realm_id, geography)
        if existing_seed:
            return existing_seed, False
        
        # 2. New seed required — validate or derive prod_region
        if prod_region is None:
            # Geography-only exception path (PLC-002)
            if not exception_ref:
                raise ValueError("exception_ref required for geography-only placement (PLC-002)")
            prod_region = self._derive_prod_region_from_geography(geography, capacity_snapshot_ref)
        else:
            # Exact region default path (PLC-001) — validate
            self._validate_prod_region(prod_region, geography)
        
        # 3. Select CVAL and DR regions
        distribution_model = self.catalogue.get_distribution_model(geography)
        cval_region, dr_region, cval_dr_colocated = self._select_cval_dr_regions(
            geography, prod_region, distribution_model, capacity_snapshot_ref
        )
        
        # 4. Create and persist seed
        seed = CustomerSeedRecord(
            customer_realm_id=customer_realm_id,
            geography=geography,
            prod_region=prod_region,
            cval_region=cval_region,
            dr_region=dr_region,
            distribution_model=distribution_model,
            cval_dr_colocated=cval_dr_colocated,
            decision_timestamp=datetime.utcnow(),
            policy_version=self.policy.version,
            capacity_snapshot_ref=capacity_snapshot_ref,
            exception_ref=exception_ref,
            products_covered=[],
        )
        
        self.state_store.write_customer_seed(seed)
        return seed, True
    
    def _validate_prod_region(self, region: str, geography: str) -> None:
        """
        Validate exact production region (PLC-001, HC-1..HC-10).
        
        Checks:
            1. Region exists in catalogue
            2. Region belongs to the stated geography
            3. Region is not pending confirmation
            4. If Restricted: exception workflow required (not handled here)
        
        Raises ValueError if validation fails.
        """
        is_valid, error = self.catalogue.validate_region(region, geography)
        if not is_valid:
            raise ValueError(f"Region validation failed: {error}")
        
        # Additional hard constraint checks would go here (HC-1..HC-10)
        # For Phase 3 skeleton: basic catalogue check only
    
    def _derive_prod_region_from_geography(
        self,
        geography: str,
        capacity_snapshot_ref: str,
    ) -> str:
        """
        Derive production region from geography (PLC-002 exception path).
        
        Geography-only selection is exceptional — requires approval + customer
        acknowledgement (PLC-002). Once derived, the region becomes the fixed seed.
        
        Algorithm (TDD Section 8.1, 8.2):
            1. Get Standard regions for geography
            2. Compute PS_Prod for each (5 weighted components)
            3. Return argmax PS_Prod
        
        Returns:
            Selected production region name
        """
        standard_regions = self.catalogue.get_standard_regions(geography)
        if not standard_regions:
            raise ValueError(f"No Standard regions available for {geography}")
        
        # Compute PS_Prod for each region (TDD Section 8.2)
        scores = {
            region.name: self.scorer.compute_ps_prod(region.name, capacity_snapshot_ref)
            for region in standard_regions
        }
        
        # argmax with deterministic tie-break (TDD Section 8.2)
        best_region = max(scores.items(), key=lambda x: (x[1], x[0]))[0]
        return best_region
    
    def _select_cval_dr_regions(
        self,
        geography: str,
        prod_region: str,
        distribution_model: str,
        capacity_snapshot_ref: str,
    ) -> Tuple[str, str, bool]:
        """
        Select CVAL and DR regions (TDD Section 8.2, PLC-010/010a).
        
        Distribution model logic (REG-003):
            - 3-region (US): Prod, CVAL, DR each in distinct region
            - 2-region (all others): Prod in one, CVAL+DR co-located in the other (PLC-010a)
        
        Middle East special case (DEC-001, DR-014):
            - dr_region = "NOT_OFFERED" (no DR assigned)
            - cval_region = the other 2-region Standard region
        
        Returns:
            (cval_region, dr_region, cval_dr_colocated)
        """
        standard_regions = self.catalogue.get_standard_regions(geography)
        available_regions = [r.name for r in standard_regions if r.name != prod_region]
        
        # Middle East: DR_NOT_OFFERED per DEC-001
        if geography == "Middle East":
            if not available_regions:
                raise ValueError(f"No CVAL region available in {geography}")
            cval_region = available_regions[0]  # Deterministic: the other region
            return cval_region, "NOT_OFFERED", False
        
        # 2-region geography: CVAL+DR must co-locate (PLC-010a)
        if distribution_model == "2-region":
            if not available_regions:
                raise ValueError(f"No CVAL/DR region available in {geography}")
            
            # Deterministic: the single remaining Standard region
            cval_dr_region = available_regions[0]
            return cval_dr_region, cval_dr_region, True
        
        # 3-region geography (US): separate CVAL and DR via scoring
        if len(available_regions) < 2:
            raise ValueError(f"3-region model requires at least 2 non-Prod regions in {geography}")
        
        # Score remaining regions for CVAL (PS_NonProd)
        cval_scores = {
            region: self.scorer.compute_ps_nonprod(region, capacity_snapshot_ref)
            for region in available_regions
        }
        cval_region = max(cval_scores.items(), key=lambda x: (x[1], x[0]))[0]
        
        # Score remaining regions for DR (PS_DR)
        dr_candidates = [r for r in available_regions if r != cval_region]
        dr_scores = {
            region: self.scorer.compute_ps_dr(region, capacity_snapshot_ref)
            for region in dr_candidates
        }
        dr_region = max(dr_scores.items(), key=lambda x: (x[1], x[0]))[0]
        
        return cval_region, dr_region, False
    
    def validate_readiness(
        self,
        customer_realm_id: str,
        geography: str,
        region: str,
        environment: str,
        requested_vcpu: int,
    ) -> ReadinessState:
        """
        Validate deployment readiness (TDD Section 11.3, RDY-001).
        
        Readiness gate (TDD Section 2.1):
            Readiness = capacity ∧ quota ∧ freshness ∧ policy
        
        Checks:
            1. Seed record exists
            2. Snapshot freshness
            3. Capacity available
            4. Quota available
            5. No hard-constraint violations
        
        Returns:
            ReadinessState with verdict code and details
        """
        # Phase 3 skeleton: basic structure only
        # Full implementation requires integrated snapshot + quota state
        
        # 1. Check seed exists
        seed = self.state_store.get_customer_seed(customer_realm_id, geography)
        if not seed:
            return ReadinessState(
                code=ReadinessCode.NO_SEED_RECORD,
                capacity_available_vcpu=0,
                quota_available_vcpu=0,
                snapshot_age_seconds=0.0,
                message=f"No seed record for {customer_realm_id} in {geography}",
                policy_version=self.policy.version,
            )
        
        # 2-6. Additional checks (capacity, quota, freshness) would integrate
        # with StateReconciler and QuotaPoolManager here
        
        # Placeholder: assume ready
        return ReadinessState(
            code=ReadinessCode.READY,
            capacity_available_vcpu=1000,  # Placeholder
            quota_available_vcpu=1000,  # Placeholder
            snapshot_age_seconds=60.0,
            capacity_snapshot_ref="snap_placeholder",
            policy_version=self.policy.version,
        )
