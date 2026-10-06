---
name: grounding-acrme-research-design
description: Grounds any ACRME (Azure Capacity & Quota Management / capacity-reservation engine) research or design work in the current requirements baseline, Microsoft Learn, and the repo's decided artefacts. Resolves which baseline version is current, maps the question to the authoritative sources, enforces evidence tags (Documented/Tested/Decided/Derived/Assumed), surfaces open POCs and spec gaps as blockers, runs baseline/HC/formula/DR/WAF gates, and lints the output before delivery. Use when researching Azure Capacity Reservations, CRGs, quota groups, zones, sharing, region placement, scoring (PS_Prod/PS_NonProd/PS_DR), DR sizing, or when drafting or revising any ACRME design note, ADR, reference doc, or mockup logic.
---

# Grounding ACRME research & design

Procedure that keeps every ACRME research finding and design output traceable to an authoritative source. It does not restate requirements — it tells you where they live, how to rank them, and what must be checked before anything is delivered.

Repo: `vishnu4573/acrme-capacity-reservation` (branch `master`), local clone `/home/ubuntu/acrme-capacity-reservation`. All paths below are repo-relative.

## Workflow

Run the steps in order. Do not draft any output before Step 3 is complete.

### Step 0 — Resolve the current baseline (never assume the version)
```bash
python3 .github/skills/grounding-acrme-research-design/scripts/check_grounding.py --baseline-only
```
The script reads the Document Control `Version` row of every baseline candidate (repo `Requirements/acrme_requirements_baseline_v*.md` and the uploaded copy under `/home/ubuntu/Uploads/`) and reports the highest. **The filename is not the version** — `acrme_requirements_baseline_v2_4.md` currently carries v2.5. If the candidates disagree, use the highest version, state the drift in your output, and do not cite the stale copy.

Then read, from the current baseline: Version History (top rows since the last version you knew), §2 Strategic Drivers, §3 Design Principles, §23 Pending Decisions & POCs, and every section mapped to your topic in `references/source-map.md`.

### Step 1 — Classify the ask
Pick one: **Research** (what does Azure/the baseline say?), **Design** (new or changed mechanism), **Formula** (scoring, sizing, headroom), **Review** (check an existing doc). Name the delivery phase(s) touched (baseline §21: P1 Visibility & Prod Protection, P2 Quota Pool, P3 Placement & Seed, P4 Distributed DR) and note downstream phase impact — a Phase 1 change can break Phase 4 DR assumptions.

### Step 2 — Load sources by rank
Use `references/source-map.md` to find the exact files and sections. Rank when sources disagree:
1. Microsoft Learn / Azure docs (platform behaviour)
2. Current requirements baseline (programme requirements and decisions)
3. Accepted ADRs in `Architecture/adr/` and the hard-constraints reference
4. Calculation logic reference (formulas and constants)
5. Design docs, walkthroughs, mockups, POC workbook
6. Prior conversation context or memory — never sufficient on its own

A higher-rank source wins. If Microsoft Learn contradicts the baseline, do not silently pick one: report the conflict as a baseline-change candidate.

### Step 3 — Research and tag every claim
Apply the tag rules and check the open-items register in `references/evidence-and-gaps.md`. Hard rules:
- Every Azure-behaviour claim carries a tag and, for `[Documented]`, a Learn URL or baseline code.
- Any formula term without a defined source, scope, and data type is a **spec gap** — flag it as a blocker, never invent a definition (e.g. `total_customers` in γ).
- Preview features (Capacity Reservation Sharing, DEP-001) are never a production dependency.
- Prefer Microsoft Learn via `web_search` / `scrape_url_content`; record the URL and access date.

### Step 4 — Design within the guardrails
Constraints that cannot be relaxed without a new ADR plus business approval:
- Hard constraints HC-1..HC-11 as defined in `Reference-Material/reference/acrme_hard_constraints_reference.md` (Part 2 summary table is authoritative for HC numbering).
- Baseline §3 design principles (production first, allocated-drives-reservations, lean DR bootstrap, max-not-sum DR sizing, zero-not-delete, config-driven policy).
- Rejected directions: multi-cloud DR, large fixed DR reserve, region hard-bound to an environment, Bicep for engine runtime logic.

### Step 5 — Gate the output
Produce the gate block from `references/output-templates.md`:
- **Baseline compliance** (SK-01 in `Skills.md`): ALIGNED / CONFLICT / NOT COVERED / EXTENDS per code. Any CONFLICT blocks.
- **Hard constraints**: PASS / FAIL / N/A for HC-1..HC-11. Any FAIL blocks.
- **Formula check** (SK-06) when capacity, quota, scoring, or DR numbers change — recompute one worked example.
- **DR sizing** (SK-09) when DR is touched — max-not-sum across non-concurrent sources.
- **WAF** five pillars (SK-02) for any architecture decision.

### Step 6 — Write the output from a template
Use the Research Brief or Design Note template in `references/output-templates.md`. Normative detail (state machines, formulas, tables, validation rules) — not summaries.

### Step 7 — Lint before delivery
```bash
python3 .github/skills/grounding-acrme-research-design/scripts/check_grounding.py path/to/output.md
```
Fix every ERROR. Review every WARN and either fix it or justify it in the doc. Exit code 0 = no errors.

### Step 8 — Publish
- Place docs by type: `Reference-Material/reference/` (reference), `Design/` (design), `Architecture/adr/` (ADRs), `Mockups/` (what-if workbooks + builder scripts).
- Write `.md` only — `.docx`/`.pdf` twins are auto-generated; do not hand-build them.
- Never edit the baseline directly; propose changes as an ADR or baseline-change note.
- Commit with a conventional message (`docs(reference): …`, `docs(adr): …`), `git pull --rebase origin master` before push.

## Reference files
- `references/source-map.md` — topic → baseline section → codes → repo artefact.
- `references/evidence-and-gaps.md` — evidence tag rules, locked Azure facts, open POC/decision/gap register.
- `references/output-templates.md` — Research Brief, Design Note, gate block, WAF block.
- `scripts/check_grounding.py` — baseline resolver and output linter (stdlib only, Python 3.8+).

## Related
- `Agents.md` (Agent 1 — Architect) and `.github/agents/acrme-research-designer.agent.md` — the agent persona that runs this skill.
- `Skills.md` SK-01/02/03/06/09 — the gate procedures invoked in Step 5.
- `Reference-Material/reference/acrme_research_and_design_prompt.md` — long-form onboarding context; this skill is the executable procedure.
