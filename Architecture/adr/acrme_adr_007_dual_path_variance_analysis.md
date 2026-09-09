# ADR-007 Companion — Dual-Path ("2-Prong") Model: Variance & Impact Analysis

**Companion analysis to ADR-007 (CRG/CR Deployment Model)**

| Field               | Value                                                                 |
|---------------------|----------------------------------------------------------------------|
| **Document**        | Variance & Impact Analysis — Dual-Path CRG Model                     |
| **Parent ADR**      | ADR-007 — CRG/CR Deployment Model                                    |
| **Status**          | ANALYSIS — for review before ADR-007 is moved from PROPOSED to ACCEPTED |
| **Date**            | 2026-09-09                                                            |
| **Baseline**        | Requirements Baseline v2.4 (7 Sep 2026) — re-read for this analysis  |
| **Author(s)**       | ACRME Platform Architecture                                          |
| **Purpose**         | Answer: *What does the 2-prong model change across the overall design? List each variance, plan to address each, and call out specifically what breaks.* |

---

> **Label conventions:** `[Baseline Requirement]` = normative text in v2.4; `[Verified Azure Fact — FC-nn]` = confirmed against MS Learn (see ADR-007 §2); `[Assumption]` = carries risk; `[Variance]` = a delta this model introduces vs the current baseline/design corpus.

---

## 1. Framing Check — Is It One Model or Two? (Read This First)

Your phrasing is "2-prong model … more modern focused." Before listing variances, the framing must be pinned down, because the variance set is different depending on which of two interpretations we adopt. **Being critical of the hypothesis is part of the task, so this is called out explicitly rather than assumed away.**

| Interpretation | What it means | ADR-007 position | Consequence for region selection |
|----------------|---------------|------------------|----------------------------------|
| **(A) Two parallel operating models** | A distinct modern operating model *and* a distinct heritage operating model, each with its own structure, naming, lifecycle, and engine logic. | **Rejected.** ADR-007 §3.3 explicitly finds "**no separate operating model** for modern vs heritage." | Would add complexity — two structures the engine must reason about. |
| **(B) One unified structural model, two *access paths*** | A single CRG structure (CAP-023), naming (OPS-006/C-12), and reconciliation logic. Only the **CRG-resolution access path** differs: *shared* (modern + remediated) vs *local* (un-remediated heritage). | **Recommended (Option C).** | **Does not touch region selection.** The path branch lives in CRG resolution, downstream of region/zone selection. |

**This analysis adopts interpretation (B)** — that is the "2-prong" your statement supports ("shouldn't add complexity to region selection"). Every variance below is scoped to interpretation (B). If the enterprise instead wants interpretation (A), variances V-05, V-07, and V-14 expand materially and region selection *would* be impacted; that path is not recommended and is flagged at the end (§7, Open Decision OD-1).

**Net answer to "is it more modern focused?"** Yes — the *shared* prong is the strategic default for modern (environment-aligned) subscriptions; the *local* prong is a **coexistence/fallback path** that keeps heritage workloads running unchanged until remediated. In production **today**, the local prong is the only production-safe path until DEP-001 (Preview→GA) and POC-001 (quota) clear — the shared prong is aspirational until then (see V-10, V-11).

---

## 2. Region-Selection Guarantee (Your Specific Concern)

`[Baseline Requirement]` Region/zone selection is driven by the placement scoring pipeline over the configurable catalogue (REG-001), the Hard Constraints, ENV-003 separation, and PLC-006/PLC-010/PLC-010a co-location rules. **Nothing in region selection references CRG ownership or sharing.**

The engine has two distinct layers; the 2-prong branch is confined to Layer 2:

| Layer | Question | Inputs | 2-prong impact |
|-------|----------|--------|----------------|
| **L1 — Region/zone selection** (ADR-001) | *Which region + AZ?* | REG-001 catalogue, geography model (US 3-region / others 2-region), ENV-003, PLC-010/010a | **None — path-agnostic** |
| **L2 — CRG resolution** (ADR-007 §10.3) | *Which CRG, owned by which subscription?* | `(domain, region, track)` → provider sub → CRG **(shared)** *or* local CRG in consumer sub **(local)** | This is the *only* place shared/local branches |

In the §10.3 consumer-assignment algorithm, **`region` is an input, not an output** — L1 has already decided it before L2 runs. A heritage (local) and a modern (shared) workload in the same geography select the **identical region + AZ**; they differ only in *who owns the CRG in that zone*.

**Variance V-06 (new, protective):** ADR-007 relies on this ordering but never states it as a hard invariant. We add:

> **INV-R1 (proposed):** Region/zone selection (ADR-001 / PLC-006) is path-agnostic. The shared-vs-local CRG determination occurs only in the CRG-resolution layer, which consumes region as an input. No modern/heritage classification, provider-subscription lookup, or sharing-grant state may be an input to region or zone selection.

This makes your requirement enforceable and prevents a future change from leaking heritage logic upward into region selection.

---

## 3. Complete Variance Register

Each variance is classified as **BREAKING** (contradicts or invalidates existing normative text / design artifacts), **ADDITIVE** (net-new; nothing existing becomes wrong), or **RECONCILE** (existing docs describe a narrower world and must be updated to stay consistent, but were not *wrong* at the time).

| ID | Variance | Source of truth affected | Type | Gate |
|----|----------|--------------------------|------|------|
| V-01 | Sharing limit semantics: "~100 per tenant" → **exactly 100 consumer subs per CRG** + sharding | CAP-013 | **BREAKING** (text + math) | — |
| V-02 | **Provider subscription** owns CRGs, separate from workload subscription | CAP-023, deployment-layout, provisioning-plan, RBAC guide | **BREAKING** (ownership locus) | POC-006 |
| V-03 | **Sharing-grant lifecycle** (grant/revoke/audit) as a first-class engine duty | *(none — gap)* | ADDITIVE (new CAP-026) | DEP-001 |
| V-04 | **MG-scoped** sharing grants for NFR-004 scale | *(none — gap)* | ADDITIVE (CAP-013 clause) | POC-003 |
| V-05 | Engine must resolve **two CRG paths** (shared vs local) + CRG-type flag in a **shard registry** | Reconciliation design, UML class model | ADDITIVE (new state + branch) | — |
| V-06 | **Region-selection invariant INV-R1** (path-agnostic) | ADR-001 principles | ADDITIVE (protective) | — |
| V-07 | **Heritage/modern classification** + heritage **excluded from sharing** until remediated | *(none — new taxonomy)* | ADDITIVE (A-01/A-02 → firm rule) | OD-1 |
| V-08 | ENV-003 enforced at a **new surface**: the sharing-grant boundary (grant audit), not only intra-subscription non-mixing | ENV-003 enforcement design | RECONCILE (mechanism extension) | — |
| V-09 | Position taken: **dedicated DR provider subscription** | POC-006 (open) | RECONCILE (pending POC) | POC-006 |
| V-10 | Shared-prong viability depends on **quota behaviour** (provider- vs consumer-scoped) | POC-001 (open) — cost model | DEPENDENCY (blocks shared prong) | POC-001 |
| V-11 | Shared prong is **Public Preview**, not production-safe until approved/GA | DEP-001 (open) | DEPENDENCY (blocks shared prong) | DEP-001 |
| V-12 | **Naming convention extension** for provider subs + shard counter | OPS-006 / C-12 | RECONCILE (additive tokens) | — |
| V-13 | Downstream **design corpus** describes single-path CRG ownership | 6 design docs + 3 diagrams | RECONCILE | — |

---

## 4. What BREAKS — Explicit Call-Out

Only three items genuinely break something already written or already assumed. Everything else is additive or a doc-reconciliation. These three must be resolved before ADR-007 moves to ACCEPTED.

### B-1 — CAP-013 limit semantics (V-01)

- **Current baseline text:** *"…up to ~100 subscriptions per tenant."*
- **What breaks:** The number is attached to the **wrong scope** (tenant) and marked approximate. `[Verified Azure Fact — FC-03]` the real limit is **exactly 100 consumer subscriptions per CRG** — a hard platform limit, not per-tenant and not a Preview soft cap. `[FC-02]` the sharing unit is the CRG, not the CR.
- **Specifically what it invalidates:** Any capacity-planning arithmetic, POC scenario, or sizing statement that treated "100" as a tenant-wide ceiling. Under the correct semantics, a single tenant can serve **hundreds** of consumer subscriptions (NFR-004) by adding CRGs/shards — but no single CRG may exceed 100 consumers. Docs that read "~100/tenant" imply the platform cannot meet NFR-004, which is false and would mis-scope the sharding requirement.
- **Fix:** Adopt the CAP-013 correction already drafted in ADR-007 §15.1 (per-CRG limit + mandatory workload-domain sharding + CRG-is-the-unit). See remediation task T-01.

### B-2 — CRG ownership locus vs CAP-023 (V-02)

- **Current baseline text (CAP-023):** *"For each environment within **a subscription and region**, reservations are organised into … one regional CRG plus one per-AZ CRG…"* — i.e. CAP-023 as written assumes the CRG lives **in the workload subscription**.
- **What breaks:** The shared prong relocates CRG ownership to a dedicated **provider subscription** that hosts no workload VMs; the workload (consumer) subscription owns *no* CRG and merely receives a sharing grant. This contradicts the literal "within a subscription" reading of CAP-023 and the assumption baked into three artifacts:
  - `acrme_cr_crg_deployment_layout.md` — shows CRGs co-resident with workloads.
  - `acrme_crg_cr_foundation_provisioning_plan.md` — provisioning steps assume the consumer sub owns the CRG.
  - `acrme_security_and_rbac_guide.md` — CRG owner role is assigned in the workload subscription, not a provider MI.
  - Diagrams 7 & 8 (foundation provisioning; sharing model) — provider/consumer split is partial.
- **Important nuance (why it is a real break, not cosmetic):** In the **local** prong the CAP-023 "within a subscription" reading still holds. So CAP-023 must be generalised to say ownership is *either* the workload subscription (local prong) *or* a provider subscription (shared prong) — the **structure** (regional + per-AZ, never-mixed) is identical in both. Without this, CAP-023 and CAP-025 (proposed) directly conflict.
- **Fix:** Generalise CAP-023 ownership wording + ratify CAP-025 (provider subscription model, already drafted ADR-007 §15). Gate on POC-006. See T-02.

### B-3 — ENV-003 enforcement surface (V-08)

- **Current baseline text (ENV-003):** Non-prod/prod and DR/prod **cannot** share capacity; DR **may** share with non-prod.
- **What "breaks":** ENV-003's *intent* is fully preserved — but the **mechanism** the existing design relies on (don't co-mingle environments inside one subscription) is **no longer sufficient** on its own. In the shared prong a mis-scoped **sharing grant** (e.g. a Prod provider CRG granted to a subscription that also runs CVAL) creates a cross-environment capacity path that intra-subscription checks would never catch.
- **Specifically what it invalidates:** Any validation/audit design that assumes ENV-003 is satisfied purely by subscription-level environment alignment. A **new mandatory audit** — "no sharing grant crosses the Prod ↔ CVAL/DR boundary" — becomes part of every reconciliation cycle. This is why **heritage (mixed-environment) subscriptions are excluded from the shared prong** (V-07): granting to them would breach ENV-003 at the grant boundary.
- **Fix:** Ratify CAP-026 (grant lifecycle + boundary audit) and add the coexistence invariant to the reconciliation loop. See T-03.

**Everything else does NOT break the existing design** — it is either net-new capability (V-03, V-04, V-05, V-06, V-07) or documentation that must be brought forward to match (V-09, V-12, V-13). The **local prong is operationally identical to today's pre-sharing state**, so no currently-running workload is disrupted by adopting the 2-prong model.

---

## 5. Remediation Plan — One Task per Variance

Sequenced so that breaking items and their gates land before dependent work. "Gate" = the open POC/decision that must clear before the task can be *finalised* (design can proceed in parallel).

| Task | Addresses | Action | Owner | Gate / Precondition | Sequence |
|------|-----------|--------|-------|---------------------|----------|
| **T-01** | V-01 (B-1) | Apply CAP-013 correction: per-CRG=100 (hard), CRG-is-unit, mandatory workload-domain sharding clause. Update any doc/POC scenario citing "~100/tenant". | Capacity Eng | none | 1 |
| **T-02** | V-02 (B-2) | Generalise CAP-023 ownership (workload-sub **or** provider-sub; structure identical). Ratify **CAP-025** (provider subscription model). | Platform Arch | POC-006 | 1 |
| **T-03** | V-08 (B-3) | Ratify **CAP-026** (grant lifecycle + ENV-003 grant-boundary audit). Add grant-boundary check to reconciliation loop. | Security + Platform Eng | DEP-001 | 1 |
| **T-04** | V-06 | Add **INV-R1** (region-selection path-agnostic) to ADR-001 principles and ADR-007 §4. | Platform Arch | none | 1 |
| **T-05** | V-04 | Add MG-scoped sharing-grant clause to CAP-013; design MG-subtree grant propagation. | Platform Eng | POC-003 | 2 |
| **T-06** | V-05 | Design the **shard registry** (`(domain,region,track)→provider→[CRG]` + CRG-type flag local/shared) and the L2 resolution branch; update UML class model. | Platform Eng | OD-2 (registry store) | 2 |
| **T-07** | V-07 | Firm up heritage/modern **classification rules** (A-01/A-02) and the heritage-exclusion-from-sharing rule; publish remediation backlog format. | Platform Arch | OD-1 (taxonomy) | 2 |
| **T-08** | V-12 | Extend OPS-006/C-12 with provider-sub + shard-counter tokens (`sub-<org>-cld-cr-<track>-<domain>-<region>-<NN>`). | Platform Eng | none | 2 |
| **T-09** | V-09 | Confirm dedicated-DR-provider-subscription position or revert to shared. | Capacity Eng | **POC-006** | 3 |
| **T-10** | V-10 | Run quota-scope POC; if provider-scoped, keep local-prong fallback (rollback flag already designed, ADR-007 §14.3). | Capacity Eng | **POC-001** | 3 |
| **T-11** | V-11 | Enterprise Preview-acceptance sign-off or wait for GA before enabling shared prong in prod. | Platform Eng | **DEP-001** | 3 |
| **T-12** | V-13 | Reconcile the 6 design docs + 3 diagrams to the dual-path model (provider/consumer split, both paths). | Platform Arch | T-02, T-03 | 3 |

**Critical path:** T-01, T-02, T-03, T-04 (the breaking items + the invariant) must complete first — they can proceed in design now; T-02/T-03 finalise only after POC-006/DEP-001. The shared prong cannot be enabled in production until **POC-001 + DEP-001** both clear (T-10, T-11); until then the estate runs the **local prong** with zero disruption.

---

## 6. Changes Needed to DESIGN (Documents & Requirements)

### 6.1 Baseline v2.4 — requirement edits

| Req | Change | Type |
|-----|--------|------|
| **CAP-013** | Replace "~100 per tenant" with "exactly 100 consumer subs per CRG (hard); CRG is the sharing unit; shard by workload domain beyond 100." Add MG-scope clause. | Correction + addition |
| **CAP-023** | Generalise ownership: CRG owned by the workload subscription (local prong) **or** a provider subscription (shared prong); structure (regional + per-AZ, never-mixed) unchanged. | Correction |
| **CAP-025** *(new)* | Provider subscription model — infra-only subs own CRGs/CRs; consumers access via grants; shard registry maps scope→provider→CRGs. | New |
| **CAP-026** *(new)* | Sharing-grant lifecycle — grant/revoke/audit + ENV-003 grant-boundary audit each reconciliation cycle. | New |
| **ENV-003** | Add note: in the shared prong, separation is additionally enforced at the sharing-grant boundary (not only intra-subscription). | Clarification |
| **OPS-006 / C-12** | Add provider-subscription and shard-counter naming tokens. | Extension |
| **ADR-001 / PLC-006** | Add **INV-R1** (region selection is path-agnostic). | New invariant |

### 6.2 Design corpus to reconcile (V-13)

- `Reference-Material/reference/acrme_cr_crg_deployment_layout.md` (+ docx/pdf)
- `Reference-Material/reference/acrme_crg_cr_foundation_provisioning_plan.md` (+ docx/pdf)
- `Reference-Material/guides/acrme_security_and_rbac_guide.md` (provider MI ownership)
- `Design/acrme_uml_class_diagrams_summary.md` (shard registry + CRG-type)
- `Architecture/diagrams/diagram_7_*`, `diagram_8_*` (provider/consumer split; both paths)
- `POC-Test-Scripts/acrme_poc_workbook_v2_4.md` (POC-001/003/006 scenarios reflect per-CRG limit + grant scope)

---

## 7. Changes Needed to MEMORY (Standing Instructions / Reference Facts)

Two items warrant a memory update (offered, not auto-applied):

1. **Stale baseline pointer (correctness fix).** The recorded ACRME standing instruction points to `Uploads/…Consolidated Requirements Baseline.md` mirrored at `docs/acrme_requirements_baseline_v2_2.md`. The **current authoritative source is `Requirements/acrme_requirements_baseline_v2_4.md`** (v2.4, 7 Sep 2026). The pointer should be updated so future work re-reads v2.4, not v2.2.
2. **New reference fact (2-prong model canon).** Optionally record: *"ACRME CRG deployment = ONE unified structural model (CAP-023) with TWO access paths — shared (provider-subscription-owned CRGs, modern/remediated subs) and local (consumer-owned CRGs, un-remediated heritage). Region selection is path-agnostic (INV-R1). Shared prong is gated on POC-001 + DEP-001."* This prevents the recurring "two models" misframing.

These are **proposed**; I will apply them only on your say-so.

---

## 8. Open Decisions Introduced / Reaffirmed

| ID | Decision | Why it matters | Owner |
|----|----------|----------------|-------|
| **OD-1** | Confirm interpretation (B) one-model/two-paths vs (A) two parallel models | (A) would impact region selection and expand V-05/V-07/V-14 | Architecture Board |
| **OD-2** | Shard-registry system of record (config repo vs platform DB vs ARG-derived) | Determines T-06 design | Platform Eng |
| **OD-3** | Dedicated vs shared DR provider subscription | POC-006; affects T-02/T-09 | Capacity Eng |
| **OD-4** | Break-glass path when sharing grant fails at scale | Availability of the shared prong | Platform Eng |

---

## 9. Summary

- The 2-prong model is **one unified structural model with two access paths** — it is "modern-focused" (shared prong is the strategic default) with a **non-disruptive local prong** for heritage. It **does not add complexity to region selection** (guaranteed by INV-R1).
- **13 variances** identified. **Only 3 genuinely break** existing design: **B-1** CAP-013 limit semantics, **B-2** CRG ownership locus vs CAP-023, **B-3** ENV-003 enforcement surface. Each has a specific, bounded fix (T-01/T-02/T-03).
- Everything else is **additive** (new capability) or **doc reconciliation**. **No running workload is disrupted** — the local prong equals today's behaviour.
- The **shared prong is not production-safe until POC-001 (quota) and DEP-001 (Preview→GA) clear**; design proceeds now, production enablement waits on those gates.
- **Memory:** the recorded baseline pointer is stale (v2.2 → should be v2.4) — recommend updating.
