"""Group 5 — Engine safety controls (POC-15..POC-20).

Includes hypothesis-validation tests (POC-15 zero-quantity, POC-16 ARG indexing
delay), a concurrency-safety test (POC-17), and engine-dependent tier tests
(POC-18/19/20) that are blocked until the ACRME engine is deployed.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List

from ..az_client import AzClient
from ..config import Config
from ..runner_core import Registry, TestCase, TestResult, make_cleanup_note

GROUP = "G5"


def poc_15(config: Config, az: AzClient) -> TestResult:
    """POC-15: Zero-quantity reservation behaviour (hypothesis validation)."""
    evidence: Dict[str, Any] = {}
    az.set_subscription(config.provider_subscription_id)

    update = az.run([
        "capacity", "reservation", "update",
        "--resource-group", config.provider_resource_group,
        "--capacity-reservation-group", config.crg_name,
        "--name", config.reservation_name,
        "--capacity", "0",
        "-o", "json",
    ])
    evidence["update_command"] = update.command
    evidence["update_result"] = update.as_evidence()
    evidence["api_accepted_zero"] = update.success

    # Observe VM state after the attempt (provider VM from POC-03).
    vm_state = az.run([
        "vm", "get-instance-view",
        "-g", config.provider_resource_group, "-n", "acrme-poc-vm-03-01",
        "--query", "instanceView.statuses[?starts_with(code, 'PowerState')].code",
        "-o", "json",
    ])
    evidence["vm_state_result"] = vm_state.as_evidence()
    evidence["vm_power_state"] = vm_state.data

    # Restore capacity for downstream tests (best-effort).
    restore = az.run([
        "capacity", "reservation", "update",
        "--resource-group", config.provider_resource_group,
        "--capacity-reservation-group", config.crg_name,
        "--name", config.reservation_name,
        "--capacity", str(config.quantity),
        "-o", "json",
    ])
    evidence["restore_result"] = restore.as_evidence()
    evidence["hypothesis"] = ("Documentation test: records whether the API accepts a "
                              "zero-capacity update and whether associated VMs keep "
                              "running. Any outcome is acceptable — result documented.")

    # Documentation-gathering test: passes as long as commands executed & recorded.
    return TestResult(
        poc_id="POC-15", status="pass",
        actual_result=f"Zero-quantity update executed (api_accepted={update.success}); "
                      f"VM power state and behaviour recorded for engineering analysis.",
        evidence=evidence,
    )


def poc_16(config: Config, az: AzClient) -> TestResult:
    """POC-16: ARG indexing delay measurement (5 iterations)."""
    evidence: Dict[str, Any] = {}
    az.set_subscription(config.provider_subscription_id)
    delays: List[float] = []
    iterations = 5
    kusto = (
        "Resources | where type =~ 'microsoft.compute/capacityreservationgroups' "
        f"| where name == '{config.crg_name}'"
    )

    for i in range(iterations):
        arm = az.run([
            "capacity", "reservation", "group", "show",
            "-g", config.provider_resource_group, "-n", config.crg_name, "-o", "json",
        ])
        arm_time = time.time()
        matched_at = None
        # Poll ARG up to ~5 minutes in 30s steps.
        for _ in range(10):
            arg = az.graph_query(kusto, subscription_id=config.provider_subscription_id)
            rows = (arg.data or {}).get("data", []) if isinstance(arg.data, dict) else []
            if rows:
                matched_at = time.time()
                break
            time.sleep(30)
        if matched_at:
            delays.append(round(matched_at - arm_time, 1))
        evidence[f"iteration_{i}"] = {
            "arm_success": arm.success,
            "arg_matched": matched_at is not None,
            "delay_seconds": delays[-1] if matched_at else None,
        }

    if delays:
        delays_sorted = sorted(delays)
        median = delays_sorted[len(delays_sorted) // 2]
        evidence["delays_seconds"] = delays
        evidence["min_delay"] = min(delays)
        evidence["median_delay"] = median
        evidence["max_delay"] = max(delays)
        return TestResult(
            poc_id="POC-16", status="pass",
            actual_result=f"ARG indexing delay measured over {len(delays)} iteration(s): "
                          f"min={min(delays)}s median={median}s max={max(delays)}s.",
            evidence=evidence,
        )
    evidence["delays_seconds"] = delays
    return TestResult(
        poc_id="POC-16", status="pass",
        actual_result="ARG delay test executed; ARG did not index within polling window "
                      "(documented for engineering threshold configuration).",
        evidence=evidence,
    )


def _create_vm_thread(az: AzClient, config: Config, name: str, results: Dict[str, Any]) -> None:
    """Worker that creates one VM against the shared CRG."""
    res = az.run([
        "vm", "create",
        "--resource-group", config.provider_resource_group,
        "--name", name,
        "--image", "Ubuntu2204",
        "--size", config.vm_sku,
        "--capacity-reservation-group", config.crg_resource_id,
        "--generate-ssh-keys",
        "--location", config.primary_region,
    ], parse_json=True, timeout=config.timeout_seconds + 60)
    results[name] = {"success": res.success, "returncode": res.returncode,
                     "stderr": (res.stderr or "")[:800]}


def poc_17(config: Config, az: AzClient) -> TestResult:
    """POC-17: Concurrent association safety (two simultaneous VM creates)."""
    evidence: Dict[str, Any] = {}
    az.set_subscription(config.provider_subscription_id)
    names = ["acrme-poc-vm-17-a", "acrme-poc-vm-17-b"]
    thread_results: Dict[str, Any] = {}

    threads = [
        threading.Thread(target=_create_vm_thread, args=(az, config, n, thread_results))
        for n in names
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    evidence["thread_results"] = thread_results
    evidence.update(make_cleanup_note(
        "az vm delete -g {rg} -n acrme-poc-vm-17-a acrme-poc-vm-17-b --yes".format(
            rg=config.provider_resource_group)
    ))

    show = az.run([
        "capacity", "reservation", "show",
        "--resource-group", config.provider_resource_group,
        "--capacity-reservation-group", config.crg_name,
        "--name", config.reservation_name,
        "--query", "virtualMachinesAssociated", "-o", "json",
    ])
    associated = show.data if isinstance(show.data, list) else []
    evidence["associated_count"] = len(associated)
    both_ok = all(r.get("success") for r in thread_results.values())

    if both_ok and len(associated) >= 2:
        return TestResult(
            poc_id="POC-17", status="pass",
            actual_result=f"Both concurrent VM creates succeeded; association count "
                          f"{len(associated)} with no API error or mismatch.",
            evidence=evidence,
        )
    return TestResult(
        poc_id="POC-17", status="fail",
        actual_result=f"Concurrent association not clean (both_ok={both_ok}, "
                      f"count={len(associated)}).",
        evidence=evidence,
    )


def _engine_required(poc_id: str, note: str) -> TestResult:
    """Return a standard 'engine not deployed' blocked result."""
    return TestResult(
        poc_id=poc_id, status="blocked",
        actual_result=f"Engine not deployed — manual test required. {note}",
        evidence={"engine_required": True, "note": note},
    )


def poc_18(config: Config, az: AzClient) -> TestResult:
    """POC-18: Tier 1 automatic capacity increase (engine required)."""
    return _engine_required("POC-18", "Tier 1 auto-increase per workbook §4, POC-18.")


def poc_19(config: Config, az: AzClient) -> TestResult:
    """POC-19: Tier 2 approval gate (engine required)."""
    return _engine_required("POC-19", "Tier 2 approval gate per workbook §4, POC-19.")


def poc_20(config: Config, az: AzClient) -> TestResult:
    """POC-20: Tier 3 rejection in Phase 1 (engine required)."""
    return _engine_required(
        "POC-20",
        "Tier 3 must be REJECTED in Phase 1; requires engine deployment to validate.",
    )


def register(registry: Registry) -> None:
    """Register all Group 5 test cases."""
    registry.add(TestCase("POC-15", GROUP, "Zero-quantity reservation behaviour",
                          ["phase1"], ["POC-03"], poc_15,
                          warning="Hypothesis-validation: temporarily sets capacity to 0."))
    registry.add(TestCase("POC-16", GROUP, "ARG indexing delay measurement",
                          ["phase1"], ["POC-04"], poc_16))
    registry.add(TestCase("POC-17", GROUP, "Concurrent association safety",
                          ["phase1"], ["POC-06"], poc_17))
    registry.add(TestCase("POC-18", GROUP, "Tier 1 automatic capacity increase",
                          ["phase2"], [], poc_18))
    registry.add(TestCase("POC-19", GROUP, "Tier 2 approval gate",
                          ["phase2"], [], poc_19))
    registry.add(TestCase("POC-20", GROUP, "Tier 3 rejection in Phase 1",
                          ["phase1"], [], poc_20))
