#!/usr/bin/env python3
"""Generate the Jira-importable CSV backlog from backlog_data.py.

Output: acrme_backlog_jira_import.csv

Import scheme
-------------
One row per issue (Epic, Story, Sub-task). Hierarchy is expressed with two
columns so Jira's CSV importer can link everything in a single pass:

- "Epic Link"  -> put the Epic's key on each Story so Jira nests stories
                  under the epic.
- "Parent ID"  -> the external ID of the parent issue; combined with
                  "Issue ID" it lets the importer map Story->Sub-task links.

During the Jira import wizard, map:
  Issue ID   -> "Issue ID" (external id used for linking)
  Parent ID  -> "Parent ID"
  Epic Name  -> the epic-name field (required for Epic rows)
  Epic Link  -> the epic-link field (used on Story rows)
"""
import csv
import os
from backlog_data import EPICS

OUT = os.path.join(os.path.dirname(__file__), "acrme_backlog_jira_import.csv")

FIELDS = [
    "Issue Type",
    "Issue ID",
    "Parent ID",
    "Epic Link",
    "Epic Name",
    "Summary",
    "Priority",
    "Story Points",
    "Phase",
    "Labels",
    "PRR Refs",
    "Description",
    "Acceptance Criteria",
]


def story_description(s):
    return (f"As a {s['as_a']}, I want {s['i_want']}, so that {s['so_that']}.")


def main():
    rows = []
    for e in EPICS:
        # Epic row
        rows.append({
            "Issue Type": "Epic",
            "Issue ID": e["id"],
            "Parent ID": "",
            "Epic Link": "",
            "Epic Name": e["name"],
            "Summary": e["name"],
            "Priority": "",
            "Story Points": "",
            "Phase": "",
            "Labels": "ACRME",
            "PRR Refs": "; ".join(e["prr_refs"]),
            "Description": e["goal"],
            "Acceptance Criteria": "",
        })
        for s in e["stories"]:
            labels = " ".join(["ACRME", s["phase"]])
            rows.append({
                "Issue Type": "Story",
                "Issue ID": s["id"],
                "Parent ID": e["id"],
                "Epic Link": e["id"],
                "Epic Name": "",
                "Summary": s["title"],
                "Priority": s["priority"],
                "Story Points": s["points"],
                "Phase": s["phase"],
                "Labels": labels,
                "PRR Refs": "; ".join(s["prr_refs"]),
                "Description": story_description(s)
                + (f"\n\nDepends on: {', '.join(s['depends_on'])}"
                   if s["depends_on"] else ""),
                "Acceptance Criteria": "\n".join(f"- {a}" for a in s["acceptance"]),
            })
            for t in s["tasks"]:
                note = f" — {t['note']}" if t.get("note") else ""
                rows.append({
                    "Issue Type": "Sub-task",
                    "Issue ID": t["id"],
                    "Parent ID": s["id"],
                    "Epic Link": e["id"],
                    "Epic Name": "",
                    "Summary": t["title"] + note,
                    "Priority": s["priority"],
                    "Story Points": "",
                    "Phase": s["phase"],
                    "Labels": " ".join(["ACRME", s["phase"]]),
                    "PRR Refs": "",
                    "Description": "",
                    "Acceptance Criteria": "",
                })

    with open(OUT, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=FIELDS, quoting=csv.QUOTE_ALL)
        wr.writeheader()
        wr.writerows(rows)

    n_epic = sum(1 for r in rows if r["Issue Type"] == "Epic")
    n_story = sum(1 for r in rows if r["Issue Type"] == "Story")
    n_task = sum(1 for r in rows if r["Issue Type"] == "Sub-task")
    print(f"Wrote {OUT}")
    print(f"  {len(rows)} rows -> {n_epic} epics, {n_story} stories, {n_task} sub-tasks")


if __name__ == "__main__":
    main()
