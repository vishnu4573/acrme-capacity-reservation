# ACRME — CRG & CR Foundation Provisioning Plan

## Document Control

| Field                   | Value                                                                                                |
|-------------------------|-----------------------------------------------------------------------------------------------------|
| **Title**               | ACRME — Capacity Reservation Group & Capacity Reservation Foundation Provisioning Plan               |
| **Version**             | 1.0                                                                                                  |
| **Date**                | 9 Sep 2026                                                                                           |
| **Status**              | Draft — planning gate (pre-deployment)                                                               |
| **Owner**               | Platform Engineering / Cloud Architecture                                                            |
| **Source baseline**     | `acrme_requirements_baseline_v2_4.md` (authoritative: CAP-001..024, OPS-006, ENV-003, QUA-*, REG-003)|
| **Related**             | `acrme_cr_crg_deployment_layout.md`, `acrme_poc_workbook_v2_4.md`, ADR-002/003/006                   |
| **Purpose**             | Plan the creation of CRGs and CRs (the foundation) **before** any deployment — cover all grounds     |

> **Scope of this plan.** This is a **planning artifact for the creation phase only** — standing up the CRG/CR *structure* (groups + seed reservations at count 0), not deploying workloads and not building the reconciliation engine. It answers: *what do we create, in what order, with what names, where, and how do we prove it is correct before we start deploying?* It deliberately stops at the point where the seed structure exists and validates; workload deployment, reconciliation automation (CAP-005/CAP-006), and DR activation are downstream phases.

---

## 1. Purpose & Position in the Programme

This plan operationalizes the **deployment layout** (`acrme_cr_crg_deployment_layout.md`) into an **ordered, checkable build sequence**. Where the layout doc answers *"what does the structure look like"*, this plan answers *"how do we bring it into existence correctly, and how do we know we covered everything."*

**Explicit goals:**
1. Establish the canonical **order of operations** for creating CRGs and CRs (Azure-first, CAP-002).
2. Define the **seed matrix** to create (count-0 reservations per eligible SKU × region × AZ, CAP-022).
3. Apply the **naming convention** deterministically (OPS-006 / C-12).
4. Enforce **structural isolation** at creation time (per-AZ CRGs CAP-023; environment separation ENV-003).
5. Gate creation with **eligibility checks** (CAP-020/021 — no Availability-Set VMs; zonal placement).
6. Provide a **coverage matrix** proving every relevant requirement maps to a build step and a validation.
7. Define a **phased rollout** (pilot → geography-by-geography) so we do not big-bang the estate.

**Non-goals (downstream phases, not this plan):**
- Reconciliation automation / the container-app job (CAP-005/CAP-006) — Phase 3.
- Workload (VM/VMSS/AKS) deployment against reservations — Phase 2+.
- Quota pooling automation (QUA-003/004/008/009) — parallel track, prerequisite only here.
- DR activation runbook (DR-005/006/009) — separate DR programme.
- IaC authoring (Bicep/Terraform) — follows plan approval (see §12 Next Steps).

---

## 2. Guiding Principles for the Build

These baseline rules constrain **how** we create resources and must hold at every step:

| # | Principle | Requirement | Build implication |
|---|-----------|-------------|-------------------|
| 1 | **Azure-first, then config** | CAP-002 | Create the CRG + reservation in Azure and validate it **before** activating it in deployment config / scope file. Never reference a reservation in config that does not yet exist in Azure. |
| 2 | **Seed at zero, never delete** | CAP-009, CAP-022 | Every eligible SKU/AZ is created as a reservation at **quantity 0**. Reaching 0 is normal; deletion is a governed decommission (CAP-010), never part of the build. |
| 3 | **Structural zone isolation** | CAP-011, CAP-023 | Zone isolation is enforced by **separate per-AZ CRGs**, not just accounting. One regional (non-zonal) CRG + one CRG per AZ, per environment. |
| 4 | **Environment separation** | ENV-003 | Prod ≠ non-prod, Prod ≠ DR (never share a CRG or subscription boundary). DR may co-locate/share with non-prod only where PLC-010 permits. |
| 5 | **Eligibility before onboarding** | CAP-020, CAP-021 | Only zonal-placed (or regional-only-where-SKU-lacks-zonal) resources are eligible. Availability-Set VMs are excluded and flagged for deallocate/redeploy. |
| 6 | **Deterministic naming** | OPS-006, C-12 | Every RG/CRG/subscription name is generated from tokens + zero-padded counter and validated against the convention; non-conforming names are governance exceptions. |
| 7 | **Budget-governed matrix** | CAP-022 | A SKU/AZ enters the seed matrix only with a named owning product team + approved budget line. Anything scaled above 0 incurs cost. |
| 8 | **Quota is parallel, validated not re-gated** | QUA-001, QUA-007, ADR-006 | Quota must be *present* in the deploying subscription (a build prerequisite we verify), but the build does not create quota gates — Azure enforces quota natively. |

---

## 3. Prerequisites — Pre-Flight Before Any Creation

**Nothing is created until every item below is confirmed.** (Aligns with the POC workbook Pre-Flight PF-01..PF-10.)

### 3.1 Identity, subscription & governance

| ID | Prerequisite | How verified | Requirement |
|----|--------------|--------------|-------------|
| PRE-01 | Target subscriptions exist and are named per convention (Prod / NonProd / DR per geography) | `az account list -o table`; name matches `sub-<org>-<domain>-<purpose>-<NN>` | OPS-006, ENV-003 |
| PRE-02 | Core subscription identified and flagged **all-production** | Scope-file entry; CAP-001a classification set | CAP-001a |
| PRE-03 | RBAC: build identity (UAMI/SPN) has least-privilege custom role at target RG/subscription scope | `az role assignment list --scope <SCOPE>` | GOV-*, security guide |
| PRE-04 | Resource groups created per convention (`rg-odcr-<env>-<region>-<NN>`) | `az group show`; name validated | OPS-006 |
| PRE-05 | Region catalogue configuration loaded (distribution model, zone support, `DR_NOT_OFFERED` flags) | `PlacementPolicy` config version pinned | REG-001, REG-003 |
| PRE-06 | Scope-file schema ready (tenant, sub, region, AZ, RG, CRG, reservation name, SKU/family, env, buffer, enabled, effective date/version) | Scope-file present + versioned | CAP-001, CAP-019 |

### 3.2 Capacity, quota & preview features

| ID | Prerequisite | How verified | Requirement |
|----|--------------|--------------|-------------|
| PRE-07 | **Quota present** in each deploying subscription for the target VM families/regions | `az vm list-usage --location <REGION>` ≥ planned seed+buffer intent | QUA-002, QUA-007 |
| PRE-08 | Zone support confirmed per SKU × region (which SKUs support zonal reservations) | `az vm list-skus --location <REGION> --zone` | CAP-011, CAP-023 |
| PRE-09 | **Capacity Reservation Sharing** preview feature registration state recorded (if sharing in scope) | `az feature show` — record as *Observed*, not SLA | CAP-013, preview risk |
| PRE-10 | **Quota Groups** preview state recorded (if pooling in scope) | `az feature show` — record as *Observed* | QUA-003, preview risk |
| PRE-11 | No name-colliding CRGs already present | `az capacity reservation group list -g <RG>` | OPS-006 |
| PRE-12 | Eligible-SKU/AZ matrix drafted with owning **product team + budget line** per entry | Seed-matrix config reviewed & approved | CAP-022 |

> **Blocker rule.** If PRE-07 (quota) fails for a target family/region, do **not** create above-zero reservations there — seed at 0 is still valid, but flag a quota readiness risk (QUA-007) and raise a quota request (QUA-010) before any scale-up.

---

## 4. Canonical Order of Operations (per environment × region)

This is the **repeatable creation sequence**. It is idempotent-friendly (re-running should not duplicate) and Azure-first (CAP-002).

```
FOR each (geography → environment → region) in the phased rollout:

  STEP 0  Pre-flight gate (Section 3) passes for this scope ............... GATE
  STEP 1  Set subscription context
            az account set --subscription <ENV_SUB>
  STEP 2  Ensure resource group (naming: rg-odcr-<env>-<region>-<NN>)
            az group create -n <RG> -l <REGION>            (if absent)
  STEP 3  Create the REGIONAL (non-zonal) CRG
            crg-<env>-<region>-reg
            az capacity reservation group create -g <RG> -n <CRG_REG> -l <REGION>
  STEP 4  Create one PER-AZ CRG for each supported zone
            crg-<env>-<region>-az1 / az2 / az3
            az capacity reservation group create -g <RG> -n <CRG_AZn> -l <REGION> --zones n
  STEP 5  For each eligible SKU in the seed matrix (CAP-022):
            5a  Zonal SKU  → create count-0 reservation in each per-AZ CRG
                  az capacity reservation create -g <RG> \
                    --capacity-reservation-group <CRG_AZn> \
                    --name <CR_NAME> --sku <SKU> --capacity 0 \
                    --location <REGION> --zone n
            5b  Non-zonal SKU → create count-0 reservation in the regional CRG
                  az capacity reservation create -g <RG> \
                    --capacity-reservation-group <CRG_REG> \
                    --name <CR_NAME> --sku <SKU> --capacity 0 --location <REGION>
  STEP 6  VALIDATE in Azure (Section 8 gates) ............................ GATE
            provisioningState=Succeeded; zones correct; capacity=0
  STEP 7  ONLY AFTER Azure validation passes → activate in scope file
            (write CRG + reservation entries, enabled=true, effective date/version)
  STEP 8  Record evidence (resource IDs, request IDs, timestamps) into build log
```

**Why this order:** STEP 7 (config activation) strictly follows STEP 6 (Azure validation) to honor CAP-002 — the deployment pipeline reads the scope file to decide reservation association, so a config entry must never point at a non-existent Azure object.

---

## 5. Naming Plan (OPS-006 / C-12)

All tokens resolved deterministically; counter is zero-padded (`C-12` width configurable).

| Resource | Pattern | Token meaning | Example |
|----------|---------|---------------|---------|
| Resource group | `rg-odcr-<env>-<region>-<NN>` | env ∈ {prod,cval,nonprod,dr}; region = short code; NN = instance counter | `rg-odcr-prod-eus2-01` |
| Regional CRG | `crg-<env>-<region>-reg` | scope `reg` = non-zonal SKUs | `crg-pr-eus2-reg` |
| Per-AZ CRG | `crg-<env>-<region>-az<n>` | scope `az1/az2/az3` = zone-bound | `crg-pr-eus2-az1` |
| Capacity Reservation | `res-<env>-<region>-<scope>-<SkuCompact>-<NNN>` | scope = reg/az1..; SkuCompact = SKU w/o punctuation | `res-pr-eus2-az1-StandardD16sv5-001` |
| Subscription | `sub-<org>-<domain>-<purpose>-<NN>` | purpose ∈ {core,app,nonprod,dr} | `sub-jda-cld-core-01` |

**Region short-code table (examples — driven by REG-001 config):**

| Region | Code | Region | Code |
|--------|------|--------|------|
| West US 3 | wus3 | Switzerland North | swn |
| Central US | cus | Sweden Central | sdc |
| Canada Central | cac | Australia East | aue |
| East US 2 | eus2 | Australia Southeast | ause |
| East Asia | ea | Southeast Asia | sea |
| Saudi Arabia Central | sac | UAE North | uan |

> **Reconciliation note.** The older POC workbook (`acrme_poc_workbook_v2_4.md`) shows a per-SKU CRG example (`crg-prod-<region>-<sku>`) that **predates CAP-023**. This plan follows the **authoritative v2.4 per-zone CRG structure** (one CRG per zone holding multiple SKUs), consistent with the deployment-layout reference. The engine validates managed resources against OPS-006 and flags non-conforming names as governance exceptions.

---

## 6. CRG Structure Plan (CAP-023)

Per **environment × region**, create exactly this set (assuming a 3-zone region):

```
<env> in <region>:
  ├── crg-<env>-<region>-reg   ← 1 regional CRG (non-zonal SKUs only)
  ├── crg-<env>-<region>-az1   ← 1 per-AZ CRG (zone 1)
  ├── crg-<env>-<region>-az2   ← 1 per-AZ CRG (zone 2)
  └── crg-<env>-<region>-az3   ← 1 per-AZ CRG (zone 3)
= 4 CRGs per environment per 3-zone region
```

- **Regional CRG** holds **only** SKUs that do not support zonal reservations (PRE-08 determines this per SKU).
- **Per-AZ CRGs** hold zone-bound reservations → structurally enforce CAP-011 (zone-1 capacity never counted elsewhere).
- **Environments are never mixed** in a CRG (ENV-003). Separate RGs and, where required, separate subscriptions per environment.
- Adjust CRG count for regions with fewer/more zones (e.g., a 2-zone region → reg + az1 + az2 = 3 CRGs).

---

## 7. Seed Matrix Plan (CAP-022, CAP-020/021)

### 7.1 What gets seeded

Every **eligible** SKU/family × region × AZ combination in the approved scope file is created as a **count-0 reservation** ("seed reservation") in the correct CRG, so reconciliation can scale it from a known baseline the instant demand appears (CAP-007).

### 7.2 Eligibility gate (create only if ALL true)

| Gate | Rule | Requirement |
|------|------|-------------|
| E1 | SKU × region combination is in the approved scope file | CAP-001, CAP-019 |
| E2 | Placement is **zonal** (per-AZ CRG) OR SKU has no zonal support → regional CRG only | CAP-011, CAP-023 |
| E3 | Target is **not** an Availability Set (mutually exclusive with reservations) | CAP-020 |
| E4 | Any existing VM to onboard is in an eligible placement, else record deallocate/redeploy-to-AZ action first | CAP-021 |
| E5 | Entry has a named owning **product team** + approved **budget line** | CAP-022 |

### 7.3 Seed-matrix worksheet (template — fill per region before build)

| CRG | Reservation Name | SKU | Zonal? | Initial Qty | Product Team | Budget Line | Eligibility (E1-E5) |
|-----|------------------|-----|--------|-------------|--------------|-------------|---------------------|
| crg-pr-eus2-az1 | res-pr-eus2-az1-StandardD16sv5-001 | Standard_D16s_v5 | Yes | 0 | Platform-Core | FY27-Q1-Compute-001 | ✅ |
| crg-pr-eus2-az2 | res-pr-eus2-az2-StandardD16sv5-001 | Standard_D16s_v5 | Yes | 0 | Platform-Core | FY27-Q1-Compute-001 | ✅ |
| crg-pr-eus2-az3 | res-pr-eus2-az3-StandardD16sv5-001 | Standard_D16s_v5 | Yes | 0 | Platform-Core | FY27-Q1-Compute-001 | ✅ |
| crg-pr-eus2-reg | res-pr-eus2-reg-StandardM128s-001 | Standard_M128s | No (regional) | 0 | Data-Services | FY27-Q1-Compute-002 | ✅ |
| ... | ... | ... | ... | 0 | ... | ... | ... |

### 7.4 Reactive discovery reconciled (CAP-024)

The build seeds the **known** matrix. When an allocated VM later appears for a SKU/AZ **not** yet seeded, the engine (downstream phase) auto-creates the CRG (if absent) + reservation at `allocated + buffer` **and** raises a scope-file governance item (CAP-019) to ratify it. This plan only needs to ensure the **naming + CRG structure rules are deterministic** so reactive creation slots in cleanly.

---

## 8. Validation Gates (post-creation, before config activation)

Run these after STEP 5 and before STEP 7, per resource:

| Gate | Check | Command / method | Pass criteria |
|------|-------|------------------|---------------|
| V1 | CRG provisioned | `az capacity reservation group show` | `provisioningState = Succeeded` |
| V2 | Zones correct | same `show -o json` | per-AZ CRG `zones` = [n]; regional CRG has none |
| V3 | Reservation provisioned | `az capacity reservation show` | `provisioningState = Succeeded` |
| V4 | Seed quantity is 0 | same `show` | `sku.capacity = 0` |
| V5 | SKU matches | same `show` | `sku.name = <SKU>` |
| V6 | Naming conforms | regex vs OPS-006 pattern | match; else governance exception |
| V7 | Environment isolation | RG/CRG env token vs subscription purpose | no cross-env mix (ENV-003) |
| V8 | Quota present for family/region | `az vm list-usage` | available ≥ planned scale-up intent (QUA-007) |
| V9 | Scope-file consistency | scope file vs Azure inventory | 1:1 after STEP 7 (CAP-019) |
| V10 | Evidence captured | build log | resource IDs + request IDs + timestamps recorded |

> A resource that fails any gate is **not** activated in the scope file (STEP 7 withheld) until remediated.

---

## 9. Full Build Inventory by Geography (phased)

Grounded in the deployment-layout reference and the region catalogue (REG-001). CRG counts assume 3-zone regions (adjust per actual zone support, PRE-08).

| Geography | Model | Environments to build | Regions | CRGs (per env × 4) | Notes |
|-----------|-------|-----------------------|---------|--------------------|-------|
| **US** | 3-region | Prod, CVAL, DR (distinct regions) | West US 3 / Central US / Canada Central | 12 total | Only geography with full 3-way region separation |
| **Europe** | 2-region | Prod; CVAL+DR co-located | Sweden Central (Prod) / Switzerland North (CVAL+DR) | 12 total (4 Prod + 4 CVAL + 4 DR; CVAL & DR share region, **separate subs/CRGs**) | Co-location mandatory (PLC-010a); `cval_region == dr_region` |
| **Australia** | 2-region | Prod; CVAL+DR co-located | Australia East (Prod) / Australia Southeast (CVAL+DR) | 12 total | Same co-location pattern as EU |
| **Asia Pacific** | 2-region | Prod; CVAL+DR co-located | East Asia (Prod) / Southeast Asia (CVAL+DR) | 12 total | Japan East pending (REG-001) — not built until confirmed |
| **Middle East** | **[Amended v2.4]** cross-geo DR | Prod+CVAL co-located in a weighted-selected ME region; DR cross-geo in a weighted-selected Europe region | 12 total (4 Prod + 4 CVAL in ME, **separate subs/CRGs**; 4 DR in Europe) | Cross-geo DR (PLC-010b, DR-020, DEC-001 RESOLVED); Prod+CVAL `region == ME region`, DR `region ∈ Europe`; Europe destination sizes DR max-not-sum (DR-017) |

> **Distribution-model reminder (memory-checked).** In EU/Australia/Asia Pacific, one region hosts **Prod** and the other hosts **CVAL + DR co-located** — DR **is** offered in-geo (PLC-010a). **[Amended v2.4]** The **Middle East** is the exception: Prod+CVAL co-locate in one ME region and **DR is built cross-geo in a weighted-selected Europe region** (PLC-010b, DR-020, DEC-001 RESOLVED) — build ME Prod+CVAL CRGs locally and DR CRGs in the selected Europe region. Do not skip DR CRGs for any geography.

---

## 10. Phased Rollout

| Phase | Scope | Exit criteria |
|-------|-------|---------------|
| **Phase 0 — Pre-flight** | All PRE-01..PRE-12 for pilot scope | Every prerequisite green for the pilot region |
| **Phase 1 — Pilot (single region, Prod)** | One geography, Prod env only, one region, small eligible SKU set — e.g. US Prod West US 3 | POC-01..POC-05 pass; V1..V10 pass; scope file consistent |
| **Phase 2 — Pilot environments complete** | Add CVAL + DR for the pilot geography (validates co-location for a 2-region geo, and 3-way separation for US) | Co-location accounting verified (HC-6/HC-7); ENV-003 isolation proven |
| **Phase 3 — Geography rollout** | Repeat Phases 1-2 per geography per the inventory (§9) | All in-scope geographies seeded + validated |
| **Phase 4 — Handoff to reconciliation** | Enable the reconciliation job to manage the seeded matrix (CAP-005/006) | Engine scales seeds from 0 on real demand; out of scope for *this* plan |

> **Start small:** Phase 1 deliberately limits to one region + Prod + a handful of SKUs so the order-of-operations, naming, and validation gates are proven before any fan-out.

---

## 11. Coverage Matrix — "Are We Covering Grounds?"

Every relevant creation-phase requirement mapped to a plan step and its validation. (Downstream-only requirements are marked as such.)

| Requirement | Covered by | Validated by |
|-------------|-----------|--------------|
| CAP-001 authoritative scope file | §3 PRE-06, §4 STEP 7 | V9 |
| CAP-001a core = all production | §3 PRE-02 | V7 |
| CAP-002 Azure-first then config | §4 STEP 6→7 ordering | V9 |
| CAP-009 zero-not-delete | §2 P2, §7.1 seed at 0 | V4 |
| CAP-011 zone isolation | §6 per-AZ CRGs | V2 |
| CAP-013/014/015 sharing | Prereq PRE-09 (build seeds structure; sharing enabled downstream) | PRE-09 recorded |
| CAP-016 pre-deploy validation | (downstream — deploy phase) | n/a this plan |
| CAP-019 scope-file governance | §4 STEP 7, §7.4 | V9 |
| CAP-020 Availability-Set ineligible | §7.2 E3 | E3 gate |
| CAP-021 deallocate/redeploy-to-AZ | §7.2 E4 | E4 gate |
| CAP-022 seed matrix + budget | §7 whole section | E5 gate, V4 |
| CAP-023 regional + per-AZ CRG | §6 structure | V1, V2 |
| CAP-024 reactive discovery | §7.4 (deterministic naming enables it) | V6 |
| ENV-003 environment separation | §6, §9 separate subs/RGs/CRGs | V7 |
| OPS-006 / C-12 naming | §5 naming plan | V6 |
| QUA-002/007 quota present | §3 PRE-07 | V8 |
| REG-001/003 catalogue + distribution | §3 PRE-05, §9 inventory | inventory review |
| PLC-010a co-location (2-region) | §9 notes | Phase 2 co-location check |
| **[Amended v2.4]** DEC-001 RESOLVED — Middle East cross-geo DR | §9 (ME Prod+CVAL local; DR CRGs in weighted Europe region) | inventory review |
| DR-003/004 lean DR (seed at 0/bootstrap) | §7.1 seed at 0 | V4 |
| HC-6/HC-7 co-location capacity floor | Phase 2 exit criteria | Phase 2 check |

---

## 12. Risks, Preview Dependencies & Out-of-Scope

### 12.1 Risks / dependencies
- **Preview features** (Capacity Reservation Sharing, Quota Groups) are **not** Microsoft contractual commitments — record observed behavior as *Observed*, not SLA (PRE-09/PRE-10). Sharing (Tier 2/3) build steps are gated on preview availability.
- **Quota absence** blocks above-zero scale-up (not seeding at 0). Raise quota requests (QUA-010) early for pilot families.
- **Zone support varies by SKU/region** (PRE-08) — a SKU without zonal reservation support must go in the regional CRG, not a per-AZ CRG; mis-placement fails V2.
- **Availability-Set legacy VMs** require deallocate/redeploy before onboarding (CAP-021) — service-impacting, owned by the workload team, not auto-migrated.

### 12.2 Explicitly out of scope for this plan
- Reconciliation automation / container-app job (CAP-005/006) — Phase 4.
- Workload deployment + reservation association (POC-03 onward is *validation*, not production deploy).
- Quota pooling/reclamation automation (QUA-003/004/008/009).
- DR declaration/activation runbook (DR-005/006/009).
- IaC authoring — see Next Steps.

---

## 13. Next Steps (after this plan is approved)

1. **Fill the seed-matrix worksheet** (§7.3) for the Phase 1 pilot region with real SKUs, product teams, and budget lines.
2. **Confirm pilot scope** — recommended: **US Prod, West US 3**, 3-5 eligible SKUs.
3. **Author IaC** (Bicep or Terraform) implementing §4 order-of-operations + §5 naming, or a scripted `az` runbook mirroring the POC workbook Group 1.
4. **Execute Phase 0 pre-flight** and record evidence.
5. **Run Phase 1** and capture V1..V10 results before any fan-out.

> Tell me which of steps 1-3 to start on and I'll produce it (e.g., the Bicep/Terraform module, the seed-matrix worksheet pre-filled for a chosen pilot region, or a scripted `az` build runbook).

---

## 14. Revision History

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 9 Sep 2026 | Initial CRG/CR foundation provisioning plan — order of operations, naming, CRG structure, seed matrix, eligibility gates, validation gates, phased rollout, coverage matrix. Reconciled to baseline v2.4. |

---

*End of document.*
