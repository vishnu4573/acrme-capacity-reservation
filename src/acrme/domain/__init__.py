"""
Domain Entities — ACRME v2.3

Core domain model implementing the data architecture from TDD Section 6, 18.
All entities support versioned, optimistic-concurrency state management (DAT-001..006).

Key entities for Phase 3:
    - CustomerSeedRecord: First placement decision (PLC-003/004)
    - PlacementPolicy: Scoring weights, thresholds, catalogue (REG-001, ADR-001)
    - RegionCatalogue: Five-geography region model with distribution models
    - ReadinessState: Combined capacity+quota+freshness verdict (RDY-001..004)
"""

from .readiness import ReadinessState, ReadinessCode
from .seed import CustomerSeedRecord
from .policy import PlacementPolicy, RegionCatalogue, RegionEntry, ScoringWeights
from .dr_index import SourceDestinationDRIndex
from .dr_declaration import (
    DRDeclaration,
    DRDeclarationStatus,
    DRActivationRecord,
    ActivationState,
)
from .earmark import CVALEarmarkRecord
from .quota import QuotaPoolState
from .reservation import ReservationState

__all__ = [
    "ReadinessState",
    "ReadinessCode",
    "CustomerSeedRecord",
    "PlacementPolicy",
    "RegionCatalogue",
    "RegionEntry",
    "ScoringWeights",
    "SourceDestinationDRIndex",
    "DRDeclaration",
    "DRDeclarationStatus",
    "DRActivationRecord",
    "ActivationState",
    "CVALEarmarkRecord",
    "QuotaPoolState",
    "ReservationState",
]
