"""
Quota Pool State — ACRME v2.3

Single governed quota pool per region/family (TDD Section 5.3, QUA-004, ADR-002).
"""

from dataclasses import dataclass


@dataclass
class QuotaPoolState:
    """
    Single governed quota pool state (TDD Section 5.3, 8.3; QUA-004, ADR-002).
    
    Primary model: one pool covering Prod + NonProd/CVAL + DR. Prod and DR are
    protected by logical earmarks enforced at allocation time (not physical group
    separation). Emergency DR draw needs NO cross-group transfer.
    
    Quota arithmetic (TDD Section 8.3):
        Pool_Limit: Total governed quota (collected from unused cross-region defaults)
        Prod_Reserved_Floor: Protects production growth buffer
        DR_Earmark_vCPU: Protects DR capacity (max-not-sum per Appendix D, A.6)
        NonProd_Headroom = Pool_Limit - Prod_Reserved_Floor - DR_Earmark_vCPU
    
    Fields:
        region: Azure region
        vm_family: VM family (e.g. "standardDSv3Family")
        pool_limit: Total governed quota vCPU
        prod_reserved_floor: Prod floor (cannot be reclaimed for other uses)
        dr_earmark_vcpu: DR earmark (max-not-sum across all sources)
        current_usage_vcpu: Currently deployed vCPU across all environments
    """
    
    region: str
    vm_family: str
    pool_limit: int
    prod_reserved_floor: int
    dr_earmark_vcpu: int
    current_usage_vcpu: int
    
    @property
    def nonprod_headroom_vcpu(self) -> int:
        """Available headroom for NonProd/CVAL (TDD Section 8.3)."""
        return max(0, self.pool_limit - self.prod_reserved_floor - self.dr_earmark_vcpu)
    
    @property
    def available_for_allocation(self) -> int:
        """Quota available for new allocation (pool_limit - current_usage)."""
        return max(0, self.pool_limit - self.current_usage_vcpu)
    
    @property
    def headroom_ratio(self) -> float:
        """Headroom ratio for auto-increase threshold check (TDD Section 8.4, T16)."""
        if self.pool_limit == 0:
            return 0.0
        return self.available_for_allocation / self.pool_limit
