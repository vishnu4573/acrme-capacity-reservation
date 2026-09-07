"""
DR Destination Sizing — ACRME v2.3

Max-not-sum destination DR sizing (DR-017; Appendix A.6/A.7/A.8; Appendix D).

Under the single-region-failure assumption (DR-001), a destination region that
serves as DR target for several source regions is sized to absorb the **largest
single source** it protects — NOT the sum of all of them. This is the primary
mechanism that keeps the lean DR reserve affordable (FIN-006/008).

    A.6  Destination DR Requirement(d) = MAX over non-concurrent sources s of portion(s→d)
    A.7  DR Capacity Gap(d)            = max(0, Requirement(d) - Usable Destination Capacity(d))
    A.8  Overcommit Ratio(d)          = SUM(source portions on d) / MAX(source portions on d)

A conservative SUM override (C-11) is available per destination/scope only where a
customer/contract explicitly requires protection against concurrent failures.
"""

from dataclasses import dataclass, field
from typing import Dict, Iterable, Literal, Optional


SizingBasis = Literal["max", "sum"]


@dataclass
class SourcePortion:
    """One source region's failover portion landing on a destination.

    Fields:
        source_region: The protected production region.
        vcpu: vCPU that this source's customers would require in the destination
              if `source_region` fails (aggregated across its customers).
    """

    source_region: str
    vcpu: int


@dataclass
class DestinationSizing:
    """Computed sizing verdict for one destination region.

    Fields:
        destination_region: The DR-hosting region.
        basis: "max" (default, DR-017) or "sum" (conservative override, C-11).
        requirement_vcpu: Standby vCPU the destination must reserve (A.6).
        usable_capacity_vcpu: Capacity available to satisfy DR (bootstrap +
            available reservation + releasable CVAL + acquired sharing/expansion).
        gap_vcpu: Shortfall that must be acquired via staged sequence (A.7).
        overcommit_ratio: SUM/MAX exposure measure (A.8); 1.0 when a single source.
        largest_source: The source region that drives the max requirement.
        source_portions: The inputs used, for audit/replay.
    """

    destination_region: str
    basis: SizingBasis
    requirement_vcpu: int
    usable_capacity_vcpu: int
    gap_vcpu: int
    overcommit_ratio: float
    largest_source: Optional[str]
    source_portions: list = field(default_factory=list)  # list[SourcePortion]

    @property
    def is_covered(self) -> bool:
        """True if usable capacity already meets the requirement (no gap)."""
        return self.gap_vcpu == 0

    def to_dict(self) -> dict:
        return {
            "destination_region": self.destination_region,
            "basis": self.basis,
            "requirement_vcpu": self.requirement_vcpu,
            "usable_capacity_vcpu": self.usable_capacity_vcpu,
            "gap_vcpu": self.gap_vcpu,
            "overcommit_ratio": round(self.overcommit_ratio, 4),
            "largest_source": self.largest_source,
            "source_portions": [
                {"source_region": p.source_region, "vcpu": p.vcpu}
                for p in self.source_portions
            ],
        }


class DRSizer:
    """
    Max-not-sum DR destination sizer (DR-017, Appendix D).

    Aggregates per-customer protected portions into per-source-region portions,
    then sizes each destination for its largest single protected source. Exposes
    the overcommit ratio (A.8) so leadership can sign off the residual exposure
    (POC-011) if the single-failure assumption is ever violated.
    """

    def __init__(self, default_basis: SizingBasis = "max"):
        if default_basis not in ("max", "sum"):
            raise ValueError("default_basis must be 'max' or 'sum'")
        self.default_basis = default_basis
        # Per-destination SUM overrides (C-11), keyed by destination region.
        self._sum_overrides: set[str] = set()

    def set_sum_override(self, destination_region: str, enabled: bool = True) -> None:
        """Enable/disable the conservative SUM override for a destination (C-11)."""
        if enabled:
            self._sum_overrides.add(destination_region)
        else:
            self._sum_overrides.discard(destination_region)

    @staticmethod
    def aggregate_source_portions(
        protected_portions: Iterable,
    ) -> list:
        """
        Collapse per-customer protected portions into per-source-region totals.

        Args:
            protected_portions: iterable of objects/dicts exposing
                `source_region` and `protected_vcpu` (e.g. SourceDestinationDRIndex
                entries for one destination).

        Returns:
            list[SourcePortion] — one entry per distinct source region.
        """
        totals: Dict[str, int] = {}
        for p in protected_portions:
            if isinstance(p, dict):
                src = p["source_region"]
                vcpu = int(p.get("protected_vcpu", p.get("vcpu", 0)))
            else:
                src = p.source_region
                vcpu = int(getattr(p, "protected_vcpu", getattr(p, "vcpu", 0)))
            totals[src] = totals.get(src, 0) + vcpu
        return [SourcePortion(source_region=s, vcpu=v) for s, v in totals.items()]

    def size_destination(
        self,
        destination_region: str,
        protected_portions: Iterable,
        usable_capacity_vcpu: int = 0,
        basis: Optional[SizingBasis] = None,
    ) -> DestinationSizing:
        """
        Compute the standby requirement, gap and overcommit ratio for a destination.

        Args:
            destination_region: The DR-hosting region.
            protected_portions: per-customer or per-source portions landing here.
            usable_capacity_vcpu: capacity already usable for DR at the destination.
            basis: override the sizing basis for this call ("max"/"sum").

        Returns:
            DestinationSizing.
        """
        portions = self.aggregate_source_portions(protected_portions)

        # Resolve basis: explicit arg > per-destination override (C-11) > default.
        effective_basis: SizingBasis = (
            basis
            if basis is not None
            else ("sum" if destination_region in self._sum_overrides else self.default_basis)
        )

        vcpus = [p.vcpu for p in portions]
        sum_v = sum(vcpus)
        max_v = max(vcpus) if vcpus else 0
        largest_source = (
            max(portions, key=lambda p: p.vcpu).source_region if portions else None
        )

        requirement = sum_v if effective_basis == "sum" else max_v
        gap = max(0, requirement - usable_capacity_vcpu)
        overcommit = (sum_v / max_v) if max_v > 0 else 1.0

        return DestinationSizing(
            destination_region=destination_region,
            basis=effective_basis,
            requirement_vcpu=requirement,
            usable_capacity_vcpu=usable_capacity_vcpu,
            gap_vcpu=gap,
            overcommit_ratio=overcommit,
            largest_source=largest_source,
            source_portions=portions,
        )

    def size_all(
        self,
        portions_by_destination: Dict[str, Iterable],
        usable_by_destination: Optional[Dict[str, int]] = None,
    ) -> Dict[str, DestinationSizing]:
        """
        Size every destination region in one pass.

        Args:
            portions_by_destination: {destination_region: [portions...]}
            usable_by_destination: {destination_region: usable_capacity_vcpu}

        Returns:
            {destination_region: DestinationSizing}
        """
        usable_by_destination = usable_by_destination or {}
        return {
            dest: self.size_destination(
                destination_region=dest,
                protected_portions=portions,
                usable_capacity_vcpu=usable_by_destination.get(dest, 0),
            )
            for dest, portions in portions_by_destination.items()
        }
