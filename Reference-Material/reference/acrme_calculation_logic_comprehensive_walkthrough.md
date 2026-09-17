# ACRME Calculation Logic — Plain English Walkthrough

**EU and US · E16ads\_v5 and E8ads\_v5 · 3 VMs per deployment**

---

## The Big Picture — Think of it Like Office Space

Before any numbers, here's the analogy that ties everything together:

| Technical term | Plain English |
|---|---|
| Geography / Region | Country → specific city office building |
| Quota | Maximum number of desks the building permit allows |
| Capacity Reservation | Desks you have physically reserved (even if nobody is sitting there yet) |
| Buffer/Headroom | Extra reserved desks kept deliberately empty for next hire |
| Prod | The main trading floor where real work happens |
| CVAL/NonProd | The testing room — try things before going live |
| DR | An emergency backup office in case the main building floods |
| Placement Score | A report card grading each building on how suitable it is |
| Hard Constraint | A legal requirement — if it fails, you cannot use that building, full stop |

---

## Starter Values Assumed

### SKU Sizes

| VM Type | vCPUs per VM | 3 VMs = vCPUs needed |
|---|---|---|
| E16ads\_v5 | 16 vCPU | 48 vCPU |
| E8ads\_v5 | 8 vCPU | 24 vCPU |

(vCPU = virtual processor — think of it as the number of "workers" each VM needs)

### Regional Snapshot — Assumed Starter Values

Think of each row as the current state of each office building before our customer arrives.

**US Geography — 3 Standard buildings available:**

| Region | Total Pool (vCPU) | Prod Already Used | NonProd Already Used | DR Earmark | Headroom Left | Existing Customers | Floors (AZs) |
|---|---|---|---|---|---|---|---|
| West US 3 | 500 | 120 | 80 | 60 | 240 | 8 of 20 | 3 |
| Central US | 500 | 160 | 100 | 80 | 160 | 12 of 20 | 3 |
| Canada Central | 500 | 80 | 60 | 32 | 328 | 5 of 20 | 2 |

**EU Geography — 2 Standard buildings available:**

| Region | Total Pool (vCPU) | Prod Already Used | NonProd Already Used | DR Earmark | Headroom Left | Existing Customers | Floors (AZs) |
|---|---|---|---|---|---|---|---|
| Switzerland North | 300 | 100 | 60 | 40 | 100 | 6 of 15 | 3 |
| Sweden Central | 300 | 80 | 50 | 32 | 138 | 4 of 15 | 3 |

**Minimum floor (safety net — always kept free regardless):**

- **Prod:** 20 vCPU minimum must remain untouched
- **NonProd:** 20 vCPU minimum must remain untouched
- **DR:** 16 vCPU minimum must remain untouched

---

## PART 1 — REGION SELECTION

### What is region selection?

It is the system picking which buildings a customer's deployment goes into — one for Prod, one for CVAL, one for DR — in that order. Each environment has its own report card formula.

### Why do the scoring weights exist, and why these specific values?

| Weight | Value | Plain English reason |
|---|---|---|
| α = 0.30 (largest) | Headroom/capacity signal | The single most important factor. If a building is nearly full, we cannot grow — and growing is inevitable. Deserves the highest priority. |
| γ = 0.25 | Distribution fairness | We never want all customers in the same building. If one building catches fire (fails), we want as few customers affected as possible. Second highest. |
| β = 0.20 | Quota headroom | The building permit (quota) must have room approved by the authority (Microsoft). Without it, no new desks can be added even if the floor is empty. |
| δ = 0.15 | DR readiness | Is the backup office already covering enough customers? A well-covered DR region is a better destination. Lower priority because DR coverage depends on the customer mix, not just space. |
| ε = 0.10 (smallest) | Zone diversity | Are the desks spread across different floors of the building? If one floor has a power cut, other floors keep running. Nice-to-have, not critical. |

All five add to exactly **1.0 (100%)**. They are policy defaults stored in config — not hardcoded. The team can adjust them if priorities change.

---

## US REGION SELECTION — Customer deploys E16ads\_v5 (48 vCPU needed)

### HAPPY PATH — US, Customer supplies "Central US" (default/exact path)

#### Step 1 — Hard Constraint Gate (Pass/Fail)

Think of this as the building inspector's checklist. Every box must be ticked — no partial credit.

| Check | What it asks | Central US has | Needed | Result |
|---|---|---|---|---|
| HC-3 Quota floor (Prod) | Does the building permit have enough room? | 160 vCPU headroom | 48 vCPU | ✅ Pass (160 ≥ 48) |
| HC-3 Minimum floor | Must keep 20 vCPU free always | 160 − 48 = 112 left | 20 | ✅ Pass |
| HC-6 DR coverage | Enough backup office space? | 80 DR earmark available | — | ✅ Pass |
| HC-7 DR floor integrity | Does adding NonProd break the DR safety net? | Pool still balanced | — | ✅ Pass |

**All pass → Central US enters the scoring round.**

Since the customer supplied the exact region (default path), there is no scoring race — Central US is validated and accepted directly. The score is computed only for audit/replay:

```
PS_Prod(Central US):
  α: 100/160 = 0.625 → 0.30 × 0.625 = 0.188
  β: 160/500 = 0.32  → 0.20 × 0.32  = 0.064
  γ: 1-(12/20)= 0.40 → 0.25 × 0.40  = 0.100
  δ: 0.80 coverage   → 0.15 × 0.80  = 0.120
  ε: 3/3 = 1.0       → 0.10 × 1.0   = 0.100

PS_Prod(Central US) = 0.188 + 0.064 + 0.100 + 0.120 + 0.100 = 0.572
```

**Prod = Central US ✅**

#### Step 2 — CVAL Region Selection

Central US is taken (Prod). Only {West US 3, Canada Central} eligible.

```
PS_NonProd(West US 3):
  α: 240/500 = 0.48 → 0.30 × 0.48 = 0.144
  β: 240/500 = 0.48 → 0.20 × 0.48 = 0.096
  γ: 1-(8/20) = 0.60 → 0.25 × 0.60 = 0.150
  δ: 0.75            → 0.15 × 0.75 = 0.113
  ε: 3/3 = 1.0       → 0.10 × 1.0  = 0.100
= 0.603

PS_NonProd(Canada Central):
  α: 328/500 = 0.66 → 0.30 × 0.66 = 0.198
  β: 328/500 = 0.66 → 0.20 × 0.66 = 0.132
  γ: 1-(5/20) = 0.75 → 0.25 × 0.75 = 0.188
  δ: 0.70            → 0.15 × 0.70 = 0.105
  ε: 2/3 = 0.67      → 0.10 × 0.67 = 0.067
= 0.690
```

Canada Central scores higher (0.690 vs 0.603) — more headroom, fewer customers, but loses slightly on zone diversity (2 floors vs 3).

**CVAL = Canada Central ✅**

#### Step 3 — DR Region Selection

Central US = Prod (excluded). Canada Central = CVAL.

ENV-003 allows DR to share with CVAL → Canada Central is eligible for DR too.
But West US 3 is still available and unused.

```
PS_DR(West US 3):
  α: 240/500 = 0.48 → 0.30 × 0.48 = 0.144
  β: 240/500 = 0.48 → 0.20 × 0.48 = 0.096
  γ: 1-(8/20) = 0.60 → 0.25 × 0.60 = 0.150
  δ: 0.75            → 0.15 × 0.75 = 0.113
  ε: 3/3 = 1.0       → 0.10 × 1.0  = 0.100
= 0.603

PS_DR(Canada Central — co-locate with CVAL):
  α: (328-48)/500 = 0.56 → 0.30 × 0.56 = 0.168
  (after CVAL already consumed 48 vCPU)
  ... [scores lower than West US 3 after CVAL allocation]
```

**DR = West US 3 ✅ (dedicated, better than co-locating)**

#### 🟢 HAPPY PATH RESULT — US, E16ads\_v5:

```
Prod:  Central US        (48 vCPU)
CVAL:  Canada Central    (48 vCPU)
DR:    West US 3         (48 vCPU earmarked standby)
```

Three different buildings, clean separation. Full 3-region deployment. ✅

---

### SAD PATH 1 — US, E16ads\_v5, Central US is nearly full

Assume Central US quota headroom = 12 vCPU (almost no room left)

#### Step 1 — Hard Constraint Gate:

| Check | Central US has | Needed | Result |
|---|---|---|---|
| HC-3 Quota floor | 12 vCPU headroom | 48 vCPU | ❌ FAIL (12 < 48) |

Central US fails the gate before it is even scored. The engine does not guess, try another region, or silently proceed.

**Readiness state returned: `QUOTA_DEFICIT`**

#### What happens next:

1. Deployment is **blocked** with a clear message: "Central US has insufficient quota headroom (12 vCPU available; 48 vCPU required)."
2. A `CapacityIncreaseRequest` is raised automatically (Scenario 12 — auto-increase trigger).
3. Operator receives an alert. After approval, a quota request goes to Microsoft.
4. Until quota is **confirmed** (not assumed — the 10-step lifecycle must complete), deployment stays blocked.
5. Customer cannot proceed until the system reaches `READY`.

#### 🔴 SAD PATH 1 RESULT: `QUOTA_DEFICIT` — deployment blocked, quota increase workflow triggered. ❌

---

### SAD PATH 2 — US, Geography "US" requested (exception path)

Customer says "put me in US" — no specific region named

#### Step 1 — Governance gate fires first:

- This is the **exception path** (Scenario 1) — requires explicit approval + customer acknowledgement.
- If no exception approval on file: `POLICY_BLOCKED` immediately.
- If approval obtained: score all 3 Standard regions.

#### Step 2 — Score all three with PS\_Prod:

| Region | PS\_Prod Score |
|---|---|
| West US 3 | 0.612 |
| Central US | 0.572 |
| Canada Central | 0.660 ← wins |

**Prod = Canada Central** (highest score — most headroom, fewest customers)

But now the **seed is fixed forever** — Canada Central is this customer's permanent Prod unless a migration is formally approved. If the customer later complains "I wanted East Coast," they are told: "You asked for geography; the engine picked the best available building at that moment."

#### 🟡 EXCEPTION PATH RESULT: Works, but the customer has less control. The seed is permanent. This is why exact-region input is the default, and geography-only is the exception path. ⚠️

---

## EU REGION SELECTION — Customer deploys E8ads\_v5 (24 vCPU needed)

EU has only 2 Standard buildings: Switzerland North and Sweden Central. As corrected earlier, EU uses **CVAL + DR co-location** (both share one region), because the design allows DR to share with NonProd (ENV-003).

### HAPPY PATH — EU, Customer supplies "Switzerland North"

#### Step 1 — Hard Constraint Gate for Switzerland North:

| Check | Switzerland North has | Needed | Result |
|---|---|---|---|
| HC-3 Quota floor (Prod) | 100 vCPU headroom | 24 vCPU | ✅ Pass (100 ≥ 24) |
| HC-3 Minimum floor | 100 − 24 = 76 left | 20 vCPU | ✅ Pass |
| HC-7 DR floor integrity | Pool still balanced | — | ✅ Pass |

✅ All pass. **Prod = Switzerland North.**

#### Step 2 — CVAL Selection

Only Sweden Central is available (Switzerland North = Prod, excluded by ENV-003).
One candidate → no scoring needed, deterministic.

HC gate: Sweden Central has 138 vCPU headroom → needs 24 → ✅ Pass.

**CVAL = Sweden Central ✅**

#### Step 3 — DR Selection

EU Standard regions exhausted for separate DR: Switzerland North = Prod (excluded), Sweden Central = CVAL.

ENV-003 explicitly allows DR to co-locate with CVAL.

Sweden Central still has: 138 − 24 (CVAL) = 114 vCPU remaining → 24 more for DR → ✅ Still fits.

**DR = Sweden Central (co-located with CVAL) ✅**

#### 🟢 HAPPY PATH RESULT — EU, E8ads\_v5:

```
Prod:       Switzerland North   (24 vCPU)
CVAL + DR:  Sweden Central      (24 + 24 vCPU in the same building)
```

Two buildings, three environments. Valid by design — Sweden Central hosts both CVAL and DR standby. ✅

The only risk: if Sweden Central itself fails, both CVAL and DR are lost simultaneously — this is a known, accepted trade-off for a 2-region geography.

---

### SAD PATH — EU, E16ads\_v5 (48 vCPU), Switzerland North is nearly full

Assume Switzerland North has only 30 vCPU headroom remaining

#### Step 1 — HC Gate for Switzerland North:

| Check | Has | Needs | Result |
|---|---|---|---|
| HC-3 Quota floor | 30 vCPU | 48 vCPU | ❌ FAIL |

Switzerland North fails. No other Standard EU Prod region is available (Sweden Central is the only alternative).

#### Try Sweden Central for Prod:

| Check | Has | Needs | Result |
|---|---|---|---|
| HC-3 Quota floor | 138 vCPU | 48 vCPU | ✅ Pass |

**Prod = Sweden Central** (only viable option)

#### Step 2 — CVAL: Only Switzerland North remains.

30 vCPU headroom → needs 48 → ❌ FAIL — insufficient for CVAL too.

**Readiness state: `CAPACITY_UNAVAILABLE`**

Both Standard EU buildings cannot satisfy E16ads\_v5 demand simultaneously. Deployment cannot be placed.

#### 🔴 SAD PATH RESULT — EU, E16ads\_v5: `CAPACITY_UNAVAILABLE` — the EU estate is too small for this SKU size today. Options:

1. **Wait** — reconciliation will request more capacity from Microsoft automatically.
2. **Switch to E8ads\_v5** — fits within current headroom.
3. **Cross-geo exception** — deploy Prod in EU, CVAL/DR via a governance-approved cross-geo path.

---

## PART 2 — QUOTA MANAGEMENT

### What is quota management?

Think of quota as the **building permit** issued by the local authority (Microsoft). Even if you have empty desks (capacity), you cannot seat more people than your permit allows. Quota management keeps the permit large enough for today plus planned growth, without wasting money on unused permit space.

### Why are the growth buffer constants 20%?

#### Why 20% (0.20) for Prod and NonProd growth buffers?

**Baseline principle (QUA-006):** "Production subscriptions maintain a configurable quota headroom above current usage to support growth and the next deployment." The 20% is the policy default — if you are using 100 desks today, the permit covers 120, so you are never caught scrambling when the next team joins. 20% balances cost (unused permit has a cost) against deployment agility (no emergency quota requests to Microsoft). This value is configurable per product/region — a fast-growing product might use 30%; a stable mature product might use 10%.

#### Why 30% (0.30) for emergency transfer headroom?

During a disaster, you need to quickly move staff from a failed building to the backup office. 30% of potential DR demand is kept as emergency headroom inside the pool. Without it, the emergency request to Microsoft (which takes days) would happen at the worst possible moment. 30% is the default balance between cost and emergency readiness — also configurable.

---

## Quota Pool Calculation — US, E16ads\_v5 (48 vCPU per deployment)

Using West US 3 as the example region, with these assumed starter values:

| Item | Value |
|---|---|
| Prod CRG quantity reserved | 200 vCPU (for existing customers) |
| NonProd CRG quantity reserved | 120 vCPU |
| DR Earmark (max-not-sum, from Part 3) | 120 vCPU (standby for largest source = 120) |
| Emergency transfer headroom | 36 vCPU (30% × 120 DR demand) |

### Pool Limit calculation:

```
Pool_Limit(West US 3) =
    Prod_CRG × (1 + 0.20)    = 200 × 1.20 = 240 vCPU  [Prod + 20% growth]
  + NonProd_CRG × (1 + 0.20) = 120 × 1.20 = 144 vCPU  [NonProd + 20% growth]
  + DR_Earmark               =              120 vCPU  [standby for DR]
  + Emergency headroom        =               36 vCPU  [30% emergency buffer]
                                          ─────────
Pool_Limit(West US 3)        =              540 vCPU
```

### Protection earmarks inside the pool (nobody can touch these):

```
Prod_Reserved_Floor  = 200 (used) + 40 (20% growth buffer) = 240 vCPU    [LOCKED for Prod]
DR_Earmark_vCPU      = 120 vCPU                                           [LOCKED for DR]
NonProd_Used         = 120 vCPU

Allocatable_NonProd  = 540 - 240 - 120 - 120 = 60 vCPU   [freely available for NonProd]
Pool_Headroom        = 540 - (240+120+120) = 60 vCPU       [total free space]
```

### HAPPY PATH — New customer requests 48 vCPU (E16ads\_v5 × 3 VMs)

The 60 vCPU of Allocatable\_NonProd is checked:

```
60 vCPU available ≥ 48 vCPU requested → ✅ PASS
After allocation: Allocatable_NonProd = 60 - 48 = 12 vCPU remaining
```

🟢 **HAPPY PATH — Quota check passes. Deployment proceeds.**

Separately, the Prod quota for Central US (new Prod region) is checked:

```
Prod_Group_headroom(Central US) = 160 vCPU ≥ 48 vCPU → ✅ PASS
```

Both checks pass → `READY` state confirmed.

### SAD PATH — Pool is nearly exhausted (10 vCPU Allocatable\_NonProd)

Assume many customers were just deployed; Allocatable\_NonProd dropped to 10 vCPU.

```
10 vCPU available < 48 vCPU requested → ❌ FAIL (HC-7 DR Floor Integrity)
```

The system does NOT touch the Prod\_Reserved\_Floor or DR\_Earmark\_vCPU — those are locked. It refuses the NonProd allocation.

**Alert fired: `DRFloorViolationDetected` (Critical severity)**

#### What happens:

1. Deployment **blocked**: `RESERVATION_DEFICIT` or `QUOTA_DEFICIT` state returned.
2. The dual-validation detector independently confirms the shortfall.
3. Auto-increase trigger fires (utilisation ≥ 20% threshold crossed for NonProd).
4. The 10-step lifecycle begins (detect → re-read → create request → calculate target → operator approves → submit to Microsoft → wait for confirmation → update pool → confirm → refresh snapshot).

🔴 **SAD PATH — Deployment blocked. Quota increase workflow triggered. Estimated resolution: hours to days depending on Microsoft's quota approval time.**

---

## EU Quota — E8ads\_v5 (24 vCPU), Sweden Central

Starter values for Sweden Central:

```
Prod_CRG = 80 vCPU,  NonProd_CRG = 50 vCPU,  DR_Earmark = 80 vCPU

Pool_Limit(Sweden Central) =
    80 × 1.20 + 50 × 1.20 + 80 + (0.30 × 80)
  = 96 + 60 + 80 + 24 = 260 vCPU

Prod_Reserved_Floor = 80 + 16 = 96 vCPU
DR_Earmark          = 80 vCPU
NonProd_Used        = 50 vCPU
Allocatable_NonProd = 260 - 96 - 80 - 50 = 34 vCPU
```

- **Happy path** (E8ads\_v5 = 24 vCPU): 34 ≥ 24 → ✅ `READY`
- **Sad path** (E16ads\_v5 = 48 vCPU): 34 < 48 → ❌ `QUOTA_DEFICIT`

---

## PART 3 — CAPACITY MANAGEMENT

### What is capacity management?

Quota is the permit; **capacity is the actual furniture** — the reserved desks. Quota allows you to have up to N desks; capacity management ensures you have exactly the right number of desks reserved at all times — not too few (team can't sit), not too many (paying for empty desks). The engine re-checks this every 6 minutes.

### Why are the auto-increase threshold values what they are?

| Threshold | Value | Why |
|---|---|---|
| DR auto-increase | 35% utilised | DR capacity is the hardest to acquire in an emergency. We trigger the increase earlier (at 35%) to give enough lead time. You would rather have too much DR standby than scramble for it during a disaster. |
| Prod auto-increase | 20% utilised | Production is business-critical. Trigger early, before pressure builds. But 20% (not 35%) because Prod quota is generally more available than DR capacity. |
| NonProd auto-increase | 20% utilised | Same logic as Prod — early warning, manageable pressure. |
| Debounce cooldown | 30 min | Prevents the engine from flooding Microsoft with quota requests if utilisation briefly spikes and then drops. Wait 30 minutes to confirm the trend is real. |

These are all **configurable policy defaults** — not hardcoded constants.

---

## Capacity Reconciliation — US, West US 3, E16ads\_v5

Starter state:

```
Reserved (CRG quantity):  200 vCPU  [desks physically reserved]
Allocated (running VMs):  160 vCPU  [desks with people sitting]
Configured Buffer:         40 vCPU  [deliberately empty desks for next hire]
```

### Target Reserved Capacity:

```
Target = Allocated + Buffer = 160 + 40 = 200 vCPU
Reservation Headroom = 200 - 160 = 40 vCPU    [40 desks sitting empty, as planned]
Reservation Deficit  = max(0, 200 - 200) = 0   [no deficit — perfectly balanced]
```

### HAPPY PATH — New customer adds 3 × E16ads\_v5 (48 vCPU)

After deployment:

```
Allocated = 160 + 48 = 208 vCPU
Target    = 208 + 40  = 248 vCPU    [we now need 248 desks reserved]
Reserved  = 200 vCPU  (unchanged yet)

Reservation Deficit = max(0, 248 - 200) = 48 vCPU
```

The engine detects the deficit at next reconciliation cycle (within 6 minutes):

1. Checks: is utilisation ≥ 20% threshold? → 208/500 = 41.6% → ✅ Yes, auto-increase triggers.
2. Calculates: need 48 more vCPU reserved.
3. Operator approves → submits to Azure → waits for confirmation (never assumes) → updates CRG → refreshes snapshot.

🟢 **HAPPY PATH — System self-heals within one reconciliation cycle. ✅**

### SAD PATH — Azure cannot supply the additional 48 vCPU

After the quota increase request is submitted, Azure responds: "SKU E16ads\_v5 has no available capacity in West US 3 at this time."

```
Reserved stays: 200 vCPU
Target needs:   248 vCPU
Deficit:         48 vCPU — CANNOT be filled
```

#### System behaviour:

1. Does NOT silently deploy — the system holds current state.
2. Fires alert: "Buffer deficit of 48 vCPU in West US 3; Azure cannot supply at this time."
3. Readiness state: `CAPACITY_UNAVAILABLE`
4. The CRG reservation object is kept at zero (not deleted — deletion only via a formal decommissioning workflow).
5. Operator options: wait for Azure capacity to free up, switch SKU to E8ads\_v5, or move to Canada Central.

🔴 **SAD PATH — `CAPACITY_UNAVAILABLE`. System is holding and alerting; it will not destroy the reservation or silently accept a gap.**

---

## DR Capacity — Max-Not-Sum Sizing (the lean DR model)

This is where the old fixed 30-40% DR reserve is replaced with a smarter calculation.

### Why max-not-sum? A plain English explanation:

**The old way (wrong):** "Our 3 US buildings each need a backup office. Building A sends 120 people to West US 3 in a disaster. Building B sends 80 people to West US 3. So West US 3 needs 200 backup desks reserved."

**The flaw:** Can both Building A AND Building B fail at the same time? The design assumes no — only one production building fails at a time. So you only ever need to recover from the biggest source, not all sources simultaneously.

**The new way (correct):**

```
DR standby needed at West US 3 = MAX(120, 80) = 120 desks   [not 200]
Saving: 80 desks (40%) — freed for real work, paying nothing extra for protection
```

### Worked example with our starter values:

| Source Region | Customers sending DR to West US 3 | vCPU at risk |
|---|---|---|
| Central US | Customers 1–5 | 120 vCPU |
| Canada Central | Customer 6 | 80 vCPU |

```
DR_Requirement(West US 3) = MAX(120, 80) = 120 vCPU    [only the biggest]
DR_Gap(West US 3) = max(0, 120 - 100 usable) = 20 vCPU  [need 20 more]

Overcommit_Ratio = (120+80)/120 = 1.67
```

→ West US 3 is "1.67× oversubscribed" for DR — acceptable because failures are mutually exclusive

### HAPPY PATH — DR capacity is sufficient

```
Usable_Destination_Capacity(West US 3) = 130 vCPU
DR_Requirement                          = 120 vCPU
DR_Gap = max(0, 120 - 130) = 0 vCPU    → ✅ No gap. DR is fully covered.
```

🟢 **HAPPY PATH — DR standby is healthy. Alert threshold (OBS-002) not breached. ✅**

### SAD PATH — DR capacity falls below the requirement

```
Usable_Destination_Capacity(West US 3) = 100 vCPU   [some VMs allocated into the headroom]
DR_Requirement                          = 120 vCPU
DR_Gap = max(0, 120 - 100) = 20 vCPU   → ❌ Gap!
```

Auto-increase fires at 35% DR utilisation threshold (earlier than Prod's 20%):

```
DR utilisation = 100/120 = 83% ≥ 35% threshold → trigger auto-increase
```

🔴 **SAD PATH — DR gap detected. System fires `ForecastApproachingQuotaLimit` alert. Operator must approve a 20 vCPU DR increase. Until confirmed, the DR coverage is flagged `READY_WITH_RISK` — system continues running but marks the shortfall on the dashboard.**

---

## Complete Summary — All Paths

| Geography | SKU | Scenario | Region Result | Quota Result | Capacity Result | Final State |
|---|---|---|---|---|---|---|
| US | E16ads\_v5 | Exact region, all headroom available | Prod: Central US · CVAL: Canada Central · DR: West US 3 | Pool passes all checks | Target met, no deficit | 🟢 `READY` |
| US | E16ads\_v5 | Central US quota exhausted | HC-3 fails | `QUOTA_DEFICIT` | Blocked | 🔴 `QUOTA_DEFICIT` |
| US | E16ads\_v5 | Geography only ("US") — exception | Prod: Canada Central (highest score) | Must recheck after scoring | System continues | 🟡 `READY` (seed locked forever) |
| EU | E8ads\_v5 | Switzerland North available | Prod: Switzerland North · CVAL+DR: Sweden Central | Both pools pass | Target met | 🟢 `READY` |
| EU | E16ads\_v5 | Switzerland North nearly full (30 vCPU) | Both EU buildings fail HC-3 | N/A | N/A | 🔴 `CAPACITY_UNAVAILABLE` |
| EU/US | Any | Pool nearly full (10 vCPU left) | Region selected | DR floor integrity violated | Blocked | 🔴 `RESERVATION_DEFICIT` |
| US | E16ads\_v5 | Azure cannot supply after auto-increase | Region selected | Quota requested | Azure returns no capacity | 🔴 `CAPACITY_UNAVAILABLE` (holds, alerts, never deletes) |
| US | E16ads\_v5 | DR gap at West US 3 | Regions selected fine | Quota fine | DR short by 20 vCPU | 🟡 `READY_WITH_RISK` |
