**Project:** Azure Capacity Reservation Management Engine (ACRME)  
**Classification:** Principal Cloud Architect - Architecture Governance  
**Version:** 1.1  
**Date:** 7 September 2026  
**Status:** Accepted - new ADR introduced with Requirements Baseline v2.2; reconciled to Baseline v2.4 (no DR-model change)  
**Part of:** ACRME Architecture Decision Records - aligned to Capacity & Quota Management Requirements Baseline v2.4.

> **About ADRs.** An Architecture Decision Record captures a significant architectural decision, the context that forced it, the options considered, the choice made, and its consequences. This ADR consolidates the distributed DR reference model (Section 12A of the requirements baseline) that was previously distributed across ADR-003 and the calculation logic reference. Evidence tags: `[Documented]`, `[Decided]`, `[Derived]`, `[Assumed]`.
>
> **v2.4 reconciliation note — reservation-model gaps.** The distributed, reciprocal DR reference model, max-not-sum destination sizing (DR-017), the `SourceDestinationDRIndex` (DR-018) and the reference topology are **unchanged** by the *reservation-model* gaps folded into Baseline v2.4 (seed matrix CAP-022, per-AZ CRG structure CAP-023, reactive discovery CAP-024, Availability-Set ineligibility CAP-020/021, even zone distribution PLC-011, naming OPS-006/C-12). Where DR sizing is applied **per zone**, the per-zone floors are held in the destination's per-AZ CRGs (CAP-023) and are kept balanced by the PLC-011 even-distribution target — see ADR-003 *DR Sizing Formula* for that cross-reference.
>
> **v2.4 (amended) note — Middle East DR now offered (cross-geo to Europe).** As of the 11 Sep 2026 amendment to baseline v2.4, the Middle East `DR_NOT_OFFERED` carve-out (former DR-014/DEC-001) is **superseded**. Middle East DR **is now offered** as a **cross-geo DR** model (DR-020, PLC-010b): **Prod and CVAL co-locate in a selected Middle East Standard region** and **DR is placed cross-geo in a weighted-selected Europe Standard region**. Middle East regions are **sources** in this reference model (they emit `source → Europe destination` index rows); the DR standby is sized and earmarked in the Europe destination using dedicated reserved capacity. The CVAL-sacrifice bootstrap (DR-005/006) does **not** apply to the Middle East (CVAL co-locates with Prod locally, not with DR). Europe Standard regions become cross-geo DR destinations that absorb Middle East DR load in addition to their own two-region co-located role. The affected sections below carry inline **[Amended v2.4]** markers.

---

# ADR-005 - Distributed DR Reference Model

**Status:** Accepted  
**Date:** 2 September 2026  
**Deciders:** Principal Cloud Architect, DR Owner, Platform Engineering, FinOps, Capacity Planning  
**Related requirements:** DR-006, DR-007, DR-009, DR-013, DR-016, DR-017, DR-018, DR-019, **DR-020**, PLC-003..PLC-005, PLC-010, **PLC-010b**, DAT-002, DAT-003, OBS-001..OBS-004, **A-ME1**  
**Related POCs/decisions:** POC-006 (DR topology), POC-007 (bootstrap sizing), POC-011 (max-not-sum overcommit safety), DEC-001 (Middle East DR — **RESOLVED v2.4 amended: cross-geo DR to Europe**), DEC-002 (failback duration)  
**Related ADRs:** ADR-001 (seed record), ADR-002 (single governed quota pool, DR earmark), ADR-003 (lean bootstrap, activation, CVAL earmark, state machine)

## Context

The requirements baseline (introduced at v2.2, current v2.4) replaces the fixed-ratio, per-customer DR clone with a **distributed, reciprocal DR reference model** (Section 12A). At platform scale, dedicating a fixed 30-40% standby copy of every production region is prohibitively expensive and does not reflect the operating assumption that **one source region fails at a time**. `[Decided]`

The distributed model spreads each customer's standby capacity across the same shared regional footprint that already hosts production and CVAL. This creates a many-to-many topology in which a single region is simultaneously a **production** region for some customers, a **CVAL** host for others, and a **DR standby** host for customers whose production is in one or more *different* source regions. `[Decided]`

Because ADR-003 already carries the operational DR decisions (bootstrap, activation waves, CVAL earmark, engine state machine), this ADR fixes the **reference model itself**: the topology, the authoritative source→destination mapping, the destination-sizing boundary, the single-failure assumption, and the observability contract that makes the model auditable. It is the design anchor for the Section 12A worked example and the `acrme_three_region_capacity_model` diagram. `[Derived]`

## Decision

Adopt the **distributed, reciprocal DR reference model** with the following normative elements:

1. **Distributed standby, not co-located clones.** Each customer's DR standby is placed by the ADR-001 placement engine into a destination region drawn from the shared regional footprint, recorded in the seed record, and never defaulted to a fixed percentage of production. `[Decided]`

2. **Reciprocal, many-to-many roles.** Every managed region may concurrently hold three roles — Prod, CVAL, and DR standby for multiple different source regions. No region is a dedicated DR-only region. `[Decided]`

3. **Authoritative source→destination index (DR-018).** `SourceDestinationDRIndex` is the required state entity that maps each protected source region to the destination regions holding its standby capacity, per customer/realm and seed. It is the reverse view of the seed record and the driver of activation. `[Decided]`

4. **Bidirectional queryability.** The index must answer both `source → destinations` (which standby sets activate when a source fails) and `destination → sources` (which sources a destination protects, for max-source coverage and dashboards). `[Decided]`

5. **Max-not-sum destination boundary (DR-017).** A destination sizes its standby capacity to the **largest single non-concurrent protected source portion**, not the sum across sources. A configured SUM override is available where a contract or geography requires simultaneous-failure coverage. `[Decided]`

6. **Single-source-failure assumption is explicit.** The model is valid only under the assumption that at most one protected source region is in a declared DR event at a time. Concurrent multi-source failure is an out-of-model risk mitigated only by SUM override or additional earmark. `[Decided]`

7. **The DR earmark lives inside the single governed quota pool.** Per ADR-002, the max-not-sum destination requirement is reserved as `DR_Earmark_vCPU` inside the one governed quota pool for that region/family, so live NonProd/CVAL usage cannot consume standby-activation headroom. `[Decided]`

8. **Activation is source-specific and wave-ordered.** A declared source-region failure activates only that source's mapped standby set, in business-priority waves, via the ADR-003 staged acquisition sequence, and is reversible on failback. `[Decided]`

9. **`DR_NOT_OFFERED` geographies are excluded from the reciprocal model (DR-014).** Where legal/data-sovereignty prevents an acceptable DR design, the geography is flagged `DR_NOT_OFFERED` and **does not participate** in the distributed, reciprocal, max-not-sum model at all: its customers get `dr_region = NOT_OFFERED` in the seed, contribute **no** entries to the `SourceDestinationDRIndex`, and are **never** sized, earmarked, or activated as a source or destination. **[Amended v2.4] The Middle East is no longer `DR_NOT_OFFERED`** — it now participates via the cross-geo DR model (DR-020, see the Middle East section below). The flag remains available for any future geography/country Legal declares no-DR. `[Decided]`

10. **Cross-geo DR participation (Middle East → Europe) [Amended v2.4] (DR-020, PLC-010b).** A cross-geo DR geography participates as a **source only within its own regions** and as a **destination in the paired geography**. For the Middle East: Middle East Standard regions (e.g., Saudi Arabia Central, UAE North) are **DR sources** whose mapped **destinations are weighted-selected Europe Standard regions**. The Europe destination sizes the Middle East DR standby using **max-not-sum** across all sources it serves (DR-017) and holds it as **dedicated reserved capacity**; the Middle East CVAL is **not** sacrificed for bootstrap (DR-005/006 do not apply). The `source → destination` rows are cross-geo and subject to sovereignty/zone-alignment constraints (HC-10) and the data-residency assumption A-ME1. `[Decided]`

## Middle East Cross-Geo DR Model [Amended v2.4] (DR-020, PLC-010b — supersedes DR-014/DEC-001 `DR_NOT_OFFERED`)

> **DR is now offered in the Middle East as a cross-geo DR model.** Per the 11 Sep 2026 amendment to baseline v2.4, the former `DR_NOT_OFFERED` position (DR-014/DEC-001) is **superseded**. **Prod and CVAL co-locate in a selected Middle East Standard region** (separate CRGs — co-location in a region is not capacity sharing, ENV-003) and **DR is placed cross-geo in a weighted-selected Europe Standard region**. Both the Middle East (Prod+CVAL) source selection and the Europe (DR) destination selection run the **weighted capacity placement model** (baseline Section 6, REG-002/REG-003). Data residency of the DR copy is governed by assumption **A-ME1** (Europe as the approved cross-geo destination); per-country legal carve-outs remain possible but are out of scope of the automated engine (baseline Section 5).

> **Historical note.** Prior to v2.4 (amended), the Middle East was `DR_NOT_OFFERED` (DR-014/DEC-001): Legal owned the programme and cross-border DR was held to be incompatible with data-residency laws for a largely government/medical customer base. That position has been reversed — Europe is now an approved cross-geo DR destination for the Middle East.

Normative consequences for this reference model:

1. **Middle East regions are DR sources, Europe regions are their destinations.** Middle East Standard regions (Saudi Arabia Central, UAE North) carry **Prod + CVAL co-located** and are **DR sources**. Their mapped **destinations are weighted-selected Europe Standard regions** (not a single fixed region). The many-to-many reciprocal roles (Decision 2) apply **across the geography pair**: a Middle East source maps to a Europe destination; the Europe region continues to serve its own two-region co-located role in addition. `[Decided]`

2. **Index entries, earmark and activation at the Europe destination.** Middle East customers produce `dr_region = <Europe region>` seeds (ADR-001), adding cross-geo `source → destination` rows to the `SourceDestinationDRIndex`. The DR standby is **sized with max-not-sum (DR-017) and earmarked as `DR_Earmark_vCPU` in the Europe destination**, held as **dedicated reserved capacity**. A declared Middle East source-region failure activates only that source's mapped Europe standby set, wave-ordered (Decision 8). `[Decided]`

3. **No CVAL-sacrifice bootstrap for the Middle East (DR-005/006 do not apply).** Because CVAL co-locates with **Prod locally** in the Middle East (not with DR), the CVAL-sacrifice DR bootstrap does not apply. The Europe DR standby is provisioned as dedicated reserved capacity from the start; this is the key contrast with the two-region co-located geographies. `[Decided]`

4. **Cross-geo constraints apply.** The Middle East → Europe mapping is a cross-geo case and is subject to sovereignty/zone-alignment constraints (HC-10) and the data-residency assumption A-ME1. If Legal changes the approved destination geography or adds per-country carve-outs, the affected Middle East regions revert to `DR_NOT_OFFERED` for those countries (config change, no code change; FIN-002, C-8). Reversible. `[Decided]`

## Reference Topology

> **Scope note.** The three-region reciprocal footprint below is illustrative of a **three-region DR-offered geography** (e.g., North America). It is **not** the Middle East: **[Amended v2.4]** the Middle East now uses the **cross-geo DR** model (Prod+CVAL in a Middle East region, DR in a weighted-selected Europe region — see the Middle East Cross-Geo DR Model section above), so its topology is a source→destination geography pair rather than an in-geo three-region footprint.

The reference footprint used in the Section 12A worked example spans three regions (R1, R2, R3). Each region carries its own production and CVAL workloads and hosts distributed DR standby for the *other* regions' production. The `src Rn` tag on each standby cell identifies the source region whose production that standby protects.

![ACRME Distributed DR Reference Model](diagrams/acrme_three_region_capacity_model.png)

*Figure 1. Distributed DR reference model (Section 12A worked example). Each region simultaneously hosts Prod, CVAL, and DR standby for other source regions; every DR standby cell is tagged with its `src Rn` source region. See `diagrams/acrme_three_region_capacity_model.html` for the self-contained source.*

```mermaid
flowchart LR
    subgraph R1[Region R1]
        P1[Prod R1]
        C1[CVAL R1]
        D1["DR standby<br/>src R2, src R3"]
    end
    subgraph R2[Region R2]
        P2[Prod R2]
        C2[CVAL R2]
        D2["DR standby<br/>src R1, src R3"]
    end
    subgraph R3[Region R3]
        P3[Prod R3]
        C3[CVAL R3]
        D3["DR standby<br/>src R1, src R2"]
    end
    P1 -. protected by .-> D2
    P1 -. protected by .-> D3
    P2 -. protected by .-> D1
    P2 -. protected by .-> D3
    P3 -. protected by .-> D1
    P3 -. protected by .-> D2
```

*Figure 2. Reciprocal protection: each region's production is protected by standby distributed across the other regions; each region's DR cell hosts standby for multiple source regions (many-to-many).*

## SourceDestinationDRIndex (DR-018, DAT-002)

| Field | Purpose |
|---|---|
| `source_region` | Failed or protected production source. |
| `destination_region` | Region holding standby DR capacity for that source. |
| `customer_or_realm_id` | Customer/realm whose standby set is mapped. |
| `seed_id` | Link back to `CustomerSeedRecord` (ADR-001). |
| `standby_instance_set` | VM/VMSS/node-pool/application set eligible for activation. |
| `sku_family`, `sku`, `zone`, `quantity` | Capacity/quota dimensions. |
| `activation_state` | `standby`, `activation_pending`, `active`, `failback_pending`, `returned`. |
| `priority_wave` | Business-priority order for activation (DR-009). |
| `policy_version`, `last_updated` | Replay, freshness, and audit fields. |

The index is derived from the seed records but is maintained as a first-class, independently queryable entity so activation does not require scanning all seeds at declaration time. `[Decided]`

## Destination Sizing Boundary (DR-017)

For each destination `d`, SKU, zone, and policy scope:

```text
Destination_DR_Requirement(d, sku, zone)
  = MAX over non-concurrent source regions s protected by d (
      Workload_Portion(s -> d, sku, zone)
    )

DR_Floor_vCPU(d, sku, zone)
  = Destination_DR_Requirement(d, sku, zone) * vCPU_Per_Instance(sku)

# Overcommit visibility (App. A.8):
Overcommit_Ratio(d) = ( SUM over sources s ( Workload_Portion(s -> d) ) )
                      / Destination_DR_Requirement(d)

# Coverage gap (App. A.7):
DR_Capacity_Gap(d) = Destination_DR_Requirement(d) - Standby_Provisioned(d)
```

- `MAX` is valid only under the single-source-failure assumption (Decision 6). `[Decided]`
- `Overcommit_Ratio(d) > 1` is expected and healthy — it quantifies how much cheaper the distributed max-not-sum model is than summed clones. It is surfaced, not alerted, unless it exceeds a configured safety ceiling (POC-011). `[Derived]`
- `DR_Capacity_Gap(d) > 0` means the destination cannot currently satisfy its worst-case single-source activation and must raise a coverage alert. `[Decided]`

## Worked Example (Section 12A)

Using the reference footprint, assume for one SKU/zone that region R1's DR cell protects R2 (portion 40 instances) and R3 (portion 55 instances), non-concurrently:

```text
Destination_DR_Requirement(R1) = MAX(40, 55) = 55 instances     # not 40 + 55 = 95
Overcommit_Ratio(R1)           = (40 + 55) / 55 = 1.73           # 73% cheaper than summed clones
```

R1 reserves standby for **55** instances (the larger single source), earmarked inside R1's single governed quota pool. If R3 is declared failed, R1 activates R3's 55-instance standby set in priority waves; R2's mapped standby (which may sit in a different destination) is untouched. `[Decided]`

## Observability Contract (OBS-001..004)

The distributed model is auditable only if the following are exposed:

- per-destination **max-source coverage** metric and a **coverage-gap** alert when `DR_Capacity_Gap(d) > 0` (OBS-001/002);
- **overcommit ratio** per destination, with a POC-011 safety-ceiling alert (OBS-002);
- a **source ↔ destination DR mapping** dashboard view driven by the index (OBS-004);
- activation state by customer and priority wave, and failback-pending age (OBS-003/004). `[Decided]`

## Consequences

**Positive**

- Removes fixed 30-40% idle standby as the default; distributed max-not-sum is materially cheaper. `[Decided]`
- Reuses the shared regional footprint (Prod/CVAL/DR reciprocal roles) instead of dedicated DR regions. `[Decided]`
- Makes activation deterministic and source-specific via the index and seed. `[Decided]`
- Pairs naturally with the single governed quota pool: the DR earmark is one line item inside the shared pool. `[Derived]`

**Negative / trade-offs**

- Under-protects genuinely concurrent multi-source failures unless SUM override or extra earmark is configured. `[Derived]`
- Requires the `SourceDestinationDRIndex` to be kept fresh and consistent with seeds. `[Decided]`
- Overcommit visibility and safety ceilings depend on POC-011 evidence. `[Assumed]`
- Cross-geo cases add sovereignty/zone-alignment constraints to the mapping. **[Amended v2.4]** The **Middle East** now participates as a cross-geo DR source whose destinations are weighted-selected **Europe** Standard regions (DR-020, PLC-010b; see the Middle East Cross-Geo DR Model above), governed by data-residency assumption A-ME1. `DR_NOT_OFFERED` remains available for any future geography/country Legal declares no-DR. `[Derived]`
- **[Amended v2.4]** Europe Standard regions now absorb Middle East DR load in addition to their own two-region co-located DR, increasing the max-not-sum earmark those regions must hold. `[Derived]`

## Alternatives Considered

| Alternative | Disposition |
|---|---|
| Fixed 30-40% per-customer DR clone | Rejected as default — idle cost, ignores single-failure assumption. `[Decided]` |
| Dedicated DR-only regions | Rejected — wastes the reciprocal capacity already present in shared regions. `[Decided]` |
| Sum-of-sources destination sizing as default | Rejected as default; retained as configurable SUM override. `[Decided]` |
| Compute activation set by scanning all seeds at declaration | Rejected — too slow; `SourceDestinationDRIndex` precomputes it. `[Decided]` |
| Earmark DR in a separate quota group | Rejected as default — single governed pool with a logical DR earmark is preferred (ADR-002). `[Decided]` |

---

## Appendix - ADR Summary

| ADR | Requirements Applied | Key Open Items |
|---|---|---|
| ADR-005 Distributed DR Reference Model | DR-006/007/009/013/016..020, **DR-020**, PLC-003..005/010, **PLC-010b**, DAT-002/003, OBS-001..004, **A-ME1** | POC-006 topology; POC-007 bootstrap sizing; POC-011 overcommit safety ceiling; ~~DEC-001~~ **RESOLVED — Middle East DR now offered (cross-geo to Europe, v2.4 amended)**; per-country ME data-residency carve-outs (Legal) |

## Appendix - Status Legend

| Status | Meaning |
|---|---|
| **Proposed** | Under discussion; not yet ratified |
| **Accepted** | Ratified and in force |
| **Deprecated** | No longer recommended but not yet replaced |
| **Superseded** | Replaced by a later ADR |

## Appendix - Evidence Tag Taxonomy

| Tag | Meaning |
|---|---|
| `[Documented]` | Traceable to Azure platform behaviour or documentation |
| `[Decided]` | An explicit ACRME design choice recorded in this ADR set |
| `[Derived]` | A logical consequence of a documented constraint or decision |
| `[Assumed]` | Architectural judgement pending proof-of-concept validation |

## Related ADRs

- **ADR-001 - Region Selection and Customer Placement** (`acrme_adr_001_region_selection.md`)
- **ADR-002 - Quota and Capacity Management** (`acrme_adr_002_quota_and_capacity_management.md`)
- **ADR-003 - Capacity Management during Disaster Recovery (DR)** (`acrme_adr_003_capacity_management_during_dr.md`)
- **ADR-004 - Forecast, Reconciliation, and Increase of Capacity and Quota** (`acrme_adr_004_forecast_and_increase_of_capacity_and_quota.md`)

---

**Document Status:** Accepted  
**Next Review:** After POC-006, POC-007, POC-011, and first `SourceDestinationDRIndex` implementation test. (DEC-001 resolved — Middle East DR now offered as cross-geo DR to Europe, v2.4 amended 11 Sep 2026.)
