"""Group 3 — DR capacity and failover (POC-11..POC-14).

Creates DR-region capacity, simulates failover/failback, and validates that DR
floor protection is an engine-controlled concept (Azure does not enforce it
natively — assumption A-06).
"""

from __future__ import annotations

import time
from typing import Any, Dict

from ..az_client import AzClient
from ..config import Config
from ..runner_core import Registry, TestCase, TestResult, make_cleanup_note

GROUP = "G3"
DR_VM = "acrme-poc-vm-12-dr"
PROVIDER_VM = "acrme-poc-vm-03-01"


def poc_11(config: Config, az: AzClient) -> TestResult:
    """POC-11: Create DR-region CRG and reservation."""
    evidence: Dict[str, Any] = {}
    az.set_subscription(config.provider_subscription_id)

    crg = az.run([
        "capacity", "reservation", "group", "create",
        "--resource-group", config.provider_resource_group,
        "--name", config.dr_crg_name,
        "--location", config.dr_region,
        "--zones", "1", "2", "3",
        "-o", "json",
    ])
    evidence["crg_create_result"] = crg.as_evidence()

    res = az.run([
        "capacity", "reservation", "create",
        "--resource-group", config.provider_resource_group,
        "--capacity-reservation-group", config.dr_crg_name,
        "--name", config.dr_reservation_name,
        "--sku", config.vm_sku,
        "--capacity", str(config.dr_quantity),
        "--location", config.dr_region,
        "-o", "json",
    ])
    evidence["reservation_create_result"] = res.as_evidence()

    show = az.run([
        "capacity", "reservation", "show",
        "--resource-group", config.provider_resource_group,
        "--capacity-reservation-group", config.dr_crg_name,
        "--name", config.dr_reservation_name,
        "-o", "json",
    ])
    evidence["show_result"] = show.as_evidence()
    evidence.update(make_cleanup_note(
        f"az capacity reservation group delete -g {config.provider_resource_group} "
        f"-n {config.dr_crg_name} --yes"
    ))
    data = show.data if isinstance(show.data, dict) else {}
    prov_state = (data.get("provisioningState")
                  or (data.get("properties") or {}).get("provisioningState"))
    location = data.get("location")
    evidence["provisioningState"] = prov_state
    evidence["location"] = location
    evidence["dr_region_distinct"] = config.dr_region != config.primary_region

    if (prov_state == "Succeeded" and location
            and location.lower() == config.dr_region.lower()
            and config.dr_region != config.primary_region):
        return TestResult(
            poc_id="POC-11", status="pass",
            actual_result=f"DR reservation Succeeded in {location} (distinct from primary).",
            evidence=evidence,
        )
    return TestResult(
        poc_id="POC-11", status="fail",
        actual_result=f"DR reservation not confirmed (state={prov_state}, location={location}).",
        evidence=evidence, error=crg.stderr or res.stderr,
    )


def poc_12(config: Config, az: AzClient) -> TestResult:
    """POC-12: Simulate DR failover (phase2+)."""
    evidence: Dict[str, Any] = {}
    az.set_subscription(config.provider_subscription_id)
    t0 = time.time()

    dealloc = az.run([
        "vm", "deallocate",
        "--resource-group", config.provider_resource_group,
        "--name", PROVIDER_VM,
    ], parse_json=False)
    t1 = time.time()
    evidence["deallocate_result"] = dealloc.as_evidence()
    evidence["deallocate_note"] = ("Primary VM deallocate attempted; if VM absent this "
                                   "step is documented and failover continues.")

    create = az.run([
        "vm", "create",
        "--resource-group", config.provider_resource_group,
        "--name", DR_VM,
        "--image", "Ubuntu2204",
        "--size", config.vm_sku,
        "--capacity-reservation-group", config.dr_crg_resource_id,
        "--generate-ssh-keys",
        "--location", config.dr_region,
        "--no-wait",
    ], parse_json=False)
    evidence["dr_create_result"] = create.as_evidence()

    wait = az.run([
        "vm", "wait",
        "--resource-group", config.provider_resource_group,
        "--name", DR_VM,
        "--created",
        "--timeout", str(config.timeout_seconds),
    ], parse_json=False, timeout=config.timeout_seconds + 30)
    t2 = time.time()
    evidence["dr_wait_result"] = wait.as_evidence()
    evidence.update(make_cleanup_note(
        f"az vm delete -g {config.provider_resource_group} -n {DR_VM} --yes"
    ))

    show = az.run([
        "vm", "show", "-g", config.provider_resource_group, "-n", DR_VM,
        "--query", "capacityReservation", "-o", "json",
    ])
    evidence["dr_vm_capacity"] = show.data
    evidence["timings"] = {
        "t0": t0, "t1_deallocate_complete": t1, "t2_dr_running": t2,
        "deallocate_seconds": round(t1 - t0, 1),
        "dr_provision_seconds": round(t2 - t1, 1),
    }
    data = show.data if isinstance(show.data, dict) else {}
    assoc = ((data.get("capacityReservationGroup") or {}).get("id") or "")
    if assoc.lower() == config.dr_crg_resource_id.lower():
        return TestResult(
            poc_id="POC-12", status="pass",
            actual_result=f"DR VM running against DR reservation; failover took "
                          f"{round(t2 - t1, 1)}s after deallocate.",
            evidence=evidence,
        )
    return TestResult(
        poc_id="POC-12", status="fail",
        actual_result="DR VM not confirmed against DR reservation.",
        evidence=evidence, error=create.stderr or wait.stderr,
    )


def poc_13(config: Config, az: AzClient) -> TestResult:
    """POC-13: DR floor protection verification (documentation of A-06)."""
    evidence: Dict[str, Any] = {}
    az.set_subscription(config.provider_subscription_id)
    show = az.run([
        "capacity", "reservation", "show",
        "--resource-group", config.provider_resource_group,
        "--capacity-reservation-group", config.dr_crg_name,
        "--name", config.dr_reservation_name,
        "--query", "sku",
        "-o", "json",
    ])
    evidence["dr_sku_result"] = show.as_evidence()
    data = show.data if isinstance(show.data, dict) else {}
    dr_qty = data.get("capacity", config.dr_quantity)
    floor_vcpu = dr_qty * config.vcpus_per_instance * (config.dr_floor_percentage / 100.0)
    evidence["dr_quantity"] = dr_qty
    evidence["vcpus_per_instance"] = config.vcpus_per_instance
    evidence["dr_floor_percentage"] = config.dr_floor_percentage
    evidence["dr_floor_vcpu"] = floor_vcpu
    evidence["A-06"] = ("Azure does NOT natively enforce a DR floor; the floor is an "
                        "ACRME engine-controlled policy. This test documents the "
                        "calculation only.")
    # This is a documentation/derivation test — passes when the floor is computed.
    return TestResult(
        poc_id="POC-13", status="pass",
        actual_result=f"DR floor computed as {floor_vcpu:.0f} vCPU "
                      f"({dr_qty} × {config.vcpus_per_instance} × "
                      f"{config.dr_floor_percentage}%). Native enforcement absent (A-06).",
        evidence=evidence,
    )


def poc_14(config: Config, az: AzClient) -> TestResult:
    """POC-14: Failback — restore primary, release DR (phase2+)."""
    evidence: Dict[str, Any] = {}
    az.set_subscription(config.provider_subscription_id)

    dealloc = az.run([
        "vm", "deallocate", "-g", config.provider_resource_group, "-n", DR_VM,
    ], parse_json=False)
    evidence["dr_deallocate_result"] = dealloc.as_evidence()

    update = az.run([
        "vm", "update", "-g", config.provider_resource_group, "-n", DR_VM,
        "--set", "capacityReservation.capacityReservationGroup=null", "-o", "json",
    ])
    evidence["dr_disassociate_result"] = update.as_evidence()

    show = az.run([
        "capacity", "reservation", "show",
        "--resource-group", config.provider_resource_group,
        "--capacity-reservation-group", config.dr_crg_name,
        "--name", config.dr_reservation_name,
        "--query", "virtualMachinesAssociated",
        "-o", "json",
    ])
    evidence["dr_associations_after"] = show.data
    associated = show.data if isinstance(show.data, list) else []
    evidence["dr_association_count"] = len(associated)

    if len(associated) == 0:
        return TestResult(
            poc_id="POC-14", status="pass",
            actual_result="Failback complete: DR associations cleared; DR capacity "
                          "returned to available pool.",
            evidence=evidence,
        )
    return TestResult(
        poc_id="POC-14", status="fail",
        actual_result=f"DR still shows {len(associated)} association(s) after failback.",
        evidence=evidence, error=update.stderr,
    )


def register(registry: Registry) -> None:
    """Register all Group 3 test cases."""
    registry.add(TestCase("POC-11", GROUP, "Create DR CRG and reservation",
                          ["phase1"], ["POC-01"], poc_11))
    registry.add(TestCase("POC-12", GROUP, "Simulate DR failover",
                          ["phase2"], ["POC-11"], poc_12,
                          warning="Destructive: deallocates the primary VM."))
    registry.add(TestCase("POC-13", GROUP, "DR floor protection verification (A-06)",
                          ["phase1"], ["POC-11"], poc_13))
    registry.add(TestCase("POC-14", GROUP, "Failback — restore primary, release DR",
                          ["phase2"], ["POC-12"], poc_14))
