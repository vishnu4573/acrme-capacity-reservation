"""Offline unit tests for the GEOGRAPHY-AWARE region-distinctness model (v2.4).

Validates baseline REG-003 / PLC-010a / PLC-010b in the config loader
(``Config.validate``) and pre-flight checks PF-09/PF-10, WITHOUT touching Azure.
These are pure in-memory checks on the config-validation logic.

Run directly:      python test_region_model.py
Run with pytest:   pytest test_region_model.py -q

Covers:
  * three-region (US): Prod, CVAL/NonProd, DR must all differ  -> pass
  * three-region with a duplicated region                      -> reject
  * two-region (EU/AU/APAC): CVAL and DR co-locate (dr==nonprod) -> pass  (PLC-010a)
  * two-region with dr != nonprod (spurious third region)      -> reject
  * cross-geo (Middle East) [Amended v2.4]: Prod+CVAL co-locate in-geo,
    DR placed cross-geo in Europe (dr != primary)             -> pass  (PLC-010b/DR-020)
  * cross-geo with dr == primary (DR not cross-geo)            -> reject
  * cross-geo with nonprod != primary (Prod/CVAL not co-located) -> reject
  * two-region, legacy DR_NOT_OFFERED, dr blank                -> pass
  * Prod == NonProd in a non-cross-geo model                  -> reject
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
    ("cross-geo Middle East (Prod+CVAL in-geo, DR cross-geo in Europe)", "ok", {
        "distribution_model": "cross-geo",
        "primary": "uaenorth", "dr": "switzerlandnorth", "nonprod": "uaenorth",
    }),
    ("cross-geo dr == primary (DR not cross-geo)", "reject", {
        "distribution_model": "cross-geo",
        "primary": "uaenorth", "dr": "uaenorth", "nonprod": "uaenorth",
    }),
    ("cross-geo nonprod != primary (Prod/CVAL not co-located)", "reject", {
        "distribution_model": "cross-geo",
        "primary": "uaenorth", "dr": "switzerlandnorth", "nonprod": "qatarcentral",
    }),
    ("cross-geo dr missing", "reject", {
        "distribution_model": "cross-geo",
        "primary": "uaenorth", "dr": "", "nonprod": "uaenorth",
    }),
    ("two-region legacy DR_NOT_OFFERED (dr blank)", "ok", {
        "distribution_model": "two-region", "dr_offered": False,
        "primary": "brazilsouth", "dr": "", "nonprod": "brazilsoutheast",
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
def _case(label: str) -> tuple:
    """Look a case up by label so tests are robust to list ordering."""
    for lbl, kind, regions in CASES:
        if lbl == label:
            return lbl, kind, regions
    raise KeyError(f"No test case labelled {label!r}")


def test_three_region_distinct_valid():
    lbl, _, regions = _case("three-region US distinct")
    assert _expect_ok(lbl, regions)


def test_two_region_colocated_valid():
    lbl, _, regions = _case("two-region EU co-located dr==nonprod")
    assert _expect_ok(lbl, regions)


def test_cross_geo_middle_east_valid():
    lbl, _, regions = _case(
        "cross-geo Middle East (Prod+CVAL in-geo, DR cross-geo in Europe)"
    )
    assert _expect_ok(lbl, regions)


def test_cross_geo_dr_equals_primary_rejected():
    lbl, _, regions = _case("cross-geo dr == primary (DR not cross-geo)")
    assert _expect_reject(lbl, regions)


def test_cross_geo_nonprod_not_colocated_rejected():
    lbl, _, regions = _case(
        "cross-geo nonprod != primary (Prod/CVAL not co-located)"
    )
    assert _expect_reject(lbl, regions)


def test_two_region_dr_not_offered_valid():
    lbl, _, regions = _case("two-region legacy DR_NOT_OFFERED (dr blank)")
    assert _expect_ok(lbl, regions)


def test_two_region_spurious_third_region_rejected():
    lbl, _, regions = _case("two-region dr != nonprod (spurious third region)")
    assert _expect_reject(lbl, regions)


def test_three_region_duplicate_rejected():
    lbl, _, regions = _case("three-region duplicate dr==primary")
    assert _expect_reject(lbl, regions)


if __name__ == "__main__":
    sys.exit(run())
