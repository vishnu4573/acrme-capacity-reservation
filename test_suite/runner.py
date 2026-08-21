#!/usr/bin/env python3
"""ACRME POC Test Suite — command line entry point.

Usage examples::

    python runner.py --help
    python runner.py preflight
    python runner.py run --group G1
    python runner.py run --all
    python runner.py run --poc POC-06a
    python runner.py run --all --dry-run
    python runner.py run --all --resume
    python runner.py report --run-id <RUN_ID>
    python runner.py gate
    python runner.py list
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from acrme_suite.az_client import AzClient
from acrme_suite.config import Config, ConfigError, set_active_config
from acrme_suite.preflight import Preflight, preflight_blocks_run
from acrme_suite.reporter import Reporter
from acrme_suite.result_store import ResultStore
from acrme_suite.runner_core import (
    REGISTRY,
    TestRunner,
    build_registry,
    cumulative_gate_requirements,
)

try:
    from tabulate import tabulate
except ImportError:  # pragma: no cover - tabulate is a declared dependency
    tabulate = None


# ----------------------------------------------------------------------
# Argument parsing
# ----------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="runner.py",
        description="ACRME POC test automation suite (Azure CLI driven).",
    )
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true", default=None,
                        help="Print commands, do not execute")
    parser.add_argument("--phase-gate", dest="phase_gate", default=None,
                        help="Override phase gate (phase1|phase2|production)")
    parser.add_argument("--timeout", dest="timeout", type=int, default=None,
                        help="Per-test timeout seconds")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("preflight", help="Run pre-flight checks (PF-01..PF-10)")

    run_p = sub.add_parser("run", help="Run tests")
    group = run_p.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Run all tests in order")
    group.add_argument("--group", help="Run a group by id (e.g. G1)")
    group.add_argument("--poc", help="Run a single test by POC id")
    run_p.add_argument("--resume", action="store_true", help="Resume last run; skip passed")
    run_p.add_argument("--skip-preflight", action="store_true",
                       help="Skip pre-flight checks (not recommended)")
    # Accept these after the subcommand too (e.g. `run --all --dry-run`). Using
    # SUPPRESS means an absent flag here does NOT overwrite a value supplied
    # before the subcommand.
    run_p.add_argument("--dry-run", dest="dry_run", action="store_true",
                       default=argparse.SUPPRESS, help="Print commands, do not execute")
    run_p.add_argument("--phase-gate", dest="phase_gate", default=argparse.SUPPRESS,
                       help="Override phase gate (phase1|phase2|production)")
    run_p.add_argument("--timeout", dest="timeout", type=int, default=argparse.SUPPRESS,
                       help="Per-test timeout seconds")

    rep_p = sub.add_parser("report", help="Generate/regenerate a report for a run")
    rep_p.add_argument("--run-id", required=True, help="Run id to report on")

    sub.add_parser("gate", help="Evaluate phase gate for the latest run")
    sub.add_parser("list", help="List all test cases with gates and prerequisites")

    return parser


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _load_config(args) -> Config:
    cfg = Config.load(args.config)
    if args.dry_run:
        cfg.dry_run = True
    if args.phase_gate:
        cfg.phase_gate = args.phase_gate
        cfg.validate()
    if args.timeout:
        cfg.timeout_seconds = args.timeout
    set_active_config(cfg)
    return cfg


def _make_client(cfg: Config) -> AzClient:
    return AzClient(timeout_seconds=cfg.timeout_seconds, dry_run=cfg.dry_run)


def _print_preflight(results) -> bool:
    """Print pre-flight results; return True if run may proceed."""
    rows = [[r.check_id, r.name, r.status.upper(), r.detail] for r in results]
    if tabulate:
        print(tabulate(rows, headers=["ID", "Check", "Status", "Detail"], tablefmt="github"))
    else:
        for r in rows:
            print(" | ".join(str(c) for c in r))
    blocking = preflight_blocks_run(results)
    if blocking:
        print("\n[ABORT] Hard-blocking pre-flight failures:")
        for b in blocking:
            print(f"  - {b.check_id} {b.name}: {b.detail}")
        return False
    return True


# ----------------------------------------------------------------------
# Command handlers
# ----------------------------------------------------------------------
def cmd_preflight(args) -> int:
    cfg = _load_config(args)
    az = _make_client(cfg)
    results = Preflight(cfg, az).run_all()
    ok = _print_preflight(results)
    return 0 if ok else 3


def cmd_list(args) -> int:
    build_registry()
    rows = []
    for case in REGISTRY.all():
        rows.append([
            case.poc_id, case.group, ",".join(case.phase_gates),
            ",".join(case.prerequisites) or "-", case.name,
        ])
    if tabulate:
        print(tabulate(rows, headers=["POC", "Group", "Gates", "Prereqs", "Name"],
                       tablefmt="github"))
    else:
        for r in rows:
            print(" | ".join(str(c) for c in r))
    print(f"\nTotal: {len(rows)} test cases across {len(REGISTRY.groups())} groups.")
    return 0


def _select_cases(args) -> List:
    build_registry()
    if args.all:
        return REGISTRY.all()
    if args.group:
        cases = REGISTRY.by_group(args.group)
        if not cases:
            print(f"[ERROR] No tests found for group '{args.group}'.")
        return cases
    if args.poc:
        case = REGISTRY.get(args.poc)
        if not case:
            print(f"[ERROR] Unknown POC id '{args.poc}'.")
            return []
        return [case]
    return []


def cmd_run(args) -> int:
    cfg = _load_config(args)
    az = _make_client(cfg)
    build_registry()

    # Pre-flight (unless skipped or a single non-G1 poc).
    if not args.skip_preflight:
        print("=== Pre-flight checks ===")
        pf_results = Preflight(cfg, az).run_all()
        if not _print_preflight(pf_results):
            return 3
        print()

    cases = _select_cases(args)
    if not cases:
        return 2

    # Resume: reuse latest run; else start a fresh run.
    if args.resume:
        run_id = ResultStore.latest_run_id()
        if run_id:
            store = ResultStore(run_id=run_id)
            print(f"[RESUME] Continuing run {run_id}")
        else:
            print("[RESUME] No previous run found; starting a new run.")
            store = ResultStore.new_run("reports", cfg.phase_gate, cfg.snapshot(), cfg.dry_run)
    else:
        store = ResultStore.new_run("reports", cfg.phase_gate, cfg.snapshot(), cfg.dry_run)

    print(f"=== Running {len(cases)} test(s) | run_id={store.run_id} | "
          f"phase_gate={cfg.phase_gate} | dry_run={cfg.dry_run} ===")
    runner = TestRunner(cfg, az, store, resume=args.resume)
    runner.run_cases(cases)
    store.mark_finished()

    # Generate reports.
    reporter = Reporter(store.metadata, store.all_results(), REGISTRY)
    paths = reporter.write_all()
    print("\n=== Reports ===")
    for kind, path in paths.items():
        print(f"  {kind}: {path}")
    print(f"  results: {store.path}")
    print(f"  session log: {az.session_log}")

    # Exit code reflects failures.
    statuses = [r.get("status") for r in store.all_results()]
    if "fail" in statuses:
        return 1
    return 0


def cmd_report(args) -> int:
    store = ResultStore(run_id=args.run_id)
    if not store.all_results():
        print(f"[ERROR] No results found for run {args.run_id}.")
        return 2
    build_registry()
    reporter = Reporter(store.metadata, store.all_results(), REGISTRY)
    paths = reporter.write_all()
    print(f"Report regenerated for run {args.run_id}:")
    for kind, path in paths.items():
        print(f"  {kind}: {path}")
    return 0


def cmd_gate(args) -> int:
    run_id = ResultStore.latest_run_id()
    if not run_id:
        print("[ERROR] No runs found. Execute `python runner.py run --all` first.")
        return 2
    store = ResultStore(run_id=run_id)
    build_registry()
    reporter = Reporter(store.metadata, store.all_results(), REGISTRY)
    evaluation = reporter.evaluate_phase_gates()
    print(f"Phase gate evaluation for run {run_id} "
          f"(configured gate: {store.metadata.get('phase_gate')}):\n")
    for gate, data in evaluation["gates"].items():
        verdict = "SATISFIED" if data["gate_satisfied"] else "NOT SATISFIED"
        print(f"  {gate}: {verdict} ({data['passed_count']}/{data['required_count']})")
        for item in data["items"]:
            if not item["satisfied"]:
                print(f"      - {item['poc_id']}: {item['status']}")
    # Also write the JSON artefact.
    path = reporter._write_phase_gate_json(evaluation)  # noqa: SLF001 (intentional)
    print(f"\nWritten: {path}")
    return 0


COMMANDS = {
    "preflight": cmd_preflight,
    "run": cmd_run,
    "report": cmd_report,
    "gate": cmd_gate,
    "list": cmd_list,
}


def main(argv: Optional[List[str]] = None) -> int:
    """Parse arguments and dispatch to the requested command."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return COMMANDS[args.command](args)
    except ConfigError as exc:
        print(f"[CONFIG ERROR] {exc}")
        return 2
    except KeyboardInterrupt:  # pragma: no cover
        print("\n[INTERRUPTED]")
        return 130


if __name__ == "__main__":
    sys.exit(main())
