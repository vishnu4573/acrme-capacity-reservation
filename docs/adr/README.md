# ACRME Architecture Decision Records (ADR Set)

Individual, standalone Architecture Decision Records for the Azure Capacity Reservation Management Engine (ACRME). Each ADR is self-contained (`.md` source + `.pdf` print-ready + `.docx` editable) with its own context, decision, consequences, alternatives-considered, the relevant normative detail, and cross-references to the other ADRs.

These were split from the consolidated `../acrme_architecture_decision_records.md`, which remains available as a single combined document.

| ADR | Title | Scope | Files |
|---|---|---|---|
| **ADR-001** | Region Selection | Sequential Prod→NonProd→DR placement, region classification model, Scenario 1/2 input modes, EC-1..EC-4 exception workflow, VR-1..VR-11, capacity holds, corrected scoring model | `acrme_adr_001_region_selection.{md,pdf,docx}` |
| **ADR-002** | Quota and Capacity Management | Two quota groups, engine-enforced DR floor, group accounting formulas, dual-validation detector, `groupType` FC-11 preview status | `acrme_adr_002_quota_and_capacity_management.{md,pdf,docx}` |
| **ADR-003** | Capacity Management during DR | NonProd/DR co-location (HC-6), full five-state engine state machine, `EngineModeState` entity, three-tier emergency transfer, DR-activation semantics | `acrme_adr_003_capacity_management_during_dr.{md,pdf,docx}` |
| **ADR-004** | Forecast and Increase of Capacity and Quota | Forecast-driven approval-gated growth, `Forecast_Quantity` formula, 10-step steady-state lifecycle, auto-decrease exclusion, mode isolation | `acrme_adr_004_forecast_and_increase_of_capacity_and_quota.{md,pdf,docx}` |

**Evidence tags** used throughout: `[Documented]` (Azure platform docs / formal FR-NFR), `[Decided]` (Decision Log D1–D11), `[Derived]` (logical consequence), `[Assumed]` (architectural judgement pending POC validation).

`split_adrs.py` is the deterministic splitter that regenerates these `.md` files from the consolidated source.
