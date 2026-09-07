"""
Readiness API — ACRME v2.3

Combined capacity+quota+freshness verdict API (TDD Section 11, RDY-001..004, INT-001..007).
"""

from typing import Dict, Any
from ..components import PlacementEngine
from ..domain import ReadinessState


class ReadinessAPI:
    """
    Readiness API (TDD Section 11).
    
    Endpoints:
        POST /readiness: Query deployment readiness (idempotent)
        POST /placement/seed: Create or reuse customer seed
    
    Every mutating call carries idempotency key + expected-state version (INT-004..006).
    """
    
    def __init__(self, placement_engine: PlacementEngine):
        self.placement_engine = placement_engine
    
    def query_readiness(
        self,
        customer_realm_id: str,
        geography: str,
        region: str,
        environment: str,
        sku_family: str,
        requested_vcpu: int,
    ) -> Dict[str, Any]:
        """
        Query deployment readiness (TDD Section 11.1, RDY-001).
        
        Request:
            customer_realm_id: Customer identifier
            geography: Target geography
            region: Exact Azure region
            environment: Prod | NonProd | CVAL | DR
            sku_family: VM family
            requested_vcpu: Requested capacity
        
        Response:
            ReadinessState as JSON dict with:
                code: READY | CAPACITY_INSUFFICIENT | QUOTA_INSUFFICIENT | ...
                capacity_available_vcpu: Available capacity
                quota_available_vcpu: Available quota
                snapshot_age_seconds: Snapshot freshness
                message: Human-readable message (optional)
        
        Phase 3 skeleton: structure defined, integrated checks pending.
        """
        state = self.placement_engine.validate_readiness(
            customer_realm_id=customer_realm_id,
            geography=geography,
            region=region,
            environment=environment,
            requested_vcpu=requested_vcpu,
        )
        
        return {
            "code": state.code.value,
            "is_ready": state.is_ready,
            "capacity_available_vcpu": state.capacity_available_vcpu,
            "quota_available_vcpu": state.quota_available_vcpu,
            "snapshot_age_seconds": state.snapshot_age_seconds,
            "blocking_constraint": state.blocking_constraint,
            "message": state.message,
            "capacity_snapshot_ref": state.capacity_snapshot_ref,
            "policy_version": state.policy_version,
        }
    
    def create_or_get_seed(
        self,
        customer_realm_id: str,
        geography: str,
        prod_region: str = None,
        exception_ref: str = None,
    ) -> Dict[str, Any]:
        """
        Create or retrieve customer seed record (PLC-003/004).
        
        Returns:
            Seed record as JSON dict + "created": bool flag
        """
        seed, created = self.placement_engine.get_or_create_seed(
            customer_realm_id=customer_realm_id,
            geography=geography,
            prod_region=prod_region,
            exception_ref=exception_ref,
            capacity_snapshot_ref="snap_placeholder",
        )
        
        return {
            **seed.to_dict(),
            "created": created,
        }
