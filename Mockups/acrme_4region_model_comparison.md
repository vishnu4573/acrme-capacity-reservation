# ACRME 4-Region DR Model — What-If Analysis Comparison

**Document Purpose:** Compare the baseline v2.4 region distribution models against a proposed 4-region upgrade for US and EU geographies.

**Workbook:** `acrme_region_selection_whatif_4region.xlsx` (what-if variant; does NOT modify baseline requirements)

---

## Model Comparison Matrix

| Geography | Baseline v2.4 Model | 4-Region What-If | Regions Required | Impact |
|-----------|---------------------|------------------|------------------|--------|
| **US** | 3-region | **4-region** | 4 Standard regions | ✅ All 4 US Standard regions compete |
| **EU** | 2-region (CVAL/DR co-located) | **4-region** | 4 Standard regions | ✅ CVAL and DR **no longer co-locate** |
| **Australia** | 2-region (CVAL/DR co-located) | **2-region** (unchanged) | 2 Standard regions | No change |
| **Asia Pacific** | 2-region (CVAL/DR co-located) | **2-region** (unchanged) | 2 Standard regions | No change |
| **Middle East** | cross-geo DR (Prod+CVAL local; DR in EU) | **cross-geo** (unchanged) | 1 local + 1 EU | No change |

---

## Key Changes — 4-Region Model

### 1. **PLC-010a Co-Location Rule — DEACTIVATED for US and EU**

**Baseline (2-region model):**
```
PLC-010a: In 2-region geographies (EU, Australia, Asia Pacific),
          CVAL and DR MUST co-locate in the same region.
```

**4-Region model:**
- **US and EU**: PLC-010a **NO LONGER APPLIES**
- Prod, CVAL, and DR can each occupy **separate, distinct regions**
- Improves **blast-radius isolation** — a CVAL region failure no longer impacts DR readiness

**Australia, Asia Pacific**: PLC-010a still applies (remain 2-region)

---

### 2. **HC-6 and HC-7 Hard Constraint Gates — DISABLED for US/EU**

| HC Gate | Baseline (2-region) | 4-Region Model (US/EU) |
|---------|---------------------|------------------------|
| **HC-3 Prod** | `Prod_Q_Headroom >= Req_vCPU AND Prod_Q_Headroom - Req_vCPU >= MinBuffer` | ✅ Same (still applies) |
| **HC-3 NonProd** | `NP_Eff_Free >= Req_vCPU AND NP_Q_Headroom - Req_vCPU >= MinBuffer` | ✅ Same (still applies) |
| **HC-3 DR** | `DR_Free >= DR_bootstrap_qty` | ✅ Same (still applies) |
| **HC-6 DR Floor** | `DR_Free + CVAL_Eff_Free >= DR_bootstrap_qty` | ⚠️ **N/A (4-region)** — auto-satisfied |
| **HC-7 DR Integrity** | `CVAL_Q_Used + Req_vCPU <= CVAL_Q_Limit - DR_bootstrap_qty` | ⚠️ **N/A (4-region)** — auto-satisfied |

**Implementation:**
- **HC-6/HC-7 formulas** check geography first:
  ```excel
  =IF(OR(Geography="US",Geography="EU"),"N/A (4-region)",<normal check>)
  ```
- Eligibility logic treats `"N/A (4-region)"` as an automatic **PASS**
- **Result:** US and EU regions are **no longer blocked** by CVAL/DR co-location constraints

---

### 3. **Region Catalogue — All Standard Regions Now Compete**

| Geography | Baseline Restricted Regions | 4-Region Model Status |
|-----------|----------------------------|----------------------|
| **US** | East US 2 (exception required) | ✅ Promoted to **Standard** (competes for placement) |
| **EU** | North Europe, West Europe (exception required) | ✅ Promoted to **Standard** (compete for placement) |
| **Middle East** | Saudi Arabia East, UAE North (production-only) | ⚠️ Remain **Restricted** (unchanged) |

**Impact:**
- **US**: 4 candidate regions (West US 3, Central US, Canada Central, East US 2)
- **EU**: 4 candidate regions (Switzerland North, Sweden Central, North Europe, West Europe)

---

### 4. **Region Selection Sequencing — 3-Pass vs 2-Pass**

**Baseline (2-region EU):**
1. Select Prod region (weighted scoring on 2 Standard regions)
2. Select CVAL/DR region (the other Standard region — they co-locate)

**4-Region model (EU):**
1. Select Prod region (weighted scoring on all 4 Standard regions)
2. Select CVAL region (weighted scoring on remaining 3 regions, excluding Prod)
3. Select DR region (weighted scoring on remaining 2 regions, excluding Prod and CVAL)

**Impact:** More **fine-grained placement** — each environment gets its own weighted-optimal region

---

### 5. **Capacity Accounting — Simplified (US/EU)**

**Baseline (2-region co-located model):**
- CVAL and DR share the same **Reserved** pool
- Complex accounting: HC-6 (combined DR+CVAL floor), HC-7 (CVAL allocation protects DR headroom)
- Risk: CVAL allocation can consume DR reserve

**4-Region model (US/EU):**
- Each environment (Prod / CVAL / DR) has its **own Reserved pool**
- Independent capacity accounting — no cross-environment interference
- Simpler HC checks: each region evaluated purely on its own metrics

---

### 6. **DR Sizing Formula — No Change**

The **MAX-NOT-SUM** sizing rule (A.6 / DR-017) remains unchanged:
```
DR_req = MAX over all source_regions of (customers_in_source × vCPU_per_customer)
```

- This is **model-independent**
- **Multi-source DR hosting** (DR-016) benefits from 4-region model (more DR destination candidates)

---

### 7. **Placement Scoring Engine — γ Component Adjustment**

| Component | Baseline (2-region EU) | 4-Region Model (EU) |
|-----------|------------------------|---------------------|
| **α (Efficient Free)** | Same formula | Same formula |
| **β (Quota Headroom)** | Same formula | Same formula |
| **γ (Distribution Fairness)** | `1 - (customers_in_region / total_customers)` normalized over **2 regions** | `1 - (customers_in_region / total_customers)` normalized over **4 regions** |
| **δ (DR Coverage)** | CVAL region scores for DR too | **Separate DR scoring** |
| **ε (Zone Diversity)** | Same formula | Same formula |

**Impact:** γ component normalizes over **4 regions** instead of 2, improving distribution fairness

---

## What-If Workbook Usage

1. **Open** `acrme_region_selection_whatif_4region.xlsx`
2. **Navigate to Setup sheet:**
   - Select **Geography** (US or EU to see 4-region impact)
   - Enter **SKU**, **VM count**, **Customer ID**
3. **Review HC_Gate sheet:**
   - US and EU regions show **"N/A (4-region)"** for HC-6 and HC-7
   - All US/EU regions automatically eligible for NonProd and DR (if HC-3 passes)
4. **Check Scoring sheets:**
   - More regions compete (4 candidates instead of 2-3)
   - Rank column shows placement order
5. **Review Result sheet:**
   - Prod, CVAL, DR placements (may occupy **3 distinct regions** in 4-region model)
   - Readiness states
   - Ranked Candidates table

---

## Side-by-Side Comparison: US Geography Example

### Baseline (3-region model)
- **Prod**: West US 3 (Rank 1, PS = 0.82)
- **CVAL**: Central US (Rank 2, PS = 0.76)
- **DR**: Canada Central (Rank 3, PS = 0.71)
- **East US 2**: Excluded (Restricted — requires exception)

### 4-Region Model
- **Prod**: West US 3 (Rank 1, PS = 0.82)
- **CVAL**: Central US (Rank 2, PS = 0.76)
- **DR**: Canada Central (Rank 3, PS = 0.71)
- **East US 2**: Now **Rank 4** candidate (PS = 0.68) — competes for placement

**Impact:** East US 2 now participates in weighted scoring; if capacity shifts (e.g., West US 3 fills up), East US 2 automatically becomes a viable alternative.

---

## Side-by-Side Comparison: EU Geography Example

### Baseline (2-region model with PLC-010a co-location)
- **Prod**: Switzerland North (Rank 1, PS = 0.79)
- **CVAL + DR**: Sweden Central (Rank 2, PS = 0.74) — **co-located in the same region**
- **North Europe, West Europe**: Excluded (Restricted)

**Constraints:**
- HC-6: `DR_Free + CVAL_Eff_Free >= DR_bootstrap_qty` (joint check)
- HC-7: `CVAL_Q_Used + Req_vCPU <= CVAL_Q_Limit - DR_bootstrap_qty` (protects DR floor)

### 4-Region Model
- **Prod**: Switzerland North (Rank 1, PS = 0.79)
- **CVAL**: Sweden Central (Rank 2, PS = 0.74)
- **DR**: North Europe (Rank 3, PS = 0.69) — **separate region**
- **West Europe**: Now Rank 4 candidate (PS = 0.65)

**Constraints:**
- HC-6: **N/A (4-region)** — auto-satisfied
- HC-7: **N/A (4-region)** — auto-satisfied
- CVAL and DR evaluated independently

**Impact:**
1. **Blast-radius improvement:** DR no longer impacted by CVAL region failure
2. **Capacity independence:** CVAL allocation cannot consume DR reserve
3. **More placement options:** 4 regions compete instead of 2

---

## Migration Path (If Adopted)

If the 4-region model is adopted as the new baseline:

### Phase 1: US (3-region → 4-region)
✅ **Low risk** — US already has 3 separated regions
- Promote **East US 2** from Restricted → Standard
- **Option A:** Dual-DR model (Prod / CVAL / DR-Primary / DR-Secondary)
- **Option B:** 4-way split (Prod / CVAL / DR-1 / DR-2)

### Phase 2: EU (2-region → 4-region)
⚠️ **Higher impact** — requires breaking CVAL/DR co-location
- Promote **North Europe + West Europe** from Restricted → Standard
- Update **REG-003** (distribution model) to add "4-region" as a third model
- Amend **PLC-010** to carve out US/EU from PLC-010a (co-location rule)
- Remove **HC-6/HC-7** co-location checks for 4-region geographies
- **Migrate existing EU customers:** re-run placement seed (PLC-003) to split CVAL and DR into separate regions

---

## Requirements Impact Summary (If Adopted)

| Requirement | Current State | 4-Region Model Change |
|-------------|---------------|----------------------|
| **REG-003** | Three models: 3-region (US), 2-region (EU/AU/AP), cross-geo (ME) | Add **4-region model** for US and EU |
| **PLC-010a** | CVAL/DR co-location mandatory in 2-region geographies | Carve out US/EU (no longer applies to 4-region) |
| **HC-6** | DR Floor check for 2-region co-located model | Disabled for 4-region geographies |
| **HC-7** | DR Integrity check for 2-region co-located model | Disabled for 4-region geographies |
| **ENV-003** | Co-location-in-region vs capacity-sharing clarified | No change (still applies to Australia, Asia Pacific) |

---

## Known Limitations (What-If Model)

1. **No real production data** — workbook uses SYNTHETIC distributed capacity
2. **East US 2, North Europe, West Europe** promoted to Standard for this what-if only (still Restricted in baseline v2.4)
3. **Migration plan not included** — existing EU customers would need placement re-seeding
4. **No cost model** — does not quantify 4-region DR reserve cost vs 2-region co-located model

---

## Next Steps

1. **Run the what-if workbook** with representative customer scenarios (US, EU)
2. **Compare placement results:** baseline vs 4-region model
3. **Evaluate blast-radius benefits** (CVAL/DR separation in EU)
4. **Assess cost impact** (4 DR regions vs 2 co-located regions)
5. **Decision:** formal REG-003 amendment or remain with baseline v2.4 models

---

**Document Status:** What-if exploration only — does NOT modify baseline requirements  
**Baseline Reference:** Requirements Baseline v2.4, REG-003, PLC-010a, HC-6, HC-7  
**Workbook:** `acrme_region_selection_whatif_4region.xlsx`  
**Builder Script:** `build_acrme_whatif_4region.py`
