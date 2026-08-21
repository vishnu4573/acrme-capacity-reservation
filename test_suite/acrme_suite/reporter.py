"""Report generation for the ACRME POC suite.

Produces three artefacts per run:
    * ``report_<run_id>.html`` — self-contained styled HTML report
    * ``report_<run_id>.md``   — Markdown summary
    * ``phase_gate_<run_id>.json`` — phase-gate evaluation result
"""

from __future__ import annotations

import html
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .runner_core import (
    PHASE_GATE_REQUIREMENTS,
    Registry,
    cumulative_gate_requirements,
)

STATUS_COLORS = {
    "pass": "#1b7f37",
    "fail": "#b3261e",
    "blocked": "#c77700",
    "skipped": "#666666",
    "not_run": "#999999",
}
STATUS_BG = {
    "pass": "#e6f4ea",
    "fail": "#fbe9e7",
    "blocked": "#fff4e5",
    "skipped": "#f0f0f0",
    "not_run": "#f7f7f7",
}


class Reporter:
    """Generates HTML, Markdown, and phase-gate JSON reports."""

    def __init__(
        self,
        metadata: Dict[str, Any],
        results: List[Dict[str, Any]],
        registry: Optional[Registry] = None,
        report_dir: str = "reports",
    ) -> None:
        self.metadata = metadata
        self.results = results
        self.registry = registry
        self.report_dir = report_dir
        os.makedirs(self.report_dir, exist_ok=True)
        self.run_id = metadata.get("run_id", "unknown")
        self._by_id = {r["poc_id"]: r for r in results}

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------
    def _counts(self) -> Dict[str, int]:
        counts = {"pass": 0, "fail": 0, "blocked": 0, "skipped": 0, "not_run": 0}
        for r in self.results:
            counts[r.get("status", "not_run")] = counts.get(r.get("status", "not_run"), 0) + 1
        return counts

    def _total_duration(self) -> float:
        return sum(float(r.get("duration_seconds", 0) or 0) for r in self.results)

    def _group_of(self, poc_id: str) -> str:
        if self.registry:
            case = self.registry.get(poc_id)
            if case:
                return case.group
        return "?"

    def _grouped_results(self) -> Dict[str, List[Dict[str, Any]]]:
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for r in self.results:
            grouped.setdefault(self._group_of(r["poc_id"]), []).append(r)
        return grouped

    # ------------------------------------------------------------------
    # Phase gate evaluation
    # ------------------------------------------------------------------
    def evaluate_phase_gates(self) -> Dict[str, Any]:
        """Evaluate every phase gate against current results."""
        evaluation: Dict[str, Any] = {
            "run_id": self.run_id,
            "configured_gate": self.metadata.get("phase_gate"),
            "generated": datetime.now(timezone.utc).isoformat(),
            "gates": {},
        }
        for gate in ("phase1", "phase2", "production"):
            required = cumulative_gate_requirements(gate)
            items = []
            gate_pass = True
            for poc_id in required:
                status = self._by_id.get(poc_id, {}).get("status", "not_run")
                item_ok = status == "pass"
                if not item_ok:
                    gate_pass = False
                items.append({"poc_id": poc_id, "status": status, "satisfied": item_ok})
            evaluation["gates"][gate] = {
                "required_count": len(required),
                "passed_count": sum(1 for i in items if i["satisfied"]),
                "gate_satisfied": gate_pass,
                "items": items,
            }
        return evaluation

    # ------------------------------------------------------------------
    # Writers
    # ------------------------------------------------------------------
    def write_all(self) -> Dict[str, str]:
        """Generate all three report artefacts and return their paths."""
        gate_eval = self.evaluate_phase_gates()
        paths = {
            "html": self._write_html(gate_eval),
            "md": self._write_md(gate_eval),
            "phase_gate": self._write_phase_gate_json(gate_eval),
        }
        return paths

    def _write_phase_gate_json(self, gate_eval: Dict[str, Any]) -> str:
        path = os.path.join(self.report_dir, f"phase_gate_{self.run_id}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(gate_eval, fh, indent=2)
        return path

    def _write_md(self, gate_eval: Dict[str, Any]) -> str:
        counts = self._counts()
        lines: List[str] = []
        lines.append(f"# ACRME POC Test Report — Run `{self.run_id}`")
        lines.append("")
        lines.append(f"- **Date:** {self.metadata.get('start_time', '?')}")
        lines.append(f"- **Phase gate:** {self.metadata.get('phase_gate', '?')}")
        lines.append(f"- **Dry run:** {self.metadata.get('dry_run', False)}")
        lines.append(f"- **Total duration:** {self._total_duration():.1f}s")
        lines.append("")
        lines.append("## Summary")
        lines.append("")
        lines.append("| Status | Count |")
        lines.append("|---|---|")
        for status in ("pass", "fail", "blocked", "skipped", "not_run"):
            lines.append(f"| {status} | {counts.get(status, 0)} |")
        lines.append("")

        lines.append("## Phase Gate Evaluation")
        lines.append("")
        for gate, data in gate_eval["gates"].items():
            verdict = "✅ SATISFIED" if data["gate_satisfied"] else "❌ NOT SATISFIED"
            lines.append(
                f"### {gate} — {verdict} "
                f"({data['passed_count']}/{data['required_count']})"
            )
            lines.append("")
            lines.append("| POC | Status |")
            lines.append("|---|---|")
            for item in data["items"]:
                mark = "✅" if item["satisfied"] else "⛔"
                lines.append(f"| {item['poc_id']} | {mark} {item['status']} |")
            lines.append("")

        lines.append("## Results by Group")
        lines.append("")
        for group, rows in self._grouped_results().items():
            lines.append(f"### {group}")
            lines.append("")
            lines.append("| POC | Status | Duration (s) | Result |")
            lines.append("|---|---|---|---|")
            for r in rows:
                result_txt = (r.get("actual_result") or "").replace("|", "\\|")[:140]
                lines.append(
                    f"| {r['poc_id']} | {r.get('status')} | "
                    f"{float(r.get('duration_seconds', 0) or 0):.1f} | {result_txt} |"
                )
            lines.append("")

        blockers = [r for r in self.results if r.get("status") in ("fail", "blocked")]
        if blockers:
            lines.append("## Blockers & Failures")
            lines.append("")
            for r in blockers:
                lines.append(
                    f"- **{r['poc_id']}** ({r.get('status')}): "
                    f"{(r.get('actual_result') or r.get('error') or '')[:300]}"
                )
            lines.append("")

        path = os.path.join(self.report_dir, f"report_{self.run_id}.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        return path

    def _write_html(self, gate_eval: Dict[str, Any]) -> str:
        counts = self._counts()
        esc = html.escape

        def badge(status: str) -> str:
            color = STATUS_COLORS.get(status, "#333")
            return (
                f'<span style="display:inline-block;padding:2px 8px;border-radius:10px;'
                f'background:{color};color:#fff;font-size:12px;font-weight:600;">'
                f"{esc(status)}</span>"
            )

        parts: List[str] = []
        parts.append("<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>")
        parts.append("<meta name='viewport' content='width=device-width, initial-scale=1'>")
        parts.append(f"<title>ACRME POC Report {esc(self.run_id)}</title>")
        parts.append(
            "<style>"
            "body{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;"
            "margin:0;background:#f5f6f8;color:#1a1a1a;}"
            ".wrap{max-width:1100px;margin:0 auto;padding:24px;}"
            "h1{font-size:24px;margin:0 0 4px;} h2{font-size:19px;margin:28px 0 10px;"
            "border-bottom:2px solid #e0e0e0;padding-bottom:6px;} h3{font-size:16px;margin:18px 0 8px;}"
            ".meta{color:#555;font-size:14px;margin-bottom:12px;}"
            ".cards{display:flex;gap:12px;flex-wrap:wrap;margin:12px 0;}"
            ".card{flex:1;min-width:120px;background:#fff;border-radius:10px;padding:14px 16px;"
            "box-shadow:0 1px 3px rgba(0,0,0,.08);text-align:center;}"
            ".card .n{font-size:28px;font-weight:700;} .card .l{font-size:12px;color:#666;text-transform:uppercase;}"
            "table{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;"
            "box-shadow:0 1px 3px rgba(0,0,0,.06);margin-bottom:8px;}"
            "th,td{text-align:left;padding:9px 12px;font-size:14px;border-bottom:1px solid #eee;vertical-align:top;}"
            "th{background:#fafafa;font-weight:600;}"
            "details{background:#fff;border-radius:6px;margin:4px 0;padding:6px 10px;}"
            "summary{cursor:pointer;font-size:13px;}"
            "pre{background:#0d1117;color:#c9d1d9;padding:10px;border-radius:6px;overflow-x:auto;font-size:12px;}"
            ".gate-ok{color:#1b7f37;font-weight:700;} .gate-no{color:#b3261e;font-weight:700;}"
            ".blockers{background:#fff4f2;border:1px solid #f3c9c2;border-radius:8px;padding:12px 16px;}"
            "</style></head><body><div class='wrap'>"
        )

        parts.append(f"<h1>ACRME POC Test Report</h1>")
        parts.append(
            f"<div class='meta'>Run <code>{esc(self.run_id)}</code> &middot; "
            f"{esc(str(self.metadata.get('start_time', '?')))} &middot; "
            f"Phase gate: <b>{esc(str(self.metadata.get('phase_gate', '?')))}</b> &middot; "
            f"Dry run: {esc(str(self.metadata.get('dry_run', False)))} &middot; "
            f"Total duration: {self._total_duration():.1f}s</div>"
        )

        # Summary cards.
        parts.append("<div class='cards'>")
        for status in ("pass", "fail", "blocked", "skipped", "not_run"):
            parts.append(
                f"<div class='card'><div class='n' style='color:{STATUS_COLORS[status]}'>"
                f"{counts.get(status, 0)}</div><div class='l'>{status}</div></div>"
            )
        parts.append("</div>")

        # Phase gate evaluation.
        parts.append("<h2>Phase Gate Evaluation</h2>")
        for gate, data in gate_eval["gates"].items():
            cls = "gate-ok" if data["gate_satisfied"] else "gate-no"
            verdict = "SATISFIED" if data["gate_satisfied"] else "NOT SATISFIED"
            parts.append(
                f"<h3>{esc(gate)} — <span class='{cls}'>{verdict}</span> "
                f"({data['passed_count']}/{data['required_count']})</h3>"
            )
            parts.append("<table><tr><th>POC</th><th>Status</th></tr>")
            for item in data["items"]:
                parts.append(
                    f"<tr><td>{esc(item['poc_id'])}</td><td>{badge(item['status'])}</td></tr>"
                )
            parts.append("</table>")

        # Results by group.
        parts.append("<h2>Results by Group</h2>")
        for group, rows in self._grouped_results().items():
            parts.append(f"<h3>{esc(group)}</h3>")
            parts.append(
                "<table><tr><th>POC</th><th>Status</th><th>Duration</th>"
                "<th>Result</th></tr>"
            )
            for r in rows:
                status = r.get("status", "not_run")
                bg = STATUS_BG.get(status, "#fff")
                parts.append(
                    f"<tr style='background:{bg}'><td><b>{esc(r['poc_id'])}</b></td>"
                    f"<td>{badge(status)}</td>"
                    f"<td>{float(r.get('duration_seconds', 0) or 0):.1f}s</td>"
                    f"<td>{esc((r.get('actual_result') or '')[:220])}</td></tr>"
                )
                # Expandable evidence detail.
                evidence_json = json.dumps(r.get("evidence", {}), indent=2)[:6000]
                err = r.get("error")
                detail_inner = f"<pre>{esc(evidence_json)}</pre>"
                if err:
                    detail_inner += f"<b>Error:</b><pre>{esc(str(err)[:3000])}</pre>"
                parts.append(
                    "<tr><td colspan='4'><details><summary>Evidence &amp; detail</summary>"
                    f"{detail_inner}</details></td></tr>"
                )
            parts.append("</table>")

        # Blockers section.
        blockers = [r for r in self.results if r.get("status") in ("fail", "blocked")]
        parts.append("<h2>Blockers &amp; Failures</h2>")
        if blockers:
            parts.append("<div class='blockers'><ul>")
            for r in blockers:
                reason = (r.get("actual_result") or r.get("error") or "")[:400]
                parts.append(
                    f"<li><b>{esc(r['poc_id'])}</b> ({esc(r.get('status', ''))}): "
                    f"{esc(reason)}</li>"
                )
            parts.append("</ul></div>")
        else:
            parts.append("<p>No blockers or failures recorded. 🎉</p>")

        parts.append("</div></body></html>")

        path = os.path.join(self.report_dir, f"report_{self.run_id}.html")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("".join(parts))
        return path
