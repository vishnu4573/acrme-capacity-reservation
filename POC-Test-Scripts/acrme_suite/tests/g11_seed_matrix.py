"""Group 11 — v2.4 seed matrix & reactive discovery (CAP-022 / CAP-024).

* **CAP-022** (extends CAP-009) — the managed SKU × region × availability-zone
  set is initialised as a **seed matrix of count-0 reservations** ("seed
  reservations"): every eligible combination in the scope file is created at
  reserved quantity **0** inside the correct regional / per-AZ CRG (CAP-023), so
  reconciliation can scale each up the instant demand appears. A combination
  enters the matrix **only** with a named owning **product team** and an
  approved **budget line** (budget governance), because any reservation scaled
  above 0 incurs cost.

* **CAP-024** (reconciles CAP-019) — when an allocated VM of a SKU/AZ **not yet
  in the seed matrix** is discovered, the engine **auto-creates** the reservation
  (CRG if absent + reservation sized ``allocated + buffer``, CAP-003) so
  production is protected immediately, **and simultaneously raises a scope-file
  governance item** so the discovered SKU/AZ is ratified with an owning product
  team and budget. Auto-creation protects capacity first; governance
  reconciliation then makes it authoritative (or triggers CAP-010 rollback).

Deterministic seed-matrix construction, the budget gate, and the reactive-
discovery reconciliation are implemented as pure functions and validated
offline. A **live** reactive-discovery case is BLOCKED until the engine runs
against Azure.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..az_client import AzClient
from ..config import Config
from ..runner_core import Registry, TestCase, TestResult

GROUP = "G11"
REQ_CAP_022 = "CAP-022"
REQ_CAP_024 = "CAP-024"
REQ_CAP_009 = "CAP-009"
REQ_CAP_019 = "CAP-019"
REQ_CAP_003 = "CAP-003"


# ---------------------------------------------------------------------------
# Pure, Azure-free seed-matrix / discovery logic
# ---------------------------------------------------------------------------
def build_seed_matrix(
    skus: Sequence[str],
    region: str,
    zones: Sequence[str],
    *,
    sku_supports_zonal: Optional[Dict[str, bool]] = None,
) -> List[Dict[str, Any]]:
    """Return the full seed matrix of **count-0** reservations (CAP-022).

    One entry per eligible SKU × zone; SKUs without zonal support get a single
    regional (non-zonal) entry instead of per-AZ entries (CAP-020/CAP-023).
    Every entry is created at ``reserved_quantity == 0`` (CAP-009).
    """
    sku_supports_zonal = sku_supports_zonal or {}
    matrix: List[Dict[str, Any]] = []
    for sku in skus:
        if sku_supports_zonal.get(sku, True):
            for z in zones:
                matrix.append({
                    "sku": sku, "region": region, "zone": z,
                    "scope": z, "reserved_quantity": 0,
                })
        else:
            matrix.append({
                "sku": sku, "region": region, "zone": None,
                "scope": "reg", "reserved_quantity": 0,
            })
    return matrix


def budget_gate(entry: Dict[str, Any], budget_book: Dict[Tuple[str, str], Dict[str, Any]]) -> Tuple[bool, str]:
    """CAP-022 budget governance: a SKU/AZ enters the matrix only with a named
    owning product team AND an approved budget line."""
    key = (entry["sku"], entry.get("zone") or entry.get("scope") or "reg")
    line = budget_book.get(key)
    if not line:
        return False, "No budget line — SKU/AZ may not enter the seed matrix (CAP-022)."
    if not line.get("product_team"):
        return False, "Budget line missing an owning product team (CAP-022)."
    if not line.get("approved"):
        return False, "Budget line not approved (CAP-022)."
    return True, f"Approved for product team '{line['product_team']}'."


def approved_seed_matrix(
    matrix: Sequence[Dict[str, Any]],
    budget_book: Dict[Tuple[str, str], Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Split a candidate matrix into (admitted, rejected) per the budget gate."""
    admitted, rejected = [], []
    for entry in matrix:
        ok, reason = budget_gate(entry, budget_book)
        record = dict(entry, gate_reason=reason)
        (admitted if ok else rejected).append(record)
    return admitted, rejected


def reactive_discovery(
    discovered: Dict[str, Any],
    seed_matrix: Sequence[Dict[str, Any]],
    *,
    buffer: int = 0,
) -> Dict[str, Any]:
    """CAP-024: reconcile an allocated SKU/AZ that is not yet in the seed matrix.

    Returns the actions the engine must take: auto-create the reservation sized
    ``allocated + buffer`` (CAP-003) AND raise a scope-file governance item
    (CAP-019/CAP-022). If the SKU/AZ is already managed, no action is required.
    """
    in_matrix = any(
        e["sku"] == discovered["sku"]
        and (e.get("zone") or e.get("scope")) == (discovered.get("zone") or discovered.get("scope"))
        for e in seed_matrix
    )
    if in_matrix:
        return {"auto_create": False, "governance_item": False,
                "reason": "SKU/AZ already in seed matrix — no reactive action."}
    allocated = int(discovered.get("allocated", 0))
    return {
        "auto_create": True,
        "reservation_size": allocated + buffer,   # CAP-003 allocated + buffer
        "create_crg_if_absent": True,             # CAP-023
        "governance_item": True,                  # CAP-019 scope-file ratification
        "governance_fields": ["owning_product_team", "budget_line"],  # CAP-022
        "protect_capacity_first": True,           # CAP-002 preserved
        "reason": "Unmanaged allocated SKU/AZ discovered — auto-create to protect "
                  "production, then raise scope-file governance item for ratification.",
    }


# ---------------------------------------------------------------------------
# Test cases — logic (offline PASS)
# ---------------------------------------------------------------------------
def cap_022_logic(config: Config, az: AzClient) -> TestResult:  # noqa: ARG001
    """CAP-022: seed matrix is count-0 across SKU×AZ and gated by budget approval."""
    evidence: Dict[str, Any] = {"requirement": [REQ_CAP_022, REQ_CAP_009]}
    skus = ["Standard_D4s_v3", "Standard_E8s_v5", "Standard_M128s"]
    zones = ["az1", "az2", "az3"]
    supports = {"Standard_D4s_v3": True, "Standard_E8s_v5": True,
                "Standard_M128s": False}  # M-series: regional-only in this example
    matrix = build_seed_matrix(skus, "eastus2", zones, sku_supports_zonal=supports)

    all_zero = all(e["reserved_quantity"] == 0 for e in matrix)
    # 2 zonal SKUs × 3 zones + 1 regional-only SKU = 7 entries.
    expected_entries = 2 * 3 + 1
    scopes = sorted({e["scope"] for e in matrix})

    budget_book = {
        ("Standard_D4s_v3", "az1"): {"product_team": "payments", "approved": True},
        ("Standard_D4s_v3", "az2"): {"product_team": "payments", "approved": True},
        ("Standard_D4s_v3", "az3"): {"product_team": "payments", "approved": True},
        ("Standard_E8s_v5", "az1"): {"product_team": "search", "approved": True},
        ("Standard_E8s_v5", "az2"): {"product_team": "search", "approved": False},  # not approved
        # E8s az3 has NO budget line at all
        ("Standard_M128s", "reg"): {"product_team": "analytics", "approved": True},
    }
    admitted, rejected = approved_seed_matrix(matrix, budget_book)

    evidence.update({
        "total_candidate_entries": len(matrix),
        "expected_entries": expected_entries,
        "all_reserved_quantity_zero": all_zero,
        "scopes_present": scopes,
        "admitted_count": len(admitted),
        "rejected_count": len(rejected),
        "rejected_reasons": [(r["sku"], r.get("zone") or r["scope"], r["gate_reason"]) for r in rejected],
    })
    ok = (
        all_zero
        and len(matrix) == expected_entries
        and scopes == ["az1", "az2", "az3", "reg"]
        and len(admitted) == 5  # 3x D4s + 1 E8s(az1) + 1 M128s(reg)
        and len(rejected) == 2  # E8s az2 (unapproved) + E8s az3 (no line)
    )
    if ok:
        return TestResult(
            poc_id="POC-CAP-022", status="pass",
            actual_result="Seed matrix built at count-0 across SKU×AZ (zonal SKUs per-AZ, "
                          "non-zonal SKU regional); budget gate admits 5 and rejects 2 "
                          "(unapproved / no budget line) per CAP-022 governance.",
            evidence=evidence,
        )
    return TestResult(
        poc_id="POC-CAP-022", status="fail",
        actual_result="Seed matrix / budget-gate behaviour did not match CAP-022.",
        evidence=evidence,
    )


def cap_024_logic(config: Config, az: AzClient) -> TestResult:  # noqa: ARG001
    """CAP-024: unseen allocated SKU/AZ triggers governed auto-create + governance item."""
    evidence: Dict[str, Any] = {"requirement": [REQ_CAP_024, REQ_CAP_019, REQ_CAP_003]}
    seed_matrix = build_seed_matrix(["Standard_D4s_v3"], "eastus2", ["az1", "az2", "az3"])

    # A product team deployed a brand-new SKU in az2 that is not in the matrix.
    discovered = {"sku": "Standard_L16s_v3", "region": "eastus2", "zone": "az2",
                  "allocated": 12}
    action = reactive_discovery(discovered, seed_matrix, buffer=4)

    # A SKU/AZ already managed must NOT trigger reactive action.
    already = {"sku": "Standard_D4s_v3", "region": "eastus2", "zone": "az1",
               "allocated": 5}
    noop = reactive_discovery(already, seed_matrix, buffer=4)

    evidence.update({"discovered_action": action, "already_managed_action": noop})
    ok = (
        action["auto_create"] is True
        and action["reservation_size"] == 16          # 12 allocated + 4 buffer (CAP-003)
        and action["governance_item"] is True
        and action["create_crg_if_absent"] is True
        and noop["auto_create"] is False
        and noop["governance_item"] is False
    )
    if ok:
        return TestResult(
            poc_id="POC-CAP-024", status="pass",
            actual_result="Unseen allocated SKU/AZ → auto-create reservation sized "
                          "allocated+buffer (16) with CRG-if-absent, plus a scope-file "
                          "governance item (CAP-019/022); already-managed SKU/AZ is a no-op.",
            evidence=evidence,
        )
    return TestResult(
        poc_id="POC-CAP-024", status="fail",
        actual_result="Reactive-discovery reconciliation did not match CAP-024.",
        evidence=evidence,
    )


# ---------------------------------------------------------------------------
# Test case — live (engine required → BLOCKED)
# ---------------------------------------------------------------------------
def cap_024_live(config: Config, az: AzClient) -> TestResult:  # noqa: ARG001
    """CAP-024 (live): observe real auto-create + governance-item raising against Azure."""
    return TestResult(
        poc_id="POC-CAP-024-LIVE", status="blocked",
        actual_result="Engine/live Azure required — deploy an unmanaged SKU/AZ and "
                      "confirm the engine auto-creates the CRG+reservation (allocated+buffer) "
                      "and raises a scope-file governance item. Blocked until deployment.",
        evidence={"engine_required": True, "requirement": [REQ_CAP_024]},
    )


def register(registry: Registry) -> None:
    """Register all Group 11 test cases."""
    registry.add(TestCase("POC-CAP-022", GROUP,
                          "CAP-022: seed-at-0 SKU/AZ matrix + product-team budget gate",
                          ["phase1"], [], cap_022_logic))
    registry.add(TestCase("POC-CAP-024", GROUP,
                          "CAP-024: reactive SKU/AZ discovery auto-create + governance item",
                          ["phase1"], [], cap_024_logic))
    registry.add(TestCase("POC-CAP-024-LIVE", GROUP,
                          "CAP-024 (live): Azure auto-create + scope-file governance item",
                          ["phase2"], [], cap_024_live))
