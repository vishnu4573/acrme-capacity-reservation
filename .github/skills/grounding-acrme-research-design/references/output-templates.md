# Output templates

## Contents
- Header block (all outputs)
- Research Brief
- Design Note
- Gate block
- WAF block

## Header block (all outputs)

```markdown
# <Title>

**Type:** Research Brief | Design Note | ADR delta | Review
**Baseline:** v<X.Y> (<date>) — resolved via check_grounding.py on <date>
**Phases touched:** P1 | P2 | P3 | P4  (downstream impact: <none | …>)
**Codes in scope:** <CAP-0xx, QUA-0xx, …>
**Status:** Draft | For review | Accepted
```

## Research Brief

```markdown
## 1. Question
<One sentence. What decision does the answer unblock?>

## 2. Findings
| # | Finding | Tag | Source |
|---|---|---|---|
| F1 | … | [Documented] | <Learn URL, accessed YYYY-MM-DD> / <code> |

## 3. Baseline position
<What the baseline already says, by code. Note ALIGNED / CONFLICT / NOT COVERED.>

## 4. Conflicts and gaps
- CONFLICT: <Learn vs baseline, doc vs doc> → baseline-change candidate
- SPEC GAP: <term> — used in <where>; missing <source/scope/type>
- POC needed: <POC-xxx or new>

## 5. Implications for design
<What changes, per phase. Tag each.>

## 6. Open questions
<Numbered; each with owner and closing evidence.>
```

## Design Note

```markdown
## 1. Context and problem
<Cite codes. State the constraint that forces a decision.>

## 2. Options
| Option | Summary | HC impact | Cost | Risk | Tag of key assumption |
|---|---|---|---|---|---|

## 3. Recommendation
<Chosen option and why. Rejected options and why.>

## 4. Normative specification
<State machine (mermaid), formulas with units, classification tables, validation rules,
config items with defaults marked Configurable. No summaries in place of rules.>

## 5. Worked example
<One end-to-end numeric example recomputed from the formulas.>

## 6. Gates
<Gate block below.>

## 7. WAF
<WAF block below.>

## 8. Traceability
| Requirement | Section here | Test / POC |
|---|---|---|

## 9. Baseline-change candidates
<Anything that extends or conflicts with the baseline — proposed wording; never edit the baseline directly.>
```

## Gate block

```markdown
### Gates
**Baseline compliance (SK-01):** COMPLIANT | BLOCKED
| Code | Baseline statement | This design | Status |
|---|---|---|---|

**Hard constraints (HC reference Part 2):** COMPLIANT | BLOCKED
| HC | Name | Affected | PASS/FAIL/N/A | Evidence |
|---|---|---|---|---|
| HC-1 | REGION_SEPARATION | | | |
| HC-2 | CAPACITY_FLOOR | | | |
| HC-3 | QUOTA_FLOOR | | | |
| HC-4 | DR_SEPARATION_CLASS | | | |
| HC-5 | ZONE_AVAILABILITY | | | |
| HC-6 | DR_COVERAGE_FLOOR | | | |
| HC-7 | DR_FLOOR_INTEGRITY | | | |
| HC-8 | GEOGRAPHY_CONTAINMENT | | | |
| HC-9 | STANDARD_REGION_ONLY | | | |
| HC-10 | CROSS_GEO_EXTENSION_PATH_APPROVED | | | |
| HC-11 | AVAILABILITY_SET_INELIGIBLE | | | |

**Formula check (SK-06):** <recomputed example matches | n/a>
**DR sizing (SK-09):** <max-not-sum verified | n/a>
**Open items touched:** <POC/DEC/DEP/GAP IDs>
```

## WAF block

```markdown
### WAF
| Pillar | Assessment | Risk | Mitigation |
|---|---|---|---|
| Reliability | zone/region isolation, DR floor, reconciliation failure modes | | |
| Security | least-privilege RBAC per GOV-xxx, cross-subscription/tenant sharing scope | | |
| Cost Optimization | idle reservation spend, buffer sizing, max-not-sum saving | | |
| Operational Excellence | idempotency, drift detection, audit (DAT/OBS), runbooks | | |
| Performance Efficiency | ARM throttling, snapshot freshness (RDY-004), API call budget | | |
```
