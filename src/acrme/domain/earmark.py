"""
CVAL Earmark Record — ACRME v2.3

Tracks CVAL capacity earmarked for DR activation (TDD Section 6.2, PLC-010, DR-005/006).
CVAL-sacrifice bootstrap pattern: co-located CVAL is releasable toward DR.
"""

from dataclasses import dataclass


@dataclass
class CVALEarmarkRecord:
    """
    Records that CVAL capacity is earmarked as releasable toward DR activation
    (TDD Section 6.2, PLC-010, DR-005/006).
    
    When CVAL and DR co-locate (mandatory in 2-region geographies per PLC-010a),
    the engine must NOT double-count the shared capacity as both live CVAL and
    available DR headroom.
    
    Fields:
        customer_realm_id: Customer identifier
        region: CVAL/DR co-located region
        cval_capacity_vcpu: vCPU reserved for CVAL (releasable for DR)
        earmarked_for_dr_vcpu: vCPU portion earmarked for DR activation
        colocated: True if CVAL and DR share the same region (PLC-010/010a)
    """
    
    customer_realm_id: str
    region: str
    cval_capacity_vcpu: int
    earmarked_for_dr_vcpu: int
    colocated: bool  # True if cval_region == dr_region
    
    @property
    def unearmarked_cval_vcpu(self) -> int:
        """CVAL capacity NOT earmarked for DR (pure CVAL headroom)."""
        return self.cval_capacity_vcpu - self.earmarked_for_dr_vcpu
