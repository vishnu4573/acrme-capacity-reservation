"""Offline unit tests for the GEOGRAPHY-AWARE region-distinctness model (v2.4).

Validates baseline REG-003 / PLC-010a in the config loader (``Config.validate``)
and pre-flight checks PF-09/PF-10, WITHOUT touching Azure. These are pure
in-memory checks on the config-validation logic.

Run directly:      python test_region_model.py
Run with pytest:   pytest test_region_model.py -q

Covers:
  * three-region (US): Prod, CVAL/NonProd, DR must all differ  -> pass
  * three-region with a duplicated region                      -> reject
  * two-region (EU/AU/APAC): CVAL and DR co-locate (dr==nonprod) -> pass  (PLC-010a)
  * two-region with dr != nonprod (spurious third region)      -> reject
  * two-region, DR_NOT_OFFERED (Middle East, DEC-001), dr blank -> pass
  * Prod == NonProd in any model                               -> reject
"""

from __future__ import annotations

import sys

from acrme_suite.config import Config, ConfigError
from acrme_suite.preflight import Preflight


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _base_raw() -> dict:
    """A fully-populated raw config with placeholder non-region fields."""
    return {
        "provider": {
            "subscription_id": "00000000-0000-0000-0000-000000000001",
            "resource_group": "acrme-poc-rg",
            "tenant_id": "00000000-0000-0000-0000-0000000000aa",
        },
        "consumer": {
            "subscription_id": "00000000-0000-0000-0000-000000000002",
            "resource_group": "acrme-poc-rg-consumer",
        },
        "vm": {"sku": "Standard_D4s_v3", "sku_family": "standardDSv3Family"},
        "crg": {
            "name": "crg",
            "reservation_name": "res",
            "dr_crg_name": "dr-crg",
            "dr_reservation_name": "dr-res",
        },
    }


def _make(regions: dict) -> Config:
    """Build and validate a Config from a regions block (mirrors Config.load)."""
    raw = _base_raw()
    raw["regions"] = regions
    cfg = Config(raw=raw, path="<memory>")
    cfg._populate(raw)
    cfg.validate()
    return cfg


def _expect_ok(name: str, regions: dict) -> bool:
    try:
        cfg = _make(regions)
    except ConfigError as exc:
        print(f"  FAIL [{name}] expected VALID but raised: {exc}")
        return False
    # Pre-flight PF-09/PF-10 must also pass (they are geography-aware).
    pf = Preflight(cfg, az=None)  # type: ignore[arg-type]
    r9, r10 = pf.pf09_primary_ne_dr(), pf.pf10_nonprod_distinct()
    if r9.status != "pass" or r10.status != "pass":
        print(
            f"  FAIL [{name}] config valid but pre-flight blocked: "
            f"PF-09={r9.status} ({r9.detail}); PF-10={r10.status} ({r10.detail})"
        )
        return False
    print(f"  OK   [{name}] valid + pre-flight pass")
    return True


def _expect_reject(name: str, regions: dict) -> bool:
    try:
        _make(regions)
    except ConfigError as exc:
        print(f"  OK   [{name}] correctly rejected: {exc}")
        return True
    print(f"  FAIL [{name}] expected REJECT but config validated")
    return False


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------
CASES = [
    # (label, kind, regions)
    ("three-region US distinct", "ok", {
        "distribution_model": "three-region",
        "primary": "westus3", "dr": "canadacentral", "nonprod": "centralus",
    }),
    ("three-region duplicate dr==primary", "reject", {
        "distribution_model": "three-region",
        "primary": "westus3", "dr": "westus3", "nonprod": "centralus",
    }),
    ("three-region duplicate nonprod==dr", "reject", {
        "distribution_model": "three-region",
        "primary": "westus3", "dr": "canadacentral", "nonprod": "canadacentral",
    }),
    ("two-region EU co-located dr==nonprod", "ok", {
        "distribution_model": "two-region",
        "primary": "switzerlandnorth", "dr": "swedencentral", "nonprod": "swedencentral",
    }),
    ("two-region AU co-located", "ok", {
        "distribution_model": "two-region",
        "primary": "australiaeast", "dr": "australiasoutheast", "nonprod": "australiasoutheast",
    }),
    ("two-region dr != nonprod (spurious third region)", "reject", {
        "distribution_model": "two-region",
        "primary": "switzerlandnorth", "dr": "northeurope", "nonprod": "swedencentral",
    }),
    ("two-region Middle East DR_NOT_OFFERED (dr blank)", "ok", {
        "distribution_model": "two-region", "dr_offered": False,
        "primary": "uaenorth", "dr": "", "nonprod": "saudiarabiacentral",
    }),
    ("two-region dr==primary", "reject", {
        "distribution_model": "two-region",
        "primary": "switzerlandnorth", "dr": "switzerlandnorth", "nonprod": "switzerlandnorth",
    }),
    ("prod == nonprod (two-region)", "reject", {
        "distribution_model": "two-region",
        "primary": "switzerlandnorth", "dr": "switzerlandnorth", "nonprod": "switzerlandnorth",
    }),
    ("unknown distribution_model", "reject", {
        "distribution_model": "four-region",
        "primary": "a", "dr": "b", "nonprod": "c",
    }),
    ("default model (omitted) three-region distinct", "ok", {
        "primary": "westus3", "dr": "canadacentral", "nonprod": "centralus",
    }),
]


def run() -> int:
    print("Region-model geography-aware validation tests (v2.4, PLC-010a):")
    passed = 0
    for label, kind, regions in CASES:
        ok = _expect_ok(label, regions) if kind == "ok" else _expect_reject(label, regions)
        passed += 1 if ok else 0
    total = len(CASES)
    print(f"\n{passed}/{total} cases passed.")
    return 0 if passed == total else 1


# --- pytest entry points ---------------------------------------------------
def test_three_region_distinct_valid():
    assert _expect_ok(CASES[0][0], CASES[0][2])


def test_two_region_colocated_valid():
    assert _expect_ok(CASES[3][0], CASES[3][2])


def test_two_region_dr_not_offered_valid():
    assert _expect_ok(CASES[6][0], CASES[6][2])


def test_two_region_spurious_third_region_rejected():
    assert _expect_reject(CASES[5][0], CASES[5][2])


def test_three_region_duplicate_rejected():
    assert _expect_reject(CASES[1][0], CASES[1][2])


if __name__ == "__main__":
    sys.exit(run())
