#!/usr/bin/env python3
"""
ACRME Phase 3 Demo — Placement & Seed Record

Demonstrates:
    1. Policy loading (v2.3 five-geography model)
    2. Exact-region seed creation (PLC-001)
    3. Seed reuse across products (PLC-004)
    4. Two-region co-location (PLC-010a)
    5. Middle East DR_NOT_OFFERED (DEC-001)
"""

import sys
sys.path.insert(0, "/home/ubuntu/acrme-capacity-reservation/src")

from acrme.components import PlacementEngine, ConfigService
from acrme.store import StateStore
from acrme.algorithms import PlacementScorer


def main():
    print("=" * 70)
    print("ACRME Phase 3 Demo — Placement & Customer Seed")
    print("=" * 70)
    
    # 1. Initialize components
    print("\n1. Initializing components...")
    config_service = ConfigService()
    policy = config_service.load_policy()
    store = StateStore()
    scorer = PlacementScorer({
        "alpha": policy.scoring_weights.alpha,
        "beta": policy.scoring_weights.beta,
        "gamma": policy.scoring_weights.gamma,
        "delta": policy.scoring_weights.delta,
        "epsilon": policy.scoring_weights.epsilon,
    })
    engine = PlacementEngine(store, policy, scorer)
    
    print(f"   Policy version: {policy.version}")
    print(f"   Scoring weights: α={policy.scoring_weights.alpha}, "
          f"β={policy.scoring_weights.beta}, γ={policy.scoring_weights.gamma}, "
          f"δ={policy.scoring_weights.delta}, ε={policy.scoring_weights.epsilon}")
    print(f"   Geographies: {list(policy.region_catalogue.distribution_models.keys())}")
    
    # 2. Create seed for Europe (2-region geography)
    print("\n2. Creating seed for customer_acme in Europe (2-region)...")
    seed_eu, created_eu = engine.get_or_create_seed(
        customer_realm_id="customer_acme",
        geography="Europe",
        prod_region="Switzerland North",
        capacity_snapshot_ref="snap_001",
    )
    
    print(f"   Seed created: {created_eu}")
    print(f"   Prod region: {seed_eu.prod_region}")
    print(f"   CVAL region: {seed_eu.cval_region}")
    print(f"   DR region: {seed_eu.dr_region}")
    print(f"   Co-located (PLC-010a): {seed_eu.cval_dr_colocated}")
    print(f"   Distribution model: {seed_eu.distribution_model}")
    
    # 3. Reuse seed for another product (PLC-004)
    print("\n3. Reusing seed for another product (PLC-004)...")
    seed_eu_2, created_eu_2 = engine.get_or_create_seed(
        customer_realm_id="customer_acme",
        geography="Europe",
        prod_region="Sweden Central",  # Different request — ignored, seed reused
        capacity_snapshot_ref="snap_002",
    )
    
    print(f"   Seed created: {created_eu_2}")
    print(f"   Prod region (from seed): {seed_eu_2.prod_region}")
    print(f"   Seed reused successfully: {seed_eu.prod_region == seed_eu_2.prod_region}")
    
    # 4. Create seed for US (3-region geography)
    print("\n4. Creating seed for customer_beta in US (3-region)...")
    seed_us, created_us = engine.get_or_create_seed(
        customer_realm_id="customer_beta",
        geography="US",
        prod_region="West US 3",
        capacity_snapshot_ref="snap_003",
    )
    
    print(f"   Seed created: {created_us}")
    print(f"   Prod region: {seed_us.prod_region}")
    print(f"   CVAL region: {seed_us.cval_region}")
    print(f"   DR region: {seed_us.dr_region}")
    print(f"   Co-located: {seed_us.cval_dr_colocated}")  # False for 3-region
    print(f"   Distribution model: {seed_us.distribution_model}")
    
    # 5. Middle East — DR_NOT_OFFERED (DEC-001)
    print("\n5. Creating seed for customer_gamma in Middle East (DR_NOT_OFFERED)...")
    seed_me, created_me = engine.get_or_create_seed(
        customer_realm_id="customer_gamma",
        geography="Middle East",
        prod_region="UAE North",
        capacity_snapshot_ref="snap_004",
    )
    
    print(f"   Seed created: {created_me}")
    print(f"   Prod region: {seed_me.prod_region}")
    print(f"   CVAL region: {seed_me.cval_region}")
    print(f"   DR region: {seed_me.dr_region}")  # "NOT_OFFERED"
    print(f"   DR offered: {seed_me.dr_offered}")  # False
    print(f"   Distribution model: {seed_me.distribution_model}")
    
    # 6. Region catalogue inspection
    print("\n6. Region catalogue (v2.3)...")
    for geo, model in policy.region_catalogue.distribution_models.items():
        standard = policy.region_catalogue.get_standard_regions(geo)
        restricted = policy.region_catalogue.get_restricted_regions(geo)
        print(f"   {geo} ({model}):")
        print(f"      Standard: {', '.join(r.name for r in standard)}")
        if restricted:
            print(f"      Restricted: {', '.join(r.name for r in restricted)}")
    
    print("\n" + "=" * 70)
    print("Phase 3 Demo Complete")
    print("=" * 70)


if __name__ == "__main__":
    main()
