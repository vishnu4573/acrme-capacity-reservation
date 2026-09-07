"""
DR Simulator & Compliance Evidence — ACRME v2.3

Dry-run DR failover simulation and compliance-evidence generation
(DR-012 annual mock drill; FIN-008/POC-011 overcommit exposure; SOC 2 DR assertions).

The simulator runs the real DRActivationEngine in *simulation* mode: it exercises
the DR-018 index lookup, DR-009 priority-wave ordering and DR-006 staged acquisition
for a hypothetical region failure WITHOUT mutating live standby state, then rolls the
max-not-sum sizing (DR-017) and overcommit ratios (A.8) into an auditable report.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..algorithms.dr_sizing import DRSizer
from ..domain.dr_declaration import DRDeclaration
from ..store.state_store import StateStore
from .dr_activation import DRActivationEngine
from .dr_index_manager import DRIndexManager


class DRSimulator:
    """
    DR failover simulator and compliance-evidence generator (DR-012).

    Produces, for a simulated single-region failure (DR-001):
        - the standby set that would activate and whether each customer is covered;
        - the destination sizing verdict (max-not-sum, DR-017) and any capacity gap;
        - the overcommit ratio exposure (A.8) for leadership sign-off (POC-011);
        - a timestamped evidence record suitable for SOC 2 DR assertions (FIN-007).
    """

    def __init__(
        self,
        state_store: StateStore,
        index_manager: DRIndexManager,
        activation_engine: DRActivationEngine,
        sizer: Optional[DRSizer] = None,
    ):
        self.state_store = state_store
        self.index_manager = index_manager
        self.activation_engine = activation_engine
        self.sizer = sizer or DRSizer(default_basis="max")

    def simulate_region_failure(
        self,
        source_region: str,
        geography: str,
        authorised_by: str = "dr-drill-runner",
        capacity_snapshot_ref: Optional[str] = None,
    ) -> Dict[str, object]:
        """
        Simulate failover of `source_region` and return a compliance-evidence dict.

        The declaration is created with is_simulation=True so live index/standby
        state is never mutated (DR-012 non-destructive drill).
        """
        declaration_id = (
            f"SIM-{source_region.replace(' ', '_')}-"
            f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        )
        declaration = self.activation_engine.declare(
            declaration_id=declaration_id,
            source_region=source_region,
            geography=geography,
            authorised_by=authorised_by,
            capacity_snapshot_ref=capacity_snapshot_ref,
            is_simulation=True,
        )
        declaration = self.activation_engine.activate(declaration)

        evidence = self._build_evidence(declaration)
        self.state_store.append_operation(
            {"operation": "dr_simulation", "declaration_id": declaration_id,
             "source_region": source_region, "covered": evidence["all_customers_covered"]}
        )
        return evidence

    def simulate_all_regions(self, geographies: Dict[str, str]) -> List[Dict[str, object]]:
        """
        Run a drill across multiple source regions (DR-012 annual programme).

        Args:
            geographies: {source_region: geography}
        Returns:
            list of evidence dicts, one per simulated region failure.
        """
        return [
            self.simulate_region_failure(region, geo)
            for region, geo in geographies.items()
        ]

    # ------------------------------------------------------------------ evidence

    def _build_evidence(self, declaration: DRDeclaration) -> Dict[str, object]:
        """Assemble the compliance-evidence record for a simulated declaration."""
        # Sizing verdict for each destination that protects the failed source.
        portions = self.index_manager.destinations_for_source(declaration.source_region)
        by_dest: Dict[str, list] = {}
        for e in portions:
            by_dest.setdefault(e.destination_region, []).append(e)

        sizing = {
            dest: self.sizer.size_destination(dest, entries).to_dict()
            for dest, entries in by_dest.items()
        }

        records = declaration.activation_records
        all_covered = all(r.succeeded for r in records) if records else True

        return {
            "declaration_id": declaration.declaration_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_region": declaration.source_region,
            "geography": declaration.geography,
            "is_simulation": declaration.is_simulation,
            "policy_version": declaration.policy_version,
            "customers_in_scope": len(records),
            "customers_covered": declaration.customers_failed_over,
            "customers_uncovered": declaration.customers_failed,
            "all_customers_covered": all_covered,
            "total_protected_vcpu": declaration.total_protected_vcpu,
            "destination_sizing": sizing,
            "overcommit_ratios": self.index_manager.overcommit_summary(),
            "activation_records": [r.to_dict() for r in records],
            "assumption": "single-region failure (DR-001); max-not-sum sizing (DR-017)",
            "note": (
                "Non-destructive drill (DR-012). Uncovered customers indicate a DR "
                "capacity gap (A.7) requiring staged acquisition or SUM override (C-11)."
            ),
        }
