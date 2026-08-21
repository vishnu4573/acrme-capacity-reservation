"""Pre-flight checklist (PF-01 through PF-10) for the ACRME POC suite.

Each check returns a :class:`PreflightResult`. PF-09 and PF-10 are HARD BLOCKING
failures: if either fails the runner must refuse to execute Group 1+ tests.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

from .az_client import AzClient
from .config import Config


@dataclass
class PreflightResult:
    """Result of one pre-flight check."""

    check_id: str
    name: str
    status: str  # pass | fail | warn
    detail: str = ""
    blocking: bool = False
    evidence: Dict[str, Any] = field(default_factory=dict)


def _parse_cli_version(stdout: str) -> str:
    """Extract the azure-cli semantic version from `az --version` output."""
    # Line looks like: "azure-cli                         2.61.0"
    for line in stdout.splitlines():
        m = re.match(r"\s*azure-cli\s+(\d+\.\d+\.\d+)", line)
        if m:
            return m.group(1)
    # Fallback: first x.y.z anywhere.
    m = re.search(r"(\d+\.\d+\.\d+)", stdout)
    return m.group(1) if m else ""


def _version_ge(actual: str, minimum: str) -> bool:
    """Return True if semantic *actual* >= *minimum*."""
    def parts(v: str) -> List[int]:
        return [int(x) for x in v.split(".")[:3]] if v else [0, 0, 0]
    return parts(actual) >= parts(minimum)


class Preflight:
    """Runs PF-01..PF-10 and aggregates results."""

    MIN_CLI_VERSION = "2.50.0"

    def __init__(self, config: Config, az: AzClient) -> None:
        self.config = config
        self.az = az

    # ------------------------------------------------------------------
    def run_all(self) -> List[PreflightResult]:
        """Run all pre-flight checks in order and return the list of results."""
        self.az.set_current_test("PREFLIGHT")
        checks = [
            self.pf01_cli_version,
            self.pf02_account_show,
            self.pf03_set_provider_sub,
            self.pf04_providers_registered,
            self.pf05_provider_quota,
            self.pf06_consumer_quota,
            self.pf07_rbac_assignments,
            self.pf08_no_conflicting_crg,
            self.pf09_primary_ne_dr,
            self.pf10_nonprod_distinct,
        ]
        results = []
        for check in checks:
            try:
                results.append(check())
            except Exception as exc:  # noqa: BLE001
                results.append(
                    PreflightResult(
                        check_id=check.__name__.split("_")[0].upper(),
                        name=check.__doc__ or check.__name__,
                        status="fail",
                        detail=f"Check raised: {exc}",
                    )
                )
        return results

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------
    def pf01_cli_version(self) -> PreflightResult:
        """PF-01: Azure CLI installed and version >= 2.50.0."""
        res = self.az.run(["--version"], parse_json=False)
        version = _parse_cli_version(res.stdout)
        if not version:
            return PreflightResult(
                "PF-01", "Azure CLI version", "fail",
                "Could not determine az CLI version (is az installed?).",
                evidence=res.as_evidence(),
            )
        ok = _version_ge(version, self.MIN_CLI_VERSION)
        return PreflightResult(
            "PF-01", "Azure CLI version",
            "pass" if ok else "fail",
            f"az {version} (minimum {self.MIN_CLI_VERSION})",
            evidence={"version": version, "minimum": self.MIN_CLI_VERSION},
        )

    def pf02_account_show(self) -> PreflightResult:
        """PF-02: An identity is signed in (`az account show`)."""
        res = self.az.run(["account", "show"], parse_json=True)
        if res.success and isinstance(res.data, dict):
            user = (res.data.get("user") or {}).get("name", "unknown")
            return PreflightResult(
                "PF-02", "Signed-in identity", "pass",
                f"Signed in as {user}",
                evidence={"user": user, "subscription": res.data.get("id")},
            )
        return PreflightResult(
            "PF-02", "Signed-in identity", "fail",
            "az account show failed — run `az login`.",
            evidence=res.as_evidence(),
        )

    def pf03_set_provider_sub(self) -> PreflightResult:
        """PF-03: Provider subscription can be set and is active."""
        self.az.set_subscription(self.config.provider_subscription_id)
        res = self.az.run(["account", "show"], parse_json=True)
        active = (res.data or {}).get("id") if isinstance(res.data, dict) else None
        ok = active == self.config.provider_subscription_id
        return PreflightResult(
            "PF-03", "Provider subscription active",
            "pass" if ok else "fail",
            f"Active subscription: {active}",
            evidence={"expected": self.config.provider_subscription_id, "active": active},
        )

    def pf04_providers_registered(self) -> PreflightResult:
        """PF-04: Microsoft.Compute and Microsoft.Quota are registered."""
        needed = ["Microsoft.Compute", "Microsoft.Quota"]
        states = {}
        for ns in needed:
            res = self.az.run(
                ["provider", "show", "--namespace", ns,
                 "--query", "registrationState", "-o", "tsv"],
                parse_json=False,
            )
            states[ns] = (res.stdout or "").strip() or "Unknown"
        all_registered = all(v == "Registered" for v in states.values())
        status = "pass" if all_registered else "warn"
        detail = ", ".join(f"{k}={v}" for k, v in states.items())
        return PreflightResult(
            "PF-04", "Resource providers registered", status, detail,
            evidence=states,
        )

    def pf05_provider_quota(self) -> PreflightResult:
        """PF-05: Provider subscription quota for the SKU family."""
        return self._quota_check(
            "PF-05", "Provider quota",
            self.config.provider_subscription_id, self.config.primary_region,
        )

    def pf06_consumer_quota(self) -> PreflightResult:
        """PF-06: Consumer subscription quota for the SKU family."""
        return self._quota_check(
            "PF-06", "Consumer quota",
            self.config.consumer_subscription_id, self.config.primary_region,
        )

    def _quota_check(self, cid: str, name: str, sub: str, region: str) -> PreflightResult:
        self.az.set_subscription(sub)
        res = self.az.run(
            ["vm", "list-usage", "--location", region, "-o", "json"],
            parse_json=True,
        )
        family = self.config.vm_sku_family.lower()
        if res.success and isinstance(res.data, list):
            match = None
            for item in res.data:
                local = (item.get("name") or {}).get("value", "").lower()
                if local == family:
                    match = item
                    break
            if match:
                current = match.get("currentValue")
                limit = match.get("limit")
                headroom = (limit or 0) - (current or 0)
                status = "pass" if headroom >= self.config.quantity else "warn"
                return PreflightResult(
                    cid, name, status,
                    f"{self.config.vm_sku_family}: {current}/{limit} used "
                    f"(headroom {headroom})",
                    evidence={"current": current, "limit": limit, "headroom": headroom},
                )
            return PreflightResult(
                cid, name, "warn",
                f"SKU family '{self.config.vm_sku_family}' not found in usage list "
                f"for {region}; verify family name.",
                evidence={"region": region},
            )
        return PreflightResult(
            cid, name, "warn",
            "Could not read usage (permissions or region?).",
            evidence=res.as_evidence(),
        )

    def pf07_rbac_assignments(self) -> PreflightResult:
        """PF-07: RBAC assignments visible on provider subscription scope."""
        self.az.set_subscription(self.config.provider_subscription_id)
        res = self.az.run(
            ["role", "assignment", "list",
             "--scope", self.config.provider_sub_scope,
             "-o", "json"],
            parse_json=True,
        )
        if res.success and isinstance(res.data, list):
            return PreflightResult(
                "PF-07", "RBAC assignments", "pass",
                f"{len(res.data)} role assignment(s) at provider sub scope",
                evidence={"count": len(res.data)},
            )
        return PreflightResult(
            "PF-07", "RBAC assignments", "warn",
            "Could not list role assignments (Reader on scope required).",
            evidence=res.as_evidence(),
        )

    def pf08_no_conflicting_crg(self) -> PreflightResult:
        """PF-08: No conflicting CRG names already exist in provider RG."""
        self.az.set_subscription(self.config.provider_subscription_id)
        res = self.az.run(
            ["capacity", "reservation", "group", "list",
             "--resource-group", self.config.provider_resource_group,
             "-o", "json"],
            parse_json=True,
        )
        conflicts = []
        if res.success and isinstance(res.data, list):
            names = {c.get("name") for c in res.data}
            for candidate in (self.config.crg_name, self.config.dr_crg_name):
                if candidate in names:
                    conflicts.append(candidate)
        if conflicts:
            return PreflightResult(
                "PF-08", "No conflicting CRGs", "warn",
                f"Existing CRG(s) found: {', '.join(conflicts)} — tests are "
                f"idempotent but verify state.",
                evidence={"conflicts": conflicts},
            )
        return PreflightResult(
            "PF-08", "No conflicting CRGs", "pass",
            "No conflicting CRG names in provider resource group.",
        )

    def pf09_primary_ne_dr(self) -> PreflightResult:
        """PF-09 (HARD BLOCKER): primary region != DR region."""
        ok = self.config.primary_region != self.config.dr_region
        return PreflightResult(
            "PF-09", "Primary != DR region",
            "pass" if ok else "fail",
            f"primary={self.config.primary_region}, dr={self.config.dr_region}",
            blocking=True,
        )

    def pf10_nonprod_distinct(self) -> PreflightResult:
        """PF-10 (HARD BLOCKER): nonprod != primary and nonprod != dr."""
        ok = self.config.nonprod_region not in (
            self.config.primary_region, self.config.dr_region
        )
        return PreflightResult(
            "PF-10", "NonProd region distinct",
            "pass" if ok else "fail",
            f"nonprod={self.config.nonprod_region}, "
            f"primary={self.config.primary_region}, dr={self.config.dr_region}",
            blocking=True,
        )


def preflight_blocks_run(results: List[PreflightResult]) -> List[PreflightResult]:
    """Return the list of blocking pre-flight failures (empty if run may proceed)."""
    return [r for r in results if r.blocking and r.status == "fail"]
