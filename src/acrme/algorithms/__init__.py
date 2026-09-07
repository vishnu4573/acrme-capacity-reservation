"""
ACRME Algorithms — Phase 3

Core algorithms implementing placement scoring, DR sizing, and capacity forecasting.

Key algorithms for Phase 3:
    - PlacementScorer: PS_Prod/PS_DR/PS_NonProd weighted scoring (TDD Section 8.2)
    - Clamp: Component clamping [0,1] before weighting
"""

from .scoring import PlacementScorer, clamp
from .dr_sizing import DRSizer, DestinationSizing, SourcePortion

__all__ = [
    "PlacementScorer",
    "clamp",
    "DRSizer",
    "DestinationSizing",
    "SourcePortion",
]
