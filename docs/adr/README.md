# ACRME Architecture Decision Records (ADR Set)

Individual, standalone Architecture Decision Records for the Azure Capacity Reservation Management Engine (ACRME). Each ADR is **self-contained and reference-free** — it can be read without any companion document (`.md` source + `.pdf` print-ready + `.docx` editable), and includes its own context, decision, consequences, alternatives considered, the relevant normative detail, and rendered architecture diagrams.

A legacy combined document, `../acrme_architecture_decision_records.md`, contains an earlier consolidated form of records 001–004 (pre-v2.2 two-group / Belgium Central) and is **superseded** by these standalone v2.2 ADRs plus ADR-005; it is retained for history only.

The v2.2 reconciliation aligned these ADRs to Requirements Baseline v2.2: **single governed quota pool** (ADR-002, QUA-004), Belgium Central → **Switzerland North** cross-geo DR, max-not-sum sizing, seed record, `SourceDestinationDRIndex`, standby activation, and the distributed DR reference model (new ADR-005).

> **Current authoritative baseline: v2.4 — all ADRs reconciled.** The single source of truth is now [`../requirements/acrme_requirements_baseline_v2_4.md`](../requirements/acrme_requirements_baseline_v2_4.md), and **ADR-001..005 are all reconciled to v2.4** (each carries a v2.4 reconciliation note in its header):
> - **ADR-001** — geography-aware region model confirmed; the legacy "three-region gate" is replaced by an explicit *region-model gate* (US three-region; Europe/Australia/Asia Pacific two-region with CVAL+DR co-located per **PLC-010a**; Middle East `DR_NOT_OFFERED` per **DEC-001**). No region-model change in v2.4.
> - **ADR-002** — reconciled to the v2.4 single-governed-quota-pool model.
> - **ADR-003** — DR model unchanged; adds a per-zone cross-reference to **PLC-011 / Appendix A.9** and per-AZ CRGs (**CAP-023**) at the DR sizing formula.
> - **ADR-004** — adds the full **CAP-022** (seed-at-0 matrix + budget governance) and **CAP-024** (reactive SKU/AZ discovery) normative blocks.
> - **ADR-005** — distributed DR reference model unchanged; header note confirms no DR-model change.
>
> The v2.4 reservation-model additions (CAP-020/021 Availability-Set ineligibility, CAP-022 seed matrix, CAP-023 per-AZ CRG structure, CAP-024 reactive discovery, PLC-011 even zone distribution, OPS-006/C-12 naming) do not alter the region-selection or DR-placement decisions; they are captured in ADR-002/ADR-004 and the TDD.

| ADR | Title | Scope | Files |
|---|---|---|---|
| **ADR-001** | Region Selection and Customer Placement | Exact-region-first (default) vs geography exception, `CustomerSeedRecord`, `DR_NOT_OFFERED`, geography-aware region-model gate, readiness-state enum, versioned region catalogue, atomic placement holds, DR-index contribution | `acrme_adr_001_region_selection.{md,pdf,docx}` |
| **ADR-002** | Quota and Capacity Management | **Single governed quota pool (primary, QUA-004)** with logical Prod/DR earmarks; two-group topology as narrow exception; quota-as-governor; max-not-sum DR floor; `Allocated + Buffer` control; `groupType` preview status | `acrme_adr_002_quota_and_capacity_management.{md,pdf,docx}` |
| **ADR-003** | Capacity Management during DR | Lean bootstrap, max-not-sum sizing, reciprocal multi-source hosting, standby activation waves, `CVALEarmarkRecord` double-count guard, five-state engine machine, staged acquisition, zero-capacity/no-delete | `acrme_adr_003_capacity_management_during_dr.{md,pdf,docx}` |
| **ADR-004** | Forecast and Increase of Capacity and Quota | `Target = Allocated + Buffer` reconciliation floor, `Forecast_Quantity` advisory planning, 6-min reconciliation loop, scale-down guards, no-auto-delete, readiness/alerting integration, **seed-at-0 matrix + budget governance (CAP-022)**, **reactive SKU/AZ discovery (CAP-024)** | `acrme_adr_004_forecast_and_increase_of_capacity_and_quota.{md,pdf,docx}` |
| **ADR-005** | Distributed DR Reference Model | Section 12A topology, reciprocal many-to-many roles, `SourceDestinationDRIndex` (bidirectional), max-not-sum destination boundary + overcommit ratio/gap, single-failure assumption, DR earmark in single pool, observability contract | `acrme_adr_005_distributed_dr_reference_model.{md,pdf,docx}` |

**Evidence tags** used throughout: `[Documented]` (traceable to Azure platform behaviour or documentation), `[Decided]` (an explicit ACRME design choice recorded in this ADR set), `[Derived]` (a logical consequence of a documented constraint or decision), `[Assumed]` (architectural judgement pending proof-of-concept validation).

**Diagrams** are rendered from the Mermaid sources in `diagrams/*.mmd` to `diagrams/*.png`; the `.png` files are embedded in each ADR.

`split_adrs.py` is the deterministic splitter that regenerates these `.md` files from the consolidated source.
