#!/usr/bin/env python3
"""Transform the consolidated ACRME ADR document into a self-contained,
reference-less document and embed rendered architecture diagrams.

Reference-less means: no pointers that force the reader to open another
document — external file names, section numbers (e.g. PRR §29, FR-7.3),
and cross-document tracking codes (G-/B-/POC-/FC-/QG-/GP-/E-) are removed
or reworded in place. All *substantive* detail (rules, formulas, tables,
state machine, lifecycle) is preserved. Evidence tags are normalized to the
four bare categories. Diagrams are inserted at the relevant anchors.

Idempotent-ish: safe to run against the already-enriched v1.1 source.
"""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parent / "acrme_architecture_decision_records.md"
text = SRC.read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# 1. Header: version bump + reference-less change note
# ---------------------------------------------------------------------------
text = text.replace("**Version:** 1.1  ", "**Version:** 1.2  ", 1)

old_change = re.search(r"\*\*Change note \(v1\.1\):\*\*.*", text).group(0)
new_change = (
    "**Change note (v1.2):** Made this a self-contained, reference-free document — removed "
    "external document and section citations so it can be read without any companion document — "
    "and added rendered architecture diagrams (placement pipeline, input modes, quota-group model, "
    "engine state machine, emergency-transfer tiers, capacity-increase lifecycle). "
    "**(v1.1):** Added the region-classification model, Scenario 1/2 input modes, the exception "
    "workflow, the validation-rule framework, capacity-hold concurrency and corrected scoring "
    "(ADR-001); group accounting formulas, the dual-validation detector and `groupType` preview "
    "status (ADR-002); the five-state engine state machine, the `EngineModeState` entity and "
    "DR-activation semantics (ADR-003); and the 10-step steady-state lifecycle with the "
    "auto-decrease exclusion (ADR-004)."
)
text = text.replace(old_change, new_change)

# About This Document: make the evidence-tag description self-contained
text = text.replace(
    "**Evidence tags** used throughout: `[Documented]` (Azure platform docs), `[Decided]` "
    "(Decision Log D1\u2013D11), `[Derived]` (logical consequence), `[Assumed]` (architectural "
    "judgement pending validation).",
    "**Evidence tags** used throughout: `[Documented]` (traceable to Azure platform behaviour or "
    "documentation), `[Decided]` (an explicit ACRME design choice recorded in this ADR set), "
    "`[Derived]` (a logical consequence of a documented constraint or decision), `[Assumed]` "
    "(architectural judgement pending proof-of-concept validation).",
)

# ---------------------------------------------------------------------------
# 2. Remove the external **Source:** metadata lines
# ---------------------------------------------------------------------------
text = re.sub(r"^\*\*Source:\*\*.*\n", "", text, flags=re.M)

# 3. Reword the per-ADR "Related decisions" metadata to self-defined constraints only
text = text.replace(
    "**Related decisions:** D1, D4, D5, D8, D9; HC-1..HC-10; VR-1..VR-11  ",
    "**Related constraints:** HC-1..HC-10 (hard constraints); VR-1..VR-11 (validation rules)  ",
)
text = text.replace(
    "**Related decisions:** D6, D7, D9; HC-2, HC-3, HC-7  ",
    "**Related constraints:** HC-2, HC-3, HC-7 (hard constraints)  ",
)
text = text.replace(
    "**Related decisions:** D8, D10, D11; HC-1, HC-4, HC-6; G-14, G-15  ",
    "**Related constraints:** HC-1, HC-4, HC-6 (hard constraints)  ",
)
text = text.replace(
    "**Related decisions:** D10; FR-7, FR-4.4; G-24  ",
    "**Related constraints:** HC-3 (applied at increase-execution time)  ",
)

# ---------------------------------------------------------------------------
# 4. Reword prose that embeds external tracking codes (preserve the substance)
# ---------------------------------------------------------------------------
prose = {
    "(but **may** share with NonProd per D8).":
        "(but **may** share with NonProd).",
    "increase implementation and snapshot-maintenance cost (backlog E07-S16, E03-S10).":
        "increase implementation and snapshot-maintenance cost.",
    "if the region count ever exceeds 6, joint optimization should be revisited (D1 review trigger).":
        "if the region count ever exceeds 6, joint optimization should be revisited.",
    "Worked scoring examples remain a known gap (G-7) until per-CRG-type inputs are finalised.":
        "Worked scoring examples remain a known gap until per-CRG-type inputs are finalised.",
    "CRG_Score (RCW) is demoted from a primary scoring input to a monitoring-only signal (D9).":
        "CRG_Score (Regional Capacity Weight) is demoted from a primary scoring input to a monitoring-only signal.",
    "This closes the concurrent-placement race (B-7).":
        "This closes the concurrent-placement race.",
    "**Worked POC topology (GP-06):**":
        "**Worked topology example:**",
    "#### `groupType` Preview Dependency (FC-11)":
        "#### `groupType` Preview Dependency",
    "that dependency must pass the preview-acceptance gate (POC-30) and a Decision Log entry first.":
        "that dependency must pass a preview-acceptance proof-of-concept and a recorded decision first.",
    "**Hard dependency on Azure Quota Groups GA** \u2014 Blocker B-1 (POC-30); if `groupQuotas` returns 404":
        "**Hard dependency on Azure Quota Groups GA** \u2014 validated by proof-of-concept before rollout; if `groupQuotas` returns 404",
    "state machine `EngineModeState`, PRR §29), never automatic.":
        "state machine `EngineModeState`), never automatic.",
    "a production blocker until implemented (G-15):":
        "a production blocker until implemented:",
    "**Tier 3 is blocked** pending the G-14 consumer-credential model and G-15 engine-mode state machine.":
        "**Tier 3 is blocked** pending the consumer-credential model and the engine-mode state machine.",
    "until G-14 (Managed Identity vs cross-tenant SP credential model) and G-15 (state machine) are resolved \u2014 a known Phase-1 limitation.":
        "until the consumer-credential model (Managed Identity vs cross-tenant service-principal) and the engine-mode state machine are resolved \u2014 a known Phase-1 limitation.",
    "exposing raw time series and derived recommendations via API.":
        "exposing raw time series and derived recommendations via API.",
    "workload-tagged per-workload forecasts (FR-7.5) are only partially covered (gap G-16).":
        "workload-tagged per-workload forecasts are only partially covered.",
    "`CapacityIncreaseRequest` lifecycle (entity, approval, retry, cancellation) is still a backlog item (G-24) requiring an end-to-end approved-increase test.":
        "the `CapacityIncreaseRequest` lifecycle (entity, approval, retry, cancellation) is still a backlog item requiring an end-to-end approved-increase test.",
    "guarded reduction (right-sizing) never drops a CR below its allocated count (platform floor, FR-1.6) and is itself approval-gated.":
        "guarded reduction (right-sizing) never drops a CR below its allocated count (the platform floor) and is itself approval-gated.",
    "at group level where Quota Groups apply (ADR-002) \u2014 subject to the same operator-approval gate.":
        "at group level where Quota Groups apply (see ADR-002) \u2014 subject to the same operator-approval gate.",
    "the protected floor uses `dr_ratio_max` (ADR-002/D7).":
        "the protected floor uses `dr_ratio_max` (see ADR-002).",
    "organic growth via the reconciliation loop and `CapacityIncreaseRequest` (ADR-004).":
        "organic growth via the reconciliation loop and `CapacityIncreaseRequest` (see ADR-004).",
    "This is possible *only* because of the two-group model (ADR-002).":
        "This is possible *only* because of the two-group model (see ADR-002).",
    "This growth path must be architecturally distinct from crisis operations (ADR-003).":
        "This growth path must be architecturally distinct from crisis operations (see ADR-003).",
    "keeping organic growth strictly separate from crisis transfer (ADR-003).":
        "keeping organic growth strictly separate from crisis transfer (see ADR-003).",
    "Make emergency capacity transfer (ADR-003) **quota-neutral**":
        "Make emergency capacity transfer (see ADR-003) **quota-neutral**",
    "because Emergency Transfer (ADR-003) covers crisis speed.":
        "because Emergency Transfer (see ADR-003) covers crisis speed.",
    "The DR orchestrator validates group+subscription quota and CR/sharing state before starting any approved failover deployment, and records active-or-incident-hold state back to the state service.":
        "The DR orchestrator validates group and subscription quota and CR/sharing state before starting any approved failover deployment, and records active-or-incident-hold state back to the state service.",
}
for a, b in prose.items():
    if a in text:
        text = text.replace(a, b)
    else:
        print("WARN prose not found:", a[:60])

# ---------------------------------------------------------------------------
# 5. Normalize evidence tags to the four bare categories
# ---------------------------------------------------------------------------
text = re.sub(r"`\[Documented[^\]]*\]`", "`[Documented]`", text)
text = re.sub(r"`\[Decided[^\]]*\]`", "`[Decided]`", text)
text = re.sub(r"`\[Derived[^\]]*\]`", "`[Derived]`", text)
text = re.sub(r"`\[Assumed[^\]]*\]`", "`[Assumed]`", text)
text = re.sub(r"`\[Undocumented[^\]]*\]`", "`[Assumed]`", text)
# Standalone reference tags used in the Alternatives tables
text = re.sub(r"`\[D\d+\]`", "`[Decided]`", text)
text = re.sub(r"`\[§[^\]]*\]`", "`[Documented]`", text)
text = re.sub(r"`\[FR-[^\]]*\]`", "`[Documented]`", text)
text = re.sub(r"`\[PRR[^\]]*\]`", "`[Assumed]`", text)

# ---------------------------------------------------------------------------
# 6. Rewrite Appendix A into a self-contained ADR summary (no external codes)
# ---------------------------------------------------------------------------
appendix_a_old = re.search(
    r"## Appendix A — Decision Log Cross-Reference.*?(?=\n## Appendix B)",
    text, flags=re.S).group(0)
appendix_a_new = (
    "## Appendix A — ADR Summary\n\n"
    "| ADR | Hard Constraints Applied | Key Open Items |\n"
    "|---|---|---|\n"
    "| ADR-001 Region Selection | HC-1, HC-4, HC-5, HC-8, HC-9, HC-10 | Worked scoring examples pending final per-CRG-type inputs |\n"
    "| ADR-002 Quota & Capacity | HC-2, HC-3, HC-7 | Azure Quota Groups GA validated by proof-of-concept before rollout |\n"
    "| ADR-003 Capacity during DR | HC-1, HC-4, HC-6 | Consumer-credential model and engine-mode state machine; quota-release latency measured |\n"
    "| ADR-004 Forecast & Increase | HC-3 (at execution) | Workload-tagged forecasts; `CapacityIncreaseRequest` lifecycle end-to-end test |\n\n"
)
text = text.replace(appendix_a_old, appendix_a_new)

# Appendix C — make evidence tag meanings self-contained
appendix_c_old = re.search(
    r"## Appendix C — Evidence Tag Taxonomy.*?(?=\n---\n)",
    text, flags=re.S).group(0)
appendix_c_new = (
    "## Appendix C — Evidence Tag Taxonomy\n\n"
    "| Tag | Meaning |\n"
    "|---|---|\n"
    "| `[Documented]` | Traceable to Azure platform behaviour or documentation |\n"
    "| `[Decided]` | An explicit ACRME design choice recorded in this ADR set |\n"
    "| `[Derived]` | A logical consequence of a documented constraint or decision |\n"
    "| `[Assumed]` | Architectural judgement pending proof-of-concept validation |\n"
)
text = text.replace(appendix_c_old, appendix_c_new)

# Footer Next Review — plain language
text = text.replace(
    "**Next Review:** After POC-30 (Quota Groups GA) and POC-31 (quota release latency), and on resolution of G-14 / G-15.",
    "**Next Review:** After proof-of-concept validation of Azure Quota Groups GA and quota-release latency, and on resolution of the consumer-credential model and engine-mode state-machine items.",
)

# ---------------------------------------------------------------------------
# 7. Insert diagrams at anchors (paths relative to docs/ = adr/diagrams/...)
# ---------------------------------------------------------------------------
figs = {
    "#### Region Classification Model (normative)":
        "![**Figure 1.** ACRME staged placement pipeline \u2014 Stage 1 eligibility pre-filter, Stage 2 hard-constraint gate, Stage 3 environment-type-specific scoring, then sequential Prod \u2192 NonProd \u2192 DR selection.](adr/diagrams/adr001_pipeline.png){ width=80% }",
    "#### Exception Deployment Workflow (Scenario 2 — Restricted region)":
        "![**Figure 2.** Prod region input modes \u2014 geography-supplied (Scenario 1) versus specific-region (Scenario 2), including the restricted-region Exception Deployment Workflow.](adr/diagrams/adr001_input_modes.png){ width=72% }",
    "#### Group Accounting Formulas (normative)":
        "![**Figure 3.** Two-quota-group-per-region model \u2014 an isolated Prod-only group and a shared NonProd+DR group with the engine-enforced DR floor and the effective NonProd ceiling.](adr/diagrams/adr002_quota_groups.png){ width=85% }",
    "5. **DR reserve sizing** is `30\u201340%` of Prod":
        "![**Figure 5.** Three-tier Emergency Capacity Transfer escalation \u2014 Tier 1 automated, Tier 2 quota-neutral, Tier 3 destructive (blocked in Phase 1).](adr/diagrams/adr003_transfer_tiers.png){ width=33% }",
    "#### Auto-Decrease Exclusion":
        "![**Figure 6.** Ten-step steady-state capacity-increase lifecycle, running only in STEADY_STATE behind an operator-approval gate.](adr/diagrams/adr004_lifecycle.png){ width=25% }",
}
# State-machine figure: insert AFTER the "All transitions..." line (after the table)
state_anchor = "All transitions are **operator-gated with dual approval** — never automatic."
state_fig = "![**Figure 4.** Five-state engine mode machine \u2014 every transition is operator-gated with dual approval.](adr/diagrams/adr003_state_machine.png){ width=98% }"

lines = text.splitlines()
out = []
for ln in lines:
    stripped = ln.strip()
    # insert-before anchors
    if stripped in figs:
        out.append(figs[stripped])
        out.append("")
    out.append(ln)
    # insert-after anchor (state machine)
    if stripped == state_anchor:
        out.append("")
        out.append(state_fig)
text = "\n".join(out) + "\n"

SRC.write_text(text, encoding="utf-8")
print("Transformed consolidated ADR written:", SRC.name, "-", len(text.splitlines()), "lines")
