---
name: grounding-acrme-research-design
description: Grounds any ACRME (Azure Capacity & Quota Management / capacity-reservation engine) research or design work in the current requirements baseline, Microsoft Learn, and the repo's decided artefacts. Resolves which baseline version is current, maps the question to the authoritative sources, enforces evidence tags (Documented/Tested/Decided/Derived/Assumed), surfaces open POCs and spec gaps as blockers, runs baseline/HC/formula/DR/WAF gates, and lints the output before delivery. Use when researching Azure Capacity Reservations, CRGs, quota groups, zones, sharing, region placement, scoring (PS_Prod/PS_NonProd/PS_DR), DR sizing, or when drafting or revising any ACRME design note, ADR, reference doc, or mockup logic.
---

# Grounding ACRME research & design

Procedure that keeps every ACRME research finding and design output traceable to an authoritative source. It does not restate requirements — it tells you where they live, how to rank them, and what must be checked before anything is delivered.

Repo: `vishnu4573/acrme-capacity-reservation` (branch `master`). All paths below are repo-relative. The grounding checker derives the repository root from its own location, so it can run from any checkout path.

## Workflow

Run the steps in order. Do not draft any output before Step 3 is complete.

### Step 0 — Resolve the current baseline (never assume the version)
```bash
python3 .github/skills/grounding-acrme-research-design/scripts/check_grounding.py --baseline-only
```
The script reads the Document Control `Version` row of every repository baseline candidate (`Requirements/acrme_requirements_baseline_v*.md`) and reports the highest. To include an external/uploaded copy, pass `--uploaded-baseline <path>` or set `ACRME_UPLOADED_BASELINE`; the checker has no host-specific upload path. **The filename is not the version.** If candidates disagree, use the highest version, state the drift in your output, and do not cite the stale copy.

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
- Any formula term without a defined source, scope, and data type is a **spec gap** — flag it as a blocker, never invent a definition. (`total_customers` in γ was such a gap; it is now decided — PLC-012, A.10.)
- Preview features (Capacity Reservation Sharing, DEP-001) are never a production dependency.
- Use Microsoft Learn MCP and Azure MCP for Azure research and fact-checking, following the procedure below.

#### Microsoft Learn and Azure MCP research procedure

1. **Discover tools first.** Search the connected tool catalogue for Microsoft Learn MCP documentation search/fetch and Azure MCP documentation or relevant service guidance. Inspect returned schemas; do not guess tool arguments, child commands, or server prefixes. Multiple Azure MCP aliases may expose the same capability; use one available connection, not every alias.
2. **Search, then fetch.** Use Microsoft Learn MCP `microsoft_docs_search` for the topic, then `microsoft_docs_fetch` for the authoritative pages needed to substantiate the answer. Use `microsoft_code_sample_search` when generating Azure SDK/CLI examples or POC scripts. Read the relevant limitations, prerequisites, and API-version details, not just search snippets.
3. **Cross-check with Azure MCP.** Use its documentation, best-practice, or service-specific guidance where relevant to the claim. For hierarchical routers, discover child commands and parameters first (for example, `learn=true` when the exposed schema supports it). MCP is a retrieval/observation mechanism, not a new source authority: official documentation governs platform claims; the baseline governs programme decisions. Generic guidance does not override either.
4. **Keep research separate from execution.** Documentation lookup does not authorize live subscription/resource queries. Use live read-only tools only when the user has authorized that environment and scope. Never provision, resize, associate, deallocate, transfer quota, change configuration, or execute POCs as part of fact-checking. Hand live validation to the POC workflow in approved test subscriptions.
5. **Record evidence precisely.** For each material platform claim, cite the official URL and access date, applicable API version, region/SKU/zone restrictions, and Preview/GA state. Record the MCP capability used and distinguish documentation retrieval from live observations. Search results, generated guidance, and successful tool calls are not `[Tested]` evidence; that tag requires a POC ID and reproducible results artefact. Do not send private repository content, credentials, or sensitive environment data in research queries.
6. **Surface unavailable evidence.** If either MCP capability is unavailable, denied, or fails, report that limitation. Use an available alternative MCP documentation capability, or direct official Microsoft Learn pages via web search/fetch, and state the fallback used. Never claim a missing cross-check ran. If official evidence still cannot establish a required behaviour, mark it `[Assumed]` or a `SPEC GAP` blocker and identify the POC/decision needed. A Learn-vs-baseline or observation-vs-documentation conflict must be escalated, not silently resolved.

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
