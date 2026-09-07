"""
Readiness State & Codes — ACRME v2.3

Combined capacity+quota+freshness verdict (TDD Section 11.3, RDY-001..004).
Readiness = capacity ∧ quota ∧ freshness ∧ policy (TDD Section 2.1).
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class ReadinessCode(Enum):
    """Readiness verdict codes (TDD Section 11.3)"""
    
    # Green — ready to proceed
    READY = "READY"
    
    # Amber — not ready, actionable
    CAPACITY_INSUFFICIENT = "CAPACITY_INSUFFICIENT"
    QUOTA_INSUFFICIENT = "QUOTA_INSUFFICIENT"
    SNAPSHOT_STALE = "SNAPSHOT_STALE"
    
    # Red — blocked
    HARD_CONSTRAINT_VIOLATION = "HARD_CONSTRAINT_VIOLATION"
    POLICY_EXCEPTION_REQUIRED = "POLICY_EXCEPTION_REQUIRED"
    NO_SEED_RECORD = "NO_SEED_RECORD"
    DR_NOT_OFFERED = "DR_NOT_OFFERED"
    CONCURRENCY_CONFLICT = "CONCURRENCY_CONFLICT"


@dataclass(frozen=True)
class ReadinessState:
    """
    Combined readiness verdict for a deployment request (TDD Section 11.3, RDY-001).
    
    Readiness gate logic:
        1. Seed record exists (or can be created)
        2. Snapshot freshness: now() - collected_at <= max_snapshot_age
        3. Capacity available: Reserved_Quantity >= Allocated + Requested
        4. Quota available: Assigned_Quota - Current_Usage >= Requested
        5. No hard-constraint violations (HC-1..HC-10)
        6. No blocking policy exceptions
    
    Returns READY if all checks pass; specific error code otherwise.
    """
    
    code: ReadinessCode
    capacity_available_vcpu: int
    quota_available_vcpu: int
    snapshot_age_seconds: float
    blocking_constraint: Optional[str] = None
    message: Optional[str] = None
    capacity_snapshot_ref: Optional[str] = None
    policy_version: str = "v2.3"
    
    @property
    def is_ready(self) -> bool:
        """True if deployment can proceed."""
        return self.code == ReadinessCode.READY
    
    @property
    def is_actionable(self) -> bool:
        """True if not-ready but can be fixed (capacity/quota increase, wait for snapshot)."""
        return self.code in {
            ReadinessCode.CAPACITY_INSUFFICIENT,
            ReadinessCode.QUOTA_INSUFFICIENT,
            ReadinessCode.SNAPSHOT_STALE,
        }
    
    @property
    def is_blocked(self) -> bool:
        """True if blocked by policy/constraint (requires exception or design change)."""
        return self.code in {
            ReadinessCode.HARD_CONSTRAINT_VIOLATION,
            ReadinessCode.POLICY_EXCEPTION_REQUIRED,
            ReadinessCode.DR_NOT_OFFERED,
        }
