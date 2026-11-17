#!/usr/bin/env python3
"""ACRME grounding checker.

1. Resolves the current requirements baseline (highest Document Control version
   among repo and uploaded copies) and reports drift.
2. Lints research/design markdown: unknown requirement codes, stale baseline
   citations, untagged Azure-behaviour claims, unflagged spec gaps, Preview
   sharing used as a production dependency, and rejected design directions.
3. Optionally checks the deployment standard and requires deployment-related
   outputs to include its gate, source citation, and known config-drift notice.

Exit code: 0 = no errors, 1 = errors found, 2 = usage/setup problem.
Stdlib only.
"""
import argparse
import difflib
import glob
import os
import re
import sys
from pathlib import Path

DEFAULT_REPO = Path(__file__).resolve().parents[4]
CODE_RE = re.compile(
    r"\b(?:REG|DEC|ENV|CAP|QUA|RDY|PLC|DR|FIN|INT|DAT|OBS|GOV|NFR|OPS|POC|DEP)"
    r"-\d{3}[a-z]?\b"
)
HC_RE = re.compile(r"\bHC-(\d{1,2})\b")
TAG_RE = re.compile(
    r"\[(Documented|Tested|Decided|Derived|Assumed|Verified|Undocumented|Baseline)\b[^\]]*\]"
    r"|SPEC GAP|Configurable",
    re.I,
)
VERSION_ROW_RE = re.compile(
    r"\|\s*\*\*Version\*\*\s*\|\s*(?:\*\*)?([0-9]+(?:\.[0-9]+)*)(?:\*\*)?"
)
BASELINE_CITE_RE = re.compile(r"[Bb]aseline[\s*:]*v?(\d+(?:\.\d+)+)")
AZURE_CLAIM_RE = re.compile(
    r"\b(Azure|ARM|CRG|capacity reservation|quota group|Quota Group|sharing|"
    r"availability zone|logical zone)\b.*\b(supports?|does not|cannot|can't|must|"
    r"requires?|limit(?:ed)?|allows?|only|maximum|up to|guarantee[sd]?)\b",
    re.I,
)
# Formula terms that were spec gaps and are now decided in the baseline: term -> (citation regex, decision).
DECIDED_TERMS = {
    "total_customers": (re.compile(r"PLC-012|A\.10|geograph", re.I),
                        "γ denominator = distinct customers per geography, zero rule γ=1 (PLC-012, A.10)"),
}
STALE_GAP_RE = re.compile(r"SPEC GAP|OPEN ISSUE|spec(?:ification)? gap|UNDEFINED|not defined|undefined", re.I)
RESOLVED_RE = re.compile(r"PLC-012|A\.10|resolved|decided|closed", re.I)
PROPOSED_RE = re.compile(r"propos|\badd\b|\bnew\b|candidate", re.I)
ANTI_PATTERNS = [
    (re.compile(r"\b(recommend|adopt|use|propose)\w*\b[^.\n]{0,60}\bmulti-?cloud\b", re.I),
     "multi-cloud DR proposed — rejected at ELT (baseline §2)"),
    (re.compile(r"\bsum[- ]of[- ](all )?(the )?source", re.I),
     "DR sized as a sum of sources — baseline requires max-not-sum (DR-017)"),
    (re.compile(r"\bdelete (the |a |an )?(capacity )?reservation\b", re.I),
     "reservation deletion — use set-to-zero (CAP-009) or decommission workflow (CAP-010)"),
    (re.compile(r"\bBicep\b[^.\n]{0,80}\b(runtime|reconcil|engine logic)", re.I),
     "Bicep for engine runtime logic — Bicep is infrastructure layer only"),
]
# Lines that quote a rejected/superseded rule on purpose (e.g. baseline App. D "❌ over-provisions",
# hard-constraints "Superseded — do not use") are documentation of the rejection, not a recommendation.
REJECTED_MARK_RE = re.compile(
    r"❌|\b(superseded|retired|deprecated|rejected|do not use|over-provisions|original formula|version 2\.0|v2\.0)\b", re.I)
SHARED_RES = r"(?:reservation sharing|sharing (?:the )?(?:CRG|reservation|capacity)|shared (?:CRG|reservation|capacity reservation|reservation group))"
SHARING_PROD_RE = re.compile(
    rf"{SHARED_RES}[^.\n]{{0,60}}\bproduction\b|\bproduction\b[^.\n]{{0,60}}{SHARED_RES}",
    re.I,
)
SHARING_SAFE_RE = re.compile(r"Preview|DEP-001|CAP-013|not GA|until .*GA|deploying subscription", re.I)
DEPLOYMENT_RE = re.compile(
    r"environment_v2\.yaml|capacity_request_policy|deployment.standard|"
    r"deployment readiness|blue.green|series allowlist|VM.series",
    re.I,
)
ENVIRONMENT_EFFECTIVE_DATE = "2026-10-23"
DEPLOYMENT_CONFIG_PATHS = (
    "capacity_request_policy.effective_date",
    "capacity_request_policy.allowed_vm_series.series",
    "capacity_request_policy.approval.scope",
    "capacity_request_policy.approval.required_approvals",
    "capacity_request_policy.approval.evidence",
    "capacity_request_policy.deployment_validation.exact_vm_size_required",
    "capacity_request_policy.deployment_validation.region_zone_and_subscription_eligibility_required",
    "capacity_request_policy.deployment_validation.reservation_support_required_when_enforced",
    "capacity_request_policy.deployment_validation.capacity_and_both_quota_caps_required",
    "compute_subscription_policies.standard.cluster_capacity.max_total_clusters",
    "compute_subscription_policies.standard.cluster_capacity.max_active_clusters",
    "compute_subscription_policies.standard.deployment.model",
    "compute_subscription_policies.standard.deployment.rollout.capacity_check",
    "compute_subscription_policies.standard.deployment.rollout.validate_replacement_before_traffic_cutover",
    "compute_subscription_policies.standard.dr_clusters.provision",
    "compute_subscription_policies.standard.dr_clusters.rollout_headroom_conflict_policy",
    "resource_subscription_policies.standard.scale_out.trigger_scope",
    "capacity_reservation_policies.standard.sharing.scope",
    "capacity_reservation_policies.standard.sharing.production_capacity_shared",
    "capacity_reservation_policies.standard.sharing.feature_maturity",
    "capacity_reservation_policies.standard.sharing.production_dependency_allowed",
    "capacity_reservation_policies.standard.sharing.fallback",
    "capacity_reservation_policies.standard.sharing.provider_subscription",
    "capacity_reservation_policies.standard.dr_foundation.subscription",
    "capacity_reservation_policies.standard.dr_foundation.depends_on_sharing",
    "capacity_reservation_policies.standard.pending_decisions",
    "environment_profiles.standard.subscription_model",
    "geographies",
)
DEPLOYMENT_EXPECTED_VALUES = {
    "capacity_request_policy.effective_date": ENVIRONMENT_EFFECTIVE_DATE,
    "capacity_request_policy.allowed_vm_series.matching": "exact_series_membership",
    "capacity_request_policy.approval.scope": "new_capacity_requests",
    "capacity_request_policy.approval.approval_requirement": "all_required",
    "capacity_request_policy.approval.existing_protective_reconciliation": "unchanged",
    "capacity_request_policy.deployment_validation.exact_vm_size_required": "true",
    "capacity_request_policy.deployment_validation.region_zone_and_subscription_eligibility_required": "true",
    "capacity_request_policy.deployment_validation.reservation_support_required_when_enforced": "true",
    "capacity_request_policy.deployment_validation.capacity_and_both_quota_caps_required": "true",
    "compute_subscription_policies.standard.deployment.model": "blue_green",
    "compute_subscription_policies.standard.deployment.rollout.capacity_check": "current_and_replacement_overlap",
    "compute_subscription_policies.standard.deployment.rollout.validate_replacement_before_traffic_cutover": "true",
    "compute_subscription_policies.standard.dr_clusters.provision": "before_dr",
    "capacity_reservation_policies.standard.sharing.scope": "domain_group_and_region",
    "capacity_reservation_policies.standard.sharing.production_capacity_shared": "false",
    "capacity_reservation_policies.standard.sharing.feature_maturity": "preview",
    "capacity_reservation_policies.standard.sharing.production_dependency_allowed": "false",
    "capacity_reservation_policies.standard.sharing.fallback": "reservation_in_deploying_subscription",
    "capacity_reservation_policies.standard.dr_foundation.subscription": "dedicated_dr_compute_subscription",
    "capacity_reservation_policies.standard.dr_foundation.depends_on_sharing": "false",
}
def parse_simple_yaml_paths(path):
    """Extract dotted keys and list values from the repository's indentation-based policy YAML."""
    values = {}
    stack = []
    with open(path, encoding="utf-8") as fh:
        for line_no, raw_line in enumerate(fh, 1):
            line = raw_line.rstrip()
            if not line.strip() or line.lstrip().startswith("#") or line.lstrip().startswith("---"):
                continue
            indent = len(line) - len(line.lstrip(" "))
            content = line.strip()
            if content.startswith("- "):
                if stack:
                    key_path = ".".join(key for _, key in stack)
                    if not isinstance(values.get(key_path), list):
                        values[key_path] = []
                    values[key_path].append(content[2:].strip().strip("'\""))
                continue
            match = re.match(r"([^:#][^:]*):(?:\s*(.*))?$", content)
            if not match:
                continue
            key, raw_value = match.group(1).strip(), (match.group(2) or "").strip()
            while stack and stack[-1][0] >= indent:
                stack.pop()
            key_path = ".".join([*(entry[1] for entry in stack), key])
            value = re.sub(r"\s+#.*$", "", raw_value).strip()
            if not value:
                values.setdefault(key_path, None)
                stack.append((indent, key))
            else:
                values[key_path] = value.strip("'\"")
    return values


def deployment_standard_status(repo):
    """Return config errors and warnings without treating file drift as an authority decision."""
    errors, warns = [], []
    v2_path = os.path.join(repo, "environment_v2.yaml")
    legacy_path = os.path.join(repo, "environment.yaml")
    if not os.path.isfile(v2_path):
        return [f"deployment standard not found: {v2_path}"], warns

    try:
        v2_values = parse_simple_yaml_paths(v2_path)
    except OSError as exc:
        return [f"cannot read deployment standard {v2_path}: {exc}"], warns

    missing = [key for key in DEPLOYMENT_CONFIG_PATHS if key not in v2_values]
    if missing:
        errors.append("environment_v2.yaml is missing required policy keys: " + ", ".join(missing))
    changed = [
        f"{key}={v2_values.get(key)!r} (expected {expected!r})"
        for key, expected in DEPLOYMENT_EXPECTED_VALUES.items()
        if key in v2_values and v2_values[key] != expected
    ]
    if changed:
        errors.append(
            "environment_v2.yaml differs from the deployment guardrails encoded by this checker; "
            "review the new standard and update the checker if the change is intentional: " + "; ".join(changed)
        )
    series = v2_values.get("capacity_request_policy.allowed_vm_series.series", [])
    if not isinstance(series, list) or not series:
        errors.append("environment_v2.yaml must contain a non-empty allowed VM-series list")
    elif len(series) != len(set(series)):
        errors.append("environment_v2.yaml allowed VM-series list contains duplicates")
    approvals = v2_values.get("capacity_request_policy.approval.required_approvals", [])
    if not isinstance(approvals, list) or not {"business", "finance"}.issubset(set(approvals)):
        errors.append("environment_v2.yaml must require both business and finance approval")

    if not os.path.isfile(legacy_path):
        warns.append("environment.yaml is absent; cannot compare deployment configuration drift")
    else:
        with open(legacy_path, encoding="utf-8") as fh:
            legacy_lines = fh.readlines()
        with open(v2_path, encoding="utf-8") as fh:
            v2_lines = fh.readlines()
        if legacy_lines != v2_lines:
            delta = list(difflib.unified_diff(
                legacy_lines, v2_lines, fromfile="environment.yaml",
                tofile="environment_v2.yaml", n=0,
            ))
            changed = sum(1 for line in delta if line.startswith(("+", "-")) and not line.startswith(("+++", "---")))
            warns.append(
                f"environment.yaml and environment_v2.yaml differ ({changed} changed lines); "
                "environment.yaml is the historical what-if model; environment_v2.yaml is the owner-confirmed standard (17 Nov 2026)"
            )
    return errors, warns


def lint_deployment_output(text, deployment_drift):
    errors, warns = [], []
    if not DEPLOYMENT_RE.search(text):
        return errors, warns

    if not re.search(r"Deployment-standard compliance", text, re.I):
        errors.append("deployment-related output is missing the Deployment-standard compliance gate")
    elif not re.search(
        r"Deployment-standard compliance.{0,100}\b(ALIGNED|BLOCKED|OPEN|N/A)\b",
        text,
        re.I | re.S,
    ):
        errors.append("deployment-standard gate must state ALIGNED, BLOCKED, OPEN, or N/A")
    if ENVIRONMENT_EFFECTIVE_DATE not in text:
        errors.append(
            f"deployment-related output must cite environment_v2.yaml effective date {ENVIRONMENT_EFFECTIVE_DATE}"
        )
    if not any(key in text for key in DEPLOYMENT_CONFIG_PATHS):
        errors.append("deployment-related output must cite at least one exact environment_v2.yaml key path")
    if deployment_drift and not re.search(r"environment\.yaml|ENV-V2-001|configuration authority", text, re.I):
        errors.append(
            "deployment-related output must disclose environment.yaml drift and unresolved configuration authority"
        )
    return errors, warns


def parse_version(text):
    m = VERSION_ROW_RE.search(text)
    return m.group(1) if m else None


def vkey(v):
    return tuple(int(p) for p in v.split(".")) if v else (0,)


def resolve_baseline(repo, uploaded_baseline=None):
    candidates = sorted(glob.glob(os.path.join(repo, "Requirements", "acrme_requirements_baseline_v*.md")))
    if uploaded_baseline:
        if not os.path.isfile(uploaded_baseline):
            raise FileNotFoundError(f"uploaded baseline not found: {uploaded_baseline}")
        candidates.append(uploaded_baseline)
    found = []
    for path in candidates:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        found.append((parse_version(text), path, text))
    if not found:
        return None, []
    current = max(found, key=lambda f: vkey(f[0]))
    return current, found


def known_codes(repo, baseline_text):
    corpus = [baseline_text]
    for rel in ("Reference-Material/reference/acrme_requirements_code_glossary.md",
                "Requirements/acrme_complete_requirements_reference.md"):
        p = os.path.join(repo, rel)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as fh:
                corpus.append(fh.read())
    codes = set()
    for text in corpus:
        codes.update(CODE_RE.findall(text))
    return codes


def paragraphs(text):
    """Yield (start_line, paragraph_text) skipping fenced code blocks."""
    lines = text.splitlines()
    buf, start, in_fence = [], 1, False
    for i, line in enumerate(lines, 1):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if line.strip() == "":
            if buf:
                yield start, "\n".join(buf)
            buf = []
            continue
        if not buf:
            start = i
        buf.append(line)
    if buf:
        yield start, "\n".join(buf)


def lint(path, repo, current_version, codes, deployment_drift=False):
    errors, warns = [], []
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    is_baseline_source = Path(path).name.startswith("acrme_requirements_baseline_v")

    for code in sorted(set(CODE_RE.findall(text)) - codes):
        ctx = [ln for ln in text.splitlines() if code in ln]
        if any(PROPOSED_RE.search(ln) for ln in ctx):
            warns.append(f"proposed code {code} is not in baseline v{current_version} — keep it marked as a baseline-change candidate")
        else:
            errors.append(f"unknown requirement code {code} (not in baseline, glossary, or complete reference)")
    for n in sorted({int(x) for x in HC_RE.findall(text)}):
        if not 1 <= n <= 11:
            errors.append(f"HC-{n} does not exist (HC-1..HC-11)")

    # A baseline is the normative input source, not a research/design output.
    if is_baseline_source:
        return errors, warns

    cited = {v for v in BASELINE_CITE_RE.findall(text)}
    if current_version and cited and current_version not in cited:
        warns.append(f"cites baseline {', '.join(sorted(cited))} but current is v{current_version}")
    if current_version and not cited:
        warns.append("no baseline version cited — add the header block from output-templates.md")

    for line_no, para in paragraphs(text):
        for offset, chunk in enumerate(para.splitlines()):
            ln = line_no + offset
            if chunk.lstrip().startswith("#") or re.fullmatch(r"[\s|:\-]+", chunk):
                continue
            if AZURE_CLAIM_RE.search(chunk) and not TAG_RE.search(chunk) and not CODE_RE.search(chunk):
                warns.append(f"L{ln}: Azure-behaviour claim without evidence tag or code: {chunk.strip()[:110]}")
            if SHARING_PROD_RE.search(chunk) and not SHARING_SAFE_RE.search(para):
                warns.append(f"L{ln}: shared reservation tied to production without Preview/DEP-001/CAP-013 caveat")
            for rx, msg in ANTI_PATTERNS:
                if (rx.search(chunk) and not REJECTED_MARK_RE.search(chunk)
                        and not re.search(r"\b(not|never|rejected|don't|do not|avoid)\b", chunk, re.I)):
                    errors.append(f"L{ln}: {msg}")
    # A formerly-undefined term must cite its decision, and must not still be described as a gap.
    for term, (cite_re, why) in DECIDED_TERMS.items():
        uses = [(ln, p) for ln, p in paragraphs(text) if term in p]
        for ln, p in uses:
            if STALE_GAP_RE.search(p) and not RESOLVED_RE.search(p):
                errors.append(f"L{ln}: `{term}` still described as a spec gap — now decided: {why}")
        if uses and not any(cite_re.search(p) for _, p in uses):
            warns.append(f"L{uses[0][0]}: `{term}` used {len(uses)}x without citing PLC-012/A.10 — {why}")
    deployment_errors, deployment_warns = lint_deployment_output(text, deployment_drift)
    errors.extend(deployment_errors)
    warns.extend(deployment_warns)
    return errors, warns


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", help="markdown outputs to lint")
    ap.add_argument("--repo", default=os.environ.get("ACRME_REPO", DEFAULT_REPO))
    ap.add_argument(
        "--uploaded-baseline",
        default=os.environ.get("ACRME_UPLOADED_BASELINE"),
        help="optional external baseline copy to compare (or set ACRME_UPLOADED_BASELINE)",
    )
    ap.add_argument("--baseline-only", action="store_true", help="only resolve the current baseline")
    ap.add_argument(
        "--deployment-standard",
        action="store_true",
        help="audit environment_v2.yaml, report environment.yaml drift, and enforce deployment-output checks",
    )
    ap.add_argument("--max-warn", type=int, default=25, help="max warnings printed per file")
    args = ap.parse_args()

    try:
        current, found = resolve_baseline(args.repo, args.uploaded_baseline)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if not current:
        print(f"ERROR: no baseline found under {args.repo}/Requirements", file=sys.stderr)
        return 2
    cur_version, cur_path, cur_text = current
    print(f"Current baseline: v{cur_version}  ->  {cur_path}")
    stale = [(v, p) for v, p, _ in found if vkey(v) < vkey(cur_version)]
    for v, p in stale:
        print(f"  DRIFT: {p} is v{v} (behind v{cur_version}) — do not cite it")
    if args.baseline_only and not args.deployment_standard:
        return 0
    if not args.files and not args.deployment_standard:
        ap.error("pass at least one file, or --baseline-only")

    deployment_related = args.deployment_standard
    for path in args.files:
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                if DEPLOYMENT_RE.search(fh.read()):
                    deployment_related = True
                    break
    deployment_drift = False
    total_errors = 0
    if deployment_related:
        config_errors, config_warns = deployment_standard_status(args.repo)
        deployment_drift = any("configuration authority is unresolved" in warning for warning in config_warns)
        print("\nDeployment standard audit (environment_v2.yaml):")
        for error in config_errors:
            print(f"  ERROR {error}")
        for warning in config_warns:
            print(f"  WARN  {warning}")
        if not config_errors and not config_warns:
            print("  PASS: required deployment policy keys and guardrail values are present")
        total_errors += len(config_errors)

    if args.baseline_only:
        return 1 if total_errors else 0

    codes = known_codes(args.repo, cur_text)
    for f in args.files:
        if not os.path.exists(f):
            print(f"\n{f}: ERROR file not found")
            total_errors += 1
            continue
        errors, warns = lint(f, args.repo, cur_version, codes, deployment_drift)
        total_errors += len(errors)
        print(f"\n{f}: {len(errors)} error(s), {len(warns)} warning(s)")
        for e in errors:
            print(f"  ERROR {e}")
        for w in warns[: args.max_warn]:
            print(f"  WARN  {w}")
        if len(warns) > args.max_warn:
            print(f"  … {len(warns) - args.max_warn} more warnings (raise --max-warn)")
    return 1 if total_errors else 0


if __name__ == "__main__":
    sys.exit(main())
