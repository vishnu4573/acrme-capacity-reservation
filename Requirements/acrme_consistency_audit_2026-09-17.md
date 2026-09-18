# ACRME Repo Consistency Audit — 17 September 2026

**Scope.** Full sweep of the ACRME documentation set (`Requirements/`, `Architecture/adr/`, `Design/`, `Reference-Material/`, `POC-Test-Scripts/`) checked against (a) the requirements baseline and (b) the canonical calculation formulas & constants. `Archive/` excluded (historical). Auto-generated `.docx`/`.pdf` twins excluded (they regenerate from their `.md`).

**Authority sources used for the audit**
- Requirements: `Requirements/acrme_requirements_baseline_v2_4.md` — **v2.4 (amended), 11 September 2026** (the newest baseline in the repo).
- Formulas & constants: `Reference-Material/reference/acrme_calculation_logic_reference.md`.

**Bottom line.** The repo is internally consistent. The audit found **two** issues, both now **RESOLVED**: (1) the uploaded "source of truth" baseline was stale vs. the repo baseline — now synchronized to the amended 11-Sep version; (2) one internal typo (5-min vs. 6-min reconciliation interval) — corrected. All documents now reconcile to the authoritative baseline v2.4 (amended), 11 September 2026.

---

## Finding 1 — HIGH — The uploaded "source of truth" baseline was STALE vs. the repo baseline [RESOLVED]

The standing instruction points at the uploaded file as the single source of truth, but it is an **older revision** than the baseline committed in the repo, and **every other document in the repo reconciles to the newer repo baseline, not the uploaded one.**

| | Uploaded file | Repo baseline |
|---|---|---|
| Path | `/home/ubuntu/Uploads/Azure Capacity & Quota Management- Consolidated Requirements Baseline.md` | `Requirements/acrme_requirements_baseline_v2_4.md` |
| Version / date | v2.4, **7 September 2026** | **v2.4 (amended), 11 September 2026** |
| Middle East DR | **`DR_NOT_OFFERED`** ("DR is unlikely to be offered there") | **Cross-geo DR to Europe** (Prod+CVAL co-located in a weighted-selected ME region; DR weighted-selected in a Europe Standard region) |
| DEC-001 | Pending / open | **RESOLVED** |
| Extra normative IDs | — | Adds **DR-020, PLC-010b, A-ME1** |

**Impact.** All downstream docs — ADRs, FDD, TDD, calc-logic reference, POC workbook, epics/stories, complete requirements reference — already implement the **amended (11-Sep)** Middle East cross-geo position with DEC-001 RESOLVED. Examples:
- `Requirements/acrme_complete_requirements_reference.md:103,302` — cross-geo DR into Europe (DR-020, PLC-010b, DEC-001 RESOLVED).
- `POC-Test-Scripts/acrme_poc_workbook_v2_4.md:19,144,2167` — POC-PLC-010b positive cross-geo case; supersedes `DR_NOT_OFFERED`.
- `Reference-Material/backlog/acrme_epics_stories_tasks.md:593,697` — ACRME-S0706 Middle East cross-geo DR (DEC-001 RESOLVED).

So the repo is coherent **against the amended repo baseline**; the divergence is only against the **uploaded** file the standing instruction names.

**Resolution (confirmed by user):** The amended 11-Sep baseline is authoritative. The uploaded file at `/home/ubuntu/Uploads/Azure Capacity & Quota Management- Consolidated Requirements Baseline.md` has been **synchronized** with the repo baseline — both now carry **v2.4 (amended), 11 September 2026** with Middle East cross-geo DR, DEC-001 RESOLVED, DR-020, PLC-010b, A-ME1. The standing instruction source of truth and the repo are now aligned.

---

## Finding 2 — LOW — Reconciliation interval typo (FIXED in this change)

`Design/acrme_uml_class_diagrams_summary.md:64` stated the reconciliation loop target interval as **5 minutes**. Every other source says **6 minutes (360 s), configurable**:
- Baseline **CAP-006**;
- `Design/acrme_technical_design_document.md:135` — "6-minute target interval (configurable, CAP-006)";
- `Reference-Material/reference/acrme_calculation_logic_reference.md:610`.

**Fix applied:** line 64 now reads *"6-min target interval (configurable, CAP-006)"*.

---

## Finding 3 — MEDIUM — Fixed DR ratio still live in Hard Constraints / ADR-007 (CONVERTED to max-not-sum in this change)

While the Calculation Logic Reference already sized DR with **max-not-sum** (A.6 / DR-017 / Scenario 17) and marked Scenario 15 superseded, several docs still **actively computed HC-6 / HC-7 with the fixed `dr_ratio_max = 0.40`** — the exact model the calc ref says must NOT be used. This was an internal inconsistency, now resolved by retiring the fixed `dr_ratio_*` model everywhere it was still a *live* formula and converting to max-not-sum plus the configurable DR bootstrap target (DR-007).

**Files converted:**
- `Reference-Material/reference/acrme_hard_constraints_reference.md` — HC-6 (per-customer DR demand → `dr_bootstrap_qty`, DR-007), HC-7 DR floor (`DR_Floor_vCPU(R) = Destination_DR_Requirement(R) × vCPU`, `Destination_DR_Requirement(R) = MAX(source portions)`), POC example reframed, policy JSON + constants table (`dr_ratio_*` marked ❌ Retired).
- `Reference-Material/reference/acrme_calculation_logic_reference.md` — fixed internal inconsistency in `coverage_ratio` denominator (was `Σ potential_dr_demand`, now `Destination_DR_Requirement = MAX(...)`, matching line ~465); Scenario 15 reframed **Retired (historical rationale only)**; clarified the C-11 SUM override sums actual source portions and does **not** reintroduce `dr_ratio`; summary/disambiguation tables → Retired.
- `Architecture/adr/acrme_adr_007_crg_deployment_model.md` — Appendix B HC-6/HC-7 formulas converted to bootstrap + max-not-sum.
- `Requirements/acrme_complete_requirements_reference.md` — FR-5.6 traceability note updated to max-not-sum floor + configurable bootstrap.
- `Design/acrme_technical_design_document.md`, `Reference-Material/reference/ACRME_Scoring_Weights_Explained.md`, `Reference-Material/reference/acrme_plain_english_walkthrough.md`, and calc ref PS_DR — the scoring δ term's normalization constant renamed `dr_ratio_target` → `dr_coverage_target` and annotated as a **scoring-only** reference (its `coverage_ratio` uses the max-not-sum denominator), NOT the retired sizing ratio.
- `POC-Test-Scripts/acrme_poc_workbook_v2_4.md` — assumption A-09 ("30–40% baseline is sufficient") marked **RETIRED**.

**Preserved (historical rationale, intentionally not removed):** the $1.5M–$5M/year idle-cost justification (Scenario 15, ADR-002/003/005, baseline Appendix D), ENV-005 "must NOT default to fixed 30–40%", and C-1's ratio-evolution history. **Out of scope:** `Archive/` documents (historical snapshots) retain the old fixed-ratio formulas by design.

**No conversion needed (already correct):** FDD §4.5, ADR-002/003/005, comprehensive walkthrough, code glossary C-1, and the baseline itself — all already state max-not-sum / configurable bootstrap and reject the fixed ratio.

---

## Items reviewed and confirmed CONSISTENT (no action)

- **Formulas A.1–A.9** (baseline Appendix A) match the calc-logic reference — including A.6 DR destination sizing = **MAX not SUM** over sources (DR-017) and A.9 even-zone share = 1/zone_count.
- **Scoring weights** α=0.30, β=0.20, γ=0.25, δ=0.15, ε=0.10 (sum 1.0) — consistent wherever cited (marked `[Assumed]` in the calc ref, which is correct; the baseline does not fix them numerically).
- **Growth buffers** prod/nonprod = 0.20, emergency transfer = 0.30; **auto-increase thresholds** dr=0.35, prod=0.20, nonprod=0.20; debounce 30 min — consistent.
- **Region model** (US 3-region; EU/AU/APAC 2-region co-located; Middle East cross-geo) — consistent across ADRs, FDD, TDD, POC, backlog.
- **ADRs** — no inconsistencies. ADR-007 is intentionally `PROPOSED` (pending POC-001/006, DEP-001); its §15 note that CAP-013 wording says "up to ~100" while Azure's hard limit is exactly 100 is a documented wording nit, not a contradiction.

## Known open design gaps (not inconsistencies — noted for awareness)

- **`total_customers` denominator** in the γ (fairness) term is not defined in the baseline. Already captured as an OPEN ISSUE in `Reference-Material/reference/acrme_calculation_logic_comprehensive_walkthrough.md` (prior commit) — left as-is.
- **PS_NonProd design-of-record** intentionally combines α and δ signal (0.45); flagged in the PRR with a corrected pilot variant — intentional, not an error.
- **Scenario 15** (fixed `dr_ratio`) is now **RETIRED** and every live HC-6/HC-7 formula has been converted to max-not-sum (see Finding 3). Historical rationale retained by design.
