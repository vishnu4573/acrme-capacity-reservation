"""Test runner engine for the ACRME POC suite.

Defines the :class:`TestCase` / :class:`TestResult` dataclasses, the global test
registry, the phase-gate requirement mapping, and the :class:`TestRunner` that
executes tests with prerequisite checking, phase-gate filtering, exception
capture, and live progress output.
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from .config import PHASE_GATE_ORDER, Config
from .az_client import AzClient
from .result_store import ResultStore

# ----------------------------------------------------------------------
# Data model
# ----------------------------------------------------------------------
VALID_STATUSES = ("pass", "fail", "blocked", "skipped", "not_run")


@dataclass
class TestResult:
    """Outcome of a single test execution."""

    poc_id: str
    status: str  # pass | fail | blocked | skipped | not_run
    actual_result: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)
    duration_seconds: float = 0.0
    error: Optional[str] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __post_init__(self) -> None:
        if self.status not in VALID_STATUSES:
            raise ValueError(
                f"Invalid status '{self.status}' for {self.poc_id}; "
                f"must be one of {VALID_STATUSES}."
            )


@dataclass
class TestCase:
    """A registered POC test case."""

    poc_id: str
    group: str
    name: str
    phase_gates: List[str]
    prerequisites: List[str]
    run_fn: Callable[[Config, AzClient], TestResult]
    warning: Optional[str] = None


# ----------------------------------------------------------------------
# Registry
# ----------------------------------------------------------------------
class Registry:
    """Ordered registry of test cases keyed by poc_id."""

    def __init__(self) -> None:
        self._cases: Dict[str, TestCase] = {}
        self._order: List[str] = []

    def add(self, case: TestCase) -> None:
        """Register a test case (last registration wins on duplicate id)."""
        if case.poc_id not in self._cases:
            self._order.append(case.poc_id)
        self._cases[case.poc_id] = case

    def get(self, poc_id: str) -> Optional[TestCase]:
        return self._cases.get(poc_id)

    def all(self) -> List[TestCase]:
        """Return all cases in registration order."""
        return [self._cases[pid] for pid in self._order]

    def by_group(self, group: str) -> List[TestCase]:
        """Return all cases belonging to *group* (case-insensitive)."""
        g = group.strip().lower()
        return [c for c in self.all() if c.group.lower() == g]

    def groups(self) -> List[str]:
        """Return the distinct group ids in registration order."""
        seen: List[str] = []
        for c in self.all():
            if c.group not in seen:
                seen.append(c.group)
        return seen


# Single global registry populated by test modules at import time.
REGISTRY = Registry()


def _register_all() -> None:
    """Import every test group module so their cases register themselves."""
    from .tests import (  # noqa: WPS433 (import inside function is intentional)
        g1_crg_basics,
        g2_sharing,
        g3_dr_failover,
        g4_quota_groups,
        g5_safety,
        g6_aks_vmss,
        g7_throttle,
        g8_ri_discount,
    )

    for module in (
        g1_crg_basics,
        g2_sharing,
        g3_dr_failover,
        g4_quota_groups,
        g5_safety,
        g6_aks_vmss,
        g7_throttle,
        g8_ri_discount,
    ):
        module.register(REGISTRY)


# ----------------------------------------------------------------------
# Phase gate requirements
# ----------------------------------------------------------------------
# Maps each phase gate to the list of POC IDs that MUST pass for that gate to be
# considered satisfied. Higher gates are cumulative (production includes phase2
# which includes phase1) — the reporter expands them accordingly.
PHASE_GATE_REQUIREMENTS: Dict[str, List[str]] = {
    "phase1": [
        "POC-01", "POC-02", "POC-03", "POC-04", "POC-05",
        "POC-06", "POC-06a", "POC-07", "POC-08", "POC-09",
        "POC-30", "POC-13",
        "POC-15", "POC-16", "POC-17", "POC-20",
        "POC-THROTTLE-01", "POC-RI-01",
    ],
    "phase2": [
        "POC-11", "POC-12", "POC-14",
        "POC-31", "POC-32",
        "POC-18", "POC-19",
        "POC-VMSS-DR", "POC-RI-02",
    ],
    "production": [
        "POC-10", "POC-THROTTLE-02", "POC-THROTTLE-03",
    ],
}


def cumulative_gate_requirements(phase_gate: str) -> List[str]:
    """Return all POC IDs required for *phase_gate*, cumulative across lower gates."""
    order = ["phase1", "phase2", "production"]
    if phase_gate not in order:
        return []
    required: List[str] = []
    for gate in order:
        required.extend(PHASE_GATE_REQUIREMENTS.get(gate, []))
        if gate == phase_gate:
            break
    # De-duplicate preserving order.
    seen: set = set()
    result: List[str] = []
    for pid in required:
        if pid not in seen:
            seen.add(pid)
            result.append(pid)
    return result


def gate_allows(test_gates: List[str], configured_gate: str) -> bool:
    """True if a test tagged *test_gates* is eligible under *configured_gate*.

    A test is eligible when its lowest (most permissive) phase gate is at or
    below the configured gate in the permissiveness order.
    """
    if not test_gates:
        return True
    configured_rank = PHASE_GATE_ORDER.get(configured_gate, 0)
    test_min_rank = min(PHASE_GATE_ORDER.get(g, 99) for g in test_gates)
    return test_min_rank <= configured_rank


# ----------------------------------------------------------------------
# Runner
# ----------------------------------------------------------------------
class TestRunner:
    """Executes test cases with prerequisite + phase-gate gating."""

    def __init__(
        self,
        config: Config,
        az: AzClient,
        store: ResultStore,
        resume: bool = False,
    ) -> None:
        self.config = config
        self.az = az
        self.store = store
        self.resume = resume

    def _prereqs_satisfied(self, case: TestCase) -> Optional[str]:
        """Return None if prereqs are met, else a human-readable blocking reason."""
        unmet = []
        for prereq in case.prerequisites:
            status = self.store.get_status(prereq)
            if status != "pass":
                unmet.append(f"{prereq} (status={status or 'not_run'})")
        if unmet:
            return "Blocked by unmet prerequisites: " + ", ".join(unmet)
        return None

    def run_case(self, case: TestCase) -> TestResult:
        """Execute a single test case, applying all gating rules."""
        # Resume: skip already-passed tests.
        if self.resume and self.store.get_status(case.poc_id) == "pass":
            print(f"[SKIP] {case.poc_id} — already passed (resume)")
            existing = self.store.get_result(case.poc_id)
            return TestResult(
                poc_id=case.poc_id,
                status="pass",
                actual_result=(existing or {}).get("actual_result", "Previously passed"),
                evidence=(existing or {}).get("evidence", {}),
            )

        # Phase gate filter.
        if not gate_allows(case.phase_gates, self.config.phase_gate):
            reason = (
                f"Test phase gates {case.phase_gates} exclude configured gate "
                f"'{self.config.phase_gate}'"
            )
            print(f"[SKIP] {case.poc_id} — {reason}")
            result = TestResult(
                poc_id=case.poc_id, status="skipped", actual_result=reason
            )
            self.store.record(result)
            return result

        # Prerequisite check.
        block_reason = self._prereqs_satisfied(case)
        if block_reason:
            print(f"[BLOCKED] {case.poc_id} — {block_reason}")
            result = TestResult(
                poc_id=case.poc_id,
                status="blocked",
                actual_result=block_reason,
                error=block_reason,
            )
            self.store.record(result)
            return result

        # Execute.
        if case.warning:
            print(f"[WARN] {case.poc_id} — {case.warning}")
        print(f"[RUNNING] {case.poc_id} — {case.name}")
        self.az.set_current_test(case.poc_id)
        start = datetime.now(timezone.utc)
        try:
            result = case.run_fn(self.config, self.az)
            if not isinstance(result, TestResult):  # defensive
                raise TypeError(
                    f"{case.poc_id} run_fn returned {type(result)}, expected TestResult"
                )
        except Exception as exc:  # noqa: BLE001 — deliberate catch-all
            duration = (datetime.now(timezone.utc) - start).total_seconds()
            tb = traceback.format_exc()
            result = TestResult(
                poc_id=case.poc_id,
                status="fail",
                actual_result=f"Unhandled exception: {exc}",
                error=tb,
                duration_seconds=duration,
            )

        # Ensure duration is populated.
        if not result.duration_seconds:
            result.duration_seconds = (datetime.now(timezone.utc) - start).total_seconds()

        self.store.record(result)
        dur = result.duration_seconds
        if result.status == "pass":
            print(f"[PASS] {case.poc_id} ({dur:.1f}s)")
        elif result.status == "fail":
            print(f"[FAIL] {case.poc_id} ({dur:.1f}s) — {result.actual_result[:120]}")
        elif result.status == "blocked":
            print(f"[BLOCKED] {case.poc_id} ({dur:.1f}s) — {result.actual_result[:120]}")
        else:
            print(f"[{result.status.upper()}] {case.poc_id} ({dur:.1f}s)")
        return result

    def run_cases(self, cases: List[TestCase]) -> List[TestResult]:
        """Execute a list of cases in order and return their results."""
        results = []
        for case in cases:
            results.append(self.run_case(case))
        return results


def build_registry() -> Registry:
    """Populate and return the global registry (idempotent)."""
    if not REGISTRY.all():
        _register_all()
    return REGISTRY


# Helper used by test modules to build a standard evidence dict entry.
def make_cleanup_note(command: str) -> Dict[str, Any]:
    """Return a standard cleanup evidence fragment for resource-creating tests."""
    return {"cleanup_required": True, "cleanup_command": command}
