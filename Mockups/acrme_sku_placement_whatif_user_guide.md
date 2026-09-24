# ACRME SKU-Level Placement WHAT-IF — User Guide (Phase 2)

**Workbook:** `acrme_sku_placement_whatif.xlsx`
**Builder:** `build_acrme_sku_scoring_whatif.py`
**Baseline:** Azure Capacity & Quota Management Consolidated Requirements Baseline v2.4
**Status:** Mockup / feasibility — derived planning figures only; not connected to live Azure state. Does **not** modify the v2.4 baseline or the Phase 1 workbook.

---

## 1. What this is (and how it differs from the region-selection what-if)

This is a **new, standalone** what-if — a *different kind of analysis* from `acrme_region_selection_whatif_acrme_regions.xlsx`.

| | Region-selection what-if | **This — SKU-level placement what-if (Phase 2)** |
|---|---|---|
| Capacity grain | ONE blended number per region | **Per SKU** (CAP-022/023) |
| Quota grain | ONE number per environment/region | **Per VM/quota family** (QUA-002/003/004) |
| Availability term (α) | blended region free-pool | **per-SKU `GROUP AVAIL` = MIN(reserved-free, family quota-available)** |
| Question answered | "Which region overall?" | **"For *this multi-SKU workload*, which region for Prod / CVAL / DR — and is it READY for every SKU?"** |
| Readiness | region-level | **RDY-002 per candidate (all active SKU lines must clear)** |
| SKUs per run | single | **up to 8 SKU lines per run** |

Phase 2 is the design-doc step *"availability-by-group in scoring: point α at per-SKU group-availability; emit RDY-002 readiness per candidate."* It is **read-only** — the freeze & logical-lock layer is **Phase 3** and is not in this file.

## 2. Workbook structure (processing order)

| Order | Sheet | Role | Editable |
|-------|-------|------|----------|
| 1 | **ReadMe** | In-workbook overview | No |
| 2 | **Request** | The placement request | **Yellow cells** |
| 3 | **Policy** | Score weights & thresholds | **Yellow cells** |
| 4 | **SKU_Family_Map** | SKU → quota family lookup | No |
| 5 | **SKU_Catalogue** | Managed SKU set (vCPU, family, flags) | No |
| 6 | **Capacity_By_SKU** | Reservation plane: Region × Env × SKU | No (rebuild) |
| 7 | **Quota_Groups** | Quota plane: pooled group per Region × Family | No (rebuild) |
| 8 | **Score_Prod** | SKU-grain placement score — Production | No — formulas |
| 9 | **Score_CVAL** | SKU-grain placement score — CVAL / NonProd | No — formulas |
| 10 | **Score_DR** | SKU-grain placement score — Disaster Recovery | No — formulas |
| 11 | **Result** | Recommended Prod/CVAL/DR + ranked candidates | No — formulas |

**Data flow:** `Request` + `Policy` → (read against) `Capacity_By_SKU` + `Quota_Groups` → `Score_Prod / Score_CVAL / Score_DR` → `Result`. Every computed cell is a live formula; edits propagate instantly.

## 3. How to run a scenario

### Request sheet (yellow cells only)

| Cell | Input | Notes |
|------|-------|-------|
| B4 | **Geography** | Dropdown: `US` or `EU`. Filters eligible regions. |
| B5 | **Customer ID** | Free text — flows to the Result sheet header. |
| B8–B15 | **SKU** (per line) | Dropdown of the 8 managed SKUs. Leave blank to skip a line. |
| C8–C15 | **VM Count** (per line) | Positive integer. Leave blank to skip a line. |

Both **SKU** and **VM Count** must be filled for a line to be active. Leaving either blank removes that line from all scoring.

Derived (auto-filled, read-only):

| Column | Derivation |
|--------|-----------|
| D — vCPU / instance | `VLOOKUP(SKU, SKU_Catalogue)` |
| E — Line Cores | `VM Count × vCPU` |
| F — Quota Family | `VLOOKUP(SKU, SKU_Family_Map)` |

**B17 (Active SKU lines)** and **B18 (Total requested cores)** are summary counters — read-only.

### Policy sheet (optional tuning)

Tune weights `w_alpha` / `w_beta` / `w_epsilon` (must sum to 1.00 — verify `B7`) and thresholds `risk_threshold` (default 0.10) and `min_buffer_floor`.

### Reading the results

Go to the **Result** sheet. It shows:

- **Recommended Placement** — the top-pick region per environment (Prod / CVAL / DR), its Placement Score, and its RDY-002 readiness state. Each recommendation satisfies **every active SKU line**.
- **Overall Readiness** — a summary signal based on the Prod top-pick.
- **Ranked Prod Candidates** — all 8 regions ranked by Placement Score (only eligible regions get a rank).

## 4. The scoring model (per candidate region, across all active SKU lines)

A region is **eligible** only when **every active SKU line** clears the availability gate. The score aggregates across lines using **bottleneck semantics** — a single thin line drags all components down.

### Availability gate (Meets-All)

For each active line `i` the sheet computes:

```
GROUP_AVAIL_i = MIN( SUMIFS(Capacity_By_SKU.ReservedFree, Region, SKU_i),
                     SUMIFS(Quota_Groups.QuotaAvail, Region, Family_i) )

line_meets_i  = IF( GROUP_AVAIL_i >= LineCore_i, 1, 0 )
```

A blank line contributes 1 (not a constraint). The region-level gate is:

```
Meets-All = MIN( line_meets_1, …, line_meets_8 )   [= 0 if any active line fails]
```

`Eligible = 1` only when `InGeo = 1` **AND** `Meets-All = 1`.

### Score components (eligible candidates only)

Each component is the **MIN** across active lines — the tightest constraint drives the score:

| Symbol | Formula per active line | Aggregate |
|--------|------------------------|-----------|
| **α** (availability fit) | `1 − LineCore_i / MIN(ReservedFree_i, QuotaAvail_i)` — headroom cushion left | `MIN(α_i)` |
| **β** (quota headroom) | `QuotaAvail_i / QuotaLimit_i` | `MIN(β_i)` |
| **ε** (buffer safety) | `ReservedFree_i / Reserved_i` | `MIN(ε_i)` |

Blank lines contribute 1 to every MIN (neutral). Components are clamped to `[0, 1]`.

**Placement Score:** `PS = w_alpha·α + w_beta·β + w_epsilon·ε` (defaults 0.50 / 0.30 / 0.20).

**Rank:** dense rank of PS among eligible candidates (Rank 1 = highest PS). The **top pick** per environment is `INDEX/MATCH` on Rank = 1; if no region is eligible it shows `NONE ELIGIBLE`.

**Binding Constraint:** for eligible rows, shows whether `CAPACITY` or `QUOTA` is the tighter limit (i.e., which of ε vs β is lower across lines).

## 5. Readiness states (RDY-002, per candidate)

The readiness hierarchy evaluates in strict priority order:

| State | Condition |
|-------|-----------|
| `NO_REQUEST` | No active SKU lines (B17 = 0). |
| `RESERVATION_DEFICIT` | At least one active line has `ReservedFree = 0` for this region. |
| `QUOTA_DEFICIT` | At least one active line has `QuotaAvail = 0` for this region. |
| `CAPACITY_DEFICIT` | `Meets-All = 0` — GROUP AVAIL < LineCore for at least one line, but no full zero-capacity line. |
| `READY_WITH_RISK` | Eligible (`Meets-All = 1`), but `MIN(α_i) < risk_threshold` (0.10 default) — thin cushion across lines. |
| `READY` | Eligible with comfortable cushion across all lines. |

The **Binding Constraint** column (col O) shows `CAPACITY` or `QUOTA` for eligible rows; `N/A` for ineligible.

## 6. Worked example (pre-loaded sample — verified with a headless recalc, 0 formula errors)

The workbook ships with a 2-line sample request (US geography):

| Line | SKU | VMs | vCPU | Line Cores | Family |
|------|-----|-----|------|-----------|--------|
| 1 | Standard_E32ads_v5 | 4 | 32 | **128 cores** | memory_optimized |
| 2 | Standard_D8as_v5 | 2 | 8 | **16 cores** | general_purpose |

**Total requested cores: 144** (shown in B18). **Active lines: 2** (shown in B17).

A region must have GROUP AVAIL ≥ 128 for E32ads_v5 **and** GROUP AVAIL ≥ 16 for D8as_v5 to pass Meets-All. The tighter constraint (E32ads_v5, 128 cores) dominates α, β, and ε via the MIN aggregation.

Expected observations (US, Prod):

- **East US 2** — passes both lines, `READY`. High α because E32ads_v5 headroom is large relative to 128 cores.
- **Canada Central** — mock region (0.5 × mean); likely `CAPACITY_DEFICIT` or `READY_WITH_RISK` on the E32ads_v5 line.
- **West US 3** — `RESERVATION_DEFICIT` by design (greenfield, ~0 observed allocation → quota limit = 0).
- **DR** — 30% bootstrap capacity (ENV-005); thin cushions push to `READY_WITH_RISK` for the large E32ads_v5 line.

To test a single-SKU scenario, clear lines 2–8 (leave B9:C15 blank) and update line 1 as needed. The formulas automatically reduce to single-line evaluation.

## 7. Data provenance & rulings baked in

- **Allocated** cores are derived from real usage (`SKU_USage.xlsx`). **Canada Central** is a flagged mock (0.5 × mean of the other US regions — it is absent from the source data). **DR = 30% of Prod** (ENV-005 bootstrap, not a full duplicate).
- **West US 3** shows deficits across SKUs by design: the source data has ~0 observed allocation there, so its quota limit is 0 — the correct signal for a reserved-but-unprovisioned greenfield region.
- Rulings from Phase 1: one **pooled** quota group per region+family across Prod+NonProd+DR (QUA-004); ENV-003 hard separation applies to **capacity reservations only** (quota pooled — separate planes); quota **hoarded** to one pool and distributed on demand (QUA-003).

## 8. Limitations / deferred

- **Read-only feasibility** — does not modify the v2.4 baseline or the Phase 1 workbook.
- **8-line cap** — the Request sheet supports up to 8 concurrent SKU lines. Workloads exceeding 8 SKU types require a separate run or a builder extension.
- **CRG scope is regional** (`crg-…-reg`); per-AZ CRGs (CAP-023, `crg-…-az1`) are a later increment.
- **Freeze & logical lock** (the `LOCKED` state + `Allocation_Ledger`, logical-vs-physical CAP-002 distinction) is **Phase 3** — not in this file.
- **SKU→family map is naming-derived**; a canonical Azure family table would replace `SKU_Family_Map`.
- `total_customers` (γ distribution term) remains undefined in v2.4 — not used by this model, still an open baseline issue.

---

*Phase 2 SKU-grain placement what-if (multi-SKU, up to 8 lines) — baseline v2.4 · updated 24 Sep 2026*
