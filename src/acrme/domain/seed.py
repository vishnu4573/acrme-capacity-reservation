"""
Customer Seed Record — ACRME v2.3

First placement decision becomes the authoritative seed; subsequent products/
environments for the same customer+geography read the seed instead of re-selecting
(TDD Section 6.2, PLC-003/004, DAT-003).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class CustomerSeedRecord:
    """
    Authoritative placement seed for a customer in a geography (TDD Section 6.2, PLC-003).
    
    Created on first placement; reused for all subsequent products/environments in that
    geography. "Their production is their production for all products in that geography."
    
    Attributes aligned to Requirements Baseline v2.3:
        - Five geographies: US (3-region), Europe/Australia/Asia Pacific/Middle East (2-region)
        - Two-region geos: CVAL+DR co-locate deterministically (PLC-010a)
        - Middle East: dr_region = "NOT_OFFERED" until DEC-001 clears (DR-014)
    
    Fields (TDD Section 6.2):
        customer_realm_id: Unique customer/realm identifier
        geography: US | Europe | Australia | "Asia Pacific" | "Middle East"
        prod_region: Azure region (exact, validated via HC-1..HC-10)
        cval_region: CVAL/NonProd region (may == dr_region if co-located)
        dr_region: DR region, or "NOT_OFFERED" (Middle East per DEC-001)
        distribution_model: "3-region" | "2-region" (from RegionCatalogue, REG-001/003)
        cval_dr_colocated: True if cval_region == dr_region (PLC-010/010a)
        
        decision_timestamp: When seed was created (ISO 8601)
        policy_version: PlacementPolicy version that drove this decision (v2.3)
        capacity_snapshot_ref: Snapshot ID for deterministic replay (DAT-002)
        exception_ref: Exception approval ID if geography-only input was used (PLC-002)
        products_covered: List of products using this seed
    """
    
    # Identity
    customer_realm_id: str
    geography: str  # US | Europe | Australia | "Asia Pacific" | "Middle East"
    
    # Placement decision
    prod_region: str
    cval_region: str
    dr_region: str  # or "NOT_OFFERED"
    distribution_model: str  # "3-region" | "2-region"
    cval_dr_colocated: bool  # True if cval_region == dr_region (PLC-010/010a)
    
    # Provenance
    decision_timestamp: datetime
    policy_version: str  # e.g. "v2.3"
    capacity_snapshot_ref: str
    exception_ref: Optional[str] = None  # Set if geography-only input (PLC-002)
    
    # Reuse tracking
    products_covered: list[str] = None  # Products using this seed
    
    def __post_init__(self):
        if self.products_covered is None:
            self.products_covered = []
    
    @property
    def is_two_region_geography(self) -> bool:
        """True if geography runs the 2-region distribution model (REG-003)."""
        return self.distribution_model == "2-region"
    
    @property
    def dr_offered(self) -> bool:
        """True if DR is offered (not Middle East with DR_NOT_OFFERED)."""
        return self.dr_region != "NOT_OFFERED"
    
    def to_dict(self) -> dict:
        """Serialize for state store (DAT-001)."""
        return {
            "customer_realm_id": self.customer_realm_id,
            "geography": self.geography,
            "prod_region": self.prod_region,
            "cval_region": self.cval_region,
            "dr_region": self.dr_region,
            "distribution_model": self.distribution_model,
            "cval_dr_colocated": self.cval_dr_colocated,
            "decision_timestamp": self.decision_timestamp.isoformat(),
            "policy_version": self.policy_version,
            "capacity_snapshot_ref": self.capacity_snapshot_ref,
            "exception_ref": self.exception_ref,
            "products_covered": self.products_covered,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "CustomerSeedRecord":
        """Deserialize from state store (DAT-001)."""
        return cls(
            customer_realm_id=data["customer_realm_id"],
            geography=data["geography"],
            prod_region=data["prod_region"],
            cval_region=data["cval_region"],
            dr_region=data["dr_region"],
            distribution_model=data["distribution_model"],
            cval_dr_colocated=data["cval_dr_colocated"],
            decision_timestamp=datetime.fromisoformat(data["decision_timestamp"]),
            policy_version=data["policy_version"],
            capacity_snapshot_ref=data["capacity_snapshot_ref"],
            exception_ref=data.get("exception_ref"),
            products_covered=data.get("products_covered", []),
        )
