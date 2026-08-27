#!/usr/bin/env python3
"""Split the combined ACRME ADR document into four standalone ADR files.

Each output file is fully self-contained: per-ADR metadata header, the ADR body
(verbatim from the combined source, preserving all normative detail), a
Related-ADRs cross-reference, and the shared appendices (Decision Log row for
that ADR, Status Legend, Evidence Tag Taxonomy).
"""
import re
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent
SRC = DOCS / "acrme_architecture_decision_records.md"
OUT = DOCS / "adr"
OUT.mkdir(exist_ok=True)

text = SRC.read_text(encoding="utf-8")
lines = text.splitlines()

# Locate ADR section headings and the first appendix (end boundary).
headings = {}
appendix_a_start = None
for i, ln in enumerate(lines):
    m = re.match(r"^## (ADR-00\d) — (.+)$", ln)
    if m:
        headings[m.group(1)] = (i, m.group(2).strip())
    if ln.startswith("## Appendix A"):
        appendix_a_start = i

order = ["ADR-001", "ADR-002", "ADR-003", "ADR-004"]
bounds = {}
for idx, adr in enumerate(order):
    start = headings[adr][0]
    end = headings[order[idx + 1]][0] if idx + 1 < len(order) else appendix_a_start
    bounds[adr] = (start, end)

# Shared appendices (Status Legend + Evidence Tag Taxonomy) reused per file.
status_legend = """## Appendix — Status Legend

| Status | Meaning |
|---|---|
| **Proposed** | Under discussion; not yet ratified |
| **Accepted** | Ratified and in force |
| **Deprecated** | No longer recommended but not yet replaced |
| **Superseded** | Replaced by a later ADR |

## Appendix — Evidence Tag Taxonomy

| Tag | Meaning |
|---|---|
| `[Documented]` | Traceable to Azure platform behaviour or documentation |
| `[Decided]` | An explicit ACRME design choice recorded in this ADR set |
| `[Derived]` | A logical consequence of a documented constraint or decision |
| `[Assumed]` | Architectural judgement pending proof-of-concept validation |
"""

# Per-ADR summary rows (self-contained; no external tracking codes).
decision_log = {
    "ADR-001": "| ADR-001 Region Selection | HC-1, HC-4, HC-5, HC-8, HC-9, HC-10 | Worked scoring examples pending final per-CRG-type inputs |",
    "ADR-002": "| ADR-002 Quota & Capacity | HC-2, HC-3, HC-7 | Azure Quota Groups GA validated by proof-of-concept before rollout |",
    "ADR-003": "| ADR-003 Capacity during DR | HC-1, HC-4, HC-6 | Consumer-credential model and engine-mode state machine; quota-release latency measured |",
    "ADR-004": "| ADR-004 Forecast & Increase | HC-3 (at execution) | Workload-tagged forecasts; `CapacityIncreaseRequest` lifecycle end-to-end test |",
}

titles = {a: headings[a][1] for a in order}
slug = {
    "ADR-001": "acrme_adr_001_region_selection",
    "ADR-002": "acrme_adr_002_quota_and_capacity_management",
    "ADR-003": "acrme_adr_003_capacity_management_during_dr",
    "ADR-004": "acrme_adr_004_forecast_and_increase_of_capacity_and_quota",
}

for adr in order:
    s, e = bounds[adr]
    # Body: convert the top-level "## ADR-00X — Title" into an H1 for a standalone doc,
    # and demote the inner "### " sub-sections stay as-is (they already sit under H1).
    body_lines = lines[s:e]
    # Drop trailing blank lines
    while body_lines and body_lines[-1].strip() == "":
        body_lines.pop()
    body = "\n".join(body_lines)
    # Promote the ADR heading to H1.
    body = re.sub(r"^## (ADR-00\d — .+)$", r"# \1", body, count=1, flags=re.M)
    # Diagram images live in docs/adr/diagrams/; rewrite the docs-relative path
    # (adr/diagrams/...) used by the consolidated doc to the adr-local path.
    body = body.replace("](adr/diagrams/", "](diagrams/")
    # Renumber figures per-document, starting at 1, so each standalone ADR is
    # self-contained (the consolidated doc numbers figures 1..6 across all ADRs).
    _fig_counter = [0]

    def _renumber_fig(m):
        _fig_counter[0] += 1
        return f"**Figure {_fig_counter[0]}.**"

    body = re.sub(r"\*\*Figure \d+\.\*\*", _renumber_fig, body)

    # Related-ADRs list (all others).
    related = "\n".join(
        f"- **{o} — {titles[o]}** (`{slug[o]}.md`)"
        for o in order if o != adr
    )

    header = f"""**Project:** Azure Capacity Reservation Management Engine (ACRME)  
**Classification:** Principal Cloud Architect — Architecture Governance  
**Version:** 1.2  
**Date:** August 2026  
**Status:** Accepted  
**Part of:** ACRME Architecture Decision Records — one of four standalone, self-contained records.

> **About ADRs.** An Architecture Decision Record captures a single significant architectural decision, the context that forced it, the options considered, the choice made, and its consequences. ADRs are immutable once accepted — a superseding decision is recorded as a new ADR rather than editing the original. This record is self-contained: it can be read without any companion document. Evidence tags: `[Documented]`, `[Decided]`, `[Derived]`, `[Assumed]` (see Appendix).

---

"""

    footer = f"""

---

## Appendix — ADR Summary

| ADR | Hard Constraints Applied | Key Open Items |
|---|---|---|
{decision_log[adr]}

{status_legend}
## Related ADRs

{related}

---

**Document Status:** Accepted  
**Next Review:** After proof-of-concept validation of Azure Quota Groups GA and quota-release latency, and on resolution of the consumer-credential model and engine-mode state-machine items.
"""

    out_path = OUT / f"{slug[adr]}.md"
    out_path.write_text(header + body + footer + "\n", encoding="utf-8")
    print(f"wrote {out_path.name} ({len(body.splitlines())} body lines)")
