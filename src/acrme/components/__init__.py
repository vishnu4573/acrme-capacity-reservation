"""
ACRME Components — Phase 3

Logical components implementing the TDD Section 3 architecture.

Key Phase 3 components:
    - PlacementEngine: Region selection via PS_Prod/PS_DR/PS_NonProd scoring
    - StateReconciler: Capacity reconciliation (Allocated + Buffer floor)
    - QuotaPoolManager: Single governed pool with Prod floor + DR earmark
    - InventoryCollector: Snapshot collection from Azure APIs
    - ConfigService: Versioned policy and region catalogue
"""

from .placement import PlacementEngine
from .reconciler import StateReconciler
from .quota_manager import QuotaPoolManager
from .inventory import InventoryCollector
from .config_service import ConfigService
from .dr_index_manager import DRIndexManager
from .dr_activation import DRActivationEngine, STAGED_ACQUISITION_SEQUENCE
from .dr_simulator import DRSimulator

__all__ = [
    "PlacementEngine",
    "StateReconciler",
    "QuotaPoolManager",
    "InventoryCollector",
    "ConfigService",
    "DRIndexManager",
    "DRActivationEngine",
    "STAGED_ACQUISITION_SEQUENCE",
    "DRSimulator",
]
