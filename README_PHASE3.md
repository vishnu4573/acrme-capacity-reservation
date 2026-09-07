# ACRME Phase 3 — Implementation Skeleton

**ACRME** (Azure Capacity Reservation Management Engine) — Phase 3: Placement & Customer Seed

## Overview

Phase 3 implements the **placement scoring engine** and **customer seed record** infrastructure, enabling deterministic region selection and placement reuse across products.

**Scope (Requirements Baseline v2.3, Section 21):**
- Exact production-region input validation (PLC-001 default path)
- Geography-only exception path with approval (PLC-002)
- Seed-record creation & reuse (PLC-003/004)
- CVAL/DR weighted placement scoring (PS_Prod/PS_DR/PS_NonProd)
- **CVAL/DR co-location in two-region geographies (PLC-010a)**
- Capacity commitment workflow foundation

## Architecture

Based on **Technical Design Document** (`docs/design/acrme_technical_design_document.md`).

### Component Structure

```
src/acrme/
├── domain/              # Domain entities (v2.3 data model)
│   ├── readiness.py     # ReadinessState, ReadinessCode
│   ├── seed.py          # CustomerSeedRecord
│   ├── policy.py        # PlacementPolicy, RegionCatalogue, ScoringWeights
│   ├── dr_index.py      # SourceDestinationDRIndex
│   ├── earmark.py       # CVALEarmarkRecord
│   ├── quota.py         # QuotaPoolState
│   └── reservation.py   # ReservationState
│
├── components/          # Logical components (TDD Section 3)
│   ├── placement.py     # PlacementEngine — region selection & scoring
│   ├── reconciler.py    # StateReconciler — capacity reconciliation
│   ├── quota_manager.py # QuotaPoolManager — single governed pool
│   ├── inventory.py     # InventoryCollector — Azure snapshot collection
│   └── config_service.py# ConfigService — versioned policy
│
├── algorithms/          # Core algorithms
│   └── scoring.py       # PlacementScorer — PS_Prod/PS_DR/PS_NonProd
│
├── store/               # State persistence
│   └── state_store.py   # StateStore — versioned document store
│
└── api/                 # API layer
    └── readiness.py     # ReadinessAPI — readiness query endpoint
```

### Key Features Implemented (Skeleton)

#### 1. Five-Geography Region Model (Baseline v2.3, REG-001/003)
- **US**: 3-region (West US 3, Central US, Canada Central)
- **Europe, Australia, Asia Pacific, Middle East**: 2-region with **mandatory CVAL+DR co-location** (PLC-010a)
- Middle East: `DR_NOT_OFFERED` (DEC-001) until legal approval

#### 2. Placement Scoring Algorithm (TDD Section 8.2, ADR-001)
Weighted scoring with five components (weights sum to 1.0):
```
PS = α·Clamp(α_component) + β·Clamp(β_component) + γ·Clamp(γ_component)
     + δ·Clamp(δ_component) + ε·Clamp(ε_component)

α (0.30): NonProd headroom
β (0.20): Prod quota headroom
γ (0.25): Distribution fairness
δ (0.15): DR readiness
ε (0.10): Zone diversity
```

All components clamped [0,1] before weighting: `Clamp(x) = max(0, min(1, x))`

#### 3. Customer Seed Record (PLC-003/004)
First placement creates authoritative seed:
```python
CustomerSeedRecord(
    customer_realm_id="customer_123",
    geography="Europe",
    prod_region="Switzerland North",
    cval_region="Sweden Central",
    dr_region="Sweden Central",  # Co-located in 2-region geography
    distribution_model="2-region",
    cval_dr_colocated=True,  # PLC-010a
    decision_timestamp=...,
    policy_version="v2.3",
)
```

Subsequent products for same customer+geography **reuse the seed** (PLC-004).

#### 4. Two-Region Co-location (PLC-010a)
In 2-region geographies, once Prod is placed, **CVAL and DR co-locate deterministically** in the remaining Standard region:
- Not an error state — **normative configuration**
- HC-6/HC-7 combined-capacity checks ensure shared pool can absorb DR demand
- Earmark tracking prevents double-counting (CVALEarmarkRecord)

## Phase 3 Status

### ✅ Implemented (Skeleton)
- Domain entities with v2.3 schema
- PlacementEngine with exact-region validation and geography-derivation structure
- PlacementScorer with PS_Prod/PS_DR/PS_NonProd formulas
- CustomerSeedRecord creation and reuse logic
- Two-region co-location decision logic (PLC-010a)
- ConfigService with hardcoded v2.3 policy
- StateStore in-memory implementation
- ReadinessAPI structure

### 🚧 Pending (Phase 4+)
- Azure SDK integration (CRG/quota/zone API calls)
- Live snapshot collection and freshness checks
- Hard constraint validation (HC-1..HC-10 full suite)
- DR sizing algorithms (max-not-sum, DR-017)
- Reconciliation loop with Azure mutations
- Observability/metrics emission
- Production StateStore (Cosmos DB / Table Storage)

## Usage Example

```python
from acrme.components import PlacementEngine, ConfigService
from acrme.store import StateStore
from acrme.algorithms import PlacementScorer

# Initialize
config_service = ConfigService()
policy = config_service.load_policy()
store = StateStore()
scorer = PlacementScorer(policy.scoring_weights.__dict__)
engine = PlacementEngine(store, policy, scorer)

# Create or get seed (exact region, default path PLC-001)
seed, created = engine.get_or_create_seed(
    customer_realm_id="customer_acme",
    geography="Europe",
    prod_region="Switzerland North",
    capacity_snapshot_ref="snap_001",
)

print(f"Seed created: {created}")
print(f"Prod: {seed.prod_region}, CVAL: {seed.cval_region}, DR: {seed.dr_region}")
print(f"Co-located: {seed.cval_dr_colocated}")  # True for 2-region Europe

# Reuse for another product (PLC-004)
seed2, created2 = engine.get_or_create_seed(
    customer_realm_id="customer_acme",
    geography="Europe",
    prod_region="Sweden Central",  # Different region — ignored, seed reused
    capacity_snapshot_ref="snap_002",
)

assert seed2.prod_region == "Switzerland North"  # Original seed reused
assert not created2
```

## Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests (Phase 4: test suite pending)
pytest tests/

# Type checking
mypy src/acrme

# Linting
ruff check src/acrme
black --check src/acrme
```

## Design Documents

| Document | Path |
|---|---|
| Requirements Baseline v2.3 | `docs/requirements/acrme_requirements_baseline_v2_2.md` |
| Technical Design Document | `docs/design/acrme_technical_design_document.md` |
| Functional Design Document | `docs/design/acrme_functional_design_document.md` |
| ADR-001 Region Selection | `docs/adr/acrme_adr_001_region_selection.md` |
| Calculation Logic Reference | `docs/reference/acrme_calculation_logic_reference.md` |

## Roadmap

- **Phase 1–2**: Design reconciliation ✅ (Complete, pushed)
- **Phase 3**: Placement skeleton ✅ (This release)
- **Phase 4**: Distributed DR capacity management (SourceDestinationDRIndex, max-not-sum sizing)
- **Phase 5**: Production integration (Azure SDK, live reconciliation loop)
- **Phase 6**: Observability & hardening

## License

Internal — Restricted (Azure SaaS Design Services capacity & DR programme)

---

**Version:** 0.1.0-phase3-skeleton  
**Baseline:** v2.3 (7 Sep 2026)  
**Status:** Implementation skeleton — Azure integration pending
