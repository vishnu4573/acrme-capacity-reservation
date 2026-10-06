#!/usr/bin/env python3
"""ACRME grounding checker.

1. Resolves the current requirements baseline (highest Document Control version
   among repo and uploaded copies) and reports drift.
2. Lints research/design markdown: unknown requirement codes, stale baseline
   citations, untagged Azure-behaviour claims, unflagged spec gaps, Preview
   sharing used as a production dependency, and rejected design directions.

Exit code: 0 = no errors, 1 = errors found, 2 = usage/setup problem.
Stdlib only.
"""
import argparse
import glob
import os
import re
import sys

DEFAULT_REPO = "/home/ubuntu/acrme-capacity-reservation"
UPLOADED_BASELINE = (
    "/home/ubuntu/Uploads/Azure Capacity & Quota Management- "
    "Consolidated Requirements Baseline.md"
)
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
VERSION_ROW_RE = re.compile(r"\|\s*\*\*Version\*\*\s*\|\s*([0-9]+(?:\.[0-9]+)*)")
BASELINE_CITE_RE = re.compile(r"[Bb]aseline[\s*:]*v?(\d+\.\d+)")
AZURE_CLAIM_RE = re.compile(
    r"\b(Azure|ARM|CRG|capacity reservation|quota group|Quota Group|sharing|"
    r"availability zone|logical zone)\b.*\b(supports?|does not|cannot|can't|must|"
    r"requires?|limit(?:ed)?|allows?|only|maximum|up to|guarantee[sd]?)\b",
    re.I,
)
GAP_TERMS = {"total_customers": "γ distribution-fairness term (no defined source/scope/type)"}
PROPOSED_RE = re.compile(r"propos|\badd\b|\bnew\b|candidate", re.I)
GAP_FLAG_RE = re.compile(r"SPEC GAP|OPEN ISSUE|spec(?:ification)? gap|undefined|\[Assumed|blocker", re.I)
ANTI_PATTERNS = [
    (re.compile(r"\b(recommend|adopt|use|propose)\w*\b[^.\n]{0,60}\bmulti-?cloud\b", re.I),
     "multi-cloud DR proposed — rejected at ELT (baseline §2)"),
    (re.compile(r"\bsum of (all )?(the )?source", re.I),
     "DR sized as a sum of sources — baseline requires max-not-sum (DR-017)"),
    (re.compile(r"\bdelete (the |a |an )?(capacity )?reservation\b", re.I),
     "reservation deletion — use set-to-zero (CAP-009) or decommission workflow (CAP-010)"),
    (re.compile(r"\bBicep\b[^.\n]{0,80}\b(runtime|reconcil|engine logic)", re.I),
     "Bicep for engine runtime logic — Bicep is infrastructure layer only"),
]
SHARED_RES = r"(?:reservation sharing|sharing (?:the )?(?:CRG|reservation|capacity)|shared (?:CRG|reservation|capacity reservation|reservation group))"
SHARING_PROD_RE = re.compile(
    rf"{SHARED_RES}[^.\n]{{0,60}}\bproduction\b|\bproduction\b[^.\n]{{0,60}}{SHARED_RES}",
    re.I,
)
SHARING_SAFE_RE = re.compile(r"Preview|DEP-001|CAP-013|not GA|until .*GA|deploying subscription", re.I)


def parse_version(text):
    m = VERSION_ROW_RE.search(text)
    return m.group(1) if m else None


def vkey(v):
    return tuple(int(p) for p in v.split(".")) if v else (0,)


def resolve_baseline(repo):
    candidates = sorted(glob.glob(os.path.join(repo, "Requirements", "acrme_requirements_baseline_v*.md")))
    if os.path.exists(UPLOADED_BASELINE):
        candidates.append(UPLOADED_BASELINE)
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


def lint(path, repo, current_version, codes):
    errors, warns = [], []
    with open(path, encoding="utf-8") as fh:
        text = fh.read()

    for code in sorted(set(CODE_RE.findall(text)) - codes):
        ctx = [ln for ln in text.splitlines() if code in ln]
        if any(PROPOSED_RE.search(ln) for ln in ctx):
            warns.append(f"proposed code {code} is not in baseline v{current_version} — keep it marked as a baseline-change candidate")
        else:
            errors.append(f"unknown requirement code {code} (not in baseline, glossary, or complete reference)")
    for n in sorted({int(x) for x in HC_RE.findall(text)}):
        if not 1 <= n <= 11:
            errors.append(f"HC-{n} does not exist (HC-1..HC-11)")

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
                if rx.search(chunk) and not re.search(r"\b(not|never|rejected|don't|do not|avoid)\b", chunk, re.I):
                    errors.append(f"L{ln}: {msg}")
    # A gap term must be flagged somewhere in the doc, next to the term.
    for term, why in GAP_TERMS.items():
        uses = [(ln, p) for ln, p in paragraphs(text) if term in p]
        if uses and not any(GAP_FLAG_RE.search(p) for _, p in uses):
            errors.append(f"L{uses[0][0]}: `{term}` used {len(uses)}x, never flagged as SPEC GAP — {why}")
    return errors, warns


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", help="markdown outputs to lint")
    ap.add_argument("--repo", default=os.environ.get("ACRME_REPO", DEFAULT_REPO))
    ap.add_argument("--baseline-only", action="store_true", help="only resolve the current baseline")
    ap.add_argument("--max-warn", type=int, default=25, help="max warnings printed per file")
    args = ap.parse_args()

    current, found = resolve_baseline(args.repo)
    if not current:
        print(f"ERROR: no baseline found under {args.repo}/Requirements or Uploads", file=sys.stderr)
        return 2
    cur_version, cur_path, cur_text = current
    print(f"Current baseline: v{cur_version}  ->  {cur_path}")
    stale = [(v, p) for v, p, _ in found if vkey(v) < vkey(cur_version)]
    for v, p in stale:
        print(f"  DRIFT: {p} is v{v} (behind v{cur_version}) — do not cite it")
    if args.baseline_only:
        return 0
    if not args.files:
        ap.error("pass at least one file, or --baseline-only")

    codes = known_codes(args.repo, cur_text)
    total_errors = 0
    for f in args.files:
        if not os.path.exists(f):
            print(f"\n{f}: ERROR file not found")
            total_errors += 1
            continue
        errors, warns = lint(f, args.repo, cur_version, codes)
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
