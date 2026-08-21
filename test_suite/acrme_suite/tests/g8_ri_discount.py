"""Group 8 — Reserved Instance discount scope (POC-RI-01, POC-RI-02).

Validates that Reserved Instance (RI) discounts are scoped to include the
consumer subscriptions that share a provider CRG (FC-09). Any provider–consumer
pair without the consumer in an RI applied-scope is flagged as a gap requiring
scope reconfiguration.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..az_client import AzClient
from ..config import Config
from ..runner_core import Registry, TestCase, TestResult

GROUP = "G8"


def _list_reservation_orders(az: AzClient) -> List[Dict[str, Any]]:
    res = az.run(["reservations", "reservation-order", "list", "-o", "json"])
    return res.data if isinstance(res.data, list) else []


def _applied_scopes(az: AzClient, order_id: str) -> Dict[str, Any]:
    res = az.run([
        "reservations", "reservation-order", "show",
        "--reservation-order-id", order_id,
        "--query", "properties",
        "-o", "json",
    ])
    return res.data if isinstance(res.data, dict) else {}


def poc_ri_01(config: Config, az: AzClient) -> TestResult:
    """POC-RI-01: Verify RI discount scope for the provider subscription."""
    evidence: Dict[str, Any] = {}
    az.set_subscription(config.provider_subscription_id)
    orders = _list_reservation_orders(az)
    evidence["reservation_order_count"] = len(orders)

    consumer_scope = f"/subscriptions/{config.consumer_subscription_id}".lower()
    provider_scope = f"/subscriptions/{config.provider_subscription_id}".lower()
    order_details: List[Dict[str, Any]] = []
    for order in orders:
        order_id = order.get("name") or order.get("id", "").split("/")[-1]
        props = _applied_scopes(az, order_id)
        reservations = props.get("reservations", []) or []
        # scope may be at the reservation level
        scope_type = props.get("appliedScopeType") or "Unknown"
        applied = props.get("appliedScopes", []) or []
        applied_lc = [str(a).lower() for a in applied]
        consumer_in_scope = (
            scope_type == "Shared"
            or any(consumer_scope in a for a in applied_lc)
        )
        provider_in_scope = (
            scope_type == "Shared"
            or any(provider_scope in a for a in applied_lc)
        )
        order_details.append({
            "order_id": order_id,
            "scope_type": scope_type,
            "applied_scopes": applied,
            "provider_in_scope": provider_in_scope,
            "consumer_in_scope": consumer_in_scope,
            "flag": "Discount Confirmed" if consumer_in_scope else "Gap — Action Required",
        })
    evidence["orders"] = order_details

    if not orders:
        return TestResult(
            poc_id="POC-RI-01", status="pass",
            actual_result="No reservation orders found in provider subscription; RI scope "
                          "documented as empty (nothing to validate).",
            evidence=evidence,
        )
    gaps = [o for o in order_details if o["flag"].startswith("Gap")]
    return TestResult(
        poc_id="POC-RI-01", status="pass",
        actual_result=f"Documented {len(order_details)} reservation order(s); "
                      f"{len(gaps)} flagged as gaps requiring scope reconfiguration.",
        evidence=evidence,
    )


def poc_ri_02(config: Config, az: AzClient) -> TestResult:
    """POC-RI-02: Document the discount gap per provider–consumer pair."""
    evidence: Dict[str, Any] = {}
    az.set_subscription(config.provider_subscription_id)
    orders = _list_reservation_orders(az)

    # Consumer subs currently in scope (from config; POC-09 evidence augments this).
    consumer_subs = [config.consumer_subscription_id]
    table: List[Dict[str, Any]] = []
    for consumer in consumer_subs:
        consumer_scope = f"/subscriptions/{consumer}".lower()
        confirmed = False
        matched_scope_type = "None"
        for order in orders:
            order_id = order.get("name") or order.get("id", "").split("/")[-1]
            props = _applied_scopes(az, order_id)
            scope_type = props.get("appliedScopeType") or "Unknown"
            applied = [str(a).lower() for a in (props.get("appliedScopes", []) or [])]
            if scope_type == "Shared" or any(consumer_scope in a for a in applied):
                confirmed = True
                matched_scope_type = scope_type
                break
        table.append({
            "provider_sub": config.provider_subscription_id,
            "consumer_sub": consumer,
            "ri_discount_confirmed": "Y" if confirmed else "N",
            "scope_type": matched_scope_type,
            "notes": ("Discount applies" if confirmed
                      else "Gap — reconfigure RI applied scope to include consumer"),
        })
    evidence["discount_matrix"] = table
    gaps = [row for row in table if row["ri_discount_confirmed"] == "N"]
    evidence["gap_count"] = len(gaps)

    return TestResult(
        poc_id="POC-RI-02", status="pass",
        actual_result=f"Discount matrix built for {len(table)} provider–consumer pair(s); "
                      f"{len(gaps)} gap(s) requiring scope reconfiguration.",
        evidence=evidence,
    )


def register(registry: Registry) -> None:
    """Register all Group 8 test cases."""
    registry.add(TestCase("POC-RI-01", GROUP, "Verify RI discount scope for provider sub",
                          ["phase1"], [], poc_ri_01))
    registry.add(TestCase("POC-RI-02", GROUP, "Document discount gap per customer pair (FC-09)",
                          ["phase2"], ["POC-09"], poc_ri_02))
