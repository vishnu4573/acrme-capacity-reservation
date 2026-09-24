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
| Question answered | "Which region overall?" | **"For *this SKU*, which region for Prod / CVAL / DR — and is it READY?"** |
| Readiness | region-level | **RDY-002 per candidate** |

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

1. **Request sheet** (yellow): set `Geography` (US/EU dropdown), `Requested SKU` (dropdown of the 8 modelled SKUs), `VM count`, `Customer ID`. The sheet derives **Quota Family**, **vCPU/instance**, and **Requested cores** (= VMs × vCPU).
2. *(Optional)* **Policy sheet** (yellow): tune weights `w_alpha` / `w_beta` / `w_epsilon` (must sum to 1.00 — check `B7`) and thresholds `risk_factor`, `min_buffer_floor`.
3. Read **Result**: the recommended region per environment, its PS and readiness, the overall readiness, and the ranked Prod-candidate table.

> **One SKU per run.** Placement is evaluated at SKU grain, so a multi-SKU workload is run once per SKU.

## 4. The scoring model (per candidate region, for the requested SKU)

For each of the 8 candidate regions, in each environment, the sheet pulls the region's numbers for the **requested SKU** from `Capacity_By_SKU` / `Quota_Groups` via `SUMIFS` keyed on (Region, Environment, SKU) and (Region, Family):

| Column | Meaning | Formula (essence) |
|--------|---------|-------------------|
| Reserved / Reserved-Free | reservation for this SKU | `SUMIFS(Capacity_By_SKU!J / K, …)` |
| Family Q-Limit / Q-Avail | pooled quota for the family | `SUMIFS(Quota_Groups!E / G, …)` |
| **GROUP AVAIL** | **placeable headroom** | **`=MIN(Reserved-Free, Family Q-Avail)`** |
| InGeo | region geography = requested geography | `=IF(B=Request!Geo,1,0)` |
| Meets-Cap | GROUP AVAIL ≥ requested cores | `=IF(GROUP AVAIL≥Req Cores,1,0)` |
| Readiness (RDY-002) | per-candidate state | see §5 |
| Eligible | `InGeo AND Meets-Cap` | `=IF(AND(InGeo,Meets-Cap),1,0)` |

**Score components (only for eligible candidates):**

- **α (availability fit)** = `1 − requested cores / GROUP AVAIL` — the **headroom cushion left after placement**. Higher = safer. *This is the SKU-grain change* — α is driven by the per-SKU group availability, not a blended region pool. (Chosen over a capped `MIN(avail/req,1)` because that saturates at 1 and fails to discriminate between candidates; the cushion form ranks regions by how much room remains.)
- **β (quota headroom)** = `family quota-available / family quota-limit`.
- **ε (buffer safety)** = `reserved-free / reserved`.

**Placement Score:** `PS = w_alpha·α + w_beta·β + w_epsilon·ε` (defaults 0.50 / 0.30 / 0.20).

**Rank:** dense rank of PS among eligible candidates (Rank 1 = highest PS). The **top pick** per environment is `INDEX/MATCH` on Rank = 1; if no region is eligible it shows `NONE ELIGIBLE`.

## 5. Readiness states (RDY-002, per candidate)

| State | Condition |
|-------|-----------|
| `RESERVATION_DEFICIT` | reserved-free ≤ 0, or capacity is the binding shortfall when GROUP AVAIL < requested |
| `QUOTA_DEFICIT` | family quota-available ≤ 0, or quota is the binding shortfall when GROUP AVAIL < requested |
| `READY_WITH_RISK` | eligible but GROUP AVAIL < requested cores × `risk_factor` (thin cushion) |
| `READY` | eligible with comfortable cushion |

The **Binding Constraint** column shows whether CAPACITY or QUOTA is the limiter for that row.

## 6. Worked examples (verified with a headless recalc — 0 formula errors)

**Scenario A — `Standard_E32ads_v5`, 6 VMs (192 cores), US:**
- **Prod →** East US 2 (`GROUP AVAIL` 684, READY) — the only US region with enough per-SKU headroom; Central US and Canada Central fall to `RESERVATION_DEFICIT`, West US 3 to `QUOTA_DEFICIT` (greenfield, no quota provisioned).
- **CVAL →** ranks **East US 2 (α 0.978) > Canada Central (0.877) > Central US (0.650)** — the cushion-based α discriminates correctly.
- **DR →** East US 2, `READY_WITH_RISK` (DR is a 30% bootstrap, so cushions are thin).

**Scenario B — `Standard_D8as_v5`, 2 VMs (16 cores), US:**
- **Prod →** East US 2 (1191) > Central US (613) > Canada Central (301); all `READY`. DR now `READY` too (small request fits the bootstrap).

## 7. Data provenance & rulings baked in

- **Allocated** cores are derived from real usage (`SKU_USage.xlsx`). **Canada Central** is a flagged mock (0.5 × mean of the other US regions — it is absent from the source data). **DR = 30% of Prod** (ENV-005 bootstrap, not a full duplicate).
- **West US 3** shows deficits across SKUs by design: the source data has ~0 observed allocation there, so its quota limit is 0 — the correct signal for a reserved-but-unprovisioned greenfield region.
- Rulings from Phase 1: one **pooled** quota group per region+family across Prod+NonProd+DR (QUA-004); ENV-003 hard separation applies to **capacity reservations only** (quota pooled — separate planes); quota **hoarded** to one pool and distributed on demand (QUA-003).

## 8. Limitations / deferred

- **Read-only feasibility** — does not modify the v2.4 baseline or the Phase 1 workbook.
- **One SKU per run** (SKU grain).
- **CRG scope is regional** (`crg-…-reg`); per-AZ CRGs (CAP-023, `crg-…-az1`) are a later increment.
- **Freeze & logical lock** (the `LOCKED` state + `Allocation_Ledger`, logical-vs-physical CAP-002 distinction) is **Phase 3** — not in this file.
- **SKU→family map is naming-derived**; a canonical Azure family table would replace `SKU_Family_Map`.
- `total_customers` (γ distribution term) remains undefined in v2.4 — not used by this model, still an open baseline issue.

---

*Phase 2 SKU-grain placement what-if — baseline v2.4 · created 24 Sep 2026*
