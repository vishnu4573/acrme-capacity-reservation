"""Group 12 — v2.4 CRG structure & resource naming (CAP-023 / OPS-006 / C-12).

* **CAP-023** (extends CAP-011) — for each **environment** (Prod, CVAL/NonProd,
  DR) within a subscription and region, reservations are organised into an
  explicit CRG structure: **one regional (non-zonal) CRG plus one CRG per
  availability zone**. Example (Prod in East US 2, three zones):
  ``crg-pr-eus2-reg``, ``crg-pr-eus2-az1``, ``crg-pr-eus2-az2``,
  ``crg-pr-eus2-az3``. Environments are never mixed within a CRG (ENV-003).

* **OPS-006 / C-12** — all managed resource groups, CRGs, and subscriptions
  follow a deterministic, parseable naming convention with env / region /
  purpose tokens and a zero-padded instance **counter**. Reference patterns:
  ``rg-odcr-<env>-<region>-<NN>``; ``crg-<env>-<region>-<scope>`` with
  ``scope ∈ {reg, az1, az2, az3}``; ``sub-<org>-<domain>-<purpose>-<NN>``.
  The engine validates managed resources against the convention and flags
  non-conforming names as governance exceptions. The CRG scope tokens map
  directly onto the CAP-023 structure.

All validation and structure derivation is pure/offline. A **live** case that
enumerates real CRGs in Azure and asserts the structure is BLOCKED until the
provider subscription is available.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence, Tuple

from ..az_client import AzClient
from ..config import Config
from ..runner_core import Registry, TestCase, TestResult

GROUP = "G12"
REQ_CAP_023 = "CAP-023"
REQ_OPS_006 = "OPS-006"
REQ_C12 = "C-12"
REQ_CAP_011 = "CAP-011"

# Deterministic naming patterns (OPS-006 / C-12). Counter width is configurable;
# the default reference convention uses a two-digit zero-padded counter.
_RG_RE = re.compile(r"^rg-odcr-[a-z0-9]+-[a-z0-9]+-\d{2,}$")
_CRG_RE = re.compile(r"^crg-[a-z0-9]+-[a-z0-9]+-(reg|az[1-9])$")
_SUB_RE = re.compile(r"^sub-[a-z0-9]+-[a-z0-9]+-[a-z0-9]+-\d{2,}$")


# ---------------------------------------------------------------------------
# Pure, Azure-free naming / structure logic
# ---------------------------------------------------------------------------
def validate_rg_name(name: str) -> bool:
    """Validate a resource-group name against ``rg-odcr-<env>-<region>-<NN>``."""
    return bool(_RG_RE.match(name))


def validate_crg_name(name: str) -> bool:
    """Validate a CRG name against ``crg-<env>-<region>-<scope>`` (scope reg|azN)."""
    return bool(_CRG_RE.match(name))


def validate_subscription_name(name: str) -> bool:
    """Validate a subscription name against ``sub-<org>-<domain>-<purpose>-<NN>``."""
    return bool(_SUB_RE.match(name))


def expected_crg_set(env_token: str, region_token: str, zone_count: int) -> List[str]:
    """Return the CAP-023 CRG name set for one environment: 1 regional + per-AZ."""
    names = [f"crg-{env_token}-{region_token}-reg"]
    names += [f"crg-{env_token}-{region_token}-az{z}" for z in range(1, zone_count + 1)]
    return names


def flag_nonconforming(names: Sequence[str], kind: str) -> List[str]:
    """Return the names that violate the convention (governance exceptions)."""
    validator = {"rg": validate_rg_name, "crg": validate_crg_name,
                 "sub": validate_subscription_name}[kind]
    return [n for n in names if not validator(n)]


# ---------------------------------------------------------------------------
# Test cases — logic (offline PASS)
# ---------------------------------------------------------------------------
def cap_023_logic(config: Config, az: AzClient) -> TestResult:  # noqa: ARG001
    """CAP-023: one regional CRG + one CRG per AZ, per environment; names conform."""
    evidence: Dict[str, Any] = {"requirement": [REQ_CAP_023, REQ_CAP_011]}
    region = "eus2"
    zone_count = 3
    # env token per CAP-023/OPS-006 example: pr (Prod), cval (CVAL/NonProd), dr (DR).
    env_tokens = {"Prod": "pr", "CVAL": "cval", "DR": "dr"}
    per_env: Dict[str, List[str]] = {}
    ok = True
    for env, token in env_tokens.items():
        crgs = expected_crg_set(token, region, zone_count)
        per_env[env] = crgs
        regional = [c for c in crgs if c.endswith("-reg")]
        zonal = [c for c in crgs if re.search(r"-az\d$", c)]
        conforming = all(validate_crg_name(c) for c in crgs)
        if not (len(regional) == 1 and len(zonal) == zone_count and conforming):
            ok = False

    # Environments must never be mixed within a CRG name (ENV-003): distinct env tokens.
    all_names = [c for lst in per_env.values() for c in lst]
    distinct_env_tokens = {n.split("-")[1] for n in all_names}
    evidence.update({
        "per_environment_crgs": per_env,
        "regional_plus_perAZ_each": {e: {"regional": 1, "per_az": zone_count} for e in env_tokens},
        "distinct_env_tokens": sorted(distinct_env_tokens),
        "example_prod": per_env["Prod"],
    })
    if ok and distinct_env_tokens == {"pr", "cval", "dr"}:
        return TestResult(
            poc_id="POC-CAP-023", status="pass",
            actual_result="Each environment (Prod/CVAL/DR) has exactly one regional CRG "
                          "plus one CRG per AZ (3); all names conform to the convention; "
                          "environments never share a CRG (distinct env tokens).",
            evidence=evidence,
        )
    return TestResult(
        poc_id="POC-CAP-023", status="fail",
        actual_result="CAP-023 CRG structure/derivation did not match expectations.",
        evidence=evidence,
    )


def ops_006_logic(config: Config, az: AzClient) -> TestResult:  # noqa: ARG001
    """OPS-006 / C-12: conforming names validate; non-conforming flagged as exceptions."""
    evidence: Dict[str, Any] = {"requirement": [REQ_OPS_006, REQ_C12]}

    good_rgs = ["rg-odcr-prod-eus2-01", "rg-odcr-cval-swec-02"]
    good_crgs = ["crg-pr-eus2-reg", "crg-pr-eus2-az1", "crg-pr-eus2-az2", "crg-pr-eus2-az3"]
    good_subs = ["sub-jda-cld-core-01"]

    bad_rgs = ["rg-odcr-prod-eus2", "prod-rg-eus2-01", "rg-odcr-prod-eus2-1"]  # missing NN / wrong order / not zero-padded
    bad_crgs = ["crg-pr-eus2-az0", "crg-pr-eus2", "crg-pr-eus2-zone1"]         # az0 invalid / missing scope / wrong token
    bad_subs = ["sub-jda-cld-core", "subscription-core-01"]                     # missing NN / wrong prefix

    good_ok = (
        not flag_nonconforming(good_rgs, "rg")
        and not flag_nonconforming(good_crgs, "crg")
        and not flag_nonconforming(good_subs, "sub")
    )
    rg_flags = flag_nonconforming(bad_rgs, "rg")
    crg_flags = flag_nonconforming(bad_crgs, "crg")
    sub_flags = flag_nonconforming(bad_subs, "sub")
    bad_all_flagged = (
        len(rg_flags) == len(bad_rgs)
        and len(crg_flags) == len(bad_crgs)
        and len(sub_flags) == len(bad_subs)
    )
    evidence.update({
        "good_conforming": good_ok,
        "flagged_rg": rg_flags, "flagged_crg": crg_flags, "flagged_sub": sub_flags,
    })
    if good_ok and bad_all_flagged:
        return TestResult(
            poc_id="POC-OPS-006", status="pass",
            actual_result="All reference-conforming RG/CRG/subscription names validate; "
                          "every non-conforming name (missing/short counter, bad scope "
                          "token, wrong prefix) is flagged as a governance exception.",
            evidence=evidence,
        )
    return TestResult(
        poc_id="POC-OPS-006", status="fail",
        actual_result="Naming validation did not behave per OPS-006 / C-12.",
        evidence=evidence,
    )


# ---------------------------------------------------------------------------
# Test case — live (engine / Azure required → BLOCKED)
# ---------------------------------------------------------------------------
def cap_023_live(config: Config, az: AzClient) -> TestResult:  # noqa: ARG001
    """CAP-023 (live): enumerate real CRGs and assert the per-env regional+per-AZ
    structure and naming — requires the provider subscription to be provisioned."""
    return TestResult(
        poc_id="POC-CAP-023-LIVE", status="blocked",
        actual_result="Engine/live Azure required — enumerate CRGs in the provider "
                      "subscription and assert one regional + one per-AZ CRG per "
                      "environment with OPS-006-conforming names. Blocked until deployment.",
        evidence={"engine_required": True, "requirement": [REQ_CAP_023, REQ_OPS_006]},
    )


def register(registry: Registry) -> None:
    """Register all Group 12 test cases."""
    registry.add(TestCase("POC-CAP-023", GROUP,
                          "CAP-023: regional + per-AZ CRG structure per environment",
                          ["phase1"], [], cap_023_logic))
    registry.add(TestCase("POC-OPS-006", GROUP,
                          "OPS-006/C-12: deterministic RG/CRG/subscription naming + counter",
                          ["phase1"], [], ops_006_logic))
    registry.add(TestCase("POC-CAP-023-LIVE", GROUP,
                          "CAP-023 (live): enumerate real CRGs & assert structure/naming",
                          ["phase2"], [], cap_023_live))
