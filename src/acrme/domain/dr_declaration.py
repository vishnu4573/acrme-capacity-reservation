"""
DR Declaration & Activation Records — ACRME v2.3

Entities backing the DR declaration workflow and standby activation
(TDD Section 12A; DR-009/010/013/019).

A DR declaration is an authorised, auditable event that fails a source region
over to its pre-placed standby DR instances in the surviving regions. The engine
transitions each protected customer's DR block from *associated* (standby) to
*allocated* (active) in approved business-priority wave order (DR-009/019), and
reverses the transition on failback (DR-013).
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class DRDeclarationStatus(str, Enum):
    """Lifecycle of a DR declaration (mirrors the T6 engine state machine)."""

    PENDING = "DR_DECLARATION_PENDING"   # authorised, not yet activated
    ACTIVE = "DR_EVENT_ACTIVE"           # standby set activated (associated → allocated)
    FAILBACK_PENDING = "FAILBACK_PENDING"  # source recovered, unwinding
    INCIDENT_HOLD = "INCIDENT_HOLD"      # safety trip — activation/failback paused
    COMPLETED = "COMPLETED"              # failed region recovered, failback done
    SIMULATED = "SIMULATED"             # dry-run / annual mock drill (DR-012)


class ActivationState(str, Enum):
    """Per-customer DR instance activation state (DR-019)."""

    ASSOCIATED = "associated"  # standby — reserved, not consuming compute
    ALLOCATED = "allocated"    # active — failed over, consuming compute
    RELEASED = "released"      # torn down after failback (DR-013)
    FAILED = "failed"          # activation could not acquire capacity


@dataclass
class DRActivationRecord:
    """
    Auditable record of a single customer's standby → active transition during a
    DR declaration (DR-019). Reversible on failback (DR-013).

    Fields:
        declaration_id: Parent DRDeclaration this activation belongs to
        customer_realm_id: Customer being failed over
        source_region: The failed production region
        destination_region: Region holding this customer's standby DR (DR-018)
        protected_vcpu: vCPU the standby must carry when active
        priority_wave: Business-priority wave (0 = P0 platform first; DR-009)
        from_state / to_state: activation transition
        acquisition_step: Which staged-acquisition step (DR-006) supplied capacity
        cval_sacrificed_vcpu: CVAL released in destination to fund activation (DR-005)
        transitioned_at: Timestamp of the transition
        capacity_snapshot_ref: Snapshot for deterministic replay
        notes: Free-text audit annotation
    """

    declaration_id: str
    customer_realm_id: str
    source_region: str
    destination_region: str
    protected_vcpu: int
    priority_wave: int
    from_state: ActivationState = ActivationState.ASSOCIATED
    to_state: ActivationState = ActivationState.ALLOCATED
    acquisition_step: Optional[str] = None
    cval_sacrificed_vcpu: int = 0
    transitioned_at: Optional[datetime] = None
    capacity_snapshot_ref: Optional[str] = None
    notes: str = ""

    @property
    def succeeded(self) -> bool:
        """True if the customer is now allocated (active)."""
        return self.to_state == ActivationState.ALLOCATED

    def to_dict(self) -> dict:
        return {
            "declaration_id": self.declaration_id,
            "customer_realm_id": self.customer_realm_id,
            "source_region": self.source_region,
            "destination_region": self.destination_region,
            "protected_vcpu": self.protected_vcpu,
            "priority_wave": self.priority_wave,
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "acquisition_step": self.acquisition_step,
            "cval_sacrificed_vcpu": self.cval_sacrificed_vcpu,
            "transitioned_at": self.transitioned_at.isoformat() if self.transitioned_at else None,
            "capacity_snapshot_ref": self.capacity_snapshot_ref,
            "notes": self.notes,
        }


@dataclass
class DRDeclaration:
    """
    An authorised DR failover event for a single source region (DR-010).

    Under the single-region-failure assumption (DR-001), exactly one source region
    is failing; this declaration drives activation of every customer whose Prod was
    in that region onto their pre-placed standby DR (DR-018/019).

    Fields:
        declaration_id: Unique id
        source_region: The failed production region
        geography: Parent geography of the source region
        status: DRDeclarationStatus
        authorised_by: Approver identity (DR-010 governance)
        is_simulation: True for annual mock drill / dry-run (DR-012)
        declared_at / activated_at / failback_at / completed_at: lifecycle timestamps
        activation_records: per-customer transitions (DR-019)
        capacity_snapshot_ref: snapshot at declaration time
        policy_version: policy in force at declaration (deterministic replay)
    """

    declaration_id: str
    source_region: str
    geography: str
    status: DRDeclarationStatus = DRDeclarationStatus.PENDING
    authorised_by: Optional[str] = None
    is_simulation: bool = False
    declared_at: Optional[datetime] = None
    activated_at: Optional[datetime] = None
    failback_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    activation_records: list = field(default_factory=list)  # list[DRActivationRecord]
    capacity_snapshot_ref: Optional[str] = None
    policy_version: str = "v2.3"

    @property
    def is_active(self) -> bool:
        return self.status == DRDeclarationStatus.ACTIVE

    @property
    def customers_failed_over(self) -> int:
        return sum(1 for r in self.activation_records if r.succeeded)

    @property
    def customers_failed(self) -> int:
        return sum(1 for r in self.activation_records if r.to_state == ActivationState.FAILED)

    @property
    def total_protected_vcpu(self) -> int:
        return sum(r.protected_vcpu for r in self.activation_records if r.succeeded)

    def to_dict(self) -> dict:
        return {
            "declaration_id": self.declaration_id,
            "source_region": self.source_region,
            "geography": self.geography,
            "status": self.status.value,
            "authorised_by": self.authorised_by,
            "is_simulation": self.is_simulation,
            "declared_at": self.declared_at.isoformat() if self.declared_at else None,
            "activated_at": self.activated_at.isoformat() if self.activated_at else None,
            "failback_at": self.failback_at.isoformat() if self.failback_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "activation_records": [r.to_dict() for r in self.activation_records],
            "capacity_snapshot_ref": self.capacity_snapshot_ref,
            "policy_version": self.policy_version,
        }
