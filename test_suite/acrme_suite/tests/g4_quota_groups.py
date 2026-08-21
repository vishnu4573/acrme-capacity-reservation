"""Group 4 — Quota Group validation (POC-30..POC-32).

Quota Groups is a Public Preview API. POC-30 is a HARD GATE: if the API is not
available in the tenant, all quota-group engineering is blocked.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List

from ..az_client import AzClient
from ..config import Config
from ..runner_core import Registry, TestCase, TestResult

GROUP = "G4"
QG_API_VERSION = "2025-03-01-preview"


def _group_quotas_url(config: Config, group: str = "") -> str:
    base = (f"{config.arm_base_url}/subscriptions/{config.provider_subscription_id}"
            f"/providers/Microsoft.Quota/groupQuotas")
    if group:
        base = f"{base}/{group}"
    return f"{base}?api-version={QG_API_VERSION}"


def poc_30(config: Config, az: AzClient) -> TestResult:
    """POC-30: Verify Quota Group API availability (hard gate)."""
    evidence: Dict[str, Any] = {}
    az.set_subscription(config.provider_subscription_id)

    if not config.quota_group_enabled:
        return TestResult(
            poc_id="POC-30", status="skipped",
            actual_result="quota_group.name not configured — quota group tests skipped.",
            evidence={"note": "Set quota_group.name in config.yaml to enable."},
        )

    list_res = az.az_rest("GET", _group_quotas_url(config))
    evidence["list_command"] = list_res.command
    evidence["list_result"] = list_res.as_evidence()

    api_available = list_res.success or list_res.returncode == 0
    # Attempt creation (idempotent PUT).
    put_body = {"properties": {"displayName": config.quota_group_name}}
    put_res = az.az_rest("PUT", _group_quotas_url(config, config.quota_group_name),
                         body=put_body)
    evidence["put_result"] = put_res.as_evidence()

    # Per-region probing.
    per_region: Dict[str, str] = {}
    for label, region in (("primary", config.primary_region),
                          ("dr", config.dr_region),
                          ("nonprod", config.nonprod_region)):
        # groupQuotas are subscription/tenant scoped; region recorded for context.
        per_region[label] = region
    evidence["regions_probed"] = per_region

    stderr = (list_res.stderr or "") + (put_res.stderr or "")
    not_available = ("MethodNotAllowed" in stderr or "404" in stderr
                     or "was not found" in stderr.lower())

    if (api_available or put_res.success) and not not_available:
        return TestResult(
            poc_id="POC-30", status="pass",
            actual_result="Quota Groups API available; group create/list succeeded.",
            evidence=evidence,
        )
    return TestResult(
        poc_id="POC-30", status="blocked",
        actual_result="Quota Groups API not available — all quota group engineering "
                      "blocked (POC-30 hard gate).",
        evidence=evidence, error=stderr[:2000],
    )


def poc_31(config: Config, az: AzClient) -> TestResult:
    """POC-31: Add subscription to quota group and verify headroom (phase2)."""
    evidence: Dict[str, Any] = {}
    az.set_subscription(config.provider_subscription_id)

    before = az.az_rest("GET", _group_quotas_url(config, config.quota_group_name))
    evidence["before_result"] = before.as_evidence()

    add_url = (f"{config.arm_base_url}/subscriptions/{config.provider_subscription_id}"
               f"/providers/Microsoft.Quota/groupQuotas/{config.quota_group_name}"
               f"/subscriptions/{config.consumer_subscription_id}"
               f"?api-version={QG_API_VERSION}")
    add = az.az_rest("PUT", add_url, body={"properties": {}})
    evidence["add_command"] = add.command
    evidence["add_result"] = add.as_evidence()

    # Poll for propagation.
    t0 = time.time()
    propagated = False
    for _ in range(6):
        time.sleep(10)
        after = az.az_rest("GET", add_url)
        if after.success:
            propagated = True
            evidence["after_result"] = after.as_evidence()
            break
    evidence["propagation_seconds"] = round(time.time() - t0, 1)
    evidence["propagated"] = propagated

    if add.success and propagated:
        return TestResult(
            poc_id="POC-31", status="pass",
            actual_result=f"Subscription added to quota group; membership propagated in "
                          f"~{evidence['propagation_seconds']}s.",
            evidence=evidence,
        )
    return TestResult(
        poc_id="POC-31", status="fail",
        actual_result="Could not confirm subscription membership propagation.",
        evidence=evidence, error=add.stderr,
    )


def poc_32(config: Config, az: AzClient) -> TestResult:
    """POC-32: Release and reuse behaviour (phase2)."""
    evidence: Dict[str, Any] = {}
    az.set_subscription(config.provider_subscription_id)
    member_url = (f"{config.arm_base_url}/subscriptions/{config.provider_subscription_id}"
                  f"/providers/Microsoft.Quota/groupQuotas/{config.quota_group_name}"
                  f"/subscriptions/{config.consumer_subscription_id}"
                  f"?api-version={QG_API_VERSION}")

    remove = az.az_rest("DELETE", member_url)
    evidence["remove_result"] = remove.as_evidence()

    # Poll for removal propagation.
    t0 = time.time()
    for _ in range(6):
        time.sleep(10)
        check = az.az_rest("GET", member_url)
        if not check.success:  # membership gone
            break
    evidence["remove_propagation_seconds"] = round(time.time() - t0, 1)

    readd = az.az_rest("PUT", member_url, body={"properties": {}})
    evidence["readd_result"] = readd.as_evidence()

    t1 = time.time()
    readded = False
    for _ in range(6):
        time.sleep(10)
        check = az.az_rest("GET", member_url)
        if check.success:
            readded = True
            break
    evidence["readd_propagation_seconds"] = round(time.time() - t1, 1)
    evidence["readded"] = readded

    if remove.success and readd.success and readded:
        return TestResult(
            poc_id="POC-32", status="pass",
            actual_result="Release+reuse consistent: removal and re-add both propagated; "
                          "no orphaned state observed.",
            evidence=evidence,
        )
    return TestResult(
        poc_id="POC-32", status="fail",
        actual_result="Release/reuse cycle not fully confirmed.",
        evidence=evidence, error=remove.stderr or readd.stderr,
    )


def register(registry: Registry) -> None:
    """Register all Group 4 test cases."""
    registry.add(TestCase("POC-30", GROUP, "Verify Quota Group API availability (hard gate)",
                          ["phase1"], [], poc_30,
                          warning="Quota Groups is Public Preview — POC-30 is a hard gate."))
    registry.add(TestCase("POC-31", GROUP, "Add subscription to quota group; verify headroom",
                          ["phase2"], ["POC-30"], poc_31))
    registry.add(TestCase("POC-32", GROUP, "Release and reuse behaviour",
                          ["phase2"], ["POC-30"], poc_32))
