"""
ACRME Phase 4 Demo — Distributed DR Capacity Management

Exercises the Phase 4 components against the reviewed worked example from
Requirements Baseline v2.3 §12A.2 (Distributed DR Reference Model) and
Appendix D.3 (max-not-sum sizing):

    Region       Prod            DR standby hosted (source region)
    Region 1     Cust1,3,5       Cust2 (R2), Cust7 (R3)
    Region 2     Cust2,4         Cust1 (R1), Cust6 (R3), Cust5 (R1)
    Region 3     Cust6,7         Cust3 (R1), Cust4 (R2)

Appendix D.3 sizing for Region 2 (destination): protects R1 (Cust1+Cust5 = 120)
and R3 (Cust6 = 80). Max-not-sum requirement = max(120, 80) = 120 (not 200);
overcommit ratio = 200/120 ≈ 1.67.

Run:  python examples/phase4_demo.py
"""

from acrme.store.state_store import StateStore
from acrme.components import DRIndexManager, DRActivationEngine, DRSimulator
from acrme.algorithms import DRSizer


def build_index(mgr: DRIndexManager) -> None:
    """Register the reviewed diagram's DR placements (source, dest, vcpu, wave)."""
    # (customer, source=Prod region, destination=DR region, protected_vcpu, wave)
    placements = [
        # Region 1 destination protects Cust2 (R2) and Cust7 (R3)
        ("Cust2", "Region 2", "Region 1", 90, 0),
        ("Cust7", "Region 3", "Region 1", 60, 1),
        # Region 2 destination protects R1 (Cust1+Cust5=120) and R3 (Cust6=80)
        ("Cust1", "Region 1", "Region 2", 70, 0),
        ("Cust5", "Region 1", "Region 2", 50, 1),   # R1 total on R2 = 120
        ("Cust6", "Region 3", "Region 2", 80, 1),    # R3 total on R2 = 80
        # Region 3 destination protects Cust3 (R1) and Cust4 (R2)
        ("Cust3", "Region 1", "Region 3", 40, 0),
        ("Cust4", "Region 2", "Region 3", 55, 1),
    ]
    for cust, src, dst, vcpu, wave in placements:
        mgr.register_placement(cust, src, dst, vcpu, priority_wave=wave)


def main() -> None:
    store = StateStore()
    index = DRIndexManager(store)
    sizer = DRSizer(default_basis="max")
    activation = DRActivationEngine(store, index)
    simulator = DRSimulator(store, index, activation, sizer)

    build_index(index)

    print("=" * 68)
    print("ACRME Phase 4 — Distributed DR Capacity Management")
    print("=" * 68)

    # 1. Reciprocal multi-source hosting view (DR-016)
    print("\n[1] Reciprocal hosting view (DR-016):")
    for region, view in sorted(index.reciprocal_view().items()):
        print(f"  {region}:")
        print(f"      protects sources        -> {view['protects_sources']}")
        print(f"      protected by destinations-> {view['protected_by_destinations']}")

    # 2. Max-not-sum sizing for Region 2 (Appendix D.3)
    print("\n[2] Max-not-sum sizing (DR-017, Appendix A.6/D.3):")
    r2 = sizer.size_destination(
        "Region 2", index.sources_for_destination("Region 2"), usable_capacity_vcpu=100
    )
    print(f"  Region 2 protects sources: "
          f"{[(p.source_region, p.vcpu) for p in r2.source_portions]}")
    print(f"  requirement (max)      = {r2.requirement_vcpu} vCPU  (expected 120)")
    print(f"  largest source         = {r2.largest_source}")
    print(f"  usable capacity        = {r2.usable_capacity_vcpu} vCPU")
    print(f"  capacity gap (A.7)     = {r2.gap_vcpu} vCPU")
    print(f"  overcommit ratio (A.8) = {r2.overcommit_ratio:.2f}  (expected ~1.67)")

    # 2b. Conservative SUM override (C-11)
    r2_sum = sizer.size_destination(
        "Region 2", index.sources_for_destination("Region 2"),
        usable_capacity_vcpu=100, basis="sum",
    )
    print(f"  SUM override (C-11)    = {r2_sum.requirement_vcpu} vCPU  (expected 200)")

    # 3. DR declaration + standby activation (DR-010/019) — Region 1 fails
    print("\n[3] DR declaration & standby activation (DR-010/019): Region 1 fails")
    decl = activation.declare(
        declaration_id="DECL-R1-001",
        source_region="Region 1",
        geography="US",
        authorised_by="dr-approver@platform",
        capacity_snapshot_ref="snap_dr_001",
    )
    decl = activation.activate(decl)
    print(f"  status              = {decl.status.value}")
    print(f"  customers failed over= {decl.customers_failed_over} / "
          f"{len(decl.activation_records)}")
    for rec in sorted(decl.activation_records, key=lambda r: r.priority_wave):
        print(f"      wave {rec.priority_wave} {rec.customer_realm_id}: "
              f"{rec.from_state.value} -> {rec.to_state.value} "
              f"({rec.protected_vcpu} vCPU via {rec.acquisition_step})")

    # 4. Failback (DR-013)
    print("\n[4] Failback (DR-013): Region 1 recovers")
    decl = activation.failback(decl)
    print(f"  status              = {decl.status.value}")
    print(f"  index reset to standby: "
          f"{[e.activation_state for e in index.destinations_for_source('Region 1')]}")

    # 5. Non-destructive DR drill + compliance evidence (DR-012)
    print("\n[5] DR simulation & compliance evidence (DR-012): Region 2 fails")
    evidence = simulator.simulate_region_failure("Region 2", "US")
    print(f"  customers in scope  = {evidence['customers_in_scope']}")
    print(f"  all covered         = {evidence['all_customers_covered']}")
    print(f"  total protected vCPU= {evidence['total_protected_vcpu']}")
    print(f"  overcommit ratios   = "
          f"{ {k: round(v, 2) for k, v in evidence['overcommit_ratios'].items()} }")
    print(f"  assumption          = {evidence['assumption']}")

    print("\n" + "=" * 68)
    print("Phase 4 demo complete.")
    print("=" * 68)


if __name__ == "__main__":
    main()
