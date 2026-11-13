"""ACRME Placement Engine — Report Generator.

Produces a detailed Markdown report showing the full selection/rejection
process at region, environment, and zone level.
"""
from __future__ import annotations

from models import (
    CRVResult, DPBResult, Environment, PlacementDecision,
    PlacementPolicy, PlacementReport, ScoringDetail,
)


def _decision_icon(d: PlacementDecision) -> str:
    icons = {
        PlacementDecision.SELECTED: "✅",
        PlacementDecision.REJECTED_HC: "❌",
        PlacementDecision.REJECTED_SCORING: "⚠️",
        PlacementDecision.DETERMINISTIC: "🔒",
        PlacementDecision.CROSS_GEO: "🌍",
        PlacementDecision.NOT_EVALUATED: "➖",
    }
    return icons.get(d, "")


def _scoring_table(scores: list[ScoringDetail], policy: PlacementPolicy) -> str:
    """Render a scoring breakdown table."""
    if not scores:
        return "_No candidates evaluated._\n"

    lines = []
    lines.append("| Region | α ({:.0%}) | β ({:.0%}) | γ ({:.0%}) | δ ({:.0%}) | ε ({:.0%}) | **Score** | HC | Decision |".format(
        policy.alpha, policy.beta, policy.gamma, policy.delta, policy.epsilon))
    lines.append("|---|---|---|---|---|---|---|---|---|")

    for s in sorted(scores, key=lambda x: x.total_score, reverse=True):
        hc_icon = "✅" if s.hc_passed else "❌"
        dec = _decision_icon(s.decision)
        lines.append(
            f"| {s.region_id} "
            f"| {s.alpha_clamped:.3f} "
            f"| {s.beta_clamped:.3f} "
            f"| {s.gamma_clamped:.3f} "
            f"| {s.delta_clamped:.3f} "
            f"| {s.epsilon_clamped:.3f} "
            f"| **{s.total_score:.4f}** "
            f"| {hc_icon} "
            f"| {dec} {s.decision.value} |"
        )

    # Rejection details
    rejected = [s for s in scores if s.rejection_reasons]
    if rejected:
        lines.append("")
        lines.append("**Rejection details:**")
        for s in rejected:
            for reason in s.rejection_reasons:
                lines.append(f"- `{s.region_id}`: {reason}")

    return "\n".join(lines)


def _hc_detail_table(hc_results) -> str:
    """Render HC gate results."""
    if not hc_results:
        return ""
    lines = ["| HC | Description | Result | Detail |"]
    lines.append("|---|---|---|---|")
    for hc in hc_results:
        icon = "✅" if hc.passed else "❌"
        lines.append(f"| {hc.hc_id} | {hc.description} | {icon} | {hc.detail} |")
    return "\n".join(lines)


def generate_report(report: PlacementReport) -> str:
    """Generate the full Markdown placement report."""
    c = report.customer
    crv = report.crv
    p = report.policy
    lines: list[str] = []

    # Header
    lines.append(f"# ACRME Placement Report")
    lines.append(f"")
    lines.append(f"**Customer:** {c.customer_name} (`{c.customer_id}`)")
    lines.append(f"**Geography:** {c.geography}")
    lines.append(f"**Domain Groups:** {', '.join(d.display_name for d in c.domain_groups)}")
    lines.append(f"**Policy Version:** {p.policy_version}")
    lines.append(f"**Timestamp:** {report.timestamp}")
    lines.append(f"**Overall Status:** `{report.overall_status}`")
    lines.append(f"")

    # Customer demand summary
    lines.append(f"## Customer Demand Summary")
    lines.append(f"")
    lines.append(f"| Domain | Prod vCPU | CVAL vCPU | DR vCPU | SKU Family |")
    lines.append(f"|---|---|---|---|---|")
    for d in c.domain_groups:
        lines.append(f"| {d.display_name} | {d.prod_vcpu_demand} | {d.cval_vcpu_demand} | {d.dr_vcpu_demand} | {d.sku_family} |")
    lines.append(f"| **Total** | **{c.total_prod_demand}** | **{c.total_cval_demand}** | **{c.total_dr_demand}** | |")
    lines.append(f"")

    # Warnings
    if crv.warnings:
        lines.append(f"## ⚠️ Warnings")
        for w in crv.warnings:
            lines.append(f"- {w}")
        lines.append(f"")

    # Phase 1: CRV
    lines.append(f"---")
    lines.append(f"## Phase 1 — Customer Region Vector (CRV)")
    lines.append(f"")
    lines.append(f"**Path:** `{crv.path_used}` | **Distribution Model:** `{crv.distribution_model.value}`")
    lines.append(f"")

    # CRV result box
    lines.append(f"### CRV Result")
    lines.append(f"")
    lines.append(f"| Environment | Selected Region |")
    lines.append(f"|---|---|")
    lines.append(f"| Prod | `{crv.prod_region or 'NONE'}` |")
    lines.append(f"| CVAL | `{crv.cval_region or 'NONE'}` |")
    lines.append(f"| DR | `{crv.dr_region or 'NONE'}` |")
    lines.append(f"")

    # Prod scoring
    lines.append(f"### Prod Region Selection")
    lines.append(f"")
    if crv.path_used == "exact_region" and crv.prod_scoring:
        s = crv.prod_scoring[0]
        lines.append(f"**Supplied region:** `{c.supplied_prod_region}` → "
                      f"{_decision_icon(s.decision)} `{s.decision.value}`")
        lines.append(f"")
        lines.append(f"**HC Gate:**")
        lines.append(f"")
        lines.append(_hc_detail_table(s.hc_results))
        lines.append(f"")
        lines.append(f"**Audit score (not used for selection):** `{s.total_score:.4f}`")
    else:
        lines.append(_scoring_table(crv.prod_scoring, p))
    lines.append(f"")

    # CVAL scoring
    lines.append(f"### CVAL Region Selection")
    lines.append(f"")
    if crv.distribution_model.value == "two_region":
        lines.append(f"🔒 **Deterministic co-location (PLC-010a):** CVAL = DR = "
                      f"only remaining standard region")
    elif crv.distribution_model.value == "cross_geography_dr":
        lines.append(f"🌍 **Cross-geo model (PLC-010b):** CVAL co-locates with Prod "
                      f"(separate CRGs)")
    else:
        lines.append(_scoring_table(crv.cval_scoring, p))
    lines.append(f"")

    # DR scoring
    lines.append(f"### DR Region Selection")
    lines.append(f"")
    if crv.distribution_model.value == "two_region":
        lines.append(f"🔒 **Deterministic co-location (PLC-010a):** DR co-locates "
                      f"with CVAL")
    elif crv.distribution_model.value == "cross_geography_dr":
        lines.append(f"🌍 **Cross-geo DR (DR-020, PLC-010b):** DR placed in Europe")
        lines.append(f"")
        lines.append(_scoring_table(crv.dr_scoring, p))
    else:
        lines.append(_scoring_table(crv.dr_scoring, p))
    lines.append(f"")

    # Phase 2: DPB
    lines.append(f"---")
    lines.append(f"## Phase 2 — Domain Placement Binding (DPB)")
    lines.append(f"")
    lines.append(f"CRV is consumed by DPB. Each domain group gets its own "
                  f"subscription, instance group, CRG set, and quota draw.")
    lines.append(f"")

    for domain in c.domain_groups:
        domain_dpbs = [d for d in report.dpb_results
                       if d.domain_token == domain.token]
        lines.append(f"### Domain: {domain.display_name} (`{domain.token}`)")
        lines.append(f"")

        for dpb in domain_dpbs:
            status_icon = "✅" if dpb.passed else "❌"
            lines.append(f"#### {dpb.environment.value} → `{dpb.region}` {status_icon}")
            lines.append(f"")
            lines.append(f"| Property | Value |")
            lines.append(f"|---|---|")
            lines.append(f"| Instance Group | `{dpb.instance_group}` |")
            lines.append(f"| Subscription | `{dpb.subscription_id}` |")
            lines.append(f"| CRG Set Type | `{dpb.crg_set_type.value}` |")
            lines.append(f"| Target Reserved (F.1) | {dpb.target_reserved} vCPU |")
            lines.append(f"| Headroom (F.2) | {dpb.headroom} vCPU |")
            lines.append(f"| Deficit (F.3) | {dpb.deficit} vCPU |")
            lines.append(f"| Available Quota (F.4) | {dpb.available_quota} vCPU |")
            lines.append(f"| Quota Deficit (F.5) | {dpb.quota_deficit} vCPU |")
            lines.append(f"| Quota Replenish Needed | {'YES ⚠️' if dpb.quota_replenish_needed else 'No'} |")
            lines.append(f"")

            if dpb.rejection_reasons:
                lines.append(f"**❌ Rejection reasons:**")
                for r in dpb.rejection_reasons:
                    lines.append(f"- {r}")
                lines.append(f"")

            # HC detail
            if dpb.hc_results:
                lines.append(f"**DPB HC Gate:**")
                lines.append(f"")
                lines.append(_hc_detail_table(dpb.hc_results))
                lines.append(f"")

            # Zone-level detail
            if dpb.zone_placements:
                lines.append(f"**Zone-Level Placement (F.9, PLC-016):**")
                lines.append(f"")
                lines.append(f"| Zone | Target | Current | Skew | Rebalance | CRG | Avail Slots | Quota Avail |")
                lines.append(f"|---|---|---|---|---|---|---|---|")
                for zp in dpb.zone_placements:
                    rebal = "⚠️ YES" if zp.rebalance_needed else "—"
                    lines.append(
                        f"| Zone {zp.zone_id} "
                        f"| {zp.target_vms} "
                        f"| {zp.current_vms} "
                        f"| {zp.skew:+d} "
                        f"| {rebal} "
                        f"| `{zp.crg_name}` "
                        f"| {zp.available_slots} "
                        f"| {zp.quota_available} |")
                lines.append(f"")

    # Summary
    lines.append(f"---")
    lines.append(f"## Summary")
    lines.append(f"")
    lines.append(f"| Domain | Environment | Region | Status | Deficit | Quota Deficit |")
    lines.append(f"|---|---|---|---|---|---|")
    for dpb in report.dpb_results:
        icon = "✅" if dpb.passed else "❌"
        lines.append(
            f"| {dpb.domain_token} "
            f"| {dpb.environment.value} "
            f"| {dpb.region} "
            f"| {icon} "
            f"| {dpb.deficit} "
            f"| {dpb.quota_deficit} |")
    lines.append(f"")

    return "\n".join(lines)
