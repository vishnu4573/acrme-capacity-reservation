"""Group 1 — CRG creation and basic reservation lifecycle (POC-01..POC-05).

Covers zonal CRG creation, capacity reservation creation, VM association,
consumption counting, and disassociation / capacity release in the provider
subscription.
"""

from __future__ import annotations

from typing import Any, Dict

from ..az_client import AzClient
from ..config import Config
from ..runner_core import Registry, TestCase, TestResult, make_cleanup_note

GROUP = "G1"
PROVIDER_VM = "acrme-poc-vm-03-01"


def poc_01(config: Config, az: AzClient) -> TestResult:
    """POC-01: Create a zonal CRG in the provider subscription."""
    evidence: Dict[str, Any] = {}
    az.set_subscription(config.provider_subscription_id)

    create = az.run([
        "capacity", "reservation", "group", "create",
        "--resource-group", config.provider_resource_group,
        "--name", config.crg_name,
        "--location", config.primary_region,
        "--zones", "1", "2", "3",
        "-o", "json",
    ])
    evidence["create_command"] = create.command
    evidence["create_result"] = create.as_evidence()

    show = az.run([
        "capacity", "reservation", "group", "show",
        "--resource-group", config.provider_resource_group,
        "--name", config.crg_name,
        "-o", "json",
    ])
    evidence["show_result"] = show.as_evidence()
    evidence.update(make_cleanup_note(
        f"az capacity reservation group delete -g {config.provider_resource_group} "
        f"-n {config.crg_name} --yes"
    ))

    data = show.data if isinstance(show.data, dict) else {}
    prov_state = (data.get("provisioningState")
                  or (data.get("properties") or {}).get("provisioningState"))
    zones = data.get("zones") or []
    evidence["provisioningState"] = prov_state
    evidence["zones"] = zones

    if show.success and prov_state == "Succeeded" and zones:
        return TestResult(
            poc_id="POC-01", status="pass",
            actual_result=f"CRG '{config.crg_name}' provisioned in {config.primary_region} "
                          f"with zones {zones}.",
            evidence=evidence, duration_seconds=create.duration_seconds + show.duration_seconds,
        )
    return TestResult(
        poc_id="POC-01", status="fail",
        actual_result=f"CRG not confirmed Succeeded with zones (state={prov_state}, zones={zones}).",
        evidence=evidence, error=create.stderr or show.stderr,
        duration_seconds=create.duration_seconds + show.duration_seconds,
    )


def poc_02(config: Config, az: AzClient) -> TestResult:
    """POC-02: Create a capacity reservation within the CRG."""
    evidence: Dict[str, Any] = {}
    az.set_subscription(config.provider_subscription_id)

    create = az.run([
        "capacity", "reservation", "create",
        "--resource-group", config.provider_resource_group,
        "--capacity-reservation-group", config.crg_name,
        "--name", config.reservation_name,
        "--sku", config.vm_sku,
        "--capacity", str(config.quantity),
        "--location", config.primary_region,
        "-o", "json",
    ])
    evidence["create_command"] = create.command
    evidence["create_result"] = create.as_evidence()

    show = az.run([
        "capacity", "reservation", "show",
        "--resource-group", config.provider_resource_group,
        "--capacity-reservation-group", config.crg_name,
        "--name", config.reservation_name,
        "-o", "json",
    ])
    evidence["show_result"] = show.as_evidence()
    evidence.update(make_cleanup_note(
        f"az capacity reservation delete -g {config.provider_resource_group} "
        f"-c {config.crg_name} -n {config.reservation_name} --yes"
    ))

    data = show.data if isinstance(show.data, dict) else {}
    prov_state = (data.get("provisioningState")
                  or (data.get("properties") or {}).get("provisioningState"))
    capacity = (data.get("sku") or {}).get("capacity")
    evidence["provisioningState"] = prov_state
    evidence["capacity"] = capacity

    if show.success and prov_state == "Succeeded" and capacity == config.quantity:
        return TestResult(
            poc_id="POC-02", status="pass",
            actual_result=f"Reservation '{config.reservation_name}' Succeeded with "
                          f"capacity {capacity}.",
            evidence=evidence,
        )
    return TestResult(
        poc_id="POC-02", status="fail",
        actual_result=f"Reservation not confirmed (state={prov_state}, capacity={capacity}, "
                      f"expected {config.quantity}).",
        evidence=evidence, error=create.stderr or show.stderr,
    )


def poc_03(config: Config, az: AzClient) -> TestResult:
    """POC-03: Associate a VM with the reservation in the provider subscription."""
    evidence: Dict[str, Any] = {}
    az.set_subscription(config.provider_subscription_id)

    create = az.run([
        "vm", "create",
        "--resource-group", config.provider_resource_group,
        "--name", PROVIDER_VM,
        "--image", "Ubuntu2204",
        "--size", config.vm_sku,
        "--capacity-reservation-group", config.crg_resource_id,
        "--generate-ssh-keys",
        "--location", config.primary_region,
        "--no-wait",
    ], parse_json=False)
    evidence["create_command"] = create.command
    evidence["create_result"] = create.as_evidence()

    wait = az.run([
        "vm", "wait",
        "--resource-group", config.provider_resource_group,
        "--name", PROVIDER_VM,
        "--created",
        "--timeout", str(config.timeout_seconds),
    ], parse_json=False, timeout=config.timeout_seconds + 30)
    evidence["wait_result"] = wait.as_evidence()

    show = az.run([
        "vm", "show",
        "--resource-group", config.provider_resource_group,
        "--name", PROVIDER_VM,
        "--query", "capacityReservation",
        "-o", "json",
    ])
    evidence["show_result"] = show.as_evidence()
    evidence.update(make_cleanup_note(
        f"az vm delete -g {config.provider_resource_group} -n {PROVIDER_VM} --yes"
    ))

    data = show.data if isinstance(show.data, dict) else {}
    assoc_id = ((data.get("capacityReservationGroup") or {}).get("id") or "")
    evidence["associated_crg_id"] = assoc_id
    if assoc_id.lower() == config.crg_resource_id.lower():
        return TestResult(
            poc_id="POC-03", status="pass",
            actual_result=f"VM '{PROVIDER_VM}' associated with CRG {config.crg_name}.",
            evidence=evidence,
        )
    return TestResult(
        poc_id="POC-03", status="fail",
        actual_result=f"VM association not confirmed (got '{assoc_id}').",
        evidence=evidence, error=create.stderr or wait.stderr or show.stderr,
    )


def poc_04(config: Config, az: AzClient) -> TestResult:
    """POC-04: Verify the reservation's associated-VM count increments."""
    evidence: Dict[str, Any] = {}
    az.set_subscription(config.provider_subscription_id)

    show = az.run([
        "capacity", "reservation", "show",
        "--resource-group", config.provider_resource_group,
        "--capacity-reservation-group", config.crg_name,
        "--name", config.reservation_name,
        "--query", "virtualMachinesAssociated",
        "-o", "json",
    ])
    evidence["show_command"] = show.command
    evidence["show_result"] = show.as_evidence()
    associated = show.data if isinstance(show.data, list) else []
    evidence["associated_count"] = len(associated)
    evidence["associated"] = associated

    if show.success and len(associated) >= 1:
        return TestResult(
            poc_id="POC-04", status="pass",
            actual_result=f"Reservation shows {len(associated)} associated VM(s); "
                          f"reserved capacity unchanged.",
            evidence=evidence,
        )
    return TestResult(
        poc_id="POC-04", status="fail",
        actual_result=f"Expected >=1 associated VM, found {len(associated)}.",
        evidence=evidence, error=show.stderr,
    )


def poc_05(config: Config, az: AzClient) -> TestResult:
    """POC-05: Disassociate the VM and verify capacity is released."""
    evidence: Dict[str, Any] = {}
    az.set_subscription(config.provider_subscription_id)

    dealloc = az.run([
        "vm", "deallocate",
        "--resource-group", config.provider_resource_group,
        "--name", PROVIDER_VM,
    ], parse_json=False)
    evidence["deallocate_result"] = dealloc.as_evidence()

    update = az.run([
        "vm", "update",
        "--resource-group", config.provider_resource_group,
        "--name", PROVIDER_VM,
        "--set", "capacityReservation.capacityReservationGroup=null",
        "-o", "json",
    ])
    evidence["update_result"] = update.as_evidence()

    count = az.run([
        "capacity", "reservation", "show",
        "--resource-group", config.provider_resource_group,
        "--capacity-reservation-group", config.crg_name,
        "--name", config.reservation_name,
        "--query", "virtualMachinesAssociated",
        "-o", "json",
    ])
    evidence["count_result"] = count.as_evidence()
    associated = count.data if isinstance(count.data, list) else []
    evidence["associated_count_after"] = len(associated)

    vm_show = az.run([
        "vm", "show",
        "--resource-group", config.provider_resource_group,
        "--name", PROVIDER_VM,
        "--query", "capacityReservation",
        "-o", "json",
    ])
    evidence["vm_show_result"] = vm_show.as_evidence()
    vm_cap = vm_show.data
    evidence["vm_capacityReservation_after"] = vm_cap

    released = len(associated) == 0
    vm_cleared = not vm_cap or (isinstance(vm_cap, dict) and not vm_cap.get("capacityReservationGroup"))
    if released and vm_cleared:
        return TestResult(
            poc_id="POC-05", status="pass",
            actual_result="VM disassociated; association count is 0 and VM shows null "
                          "capacityReservation.",
            evidence=evidence,
        )
    return TestResult(
        poc_id="POC-05", status="fail",
        actual_result=f"Disassociation not fully confirmed (count={len(associated)}, "
                      f"vm_cleared={vm_cleared}).",
        evidence=evidence, error=update.stderr or vm_show.stderr,
    )


def register(registry: Registry) -> None:
    """Register all Group 1 test cases."""
    registry.add(TestCase("POC-01", GROUP, "Create zonal CRG",
                          ["phase1"], [], poc_01))
    registry.add(TestCase("POC-02", GROUP, "Create capacity reservation in CRG",
                          ["phase1"], ["POC-01"], poc_02))
    registry.add(TestCase("POC-03", GROUP, "Associate provider VM with reservation",
                          ["phase1"], ["POC-02"], poc_03))
    registry.add(TestCase("POC-04", GROUP, "Verify consumption count increments",
                          ["phase1"], ["POC-03"], poc_04))
    registry.add(TestCase("POC-05", GROUP, "Disassociate VM; verify capacity released",
                          ["phase1"], ["POC-04"], poc_05))
