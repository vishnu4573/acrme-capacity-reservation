#!/usr/bin/env python3
"""ACRME Placement Engine — Entry Point.

Runs the CRV → DPB placement pipeline against mock or Azure-collected data
and generates a detailed Markdown report showing selection/rejection at
every stage (HC gate, scoring, zone assignment).

Usage:
    # Mock data (default)
    python run_mockup.py

    # Azure-collected JSON
    python run_mockup.py --data-dir ./data --geography US

    # Custom output file
    python run_mockup.py -o placement_report.md
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from engine import run_placement
from mock_data import (
    build_all_regions,
    build_customers,
    build_eu_regions,
    build_me_regions,
    build_us_regions,
    default_policy,
)
from models import PlacementReport, RegionSnapshot
from report import generate_report

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Region lookup helpers
# -------------------------------------------------------------------

def regions_for_geography(
    geography: str,
    all_regions: dict[str, list[RegionSnapshot]],
) -> list[RegionSnapshot]:
    """Return region snapshots for a geography, with alias resolution."""
    aliases = {
        "EU": "Europe",
        "APAC": "Asia Pacific",
        "ME": "Middle East",
        "AU": "Australia",
    }
    key = aliases.get(geography, geography)
    if key not in all_regions:
        raise ValueError(
            f"No region data for geography '{geography}'. "
            f"Available: {list(all_regions.keys())}"
        )
    return all_regions[key]


def load_azure_regions(data_dir: str, geography: str) -> list[RegionSnapshot]:
    """Load region snapshots from Azure collector JSON."""
    from azure_collector import load_snapshots_from_json
    geo_key = geography.lower().replace(" ", "_")
    path = Path(data_dir) / f"regions_{geo_key}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"No Azure data found at {path}.\n"
            f"Run: python azure_collector.py -s <sub-ids> -g '{geography}' -o {data_dir}"
        )
    return load_snapshots_from_json(path)


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ACRME Placement Engine — run CRV → DPB pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_mockup.py                          # all mock customers
  python run_mockup.py --customer cust-001       # single customer
  python run_mockup.py --data-dir ./data -g US   # Azure-collected data
  python run_mockup.py -o report.md              # custom output file
""",
    )
    parser.add_argument(
        "--data-dir", "-d", default=None,
        help="Directory with Azure-collected JSON (omit for mock data)",
    )
    parser.add_argument(
        "--geography", "-g", default=None,
        help="Geography filter when using Azure data",
    )
    parser.add_argument(
        "--customer", "-c", default=None,
        help="Run for a single customer ID (e.g. cust-001)",
    )
    parser.add_argument(
        "--output", "-o", default="placement_report.md",
        help="Output Markdown report filename (default: placement_report.md)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    policy = default_policy()
    if not policy.validate():
        logger.error("Policy weight-sum invariant violated — aborting.")
        sys.exit(1)

    customers = build_customers()
    if args.customer:
        customers = [c for c in customers if c.customer_id == args.customer]
        if not customers:
            logger.error("Customer '%s' not found in mock data.", args.customer)
            sys.exit(1)

    # Build region data — Azure or mock
    if args.data_dir:
        if not args.geography:
            logger.error("--geography is required when using --data-dir.")
            sys.exit(1)
        all_regions = {args.geography: load_azure_regions(args.data_dir, args.geography)}
    else:
        all_regions = build_all_regions()

    # For cross-geo DR (ME), we also need Europe regions
    if "Middle East" in all_regions and "Europe" not in all_regions:
        if args.data_dir:
            try:
                all_regions["Europe"] = load_azure_regions(args.data_dir, "Europe")
            except FileNotFoundError:
                logger.warning(
                    "ME cross-geo DR needs Europe data. "
                    "Run collector for Europe or use mock data."
                )
                all_regions["Europe"] = build_eu_regions()
        else:
            all_regions["Europe"] = build_eu_regions()

    # ---------------------------------------------------------------
    # Run placement for each customer
    # ---------------------------------------------------------------
    reports: list[PlacementReport] = []
    for customer in customers:
        geo = customer.geography
        try:
            regions = regions_for_geography(geo, all_regions)
        except ValueError as e:
            logger.error(str(e))
            continue

        # For cross-geo DR, also supply DR-destination regions
        dr_regions: list[RegionSnapshot] | None = None
        if any(r.distribution_model.value == "cross_geography_dr" for r in regions):
            dr_dest_geo = next(
                (r.dr_destination_geography for r in regions if r.dr_destination_geography),
                None,
            )
            if dr_dest_geo and dr_dest_geo in all_regions:
                dr_regions = all_regions[dr_dest_geo]

        logger.info(
            "Running placement for %s (%s, %d domains, %s path)",
            customer.customer_name, geo,
            len(customer.domain_groups),
            "exact-region" if customer.supplied_prod_region else "geography",
        )

        # Combine customer-geography regions + DR destination regions
        combined_regions = list(regions)
        if dr_regions:
            existing_ids = {r.region_id for r in combined_regions}
            for r in dr_regions:
                if r.region_id not in existing_ids:
                    combined_regions.append(r)

        report = run_placement(
            customer=customer,
            regions=combined_regions,
            policy=policy,
        )
        reports.append(report)

        # Log summary
        crv = report.crv
        if crv:
            logger.info(
                "  CRV → Prod: %s, CVAL: %s, DR: %s  [%s path]",
                crv.prod_region or "—",
                crv.cval_region or "—",
                crv.dr_region or "—",
                crv.path_used,
            )
        for dpb in report.dpb_results:
            logger.info(
                "  DPB → %s / %s: region=%s, crg=%s, reserved=%d, passed=%s",
                dpb.domain_token, dpb.environment.value,
                dpb.region,
                dpb.crg_set_type.value,
                dpb.target_reserved,
                dpb.passed,
            )

    # ---------------------------------------------------------------
    # Generate combined report
    # ---------------------------------------------------------------
    sections: list[str] = []
    for rpt in reports:
        sections.append(generate_report(rpt))
    md = "\n\n---\n\n".join(sections)
    out_path = Path(args.output)
    out_path.write_text(md)
    print(f"\n{'='*60}")
    print(f"Placement report written to: {out_path.resolve()}")
    print(f"Customers processed: {len(reports)}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
