# PS_Prod α Component Design Rationale — Why NonProd Headroom Drives Prod Placement

**Document Type:** Design Rationale / Technical Reference\
**Baseline Version:** v2.4\
**Related Requirements:** PLC-001, PLC-002, CAP-013, QUA-004\
**Status:** Design-of-Record

---

## Executive Summary

The Production Placement Score (`PS_Prod`) uses **NonProd CRG headroom** in its α (availability fit) component, not Prod CRG headroom. This is a deliberate, forward-looking design choice that makes Prod placement a **multi-dimensional regional health check**, not just a "does this region have Prod capacity right now?" gate.

**The Formula:**

```
PS_Prod(r) α component = 0.30 × Clamp(nonprod_crg.effective_free / prod_crg.quantity)
                                      ↑                              ↑
                                   NonProd FREE              Prod REQUIREMENT
```

**NOT:**

```
❌ 0.30 × Clamp(prod_crg.effective_free / prod_crg.quantity)  ← This would be self-referential
```

This document explains the five strategic reasons behind this design.

---

## Five Strategic Reasons

### 1\. Avoid Circular Self-Reference

**If α used Prod headroom:**

* You'd be evaluating "How much Prod capacity does this region have to accommodate this Prod workload?"

* This is **self-referential** — you're measuring the thing you're about to allocate against itself

* Creates a feedback loop where Prod placement depends on Prod capacity, which changes after Prod placement

**With NonProd headroom:**

* You're measuring an **independent signal** — NonProd capacity health is not directly affected by this Prod allocation

* Provides a forward-looking indicator of the region's overall capacity health

---

### 2\. Future CVAL Co-Location Readiness (2-Region Model)

In a 2-region model (e.g., EU: West Europe + North Europe):

* **Prod** goes to Region A

* **CVAL + DR** co-locate in Region B (the other region)

**The scoring logic anticipates this:**

* If Prod goes to a region with good NonProd headroom, it signals that region can also support future NonProd (CVAL) growth in the same region if needed

* Even though CVAL typically goes to the OTHER region, having NonProd headroom where Prod lives provides overflow capacity and regional balance

#### Example — EU 2-Region Model

| Scenario | Region A (Prod Candidate) | Region B (CVAL/DR Candidate) |
| --- | --- | --- |
| **Unbalanced** | Prod Free = 8000<br>NonProd Free = 500 (tiny) | Prod Free = 2000<br>NonProd Free = 10000 |
| **Balanced** | Prod Free = 5000<br>NonProd Free = 6000 | Prod Free = 5000<br>NonProd Free = 6000 |

**If α used Prod Free:**

* Region A would score higher (8000 > 5000)

* But it's a **capacity trap** — Region A has almost no NonProd headroom; if any NonProd workload needs to overflow there, it fails

**With NonProd Free:**

* Balanced region scores higher (6000 vs 500)

* Prod placement favors regions with **holistic capacity health**, not just Prod-specific capacity

---

### 3\. Regional Capacity Health Indicator

NonProd headroom is a **proxy for overall regional health**:

**A region with ample NonProd headroom likely has:**

* Good overall capacity management

* Room for future growth across all environments

* Lower contention for resources

**A region with depleted NonProd headroom signals:**

* Capacity strain

* Higher risk of quota exhaustion

* Less flexibility for future deployments

Placing Prod in a region with good NonProd headroom ensures the Prod workload lands in a **healthy, well-provisioned region**, not just one that happens to have Prod capacity today.

---

### 4\. Overflow and Failover Capacity

In some scenarios, NonProd capacity can serve as overflow for Prod:

* **Burst capacity:** During a Prod spike, NonProd CRG might temporarily absorb overflow (subject to governance)

* **Emergency failover:** If Prod capacity is exhausted, NonProd headroom provides a safety margin

* **Multi-environment flexibility:** A region with balanced Prod + NonProd capacity can handle diverse workload mixes

By favoring regions with NonProd headroom, the model ensures Prod lands where there's **operational flexibility**, not just Prod-specific capacity.

---

### 5\. Cross-Signal Validation (β Component Covers Prod Directly)

The `PS_Prod` formula already has a **Prod-specific signal**:

```
β component = 0.20 × Clamp(prod_crg.quota_headroom / prod_crg.quota_limit)
                             ↑
                        Prod QUOTA headroom (direct Prod signal)
```

**Division of labor:**

* **α (NonProd headroom):** Forward-looking regional health + overflow capacity

* **β (Prod quota headroom):** Direct Prod capacity readiness

**If α also used Prod headroom:**

* α and β would be highly correlated (both measuring Prod capacity)

* Combined weight = 0.30 + 0.20 = 0.50 (half the total score) dominated by Prod-only signals

* Other dimensions (distribution fairness, DR coverage, zone diversity) would be under-weighted

**With α on NonProd headroom:**

* α and β measure **different dimensions** of capacity health

* The formula is balanced across multiple signals, not dominated by a single capacity type

---

## Comparison: What Changes If α Used Prod Headroom?

### Current Formula (Design-of-Record)

| Component | Signal | Weight | What It Measures |
| --- | --- | --- | --- |
| **α** | `nonprod_crg.effective_free / prod_crg.quantity` | 0.30 | Regional NonProd health + overflow capacity |
| **β** | `prod_crg.quota_headroom / prod_crg.quota_limit` | 0.20 | Direct Prod quota readiness |
| **γ** | `1 - prod_customer_count / total_customers` | 0.25 | Distribution fairness ⚠️ |
| **δ** | `dr_crg.coverage_ratio` | 0.15 | DR readiness |
| **ε** | `az_count / 3` | 0.10 | Zone diversity |

> ⚠️ **SPEC GAP (GAP-γ):** The `total_customers` term in the γ component is undefined in Requirements Baseline v2.5. Its source, scope, and data type are not specified. See `acrme_calculation_logic_comprehensive_walkthrough.md` OPEN ISSUE section for details and proposed resolution options.

**Result:** Multi-dimensional scoring across 5 independent signals.

---

### Hypothetical Alternative (α Uses Prod Headroom)

| Component | Signal | Weight | What It Measures |
| --- | --- | --- | --- |
| **α** | `prod_crg.effective_free / prod_crg.quantity` | 0.30 | Direct Prod capacity headroom |
| **β** | `prod_crg.quota_headroom / prod_crg.quota_limit` | 0.20 | Direct Prod quota headroom |
| **γ** | `1 - prod_customer_count / total_customers` | 0.25 | Distribution fairness ⚠️ |
| **δ** | `dr_crg.coverage_ratio` | 0.15 | DR readiness |
| **ε** | `az_count / 3` | 0.10 | Zone diversity |

> ⚠️ **SPEC GAP (GAP-γ):** The `total_customers` term is undefined (see note above).

**Problems:**

* α and β are **highly correlated** — both measure Prod capacity (combined 0.50 weight)

* **No NonProd signal** — regional capacity health is one-dimensional

* **Risk of imbalance** — Prod could land in a region with great Prod capacity but terrible NonProd capacity

---

## Worked Example — Why It Matters

### Scenario: US 3-Region Model

**Request:** Deploy Prod workload requiring 10,000 vCPU (64-core line item)

| Region | Prod Free | NonProd Free | Prod Quota Headroom | α (Current) | α (If Prod) | β | PS_Prod Impact |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **West US 3** | 8,000 | 12,000 | 0.85 | Clamp(12000/10000)=**1.0** | Clamp(8000/10000)=**1.0** | 0.85 | Both formulas rank this high |
| **Central US** | 9,000 | 500 | 0.90 | Clamp(500/10000)=**0.05** | Clamp(9000/10000)=**1.0** | 0.90 | **DIVERGENCE** |
| **Canada Central** | 3,000 | 8,000 | 0.60 | Clamp(8000/10000)=**0.80** | Clamp(3000/10000)=**0.30** | 0.60 | **DIVERGENCE** |

---

### Current Formula (α on NonProd):

1. **West US 3** scores highest (α=1.0, β=0.85)

2. **Canada Central** scores 2nd (α=0.80, β=0.60)

3. **Central US** scores **LOW** (α=0.05) — despite high Prod capacity, its depleted NonProd headroom signals capacity strain

---

### If α Used Prod:

1. **West US 3** still scores highest

2. **Central US** jumps to 2nd (α=1.0, β=0.90) — looks great on Prod-only metrics

3. **Canada Central** drops (α=0.30) — penalized for lower Prod capacity

---

### Outcome:

* **Current formula:** Prod lands in a **balanced, healthy region** (West US 3 or Canada Central)

* **Alternative formula:** Prod might land in **Central US** — a region with Prod capacity but **starved NonProd capacity**, risking future contention

---

## Summary — Design Rationale Table

| Reason | Benefit |
| --- | --- |
| **1. Avoid self-reference** | Independent signal, not circular dependency |
| **2. Future co-location readiness** | Anticipates CVAL placement needs (2-region model) |
| **3. Regional health indicator** | Favors holistic capacity health, not just Prod-specific |
| **4. Overflow capacity** | NonProd can serve as safety margin for Prod spikes |
| **5. Multi-dimensional scoring** | α and β measure different dimensions (not correlated) |

---

## Bottom Line

Using **NonProd headroom in α** makes `PS_Prod` a **forward-looking, multi-dimensional health check**, not just a "does this region have Prod capacity right now?" binary gate.

It ensures Prod workloads land in regions with **overall capacity resilience**, not just Prod-specific headroom — anticipating future growth, overflow needs, and regional balance across all environments.

---

_Design rationale for PS_Prod α component — ACRME Capacity Reservation baseline v2.4 · documented 28 Sep 2026_