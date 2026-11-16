"""Advisory, single-SKU/zone CRG candidate selector; not a deployment gate.

See examples/crg_region_selection.md for scope and adapter contracts.
Run with: python3 examples/crg_region_selection.py
"""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from math import isclose, isfinite
from typing import Dict, Mapping, Optional, Sequence, Tuple


FACTORS = (
    "allocated", "available_reservation", "quota", "buffers",
    "expected_dr", "zone_support", "freshness", "fairness",
)
HARD_CONSTRAINTS = tuple("HC-{}".format(number) for number in range(1, 12))


@dataclass(frozen=True)
class Request:
    geography: str
    environment: str
    domain: str
    subscription_id: str
    vm_size: str
    zone: Optional[str]
    count: int
    fixed_region: Optional[str] = None
    geography_exception_approved: bool = False
    customer_acknowledged: bool = False


@dataclass(frozen=True)
class Candidate:
    crg_id: str
    region: str
    geography: str
    environment: str
    domain: str
    subscription_id: str
    vm_size: str
    zone: Optional[str]
    available_instances: int
    observed_at: datetime
    snapshot_id: str
    standard_region: bool
    reservation_supported: bool
    family_quota_admitted: bool
    regional_quota_admitted: bool
    hard_constraints: Mapping[str, str]
    normalized_factors: Mapping[str, float]
    environment_customers: int
    geography_customers: int


@dataclass(frozen=True)
class Decision:
    region: Optional[str]
    crg_id: Optional[str]
    ranked: Tuple[Tuple[str, float], ...]
    rejected: Mapping[str, Tuple[str, ...]]
    status: str


def select_region(
    request: Request,
    candidates: Sequence[Candidate],
    weights: Mapping[str, float],
    now: datetime,
    max_age: timedelta,
) -> Decision:
    """Filter first, then maximize customer-aggregate suitability (F.10).

    fixed_region is the existing CRV region, or supplied exact Prod region.
    A blocked fixed region is returned unchanged; it is never reselected.
    HC verdicts and normalized factors must come from authoritative adapters.
    """
    if request.environment not in ("Prod", "CVAL", "DR"):
        raise ValueError("environment must be Prod, CVAL, or DR")
    if type(request.count) is not int or request.count <= 0:
        raise ValueError("count must be a positive integer")
    if now.utcoffset() is None or max_age <= timedelta(0):
        raise ValueError("now must be timezone-aware and max_age positive")
    if set(weights) != set(FACTORS):
        raise ValueError("weights must contain exactly the F.10 factors")
    if any(not isfinite(value) or value < 0 for value in weights.values()):
        raise ValueError("weights must be finite and nonnegative")
    if not isclose(sum(weights.values()), 1.0, rel_tol=0, abs_tol=1e-9):
        raise ValueError("weights must sum to 1.0")
    if request.environment == "Prod" and not request.fixed_region:
        if not (request.geography_exception_approved and request.customer_acknowledged):
            raise ValueError("Prod requires an exact region or acknowledged approved exception")
    if len({candidate.crg_id for candidate in candidates}) != len(candidates):
        raise ValueError("duplicate CRG candidates")

    ranked = []
    rejected: Dict[str, Tuple[str, ...]] = {}
    for candidate in candidates:
        reasons = []
        for field in ("geography", "environment", "domain", "subscription_id", "vm_size", "zone"):
            if getattr(candidate, field) != getattr(request, field):
                reasons.append("{} mismatch".format(field))
        if request.fixed_region and candidate.region != request.fixed_region:
            reasons.append("outside fixed region")
        if not candidate.standard_region:
            reasons.append("not a Standard region")
        if not candidate.reservation_supported:
            reasons.append("reservation unsupported")
        if type(candidate.available_instances) is not int or candidate.available_instances < request.count:
            reasons.append("insufficient usable reserved instances")
        if not candidate.family_quota_admitted or not candidate.regional_quota_admitted:
            reasons.append("quota admission failed")
        if not candidate.snapshot_id or candidate.observed_at.utcoffset() is None:
            reasons.append("missing snapshot identity or timezone")
        elif not timedelta(0) <= now - candidate.observed_at <= max_age:
            reasons.append("stale or future snapshot")
        if set(candidate.hard_constraints) != set(HARD_CONSTRAINTS) or any(
            candidate.hard_constraints.get(code) not in ("PASS", "N/A")
            for code in HARD_CONSTRAINTS
        ):
            reasons.append("missing, unresolved, or failed hard constraint")
        factors = dict(candidate.normalized_factors)
        if set(factors) != set(FACTORS) - {"fairness"} or any(
            not isfinite(value) or not 0 <= value <= 1 for value in factors.values()
        ):
            reasons.append("missing or invalid normalized scoring factors")
        if (
            type(candidate.geography_customers) is not int
            or type(candidate.environment_customers) is not int
            or not 0 <= candidate.environment_customers <= candidate.geography_customers
        ):
            reasons.append("invalid geography customer counts")
        if reasons:
            rejected[candidate.crg_id] = tuple(reasons)
            continue
        factors["fairness"] = (
            1.0 if candidate.geography_customers == 0
            else 1.0 - candidate.environment_customers / candidate.geography_customers
        )
        score = sum(weights[factor] * factors[factor] for factor in FACTORS)
        ranked.append((candidate, score))

    ranked.sort(key=lambda item: (-item[1], item[0].region, item[0].crg_id))
    scores = tuple((candidate.crg_id, score) for candidate, score in ranked)
    if not ranked:
        return Decision(request.fixed_region, None, scores, rejected, "BLOCKED")
    selected = ranked[0][0]
    return Decision(selected.region, selected.crg_id, scores, rejected, "ADVISORY")


def demo_inputs():
    """Synthetic inputs only; PASS verdicts are not live Azure evidence."""
    now = datetime.now(timezone.utc)
    request = Request("US", "Prod", "TMS", "demo-sub", "Standard_D4s_v5", "1", 3,
                      geography_exception_approved=True, customer_acknowledged=True)
    candidate = Candidate(
        crg_id="demo-eastus2", region="eastus2", geography="US", environment="Prod",
        domain="TMS", subscription_id="demo-sub", vm_size="Standard_D4s_v5", zone="1",
        available_instances=8, observed_at=now, snapshot_id="synthetic-snapshot",
        standard_region=True, reservation_supported=True,
        family_quota_admitted=True, regional_quota_admitted=True,
        hard_constraints={code: "PASS" for code in HARD_CONSTRAINTS},
        normalized_factors={factor: 0.8 for factor in FACTORS if factor != "fairness"},
        environment_customers=2, geography_customers=10,
    )
    candidates = (
        candidate,
        replace(candidate, crg_id="demo-centralus", region="centralus", environment_customers=5),
        replace(candidate, crg_id="demo-westus2", region="westus2", available_instances=1),
    )
    weights = {factor: 0.125 for factor in FACTORS}
    return request, candidates, weights, now


if __name__ == "__main__":
    demo_request, demo_candidates, demo_weights, demo_now = demo_inputs()
    print(select_region(demo_request, demo_candidates, demo_weights, demo_now, timedelta(minutes=5)))