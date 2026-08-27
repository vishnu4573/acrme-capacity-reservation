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
| **Superseded** | Replaced by a later ADR (referenced explicitly) |

## Appendix — Evidence Tag Taxonomy

| Tag | Meaning |
|---|---|
| `[Documented]` | Traceable to Azure platform documentation or a formal FR/NFR |
| `[Decided]` | Explicit design choice in the Decision Log (D1–D11) |
| `[Derived]` | Logical consequence of a documented constraint or decision |
| `[Assumed]` | Architectural judgement pending POC validation |
"""

# Per-ADR Decision Log cross-reference rows (from combined Appendix A).
decision_log = {
    "ADR-001": "| ADR-001 Region Selection | D1, D4, D5, D8, D9 | HC-1, HC-4, HC-5, HC-8, HC-9, HC-10 | G-7 (worked examples) |",
    "ADR-002": "| ADR-002 Quota & Capacity | D6, D7, D9 | HC-2, HC-3, HC-7 | B-1 (Quota Groups GA, POC-30) |",
    "ADR-003": "| ADR-003 Capacity during DR | D8, D10, D11 | HC-1, HC-4, HC-6 | G-14 (credential), G-15 (engine mode), B-2 (POC-31) |",
    "ADR-004": "| ADR-004 Forecast & Increase | D10 | — (uses HC-3 at execution) | G-16 (workload tags), G-24 (increase entity) |",
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

    # Related-ADRs list (all others).
    related = "\n".join(
        f"- **{o} — {titles[o]}** (`{slug[o]}.md`)"
        for o in order if o != adr
    )

    header = f"""**Project:** Azure Capacity Reservation Management Engine (ACRME)  
**Classification:** Principal Cloud Architect — Architecture Governance  
**Version:** 1.1  
**Date:** August 2026  
**Status:** Accepted  
**Part of:** ACRME Architecture Decision Records — this is one of four standalone ADRs split from the consolidated ADR set.

> **About ADRs.** An Architecture Decision Record captures a single significant architectural decision, the context that forced it, the options considered, the choice made, and its consequences. ADRs are immutable once accepted — a superseding decision is recorded as a new ADR rather than editing the original. Evidence tags: `[Documented]`, `[Decided]`, `[Derived]`, `[Assumed]` (see Appendix).

---

"""

    footer = f"""

---

## Appendix — Decision Log Cross-Reference

| ADR | Primary Decisions | Hard Constraints | Key Gaps/Blockers |
|---|---|---|---|
{decision_log[adr]}

{status_legend}
## Related ADRs

{related}

---

**Document Status:** Accepted  
**Next Review:** After POC-30 (Quota Groups GA) and POC-31 (quota release latency), and on resolution of G-14 / G-15.
"""

    out_path = OUT / f"{slug[adr]}.md"
    out_path.write_text(header + body + footer + "\n", encoding="utf-8")
    print(f"wrote {out_path.name} ({len(body.splitlines())} body lines)")
