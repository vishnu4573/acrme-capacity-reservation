"""ACRME Placement Engine — Scoring Functions.

Implements Score_Pool(C,R) per v4.0 §21.5 (F.10/F.11).
Three environment-specific variants: PS_Prod, PS_NonProd, PS_DR.
"""
from __future__ import annotations

from models import (
    Environment, PlacementPolicy, RegionSnapshot, ScoringDetail,
    PlacementDecision,
)


def clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def safe_div(num: float, den: float) -> float:
    return num / den if den > 0 else 0.0


def gamma_fairness(env_customer_count: int,
                   total_customers_geo: int) -> float:
    """F.10 — γ fairness term.

    γ = 1 if total_customers(g) = 0
    γ = Clamp(1 − env_customer_count / total_customers(g), 0, 1)
    """
    if total_customers_geo == 0:
        return 1.0
    return clamp(1.0 - env_customer_count / total_customers_geo)


def score_prod(region: RegionSnapshot,
               policy: PlacementPolicy) -> ScoringDetail:
    """PS_Prod(r) — design-of-record [Decided].

    α: NonProd headroom signal (cross-pool, intentional)
    β: Prod quota headroom
    γ: distribution fairness
    δ: DR readiness signal
    ε: zone diversity
    """
    detail = ScoringDetail(region_id=region.region_id,
                           environment=Environment.PROD)

    # α: nonprod_crg.effective_free / prod_crg.quantity
    detail.alpha_raw = safe_div(region.cval_free, region.prod_reserved)
    detail.alpha_clamped = clamp(detail.alpha_raw)

    # β: prod_crg.quota_headroom / prod_crg.quota_limit
    detail.beta_raw = safe_div(region.prod_quota_headroom,
                                region.prod_quota_limit)
    detail.beta_clamped = clamp(detail.beta_raw)

    # γ: fairness
    detail.gamma_raw = gamma_fairness(region.prod_customer_count,
                                      region.total_customers_geography)
    detail.gamma_clamped = clamp(detail.gamma_raw)

    # δ: DR coverage ratio
    detail.delta_raw = region.dr_coverage_ratio
    detail.delta_clamped = clamp(detail.delta_raw)

    # ε: zone diversity (az_count / 3)
    detail.epsilon_raw = region.availability_zones / 3.0
    detail.epsilon_clamped = clamp(detail.epsilon_raw)

    detail.total_score = (
        policy.alpha * detail.alpha_clamped
        + policy.beta * detail.beta_clamped
        + policy.gamma * detail.gamma_clamped
        + policy.delta * detail.delta_clamped
        + policy.epsilon * detail.epsilon_clamped
    )

    return detail


def score_nonprod(region: RegionSnapshot,
                  policy: PlacementPolicy) -> ScoringDetail:
    """PS_NonProd(r) — design-of-record [Decided].

    NOTE: α and δ duplicate the same signal (known defect, combined 0.45).
    """
    detail = ScoringDetail(region_id=region.region_id,
                           environment=Environment.CVAL)

    # α: effective NonProd headroom
    detail.alpha_raw = safe_div(region.cval_free, region.cval_reserved)
    detail.alpha_clamped = clamp(detail.alpha_raw)

    # β: NonProd quota headroom
    detail.beta_raw = safe_div(region.cval_quota_headroom,
                                region.cval_quota_limit)
    detail.beta_clamped = clamp(detail.beta_raw)

    # γ: fairness
    detail.gamma_raw = gamma_fairness(region.cval_customer_count,
                                      region.total_customers_geography)
    detail.gamma_clamped = clamp(detail.gamma_raw)

    # δ: overflow capacity health (same signal as α — known duplication)
    detail.delta_raw = safe_div(region.cval_free, region.cval_reserved)
    detail.delta_clamped = clamp(detail.delta_raw)

    # ε: zone diversity
    detail.epsilon_raw = region.availability_zones / 3.0
    detail.epsilon_clamped = clamp(detail.epsilon_raw)

    detail.total_score = (
        policy.alpha * detail.alpha_clamped
        + policy.beta * detail.beta_clamped
        + policy.gamma * detail.gamma_clamped
        + policy.delta * detail.delta_clamped
        + policy.epsilon * detail.epsilon_clamped
    )

    return detail


def score_dr(region: RegionSnapshot,
             policy: PlacementPolicy) -> ScoringDetail:
    """PS_DR(r) — design-of-record [Decided]."""
    detail = ScoringDetail(region_id=region.region_id,
                           environment=Environment.DR)

    # α: DR CRG headroom
    total_dr = region.dr_reserved + region.fnd_dr_reserved
    total_dr_free = region.dr_free + region.fnd_dr_free
    detail.alpha_raw = safe_div(total_dr_free, total_dr)
    detail.alpha_clamped = clamp(detail.alpha_raw)

    # β: DR quota headroom
    detail.beta_raw = safe_div(region.dr_quota_headroom,
                                region.dr_quota_limit)
    detail.beta_clamped = clamp(detail.beta_raw)

    # γ: fairness
    detail.gamma_raw = gamma_fairness(region.dr_customer_count,
                                      region.total_customers_geography)
    detail.gamma_clamped = clamp(detail.gamma_raw)

    # δ: coverage-ratio health
    if region.dr_coverage_target > 0:
        detail.delta_raw = region.dr_coverage_ratio / region.dr_coverage_target
    else:
        detail.delta_raw = 0.0
    detail.delta_clamped = min(1.0, max(0.0, detail.delta_raw))

    # ε: zone diversity
    detail.epsilon_raw = region.availability_zones / 3.0
    detail.epsilon_clamped = clamp(detail.epsilon_raw)

    detail.total_score = (
        policy.alpha * detail.alpha_clamped
        + policy.beta * detail.beta_clamped
        + policy.gamma * detail.gamma_clamped
        + policy.delta * detail.delta_clamped
        + policy.epsilon * detail.epsilon_clamped
    )

    return detail


def score_region(region: RegionSnapshot, env: Environment,
                 policy: PlacementPolicy) -> ScoringDetail:
    """Dispatch to the correct scoring function."""
    if env == Environment.PROD:
        return score_prod(region, policy)
    elif env == Environment.CVAL:
        return score_nonprod(region, policy)
    else:
        return score_dr(region, policy)
