"""ACRME Placement Engine — Azure Data Collector.

Collects real-time capacity, quota, and reservation data from Azure
subscriptions and converts them into RegionSnapshot objects consumed
by the placement engine.

Requires:
    pip install azure-identity azure-mgmt-compute azure-mgmt-quota \
               azure-mgmt-reservations azure-mgmt-resource \
               azure-mgmt-resourcegraph

Authentication:
    Uses DefaultAzureCredential — works with:
      • Azure CLI  (az login)
      • Managed Identity
      • Environment variables (AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_CLIENT_SECRET)
      • VS Code / Azure PowerShell

Usage:
    collector = AzureCapacityCollector(
        subscription_ids=["sub-id-1", "sub-id-2"],
        geography="US",
        sku_family="Dadsv5",
    )
    snapshots = collector.collect_region_snapshots()
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from models import (
    DistributionModel,
    RegionClassification,
    RegionSnapshot,
    ZoneCapacity,
    ZoneQuota,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Geography / region catalogue (mirrors environment.yaml)
# ---------------------------------------------------------------------------

GEOGRAPHY_CATALOGUE: dict[str, dict[str, Any]] = {
    "US": {
        "distribution_model": DistributionModel.THREE_REGION,
        "regions": {
            "westus3":        {"name": "West US 3",       "classification": "standard",   "auto_selectable": True},
            "centralus":      {"name": "Central US",      "classification": "standard",   "auto_selectable": True},
            "canadacentral":  {"name": "Canada Central",  "classification": "standard",   "auto_selectable": True},
            "eastus2":        {"name": "East US 2",       "classification": "restricted", "auto_selectable": False},
        },
    },
    "Europe": {
        "distribution_model": DistributionModel.TWO_REGION,
        "regions": {
            "switzerlandnorth": {"name": "Switzerland North", "classification": "standard",   "auto_selectable": True},
            "swedencentral":    {"name": "Sweden Central",    "classification": "standard",   "auto_selectable": True},
            "northeurope":      {"name": "North Europe",      "classification": "restricted", "auto_selectable": False},
            "westeurope":       {"name": "West Europe",       "classification": "restricted", "auto_selectable": False},
        },
    },
    "Australia": {
        "distribution_model": DistributionModel.TWO_REGION,
        "regions": {
            "australiaeast":      {"name": "Australia East",      "classification": "standard", "auto_selectable": True},
            "australiasoutheast": {"name": "Australia Southeast", "classification": "standard", "auto_selectable": True},
        },
    },
    "Middle East": {
        "distribution_model": DistributionModel.CROSS_GEO_DR,
        "regions": {
            "uaenorth":      {"name": "UAE North",      "classification": "standard", "auto_selectable": True},
            "qatarcentral":  {"name": "Qatar Central",  "classification": "standard", "auto_selectable": True},
        },
        "dr_destination_geography": "Europe",
    },
}


# ===================================================================
# Azure SDK helpers (lazy imports to allow mock-only usage)
# ===================================================================

def _get_credential():
    """Return DefaultAzureCredential (lazy import)."""
    from azure.identity import DefaultAzureCredential  # type: ignore
    return DefaultAzureCredential()


def _query_resource_graph(credential, subscription_ids: list[str], query: str) -> list[dict]:
    """Run an Azure Resource Graph KQL query across subscriptions."""
    from azure.mgmt.resourcegraph import ResourceGraphClient  # type: ignore
    from azure.mgmt.resourcegraph.models import (
        QueryRequest,
        QueryRequestOptions,
        ResultFormat,
    )
    client = ResourceGraphClient(credential)
    request = QueryRequest(
        subscriptions=subscription_ids,
        query=query,
        options=QueryRequestOptions(result_format=ResultFormat.object_array),
    )
    response = client.resources(request)
    rows: list[dict] = []
    if response.data:
        rows.extend(response.data)  # type: ignore
    # Handle pagination
    while response.skip_token:
        request.options.skip_token = response.skip_token
        response = client.resources(request)
        if response.data:
            rows.extend(response.data)  # type: ignore
    return rows


def _get_quota_usage(credential, subscription_id: str, location: str, sku_family: str) -> dict:
    """Fetch quota usage for a SKU family in a location."""
    from azure.mgmt.compute import ComputeManagementClient  # type: ignore
    client = ComputeManagementClient(credential, subscription_id)
    usages = list(client.usage.list(location))
    result = {"family_limit": 0, "family_used": 0, "regional_limit": 0, "regional_used": 0}
    for u in usages:
        if u.name and u.name.value:
            if sku_family.lower() in u.name.value.lower():
                result["family_limit"] = u.limit
                result["family_used"] = u.current_value
            if u.name.value.lower() in ("cores", "totalregionalvcpus"):
                result["regional_limit"] = u.limit
                result["regional_used"] = u.current_value
    return result


# ===================================================================
# Collector class
# ===================================================================

class AzureCapacityCollector:
    """Collects Azure capacity and quota data and produces RegionSnapshots."""

    # KQL: Capacity Reservation Groups with utilisation
    KQL_CRG = """
    resources
    | where type =~ 'microsoft.compute/capacityreservationgroups'
    | mv-expand cr = properties.capacityReservations
    | extend crId = tostring(cr.id)
    | join kind=leftouter (
        resources
        | where type =~ 'microsoft.compute/capacityreservationgroups/capacityreservations'
        | extend crId = id,
                 sku_name = tostring(sku.name),
                 capacity = toint(sku.capacity),
                 provisioningState = tostring(properties.provisioningState),
                 zone = tostring(zones[0]),
                 allocated = toint(properties.virtualMachinesAllocated)
    ) on crId
    | project subscriptionId, resourceGroup, crgName=name,
             location, sku_name, capacity, allocated, zone,
             provisioningState
    """

    # KQL: VM instances using capacity reservations
    KQL_VMS = """
    resources
    | where type =~ 'microsoft.compute/virtualmachines'
    | where isnotempty(properties.capacityReservation)
    | extend crg = tostring(properties.capacityReservation.capacityReservationGroup.id)
    | project subscriptionId, vmName=name, location,
             vmSize=tostring(properties.hardwareProfile.vmSize),
             crg, powerState=tostring(properties.extended.instanceView.powerState.code)
    """

    def __init__(
        self,
        subscription_ids: list[str],
        geography: str,
        sku_family: str = "Dadsv5",
        output_dir: str = "./data",
    ):
        self.subscription_ids = subscription_ids
        self.geography = geography
        self.sku_family = sku_family
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._credential = None

    @property
    def credential(self):
        if self._credential is None:
            self._credential = _get_credential()
        return self._credential

    # ---------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------

    def collect_region_snapshots(self) -> list[RegionSnapshot]:
        """Run full collection and return RegionSnapshot list."""
        logger.info("Collecting CRG data via Resource Graph...")
        crg_rows = _query_resource_graph(
            self.credential, self.subscription_ids, self.KQL_CRG,
        )
        logger.info("Collected %d CRG reservation rows.", len(crg_rows))

        logger.info("Collecting VM data via Resource Graph...")
        vm_rows = _query_resource_graph(
            self.credential, self.subscription_ids, self.KQL_VMS,
        )
        logger.info("Collected %d VM rows.", len(vm_rows))

        geo_config = GEOGRAPHY_CATALOGUE.get(self.geography)
        if not geo_config:
            raise ValueError(f"Unknown geography: {self.geography}")

        snapshots: list[RegionSnapshot] = []
        for region_id, rmeta in geo_config["regions"].items():
            snap = self._build_snapshot(region_id, rmeta, geo_config, crg_rows, vm_rows)
            snapshots.append(snap)

        # Persist JSON
        self._save_json(snapshots)
        return snapshots

    def collect_and_save(self) -> Path:
        """Collect, save to JSON, return output path."""
        self.collect_region_snapshots()
        return self.output_dir / f"regions_{self.geography.lower().replace(' ', '_')}.json"

    # ---------------------------------------------------------------
    # Internal — build a single RegionSnapshot
    # ---------------------------------------------------------------

    def _build_snapshot(
        self,
        region_id: str,
        rmeta: dict,
        geo_config: dict,
        crg_rows: list[dict],
        vm_rows: list[dict],
    ) -> RegionSnapshot:
        """Aggregate CRG + quota data into a RegionSnapshot."""
        # Filter CRG rows to this region
        region_crgs = [
            r for r in crg_rows
            if r.get("location", "").lower().replace(" ", "") == region_id
        ]

        # Aggregate by environment (infer from CRG naming: crg-pr-, crg-cvdr-, crg-drf-)
        envs = {"prod": {"reserved": 0, "allocated": 0},
                "cval": {"reserved": 0, "allocated": 0},
                "dr":   {"reserved": 0, "allocated": 0},
                "fnd":  {"reserved": 0, "allocated": 0}}
        zone_caps: dict[int, dict[str, int]] = {}  # zone -> {reserved, allocated}

        for row in region_crgs:
            crg_name = (row.get("crgName") or "").lower()
            cap = row.get("capacity") or 0
            alloc = row.get("allocated") or 0
            zone_str = row.get("zone", "")

            # Environment inference from CRG naming convention (OPS-006)
            env_key = "prod"
            if "crg-drf" in crg_name or "fnd" in crg_name:
                env_key = "fnd"
            elif "crg-cvdr" in crg_name:
                # Distinguish CVAL vs DR by tag or split equally
                env_key = "cval"  # Default to CVAL; DR sizing is max-not-sum
            elif "crg-pr" in crg_name:
                env_key = "prod"

            envs[env_key]["reserved"] += cap
            envs[env_key]["allocated"] += alloc

            # Zone-level
            if zone_str:
                zid = int(zone_str)
                if zid not in zone_caps:
                    zone_caps[zid] = {"reserved": 0, "allocated": 0}
                zone_caps[zid]["reserved"] += cap
                zone_caps[zid]["allocated"] += alloc

        # Quota (use first subscription, aggregate across all later)
        quota = {"family_limit": 0, "family_used": 0,
                 "regional_limit": 0, "regional_used": 0}
        for sub_id in self.subscription_ids:
            try:
                q = _get_quota_usage(self.credential, sub_id, region_id, self.sku_family)
                quota["family_limit"] = max(quota["family_limit"], q["family_limit"])
                quota["family_used"] += q["family_used"]
                quota["regional_limit"] = max(quota["regional_limit"], q["regional_limit"])
                quota["regional_used"] += q["regional_used"]
            except Exception as e:
                logger.warning("Quota query failed for %s/%s: %s", sub_id, region_id, e)

        dist_model = geo_config["distribution_model"]
        dr_dest = geo_config.get("dr_destination_geography")

        snap = RegionSnapshot(
            region_id=region_id,
            region_name=rmeta["name"],
            geography=self.geography,
            classification=RegionClassification(rmeta["classification"]),
            distribution_model=dist_model,
            availability_zones=len(zone_caps) or 3,
            auto_selectable=rmeta.get("auto_selectable", True),
            prod_reserved=envs["prod"]["reserved"],
            prod_allocated=envs["prod"]["allocated"],
            prod_free=max(0, envs["prod"]["reserved"] - envs["prod"]["allocated"]),
            cval_reserved=envs["cval"]["reserved"],
            cval_allocated=envs["cval"]["allocated"],
            cval_free=max(0, envs["cval"]["reserved"] - envs["cval"]["allocated"]),
            dr_reserved=envs["dr"]["reserved"],
            dr_allocated=envs["dr"]["allocated"],
            dr_free=max(0, envs["dr"]["reserved"] - envs["dr"]["allocated"]),
            fnd_dr_reserved=envs["fnd"]["reserved"],
            fnd_dr_allocated=envs["fnd"]["allocated"],
            fnd_dr_free=max(0, envs["fnd"]["reserved"] - envs["fnd"]["allocated"]),
            prod_quota_limit=quota["regional_limit"],
            prod_quota_used=quota["regional_used"],
            cval_quota_limit=quota["family_limit"],
            cval_quota_used=quota["family_used"],
            dr_quota_limit=quota["family_limit"],
            dr_quota_used=quota["family_used"],
            dr_destination_geography=dr_dest,
            dr_offered=dr_dest is not None or dist_model != DistributionModel.CROSS_GEO_DR,
            zone_capacities={z: ZoneCapacity(zone_id=z, reserved_quantity=d["reserved"],
                                              allocated_vms=d["allocated"])
                             for z, d in zone_caps.items()},
            zone_quotas={z: ZoneQuota(zone_id=z,
                                      family_quota_limit=quota["family_limit"],
                                      family_quota_used=quota["family_used"],
                                      regional_vcpu_limit=quota["regional_limit"],
                                      regional_vcpu_used=quota["regional_used"])
                         for z in zone_caps},
        )
        return snap

    # ---------------------------------------------------------------
    # Persistence
    # ---------------------------------------------------------------

    def _save_json(self, snapshots: list[RegionSnapshot]) -> None:
        """Persist snapshots as timestamped JSON."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        filename = f"regions_{self.geography.lower().replace(' ', '_')}_{ts}.json"
        path = self.output_dir / filename

        data = {
            "collected_at": ts,
            "geography": self.geography,
            "sku_family": self.sku_family,
            "subscription_ids": self.subscription_ids,
            "regions": [self._snapshot_to_dict(s) for s in snapshots],
        }
        path.write_text(json.dumps(data, indent=2))
        logger.info("Saved snapshot to %s", path)

        # Also write a 'latest' symlink
        latest = self.output_dir / f"regions_{self.geography.lower().replace(' ', '_')}.json"
        if latest.is_symlink() or latest.exists():
            latest.unlink()
        latest.symlink_to(path.name)

    @staticmethod
    def _snapshot_to_dict(snap: RegionSnapshot) -> dict:
        """Convert RegionSnapshot to a serialisable dict."""
        d = {
            "region_id": snap.region_id,
            "region_name": snap.region_name,
            "geography": snap.geography,
            "classification": snap.classification.value,
            "distribution_model": snap.distribution_model.value,
            "availability_zones": snap.availability_zones,
            "auto_selectable": snap.auto_selectable,
            "prod": {"reserved": snap.prod_reserved, "allocated": snap.prod_allocated, "free": snap.prod_free},
            "cval": {"reserved": snap.cval_reserved, "allocated": snap.cval_allocated, "free": snap.cval_free},
            "dr":   {"reserved": snap.dr_reserved,   "allocated": snap.dr_allocated,   "free": snap.dr_free},
            "fnd_dr": {"reserved": snap.fnd_dr_reserved, "allocated": snap.fnd_dr_allocated, "free": snap.fnd_dr_free},
            "quota": {
                "prod": {"limit": snap.prod_quota_limit, "used": snap.prod_quota_used},
                "cval": {"limit": snap.cval_quota_limit, "used": snap.cval_quota_used},
                "dr":   {"limit": snap.dr_quota_limit,   "used": snap.dr_quota_used},
            },
            "customers": {
                "prod": snap.prod_customer_count,
                "cval": snap.cval_customer_count,
                "dr":   snap.dr_customer_count,
                "total_geography": snap.total_customers_geography,
            },
            "dr_coverage": {"ratio": snap.dr_coverage_ratio, "target": snap.dr_coverage_target},
            "zones": {
                str(z): {"reserved": zc.reserved_quantity, "allocated": zc.allocated_vms, "available": zc.available_slots}
                for z, zc in snap.zone_capacities.items()
            },
        }
        if snap.dr_destination_geography:
            d["dr_destination_geography"] = snap.dr_destination_geography
        return d


# ===================================================================
# Standalone loader — read previously-saved JSON into RegionSnapshots
# ===================================================================

def load_snapshots_from_json(path: str | Path) -> list[RegionSnapshot]:
    """Re-hydrate RegionSnapshot objects from a collector JSON file."""
    data = json.loads(Path(path).read_text())
    snapshots: list[RegionSnapshot] = []
    for r in data["regions"]:
        zones_cap = {}
        zones_q = {}
        for zid_str, zdata in r.get("zones", {}).items():
            zid = int(zid_str)
            zones_cap[zid] = ZoneCapacity(
                zone_id=zid,
                reserved_quantity=zdata["reserved"],
                allocated_vms=zdata["allocated"],
            )
            zones_q[zid] = ZoneQuota(
                zone_id=zid,
                family_quota_limit=r["quota"]["prod"]["limit"],
                family_quota_used=r["quota"]["prod"]["used"],
                regional_vcpu_limit=r["quota"]["prod"]["limit"],
                regional_vcpu_used=r["quota"]["prod"]["used"],
            )
        snap = RegionSnapshot(
            region_id=r["region_id"],
            region_name=r["region_name"],
            geography=r["geography"],
            classification=RegionClassification(r["classification"]),
            distribution_model=DistributionModel(r["distribution_model"]),
            availability_zones=r["availability_zones"],
            auto_selectable=r["auto_selectable"],
            prod_reserved=r["prod"]["reserved"],
            prod_allocated=r["prod"]["allocated"],
            prod_free=r["prod"]["free"],
            cval_reserved=r["cval"]["reserved"],
            cval_allocated=r["cval"]["allocated"],
            cval_free=r["cval"]["free"],
            dr_reserved=r["dr"]["reserved"],
            dr_allocated=r["dr"]["allocated"],
            dr_free=r["dr"]["free"],
            fnd_dr_reserved=r["fnd_dr"]["reserved"],
            fnd_dr_allocated=r["fnd_dr"]["allocated"],
            fnd_dr_free=r["fnd_dr"]["free"],
            prod_quota_limit=r["quota"]["prod"]["limit"],
            prod_quota_used=r["quota"]["prod"]["used"],
            cval_quota_limit=r["quota"]["cval"]["limit"],
            cval_quota_used=r["quota"]["cval"]["used"],
            dr_quota_limit=r["quota"]["dr"]["limit"],
            dr_quota_used=r["quota"]["dr"]["used"],
            prod_customer_count=r["customers"]["prod"],
            cval_customer_count=r["customers"]["cval"],
            dr_customer_count=r["customers"]["dr"],
            total_customers_geography=r["customers"]["total_geography"],
            dr_coverage_ratio=r["dr_coverage"]["ratio"],
            dr_coverage_target=r["dr_coverage"]["target"],
            zone_capacities=zones_cap,
            zone_quotas=zones_q,
            dr_destination_geography=r.get("dr_destination_geography"),
            dr_offered=r.get("dr_destination_geography") is not None
                       or DistributionModel(r["distribution_model"]) != DistributionModel.CROSS_GEO_DR,
        )
        snapshots.append(snap)
    return snapshots


# ===================================================================
# CLI entry-point for standalone data collection
# ===================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ACRME Azure Capacity Collector")
    parser.add_argument("--subscriptions", "-s", nargs="+", required=True,
                        help="Azure subscription IDs to scan")
    parser.add_argument("--geography", "-g", required=True,
                        help="Geography to collect (US, Europe, Middle East, etc.)")
    parser.add_argument("--sku-family", default="Dadsv5",
                        help="VM SKU family to query quota for (default: Dadsv5)")
    parser.add_argument("--output-dir", "-o", default="./data",
                        help="Output directory for JSON snapshots")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    collector = AzureCapacityCollector(
        subscription_ids=args.subscriptions,
        geography=args.geography,
        sku_family=args.sku_family,
        output_dir=args.output_dir,
    )
    out = collector.collect_and_save()
    print(f"Snapshot saved to {out}")
