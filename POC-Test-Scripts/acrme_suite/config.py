"""Configuration loader and validator for the ACRME POC test suite.

Loads ``config.yaml``, validates every required field, enforces the
GEOGRAPHY-AWARE region-distinctness constraint (three-region vs two-region
distribution model per baseline REG-003 / PLC-010a), and exposes a
process-wide singleton :class:`Config` object with a number of derived
convenience properties (resource IDs, ARM base URLs, etc.).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import yaml

VALID_PHASE_GATES = ("phase1", "phase2", "production")

# Ordered permissiveness — a test tagged phase1 is eligible under phase2 and
# production; a test tagged production only runs under production.
PHASE_GATE_ORDER = {"phase1": 0, "phase2": 1, "production": 2}

RESOURCE_PREFIX = "acrme-poc-"


class ConfigError(ValueError):
    """Raised when the configuration file is missing values or is invalid."""


def _ensure_prefix(name: str) -> str:
    """Ensure a resource name carries the mandatory ``acrme-poc-`` prefix."""
    if not name:
        return name
    return name if name.startswith(RESOURCE_PREFIX) else f"{RESOURCE_PREFIX}{name}"


@dataclass
class Config:
    """Validated configuration for a suite run.

    Instances are normally created via :meth:`load`. The raw mapping is kept in
    :attr:`raw` so it can be snapshotted into the result store.
    """

    raw: Dict[str, Any] = field(default_factory=dict)
    path: Optional[str] = None

    # ----- provider -------------------------------------------------------
    provider_subscription_id: str = ""
    provider_resource_group: str = ""
    tenant_id: str = ""

    # ----- consumer -------------------------------------------------------
    consumer_subscription_id: str = ""
    consumer_resource_group: str = ""

    # ----- regions --------------------------------------------------------
    primary_region: str = ""
    dr_region: str = ""
    nonprod_region: str = ""
    # Distribution model per the v2.4 baseline region strategy (REG-003):
    #   "three-region" — Prod, CVAL/NonProd and DR each occupy a DISTINCT region
    #                    (currently the US geography only).
    #   "two-region"   — Prod occupies one region; CVAL/NonProd and DR
    #                    co-locate in the single remaining region (PLC-010a).
    #                    Currently Europe, Australia, Asia Pacific, Middle East.
    # Defaults to "three-region" for backward compatibility with existing configs.
    distribution_model: str = "three-region"
    # Whether DR is offered for this geography. Middle East carries
    # DR_NOT_OFFERED (DR-014, DEC-001) until legal approval, in which case no
    # DR region is assigned at all. Defaults to True.
    dr_offered: bool = True

    # ----- vm -------------------------------------------------------------
    vm_sku: str = ""
    vm_sku_family: str = ""
    vcpus_per_instance: int = 4

    # ----- crg ------------------------------------------------------------
    crg_name: str = ""
    reservation_name: str = ""
    quantity: int = 2
    dr_crg_name: str = ""
    dr_reservation_name: str = ""
    dr_quantity: int = 2
    dr_floor_percentage: int = 40

    # ----- quota group ----------------------------------------------------
    quota_group_name: str = ""

    # ----- aks ------------------------------------------------------------
    aks_resource_group: str = ""
    aks_cluster_name: str = ""
    aks_nodepool_name: str = ""

    # ----- run control ----------------------------------------------------
    phase_gate: str = "phase1"
    dry_run: bool = False
    timeout_seconds: int = 300

    # ==================================================================
    # Construction / validation
    # ==================================================================
    @classmethod
    def load(cls, path: str = "config.yaml") -> "Config":
        """Load and validate the config file at *path*.

        Raises :class:`ConfigError` if the file is missing, unparseable, or has
        any missing/invalid field.
        """
        if not os.path.exists(path):
            raise ConfigError(
                f"Config file not found: {path}. "
                f"Copy config.yaml.template to config.yaml and fill in values."
            )
        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = yaml.safe_load(fh) or {}
        except yaml.YAMLError as exc:  # pragma: no cover - defensive
            raise ConfigError(f"Could not parse {path}: {exc}") from exc

        cfg = cls(raw=raw, path=os.path.abspath(path))
        cfg._populate(raw)
        cfg.validate()
        return cfg

    def _populate(self, raw: Dict[str, Any]) -> None:
        """Copy nested YAML values into flat attributes."""
        provider = raw.get("provider") or {}
        consumer = raw.get("consumer") or {}
        regions = raw.get("regions") or {}
        vm = raw.get("vm") or {}
        crg = raw.get("crg") or {}
        quota_group = raw.get("quota_group") or {}
        aks = raw.get("aks") or {}

        self.provider_subscription_id = str(provider.get("subscription_id", "") or "").strip()
        self.provider_resource_group = str(provider.get("resource_group", "") or "").strip()
        self.tenant_id = str(provider.get("tenant_id", "") or "").strip()

        self.consumer_subscription_id = str(consumer.get("subscription_id", "") or "").strip()
        self.consumer_resource_group = str(consumer.get("resource_group", "") or "").strip()

        self.primary_region = str(regions.get("primary", "") or "").strip()
        self.dr_region = str(regions.get("dr", "") or "").strip()
        self.nonprod_region = str(regions.get("nonprod", "") or "").strip()
        self.distribution_model = (
            str(regions.get("distribution_model", "three-region") or "three-region")
            .strip()
            .lower()
        )
        # Accept common synonyms so operator configs are forgiving.
        if self.distribution_model in ("3", "3-region", "three", "us"):
            self.distribution_model = "three-region"
        elif self.distribution_model in ("2", "2-region", "two"):
            self.distribution_model = "two-region"
        dr_offered_raw = regions.get("dr_offered", True)
        if isinstance(dr_offered_raw, str):
            self.dr_offered = dr_offered_raw.strip().lower() not in (
                "false", "no", "0", "dr_not_offered", "not_offered", "",
            )
        else:
            self.dr_offered = bool(dr_offered_raw)

        self.vm_sku = str(vm.get("sku", "") or "").strip()
        self.vm_sku_family = str(vm.get("sku_family", "") or "").strip()
        self.vcpus_per_instance = int(vm.get("vcpus_per_instance", 4) or 4)

        self.crg_name = _ensure_prefix(str(crg.get("name", "") or "").strip())
        self.reservation_name = _ensure_prefix(str(crg.get("reservation_name", "") or "").strip())
        self.quantity = int(crg.get("quantity", 2) or 2)
        self.dr_crg_name = _ensure_prefix(str(crg.get("dr_crg_name", "") or "").strip())
        self.dr_reservation_name = _ensure_prefix(str(crg.get("dr_reservation_name", "") or "").strip())
        self.dr_quantity = int(crg.get("dr_quantity", 2) or 2)
        self.dr_floor_percentage = int(crg.get("dr_floor_percentage", 40) or 40)

        self.quota_group_name = str(quota_group.get("name", "") or "").strip()

        self.aks_resource_group = str(aks.get("resource_group", "") or "").strip()
        self.aks_cluster_name = str(aks.get("cluster_name", "") or "").strip()
        self.aks_nodepool_name = str(aks.get("nodepool_name", "") or "").strip()

        self.phase_gate = str(raw.get("phase_gate", "phase1") or "phase1").strip().lower()
        self.dry_run = bool(raw.get("dry_run", False))
        self.timeout_seconds = int(raw.get("timeout_seconds", 300) or 300)

    @property
    def is_two_region(self) -> bool:
        """True when the geography runs the two-region distribution model."""
        return self.distribution_model == "two-region"

    @property
    def dr_required(self) -> bool:
        """A DR region is required unless the geography is two-region AND
        DR is not offered (Middle East DR_NOT_OFFERED, DEC-001), in which case
        no DR region is assigned at all."""
        return not (self.is_two_region and not self.dr_offered)

    def validate(self) -> None:
        """Validate all required fields and hard constraints."""
        missing: List[str] = []

        # Guard against an unknown distribution model early.
        if self.distribution_model not in ("three-region", "two-region"):
            raise ConfigError(
                "regions.distribution_model must be 'three-region' or "
                f"'two-region'; got '{self.distribution_model}'."
            )

        required = {
            "provider.subscription_id": self.provider_subscription_id,
            "provider.resource_group": self.provider_resource_group,
            "provider.tenant_id": self.tenant_id,
            "consumer.subscription_id": self.consumer_subscription_id,
            "consumer.resource_group": self.consumer_resource_group,
            "regions.primary": self.primary_region,
            "regions.nonprod": self.nonprod_region,
            "vm.sku": self.vm_sku,
            "vm.sku_family": self.vm_sku_family,
            "crg.name": self.crg_name,
            "crg.reservation_name": self.reservation_name,
            "crg.dr_crg_name": self.dr_crg_name,
            "crg.dr_reservation_name": self.dr_reservation_name,
        }
        # DR region is required except in a two-region geography where DR is
        # not offered (Middle East DR_NOT_OFFERED, DEC-001).
        if self.dr_required:
            required["regions.dr"] = self.dr_region

        for key, value in required.items():
            if not value:
                missing.append(key)
        if missing:
            raise ConfigError(
                "Missing required config fields: " + ", ".join(missing)
            )

        # ------------------------------------------------------------------
        # HARD CONSTRAINT: region distinctness is GEOGRAPHY-AWARE (v2.4).
        # Baseline REG-003 / PLC-010a:
        #   * three-region (US): Prod, CVAL/NonProd and DR each in a DISTINCT
        #     region — all three must differ.
        #   * two-region (EU/AU/APAC/ME): Prod occupies one region; CVAL/NonProd
        #     and DR CO-LOCATE in the single remaining region. Co-location is
        #     the normal, required outcome — NOT an error. DR (when offered)
        #     must therefore equal NonProd, and both must differ from Prod.
        # ------------------------------------------------------------------
        # Prod must always be distinct from the non-Prod region.
        if self.nonprod_region == self.primary_region:
            raise ConfigError(
                f"regions.nonprod ({self.nonprod_region}) must differ from "
                f"regions.primary ({self.primary_region}) — Production and the "
                f"non-Production region cannot be the same."
            )

        if self.is_two_region:
            # Two-region model (PLC-010a): CVAL/NonProd and DR co-locate.
            if not self.dr_offered:
                # Middle East DR_NOT_OFFERED (DEC-001): no DR region assigned.
                # A DR region may be omitted; if supplied it must not introduce
                # a spurious third region — accept blank or == nonprod only.
                if self.dr_region and self.dr_region not in (
                    self.nonprod_region,
                ):
                    raise ConfigError(
                        f"Two-region geography with DR not offered "
                        f"(DR_NOT_OFFERED, DEC-001): regions.dr "
                        f"({self.dr_region}) must be blank or co-located with "
                        f"regions.nonprod ({self.nonprod_region}); no separate "
                        f"DR region is assigned."
                    )
            else:
                # DR must co-locate with the non-Prod (CVAL) region (PLC-010a).
                if self.dr_region != self.nonprod_region:
                    raise ConfigError(
                        f"Two-region geography (PLC-010a): regions.dr "
                        f"({self.dr_region}) must CO-LOCATE with regions.nonprod "
                        f"({self.nonprod_region}) — CVAL and DR share the single "
                        f"non-Production region. Set regions.dr == regions.nonprod, "
                        f"or use distribution_model: three-region for a "
                        f"three-region geography."
                    )
                if self.dr_region == self.primary_region:
                    raise ConfigError(
                        f"regions.dr ({self.dr_region}) must differ from "
                        f"regions.primary ({self.primary_region})."
                    )
        else:
            # Three-region model: Prod, DR and NonProd must all differ.
            regions = {
                "primary": self.primary_region,
                "dr": self.dr_region,
                "nonprod": self.nonprod_region,
            }
            if self.primary_region == self.dr_region:
                raise ConfigError(
                    f"regions.primary ({self.primary_region}) must differ from "
                    f"regions.dr ({self.dr_region}) — in a three-region geography "
                    f"Production and DR cannot share a region."
                )
            if self.nonprod_region == self.dr_region:
                raise ConfigError(
                    f"regions.nonprod ({self.nonprod_region}) must differ from "
                    f"regions.dr ({self.dr_region}) in a three-region geography."
                )
            # Belt-and-braces uniqueness check.
            if len(set(regions.values())) != 3:
                raise ConfigError(
                    "regions.primary, regions.dr and regions.nonprod must be "
                    f"three distinct regions in a three-region geography; got "
                    f"{regions}."
                )

        if self.phase_gate not in VALID_PHASE_GATES:
            raise ConfigError(
                f"phase_gate must be one of {VALID_PHASE_GATES}; got '{self.phase_gate}'."
            )

        if self.timeout_seconds <= 0:
            raise ConfigError("timeout_seconds must be a positive integer.")

    # ==================================================================
    # Derived values
    # ==================================================================
    @property
    def arm_base_url(self) -> str:
        """Base ARM management URL."""
        return "https://management.azure.com"

    @property
    def provider_sub_scope(self) -> str:
        """ARM scope string for the provider subscription."""
        return f"/subscriptions/{self.provider_subscription_id}"

    @property
    def consumer_sub_scope(self) -> str:
        """ARM scope string for the consumer subscription."""
        return f"/subscriptions/{self.consumer_subscription_id}"

    @property
    def crg_resource_id(self) -> str:
        """Full ARM resource ID of the primary CRG."""
        return (
            f"/subscriptions/{self.provider_subscription_id}"
            f"/resourceGroups/{self.provider_resource_group}"
            f"/providers/Microsoft.Compute/capacityReservationGroups/{self.crg_name}"
        )

    @property
    def dr_crg_resource_id(self) -> str:
        """Full ARM resource ID of the DR CRG."""
        return (
            f"/subscriptions/{self.provider_subscription_id}"
            f"/resourceGroups/{self.provider_resource_group}"
            f"/providers/Microsoft.Compute/capacityReservationGroups/{self.dr_crg_name}"
        )

    def crg_arm_url(self, api_version: str = "2024-03-01") -> str:
        """Build the ARM REST URL for the primary CRG at *api_version*."""
        return f"{self.arm_base_url}{self.crg_resource_id}?api-version={api_version}"

    @property
    def quota_group_enabled(self) -> bool:
        """True if a quota group name has been configured."""
        return bool(self.quota_group_name)

    @property
    def aks_enabled(self) -> bool:
        """True if AKS coordinates have been configured."""
        return bool(self.aks_resource_group and self.aks_cluster_name and self.aks_nodepool_name)

    def snapshot(self) -> Dict[str, Any]:
        """Return a redaction-free snapshot of the config for the result store."""
        return {
            "path": self.path,
            "provider_subscription_id": self.provider_subscription_id,
            "provider_resource_group": self.provider_resource_group,
            "tenant_id": self.tenant_id,
            "consumer_subscription_id": self.consumer_subscription_id,
            "consumer_resource_group": self.consumer_resource_group,
            "primary_region": self.primary_region,
            "dr_region": self.dr_region,
            "nonprod_region": self.nonprod_region,
            "distribution_model": self.distribution_model,
            "dr_offered": self.dr_offered,
            "vm_sku": self.vm_sku,
            "vm_sku_family": self.vm_sku_family,
            "vcpus_per_instance": self.vcpus_per_instance,
            "crg_name": self.crg_name,
            "reservation_name": self.reservation_name,
            "quantity": self.quantity,
            "dr_crg_name": self.dr_crg_name,
            "dr_reservation_name": self.dr_reservation_name,
            "dr_quantity": self.dr_quantity,
            "dr_floor_percentage": self.dr_floor_percentage,
            "quota_group_name": self.quota_group_name,
            "aks_resource_group": self.aks_resource_group,
            "aks_cluster_name": self.aks_cluster_name,
            "aks_nodepool_name": self.aks_nodepool_name,
            "phase_gate": self.phase_gate,
            "dry_run": self.dry_run,
            "timeout_seconds": self.timeout_seconds,
        }


# ----------------------------------------------------------------------
# Process-wide singleton access
# ----------------------------------------------------------------------
_ACTIVE_CONFIG: Optional[Config] = None


def set_active_config(cfg: Config) -> None:
    """Register *cfg* as the process-wide active configuration."""
    global _ACTIVE_CONFIG
    _ACTIVE_CONFIG = cfg


def get_active_config() -> Config:
    """Return the active :class:`Config`, or raise if none has been loaded."""
    if _ACTIVE_CONFIG is None:
        raise ConfigError("No active configuration. Call Config.load() first.")
    return _ACTIVE_CONFIG
