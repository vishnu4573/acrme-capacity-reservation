# ACRME Phase 4 — Distributed DR Capacity Management

**ACRME** (Azure Capacity Reservation Management Engine) — Phase 4: Distributed DR
Capacity Management, per Requirements Baseline **v2.3 Section 21** and the Distributed
DR Reference Model (**Section 12A**, Appendix A.6/A.7/A.8, Appendix D).

## Objective

Enterprise-scale DR capacity governance: reciprocal multi-source hosting, a bidirectional
source→destination DR index, **max-not-sum** destination sizing, a DR declaration &
standby-activation workflow, failback, and non-destructive DR simulation with compliance
evidence.

## Scope delivered (Baseline v2.3 §21 Phase 4)

| Requirement | Capability | Module |
|---|---|---|
| **DR-016** | Reciprocal multi-source hosting (many-to-many) | `components/dr_index_manager.py` (`reciprocal_view`) |
| **DR-018** | Authoritative bidirectional source→destination DR index | `domain/dr_index.py`, `components/dr_index_manager.py` |
| **DR-017** | Non-concurrent **max-not-sum** sizing (A.6) + SUM override (C-11) | `algorithms/dr_sizing.py` |
| A.7 / A.8 | DR capacity gap + overcommit ratio (exposure measure) | `algorithms/dr_sizing.py` |
| **DR-010** | DR declaration workflow (approver-gated) | `components/dr_activation.py` |
| **DR-019** | Standby activation `associated → allocated`, priority-wave order (DR-009) | `components/dr_activation.py` |
| **DR-006** | Staged capacity acquisition sequence (bootstrap → … → Azure request) | `components/dr_activation.py` |
| DR-005 / PLC-010a | CVAL release / sacrifice modelling toward DR | `components/dr_activation.py` |
| **DR-013** | Failback: reverse activation, restore CVAL, reset index | `components/dr_activation.py` |
| **DR-012** | Annual mock drill (non-destructive) + compliance evidence | `components/dr_simulator.py` |
| DAT-002 | DR index / declarations / activation records in state store | `store/state_store.py` |

**Post-POC (not built this phase):** live capacity-sharing quota allocation depends on
POC-001/011 outcomes; the staged sequence exposes `sharing_reassignment` and `azure_request`
steps as modelling hooks pending those results (Phase 5 Azure integration).

## Max-not-sum sizing (DR-017, Appendix D)

Under the single-region-failure assumption (**DR-001**), a destination that protects several
source regions is sized for the **largest single source**, not the sum:

```
Destination DR Requirement(d) = MAX over non-concurrent sources s of portion(s → d)   (A.6)
DR Capacity Gap(d)            = max(0, Requirement(d) - Usable Capacity(d))            (A.7)
Overcommit Ratio(d)           = SUM(portions on d) / MAX(portions on d)               (A.8)
```

A conservative **SUM override (C-11)** is available per-destination where a contract requires
concurrent-failure protection. The overcommit ratio quantifies the exposure if the
single-failure assumption is ever violated (**POC-011**).

### Worked example (Baseline §12A.2 / Appendix D.3)

Destination **Region 2** protects R1 (Cust1+Cust5 = 120 vCPU) and R3 (Cust6 = 80 vCPU):

- max-not-sum requirement = `max(120, 80)` = **120 vCPU** (vs sum = 200)
- overcommit ratio = `200 / 120` ≈ **1.67**

The Phase 4 demo reproduces these exact figures.

## Design guardrails honoured

- **Middle East `DR_NOT_OFFERED` (DEC-001)** — `register_from_seed` returns `None` for a seed
  whose `dr_region == "NOT_OFFERED"`; `register_placement` rejects a `NOT_OFFERED` destination.
  DR_NOT_OFFERED remains **Middle-East-only** (legal); it is never a generic two-region outcome.
- **Two-region geographies (EU / Australia / Asia Pacific)** use PLC-010a co-location
  (CVAL+DR in one region, Prod in the other) — never treated like Middle East.
- **ENV-003 separation** — standby DR must be in a different region from Prod (enforced).
- **Deterministic replay** — activation ordered by `(priority_wave, customer_realm_id)`;
  every declaration records `policy_version` and `capacity_snapshot_ref`.

## Run the demo

```bash
PYTHONPATH=src python examples/phase4_demo.py
```

The demo exercises: reciprocal view (DR-016) · max-not-sum + SUM override (DR-017/C-11) ·
declaration + standby activation for a Region 1 failure (DR-010/019) · failback (DR-013) ·
non-destructive drill + compliance evidence (DR-012).

## New / changed files

```
src/acrme/domain/dr_declaration.py       # DRDeclaration, DRActivationRecord, states
src/acrme/algorithms/dr_sizing.py        # DRSizer — max-not-sum (A.6/A.7/A.8, C-11)
src/acrme/components/dr_index_manager.py  # DRIndexManager — bidirectional index (DR-016/018)
src/acrme/components/dr_activation.py     # DRActivationEngine — declare/activate/failback
src/acrme/components/dr_simulator.py      # DRSimulator — drill + compliance evidence (DR-012)
src/acrme/store/state_store.py           # + DR index / declarations / activation records
examples/phase4_demo.py                  # worked example from Baseline §12A.2 / Appendix D.3
```

## Roadmap

- **Phase 1–2**: Design reconciliation ✅
- **Phase 3**: Placement & customer seed skeleton ✅
- **Phase 4**: Distributed DR capacity management ✅ (this release)
- **Phase 5**: Production integration (Azure SDK, live reconciliation, real capacity provider)
- **Phase 6**: Observability & hardening

---

**Version:** 0.2.0-phase4-skeleton
**Baseline:** v2.3 (7 Sep 2026)
**Status:** Implementation skeleton — Azure integration pending (Phase 5)
