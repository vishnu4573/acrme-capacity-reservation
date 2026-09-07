"""
State Store — ACRME v2.3

Versioned document store for entities, snapshots, operation records (TDD Section 6, 18).
"""

from typing import Optional, Dict, Any
from ..domain import CustomerSeedRecord


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
