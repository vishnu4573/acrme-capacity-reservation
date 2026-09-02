# ACRME Executive Presentation

A 14-slide leadership deck distilling the [Executive Design Document](../acrme_executive_design_document.md)
into a boardroom-ready narrative. Every slide is traceable to a specific section of the source document.

## Files

| File | Description |
|---|---|
| `acrme_executive_presentation.pptx` | Editable PowerPoint deck (16:9, Azure palette). |
| `acrme_executive_presentation.pdf` | Print / share-ready PDF export. |
| `build_executive_deck.py` | Generator script (python-pptx). Re-run to regenerate the `.pptx` from code. |

## Slide outline

| # | Slide | Source section |
|---|---|---|
| 1 | Title | — |
| 2 | The Position in One Slide | Section 1 Executive Summary |
| 3 | The Business Problem | Section 2 |
| 4 | The Three Types of Capacity | Section 3 What ACRME Does |
| 5 | The Automation Engine — Safety Before Automation | Section 3 |
| 6 | How Placement Decisions Are Made | Section 6 |
| 7 | Middle East — Cross-Geo DR Extension | Section 6 |
| 8 | How Disaster Recovery Works | Section 5 |
| 9 | What Is Working Well | Section 8 |
| 10 | What Is Still Being Validated | Section 9 |
| 11 | The Risks — Plain English | Section 10 |
| 12 | Three Decisions Leadership Must Make | Section 11 |
| 13 | Recommended Go-Live Sequence | Section 12 |
| 14 | Immediate Actions for Leadership | Section 11 / Section 12 |

## Regenerating

```bash
cd docs/presentation
python3 build_executive_deck.py                       # produces acrme_executive_presentation.pptx
libreoffice --headless --convert-to pdf acrme_executive_presentation.pptx   # produces the PDF
```

The deck deliberately preserves the source document's honest posture: **design complete, validation in
progress** — it does not overstate readiness.
