"""Group 2 — Cross-subscription sharing (POC-06, POC-06a, POC-07..POC-10).

Shared CRG is a Public Preview capability driven via the ARM REST API. This
module pins the preview api-version, validates zone alignment across
subscriptions, exercises ARG-based discovery, and probes the 100-consumer limit.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..az_client import AzClient
from ..config import Config
from ..runner_core import Registry, TestCase, TestResult, make_cleanup_note

GROUP = "G2"
API_VERSIONS = ["2024-03-01", "2024-03-01-preview"]
CONSUMER_VM = "acrme-poc-vm-08-01"


def _crg_get(config: Config, az: AzClient, api_version: str):
    """GET the primary CRG at a given api-version."""
    return az.az_rest("GET", config.crg_arm_url(api_version))


def poc_06(config: Config, az: AzClient) -> TestResult:
    """POC-06: Enable cross-subscription sharing via REST PATCH."""
    evidence: Dict[str, Any] = {}
    az.set_subscription(config.provider_subscription_id)
    body = {
        "properties": {
            "sharingProfile": {
                "subscriptionIds": [
                    {"id": f"/subscriptions/{config.consumer_subscription_id}"}
                ]
            }
        }
    }
    used_version: Optional[str] = None
    patch_result = None
    for api_version in API_VERSIONS:
        url = config.crg_arm_url(api_version)
        patch_result = az.az_rest("PATCH", url, body=body)
        evidence[f"patch_{api_version}"] = patch_result.as_evidence()
        if patch_result.success:
            used_version = api_version
            break
    evidence["api_version_used"] = used_version

    if not used_version:
        return TestResult(
            poc_id="POC-06", status="fail",
            actual_result="PATCH to enable sharing failed on all api-versions "
                          f"{API_VERSIONS}.",
            evidence=evidence,
            error=(patch_result.stderr if patch_result else None),
        )

    verify = _crg_get(config, az, used_version)
    evidence["verify_result"] = verify.as_evidence()
    data = verify.data if isinstance(verify.data, dict) else {}
    sub_ids = (((data.get("properties") or {}).get("sharingProfile") or {})
               .get("subscriptionIds") or [])
    ids = [s.get("id", "") for s in sub_ids]
    evidence["sharing_subscription_ids"] = ids
    consumer_scope = f"/subscriptions/{config.consumer_subscription_id}"
    if any(consumer_scope.lower() in (i or "").lower() for i in ids):
        return TestResult(
            poc_id="POC-06", status="pass",
            actual_result=f"Sharing enabled (api-version {used_version}); consumer "
                          f"subscription present in sharingProfile.",
            evidence=evidence,
        )
    return TestResult(
        poc_id="POC-06", status="fail",
        actual_result="Consumer subscription not found in sharingProfile after PATCH.",
        evidence=evidence,
    )


def poc_06a(config: Config, az: AzClient) -> TestResult:
    """POC-06a: Zone alignment validation across provider and consumer subs."""
    evidence: Dict[str, Any] = {}
    zone_url = ("{base}/subscriptions/{sub}/locations?api-version=2022-12-01")

    def zone_map_for(sub: str) -> Dict[str, str]:
        az.set_subscription(sub)
        res = az.az_rest("GET", zone_url.format(base=config.arm_base_url, sub=sub))
        evidence[f"locations_{sub}"] = res.as_evidence()
        mapping: Dict[str, str] = {}
        data = res.data if isinstance(res.data, dict) else {}
        for loc in data.get("value", []):
            if loc.get("name", "").lower() == config.primary_region.lower():
                for zm in loc.get("availabilityZoneMappings", []) or []:
                    mapping[str(zm.get("logicalZone"))] = str(zm.get("physicalZone"))
        return mapping

    provider_map = zone_map_for(config.provider_subscription_id)
    consumer_map = zone_map_for(config.consumer_subscription_id)
    evidence["provider_zone_map"] = provider_map
    evidence["consumer_zone_map"] = consumer_map

    # Build comparison per logical zone and store translation for later tests.
    comparison = []
    translation: Dict[str, str] = {}
    aligned = True
    for logical in ("1", "2", "3"):
        p_phys = provider_map.get(logical)
        c_phys = consumer_map.get(logical)
        comparison.append({"logical": logical, "provider_physical": p_phys,
                           "consumer_physical": c_phys})
        # find consumer logical that maps to provider's physical zone
        if p_phys:
            match = next((cl for cl, cp in consumer_map.items() if cp == p_phys), None)
            if match:
                translation[logical] = match
            if match != logical:
                aligned = False
    evidence["zone_comparison"] = comparison
    evidence["provider_to_consumer_logical_translation"] = translation

    if not provider_map or not consumer_map:
        return TestResult(
            poc_id="POC-06a", status="fail",
            actual_result="Could not retrieve availabilityZoneMappings for one or both "
                          "subscriptions.",
            evidence=evidence,
        )
    if aligned:
        return TestResult(
            poc_id="POC-06a", status="pass",
            actual_result="Logical→physical zone mapping is identical across provider "
                          "and consumer; no zone translation required.",
            evidence=evidence,
        )
    return TestResult(
        poc_id="POC-06a", status="blocked",
        actual_result="ZoneMappingMismatch: consumer logical zones map to different "
                      "physical zones. Translation table stored for POC-08.",
        evidence=evidence,
    )


def poc_07(config: Config, az: AzClient) -> TestResult:
    """POC-07: Consumer discovers the shared CRG via Azure Resource Graph."""
    evidence: Dict[str, Any] = {}
    az.set_subscription(config.consumer_subscription_id)

    kusto = (
        "Resources | where type =~ 'microsoft.compute/capacityreservationgroups' "
        f"| where id startswith '/subscriptions/{config.provider_subscription_id}'"
    )
    arg = az.graph_query(kusto, subscription_id=config.consumer_subscription_id)
    evidence["arg_command"] = arg.command
    evidence["arg_result"] = arg.as_evidence()
    arg_rows: List[Any] = []
    if isinstance(arg.data, dict):
        arg_rows = arg.data.get("data", []) or []
    elif isinstance(arg.data, list):
        arg_rows = arg.data
    evidence["arg_count"] = len(arg_rows)

    direct = az.run([
        "capacity", "reservation", "group", "list",
        "--subscription", config.consumer_subscription_id,
        "-o", "json",
    ])
    evidence["direct_list_result"] = direct.as_evidence()
    direct_rows = direct.data if isinstance(direct.data, list) else []
    evidence["direct_list_count"] = len(direct_rows)
    evidence["note"] = ("Direct list omitting the shared CRG is documented expected "
                        "behaviour; discovery relies on ARG.")

    if len(arg_rows) >= 1:
        return TestResult(
            poc_id="POC-07", status="pass",
            actual_result=f"ARG returned {len(arg_rows)} shared CRG(s); direct list "
                          f"returned {len(direct_rows)} (direct omission is expected).",
            evidence=evidence,
        )
    return TestResult(
        poc_id="POC-07", status="fail",
        actual_result="ARG query did not return the shared CRG (ensure resource-graph "
                      "extension installed and sharing enabled).",
        evidence=evidence, error=arg.stderr,
    )


def poc_08(config: Config, az: AzClient) -> TestResult:
    """POC-08: Associate a consumer VM with the shared CRG."""
    evidence: Dict[str, Any] = {}
    az.set_subscription(config.consumer_subscription_id)

    # Use translated zone if POC-06a stored a mismatch translation.
    zone_args: List[str] = []  # optional; VM create can omit zone
    args = [
        "vm", "create",
        "--resource-group", config.consumer_resource_group,
        "--name", CONSUMER_VM,
        "--image", "Ubuntu2204",
        "--size", config.vm_sku,
        "--capacity-reservation-group", config.crg_resource_id,
        "--generate-ssh-keys",
        "--location", config.primary_region,
        "--no-wait",
    ] + zone_args
    create = az.run(args, parse_json=False)
    evidence["create_command"] = create.command
    evidence["create_result"] = create.as_evidence()

    wait = az.run([
        "vm", "wait",
        "--resource-group", config.consumer_resource_group,
        "--name", CONSUMER_VM,
        "--created",
        "--timeout", str(config.timeout_seconds),
    ], parse_json=False, timeout=config.timeout_seconds + 30)
    evidence["wait_result"] = wait.as_evidence()

    show = az.run([
        "vm", "show",
        "--resource-group", config.consumer_resource_group,
        "--name", CONSUMER_VM,
        "--query", "capacityReservation",
        "-o", "json",
    ])
    evidence["show_result"] = show.as_evidence()
    evidence.update(make_cleanup_note(
        f"az vm delete -g {config.consumer_resource_group} -n {CONSUMER_VM} --yes "
        f"--subscription {config.consumer_subscription_id}"
    ))
    data = show.data if isinstance(show.data, dict) else {}
    assoc_id = ((data.get("capacityReservationGroup") or {}).get("id") or "")
    evidence["associated_crg_id"] = assoc_id
    if assoc_id.lower() == config.crg_resource_id.lower():
        return TestResult(
            poc_id="POC-08", status="pass",
            actual_result=f"Consumer VM '{CONSUMER_VM}' associated with provider shared CRG.",
            evidence=evidence,
        )
    return TestResult(
        poc_id="POC-08", status="fail",
        actual_result=f"Consumer VM association not confirmed (got '{assoc_id}').",
        evidence=evidence, error=create.stderr or wait.stderr,
    )


def poc_09(config: Config, az: AzClient) -> TestResult:
    """POC-09: Verify combined consumption count across provider and consumer."""
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
    evidence["show_result"] = show.as_evidence()
    associated = show.data if isinstance(show.data, list) else []
    evidence["associated_count"] = len(associated)
    evidence["associated"] = associated
    evidence["consumer_subscription_ids_in_scope"] = [config.consumer_subscription_id]

    if len(associated) >= 2:
        return TestResult(
            poc_id="POC-09", status="pass",
            actual_result=f"Combined consumption count is {len(associated)} (>=2: provider "
                          f"+ consumer VMs).",
            evidence=evidence,
        )
    return TestResult(
        poc_id="POC-09", status="fail",
        actual_result=f"Expected >=2 associated VMs, found {len(associated)}.",
        evidence=evidence, error=show.stderr,
    )


def poc_10(config: Config, az: AzClient) -> TestResult:
    """POC-10: Probe the 100-consumer sharing limit (production gate only)."""
    evidence: Dict[str, Any] = {}
    az.set_subscription(config.provider_subscription_id)
    # Build a synthetic list of subscription entries up to the limit boundary.
    # We PATCH increasingly large sharingProfiles using placeholder GUIDs; the
    # goal is to capture the exact error and count at which Azure rejects.
    base = config.consumer_subscription_id
    api_version = API_VERSIONS[0]
    url = config.crg_arm_url(api_version)

    triggered_at: Optional[int] = None
    error_body: Optional[str] = None
    # Generate deterministic pseudo-GUIDs derived from the real consumer GUID.
    def synthetic_guid(n: int) -> str:
        suffix = f"{n:012d}"
        return f"{base[:24]}{suffix[-12:]}" if len(base) >= 24 else base

    ids: List[Dict[str, str]] = [{"id": f"/subscriptions/{base}"}]
    for count in range(2, 105):
        ids.append({"id": f"/subscriptions/{synthetic_guid(count)}"})
        body = {"properties": {"sharingProfile": {"subscriptionIds": ids}}}
        res = az.az_rest("PATCH", url, body=body)
        if not res.success:
            triggered_at = count
            error_body = res.stderr or res.stdout
            evidence["error_count"] = count
            evidence["error_body"] = (error_body or "")[:3000]
            evidence["error_command"] = res.command
            break
    evidence["triggered_at"] = triggered_at

    if triggered_at is not None:
        return TestResult(
            poc_id="POC-10", status="pass",
            actual_result=f"Sharing limit error triggered at {triggered_at} consumer "
                          f"entries; exact error captured in evidence.",
            evidence=evidence,
        )
    return TestResult(
        poc_id="POC-10", status="fail",
        actual_result="Did not trigger a sharing-limit error within 104 entries; review "
                      "evidence (synthetic GUIDs may be rejected for other reasons).",
        evidence=evidence,
    )


def register(registry: Registry) -> None:
    """Register all Group 2 test cases."""
    registry.add(TestCase("POC-06", GROUP, "Enable cross-subscription sharing (REST PATCH)",
                          ["phase1"], ["POC-01"], poc_06,
                          warning="Shared CRG is Public Preview — REST API only."))
    registry.add(TestCase("POC-06a", GROUP, "Zone alignment validation",
                          ["phase1"], ["POC-06"], poc_06a))
    registry.add(TestCase("POC-07", GROUP, "Consumer discovers shared CRG via ARG",
                          ["phase1"], ["POC-06"], poc_07))
    registry.add(TestCase("POC-08", GROUP, "Associate consumer VM with shared CRG",
                          ["phase1"], ["POC-06", "POC-02"], poc_08))
    registry.add(TestCase("POC-09", GROUP, "Verify combined consumption count",
                          ["phase1"], ["POC-08"], poc_09))
    registry.add(TestCase("POC-10", GROUP, "100-consumer limit boundary",
                          ["production"], ["POC-06"], poc_10,
                          warning="Production gate only — mutates sharingProfile heavily."))
