# Research Documents

These are the **source research documents** that the [Production Readiness Review & Architecture](../acrme_production_readiness_review_and_architecture.md) reconciles into a single authoritative synthesis.

They are the raw design and test inputs. Where a research document and the PRR disagree, **the PRR is authoritative** — it represents the finalized, production-ready decisions derived after reviewing all of these inputs.

| # | Document | Description |
|---|---|---|
| 1 | [Azure CR Management Engine Design](azure_cr_management_engine_design.md) | Original engine design — microservice architecture, CR lifecycle, sharing, quota, placement, DR, forecasting, cost optimization, and the initial 99-story backlog. |
| 2 | [Multi-Region Placement Design](multi_region_placement_design.md) | Final placement design — three-CRG model, two-group quota architecture, sequential Prod→NonProd→DR selection, and the `PS_Prod` / `PS_NonProd` / `PS_DR` scoring formulas. Defines hard constraints HC-1 through HC-8. |
| 3 | [Design Change Summary](design_change_summary.md) | Consolidated record of the design decisions (D1–D9) and the changes each introduced across the architecture. |
| 4 | [Requirements Traceability Review](acrme_requirements_traceability_review.md) | Coverage analysis mapping the functional and non-functional requirements to design elements, with explicit gap identification. |
| 5 | [Azure CR POC Test Workbook](azure_cr_poc_test_workbook.md) | Full proof-of-concept test workbook — POC groups and test cases with pass/fail criteria and evidence tables. |

---

_Extensions added by the PRR (not present in these source documents): hard constraints **HC-9** (Standard-region-only) and **HC-10** (Cross-Geo Extension path approval), the region classification model, and the validation rule framework (VR-1 through VR-11). See PRR Section 27._
