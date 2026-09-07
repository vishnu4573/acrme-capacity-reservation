"""Group 10 — v2.4 even per-zone distribution & rebalancing (PLC-011).

Implements and validates the **PLC-011** even ``≈1/zone_count`` zone-distribution
target and drift-based rebalancing, using the two equivalent formulations in the
Baseline v2.4 corpus:

* **Calculation Logic Reference, Scenario 21** (share-based):
  ``zone_target_share = 1/zone_count``; ``zone_share(z) = vm_count(z)/total``;
  ``zone_deficit(z) = target_share − zone_share(z)``;
  ``chosen_zone = argmax_z zone_deficit(z)`` over eligible zones;
  ``max_drift = max_z |zone_share(z) − target_share|``;
  ``rebalance_needed = max_drift > tolerance`` (C-13 default 0.10).

* **Appendix A.9** (count-based skew):
  ``Target VMs per Zone = round(WorkloadVMCount / ZoneCount)``;
  ``Zone Skew(z) = VMs(z) − Target``; ``Max Skew = max_z |Zone Skew(z)|``;
  ``Preferred Placement Zone = argmin_z VMs(z)``.

The primary "logic" case reproduces the **worked three-zone example** from
Scenario 21 exactly (30 VMs distributed 14/9/7) and asserts every intermediate
number. A **live** placement/rebalance case is BLOCKED until the placement
engine is deployed.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from ..az_client import AzClient
from ..config import Config
from ..runner_core import Registry, TestCase, TestResult

GROUP = "G10"
REQ_PLC_011 = "PLC-011"
REQ_A9 = "A.9"
REQ_C13 = "C-13"

DEFAULT_TOLERANCE = 0.10  # C-13 default share tolerance (±10 percentage points)


# ---------------------------------------------------------------------------
# Pure, Azure-free A.9 / Scenario-21 arithmetic
# ---------------------------------------------------------------------------
def zone_target_share(zone_count: int) -> float:
    """``1 / zone_count`` (≈0.3333 for a three-zone region)."""
    if zone_count <= 0:
        raise ValueError("zone_count must be positive")
    return 1.0 / zone_count


def zone_shares(counts: Sequence[int]) -> List[float]:
    """``vm_count(z) / total`` per zone (0.0 for every zone when total == 0)."""
    total = sum(counts)
    if total == 0:
        return [0.0 for _ in counts]
    return [c / total for c in counts]


def zone_deficits(counts: Sequence[int]) -> List[float]:
    """``target_share − zone_share(z)`` per zone (>0 ⇒ under target)."""
    target = zone_target_share(len(counts))
    return [target - s for s in zone_shares(counts)]


def max_drift(counts: Sequence[int]) -> float:
    """``max_z |zone_share(z) − target_share|``."""
    target = zone_target_share(len(counts))
    return max(abs(s - target) for s in zone_shares(counts))


def rebalance_needed(counts: Sequence[int], tolerance: float = DEFAULT_TOLERANCE) -> bool:
    """``max_drift > tolerance`` (C-13)."""
    return max_drift(counts) > tolerance


def chosen_zone(counts: Sequence[int], eligible: Optional[Sequence[bool]] = None) -> int:
    """Greatest-deficit-first zone index; restricts to eligible zones if given."""
    deficits = zone_deficits(counts)
    idxs = range(len(counts))
    if eligible is not None:
        idxs = [i for i in idxs if eligible[i]]
        if not idxs:
            raise ValueError("no eligible zones")
    return max(idxs, key=lambda i: deficits[i])


# --- Appendix A.9 count-based variant --------------------------------------
def target_vms_per_zone(total_vms: int, zone_count: int) -> int:
    """``round(WorkloadVMCount / ZoneCount)``."""
    return round(total_vms / zone_count)


def zone_skew(counts: Sequence[int]) -> List[int]:
    """``VMs(z) − Target VMs per Zone`` per zone."""
    target = target_vms_per_zone(sum(counts), len(counts))
    return [c - target for c in counts]


def max_skew(counts: Sequence[int]) -> int:
    """``max_z |Zone Skew(z)|``."""
    return max(abs(s) for s in zone_skew(counts))


def preferred_placement_zone(counts: Sequence[int]) -> int:
    """``argmin_z VMs(z)`` — the most under-represented zone."""
    return min(range(len(counts)), key=lambda i: counts[i])


# ---------------------------------------------------------------------------
# Test case — logic (reproduces Scenario 21 worked example)
# ---------------------------------------------------------------------------
def plc_011_scenario21(config: Config, az: AzClient) -> TestResult:  # noqa: ARG001
    """PLC-011: reproduce the Scenario 21 / A.9 three-zone worked example exactly."""
    evidence: Dict[str, Any] = {"requirement": [REQ_PLC_011, REQ_A9, REQ_C13]}
    counts = [14, 9, 7]  # az1, az2, az3 — 30 VMs total (Scenario 21)
    zones = ["az1", "az2", "az3"]

    target = zone_target_share(len(counts))
    shares = zone_shares(counts)
    deficits = zone_deficits(counts)
    drift = max_drift(counts)
    reb = rebalance_needed(counts, DEFAULT_TOLERANCE)
    pick = chosen_zone(counts)

    # A.9 count-based variant.
    tgt_vms = target_vms_per_zone(sum(counts), len(counts))
    skew = zone_skew(counts)
    mskew = max_skew(counts)
    pref = preferred_placement_zone(counts)

    evidence["scenario21"] = {
        "counts": dict(zip(zones, counts)),
        "zone_target_share": round(target, 4),
        "zone_share": {z: round(s, 3) for z, s in zip(zones, shares)},
        "zone_deficit": {z: round(d, 3) for z, d in zip(zones, deficits)},
        "max_drift": round(drift, 3),
        "tolerance_C13": DEFAULT_TOLERANCE,
        "rebalance_needed": reb,
        "chosen_zone_argmax_deficit": zones[pick],
    }
    evidence["appendix_a9"] = {
        "target_vms_per_zone": tgt_vms,
        "zone_skew": dict(zip(zones, skew)),
        "max_skew": mskew,
        "preferred_placement_zone_argmin": zones[pref],
    }

    # Balanced end-state check: 10/10/10 ⇒ drift 0, no rebalance.
    balanced = [10, 10, 10]
    evidence["balanced_endstate"] = {
        "counts": dict(zip(zones, balanced)),
        "max_drift": round(max_drift(balanced), 6),
        "rebalance_needed": rebalance_needed(balanced),
    }

    checks = {
        "target_share_0.3333": abs(target - 0.3333) < 1e-3,
        "share_az1_0.467": abs(shares[0] - 0.467) < 1e-3,
        "share_az2_0.300": abs(shares[1] - 0.300) < 1e-3,
        "share_az3_0.233": abs(shares[2] - 0.233) < 1e-3,
        "deficit_az1_-0.133": abs(deficits[0] + 0.133) < 1e-3,
        "deficit_az3_+0.100": abs(deficits[2] - 0.100) < 1e-3,
        "max_drift_0.134": abs(drift - 0.134) < 2e-3,
        "rebalance_true": reb is True,
        "chosen_zone_az3": zones[pick] == "az3",
        "a9_target_vms_10": tgt_vms == 10,
        "a9_skew_az1_+4": skew[0] == 4,
        "a9_skew_az3_-3": skew[2] == -3,
        "a9_max_skew_4": mskew == 4,
        "a9_preferred_az3": zones[pref] == "az3",
        "balanced_no_rebalance": rebalance_needed(balanced) is False,
    }
    evidence["checks"] = checks
    if all(checks.values()):
        return TestResult(
            poc_id="POC-PLC-011", status="pass",
            actual_result="Scenario 21 reproduced: target 0.333/zone; az1 over target "
                          "(share 0.467, skew +4); max_drift 0.134 > 0.10 ⇒ rebalance; "
                          "next placement → az3 (greatest deficit / argmin count); "
                          "balanced 10/10/10 ⇒ drift 0, no rebalance.",
            evidence=evidence,
        )
    failed = [k for k, v in checks.items() if not v]
    return TestResult(
        poc_id="POC-PLC-011", status="fail",
        actual_result=f"PLC-011 arithmetic mismatch on: {', '.join(failed)}",
        evidence=evidence,
    )


def plc_011_eligibility_fallback(config: Config, az: AzClient) -> TestResult:  # noqa: ARG001
    """PLC-011: greatest-deficit zone that is ineligible falls back to next eligible."""
    evidence: Dict[str, Any] = {"requirement": [REQ_PLC_011]}
    counts = [14, 9, 7]
    zones = ["az1", "az2", "az3"]
    # az3 has the greatest deficit but is ineligible (e.g. no capacity/restricted);
    # placement must fall back to az2 (next-greatest deficit), never az1.
    eligible = [True, True, False]
    pick = chosen_zone(counts, eligible=eligible)
    evidence.update({
        "counts": dict(zip(zones, counts)),
        "eligible": dict(zip(zones, eligible)),
        "chosen_zone": zones[pick],
    })
    if zones[pick] == "az2":
        return TestResult(
            poc_id="POC-PLC-011-ELIG", status="pass",
            actual_result="Greatest-deficit zone az3 ineligible → placement falls back to "
                          "next-greatest-deficit eligible zone az2 (not the over-target az1).",
            evidence=evidence,
        )
    return TestResult(
        poc_id="POC-PLC-011-ELIG", status="fail",
        actual_result=f"Eligibility fallback wrong (chose {zones[pick]}, expected az2).",
        evidence=evidence,
    )


# ---------------------------------------------------------------------------
# Test case — live (engine required → BLOCKED)
# ---------------------------------------------------------------------------
def plc_011_live(config: Config, az: AzClient) -> TestResult:  # noqa: ARG001
    """PLC-011 (live): observe the engine steering placement + raising a
    ZoneRebalanceAction — requires the placement engine to be deployed."""
    return TestResult(
        poc_id="POC-PLC-011-LIVE", status="blocked",
        actual_result="Engine/live placement required — deploy skewed VMs across zones "
                      "and confirm the engine prefers the under-represented zone and "
                      "raises a ZoneRebalanceAction when drift > C-13 tolerance. Blocked.",
        evidence={"engine_required": True, "requirement": [REQ_PLC_011]},
    )


def register(registry: Registry) -> None:
    """Register all Group 10 test cases."""
    registry.add(TestCase("POC-PLC-011", GROUP,
                          "PLC-011: even ~1/zone_count distribution + rebalance (Scenario 21)",
                          ["phase1"], [], plc_011_scenario21))
    registry.add(TestCase("POC-PLC-011-ELIG", GROUP,
                          "PLC-011: greatest-deficit eligibility fallback",
                          ["phase1"], [], plc_011_eligibility_fallback))
    registry.add(TestCase("POC-PLC-011-LIVE", GROUP,
                          "PLC-011 (live): engine steers placement & raises rebalance action",
                          ["phase2"], [], plc_011_live))
