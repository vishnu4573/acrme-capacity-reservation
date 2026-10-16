"""
ACRME — Azure Capacity Reservation Management Engine

A control engine that guarantees every managed Azure deployment has both reserved
physical capacity and deployable VM-family quota — in the correct region/zone/SKU —
before it proceeds, while minimising idle cost through lean distributed DR and
continuous reconciliation.

Architecture:
    - Current requirements baseline: v4.0
    - This package remains a legacy implementation skeleton based on v2.3 concepts;
      it has not been reconciled against the v4.0 requirements.
    - Technical Design: Design/acrme_technical_design_document.md
    - Functional Design: Design/acrme_functional_design_document.md

Phase 3 Scope (Placement & Customer Seed):
    - Exact production-region input validation
    - Seed-record creation & reuse (PLC-003/004)
    - CVAL/DR weighted placement scoring (PS_Prod/PS_DR/PS_NonProd)
    - CVAL/DR co-location in two-region geographies (PLC-010/010a)
    - Capacity commitment workflow
"""

__version__ = "0.1.0-phase3-skeleton"
__baseline_version__ = "4.0"
__baseline_alignment__ = "not-reconciled"
