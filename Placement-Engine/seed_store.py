"""ACRME Placement Engine — Customer Seed Record Store.

Implements PLC-003/004/005 (Scenario 20):
  - PLC-003: first approved placement writes a seed record
  - PLC-004: subsequent placements reuse the seeded regions (no re-scoring)
  - PLC-005: region changes only via approved migration (--force-reselect)

Persistence: JSON file per customer-geography pair.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from models import CRVResult, DistributionModel

logger = logging.getLogger(__name__)

DEFAULT_SEED_DIR = Path("./seeds")


@dataclass
class SeedRecord:
    """Customer Placement Seed Record (Scenario 20).

    Persisted after first approved CRV resolution; loaded on subsequent
    placements so the engine skips Phase 1 and goes straight to DPB.
    """
    customer_id: str
    geography: str
    distribution_model: str     # DistributionModel.value
    prod_region: str
    cval_region: str
    dr_region: str
    path_used: str              # "exact_region" | "geography"
    policy_version: str
    created_at: str             # ISO-8601
    updated_at: str             # ISO-8601
    migration_history: list[dict] = field(default_factory=list)

    def to_crv(self) -> CRVResult:
        """Convert seed record back to a CRVResult (no scoring detail)."""
        return CRVResult(
            customer_id=self.customer_id,
            geography=self.geography,
            distribution_model=DistributionModel(self.distribution_model),
            prod_region=self.prod_region,
            cval_region=self.cval_region,
            dr_region=self.dr_region,
            path_used=f"seed_reuse ({self.path_used})",
            warnings=[f"CRV loaded from seed record (created {self.created_at})"]
        )


def _seed_path(seed_dir: Path, customer_id: str, geography: str) -> Path:
    """Return the JSON file path for a seed record."""
    safe_geo = geography.lower().replace(" ", "_")
    return seed_dir / f"seed_{customer_id}_{safe_geo}.json"


def load_seed(
    customer_id: str,
    geography: str,
    seed_dir: Path = DEFAULT_SEED_DIR,
) -> Optional[SeedRecord]:
    """Load existing seed record for (customer, geography). Returns None if absent."""
    path = _seed_path(seed_dir, customer_id, geography)
    if not path.exists():
        logger.debug("No seed record at %s", path)
        return None
    try:
        data = json.loads(path.read_text())
        record = SeedRecord(**data)
        logger.info(
            "Seed record loaded for %s / %s → Prod=%s, CVAL=%s, DR=%s (created %s)",
            customer_id, geography,
            record.prod_region, record.cval_region, record.dr_region,
            record.created_at,
        )
        return record
    except (json.JSONDecodeError, TypeError, KeyError) as exc:
        logger.warning("Corrupt seed record at %s: %s", path, exc)
        return None


def save_seed(
    crv: CRVResult,
    policy_version: str,
    seed_dir: Path = DEFAULT_SEED_DIR,
) -> SeedRecord:
    """Write a new seed record from a successful CRV result (PLC-003)."""
    seed_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    record = SeedRecord(
        customer_id=crv.customer_id,
        geography=crv.geography,
        distribution_model=crv.distribution_model.value,
        prod_region=crv.prod_region or "",
        cval_region=crv.cval_region or "",
        dr_region=crv.dr_region or "",
        path_used=crv.path_used,
        policy_version=policy_version,
        created_at=now,
        updated_at=now,
    )
    path = _seed_path(seed_dir, crv.customer_id, crv.geography)
    path.write_text(json.dumps(asdict(record), indent=2))
    logger.info("Seed record written → %s", path)
    return record


def update_seed_for_migration(
    customer_id: str,
    geography: str,
    new_crv: CRVResult,
    policy_version: str,
    reason: str,
    seed_dir: Path = DEFAULT_SEED_DIR,
) -> SeedRecord:
    """Overwrite seed record for an approved migration (PLC-005).

    The previous record is preserved in migration_history.
    """
    old = load_seed(customer_id, geography, seed_dir)
    now = datetime.now(timezone.utc).isoformat()

    history_entry = {
        "timestamp": now,
        "reason": reason,
        "previous_prod": old.prod_region if old else None,
        "previous_cval": old.cval_region if old else None,
        "previous_dr": old.dr_region if old else None,
        "previous_policy": old.policy_version if old else None,
    }

    migration_history = (old.migration_history if old else []) + [history_entry]

    record = SeedRecord(
        customer_id=customer_id,
        geography=geography,
        distribution_model=new_crv.distribution_model.value,
        prod_region=new_crv.prod_region or "",
        cval_region=new_crv.cval_region or "",
        dr_region=new_crv.dr_region or "",
        path_used=new_crv.path_used,
        policy_version=policy_version,
        created_at=old.created_at if old else now,
        updated_at=now,
        migration_history=migration_history,
    )
    path = _seed_path(seed_dir, customer_id, geography)
    path.write_text(json.dumps(asdict(record), indent=2))
    logger.info(
        "Seed record MIGRATED for %s / %s → Prod=%s, CVAL=%s, DR=%s (reason: %s)",
        customer_id, geography,
        record.prod_region, record.cval_region, record.dr_region, reason,
    )
    return record


def seed_exists(
    customer_id: str,
    geography: str,
    seed_dir: Path = DEFAULT_SEED_DIR,
) -> bool:
    """Check if a seed record exists without loading it."""
    return _seed_path(seed_dir, customer_id, geography).exists()
