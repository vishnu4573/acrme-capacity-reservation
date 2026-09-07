"""
Source→Destination DR Index — ACRME v2.3

Tracks reciprocal multi-source DR hosting with max-not-sum sizing (TDD Section 6.2,
DR-016/017/018, ADR-005).
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class SourceDestinationDRIndex:
    """
    Maps each source region's DR workload to destination regions (TDD Section 6.2, DR-018).
    
    Max-not-sum sizing (DR-017, ADR-005): destination reserves max(all sources assigned
    to it), not sum. Enables reciprocal hosting without N×N explosion.
    
    Fields:
        source_region: Production region
        destination_region: DR-hosting region
        customer_realm_id: Customer identifier
        protected_vcpu: vCPU portion of this customer's Prod workload in source_region
                        that must be protected in destination_region
        priority_wave: Activation wave (P0 platform, P-1..P-N; lower = higher priority)
        activation_state: "associated" | "allocated" | "released"
        capacity_snapshot_ref: Snapshot ID for deterministic replay
    """
    
    source_region: str
    destination_region: str
    customer_realm_id: str
    protected_vcpu: int
    priority_wave: int  # 0 = P0 platform, 1 = P-1, etc.
    activation_state: str = "associated"  # "associated" | "allocated" | "released"
    capacity_snapshot_ref: Optional[str] = None
    
    @property
    def is_active(self) -> bool:
        """True if DR is allocated (active failover)."""
        return self.activation_state == "allocated"
