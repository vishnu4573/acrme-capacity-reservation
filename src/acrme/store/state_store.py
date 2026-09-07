"""
State Store — ACRME v2.3

Versioned document store for entities, snapshots, operation records (TDD Section 6, 18).
"""

from typing import Optional, Dict, Any, List
from ..domain import CustomerSeedRecord
from ..domain.dr_index import SourceDestinationDRIndex
from ..domain.dr_declaration import DRDeclaration, DRActivationRecord


class StateStore:
    """
    Versioned document store (TDD Section 6).
    
    Characteristics (DAT-001..006):
        - Per-document optimistic concurrency (etag/version guards)
        - Freshness metadata on every snapshot (collected_at)
        - Append-only operation/audit records
        - Decision-traceable: capacity_snapshot_ref + policy_version
    
    Phase 3 skeleton: in-memory dict store. Production would use:
        - Azure Cosmos DB (document store with etag support)
        - Or Azure Table Storage (structured NoSQL)
        - Or Azure SQL (relational with version columns)
    """
    
    def __init__(self):
        # In-memory stores (Phase 3 skeleton)
        self._seeds: Dict[str, CustomerSeedRecord] = {}  # key: f"{customer_realm_id}:{geography}"
        self._snapshots: Dict[str, Any] = {}
        self._operations: list[Dict[str, Any]] = []

        # Phase 4 — Distributed DR state (DAT-002)
        # DR index entries keyed by f"{customer_realm_id}:{source_region}:{destination_region}"
        self._dr_index: Dict[str, SourceDestinationDRIndex] = {}
        self._dr_declarations: Dict[str, DRDeclaration] = {}  # key: declaration_id
        # Activation records keyed by f"{declaration_id}:{customer_realm_id}"
        self._dr_activations: Dict[str, DRActivationRecord] = {}
    
    def get_customer_seed(
        self,
        customer_realm_id: str,
        geography: str,
    ) -> Optional[CustomerSeedRecord]:
        """
        Get customer seed record (PLC-004 reuse).
        
        Returns:
            CustomerSeedRecord if exists, None otherwise
        """
        key = f"{customer_realm_id}:{geography}"
        return self._seeds.get(key)
    
    def write_customer_seed(self, seed: CustomerSeedRecord) -> None:
        """
        Write customer seed record (PLC-003 first placement).
        
        In production:
            - Check for existing record (idempotency)
            - Write with optimistic concurrency (etag guard)
            - Emit audit record
        """
        key = f"{seed.customer_realm_id}:{seed.geography}"
        self._seeds[key] = seed
        
        # Audit record (Phase 3 stub)
        self._operations.append({
            "operation": "create_seed",
            "customer_realm_id": seed.customer_realm_id,
            "geography": seed.geography,
            "timestamp": seed.decision_timestamp.isoformat(),
        })
    
    def write_snapshot(self, snapshot_ref: str, data: Dict[str, Any]) -> None:
        """Write capacity/quota snapshot with freshness timestamp."""
        self._snapshots[snapshot_ref] = data
    
    def get_snapshot(self, snapshot_ref: str) -> Optional[Dict[str, Any]]:
        """Retrieve snapshot by ref."""
        return self._snapshots.get(snapshot_ref)

    # ------------------------------------------------------------------ operations

    def append_operation(self, record: Dict[str, Any]) -> None:
        """Append an audit/operation record (append-only, DAT-001)."""
        self._operations.append(record)

    def list_operations(self) -> List[Dict[str, Any]]:
        """Return all audit/operation records."""
        return list(self._operations)

    # -------------------------------------------------- Phase 4: DR index (DR-018)

    @staticmethod
    def _dr_index_key(entry: SourceDestinationDRIndex) -> str:
        return f"{entry.customer_realm_id}:{entry.source_region}:{entry.destination_region}"

    def write_dr_index_entry(self, entry: SourceDestinationDRIndex) -> None:
        """Upsert a source→destination DR index entry (DR-018, DAT-002)."""
        self._dr_index[self._dr_index_key(entry)] = entry

    def list_dr_index_entries(self) -> List[SourceDestinationDRIndex]:
        """Return all DR index entries (bidirectional view, DR-016/018)."""
        return list(self._dr_index.values())

    def delete_dr_index_entry(self, entry: SourceDestinationDRIndex) -> None:
        """Remove a DR index entry (e.g. on customer migration / offboarding)."""
        self._dr_index.pop(self._dr_index_key(entry), None)

    # ----------------------------------------- Phase 4: DR declarations (DR-010/019)

    def write_dr_declaration(self, declaration: DRDeclaration) -> None:
        """Upsert a DR declaration (DR-010)."""
        self._dr_declarations[declaration.declaration_id] = declaration

    def get_dr_declaration(self, declaration_id: str) -> Optional[DRDeclaration]:
        """Retrieve a DR declaration by id."""
        return self._dr_declarations.get(declaration_id)

    def list_dr_declarations(self) -> List[DRDeclaration]:
        """Return all DR declarations."""
        return list(self._dr_declarations.values())

    def write_dr_activation_record(self, record: DRActivationRecord) -> None:
        """Upsert a per-customer DR activation record (DR-019, auditable)."""
        key = f"{record.declaration_id}:{record.customer_realm_id}"
        self._dr_activations[key] = record

    def list_dr_activation_records(
        self, declaration_id: Optional[str] = None
    ) -> List[DRActivationRecord]:
        """Return activation records, optionally filtered by declaration."""
        records = list(self._dr_activations.values())
        if declaration_id is not None:
            records = [r for r in records if r.declaration_id == declaration_id]
        return records
