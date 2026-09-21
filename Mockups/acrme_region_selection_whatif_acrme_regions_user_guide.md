# ACRME Region Selection WHAT-IF Tool — User Guide

**Workbook:** `acrme_region_selection_whatif_acrme_regions.xlsx`  
**Baseline:** Azure Capacity & Quota Management Consolidated Requirements Baseline v2.4  
**Status:** Mockup / Planning Tool — derived planning figures only; not connected to live Azure state  

---

## Table of Contents

1. [Purpose and Scope](#1-purpose-and-scope)
2. [Workbook Architecture](#2-workbook-architecture)
3. [Reading the Result Sheet](#3-reading-the-result-sheet)
4. [Setting Up a Scenario — Setup Sheet](#4-setting-up-a-scenario--setup-sheet)
5. [Updating Capacity Data — Capacity_Usage Sheet](#5-updating-capacity-data--capacity_usage-sheet)
   - [5.1 Which Cells Are Editable](#51-which-cells-are-editable)
   - [5.2 Worked Example A — Expanding Reserved Capacity](#52-worked-example-a--expanding-reserved-capacity)
   - [5.3 Worked Example B — Updating Quota Limits After a Microsoft Increase](#53-worked-example-b--updating-quota-limits-after-a-microsoft-increase)
6. [Running Multiple-SKU Scenarios](#6-running-multiple-sku-scenarios)
   - [6.1 Why the Tool Models One SKU per Run](#61-why-the-tool-models-one-sku-per-run)
   - [6.2 Worked Example — E32ads_v5 + E16ads_v5 Dual-SKU Deployment](#62-worked-example--e32ads_v5--e16ads_v5-dual-sku-deployment)
7. [Calculation Logic Reference](#7-calculation-logic-reference)
   - [7.1 Setup Sheet Lookups](#71-setup-sheet-lookups)
   - [7.2 Capacity_Usage Computed Columns](#72-capacity_usage-computed-columns)
   - [7.3 HC_Gate — Hard Constraint Eligibility Checks](#73-hc_gate--hard-constraint-eligibility-checks)
   - [7.4 Scoring Engine — Placement Score (PS)](#74-scoring-engine--placement-score-ps)
   - [7.5 Scoring_Prod — Formula Details](#75-scoring_prod--formula-details)
   - [7.6 Scoring_CVAL — Formula Details and Differences](#76-scoring_cval--formula-details-and-differences)
   - [7.7 Scoring_DR — Formula Details and Differences](#77-scoring_dr--formula-details-and-differences)
   - [7.8 Result Sheet Derivation](#78-result-sheet-derivation)
8. [Policy Sheet — Tuning Weights and Thresholds](#8-policy-sheet--tuning-weights-and-thresholds)
9. [Known Limitations and Design Gaps](#9-known-limitations-and-design-gaps)
10. [Quick Reference Tables](#10-quick-reference-tables)

---

## 1. Purpose and Scope

This workbook implements a **weighted capacity placement model** for the ACRME (Automated Customer-Region Management Engine) programme. Given a customer's geography, SKU, and VM count, it evaluates all 14 ACRME in-scope regions and recommends:

- **Prod region** — the production placement
- **CVAL region** — the Customer Validation / non-prod placement
- **DR region** — the disaster recovery placement

The tool is a **planning mockup**, not a live API. Capacity figures are derived from real usage data (distributed onto the baseline v2.4 region catalogue per the builder script) and are refreshed by re-running `build_acrme_whatif_acrme_regions.py`. All cell formulas respond instantly to edits in the yellow input cells and the Capacity_Usage data rows — no macro or recalculation button is required.

### Scope of This Guide

This guide covers:
- How to update capacity and quota data (with worked examples)
- How to model multi-SKU customer deployments
- A full explanation of every formula in the workbook, traced to the actual cell references

**Out of scope:** modifying the 14-region catalogue (CATALOGUE list in the builder), changing geographic distribution weights, or rerunning the builder script — those are engineering activities requiring a rebuild.

---

## 2. Workbook Architecture

The workbook contains 10 sheets in processing order:

| Order | Sheet | Role | User-editable |
|-------|-------|------|---------------|
| 1 | **How_To_Use** | Navigation guide and colour legend | No |
| 2 | **Usage_Source** | Raw source data imported from `SKU_USage.xlsx` and `sku_usage_prod_v1.xlsx` | No |
| 3 | **Setup** | Scenario inputs: geography, SKU, VM count, customer ID | **Yellow cells only** |
| 4 | **Policy** | Weight parameters, headroom thresholds, total_customers mode | **Yellow cells only** |
| 5 | **Capacity_Usage** | Capacity and quota state for all 14 ACRME regions | **Specific columns** (see §5.1) |
| 6 | **HC_Gate** | Hard-constraint eligibility checks for each region | No — all formulas |
| 7 | **Scoring_Prod** | Weighted placement scoring for the Prod environment | No — all formulas |
| 8 | **Scoring_CVAL** | Weighted placement scoring for the CVAL environment | No — all formulas |
| 9 | **Scoring_DR** | Weighted placement scoring for the DR environment | No — all formulas |
| 10 | **Result** | Recommended Prod/CVAL/DR regions and ranked candidate table | No — all formulas |

### Data Flow (text diagram)

```
Setup (inputs) ──────────────────────────────────────┐
                                                      ▼
Capacity_Usage (state) ──► HC_Gate (pass/fail) ──► Scoring (PS) ──► Result
Policy (weights/thresholds) ─────────────────────────┘
```

Every computed cell is a live Excel formula — edits to Setup, Policy, or Capacity_Usage propagate automatically throughout the chain.

### The 14 ACRME Regions (baseline v2.4, Section 6)

| Row | Region Name | Region ID | Geography | AZ | Model | Class |
|-----|-------------|-----------|-----------|-----|-------|-------|
| 4 | West US 3 | westus3 | US | 3 | 3-region | Standard |
| 5 | Central US | centralus | US | 3 | 3-region | Standard |
| 6 | Canada Central | canadacentral | US | 3 | 3-region | Standard |
| 7 | East US 2 | eastus2 | US | 3 | 3-region | Standard |
| 8 | Switzerland North | switzerlandnorth | EU | 3 | 2-region | Standard |
| 9 | Sweden Central | swedencentral | EU | 3 | 2-region | Standard |
| 10 | North Europe | northeurope | EU | 3 | 2-region | Standard |
| 11 | West Europe | westeurope | EU | 3 | 2-region | Standard |
| 12 | Australia East | australiaeast | AU | 3 | 2-region | Standard |
| 13 | Australia Southeast | australiasoutheast | AU | 2 | 2-region | Standard |
| 14 | East Asia | eastasia | AP | 3 | 2-region | Standard |
| 15 | Southeast Asia | southeastasia | AP | 3 | 2-region | Standard |
| 16 | Saudi Arabia Central | saudicentral | ME | 3 | cross-geo | **Restricted** |
| 17 | UAE North | uaenorth | ME | 3 | cross-geo | **Restricted** |

`AU` = Australia · `AP` = Asia Pacific · `ME` = Middle East  
**Restricted** = not auto-selected by the engine; requires the Prod region to be explicitly named in Setup!B8.

---

## 3. Reading the Result Sheet

Open **Result** (the last sheet) to see the recommended placements for the current scenario.

### Primary Placements (rows 9–11)

| Cell | Content |
|------|---------|
| B9 | Recommended **Prod region** (or `NONE ELIGIBLE`) |
| C9 | Prod placement score (0.00–1.00) |
| B10 | Recommended **CVAL region** (or `NONE ELIGIBLE`) |
| C10 | CVAL placement score |
| B11 | Recommended **DR region** (or `NONE ELIGIBLE`) |
| C11 | DR placement score |

### Readiness State (B13)

| Value | Meaning |
|-------|---------|
| `READY` | All three placements found; deployment can proceed |
| `QUOTA_DEFICIT / NEEDS EXPLICIT REGION (Prod)` | No Prod-eligible region — check quota data in Capacity_Usage and/or name the Prod region explicitly in Setup!B8 |
| `CAPACITY_UNAVAILABLE (CVAL)` | No CVAL-eligible region in the selected geography |
| `READY_WITH_RISK (no DR region)` | Prod and CVAL placed but no DR region qualifies — check DR free capacity and HC_Gate DR column |

### Ranked Candidate Table (rows 4+, columns H–P)

The ranked table shows all eligible candidates across the three placement modes (Prod / CVAL / DR) with their placement scores. Use this to understand why a particular region ranked first or fell below the winner.

---

## 4. Setting Up a Scenario — Setup Sheet

All scenario parameters are entered in **Setup** column B, rows 3–9. Cells are highlighted yellow. All other cells in Setup are computed and must not be edited.

| Cell | Parameter | Input type | Example |
|------|-----------|-----------|---------|
| **B3** | Geography | Dropdown: US / EU / Australia / Asia Pacific / Middle East | `US` |
| **B4** | SKU | Dropdown: E16ads_v5 / E32ads_v5 / E8ads_v5 / E4ads_v5 / D8ads_v5 / D4ads_v5 / D2ads_v5 / D16ads_v5 | `E32ads_v5` |
| **B5** | VM count (number of VMs for this deployment) | Positive integer | `4` |
| **B8** | Prod region override | Text — Azure region ID; leave blank for auto-selection | `eastus2` |
| **B9** | Customer ID | Text reference | `CUST-0042` |

### Computed (do not edit)

| Cell | Formula | Meaning |
|------|---------|---------|
| B6 | `=VLOOKUP(B4,E3:F10,2,FALSE)` | vCPU per VM from the SKU catalogue in E3:F10 |
| B7 | `=B5*B6` | Total **Requested vCPU** — this is the key sizing input used throughout HC_Gate and Scoring |
| B10 | `=VLOOKUP(B3,E13:G17,2,FALSE)` | Distribution model for the selected geography |
| B11 | `=VLOOKUP(B3,E13:G17,3,FALSE)` | DR scope geography (US → US; EU/AU/AP → same geo; Middle East → EU for cross-geo DR) |

### SKU Catalogue (Setup E3:F10)

| SKU | vCPU per VM |
|-----|------------|
| E32ads_v5 | 32 |
| E16ads_v5 | 16 |
| D16ads_v5 | 16 |
| E8ads_v5 | 8 |
| D8ads_v5 | 8 |
| E4ads_v5 | 4 |
| D4ads_v5 | 4 |
| D2ads_v5 | 2 |

**Example:** B4 = `E32ads_v5`, B5 = `4` → B6 = `32`, B7 = `128` vCPU requested.

---

## 5. Updating Capacity Data — Capacity_Usage Sheet

### 5.1 Which Cells Are Editable

The Capacity_Usage sheet has 22 columns (A–V). Only the columns below accept manual input; the rest are either static catalogue data (locked) or formulas that compute automatically.

**Editable columns (yellow):**

| Col | Header | What to enter |
|-----|--------|---------------|
| **F** | Prod Reserved | Total vCPU held in Production capacity reservations for this region |
| **G** | Prod Alloc | Total vCPU currently allocated (VM instances consuming Prod reservations) |
| **I** | Prod Q-Limit | Production subscription quota limit (vCPU) for the region's VM family |
| **J** | Prod Q-Used | Current production quota consumption (vCPU) |
| **L** | NP Reserved | Total vCPU in Non-Production (CVAL) capacity reservations |
| **M** | NP Alloc | Total vCPU currently allocated in Non-Prod reservations |
| **O** | NP Q-Limit | Non-Production subscription quota limit (vCPU) |
| **P** | NP Q-Used | Current Non-Prod quota consumption (vCPU) |
| **R** | DR Reserved | Total vCPU in DR capacity reservations |
| **S** | DR Free | DR vCPU not currently allocated (the available DR pool) |
| **T** | DR Coverage | DR coverage ratio (0.0–1.0, e.g. `0.6` = 60% of Prod workload covered) |
| **U** | Cust Count | Number of customers currently placed in this region |

**Computed columns (do not edit — formula cells):**

| Col | Header | Formula |
|-----|--------|---------|
| **H** | Prod Free | `=F-G` (Prod Reserved minus Prod Alloc) |
| **K** | Prod Q-Headroom | `=I-J` (Prod Q-Limit minus Prod Q-Used) |
| **N** | NP Eff-Free | `=L-M` (NP Reserved minus NP Alloc) |
| **Q** | NP Q-Headroom | `=O-P` (NP Q-Limit minus NP Q-Used) |

**Static catalogue columns (do not edit):**

| Col | Content |
|-----|---------|
| A | Region ID (e.g. `eastus2`) |
| B | Region Name (e.g. `East US 2`) |
| C | Geography (`US`, `EU`, `Australia`, `Asia Pacific`, `Middle East`) |
| D | Distribution Model (`3-region`, `2-region`, `cross-geo`) |
| E | Availability Zone count (2 or 3) |
| V | Class (`Standard` or `Restricted`) |

> **Important:** Never edit columns A–E or V. These match the ACRME catalogue definition in baseline v2.4 Section 6. Changing them will corrupt HC_Gate and Scoring formulas that reference them by value.

### 5.2 Worked Example A — Expanding Reserved Capacity

**Scenario:** Microsoft has provisioned an additional 32,768-core capacity reservation in East US 2 for Production. Update the workbook to reflect the expanded reservation.

**Before (East US 2, row 7):**

| Col | Header | Value |
|-----|--------|-------|
| F | Prod Reserved | 154,178 |
| G | Prod Alloc | 142,756 |
| H | Prod Free (computed) | **11,422** |

**Step 1:** Click cell **F7** (East US 2, Prod Reserved).  
**Step 2:** Change the value from `154178` to `186946` (154,178 + 32,768).  
**Step 3:** Press Enter. Cell H7 recalculates immediately:

| Col | Header | New value |
|-----|--------|-----------|
| F | Prod Reserved | 186,946 |
| G | Prod Alloc | 142,756 (unchanged) |
| H | Prod Free (computed) | **44,190** |

**Effect on downstream sheets:**

- **HC_Gate row 7 (East US 2):** The Prod quota headroom (K7) drives HC-3 Prod, not Prod Reserved. If the quota limit has not changed, HC-3 Prod stays the same. Prod Free (H) is informational here.
- **Scoring_Prod row 7:** α_raw = `NP Eff-Free / Prod Reserved` = N7 / F7. Increasing F7 slightly *lowers* α_raw — the ratio of NP headroom to prod size decreases. This is by design: a larger regional footprint signals higher demand pressure.

**When to update Prod Reserved (F):** Whenever Microsoft confirms a new Capacity Reservation Group (CRG) is provisioned or an existing CRG has its count adjusted via the reservation management workflow (CAP-009/CAP-022).

---

**Scenario 2 (within Example A):** A batch of 500 E32ads_v5 VMs (= 500 × 32 = 16,000 vCPU) is deployed into East US 2 Production. Update allocation.

**Step 1:** Click cell **G7** (Prod Alloc).  
**Step 2:** Change from `142756` to `158756` (142,756 + 16,000).  
**Step 3:** Press Enter. H7 recalculates:

| Col | Before | After |
|-----|--------|-------|
| G | 142,756 | 158,756 |
| H | 11,422 | −3,810 (deficit!) |

The negative H7 value means Prod Alloc exceeds Prod Reserved — a reservation deficit (A.3 from Appendix A). This is **visible but does not trigger a formula error**; it will however cause HC_Gate checks to fail if they rely on Prod Free. Treat any negative H value as an urgent action item: raise a CRG quantity increase.

### 5.3 Worked Example B — Updating Quota Limits After a Microsoft Increase

**Scenario:** Microsoft granted a quota increase of 50,000 vCPU for the `EDSv5` VM family in West US 3 (Non-Production). Update the workbook.

**Before (West US 3, row 4):**

| Col | Header | Value |
|-----|--------|-------|
| O | NP Q-Limit | 94,710 |
| P | NP Q-Used | 2 |
| Q | NP Q-Headroom (computed) | **94,708** |

**Step 1:** Click cell **O4** (NP Q-Limit).  
**Step 2:** Change from `94710` to `144710`.  
**Step 3:** Press Enter. Q4 recalculates:

| Col | Header | New value |
|-----|--------|-----------|
| O | NP Q-Limit | 144,710 |
| P | NP Q-Used | 2 (unchanged) |
| Q | NP Q-Headroom (computed) | **144,708** |

**Effect on downstream sheets:**

HC_Gate row 4 re-evaluates:
- **HC-7 DR Integ (I4):** `P4 + Setup!B7 ≤ O4 − Policy!B13` → `2 + B7 ≤ 144,710 − 40`. The expanded limit makes it far easier to PASS HC-7.
- **Scoring_Prod/CVAL/DR row 4:** β_raw uses `Q / I` (Prod) or `Q / O` (CVAL/DR quota headroom ratio) — increasing O4 or I4 directly improves the β component of the placement score.

**When to update quota cells (I, J, O, P):** After a Microsoft quota-increase approval is confirmed via the Azure Portal or quota management API. Update both the limit (I/O) and current usage (J/P) from the same observation timestamp to keep the snapshot coherent (DAT-003).

---

## 6. Running Multiple-SKU Scenarios

### 6.1 Why the Tool Models One SKU per Run

The Setup sheet accepts a single SKU (B4) and derives a single `Requested vCPU` value (B7 = B5 × B6). All HC_Gate checks and placement scores compare against this single vCPU total. The tool does not natively model mixed-SKU deployments in one pass.

This matches the baseline modelling assumption: the HC gate validates that a region can absorb the **largest homogeneous vCPU block** of a customer's deployment in each environment separately.

### 6.2 Worked Example — E32ads_v5 + E16ads_v5 Dual-SKU Deployment

**Scenario:** Customer `CUST-0099` in the **US** geography needs:
- **Component A:** 8 × E32ads_v5 VMs = 256 vCPU (workload backbone)
- **Component B:** 4 × E16ads_v5 VMs = 64 vCPU (API layer)

The platform placement decision must accommodate both blocks. Run two separate passes and compare:

#### Pass 1 — Larger block (E32ads_v5)

| Setup cell | Value |
|------------|-------|
| B3 | `US` |
| B4 | `E32ads_v5` |
| B5 | `8` |
| B9 | `CUST-0099` |

→ B7 = `256` vCPU  
→ Note the recommended Prod, CVAL, DR regions from the Result sheet.  
→ Example result: **Prod = East US 2, CVAL = West US 3, DR = Central US** (PS = 0.71 / 0.68 / 0.64)

#### Pass 2 — Smaller block (E16ads_v5)

| Setup cell | Value |
|------------|-------|
| B3 | `US` |
| B4 | `E16ads_v5` |
| B5 | `4` |
| B9 | `CUST-0099` |
| B8 | `eastus2` (← lock Prod to the Pass 1 winner) |

→ B7 = `64` vCPU  
→ With B8 = `eastus2`, the engine honours that explicit Prod region override and only competes for CVAL/DR.  
→ Check that HC_Gate rows for East US 2, West US 3, and Central US still PASS at 64 vCPU — they should, since 64 < 256.

#### Interpreting the results

If **both passes return the same Prod winner** and HC passes at both vCPU sizes, the recommended placement is valid for the combined deployment. Record both requested vCPU values in the customer seed record (PLC-003).

If Pass 1 passes but **Pass 2 fails HC-3 NonProd** in the CVAL region (e.g. West US 3 Q-Headroom < 64 after the 256 vCPU reservation already consumed most of the quota budget), escalate the quota increase for the CVAL subscription before placement.

#### Summing vCPUs for a conservative gate check

For an even more conservative check, create a third pass using the **combined vCPU total** as a single block:

| Setup cell | Value |
|------------|-------|
| B4 | `E32ads_v5` (proxy — pick the larger SKU) |
| B5 | `10` (= 8+4, treating all VMs as E32; this overstates the E16 request by 16 vCPU per VM) |

This is intentionally conservative and will overfail for very tight scenarios. Use the individual passes as the authoritative check.

#### Multiple customers with the same dual-SKU profile

If you need to plan capacity for **N customers**, each with the same dual-SKU profile:
1. Run Pass 1 with `B5 = 8 × N` to check whether the region can absorb all E32 blocks.
2. Run Pass 2 with `B5 = 4 × N` to check E16 blocks.
3. Increment `Cust Count` (col U) by N for the winning regions after each planning cycle.

---

## 7. Calculation Logic Reference

This section documents every formula in the workbook, referenced to the actual Excel cell range. Row variable `{r}` denotes any data row 4–17 (the 14 ACRME regions).

### 7.1 Setup Sheet Lookups

#### vCPU per VM (B6)

```excel
=VLOOKUP(B4, E3:F10, 2, FALSE)
```

Looks up the selected SKU (B4) in the catalogue table E3:F10 and returns the vCPU count from column F. Returns an error if the SKU is not in the dropdown list.

#### Requested vCPU (B7)

```excel
=B5 * B6
```

Multiplies VM count by vCPU per VM. This single value propagates to **every** HC check and scoring formula as `Setup!$B$7`.

#### Distribution model and DR scope geography (B10, B11)

```excel
=VLOOKUP(B3, E13:G17, 2, FALSE)   ' B10: distribution model
=VLOOKUP(B3, E13:G17, 3, FALSE)   ' B11: DR scope geography
```

The table E13:G17 maps each geography to its model and DR scope:

| Geography | Distribution Model | DR Scope Geography |
|-----------|-------------------|-------------------|
| US | 3-region | US |
| EU | 2-region | EU |
| Australia | 2-region | Australia |
| Asia Pacific | 2-region | Asia Pacific |
| Middle East | cross-geo | EU |

The DR scope geography controls which Scoring_DR regions are InScope (§7.7). Middle East maps to EU, so the DR winner is always a European region (cross-geo DR, DR-020/PLC-010b).

---

### 7.2 Capacity_Usage Computed Columns

These four columns update automatically whenever the adjacent editable inputs change.

#### Prod Free (H)

```excel
=F{r} - G{r}
```

`Prod Reserved − Prod Alloc` = unallocated production reservation capacity. A negative value indicates a **reservation deficit** (Appendix A.3). Does not directly gate eligibility but is used in the builder's distribution logic and is visible for operational review.

#### Prod Q-Headroom (K)

```excel
=I{r} - J{r}
```

`Prod Q-Limit − Prod Q-Used` = remaining production quota. This is the **gating value for HC-3 Prod** (§7.3) and the denominator in the β scoring component for Prod (§7.5).

#### NP Eff-Free (N)

```excel
=L{r} - M{r}
```

`NP Reserved − NP Alloc` = available non-production reservation headroom. This is the **gating value for HC-3 NonProd** first condition and the numerator in the α scoring component (see §7.5–7.6).

#### NP Q-Headroom (Q)

```excel
=O{r} - P{r}
```

`NP Q-Limit − NP Q-Used` = remaining non-production quota. Used in HC-3 NonProd second condition, HC-7 DR Integrity, and β scoring for CVAL/DR (§7.6–7.7).

---

### 7.3 HC_Gate — Hard Constraint Eligibility Checks

The HC_Gate sheet evaluates six binary checks (PASS/FAIL) for each region and derives three eligibility flags (YES/NO). A region must pass **all required checks for an environment** before it enters the scoring stage.

Notation below uses row 7 (East US 2) as the illustrative example.

#### HC-3 Production Quota (column E)

**What it checks:** Does this region have enough production *quota headroom* for the requested deployment, and will a minimum quota buffer remain afterwards?

```excel
=IF(AND(
    Capacity_Usage!K7 >= Setup!$B$7,
    Capacity_Usage!K7 - Setup!$B$7 >= Policy!$B$15
), "PASS", "FAIL")
```

| Component | Value source | Meaning |
|-----------|-------------|---------|
| `K7` | Prod Q-Headroom = I7 − J7 | Current available production quota |
| `Setup!$B$7` | Requested vCPU | vCPU needed for deployment |
| `Policy!$B$15` | Min Prod headroom (default: 20 vCPU) | Buffer that must remain after deployment |

**Condition 1:** `K7 ≥ B7` → quota headroom covers the deployment.  
**Condition 2:** `K7 − B7 ≥ 20` → at least 20 vCPU of headroom remains after the deployment. This is the minimum-headroom guardrail (Policy!B15).

**Example:** Requested = 128 vCPU, East US 2 Prod Q-Headroom = 11,422.  
→ 11,422 ≥ 128 ✓  
→ 11,422 − 128 = 11,294 ≥ 20 ✓  
→ Result: **PASS**

---

#### HC-3 NonProd Quota (column F)

**What it checks:** Does this region have enough non-production *reservation headroom* for the deployment AND sufficient *quota headroom* afterwards?

```excel
=IF(AND(
    Capacity_Usage!N7 >= Setup!$B$7,
    Capacity_Usage!Q7 - Setup!$B$7 >= Policy!$B$16
), "PASS", "FAIL")
```

| Component | Value source | Meaning |
|-----------|-------------|---------|
| `N7` | NP Eff-Free = L7 − M7 | Available non-prod reservation capacity |
| `Q7` | NP Q-Headroom = O7 − P7 | Available non-prod quota |
| `Policy!$B$16` | Min NonProd headroom (default: 20 vCPU) | Quota buffer required post-deployment |

**Condition 1:** `N7 ≥ B7` → NP reservation headroom covers the deployment.  
**Condition 2:** `Q7 − B7 ≥ 20` → at least 20 vCPU of NP quota remains.

Note: Condition 1 checks *reservation* headroom (N); condition 2 checks *quota* headroom (Q). These are independent resources; both must pass (CAP-009/RDY-003).

---

#### HC-3 DR Capacity (column G)

**What it checks:** Does this region hold enough free DR reservation to absorb at least one DR bootstrap event?

```excel
=IF(Capacity_Usage!S7 >= Policy!$B$13, "PASS", "FAIL")
```

| Component | Value source | Meaning |
|-----------|-------------|---------|
| `S7` | DR Free | Unallocated DR reservation capacity |
| `Policy!$B$13` | DR bootstrap qty (default: 40 vCPU) | Minimum DR headroom required |

**Example:** DR Free = 16,722 vCPU, bootstrap = 40.  
→ 16,722 ≥ 40 ✓ → **PASS**

For the Middle East (Saudi Arabia Central, UAE North), DR Reserved = 0 and DR Free = 0 → HC-3 DR always **FAIL** for these regions in the DR scoring sheet. Their DR is served cross-geo in Europe (DR-020).

---

#### HC-6 DR Coverage Floor (column H)

**What it checks:** In a two-region geography where CVAL and DR co-locate (PLC-010a), can the *combined* NP and DR pool in that region absorb the DR bootstrap demand? This handles the CVAL-sacrifice bootstrap pattern (DR-005/DR-006).

```excel
=IF(Capacity_Usage!S7 + Capacity_Usage!N7 >= Policy!$B$13, "PASS", "FAIL")
```

| Component | Value source | Meaning |
|-----------|-------------|---------|
| `S7` | DR Free | Unallocated DR capacity |
| `N7` | NP Eff-Free | Releasable CVAL capacity |
| `Policy!$B$13` | DR bootstrap qty (40 vCPU) | Minimum combined DR + releasable CVAL needed |

HC-6 recognises that in a co-located CVAL/DR region, CVAL capacity is earmarked as releasable toward DR bootstrap. Even if `S7` alone is too low, a region passes HC-6 if `S7 + N7 ≥ 40`.

---

#### HC-7 DR Floor Integrity (column I)

**What it checks:** After placing the new deployment in this region's Non-Prod quota, does the remaining NP quota still protect the DR bootstrap floor?

```excel
=IF(Capacity_Usage!P7 + Setup!$B$7 <= Capacity_Usage!O7 - Policy!$B$13, "PASS", "FAIL")
```

Rearranged: `P7 + B7 ≤ O7 − 40`  
→ `NP Q-Used + Requested vCPU ≤ NP Q-Limit − DR bootstrap`

The right-hand side `O7 − 40` is the NP quota available *above* the DR bootstrap floor. If adding the new deployment to current NP usage would consume into that floor, the check fails.

**Design intent:** In a two-region co-located model, the NP subscription's quota must always leave room for the DR minimum — you cannot deploy NP VMs if doing so would crowd out the quota needed to stand up DR bootstrap capacity.

---

#### Eligibility Flags (columns J, K, L)

```excel
' Eligible Prod (J)
=IF(E7="PASS", "YES", "NO")

' Eligible NonProd (K) — requires HC-3 NonProd AND HC-7 integrity
=IF(AND(F7="PASS", I7="PASS"), "YES", "NO")

' Eligible DR (L) — requires HC-3 DR AND HC-6 floor
=IF(AND(G7="PASS", H7="PASS"), "YES", "NO")
```

| Flag | Required checks |
|------|----------------|
| Eligible Prod | HC-3 Prod only |
| Eligible NonProd | HC-3 NonProd AND HC-7 DR integrity |
| Eligible DR | HC-3 DR AND HC-6 DR floor |

Eligible NonProd requires HC-7 because adding CVAL load must not break the DR quota floor. Eligible DR requires both HC-3 DR (absolute DR free) and HC-6 (combined pool) to ensure the co-location bootstrap model is safe.

---

### 7.4 Scoring Engine — Placement Score (PS)

For each environment (Prod/CVAL/DR), the engine computes a **Placement Score** between 0 and 1 for every eligible region. The score is a weighted sum of five normalised components:

```
PS = α·α_c + β·β_c + γ·γ_c + δ·δ_c + ε·ε_c
```

Where each `_c` suffix denotes the **clamped** form of the raw component (`MIN(MAX(raw, 0), 1)`), and the weights (α, β, γ, δ, ε) are configured in the Policy sheet:

| Parameter | Cell | Default | Dimension |
|-----------|------|---------|-----------|
| α — Capacity headroom weight | Policy!B2 | 0.30 | — |
| β — Quota headroom weight | Policy!B3 | 0.20 | — |
| γ — Distribution fairness weight | Policy!B4 | 0.25 | — |
| δ — DR readiness weight | Policy!B5 | 0.15 | — |
| ε — Zone diversity weight | Policy!B6 | 0.10 | — |
| **Sum** | Policy!B7 | **1.00** | Must equal 1.0 (validated in B8) |

The weights must sum to 1.0 (within 0.001). Cell B8 shows `VALID` or `INVALID` — always check this after any weight adjustment.

---

### 7.5 Scoring_Prod — Formula Details

Scoring_Prod rows 4–17, one row per region. Column letters below refer to Scoring_Prod columns.

#### InScope (C)

```excel
=IF(Capacity_Usage!C{r} = Setup!$B$3, 1, 0)
```

`1` if the region's geography (Capacity_Usage col C) matches the selected geography (Setup!B3). Only in-scope regions can be Prod candidates.

#### Eligible (D)

```excel
=IF(HC_Gate!J{r} = "YES", 1, 0)
```

`1` if the region passed Eligible Prod (HC_Gate col J).

#### AutoSelect (E)

```excel
=IF(OR(Capacity_Usage!V{r} = "Standard", Capacity_Usage!B{r} = Setup!$B$8), 1, 0)
```

`1` if the region is **Standard class** (auto-selectable) OR if its name matches the explicit Prod region override in Setup!B8.

**Restricted regions** (Saudi Arabia Central, UAE North) have `V = "Restricted"`. They receive `AutoSelect = 0` unless the operator explicitly names them in B8. This enforces the restricted-deployment-region rule from baseline v2.4 Section 6.

#### α_raw (G) — Capacity Headroom

```excel
=IFERROR(Capacity_Usage!N{r} / Capacity_Usage!F{r}, 0)
```

`NP Eff-Free / Prod Reserved`

This ratio measures how much non-production reservation capacity (col N) exists relative to the region's total production footprint (col F). A high ratio indicates the region has substantial NP headroom proportional to its Prod size — a proxy for under-utilised capacity available for new customer growth.

*Note:* This is the Prod scoring α, not a direct prod-headroom ratio. The reasoning is that in a 3-region US geography, the Prod placement decision considers the availability of NP capacity (where CVAL will later land) as a signal of regional capacity health.

#### α_c (H) — Clamped α

```excel
=MIN(MAX(G{r}, 0), 1)
```

Clamps α_raw to [0, 1]. A ratio > 1 is clamped to 1.

#### β_raw (I) — Quota Headroom

```excel
=IFERROR(Capacity_Usage!K{r} / Capacity_Usage!I{r}, 0)
```

`Prod Q-Headroom / Prod Q-Limit`

Fraction of production quota still available. A value of 1.0 means no quota is used; 0.0 means quota is exhausted.

**Example:** East US 2 row 7 — if I7 (Prod Q-Limit) = 200,000 and K7 = 11,422, then β_raw = 11,422 / 200,000 ≈ 0.057. This region is heavily quota-loaded and will score low on β.

#### β_c (J)

```excel
=MIN(MAX(I{r}, 0), 1)
```

#### γ_raw (K) — Distribution Fairness

```excel
=IFERROR(1 - Capacity_Usage!U{r} / F{r}, 0)
```

`1 − (Cust Count / total_customers_for_geo)`

Wait — the formula uses `F{r}` (Prod Reserved) as the denominator, **not** a total_customers value. This is actually `1 − (Cust Count / Prod Reserved)`, which approximates how saturated the region is relative to its capacity size.

> **Design note:** The `total_customers` variable (referenced in Policy!B10–B11) is not yet resolved in the baseline (see §9). The current formula uses Prod Reserved as a normalising denominator, which gives a per-vCPU saturation ratio. A region with 150 customers and 154,178 Prod Reserved vCPU (East US 2) scores: `1 − 150/154,178 ≈ 0.999` — very high, because Prod Reserved dwarfs the customer count. This is a known gap documented in the design.

#### γ_c (L)

```excel
=MIN(MAX(K{r}, 0), 1)
```

#### δ_raw (M) — DR Readiness

```excel
=IFERROR(Capacity_Usage!T{r}, 0)
```

`DR Coverage` — directly the value in Capacity_Usage col T (a 0.0–1.0 ratio). A region with 80% of Prod workload covered by DR capacity scores 0.80 on δ.

**Example:** West US 3 (row 4) DR Coverage = 0.6 → δ_raw = 0.60 → δ_c = 0.60.

#### δ_c (N)

```excel
=MIN(MAX(M{r}, 0), 1)
```

#### ε_raw (O) — Zone Diversity

```excel
=Capacity_Usage!E{r} / 3
```

`AZ count / 3`. Regions with 3 availability zones score 1.0; regions with 2 AZ (Australia Southeast) score 0.667. This rewards regions with full zone diversity for HA.

#### ε_c (P)

```excel
=MIN(MAX(O{r}, 0), 1)
```

#### Placement Score (Q)

```excel
=Policy!$B$2 * H{r}   +   Policy!$B$3 * J{r}   +   Policy!$B$4 * L{r}
 +   Policy!$B$5 * N{r}   +   Policy!$B$6 * P{r}
```

```
PS_Prod = α·α_c + β·β_c + γ·γ_c + δ·δ_c + ε·ε_c
        = 0.30·α_c + 0.20·β_c + 0.25·γ_c + 0.15·δ_c + 0.10·ε_c
```

All weights sourced live from Policy!B2:B6 — changing a weight immediately updates all 14 PS values.

#### Candidate (R)

```excel
=IF(AND(C{r}=1, D{r}=1, E{r}=1), Q{r}, -1)
```

Returns the PS score only if the region is InScope **AND** Eligible **AND** AutoSelect. Otherwise returns `-1` (excluded from ranking).

#### Rank (S)

```excel
=IF(R{r}<0, "", COUNTIF($R$4:$R$17,">"&R{r})+1)
```

Rank among all Candidate regions (blank for ineligible). The winning region has Rank = 1.

#### Winner Cells

| Cell | Content |
|------|---------|
| Scoring_Prod!U3 | Region name of the Prod winner (highest PS among all Rank=1 candidates) |
| Scoring_Prod!U4 | Winning Prod PS score |

---

### 7.6 Scoring_CVAL — Formula Details and Differences

Scoring_CVAL uses the same 19-column structure as Scoring_Prod but differs in three formulas:

#### α_raw (G) — NP Capacity Headroom

```excel
=IFERROR(Capacity_Usage!N{r} / Capacity_Usage!L{r}, 0)
```

`NP Eff-Free / NP Reserved`

For CVAL placement, α measures Non-Prod capacity headroom as a fraction of total NP Reserved — a cleaner utilisation ratio than the Prod version.

#### β_raw (I) — NP Quota Headroom

```excel
=IFERROR(Capacity_Usage!Q{r} / Capacity_Usage!O{r}, 0)
```

`NP Q-Headroom / NP Q-Limit` (Non-Prod quota, not Prod quota).

#### δ_raw (M) — δ duplicates α in CVAL

```excel
=IFERROR(Capacity_Usage!N{r} / Capacity_Usage!L{r}, 0)
```

**This is identical to α_raw.** This is a **known design gap** — the δ (DR readiness) component for CVAL scoring is not yet defined independently and currently uses the same formula as α. The effective result is that α and δ are perfectly correlated in CVAL scoring, giving the NP capacity headroom dimension a combined weight of `α + δ = 0.30 + 0.15 = 0.45`. See §9 for the documented gap.

#### Eligible (D) — uses NonProd flag

```excel
=IF(HC_Gate!K{r}="YES", 1, 0)
```

Uses HC_Gate column K (Eligible NonProd) rather than column J (Eligible Prod).

#### Candidate (R) — excludes the Prod winner

```excel
=IF(AND(C{r}=1, D{r}=1, E{r}=1, Capacity_Usage!B{r}<>Scoring_Prod!$U$3), Q{r}, -1)
```

The additional condition `B ≠ Scoring_Prod!U3` ensures the Prod winner region is excluded from CVAL candidates (ENV-003 separation — Prod and CVAL should not co-locate unless the distribution model forces it, e.g. two-region geographies per PLC-010a).

---

### 7.7 Scoring_DR — Formula Details and Differences

#### InScope (C) — uses DR scope geography (B11)

```excel
=IF(Capacity_Usage!C{r} = Setup!$B$11, 1, 0)
```

For US geography, B11 = `US` → only US regions are in scope for DR.  
For Middle East, B11 = `EU` → **only European regions** are DR candidates (cross-geo DR, DR-020/PLC-010b). This is how the model enforces that Middle East DR always lands in Europe.

#### α_raw (G) — DR Capacity Utilisation

```excel
=IFERROR(Capacity_Usage!S{r} / Capacity_Usage!R{r}, 0)
```

`DR Free / DR Reserved` — fraction of DR reservation capacity still available.

#### β_raw (I) — NP Quota Headroom (same as CVAL)

```excel
=IFERROR(Capacity_Usage!Q{r} / Capacity_Usage!O{r}, 0)
```

Reuses NP quota headroom ratio — the DR region's NP quota is relevant because DR capacity frequently co-locates with CVAL quota (PLC-010a).

#### δ_raw (M) — DR Coverage vs Target

```excel
=IFERROR(Capacity_Usage!T{r} / Policy!$B$14, 0)
```

`DR Coverage / DR coverage target (0.8)` — how close is this region to its DR coverage target? A region at 0.6 coverage with target 0.8 scores `0.6/0.8 = 0.75`. This incentivises choosing regions where DR coverage is already near-sufficient so the new customer's DR portion is well-supported.

#### Eligible (D) — uses DR flag

```excel
=IF(HC_Gate!L{r}="YES", 1, 0)
```

Uses HC_Gate column L (Eligible DR) — requires both HC-3 DR and HC-6 DR floor.

#### Candidate (R) — excludes both Prod and CVAL winners

```excel
=IF(AND(C{r}=1, D{r}=1, E{r}=1,
        Capacity_Usage!B{r}<>Scoring_Prod!$U$3,
        Capacity_Usage!B{r}<>Scoring_CVAL!$U$2),
    Q{r}, -1)
```

Excludes both the Prod winner and the CVAL winner from DR candidates. In a 3-region geography (US), this enforces full separation of all three environments (ENV-003). In a 2-region geography, the CVAL winner is the only available non-Prod region, so it will be the same as the DR winner — but that is handled at the `AutoSelect` level (the CVAL region has been designated by PLC-010a).

---

### 7.8 Result Sheet Derivation

The Result sheet pulls the winner values from each Scoring sheet:

| Cell | Formula (approximate) | Meaning |
|------|----------------------|---------|
| B9 | `=IF(Scoring_Prod!U3="","NONE ELIGIBLE",Scoring_Prod!U3)` | Prod winner or NONE ELIGIBLE |
| C9 | `=Scoring_Prod!U4` | Prod winning PS |
| B10 | `=IF(Scoring_CVAL!U2="","NONE ELIGIBLE",Scoring_CVAL!U2)` | CVAL winner |
| C10 | `=Scoring_CVAL!U3` | CVAL winning PS |
| B11 | `=IF(Scoring_DR!U2="","NONE ELIGIBLE",Scoring_DR!U2)` | DR winner |
| C11 | `=Scoring_DR!U3` | DR winning PS |
| B13 | Nested IF on B9/B10/B11 | Readiness state |

The **Readiness state** formula in B13 evaluates the three winner cells in order:

```
If B9 = "NONE ELIGIBLE" → "QUOTA_DEFICIT / NEEDS EXPLICIT REGION (Prod)"
Else if B10 = "NONE ELIGIBLE" → "CAPACITY_UNAVAILABLE (CVAL)"
Else if B11 = "NONE ELIGIBLE" → "READY_WITH_RISK (no DR region)"
Else → "READY"
```

This maps to the RDY-002 machine-readable states (`READY`, `READY_WITH_RISK`, `QUOTA_DEFICIT`, `CAPACITY_UNAVAILABLE`) from Section 10 of the baseline.

---

## 8. Policy Sheet — Tuning Weights and Thresholds

### Weight Parameters (B2:B6)

Edit these to reprioritise the placement scoring. After any change, verify **B7 = 1.000** and **B8 = "VALID"** before interpreting results.

| Cell | Parameter | Default | Effect of increasing |
|------|-----------|---------|---------------------|
| B2 | α — Capacity headroom | 0.30 | Favours regions with more free NP/DR reservation capacity |
| B3 | β — Quota headroom | 0.20 | Favours regions with more unused quota margin |
| B4 | γ — Distribution fairness | 0.25 | Favours regions with fewer existing customers relative to their size |
| B5 | δ — DR readiness | 0.15 | Favours regions where DR coverage is already strong |
| B6 | ε — Zone diversity | 0.10 | Favours 3-AZ regions over 2-AZ regions |

**Example — DR-heavy scenario:** To stress-test DR placement when DR coverage is the top priority:

```
B5 (δ) = 0.40   B2 (α) = 0.20   B3 (β) = 0.15   B4 (γ) = 0.15   B6 (ε) = 0.10
Sum = 1.00 ✓
```

### Headroom Thresholds (B13:B16)

| Cell | Parameter | Default | Meaning |
|------|-----------|---------|---------|
| B13 | DR bootstrap qty vCPU | 40 | Minimum DR Free required to pass HC-3 DR |
| B14 | DR coverage target | 0.80 | Target ratio for DR coverage (used in Scoring_DR δ) |
| B15 | Min Prod headroom vCPU | 20 | Quota buffer required after Prod deployment (HC-3 Prod condition 2) |
| B16 | Min NonProd headroom vCPU | 20 | Quota buffer required after NonProd deployment (HC-3 NonProd condition 2) |

### total_customers Mode (B10:B11, D11:E15)

| Cell | Parameter | Values |
|------|-----------|--------|
| B10 | Mode selector | 1 = Live / geography sum of Cust Count; 2 = Constant from table; 3 = Manual |
| B11 | Manual total_customers | Numeric — used when B10 = 3 |
| D11:E15 | Geography → Constant table | Per-geography constants — used when B10 = 2 |

> **Note:** In the current workbook, the γ_raw formula uses `Prod Reserved` as its denominator rather than `total_customers` (see §9). The B10/B11 mode selector is present in the policy design but is not yet wired into the Scoring sheet γ formula.

---

## 9. Known Limitations and Design Gaps

These are **documented**, expected limitations of the v2.4 mockup — not bugs.

### 1. total_customers Not Wired Into γ_raw

**Expected design:** γ_raw = `1 − (Cust Count / total_customers_for_geo)`, where `total_customers` is fetched from Policy (B10–B11) or computed as a geography sum.  
**Current state:** γ_raw uses `Prod Reserved` as the denominator: `1 − U{r}/F{r}`. Because Prod Reserved (O(10⁵) vCPU) is orders of magnitude larger than Cust Count (O(1)–O(150)), γ_c is always near 1.0 for all regions, making γ effectively a constant and not a discriminating factor in placement.  
**Impact:** Placement decisions are driven by α, β, δ, and ε. Distribution fairness is not yet a live differentiator.  
**Action:** Define and agree `total_customers` per geography (Policy!B10–B11 mode), then update the γ_raw formula accordingly.

### 2. δ Duplicates α in Scoring_CVAL

**Expected design:** δ (DR readiness) and α (capacity headroom) should use independent input metrics.  
**Current state:** In Scoring_CVAL, both δ_raw and α_raw resolve to `NP Eff-Free / NP Reserved`. The δ component in CVAL carries no additional information.  
**Impact:** Effective combined NP-headroom weight in CVAL = `α + δ = 0.45` (double-weighted). The distinction between "capacity" and "DR readiness" is lost for CVAL placement.  
**Action:** Define a suitable CVAL DR readiness metric (e.g. `DR Coverage × DR Free` for the co-located CVAL/DR region) and update Scoring_CVAL!M{r}.

### 3. Middle East Capacity Data Is Synthetic

Saudi Arabia Central and UAE North have no real usage data in the source files. The builder injects a synthetic geography pool (`ME_MOCK_PROD = 2,400 vCPU`, `ME_MOCK_NP = 3,400 vCPU`) and distributes it between the two restricted regions. All Middle East Capacity_Usage values are **derived planning estimates**, not observed consumption.  
**Action:** Replace with observed Azure subscription usage once live customers exist in Middle East regions.

### 4. Canada Central Data Is Absent — Mock Subscriber Count Used

Canada Central does not appear in the source usage file. The builder assigns a mock subscriber count (10) and distributes a synthetic floor share from the US geography total. Actual usage may differ significantly.

### 5. Reserved Capacity and Quota Limits Are Derived Planning Figures

The `Prod Reserved`, `NP Reserved`, `DR Reserved`, `Prod Q-Limit`, and `NP Q-Limit` values are **computed from the usage distribution algorithm**, not read from Azure Capacity Reservation APIs or Azure Quota APIs. They represent what *should be* reserved/requested given the modelled distribution — not what *is* provisioned today.  
**Action:** Reconcile these planning figures against actual CRG quantities (CAP-009) and quota assignments after each quarterly planning cycle.

### 6. Japan East Excluded

Japan East is noted as pending confirmation in baseline v2.4 Section 6 and is not in the catalogue. When Japan East is added to the baseline region list, the builder must be updated and the workbook rebuilt.

---

## 10. Quick Reference Tables

### Capacity_Usage — What to Update and When

| Event | Column(s) to update | Formula that re-computes |
|-------|-------------------|--------------------------|
| New CRG provisioned (Prod) | F (Prod Reserved) ↑ | H (Prod Free) |
| New CRG provisioned (NonProd) | L (NP Reserved) ↑ | N (NP Eff-Free) |
| New CRG provisioned (DR) | R (DR Reserved) ↑ | — |
| VMs deployed to Prod | G (Prod Alloc) ↑ | H (Prod Free) |
| VMs deployed to NonProd | M (NP Alloc) ↑ | N (NP Eff-Free) |
| DR VMs allocated | S (DR Free) ↓ | — |
| Quota increase granted (Prod) | I (Prod Q-Limit) ↑ | K (Prod Q-Headroom) |
| Quota increase granted (NonProd) | O (NP Q-Limit) ↑ | Q (NP Q-Headroom) |
| Quota consumed (Prod deployment) | J (Prod Q-Used) ↑ | K (Prod Q-Headroom) |
| Quota consumed (NonProd deployment) | P (NP Q-Used) ↑ | Q (NP Q-Headroom) |
| DR coverage changed | T (DR Coverage) | — |
| Customer placed | U (Cust Count) ↑ | — |

### HC_Gate — Pass/Fail Decision Matrix

| Check | Pass condition | Environment gated |
|-------|---------------|-------------------|
| HC-3 Prod | Prod Q-Headroom ≥ Requested vCPU **AND** remaining ≥ 20 | Prod eligibility |
| HC-3 NonProd | NP Eff-Free ≥ Requested vCPU **AND** NP Q-Headroom post-deploy ≥ 20 | NonProd eligibility |
| HC-3 DR | DR Free ≥ 40 vCPU | DR eligibility (first gate) |
| HC-6 DR Floor | DR Free + NP Eff-Free ≥ 40 vCPU | DR eligibility (second gate) |
| HC-7 DR Integ | NP Q-Used + Requested vCPU ≤ NP Q-Limit − 40 | NonProd eligibility (second gate) |
| Eligible Prod | HC-3 Prod = PASS | Prod enters scoring |
| Eligible NonProd | HC-3 NonProd = PASS **AND** HC-7 = PASS | CVAL enters scoring |
| Eligible DR | HC-3 DR = PASS **AND** HC-6 = PASS | DR enters scoring |

### Scoring Component Summary

| Component | Prod formula | CVAL formula | DR formula |
|-----------|-------------|-------------|-----------|
| α_raw | NP Eff-Free / Prod Reserved | NP Eff-Free / NP Reserved | DR Free / DR Reserved |
| β_raw | Prod Q-Headroom / Prod Q-Limit | NP Q-Headroom / NP Q-Limit | NP Q-Headroom / NP Q-Limit |
| γ_raw | 1 − Cust Count / Prod Reserved | (same formula) | (same formula) |
| δ_raw | DR Coverage (T) directly | **NP Eff-Free / NP Reserved (= α, gap)** | DR Coverage / DR target (B14) |
| ε_raw | AZ count / 3 | AZ count / 3 | AZ count / 3 |

### Readiness State Cheat Sheet

| Result!B13 state | Root cause | Fix |
|-----------------|-----------|-----|
| `READY` | All three placements found | No action |
| `QUOTA_DEFICIT / NEEDS EXPLICIT REGION (Prod)` | No Prod candidate: all regions fail HC-3 Prod or AutoSelect=0 | 1. Increase Prod Q-Limit (I) in target region, or 2. Set Setup!B8 to a Restricted region ID |
| `CAPACITY_UNAVAILABLE (CVAL)` | No CVAL candidate in the geography | Increase NP Eff-Free (L−M) or NP Q-Limit (O) in target NonProd region |
| `READY_WITH_RISK (no DR region)` | No DR candidate | Increase DR Free (S) or expand DR Reserved (R) in DR-scope geography |

---

*End of User Guide — baseline v2.4 · Last updated: 21 Sep 2026*
