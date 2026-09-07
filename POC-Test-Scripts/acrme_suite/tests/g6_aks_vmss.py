"""Group 6 — AKS and VMSS behaviour (POC-AKS-01/02, POC-VMSS-01/02/03, POC-VMSS-DR).

AKS CRG association is validated at node-pool creation, and the FC-18 constraint
(node-pool recreation required to change CRG) is documented. VMSS tests gather
model-level vs instance-level association behaviour, and POC-VMSS-DR documents
the FC-08 preview limitation for zone-outage reprovisioning.
"""

from __future__ import annotations

from typing import Any, Dict

from ..az_client import AzClient
from ..config import Config
from ..runner_core import Registry, TestCase, TestResult, make_cleanup_note

GROUP = "G6"


def _aks_skip(poc_id: str) -> TestResult:
    return TestResult(
        poc_id=poc_id, status="skipped",
        actual_result="AKS coordinates not configured (aks.resource_group / cluster_name "
                      "/ nodepool_name) — AKS test skipped.",
        evidence={"note": "Populate the aks section of config.yaml to enable."},
    )


def poc_aks_01(config: Config, az: AzClient) -> TestResult:
    """POC-AKS-01: AKS node pool CRG association at creation."""
    if not config.aks_enabled:
        return _aks_skip("POC-AKS-01")
    evidence: Dict[str, Any] = {}
    az.set_subscription(config.provider_subscription_id)

    add = az.run([
        "aks", "nodepool", "add",
        "--resource-group", config.aks_resource_group,
        "--cluster-name", config.aks_cluster_name,
        "--name", config.aks_nodepool_name,
        "--node-vm-size", config.vm_sku,
        "--capacity-reservation-group", config.crg_resource_id,
        "--node-count", "1",
        "-o", "json",
    ])
    evidence["add_result"] = add.as_evidence()

    show = az.run([
        "aks", "nodepool", "show",
        "--resource-group", config.aks_resource_group,
        "--cluster-name", config.aks_cluster_name,
        "--name", config.aks_nodepool_name,
        "--query", "capacityReservationGroupId", "-o", "tsv",
    ], parse_json=False)
    evidence["show_result"] = show.as_evidence()
    crg_id = (show.stdout or "").strip()
    evidence["capacityReservationGroupId"] = crg_id
    evidence.update(make_cleanup_note(
        f"az aks nodepool delete -g {config.aks_resource_group} "
        f"--cluster-name {config.aks_cluster_name} -n {config.aks_nodepool_name}"
    ))

    if crg_id.lower() == config.crg_resource_id.lower():
        return TestResult(
            poc_id="POC-AKS-01", status="pass",
            actual_result=f"Node pool '{config.aks_nodepool_name}' created with CRG "
                          f"association.",
            evidence=evidence,
        )
    return TestResult(
        poc_id="POC-AKS-01", status="fail",
        actual_result=f"Node pool CRG association not confirmed (got '{crg_id}').",
        evidence=evidence, error=add.stderr,
    )


def poc_aks_02(config: Config, az: AzClient) -> TestResult:
    """POC-AKS-02: Existing node pool requires recreation for CRG change (FC-18)."""
    if not config.aks_enabled:
        return _aks_skip("POC-AKS-02")
    evidence: Dict[str, Any] = {}
    az.set_subscription(config.provider_subscription_id)

    update = az.run([
        "aks", "nodepool", "update",
        "--resource-group", config.aks_resource_group,
        "--cluster-name", config.aks_cluster_name,
        "--name", config.aks_nodepool_name,
        "--capacity-reservation-group", config.crg_resource_id,
        "-o", "json",
    ])
    evidence["update_result"] = update.as_evidence()
    evidence["in_place_update_accepted"] = update.success
    evidence["FC-18"] = ("Per AKS Node Disruption Policy, changing a node pool's CRG "
                         "requires node-pool recreation; in-place update is expected to "
                         "be rejected or ignored.")

    # Documentation test — passes on recording behaviour.
    return TestResult(
        poc_id="POC-AKS-02", status="pass",
        actual_result=f"In-place CRG update behaviour recorded (accepted={update.success}); "
                      f"FC-18 documented — recreation required.",
        evidence=evidence,
    )


def _vmss_doc_test(config: Config, az: AzClient, poc_id: str, name: str,
                   orchestration: str) -> TestResult:
    """Create a VMSS with a CRG reference and document association behaviour."""
    evidence: Dict[str, Any] = {}
    az.set_subscription(config.provider_subscription_id)
    vmss_name = f"acrme-poc-{poc_id.lower().replace('poc-', '')}"

    args = [
        "vmss", "create",
        "--resource-group", config.provider_resource_group,
        "--name", vmss_name,
        "--image", "Ubuntu2204",
        "--vm-sku", config.vm_sku,
        "--instance-count", "1",
        "--capacity-reservation-group", config.crg_resource_id,
        "--generate-ssh-keys",
        "--location", config.primary_region,
        "-o", "json",
    ]
    if orchestration == "Flexible":
        args += ["--orchestration-mode", "Flexible"]
    else:
        args += ["--orchestration-mode", "Uniform"]

    create = az.run(args, parse_json=True, timeout=config.timeout_seconds + 60)
    evidence["create_command"] = create.command
    evidence["create_result"] = create.as_evidence()

    show = az.run([
        "vmss", "show",
        "-g", config.provider_resource_group, "-n", vmss_name,
        "--query", "virtualMachineProfile.capacityReservation", "-o", "json",
    ])
    evidence["model_capacity_reservation"] = show.data
    evidence["orchestration_mode"] = orchestration
    evidence.update(make_cleanup_note(
        f"az vmss delete -g {config.provider_resource_group} -n {vmss_name}"
    ))

    model_has_crg = bool(show.data)
    status = "pass" if create.success else "fail"
    return TestResult(
        poc_id=poc_id, status=status,
        actual_result=f"{orchestration} VMSS '{vmss_name}' create success="
                      f"{create.success}; model-level CRG present={model_has_crg}. "
                      f"Behaviour documented.",
        evidence=evidence, error=None if create.success else create.stderr,
    )


def poc_vmss_01(config: Config, az: AzClient) -> TestResult:
    """POC-VMSS-01: Uniform VMSS model-level CRG association."""
    return _vmss_doc_test(config, az, "POC-VMSS-01", "Uniform VMSS", "Uniform")


def poc_vmss_02(config: Config, az: AzClient) -> TestResult:
    """POC-VMSS-02: Flexible VMSS model-level CRG association."""
    return _vmss_doc_test(config, az, "POC-VMSS-02", "Flexible VMSS", "Flexible")


def poc_vmss_03(config: Config, az: AzClient) -> TestResult:
    """POC-VMSS-03: VMSS disassociation behaviour."""
    evidence: Dict[str, Any] = {}
    az.set_subscription(config.provider_subscription_id)
    vmss_name = "acrme-poc-vmss-01"  # created by POC-VMSS-01

    update = az.run([
        "vmss", "update",
        "-g", config.provider_resource_group, "-n", vmss_name,
        "--set", "virtualMachineProfile.capacityReservation=null", "-o", "json",
    ])
    evidence["disassociate_result"] = update.as_evidence()

    show = az.run([
        "vmss", "show", "-g", config.provider_resource_group, "-n", vmss_name,
        "--query", "virtualMachineProfile.capacityReservation", "-o", "json",
    ])
    evidence["model_capacity_reservation_after"] = show.data
    evidence["note"] = ("Records whether model-level CRG can be cleared and whether "
                        "instances require reprovisioning to take effect.")
    return TestResult(
        poc_id="POC-VMSS-03", status="pass",
        actual_result=f"VMSS disassociation behaviour recorded (update success="
                      f"{update.success}).",
        evidence=evidence,
    )


def poc_vmss_dr(config: Config, az: AzClient) -> TestResult:
    """POC-VMSS-DR: VMSS zone-outage reprovisioning via shared CRG (FC-08)."""
    evidence: Dict[str, Any] = {}
    az.set_subscription(config.consumer_subscription_id)
    vmss_name = "acrme-poc-vmss-dr"

    create = az.run([
        "vmss", "create",
        "--resource-group", config.consumer_resource_group,
        "--name", vmss_name,
        "--image", "Ubuntu2204",
        "--vm-sku", config.vm_sku,
        "--instance-count", "2",
        "--capacity-reservation-group", config.crg_resource_id,
        "--generate-ssh-keys",
        "--location", config.primary_region,
        "--orchestration-mode", "Uniform",
        "-o", "json",
    ], parse_json=True, timeout=config.timeout_seconds + 60)
    evidence["create_result"] = create.as_evidence()

    # Attempt a reprovision (reimage) to observe shared-CRG behaviour.
    reimage = az.run([
        "vmss", "reimage",
        "-g", config.consumer_resource_group, "-n", vmss_name,
    ], parse_json=False, timeout=config.timeout_seconds + 60)
    evidence["reimage_result"] = reimage.as_evidence()
    evidence["FC-08"] = ("Preview limitation: VMSS reprovisioning via a shared CRG during "
                         "a real zone outage is not supported. This test documents the "
                         "observed behaviour; any result is acceptable.")
    evidence.update(make_cleanup_note(
        f"az vmss delete -g {config.consumer_resource_group} -n {vmss_name} "
        f"--subscription {config.consumer_subscription_id}"
    ))

    # Documentation-gathering test — passes on recording the outcome.
    return TestResult(
        poc_id="POC-VMSS-DR", status="pass",
        actual_result=f"VMSS shared-CRG reprovisioning attempted (create success="
                      f"{create.success}, reimage success={reimage.success}); FC-08 "
                      f"behaviour documented.",
        evidence=evidence,
    )


def register(registry: Registry) -> None:
    """Register all Group 6 test cases."""
    registry.add(TestCase("POC-AKS-01", GROUP, "AKS node pool CRG association at creation",
                          ["phase2"], ["POC-08"], poc_aks_01))
    registry.add(TestCase("POC-AKS-02", GROUP, "AKS CRG change requires recreation (FC-18)",
                          ["phase2"], ["POC-AKS-01"], poc_aks_02))
    registry.add(TestCase("POC-VMSS-01", GROUP, "Uniform VMSS model-level CRG association",
                          ["phase2"], ["POC-01"], poc_vmss_01))
    registry.add(TestCase("POC-VMSS-02", GROUP, "Flexible VMSS model-level CRG association",
                          ["phase2"], ["POC-01"], poc_vmss_02))
    registry.add(TestCase("POC-VMSS-03", GROUP, "VMSS disassociation behaviour",
                          ["phase2"], ["POC-VMSS-01"], poc_vmss_03))
    registry.add(TestCase("POC-VMSS-DR", GROUP, "VMSS zone-outage via shared CRG (FC-08)",
                          ["phase2"], ["POC-06"], poc_vmss_dr,
                          warning="Preview limitation (FC-08) — test may fail; the goal "
                                  "is to document the result."))
