# Azure Capacity Reservation Management Engine — Proof of Concept Test Workbook

**Classification:** Principal Architect — Engineering Validation  
**Feature:** Azure Capacity Reservation Management Engine (ACRME) — Sharing, Quota Groups, Placement Engine, Emergency Transfer (Public Preview dependencies)  
**API Version:** `2024-03-01`  
**Date:** August 2026  
**Source Basis:** Azure CR Sharing Research Document (`azure_cr_sharing_research.md`) and Multi-Region Placement Design (`multi_region_placement_design.md` — final architecture, Pass 3 complete). The CR Sharing Research remains the supplementary basis for Sections 1–6; the Multi-Region Placement Design is the primary basis for Sections 7–10.  
**Status:** `[Draft — Pending Engineering Execution]`

> **Preview Notice:** Sections 1–6 target the Azure Capacity Reservation Sharing feature in **Public Preview** — behaviors may change without notice and no SLA applies to the sharing feature itself. Section 7 (Quota Group Management) depends on the `Microsoft.Quota/groupQuotas` **preview** API, whose GA availability is tracked as Blocker B-1 (validated by POC-30). Sections 8–10 validate **ACRME engine** behavior (Placement Engine, Steady State lifecycle, Emergency Capacity Transfer) layered on top of these preview APIs and require the engine to be deployed. All results should be treated as empirical observations against the preview API surface and engine build under test, not production commitments.

---

## Table of Contents

- [POC Environment Blueprint](#poc-environment-blueprint)
- [Global Prerequisites](#global-prerequisites)
- [Section 1 — Cross-Subscription Sharing](#section-1--cross-subscription-sharing)
- [Section 2 — Quota Interaction](#section-2--quota-interaction)
- [Section 3 — Shared Capacity Consumption](#section-3--shared-capacity-consumption)
- [Section 4 — VM Associate and Disassociate Behaviour](#section-4--vm-associate-and-disassociate-behaviour) — POC-11 to POC-16
- [Section 5 — Availability Zone Requirements](#section-5--availability-zone-requirements) — POC-20 to POC-22
- [Section 6 — DR Failover Scenarios](#section-6--disaster-recovery-failover-scenarios) — POC-23 to POC-29
- [Section 7 — Quota Group Management (Two-Group Model)](#section-7--quota-group-management-two-group-model) — POC-30 to POC-33
- [Section 8 — Placement Engine Validation](#section-8--placement-engine-validation) — POC-34 to POC-41
- [Section 9 — Steady State Capacity Lifecycle](#section-9--steady-state-capacity-lifecycle) — POC-42 to POC-45
- [Section 10 — Emergency Capacity Transfer](#section-10--emergency-capacity-transfer) — POC-46 to POC-51
- [Appendix A — Test Execution Log Template](#appendix-a--test-execution-log-template)
- [Appendix B — Resource Cleanup Procedure](#appendix-b--resource-cleanup-procedure)
- [Appendix C — Azure CLI Reference Commands](#appendix-c--azure-cli-reference-commands)
- [Appendix D — Test Case Index](#appendix-d--test-case-index)
- [Appendix E — Blocker Resolution Map](#appendix-e--blocker-resolution-map)
- [Appendix F — Engineering Story POC Coverage](#appendix-f--engineering-story-poc-coverage)

---

## POC Environment Blueprint

### Subscription Topology

```
TENANT: contoso.onmicrosoft.com (POC Tenant — Isolated)
│
├── SUBSCRIPTION: poc-provider-sub
│   Purpose: Capacity Reservation Group owner
│   Role: Provider
│   Location: East US 2
│   Microsoft.Compute: Registered
│   Features: Microsoft.Resources/AvailabilityZonePeering (register before Section 5)
│
├── SUBSCRIPTION: poc-consumer-a-sub
│   Purpose: Primary workload consumer — Zone mapping validated
│   Role: Consumer (Primary)
│   Location: East US 2
│   Microsoft.Compute: Registered
│   Features: Microsoft.Resources/AvailabilityZonePeering (register before Section 5)
│
├── SUBSCRIPTION: poc-consumer-b-sub
│   Purpose: Secondary workload consumer — Zone mapping mismatch testing
│   Role: Consumer (Secondary / Mismatch Validation)
│   Location: East US 2
│   Microsoft.Compute: Registered
│
├── SUBSCRIPTION: poc-dr-sub
│   Purpose: Disaster Recovery target subscription
│   Role: Consumer (DR)
│   Location: East US 2 (primary) / West US 2 (failover)
│   Microsoft.Compute: Registered
│
├── SUBSCRIPTION: poc-noshare-sub
│   Purpose: Negative testing — not in any sharing profile
│   Role: Unauthorized Consumer (negative test only)
│   Location: East US 2
│   Microsoft.Compute: Registered
│
└── SUBSCRIPTION: poc-nonprod-sub
    Purpose: NonProd workload tests for Steady State (Section 9) and Emergency Transfer (Section 10 — Tier 2/3 NonProd CRG reduction)
    Role: Consumer (NonProd / NonProdDR quota group)
    Location: East US 2 (primary) / West US 2 / Central US (simulated managed regions for Section 8)
    Microsoft.Compute: Registered
    Features: Microsoft.Quota (register before Section 7)
```

> **Multi-Region Topology Note (Sections 8–10):** The Placement Engine tests (Section 8) require **at least 3 managed regions** configured in the ACRME engine. In the POC these are simulated using distinct CRGs per region following the `crg-poc-<purpose>-<region>` naming convention (e.g. `crg-poc-prod-eus2`, `crg-poc-nonprod-wus2`, `crg-poc-dr-cus`). Region identifiers used throughout Sections 8–10: `eastus2` (R1), `westus2` (R2), `centralus` (R3), and `southcentralus` (R4) for the 4-region test (POC-41). No cross-region Azure networking is required — the engine's RegionalSnapshot cache and Cosmos DB entities model the regions; the CRGs provide the ARM-observable capacity state.

### Resource Naming Convention

| Resource Type | Naming Pattern | Example |
|---|---|---|
| Capacity Reservation Group | `crg-poc-<purpose>-<region>` | `crg-poc-primary-eus2` |
| Capacity Reservation | `cr-poc-<sku-abbrev>-<zone>` | `cr-poc-d16sv3-z1` |
| Resource Group (Provider) | `rg-poc-capacity-<region>` | `rg-poc-capacity-eus2` |
| Resource Group (Consumer) | `rg-poc-workload-<consumer>` | `rg-poc-workload-cons-a` |
| Virtual Machine | `vm-poc-<consumer>-<seq>` | `vm-poc-cons-a-01` |
| Virtual Machine Scale Set | `vmss-poc-<consumer>-<purpose>` | `vmss-poc-cons-a-web` |
| Service Principal | `sp-poc-provider-identity` | — |
| Quota Group | `qg-poc-<type>-<region>` | `qg-poc-prod-eus2`, `qg-poc-nonproddr-eus2` |
| CapacityIncreaseRequest log | `cir-poc-<region>-<crgtype>-<seq>` | `cir-poc-eus2-dr-01` |
| engine_mode state log | `enginemode-poc-<incident_id>` | `enginemode-poc-inc-001` |

### VM SKU Selection

`[POC Note]` Select a **low-cost VM SKU** available in East US 2 with zonal support. Recommended for POC: `Standard_D2s_v3` or `Standard_D4s_v3`. Validate SKU availability in East US 2 Zone 1, Zone 2, and Zone 3 before beginning. Adjust all test cases if a different SKU is used.

```bash
az vm list-skus --location eastus2 --size Standard_D4s_v3 \
  --query "[].{Name:name, Zones:locationInfo[0].zones}" \
  --output table
```

### Quota Requirements

| Subscription | Minimum Quota (vCPUs) | Purpose |
|---|---|---|
| poc-provider-sub | 32 vCPUs (Standard DSv3) | CR creation (quantity × 4 vCPU per D4s_v3) |
| poc-consumer-a-sub | 16 vCPUs (Standard DSv3) | Consumer VM deployments |
| poc-consumer-b-sub | 8 vCPUs (Standard DSv3) | Zone mismatch tests |
| poc-dr-sub | 16 vCPUs (Standard DSv3) | DR failover tests |
| poc-noshare-sub | 4 vCPUs (Standard DSv3) | Negative test only |
| poc-nonprod-sub | 32 vCPUs (Standard DSv3) | NonProd workloads (Section 9) + Tier 2/3 NonProd CRG (Section 10) |

#### Quota Group Budget Requirements (Sections 7–10)

The Two-Group Quota Architecture requires two `Microsoft.Quota/groupQuotas` groups provisioned per managed region. The following per-region group budgets are the POC minimums:

| Quota Group | Group Limit (vCPUs) | Purpose |
|---|---|---|
| `qg-poc-prod-<region>` (Prod group) | 128 vCPUs (Standard DSv3) | Prod CRGs + Prod placement headroom (HC-3 Prod quota floor) |
| `qg-poc-nonproddr-<region>` (NonProdDR group) | 80 vCPUs (Standard DSv3) | NonProd + DR CRGs + emergency transfer headroom (Tier 1/2 source pool) |

`[Pre-POC Action]` Validate quotas in all subscriptions before test execution. Request increases if required — quota increases may take 24–72 hours. Quota Group provisioning requires `Microsoft.Quota` registered on `poc-nonprod-sub` and the provider subscription (see GP-06).

---

## Global Prerequisites

The following prerequisites apply to the entire POC. They must be completed before any individual test section is executed.

### GP-01 — Subscription Registration

Execute from each POC subscription:

```bash
az provider register --namespace Microsoft.Compute
az provider show --namespace Microsoft.Compute --query "registrationState"
# Wait for: "Registered"
```

### GP-02 — Resource Group Creation

```bash
# Provider subscription
az group create --name rg-poc-capacity-eus2 \
  --location eastus2 \
  --subscription poc-provider-sub

# Consumer A
az group create --name rg-poc-workload-cons-a \
  --location eastus2 \
  --subscription poc-consumer-a-sub

# Consumer B
az group create --name rg-poc-workload-cons-b \
  --location eastus2 \
  --subscription poc-consumer-b-sub

# DR
az group create --name rg-poc-workload-dr \
  --location eastus2 \
  --subscription poc-dr-sub
```

### GP-03 — Service Principal Creation (Provider Identity)

```bash
az ad sp create-for-rbac \
  --name sp-poc-provider-identity \
  --role Contributor \
  --scopes /subscriptions/<poc-provider-sub-id>/resourceGroups/rg-poc-capacity-eus2
# Record: appId, tenant, password
```

### GP-04 — Availability Zone Mapping Discovery

Before executing Section 5 (AZ tests), collect zone mappings from all subscriptions:

```bash
# Run once per subscription — record output for each
az account list-locations \
  --query "[?name=='eastus2'].availabilityZoneMappings" \
  --subscription <sub-id>
```

Document the logical-to-physical zone mapping table for all five subscriptions. This table is used in every AZ-related test.

### GP-05 — API Version Verification

All ARM REST calls in this workbook use `api-version=2024-03-01`. Verify that this API version is available:

```bash
az provider show --namespace Microsoft.Compute \
  --query "resourceTypes[?resourceType=='capacityReservationGroups'].apiVersions"
```

Confirm `2024-03-01` appears in the output.

### GP-06 — Quota Group Prerequisites (Required for Sections 7 and 8)

`[Pre-Section 7 Action]` The following prerequisites apply to Section 7 (Quota Group Management) and also gate Section 8 (Placement Engine Validation) — the RegionalSnapshot data pipeline tests (POC-34 onward) require Quota Group data to be populated. Complete before executing POC-30 through POC-33, and before any Section 8 test.

**Step 1 — Register Microsoft.Quota provider in all POC subscriptions:**

```bash
# Run in each POC subscription
for sub in poc-provider-sub poc-consumer-a-sub poc-dr-sub; do
  az provider register --namespace Microsoft.Quota --subscription $sub
  az provider show --namespace Microsoft.Quota \
    --query "registrationState" --subscription $sub
  # Wait for: "Registered"
done
```

**Step 2 — Confirm Quota Group API availability in East US 2:**

```bash
# Check groupQuotas resource type is available
az provider show --namespace Microsoft.Quota \
  --query "resourceTypes[?resourceType=='groupQuotas']"
# Expected: resourceType present with apiVersions list
# If absent: Quota Groups are not GA in this region — POC-30 will fail; document and escalate
```

**Step 3 — Record Two-Group topology for POC subscriptions:**

The POC environment maps to the production two-group model as follows:

```
PROD QUOTA GROUP (East US 2):
  Member: poc-provider-sub
  Backs:  crg-poc-primary-eus2 (Prod CRG in production terms)
  Target limit: 128 vCPU (32 × D4s_v3 @ 4vCPU each)

NONPROD+DR QUOTA GROUP (East US 2):
  Members: poc-consumer-a-sub (NonProd role) + poc-dr-sub (DR role)
  Backs:   Consumer-A CRG (NonProd) + DR CRG from Section 6
  Target limit: 80 vCPU (20 × D4s_v3: 12 NonProd + 8 DR base)
  DR floor: 32 vCPU (8 × 4vCPU — equivalent to 40% DR ratio on 20 Prod VMs)
  Effective NonProd ceiling: 80 - 32 = 48 vCPU
```

**Step 4 — Install Quota extension if needed:**

```bash
az extension add --name quota
az extension show --name quota --query "version"
# Required for: az quota group create / az quota group show commands
```

**Step 5 — Tenant ID required for group quota ARM calls:**

```bash
az account show --query "tenantId" -o tsv
# Record: <TENANT_ID> — required for groupQuotas ARM resource path
```

`[Warning]` Quota Group creation requires **Management Group scope** or **Tenant-level scope** in some configurations. Validate that the POC tenant allows group quota creation at subscription level before executing POC-30. If tenant-level scope is required, a Global Admin or Billing Account Admin role assignment is needed.

---

## Section 1 — Cross-Subscription Sharing

**Section Objective:** Validate that the three-step sharing setup process functions correctly, that Consumers gain access to capacity only after correct setup, and that access boundaries (unauthorized subscriptions, 100-sub limit) are enforced.

**Facts Basis:** Research Section 1.2 (three-step setup), Section 1.3 (ARM model), Section 2.2 (subscription scope), Section 5.7 (pre-sharing access restriction).

---

### POC-01 — Provider CRG Creation and Sharing Profile Configuration

**Objective:** Validate that a Provider can create a CRG, create a Capacity Reservation within it, and configure a sharing profile that grants Consumer-A access. Confirm the `sharingProfile.subscriptionIds` property is correctly persisted and readable at `api-version=2024-03-01`.

**Azure Resources Required:**

| Resource | Subscription | Details |
|---|---|---|
| Resource Group | poc-provider-sub | `rg-poc-capacity-eus2` |
| Capacity Reservation Group | poc-provider-sub | `crg-poc-primary-eus2` — East US 2 — Zones: [1, 2] |
| Capacity Reservation | poc-provider-sub | `cr-poc-d4sv3-z1` — Zone 1 — Quantity: 4 — SKU: Standard_D4s_v3 |

**Subscription Layout:**

```
poc-provider-sub
└── rg-poc-capacity-eus2
    └── crg-poc-primary-eus2
        └── cr-poc-d4sv3-z1  [quantity=4, zone=1]
poc-consumer-a-sub  [target of sharing profile — Step 2]
```

**Preconditions:**

- GP-01 through GP-03 complete
- `poc-provider-sub` has minimum 16 vCPU quota (Standard DSv3) in East US 2
- `poc-consumer-a-sub` subscription ID recorded
- Service principal `sp-poc-provider-identity` created

**Execution Steps:**

```
Step 1 — Create CRG
  az capacity reservation group create \
    --name crg-poc-primary-eus2 \
    --resource-group rg-poc-capacity-eus2 \
    --location eastus2 \
    --zones 1 2 3 \
    --subscription poc-provider-sub

Step 2 — Create CR inside CRG
  az capacity reservation create \
    --capacity-reservation-group-name crg-poc-primary-eus2 \
    --name cr-poc-d4sv3-z1 \
    --resource-group rg-poc-capacity-eus2 \
    --location eastus2 \
    --sku Standard_D4s_v3 \
    --capacity 4 \
    --zone 1 \
    --subscription poc-provider-sub

Step 3 — Add Consumer-A to sharing profile (Step 2 of RBAC process)
  az rest --method put \
    --uri "https://management.azure.com/subscriptions/<provider-sub-id>/
           resourceGroups/rg-poc-capacity-eus2/providers/
           Microsoft.Compute/capacityReservationGroups/
           crg-poc-primary-eus2?api-version=2024-03-01" \
    --body '{
      "location": "eastus2",
      "zones": ["1","2","3"],
      "properties": {
        "sharingProfile": {
          "subscriptionIds": [
            {"id": "/subscriptions/<consumer-a-sub-id>"}
          ]
        }
      }
    }'

Step 4 — Verify sharing profile persisted
  az rest --method get \
    --uri "https://management.azure.com/subscriptions/<provider-sub-id>/
           resourceGroups/rg-poc-capacity-eus2/providers/
           Microsoft.Compute/capacityReservationGroups/
           crg-poc-primary-eus2?api-version=2024-03-01"

Step 5 — Grant Consumer-A RBAC on Provider CRG (Step 3 of RBAC process)
  az role assignment create \
    --role "Reader" \
    --assignee <consumer-a-sp-or-identity> \
    --scope /subscriptions/<provider-sub-id>/resourceGroups/
            rg-poc-capacity-eus2/providers/
            Microsoft.Compute/capacityReservationGroups/crg-poc-primary-eus2

  # Grant deploy/action via custom role or built-in if applicable
  # Document: custom role definition required for deploy/action

Step 6 — Consumer-A grants Provider deploy/action on Consumer scope (Step 1 of RBAC process)
  az role assignment create \
    --role "Virtual Machine Contributor" \
    --assignee <sp-poc-provider-identity-app-id> \
    --scope /subscriptions/<consumer-a-sub-id>
```

**Expected Results:**

- CRG created with `zones: [1, 2, 3]`
- CR created with `sku: Standard_D4s_v3`, `capacity: 4`, `zone: 1`
- GET on CRG returns `properties.sharingProfile.subscriptionIds` containing Consumer-A subscription resource ID
- Both RBAC assignments created without error
- CR status shows `provisioningState: Succeeded`
- CR allocated count = 0 (no VMs yet)

**Validation Criteria:**

```
✓ CRG GET response includes sharingProfile.subscriptionIds[0].id == 
  "/subscriptions/<consumer-a-sub-id>"
✓ CR provisioningState == "Succeeded"
✓ CR instanceView shows reservedResourceType correct SKU
✓ CR quantity == 4, allocated == 0
✓ Both RBAC assignments visible in IAM blade / az role assignment list
✓ api-version=2024-03-01 accepted without 400 error
```

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| API version `2024-03-01` not available in region | Low | High | Verify via GP-05 before test execution |
| SKU not available in East US 2 Zone 1 | Medium | High | Run SKU availability check (GP note) |
| Custom role required for `deploy/action` | High | Medium | Pre-create custom role definition before Step 5 |
| Provider quota insufficient | Medium | High | Validate quota pre-POC; request increase 24–72h ahead |

---

### POC-02 — Consumer VM Deployment Against Shared CRG (Happy Path)

**Objective:** Validate that a Consumer subscription correctly authorized via the sharing profile can deploy a VM against the shared CRG, that the CR allocated count increments, and that the VM runs with the expected CRG association.

**Azure Resources Required:**

| Resource | Subscription | Details |
|---|---|---|
| Virtual Machine | poc-consumer-a-sub | `vm-poc-cons-a-01` — Standard_D4s_v3 — Zone matching CR zone |
| Resource Group | poc-consumer-a-sub | `rg-poc-workload-cons-a` |
| Shared CRG (pre-existing) | poc-provider-sub | `crg-poc-primary-eus2` from POC-01 |

**Subscription Layout:**

```
poc-provider-sub
└── crg-poc-primary-eus2
    └── cr-poc-d4sv3-z1  [quantity=4, allocated=0 before test]

poc-consumer-a-sub
└── rg-poc-workload-cons-a
    └── vm-poc-cons-a-01  [references cross-sub CRG]
```

**Preconditions:**

- POC-01 complete and validated
- Consumer-A has quota for Standard_D4s_v3 in East US 2 (minimum 4 vCPUs)
- Zone mapping for Consumer-A resolved (identify which Consumer-A logical zone maps to same physical zone as Provider Zone 1 — see GP-04)
- RBAC setup complete (all three steps from POC-01)

**Execution Steps:**

```
Step 1 — Confirm Consumer-A zone that maps to Provider Zone 1 physical zone
  [Use zone mapping table from GP-04]
  Record: Consumer-A logical zone = <X> maps to same physical zone as Provider logical zone 1

Step 2 — Deploy VM from Consumer-A targeting shared CRG
  az vm create \
    --name vm-poc-cons-a-01 \
    --resource-group rg-poc-workload-cons-a \
    --image Ubuntu2204 \
    --size Standard_D4s_v3 \
    --zone <consumer-a-correct-logical-zone> \
    --capacity-reservation-group \
      /subscriptions/<provider-sub-id>/resourceGroups/
      rg-poc-capacity-eus2/providers/
      Microsoft.Compute/capacityReservationGroups/crg-poc-primary-eus2 \
    --subscription poc-consumer-a-sub \
    --admin-username azurepocadmin \
    --generate-ssh-keys

Step 3 — Verify VM deployed successfully
  az vm show \
    --name vm-poc-cons-a-01 \
    --resource-group rg-poc-workload-cons-a \
    --subscription poc-consumer-a-sub \
    --query "properties.capacityReservationGroup"

Step 4 — Verify CR allocated count incremented
  az rest --method get \
    --uri "https://management.azure.com/subscriptions/<provider-sub-id>/
           resourceGroups/rg-poc-capacity-eus2/providers/
           Microsoft.Compute/capacityReservationGroups/
           crg-poc-primary-eus2/capacityReservations/
           cr-poc-d4sv3-z1?api-version=2024-03-01&$expand=instanceView"
  # Inspect: instanceView.utilizationInfo.virtualMachinesAllocated

Step 5 — Deploy a second Consumer-A VM to confirm multi-VM allocation
  Repeat Step 2 for vm-poc-cons-a-02; verify CR allocated == 2
```

**Expected Results:**

- VM creates and enters `Running` state without error
- `vm.properties.capacityReservationGroup.id` references the Provider CRG resource ID
- CR `instanceView.utilizationInfo.virtualMachinesAllocated` count increases by 1 per VM deployed
- VM billing meter appears in Consumer-A subscription
- Reservation fee billing remains in Provider subscription

**Validation Criteria:**

```
✓ VM power state == "VM running"
✓ vm.properties.capacityReservationGroup.id == 
  "/subscriptions/<provider-sub-id>/.../crg-poc-primary-eus2"
✓ CR allocated count == 2 after two VM deployments
✓ CR quantity (4) > allocated (2) — capacity available state
✓ No quota error returned during deployment
✓ Cross-subscription CRG reference accepted by ARM
```

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Zone mapping incorrect — wrong physical zone targeted | High | High | Complete GP-04 zone mapping table before this test; use Check Zone Peers API (POC-20) |
| Consumer RBAC insufficient — Step 3 permissions missing | Medium | High | Audit role assignments before VM deployment |
| Consumer quota insufficient | Medium | High | Pre-validate quota; request increase if needed |
| ARM cross-subscription reference rejected | Low | High | Confirm `api-version=2024-03-01` and sharing profile populated |

---

### POC-03 — Unauthorized Consumer Rejection

**Objective:** Validate that a subscription NOT included in the sharing profile cannot reference the shared CRG in a VM deployment. Confirm the authorization failure mechanism and error message.

**Azure Resources Required:**

| Resource | Subscription | Details |
|---|---|---|
| Virtual Machine (attempt only) | poc-noshare-sub | `vm-poc-noshare-01` — Standard_D4s_v3 |
| Shared CRG (pre-existing) | poc-provider-sub | `crg-poc-primary-eus2` — poc-noshare-sub NOT in sharingProfile |

**Subscription Layout:**

```
poc-provider-sub
└── crg-poc-primary-eus2
    sharingProfile: [consumer-a-sub-id]  ← poc-noshare-sub absent

poc-noshare-sub
└── rg-poc-workload-noshare  [create for this test]
    └── vm-poc-noshare-01  [deployment attempt — expected to fail]
```

**Preconditions:**

- POC-01 complete
- `poc-noshare-sub` confirmed absent from `crg-poc-primary-eus2` sharingProfile
- `poc-noshare-sub` has basic quota (4 vCPUs) in East US 2

**Execution Steps:**

```
Step 1 — Confirm poc-noshare-sub is not in sharing profile
  GET crg-poc-primary-eus2 at api-version=2024-03-01
  Assert sharingProfile.subscriptionIds does NOT include poc-noshare-sub-id

Step 2 — Create resource group in poc-noshare-sub
  az group create --name rg-poc-workload-noshare \
    --location eastus2 --subscription poc-noshare-sub

Step 3 — Attempt VM deployment from poc-noshare-sub referencing Provider CRG
  az vm create \
    --name vm-poc-noshare-01 \
    --resource-group rg-poc-workload-noshare \
    --image Ubuntu2204 \
    --size Standard_D4s_v3 \
    --zone 1 \
    --capacity-reservation-group \
      /subscriptions/<provider-sub-id>/resourceGroups/
      rg-poc-capacity-eus2/providers/
      Microsoft.Compute/capacityReservationGroups/crg-poc-primary-eus2 \
    --subscription poc-noshare-sub \
    --admin-username azurepocadmin \
    --generate-ssh-keys

Step 4 — Capture full error response
  Record: HTTP status code, error code, error message

Step 5 — Add poc-noshare-sub to sharing profile temporarily
  [Update sharingProfile to include poc-noshare-sub]

Step 6 — Retry VM deployment from poc-noshare-sub
  Repeat Step 3 (with zone mapping correction if needed)
  Confirm VM deploys successfully once authorized

Step 7 — Remove poc-noshare-sub from sharing profile
  [Update sharingProfile to remove poc-noshare-sub; restore to original state]
```

**Expected Results:**

- Step 3: Deployment fails with an authorization/access error
- Error message references either: unauthorized access to cross-subscription resource, CRG not found, or insufficient permissions on `Microsoft.Compute/capacityReservationGroups`
- After Step 5 (temporary add): VM deploys successfully, confirming the error was access-based not configuration-based
- After Step 7: sharingProfile restored to Consumer-A only

**Validation Criteria:**

```
✓ Step 3 returns non-2xx HTTP response (400 or 403 expected)
✓ Error body recorded and classified (authorization vs. validation error)
✓ Step 6 VM deployment succeeds — confirms authorization was the blocker
✓ CR allocated count correct after successful Step 6 deployment
✓ Step 7 sharing profile correctly reverted
```

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Error message too generic to confirm root cause | Medium | Low | Cross-reference Activity Log for full error detail |
| Temporary addition in Step 5 not reverted | Low | Medium | Execute Step 7 immediately; confirm via GET before leaving test |
| poc-noshare-sub lacks zone quota for confirmation test | Low | Low | Add quota only if Step 6 confirmation is required |

---

### POC-04 — Sharing Profile Modification — Add and Remove Consumer

**Objective:** Validate that the Provider can dynamically add and remove Consumer subscriptions from an active sharing profile, that changes take effect without CRG or CR restart, and that Consumer access is revoked immediately upon removal.

**Azure Resources Required:**

| Resource | Subscription | Details |
|---|---|---|
| Shared CRG (pre-existing) | poc-provider-sub | `crg-poc-primary-eus2` |
| VM (running) | poc-consumer-a-sub | `vm-poc-cons-a-01` from POC-02 |

**Preconditions:**

- POC-01 and POC-02 complete
- `vm-poc-cons-a-01` running and associated with shared CRG
- `poc-consumer-b-sub` subscription ID recorded

**Execution Steps:**

```
Step 1 — Record current sharing profile state
  GET crg-poc-primary-eus2; record sharingProfile contents

Step 2 — Add Consumer-B to sharing profile (alongside existing Consumer-A)
  PUT crg with sharingProfile.subscriptionIds = [consumer-a-sub, consumer-b-sub]

Step 3 — Verify both consumers in profile
  GET crg; assert both subscription IDs present

Step 4 — Consumer-B deploys VM against shared CRG (confirm access granted)
  [Zone mapping for Consumer-B required — see GP-04]
  Deploy vm-poc-cons-b-01 from poc-consumer-b-sub

Step 5 — Remove Consumer-B from sharing profile (leave Consumer-A)
  PUT crg with sharingProfile.subscriptionIds = [consumer-a-sub]

Step 6 — Verify Consumer-B removed from profile
  GET crg; assert only consumer-a-sub-id in sharingProfile

Step 7 — Consumer-B attempts new VM deployment after removal
  Attempt to deploy vm-poc-cons-b-02
  Expected: authorization failure

Step 8 — Verify Consumer-B existing VM (vm-poc-cons-b-01) continues running
  az vm show vm-poc-cons-b-01 — confirm still Running
  Check CR allocated count (should still include Consumer-B VM)
```

**Expected Results:**

- Sharing profile update (add/remove) succeeds without CR or CRG restart
- Consumer-B gains access immediately after Step 2
- Consumer-B loses access to new deployments immediately after Step 5
- Consumer-B existing VM continues running after removal (SLA maintained)
- CR allocated count remains unchanged after profile modification

**Validation Criteria:**

```
✓ Step 2 PUT returns 200/201; sharingProfile updated
✓ Consumer-B VM deploys successfully at Step 4
✓ Step 5 PUT returns 200/201; Consumer-B removed from sharingProfile
✓ Step 7 deployment fails with authorization error (same as POC-03)
✓ Consumer-B existing VM power state == "VM running" after removal
✓ CR allocated count == (Consumer-A VMs + Consumer-B VMs) — unchanged by profile modification
```

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Zone mapping for Consumer-B not resolved — Step 4 fails on zone mismatch | High | Medium | Complete GP-04 for Consumer-B; if zone mapping not resolved, skip Step 4 and use negative test only |
| sharingProfile PUT overwrites existing entries if array not complete | Medium | High | Always read current sharingProfile before PUT; merge arrays client-side |
| Consumer-B VM not cleaning up after test | Low | Low | Ensure cleanup procedure followed (Appendix B) |

---

## Section 2 — Quota Interaction

**Section Objective:** Validate the dual-quota model — Provider quota governs CR creation, Consumer quota independently governs VM deployment. Validate that Consumer quota failure blocks VM deployment even when shared capacity is available.

**Facts Basis:** Research Section 3.1 (ownership model), Section 3.2 (billing model), Section 5.1 (Provider quota failure), Section 5.2 (Consumer quota failure).

---

### POC-05 — Provider Quota Enforcement at CR Creation

**Objective:** Validate that CR creation fails entirely when the Provider subscription lacks sufficient quota. Validate the error type (quota vs. capacity), HTTP status code, and error message content.

**Azure Resources Required:**

| Resource | Subscription | Details |
|---|---|---|
| Capacity Reservation Group (new) | poc-provider-sub | `crg-poc-quotatest-eus2` |
| Capacity Reservation (attempt) | poc-provider-sub | `cr-poc-overlimit` — quantity set to exceed Provider quota |

**Preconditions:**

- Current Provider quota for Standard_D4s_v3 in East US 2 known (e.g., 32 vCPUs)
- A CR quantity that would exceed quota prepared (e.g., if quota=32 vCPUs, request quantity=10 × 4 vCPU = 40 vCPUs)
- `[Warning]` Do not make real quota increase requests during this test — the goal is to observe failure at the current quota limit

**Execution Steps:**

```
Step 1 — Record current Provider quota for Standard_D4s_v3 in East US 2
  az vm list-usage --location eastus2 \
    --query "[?name.value=='standardDSv3Family']" \
    --subscription poc-provider-sub

Step 2 — Calculate quantity that would exceed quota
  quota_limit = <current_limit_from_step_1>
  current_usage = <current_usage_from_step_1>
  available_quota = quota_limit - current_usage
  over_quota_quantity = (available_quota / 4) + 2  
  # +2 VMs beyond what quota allows (at 4 vCPU per D4s_v3)

Step 3 — Create test CRG for quota test
  az capacity reservation group create \
    --name crg-poc-quotatest-eus2 \
    --resource-group rg-poc-capacity-eus2 \
    --location eastus2 \
    --zones 1 \
    --subscription poc-provider-sub

Step 4 — Attempt CR creation with over-quota quantity
  az capacity reservation create \
    --capacity-reservation-group-name crg-poc-quotatest-eus2 \
    --name cr-poc-overlimit \
    --resource-group rg-poc-capacity-eus2 \
    --location eastus2 \
    --sku Standard_D4s_v3 \
    --capacity <over_quota_quantity> \
    --zone 1 \
    --subscription poc-provider-sub

Step 5 — Capture full error response
  Record: HTTP status code, error.code, error.message, error.details

Step 6 — Create within-quota CR
  az capacity reservation create \
    --capacity-reservation-group-name crg-poc-quotatest-eus2 \
    --name cr-poc-withinlimit \
    --resource-group rg-poc-capacity-eus2 \
    --location eastus2 \
    --sku Standard_D4s_v3 \
    --capacity <within_quota_quantity> \
    --zone 1 \
    --subscription poc-provider-sub

Step 7 — Verify within-quota CR created successfully
  Confirm provisioningState == Succeeded
```

**Expected Results:**

- Step 4 fails entirely — no partial CR created
- Error is quota-related (QuotaExceeded or similar), NOT capacity-related
- Within-quota CR (Step 6) succeeds
- HTTP status on failure: 400 or 409

**Validation Criteria:**

```
✓ Step 4 returns non-2xx response
✓ Error code is quota-related (record exact code for documentation)
✓ No CR resource created after Step 4 failure (GET confirms no cr-poc-overlimit resource)
✓ Step 6 CR provisioningState == "Succeeded"
✓ Quota error message text recorded verbatim for runbook documentation
```

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Provider already has large quota — difficult to exceed | Medium | Low | Use a less common SKU with lower quota for this test specifically |
| Quota error and capacity error have identical messages | Medium | Medium | Validate by comparing error code between quota failure and physical capacity failure tests |
| CR creation succeeds partially then rolls back | Low | Medium | Monitor provisioning state over 5-minute window before declaring failure |

---

### POC-06 — Consumer Quota Independence — Failure with Available Shared Capacity

**Objective:** Validate that a Consumer subscription without quota for the VM SKU cannot deploy a VM against a shared CRG with available capacity. Confirm that shared capacity does NOT transfer quota from Provider to Consumer.

**Azure Resources Required:**

| Resource | Subscription | Details |
|---|---|---|
| Shared CRG (pre-existing) | poc-provider-sub | `crg-poc-primary-eus2` — with available capacity |
| VM (attempt only) | poc-consumer-b-sub | `vm-poc-cons-b-quota-01` — Standard_D4s_v3 |

**Preconditions:**

- POC-01 complete; Consumer-B in sharing profile (added in POC-04, or add for this test)
- `poc-consumer-b-sub` quota for Standard_D4s_v3 in East US 2 is ZERO or insufficient
- `[Warning]` Do NOT increase Consumer-B quota during this test — the goal is to observe the failure

**Execution Steps:**

```
Step 1 — Confirm Consumer-B quota for Standard_D4s_v3 is zero or insufficient
  az vm list-usage --location eastus2 \
    --query "[?name.value=='standardDSv3Family']" \
    --subscription poc-consumer-b-sub

Step 2 — Confirm shared CRG has available capacity (allocated < quantity)
  GET crg-poc-primary-eus2 with instanceView
  Assert: quantity > allocated

Step 3 — Add Consumer-B to sharing profile if not present
  [Update sharingProfile to include consumer-b-sub]

Step 4 — Attempt Consumer-B VM deployment against shared CRG
  az vm create \
    --name vm-poc-cons-b-quota-01 \
    --resource-group rg-poc-workload-cons-b \
    --image Ubuntu2204 \
    --size Standard_D4s_v3 \
    --zone <consumer-b-correct-zone> \
    --capacity-reservation-group \
      /subscriptions/<provider-sub-id>/.../crg-poc-primary-eus2 \
    --subscription poc-consumer-b-sub \
    --admin-username azurepocadmin \
    --generate-ssh-keys

Step 5 — Capture error response
  Record: HTTP status, error code, error message

Step 6 — Confirm CR allocated count unchanged
  GET crg with instanceView; assert allocated == same as before Step 4

Step 7 — Record: does error message reference quota or capacity?
  [Classify error to distinguish quota from capacity failure]
```

**Expected Results:**

- Step 4 fails with quota error (not capacity error)
- Error message references Consumer-B subscription quota, not shared capacity
- CR allocated count unchanged after failure (no partial allocation)
- Confirms: sharing grants capacity access, not quota transfer

**Validation Criteria:**

```
✓ Step 4 returns non-2xx response
✓ Error code is quota-related (not capacity-related)
✓ CR allocated count unchanged after failed deployment
✓ Error message references Consumer-B subscription quota limit
✓ Confirms shared capacity is available but Consumer quota blocked the deployment
```

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Consumer-B already has DSv3 quota from prior tests | Medium | High | Use a fresh subscription or a SKU that Consumer-B has zero quota for |
| Quota and capacity errors indistinguishable | Medium | Medium | Compare error codes with POC-05 results |

---

### POC-07 — Dual Quota State Observation

**Objective:** Observe and document the real-time quota state across Provider and Consumer subscriptions simultaneously during active CR and VM usage. Confirm that Provider quota reflects reserved quantity (not allocated VMs) and Consumer quota reflects deployed VM instances.

**Azure Resources Required:**

| Resource | Subscription | Details |
|---|---|---|
| Shared CRG (pre-existing) | poc-provider-sub | `crg-poc-primary-eus2` |
| VM (running) | poc-consumer-a-sub | `vm-poc-cons-a-01` from POC-02 |

**Preconditions:**

- POC-02 complete; `vm-poc-cons-a-01` running
- Both Provider and Consumer-A quota can be queried

**Execution Steps:**

```
Step 1 — Query Provider quota usage
  az vm list-usage --location eastus2 \
    --query "[?name.value=='standardDSv3Family']" \
    --subscription poc-provider-sub
  Record: currentValue, limit

Step 2 — Query Consumer-A quota usage
  az vm list-usage --location eastus2 \
    --query "[?name.value=='standardDSv3Family']" \
    --subscription poc-consumer-a-sub
  Record: currentValue, limit

Step 3 — Record expected quota usage model
  Provider: quota consumed by CR quantity (4 × 4 vCPU = 16 vCPUs reserved)
  Consumer-A: quota consumed by deployed VM (1 × 4 vCPU = 4 vCPUs deployed)

Step 4 — Increase CR quantity from 4 to 6; observe Provider quota change
  az capacity reservation update \
    --capacity-reservation-group-name crg-poc-primary-eus2 \
    --name cr-poc-d4sv3-z1 \
    --capacity 6 \
    --resource-group rg-poc-capacity-eus2 \
    --subscription poc-provider-sub
  Re-query Provider quota; confirm increase from 16 to 24 vCPUs consumed

Step 5 — Reduce CR quantity back to 4; observe Provider quota release
  az capacity reservation update ... --capacity 4
  Re-query Provider quota; confirm return to 16 vCPUs

Step 6 — Deallocate Consumer-A VM; observe Consumer quota release
  az vm deallocate --name vm-poc-cons-a-01 ...
  Re-query Consumer-A quota; confirm vCPU count decreases

Step 7 — Document quota model findings
  Table: [State] → [Provider quota consumed] → [Consumer quota consumed]
```

**Expected Results:**

- Provider quota tracks CR `quantity` (reserved), not allocated VM count
- Consumer quota tracks deployed VM count only
- Quantity increase/decrease immediately reflected in Provider quota
- VM deallocation releases Consumer quota (VM compute), not Provider quota

**Validation Criteria:**

```
✓ Provider quota increases when CR quantity increases (before any new VM)
✓ Provider quota does not change when Consumer deploys or deallocates VMs
✓ Consumer quota changes only on VM deploy/deallocate operations
✓ The quota model table can be reconstructed from observations
```

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Quota reflects both reserved and allocated causing ambiguity | Medium | Medium | Check `currentValue` at each step; document delta not absolute values |
| Quota refresh delay — API returns stale values | Low | Low | Wait 60 seconds between operations and re-query |

---

## Section 3 — Shared Capacity Consumption

**Section Objective:** Validate how capacity is consumed across a shared CRG — specifically the zero-size pattern, overallocation behavior, capacity release, and the distinction between available and overallocated states.

**Facts Basis:** Research Section 3.3 (zero-size), Section 3.4 (overallocation), Section 3.5 (capacity release), Section 5.3 (physical capacity failure).

---

### POC-08 — Zero-Size Reservation Pattern — Association Before Capacity

**Objective:** Validate that a CR can be created with `quantity=0`, that Consumer VMs can be associated with the resulting overallocated CR, and that the overallocated state is correctly observable. Confirm no SLA is in effect until Provider increases quantity.

**Azure Resources Required:**

| Resource | Subscription | Details |
|---|---|---|
| Capacity Reservation Group (new) | poc-provider-sub | `crg-poc-zerosize-eus2` |
| Capacity Reservation | poc-provider-sub | `cr-poc-d4sv3-zero` — Zone 1 — Quantity: 0 |
| VMs (3 units) | poc-consumer-a-sub | `vm-poc-cons-a-z01/z02/z03` — Standard_D4s_v3 |

**Preconditions:**

- Consumer-A in sharing profile of `crg-poc-zerosize-eus2`
- Consumer-A zone mapping validated for Zone 1
- Consumer-A has quota for 3 × Standard_D4s_v3 (12 vCPUs minimum)

**Execution Steps:**

```
Step 1 — Create CRG for zero-size test
  az capacity reservation group create \
    --name crg-poc-zerosize-eus2 \
    --resource-group rg-poc-capacity-eus2 \
    --location eastus2 --zones 1 \
    --subscription poc-provider-sub

Step 2 — Create CR with quantity = 0
  az capacity reservation create \
    --capacity-reservation-group-name crg-poc-zerosize-eus2 \
    --name cr-poc-d4sv3-zero \
    --resource-group rg-poc-capacity-eus2 \
    --location eastus2 \
    --sku Standard_D4s_v3 \
    --capacity 0 \
    --zone 1 \
    --subscription poc-provider-sub
  Record: provisioningState, quota consumed

Step 3 — Verify CR at quantity=0 — no quota consumed
  az vm list-usage --location eastus2 \
    --query "[?name.value=='standardDSv3Family']" \
    --subscription poc-provider-sub
  Confirm: usage unchanged from pre-test baseline

Step 4 — Add Consumer-A to zero-size CRG sharing profile
  [Update crg-poc-zerosize-eus2 sharingProfile to include consumer-a-sub]

Step 5 — Deploy 3 VMs from Consumer-A against zero-size CRG
  For each VM (vm-poc-cons-a-z01, z02, z03):
    az vm create --size Standard_D4s_v3 --zone <consumer-a-zone-1-equivalent> \
      --capacity-reservation-group .../crg-poc-zerosize-eus2 ...

Step 6 — Observe CR state after 3 VM associations
  GET cr-poc-d4sv3-zero with instanceView
  Record: quantity (expected: 0), allocated (expected: 3)
  Document: overallocated state — allocated > quantity

Step 7 — Confirm Provider quota still zero for zero-size CR
  Re-query Provider DSv3 quota
  Confirm: no increase from baseline (CR at quantity=0 consumes no quota)

Step 8 — Provider increases CR quantity from 0 to 3
  az capacity reservation update --capacity 3 ...
  Record: provisioningState, quota delta

Step 9 — Verify Provider quota now consumed
  Re-query Provider DSv3 quota; confirm +12 vCPU (3 × D4s_v3)

Step 10 — Verify CR state shows allocation ≥ quantity (SLA active)
  GET CR with instanceView; confirm quantity=3, allocated=3
```

**Expected Results:**

- CR created at quantity=0 without quota or capacity consumption
- VMs deploy successfully against zero-size CR (overallocated state)
- CR shows `quantity=0, allocated=3` — clearly overallocated
- No SLA coverage in overallocated state
- After quantity increase to 3: Provider quota +12 vCPU; CR shows quantity=allocated=3

**Validation Criteria:**

```
✓ CR creation at quantity=0 succeeds
✓ Provider quota usage unchanged after quantity=0 CR creation
✓ 3 Consumer VMs deploy successfully against zero-size CRG
✓ CR instanceView: quantity=0, allocated=3 confirmed (overallocated state)
✓ After quantity=3 update: Provider quota +12 vCPU
✓ CR instanceView: quantity=3, allocated=3 (SLA active state)
✓ All 3 VMs continue running throughout — no interruption
```

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Platform may reject quantity=0 CR creation | Medium | High | This is documented behavior; if rejected, record error for POC findings |
| Overallocated state not surfaced in instanceView | Medium | Medium | Use Resource Graph query as alternative visibility mechanism |
| VM creation fails against quantity=0 CRG | Medium | High | Document failure mode; test whether pre-existing VMs can be associated |

---

### POC-09 — Overallocation State Observation and SLA Boundary

**Objective:** Validate that Azure does not block VM association when a CR is fully consumed (allocated = quantity), confirm the overallocated VM enters an identifiable state, and determine whether any observable SLA signal distinguishes allocated-with-SLA from allocated-without-SLA VMs.

**Azure Resources Required:**

| Resource | Subscription | Details |
|---|---|---|
| Shared CRG (pre-existing) | poc-provider-sub | `crg-poc-primary-eus2` |
| CR | poc-provider-sub | `cr-poc-d4sv3-z1` — quantity=4 |
| VMs (5 total) | poc-consumer-a-sub | Deploy 5 VMs against a CR with quantity=4 |

**Preconditions:**

- CR `cr-poc-d4sv3-z1` has quantity=4 and current allocated=0 (or adjust accordingly)
- Consumer-A has quota for 5 × Standard_D4s_v3 (20 vCPUs)
- Zone mapping validated

**Execution Steps:**

```
Step 1 — Ensure CR is at known state: quantity=4, allocated=0
  [Deallocate any existing Consumer VMs if needed]
  GET CR; confirm quantity=4, allocated=0

Step 2 — Deploy 4 VMs — fill CR to capacity
  Deploy vm-poc-cons-a-01 through 04
  After each: GET CR; record allocated count

Step 3 — Confirm CR fully consumed state
  GET CR with instanceView
  Assert: quantity=4, allocated=4

Step 4 — Deploy 5th VM — expected to enter overallocated state
  Deploy vm-poc-cons-a-05 against same shared CRG
  Record: did deployment succeed or fail?

Step 5 — If deployment succeeds — observe overallocated CR state
  GET CR; record quantity=4, allocated=5
  Check: any error/warning on VM resource itself?
  Check: any event in Activity Log for the CR?

Step 6 — Check all 5 VMs running
  az vm list --resource-group rg-poc-workload-cons-a \
    --query "[].{Name:name, PowerState:powerState}" \
    --subscription poc-consumer-a-sub

Step 7 — Attempt to find SLA signal in VM or CR metadata
  Check VM properties for any SLA/guaranteed status flag
  Check CR instanceView fields for overallocation warning

Step 8 — Document observations
  Is overallocated state visible to Provider? To Consumer?
  What signal (if any) indicates overallocation?
```

**Expected Results:**

- 4 VMs deploy successfully (within CR quantity)
- 5th VM deployment succeeds despite CR fully consumed
- CR shows `quantity=4, allocated=5` after 5th VM
- All 5 VMs in Running state
- No explicit SLA signal visible at VM resource level
- Provider can observe overallocation via CR instanceView

**Validation Criteria:**

```
✓ All 5 VMs reach Running state
✓ CR instanceView after 5th VM: allocated > quantity (overallocated)
✓ Azure did NOT block the 5th VM association — confirm this behavior
✓ No automatic error/event triggered by overallocation
✓ Document: where (if anywhere) is overallocation state surfaced
✓ CR allocated count accurately reflects all associated VMs
```

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| 5th VM deployment blocked by platform | Medium | High | Record failure if it occurs — platform may have changed behavior in preview |
| Overallocation state causes VM instability | Low | High | Monitor VMs during test; be prepared to deallocate quickly |
| CR state not immediately updated — latency | Low | Low | Wait 2 minutes between last VM deploy and CR state query |

---

### POC-10 — Capacity Release on CR Quantity Reduction

**Objective:** Validate that reducing CR quantity releases reserved physical capacity back to the Azure pool and correctly reflects in Provider quota. Confirm the minimum quantity floor (cannot reduce below currently allocated count).

**Azure Resources Required:**

| Resource | Subscription | Details |
|---|---|---|
| Shared CRG (pre-existing) | poc-provider-sub | `crg-poc-primary-eus2` |
| CR | poc-provider-sub | `cr-poc-d4sv3-z1` — currently at quantity=4 |
| VMs (2 running) | poc-consumer-a-sub | `vm-poc-cons-a-01`, `vm-poc-cons-a-02` |

**Preconditions:**

- CR quantity=4, allocated=2 (2 Consumer VMs running)

**Execution Steps:**

```
Step 1 — Record baseline state
  Provider DSv3 quota usage (before reduction)
  CR: quantity=4, allocated=2

Step 2 — Reduce CR quantity from 4 to 2 (matching allocated count)
  az capacity reservation update --capacity 2 ...
  Record: provisioningState, new quantity
  Re-query Provider quota; confirm -8 vCPU (2 × D4s_v3 released)

Step 3 — Attempt to reduce CR quantity below allocated count (quantity=1 when allocated=2)
  az capacity reservation update --capacity 1 ...
  Record: success or failure; error message

Step 4 — Verify 2 VMs still running after quantity reduction to 2
  All 2 VMs should still be associated and running

Step 5 — Deallocate 1 VM; then reduce quantity to 1
  az vm deallocate vm-poc-cons-a-02
  az capacity reservation update --capacity 1 ...
  Record: success — now 1 allocated, quantity=1

Step 6 — Delete CR entirely; observe capacity and quota release
  az capacity reservation delete \
    --name cr-poc-d4sv3-z1 \
    --capacity-reservation-group-name crg-poc-primary-eus2 \
    [Note: will fail if any VMs still associated — deallocate all first]

Step 7 — Confirm Provider quota released after CR delete
  Re-query Provider DSv3 quota; confirm returns to pre-CR baseline
```

**Expected Results:**

- Quantity reduction to 2 succeeds; Provider quota decreases by 8 vCPUs
- Quantity reduction below allocated count (Step 3) fails with error
- CR deletion requires all VMs disassociated; fails if any remain
- Full quota release confirmed on CR deletion

**Validation Criteria:**

```
✓ Provider quota delta matches (quantity_old - quantity_new) × SKU_vCPUs
✓ Step 3 quantity below allocated count returns error (record error code)
✓ Both VMs continue running after quantity reduction to 2
✓ CR deletion succeeds only after all VMs disassociated
✓ Provider quota returns to pre-CR baseline after deletion
```

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Quantity reduction below allocated not blocked | Low | High | Record behavior if platform allows — significant finding for POC |
| CR deletion fails silently — quota not released | Low | Medium | Explicitly verify quota after deletion |

---

## Section 4 — VM Associate and Disassociate Behaviour

**Section Objective:** Validate both association paths (at creation and via deallocation), both disassociation paths (deallocation-based and zero-size-based), VMSS behavior, and the operational hazard of unsharing while Consumer VMs are active.

**Facts Basis:** Research Section 4.1 (association mechanics), Section 4.2 (running VM association), Section 4.3 (disassociation paths), Section 4.4 (VMSS), Section 4.5 (unsharing with active VMs).

---

### POC-11 — Running VM Direct Association Failure

**Objective:** Confirm that attempting to associate a running VM with a CRG by directly setting `capacityReservationGroup` on a running VM (without prior deallocation) fails with a documented error. Record the exact error for runbook documentation.

**Azure Resources Required:**

| Resource | Subscription | Details |
|---|---|---|
| Running VM (no CRG) | poc-consumer-a-sub | `vm-poc-cons-a-nodcrg` — Standard_D4s_v3 — running, no CRG association |
| Shared CRG (pre-existing) | poc-provider-sub | `crg-poc-primary-eus2` |

**Preconditions:**

- `vm-poc-cons-a-nodcrg` deployed without `capacityReservationGroup` property
- VM is in Running state
- Shared CRG has available capacity

**Execution Steps:**

```
Step 1 — Verify VM is in Running state
  az vm show --name vm-poc-cons-a-nodcrg ... \
    --query "powerState" -- confirm "VM running"

Step 2 — Verify VM has no CRG association
  az vm show ... --query "properties.capacityReservationGroup"
  Assert: null or empty

Step 3 — Attempt direct association on running VM
  az rest --method put \
    --uri ".../virtualMachines/vm-poc-cons-a-nodcrg?api-version=2024-11-01" \
    --body '{
      "location": "eastus2",
      "properties": {
        "capacityReservationGroup": {
          "id": "/subscriptions/<provider-sub>/...crg-poc-primary-eus2"
        }
      }
    }'

Step 4 — Capture full error response
  Record: HTTP status, error.code, error.message

Step 5 — Confirm VM still running with no CRG association
  Verify VM power state unchanged; capacityReservationGroup still null
```

**Expected Results:**

- Step 3 fails with validation error indicating VM must be deallocated
- VM remains Running with no CRG association
- Error message recorded verbatim for runbook documentation

**Validation Criteria:**

```
✓ Step 3 returns non-2xx HTTP response
✓ Error message references deallocation requirement
✓ VM power state unchanged (still Running) after failed attempt
✓ VM capacityReservationGroup property still null
```

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Platform silently accepts association on running VM | Low | High | This would be an undocumented behavior change — document thoroughly |

---

### POC-12 — Running VM Association via Deallocation (Path A)

**Objective:** Validate Path A disassociation and re-association — deallocate running VM, set `capacityReservationGroup`, restart VM. Confirm VM restarts within the CR and CR allocated count increments correctly.

**Azure Resources Required:**

| Resource | Subscription | Details |
|---|---|---|
| VM (running, no CRG) | poc-consumer-a-sub | `vm-poc-cons-a-nodcrg` from POC-11 |
| Shared CRG | poc-provider-sub | `crg-poc-primary-eus2` |

**Preconditions:**

- POC-11 complete
- CR has available capacity (allocated < quantity)
- Zone mapping validated for Consumer-A

**Execution Steps:**

```
Step 1 — Record CR state before test
  GET CR; record quantity and allocated

Step 2 — Deallocate the VM
  az vm deallocate --name vm-poc-cons-a-nodcrg \
    --resource-group rg-poc-workload-cons-a \
    --subscription poc-consumer-a-sub
  Wait for: powerState == "VM deallocated"

Step 3 — Set capacityReservationGroup on deallocated VM
  az vm update \
    --name vm-poc-cons-a-nodcrg \
    --resource-group rg-poc-workload-cons-a \
    --capacity-reservation-group \
      /subscriptions/<provider-sub-id>/.../crg-poc-primary-eus2 \
    --subscription poc-consumer-a-sub

Step 4 — Verify CRG property set correctly
  az vm show ... --query "properties.capacityReservationGroup.id"

Step 5 — Start VM
  az vm start --name vm-poc-cons-a-nodcrg ...
  Wait for: powerState == "VM running"

Step 6 — Verify CR allocated count incremented
  GET CR with instanceView; allocated should be +1 vs Step 1 baseline

Step 7 — Disassociate VM — Path A (reverse)
  az vm deallocate vm-poc-cons-a-nodcrg
  az vm update ... --capacity-reservation-group ""  # or null
  az vm start vm-poc-cons-a-nodcrg
  Verify CR allocated -1; VM running without CRG
```

**Expected Results:**

- VM deallocates successfully
- CRG property set on deallocated VM without error
- VM starts successfully with CRG association
- CR allocated count +1 on start; -1 on disassociation
- VM runs normally post-association

**Validation Criteria:**

```
✓ VM reaches "VM deallocated" before Step 3
✓ Step 3 succeeds without error
✓ VM reaches "VM running" after Step 5
✓ CR allocated count increments by 1 after VM start
✓ CR allocated count decrements by 1 after Path A disassociation
✓ Total CR quantity not changed by any association/disassociation operation
```

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| VM start fails — zone mismatch after deallocation | Medium | High | Confirm zone targeting before Step 5 |
| CRG property cannot be cleared via CLI | Low | Medium | Use az rest PUT with null CRG property as fallback |

---

### POC-13 — Running VM Disassociation via Zero-Size Pattern (Path B)

**Objective:** Validate that a running VM can be disassociated from a CRG without deallocation using Path B — Provider reduces CR quantity to 0, Consumer clears `capacityReservationGroup` on running VM. Confirm VM continues running without interruption.

**Azure Resources Required:**

| Resource | Subscription | Details |
|---|---|---|
| VM (running, associated with CRG) | poc-consumer-a-sub | `vm-poc-cons-a-01` — currently associated |
| Capacity Reservation | poc-provider-sub | `cr-poc-d4sv3-z1` — quantity=2, allocated=1 |

**Preconditions:**

- `vm-poc-cons-a-01` running and associated with `crg-poc-primary-eus2`
- CR quantity ≥ 1; only this one VM associated (or reduce quantity to exactly match allocated)

**Execution Steps:**

```
Step 1 — Record baseline VM and CR state
  VM: powerState=Running, capacityReservationGroup = CRG-ID
  CR: quantity=2, allocated=1

Step 2 — Provider reduces CR quantity to 0
  az capacity reservation update \
    --name cr-poc-d4sv3-z1 \
    --capacity 0 \
    --capacity-reservation-group-name crg-poc-primary-eus2 \
    --resource-group rg-poc-capacity-eus2 \
    --subscription poc-provider-sub
  Record: success/failure; CR state after update

Step 3 — Observe VM state immediately after CR quantity set to 0
  VM should still be running — record powerState

Step 4 — Consumer clears capacityReservationGroup on running VM
  az rest --method patch \
    --uri ".../virtualMachines/vm-poc-cons-a-01?api-version=2024-11-01" \
    --body '{"properties": {"capacityReservationGroup": null}}'
  Or use az vm update if null property supported

Step 5 — Confirm VM still running after property clear
  az vm show ... --query "powerState"
  Expected: VM running

Step 6 — Confirm capacityReservationGroup property cleared
  az vm show ... --query "properties.capacityReservationGroup"
  Expected: null

Step 7 — Confirm CR allocated count decremented
  GET CR; record allocated (should be 0 after clear)

Step 8 — Provider restores CR quantity to previous value if needed for subsequent tests
  az capacity reservation update --capacity 2 ...
```

**Expected Results:**

- VM continues running throughout Path B disassociation
- VM `capacityReservationGroup` property clears without deallocation
- CR allocated count decrements without VM deallocation
- No maintenance window required

**Validation Criteria:**

```
✓ Provider CR quantity=0 update succeeds
✓ VM powerState == "VM running" at every observation point during test
✓ VM capacityReservationGroup property == null after Step 4
✓ CR allocated count == 0 after disassociation
✓ Zero interruption to running VM confirmed
```

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Platform rejects CRG property clear on running VM even at quantity=0 | Medium | High | Document failure mode; test Path A as fallback |
| CR quantity=0 immediately releases physical capacity — VM becomes unstable | Low | High | Monitor VM heartbeat throughout; be prepared to deallocate if instability observed |

---

### POC-14 — Forced Unsharing with Active Consumer VMs — Silent Hazard Validation

**Objective:** Validate the documented silent operational hazard — Provider removes Consumer from sharing profile while Consumer VMs are running and associated. Confirm VMs continue running, then confirm next deallocation/restart fails.

**Azure Resources Required:**

| Resource | Subscription | Details |
|---|---|---|
| VMs (2 running) | poc-consumer-a-sub | `vm-poc-cons-a-01`, `vm-poc-cons-a-02` — associated with shared CRG |
| Shared CRG | poc-provider-sub | `crg-poc-primary-eus2` |

**Preconditions:**

- 2 Consumer-A VMs running and associated with `crg-poc-primary-eus2`
- All 3 RBAC steps complete

**Execution Steps:**

```
Step 1 — Confirm baseline VM and CRG state
  Both VMs: Running, capacityReservationGroup set to Provider CRG
  CRG: Consumer-A in sharingProfile

Step 2 — Provider removes Consumer-A from sharing profile
  PUT crg-poc-primary-eus2 with sharingProfile.subscriptionIds = []
  (empty array — no consumers)

Step 3 — Immediately check Consumer-A VMs after unsharing
  Both VMs: confirm still Running — SLA maintained at time of unsharing

Step 4 — Attempt Consumer-A new VM deployment after unsharing
  Deploy vm-poc-cons-a-new
  Expected: authorization failure (Consumer no longer in profile)

Step 5 — Deallocate vm-poc-cons-a-01 (simulate maintenance operation)
  az vm deallocate vm-poc-cons-a-01

Step 6 — Attempt to restart vm-poc-cons-a-01
  az vm start vm-poc-cons-a-01
  Expected: start FAILS — CRG association still set but Consumer no longer authorized

Step 7 — Capture and record the exact error from Step 6
  HTTP status, error.code, error.message

Step 8 — Resolve: clear CRG association, restart VM (best-effort capacity)
  Set capacityReservationGroup to null on vm-poc-cons-a-01
  az vm start vm-poc-cons-a-01 (now without CRG — best-effort capacity)

Step 9 — Restore Consumer-A to sharing profile
  PUT crg with sharingProfile.subscriptionIds = [consumer-a-sub]
  Re-associate vm-poc-cons-a-01 via Path A if needed
```

**Expected Results:**

- Both VMs continue running immediately after unsharing (Step 3)
- New Consumer-A VM deployment fails (Step 4)
- vm-poc-cons-a-01 FAILS to restart after deallocation (Step 6)
- Error message at Step 6 is the key finding — record for runbook documentation
- VM can be recovered by clearing CRG property and restarting without CRG (Step 8)

**Validation Criteria:**

```
✓ Step 3: Both VMs Running immediately after unsharing — silent hazard confirmed
✓ Step 4: New VM deployment fails — authorization error
✓ Step 6: VM restart fails after deallocation — critical failure mode confirmed
✓ Step 7: Error message recorded verbatim — required for operational runbooks
✓ Step 8: VM recovers when CRG association cleared
✓ The silent hazard is reproducible and documented
```

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| VM restart succeeds in Step 6 — platform behavior changed | Medium | High | Document if this occurs — behavior change from documented state |
| VM restart fails with non-descriptive error making root cause unclear | Medium | Medium | Check Activity Log for detailed error; compare with authorization error from POC-03 |
| Consumer-A VMs lose stability during test | Low | Medium | Have a recovery procedure ready (Step 8) before starting |

---

### POC-15 — VMSS Instance Individual Disassociation Scoped Test (G-13)

**Objective:** Confirm that individual VMSS instances **cannot** be disassociated from a CRG via the standard VM PATCH operation — specifically, that `az vm update --capacity-reservation-group ""` fails or is unsupported for VMSS instances. Document the actual ARM error returned. This scopes G-13 (VMSS disassociation path) for the Tier 3 Emergency Transfer design.

**Priority:** High (G-13 scoping input)

**Azure Resources Required:**

| Resource | Subscription | Details |
|---|---|---|
| CRG (pre-existing) | poc-provider-sub | `crg-poc-primary-eus2` shared to poc-consumer-a-sub |
| VMSS | poc-consumer-a-sub | `vmss-poc-cons-a-web` — 2 instances, associated to `crg-poc-primary-eus2` |

**Preconditions:**

- POC-28 complete (VMSS known issue observed)
- VMSS `vmss-poc-cons-a-web` running with at least 2 instances, both consuming CR slots

**Execution Steps:**

```
Step 1 — Record starting state
  az vmss list-instances --resource-group rg-poc-workload-cons-a \
    --name vmss-poc-cons-a-web --subscription poc-consumer-a-sub \
    --query "[].{id:instanceId, name:name}" --output table
  GET the CRG CR instanceView; record allocated slot count (expect 2)

Step 2 — Attempt individual VMSS instance disassociation via az vm update
  # VMSS instances are exposed as Microsoft.Compute/virtualMachineScaleSets/{name}/virtualMachines/{instanceId}
  az rest --method patch \
    --uri "https://management.azure.com/subscriptions/<cons-a-sub-id>/resourceGroups/rg-poc-workload-cons-a/providers/Microsoft.Compute/virtualMachineScaleSets/vmss-poc-cons-a-web/virtualMachines/0?api-version=2024-03-01" \
    --body '{"properties":{"capacityReservation":{"capacityReservationGroup":null}}}'
  Record: exact HTTP status code, error.code, and error.message VERBATIM
  Expected: failure (operation unsupported on VMSS instance) — capture the precise error

Step 3 — Attempt VMSS-level disassociation
  az rest --method patch \
    --uri "https://management.azure.com/subscriptions/<cons-a-sub-id>/resourceGroups/rg-poc-workload-cons-a/providers/Microsoft.Compute/virtualMachineScaleSets/vmss-poc-cons-a-web?api-version=2024-03-01" \
    --body '{"properties":{"virtualMachineProfile":{"capacityReservation":{"capacityReservationGroup":null}}}}'
  Record: HTTP status; whether the model updates but instances retain association until reimage
  If accepted: az vmss update-instances --instance-ids '*' to roll the change

Step 4 — Determine which operation actually frees the CR slot
  After each attempt, GET the CR instanceView and record allocated count
  Document which operation (instance PATCH, VMSS-model PATCH + reimage, or scale-in) reduces allocated

Step 5 — Confirm scale-in path (Path B equivalent for VMSS)
  az vmss scale --resource-group rg-poc-workload-cons-a \
    --name vmss-poc-cons-a-web --new-capacity 1 --subscription poc-consumer-a-sub
  GET CR instanceView; confirm allocated decremented by scaled-in instance count
```

**Expected Results:**

- Individual VMSS instance disassociation via VM PATCH (Step 2) fails or is silently unsupported — exact error captured
- VMSS-model-level disassociation (Step 3) either requires a reimage/roll to take effect or is rejected
- Scale-in (Step 5) is confirmed as the reliable path to free CR slots for VMSS
- The confirmed disassociation path is documented for the Tier 3 `vm_disassociation_list` VMSS handling

**Validation Criteria:**

```
✓ Step 2: Individual instance disassociation error code + message recorded verbatim
✓ Step 3: VMSS-model PATCH behavior documented (accepted+reimage-required, or rejected)
✓ Step 4: The operation that actually frees the CR slot is identified
✓ Step 5: Scale-in confirmed to decrement CR allocated count
✓ VMSS disassociation path fully scoped for G-13 design session
```

**Finding Target:** The confirmed disassociation path for VMSS instances feeds the G-13 design session and the Tier 3 `vm_disassociation_list` handling for VMSS entries.

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| VMSS instance PATCH silently succeeds without freeing slot | Medium | High | Always confirm via CR instanceView allocated count, not the PATCH response alone |
| Reimage required to apply model change causes workload disruption | Medium | Medium | Perform on non-production POC VMSS only; document reimage requirement |
| Uniform vs Flexible orchestration mode changes behavior | Medium | Medium | Record orchestration mode; note that findings apply to the tested mode; retest other mode if design requires |

---

## Section 5 — Availability Zone Requirements

**Section Objective:** Validate the zone logical-to-physical mapping challenge in cross-subscription scenarios, confirm the Check Zone Peers API mechanism, reproduce the AZ mismatch failure mode, and validate the resolution workflow.

**Facts Basis:** Research Section 2.4 (AZ scope), Section 5.4 (AZ mismatch failure), GP-04 (zone mapping discovery).

---

### POC-20 — Zone Mapping Discovery and Documentation

**Objective:** Document the complete logical-to-physical zone mapping for all POC subscriptions in East US 2. This output is a required input artifact for all subsequent AZ tests.

**Azure Resources Required:**

- No Azure resources required — query only

**Preconditions:**

- Access to all 5 POC subscriptions
- `Microsoft.Resources/AvailabilityZonePeering` feature registered in poc-provider-sub and poc-consumer-a-sub (submit registration before starting; may take up to 60 minutes)

**Execution Steps:**

```
Step 1 — Query zone mapping from each subscription (repeat for all 5 subs)
  az account list-locations \
    --query "[?name=='eastus2'].{name:name, zoneMappings:availabilityZoneMappings}" \
    --subscription <sub-id>

Step 2 — Register AvailabilityZonePeering feature in Provider and Consumer-A
  az feature register \
    --namespace Microsoft.Resources \
    --name AvailabilityZonePeering \
    --subscription poc-provider-sub

  az feature register \
    --namespace Microsoft.Resources \
    --name AvailabilityZonePeering \
    --subscription poc-consumer-a-sub

Step 3 — Check feature registration status
  az feature show \
    --namespace Microsoft.Resources \
    --name AvailabilityZonePeering \
    --subscription poc-provider-sub
  Wait for: state == "Registered"

Step 4 — Call Check Zone Peers API from Provider subscription
  az rest --method post \
    --uri "https://management.azure.com/subscriptions/<provider-sub-id>/
           providers/Microsoft.Resources/checkZonePeers/?api-version=2022-12-01" \
    --body '{
      "location": "eastus2",
      "subscriptionIds": [
        "/subscriptions/<consumer-a-sub-id>",
        "/subscriptions/<consumer-b-sub-id>",
        "/subscriptions/<dr-sub-id>"
      ]
    }'

Step 5 — Document zone mapping table from API response
  Build table: For each Provider logical zone (1,2,3) → corresponding Consumer-A logical zone
  Example table format:

  | Physical Zone | Provider Logical | Consumer-A Logical | Consumer-B Logical |
  |---|---|---|---|
  | Physical-A    | 1                | 2                  | 3                  |
  | Physical-B    | 2                | 1                  | 2                  |
  | Physical-C    | 3                | 3                  | 1                  |

Step 6 — Validate: use az account list-locations output to cross-reference API results
```

**Expected Results:**

- Zone mapping table produced for all 5 subscriptions
- Check Zone Peers API returns cross-subscription zone peer mapping
- At least 2 subscriptions have non-identical logical zone numbering (expected — random assignment)
- Feature registration succeeds within 60 minutes

**Validation Criteria:**

```
✓ Zone mapping table complete for all 5 POC subscriptions
✓ Check Zone Peers API returns valid response (not feature unavailable error)
✓ Feature registration state == "Registered" before API call
✓ At least one subscription pair shows non-identical logical zone numbering
✓ Zone mapping table signed off as POC-20 artifact before proceeding to POC-21
```

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| AvailabilityZonePeering feature requires Microsoft support to enable | Medium | High | Submit feature registration early; if self-service fails, escalate to support |
| All POC subscriptions have identical zone mappings — mismatch test cannot be run | Low | Medium | If mappings are identical, document this and note POC-21 is not testable in this environment |
| Check Zone Peers API returns 404 — feature not available in region | Low | High | Test with different region or document as known limitation |

---

### POC-21 — AZ Mismatch Deployment Failure

**Objective:** Reproduce the documented AZ mismatch failure — Consumer deliberately targets the wrong logical zone (one that maps to a different physical zone than the Provider's CR). Confirm deployment fails and record the exact error message.

**Azure Resources Required:**

| Resource | Subscription | Details |
|---|---|---|
| Shared CRG | poc-provider-sub | `crg-poc-primary-eus2` — CR in Provider logical Zone 1 |
| VM (attempt only) | poc-consumer-a-sub | `vm-poc-cons-a-azmismatch` — wrong zone intentionally |

**Preconditions:**

- POC-20 zone mapping table complete
- Provider CR is in logical Zone 1 (maps to Physical-X)
- Identified Consumer-A logical zone that maps to a DIFFERENT physical zone than Physical-X
- Consumer-A has quota and RBAC setup is complete

**Execution Steps:**

```
Step 1 — Identify zones for mismatch test
  From POC-20 table: Provider Zone 1 → Physical-X
  Find Consumer-A logical zone that does NOT map to Physical-X
  Record: Consumer-A wrong zone = <Y>

Step 2 — Attempt VM deployment from Consumer-A using wrong zone <Y>
  az vm create \
    --name vm-poc-cons-a-azmismatch \
    --resource-group rg-poc-workload-cons-a \
    --image Ubuntu2204 \
    --size Standard_D4s_v3 \
    --zone <wrong-consumer-zone-Y> \
    --capacity-reservation-group \
      /subscriptions/<provider-sub-id>/.../crg-poc-primary-eus2 \
    --subscription poc-consumer-a-sub \
    --admin-username azurepocadmin \
    --generate-ssh-keys

Step 3 — Capture full error response
  Record: HTTP status, error.code, error.message, error.details

Step 4 — Confirm no VM resource created
  az vm show vm-poc-cons-a-azmismatch — should return 404

Step 5 — Confirm CR allocated count unchanged
  GET CR; allocated unchanged from before attempt

Step 6 — Identify correct Consumer-A zone from POC-20 table
  Find Consumer-A logical zone that maps to same physical zone as Provider Zone 1

Step 7 — Retry VM deployment with correct Consumer-A zone
  Same command but with correct zone
  Confirm: VM deploys successfully — zone mismatch was the only blocker
```

**Expected Results:**

- Step 2 deployment fails — zone validation prevents deployment
- Error message references zone constraint or availability zone mismatch
- No partial VM resource created (Step 4 returns 404)
- CR allocated count unchanged (Step 5)
- Correct zone retry (Step 7) succeeds — confirms zone was the only issue

**Validation Criteria:**

```
✓ Step 2 returns non-2xx HTTP response
✓ Error message references availability zone or zone mismatch (record exact message)
✓ No VM resource exists after failed attempt
✓ CR allocated unchanged after failed attempt
✓ Step 7 VM deployment succeeds with correct zone
✓ Zone mismatch failure is reproducible and documented for runbook
```

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Both POC subscriptions have identical zone mappings — mismatch untestable | Low | Medium | Document and skip to POC-22 if this is the case |
| Error message does not clearly reference zone — root cause unclear | Medium | Medium | Cross-reference Activity Log for full ARM evaluation details |

---

### POC-22 — Check Zone Peers API Resolution Workflow

**Objective:** Validate the end-to-end Check Zone Peers API workflow as the documented resolution mechanism for cross-subscription zone alignment. Confirm the workflow produces actionable zone mapping data for use in Capacity Reservation deployments.

**Azure Resources Required:**

- No Azure resources required — API query only (uses POC-20 outputs)

**Preconditions:**

- POC-20 complete; Check Zone Peers API validated
- `Microsoft.Resources/AvailabilityZonePeering` registered in all relevant subscriptions

**Execution Steps:**

```
Step 1 — Call Check Zone Peers API for all Consumer subscriptions simultaneously
  POST https://management.azure.com/subscriptions/<provider-sub-id>/
       providers/Microsoft.Resources/checkZonePeers/?api-version=2022-12-01
  Body: all consumer subscription IDs

Step 2 — Parse response to build zone peer map
  For each avZonePeers entry:
    physicalZone = entry.physicalZone
    providerLogicalZone = entry.avZone
    For each peerZone:
      consumerSubscriptionId = peerZone.subscriptionId
      consumerLogicalZone = peerZone.avZone
  Build complete mapping table

Step 3 — Validate mapping table against az account list-locations output
  Cross-check 2 entries from each subscription

Step 4 — Document the operational workflow for IaC/automation use
  Describe: API call → parse → zone substitution table → use in Bicep/ARM template
  toLogicalZones() Bicep function applicability

Step 5 — Validate the Bicep toLogicalZones() function (if available in target environment)
  Create a simple Bicep template that uses toLogicalZones() for zone resolution
  Confirm: template passes validation with correct zone values
```

**Expected Results:**

- Check Zone Peers API returns complete cross-subscription zone mapping
- Mapping table validated against list-locations output
- Operational workflow documented for automation use
- Bicep function behavior documented (if testable)

**Validation Criteria:**

```
✓ API response contains avZonePeers entries for all requested subscriptions
✓ Zone mapping table matches list-locations output for spot-checked entries
✓ Operational workflow documented with exact API call, response schema, and mapping algorithm
✓ Zone mapping table is the definitive zone reference for all remaining POC tests
```

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Check Zone Peers API returns empty peersInformation | Medium | High | Confirm feature registration is complete in all subscriptions |
| Bicep toLogicalZones() not available in current API version | Medium | Low | Skip Bicep step; focus on REST API workflow |

---

### POC-16 — Zone Peers Multi-Subscription Resolution (Extends POC-22)

**Objective:** Extend POC-22 (single-pair Check Zone Peers) to validate that the API accepts a **multi-subscription payload** (3+ subscriptions) and correctly returns zone mapping for all of them in one call. This is the pattern the ACRME Zone Mapping Registry (E06-S02) uses during batch zone resolution on subscription onboarding.

**Priority:** Medium

**Azure Resources Required:**

- No Azure resources required — API query only (4 POC Consumer subscriptions in one payload)

**Preconditions:**

- POC-22 complete (single-pair Check Zone Peers workflow validated)
- `Microsoft.Resources/AvailabilityZonePeering` registered in all subscriptions in the payload
- Subscription IDs recorded for poc-consumer-a-sub, poc-consumer-b-sub, poc-dr-sub, poc-nonprod-sub

**Execution Steps:**

```
Step 1 — Record single-subscription baseline latency (from POC-22)
  Issue checkZonePeers for poc-provider-sub with ONE subscription in subscriptionIds
  Record: response time (T_single)

Step 2 — Issue multi-subscription checkZonePeers (4 subscriptions in one call)
  az rest --method post \
    --uri "https://management.azure.com/subscriptions/<provider-sub-id>/providers/Microsoft.Resources/checkZonePeers?api-version=2022-12-01" \
    --body '{
      "location": "eastus2",
      "subscriptionIds": [
        "subscriptions/<cons-a-sub-id>",
        "subscriptions/<cons-b-sub-id>",
        "subscriptions/<dr-sub-id>",
        "subscriptions/<nonprod-sub-id>"
      ]
    }'
  Record: response time (T_multi); full response body

Step 3 — Confirm zone equivalence returned for ALL 4 subscriptions
  Parse response.availabilityZonePeers[].peers[]
  Confirm each of the 4 subscriptions appears with its zone mapping
  Build the 4-subscription zone equivalence matrix

Step 4 — Compare latency: 4-subscription payload vs 1-subscription payload
  Record: T_multi vs T_single; document whether latency scales linearly with subscription count

Step 5 — Partial-failure behavior test
  Repeat Step 2 but include one INVALID subscription ID (non-existent GUID)
  Record: does the API return partial results for valid subscriptions, or fail the entire call (4xx)?
  Document the error code and whether valid entries are still returned
```

**Expected Results:**

- Multi-subscription checkZonePeers accepts a 4-subscription payload in one call
- Zone equivalence is returned for all 4 subscriptions
- Latency for the 4-subscription call is characterized relative to the single-subscription baseline
- Partial-failure behavior (one bad subscription) is documented — either partial results or whole-call rejection

**Validation Criteria:**

```
✓ Step 2: 4-subscription payload accepted (HTTP 200)
✓ Step 3: Zone equivalence present for all 4 subscriptions
✓ Step 4: T_multi vs T_single latency comparison recorded
✓ Step 5: Partial-failure behavior documented (partial results vs whole-call failure)
✓ Batch zone resolution pattern for E06-S02 confirmed viable
```

**Finding Target:** Confirms whether the ACRME Zone Mapping Registry (E06-S02) can batch-resolve zone mappings for multiple Consumer subscriptions in a single API call during onboarding, and how it must handle a partial failure within the batch.

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| API imposes a maximum subscription count per payload | Medium | Medium | Record the limit; design E06-S02 to page the batch below the limit |
| One invalid subscription fails the entire batch | Medium | Medium | If confirmed, E06-S02 must validate subscription IDs before batching |
| Latency scales super-linearly with subscription count | Low | Low | Document; cap batch size for acceptable onboarding latency |

---

## Section 6 — Disaster Recovery Failover Scenarios

**Section Objective:** Validate DR-specific capacity patterns — pre-positioned shared capacity as DR reserve, failover VM deployment against pre-positioned capacity, capacity reallocation from primary to DR zone, and the VMSS zone outage known issue.

> **Engine Cross-Reference:** Section 6 tests validate Azure ARM behavior for DR pre-positioning. The ACRME engine activates DR operations only when `engine_mode == DR_EVENT_ACTIVE`. Section 10 (POC-46 through POC-51) validates the engine_mode state machine and Emergency Capacity Transfer tiers. POC-23 and POC-24 (below) extend this section to scope the `potential_dr_demand` churn path (B-4) and the RegionalSnapshot staleness fallback that the engine relies on.

**Facts Basis:** Research Section 4.4 (VMSS known issue), Section 4.5 (unsharing behavior), Section 2.3 (regional scope), Section 6.1 (VMSS reprovisioning known issue); `multi_region_placement_design.md` RegionalSnapshot and engine_mode sections (POC-23/24 basis).

---

### POC-23 — `potential_dr_demand` Maintenance — Churn Path Validation (B-4)

**Objective:** Validate the churn path for `potential_dr_demand(region)`. This field is computed as `Σ prod_allocated for customers where dr_region == this region`. The ACRME design specifies the field but has no reconciliation loop step that describes how it is updated when Prod VMs are deallocated. This POC manually simulates the churn and confirms whether an ARM polling-based approach can detect the deallocation event.

**Priority:** High (B-4 blocker scoping)

**Azure Resources Required:**

| Resource | Subscription | Details |
|---|---|---|
| Prod CRG | poc-provider-sub | `crg-poc-prod-eus2` — quantity: 1 |
| Prod VM | poc-consumer-a-sub | `vm-poc-cons-a-churn` — Standard_D4s_v3, associated to Prod CRG |
| DR designation | poc-dr-sub | designated DR target region for the customer under test |

**Preconditions:**

- POC-26 complete (DR deployment observed)
- POC-07 complete (dual quota state understanding)
- A customer record whose `dr_region` maps to the region hosting `poc-dr-sub`

**Execution Steps:**

```
Step 1 — Establish a Prod VM running against a Prod CRG
  az vm create --name vm-poc-cons-a-churn --size Standard_D4s_v3 \
    --resource-group rg-poc-workload-cons-a \
    --capacity-reservation-group <prod-crg-resource-id> \
    --subscription poc-consumer-a-sub --zone 1 ...
  GET the Prod CR instanceView; confirm allocated == 1 (Prod VM consuming one slot)

Step 2 — Record baseline potential_dr_demand for the DR region
  # Prod allocated for this customer contributes to potential_dr_demand(dr_region)
  redis-cli GET snapshot:<dr_region>   # inspect potential_dr_demand field
  Record: potential_dr_demand baseline value

Step 3 — Deallocate the Prod VM (simulate customer Prod churn)
  T0 = now
  az vm deallocate --name vm-poc-cons-a-churn \
    --resource-group rg-poc-workload-cons-a --subscription poc-consumer-a-sub

Step 4 — Poll the CR instanceView until utilized reflects the deallocation
  watch: az rest --method get \
    --uri "https://management.azure.com/subscriptions/<provider-sub-id>/resourceGroups/rg-poc-capacity-eus2/providers/Microsoft.Compute/capacityReservationGroups/crg-poc-prod-eus2/capacityReservations/<cr-name>?api-version=2024-03-01&$expand=instanceView"
  T1 = timestamp when instanceView.utilizedResourceCount (allocated) == 0
  Record: latency = T1 - T0

Step 5 — Determine observability channel
  Check Activity Log for a deallocation event:
    az monitor activity-log list --resource-group rg-poc-workload-cons-a \
      --subscription poc-consumer-a-sub --offset 30m \
      --query "[?contains(operationName.value, 'deallocate')]"
  Compare ARM instanceView latency (Step 4) with Azure Resource Graph latency:
    az graph query -q "Resources | where type =~ 'microsoft.compute/capacityreservationgroups/capacityreservations' | project name, properties.instanceView"
  Record: is deallocation observable via Activity Log event, or only via polling? ARG delay vs ARM delay
```

**Expected Results:**

- Prod VM deallocation reduces CR allocated from 1 to 0
- Latency between `az vm deallocate` and `instanceView.utilized == 0` is measured
- The observability channel (Activity Log event vs polling) is determined
- ARG indexing delay vs ARM real-time is quantified for the deallocation event

**Validation Criteria:**

```
✓ Step 1: Prod CR allocated == 1 with running Prod VM
✓ Step 3–4: Deallocation reduces allocated to 0; latency recorded
✓ Step 5: Activity Log deallocation event presence confirmed (or absence documented)
✓ Step 5: ARG vs ARM consistency delay quantified
✓ Recommendation captured: 5-min poll sufficient, or event-driven trigger required
```

**Finding Target:** Confirms whether the reconciliation loop's 5-minute ARM poll cycle is sufficient to detect Prod churn and update `potential_dr_demand`, or whether an event-driven subscription (Activity Log alert → reconciliation trigger) is required.

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| instanceView utilized field lags deallocation by minutes | Medium | High | This is exactly the measurement — document the lag; feeds poll-interval decision |
| Activity Log does not emit a discrete CR-utilization event | Medium | Medium | Fall back to polling recommendation; document event gap for B-4 |
| ARG indexing delay > 30s makes ARG unusable for churn detection | Medium | Medium | Confirm ARM REST is authoritative for reconciliation, not ARG |

---

### POC-24 — RegionalSnapshot Staleness — Cosmos DB Fallback Trigger

**Objective:** Validate the ACRME staleness fallback path. The design specifies: "If a snapshot is older than 10 minutes (e.g. reconciliation loop is stuck), placement falls back to read directly from Cosmos DB and emits a `StaleRegionalSnapshot` warning." This POC simulates stale data conditions to confirm the ARM/API behaviour that makes this fallback meaningful.

**Priority:** Medium

**Azure Resources Required:**

- No new Azure resources — uses existing CRGs and CRs from POC-25/POC-26; ACRME Redis + Cosmos DB read access

**Preconditions:**

- POC-07 complete (dual quota state understanding)
- POC-29 complete (ARG query patterns)
- Read access to the RegionalSnapshot Redis cache and the backing Cosmos DB region documents

**Execution Steps:**

```
Step 1 — Query CR instanceView via direct ARM API — record latency and consistency
  T_arm_write = time a known state change was applied (e.g. a VM deallocate)
  az rest --method get \
    --uri "https://management.azure.com/.../capacityReservations/<cr>?api-version=2024-03-01&$expand=instanceView"
  Record: ARM read latency; whether the read reflects the write immediately (read-after-write)

Step 2 — Query the same resource via Azure Resource Graph at the same timestamp
  az graph query -q "Resources | where id =~ '<cr-resource-id>' | project properties.instanceView"
  Record: ARG value; timestamp of ARG record vs ARM write

Step 3 — Compute the maximum ARM-vs-ARG consistency delta
  Repeat Steps 1–2 immediately after a state change, sampling every 5s for 60s
  Record: max delta (seconds) between ARM write and ARG reflecting the change

Step 4 — Simulate a stale RegionalSnapshot
  Freeze the reconciliation loop (or manually age the Redis snapshot timestamp > 10 min)
  redis-cli GET snapshot:<region>   # confirm snapshot_age_seconds > 600
  Issue a placement evaluation and confirm the engine falls back to Cosmos DB read
  Confirm StaleRegionalSnapshot warning is emitted

Step 5 — Confirm authoritative data source and consistency SLA
  Compare Cosmos DB region document values with fresh ARM reads
  Document: ARM REST is authoritative; ARG has >30s indexing delay; Cosmos is the fallback store
```

**Expected Results:**

- ARM REST API provides read-after-write consistency for CR instanceView
- ARG exhibits a measurable indexing delay (expected >30s) vs ARM
- When the RegionalSnapshot is older than 10 minutes, the engine falls back to Cosmos DB and emits `StaleRegionalSnapshot`
- The authoritative data source and its consistency SLA are documented

**Validation Criteria:**

```
✓ Step 1: ARM read-after-write consistency confirmed and latency recorded
✓ Step 3: Max ARM-vs-ARG consistency delta quantified (seconds)
✓ Step 4: Stale snapshot (>10 min) triggers Cosmos DB fallback + StaleRegionalSnapshot warning
✓ Step 5: Authoritative source (ARM) and fallback (Cosmos) documented with consistency SLA
```

**Finding Target:** Confirms the correct fallback data source and its consistency SLA, validating that the 10-minute staleness threshold and Cosmos DB fallback are operationally sound.

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| ARG delay is highly variable, hard to bound | Medium | Medium | Sample repeatedly; report p50/p95 delay rather than a single value |
| Cosmos DB fallback path not yet implemented in engine build under test | Medium | High | If unavailable, document as engineering gate; test ARM/ARG consistency only |
| Manually aging the Redis snapshot not supported | Low | Medium | Freeze reconciliation loop instead; or use a test hook to set snapshot timestamp |

---

### POC-25 — DR Capacity Pre-Positioning via Shared CRG

**Objective:** Validate that a DR subscription can be granted access to a shared CRG in the DR target region as a pre-positioned standby capacity reserve. Confirm the DR subscription can deploy VMs against the reserved capacity on demand without prior warm-up time.

**Azure Resources Required:**

| Resource | Subscription | Details |
|---|---|---|
| Capacity Reservation Group (new) | poc-provider-sub | `crg-poc-dr-eus2` — East US 2 (DR region) |
| Capacity Reservation | poc-provider-sub | `cr-poc-dr-d4sv3-z2` — Zone 2 — Quantity: 4 — Standard_D4s_v3 |
| Resource Group | poc-dr-sub | `rg-poc-workload-dr` |

**Subscription Layout:**

```
poc-provider-sub (Primary + DR capacity owner)
├── crg-poc-primary-eus2  [primary workloads]
└── crg-poc-dr-eus2       [DR pre-positioned capacity]
    └── cr-poc-dr-d4sv3-z2  [quantity=4, Zone 2]
    sharingProfile: [poc-dr-sub]

poc-dr-sub (DR Consumer)
└── rg-poc-workload-dr
    └── [no VMs until failover event]
```

**Preconditions:**

- `poc-provider-sub` has quota for DR CRG SKU in East US 2 Zone 2 (additional 16 vCPUs beyond primary CRG)
- `poc-dr-sub` has quota for 4 × Standard_D4s_v3 in East US 2 Zone 2 (16 vCPUs)
- Zone mapping resolved for poc-dr-sub (Zone 2 in provider vs Zone equivalent in dr-sub)
- RBAC three-step setup complete between poc-provider-sub and poc-dr-sub

> **Engine Note:** This test validates the Azure capacity pre-positioning layer. In production, POC-25 state would be established during onboarding. DR failover (POC-26) is engine-triggered only when `engine_mode == DR_EVENT_ACTIVE` (see POC-46).

**Execution Steps:**

```
Step 1 — Create DR CRG and CR
  az capacity reservation group create \
    --name crg-poc-dr-eus2 \
    --resource-group rg-poc-capacity-eus2 \
    --location eastus2 --zones 2 \
    --subscription poc-provider-sub

  az capacity reservation create \
    --capacity-reservation-group-name crg-poc-dr-eus2 \
    --name cr-poc-dr-d4sv3-z2 \
    --resource-group rg-poc-capacity-eus2 \
    --sku Standard_D4s_v3 --capacity 4 --zone 2 \
    --subscription poc-provider-sub

Step 2 — Configure sharing profile for poc-dr-sub
  PUT crg-poc-dr-eus2 with sharingProfile = [poc-dr-sub]

Step 3 — Complete RBAC setup for DR consumer
  [Three-step RBAC process for poc-dr-sub]

Step 4 — Verify DR CR is provisioned and standing by
  GET cr-poc-dr-d4sv3-z2; confirm quantity=4, allocated=0
  Confirm Provider quota consumed: +16 vCPU in East US 2

Step 5 — Simulate steady-state wait — DR CRG remains at allocated=0
  Record: Provider is paying for unused DR reserved capacity
  Document: cost implication of pre-positioned capacity model

Step 6 — Measure failover deployment time
  Start timer
  Deploy 4 VMs from poc-dr-sub against crg-poc-dr-eus2 (simulated failover)
  Stop timer when all 4 VMs reach Running state
  Record: deployment time to 4 running VMs with pre-positioned capacity
```

**Expected Results:**

- DR CRG and CR created successfully with sharing profile for poc-dr-sub
- DR CR stands at quantity=4, allocated=0 in steady state (pre-positioned)
- Provider pays for unused DR reserved capacity during steady state
- On failover trigger (Step 6): 4 VMs deploy against pre-positioned capacity
- Deployment time is consistent — no capacity acquisition delay (capacity pre-positioned)

**Validation Criteria:**

```
✓ DR CR provisioned: quantity=4, allocated=0
✓ Provider quota shows +16 vCPU for DR reservation
✓ All 4 failover VMs reach Running state in Step 6
✓ CR allocated count == 4 after failover deployment
✓ Deployment time recorded for comparison with non-pre-positioned deployment
✓ No "insufficient capacity" error during failover deployment
```

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Provider quota insufficient for both primary and DR CRGs | High | High | Request quota increase for both CRGs before POC; 24-72h lead time |
| Zone 2 mapping for poc-dr-sub not resolved | Medium | High | Complete zone mapping discovery (POC-20 equivalent for DR sub) |
| Physical capacity unavailable in DR zone at CR creation | Medium | High | Attempt CR creation in Zone 1 or Zone 3 as alternative |

---

### POC-26 — Failover VM Deployment Against Pre-Positioned Shared Capacity

**Objective:** Simulate a controlled failover event — DR subscription deploys VMs against pre-positioned shared CRG capacity. Validate deployment speed, capacity guarantee, and the end-to-end failover VM lifecycle against shared reserved capacity.

**Azure Resources Required:**

| Resource | Subscription | Details |
|---|---|---|
| DR CRG (pre-existing) | poc-provider-sub | `crg-poc-dr-eus2` from POC-25 |
| VMs (4 failover VMs) | poc-dr-sub | `vm-poc-dr-01` through `vm-poc-dr-04` |

**Preconditions:**

- POC-25 complete; DR CRG at quantity=4, allocated=0
- Zone mapping for poc-dr-sub and poc-provider-sub Zone 2 resolved
- poc-dr-sub quota sufficient for 4 × Standard_D4s_v3

> **Engine Note:** This test validates the Azure capacity pre-positioning layer. In production, POC-25 state would be established during onboarding. DR failover (POC-26) is engine-triggered only when `engine_mode == DR_EVENT_ACTIVE` (see POC-46).

**Execution Steps:**

```
Step 1 — Record pre-failover state
  DR CR: quantity=4, allocated=0
  Record timestamp T0 (failover trigger)

Step 2 — Deploy all 4 failover VMs simultaneously
  [Run in parallel — 4 concurrent az vm create commands]
  az vm create --name vm-poc-dr-01 --size Standard_D4s_v3 \
    --zone <dr-sub-zone-mapping-zone2-equivalent> \
    --capacity-reservation-group .../crg-poc-dr-eus2 \
    --subscription poc-dr-sub ...

  [repeat for vm-poc-dr-02, 03, 04]

Step 3 — Record timestamps for each VM reaching Running state
  T1 = vm-poc-dr-01 Running
  T2 = vm-poc-dr-02 Running
  ...
  Record: total failover time = max(T1..T4) - T0

Step 4 — Verify CR fully consumed post-failover
  GET CR; assert quantity=4, allocated=4

Step 5 — Attempt to deploy a 5th VM (over-capacity test)
  Deploy vm-poc-dr-05 against DR CRG
  Record: success (overallocated) or failure

Step 6 — Simulate failback — deallocate all DR VMs
  az vm deallocate vm-poc-dr-01 through 04
  GET CR; confirm allocated=0

Step 7 — Record failback state
  DR CR: quantity=4, allocated=0 (capacity reserved, ready for next failover)
  Provider continues paying for reserved but unused capacity
```

**Expected Results:**

- 4 DR VMs deploy in parallel against pre-positioned shared capacity
- No capacity acquisition delay — VMs reach Running state faster than non-reserved deployment
- CR fully consumed (quantity=4, allocated=4) after all 4 VMs start
- 5th VM deployment: enters overallocated state (if platform allows) or fails
- After failback: CR returns to allocated=0 but quantity=4 retained (capacity held for future failover)

**Validation Criteria:**

```
✓ All 4 failover VMs reach Running state
✓ CR allocated == 4 after all 4 VMs running
✓ Failover deployment time recorded (key POC metric)
✓ 5th VM behavior documented (overallocated or blocked)
✓ Failback: CR allocated == 0 after deallocation
✓ CR quantity unchanged by failback — capacity retained for next failover
```

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Parallel VM deployments throttled — ARM rate limiting | Medium | Low | Retry failed deployments; document as operational consideration |
| Zone mapping error causes one or more VMs to target wrong zone | Medium | High | Validate zone mapping before Step 2; deploy one VM first to confirm zone |
| Failover time metric not meaningful due to test environment conditions | Low | Low | Run 3 times and average; note test environment caveat in findings |
| Without engine_mode validation (POC-46), the DR failover trigger path is incomplete in the ACRME engine | High | High | Treat POC-26 as validating the ARM layer only; the engine-triggered path is validated by POC-46 (engine_mode) and Section 10 |

---

### POC-27 — Capacity Reallocation — Primary to DR Zone (Controlled Shift)

**Objective:** Validate the workflow for intentionally shifting capacity from a primary CRG to a DR CRG — reducing quantity in the primary CR and increasing quantity in the DR CR — to reallocate physical capacity reservation from one zone to another.

**Azure Resources Required:**

| Resource | Subscription | Details |
|---|---|---|
| Primary CR | poc-provider-sub | `cr-poc-d4sv3-z1` — Zone 1 — quantity=4 |
| DR CR | poc-provider-sub | `cr-poc-dr-d4sv3-z2` — Zone 2 — quantity=4 |

**Preconditions:**

- Primary VMs deallocated (CR allocated=0) for this test
- DR CR at quantity=4, allocated=0
- Provider has quota for both CRs simultaneously (sum total)

**Execution Steps:**

```
Step 1 — Record baseline quota state
  Provider DSv3 quota: total consumed = (primary quantity + DR quantity) × 4 vCPU

Step 2 — Reduce primary CR quantity from 4 to 0
  az capacity reservation update \
    --name cr-poc-d4sv3-z1 --capacity 0 \
    --capacity-reservation-group-name crg-poc-primary-eus2 \
    --subscription poc-provider-sub
  Record: provisioningState, quota delta

Step 3 — Re-query Provider quota after primary CR reduction
  Confirm: -16 vCPU (4 × D4s_v3 released from primary)

Step 4 — Increase DR CR quantity from 4 to 8 (using released quota)
  az capacity reservation update \
    --name cr-poc-dr-d4sv3-z2 --capacity 8 \
    --capacity-reservation-group-name crg-poc-dr-eus2 \
    --subscription poc-provider-sub
  Record: provisioningState, quota delta

Step 5 — Re-query Provider quota after DR CR increase
  Confirm: +16 vCPU consumed (shifted from primary to DR)
  Net quota: same as baseline (reallocation, not addition)

Step 6 — Deploy 8 DR VMs to validate expanded DR capacity
  [Deploy 8 VMs from poc-dr-sub against crg-poc-dr-eus2]
  Confirm: all 8 VMs reach Running state with SLA coverage

Step 7 — Restore — reduce DR CR to 4, restore primary CR to 4
  [Reverse the steps; redeploy primary VMs if needed]
```

**Expected Results:**

- Primary CR quantity reduction releases quota immediately
- DR CR quantity increase uses released quota successfully
- Net Provider quota unchanged (reallocation)
- Expanded DR capacity (8 CRs) accepts 8 VM deployments
- Physical capacity reallocation between zones observed via quota tracking

**Validation Criteria:**

```
✓ Primary CR quantity=0 reduces Provider quota by 16 vCPU
✓ DR CR quantity=8 increases Provider quota by 16 vCPU
✓ Net Provider quota unchanged from baseline
✓ 8 DR VMs deploy successfully against expanded DR CR
✓ DR CR allocated=8, quantity=8 (no overallocation)
```

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Physical capacity unavailable for DR CR expansion to quantity=8 | Medium | High | Test with quantity increase of 2 initially; confirm capacity before full expansion |
| Quota delta does not match expected calculation | Low | Medium | Verify quota tracking methodology is per-vCPU not per-instance |

---

### POC-28 — VMSS Zone Outage Known Issue Observation

**Objective:** Observe and document the behavior of VMSS instances associated with a shared CRG during a simulated zone-level disruption. This test targets Known Issue 1 (VMSS reprovisioning not supported during zone outage with shared CRG). Due to the inability to simulate a real Azure zone outage in a test environment, this POC documents the setup state and the expected failure mode, with steps to trigger and observe reprovisioning behavior when zone disruption can be induced.

**Azure Resources Required:**

| Resource | Subscription | Details |
|---|---|---|
| VMSS | poc-consumer-a-sub | `vmss-poc-cons-a-web` — Standard_D4s_v3 — single zone — Zone 1 |
| Shared CRG | poc-provider-sub | `crg-poc-primary-eus2` — Zone 1 CR |

**Preconditions:**

- POC-01 complete; Consumer-A in sharing profile
- Zone mapping validated for VMSS deployment
- Consumer-A has quota for 3 × Standard_D4s_v3 (VMSS initial count=3)

**Execution Steps:**

```
Step 1 — Create VMSS associated with shared CRG
  az vmss create \
    --name vmss-poc-cons-a-web \
    --resource-group rg-poc-workload-cons-a \
    --image Ubuntu2204 \
    --vm-sku Standard_D4s_v3 \
    --instance-count 3 \
    --zones <consumer-a-zone-1-equivalent> \
    --capacity-reservation-group \
      /subscriptions/<provider-sub-id>/.../crg-poc-primary-eus2 \
    --subscription poc-consumer-a-sub

Step 2 — Verify VMSS instances running and associated with shared CRG
  az vmss list-instances --name vmss-poc-cons-a-web ...
  Confirm: 3 instances in Running state
  GET CR; confirm allocated == 3 (VMSS instances consume capacity)

Step 3 — Document VMSS reprovisioning trigger options available in test environment
  Option A: Force-delete one VMSS instance (triggers automatic reprovisioning)
  Option B: Scale in then scale out (triggers reprovisioning of new instances)
  Option C: Use VMSS reimage command

Step 4 — Trigger VMSS instance reprovisioning (using available method)
  az vmss delete-instances \
    --name vmss-poc-cons-a-web \
    --instance-ids 0 \
    --resource-group rg-poc-workload-cons-a \
    --subscription poc-consumer-a-sub
  [This forces VMSS to reprovision a replacement instance]

Step 5 — Observe reprovisioning behavior
  Monitor VMSS instance count; observe whether replacement instance provisions
  Record: success, failure, partial failure, or timeout

Step 6 — Scale VMSS from 3 to 4 instances (alternative reprovisioning trigger)
  az vmss scale --new-capacity 4 ...
  Observe: new instance association with shared CRG

Step 7 — Document findings
  Does reprovisioning succeed in test environment (non-outage)?
  Record: behavior for runbook; note real zone outage behavior is untestable in POC
```

**Expected Results:**

- VMSS deploys successfully with shared CRG association (Step 1-2 should succeed)
- In non-outage reprovisioning (Steps 4-6): behavior may differ from outage scenario
- The known issue (reprovisioning failure during zone outage) cannot be fully reproduced without a real zone outage
- POC documents: VMSS setup works; reprovisioning in non-outage context observed; outage behavior documented as a known risk

**Validation Criteria:**

```
✓ VMSS initial deployment succeeds with shared CRG association
✓ CR allocated count reflects VMSS instance count
✓ Reprovisioning behavior in Steps 4-6 documented (success or failure)
✓ Known Issue risk formally documented in POC findings
✓ Recommendation: Do not use VMSS with shared CRGs in zone-critical architectures until GA
```

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Real zone outage behavior cannot be reproduced — test is partial | High | Medium | Document as known limitation; note that the VMSS known issue is documented by Microsoft |
| VMSS reprovisioning fails even in non-outage scenario | Medium | High | Document failure; investigate whether VMSS + shared CRG is stable at all |
| CR allocated count does not update correctly for VMSS instances | Medium | Medium | Monitor instanceView across VMSS scale operations |

---

### POC-29 — CRG List API Bug and ARG Workaround Validation

**Objective:** Reproduce Known Issue 2 (CRG list API returns incorrect response from Consumer subscription with no local CRG), confirm the bug is reproducible, and validate both documented workarounds.

> **Engine Cross-Reference (E07-S12 RegionalSnapshot):** The ACRME engine does not rely on this API for placement decisions — it uses the RegionalSnapshot Redis cache (E07-S12, POC-34). This POC validates the raw platform bug and the ARG workaround for operators performing manual diagnostics.

**Azure Resources Required:**

- Consumer subscription with no local CRG (`poc-consumer-b-sub` — no local CRGs created)

**Preconditions:**

- poc-consumer-b-sub has no locally created CRGs in East US 2
- poc-consumer-b-sub is in the sharing profile of `crg-poc-primary-eus2`

**Execution Steps:**

```
Step 1 — Confirm no local CRGs in poc-consumer-b-sub
  az capacity reservation group list \
    --subscription poc-consumer-b-sub
  Expected: empty list (or bug condition — incorrect response)

Step 2 — Call CRG list API from poc-consumer-b-sub (no local CRG)
  az rest --method get \
    --uri "https://management.azure.com/subscriptions/<consumer-b-sub-id>/
           providers/Microsoft.Compute/capacityReservationGroups?api-version=2024-03-01"
  Record: response (expected: empty or incorrect — known bug)

Step 3 — Call Azure Resource Graph from poc-consumer-b-sub
  az graph query \
    --subscriptions <consumer-b-sub-id> \
    --graph-query "resources | where type == 
                   'microsoft.compute/capacityreservationgroups'"
  Record: response — ARG should return shared CRGs accessible to Consumer-B

Step 4 — Compare results: CRG list API vs ARG query
  Document: which shows the shared CRG?

Step 5 — Apply Workaround 1 — create local CRG in Consumer-B
  az capacity reservation group create \
    --name crg-poc-local-cons-b \
    --resource-group rg-poc-workload-cons-b \
    --location eastus2 \
    --subscription poc-consumer-b-sub
  [No CRs needed — just the CRG object]

Step 6 — Re-call CRG list API from Consumer-B after local CRG created
  az rest --method get ... (same as Step 2)
  Record: does list API now return correct results (including shared CRGs)?

Step 7 — Delete local dummy CRG and confirm bug returns
  az capacity reservation group delete crg-poc-local-cons-b ...
  Re-call list API; confirm bug returns (if observable)
```

**Expected Results:**

- Step 2: CRG list API returns empty or incorrect response (Known Issue 2 reproduced)
- Step 3: ARG query correctly returns shared CRGs accessible to Consumer-B
- Step 5 + Step 6: After creating local dummy CRG, list API returns correct results
- Step 7: Bug may return after deleting dummy CRG

**Validation Criteria:**

```
✓ Known Issue 2 reproduced in Step 2 (or documented as not reproducible)
✓ ARG workaround (Step 3) returns correct results
✓ Workaround 1 (local dummy CRG) restores list API behavior in Step 6
✓ Results recorded for operational runbook recommendation
✓ ARG query documented as recommended Consumer-side CRG discovery mechanism
```

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Bug may have been fixed in current preview build | Medium | Low | Document if not reproducible; confirms improvement |
| ARG query requires permissions not held by Consumer-B | Low | Medium | Grant Reader on shared CRG to Consumer-B before ARG test |

---

## Section 7 — Quota Group Management (Two-Group Model)

**Section Objective:** Validate that the `Microsoft.Quota/groupQuotas` API is available in the target region, that two quota groups can be created and managed (one Prod, one NonProdDR), that releasing a member subscription's CR quantity returns quota to the group pool, and that quota increase requests can be targeted at the group level rather than individual subscriptions. These tests directly validate the foundational assumptions of the ACRME engine's quota architecture.

**Architecture Context:** The design establishes two quota groups per region:
- **Prod Quota Group**: Contains `poc-provider-sub`. Backs Prod CRG reservations only.
- **NonProd+DR Quota Group**: Contains `poc-consumer-a-sub` (NonProd role) + `poc-dr-sub` (DR role). Backs NonProd CRG + DR CRG. Includes an engine-enforced DR floor protecting DR quota within the shared group.

**Facts Basis:** ACRME multi_region_placement_design.md (Quota Group Architecture section); design decisions D6, D7. All behaviors in this section are `[Derived]` until validated — these tests are the primary mechanism by which derived assumptions are promoted to `[Tested]`.

> **Engine Cross-Reference:** The POC-30 through POC-33 tests validate the Azure API layer. The engine's use of these APIs is specified in the Quota Group Architecture section of `multi_region_placement_design.md` (D6/D7). Engineering stories E03-S09 and E03-S10 implement the Quota Sync Worker that populates these fields — those stories are gated on POC-30 passing.

**Prerequisites:** GP-06 complete — Microsoft.Quota registered in all POC subscriptions; groupQuotas resource type confirmed available in East US 2; POC group topology documented; quota CLI extension installed.

**Distinction from Section 2 (Quota Interaction):** Section 2 tests validate **per-subscription quota** behavior at the `Microsoft.Capacity/serviceLimits` layer — Provider quota for CR creation, Consumer quota for VM deployment. Section 7 tests validate the **group quota** layer at `Microsoft.Quota/groupQuotas` — the pool management, cross-subscription sharing, and DR floor enforcement that sit on top of per-subscription quota. Both layers are real, both are required, and they are additive not conflicting.

---

### POC-30 — Quota Group GA Availability and Registration Validation

**Objective:** Confirm that `Microsoft.Quota/groupQuotas` is available (GA or preview) in East US 2. Create one Prod Quota Group (poc-provider-sub member) and one NonProdDR Quota Group (poc-consumer-a-sub + poc-dr-sub members). Confirm group-level limit and used vCPU fields are correctly reported. This is the gate test — if it fails, POC-31 through POC-33 cannot proceed.

**Azure Resources Required:**

| Resource | Scope | Details |
|---|---|---|
| Quota Group (Prod) | Management Group or Tenant | `qg-poc-prod-eus2` — member: poc-provider-sub |
| Quota Group (NonProdDR) | Management Group or Tenant | `qg-poc-nonprod-dr-eus2` — members: poc-consumer-a-sub, poc-dr-sub |

**Preconditions:**
- GP-06 Steps 1–5 complete
- Tenant ID recorded from GP-06 Step 5
- Management Group or Tenant-level RBAC sufficient for group creation confirmed

**Execution Steps:**

```
Step 1 — Confirm groupQuotas API is accessible
  az rest --method get \
    --uri "https://management.azure.com/providers/Microsoft.Quota/groupQuotas?api-version=2023-06-01-preview"
  Record: HTTP status code, response body
  Expected: 200 with groupQuotas list (may be empty — confirms endpoint exists)
  Failure: 404 = API not available in this tenant/region; escalate before proceeding

Step 2 — Create Prod Quota Group
  az rest --method put \
    --uri "https://management.azure.com/providers/Microsoft.Management/managementGroups/<mgmt-group-id>/
           providers/Microsoft.Quota/groupQuotas/qg-poc-prod-eus2?api-version=2023-06-01-preview" \
    --body '{
      "properties": {
        "displayName": "POC Prod Quota Group - East US 2",
        "additionalAttributes": {
          "groupId": {
            "groupingIdType": "BillingId"
          },
          "environment": "Production"
        }
      }
    }'
  Record: HTTP status, provisioningState

Step 3 — Add poc-provider-sub to Prod Quota Group
  az rest --method put \
    --uri "https://management.azure.com/providers/Microsoft.Management/managementGroups/<mgmt-group-id>/
           providers/Microsoft.Quota/groupQuotas/qg-poc-prod-eus2/
           groupQuotaSubscriptions/<poc-provider-sub-id>?api-version=2023-06-01-preview"
  Record: HTTP status, subscriptionState

Step 4 — Create NonProdDR Quota Group
  az rest --method put \
    --uri "https://management.azure.com/providers/Microsoft.Management/managementGroups/<mgmt-group-id>/
           providers/Microsoft.Quota/groupQuotas/qg-poc-nonprod-dr-eus2?api-version=2023-06-01-preview" \
    --body '{
      "properties": {
        "displayName": "POC NonProd+DR Quota Group - East US 2",
        "additionalAttributes": {
          "groupId": { "groupingIdType": "BillingId" },
          "environment": "NonProduction"
        }
      }
    }'

Step 5 — Add poc-consumer-a-sub and poc-dr-sub to NonProdDR group
  [Repeat PUT groupQuotaSubscriptions for each sub-id]

Step 6 — Request group-level quota allocation (Standard DSv3 family)
  az rest --method put \
    --uri "https://management.azure.com/providers/Microsoft.Management/managementGroups/<mgmt-group-id>/
           providers/Microsoft.Quota/groupQuotas/qg-poc-prod-eus2/
           resourceProviders/Microsoft.Compute/groupQuotaLimits/standardDSv3Family?api-version=2023-06-01-preview" \
    --body '{"properties": {"limit": 128, "comment": "POC-30 Prod group quota"}}'

  [Repeat for NonProdDR group with limit: 80]

Step 7 — GET group quota limits; observe group_limit and group_used fields
  az rest --method get \
    --uri "https://management.azure.com/providers/Microsoft.Management/managementGroups/<mgmt-group-id>/
           providers/Microsoft.Quota/groupQuotas/qg-poc-prod-eus2/
           resourceProviders/Microsoft.Compute/groupQuotaLimits/standardDSv3Family?api-version=2023-06-01-preview"
  Record: properties.limit, properties.value (used), observed field names

Step 8 — Document exact API version, endpoint paths, and field names for engine implementation
  These are the authoritative values for E03-S09 and E03-S10 story implementation.
```

**Expected Results:**
- Step 1 returns 200 (API available); any non-404 confirms endpoint exists
- Both groups created with `provisioningState: Succeeded`
- Both subscriptions added to their respective groups
- Group quota limits accepted (128 vCPU Prod, 80 vCPU NonProdDR)
- GET returns `limit` and `value` (or equivalent used field) — document exact field names

**Validation Criteria:**

```
✓ Step 1 HTTP status ≠ 404  (API exists in tenant)
✓ Both group PUT operations return provisioningState == Succeeded
✓ Both subscription memberships confirmed via GET groupQuotaSubscriptions
✓ Group quota limit fields populated correctly
✓ group_used == 0 (no CRs created yet in group context)
✓ API version, endpoint structure, and exact field names documented for E03-S09/S10
```

**Failure Paths:**

| Failure | Classification | Action |
|---------|---------------|--------|
| Step 1 returns 404 | `[Tested — Feature Not Available]` | Quota Groups not accessible in this tenant config. Escalate to Azure Support. POC-31–33 blocked. Document as blocker for D6 architecture decision. |
| Group creation requires Tenant Root scope (not Management Group) | `[Tested — Scope Restriction]` | Retry at tenant root. If Global Admin role required, document as operational constraint for production. |
| Subscription add to group fails with permission error | `[Tested — RBAC Restriction]` | Document required role; update GP-06 Step 5 warning |
| Quota limit request requires approval (async) | `[Tested]` | Record approval workflow; impacts E03-S14 design for quota increase requests |

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| API version `2023-06-01-preview` not available — GA version different | Medium | High | Try `2024-01-01` or latest; check `az provider show` for current versions |
| Management Group scope not available in POC tenant | Medium | High | Create Management Group in POC tenant first; or use Tenant Root scope |
| Group quota requires EA or MCA billing agreement | Medium | High | Validate billing account type compatibility; document if restricted to specific agreement types |

---

### POC-31 — NonProdDR Group Decomposition and Quota Release Validation

**Objective:** With the NonProdDR group containing both `poc-consumer-a-sub` (NonProd role) and `poc-dr-sub` (DR role), validate that the group's `group_used` correctly sums the per-subscription consumption. Then create a CR in the NonProd role subscription, reduce its quantity to zero, and confirm that the released quota returns to the **group pool** (not just to the subscription), making it immediately available for a DR role subscription to consume. This directly validates the Tier 3 Emergency Capacity Transfer's quota-neutral claim.

> **Blocker Cross-Reference (B-2):** POC-31 validates the Azure platform behavior that underpins **Blocker B-2 (Tier 2 quota-neutral transfer claim)**. The finding from this test directly determines whether the ACRME Tier 2 Emergency Transfer path (POC-49) is viable. If POC-31 Step 5 (quota release observation) fails, B-2 is confirmed as a critical architecture risk requiring redesign of Tier 2.

**Azure Resources Required:**

| Resource | Subscription | Details |
|---|---|---|
| NonProdDR Quota Group (pre-existing) | Group | `qg-poc-nonprod-dr-eus2` from POC-30 |
| CR (NonProd role) | poc-consumer-a-sub | `cr-poc-nonprod-d4sv3-z1` — quantity: 4 |
| CR (DR role) | poc-dr-sub | `cr-poc-dr-d4sv3-z1` — quantity: 2 (will expand to 6 after release) |

**Preconditions:**
- POC-30 complete — both quota groups exist with correct members
- POC-13 (Path B disassociation) validated — understand zero-size CR behavior
- Sufficient group quota to cover both CRs (4 + 2 = 6 VMs × 4 vCPU = 24 vCPU < 80 vCPU group limit)

**Execution Steps:**

```
Step 1 — Baseline: GET group quota state before any CRs
  GET qg-poc-nonprod-dr-eus2 groupQuotaLimits/standardDSv3Family
  Record: group_limit (80 vCPU), group_used (expected: 0)
  GET each member subscription vCPU usage (az vm list-usage)
  Record: poc-consumer-a-sub.used, poc-dr-sub.used

Step 2 — Create NonProd role CR in poc-consumer-a-sub (qty=4 → 16 vCPU consumed)
  az capacity reservation create \
    --capacity-reservation-group-name <nonprod-crg-name> \
    --name cr-poc-nonprod-d4sv3-z1 \
    --resource-group <nonprod-rg> \
    --sku Standard_D4s_v3 --capacity 4 --zone 1 \
    --subscription poc-consumer-a-sub

Step 3 — Create DR role CR in poc-dr-sub (qty=2 → 8 vCPU consumed)
  az capacity reservation create \
    --capacity-reservation-group-name <dr-crg-name> \
    --name cr-poc-dr-d4sv3-z1 \
    --resource-group <dr-rg> \
    --sku Standard_D4s_v3 --capacity 2 --zone 1 \
    --subscription poc-dr-sub

Step 4 — Observe group_used after both CRs
  GET qg-poc-nonprod-dr-eus2 groupQuotaLimits/standardDSv3Family
  Record: group_used
  EXPECTED: group_used = (4+2) × 4 = 24 vCPU
  Verify decomposition: poc-consumer-a.used = 16 vCPU, poc-dr.used = 8 vCPU

Step 5 — Reduce NonProd CR quantity to 0 (Path B — VMs keep running if any, lose SLA)
  az capacity reservation update \
    --capacity-reservation-group-name <nonprod-crg-name> \
    --name cr-poc-nonprod-d4sv3-z1 \
    --capacity 0 \
    --resource-group <nonprod-rg> \
    --subscription poc-consumer-a-sub
  Record: timestamp of operation completion (T_release)

Step 6 — Immediately GET group quota state; measure propagation latency
  Poll GET qg-poc-nonprod-dr-eus2 every 10 seconds
  Record: time until group_used reflects the released 16 vCPU
  Expected: group_used drops from 24 → 8 vCPU (DR role still consuming 8)
  CRITICAL: Record exact elapsed time from T_release to group_used update
  This latency bounds the Tier 3 RTO (DR expansion cannot proceed before quota is visible)

Step 7 — Expand DR CR quantity from 2 to 6 (consumes 16 vCPU from group pool)
  az capacity reservation update \
    --capacity-reservation-group-name <dr-crg-name> \
    --name cr-poc-dr-d4sv3-z1 \
    --capacity 6 \
    --resource-group <dr-rg> \
    --subscription poc-dr-sub
  Record: T_expand timestamp, success/failure, any errors

Step 8 — Verify final group state
  GET qg-poc-nonprod-dr-eus2
  Record: group_used (expected: 6 × 4 = 24 vCPU, same as before — quota-neutral)
  Verify: poc-consumer-a.used = 0, poc-dr.used = 24

Step 9 — Verify no Azure quota increase request was generated
  Check: no quota increase ticket was created during Steps 5–7
  This confirms the quota-neutral claim for Tier 3 Emergency Transfer
```

**Expected Results:**
- Group used correctly sums per-subscription consumption (Step 4)
- Qty=0 on NonProd CR releases quota to group pool (Step 6)
- DR CR expansion succeeds immediately from group pool — no quota increase request (Step 7)
- Net group_used unchanged before and after the transfer (quota-neutral)

**Validation Criteria:**

```
✓ Step 4: group_used == (nonprod_qty + dr_qty) × vCPU per instance
✓ Step 6: group_used decreases after NonProd qty→0
✓ Step 6: propagation latency measured and recorded (key RTO input for engine design)
✓ Step 7: DR CR expansion succeeds without quota increase request
✓ Step 8: group_used == dr_only_qty × vCPU (quota-neutral confirmed)
✓ Step 9: No Azure quota request generated during transfer
```

**Key Measurement: Quota Propagation Latency**

```
propagation_latency_seconds = T_visible - T_release

Where:
  T_release = timestamp when qty=0 PUT returns provisioningState: Succeeded
  T_visible = timestamp when group_used first reflects the reduced value

This value becomes the documented Tier 3 RTO floor:
  "The minimum observable Tier 3 Emergency Transfer time is T_propagation + T_expand_arm"
  where T_expand_arm = ARM operation time for DR CR qty increase.

If propagation_latency > 60 seconds: flag as HIGH RISK — document in engine design.
If propagation_latency > 5 minutes: flag as BLOCKER — quota group may not be suitable for Tier 3.
```

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Group_used does not reflect per-subscription decomposition correctly | Medium | High | Compare with individual sub usage; if mismatch, engine sync logic must query both layers |
| Propagation latency > 5 min | Low | Critical | Would invalidate the quota-neutral Tier 3 claim; must fall back to pre-staged quota increase requests |
| DR CR expansion fails even after group_used update | Low | High | Check ARM provisioning state; may indicate group enforces per-subscription sub-limits separately |

---

### POC-32 — DR Floor Enforcement Timing and Engine Behavior Validation

**Objective:** Validate the engine's DR floor enforcement mechanism. With the NonProdDR group sized at 80 vCPU and a DR floor of 32 vCPU (effective NonProd ceiling = 48 vCPU), attempt to expand the NonProd CR beyond the effective ceiling. Confirm the engine blocks the expansion (HC-7). Then validate that the group does not natively enforce this floor (Azure has no intra-group sub-limit mechanism) — only the engine does. Finally, measure the propagation latency for DR floor compliance status after a NonProd CR quantity change.

> **Blocker Cross-Reference (B-6 / Tier 2 RTO):** POC-32 measures the quota propagation latency that bounds **Blocker B-6** and the **Tier 2 RTO denominator**. The Step 4 latency measurement feeds directly into the RTO calculation: `Tier 2 RTO = approval_time + quota_propagation_latency(B-6) + ARM_ARM_time`. If propagation latency > 60 min, the Tier 2 design must be reconsidered.

**Preconditions:**
- POC-30 complete — NonProdDR group exists with 80 vCPU limit
- POC-31 complete — per-subscription quota decomposition and group pool behavior validated
- POC-13 (Path B) and POC-28 (VMSS zero-size) previously validated — Path B mechanics understood
- Engine HC-7 implementation in a test harness (can be a script simulating the check)

**Execution Steps:**

```
Step 1 — Establish DR floor calculation
  Scenario: 20 Prod VMs × 4 vCPU = 80 vCPU Prod allocation
  DR floor = 20 × 4 × 0.40 = 32 vCPU
  Effective NonProd ceiling = 80 - 32 = 48 vCPU
  NonProd max instances = 48 / 4 = 12 Standard_D4s_v3 VMs
  Record these values; they drive the HC-7 test thresholds

Step 2 — Create NonProd CR at quantity=11 (within effective ceiling: 11×4=44 vCPU < 48)
  az capacity reservation create \
    --name cr-poc-nonprod-floor-test \
    --capacity 11 ... --subscription poc-consumer-a-sub
  Expected: SUCCESS (44 vCPU < 48 effective ceiling)

Step 3 — Attempt NonProd CR increase to quantity=13 (WOULD exceed ceiling: 13×4=52 > 48)
  [ENGINE HC-7 CHECK — simulate in test harness:]
    projected_nonprod_vcpu = 13 × 4 = 52
    effective_nonprod_ceiling = 48
    52 > 48 → HC-7 VIOLATION → BLOCK
  Record: engine blocks the operation before submitting to ARM
  DO NOT submit qty=13 to ARM — confirm Azure would not block this independently

Step 4 — CRITICAL FINDING: Verify Azure does NOT natively block the qty=13 request
  [Temporarily bypass engine HC-7; submit qty=13 directly to ARM]
  az capacity reservation update --capacity 13 ... --subscription poc-consumer-a-sub
  Record: HTTP status, success/failure
  EXPECTED: ARM SUCCEEDS (Azure does not enforce intra-group sub-limits)
  If Azure blocks: document; this may indicate a new native enforcement feature
  [Immediately reduce back to qty=11 after observation]

Step 5 — Confirm: engine is the sole enforcer of the DR floor
  Compare Step 3 result (engine blocks) vs Step 4 result (ARM accepts)
  Document: "Azure Quota Groups do not enforce intra-group sub-limits as of [test date]"
  This confirms the Derived assumption in the architecture design

Step 6 — Measure dr_floor_compliant status update latency
  Reduce NonProd CR from qty=11 to qty=8 (32 vCPU — at ceiling edge)
  Record: T_change
  Poll engine's quota sync model: when does dr_floor_compliant flip to False then True?
  (Simulate by querying the group_used decomposition as in POC-31)
  Record: propagation latency for compliance status update

Step 7 — Verify DRFloorViolationDetected alert fires in test harness
  Set NonProd quota_used artificially to 50 (simulating violation scenario)
  Confirm: engine emits DRFloorViolationDetected alert
  Confirm: engine blocks further NonProd CRG quantity increase operations
```

**Expected Results:**
- Engine (HC-7) blocks NonProd CR increase that would exceed effective ceiling (Step 3)
- Azure ARM does NOT natively block the same request (Step 4) — confirms engine is sole enforcer
- DR floor compliance status update observed within expected latency window
- `DRFloorViolationDetected` alert fires correctly in test harness

**Validation Criteria:**

```
✓ Step 3: Engine HC-7 check blocks qty=13 increase (projected 52 > ceiling 48)
✓ Step 4: ARM accepts qty=13 directly (Azure has no native intra-group floor enforcement)
✓ Step 5: Architecture note "engine is sole enforcer" confirmed and documented
✓ Step 6: dr_floor_compliant propagation latency measured (input to monitoring alert cadence)
✓ Step 7: DRFloorViolationDetected alert fires and blocks NonProd scale operations
```

**Architecture Finding to Document:**

```
FINDING (classify based on Step 4 result):
  If ARM accepts qty=13:
    [Tested — Derived Confirmed]: Azure Quota Groups do not enforce intra-group sub-limits.
    Engine must be the sole enforcer via HC-7. Risk: engine bug bypasses enforcement.
    Mitigation: DRFloorViolationDetected alert + operator gate on NonProd CRG scale.

  If ARM blocks qty=13:
    [Tested — New Finding]: Azure Quota Groups now natively enforce sub-limits.
    Update architecture: engine HC-7 is now a secondary check; Azure provides primary enforcement.
    Investigate: how are sub-limits configured at the group level? Update E03-S09 entity model.
```

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Azure has added native sub-limit enforcement — test outcome unexpected | Low | Design Change | Document; update architecture; new finding improves safety |
| Engine HC-7 check has timing gap (stale snapshot) | Medium | High | Quota sync cycle must be ≤ 5 min; alert on stale snapshot; HC-7 reads from Redis fast path |
| dr_floor_compliant latency > reconciliation cycle | Low | Medium | Double-check sync worker trigger; alert before violation, not at violation |

---

### POC-33 — Quota Increase Targeting — Group Level vs Subscription Level

**Objective:** Validate that quota increase requests can be targeted at the group level via `POST Microsoft.Quota/groupQuotas/{id}/quota`, and that approved group-level increases are reflected in each member subscription's available quota. Confirm the correct endpoint, required fields, and approval workflow for production use in E03-S14.

> **Blocker Cross-Reference (B-5):** POC-33 validates **Blocker B-5**. The confirmed endpoint and approval workflow from Step 2–3 is the implementation reference for `E03-S14` (quota increase automation story). If the API is async with >5 min latency, the engine quota increase path is asynchronous by design and must not be used in Tier 1/2 RTO paths.

**Preconditions:**
- POC-30 complete — both quota groups exist
- POC-31 complete — group quota decomposition behavior understood
- Note: This test may trigger an actual quota increase approval workflow — keep quantities small

**Execution Steps:**

```
Step 1 — Record current group limits for both groups
  GET qg-poc-prod-eus2 groupQuotaLimits/standardDSv3Family
  GET qg-poc-nonprod-dr-eus2 groupQuotaLimits/standardDSv3Family
  Record: current limits (128 vCPU Prod, 80 vCPU NonProdDR from POC-30)

Step 2 — Submit small group-level quota increase for Prod group (+8 vCPU = 2 VMs)
  az rest --method put \
    --uri "https://management.azure.com/providers/Microsoft.Management/managementGroups/<mgmt-group-id>/
           providers/Microsoft.Quota/groupQuotas/qg-poc-prod-eus2/
           resourceProviders/Microsoft.Compute/groupQuotaLimits/standardDSv3Family?api-version=2023-06-01-preview" \
    --body '{"properties": {"limit": 136, "comment": "POC-33 group increase test +8 vCPU"}}'
  Record: HTTP status, response body, provisioningState
  Record: Is this sync (200) or async (202 + location header)?

Step 3 — If async: poll for completion
  GET <location-header-url> until provisioningState == Succeeded or Failed
  Record: total approval latency (minutes/hours — this bounds E03-S14 design)

Step 4 — After approval: verify group limit updated
  GET qg-poc-prod-eus2 groupQuotaLimits/standardDSv3Family
  Expected: limit == 136 vCPU

Step 5 — Verify increase is reflected in member subscription
  az vm list-usage --location eastus2 \
    --query "[?name.value=='standardDSv3Family']" \
    --subscription poc-provider-sub
  Record: new subscription limit
  Question: Does the subscription-level limit increase automatically when group limit increases?
  OR: Must the group limit be explicitly allocated to a specific subscription?

Step 6 — Test group-level decrease (reduce group limit by 4 vCPU back to 132)
  Submit PUT with limit: 132
  Record: success/failure; observe if ARM blocks decrease below group_used

Step 7 — Submit NonProdDR group increase (+16 vCPU) without specifying which subscription receives it
  PUT limit: 96 on qg-poc-nonprod-dr-eus2
  Record: behavior — does the increase become available to both members proportionally?
  Or must it be allocated per-subscription?

Step 8 — Document findings for E03-S14 implementation
  Endpoint pattern: [confirmed PUT or POST endpoint]
  Approval workflow: [sync vs async; latency]
  Member subscription propagation: [automatic vs manual allocation]
  Required fields: [limit, comment, justification?]
  Error response structure for exceeded requests: [document verbatim]
```

**Expected Results:**
- Group-level quota increase request accepted (200 or 202)
- Approved limit reflected in GET response
- Increased quota available to member subscriptions (auto or manual allocation)
- Decrease below group_used blocked or returns error

**Validation Criteria:**

```
✓ Step 2: PUT to groupQuotaLimits accepted without 404 (endpoint confirmed)
✓ Step 3/4: Approval latency measured (critical RTO input for Tier 3 path)
✓ Step 5: Member subscription quota change observed (document propagation behavior)
✓ Step 7: NonProdDR group increase behavior documented (allocation mechanism confirmed)
✓ Step 8: Full E03-S14 implementation reference documented
```

**Key Finding to Capture:**

```
FINDING — Approval Latency:
  If approval latency ≤ 5 minutes (sync or near-sync):
    [Tested]: Group quota increases can be used as a fast path.
    Update architecture: Tier 3 may optionally request a group increase
    instead of relying solely on pre-staged emergency_transfer_headroom_vcpu.

  If approval latency > 60 minutes (standard approval SLA):
    [Tested — Confirmed]: Pre-staged emergency_transfer_headroom_vcpu is essential.
    The group limit MUST be sized correctly at creation time.
    Tier 3 cannot rely on on-demand group increases for RTO.
```

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Group increase requires EA support ticket (not API-driven) | Medium | High | Document; means E03-S14 must create Azure Support tickets programmatically; evaluate ARM quota increase request API as alternative |
| Increase propagation to member subscriptions is manual | Medium | Medium | Document; engine must explicitly allocate group quota to subscriptions after group increase approved |
| Group decrease below group_used blocked | Low | Low | Expected behavior — confirms integrity check; document error code |

---

## Section 8 — Placement Engine Validation

**Section Objective:** Validate the ACRME Placement Engine's core logic — the RegionalSnapshot data pipeline (E03-S09/S10), Hard Constraints (HC-1 through HC-7), Placement Score formulas (PS_Prod, PS_NonProd, PS_DR), and the selection algorithm (3-region and 4-region scenarios).

> **Section Preamble Note:** Unlike Sections 1–7 (which validate Azure ARM API behavior), Section 8 validates **ACRME engine behavior** — the engine's logic acting on top of ARM APIs. These tests require the engine to be running. All engine API calls target the ACRME control plane base URL `https://acrme-engine.contoso.internal/api/v1`.

**Dependencies:** Section 8 tests require:
- ACRME engine deployed with E03-S09, E03-S10, E07-S12, E07-S13 complete
- Section 7 (Quota Group Management) validated — POC-30 passed (GP-06 gates Section 8)
- At least 3 managed regions configured in the engine (`eastus2`, `westus2`, `centralus`)

**Facts Basis:** `multi_region_placement_design.md` — RegionalSnapshot model, Hard Constraints HC-1 through HC-7, Placement Score formula section, Selection Algorithm section, worked Examples A and B.

---

### POC-34 — RegionalSnapshot Population and Quota Group Field Validation

**Objective:** Confirm that the Quota Sync Worker (E03-S09) correctly populates the Quota Group entity in Cosmos DB, and that the reconciliation loop (E03-S10, E07-S12) writes all Quota Group fields and per-CRG-type fields to the RegionalSnapshot Redis cache. This is the data pipeline gate for all scoring formulas.

**Priority:** Critical (P0 — gates all Section 8 tests)

**Blockers / Stories Validated:** E03-S09, E03-S10 (G-22); B-1 must be resolved (POC-30 passed)

**Preconditions:**
- POC-30 passed (Quota Groups exist and report limit/used vCPU)
- ACRME engine deployed with Quota Sync Worker and reconciliation loop running
- Redis and Cosmos DB read access for verification

**Execution Steps:**

```
Step 1 — Trigger the Quota Sync Worker and confirm Cosmos DB QuotaGroup entity
  # Force a sync cycle via the engine control plane
  curl -sS -X POST https://acrme-engine.contoso.internal/api/v1/admin/quota-sync/trigger \
    -H "Authorization: Bearer $ACRME_TOKEN" -H "Content-Type: application/json" \
    -d '{"region":"eastus2"}'
  # Confirm the Microsoft.Quota groupQuotas read populated the entity
  az rest --method get \
    --uri "https://management.azure.com/providers/Microsoft.Management/managementGroups/<mgmt-group-id>/providers/Microsoft.Quota/groupQuotas/qg-poc-prod-eus2/quotaLimits?api-version=2023-06-01-preview"
  Verify Cosmos DB QuotaGroup entity fields populated:
    prod_group_limit_vcpu, prod_group_used_vcpu,
    nonprod_dr_group_limit_vcpu, nonprod_dr_group_used_vcpu

Step 2 — Wait one reconciliation cycle (5 min) and inspect the RegionalSnapshot
  sleep 300
  redis-cli GET snapshot:eastus2
  Confirm the snapshot contains all 16+ Quota Group and per-CRG-type fields, including:
    prod_crg_free_slots, prod_crg_quantity, dr_crg_quantity, dr_crg_coverage_ratio,
    prod_group_headroom_vcpu, nonprod_dr_group_headroom_vcpu, potential_dr_demand,
    emergency_transfer_headroom_vcpu, snapshot_age_seconds

Step 3 — Confirm fast-path scalar keys are populated
  redis-cli GET quota:group:eastus2:prod
  redis-cli GET quota:group:eastus2:nonprod_dr
  Both must return current headroom values

Step 4 — Confirm legacy per-subscription QuotaRecord fields retained and flagged
  redis-cli GET snapshot:eastus2 | jq '.legacy_quota_records'
  Confirm legacy fields present and flagged [Legacy]

Step 5 — Inject a quota change and confirm one-cycle propagation
  # Small manual adjustment to the Prod group limit
  az rest --method patch \
    --uri "https://management.azure.com/providers/Microsoft.Management/managementGroups/<mgmt-group-id>/providers/Microsoft.Quota/groupQuotas/qg-poc-prod-eus2?api-version=2023-06-01-preview" \
    --body '{"properties":{"limit":{"value":132}}}'
  sleep 300
  redis-cli GET snapshot:eastus2 | jq '.prod_group_limit_vcpu'
  Confirm the new value (132) is reflected within one cycle
```

**Expected Results:**

- Quota Sync Worker populates the Cosmos DB QuotaGroup entity with all four group limit/used fields
- RegionalSnapshot Redis cache contains all 16+ Quota Group and per-CRG-type fields after one cycle
- Fast-path scalar keys `quota:group:{region}:prod` and `:nonprod_dr` are populated
- Legacy per-subscription QuotaRecord fields retained and flagged `[Legacy]`
- An injected quota change propagates to the RegionalSnapshot within one reconciliation cycle

**Validation Criteria:**

```
✓ Step 1: Cosmos DB QuotaGroup entity has prod/nonprod_dr limit and used vCPU fields
✓ Step 2: RegionalSnapshot Redis contains all 16+ required fields
✓ Step 3: Fast-path scalars quota:group:eastus2:prod and :nonprod_dr populated
✓ Step 4: Legacy QuotaRecord fields retained and flagged [Legacy]
✓ Step 5: Injected quota change reflected in snapshot within one cycle (5 min)
```

**Finding Target:** Confirms the data pipeline (E03-S09/S10) is complete and correct — the precondition for every scoring and Hard Constraint test in Section 8.

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Quota Sync Worker not deployed in engine build under test | Medium | Critical | Gate Section 8 on E03-S09/S10 completion; do not proceed without POC-34 pass |
| RegionalSnapshot missing per-CRG-type fields | Medium | High | File engineering defect against E07-S12; block Section 8 |
| Propagation exceeds one cycle | Medium | Medium | Measure actual propagation; adjust reconciliation interval or document longer bound |

---

### POC-35 — Hard Constraint HC-2 and HC-3 Enforcement (Capacity and Quota Floor)

**Objective:** Validate that the placement engine correctly rejects region placement when HC-2 (CAPACITY_FLOOR — minimum free slots) or HC-3 (QUOTA_FLOOR — minimum group quota headroom) are violated.

**Priority:** Critical

**Stories Validated:** E03-S10, E07-S12, E07-S13

**Preconditions:**
- POC-34 passed (RegionalSnapshot populated)
- Ability to configure a test region's capacity and quota state (test hooks or controlled CRG state)

**Execution Steps:**

```
Step 1 — Configure a region below HC-2 (capacity floor)
  Set test region westus2 so prod_crg_free_slots < HC_MIN_FREE_SLOTS
  redis-cli GET snapshot:westus2 | jq '.prod_crg_free_slots'   # confirm below floor

Step 2 — Request Prod placement to the capacity-starved region
  curl -sS -X POST https://acrme-engine.contoso.internal/api/v1/placement/evaluate \
    -H "Authorization: Bearer $ACRME_TOKEN" -H "Content-Type: application/json" \
    -d '{"customer_id":"cust-poc-01","prod_region":"westus2","workload_class":"Prod","requested_slots":1}'
  Expected: HTTP 409, error.code = HC_VIOLATED, constraint = CapacityFloorViolation

Step 3 — Configure a region below HC-3 (quota floor) but with capacity available
  Set eastus2 so prod_group_headroom_vcpu < HC_MIN_PROD_QUOTA_VCPU (but free slots OK)

Step 4 — Request Prod placement to the quota-starved region
  curl -sS -X POST https://acrme-engine.contoso.internal/api/v1/placement/evaluate \
    -H "Authorization: Bearer $ACRME_TOKEN" -H "Content-Type: application/json" \
    -d '{"customer_id":"cust-poc-02","prod_region":"eastus2","workload_class":"Prod","requested_slots":1}'
  Expected: HTTP 409, error.code = HC_VIOLATED, constraint = QuotaFloorViolation

Step 5 — Confirm evaluation order (HC-2 before HC-3)
  Configure a region violating BOTH HC-2 and HC-3
  Confirm the returned constraint name is CapacityFloorViolation (HC-2 evaluated first)
```

**Expected Results:**

- HC-2 violation returns 409 `HC_VIOLATED` / `CapacityFloorViolation`
- HC-3 violation returns 409 `HC_VIOLATED` / `QuotaFloorViolation`
- When both are violated, HC-2 is reported first (documented evaluation order)
- The error payload identifies the specific constraint name

**Validation Criteria:**

```
✓ Step 2: Capacity floor violation → 409 HC_VIOLATED / CapacityFloorViolation
✓ Step 4: Quota floor violation → 409 HC_VIOLATED / QuotaFloorViolation
✓ Step 5: HC-2 evaluated before HC-3 (order confirmed)
✓ Error payload includes the specific constraint name for operator diagnosis
```

**Finding Target:** Confirms HC-2 and HC-3 enforcement and the documented constraint evaluation order.

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| No test hook to force region below floor | Medium | High | Use controlled CRG state to drive real snapshot values below thresholds |
| Engine returns generic 409 without constraint name | Medium | Medium | File defect against E07-S13; constraint name is required for diagnostics |
| HC evaluation order undocumented | Low | Medium | Record observed order; confirm against design |

---

### POC-36 — Hard Constraint HC-6 Enforcement (DR Coverage Floor)

**Objective:** Validate that the engine rejects a DR placement when HC-6 (DR_COVERAGE_FLOOR) would be violated — i.e., when `(dr_crg_qty + nonprod_overflow) / potential_dr_demand < dr_ratio_min`.

**Priority:** Critical

**Stories Validated:** E07-S13

**Preconditions:**
- POC-34 passed
- `dr_ratio_min` policy value known (0.30)

**Execution Steps:**

```
Step 1 — Establish a region at exactly dr_ratio_min (0.30)
  Configure centralus so dr_crg_coverage_ratio == 0.30
  redis-cli GET snapshot:centralus | jq '.dr_crg_coverage_ratio'

Step 2 — Request a DR placement that would push coverage below 0.30
  curl -sS -X POST https://acrme-engine.contoso.internal/api/v1/placement/evaluate \
    -H "Authorization: Bearer $ACRME_TOKEN" -H "Content-Type: application/json" \
    -d '{"customer_id":"cust-poc-03","dr_region":"centralus","workload_class":"DR","requested_slots":2}'
  Expected: HTTP 409, error.code = HC_VIOLATED, constraint = DrCoverageFloorViolation
  Confirm error payload includes computed coverage_ratio and dr_ratio_min

Step 3 — Increase DR CRG quantity so coverage_ratio > dr_ratio_min
  # Expand the DR CRG in centralus
  az capacity reservation update --capacity-reservation-group crg-poc-dr-cus \
    --name cr-poc-dr-d4sv3-z1 --capacity 6 --resource-group rg-poc-capacity-cus
  Wait one reconciliation cycle; confirm coverage_ratio now > 0.30

Step 4 — Re-request the DR placement
  Repeat Step 2 request — confirm HTTP 200 and placement accepted
```

**Expected Results:**

- DR placement below coverage floor rejected with 409 `DrCoverageFloorViolation`
- Error payload includes both the computed `coverage_ratio` and the `dr_ratio_min` threshold
- After raising DR CRG quantity, the same placement is accepted

**Validation Criteria:**

```
✓ Step 2: Placement below floor → 409 HC_VIOLATED / DrCoverageFloorViolation
✓ Step 2: Error payload includes coverage_ratio and dr_ratio_min
✓ Step 4: After DR CRG increase, placement accepted (HTTP 200)
```

**Finding Target:** Confirms HC-6 DR coverage floor enforcement and that the error payload supports operator diagnosis.

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| potential_dr_demand computed incorrectly (see POC-23) | Medium | High | Validate POC-23 finding first; coverage ratio depends on accurate demand |
| Coverage ratio rounding causes boundary ambiguity | Medium | Medium | Test at 0.29 and 0.31 to confirm strict inequality behavior |

---

### POC-37 — Hard Constraint HC-7 Enforcement (DR Floor Integrity on NonProd)

**Objective:** Validate that HC-7 (DR_FLOOR_INTEGRITY) correctly blocks a NonProd placement that would violate the DR floor even when the raw quota headroom (HC-3) would otherwise allow it.

**Priority:** High

**Stories Validated:** E07-S13

**Preconditions:**
- POC-34 passed
- NonProdDR group configured with a DR floor within the shared group (per POC-32)

**Execution Steps:**

```
Step 1 — Configure state where HC-3 passes but HC-7 would be violated
  NonProdDR group: raw headroom sufficient for the NonProd request (HC-3 pass)
  BUT the request would consume quota reserved by the DR floor (HC-7 fail)
  redis-cli GET snapshot:eastus2 | jq '{nonprod_dr_group_headroom_vcpu, dr_floor_vcpu}'

Step 2 — Request the NonProd placement
  curl -sS -X POST https://acrme-engine.contoso.internal/api/v1/placement/evaluate \
    -H "Authorization: Bearer $ACRME_TOKEN" -H "Content-Type: application/json" \
    -d '{"customer_id":"cust-poc-04","nonprod_region":"eastus2","workload_class":"NonProd","requested_slots":8}'
  Expected: HTTP 409, error.code = HC_VIOLATED, constraint = HC7_DrFloorIntegrityViolation
  Confirm error payload includes nonprod_headroom_after_placement

Step 3 — Confirm HC-7 evaluated after HC-3 (documented order)
  Confirm the rejection cites HC-7, proving HC-3 passed first

Step 4 — Reduce the NonProd request size until HC-7 passes
  Repeat with requested_slots reduced (e.g. 2) — confirm HTTP 200 and placement accepted
```

**Expected Results:**

- NonProd placement violating the DR floor is rejected with 409 `HC7_DrFloorIntegrityViolation`, even though HC-3 passed
- Error payload includes `nonprod_headroom_after_placement`
- HC-7 is evaluated after HC-3 (documented order)
- Reducing request size below the floor impact allows the placement

**Validation Criteria:**

```
✓ Step 2: NonProd placement → 409 HC_VIOLATED / HC7_DrFloorIntegrityViolation
✓ Step 2: Error payload includes nonprod_headroom_after_placement
✓ Step 3: HC-7 evaluated after HC-3 (order confirmed)
✓ Step 4: Reduced-size request accepted (HTTP 200)
```

**Finding Target:** Confirms HC-7 protects the DR floor within the shared NonProdDR group independently of raw quota headroom.

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| DR floor not enforced by engine (only Azure group limit) | Medium | High | Confirm POC-32 finding — Azure does not enforce intra-group sub-limits; engine must |
| HC-3/HC-7 order ambiguous | Low | Medium | Record observed order; confirm against design |

---

### POC-38 — Placement Score Formula Determinism (Same Snapshot → Same Result)

**Objective:** Validate that `PS_Prod`, `PS_NonProd`, and `PS_DR` formulas are deterministic — identical RegionalSnapshot → identical scores and region selection. Also validate that jitter logging is correct and jitter is seeded from `(customer_id, timestamp)`.

**Priority:** High

**Stories Validated:** E07-S14

**Preconditions:**
- POC-34 passed
- Ability to freeze the reconciliation loop (test hook or admin endpoint)

**Execution Steps:**

```
Step 1 — Freeze the RegionalSnapshot
  curl -sS -X POST https://acrme-engine.contoso.internal/api/v1/admin/reconciliation/pause \
    -H "Authorization: Bearer $ACRME_TOKEN" -d '{"duration_seconds":120}'

Step 2 — Issue identical placement requests twice for the same customer
  REQ='{"customer_id":"cust-poc-05","prod_region":"eastus2"}'
  R1=$(curl -sS -X POST https://acrme-engine.contoso.internal/api/v1/placement/evaluate \
    -H "Authorization: Bearer $ACRME_TOKEN" -H "Content-Type: application/json" -d "$REQ")
  R2=$(curl -sS -X POST https://acrme-engine.contoso.internal/api/v1/placement/evaluate \
    -H "Authorization: Bearer $ACRME_TOKEN" -H "Content-Type: application/json" -d "$REQ")
  Confirm R1.nonprod_region == R2.nonprod_region AND R1.dr_region == R2.dr_region

Step 3 — Confirm jitter values logged in OperationRecord
  Fetch the OperationRecord for each evaluation; confirm before_state.scores contains
  per-candidate PS values and the jitter component

Step 4 — Different customer, same snapshot — jitter may differ, determinism holds per-customer
  Issue the same request with customer_id = cust-poc-06
  Confirm scores may differ (different jitter seed) but repeating for cust-poc-06 is deterministic

Step 5 — Re-enable reconciliation and confirm snapshot update changes scores
  curl -sS -X POST https://acrme-engine.contoso.internal/api/v1/admin/reconciliation/resume \
    -H "Authorization: Bearer $ACRME_TOKEN"
  After a snapshot change, confirm scores change as expected
```

**Expected Results:**

- Two identical requests for the same customer on a frozen snapshot produce identical region selections
- Jitter values are logged in `OperationRecord.before_state.scores`
- Jitter is seeded from `(customer_id, timestamp)` — different customer may differ, but per-customer determinism holds
- Re-enabling reconciliation and changing the snapshot changes the scores

**Validation Criteria:**

```
✓ Step 2: Identical requests → identical nonprod_region and dr_region
✓ Step 3: Jitter logged in OperationRecord.before_state.scores
✓ Step 4: Per-customer determinism holds; cross-customer jitter may differ
✓ Step 5: Snapshot change alters scores as expected
```

**Finding Target:** Confirms score formula determinism and correct jitter logging — required for reproducible, auditable placement decisions.

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| No admin hook to freeze reconciliation | Medium | Medium | Issue both requests within one cycle window; document timing |
| Jitter not logged | Medium | Medium | File defect against E07-S14; jitter must be auditable |
| Timestamp component makes strict determinism impossible | Low | Medium | Confirm jitter seed granularity; determinism must hold within the seed window |

---

### POC-39 — Concurrent Placement Race Condition (B-7)

**Objective:** Validate the distributed lock or optimistic concurrency guard that prevents two concurrent `POST /placement/evaluate` calls from both passing HC-6 on the same stale snapshot and over-assigning the DR region. This validates the B-7 blocker resolution.

**Priority:** High (B-7 blocker validation)

**Blockers / Stories Validated:** B-7; E07-S15

**Preconditions:**
- POC-34 passed
- Ability to configure the DR region at exactly HC-6 minimum (one slot above the floor)

**Execution Steps:**

```
Step 1 — Configure DR region at exactly HC-6 minimum
  Set centralus so only ONE DR slot is available above the floor
  redis-cli GET snapshot:centralus | jq '.dr_crg_coverage_ratio'

Step 2 — Issue two concurrent placement requests for two different customers, same DR region
  curl -sS -X POST https://acrme-engine.contoso.internal/api/v1/placement/evaluate \
    -H "Authorization: Bearer $ACRME_TOKEN" -H "Content-Type: application/json" \
    -d '{"customer_id":"cust-poc-07","dr_region":"centralus","workload_class":"DR","requested_slots":1}' &
  curl -sS -X POST https://acrme-engine.contoso.internal/api/v1/placement/evaluate \
    -H "Authorization: Bearer $ACRME_TOKEN" -H "Content-Type: application/json" \
    -d '{"customer_id":"cust-poc-08","dr_region":"centralus","workload_class":"DR","requested_slots":1}' &
  wait
  Record both responses

Step 3 — Confirm exactly one succeeds
  Confirm one returns HTTP 200 (placement accepted)
  Confirm the other returns 409 with error.code = CapacityConflict or ConflictingPlacementRequest

Step 4 — Confirm the winner's OperationRecord shows lock acquire/release timestamps
  Fetch the successful OperationRecord; confirm lock_acquired_at and lock_released_at present

Step 5 — Confirm the loser left no partial state
  Query Cosmos DB for cust-poc-08 CustomerRegionAssignment — confirm none created
```

**Expected Results:**

- Exactly one of the two concurrent requests succeeds; the other is rejected with a conflict error
- The winner's `OperationRecord` shows lock acquisition and release timestamps
- The failed placement leaves no partial state in Cosmos DB

**Validation Criteria:**

```
✓ Step 3: Exactly one 200 success; the other 409 CapacityConflict/ConflictingPlacementRequest
✓ Step 4: Winner OperationRecord shows lock_acquired_at and lock_released_at
✓ Step 5: Loser leaves no CustomerRegionAssignment / partial Cosmos state
```

**Finding Target:** Confirms the B-7 concurrency guard prevents DR region over-assignment under concurrent load.

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Both requests succeed (guard absent/broken) | Medium | Critical | This is the B-7 failure mode — file critical defect against E07-S15; block Section 10 |
| Race window too small to hit reliably | Medium | Medium | Repeat 10× with tight concurrency; use a barrier to synchronize request start |
| Loser leaves orphaned state | Medium | High | Confirm cleanup; file defect if partial state persists |

---

### POC-40 — 3-Region Customer Assignment (End-to-End Selection Algorithm)

**Objective:** Validate the full selection algorithm for a 3-region engine configuration. Customer provides Prod region; engine selects NonProd and DR. NonProd and DR may share a region (HC-1 updated by D8). Validate all scores are computed and logged.

**Priority:** Critical

**Stories Validated:** E07-S14, E07-S16

**Preconditions:**
- POC-34 through POC-38 passed
- 3 managed regions (`eastus2`, `westus2`, `centralus`) with distinct capacity profiles matching Example A

**Execution Steps:**

```
Step 1 — Configure 3 regions with distinct capacity profiles (Example A)
  Set RegionalSnapshot values for eastus2 (R1), westus2 (R2), centralus (R3)
  to match worked Example A in multi_region_placement_design.md

Step 2 — Issue placement with prod_region = R1
  curl -sS -X POST https://acrme-engine.contoso.internal/api/v1/placement/evaluate \
    -H "Authorization: Bearer $ACRME_TOKEN" -H "Content-Type: application/json" \
    -d '{"customer_id":"cust-poc-A","prod_region":"eastus2"}'
  Record: selected nonprod_region, dr_region, and all scores

Step 3 — Confirm NonProd selected as highest PS_NonProd from {R2, R3}
  Confirm DR selected as highest PS_DR from {R2, R3} (may equal NonProd under D8)

Step 4 — Confirm CustomerRegionAssignment entity created in Cosmos DB
  Query Cosmos DB for cust-poc-A assignment; confirm fields:
    prod_region, nonprod_region, dr_region, scores, policy_id, assigned_at

Step 5 — Confirm consumer counts updated in RegionalSnapshot for selected regions
  redis-cli GET snapshot:<selected_nonprod> | jq '.nonprod_consumer_count'
  redis-cli GET snapshot:<selected_dr> | jq '.dr_consumer_count'

Step 6 — Validate against worked Example A
  Confirm the selection matches Example A's documented result
```

**Expected Results:**

- Engine selects NonProd = highest `PS_NonProd` from `{R2, R3}`
- Engine selects DR = highest `PS_DR` from `{R2, R3}` (may equal NonProd under D8)
- `CustomerRegionAssignment` created with all required fields
- RegionalSnapshot consumer counts updated for the selected regions
- Result matches worked Example A

**Validation Criteria:**

```
✓ Step 3: NonProd and DR selected by highest respective scores
✓ Step 4: CustomerRegionAssignment created with prod/nonprod/dr regions, scores, policy_id, assigned_at
✓ Step 5: Consumer counts incremented for selected NonProd and DR regions
✓ Step 6: Selection matches worked Example A
```

**Finding Target:** Confirms end-to-end 3-region selection correctness against the design's worked example.

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Result diverges from Example A | Medium | High | Diff computed scores vs Example A term-by-term; file defect against E07-S14 |
| Consumer counts not updated | Medium | Medium | Confirm reconciliation writes counts; file defect if stale |
| D8 (NonProd==DR allowed) not implemented | Medium | Medium | Confirm HC-1 update; document if engine still forces distinct regions |

---

### POC-41 — 4-Region Customer Assignment (Engine Optimal Selection)

**Objective:** Validate the full selection algorithm for a 4-region engine configuration. Customer provides Prod region (R1); engine selects optimal NonProd and DR from 3 remaining regions (R2, R3, R4). Validate that scores drive the selection correctly and that the `CustomerRegionAssignment` captures all regions.

**Priority:** High

**Stories Validated:** E07-S14, E07-S16

**Preconditions:**
- POC-40 passed
- 4 managed regions (`eastus2`, `westus2`, `centralus`, `southcentralus`) calibrated to Example B

**Execution Steps:**

```
Step 1 — Configure 4 regions with capacity profiles matching Example B
  Set RegionalSnapshot values for R1..R4 to match worked Example B

Step 2 — Issue placement with prod_region = R1 (eastus2)
  curl -sS -X POST https://acrme-engine.contoso.internal/api/v1/placement/evaluate \
    -H "Authorization: Bearer $ACRME_TOKEN" -H "Content-Type: application/json" \
    -d '{"customer_id":"cust-poc-B","prod_region":"eastus2"}'
  Record: nonprod_region, dr_region, all candidate scores

Step 3 — Confirm NonProd = highest PS_NonProd from {R2, R3, R4}
  Confirm DR = highest PS_DR from {R2, R3, R4} (may equal NonProd under D8)

Step 4 — Confirm scores for ALL candidates logged in OperationRecord (not just winner)
  Fetch OperationRecord; confirm PS values for R2, R3, R4 all present

Step 5 — Validate against worked Example B
  Confirm selection matches Example B's documented result
```

**Expected Results:**

- Engine selects NonProd and DR as the highest-scoring candidates from 3 remaining regions
- All candidate scores (not just the winner) are logged in `OperationRecord`
- `CustomerRegionAssignment` captures all regions
- Result matches worked Example B

**Validation Criteria:**

```
✓ Step 3: NonProd and DR selected by highest respective scores from {R2, R3, R4}
✓ Step 4: All candidate scores logged in OperationRecord
✓ Step 5: Selection matches worked Example B
```

**Finding Target:** Confirms 4-region optimal selection and full score transparency in the audit record.

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Result diverges from Example B | Medium | High | Diff scores term-by-term vs Example B; file defect |
| Only winner's score logged | Medium | Medium | File defect against E07-S14; all candidate scores required for audit |

---

## Section 9 — Steady State Capacity Lifecycle

**Section Objective:** Validate the ACRME Steady State Capacity Lifecycle — the non-crisis growth path. Specifically: auto-increase trigger detection, `CapacityIncreaseRequest` entity lifecycle, Phase A (approval-gated), Phase B (auto-approved), and cooldown enforcement.

> **Section Preamble Note:** Section 9 validates **ACRME engine behavior** and requires the engine running. All engine API calls target `https://acrme-engine.contoso.internal/api/v1`.

**Dependencies:** ACRME engine running with E02-S10, E05-S01 (reconciliation loop), E03-S09/S10 (quota data) complete. Section 8 (placement state) recommended before Section 9.

**Facts Basis:** `multi_region_placement_design.md` — Steady State Capacity Lifecycle section; CapacityIncreaseRequest entity; Phase A / Phase B workflow; auto-increase trigger and cooldown.

---

### POC-42 — Auto-Increase Trigger Detection — DR CRG Coverage Below Threshold

**Objective:** Validate that the reconciliation loop correctly raises a `CapacityIncreaseRequest` when `dr_crg_coverage_ratio < policy.dr_autoincrease_threshold` and `engine_mode == STEADY_STATE`.

**Priority:** Critical

**Stories Validated:** E02-S10, E05-S01

**Preconditions:**
- POC-34 passed (RegionalSnapshot populated)
- `engine_mode == STEADY_STATE` (confirm via `GET /engine/mode`)
- `policy.dr_autoincrease_threshold` configurable

**Execution Steps:**

```
Step 1 — Confirm engine_mode is STEADY_STATE
  curl -sS https://acrme-engine.contoso.internal/api/v1/engine/mode \
    -H "Authorization: Bearer $ACRME_TOKEN"
  Expect: {"engine_mode":"STEADY_STATE"}

Step 2 — Set the auto-increase threshold
  curl -sS -X PATCH https://acrme-engine.contoso.internal/api/v1/policy \
    -H "Authorization: Bearer $ACRME_TOKEN" -H "Content-Type: application/json" \
    -d '{"dr_autoincrease_threshold":0.35}'

Step 3 — Drive DR CRG coverage just below threshold (0.34)
  Adjust DR CRG state (or potential_dr_demand) so dr_crg_coverage_ratio == 0.34
  redis-cli GET snapshot:eastus2 | jq '.dr_crg_coverage_ratio'

Step 4 — Wait for next reconciliation cycle (max 5 min) and confirm the request
  sleep 300
  curl -sS "https://acrme-engine.contoso.internal/api/v1/capacity/increase-requests?region=eastus2&crg_type=DR&status=PENDING_APPROVAL" \
    -H "Authorization: Bearer $ACRME_TOKEN"
  Confirm a CapacityIncreaseRequest entity with:
    crg_type=DR, status=PENDING_APPROVAL, trigger_metric=0.34, trigger_threshold=0.35,
    target_quantity computed correctly, requested_by="engine-reconciliation-loop"

Step 5 — Confirm the alert raised
  Confirm CapacityIncreaseRequired alert emitted with correct payload
```

**Expected Results:**

- Reconciliation loop raises a `CapacityIncreaseRequest` with `status=PENDING_APPROVAL`
- Entity fields: `crg_type=DR`, `trigger_metric=0.34`, `trigger_threshold=0.35`, correct `target_quantity`, `requested_by="engine-reconciliation-loop"`
- `CapacityIncreaseRequired` alert raised with correct payload

**Validation Criteria:**

```
✓ Step 1: engine_mode == STEADY_STATE confirmed
✓ Step 4: CapacityIncreaseRequest created with all required fields
✓ Step 4: requested_by == "engine-reconciliation-loop"
✓ Step 4: target_quantity computed correctly for the deficit
✓ Step 5: CapacityIncreaseRequired alert raised
```

**Finding Target:** Confirms the auto-increase trigger detection and the CapacityIncreaseRequest creation contract.

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Trigger not raised within one cycle | Medium | High | Confirm reconciliation interval; extend wait; file defect if never raised |
| target_quantity computed incorrectly | Medium | High | Verify against the deficit formula; file defect against E02-S10 |
| Alert not emitted | Medium | Medium | Confirm alert pipeline wiring |

---

### POC-43 — Phase A Workflow — Approval-Gated CapacityIncreaseRequest

**Objective:** Validate the full Phase A approval workflow: `PENDING_APPROVAL → APPROVED → EXECUTING → COMPLETED`.

**Priority:** Critical

**Stories Validated:** E02-S10

**Preconditions:**
- POC-42 passed — a `PENDING_APPROVAL` CapacityIncreaseRequest exists
- Operator identity with approval rights available

**Execution Steps:**

```
Step 1 — Capture the pending request ID from POC-42
  REQ_ID=$(curl -sS "https://acrme-engine.contoso.internal/api/v1/capacity/increase-requests?status=PENDING_APPROVAL&crg_type=DR" \
    -H "Authorization: Bearer $ACRME_TOKEN" | jq -r '.items[0].id')

Step 2 — Operator approves the request
  curl -sS -X POST "https://acrme-engine.contoso.internal/api/v1/capacity/increase-requests/$REQ_ID/approve" \
    -H "Authorization: Bearer $OPERATOR_TOKEN" -H "Content-Type: application/json" \
    -d '{"comment":"POC-43 approval"}'
  Confirm status transitions PENDING_APPROVAL → APPROVED → EXECUTING

Step 3 — Confirm the ARM CR expansion is invoked
  Confirm PATCH /capacityReservations/{id} called with target_quantity from the request
  az rest --method get --uri "https://management.azure.com/.../capacityReservations/<dr_cr_id>?api-version=2024-03-01" \
    | jq '.sku.capacity'

Step 4 — Confirm completion
  Poll the request; confirm status → COMPLETED after ARM operation succeeds

Step 5 — Confirm RegionalSnapshot refreshed
  redis-cli GET snapshot:eastus2 | jq '{dr_crg_quantity, dr_crg_coverage_ratio}'
  Confirm dr_crg_quantity and dr_crg_coverage_ratio refreshed

Step 6 — Confirm audit trail and alert resolution
  Fetch OperationRecord; confirm approved_by (operator GUID) present
  Confirm CapacityIncreaseRequired alert resolved

Step 7 — Reject path (separate request)
  Trigger a new PENDING_APPROVAL request; operator rejects via
    POST /capacity/increase-requests/{id}/reject
  Confirm status → REJECTED, no ARM operation, alert closed
```

**Expected Results:**

- Approval drives `PENDING_APPROVAL → APPROVED → EXECUTING → COMPLETED`
- ARM CR quantity expanded to `target_quantity`
- RegionalSnapshot `dr_crg_quantity` and `dr_crg_coverage_ratio` refreshed
- `OperationRecord` written with `approved_by` (operator GUID)
- `CapacityIncreaseRequired` alert resolved
- Reject path: `status → REJECTED`, no ARM operations, alert closed

**Validation Criteria:**

```
✓ Step 2: Full state progression to EXECUTING on approval
✓ Step 3: PATCH /capacityReservations called with target_quantity
✓ Step 4: status → COMPLETED after ARM success
✓ Step 5: RegionalSnapshot dr_crg_quantity + coverage_ratio refreshed
✓ Step 6: OperationRecord shows approved_by; alert resolved
✓ Step 7: Reject path → REJECTED, no ARM op, alert closed
```

**Finding Target:** Confirms the complete Phase A approval-gated lifecycle including the reject path and audit trail.

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| ARM PATCH fails mid-execution | Medium | High | Confirm engine sets a FAILED/retry state; verify no snapshot corruption |
| approved_by not recorded | Medium | Medium | File defect against E02-S10; audit trail is mandatory |
| Alert not resolved on completion | Low | Medium | Confirm alert lifecycle wiring |

---

### POC-44 — Phase B Workflow — Auto-Approved CR Quantity Expansion

**Objective:** Validate Phase B: `policy.autoincrease_auto_approve = true` causes the engine to directly execute the CR quantity expansion without an approval gate.

**Priority:** High

**Stories Validated:** E02-S10

**Preconditions:**
- POC-42 passed (trigger detection understood)
- `policy.autoincrease_auto_approve` togglable

**Execution Steps:**

```
Step 1 — Enable auto-approve
  curl -sS -X PATCH https://acrme-engine.contoso.internal/api/v1/policy \
    -H "Authorization: Bearer $ACRME_TOKEN" -H "Content-Type: application/json" \
    -d '{"autoincrease_auto_approve":true}'

Step 2 — Trigger the DR CRG auto-increase condition (as in POC-42)
  Drive dr_crg_coverage_ratio below threshold; wait one reconciliation cycle

Step 3 — Confirm NO PENDING_APPROVAL wait — direct execution
  Fetch the request; confirm status progression:
    PENDING_APPROVAL → APPROVED (engine-policy) → EXECUTING → COMPLETED
  Confirm approved_by == "engine-policy"

Step 4 — Confirm the Info-severity alert
  Confirm CapacityAutoIncreaseExecuted alert (Severity: Info) raised
  Confirm CapacityIncreaseRequired (approval-needed) alert NOT raised

Step 5 — Phase B + quota increase needed
  Configure state so quota_increase_needed_vcpu > 0
  Confirm engine posts a group quota request and polls before expanding the CR
    (POST Microsoft.Quota/groupQuotas/{id}/quota then poll to completion)
```

**Expected Results:**

- No `PENDING_APPROVAL` wait — status flows directly to `COMPLETED`
- `approved_by == "engine-policy"`
- `CapacityAutoIncreaseExecuted` (Info) alert raised instead of `CapacityIncreaseRequired`
- When `quota_increase_needed_vcpu > 0`, engine posts a group quota request and polls before expanding the CR

**Validation Criteria:**

```
✓ Step 3: Direct progression to COMPLETED; approved_by == "engine-policy"
✓ Step 4: CapacityAutoIncreaseExecuted (Info) raised; no approval-needed alert
✓ Step 5: quota increase posted and polled before CR expansion when needed
```

**Finding Target:** Confirms Phase B auto-approved lifecycle and the quota-increase-before-expansion ordering.

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Engine expands CR before quota increase completes | Medium | High | Confirm ordering; file defect — expansion must not precede quota availability |
| Auto-approve applied when policy false | Low | Critical | Regression-test the gate; auto-approve must be strictly policy-driven |

---

### POC-45 — Cooldown Period Enforcement — Debounce Guard Active

**Objective:** Validate that a second `CapacityIncreaseRequest` for the same `region + CRG_type` pair is suppressed within the `autoincrease_cooldown_minutes` window (default: 30 min).

**Priority:** High

**Stories Validated:** E02-S10, E05-S01

**Preconditions:**
- POC-43 COMPLETED (a prior increase happened)
- `autoincrease_cooldown_minutes` known (default 30)

**Execution Steps:**

```
Step 1 — Immediately after POC-43 COMPLETED, drive DR CRG back below threshold
  Reduce dr_crg_coverage_ratio below the threshold again

Step 2 — Wait one reconciliation cycle; confirm NO second request within cooldown
  sleep 300
  curl -sS "https://acrme-engine.contoso.internal/api/v1/capacity/increase-requests?region=eastus2&crg_type=DR&status=PENDING_APPROVAL" \
    -H "Authorization: Bearer $ACRME_TOKEN"
  Confirm NO new CapacityIncreaseRequest created (cooldown active)

Step 3 — Confirm the debounce event
  Confirm AutoIncreaseDebounceActive event emitted (metric below threshold but cooldown active)

Step 4 — Confirm last_autoincrease_at field
  Confirm region.last_autoincrease_at reflects the POC-43 completion time

Step 5 — After cooldown expires, confirm a new request IS raised
  Wait until now > last_autoincrease_at + 30 min; wait one more cycle
  Confirm a new CapacityIncreaseRequest IS created
```

**Expected Results:**

- No second `CapacityIncreaseRequest` within the 30-min cooldown despite the metric being below threshold
- `AutoIncreaseDebounceActive` event emitted during cooldown
- `region.last_autoincrease_at` updated correctly
- After cooldown expiry, a new `CapacityIncreaseRequest` is raised

**Validation Criteria:**

```
✓ Step 2: No second request created within 30-min cooldown
✓ Step 3: AutoIncreaseDebounceActive event emitted
✓ Step 4: region.last_autoincrease_at set to POC-43 completion time
✓ Step 5: New request raised after cooldown expiry
```

**Finding Target:** Confirms the debounce guard prevents auto-increase thrashing within the cooldown window.

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Cooldown not enforced (thrashing) | Medium | High | File defect against E02-S10; thrashing wastes quota and generates alert noise |
| last_autoincrease_at not persisted | Medium | Medium | Confirm persistence; cooldown depends on it |
| 30-min wait impractical for POC | Low | Low | Temporarily set cooldown to a short value for the test; document the override |

---

## Section 10 — Emergency Capacity Transfer

**Section Objective:** Validate the ACRME Emergency Capacity Transfer system — the crisis-only path. Tests cover engine_mode state transitions, rejection outside DR events, and Tier 1 / Tier 2 / Tier 3 operations.

> **⚠ CRITICAL GATE:** POC-46 must pass before any other Section 10 test is executed. The engine_mode state machine is the guard for all Emergency Transfer operations. Section 10 is strictly sequential: POC-46 → POC-47 → POC-48 → POC-49 → POC-50 → POC-51. The engine_mode state is shared, so parallel execution creates state conflicts.

> **Section Preamble Note:** Section 10 validates **ACRME engine behavior** and requires the engine running with E08-S11 (Emergency Transfer API endpoint) complete. All engine API calls target `https://acrme-engine.contoso.internal/api/v1`.

**Dependencies:** ACRME engine running with E08-S11 complete. **B-3 (G-15) design gap must be resolved before POC-46 can be scripted.** GATE 2 (B-2 validated via POC-31) required before POC-49.

**Facts Basis:** `multi_region_placement_design.md` — Emergency Capacity Transfer section; engine_mode state machine (D10, B-3/G-15); Tier Model (Tier 1 DirectExpansion, Tier 2 QuotaNeutralTransfer, Tier 3 Destructive).

---

### POC-46 — engine_mode Declaration — STEADY_STATE → DR_EVENT_ACTIVE Transition (B-3/G-15)

**Objective:** Validate the `engine_mode` state machine. Operator declares a DR event via the ACRME control plane. Engine transitions from `STEADY_STATE` to `DR_EVENT_ACTIVE`. Confirm that the reconciliation loop's auto-increase path is suppressed during DR_EVENT_ACTIVE.

**Priority:** Critical (B-3 blocker resolution gate)

**Blockers Validated:** B-3, G-15

> **Design Gate Note:** G-15 (engine_mode state machine) design gap must be resolved before this POC can be scripted. The `engine_mode` entity must be a deployed Cosmos DB singleton with defined schema, transition APIs, and audit events. **POC-46 is the gate for all other Section 10 tests.**

**Preconditions:**
- G-15 design resolved; `engine_mode` Cosmos DB singleton deployed
- ACRME engine running with E08-S11 complete
- Operator identity with DR-declaration rights

**Execution Steps:**

```
Step 1 — Confirm starting state
  curl -sS https://acrme-engine.contoso.internal/api/v1/engine/mode \
    -H "Authorization: Bearer $ACRME_TOKEN"
  Expect: {"engine_mode":"STEADY_STATE"}

Step 2 — Declare a DR event
  curl -sS -X POST https://acrme-engine.contoso.internal/api/v1/engine/mode/declare-dr-event \
    -H "Authorization: Bearer $OPERATOR_TOKEN" -H "Content-Type: application/json" \
    -d '{"region":"eastus2","incident_id":"INC-001","declared_by":"<operator-guid>"}'
  Confirm response reflects DR_EVENT_ACTIVE

Step 3 — Confirm the Cosmos DB singleton updated
  Confirm engine_mode entity: STEADY_STATE → DR_EVENT_ACTIVE
  Record the state transition timestamp fields and singleton schema

Step 4 — Confirm the audit event
  Confirm DREventDeclared audit event logged with incident_id, declared_by, timestamp

Step 5 — Confirm auto-increase suppression during DR_EVENT_ACTIVE
  Trigger an auto-increase condition (drive DR coverage below threshold)
  Wait one reconciliation cycle
  Confirm the reconciliation loop does NOT raise a CapacityIncreaseRequest
    (suppressed by engine_mode == DR_EVENT_ACTIVE)
```

**Expected Results:**

- `GET /engine/mode` initially returns `STEADY_STATE`
- Declaring a DR event transitions the singleton to `DR_EVENT_ACTIVE`
- `DREventDeclared` audit event logged with `incident_id`, `declared_by`, `timestamp`
- Auto-increase is suppressed while `engine_mode == DR_EVENT_ACTIVE`
- engine_mode singleton schema and transition timestamp fields recorded

**Validation Criteria:**

```
✓ Step 1: Initial engine_mode == STEADY_STATE
✓ Step 2–3: Transition to DR_EVENT_ACTIVE persisted in Cosmos DB singleton
✓ Step 4: DREventDeclared audit event with incident_id, declared_by, timestamp
✓ Step 5: Auto-increase suppressed during DR_EVENT_ACTIVE
✓ engine_mode singleton schema + transition timestamp fields documented
```

**Finding Target:** Resolves B-3 by validating the engine_mode declaration mechanism and confirming it gates DR operations — the guard for all Emergency Transfer tiers.

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| G-15 design not resolved — POC-46 cannot be scripted | High | Critical | Complete G-15 design session first (GATE 5); do not script with placeholder APIs |
| Auto-increase NOT suppressed in DR mode | Medium | High | File critical defect; DR mode must suppress steady-state growth |
| Singleton contention under concurrent declarations | Low | Medium | Confirm optimistic concurrency on the singleton; test double-declare |

---

### POC-47 — Emergency Transfer Gate Enforcement — Rejection Outside DR Event

**Objective:** Validate that `POST /api/v1/capacity/emergency-transfer` is rejected when `engine_mode == STEADY_STATE`. This is the operator error protection guard.

**Priority:** Critical

**Stories Validated:** E08-S11

**Preconditions:**
- POC-46 passed (state machine understood)
- `engine_mode == STEADY_STATE` (reset from POC-46 or a clean test environment)

**Execution Steps:**

```
Step 1 — Confirm engine_mode == STEADY_STATE
  curl -sS https://acrme-engine.contoso.internal/api/v1/engine/mode \
    -H "Authorization: Bearer $ACRME_TOKEN"
  Expect: {"engine_mode":"STEADY_STATE"}

Step 2 — Attempt an emergency transfer with a valid Tier 1 body
  curl -sS -X POST https://acrme-engine.contoso.internal/api/v1/capacity/emergency-transfer \
    -H "Authorization: Bearer $OPERATOR_TOKEN" -H "Content-Type: application/json" \
    -d '{"region":"eastus2","dr_cr_id":"<dr_cr_id>","requested_slots":2,"tier_hint":1}'
  Expected: HTTP 409, error.code = EngineNotInDRMode

Step 3 — Confirm no partial state created
  Query Cosmos DB for any EmergencyCapacityTransferRequest for this call — confirm none

Step 4 — Confirm the audit event
  Confirm UnauthorizedEmergencyTransferAttempt audit event logged with caller identity
```

**Expected Results:**

- Emergency transfer rejected with 409 `EngineNotInDRMode` while in `STEADY_STATE`
- No partial state created in Cosmos DB
- `UnauthorizedEmergencyTransferAttempt` audit event logged with caller identity

**Validation Criteria:**

```
✓ Step 2: 409 EngineNotInDRMode returned
✓ Step 3: No EmergencyCapacityTransferRequest / partial state created
✓ Step 4: UnauthorizedEmergencyTransferAttempt audit event with caller identity
```

**Finding Target:** Confirms the engine_mode guard blocks emergency transfers outside a declared DR event — the operator error protection.

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Transfer accepted in STEADY_STATE | Medium | Critical | File critical defect; this is the core safety guard |
| Partial state leaked on rejection | Medium | High | Confirm transactional rejection; file defect if state persists |

---

### POC-48 — Tier 1 Emergency Transfer — DirectExpansion

**Objective:** Validate Tier 1 Emergency Transfer: `emergency_transfer_headroom_available_vcpu ≥ requested_slots × vCPU`. Fully automated — no approval gate. DR CRG quantity expanded using pre-staged headroom within the NonProdDR quota group.

**Priority:** Critical (B-2 partial — platform API behavior; POC-31 is the prerequisite)

**Stories Validated:** E08-S11

**Preconditions:**
- POC-46 passed (engine_mode = DR_EVENT_ACTIVE)
- POC-31 passed (quota group decomposition understood)
- Pre-staged headroom configured in `emergency_transfer_headroom_vcpu`

**Execution Steps:**

```
Step 1 — Confirm DR mode and pre-staged headroom
  curl -sS https://acrme-engine.contoso.internal/api/v1/engine/mode -H "Authorization: Bearer $ACRME_TOKEN"
  redis-cli GET snapshot:eastus2 | jq '.emergency_transfer_headroom_vcpu'
  Confirm engine_mode == DR_EVENT_ACTIVE and headroom >= requested_slots × vCPU

Step 2 — Record NonProd CR quantity baseline (must not change in Tier 1)
  az rest --method get --uri "https://management.azure.com/.../capacityReservations/<nonprod_cr_id>?api-version=2024-03-01" | jq '.sku.capacity'

Step 3 — Request the transfer (N slots within headroom)
  curl -sS -X POST https://acrme-engine.contoso.internal/api/v1/capacity/emergency-transfer \
    -H "Authorization: Bearer $OPERATOR_TOKEN" -H "Content-Type: application/json" \
    -d '{"region":"eastus2","dr_cr_id":"<dr_cr_id>","requested_slots":N}'
  T0 = now

Step 4 — Confirm Tier 1 path selected
  Fetch the EmergencyCapacityTransferRequest; confirm tier_selected == 1, tier_name == "DirectExpansion"

Step 5 — Confirm DR CRG quantity expanded by N
  az rest --method get --uri "https://management.azure.com/.../capacityReservations/<dr_cr_id>?api-version=2024-03-01" | jq '.sku.capacity'
  T1 = timestamp when DR CR quantity confirmed increased by N
  Confirm request status → COMPLETED and quota_neutral == true in response

Step 6 — Confirm NonProd CR quantity UNCHANGED
  Re-read NonProd CR quantity; confirm equal to Step 2 baseline (Tier 1 does not touch NonProd)

Step 7 — Measure RTO
  Record RTO = T1 - T0 (ARM propagation from request to DR CR quantity confirmed increased)
```

**Expected Results:**

- Tier 1 path selected (`tier_selected: 1`, `tier_name: DirectExpansion`)
- DR CRG quantity expanded by N via `PATCH /capacityReservations/{dr_cr_id}`
- Request `status → COMPLETED`, `quota_neutral: true`
- NonProd CR quantity unchanged
- RTO measured

**Validation Criteria:**

```
✓ Step 4: tier_selected == 1, tier_name == DirectExpansion
✓ Step 5: DR CR quantity increased by N; status COMPLETED; quota_neutral == true
✓ Step 6: NonProd CR quantity unchanged from baseline
✓ Step 7: Tier 1 RTO recorded
```

**Finding Target:** Confirms the fully-automated Tier 1 DirectExpansion path and its quota-neutral, NonProd-untouched behavior; establishes the Tier 1 RTO baseline.

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Headroom insufficient — engine escalates to Tier 2 unexpectedly | Medium | Medium | Confirm headroom >= request before the test; this test is Tier 1 only |
| NonProd CR touched in Tier 1 | Low | High | File critical defect; Tier 1 must not touch NonProd |
| DR CR expansion fails at ARM | Medium | High | Capture ARM error; confirm request enters FAILED, not COMPLETED |

---

### POC-49 — Tier 2 Emergency Transfer — QuotaNeutralTransfer

**Objective:** Validate Tier 2: Tier 1 headroom exhausted; NonProd CRG quantity reduced to 0; freed quota flows back to NonProdDR group pool; DR CRG quantity expanded using the released headroom. This validates B-2 in the operational context.

**Priority:** Critical (B-2 blocker resolution gate in engine context)

**Blockers / Stories Validated:** B-2 (engine context); E08-S11

**Preconditions:**
- POC-46 passed (engine_mode = DR_EVENT_ACTIVE)
- POC-31 passed (platform quota-neutral behavior validated)
- POC-48 passed (Tier 1 path confirmed)
- Pre-staged headroom exhausted for this test (`emergency_transfer_headroom_available_vcpu = 0`)

**Execution Steps:**

```
Step 1 — Exhaust Tier 1 headroom
  Configure emergency_transfer_headroom_available_vcpu = 0 for eastus2
  redis-cli GET snapshot:eastus2 | jq '.emergency_transfer_headroom_vcpu'   # confirm 0

Step 2 — Record NonProd CR quantity and NonProdDR group headroom baseline
  az rest --method get --uri "https://management.azure.com/.../capacityReservations/<nonprod_cr_id>?api-version=2024-03-01" | jq '.sku.capacity'
  redis-cli GET quota:group:eastus2:nonprod_dr

Step 3 — Request N slots where NonProd CRG qty→0 covers the deficit
  curl -sS -X POST https://acrme-engine.contoso.internal/api/v1/capacity/emergency-transfer \
    -H "Authorization: Bearer $OPERATOR_TOKEN" -H "Content-Type: application/json" \
    -d '{"region":"eastus2","dr_cr_id":"<dr_cr_id>","nonprod_cr_id":"<nonprod_cr_id>","requested_slots":N}'
  Fetch request; confirm tier_selected == 2, tier_name == "QuotaNeutralTransfer"

Step 4 — Approval handling
  If tier2_auto_approve == false: confirm status == PENDING_APPROVAL
    Approve: POST /capacity/increase-requests/{id}/approve (operator)
    Confirm status → EXECUTING

Step 5 — Confirm NonProd CR reduced to 0
  Confirm PATCH to quantity = 0 called on NonProd CR
  az rest --method get --uri "https://management.azure.com/.../capacityReservations/<nonprod_cr_id>?api-version=2024-03-01" | jq '.sku.capacity'   # expect 0

Step 6 — After quota propagation delay (POC-32 latency), confirm group headroom increased
  sleep <POC-32 measured propagation latency>
  redis-cli GET quota:group:eastus2:nonprod_dr   # confirm increased vs Step 2 baseline

Step 7 — Confirm DR CRG quantity expanded by N
  az rest --method get --uri "https://management.azure.com/.../capacityReservations/<dr_cr_id>?api-version=2024-03-01" | jq '.sku.capacity'
  Confirm quota_neutral == true in the response

Step 8 — Measure end-to-end Tier 2 RTO
  RTO = approval_time + quota_propagation_latency + (ARM PATCH × 2)
```

**Expected Results:**

- Tier 2 path selected (`tier_selected: 2`, `tier_name: QuotaNeutralTransfer`)
- NonProd CR quantity reduced to 0; freed quota returns to the NonProdDR group pool
- After propagation, NonProdDR group headroom increases
- DR CRG quantity expanded by N; `quota_neutral: true`
- End-to-end Tier 2 RTO measured (approval + propagation + ARM × 2)

**Validation Criteria:**

```
✓ Step 3: tier_selected == 2, tier_name == QuotaNeutralTransfer
✓ Step 4: Approval gate honored per tier2_auto_approve
✓ Step 5: NonProd CR PATCHed to quantity = 0
✓ Step 6: NonProdDR group headroom increases after propagation
✓ Step 7: DR CR expanded by N; quota_neutral == true
✓ Step 8: End-to-end Tier 2 RTO recorded
```

**Finding Target:** Resolves B-2 in the engine context — confirms the quota-neutral transfer works end-to-end and quantifies the Tier 2 RTO (bounded by POC-32 propagation latency).

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Freed quota does NOT return to group pool (B-2 fails) | Medium | Critical | If POC-31 failed, do not run POC-49; B-2 must be redesigned per change plan |
| Propagation latency > 60 min makes Tier 2 RTO infeasible | Medium | High | Use POC-32 measured latency; if excessive, escalate Tier 2 design reconsideration |
| DR CR expanded before quota available | Medium | High | Confirm engine polls group headroom before expanding DR CR |

---

### POC-50 — Tier 3 Approval Gate — Dual Approval Required

**Objective:** Validate that Tier 3 (Destructive Transfer — VM disassociation required) enforces the dual approval gate. The engine MUST NOT execute any ARM disassociation operations without two approvals from distinct operators with `ACRME.EmergencyOperator` role.

**Priority:** High (G-14 scoping — Tier 3 credential model)

**Stories Validated:** E08-S11

> **Note:** This test validates the approval gate mechanism only. Actual VM disassociation (Tier 3 Step 2) requires the **G-14 consumer credential model** to be resolved before it can be executed. Step 2 of this POC (below) is a design gate, not an execution step.

**Preconditions:**
- POC-46 passed (engine_mode = DR_EVENT_ACTIVE)
- POC-48 and POC-49 understood (Tier 1/2 exhaustion path)
- Two distinct operator identities, both with `ACRME.EmergencyOperator` role

**Execution Steps:**

```
Step 1 — Exhaust Tier 1 and Tier 2 (configure both insufficient)
  Set emergency_transfer_headroom_available_vcpu = 0 AND NonProd CR already at 0
  so neither Tier 1 nor Tier 2 can satisfy the request

Step 2 — Submit a Tier 3 request with vm_disassociation_list populated
  curl -sS -X POST https://acrme-engine.contoso.internal/api/v1/capacity/emergency-transfer \
    -H "Authorization: Bearer $OPERATOR1_TOKEN" -H "Content-Type: application/json" \
    -d '{"region":"eastus2","dr_cr_id":"<dr_cr_id>","requested_slots":N,
         "vm_disassociation_list":["<vm_id_1>","<vm_id_2>"]}'
  Confirm status == PENDING_APPROVAL (NOT EXECUTING)
  Confirm tier3_dual_approval_required == true in the request state

  # DESIGN GATE (not executed): actual VM disassociation requires the G-14
  # consumer credential model to be resolved. Do not execute disassociation in this POC.

Step 3 — First operator approves
  curl -sS -X POST "https://acrme-engine.contoso.internal/api/v1/capacity/increase-requests/<req_id>/approve" \
    -H "Authorization: Bearer $OPERATOR1_TOKEN"
  Confirm status remains PENDING_APPROVAL (awaiting second approver)

Step 4 — Second (distinct) operator approves
  curl -sS -X POST "https://acrme-engine.contoso.internal/api/v1/capacity/increase-requests/<req_id>/approve" \
    -H "Authorization: Bearer $OPERATOR2_TOKEN"
  Confirm status → APPROVED → EXECUTING
  Confirm approved_by contains BOTH operator GUIDs

Step 5 — Reject path: same operator attempts both approvals
  On a fresh Tier 3 request, OPERATOR1 approves twice
  Confirm the second approval is rejected with DualApprovalViolation
```

**Expected Results:**

- Tier 3 request enters `PENDING_APPROVAL` with `tier3_dual_approval_required: true`
- One approval keeps it `PENDING_APPROVAL`; a second distinct-operator approval moves it to `EXECUTING`
- `approved_by` contains both operator GUIDs
- Same operator approving twice is rejected with `DualApprovalViolation`
- No ARM disassociation executed in this POC (G-14 design gate)

**Validation Criteria:**

```
✓ Step 2: Tier 3 request → PENDING_APPROVAL; tier3_dual_approval_required == true
✓ Step 3: First approval keeps status PENDING_APPROVAL
✓ Step 4: Second distinct approval → APPROVED → EXECUTING; approved_by has both GUIDs
✓ Step 5: Same-operator double approval → DualApprovalViolation
✓ No ARM disassociation executed (G-14 design gate respected)
```

**Finding Target:** Confirms the Tier 3 dual-approval gate mechanism and scopes G-14 (Tier 3 consumer credential model) as the outstanding design gate before Tier 3 execution.

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Single approval advances to EXECUTING | Medium | Critical | File critical defect; dual approval is mandatory for destructive ops |
| Same operator satisfies both approvals | Medium | High | Confirm DualApprovalViolation; distinct identities are mandatory |
| Engine attempts disassociation despite G-14 unresolved | Low | High | Confirm Step 2 is a design gate; disassociation must not execute |

---

### POC-51 — engine_mode Restoration — FAILBACK_PENDING → STEADY_STATE Transition

**Objective:** Validate the engine_mode restoration path after DR event resolution. Engine transitions: `DR_EVENT_ACTIVE → FAILBACK_PENDING → STEADY_STATE`. Auto-increase loop is re-enabled.

**Priority:** High

**Stories Validated:** E08-S11

**Preconditions:**
- POC-46 passed (DR event declared; engine_mode == DR_EVENT_ACTIVE)
- Some Tier 1 or Tier 2 operations performed (POC-48 / POC-49)

**Execution Steps:**

```
Step 1 — Declare failback
  curl -sS -X POST https://acrme-engine.contoso.internal/api/v1/engine/mode/declare-failback \
    -H "Authorization: Bearer $OPERATOR_TOKEN" -H "Content-Type: application/json" \
    -d '{"region":"eastus2","incident_id":"INC-001"}'
  Confirm engine_mode → FAILBACK_PENDING

Step 2 — Confirm Emergency Transfer API now rejected in failback
  curl -sS -X POST https://acrme-engine.contoso.internal/api/v1/capacity/emergency-transfer \
    -H "Authorization: Bearer $OPERATOR_TOKEN" -H "Content-Type: application/json" \
    -d '{"region":"eastus2","dr_cr_id":"<dr_cr_id>","requested_slots":1}'
  Expected: rejection with error.code = EngineInFailbackMode

Step 3 — Execute failback operations
  Deallocate DR VMs; restore Prod region workloads
  (For Tier 2: increase NonProd CR quantity back to its pre-transfer value)

Step 4 — Resolve the DR event
  curl -sS -X POST https://acrme-engine.contoso.internal/api/v1/engine/mode/resolve-dr-event \
    -H "Authorization: Bearer $OPERATOR_TOKEN" -H "Content-Type: application/json" \
    -d '{"region":"eastus2","incident_id":"INC-001"}'
  Confirm engine_mode → STEADY_STATE

Step 5 — Confirm the audit event
  Confirm DREventResolved audit event logged

Step 6 — Confirm auto-increase re-enabled
  Trigger an auto-increase condition; wait one reconciliation cycle
  Confirm a CapacityIncreaseRequest IS raised again (loop re-enabled)

Step 7 — Confirm NonProdDR group quota headroom restored
  After NonProd CR quantity increased back (Step 3), confirm group headroom restores correctly
  redis-cli GET quota:group:eastus2:nonprod_dr
```

**Expected Results:**

- `declare-failback` transitions engine_mode to `FAILBACK_PENDING`
- Emergency Transfer API rejected with `EngineInFailbackMode` during failback
- `resolve-dr-event` transitions engine_mode to `STEADY_STATE`
- `DREventResolved` audit event logged
- Auto-increase loop re-enabled (a request is raised again after resolution)
- NonProdDR group quota headroom restores after NonProd CR quantity is increased back

**Validation Criteria:**

```
✓ Step 1: engine_mode → FAILBACK_PENDING
✓ Step 2: Emergency Transfer rejected with EngineInFailbackMode
✓ Step 4: engine_mode → STEADY_STATE
✓ Step 5: DREventResolved audit event logged
✓ Step 6: Auto-increase loop re-enabled (request raised again)
✓ Step 7: NonProdDR group headroom restored correctly
```

**Finding Target:** Confirms the full engine_mode restoration path and that steady-state operations (auto-increase) resume correctly after a DR event, closing the Emergency Transfer lifecycle.

**Risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Emergency Transfer allowed during FAILBACK_PENDING | Medium | High | File defect; failback must block new transfers |
| Auto-increase not re-enabled after resolution | Medium | High | File defect; steady-state growth must resume |
| Group headroom not restored after NonProd CR increase | Medium | Medium | Confirm quota returns to pool; verify against POC-31 behavior |

---

## Appendix A — Test Execution Log Template

For each test case, complete the following fields during execution:

```
Test ID:          [POC-XX]
Test Title:       [Full title from workbook]
Executed By:      [Name / alias]
Execution Date:   [YYYY-MM-DD]
Environment:      [Subscription names / tenant]
API Version Used: [e.g., 2024-03-01]

Pre-Test State:
  [Record all resource states before test begins]

Execution Log:
  Step 1: [Actual command run] → [Actual output summary]
  Step 2: [Actual command run] → [Actual output summary]
  ...

Deviations from Workbook:
  [Any step that could not be executed as written; reason; actual alternative]

Actual Results:
  [Paste key API responses, error messages verbatim]

Validation Criteria Met:
  ✓/✗ [Criterion 1]
  ✓/✗ [Criterion 2]
  ...

Overall Result:    PASS / FAIL / PARTIAL / BLOCKED
If FAIL:          [Root cause hypothesis; next steps]
If BLOCKED:       [Blocker description; escalation needed]

Post-Test State:
  [Confirm resources cleaned up or left for subsequent test]

Findings for POC Report:
  [Key behavioral observations; deviations from expected; risks identified]
```

---

## Appendix B — Resource Cleanup Procedure

Execute after each test section (or at end of POC). Order matters — VMs must be disassociated before CRs can be deleted; CRs must be deleted before CRGs.

```
Phase 1 — Deallocate and disassociate all VMs
  [For each Consumer subscription]
  az vm deallocate --name <vm-name> --resource-group <rg> --subscription <sub>
  az vm update --name <vm-name> --capacity-reservation-group "" ...

Phase 2 — Delete all VMs in Consumer subscriptions
  az vm delete --name <vm-name> ...

Phase 3 — Delete VMSS
  az vmss delete --name vmss-poc-cons-a-web ...

Phase 4 — Delete all Capacity Reservations (per CRG)
  az capacity reservation delete \
    --name <cr-name> \
    --capacity-reservation-group-name <crg-name> \
    --resource-group rg-poc-capacity-eus2 \
    --subscription poc-provider-sub

Phase 5 — Delete all Capacity Reservation Groups
  az capacity reservation group delete \
    --name <crg-name> \
    --resource-group rg-poc-capacity-eus2 \
    --subscription poc-provider-sub

Phase 6 — Remove RBAC assignments created during POC
  az role assignment delete --ids <assignment-id> ...

Phase 7 — Verify Provider quota returned to pre-POC baseline
  az vm list-usage --location eastus2 \
    --query "[?name.value=='standardDSv3Family']" \
    --subscription poc-provider-sub

Phase 8 — Reset engine_mode to STEADY_STATE (Sections 10 only)
  # Ensure any DR event declared during Section 10 is resolved before teardown
  curl -sS https://acrme-engine.contoso.internal/api/v1/engine/mode \
    -H "Authorization: Bearer $ACRME_TOKEN"
  # If not STEADY_STATE, declare failback then resolve:
  curl -sS -X POST https://acrme-engine.contoso.internal/api/v1/engine/mode/declare-failback \
    -H "Authorization: Bearer $OPERATOR_TOKEN" -d '{"region":"eastus2","incident_id":"INC-001"}'
  curl -sS -X POST https://acrme-engine.contoso.internal/api/v1/engine/mode/resolve-dr-event \
    -H "Authorization: Bearer $OPERATOR_TOKEN" -d '{"region":"eastus2","incident_id":"INC-001"}'
  # Confirm engine_mode == STEADY_STATE

Phase 9 — Close / archive engine lifecycle entities (Sections 9 and 10)
  # Cancel any open CapacityIncreaseRequest entities left in PENDING_APPROVAL
  for id in $(curl -sS "https://acrme-engine.contoso.internal/api/v1/capacity/increase-requests?status=PENDING_APPROVAL" \
      -H "Authorization: Bearer $ACRME_TOKEN" | jq -r '.items[].id'); do
    curl -sS -X POST "https://acrme-engine.contoso.internal/api/v1/capacity/increase-requests/$id/reject" \
      -H "Authorization: Bearer $OPERATOR_TOKEN" -d '{"comment":"POC teardown"}'
  done
  # Confirm no open EmergencyCapacityTransferRequest entities remain
  # Restore any NonProd CR quantities reduced during Tier 2/3 tests back to baseline

Phase 10 — Tear down Quota Groups (Sections 7 and 8)
  # Delete the POC Quota Groups (reverse of GP-06 / POC-30 creation)
  az rest --method delete \
    --uri "https://management.azure.com/providers/Microsoft.Management/managementGroups/<mgmt-group-id>/providers/Microsoft.Quota/groupQuotas/qg-poc-prod-eus2?api-version=2023-06-01-preview"
  az rest --method delete \
    --uri "https://management.azure.com/providers/Microsoft.Management/managementGroups/<mgmt-group-id>/providers/Microsoft.Quota/groupQuotas/qg-poc-nonprod-dr-eus2?api-version=2023-06-01-preview"
  # Confirm both groups removed (repeat for westus2/centralus/southcentralus if provisioned)

Phase 11 — Delete resource groups (if full cleanup desired)
  az group delete --name rg-poc-capacity-eus2 ...
  [Repeat for all Consumer resource groups, including rg-poc-workload-dr and poc-nonprod-sub RGs]
```

**Cleanup Verification:**

```
✓ No CRs exist in any POC CRG
✓ No CRGs exist in poc-provider-sub after cleanup
✓ No VMs in Running or Deallocated state in Consumer subscriptions
✓ Provider quota matches pre-POC baseline
✓ No outstanding RBAC assignments from POC
✓ engine_mode == STEADY_STATE (no lingering DR event)
✓ No open CapacityIncreaseRequest or EmergencyCapacityTransferRequest entities
✓ NonProd CR quantities restored to baseline (post Tier 2/3 tests)
✓ POC Quota Groups deleted in all provisioned regions
```

---

## Appendix C — Azure CLI Reference Commands

### CRG Operations

```bash
# Create CRG
az capacity reservation group create \
  --name <crg-name> --resource-group <rg> --location eastus2 \
  --zones 1 2 3 --subscription <sub-id>

# Create CR
az capacity reservation create \
  --capacity-reservation-group-name <crg> --name <cr-name> \
  --resource-group <rg> --location eastus2 \
  --sku <sku> --capacity <n> --zone <z> --subscription <sub-id>

# Update CR quantity
az capacity reservation update \
  --capacity-reservation-group-name <crg> --name <cr-name> \
  --capacity <n> --resource-group <rg> --subscription <sub-id>

# Get CR with instanceView (allocated count)
az rest --method get \
  --uri "https://management.azure.com/subscriptions/<sub>/resourceGroups/<rg>/
         providers/Microsoft.Compute/capacityReservationGroups/<crg>/
         capacityReservations/<cr>?api-version=2024-03-01&\$expand=instanceView"

# Update sharing profile
az rest --method put \
  --uri "https://management.azure.com/subscriptions/<provider-sub>/
         resourceGroups/<rg>/providers/Microsoft.Compute/
         capacityReservationGroups/<crg>?api-version=2024-03-01" \
  --body '{"location":"eastus2","properties":{"sharingProfile":{"subscriptionIds":[{"id":"/subscriptions/<consumer-sub>"}]}}}'
```

### Zone Mapping Commands

```bash
# List zone mappings for current subscription
az account list-locations \
  --query "[?name=='eastus2'].availabilityZoneMappings" --output json

# Register AvailabilityZonePeering feature
az feature register \
  --namespace Microsoft.Resources --name AvailabilityZonePeering

# Check Zone Peers API
az rest --method post \
  --uri "https://management.azure.com/subscriptions/<provider-sub>/
         providers/Microsoft.Resources/checkZonePeers/?api-version=2022-12-01" \
  --body '{"location":"eastus2","subscriptionIds":["/subscriptions/<consumer-sub>"]}'
```

### Quota Commands

```bash
# Check DSv3 quota usage
az vm list-usage --location eastus2 \
  --query "[?name.value=='standardDSv3Family'].{Name:name.localizedValue,
           Current:currentValue,Limit:limit}" \
  --subscription <sub-id>

# Check SKU availability by zone
az vm list-skus --location eastus2 --size Standard_D4s_v3 \
  --query "[].{Name:name,Zones:locationInfo[0].zones}"
```

### VM Association Commands

```bash
# Deploy VM with CRG association
az vm create --name <vm> --resource-group <rg> --size <sku> --zone <z> \
  --capacity-reservation-group <crg-resource-id> --subscription <sub>

# Update VM CRG association (deallocated VM only)
az vm update --name <vm> --resource-group <rg> \
  --capacity-reservation-group <crg-resource-id> --subscription <sub>

# Clear CRG association
az vm update --name <vm> --resource-group <rg> \
  --capacity-reservation-group "" --subscription <sub>
```

### ARG Queries

```bash
# List all CRGs accessible to Consumer subscription (workaround for Known Issue 2)
az graph query \
  --subscriptions <consumer-sub-id> \
  --graph-query "resources | where type == 
                 'microsoft.compute/capacityreservationgroups' | 
                 project name, resourceGroup, subscriptionId, 
                 properties.sharingProfile"
```

### Placement Engine API Commands

> Base URL: `https://acrme-engine.contoso.internal/api/v1`. All calls carry a bearer token: `-H "Authorization: Bearer $ACRME_TOKEN"`. Used by Section 8 (POC-34 through POC-41).

```bash
# Inspect a RegionalSnapshot (full JSON) from the Redis fast cache
redis-cli GET snapshot:eastus2 | jq '.'

# Inspect fast-path scalar quota keys (Quota Group budgets)
redis-cli GET quota:group:eastus2:prod
redis-cli GET quota:group:eastus2:nonprod_dr

# Request a placement evaluation (returns selected region + score breakdown + OperationRecord id)
curl -sS -X POST https://acrme-engine.contoso.internal/api/v1/placement/evaluate \
  -H "Authorization: Bearer $ACRME_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "customer_id": "cust-0001",
        "workload_class": "Prod",
        "requested_vcpu": 64,
        "candidate_regions": ["eastus2", "centralus", "westus2"],
        "dr_region_hint": "centralus"
      }'

# Retrieve the OperationRecord (audit trail) for a completed evaluation
curl -sS https://acrme-engine.contoso.internal/api/v1/placement/operations/$OP_ID \
  -H "Authorization: Bearer $ACRME_TOKEN" | jq '.'

# Pause the reconciliation loop (freeze snapshots for deterministic scoring tests)
curl -sS -X POST https://acrme-engine.contoso.internal/api/v1/admin/reconciliation/pause \
  -H "Authorization: Bearer $ACRME_TOKEN"

# Resume the reconciliation loop
curl -sS -X POST https://acrme-engine.contoso.internal/api/v1/admin/reconciliation/resume \
  -H "Authorization: Bearer $ACRME_TOKEN"
```

### Steady State Lifecycle Commands

> Used by Section 9 (POC-42 through POC-45). Governs `CapacityIncreaseRequest` CRUD and PlacementPolicy tuning.

```bash
# List pending CapacityIncreaseRequests (filterable by region / crg_type / status)
curl -sS "https://acrme-engine.contoso.internal/api/v1/capacity/increase-requests?region=eastus2&crg_type=DR&status=PENDING_APPROVAL" \
  -H "Authorization: Bearer $ACRME_TOKEN" | jq '.'

# Get a single CapacityIncreaseRequest by id
curl -sS https://acrme-engine.contoso.internal/api/v1/capacity/increase-requests/$REQ_ID \
  -H "Authorization: Bearer $ACRME_TOKEN" | jq '.'

# Approve a Phase A (approval-gated) request
curl -sS -X POST https://acrme-engine.contoso.internal/api/v1/capacity/increase-requests/$REQ_ID/approve \
  -H "Authorization: Bearer $ACRME_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"approver": "capacity-oncall@contoso.com", "note": "POC-43 approval"}'

# Reject a request
curl -sS -X POST https://acrme-engine.contoso.internal/api/v1/capacity/increase-requests/$REQ_ID/reject \
  -H "Authorization: Bearer $ACRME_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"approver": "capacity-oncall@contoso.com", "reason": "POC-43 negative path"}'

# Tune PlacementPolicy (thresholds, cooldown, weights) for lifecycle tests
curl -sS -X PATCH https://acrme-engine.contoso.internal/api/v1/policy \
  -H "Authorization: Bearer $ACRME_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"dr_autoincrease_threshold": 0.35, "autoincrease_cooldown_minutes": 60}'
```

### Emergency Transfer Commands

> Used by Section 10 (POC-46 through POC-51). The `engine_mode` state machine gates all `/capacity/emergency-transfer` calls.

```bash
# Read current engine_mode
curl -sS https://acrme-engine.contoso.internal/api/v1/engine/mode \
  -H "Authorization: Bearer $ACRME_TOKEN" | jq '.'

# Declare a DR event: STEADY_STATE -> DR_EVENT_ACTIVE
curl -sS -X POST https://acrme-engine.contoso.internal/api/v1/engine/mode/declare-dr-event \
  -H "Authorization: Bearer $ACRME_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"affected_region": "eastus2", "declared_by": "dr-commander@contoso.com", "incident_id": "INC-POC-46"}'

# Declare failback: DR_EVENT_ACTIVE -> FAILBACK_PENDING
curl -sS -X POST https://acrme-engine.contoso.internal/api/v1/engine/mode/declare-failback \
  -H "Authorization: Bearer $ACRME_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"declared_by": "dr-commander@contoso.com", "incident_id": "INC-POC-46"}'

# Resolve DR event: FAILBACK_PENDING -> STEADY_STATE
curl -sS -X POST https://acrme-engine.contoso.internal/api/v1/engine/mode/resolve-dr-event \
  -H "Authorization: Bearer $ACRME_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"declared_by": "dr-commander@contoso.com", "incident_id": "INC-POC-46"}'

# Tier 1 — DirectExpansion (add CR quantity into DR headroom)
curl -sS -X POST https://acrme-engine.contoso.internal/api/v1/capacity/emergency-transfer \
  -H "Authorization: Bearer $ACRME_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tier": 1, "strategy": "DirectExpansion", "target_region": "eastus2",
       "crg_type": "DR", "delta_vcpu": 128, "incident_id": "INC-POC-46"}'

# Tier 2 — QuotaNeutralTransfer (release NonProdDR budget, reallocate to DR)
curl -sS -X POST https://acrme-engine.contoso.internal/api/v1/capacity/emergency-transfer \
  -H "Authorization: Bearer $ACRME_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tier": 2, "strategy": "QuotaNeutralTransfer", "target_region": "eastus2",
       "source_group": "nonprod_dr", "delta_vcpu": 256, "incident_id": "INC-POC-46"}'

# Tier 3 — DualApprovalTransfer (requires two distinct approvers)
curl -sS -X POST https://acrme-engine.contoso.internal/api/v1/capacity/emergency-transfer \
  -H "Authorization: Bearer $ACRME_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tier": 3, "strategy": "DualApprovalTransfer", "target_region": "eastus2",
       "delta_vcpu": 512, "incident_id": "INC-POC-46",
       "approvers": ["capacity-lead@contoso.com", "vp-infra@contoso.com"]}'
```

---

## Appendix D — Test Case Index

| POC-ID | Section | Title | Priority | Status |
|---|---|---|---|---|
| POC-01 | 1 — Cross-Sub Sharing | Provider CRG Creation and Sharing Profile Configuration | Critical | Pending |
| POC-02 | 1 — Cross-Sub Sharing | Consumer VM Deployment — Happy Path | Critical | Pending |
| POC-03 | 1 — Cross-Sub Sharing | Unauthorized Consumer Rejection | Critical | Pending |
| POC-04 | 1 — Cross-Sub Sharing | Sharing Profile Modification — Add and Remove Consumer | High | Pending |
| POC-05 | 2 — Quota Interaction | Provider Quota Enforcement at CR Creation | Critical | Pending |
| POC-06 | 2 — Quota Interaction | Consumer Quota Independence — Failure with Available Capacity | Critical | Pending |
| POC-07 | 2 — Quota Interaction | Dual Quota State Observation | High | Pending |
| POC-08 | 3 — Capacity Consumption | Zero-Size Reservation Pattern | High | Pending |
| POC-09 | 3 — Capacity Consumption | Overallocation State Observation and SLA Boundary | High | Pending |
| POC-10 | 3 — Capacity Consumption | Capacity Release on CR Quantity Reduction | Medium | Pending |
| POC-11 | 4 — VM Associate/Disassociate | Running VM Direct Association Failure | Critical | Pending |
| POC-12 | 4 — VM Associate/Disassociate | Running VM Association via Deallocation — Path A | Critical | Pending |
| POC-13 | 4 — VM Associate/Disassociate | Running VM Disassociation via Zero-Size — Path B | High | Pending |
| POC-14 | 4 — VM Associate/Disassociate | Forced Unsharing with Active Consumer VMs — Silent Hazard | Critical | Pending |
| POC-15 | 4 — VM Associate/Disassociate | VMSS Instance Individual Disassociation Scoped Test (G-13) | High | Pending |
| POC-20 | 5 — AZ Requirements | Zone Mapping Discovery and Documentation | Critical | Pending |
| POC-21 | 5 — AZ Requirements | AZ Mismatch Deployment Failure | Critical | Pending |
| POC-22 | 5 — AZ Requirements | Check Zone Peers API Resolution Workflow | Critical | Pending |
| POC-16 | 5 — AZ Requirements | Zone Peers Multi-Subscription Resolution (Extends POC-22) | Medium | Pending |
| POC-25 | 6 — DR Failover | DR Capacity Pre-Positioning via Shared CRG | High | Pending |
| POC-26 | 6 — DR Failover | Failover VM Deployment Against Pre-Positioned Capacity | High | Pending |
| POC-27 | 6 — DR Failover | Capacity Reallocation — Primary to DR Zone | Medium | Pending |
| POC-28 | 6 — DR Failover | VMSS Zone Outage Known Issue Observation | High | Pending |
| POC-29 | 6 — DR Failover | CRG List API Bug and ARG Workaround Validation | Medium | Pending |
| POC-23 | 6 — DR Failover | `potential_dr_demand` Maintenance — Churn Path Validation (B-4) | High | Pending |
| POC-24 | 6 — DR Failover | RegionalSnapshot Staleness — Cosmos DB Fallback Trigger | Medium | Pending |
| POC-30 | 7 — Quota Group Management | Quota Group GA Availability and Registration Validation | Critical | Pending |
| POC-31 | 7 — Quota Group Management | NonProdDR Group Decomposition and Quota Release Validation | Critical | Pending |
| POC-32 | 7 — Quota Group Management | DR Floor Enforcement Timing and Alert Validation | Critical | Pending |
| POC-33 | 7 — Quota Group Management | Quota Increase Targeting — Group vs Subscription Level | High | Pending |
| POC-34 | 8 — Placement Engine Validation | RegionalSnapshot Population and Quota Group Field Validation | Critical | Pending |
| POC-35 | 8 — Placement Engine Validation | Hard Constraint HC-2 and HC-3 Enforcement (Capacity and Quota Floor) | Critical | Pending |
| POC-36 | 8 — Placement Engine Validation | Hard Constraint HC-6 Enforcement (DR Coverage Floor) | Critical | Pending |
| POC-37 | 8 — Placement Engine Validation | Hard Constraint HC-7 Enforcement (DR Floor Integrity on NonProd) | High | Pending |
| POC-38 | 8 — Placement Engine Validation | Placement Score Formula Determinism (Same Snapshot → Same Result) | High | Pending |
| POC-39 | 8 — Placement Engine Validation | Concurrent Placement Race Condition (B-7) | High | Pending |
| POC-40 | 8 — Placement Engine Validation | 3-Region Customer Assignment (End-to-End Selection Algorithm) | Critical | Pending |
| POC-41 | 8 — Placement Engine Validation | 4-Region Customer Assignment (Engine Optimal Selection) | High | Pending |
| POC-42 | 9 — Steady State Capacity Lifecycle | Auto-Increase Trigger Detection — DR CRG Coverage Below Threshold | Critical | Pending |
| POC-43 | 9 — Steady State Capacity Lifecycle | Phase A Workflow — Approval-Gated CapacityIncreaseRequest | Critical | Pending |
| POC-44 | 9 — Steady State Capacity Lifecycle | Phase B Workflow — Auto-Approved CR Quantity Expansion | High | Pending |
| POC-45 | 9 — Steady State Capacity Lifecycle | Cooldown Period Enforcement — Debounce Guard Active | High | Pending |
| POC-46 | 10 — Emergency Capacity Transfer | engine_mode Declaration — STEADY_STATE → DR_EVENT_ACTIVE Transition (B-3/G-15) | Critical | Pending |
| POC-47 | 10 — Emergency Capacity Transfer | Emergency Transfer Gate Enforcement — Rejection Outside DR Event | Critical | Pending |
| POC-48 | 10 — Emergency Capacity Transfer | Tier 1 Emergency Transfer — DirectExpansion | Critical | Pending |
| POC-49 | 10 — Emergency Capacity Transfer | Tier 2 Emergency Transfer — QuotaNeutralTransfer | Critical | Pending |
| POC-50 | 10 — Emergency Capacity Transfer | Tier 3 Approval Gate — Dual Approval Required | High | Pending |
| POC-51 | 10 — Emergency Capacity Transfer | engine_mode Restoration — FAILBACK_PENDING → STEADY_STATE Transition | High | Pending |

### Execution Priority

**Critical (execute first):** POC-01, POC-02, POC-03, POC-05, POC-06, POC-11, POC-12, POC-20, POC-21, POC-22, POC-14, POC-30, POC-31, POC-32, POC-34, POC-35, POC-36, POC-40, POC-42, POC-43, POC-46, POC-47, POC-48, POC-49

**High (execute after Critical):** POC-04, POC-07, POC-08, POC-09, POC-13, POC-25, POC-26, POC-28, POC-33, POC-15, POC-23, POC-37, POC-38, POC-39, POC-41, POC-44, POC-45, POC-50, POC-51

**Medium (execute if time permits):** POC-10, POC-27, POC-29, POC-16, POC-24

---

## Appendix E — Blocker Resolution Map

This map ties each engineering blocker (B-1 through B-7) to the POC(s) that resolve it and the gating relationship that governs execution order.

| Blocker | Description | Resolving POC(s) | Gate Status |
|---|---|---|---|
| B-1 | Quota Group GA availability | POC-30 | First gate — must pass before Sections 7/8 |
| B-2 | Tier 2 quota-neutral transfer claim | POC-31 (platform API), POC-49 (engine) | POC-31 gates POC-49 |
| B-3 | engine_mode declaration mechanism | POC-46 | G-15 design gap must be resolved first |
| B-4 | `potential_dr_demand` churn path | POC-23 | New test in gap slot |
| B-5 | Group quota increase endpoint | POC-33 | Parallelizable with B-1 |
| B-6 | Quota propagation latency bounds | POC-32 | Parallelizable with B-1 |
| B-7 | Concurrent placement race condition | POC-39 | Section 8 gate |

---

## Appendix F — Engineering Story POC Coverage

This table maps backlog stories (by Epic) to the POC(s) that validate them.

| Story | Epic | Description | Validating POC |
|---|---|---|---|
| E03-S09 | EPIC-03 | Quota Sync Worker — Quota Group field population | POC-34 |
| E03-S10 | EPIC-03 | RegionalSnapshot Redis — Quota Group + per-CRG-type fields | POC-34, POC-35 |
| E07-S12 | EPIC-07 | RegionalSnapshot Redis model with Quota Group fields | POC-34, POC-35 |
| E07-S13 | EPIC-07 | Hard Constraint evaluation (HC-1–HC-7) | POC-35, POC-36, POC-37 |
| E07-S14 | EPIC-07 | Placement score formulas (PS_Prod, PS_NonProd, PS_DR) | POC-38, POC-40, POC-41 |
| E07-S15 | EPIC-07 | Concurrent placement guard (B-7) | POC-39 |
| E07-S16 | EPIC-07 | PlacementPolicy extended weights and quota group fields | POC-40, POC-41 |
| E02-S10 | EPIC-02 | CapacityIncreaseRequest CRUD + lifecycle | POC-42, POC-43, POC-44, POC-45 |
| E08-S11 | EPIC-08 | Emergency Transfer API endpoint | POC-46, POC-47, POC-48, POC-49, POC-50, POC-51 |

---

*End of POC Test Workbook — Azure Capacity Reservation Management Engine (Preview)*  
*Tests validated against research findings in `azure_cr_sharing_research.md` and the architecture in `multi_region_placement_design.md`*  
*Status: `[Draft — Pending Engineering Execution]`*
