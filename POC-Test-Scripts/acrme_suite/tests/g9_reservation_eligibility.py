"""Group 9 — v2.4 reservation-eligibility & subscription classification.

Covers the Baseline **v2.4** reservation-model requirements that gate whether a
VM may be brought under Capacity-Reservation management at all:

* **CAP-020 / HC-11** — Availability-Set VMs are ineligible for (zonal) capacity
  reservations; they are excluded from the ``allocated``/``associated`` counts
  that drive reservation targets (CAP-003) and are surfaced as a non-eligible
  exception carrying the CAP-021 remediation action.
* **CAP-021** — Deallocate-or-migrate-to-AZ onboarding precondition: a VM must
  occupy a reservation-eligible placement — an availability zone (preferred), or
  regional placement only where the SKU has no zonal support — before it can be
  managed. The engine records the required remediation and never auto-migrates
  a running workload.
* **PLC-010a** (positive) — a valid two-region co-located config (CVAL/DR share
  the non-Prod region) is accepted, not treated as an error.
* **CAP-001a** — VMs in a shared **core** subscription are classified
  **production** for reservation/buffer/seed-matrix purposes regardless of any
  individual workload label.

Design: the deterministic classification rules are implemented as pure,
Azure-free functions so the "logic" test cases PASS offline (mirroring the
suite's hypothesis-validation style). The **live** onboarding-rejection case
(actually attempting to associate an Availability-Set VM with a reservation in
Azure) is BLOCKED until the engine / provider subscription is available,
consistent with the G5/G6 engine-gating convention.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..az_client import AzClient
from ..config import Config, ConfigError
from ..preflight import Preflight
from ..runner_core import Registry, TestCase, TestResult

GROUP = "G9"

# Requirement identifiers surfaced in evidence / reporter output.
REQ_CAP_020 = "CAP-020"
REQ_CAP_021 = "CAP-021"
REQ_HC_11 = "HC-11"
REQ_PLC_010A = "PLC-010a"
REQ_PLC_010B = "PLC-010b"
REQ_DR_020 = "DR-020"
REQ_CAP_001A = "CAP-001a"


# ---------------------------------------------------------------------------
# Pure, Azure-free rule implementation (v2.4)
# ---------------------------------------------------------------------------
# A VM is modelled as a plain mapping with the placement facts the eligibility
# rules depend on:
#   placement            : "availability_set" | "zone" | "regional"
#   zone                 : "1" | "2" | "3" | None
#   sku_supports_zonal   : bool  (does the SKU offer zonal capacity reservations?)
#   subscription_class   : "core" | "workload"
#   workload_label       : "production" | "nonproduction" | ... (advisory only)

def is_reservation_eligible(vm: Dict[str, Any]) -> Tuple[bool, str]:
    """Return ``(eligible, reason)`` per CAP-020 / HC-11 / CAP-021.

    Eligibility requires **zonal** placement, or **regional** placement only
    where the SKU has no zonal-reservation support. Availability-Set VMs are
    always ineligible (HC-11 / CAP-020).
    """
    placement = (vm.get("placement") or "").lower()

    if placement == "availability_set":
        return False, (
            "AVAILABILITY_SET_INELIGIBLE (HC-11 / CAP-020): Availability Sets and "
            "Capacity Reservations are mutually exclusive."
        )
    if placement == "zone":
        if str(vm.get("zone") or "") in {"1", "2", "3"}:
            return True, "Zonal placement — reservation-eligible (preferred, CAP-021)."
        return False, "Zone placement declared but no valid availability zone set."
    if placement == "regional":
        if vm.get("sku_supports_zonal", True):
            # Zonal-capable SKU sitting in a regional (non-zonal) placement:
            # AZ is preferred (CAP-021) — redeploy required.
            return False, (
                "Regional placement of a zonal-capable SKU — AZ placement is "
                "preferred (CAP-021); redeploy into an availability zone."
            )
        return True, (
            "Regional placement permitted — SKU has no zonal-reservation support "
            "(CAP-020 / CAP-022 matrix)."
        )
    return False, f"Unknown placement '{placement}'."


def required_remediation(vm: Dict[str, Any]) -> Optional[str]:
    """Return the CAP-021 remediation action for an ineligible VM, else ``None``."""
    eligible, _ = is_reservation_eligible(vm)
    if eligible:
        return None
    placement = (vm.get("placement") or "").lower()
    if placement == "availability_set":
        return (
            "Deallocate and redeploy the VM into an availability zone (or migrate "
            "per the approved runbook) before onboarding — CAP-021 precondition; "
            "the engine records the action and does NOT auto-migrate the workload."
        )
    if placement == "regional" and vm.get("sku_supports_zonal", True):
        return (
            "Redeploy the VM into an availability zone (AZ preferred) — CAP-021; "
            "regional placement is only permitted for SKUs without zonal support."
        )
    return "Move the VM to a reservation-eligible placement before onboarding (CAP-021)."


def counts_toward_reservation_target(vm: Dict[str, Any]) -> bool:
    """CAP-020(a): Availability-Set VMs are excluded from allocated/associated counts."""
    return (vm.get("placement") or "").lower() != "availability_set"


def is_manageable(vm: Dict[str, Any]) -> bool:
    """CAP-021: a reservation is manageable only once the VM is in an eligible placement."""
    eligible, _ = is_reservation_eligible(vm)
    return eligible


def classify_for_buffer(vm: Dict[str, Any]) -> str:
    """CAP-001a: core-subscription VMs are production regardless of workload label."""
    if (vm.get("subscription_class") or "").lower() == "core":
        return "production"
    return (vm.get("workload_label") or "nonproduction").lower()


# ---------------------------------------------------------------------------
# Test fixtures (synthetic estate — no Azure calls)
# ---------------------------------------------------------------------------
def _sample_estate() -> List[Dict[str, Any]]:
    return [
        {"name": "vm-avset-01", "placement": "availability_set", "zone": None,
         "sku_supports_zonal": True, "subscription_class": "workload",
         "workload_label": "production"},
        {"name": "vm-zonal-01", "placement": "zone", "zone": "2",
         "sku_supports_zonal": True, "subscription_class": "workload",
         "workload_label": "production"},
        {"name": "vm-regional-nozonal", "placement": "regional", "zone": None,
         "sku_supports_zonal": False, "subscription_class": "workload",
         "workload_label": "nonproduction"},
        {"name": "vm-regional-zonalsku", "placement": "regional", "zone": None,
         "sku_supports_zonal": True, "subscription_class": "workload",
         "workload_label": "production"},
        {"name": "vm-core-nonprodlabel", "placement": "zone", "zone": "1",
         "sku_supports_zonal": True, "subscription_class": "core",
         "workload_label": "nonproduction"},
    ]


# ---------------------------------------------------------------------------
# Test cases — logic (offline PASS)
# ---------------------------------------------------------------------------
def cap_020_logic(config: Config, az: AzClient) -> TestResult:  # noqa: ARG001
    """CAP-020 / HC-11: Availability-Set VMs are ineligible and excluded from counts."""
    evidence: Dict[str, Any] = {"requirement": [REQ_CAP_020, REQ_HC_11]}
    estate = _sample_estate()
    findings = []
    ok = True

    avset = next(v for v in estate if v["placement"] == "availability_set")
    elig, reason = is_reservation_eligible(avset)
    findings.append({"vm": avset["name"], "eligible": elig, "reason": reason,
                     "counts_toward_target": counts_toward_reservation_target(avset)})
    if elig or counts_toward_reservation_target(avset) or "HC-11" not in reason:
        ok = False

    zonal = next(v for v in estate if v["name"] == "vm-zonal-01")
    z_elig, z_reason = is_reservation_eligible(zonal)
    findings.append({"vm": zonal["name"], "eligible": z_elig, "reason": z_reason,
                     "counts_toward_target": counts_toward_reservation_target(zonal)})
    if not z_elig or not counts_toward_reservation_target(zonal):
        ok = False

    evidence["findings"] = findings
    if ok:
        return TestResult(
            poc_id="POC-CAP-020", status="pass",
            actual_result="Availability-Set VM ineligible (HC-11/CAP-020) and excluded "
                          "from reservation-target counts; zonal VM eligible and counted.",
            evidence=evidence,
        )
    return TestResult(
        poc_id="POC-CAP-020", status="fail",
        actual_result="Eligibility classification did not match CAP-020/HC-11 expectations.",
        evidence=evidence,
    )


def cap_021_logic(config: Config, az: AzClient) -> TestResult:  # noqa: ARG001
    """CAP-021: onboarding blocked until VM is redeployed to an eligible placement."""
    evidence: Dict[str, Any] = {"requirement": [REQ_CAP_021]}
    avset = {"name": "vm-avset-onboard", "placement": "availability_set", "zone": None,
             "sku_supports_zonal": True, "subscription_class": "workload"}

    before_manageable = is_manageable(avset)
    remediation = required_remediation(avset)

    # Simulate the operator performing the remediation (redeploy into AZ 3).
    remediated = dict(avset, placement="zone", zone="3")
    after_manageable = is_manageable(remediated)

    evidence.update({
        "before": {"manageable": before_manageable, "remediation": remediation},
        "after_redeploy_to_az": {"manageable": after_manageable},
        "auto_migrate": False,
    })
    ok = (not before_manageable) and bool(remediation) and after_manageable
    if ok:
        return TestResult(
            poc_id="POC-CAP-021", status="pass",
            actual_result="VM not manageable while in an Availability Set; remediation "
                          "recorded (deallocate/redeploy to AZ, no auto-migration); "
                          "manageable only after redeployment to a zone.",
            evidence=evidence,
        )
    return TestResult(
        poc_id="POC-CAP-021", status="fail",
        actual_result="CAP-021 onboarding-precondition behaviour not as expected.",
        evidence=evidence,
    )


def _build_two_region_config() -> Config:
    """Construct a valid two-region co-located Config in memory (no Azure)."""
    raw = {
        "provider": {"subscription_id": "00000000-0000-0000-0000-000000000001",
                     "resource_group": "acrme-poc-rg",
                     "tenant_id": "00000000-0000-0000-0000-0000000000aa"},
        "consumer": {"subscription_id": "00000000-0000-0000-0000-000000000002",
                     "resource_group": "acrme-poc-rg-consumer"},
        "vm": {"sku": "Standard_D4s_v3", "sku_family": "standardDSv3Family"},
        "crg": {"name": "crg", "reservation_name": "res",
                "dr_crg_name": "dr-crg", "dr_reservation_name": "dr-res"},
        "regions": {"distribution_model": "two-region",
                    "primary": "switzerlandnorth",
                    "dr": "swedencentral", "nonprod": "swedencentral"},
    }
    cfg = Config(raw=raw, path="<memory>")
    cfg._populate(raw)
    cfg.validate()
    return cfg


def plc_010a_positive(config: Config, az: AzClient) -> TestResult:  # noqa: ARG001
    """PLC-010a (positive): a two-region co-located config validates and pre-flight passes."""
    evidence: Dict[str, Any] = {"requirement": [REQ_PLC_010A]}
    try:
        cfg = _build_two_region_config()
    except ConfigError as exc:
        evidence["error"] = str(exc)
        return TestResult(
            poc_id="POC-PLC-010a", status="fail",
            actual_result=f"Valid two-region co-located config was rejected: {exc}",
            evidence=evidence,
        )
    pf = Preflight(cfg, az=None)  # type: ignore[arg-type]
    r9, r10 = pf.pf09_primary_ne_dr(), pf.pf10_nonprod_distinct()
    evidence.update({
        "distribution_model": cfg.distribution_model,
        "cval_region": cfg.nonprod_region, "dr_region": cfg.dr_region,
        "cval_equals_dr": cfg.nonprod_region == cfg.dr_region,
        "PF-09": {"status": r9.status, "detail": r9.detail},
        "PF-10": {"status": r10.status, "detail": r10.detail},
    })
    if cfg.nonprod_region == cfg.dr_region and r9.status == "pass" and r10.status == "pass":
        return TestResult(
            poc_id="POC-PLC-010a", status="pass",
            actual_result="Two-region config accepted: CVAL and DR co-locate in the "
                          "non-Prod region (cval_region == dr_region) and pre-flight "
                          "PF-09/PF-10 pass — co-location is the required outcome.",
            evidence=evidence,
        )
    return TestResult(
        poc_id="POC-PLC-010a", status="fail",
        actual_result="Two-region co-location not confirmed as a valid, passing outcome.",
        evidence=evidence,
    )


def _build_cross_geo_config() -> Config:
    """Construct a valid cross-geo DR Config in memory (no Azure) — Middle East.

    [Amended v2.4] Prod and CVAL/NonProd co-locate in a weighted-selected
    Middle East region; DR is placed cross-geo in a weighted-selected Europe
    region (DR-020, PLC-010b).
    """
    raw = {
        "provider": {"subscription_id": "00000000-0000-0000-0000-000000000001",
                     "resource_group": "acrme-poc-rg",
                     "tenant_id": "00000000-0000-0000-0000-0000000000aa"},
        "consumer": {"subscription_id": "00000000-0000-0000-0000-000000000002",
                     "resource_group": "acrme-poc-rg-consumer"},
        "vm": {"sku": "Standard_D4s_v3", "sku_family": "standardDSv3Family"},
        "crg": {"name": "crg", "reservation_name": "res",
                "dr_crg_name": "dr-crg", "dr_reservation_name": "dr-res"},
        "regions": {"distribution_model": "cross-geo",
                    "primary": "uaenorth",
                    "nonprod": "uaenorth", "dr": "switzerlandnorth"},
    }
    cfg = Config(raw=raw, path="<memory>")
    cfg._populate(raw)
    cfg.validate()
    return cfg


def plc_010b_positive(config: Config, az: AzClient) -> TestResult:  # noqa: ARG001
    """PLC-010b / DR-020 (positive): a cross-geo DR config (Middle East Prod+CVAL
    co-located in-geo, DR cross-geo in Europe) validates and pre-flight passes."""
    evidence: Dict[str, Any] = {"requirement": [REQ_PLC_010B, REQ_DR_020]}
    try:
        cfg = _build_cross_geo_config()
    except ConfigError as exc:
        evidence["error"] = str(exc)
        return TestResult(
            poc_id="POC-PLC-010b", status="fail",
            actual_result=f"Valid cross-geo DR config was rejected: {exc}",
            evidence=evidence,
        )
    pf = Preflight(cfg, az=None)  # type: ignore[arg-type]
    r9, r10 = pf.pf09_primary_ne_dr(), pf.pf10_nonprod_distinct()
    evidence.update({
        "distribution_model": cfg.distribution_model,
        "primary_region": cfg.primary_region,
        "cval_region": cfg.nonprod_region, "dr_region": cfg.dr_region,
        "prod_cval_colocated": cfg.primary_region == cfg.nonprod_region,
        "dr_cross_geo": cfg.dr_region != cfg.primary_region,
        "PF-09": {"status": r9.status, "detail": r9.detail},
        "PF-10": {"status": r10.status, "detail": r10.detail},
    })
    if (
        cfg.primary_region == cfg.nonprod_region
        and cfg.dr_region not in ("", cfg.primary_region)
        and r9.status == "pass" and r10.status == "pass"
    ):
        return TestResult(
            poc_id="POC-PLC-010b", status="pass",
            actual_result="Cross-geo config accepted: Prod and CVAL co-locate in the "
                          "in-geo region (primary == nonprod) while DR is placed "
                          "cross-geo in a different geography (Middle East -> Europe); "
                          "pre-flight PF-09/PF-10 pass (DR-020, PLC-010b).",
            evidence=evidence,
        )
    return TestResult(
        poc_id="POC-PLC-010b", status="fail",
        actual_result="Cross-geo DR placement not confirmed as a valid, passing outcome.",
        evidence=evidence,
    )


def cap_001a_logic(config: Config, az: AzClient) -> TestResult:  # noqa: ARG001
    """CAP-001a: core-subscription VMs classified production regardless of label."""
    evidence: Dict[str, Any] = {"requirement": [REQ_CAP_001A]}
    core_vm = {"name": "vm-core", "subscription_class": "core",
               "workload_label": "nonproduction"}
    workload_vm = {"name": "vm-wl", "subscription_class": "workload",
                   "workload_label": "nonproduction"}
    core_class = classify_for_buffer(core_vm)
    wl_class = classify_for_buffer(workload_vm)
    evidence.update({
        "core_vm": {"label": core_vm["workload_label"], "classified": core_class},
        "workload_vm": {"label": workload_vm["workload_label"], "classified": wl_class},
    })
    if core_class == "production" and wl_class == "nonproduction":
        return TestResult(
            poc_id="POC-CAP-001a", status="pass",
            actual_result="Core-subscription VM classified PRODUCTION despite a "
                          "non-production label; workload-subscription VM keeps its label.",
            evidence=evidence,
        )
    return TestResult(
        poc_id="POC-CAP-001a", status="fail",
        actual_result=f"Classification wrong (core={core_class}, workload={wl_class}).",
        evidence=evidence,
    )


# ---------------------------------------------------------------------------
# Test case — live (engine / Azure required → BLOCKED until available)
# ---------------------------------------------------------------------------
def cap_020_live(config: Config, az: AzClient) -> TestResult:  # noqa: ARG001
    """CAP-020 (live): attempting to associate an Availability-Set VM with a
    reservation must be rejected by Azure — requires a provisioned AV-Set VM."""
    return TestResult(
        poc_id="POC-CAP-020-LIVE", status="blocked",
        actual_result="Engine/live Azure required — provision an Availability-Set VM "
                      "and confirm Azure rejects its association with a Capacity "
                      "Reservation (HC-11 / CAP-020). Blocked until deployment.",
        evidence={"engine_required": True, "requirement": [REQ_CAP_020, REQ_HC_11]},
    )


def register(registry: Registry) -> None:
    """Register all Group 9 test cases."""
    registry.add(TestCase("POC-CAP-020", GROUP,
                          "CAP-020/HC-11: Availability-Set VMs ineligible & uncounted",
                          ["phase1"], [], cap_020_logic))
    registry.add(TestCase("POC-CAP-021", GROUP,
                          "CAP-021: deallocate/redeploy-to-AZ onboarding precondition",
                          ["phase1"], [], cap_021_logic))
    registry.add(TestCase("POC-PLC-010a", GROUP,
                          "PLC-010a: two-region CVAL/DR co-location valid (positive)",
                          ["phase1"], [], plc_010a_positive))
    registry.add(TestCase("POC-PLC-010b", GROUP,
                          "PLC-010b/DR-020: cross-geo DR (ME Prod+CVAL in-geo, DR in Europe) valid (positive)",
                          ["phase1"], [], plc_010b_positive))
    registry.add(TestCase("POC-CAP-001a", GROUP,
                          "CAP-001a: core subscription classified all-production",
                          ["phase1"], [], cap_001a_logic))
    registry.add(TestCase("POC-CAP-020-LIVE", GROUP,
                          "CAP-020 (live): Azure rejects AV-Set VM reservation association",
                          ["phase2"], [], cap_020_live))
