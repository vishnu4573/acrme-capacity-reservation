"""
ACRME State Store — Phase 3

Versioned document store with optimistic concurrency (TDD Section 6, DAT-001..006, NFR-007).
"""

from .state_store import StateStore

__all__ = ["StateStore"]
