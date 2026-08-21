"""Persistent JSON result store for the ACRME POC suite.

Results are written to ``reports/results_<run_id>.json`` after every test so a
run can be resumed after interruption. The store also holds run metadata (run
id, start time, phase gate, and a config snapshot) used by the reporter.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _serialise(obj: Any) -> Any:
    """Best-effort conversion of dataclasses/objects to JSON-friendly data."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    return obj


class ResultStore:
    """Append-only JSON persistence for TestResult records + run metadata."""

    def __init__(self, run_id: str, report_dir: str = "reports") -> None:
        self.run_id = run_id
        self.report_dir = report_dir
        os.makedirs(self.report_dir, exist_ok=True)
        self.path = os.path.join(self.report_dir, f"results_{run_id}.json")
        self._metadata: Dict[str, Any] = {}
        self._results: Dict[str, Dict[str, Any]] = {}
        if os.path.exists(self.path):
            self._load()

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------
    @classmethod
    def new_run(
        cls,
        report_dir: str,
        phase_gate: str,
        config_snapshot: Dict[str, Any],
        dry_run: bool = False,
    ) -> "ResultStore":
        """Create a brand-new run with a fresh UUID and initial metadata."""
        run_id = uuid.uuid4().hex[:12]
        store = cls(run_id=run_id, report_dir=report_dir)
        store._metadata = {
            "run_id": run_id,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "phase_gate": phase_gate,
            "dry_run": dry_run,
            "config_snapshot": config_snapshot,
        }
        store._flush()
        return store

    @classmethod
    def latest_run_id(cls, report_dir: str = "reports") -> Optional[str]:
        """Return the run_id of the most recently modified results file, if any."""
        if not os.path.isdir(report_dir):
            return None
        candidates = [
            f for f in os.listdir(report_dir)
            if f.startswith("results_") and f.endswith(".json")
        ]
        if not candidates:
            return None
        candidates.sort(
            key=lambda f: os.path.getmtime(os.path.join(report_dir, f)),
            reverse=True,
        )
        newest = candidates[0]
        return newest[len("results_"):-len(".json")]

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load(self) -> None:
        with open(self.path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        self._metadata = payload.get("metadata", {})
        for rec in payload.get("results", []):
            self._results[rec["poc_id"]] = rec

    def _flush(self) -> None:
        payload = {
            "metadata": self._metadata,
            "results": list(self._results.values()),
        }
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, default=_serialise)
        os.replace(tmp, self.path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def record(self, result: Any) -> None:
        """Persist a TestResult (dataclass or dict), keyed by poc_id."""
        rec = asdict(result) if is_dataclass(result) and not isinstance(result, type) else dict(result)
        self._results[rec["poc_id"]] = rec
        self._flush()

    def get_status(self, poc_id: str) -> Optional[str]:
        """Return the recorded status for *poc_id*, or None if not yet run."""
        rec = self._results.get(poc_id)
        return rec.get("status") if rec else None

    def get_result(self, poc_id: str) -> Optional[Dict[str, Any]]:
        """Return the full recorded result dict for *poc_id*, or None."""
        return self._results.get(poc_id)

    def all_results(self) -> List[Dict[str, Any]]:
        """Return all recorded results as a list of dicts."""
        return list(self._results.values())

    @property
    def metadata(self) -> Dict[str, Any]:
        """Run metadata dictionary."""
        return self._metadata

    def get_evidence(self, poc_id: str) -> Dict[str, Any]:
        """Return the evidence dict of a prior result (empty dict if none)."""
        rec = self._results.get(poc_id)
        return (rec or {}).get("evidence", {}) or {}

    def mark_finished(self) -> None:
        """Record the run end time."""
        self._metadata["end_time"] = datetime.now(timezone.utc).isoformat()
        self._flush()
