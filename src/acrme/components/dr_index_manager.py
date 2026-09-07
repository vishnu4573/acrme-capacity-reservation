"""
DR Index Manager — ACRME v2.3

Maintains and queries the authoritative source→destination DR index
(DR-018) and the reciprocal, bidirectional multi-source hosting view (DR-016).

The index is the reverse view of the per-customer seed record (PLC-003): each
seed says where a customer's Prod/CVAL/DR live; the index answers, for a given
source region, *which destinations hold its customers' standby DR and how much*,
and — reciprocally — for a given destination, *which sources it protects*.

On a regional failure the DRActivationEngine consults this index to determine
exactly which standby instances to activate and where (DR-018/019).
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..domain.dr_index import SourceDestinationDRIndex
from ..domain.seed import CustomerSeedRecord
from ..store.state_store import StateStore


class DRIndexManager:
    """
    Manager for the bidirectional source→destination DR index (DR-016/018).

    Responsibilities:
        - Register a customer's DR placement (typically derived from the seed).
        - Query destinations for a source region (failover lookup, DR-018).
        - Query sources protected by a destination (sizing input, DR-017).
        - Produce the reciprocal many-to-many hosting view (DR-016).

    Persistence is delegated to the StateStore (DAT-002). This class holds no
    authoritative state of its own beyond a reference to the store.
    """

    def __init__(self, state_store: StateStore):
        self.state_store = state_store

    # ------------------------------------------------------------------ register

    def register_placement(
        self,
        customer_realm_id: str,
        source_region: str,
        destination_region: str,
        protected_vcpu: int,
        priority_wave: int = 0,
        capacity_snapshot_ref: Optional[str] = None,
    ) -> SourceDestinationDRIndex:
        """
        Record that `customer_realm_id`'s DR (source=Prod region) is standby-hosted
        in `destination_region` (DR-018).

        Middle East (DR_NOT_OFFERED, DEC-001) customers must NOT be registered with
        a destination; that is enforced upstream in placement (seed.dr_region ==
        "NOT_OFFERED"). This method assumes a real destination region is supplied.
        """
        if not destination_region or destination_region == "NOT_OFFERED":
            raise ValueError(
                "Cannot register a DR index entry without a destination region "
                "(DR_NOT_OFFERED customers have no standby placement — DEC-001)."
            )
        if source_region == destination_region:
            raise ValueError(
                "DR standby must be in a different region from Prod (ENV-003)."
            )

        entry = SourceDestinationDRIndex(
            source_region=source_region,
            destination_region=destination_region,
            customer_realm_id=customer_realm_id,
            protected_vcpu=protected_vcpu,
            priority_wave=priority_wave,
            activation_state="associated",
            capacity_snapshot_ref=capacity_snapshot_ref,
        )
        self.state_store.write_dr_index_entry(entry)
        return entry

    def register_from_seed(
        self,
        seed: CustomerSeedRecord,
        protected_vcpu: int,
        priority_wave: int = 0,
    ) -> Optional[SourceDestinationDRIndex]:
        """
        Derive a DR index entry from a customer seed (the reverse view of PLC-003).

        Returns None for DR_NOT_OFFERED customers (Middle East, DEC-001) — they
        have production but no standby DR placement, so no index entry exists.
        """
        if not seed.dr_offered:
            return None
        return self.register_placement(
            customer_realm_id=seed.customer_realm_id,
            source_region=seed.prod_region,
            destination_region=seed.dr_region,
            protected_vcpu=protected_vcpu,
            priority_wave=priority_wave,
            capacity_snapshot_ref=seed.capacity_snapshot_ref,
        )

    # --------------------------------------------------------------------- query

    def destinations_for_source(self, source_region: str) -> List[SourceDestinationDRIndex]:
        """
        Which destinations hold DR for customers whose Prod is in `source_region`?
        This is the failover lookup used on declaration (DR-018/019).
        """
        return [
            e for e in self.state_store.list_dr_index_entries()
            if e.source_region == source_region
        ]

    def sources_for_destination(self, destination_region: str) -> List[SourceDestinationDRIndex]:
        """
        Which sources does `destination_region` protect? Input to max-not-sum
        sizing (DR-017): the destination must absorb the largest single source.
        """
        return [
            e for e in self.state_store.list_dr_index_entries()
            if e.destination_region == destination_region
        ]

    def portions_by_destination(self) -> Dict[str, List[SourceDestinationDRIndex]]:
        """Group every index entry by destination region (sizing input for all)."""
        grouped: Dict[str, List[SourceDestinationDRIndex]] = {}
        for e in self.state_store.list_dr_index_entries():
            grouped.setdefault(e.destination_region, []).append(e)
        return grouped

    def reciprocal_view(self) -> Dict[str, Dict[str, object]]:
        """
        Build the many-to-many reciprocal hosting view (DR-016): for each region,
        the set of source regions it protects (as a destination) and the set of
        destinations that protect it (as a source).

        Returns:
            {region: {"protects_sources": {..}, "protected_by_destinations": {..}}}
        """
        view: Dict[str, Dict[str, set]] = {}

        def _slot(region: str) -> Dict[str, set]:
            return view.setdefault(
                region, {"protects_sources": set(), "protected_by_destinations": set()}
            )

        for e in self.state_store.list_dr_index_entries():
            _slot(e.destination_region)["protects_sources"].add(e.source_region)
            _slot(e.source_region)["protected_by_destinations"].add(e.destination_region)

        # Materialise sets to sorted lists for stable, serialisable output.
        return {
            region: {
                "protects_sources": sorted(slots["protects_sources"]),
                "protected_by_destinations": sorted(slots["protected_by_destinations"]),
            }
            for region, slots in view.items()
        }

    def overcommit_summary(self) -> Dict[str, float]:
        """
        Per-destination overcommit ratio SUM/MAX (A.8) across source portions —
        the exposure measure if the single-failure assumption is violated.
        """
        summary: Dict[str, float] = {}
        for dest, entries in self.portions_by_destination().items():
            totals: Dict[str, int] = {}
            for e in entries:
                totals[e.source_region] = totals.get(e.source_region, 0) + e.protected_vcpu
            vals = list(totals.values())
            max_v = max(vals) if vals else 0
            summary[dest] = (sum(vals) / max_v) if max_v > 0 else 1.0
        return summary
