"""
State Reconciler — ACRME v2.3

Capacity reconciliation: enforces Allocated + Buffer floor, guarded scale-down,
never deletes (TDD Section 3, CAP-003/004/009/010, OPS-002).
"""

from typing import List, Any, Optional
from ..domain import ReservationState


class StateReconciler:
    """
    State Reconciler (TDD Section 3, 10).
    
    Every reconciliation cycle:
        1. Read desired state (seed records, DR index, earmarks)
        2. Read actual state (CRG snapshots from InventoryCollector)
        3. Compute delta: desired_floor = Allocated + Buffer
        4. If actual < desired_floor: scale up
        5. If actual > desired_floor + threshold: guarded scale-down (OPS-002)
        6. Never delete CRGs (CAP-010)
    
    Phase 3 skeleton: reconciliation loop structure, Azure mutation methods stubbed.
    """
    
    def __init__(self, azure_client: Any = None):
        self.azure_client = azure_client  # Azure SDK client for CRG mutations
    
    def reconcile_region_capacity(
        self,
        region: str,
        sku_family: str,
        desired_reservations: List[ReservationState],
        actual_reservations: List[ReservationState],
    ) -> None:
        """
        Reconcile capacity for a region/sku_family (TDD Section 10).
        
        Args:
            region: Azure region
            sku_family: VM family
            desired_reservations: Desired state (from seed records, DR index)
            actual_reservations: Actual state (from InventoryCollector snapshot)
        
        Logic:
            For each environment (Prod, NonProd, DR):
                1. Compute desired_floor = allocated + buffer
                2. If actual < desired_floor: scale up via Azure API
                3. If actual > desired_floor + scale_down_threshold: guarded scale-down
        """
        # Phase 3 skeleton: reconciliation structure
        for desired in desired_reservations:
            actual = self._find_matching_reservation(desired, actual_reservations)
            
            if actual is None:
                # CRG doesn't exist: create it (CAP-001)
                self._create_crg(desired)
                continue
            
            desired_floor = desired.allocated_quantity  # + buffer (from policy)
            actual_qty = actual.reserved_quantity
            
            if actual_qty < desired_floor:
                # Scale up to floor
                delta = desired_floor - actual_qty
                self._scale_up_reservation(actual.crg_id, delta)
            elif actual_qty > desired_floor + 10:  # Placeholder threshold
                # Guarded scale-down (OPS-002)
                delta = actual_qty - desired_floor
                self._scale_down_reservation(actual.crg_id, delta)
    
    def _find_matching_reservation(
        self,
        desired: ReservationState,
        actuals: List[ReservationState],
    ) -> Optional[ReservationState]:
        """Find matching actual reservation by region/environment/sku."""
        for actual in actuals:
            if (
                actual.region == desired.region
                and actual.environment == desired.environment
                and actual.sku_family == desired.sku_family
            ):
                return actual
        return None
    
    def _create_crg(self, desired: ReservationState) -> None:
        """Create new CRG via Azure API (Phase 3 stub)."""
        # azure_client.create_capacity_reservation_group(...)
        pass
    
    def _scale_up_reservation(self, crg_id: str, delta: int) -> None:
        """Increase reservation quantity (Phase 3 stub)."""
        # azure_client.update_capacity_reservation(crg_id, increase_by=delta)
        pass
    
    def _scale_down_reservation(self, crg_id: str, delta: int) -> None:
        """Guarded scale-down (OPS-002) (Phase 3 stub)."""
        # Check safety conditions, then scale down
        pass
