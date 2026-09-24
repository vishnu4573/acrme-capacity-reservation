# ACRME Aligned Placement What-If — User Guide

**Workbook:** `acrme_aligned_placement_whatif.xlsx`  
**Builder:** `build_acrme_aligned_placement.py`  
**Baseline:** Azure Capacity & Quota Management Consolidated Requirements Baseline v2.4  
**Status:** Planning mockup. Capacity and quota figures are synthetic. The file does not change the baseline and it is not connected to live Azure.

---

## 1. What this workbook answers

Given a customer, a geography, and one or more VM SKUs, which region should host **Prod**, which should host **CVAL**, and which should host **DR** — and what do the mock reservations and quota pools look like after that placement is accepted.

Every active SKU line has to fit. A region that can take the large SKU and not the small one is out.

## 2. Sheets, in the order Excel uses them

| Sheet | What you do with it |
|---|---|
| **ReadMe** | Short orientation |
| **Request** | The deployment. Yellow cells only |
| **Policy** | Weights and thresholds. Yellow cells. Geography model table is also here |
| **Region_Catalogue** | The 14 baseline regions, class, and distribution model |
| **SKU_Catalogue** | Eight managed SKUs, vCPU, and quota family |
| **Capacity_Reservations** | Mock reservation per region, environment, and SKU. Yellow: Allocated and Buffer |
| **Quota_Groups** | One pool per region and VM family. Yellow: Limit |
| **Line_Check** | Formulas. Per-SKU free cores and quota for each region |
| **Score_Prod**, **Score_CVAL**, **Score_DR** | Gates, then the placement score |
| **Allocation** | The decision and the customer seed |
| **Post_Allocation** | Reservation rows after a successful placement |
| **Quota_After** | Family pools after that same placement |

Nothing is applied on Post_Allocation unless Allocation says the overall state is `READY` or `READY_WITH_RISK`.

## 3. How to enter a deployment

On **Request**, yellow cells:

| Cell | Input | Rule |
|---|---|---|
| B4 | Geography | `US`, `EU`, `Australia`, `Asia Pacific`, or `Middle East` |
| B5 | Customer ID | Free text. Copied onto the seed |
| B6 | Prod region id | Normal path (PLC-001). Leave blank only for the exception below |
| B7 | Geography-only exception | `Y` or `N`. Must be `Y` when B6 is blank (PLC-002) |
| B8 | DR offered | `N` records `NOT_OFFERED` and adds no DR cores (DR-014) |
| A13:B20 | Up to 8 SKU lines | Both SKU and VM count are required. One row per SKU |

Derived, do not type over them:

| Cell | Meaning |
|---|---|
| B9 | Distribution model for the geography (`3-region`, `2-region`, or `cross-geo`) |
| B10 | DR scope. Middle East points at EU |
| C13:C20 | vCPU per VM |
| D13:D20 | Line cores = VM count × vCPU |
| E13:E20 | Quota family (`Eadsv5`, `Eadsv6`, `Dadsv5`, `Dasv5`) |
| B22 | How many lines are active |
| B23 | Total requested cores |
| B24 | `OK`, or `DUPLICATE SKU` if the same SKU appears twice |
| B25 | DR bootstrap cores = total cores × Policy!B15, rounded. Default fraction is 0.10 |

A duplicate SKU blocks the run (`POLICY_BLOCKED`). Put the whole quantity on one row.

## 4. How a region is chosen

Selection order is fixed: **Prod, then CVAL, then DR**. A region that fails a gate is not given a placement score.

### Who may compete

| Geography | Model | What the engine does |
|---|---|---|
| US | 3-region | Prod, CVAL, and DR are three different **Standard** regions |
| EU, Australia, Asia Pacific | 2-region | Prod takes one Standard region. CVAL and DR are the same other region (PLC-010a) |
| Middle East | cross-geo | Prod and CVAL are the same Middle East region, on separate reservations. DR is the best Europe Standard region (PLC-010b) |

**Restricted** regions (East US 2, North Europe, West Europe) are not in the automatic list. They compete only when Request!B6 names that region as Prod.

### The gate for every active SKU line

A line fits an environment only when both of these are true:

```
reserved-free for that SKU  >=  cores this line needs
family quota available      >=  cores this line needs
```

The cores DR must cover are the bootstrap quantity for that line, not the full Prod quantity. Prod and CVAL must cover the full line.

The tightest line sets the score. Blank rows are ignored.

### The score

Only regions that pass every gate are scored:

```
PS = 0.30α + 0.20β + 0.25γ + 0.15δ + 0.10ε
```

| Term | Prod | CVAL | DR |
|---|---|---|---|
| α | NonProd free ÷ Prod reserved | NonProd free ÷ NonProd reserved | DR free ÷ DR reserved |
| β | Family quota available ÷ family quota limit | same | same |
| γ | 1 − customers in the region ÷ total_customers | same | same |
| δ | DR coverage ratio | same value as α | coverage ÷ bootstrap fraction, clamped at 1 |
| ε | availability zones ÷ 3 | same | same |

`total_customers` is an assumed 100 on Policy!B17. Baseline v2.4 does not define that source. Weights must sum to 1.00 or the run is `POLICY_BLOCKED`. A tie goes to the earlier region in the catalogue.

### Readiness

| State | When |
|---|---|
| `READY` | Every chosen environment fits, and α is at or above the risk threshold (0.10) |
| `READY_WITH_RISK` | It fits, but α is below that threshold |
| `CAPACITY_UNAVAILABLE` | Reserved-free is too small, or no region passed |
| `QUOTA_DEFICIT` | The family pool cannot take the line and still leave the quota floor (20 cores) |
| `RESERVATION_DEFICIT` | An active SKU has no reservation in that environment |
| `POLICY_BLOCKED` | Weights do not sum to 1, a SKU is duplicated, or Prod was left blank without an approved exception |
| `NOT_OFFERED` | DR offered = N |

## 5. What a successful allocation changes

On the winners only:

| Environment | Cores added |
|---|---|
| Prod | Full line cores, per SKU |
| CVAL (NonProd rows) | Full line cores, per SKU |
| DR | Rounded bootstrap cores, per SKU |

Allocated goes up. Reserved-free goes down. The family pool’s used cores go up by the sum of every line in that family that landed in that region. Buffer stays as it was. A later reconciliation would rebuild the buffer; this sheet does not.

Rows with **Added cores** highlighted are the ones that moved. **Shortfall** is greater than 0 only if a placement was applied that the free pool cannot cover.

## 6. Examples

The numbers below use the estate shipped in the workbook (HC-2 multiplier = 1, bootstrap = 10%, exception path for US). Open Allocation after Excel calculates. Scores move if you edit Allocated, Buffer, or quota Limit.

### Example 1 — two SKUs, the file as shipped

| Line | SKU | VMs | Cores | Family |
|---|---|---|---|---|
| 1 | Standard_E32ads_v5 | 4 | 128 | Eadsv5 |
| 2 | Standard_D8as_v5 | 2 | 16 | Dasv5 |

Request: Geography `US`, Customer `CUST-1008`, Prod region blank, exception `Y`, DR offered `Y`.

| Environment | Region | Why |
|---|---|---|
| Prod | West US 3 | Passes both lines and has the highest score (about 0.63) |
| CVAL | Central US | Best remaining Standard region |
| DR | Canada Central | Only Standard region left. DR needs 13 and 2 cores, which Canada can hold |
| Overall | `READY` | Post_Allocation is filled in |

Canada Central’s Prod reservation for `E32ads_v5` has 64 free cores. The line needs 128, so Canada is not a Prod or CVAL candidate. It can still be DR because the bootstrap is much smaller. East US 2 has room, and it stays out because it is Restricted.

After the placement, West US 3 Prod free for `E32ads_v5` goes from 200 to 72. Canada’s DR row for that SKU gains 13 cores, not 128.

### Example 2 — four SKUs

Clear the sample lines and enter:

| Line | SKU | VMs | Cores | Family |
|---|---|---|---|---|
| 1 | Standard_E32ads_v5 | 2 | 64 | Eadsv5 |
| 2 | Standard_E16ads_v5 | 4 | 64 | Eadsv5 |
| 3 | Standard_E64ads_v5 | 1 | 64 | Eadsv5 |
| 4 | Standard_D8as_v5 | 2 | 16 | Dasv5 |

Same US exception path.

What changes versus Example 1:

- Three of the lines draw on **one** quota family, `Eadsv5`. Each line is checked on its own against that family’s available quota. The post-allocation sheet then **adds all three** into the same pool. With the shipped quota headroom (5,000 cores) the pool still passes. If you cut a region’s `Eadsv5` Limit until available is under 64, every Eads line fails together even when the D8as line would have fit.
- Reservations are not shared across SKUs. `E16ads_v5` does not consume `E32ads_v5` free cores. Canada Central has only 32 free cores for `E16ads_v5`, and line 2 needs 64, so Canada still fails Prod and CVAL. The other three lines are not enough to save it.
- West US 3 still wins Prod, Central US still wins CVAL, Canada Central still wins DR. Adding SKUs removed nobody who was already winning, because the new lines fit there. The result moves when a new line is the one a current winner cannot hold.

Watch Request!B22. It should read 4. If it reads less, a SKU name or a VM count is blank.

### Example 3 — shrink the request so another region can compete

Use only:

| SKU | VMs | Cores |
|---|---|---|
| Standard_E32ads_v5 | 1 | 32 |
| Standard_D8as_v5 | 1 | 8 |

Canada Central now clears both lines (64 free and 16 free). It becomes eligible. It still does not win Prod: its score is about 0.60 against West US 3 at about 0.63. Passing the gate puts a region on the ranked list. The score picks the winner among that list.

### Example 4 — the customer names a Restricted Prod region

| Input | Value |
|---|---|
| Geography | US |
| Prod region | `eastus2` |
| Exception | N (ignored once a region is named) |
| DR offered | Y |
| SKU | Standard_E32ads_v5 × 4 (128 cores) |

| Environment | Region |
|---|---|
| Prod | East US 2 only. The other US regions are not scored for Prod |
| CVAL | West US 3 |
| DR | Canada Central |

If East US 2 cannot hold the line, the result is `NONE ELIGIBLE` for Prod. The workbook does not fall through to another region. That is the PLC-001 rule: a supplied region is validated, not replaced.

### Example 5 — two-region co-location

| Input | Value |
|---|---|
| Geography | EU |
| Prod region | blank |
| Exception | Y |
| DR offered | Y |
| SKUs | the shipped pair (128 + 16 cores) |

| Environment | Region |
|---|---|
| Prod | Sweden Central |
| CVAL | Switzerland North |
| DR | Switzerland North, the same region as CVAL |

North Europe and West Europe stay Restricted. Allocation’s separation checks should show PLC-010a as `PASS`.

### Example 6 — no DR

Set DR offered to `N` on the shipped US request. Prod and CVAL are unchanged. DR shows `NOT_OFFERED`. No DR rows gain cores. Overall readiness can still be `READY`.

### Example 7 — make the fit harder

On Policy, set the HC-2 multiplier (B13) from 1 to 2. Every line then needs twice as many free cores as it consumes. On the shipped 128-core E32 line, West US 3 has 200 free and Central US has 180, so both fail. Overall becomes `CAPACITY_UNAVAILABLE` and Post_Allocation adds nothing. Put the multiplier back to 1 to restore the sample.

## 7. Can you change the deployment model from this file?

Short answers first.

| Change | From the yellow inputs? | What actually happens |
|---|---|---|
| US 3-region to a 4-region model | No | There is no 4-region choice. Typing `4-region` into the model table does not turn on a new mode |
| Restricted region to Standard | Not as a request option | You can type `Standard` over `Restricted` on Region_Catalogue. Scoring reads that cell |
| Co-locate DR with CVAL while other regions are still free | No separate switch | Co-location happens only when that geography’s model is the text `2-region` |

### 3-region to 4-region

The engine recognises three model texts, looked up from Policy!D5:F9 into Request!B9:

- `3-region` — Prod, CVAL, and DR must be three different Standard regions
- `2-region` — DR is forced onto the CVAL region, and HC-6 (DR free + NonProd free) is applied
- `cross-geo` — Prod and CVAL share a region; DR is chosen in the DR-scope geography

`4-region` is not one of those texts. If you overwrite the US model with `4-region`, the formulas treat it like `3-region`: environments stay apart, and HC-6 stays off. The label changes. The behaviour does not.

US also has only three Standard regions. East US 2 is the fourth region, and it is Restricted, so it never enters automatic scoring. A 4-region layout needs both of these, and this workbook does not do them for you:

1. East US 2 class set to Standard (catalogue cell for East US 2, column Class).
2. A real 4-region rule: four Standard regions compete, and Prod, CVAL, and DR stay in different regions.

After a class edit, East US 2 would compete, and one of the four would be left unused because the current rule still places only three environments. That is not the same as a 4-region distribution model. The older file `acrme_region_selection_whatif_4region.xlsx` is the sandbox that explores that model. This workbook was built to stay on the v2.4 catalogue.

### Restricted to Standard

Class is a value on **Region_Catalogue**, column Class. Line_Check and the score sheets read it. The sheet is not locked.

Change East US 2 from `Restricted` to `Standard`, leave the US request on the exception path, and East US 2 joins West US 3, Central US, and Canada Central in automatic scoring. Change it back to restore the baseline.

That edit is local to this workbook. It does not reclassify the region in the requirements baseline. The supported baseline path for a Restricted region is still to name it in Request!B6.

### Co-host DR with CVAL when spare regions exist

There is no Policy flag for “co-locate DR with CVAL even though another region is free.”

Co-location is wired to one test: Request!B9 = `2-region`. That is true today for EU, Australia, and Asia Pacific, which is what PLC-010a requires. For US, B9 is `3-region`, so DR is chosen from the Standard regions that are not Prod and not CVAL.

If you overwrite the US row on Policy from `3-region` to `2-region`, DR will sit on the CVAL region even while other US regions remain. HC-6 turns on as well. That is a side effect of the model text, not a customer-level option, and it disagrees with the baseline for US. The baseline co-locates only where the geography does not have a third Standard region.

A configuration item that means “this customer co-hosts DR with CVAL” while the geography stays 3-region is not in this file.

## 8. What this mockup does not do

- Per-zone reservation groups. Names are `crg-…-reg` only. Allocation shows the even zone share (1 / AZ) and does not place VMs into zones.
- A stored seed. Allocation displays the PLC-003 fields for this run.
- Cumulative quota across lines of the same family at gate time. Each line is compared with the full pool. The combined draw appears on Quota_After.
- Live Azure inventory, associated-but-deallocated VMs, or `STALE_STATE`.
- The multi-customer DR rule that sizes a destination as the max of its sources.

Rebuild with `python Mockups/build_acrme_aligned_placement.py` only when the catalogue or the mock estate in the builder should change. Edits to yellow cells, and to Class or the model text as described above, recalculate in Excel without a rebuild.
