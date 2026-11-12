# ACRME Placement Engine

A Python-based placement engine mockup that implements the ACRME
**CRV → DPB** (Customer Region Vector → Domain Placement Binding)
pipeline with full selection/rejection traceability down to
availability-zone level.

## Overview

The engine processes multi-domain, multi-subscription customer
deployments through two phases:

```
┌───────────────────────────────────────────────────────┐
│  Phase 1: CRV (Customer Region Vector)              │
│  ─ Customer-scoped (same for all domain groups)      │
│  ─ Selects: R_prod, R_cval, R_dr                     │
│  ─ Hard-constraint gate → scoring → ranking           │
└───────────────────────────────────────────────────────┘
                          │
                    PLC-015 gate
                          │
┌───────────────────────────────────────────────────────┐
│  Phase 2: DPB (Domain Placement Binding)             │
│  ─ Per domain group (TMS, WMS, ...)                  │
│  ─ Assigns: subscription, CRG set, CR sizing, quota  │
│  ─ Zone-level placement with skew checks             │
└───────────────────────────────────────────────────────┘
```

### Distribution Models Supported

| Model | Geography | Prod | CVAL | DR |
|---|---|---|---|---|
| **three_region** | US | R_p | R_c (≠ R_p) | R_d (≠ R_p, ≠ R_c) |
| **two_region** | EU, AU, APAC | R_p | R_c = R_d (co-located) | R_c = R_d |
| **cross_geo_dr** | ME | R_p = R_c | R_p = R_c (same CRGs) | Europe (weighted) |

### Hard Constraints (HC-1 – HC-11)

Every candidate region must pass a hard-constraint gate before scoring.
Failed constraints are logged with the specific reason:

| HC | Description |
|---|---|
| HC-1 | Region must be in approved catalogue |
| HC-2 | Region must have target SKU availability |
| HC-3 | Per-environment capacity reservation required |
| HC-4 | Region must have ≥ 3 availability zones |
| HC-5 | Zone skew tolerance (C-13) |
| HC-6 | DR region must differ from Prod region |
| HC-7 | NonProd (CVAL) region must differ from Prod (3-region model) |
| HC-8 | Restricted-region auto-selection blocked |
| HC-9 | Quota headroom must exist for demand |
| HC-10 | Combined load must not exceed alert threshold (C-15) |
| HC-11 | Foundation DR capacity must be available |

---

## Prerequisites

- **Python 3.10+** (uses `match` statements, `dict` unions, type hints)
- No external packages needed for mock-data mode
- For Azure data collection: `pip install -r requirements.txt`

## Installation

```bash
# Clone the repository
git clone https://github.com/vishnu4573/acrme-capacity-reservation.git
cd acrme-capacity-reservation/Placement-Engine

# (Optional) Create a virtual environment
python3 -m venv .venv && source .venv/bin/activate

# (Optional) Install Azure SDK for live data collection
pip install -r requirements.txt
```

---

## Quick Start — Mock Data

```bash
# Run all three mock customers (US, EU, ME)
python run_mockup.py

# Run a single customer
python run_mockup.py --customer cust-001

# Verbose logging
python run_mockup.py -v

# Custom output file
python run_mockup.py -o my_report.md
```

The mock data includes:

| Customer | Geography | Model | Domains | Supplied Region |
|---|---|---|---|---|
| Contoso Ltd (`cust-001`) | US | three_region | TMS + WMS | westus3 (exact-region) |
| Fabrikam Inc (`cust-002`) | Europe | two_region | TMS | — (geography path) |
| Litware Corp (`cust-003`) | Middle East | cross_geo_dr | TMS | qatarcentral |

---

## Using Azure Real-Time Data

### Step 1: Pre-collect Data

```bash
# Authenticate with Azure
az login

# Collect US geography data from your subscriptions
python azure_collector.py \
    --subscriptions sub-id-1 sub-id-2 sub-id-3 \
    --geography US \
    --sku-family Dadsv5 \
    --output-dir ./data

# Collect Europe data (needed for ME cross-geo DR)
python azure_collector.py \
    -s sub-eu-1 sub-eu-2 \
    -g Europe \
    -o ./data
```

This produces timestamped JSON files in `./data/` with a `latest`
symlink for each geography.

### Step 2: Run Placement Against Azure Data

```bash
python run_mockup.py --data-dir ./data --geography US
```

### Continuous Updates

Schedule the collector via cron or an Azure Function:

```bash
# Every 30 minutes
*/30 * * * * cd /path/to/Placement-Engine && python azure_collector.py -s $SUBS -g US -o ./data
```

---

## Input Format

### Region Snapshot JSON

The collector produces (and the engine can consume) JSON in this schema:

```json
{
  "collected_at": "20261112T103000Z",
  "geography": "US",
  "sku_family": "Dadsv5",
  "subscription_ids": ["sub-1", "sub-2"],
  "regions": [
    {
      "region_id": "westus3",
      "region_name": "West US 3",
      "geography": "US",
      "classification": "standard",
      "distribution_model": "three_region",
      "availability_zones": 3,
      "auto_selectable": true,
      "prod": { "reserved": 640, "allocated": 480, "free": 160 },
      "cval": { "reserved": 320, "allocated": 200, "free": 120 },
      "dr":   { "reserved": 320, "allocated": 128, "free": 192 },
      "fnd_dr": { "reserved": 64, "allocated": 32, "free": 32 },
      "quota": {
        "prod": { "limit": 800, "used": 520 },
        "cval": { "limit": 400, "used": 220 },
        "dr":   { "limit": 400, "used": 160 }
      },
      "customers": {
        "prod": 12, "cval": 10, "dr": 8,
        "total_geography": 30
      },
      "dr_coverage": { "ratio": 0.82, "target": 1.0 },
      "zones": {
        "1": { "reserved": 220, "allocated": 160, "available": 60 },
        "2": { "reserved": 210, "allocated": 160, "available": 50 },
        "3": { "reserved": 210, "allocated": 160, "available": 50 }
      }
    }
  ]
}
```

### Customer Definition (Python)

Customers are defined as Python objects in `mock_data.py`.
To add a new customer:

```python
from models import Customer, DomainGroup

my_customer = Customer(
    customer_id="cust-new",
    customer_name="Acme Corp",
    geography="US",                       # must match region data
    supplied_prod_region="westus3",       # or None for geography path
    domain_groups=[
        DomainGroup(
            token="wl-tms",
            display_name="TMS",
            prod_vcpu_demand=64,          # vCPUs needed for Prod
            cval_vcpu_demand=32,
            dr_vcpu_demand=32,
            sku_family="Dadsv5",
            prod_subscription_id="sub-prod-001",
            cval_subscription_id="sub-cval-001",
            dr_subscription_id="sub-dr-001",
        ),
        DomainGroup(
            token="wl-wms",
            display_name="WMS",
            prod_vcpu_demand=32,
            cval_vcpu_demand=16,
            dr_vcpu_demand=16,
            sku_family="Dadsv5",
            prod_subscription_id="sub-prod-002",
            cval_subscription_id="sub-cval-002",
            dr_subscription_id="sub-dr-002",
        ),
    ],
)
```

### Placement Policy (Tunable)

```python
from models import PlacementPolicy

policy = PlacementPolicy(
    alpha=0.30,    # capacity headroom weight  [Assumed]
    beta=0.20,     # quota headroom weight     [Assumed]
    gamma=0.25,    # fairness weight           [Assumed]
    delta=0.15,    # DR readiness weight       [Assumed]
    epsilon=0.10,  # zone diversity weight     [Assumed]
    zone_skew_tolerance=2,                   # C-13
    combined_load_alert_threshold=0.85,      # C-15
    quota_group_replenish_threshold=0.85,    # QUA-015
    quota_sub_replenish_threshold=0.85,      # QUA-015
    dr_sizing_method="max_not_sum",          # DR-017
)
```

> **Note:** All weight values are labelled `[Assumed]` and are not
> approved production defaults. Adjust via `PlacementPolicy` before
> using for production decisions.

---

## Data Pre-Collection Checklist

Before running the engine against real Azure data, collect:

| # | Data | Source | Command / API |
|---|---|---|---|
| 1 | **Capacity Reservation Groups** | Resource Graph | `resources \| where type =~ 'microsoft.compute/capacityreservationgroups'` |
| 2 | **Capacity Reservations** (per CRG) | Resource Graph | `resources \| where type =~ '...capacityreservations'` |
| 3 | **VM instances** using CRs | Resource Graph | Filter on `properties.capacityReservation` |
| 4 | **Quota usage** per SKU family | Compute Usage API | `az vm list-usage --location <region>` |
| 5 | **Subscription list** | ARM | `az account list` |
| 6 | **Region catalogue** | `environment.yaml` | Static configuration |
| 7 | **Customer demand** | Onboarding system | vCPU demands per domain group |
| 8 | **Customer count** per region | Internal tracking | For γ-fairness calculation |

---

## Output: Placement Report

The engine produces a Markdown report with:

1. **Header** — customer name, geography, distribution model, policy version
2. **CRV Phase** — Hard-constraint results per region, scoring table
   (all five factors), region ranking, selected Prod/CVAL/DR regions
3. **DPB Phase** (per domain group) — CRG naming, CR sizing,
   subscription binding, quota draw, zone-level placement table
4. **Rejection Log** — every rejected region with the specific HC or
   scoring reason
5. **Alerts** — quota replenishment warnings, combined-load alerts

Sample excerpt:

```
### Scoring — Prod

| Region | α capacity | β quota | γ fairness | δ DR | ε zone | Total | Rank |
|--------|-----------|---------|------------|------|--------|-------|------|
| West US 3 | 0.075 | 0.112 | 0.167 | 0.098 | 0.082 | 0.534 | 1 |
| Canada Central | 0.113 | 0.104 | 0.208 | 0.115 | 0.078 | 0.618 | 2 |
```

---

## Project Structure

```
Placement-Engine/
├── README.md              # This file
├── requirements.txt       # Azure SDK dependencies
├── models.py              # Data models (RegionSnapshot, Customer, etc.)
├── hard_constraints.py    # HC-1 through HC-11 implementations
├── scoring.py             # PS_Prod, PS_NonProd, PS_DR scoring (F.1–F.13)
├── engine.py              # CRV → DPB pipeline orchestration
├── report.py              # Markdown report generator
├── mock_data.py           # Synthetic multi-domain/multi-subscription data
├── azure_collector.py     # Azure real-time data collector
└── run_mockup.py          # CLI entry point
```

## Requirements Traceability

| Engine Component | Requirement IDs |
|---|---|
| Hard Constraints | HC-1–HC-11 (Hard Constraints Reference v1.1) |
| CRV Resolution | PLC-001 (exact-region), PLC-002 (geography path) |
| Distribution Models | REG-003, PLC-010a (2-region), PLC-010b (cross-geo) |
| Scoring Formulas | F.1–F.9 (per-factor), F.10 (γ fairness), F.11 (CRV) |
| DPB Binding | F.12 (DPB), F.13 (lineage), PLC-015 (gate) |
| DR Sizing | DR-017 (max-not-sum) |
| CRG Naming | OPS-006, C-12, CAP-023 |
| Quota Checks | QUA-007, QUA-015 |
| Foundation DR | DR-021 (separate from workload DR) |

---

## Known Limitations

1. **Scoring weights are [Assumed]** — not approved production values.
2. **α/δ duplication** in NonProd scoring gives NP headroom effective
   weight 0.45 — this is a documented design gap (see mock exercise
   user guide).
3. **Buffer (C-3) is parameterised as 0** — no default buffer percentage
   is assumed.
4. **Azure collector** infers environment from CRG naming convention
   (OPS-006) — non-conforming names require manual mapping.
5. Cross-geo DR weighted placement uses standard scoring; a dedicated
   DR-weighted algorithm is a future enhancement.

---

## Contributing

This is a mockup for validation purposes. To modify:

1. Edit `mock_data.py` for new scenarios
2. Adjust `PlacementPolicy` weights for sensitivity analysis
3. Extend `hard_constraints.py` for new HC rules
4. Run `python run_mockup.py -v` and inspect the report
