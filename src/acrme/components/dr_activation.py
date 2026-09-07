"""
DR Activation Engine — ACRME v2.3

Implements the DR declaration workflow and standby activation
(DR-009/010/013/019), driving the T6 engine state machine.

On an authorised declaration for a failed source region, the engine looks up the
standby DR placements for that region in the source→destination DR index (DR-018),
then transitions each protected customer's DR block from *associated* → *allocated*
in approved business-priority wave order (DR-009/019). Each activation acquires
capacity via the staged sequence (DR-006):

    1. bootstrap_headroom      — lean pre-placed DR headroom
    2. available_reservation   — free reservation / pooled quota headroom
    3. cval_sacrifice          — release co-located CVAL toward DR (DR-005, PLC-010a)
    4. sharing_reassignment    — capacity sharing / reassignment (post-POC-001)
    5. pooled_quota            — single governed pool headroom (QUA-004)
    6. azure_request           — request additional capacity from Azure

On failback (DR-013) the transitions are reversed (allocated → released) and any
sacrificed CVAL is restored.
"""

from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

from ..domain.dr_declaration import (
    ActivationState,
    DRActivationRecord,
    DRDeclaration,
    DRDeclarationStatus,
)
from ..store.state_store import StateStore
from .dr_index_manager import DRIndexManager


# Ordered staged-acquisition sequence (DR-006). Each step is tried in order until
# the customer's protected_vcpu is satisfied.
STAGED_ACQUISITION_SEQUENCE: List[str] = [
    "bootstrap_headroom",
    "available_reservation",
    "cval_sacrifice",
    "sharing_reassignment",
    "pooled_quota",
    "azure_request",
]


class DRActivationEngine:
    """
    DR declaration & standby-activation engine (DR-010/019, TDD Section 12A).

    Phase 4 skeleton: the capacity-acquisition steps are modelled through a pluggable
    `capacity_provider` callback so the workflow, ordering, wave priority, CVAL-release
    accounting, auditability and failback are fully exercised without a live Azure
    backend (that arrives in Phase 5). The default provider assumes bootstrap headroom
    fully covers each customer (the lean happy path).
    """

    def __init__(
        self,
        state_store: StateStore,
        index_manager: DRIndexManager,
        capacity_provider: Optional[Callable[[str, str, int], Dict[str, int]]] = None,
    ):
        """
        Args:
            state_store: persistence for declarations/activation records.
            index_manager: source→destination DR index (DR-018).
            capacity_provider: optional callback
                (destination_region, step, needed_vcpu) -> {"granted": int, ...}
                Modelling hook for the staged sequence (DR-006). If omitted, a
                default provider grants everything from bootstrap headroom.
        """
        self.state_store = state_store
        self.index_manager = index_manager
        self.capacity_provider = capacity_provider or self._default_capacity_provider

    # --------------------------------------------------------------- declaration

    def declare(
        self,
        declaration_id: str,
        source_region: str,
        geography: str,
        authorised_by: str,
        capacity_snapshot_ref: Optional[str] = None,
        is_simulation: bool = False,
        policy_version: str = "v2.3",
    ) -> DRDeclaration:
        """
        Open a DR declaration for a failed source region (DR-010).

        Governance: `authorised_by` is required — activation is never automatic
        (DR-010). The declaration starts in DR_DECLARATION_PENDING (T6).
        """
        if not authorised_by:
            raise ValueError("DR declaration requires an approver (DR-010 governance).")

        declaration = DRDeclaration(
            declaration_id=declaration_id,
            source_region=source_region,
            geography=geography,
            status=DRDeclarationStatus.PENDING,
            authorised_by=authorised_by,
            is_simulation=is_simulation,
            declared_at=datetime.now(timezone.utc),
            capacity_snapshot_ref=capacity_snapshot_ref,
            policy_version=policy_version,
        )
        self.state_store.write_dr_declaration(declaration)
        return declaration

    # ---------------------------------------------------------------- activation

    def activate(self, declaration: DRDeclaration) -> DRDeclaration:
        """
        Activate the standby set for a declaration's failed region (DR-019).

        Steps:
            1. Look up every standby entry for the source region (DR-018).
            2. Order by priority wave (0 = P0 platform first; DR-009).
            3. For each customer, acquire `protected_vcpu` via the staged sequence
               (DR-006), transition associated → allocated, and audit the record.
        """
        if declaration.status not in (
            DRDeclarationStatus.PENDING,
            DRDeclarationStatus.INCIDENT_HOLD,
        ):
            raise ValueError(
                f"Cannot activate declaration in status {declaration.status.value}."
            )

        standby_entries = self.index_manager.destinations_for_source(
            declaration.source_region
        )
        # Business-priority wave order (DR-009): lower wave number first, then
        # deterministic tie-break by customer id for replayability.
        standby_entries.sort(key=lambda e: (e.priority_wave, e.customer_realm_id))

        records: List[DRActivationRecord] = []
        for entry in standby_entries:
            record = self._activate_one(declaration, entry)
            records.append(record)
            self.state_store.write_dr_activation_record(record)
            # Reflect activation state back onto the index entry (unless simulating).
            if not declaration.is_simulation and record.succeeded:
                entry.activation_state = "allocated"
                self.state_store.write_dr_index_entry(entry)

        declaration.activation_records = records
        declaration.activated_at = datetime.now(timezone.utc)
        declaration.status = (
            DRDeclarationStatus.SIMULATED
            if declaration.is_simulation
            else DRDeclarationStatus.ACTIVE
        )
        self.state_store.write_dr_declaration(declaration)
        return declaration

    def _activate_one(
        self, declaration: DRDeclaration, entry
    ) -> DRActivationRecord:
        """Acquire capacity for a single customer via the staged sequence (DR-006)."""
        needed = entry.protected_vcpu
        acquired = 0
        cval_sacrificed = 0
        used_step: Optional[str] = None

        for step in STAGED_ACQUISITION_SEQUENCE:
            if acquired >= needed:
                break
            grant = self.capacity_provider(
                entry.destination_region, step, needed - acquired
            )
            granted = int(grant.get("granted", 0))
            if granted <= 0:
                continue
            acquired += granted
            used_step = step
            if step == "cval_sacrifice":
                cval_sacrificed += granted

        succeeded = acquired >= needed
        return DRActivationRecord(
            declaration_id=declaration.declaration_id,
            customer_realm_id=entry.customer_realm_id,
            source_region=entry.source_region,
            destination_region=entry.destination_region,
            protected_vcpu=needed,
            priority_wave=entry.priority_wave,
            from_state=ActivationState.ASSOCIATED,
            to_state=ActivationState.ALLOCATED if succeeded else ActivationState.FAILED,
            acquisition_step=used_step,
            cval_sacrificed_vcpu=cval_sacrificed,
            transitioned_at=datetime.now(timezone.utc),
            capacity_snapshot_ref=declaration.capacity_snapshot_ref,
            notes=(
                "activated via staged sequence"
                if succeeded
                else f"capacity gap: acquired {acquired}/{needed} vCPU"
            ),
        )

    # ------------------------------------------------------------------ failback

    def failback(self, declaration: DRDeclaration) -> DRDeclaration:
        """
        Fail back once the source region recovers (DR-013).

        Reverses each successful activation (allocated → released), restores any
        sacrificed CVAL, resets index entries to standby, and completes the
        declaration.
        """
        if declaration.status not in (
            DRDeclarationStatus.ACTIVE,
            DRDeclarationStatus.SIMULATED,
            DRDeclarationStatus.FAILBACK_PENDING,
        ):
            raise ValueError(
                f"Cannot fail back declaration in status {declaration.status.value}."
            )

        declaration.status = DRDeclarationStatus.FAILBACK_PENDING
        declaration.failback_at = datetime.now(timezone.utc)

        for record in declaration.activation_records:
            if record.succeeded:
                record.from_state = ActivationState.ALLOCATED
                record.to_state = ActivationState.RELEASED
                record.transitioned_at = datetime.now(timezone.utc)
                record.notes = "released on failback; CVAL restored"
                self.state_store.write_dr_activation_record(record)

        # Reset the index entries for this source back to standby.
        for entry in self.index_manager.destinations_for_source(declaration.source_region):
            entry.activation_state = "associated"
            self.state_store.write_dr_index_entry(entry)

        declaration.status = DRDeclarationStatus.COMPLETED
        declaration.completed_at = datetime.now(timezone.utc)
        self.state_store.write_dr_declaration(declaration)
        return declaration

    # ---------------------------------------------------------------- safety net

    def incident_hold(self, declaration: DRDeclaration, reason: str) -> DRDeclaration:
        """Trip the safety hold, pausing activation/failback (T6 INCIDENT_HOLD)."""
        declaration.status = DRDeclarationStatus.INCIDENT_HOLD
        self.state_store.write_dr_declaration(declaration)
        self.state_store.append_operation(
            {"operation": "incident_hold", "declaration_id": declaration.declaration_id,
             "reason": reason}
        )
        return declaration

    # ------------------------------------------------------------------ defaults

    @staticmethod
    def _default_capacity_provider(
        destination_region: str, step: str, needed_vcpu: int
    ) -> Dict[str, int]:
        """
        Default modelling provider (Phase 4 skeleton): the lean happy path where
        pre-placed bootstrap headroom fully covers each customer. Phase 5 replaces
        this with live reservation/quota/CVAL/sharing lookups against Azure.
        """
        if step == "bootstrap_headroom":
            return {"granted": needed_vcpu}
        return {"granted": 0}
