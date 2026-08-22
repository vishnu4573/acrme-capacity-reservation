#!/usr/bin/env python3
"""Generate the human-readable Markdown backlog from backlog_data.py.

Output: acrme_epics_stories_tasks.md
"""
import os
from datetime import date
from backlog_data import EPICS

OUT = os.path.join(os.path.dirname(__file__), "acrme_epics_stories_tasks.md")


def rollup():
    n_epics = len(EPICS)
    n_stories = sum(len(e["stories"]) for e in EPICS)
    n_tasks = sum(len(s["tasks"]) for e in EPICS for s in e["stories"])
    points = sum(s["points"] for e in EPICS for s in e["stories"])
    by_phase = {}
    for e in EPICS:
        for s in e["stories"]:
            by_phase.setdefault(s["phase"], {"stories": 0, "points": 0})
            by_phase[s["phase"]]["stories"] += 1
            by_phase[s["phase"]]["points"] += s["points"]
    return n_epics, n_stories, n_tasks, points, by_phase


def main():
    n_epics, n_stories, n_tasks, points, by_phase = rollup()
    L = []
    w = L.append

    w("# ACRME — Epic / Story / Task Backlog\n")
    w("**Azure Capacity Reservation Management Engine (ACRME)**  ")
    w(f"_Generated {date.today().isoformat()} from the Production-Readiness Review & Final Architecture (PRR)._\n")
    w("> Single source of truth: [`backlog_data.py`](./backlog_data.py). "
      "This Markdown and the [Jira import CSV](./acrme_backlog_jira_import.csv) "
      "are both generated from it, so they never drift.\n")

    # ---- Summary ----------------------------------------------------------
    w("## 1. Backlog Summary\n")
    w("| Metric | Value |")
    w("|---|---|")
    w(f"| Epics | {n_epics} |")
    w(f"| Stories | {n_stories} |")
    w(f"| Tasks | {n_tasks} |")
    w(f"| Total story points | {points} |")
    w("")
    w("### Points & stories by delivery phase\n")
    w("| Phase | Meaning | Stories | Story points |")
    w("|---|---|---|---|")
    phase_meaning = {
        "P1": "Pilot — foundation, manual-assist, single/few regions",
        "P2": "Controlled automation — scoring, sharing, quota, multi-region",
        "P3": "Production / Future — DR, tier escalation, full governance",
    }
    for ph in ("P1", "P2", "P3"):
        if ph in by_phase:
            w(f"| {ph} | {phase_meaning.get(ph,'')} | "
              f"{by_phase[ph]['stories']} | {by_phase[ph]['points']} |")
    w("")

    # ---- Legend -----------------------------------------------------------
    w("## 2. Legend & Conventions\n")
    w("- **ID scheme** — Epics `ACRME-E##`, Stories `ACRME-S####`, Tasks `ACRME-T######`.")
    w("- **Priority** — Highest / High / Medium / Low (Jira default names).")
    w("- **Points** — Fibonacci story points (1, 2, 3, 5, 8, 13).")
    w("- **Phase** — P1 Pilot · P2 Controlled automation · P3 Production/Future.")
    w("- **PRR refs** — sections of the Production-Readiness Review & Architecture that drive the item.")
    w("- **Depends on** — upstream stories that must land first.")
    w("")

    # ---- Epic index -------------------------------------------------------
    w("## 3. Epic Index\n")
    w("| Epic | Name | Stories | Points |")
    w("|---|---|---|---|")
    for e in EPICS:
        ep_pts = sum(s["points"] for s in e["stories"])
        w(f"| {e['id']} | {e['name']} | {len(e['stories'])} | {ep_pts} |")
    w("")

    # ---- Detail -----------------------------------------------------------
    w("## 4. Epics, Stories & Tasks\n")
    for e in EPICS:
        ep_pts = sum(s["points"] for s in e["stories"])
        w(f"### {e['id']} — {e['name']}\n")
        w(f"**Goal.** {e['goal']}\n")
        w(f"**PRR references.** {', '.join(e['prr_refs'])}  ")
        w(f"**Rollup.** {len(e['stories'])} stories · {ep_pts} points\n")

        # story table
        w("| Story | Title | Priority | Points | Phase | Depends on |")
        w("|---|---|---|---|---|---|")
        for s in e["stories"]:
            dep = ", ".join(s["depends_on"]) if s["depends_on"] else "—"
            w(f"| {s['id']} | {s['title']} | {s['priority']} | "
              f"{s['points']} | {s['phase']} | {dep} |")
        w("")

        # per-story detail
        for s in e["stories"]:
            w(f"#### {s['id']} — {s['title']}\n")
            w(f"> **As a** {s['as_a']}, **I want** {s['i_want']}, "
              f"**so that** {s['so_that']}.\n")
            dep = ", ".join(s["depends_on"]) if s["depends_on"] else "—"
            w(f"- **Priority:** {s['priority']} · **Points:** {s['points']} · "
              f"**Phase:** {s['phase']}")
            w(f"- **PRR refs:** {', '.join(s['prr_refs'])}")
            w(f"- **Depends on:** {dep}")
            w("")
            w("**Acceptance criteria**\n")
            for a in s["acceptance"]:
                w(f"- {a}")
            w("")
            w("**Tasks**\n")
            for t in s["tasks"]:
                note = f" — {t['note']}" if t.get("note") else ""
                w(f"- [ ] `{t['id']}` {t['title']}{note}")
            w("")

    with open(OUT, "w") as f:
        f.write("\n".join(L) + "\n")
    print(f"Wrote {OUT}")
    print(f"  {n_epics} epics, {n_stories} stories, {n_tasks} tasks, {points} points")


if __name__ == "__main__":
    main()
