"""
Reservation State — ACRME v2.3

CRG and reservation snapshot state (TDD Section 5.2, CAP-001/002).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class ReservationState:
    """
    Snapshot of a CRG and its reservations (TDD Section 5.2, CAP-001/002).
    
    Three-CRG model per region (TDD Section 5.2):
        - One Prod CRG
        - One NonProd/CVAL CRG
        - One DR-standby CRG
    
    Cross-subscription sharing enabled between DR-standby CRG and consumer subscriptions
    (TDD Section 5.2, POC-001).
    
    Fields:
        crg_id: Capacity Reservation Group resource ID
        region: Azure region
        environment: "Prod" | "NonProd" | "CVAL" | "DR"
        sku_family: VM family
        reserved_quantity: Total reserved capacity (vCPU or instance count)
        allocated_quantity: Currently allocated (active deployments)
        associated_quantity: Associated but not allocated (standby DR)
        snapshot_timestamp: When this snapshot was collected (freshness check)
    """
    
    crg_id: str
    region: str
    environment: str  # "Prod" | "NonProd" | "CVAL" | "DR"
    sku_family: str
    reserved_quantity: int
    allocated_quantity: int
    associated_quantity: int = 0
    snapshot_timestamp: Optional[datetime] = None
    
    @property
    def available_capacity(self) -> int:
        """Available capacity (reserved - allocated)."""
        return max(0, self.reserved_quantity - self.allocated_quantity)
    
    @property
    def headroom_ratio(self) -> float:
        """Headroom ratio for auto-increase threshold."""
        if self.reserved_quantity == 0:
            return 0.0
        return self.available_capacity / self.reserved_quantity
