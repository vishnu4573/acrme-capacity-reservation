# ACRME POC Test Suite

Production-quality Python test-automation suite for the **Azure Capacity
Reservation Management Engine (ACRME)** proof-of-concept programme. It implements
**35 test cases across 8 groups** plus a **10-item pre-flight checklist**, driving
everything through the **Azure CLI (`az`) and `az rest`** — *no Azure SDK Python
packages are required*.

---

## 1. Prerequisites

| Requirement | Minimum |
|---|---|
| Azure CLI (`az`) | **2.50.0** (pre-flight PF-01 enforces this) |
| Python | **3.10+** |
| `az` extensions | `resource-graph` (for ARG discovery tests POC-07/POC-16) |
| Azure access | A signed-in identity (`az login`) with rights on both provider and consumer subscriptions |

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Install the resource-graph extension (used by ARG discovery tests):

```bash
az extension add --name resource-graph
```

---

## 2. Setup

Copy the template and fill in every value:

```bash
cp config.yaml.template config.yaml
$EDITOR config.yaml
```

**Hard constraint:** `regions.primary`, `regions.dr`, and `regions.nonprod` must
be **three distinct regions**. The config loader *and* pre-flight PF-09/PF-10
refuse to run if any two are identical (Production, Non-Prod, and DR must never
all share a region).

All resources created by the suite are prefixed with `acrme-poc-` to avoid
collisions. Resource names you supply are auto-prefixed if the prefix is absent.

---

## 3. Pre-flight

```bash
python runner.py preflight
```

Runs PF-01 … PF-10:

| Check | Purpose | Blocking |
|---|---|---|
| PF-01 | `az` version ≥ 2.50.0 | no |
| PF-02 | `az account show` returns an identity | no |
| PF-03 | Provider subscription can be set & is active | no |
| PF-04 | `Microsoft.Compute` + `Microsoft.Quota` registered | no |
| PF-05 | Provider subscription quota for the SKU family | no |
| PF-06 | Consumer subscription quota for the SKU family | no |
| PF-07 | RBAC assignments visible at provider sub scope | no |
| PF-08 | No conflicting CRG names in the provider RG | no |
| **PF-09** | **primary ≠ dr region** | **YES** |
| **PF-10** | **nonprod ≠ primary and nonprod ≠ dr** | **YES** |

If PF-09 or PF-10 fail, the runner aborts before Group 1.

---

## 4. Running tests

Run the full suite (pre-flight runs first automatically):

```bash
python runner.py run --all
```

Run a specific group:

```bash
python runner.py run --group G1     # G1 … G8
```

Run a single test by id:

```bash
python runner.py run --poc POC-06a
```

Preview the exact commands without touching Azure:

```bash
python runner.py run --all --dry-run
```

Resume an interrupted run (skips already-passed tests):

```bash
python runner.py run --all --resume
```

Useful global flags: `--config PATH`, `--phase-gate {phase1|phase2|production}`,
`--timeout SECONDS`, and (on `run`) `--skip-preflight`.

---

## 5. Reports & phase gate

Reports are generated automatically after every run into `reports/`:

- `report_<run_id>.html` — self-contained styled HTML (summary, phase-gate
  evaluation, per-group tables with expandable evidence, blockers section)
- `report_<run_id>.md` — Markdown summary
- `phase_gate_<run_id>.json` — machine-readable phase-gate verdict
- `results_<run_id>.json` — full result store (used for `--resume`)
- `session_<timestamp>.log` — every command, stdout, stderr, rc, and duration

Regenerate a report for an existing run:

```bash
python runner.py report --run-id <RUN_ID>
```

Evaluate the phase gate for the latest run:

```bash
python runner.py gate
```

List every test case with its gates and prerequisites:

```bash
python runner.py list
```

---

## 6. Phase gate summary

Phase gates are **cumulative** — `phase2` includes all of `phase1`; `production`
includes all of `phase2`. A gate is *satisfied* only when every POC below passes.

| Gate | POCs that must pass |
|---|---|
| **phase1** | POC-01…POC-09, POC-06a, POC-30, POC-13, POC-15, POC-16, POC-17, POC-20, POC-THROTTLE-01, POC-RI-01 |
| **phase2** | *all phase1* + POC-11, POC-12, POC-14, POC-31, POC-32, POC-18, POC-19, POC-VMSS-DR, POC-RI-02 |
| **production** | *all phase2* + POC-10, POC-THROTTLE-02, POC-THROTTLE-03 |

The authoritative mapping lives in `PHASE_GATE_REQUIREMENTS` in
`acrme_suite/runner_core.py`.

---

## 7. Test groups

| Group | POCs | Theme |
|---|---|---|
| **G1** | POC-01…05 | CRG creation & basic reservation lifecycle |
| **G2** | POC-06, 06a, 07…10 | Cross-subscription sharing (Preview) |
| **G3** | POC-11…14 | DR capacity & failover |
| **G4** | POC-30…32 | Quota Group validation (Preview gate) |
| **G5** | POC-15…20 | Engine safety controls |
| **G6** | POC-AKS-01/02, POC-VMSS-01/02/03, POC-VMSS-DR | AKS & VMSS behaviour |
| **G7** | POC-THROTTLE-01/02/03 | API rate & throttle |
| **G8** | POC-RI-01/02 | Reserved Instance discount scope |

---

## 8. Important warnings

- **Preview features.** Shared CRG (G2), Quota Groups (G4), and VMSS shared-CRG
  reprovisioning (POC-VMSS-DR) are **Public Preview**. The suite pins
  `api-version=2024-03-01` (falling back to `2024-03-01-preview`) for sharing,
  and `2025-03-01-preview` for Quota Groups. **POC-30 is a hard gate** — if the
  Quota Groups API is unavailable, POC-31/POC-32 are reported *blocked*.
- **Destructive tests.** POC-12 deallocates the primary VM; POC-05/POC-14
  disassociate VMs; POC-10 mutates the sharing profile heavily. Run against a
  dedicated POC environment only.
- **Engine-dependent tests.** POC-18/POC-19/POC-20 require the ACRME engine to be
  deployed. They return **blocked** with an "engine required" note until then.
- **Documentation-gathering tests.** POC-15, POC-VMSS-DR, POC-AKS-02 (and the
  VMSS model tests) pass as long as the command executed and the result was
  recorded — the outcome itself is the evidence, not a fixed pass/fail value.
- **Test isolation.** All created resources carry the `acrme-poc-` prefix. Use a
  clean resource group and clean up between full runs (see below).
- **Consumer discovery.** The standard CRG *list* API omitting shared CRGs is a
  documented Azure behaviour; discovery relies on Azure Resource Graph (POC-07).

---

## 9. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `Config file not found` | Copy `config.yaml.template` → `config.yaml` and fill values. |
| `regions … must be three distinct regions` | Set distinct `primary` / `dr` / `nonprod`. |
| `az CLI not found on PATH` | Install the Azure CLI and ensure `az` is on `PATH`. |
| POC-07/POC-16 fail with graph errors | `az extension add --name resource-graph`. |
| POC-06 fails on all api-versions | Confirm the sharing Preview is enabled for the tenant/subscription. |
| POC-30 blocked | Quota Groups Preview API not available in this tenant/region. |
| Many tests `blocked` | A prerequisite failed — check the earliest failing POC first. |
| Timeouts on VM create | Increase `timeout_seconds` in config or via `--timeout`. |

---

## 10. Project layout

```
acrme_test_suite/
├── README.md
├── requirements.txt
├── config.yaml.template
├── runner.py                      # CLI entry point
├── acrme_suite/
│   ├── config.py                  # config loader + validator + derived values
│   ├── az_client.py               # subprocess wrapper for az / az rest
│   ├── result_store.py            # JSON result store (+ resume)
│   ├── runner_core.py             # TestCase/TestResult, registry, phase gates
│   ├── reporter.py                # HTML + Markdown + phase-gate JSON
│   ├── preflight.py               # PF-01..PF-10
│   └── tests/
│       ├── g1_crg_basics.py
│       ├── g2_sharing.py
│       ├── g3_dr_failover.py
│       ├── g4_quota_groups.py
│       ├── g5_safety.py
│       ├── g6_aks_vmss.py
│       ├── g7_throttle.py
│       └── g8_ri_discount.py
└── reports/                       # HTML/MD/JSON reports + session logs
```

---

## 11. Cleanup

The suite records a `cleanup_command` in the evidence of every resource-creating
test. To tear down, run the recorded commands, or generally:

```bash
# VMs
az vm delete -g <provider_rg> -n acrme-poc-vm-03-01 --yes
# Reservations then CRGs
az capacity reservation delete -g <provider_rg> -c <crg> -n <res> --yes
az capacity reservation group delete -g <provider_rg> -n <crg> --yes
```

Always deallocate/disassociate VMs *before* deleting reservations and CRGs.
