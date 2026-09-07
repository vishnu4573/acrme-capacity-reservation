"""Offline unit tests for the v2.4 reservation-model logic (Phase 2 coverage).

Exercises the pure, Azure-free rule implementations behind test groups
G9–G12 WITHOUT touching Azure — the same style as ``test_region_model.py``.

Requirement coverage:
  * CAP-020 / HC-11  — Availability-Set VMs ineligible & uncounted   (G9)
  * CAP-021          — deallocate/redeploy-to-AZ onboarding gate      (G9)
  * CAP-001a         — core subscription = all-production             (G9)
  * PLC-011 / A.9    — even ~1/zone_count distribution + rebalance    (G10)
  * CAP-022          — seed-at-0 SKU/AZ matrix + budget gate          (G11)
  * CAP-024          — reactive discovery auto-create + governance    (G11)
  * CAP-023          — regional + per-AZ CRG structure                (G12)
  * OPS-006 / C-12   — deterministic RG/CRG/subscription naming       (G12)

Run directly:      python test_v24_reservation_model.py
Run with pytest:   pytest test_v24_reservation_model.py -q
"""

from __future__ import annotations

import sys

from acrme_suite.tests.g9_reservation_eligibility import (
    classify_for_buffer,
    counts_toward_reservation_target,
    is_manageable,
    is_reservation_eligible,
    required_remediation,
)
from acrme_suite.tests.g10_zone_distribution import (
    chosen_zone,
    max_drift,
    max_skew,
    preferred_placement_zone,
    rebalance_needed,
    target_vms_per_zone,
    zone_deficits,
    zone_shares,
    zone_skew,
    zone_target_share,
)
from acrme_suite.tests.g11_seed_matrix import (
    approved_seed_matrix,
    build_seed_matrix,
    reactive_discovery,
)
from acrme_suite.tests.g12_naming_convention import (
    expected_crg_set,
    flag_nonconforming,
    validate_crg_name,
    validate_rg_name,
    validate_subscription_name,
)

_RESULTS: list = []


def _check(name: str, cond: bool) -> bool:
    _RESULTS.append((name, cond))
    print(f"  {'OK  ' if cond else 'FAIL'} [{name}]")
    return cond


# ---------------------------------------------------------------------------
# CAP-020 / HC-11 / CAP-021 / CAP-001a  (G9)
# ---------------------------------------------------------------------------
def test_cap020_avset_ineligible_and_uncounted():
    avset = {"placement": "availability_set", "sku_supports_zonal": True}
    elig, reason = is_reservation_eligible(avset)
    assert _check("CAP-020 avset ineligible", elig is False)
    assert _check("CAP-020 HC-11 reason", "HC-11" in reason)
    assert _check("CAP-020 avset uncounted", counts_toward_reservation_target(avset) is False)


def test_cap020_zonal_eligible_and_counted():
    zonal = {"placement": "zone", "zone": "2", "sku_supports_zonal": True}
    elig, _ = is_reservation_eligible(zonal)
    assert _check("CAP-020 zonal eligible", elig is True)
    assert _check("CAP-020 zonal counted", counts_toward_reservation_target(zonal) is True)


def test_cap020_regional_only_when_no_zonal_support():
    reg_nozonal = {"placement": "regional", "sku_supports_zonal": False}
    reg_zonal = {"placement": "regional", "sku_supports_zonal": True}
    assert _check("CAP-020 regional nozonal eligible", is_reservation_eligible(reg_nozonal)[0] is True)
    assert _check("CAP-020 regional zonal-sku ineligible", is_reservation_eligible(reg_zonal)[0] is False)


def test_cap021_onboarding_gate():
    avset = {"placement": "availability_set", "sku_supports_zonal": True}
    assert _check("CAP-021 not manageable in avset", is_manageable(avset) is False)
    assert _check("CAP-021 remediation recorded", bool(required_remediation(avset)))
    remediated = {"placement": "zone", "zone": "3", "sku_supports_zonal": True}
    assert _check("CAP-021 manageable after redeploy", is_manageable(remediated) is True)


def test_cap001a_core_is_production():
    core = {"subscription_class": "core", "workload_label": "nonproduction"}
    workload = {"subscription_class": "workload", "workload_label": "nonproduction"}
    assert _check("CAP-001a core->production", classify_for_buffer(core) == "production")
    assert _check("CAP-001a workload keeps label", classify_for_buffer(workload) == "nonproduction")


# ---------------------------------------------------------------------------
# PLC-011 / Appendix A.9 — Scenario 21 worked example  (G10)
# ---------------------------------------------------------------------------
def test_plc011_scenario21():
    counts = [14, 9, 7]  # 30 VMs
    assert _check("PLC-011 target 0.3333", abs(zone_target_share(3) - 0.3333) < 1e-3)
    shares = zone_shares(counts)
    assert _check("PLC-011 share az1 0.467", abs(shares[0] - 0.467) < 1e-3)
    assert _check("PLC-011 share az3 0.233", abs(shares[2] - 0.233) < 1e-3)
    deficits = zone_deficits(counts)
    assert _check("PLC-011 deficit az1 -0.133", abs(deficits[0] + 0.133) < 1e-3)
    assert _check("PLC-011 deficit az3 +0.100", abs(deficits[2] - 0.100) < 1e-3)
    assert _check("PLC-011 max_drift 0.134", abs(max_drift(counts) - 0.134) < 2e-3)
    assert _check("PLC-011 rebalance true", rebalance_needed(counts, 0.10) is True)
    assert _check("PLC-011 chosen az3", chosen_zone(counts) == 2)
    # Appendix A.9 count variant
    assert _check("A.9 target vms 10", target_vms_per_zone(30, 3) == 10)
    assert _check("A.9 skew az1 +4", zone_skew(counts)[0] == 4)
    assert _check("A.9 skew az3 -3", zone_skew(counts)[2] == -3)
    assert _check("A.9 max_skew 4", max_skew(counts) == 4)
    assert _check("A.9 preferred az3", preferred_placement_zone(counts) == 2)


def test_plc011_balanced_no_rebalance():
    balanced = [10, 10, 10]
    assert _check("PLC-011 balanced drift 0", max_drift(balanced) < 1e-9)
    assert _check("PLC-011 balanced no rebalance", rebalance_needed(balanced) is False)


def test_plc011_eligibility_fallback():
    counts = [14, 9, 7]
    # az3 greatest deficit but ineligible -> fall back to az2 (index 1), never az1.
    assert _check("PLC-011 fallback az2", chosen_zone(counts, eligible=[True, True, False]) == 1)


# ---------------------------------------------------------------------------
# CAP-022 / CAP-024 — seed matrix & reactive discovery  (G11)
# ---------------------------------------------------------------------------
def test_cap022_seed_matrix_zero_and_budget_gate():
    skus = ["Standard_D4s_v3", "Standard_M128s"]
    supports = {"Standard_D4s_v3": True, "Standard_M128s": False}
    matrix = build_seed_matrix(skus, "eastus2", ["az1", "az2", "az3"], sku_supports_zonal=supports)
    assert _check("CAP-022 entries 4", len(matrix) == 3 + 1)  # 3 zonal + 1 regional
    assert _check("CAP-022 all zero", all(e["reserved_quantity"] == 0 for e in matrix))
    assert _check("CAP-022 has regional scope", any(e["scope"] == "reg" for e in matrix))
    budget = {
        ("Standard_D4s_v3", "az1"): {"product_team": "pay", "approved": True},
        ("Standard_D4s_v3", "az2"): {"product_team": "pay", "approved": False},
        # az3 has no line; M128s reg missing too
    }
    admitted, rejected = approved_seed_matrix(matrix, budget)
    assert _check("CAP-022 admitted 1", len(admitted) == 1)
    assert _check("CAP-022 rejected 3", len(rejected) == 3)


def test_cap024_reactive_discovery():
    seed = build_seed_matrix(["Standard_D4s_v3"], "eastus2", ["az1", "az2", "az3"])
    action = reactive_discovery({"sku": "Standard_L16s_v3", "zone": "az2", "allocated": 12},
                                seed, buffer=4)
    assert _check("CAP-024 auto_create", action["auto_create"] is True)
    assert _check("CAP-024 size allocated+buffer", action["reservation_size"] == 16)
    assert _check("CAP-024 governance item", action["governance_item"] is True)
    noop = reactive_discovery({"sku": "Standard_D4s_v3", "zone": "az1", "allocated": 5}, seed)
    assert _check("CAP-024 managed no-op", noop["auto_create"] is False)


# ---------------------------------------------------------------------------
# CAP-023 / OPS-006 / C-12 — CRG structure & naming  (G12)
# ---------------------------------------------------------------------------
def test_cap023_crg_structure():
    crgs = expected_crg_set("pr", "eus2", 3)
    assert _check("CAP-023 count 4", len(crgs) == 4)
    assert _check("CAP-023 one regional", sum(1 for c in crgs if c.endswith("-reg")) == 1)
    assert _check("CAP-023 three per-az", sum(1 for c in crgs if c[-3:-1] == "az") == 3)
    assert _check("CAP-023 all conform", all(validate_crg_name(c) for c in crgs))
    assert _check("CAP-023 example", crgs == ["crg-pr-eus2-reg", "crg-pr-eus2-az1",
                                              "crg-pr-eus2-az2", "crg-pr-eus2-az3"])


def test_ops006_naming():
    assert _check("OPS-006 good rg", validate_rg_name("rg-odcr-prod-eus2-01"))
    assert _check("OPS-006 good crg", validate_crg_name("crg-pr-eus2-az1"))
    assert _check("OPS-006 good sub", validate_subscription_name("sub-jda-cld-core-01"))
    assert _check("OPS-006 bad rg flagged", flag_nonconforming(["rg-odcr-prod-eus2"], "rg") == ["rg-odcr-prod-eus2"])
    assert _check("OPS-006 bad crg flagged", flag_nonconforming(["crg-pr-eus2-az0"], "crg") == ["crg-pr-eus2-az0"])
    assert _check("OPS-006 short counter flagged", flag_nonconforming(["rg-odcr-prod-eus2-1"], "rg") == ["rg-odcr-prod-eus2-1"])


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def run() -> int:
    print("v2.4 reservation-model offline unit tests (Phase 2 coverage):")
    tests = [
        test_cap020_avset_ineligible_and_uncounted,
        test_cap020_zonal_eligible_and_counted,
        test_cap020_regional_only_when_no_zonal_support,
        test_cap021_onboarding_gate,
        test_cap001a_core_is_production,
        test_plc011_scenario21,
        test_plc011_balanced_no_rebalance,
        test_plc011_eligibility_fallback,
        test_cap022_seed_matrix_zero_and_budget_gate,
        test_cap024_reactive_discovery,
        test_cap023_crg_structure,
        test_ops006_naming,
    ]
    for t in tests:
        print(f"\n{t.__name__}:")
        try:
            t()
        except AssertionError:
            pass
    passed = sum(1 for _, ok in _RESULTS if ok)
    total = len(_RESULTS)
    print(f"\n{passed}/{total} assertions passed across {len(tests)} test functions.")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(run())
