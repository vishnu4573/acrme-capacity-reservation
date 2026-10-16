# ACRME Architecture Decision Records (ADR Set)

Individual, standalone Architecture Decision Records for the Azure Capacity Reservation Management Engine (ACRME). Each ADR is **self-contained and reference-free** — it can be read without any companion document (`.md` source + `.pdf` print-ready + `.docx` editable), and includes its own context, decision, consequences, alternatives considered, the relevant normative detail, and rendered architecture diagrams.

## v4.0 reconciliation boundary

[Derived] The [FDD](../../Design/acrme_functional_design_document.md) and
[TDD](../../Design/acrme_technical_design_document.md) are now v4.0 reconciliation
drafts, not accepted replacement ADRs. Scoped reconciliation notes in ADR-001
through ADR-007 identify current baseline requirements and displaced historical
details. They do not retroactively approve new design choices or the whole ADR body.

| Historical ADR | Current binding requirement / design location |
|---|---|
| ADR-001 | PLC-013/014/015 customer CRV then domain DPB; TDD sections 4/8/11 |
| ADR-002 | QUA-004/015 one customer group with cells and confirmed subscription quota; TDD section 8.3 |
| ADR-003 | DR-021 Foundation, guarded incident resumption proposal; TDD sections 7/9 |
| ADR-004 | CAP-009 normal target-zero versus CAP-010 intentional retirement; TDD section 10 |
| ADR-005 | Domain-partitioned MAX and explicit cross-geo scenario blocker; TDD section 9 |
| ADR-006 | Both-cap residual readiness is fail-fast, not warning-only; TDD section 11 |
| ADR-007 (proposed) | CAP-023/025 domain zonal sets, CAP-013 production local-subscription route; TDD section 5 |

Canonical current diagram drafts are in [Design/diagrams](../../Design/diagrams/).
Legacy PNGs/inline diagrams remain historical, not current runtime specifications.
The splitter below is a historical generation utility: its source path does not
identify the archived consolidated document as a current editable authority.
Do not run it to overwrite scoped reconciliation notes or claim it regenerates the
new design. Source/generator modernization is outside this documentation change.

A legacy combined document, [`/Archive/adr/acrme_architecture_decision_records.md`](../../Archive/adr/acrme_architecture_decision_records.md), contains an earlier consolidated form of records 001–004 (pre-v2.2 two-group / Belgium Central) and is **superseded** by these standalone v2.2 ADRs plus ADR-005; it is retained for history only.

The v2.2 reconciliation aligned these ADRs to Requirements Baseline v2.2: **single governed quota pool** (ADR-002, QUA-004), Belgium Central → **Switzerland North** cross-geo DR, max-not-sum sizing, seed record, `SourceDestinationDRIndex`, standby activation, and the distributed DR reference model (new ADR-005).

> **Current authoritative baseline: v4.0.** The single source of truth is [`/Requirements/acrme_requirements_baseline_v4_0.md`](../../Requirements/acrme_requirements_baseline_v4_0.md). The ADRs below contain v2.4-era reconciliation notes; they have not been comprehensively reconciled to v4.0. Treat those notes as historical context, and apply v4.0 wherever there is a conflict:
> - **ADR-001** — geography-aware region model; the legacy "three-region gate" is replaced by an explicit *region-model gate* with **three distribution models**: US three-region; Europe/Australia/Asia Pacific two-region co-located (CVAL+DR co-located per **PLC-010a**); **Middle East cross-geo DR** (Prod+CVAL in a Middle East region, DR in a weighted-selected Europe region — **DR-020, PLC-010b**).
> - **ADR-002** — reconciled to the v2.4 single-governed-quota-pool model.
> - **ADR-003** — DR model unchanged; adds a per-zone cross-reference to **PLC-011 / Appendix A.9** and per-AZ CRGs (**CAP-023**) at the DR sizing formula; **[v2.4 amended]** adds Middle East cross-geo DR exclusion from the CVAL-sacrifice bootstrap.
> - **ADR-004** — adds the full **CAP-022** (seed-at-0 matrix + budget governance) and **CAP-024** (reactive SKU/AZ discovery) normative blocks.
> - **ADR-005** — distributed DR reference model; **[v2.4 amended]** adds the **Middle East Cross-Geo DR Model** (Middle East regions are DR sources whose destinations are weighted-selected Europe regions; supersedes the former `DR_NOT_OFFERED` carve-out).
>
> **[v2.4 amended — 11 Sep 2026] Middle East DR now offered (cross-geo to Europe).** The former Middle East `DR_NOT_OFFERED` position (DR-014/DEC-001) is **superseded**: Prod+CVAL co-locate in a selected Middle East Standard region and DR is placed cross-geo in a **weighted-selected Europe Standard region**. Both selections use the weighted capacity placement model. New codes: **DR-020** (cross-geo DR ME→Europe), **PLC-010b** (cross-geo DR override to PLC-010a), **A-ME1** (data-residency assumption). This is a **third distribution model** — *cross-geo DR* — alongside the US three-region and the standard two-region co-located models. ADR-001, ADR-003 and ADR-005 carry inline **[Amended v2.4]** markers.
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
