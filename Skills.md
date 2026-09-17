# ACRME Programme — Skills Inventory

> **Version:** 1.0  
> **Scope:** Azure Capacity & Quota Management Engine (ACRME) — Core/Baseline only  
> **Authority:** This document defines the reusable skill patterns for the ACRME programme. Each skill is a structured, repeatable procedure that any ACRME agent applies when the trigger condition is met. Skills are companion artefacts to `Agents.md`.

---

## Purpose

ACRME is a complex, multi-domain engine. Certain work patterns recur across agents and phases: validating against the requirements baseline, assessing against WAF pillars, authoring ADRs, verifying capacity formulas, executing POC cases. Without a structured skill definition, these recurring patterns produce inconsistent outputs and miss normative detail.

This document defines the **skill inventory** — the reusable, structured procedures that ACRME agents invoke. Each skill specifies:
- **Trigger:** When to invoke it
- **Inputs:** What the skill reads or receives
- **Process:** The exact steps to execute
- **Outputs:** What the skill produces
- **Owner:** Which agent is the primary user
- **Platform Status:** Whether a platform skill registration exists or is recommended

---

## Skill Index

| ID | Skill | Primary Agent | Platform Skill |
|---|---|---|---|
| SK-01 | [Baseline Validation](#sk-01--baseline-validation) | All agents | ✅ Recommended |
| SK-02 | [WAF Assessment](#sk-02--waf-assessment) | Architect | ✅ Recommended |
| SK-03 | [Hard Constraint Check](#sk-03--hard-constraint-check) | All agents | ✅ Recommended |
| SK-04 | [ADR Authoring](#sk-04--adr-authoring) | Architect | — Reference skill |
| SK-05 | [POC Case Execution](#sk-05--poc-case-execution) | POC Validation Engineer | — Reference skill |
| SK-06 | [Capacity Formula Verification](#sk-06--capacity-formula-verification) | Architect / Implementation Engineer | ✅ Recommended |
| SK-07 | [Requirements Traceability](#sk-07--requirements-traceability) | Architect / Documentation Steward | — Reference skill |
| SK-08 | [Backlog Story Authoring](#sk-08--backlog-story-authoring) | Architect / Documentation Steward | — Reference skill |
| SK-09 | [DR Sizing Validation](#sk-09--dr-sizing-validation) | Architect / Implementation Engineer | ✅ Recommended |
| SK-10 | [Readiness Gate Check](#sk-10--readiness-gate-check) | Architect / Implementation Engineer | — Reference skill |
| SK-11 | [Region Model Validation](#sk-11--region-model-validation) | Architect | — Reference skill |
| SK-12 | [Documentation Completeness Review](#sk-12--documentation-completeness-review) | Documentation Steward | ✅ Recommended |

> **Platform Skill:** A skill marked ✅ is a candidate for Abacus AI platform skill registration — it encodes a critical, frequently-used procedure that must be applied consistently and is worth a single-click invocation. Reference skills are procedural definitions used by agents; they are not registered as platform skills unless usage frequency justifies it.

---

## Skills

---

### SK-01 — Baseline Validation

**Purpose:** Validate any proposed design change, documentation update, or architectural recommendation against the living requirements baseline before the change is applied. Prevents baseline drift and ensures all agents operate from the same authoritative source.

**Trigger — invoke this skill when:**
- Authoring or updating any design document, ADR, or reference material
- Proposing a new architectural recommendation
- Implementing a component or algorithm
- Responding to any question about ACRME behaviour or requirements

**Inputs**

| Input | Description |
|---|---|
| Proposed change | The design decision, recommendation, or document update being proposed |
| Baseline file | `/home/ubuntu/Uploads/Azure Capacity & Quota Management- Consolidated Requirements Baseline.md` |
| Relevant FR codes | The functional requirement codes relevant to the proposed change (e.g., CAP-003, DR-017) |

**Process**

```
Step 1 — Read the baseline
  Open the living baseline file.
  Do not rely on prior context, session summary, or memory — read the current file.

Step 2 — Identify relevant sections
  Map the proposed change to the relevant baseline sections:
  - §7  Environment Policy (ENV-001 through ENV-007)
  - §8  Capacity Reservation Management (CAP-001 through CAP-024)
  - §9  Quota Management (QUA-001 through QUA-014)
  - §10 Readiness (RDY-001 through RDY-004)
  - §11 Region Selection & Placement (PLC-001 through PLC-011)
  - §12 Disaster Recovery (DR-001 through DR-019)
  - §26–§32 Production Readiness (state machine, VR-1..VR-11, scoring, lifecycle)
  - Appendix A — Core Formulas
  - Appendix D — DR Sizing (MAX-not-SUM)

Step 3 — Cross-check the proposed change
  For each relevant baseline section:
  a. Extract the normative statement (requirement, formula, constraint, or rule)
  b. Compare it to the proposed change
  c. Classify each comparison as: ALIGNED | CONFLICT | NOT COVERED | EXTENDS BASELINE

Step 4 — Produce the compliance report
  Output a table: Requirement Code | Baseline Statement | Proposed Change | Status | Action Required

Step 5 — Block on CONFLICT
  If any comparison is CONFLICT, the proposed change is blocked.
  State the conflict explicitly and require resolution before proceeding.
  Do not continue with a blocked change.
```

**Outputs**

- Compliance report table (Requirement Code / Baseline Statement / Proposed Change / Status / Action Required)
- COMPLIANT or BLOCKED verdict
- If BLOCKED: exact conflict statement with baseline reference

**Owner:** All agents (mandatory for Architect and Documentation Steward; required for Implementation Engineer on any algorithm or formula implementation)

**Platform Skill Registration:** ✅ Recommended — `acrme-baseline-check`

---

### SK-02 — WAF Assessment

**Purpose:** Apply all five Azure Well-Architected Framework pillars to an architectural recommendation, design decision, or proposed change. WAF assessment is mandatory for all major ACRME design decisions.

**Trigger — invoke this skill when:**
- A new architectural recommendation is being made
- An ADR is being authored
- A design change affects how the engine behaves at runtime
- A technology choice is being made (runtime, storage, messaging, compute host)

**Inputs**

| Input | Description |
|---|---|
| Recommendation | The architecture decision or design choice under assessment |
| WAF pillars | All five: Security, Reliability, Performance Efficiency, Cost Optimization, Operational Excellence |
| ACRME context | Engine domain (reconciliation, placement, DR, quota, readiness) |

**Process**

```
Step 1 — Security pillar
  Evaluate:
  - Identity model: Managed Identity vs service principal
  - RBAC model: minimum permissions required for engine across all subscriptions
  - PIM: elevated access for decommission and DR declaration actions
  - Key Vault: secret and configuration management
  - Network isolation: private endpoints, VNet integration
  - Policy controls: Azure Policy guardrails on CRGs, reservations
  - Governance: audit log completeness (QUA-014, OPS-00x)
  Answer: What are the security implications? What permissions are required? How is least privilege enforced?

Step 2 — Reliability pillar
  Evaluate:
  - Availability Zone strategy: per-AZ CRG structure (CAP-023)
  - Regional failover: DR-006 staged acquisition
  - DR declaration and standby activation (DR-019)
  - RTO/RPO implications for capacity availability
  - Engine self-resilience (what if the reconciler fails mid-loop?)
  - Backup and recovery for state store (seed records, DR index)
  Answer: What happens during failure? How is recovery performed? What are RTO/RPO implications?

Step 3 — Performance Efficiency pillar
  Evaluate:
  - Reconciliation interval (CAP-006 — reference: 6 minutes)
  - API throttling risk (Resource Graph, Capacity Reservation API, Quota API)
  - Placement weighting computation cost (PLC-007)
  - State freshness vs compute cost trade-off (RDY-004)
  - Throughput under peak placement load
  Answer: How does the architecture scale? What limits exist?

Step 4 — Cost Optimization pillar
  Evaluate:
  - Idle reservation cost (MAX-not-SUM overcommit saving — DR-017/Appendix D)
  - Buffer sizing impact on idle cost
  - DR bootstrap cost vs full-replica cost
  - CVAL sacrifice cost on DR declaration
  - Engine host cost (Functions vs Container Apps vs AKS)
  Answer: What costs are introduced? How can costs be optimised? What is the cost trade-off?

Step 5 — Operational Excellence pillar
  Evaluate:
  - Automation completeness (CAP-005/006 reconciliation, QUA-008/009)
  - Observability (alerting on CAP-007 scale-up failure, quota deficit)
  - Deployment pipeline (IaC for CRG/CR matrix, engine CI/CD)
  - Governance (decommission workflow CAP-010, seed record change PLC-005)
  - Runbook availability (DR declaration, CVAL sacrifice, bootstrap acquisition)
  Answer: Can this operate at scale? Can it be automated? What runbooks are required?

Step 6 — Produce WAF assessment table
  Format: Pillar | Evaluation | Risks | Recommendations | Status
  Status per pillar: PASS | RISK | FAIL
```

**Outputs**

- WAF assessment table (5 pillars × 4 columns)
- Overall WAF rating: APPROVED | CONDITIONAL (risks must be mitigated) | BLOCKED
- Risk register entries for RISK or FAIL ratings

**Owner:** Azure Capacity & Platform Architect (primary); Documentation Steward (review)

**Platform Skill Registration:** ✅ Recommended — `acrme-waf-assessment`

---

### SK-03 — Hard Constraint Check

**Purpose:** Validate any proposed design, implementation decision, POC result, or configuration change against the ACRME hard constraints (HC-1 through HC-11). Hard constraints are inviolable — any output that violates one is blocked.

**Trigger — invoke this skill when:**
- Completing any design or implementation output
- Reviewing a POC finding before updating the workbook
- Assessing any proposed configuration change
- Before authoring an ADR that records a design decision

**Inputs**

| Input | Description |
|---|---|
| Proposed output | The design, decision, or POC finding being validated |
| Hard constraints reference | `/home/ubuntu/acrme-capacity-reservation/Reference-Material/reference/acrme_hard_constraints_reference.md` |

**Hard Constraints (HC-1 through HC-11)**

| HC | Constraint | Source |
|---|---|---|
| HC-1 | Reservation target = Allocated + Buffer. Never associated-only. | CAP-003 |
| HC-2 | Zero capacity = set quantity to 0, never delete the reservation object. | CAP-009 |
| HC-3 | Decommission requires approved workflow. Reconciliation never deletes. | CAP-010 |
| HC-4 | Quota and capacity must both be validated before any placement decision. | QUA-007, RDY-001 |
| HC-5 | Placement reads exact production region from the customer seed record. Not derived from geography. | PLC-001, PLC-003 |
| HC-6 | DR destination uses MAX-not-SUM sizing across non-concurrent sources. | DR-017, Appendix D |
| HC-7 | CVAL capacity is released (sacrificed) before requesting new DR capacity from Azure. | DR-006, DR-004 |
| HC-8 | DR bootstrap is the capacity floor — not a full production copy (no fixed % of prod). | ENV-005, DR-001 |
| HC-9 | Reconciliation always uses current state — stale state is rejected. | CAP-005, RDY-004 |
| HC-10 | Every managed SKU/AZ combination is seeded at quantity 0 in the seed matrix. | CAP-022 |
| HC-11 | Middle East DR is cross-geo into EU weighted region (DEC-001 RESOLVED, v2.4). | PLC-010b, DR-020 |

**Process**

```
Step 1 — Read the hard constraints reference file
Step 2 — For each HC-1 through HC-11:
  a. Assess whether the proposed output affects this constraint
  b. If yes: classify as PASS | FAIL | N/A
  c. If FAIL: state exactly how the output violates the constraint
Step 3 — Produce HC compliance matrix
  Format: HC ID | Constraint Summary | Affected? | Status | Evidence / Violation
Step 4 — Block on any FAIL
  A single FAIL blocks the output.
  The output cannot proceed until the violation is resolved and the HC re-checked.
```

**Outputs**

- HC compliance matrix (HC-1 to HC-11 × 5 columns)
- COMPLIANT or BLOCKED verdict
- If BLOCKED: exact violation with HC reference and remediation required

**Owner:** All agents (mandatory before any output is delivered)

**Platform Skill Registration:** ✅ Recommended — `acrme-hc-check`

---

### SK-04 — ADR Authoring

**Purpose:** Author an Architecture Decision Record (ADR) for a design decision in the ACRME programme. ADRs are the authoritative record of design decisions, including the decision, alternatives considered, trade-offs, WAF assessment, and HC validation.

**Trigger — invoke this skill when:**
- A design decision has been made that is not yet recorded
- A POC finding invalidates a prior assumption and a new decision is required
- A hard constraint or baseline requirement changes

**Inputs**

| Input | Description |
|---|---|
| Decision title | The decision being recorded |
| Context | The problem the decision addresses |
| Requirements | The relevant requirement codes (FR, CAP, QUA, PLC, DR, etc.) |
| Alternatives considered | All options that were evaluated |
| Decision | The chosen option |
| Rationale | Why this option was chosen |
| POC evidence | Validated or assumed (from POC workbook if available) |

**Process**

```
Step 1 — Run SK-01 (Baseline Validation)
  Confirm the decision aligns with the current baseline before authoring.

Step 2 — Run SK-02 (WAF Assessment)
  Include the WAF assessment in the ADR body.

Step 3 — Run SK-03 (Hard Constraint Check)
  Include the HC compliance matrix in the ADR body.

Step 4 — Author the ADR with full normative detail
  Required sections:
  a. Title and ADR ID
  b. Status (Proposed | Accepted | Superseded | Deprecated)
  c. Context — the problem, requirements codes, constraints
  d. Decision — the chosen approach
  e. Rationale — why this approach over alternatives
  f. Alternatives Considered — all options with trade-offs
  g. WAF Assessment (all 5 pillars — from SK-02)
  h. Hard Constraint Validation (HC-1 to HC-11 — from SK-03)
  i. Normative Detail — ALL of: state machines, formulas, classification tables,
     validation rule sets, lifecycle steps relevant to this decision.
     Summaries are insufficient. If the decision touches reliability or DR,
     include: the five-state engine state machine, VR-1..VR-11 validation framework,
     exact scoring formulas, and the 10-step capacity lifecycle (§26–§32).
  j. Implications — what changes, what is affected, what must be updated
  k. Decision Log — decision, alternatives, trade-offs, impact
  l. Related ADRs
  m. Confidence classification: Documented | Tested | Derived | Assumed

Step 5 — Save the ADR
  File path: Architecture/adr/ADR-<NNN>-<slug>.md

Step 6 — Update dependent documents
  Identify any design document, reference material, or backlog story
  that must be updated as a result of this ADR.
  List the required updates as implementation items.
```

**Completeness Rule (Mandatory)**

> An ADR that covers a decision without its normative detail (state machines, formulas, classification tables, validation rules) **fails the completeness check** and must be returned for revision.
> This rule exists because: "Agent delivered ADRs covering the four requested areas but omitted substantial normative detail... User: ADRs don't cover details in Production Readiness design, review and update the details accordingly."

**Outputs**

- ADR document in `Architecture/adr/ADR-<NNN>-<slug>.md`
- List of dependent documents requiring update

**Owner:** Azure Capacity & Platform Architect

---

### SK-05 — POC Case Execution

**Purpose:** Execute a single POC case from the ACRME POC workbook (v2.4) in a structured, evidence-based manner. Produces a recorded result with PASS/FAIL/BLOCKED status and supporting evidence.

**Trigger — invoke this skill when:**
- Executing any case from the POC workbook (G1–G12)
- A design decision is marked POC-gated and requires live validation

**Inputs**

| Input | Description |
|---|---|
| POC Case ID | The case identifier from the workbook (e.g., G1-001, G9-003) |
| POC Workbook | `POC-Test-Scripts/acrme_poc_workbook_v2_4.md` |
| Azure test environment | Subscription IDs, region, AZ, SKU configuration |
| Config | `POC-Test-Scripts/config.yaml.template` |

**Process**

```
Step 1 — Pre-flight check
  Run: POC-Test-Scripts/acrme_suite/preflight.py
  Confirm: Azure CLI authentication, subscription access, region availability,
           Capacity Reservation Sharing preview enabled (for sharing cases).
  Do not proceed if preflight fails — record as BLOCKED.

Step 2 — Read the case definition
  Read the exact case from the workbook:
  - Objective
  - Prerequisites
  - Test steps
  - Expected result
  - Evidence required

Step 3 — Execute the case
  Execute exactly the steps defined in the workbook.
  Do not improvise additional steps or skip defined steps.
  Capture output at each step.

Step 4 — Record evidence
  For each step: capture Azure CLI output / API response / portal screenshot.
  Retain the raw evidence, not just a summary.

Step 5 — Classify the result
  PASS: Actual result matches expected result, with evidence.
  FAIL: Actual result does not match expected result. State the deviation exactly.
  BLOCKED: Pre-flight failed, Azure environment unavailable, preview feature
           behaviour not exposed, or API does not expose required information.

Step 6 — Update the workbook
  Update the POC case entry in the workbook:
  - Result: PASS | FAIL | BLOCKED
  - Evidence: Reference to captured output
  - Date executed
  - Environment details
  - Findings and observations (including unexpected behaviours)
  - If FAIL or BLOCKED: Escalate to Architect immediately

Step 7 — Hard Constraint Check (on unexpected findings)
  If the POC reveals behaviour that conflicts with a hard constraint:
  Run SK-03 immediately. Escalate the HC conflict to the Architect.
  Do not resolve the conflict in the POC record — it is an architecture input.
```

**Priority Execution Order**

```
P0 (execute first, highest risk):
  POC-001 — Consumer subscription quota on shared reservation
  POC-011 — MAX-not-SUM overcommit safety

P1 (execute next, gates Phase 4):
  POC-006 — DR subscription topology
  POC-007 — Bootstrap sizing

P2 (core sharing validation):
  G1–G8

P3 (offline-executable now, no Azure environment needed):
  G9  — Reservation eligibility
  G10 — Zone distribution
  G11 — Seed matrix validation
  G12 — Naming convention
```

**Outputs**

- Updated POC workbook entry (PASS/FAIL/BLOCKED + evidence)
- Escalation to Architect (if FAIL, BLOCKED, or HC conflict found)

**Owner:** ACRME POC Validation Engineer

---

### SK-06 — Capacity Formula Verification

**Purpose:** Verify any capacity or quota calculation against the ACRME core formulas from the requirements baseline (Appendix A and Appendix D). Prevents implementation drift from the approved formulas.

**Trigger — invoke this skill when:**
- Implementing any algorithm that computes reservation targets, buffer, DR sizing, or zone distribution
- Reviewing an existing calculation for correctness
- Responding to a question about how capacity or DR is sized

**Core Formulas (from Appendix A and D)**

#### Formula 1 — Reservation Target (CAP-003)

```
Target Reserved Capacity = Allocated VM Count + Configured Buffer
```

- **Allocated VM Count:** VMs currently running and consuming capacity (not associated-but-deallocated)
- **Configured Buffer:** Policy input per SKU/AZ/region/environment — not a hardcoded constant
- **Never:** `Target = Associated VM Count` (associated-only is explicitly rejected)

#### Formula 2 — DR Destination Sizing (DR-017, Appendix D — MAX-not-SUM)

```
Destination DR Requirement(d) = MAX over all source regions s { portion(s → d) }
```

Where:
- `d` = destination region
- `s` = each source production region that has DR mapped to `d`
- `portion(s → d)` = the DR portion of source `s` routed to destination `d`
- This uses MAX, not SUM — destination is sized for the largest single source, not the aggregate of all sources
- Rationale: sources are non-concurrent (DR-001); only one source fails at a time

```
Overcommit Ratio = SUM(portions routed to d) / MAX(portion routed to d)  [informational]
```

#### Formula 3 — Zone Distribution Target (PLC-011, CAP-023)

```
Even Zone Share = 1 / zone_count   (e.g., 33.3% per zone in a 3-zone region)
```

Skew tolerance is configurable per `PlacementPolicy` (C-13).

Rebalance trigger: actual zone share deviates from even share by more than configured tolerance.

#### Formula 4 — Production Growth Buffer (QUA-006)

```
Quota Top-Up Trigger: usage / allocated_quota > (1 - buffer_threshold)
Required Quota = current_usage + quota_buffer_headroom
```

**Process**

```
Step 1 — Identify the formula being used in the implementation or calculation
Step 2 — Match it against the canonical formulas above
Step 3 — Verify:
  a. Variable mapping: are "allocated", "associated", "buffer", "portion" used correctly?
  b. Operator: SUM vs MAX for DR destination (MAX-not-SUM is the hard constraint HC-6)
  c. Buffer: is it a configurable policy input, not a hardcoded value?
  d. Zone: is it `1/zone_count` with configurable tolerance?
Step 4 — Classify: CORRECT | DEVIATION | ERROR
Step 5 — If DEVIATION or ERROR: state the exact difference and the correct formula
```

**Outputs**

- Formula verification result: CORRECT | DEVIATION | ERROR
- If deviation: correct formula reference with source (CAP/DR code + Appendix)

**Owner:** Azure Capacity & Platform Architect / ACRME Implementation Engineer

**Platform Skill Registration:** ✅ Recommended — `acrme-formula-check`

---

### SK-07 — Requirements Traceability

**Purpose:** Trace any ACRME requirement from the baseline functional requirement (FR) through design (ADR / TDD component) to implementation (source module) and test coverage. Ensures no requirement falls through the gap between baseline and code.

**Trigger — invoke this skill when:**
- Verifying that a backlog epic/story maps to a documented requirement
- Auditing implementation completeness for a given requirement code
- Answering "has FR-X been implemented?" definitively

**Traceability Map**

| FR Domain | Requirement Codes | Design Component | Source Module | Test |
|---|---|---|---|---|
| FR-1 Capacity Inventory | CAP-001 to CAP-024 | `acrme_technical_design_document.md` §Inventory | `src/acrme/components/inventory.py` | `tests/` |
| FR-2 Reconciliation | CAP-005, CAP-006, CAP-007, CAP-008, CAP-009 | §Reconciler | `src/acrme/components/reconciler.py` | `tests/` |
| FR-3 Quota Management | QUA-001 to QUA-014 | §QuotaManager | `src/acrme/components/quota_manager.py` | `tests/` |
| FR-4 Readiness | RDY-001 to RDY-004 | §ReadinessGate | `src/acrme/domain/readiness.py` | `tests/` |
| FR-5 Placement | PLC-001 to PLC-011 | §PlacementEngine | `src/acrme/components/placement.py` | `tests/` |
| FR-6 DR Capacity | DR-001 to DR-019 | §DRManager | `src/acrme/components/dr_index_manager.py` `src/acrme/components/dr_activation.py` `src/acrme/algorithms/dr_sizing.py` | `tests/` |
| FR-7 Observability | OPS-001 to OPS-00x | §Observability | `src/acrme/observability/` | `tests/` |
| FR-8 Governance | CAP-010, CAP-019, PLC-005 | §Governance | TBD | TBD |

**Process**

```
Step 1 — Identify the requirement code(s) to trace (e.g., DR-017)
Step 2 — Find the requirement in the baseline (SK-01 read)
Step 3 — Find the design reference in the TDD or ADR
Step 4 — Find the source module that implements it
Step 5 — Find the test that validates it
Step 6 — Classify coverage:
  FULL:      Baseline → Design → Code → Test (all four layers)
  PARTIAL:   One or more layers missing
  GAP:       Requirement has no design, code, or test coverage
```

**Outputs**

- Traceability table for the traced requirement(s)
- Coverage classification (FULL / PARTIAL / GAP)
- List of gaps requiring action

**Owner:** Azure Capacity & Platform Architect / ACRME Documentation Steward

---

### SK-08 — Backlog Story Authoring

**Purpose:** Author new backlog stories and tasks in the ACRME project format. New stories arise from POC findings, design changes, baseline updates, and Phase kickoffs.

**Trigger — invoke this skill when:**
- A POC finding identifies new work not yet in the backlog
- A baseline update introduces a new or changed requirement
- A new Phase begins and stories need to be broken down from the epic

**Story Format**

```markdown
### S<ENN>-<NN> — <Story Title>

**Epic:** E<NN> — <Epic Title>
**Phase:** P<N>
**Points:** <Fibonacci: 1 2 3 5 8 13 21>
**Domain:** <FR-1 through FR-8 | CAP | QUA | PLC | DR | RDY | OPS>
**Requirements:** <Requirement codes: e.g., CAP-003, DR-017>
**Status:** `[ ]`

**Story:**
As a [role], I need [capability] so that [outcome].

**Acceptance Criteria:**
- [ ] AC-1: <Criterion>
- [ ] AC-2: <Criterion>
- [ ] AC-3: <Criterion>

**Tasks:**
- [ ] T1: <Task description> — <Points>
- [ ] T2: <Task description> — <Points>

**Dependencies:** <Story IDs or NONE>
**Blocked by:** <POC case IDs or NONE>
```

**Process**

```
Step 1 — Identify the source of the story
  POC finding / design decision / baseline requirement / phase kickoff

Step 2 — Map to an existing Epic (E01–E20)
  If no epic covers it, escalate to Architect for new epic creation.

Step 3 — Run SK-01 (Baseline Validation)
  Confirm the story requirement code exists in the baseline.

Step 4 — Run SK-03 (Hard Constraint Check)
  Confirm the story's implementation target does not violate a hard constraint.

Step 5 — Author the story using the format above
  Include exact requirement codes, not just descriptions.
  Acceptance criteria must be verifiable — not vague.
  Points follow Fibonacci: 1 2 3 5 8 13 21.
  Status starts as [ ] (unchecked).

Step 6 — Add to backlog file
  File: Reference-Material/backlog/acrme_epics_stories_tasks.md
  Insert under the correct Epic section.
  Update epic story count and phase totals.
```

**Outputs**

- Story entry in standard format, inserted into the backlog file
- Updated epic story count

**Owner:** Azure Capacity & Platform Architect / ACRME Documentation Steward

---

### SK-09 — DR Sizing Validation

**Purpose:** Validate any DR destination sizing decision against the MAX-not-SUM formula (DR-017, Appendix D) and the hard constraint HC-6. This skill is specifically for DR capacity calculations — it extends SK-06 with the full DR topology context.

**Trigger — invoke this skill when:**
- Sizing DR capacity for a destination region
- Reviewing a DR index entry
- Implementing `src/acrme/algorithms/dr_sizing.py`
- Assessing overcommit ratio for a proposed DR topology

**Inputs**

| Input | Description |
|---|---|
| DR Index | Source→destination mapping from `src/acrme/domain/dr_index.py` |
| Source portions | The DR portion of each source region assigned to the destination |
| Destination region | The region whose DR requirement is being sized |

**Process**

```
Step 1 — List all source regions routed to the destination
  Extract from DR index: { source_region → portion_size }

Step 2 — Apply MAX-not-SUM (HC-6)
  Destination DR Requirement = MAX({ portion(s → d) for all s })
  NOT: SUM({ portion(s → d) for all s })

Step 3 — Compute overcommit ratio (informational)
  Overcommit Ratio = SUM(all portions to d) / MAX(portion to d)
  Example: SUM=1200, MAX=600 → Overcommit Ratio = 2.0
  This means the destination is sized for 1 source failing at a time (non-concurrent assumption DR-001).

Step 4 — Validate against HC-6
  If the sizing uses SUM instead of MAX: FAIL — HC-6 violation.
  If the sizing uses MAX: PASS.

Step 5 — Validate the non-concurrent assumption (DR-001)
  Confirm that the sources mapped to this destination are modelled as non-concurrent.
  If simultaneous multi-region failure is being planned for: escalate to Architect —
  this is outside the default guaranteed model (DR-001) and requires separate funding/approval.

Step 6 — Record in DR index
  Update the DR index entry with:
  - Destination region
  - Source regions and portions
  - Computed MAX requirement
  - Overcommit ratio
  - Validation date
```

**Outputs**

- DR sizing validation result: PASS | FAIL (HC-6)
- Computed MAX requirement for the destination
- Overcommit ratio (informational)
- Updated DR index entry

**Owner:** Azure Capacity & Platform Architect / ACRME Implementation Engineer

**Platform Skill Registration:** ✅ Recommended — `acrme-dr-sizing-check`

---

### SK-10 — Readiness Gate Check

**Purpose:** Apply the 8-state readiness model (RDY-001/002) to validate whether a deployment target is capacity-ready. Used both in design review (validating the readiness API design) and in implementation (unit-testing the readiness gate).

**Trigger — invoke this skill when:**
- Reviewing the readiness API design or implementation
- Validating that a placement decision meets all readiness conditions
- Responding to "is region X ready for deployment?"

**The 8 Readiness States (RDY-002)**

| State | Meaning |
|---|---|
| `READY` | All checks pass; deployment may proceed |
| `READY_WITH_RISK` | Passes with a non-blocking risk present |
| `QUOTA_DEFICIT` | Consumer subscription quota insufficient |
| `RESERVATION_DEFICIT` | Reserved capacity insufficient for the target |
| `CAPACITY_UNAVAILABLE` | Azure cannot supply the requested capacity |
| `STALE_STATE` | Capacity/quota snapshot exceeds max age (RDY-004) |
| `POLICY_BLOCKED` | Placement policy or hard constraint prevents deployment |
| `VALIDATION_REQUIRED` | One or more validation checks could not complete |

**Readiness Conditions (RDY-001)**

A deployment is `READY` only when ALL pass:
1. Target region is approved and in the Standard capacity region set
2. Availability zone is supported in the target region
3. SKU is supported and in the managed scope
4. Reservation policy is known (scope file, CAP-001)
5. Reservation exists (if required; mandatory for production, ENV-001)
6. Sufficient reserved capacity OR approved over-allocation (CAP-018)
7. Sufficient consumer-subscription quota (QUA-013 — POC-gated)
8. State freshness within configured max age (RDY-004)
9. No blocking policy or hard constraint exception

**Process**

```
Step 1 — Evaluate each of the 9 readiness conditions
Step 2 — Assign state:
  All pass → READY
  Non-blocking risk → READY_WITH_RISK
  Quota check fails → QUOTA_DEFICIT
  Reservation check fails → RESERVATION_DEFICIT
  Azure supply unavailable → CAPACITY_UNAVAILABLE
  State too old → STALE_STATE
  Policy/HC blocks → POLICY_BLOCKED
  Check could not complete → VALIDATION_REQUIRED
Step 3 — Return machine-readable state
  The state is the AEP deployment gate — READY or READY_WITH_RISK allow deployment.
  All others halt deployment (CAP-017: fail safely).
```

**Outputs**

- Machine-readable readiness state (one of 8 values)
- Condition-by-condition check results
- Blocking reason if not READY or READY_WITH_RISK

**Owner:** Azure Capacity & Platform Architect / ACRME Implementation Engineer

---

### SK-11 — Region Model Validation

**Purpose:** Validate that a proposed placement decision, configuration change, or architectural recommendation correctly applies the region model (3-region for US, 2-region for all other geos, cross-geo DR for Middle East).

**Trigger — invoke this skill when:**
- Proposing placement for a new customer or geography
- Authoring or reviewing a seed record
- Discussing region strategy for any geography

**Region Model Rules**

```
Rule 1 — US (3-region model):
  Three Standard regions: West US 3, Central US, Canada Central.
  Each can host Prod, CVAL, or DR independently.
  No co-location required — three regions, three environments separate.

Rule 2 — All other geos (2-region model, ENV-003 / PLC-010a):
  Prod anchors in one Standard region.
  CVAL + DR co-locate in the other Standard region (deterministic, not optional).
  Co-location must be recorded in seed record: cval_region == dr_region.
  Co-located CVAL must not be double-counted as both live CVAL and DR headroom (PLC-010).

Rule 3 — Middle East (cross-geo DR, DEC-001 RESOLVED, v2.4):
  Prod + CVAL: ME-weighted Standard region (Saudi Arabia Central or UAE North).
  DR: cross-geo into EU-weighted Standard region (Switzerland North or Sweden Central).
  NOT a ME region for DR — this is a legal override, not a general 2-region property.

Rule 4 — Region-environment non-binding:
  ANY Standard region can host Prod, CVAL, or DR.
  No region is permanently assigned to one environment.
  The customer seed record records the actual assignment; geography does not determine environment.

Rule 5 — EUS2 exception:
  East US 2 is a restricted deployment region (exception, not Standard auto-select).
  North Europe, West Europe (EU), Japan East (APAC) are similarly exception/pending regions.
```

**Process**

```
Step 1 — Identify the geography of the proposed placement
Step 2 — Apply the correct region model (Rule 1, 2, or 3)
Step 3 — Validate:
  a. Prod region is a Standard capacity region (or approved exception)
  b. CVAL/DR co-location correctly applied for 2-region geos
  c. Middle East DR correctly routed cross-geo (not to a ME region)
  d. No region-environment binding assumed
Step 4 — Classify: VALID | INVALID
  If INVALID: state which rule is violated
```

**Outputs**

- Region model validation result: VALID | INVALID
- Rule violations if INVALID

**Owner:** Azure Capacity & Platform Architect

---

### SK-12 — Documentation Completeness Review

**Purpose:** Review any ACRME design document, ADR, or reference material for completeness — specifically that all normative detail from source material is included, not just high-level summaries.

**Trigger — invoke this skill when:**
- Completing an ADR or design document
- Reviewing a document authored by another agent
- Responding to a documentation quality concern

**The Completeness Checklist**

For any document derived from the requirements baseline, verify that the following normative detail is included where applicable:

| Check | Required content | Applies to |
|---|---|---|
| C-01 | Exact requirement codes (CAP-xxx, QUA-xxx, DR-xxx, etc.) — not paraphrased descriptions | All documents |
| C-02 | Core formulas verbatim (CAP-003 target, DR-017 MAX-not-SUM, zone distribution) | Capacity / DR docs |
| C-03 | The five-state engine state machine: `STEADY_STATE → DR_DECLARATION_PENDING → DR_EVENT_ACTIVE → FAILBACK_PENDING → INCIDENT_HOLD` | Reliability / DR ADRs |
| C-04 | VR-1 through VR-11 validation framework | Production readiness docs (§26–§32) |
| C-05 | 8 machine-readable readiness states (RDY-002) | Readiness / readiness API docs |
| C-06 | 9 readiness conditions (RDY-001) | Readiness docs |
| C-07 | Region classification table (Standard vs Restricted, per geography) | Region / placement docs |
| C-08 | HC-1 through HC-11 in full | Hard constraints reference / any doc with constraints |
| C-09 | Scoring formula components (PLC-007 live weighting: capacity, quota, buffers, zones, DR contribution) | Placement docs |
| C-10 | 10-step capacity lifecycle | Reliability / operational docs (§26–§32) |
| C-11 | Exact POC-gated assumptions labelled (e.g., QUA-013 POC-gated) | Any doc referencing sharing or quota |
| C-12 | Confidence classification per finding (Documented / Tested / Derived / Assumed) | All ADRs |

**Process**

```
Step 1 — Read the document under review
Step 2 — For each applicable check in the completeness checklist:
  a. Does the document include this content?
  b. Is it verbatim / exact, or a summary/paraphrase?
Step 3 — Classify each check: PRESENT | SUMMARISED (insufficient) | MISSING
Step 4 — Produce completeness report
Step 5 — Return document for revision if any check is SUMMARISED or MISSING
  Do not pass a document that replaces normative detail with summaries.
```

**Completeness Rule Origin**

> This skill exists because: "Agent delivered ADRs covering the four requested areas but omitted substantial normative detail present in Production Readiness Review §26–§32: the region classification model table, VR-1..VR-11 validation framework, the full five-state engine state machine, exact scoring formulas, and the 10-step capacity lifecycle. User: ADRs don't cover details in Production Readiness design, review and update the details accordingly." — Recorded lesson, 2026-08-27.

**Outputs**

- Completeness checklist results (C-01 through C-12: PRESENT / SUMMARISED / MISSING)
- COMPLETE or INCOMPLETE verdict
- Required revisions if INCOMPLETE

**Owner:** ACRME Documentation Steward (primary); Azure Capacity & Platform Architect (for ADRs)

**Platform Skill Registration:** ✅ Recommended — `acrme-doc-completeness`

---

## Skill Dependency Graph

```
Any proposed change
        │
        └──► SK-01 Baseline Validation  (always first)
                    │
                    ├──► SK-03 Hard Constraint Check  (block on any failure)
                    │           │
                    │           └──► SK-06 Capacity Formula Verification (for capacity/DR changes)
                    │                       │
                    │                       └──► SK-09 DR Sizing Validation (for DR changes)
                    │
                    ├──► SK-02 WAF Assessment (for architecture decisions)
                    │           │
                    │           └──► SK-04 ADR Authoring (records the decision)
                    │                       │
                    │                       └──► SK-12 Documentation Completeness Review
                    │
                    ├──► SK-05 POC Case Execution (for POC-gated items)
                    │
                    ├──► SK-07 Requirements Traceability (for implementation review)
                    │
                    ├──► SK-08 Backlog Story Authoring (for new work items)
                    │
                    ├──► SK-10 Readiness Gate Check (for placement/deployment decisions)
                    │
                    └──► SK-11 Region Model Validation (for placement decisions)
```

---

## Platform Skill Registration Candidates

The following skills are recommended for Abacus AI platform skill registration — encoded as persistent, single-click reusable skills available across ACRME conversations:

| SK ID | Recommended Platform Skill Name | Priority |
|---|---|---|
| SK-01 | `acrme-baseline-check` | **P0 — Register first** |
| SK-03 | `acrme-hc-check` | P0 |
| SK-06 | `acrme-formula-check` | P1 |
| SK-09 | `acrme-dr-sizing-check` | P1 |
| SK-02 | `acrme-waf-assessment` | P2 |
| SK-12 | `acrme-doc-completeness` | P2 |

> **Note:** SK-01 (`acrme-baseline-check`) should be the first skill registered. It underpins all other skills and is already a standing instruction — registering it as a platform skill makes it invocable by name in any ACRME conversation without re-stating the procedure.

---

## Skill × Agent Matrix

| Skill | Architect | Implementation Engineer | POC Validation Engineer | Documentation Steward | FinOps Analyst |
|---|---|---|---|---|---|
| SK-01 Baseline Validation | ✅ Primary | ✅ Required | ✅ Required | ✅ Primary | ⚪ As needed |
| SK-02 WAF Assessment | ✅ Primary | ⚪ Review | — | ⚪ Review | — |
| SK-03 Hard Constraint Check | ✅ Primary | ✅ Required | ✅ Required | ✅ Required | — |
| SK-04 ADR Authoring | ✅ Primary | — | — | ⚪ Review | — |
| SK-05 POC Case Execution | — | — | ✅ Primary | — | — |
| SK-06 Capacity Formula Verification | ✅ Primary | ✅ Required | — | ⚪ Review | ⚪ As needed |
| SK-07 Requirements Traceability | ✅ Primary | ⚪ As needed | — | ✅ Required | — |
| SK-08 Backlog Story Authoring | ✅ Primary | — | ⚪ As needed | ✅ Required | — |
| SK-09 DR Sizing Validation | ✅ Primary | ✅ Required | — | — | ✅ Required |
| SK-10 Readiness Gate Check | ✅ Primary | ✅ Required | — | — | — |
| SK-11 Region Model Validation | ✅ Primary | ⚪ As needed | — | ⚪ Review | — |
| SK-12 Documentation Completeness | ✅ Required | — | — | ✅ Primary | — |

`✅ Primary` = skill owner / primary user  `✅ Required` = mandatory for this agent's outputs  `⚪ As needed` = applies when relevant  `—` = not applicable
