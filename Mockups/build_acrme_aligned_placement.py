#!/usr/bin/env python3
"""ACRME aligned placement what-if.

Fresh mockup. Placement rules follow the v2.4 baseline and the plain-English
walkthrough. Capacity is reserved per SKU (CAP-003 / CAP-022). Quota is one
pool per region and VM family (QUA-004). Figures are synthetic.

Does not modify the requirements baseline or the earlier what-if workbooks.
"""
from __future__ import annotations

from collections import defaultdict

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

OUT = "/Users/vishnuvardhanreddy/Documents/GitHub/acrme-capacity-reservation/Mockups/acrme_aligned_placement_whatif.xlsx"

# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

SKUS = [
    ("Standard_E32ads_v5", 32, "Eadsv5"),
    ("Standard_E64ads_v5", 64, "Eadsv5"),
    ("Standard_E16ads_v5", 16, "Eadsv5"),
    ("Standard_E32ads_v6", 32, "Eadsv6"),
    ("Standard_D8ads_v5", 8, "Dadsv5"),
    ("Standard_D16ads_v5", 16, "Dadsv5"),
    ("Standard_D8as_v5", 8, "Dasv5"),
    ("Standard_D16as_v5", 16, "Dasv5"),
]
FAMILIES = ["Eadsv5", "Eadsv6", "Dadsv5", "Dasv5"]
VCPU = {s: v for s, v, _ in SKUS}
FAMILY = {s: f for s, _, f in SKUS}

# geo, name, id, az, distribution model, dr scope, class,
# (prod_alloc, prod_free, np_alloc, np_free, dr_alloc, dr_free) at 32 vCPU,
# customer count, DR coverage ratio, note
# Free/alloc are scaled by vCPU/32 for every other SKU.
REGIONS = [
    ("US", "West US 3", "westus3", 3, "3-region", "US", "Standard",
     (600, 200, 400, 520, 80, 40), 40, 0.50, "Synthetic estate"),
    ("US", "Central US", "centralus", 3, "3-region", "US", "Standard",
     (700, 180, 400, 352, 60, 36), 25, 0.45, "Synthetic estate"),
    ("US", "Canada Central", "canadacentral", 3, "3-region", "US", "Standard",
     (500, 64, 300, 113, 40, 48), 12, 0.60, "Synthetic — region is in the catalogue but not in the local usage extracts"),
    ("US", "East US 2", "eastus2", 3, "3-region", "US", "Restricted",
     (650, 220, 350, 400, 70, 40), 18, 0.40, "Restricted — explicit Prod region only (Section 6)"),
    ("EU", "Switzerland North", "switzerlandnorth", 3, "2-region", "EU", "Standard",
     (500, 190, 280, 240, 50, 80), 22, 0.50, "Synthetic estate"),
    ("EU", "Sweden Central", "swedencentral", 3, "2-region", "EU", "Standard",
     (420, 160, 240, 200, 40, 70), 15, 0.58, "Synthetic estate"),
    ("EU", "North Europe", "northeurope", 3, "2-region", "EU", "Restricted",
     (380, 140, 200, 160, 30, 40), 10, 0.35, "Restricted — explicit Prod region only"),
    ("EU", "West Europe", "westeurope", 3, "2-region", "EU", "Restricted",
     (460, 150, 220, 140, 36, 36), 20, 0.42, "Restricted — explicit Prod region only"),
    ("Australia", "Australia East", "australiaeast", 3, "2-region", "Australia", "Standard",
     (300, 200, 180, 160, 24, 48), 14, 0.48, "Synthetic estate"),
    ("Australia", "Australia Southeast", "australiasoutheast", 2, "2-region", "Australia", "Standard",
     (220, 100, 140, 220, 20, 36), 8, 0.52, "2 availability zones — ε = 2/3"),
    ("Asia Pacific", "East Asia", "eastasia", 3, "2-region", "Asia Pacific", "Standard",
     (260, 140, 150, 180, 20, 40), 11, 0.44, "Synthetic estate. Japan East is not in the catalogue."),
    ("Asia Pacific", "Southeast Asia", "southeastasia", 3, "2-region", "Asia Pacific", "Standard",
     (340, 180, 180, 200, 28, 44), 16, 0.50, "Synthetic estate"),
    ("Middle East", "Saudi Arabia Central", "saudicentral", 3, "cross-geo", "EU", "Standard",
     (80, 160, 60, 200, 0, 0), 4, 0.0, "Synthetic. Local DR is 0 — DR is placed in Europe (DR-020)."),
    ("Middle East", "UAE North", "uaenorth", 3, "cross-geo", "EU", "Standard",
     (100, 200, 70, 220, 0, 0), 6, 0.0, "Synthetic. Local DR is 0 — DR is placed in Europe (DR-020)."),
]

GEO_MODEL = [
    ("US", "3-region", "US"),
    ("EU", "2-region", "EU"),
    ("Australia", "2-region", "Australia"),
    ("Asia Pacific", "2-region", "Asia Pacific"),
    ("Middle East", "cross-geo", "EU"),
]

ABBR = {
    "westus3": "wus3", "centralus": "cus", "canadacentral": "cac", "eastus2": "eus2",
    "switzerlandnorth": "chn", "swedencentral": "sec", "northeurope": "neu", "westeurope": "weu",
    "australiaeast": "aue", "australiasoutheast": "aus", "eastasia": "eas", "southeastasia": "sea",
    "saudicentral": "sac", "uaenorth": "uaen",
}
ENV_AB = {"Prod": "pr", "NonProd": "np", "DR": "dr"}
ENVS = ("Prod", "NonProd", "DR")

# Extra pooled quota above current usage, per region × family. Uniform and
# large so the sample is capacity-gated, not accidentally quota-gated.
QUOTA_HEADROOM = 5000

N_REG = len(REGIONS)
N_SKU = len(SKUS)
N_FAM = len(FAMILIES)
CAP_FIRST, CAP_LAST = 5, 4 + N_REG * len(ENVS) * N_SKU
QUOTA_FIRST, QUOTA_LAST = 5, 4 + N_REG * N_FAM
LINE_FIRST, LINE_LAST = 5, 4 + N_REG
REQ_FIRST, REQ_LAST = 13, 20  # 8 SKU lines

# Line_Check identity is columns A–I. Each SKU line then occupies 12 columns.
LINE_FIELDS = (
    "active", "cores", "family",
    "prod_free", "prod_res", "np_free", "np_res", "dr_free", "dr_res",
    "q_avail", "q_limit", "np_head",
)
LINE_WIDTH = len(LINE_FIELDS)
LINE_ORIGIN = 10  # column J


def line_col(line: int, field: str) -> str:
    idx = LINE_ORIGIN + line * LINE_WIDTH + LINE_FIELDS.index(field)
    return get_column_letter(idx)


def scale(value: float, vcpu: int) -> int:
    if value == 0:
        return 0
    return max(2, int(round(value * vcpu / 32.0)))


def capacity_rows():
    rows = []
    for geo, name, rid, az, model, dr_scope, cls, profile, cust, cov, note in REGIONS:
        prod_a, prod_f, np_a, np_f, dr_a, dr_f = profile
        for env, alloc_ref, free_ref in (
            ("Prod", prod_a, prod_f),
            ("NonProd", np_a, np_f),
            ("DR", dr_a, dr_f),
        ):
            for sku, vcpu, fam in SKUS:
                alloc = scale(alloc_ref, vcpu)
                free = scale(free_ref, vcpu)
                rows.append({
                    "name": name, "rid": rid, "geo": geo, "env": env, "sku": sku,
                    "family": fam, "vcpu": vcpu,
                    "crg": f"crg-{ENV_AB[env]}-{ABBR[rid]}-reg",
                    "alloc": alloc, "buffer": free, "cls": cls, "note": note,
                })
    return rows


def quota_limits(cap_rows):
    used = defaultdict(int)
    for row in cap_rows:
        used[(row["rid"], row["family"])] += row["alloc"]
    limits = {}
    for geo, name, rid, *_rest in REGIONS:
        for fam in FAMILIES:
            limits[(rid, fam)] = used[(rid, fam)] + QUOTA_HEADROOM
    return limits


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

NAVY = "1F3864"
H1 = Font(bold=True, size=16, color=NAVY)
H2 = Font(bold=True, size=12, color=NAVY)
BOLD = Font(bold=True)
WHITE = Font(bold=True, color="FFFFFF")
SMALL = Font(size=9, color="595959")
HEAD = PatternFill("solid", fgColor=NAVY)
SUB = PatternFill("solid", fgColor="D6E0F0")
IN = PatternFill("solid", fgColor="FFF2CC")
GREY = PatternFill("solid", fgColor="F2F2F2")
ORANGE = PatternFill("solid", fgColor="FCE4D6")
GREEN = PatternFill("solid", fgColor="C6EFCE")
RED = PatternFill("solid", fgColor="FFC7CE")
TEAL = PatternFill("solid", fgColor="DDEBF7")
THIN = Border(
    left=Side(style="thin", color="BFBFBF"),
    right=Side(style="thin", color="BFBFBF"),
    top=Side(style="thin", color="BFBFBF"),
    bottom=Side(style="thin", color="BFBFBF"),
)
WRAP = Alignment(wrap_text=True, vertical="top")
CTR = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT = Alignment(horizontal="left", vertical="center")


def header_row(ws, row, labels, fills=None):
    for col, label in enumerate(labels, 1):
        cell = ws.cell(row, col, label)
        cell.font = WHITE
        cell.fill = HEAD
        cell.alignment = CTR
        cell.border = THIN
    ws.row_dimensions[row].height = 32
    ws.auto_filter.ref = None
    ws.freeze_panes = f"A{row + 1}"
    ws.auto_filter.ref = f"A{row}:{get_column_letter(len(labels))}{row}"


def paint(cell, fill=None, fmt=None, align=None, font=None):
    cell.border = THIN
    cell.alignment = align or CTR
    if fill is not None:
        cell.fill = fill
    if fmt:
        cell.number_format = fmt
    if font:
        cell.font = font


def widths(ws, pairs):
    for col, width in pairs.items():
        ws.column_dimensions[col if isinstance(col, str) else get_column_letter(col)].width = width


def min_over_lines(row, expr):
    """MIN across 8 lines. Inactive lines contribute 1 so they do not bind."""
    parts = []
    for i in range(8):
        active = f"Line_Check!{line_col(i, 'active')}{row}"
        parts.append(f"IF({active}=1,MAX(0,MIN(1,{expr(i)})),1)")
    return "MIN(" + ",".join(parts) + ")"


def all_lines(row, predicate):
    """PASS when every active line satisfies predicate (an Excel condition)."""
    parts = []
    for i in range(8):
        active = f"Line_Check!{line_col(i, 'active')}{row}"
        parts.append(f"IF({active}=1,IF({predicate(i)},1,0),1)")
    return f'IF(MIN({",".join(parts)})=1,"PASS","FAIL")'


def gate_ok(cell):
    return f'OR({cell}="PASS",{cell}="N/A")'


# ---------------------------------------------------------------------------
# Sheets
# ---------------------------------------------------------------------------

def build_readme(wb):
    ws = wb.active
    ws.title = "ReadMe"
    lines = [
        "ACRME aligned placement what-if",
        "Mock planning workbook. Figures are synthetic. Nothing here is live Azure state, and nothing here changes the v2.4 baseline.",
        "",
        "What you do",
        "1. On Request, set Geography and Customer ID. Enter up to 8 SKU lines (SKU and VM count).",
        "2. Prod region is the normal input (PLC-001). Type a region id, including a Restricted region when the customer named it.",
        "3. Leave Prod region blank only when Geography-only selection is an approved exception (PLC-002). Set that flag to Y.",
        "4. Set DR offered to N to record DR_NOT_OFFERED for this customer (DR-014).",
        "5. Read Allocation. If the placement is READY or READY_WITH_RISK, Post_Allocation and Quota_After show the estate after that placement.",
        "",
        "How a region is chosen",
        "Order is Prod, then CVAL, then DR. A region that fails a hard gate is not scored.",
        "US (3-region): Prod, CVAL, and DR are three different Standard regions.",
        "EU, Australia, Asia Pacific (2-region): Prod takes one Standard region. CVAL and DR co-locate in the other (PLC-010a). HC-6 checks the combined DR + NonProd free pool.",
        "Middle East (cross-geo): Prod and CVAL co-locate in one Middle East region on separate reservations. DR is scored across Europe Standard regions (PLC-010b, DR-020). Local DR quantity is zero.",
        "Restricted regions (East US 2, North Europe, West Europe) are not auto-selected. They are eligible only when Request names them as Prod.",
        "",
        "Score (walkthrough §3.3)",
        "PS = 0.30α + 0.20β + 0.25γ + 0.15δ + 0.10ε. Weights are editable and must sum to 1.",
        "Components are the minimum across the active SKU lines (one thin SKU binds the region).",
        "α Prod = NonProd reserved-free ÷ Prod reserved. α CVAL = NonProd free ÷ NonProd reserved. α DR = DR free ÷ DR reserved.",
        "β = family quota available ÷ family quota limit.",
        "γ = 1 − customers in the region ÷ total_customers. total_customers is not defined in v2.4; Policy holds an assumed value of 100.",
        "δ Prod = DR coverage ratio. δ CVAL repeats α. That duplicate is the documented design of record, not a new metric.",
        "δ DR = coverage ÷ the bootstrap fraction, clamped to 1.",
        "ε = availability-zone count ÷ 3.",
        "A score tie goes to the earlier region in the Section 6 catalogue.",
        "",
        "Gates",
        "HC-2 capacity floor: reserved-free ≥ multiplier × requested cores. The multiplier is policy. This file ships at 1 so the sample fits; the reference write-up uses 2.",
        "HC-3 quota floor: pooled quota can absorb the request and still leave the configured remainder.",
        "HC-5: region has at least 2 availability zones.",
        "HC-6: applied on DR only in a 2-region geography. DR free + NonProd free ≥ this customer's DR bootstrap.",
        "HC-7: applied on CVAL. NonProd headroom after Prod and DR earmarks must cover the request.",
        "HC-8: Prod and CVAL stay in the requested geography. DR stays in that geography, or in Europe when the request is Middle East.",
        "HC-9: Standard regions, or the explicit Prod region even when it is Restricted.",
        "HC-4: DR region is a different region from Prod. Middle East DR must be in Europe. The full HIGH/MEDIUM pair matrix is not in the baseline catalogue, so it is not encoded.",
        "Group availability for a line is MIN(reserved-free for that SKU and environment, family quota available). Every active line must clear it.",
        "",
        "DR size",
        "The new customer's DR reservation is requested cores × the bootstrap fraction on Policy (default 0.10). It is not a 30–40% copy of Prod (ENV-005, DR-007). Existing DR rows in the mock estate are a separate synthetic stock.",
        "",
        "After a successful allocation",
        "Prod and CVAL winners gain the requested cores (allocated up, reserved-free down). The DR winner gains the bootstrap cores. Quota used rises by the same amounts. A failed gate applies nothing.",
        "",
        "Shipped sample",
        "US, no Prod region, exception = Y, DR offered, 4 × Standard_E32ads_v5 (128 cores) and 2 × Standard_D8as_v5 (16 cores).",
        "With the shipped numbers the result is Prod = West US 3, CVAL = Central US, DR = Canada Central. Canada Central cannot take the 128-core line, so it is not a Prod or CVAL candidate. East US 2 stays out because it is Restricted. Open Allocation after Excel calculates to see that result.",
        "",
        "Not in this workbook",
        "Per-AZ capacity reservation groups (only crg-…-reg). Zone rebalancing beyond the even-share target on Allocation. Associated-but-deallocated VMs. A multi-customer MAX-not-SUM DR index. STALE_STATE and VALIDATION_REQUIRED (this file is the snapshot). A persisted seed store — Allocation displays the seed, it does not write one.",
    ]
    ws["A1"] = lines[0]
    ws["A1"].font = H1
    for i, text in enumerate(lines[1:], 2):
        cell = ws.cell(i, 1, text)
        cell.alignment = WRAP
        if text and not text.startswith(" ") and lines[i - 1] == "":
            cell.font = H2
        ws.row_dimensions[i].height = 18 if len(text) < 120 else 32
    ws.column_dimensions["A"].width = 150
    ws.row_dimensions[1].height = 24
    ws.sheet_properties.tabColor = NAVY
    return ws


def build_policy(wb):
    ws = wb.create_sheet("Policy")
    ws["A1"] = "Placement policy"
    ws["A1"].font = H1
    ws["A2"] = "Yellow cells are inputs. The score is invalid unless the five weights sum to 1.00."
    ws["A2"].font = SMALL
    labels = [
        (4, "α capacity headroom", 0.30),
        (5, "β quota headroom", 0.20),
        (6, "γ distribution fairness", 0.25),
        (7, "δ DR readiness", 0.15),
        (8, "ε zone diversity", 0.10),
    ]
    for row, label, value in labels:
        ws.cell(row, 1, label).font = BOLD
        cell = ws.cell(row, 2, value)
        paint(cell, IN, "0.00")
    ws["A9"] = "Weight sum"
    ws["A9"].font = BOLD
    ws["B9"] = "=SUM(B4:B8)"
    paint(ws["B9"], GREY, "0.00")
    ws["A10"] = "Weight check"
    ws["A10"].font = BOLD
    ws["B10"] = '=IF(ABS(B9-1)<0.001,"OK","INVALID")'
    paint(ws["B10"], GREY)
    knobs = [
        (12, "Risk threshold (α below this is READY_WITH_RISK)", 0.10, "0.00"),
        (13, "HC-2 capacity-floor multiplier", 1, "0"),
        (14, "HC-3 minimum quota left after the placement (cores)", 20, "#,##0"),
        (15, "DR bootstrap fraction of requested cores (DR-007)", 0.10, "0.00"),
        (17, "total_customers (assumed — undefined in v2.4)", 100, "#,##0"),
    ]
    for row, label, value, fmt in knobs:
        ws.cell(row, 1, label).font = BOLD
        cell = ws.cell(row, 2, value)
        paint(cell, IN, fmt)
    ws["A16"] = "Policy version"
    ws["A16"].font = BOLD
    ws["B16"] = "v2.4-aligned-mock"
    paint(ws["B16"], GREY, align=LEFT)
    ws["A18"] = "δ DR divides the region's coverage ratio by the bootstrap fraction in B15, then clamps to 1."
    ws["A18"].font = SMALL
    ws["A19"] = "HC-2 reference multiplier in the hard-constraint note is 2. B13 ships at 1 so the sample request fits the mock estate."
    ws["A19"].font = SMALL

    ws["D3"] = "Geography model (REG-003)"
    ws["D3"].font = H2
    for col, label in enumerate(("Geography", "Model", "DR scope"), 4):
        cell = ws.cell(4, col, label)
        cell.font = WHITE
        cell.fill = HEAD
        cell.alignment = CTR
        cell.border = THIN
    for i, (geo, model, scope) in enumerate(GEO_MODEL):
        for col, value in enumerate((geo, model, scope), 4):
            cell = ws.cell(5 + i, col, value)
            paint(cell, TEAL, align=LEFT)
    ws["D11"] = "Middle East DR scope is EU. CVAL co-locates with Prod. PLC-010a does not apply."
    ws["D11"].font = SMALL

    widths(ws, {"A": 78, "B": 22, "C": 3, "D": 22, "E": 16, "F": 18})
    ws.freeze_panes = "A4"
    ws.sheet_properties.tabColor = "C65911"
    return ws


def build_request(wb):
    ws = wb.create_sheet("Request", 1)
    ws["A1"] = "Deployment request"
    ws["A1"].font = H1
    ws["A2"] = "Yellow cells are the only inputs. One row per SKU. Both SKU and VM count are required for a line to count."
    ws["A2"].font = SMALL

    fields = [
        (4, "Geography", "US"),
        (5, "Customer ID", "CUST-1008"),
        (6, "Prod region id (blank = do not auto-pick)", ""),
        (7, "Geography-only exception approved (Y/N)", "Y"),
        (8, "DR offered (Y/N)", "Y"),
    ]
    for row, label, value in fields:
        ws.cell(row, 1, label).font = BOLD
        cell = ws.cell(row, 2, value)
        paint(cell, IN, align=LEFT)
    ws["C4"] = "US, EU, Australia, Asia Pacific, or Middle East"
    ws["C6"] = "PLC-001. Restricted ids are allowed here: eastus2, northeurope, westeurope."
    ws["C7"] = "PLC-002. Must be Y when Prod region is blank. Ignored when a Prod region is named."
    ws["C8"] = "N writes DR_NOT_OFFERED and does not reserve DR cores."
    for row in (4, 6, 7, 8):
        ws.cell(row, 3).font = SMALL
        ws.cell(row, 3).alignment = LEFT

    ws["A9"] = "Distribution model"
    ws["B9"] = '=IF(B4="","",VLOOKUP(B4,Policy!D5:F9,2,FALSE))'
    ws["A10"] = "DR scope geography"
    ws["B10"] = '=IF(B4="","",VLOOKUP(B4,Policy!D5:F9,3,FALSE))'
    for row in (9, 10):
        ws.cell(row, 1).font = BOLD
        paint(ws.cell(row, 2), GREY, align=LEFT)

    headers = ("SKU", "VM count", "vCPU / VM", "Line cores", "Quota family", "Active", "Duplicate")
    for col, label in enumerate(headers, 1):
        cell = ws.cell(12, col, label)
        cell.font = WHITE
        cell.fill = HEAD
        cell.alignment = CTR
        cell.border = THIN

    sample = {13: ("Standard_E32ads_v5", 4), 14: ("Standard_D8as_v5", 2)}
    for row in range(REQ_FIRST, REQ_LAST + 1):
        sku, count = sample.get(row, ("", None))
        sku_cell = ws.cell(row, 1, sku if sku else None)
        count_cell = ws.cell(row, 2, count)
        paint(sku_cell, IN, align=LEFT)
        paint(count_cell, IN, "0")
        ws.cell(row, 3, f'=IF(A{row}="","",VLOOKUP(A{row},SKU_Catalogue!A$5:C$12,2,FALSE))')
        ws.cell(row, 4, f'=IF(OR(A{row}="",NOT(ISNUMBER(B{row})),B{row}<=0),"",B{row}*C{row})')
        ws.cell(row, 5, f'=IF(A{row}="","",VLOOKUP(A{row},SKU_Catalogue!A$5:C$12,3,FALSE))')
        ws.cell(row, 6, f'=IF(AND(A{row}<>"",ISNUMBER(B{row}),B{row}>0),1,0)')
        ws.cell(row, 7, f'=IF(A{row}="",0,IF(COUNTIF($A$13:$A$20,A{row})>1,1,0))')
        for col in range(3, 8):
            paint(ws.cell(row, col), GREY, "#,##0" if col in (3, 4, 6, 7) else None)

    ws["A22"] = "Active SKU lines"
    ws["B22"] = "=SUM(F13:F20)"
    ws["A23"] = "Total requested cores"
    ws["B23"] = "=SUM(D13:D20)"
    ws["A24"] = "SKU uniqueness"
    ws["B24"] = '=IF(SUM(G13:G20)>0,"DUPLICATE SKU","OK")'
    ws["A25"] = "DR bootstrap cores (all lines)"
    ws["B25"] = '=IF(B8<>"Y",0,ROUND(B23*Policy!B15,0))'
    for row in range(22, 26):
        ws.cell(row, 1).font = BOLD
        paint(ws.cell(row, 2), TEAL, "#,##0" if row != 24 else None)

    ws["A27"] = "Prod path"
    ws["B27"] = (
        '=IF(B22=0,"Enter at least one SKU line",'
        'IF(Policy!B10<>"OK","Weights must sum to 1",'
        'IF(B24<>"OK","Remove duplicate SKUs",'
        'IF(B6<>"","Validate the named Prod region",'
        'IF(B7="Y","Exception path: score Standard regions in this geography",'
        '"Blocked: name a Prod region or approve the geography exception")))))'
    )
    paint(ws["B27"], TEAL, align=LEFT)
    ws.merge_cells("B27:E27")

    geo_dv = DataValidation(type="list", formula1='"US,EU,Australia,Asia Pacific,Middle East"', allow_blank=False)
    yn = DataValidation(type="list", formula1='"Y,N"', allow_blank=False)
    regions = ",".join(r[2] for r in REGIONS)
    region_dv = DataValidation(type="list", formula1=f'"{regions}"', allow_blank=True)
    skus = ",".join(s[0] for s in SKUS)
    sku_dv = DataValidation(type="list", formula1=f'"{skus}"', allow_blank=True)
    ws.add_data_validation(geo_dv)
    ws.add_data_validation(yn)
    ws.add_data_validation(region_dv)
    ws.add_data_validation(sku_dv)
    geo_dv.add(ws["B4"])
    region_dv.add(ws["B6"])
    yn.add(ws["B7"])
    yn.add(ws["B8"])
    sku_dv.add("A13:A20")

    widths(ws, {"A": 62, "B": 42, "C": 22, "D": 16, "E": 20, "F": 12, "G": 14})
    ws.freeze_panes = "A13"
    ws.sheet_properties.tabColor = "C65911"
    ws.auto_filter.ref = "A12:G20"
    return ws


def build_catalogue(wb):
    ws = wb.create_sheet("Region_Catalogue")
    ws["A1"] = "In-scope region catalogue — baseline v2.4 Section 6"
    ws["A1"].font = H1
    ws["A2"] = "Class and model are the baseline, not the earlier what-if promotion of Restricted regions."
    ws["A2"].font = SMALL
    labels = ("Region", "Region id", "Geography", "AZ", "Model", "DR scope", "Class",
              "Customers", "DR coverage", "Note")
    header_row(ws, 4, labels)
    for i, (geo, name, rid, az, model, scope, cls, _profile, cust, cov, note) in enumerate(REGIONS):
        row = 5 + i
        values = (name, rid, geo, az, model, scope, cls, cust, cov, note)
        for col, value in enumerate(values, 1):
            cell = ws.cell(row, col, value)
            fill = ORANGE if cls == "Restricted" else (GREY if "Synthetic —" in note or "Local DR" in note else None)
            paint(cell, fill, "0%" if col == 9 else ("0" if col in (4, 8) else None),
                  LEFT if col in (1, 2, 10) else CTR)
    widths(ws, {"A": 26, "B": 24, "C": 16, "D": 8, "E": 14, "F": 16, "G": 14, "H": 14, "I": 14, "J": 78})
    ws.auto_filter.ref = "A4:J18"
    ws.sheet_properties.tabColor = NAVY
    return ws


def build_skus(wb):
    ws = wb.create_sheet("SKU_Catalogue")
    ws["A1"] = "Managed SKU catalogue"
    ws["A1"].font = H1
    ws["A2"] = "Family names follow the Azure VM size (Eadsv5, Eadsv6, Dadsv5, Dasv5). Eight SKUs, several per family, so quota is shared."
    ws["A2"].font = SMALL
    header_row(ws, 4, ("SKU", "vCPU / VM", "Quota family", "Zonal reservation", "Note"))
    for i, (sku, vcpu, fam) in enumerate(SKUS):
        row = 5 + i
        for col, value in enumerate((sku, vcpu, fam, "Yes", "Seed-matrix member. Count starts from the mock estate, not from zero."), 1):
            paint(ws.cell(row, col, value), None, "0" if col == 2 else None, LEFT if col in (1, 5) else CTR)
    widths(ws, {"A": 26, "B": 14, "C": 16, "D": 22, "E": 70})
    ws.auto_filter.ref = "A4:E12"
    return ws


def build_capacity(wb, cap_rows):
    ws = wb.create_sheet("Capacity_Reservations")
    ws["A1"] = "Mock capacity reservations — one row per region, environment, and SKU"
    ws["A1"].font = H1
    ws["A2"] = (
        "Yellow Allocated and Buffer cells are the mock estate. Reserved = Allocated + Buffer (CAP-003). "
        "Reserved-free = Buffer. CRG names are regional (crg-…-reg); per-AZ groups are not in this file. "
        "Middle East DR rows are zero because that DR lives in Europe."
    )
    ws["A2"].font = SMALL
    ws.merge_cells("A2:N2")
    labels = ("Region", "Region id", "Geography", "Environment", "SKU", "Family", "vCPU",
              "CRG", "Allocated", "Buffer", "Reserved", "Reserved-free", "Class", "Note")
    header_row(ws, 4, labels)
    for i, row in enumerate(cap_rows):
        r = 5 + i
        values = [row["name"], row["rid"], row["geo"], row["env"], row["sku"], row["family"],
                  row["vcpu"], row["crg"], row["alloc"], row["buffer"], None, None, row["cls"], row["note"]]
        for col, value in enumerate(values, 1):
            cell = ws.cell(r, col, value)
            fill = IN if col in (9, 10) else None
            paint(cell, fill, "0" if col in (7, 9, 10) else None, LEFT if col in (1, 2, 5, 8, 14) else CTR)
        ws.cell(r, 11, f"=I{r}+J{r}")
        ws.cell(r, 12, f"=K{r}-I{r}")
        paint(ws.cell(r, 11), GREY, "#,##0")
        paint(ws.cell(r, 12), GREY, "#,##0")
    widths(ws, {"A": 26, "B": 22, "C": 16, "D": 14, "E": 24, "F": 12, "G": 10, "H": 22,
                "I": 14, "J": 12, "K": 14, "L": 16, "M": 14, "N": 62})
    ws.auto_filter.ref = f"A4:N{CAP_LAST}"
    ws.auto_filter.ref = f"A4:N{CAP_LAST}"
    ws.freeze_panes = "A5"
    ws.conditional_formatting.add(
        f"M5:M{CAP_LAST}",
        CellIsRule(operator="equal", formula=['"Restricted"'], fill=ORANGE),
    )
    return ws


def build_quota(wb, cap_rows, limits):
    ws = wb.create_sheet("Quota_Groups")
    ws["A1"] = "Mock quota groups — one pool per region and VM family"
    ws["A1"].font = H1
    ws["A2"] = (
        "One group covers Prod, NonProd, and DR (QUA-004). Yellow Limit is synthetic. "
        "Used sums Allocated on Capacity_Reservations. "
        "Prod earmark and DR earmark are the reserved cores of those environments, so CVAL cannot spend them (HC-7)."
    )
    ws["A2"].font = SMALL
    ws.merge_cells("A2:M2")
    labels = ("Quota group", "Region", "Region id", "Geography", "Family", "Limit",
              "Used", "Available", "Prod earmark", "DR earmark", "NonProd used",
              "Allocatable to NonProd", "NonProd headroom")
    header_row(ws, 4, labels)
    cap_b, cap_d, cap_f, cap_i, cap_k = (
        f"Capacity_Reservations!$B$5:$B${CAP_LAST}",
        f"Capacity_Reservations!$D$5:$D${CAP_LAST}",
        f"Capacity_Reservations!$F$5:$F${CAP_LAST}",
        f"Capacity_Reservations!$I$5:$I${CAP_LAST}",
        f"Capacity_Reservations!$K$5:$K${CAP_LAST}",
    )
    r = 5
    for geo, name, rid, *_rest in REGIONS:
        for fam in FAMILIES:
            ws.cell(r, 1, f"qg-{ABBR[rid]}-{fam}")
            ws.cell(r, 2, name)
            ws.cell(r, 3, rid)
            ws.cell(r, 4, geo)
            ws.cell(r, 5, fam)
            limit = ws.cell(r, 6, limits[(rid, fam)])
            paint(limit, IN, "#,##0")
            ws.cell(r, 7, f'=SUMIFS({cap_i},{cap_b},C{r},{cap_f},E{r})')
            ws.cell(r, 8, f"=F{r}-G{r}")
            ws.cell(r, 9, f'=SUMIFS({cap_k},{cap_b},C{r},{cap_d},"Prod",{cap_f},E{r})')
            ws.cell(r, 10, f'=SUMIFS({cap_k},{cap_b},C{r},{cap_d},"DR",{cap_f},E{r})')
            ws.cell(r, 11, f'=SUMIFS({cap_i},{cap_b},C{r},{cap_d},"NonProd",{cap_f},E{r})')
            ws.cell(r, 12, f"=MAX(0,F{r}-I{r}-J{r})")
            ws.cell(r, 13, f"=L{r}-K{r}")
            for col in range(1, 14):
                if col == 6:
                    continue
                paint(ws.cell(r, col), GREY if col >= 7 else None,
                      "#,##0" if col >= 6 else None,
                      LEFT if col in (1, 2, 3, 5) else CTR)
            r += 1
    widths(ws, {"A": 22, "B": 26, "C": 22, "D": 16, "E": 12, "F": 12, "G": 12, "H": 14,
                "I": 16, "J": 14, "K": 16, "L": 24, "M": 20})
    ws.freeze_panes = "A5"
    ws.auto_filter.ref = f"A4:M{QUOTA_LAST}"
    return ws


def build_line_check(wb):
    ws = wb.create_sheet("Line_Check")
    ws["A1"] = "Per-region, per-SKU line calculations"
    ws["A1"].font = H1
    ws["A2"] = "Formulas only. Score sheets read this grid. Inactive request lines contribute a neutral 1 to every MIN."
    ws["A2"].font = SMALL
    identity = ("Region", "Region id", "Geography", "Class", "Model", "DR scope", "AZ", "Customers", "DR coverage")
    labels = list(identity)
    for n in range(1, 9):
        for field in ("Active", "Cores", "Family", "Prod free", "Prod reserved", "NP free", "NP reserved",
                      "DR free", "DR reserved", "Quota avail", "Quota limit", "NP headroom"):
            labels.append(f"L{n} {field}")
    header_row(ws, 4, labels)
    cap = "Capacity_Reservations"
    quo = "Quota_Groups"
    for i in range(N_REG):
        r = 5 + i
        src = 5 + i
        for col, formula in enumerate((
            f"=Region_Catalogue!A{src}",
            f"=Region_Catalogue!B{src}",
            f"=Region_Catalogue!C{src}",
            f"=Region_Catalogue!G{src}",
            f"=Region_Catalogue!E{src}",
            f"=Region_Catalogue!F{src}",
            f"=Region_Catalogue!D{src}",
            f"=Region_Catalogue!H{src}",
            f"=Region_Catalogue!I{src}",
        ), 1):
            cell = ws.cell(r, col, formula)
            paint(cell, TEAL, "0%" if col == 9 else ("0" if col in (7, 8) else None),
                  LEFT if col in (1, 2) else CTR)
        for n, req in enumerate(range(REQ_FIRST, REQ_LAST + 1)):
            c = lambda field, n=n: line_col(n, field)  # noqa: E731
            active = f'{c("active")}{r}'
            sku = f"Request!A{req}"
            mapping = {
                "active": f'=IF(AND({sku}<>"",ISNUMBER(Request!B{req}),Request!B{req}>0),1,0)',
                "cores": f'=IF({active}=1,Request!D{req},0)',
                "family": f'=IF({active}=1,Request!E{req},"")',
                "prod_free": f'=IF({active}=1,SUMIFS({cap}!$L$5:$L${CAP_LAST},{cap}!$B$5:$B${CAP_LAST},$B{r},{cap}!$D$5:$D${CAP_LAST},"Prod",{cap}!$E$5:$E${CAP_LAST},{sku}),0)',
                "prod_res": f'=IF({active}=1,SUMIFS({cap}!$K$5:$K${CAP_LAST},{cap}!$B$5:$B${CAP_LAST},$B{r},{cap}!$D$5:$D${CAP_LAST},"Prod",{cap}!$E$5:$E${CAP_LAST},{sku}),0)',
                "np_free": f'=IF({active}=1,SUMIFS({cap}!$L$5:$L${CAP_LAST},{cap}!$B$5:$B${CAP_LAST},$B{r},{cap}!$D$5:$D${CAP_LAST},"NonProd",{cap}!$E$5:$E${CAP_LAST},{sku}),0)',
                "np_res": f'=IF({active}=1,SUMIFS({cap}!$K$5:$K${CAP_LAST},{cap}!$B$5:$B${CAP_LAST},$B{r},{cap}!$D$5:$D${CAP_LAST},"NonProd",{cap}!$E$5:$E${CAP_LAST},{sku}),0)',
                "dr_free": f'=IF({active}=1,SUMIFS({cap}!$L$5:$L${CAP_LAST},{cap}!$B$5:$B${CAP_LAST},$B{r},{cap}!$D$5:$D${CAP_LAST},"DR",{cap}!$E$5:$E${CAP_LAST},{sku}),0)',
                "dr_res": f'=IF({active}=1,SUMIFS({cap}!$K$5:$K${CAP_LAST},{cap}!$B$5:$B${CAP_LAST},$B{r},{cap}!$D$5:$D${CAP_LAST},"DR",{cap}!$E$5:$E${CAP_LAST},{sku}),0)',
                "q_avail": f'=IF({active}=1,SUMIFS({quo}!$H$5:$H${QUOTA_LAST},{quo}!$C$5:$C${QUOTA_LAST},$B{r},{quo}!$E$5:$E${QUOTA_LAST},Request!E{req}),0)',
                "q_limit": f'=IF({active}=1,SUMIFS({quo}!$F$5:$F${QUOTA_LAST},{quo}!$C$5:$C${QUOTA_LAST},$B{r},{quo}!$E$5:$E${QUOTA_LAST},Request!E{req}),0)',
                "np_head": f'=IF({active}=1,SUMIFS({quo}!$M$5:$M${QUOTA_LAST},{quo}!$C$5:$C${QUOTA_LAST},$B{r},{quo}!$E$5:$E${QUOTA_LAST},Request!E{req}),0)',
            }
            for field in LINE_FIELDS:
                col_idx = LINE_ORIGIN + n * LINE_WIDTH + LINE_FIELDS.index(field)
                cell = ws.cell(r, col_idx, mapping[field])
                paint(cell, GREY, "#,##0" if field not in ("family",) else None)
    ws.freeze_panes = "J5"
    ws.auto_filter.ref = f"A4:{get_column_letter(9 + 8 * LINE_WIDTH)}{LINE_LAST}"
    widths(ws, {"A": 26, "B": 22, "C": 16, "D": 14, "E": 14, "F": 16, "G": 8, "H": 12, "I": 14})
    return ws


def component_block(row, kind):
    """Return α, β, γ, δ, ε Excel expressions. kind is prod, cval, or dr."""
    def ratio(num, den):
        return lambda i: (
            f'IF(Line_Check!{line_col(i, den)}{row}=0,0,'
            f'Line_Check!{line_col(i, num)}{row}/Line_Check!{line_col(i, den)}{row})'
        )

    if kind == "prod":
        alpha = min_over_lines(row, ratio("np_free", "prod_res"))
    elif kind == "cval":
        alpha = min_over_lines(row, ratio("np_free", "np_res"))
    else:
        alpha = min_over_lines(row, ratio("dr_free", "dr_res"))
    beta = min_over_lines(
        row,
        lambda i: (
            f'IF(Line_Check!{line_col(i, "q_limit")}{row}=0,0,'
            f'Line_Check!{line_col(i, "q_avail")}{row}/Line_Check!{line_col(i, "q_limit")}{row})'
        ),
    )
    gamma = f'IF(Policy!$B$17<=0,0,MAX(0,MIN(1,1-H{row}/Policy!$B$17)))'
    if kind == "prod":
        delta = f"MAX(0,MIN(1,I{row}))"
    elif kind == "cval":
        delta = alpha  # design-of-record duplicate of α
    else:
        delta = f'IF(Policy!$B$15<=0,0,MAX(0,MIN(1,I{row}/Policy!$B$15)))'
    epsilon = "MAX(0,MIN(1,G{row}/3))".format(row=row)
    return alpha, beta, gamma, delta, epsilon


def candidate_formula(row, kind):
    geo = f"C{row}"
    rid = f"B{row}"
    cls = f"D{row}"
    blocked = 'OR(Request!$B$22=0,Policy!$B$10<>"OK",Request!$B$24<>"OK")'
    if kind == "prod":
        return (
            f'=IF({blocked},0,'
            f'IF(AND(Request!$B$6="",Request!$B$7<>"Y"),0,'
            f'IF(Request!$B$6<>"",IF(AND({rid}=Request!$B$6,{geo}=Request!$B$4),1,0),'
            f'IF(AND({geo}=Request!$B$4,{cls}="Standard"),1,0))))'
        )
    # CVAL and DR need a Prod winner that is a real region id.
    prod = "Allocation!$C$9"
    cval = "Allocation!$C$10"
    placed = f'AND({prod}<>"NONE ELIGIBLE",{prod}<>"POLICY_BLOCKED",{prod}<>"NO REQUEST")'
    if kind == "cval":
        return (
            f'=IF(OR({blocked},NOT({placed})),0,'
            f'IF(Request!$B$9="cross-geo",IF({rid}={prod},1,0),'
            f'IF(AND({geo}=Request!$B$4,{cls}="Standard",{rid}<>{prod}),1,0)))'
        )
    return (
        f'=IF(OR({blocked},Request!$B$8<>"Y",NOT({placed}),'
        f'{cval}="NONE ELIGIBLE"),0,'
        f'IF(Request!$B$9="cross-geo",IF(AND({geo}=Request!$B$10,{cls}="Standard"),1,0),'
        f'IF(Request!$B$9="2-region",IF({rid}={cval},1,0),'
        f'IF(AND({geo}=Request!$B$4,{cls}="Standard",{rid}<>{prod},{rid}<>{cval}),1,0))))'
    )


def meets_formula(row, kind):
    if kind == "prod":
        free = "prod_free"
        quota = "q_avail"
        need = lambda i: f"Line_Check!{line_col(i, 'cores')}{row}"
    elif kind == "cval":
        free = "np_free"
        quota = "np_head"
        need = lambda i: f"Line_Check!{line_col(i, 'cores')}{row}"
    else:
        free = "dr_free"
        quota = "q_avail"
        need = lambda i: f"ROUND(Line_Check!{line_col(i, 'cores')}{row}*Policy!$B$15,0)"

    def pred(i, free=free, quota=quota, need=need):
        return (
            f"MIN(Line_Check!{line_col(i, free)}{row},Line_Check!{line_col(i, quota)}{row})"
            f">={need(i)}"
        )
    return "=" + all_lines(row, pred)


def hc2_formula(row, kind):
    if kind == "dr":
        need = lambda i: f"ROUND(Line_Check!{line_col(i, 'cores')}{row}*Policy!$B$15,0)"
        free = "dr_free"
    elif kind == "cval":
        need = lambda i: f"Line_Check!{line_col(i, 'cores')}{row}"
        free = "np_free"
    else:
        need = lambda i: f"Line_Check!{line_col(i, 'cores')}{row}"
        free = "prod_free"

    def pred(i, free=free, need=need):
        return f"Line_Check!{line_col(i, free)}{row}>=Policy!$B$13*{need(i)}"
    return "=" + all_lines(row, pred)


def hc3_formula(row, kind):
    if kind == "dr":
        quota = "q_avail"
        need = lambda i: f"ROUND(Line_Check!{line_col(i, 'cores')}{row}*Policy!$B$15,0)"
    elif kind == "cval":
        quota = "q_avail"
        need = lambda i: f"Line_Check!{line_col(i, 'cores')}{row}"
    else:
        quota = "q_avail"
        need = lambda i: f"Line_Check!{line_col(i, 'cores')}{row}"

    def pred(i, quota=quota, need=need):
        q = f"Line_Check!{line_col(i, quota)}{row}"
        n = need(i)
        return f"AND({q}>={n},{q}-{n}>=Policy!$B$14)"
    return "=" + all_lines(row, pred)


def hc7_formula(row):
    def pred(i):
        head = f"Line_Check!{line_col(i, 'np_head')}{row}"
        cores = f"Line_Check!{line_col(i, 'cores')}{row}"
        return f"AND({head}>={cores},{head}-{cores}>=Policy!$B$14)"
    return "=" + all_lines(row, pred)


def hc6_formula(row):
    """Combined DR + NonProd free against bootstrap. Only meaningful for 2-region DR."""
    def pred(i):
        need = f"ROUND(Line_Check!{line_col(i, 'cores')}{row}*Policy!$B$15,0)"
        pool = (
            f"Line_Check!{line_col(i, 'dr_free')}{row}+Line_Check!{line_col(i, 'np_free')}{row}"
        )
        return f"{pool}>={need}"
    return "=" + all_lines(row, pred)


def readiness_formula(row):
    # Priority: missing reservation, empty quota, then the failed gate, then risk.
    return (
        f'=IF(J{row}<>1,"—",'
        f'IF(COUNTIFS(Line_Check!{line_col(0, "active")}{row},1)=0,"—",'
        f'IF(OR(Line_Check!{line_col(0, "prod_res")}{row}=0,Line_Check!{line_col(1, "prod_res")}{row}=0,'
        f'Line_Check!{line_col(2, "prod_res")}{row}=0,Line_Check!{line_col(3, "prod_res")}{row}=0,'
        f'Line_Check!{line_col(4, "prod_res")}{row}=0,Line_Check!{line_col(5, "prod_res")}{row}=0,'
        f'Line_Check!{line_col(6, "prod_res")}{row}=0,Line_Check!{line_col(7, "prod_res")}{row}=0),"RESERVATION_DEFICIT",'
        f'IF(H{row}="FAIL","CAPACITY_UNAVAILABLE",'
        f'IF(OR(I{row}="FAIL",L{row}="FAIL"),"QUOTA_DEFICIT",'
        f'IF(OR(K{row}="FAIL",M{row}="FAIL",N{row}="FAIL",O{row}="FAIL",P{row}<>1),"CAPACITY_UNAVAILABLE",'
        f'IF(R{row}<Policy!$B$12,"READY_WITH_RISK","READY"))))))'
    )


def binding_formula(row, free_field, quota_field):
    parts_free = []
    parts_quota = []
    for i in range(8):
        active = f"Line_Check!{line_col(i, 'active')}{row}"
        parts_free.append(f"IF({active}=1,Line_Check!{line_col(i, free_field)}{row},10^9)")
        parts_quota.append(f"IF({active}=1,Line_Check!{line_col(i, quota_field)}{row},10^9)")
    return (
        f'=IF(Q{row}<>1,"—",IF(MIN({",".join(parts_free)})<=MIN({",".join(parts_quota)}),"CAPACITY","QUOTA"))'
    )


def build_score(wb, kind, title):
    ws = wb.create_sheet({"prod": "Score_Prod", "cval": "Score_CVAL", "dr": "Score_DR"}[kind])
    ws["A1"] = title
    ws["A1"].font = H1
    ws["A2"] = "Eligible = 1 only after every gate passes. Placement score is blank for everyone else. Rank 1 is the winner. Ties break toward the earlier catalogue row."
    ws["A2"].font = SMALL
    labels = (
        "Region", "Region id", "Geography", "Class", "Model", "DR scope", "AZ", "Customers", "DR coverage",
        "Candidate", "HC-2", "HC-3", "HC-5", "HC-6", "HC-7", "HC-8", "HC-9", "HC-4", "Meets-all",
        "Eligible", "α", "β", "γ", "δ", "ε", "PS", "Rank", "Readiness", "Binding",
    )
    # Wait, I used J as candidate in readiness but then listed Candidate as column 10 which is J.
    # Let me lock columns explicitly while writing so the formulas above match.
    # A-I identity (1-9), J candidate (10), K HC2 (11), L HC3 (12), M HC5 (13), N HC6 (14),
    # O HC7 (15), P HC8 (16), Q HC9 (17), R HC4 (18), S Meets (19), T Eligible (20),
    # U α (21) ... this DOES NOT match readiness_formula which assumed different letters.
    # I will set formulas using these actual letters and fix readiness/binding/eligible to match.
    header_row(ws, 4, labels)
    free_field = {"prod": "prod_free", "cval": "np_free", "dr": "dr_free"}[kind]
    quota_field = {"prod": "q_avail", "cval": "np_head", "dr": "q_avail"}[kind]

    for i in range(N_REG):
        r = 5 + i
        for col, formula in enumerate((
            f"=Line_Check!A{r}", f"=Line_Check!B{r}", f"=Line_Check!C{r}",
            f"=Line_Check!D{r}", f"=Line_Check!E{r}", f"=Line_Check!F{r}",
            f"=Line_Check!G{r}", f"=Line_Check!H{r}", f"=Line_Check!I{r}",
        ), 1):
            paint(ws.cell(r, col, formula), TEAL, "0%" if col == 9 else ("0" if col in (7, 8) else None),
                  LEFT if col in (1, 2) else CTR)

        ws.cell(r, 10, candidate_formula(r, kind))
        paint(ws.cell(r, 10), GREY, "0")

        ws.cell(r, 11, hc2_formula(r, kind))
        ws.cell(r, 12, hc3_formula(r, kind))
        ws.cell(r, 13, f'=IF(G{r}>=2,"PASS","FAIL")')
        if kind == "dr":
            ws.cell(r, 14, f'=IF(Request!$B$9="2-region",{hc6_formula(r)[1:]},"N/A")')
        else:
            ws.cell(r, 14, "N/A")
        if kind == "cval":
            ws.cell(r, 15, hc7_formula(r))
        else:
            ws.cell(r, 15, "N/A")
        if kind == "dr":
            ws.cell(r, 16, f'=IF(C{r}=Request!$B$10,"PASS","FAIL")')
        else:
            ws.cell(r, 16, f'=IF(C{r}=Request!$B$4,"PASS","FAIL")')
        if kind == "prod":
            ws.cell(r, 17, f'=IF(OR(D{r}="Standard",B{r}=Request!$B$6),"PASS","FAIL")')
        else:
            ws.cell(r, 17, f'=IF(D{r}="Standard","PASS","FAIL")')
        if kind == "dr":
            ws.cell(r, 18, f'=IF(AND(Request!$B$9="cross-geo",C{r}=Request!$B$10),"PASS",IF(B{r}<>Allocation!$C$9,"PASS","FAIL"))')
        else:
            ws.cell(r, 18, "N/A")
        ws.cell(r, 19, meets_formula(r, kind))

        for col in range(11, 20):
            paint(ws.cell(r, col), GREY)

        gates = ",".join(gate_ok(f"{get_column_letter(c)}{r}") for c in range(11, 20))
        ws.cell(r, 20, f'=IF(AND(J{r}=1,{gates}),1,0)')
        paint(ws.cell(r, 20), GREY, "0")

        alpha, beta, gamma, delta, epsilon = component_block(r, kind)
        ws.cell(r, 21, f'=IF(J{r}<>1,"—",{alpha})')
        ws.cell(r, 22, f'=IF(J{r}<>1,"—",{beta})')
        ws.cell(r, 23, f'=IF(J{r}<>1,"—",{gamma})')
        ws.cell(r, 24, f'=IF(J{r}<>1,"—",{delta})')
        ws.cell(r, 25, f'=IF(J{r}<>1,"—",{epsilon})')
        ws.cell(r, 26, f'=IF(T{r}<>1,"—",Policy!$B$4*U{r}+Policy!$B$5*V{r}+Policy!$B$6*W{r}+Policy!$B$7*X{r}+Policy!$B$8*Y{r})')
        # Rank. Catalogue order == sheet order == lower row number wins ties.
        ws.cell(r, 27, (
            f'=IF(T{r}<>1,"—",1+COUNTIFS($T$5:$T${LINE_LAST},1,$Z$5:$Z${LINE_LAST},">"&Z{r})'
            f'+COUNTIFS($T$5:$T${LINE_LAST},1,$Z$5:$Z${LINE_LAST},Z{r},$AA$5:$AA${LINE_LAST},"<"&AA{r}))'
        ))
        reserved_field = {"prod": "prod_res", "cval": "np_res", "dr": "dr_res"}[kind]
        missing_res = ",".join(
            f'AND(Line_Check!{line_col(n, "active")}{r}=1,Line_Check!{line_col(n, reserved_field)}{r}=0)'
            for n in range(8)
        )
        ws.cell(r, 28, (
            f'=IF(J{r}<>1,"—",'
            f'IF(OR({missing_res}),"RESERVATION_DEFICIT",'
            f'IF(K{r}="FAIL","CAPACITY_UNAVAILABLE",'
            f'IF(L{r}="FAIL","QUOTA_DEFICIT",'
            f'IF(OR(M{r}="FAIL",N{r}="FAIL",O{r}="FAIL",P{r}="FAIL",Q{r}="FAIL",R{r}="FAIL",S{r}="FAIL"),"CAPACITY_UNAVAILABLE",'
            f'IF(AND(T{r}=1,U{r}<Policy!$B$12),"READY_WITH_RISK",'
            f'IF(T{r}=1,"READY","CAPACITY_UNAVAILABLE")))))))'
        ))
        parts_free, parts_quota = [], []
        for n in range(8):
            active = f"Line_Check!{line_col(n, 'active')}{r}"
            parts_free.append(f"IF({active}=1,Line_Check!{line_col(n, free_field)}{r},10^9)")
            parts_quota.append(f"IF({active}=1,Line_Check!{line_col(n, quota_field)}{r},10^9)")
        ws.cell(r, 29, f'=IF(T{r}<>1,"—",IF(MIN({",".join(parts_free)})<=MIN({",".join(parts_quota)}),"CAPACITY","QUOTA"))')
        ws.cell(r, 27)  # rank uses AA — write row index in column 27? Conflict.
        # Rank is column 27 (AA is 27). I used Z for PS and AA for row index in the rank formula,
        # but PS is column 26 (Z) and Rank is column 27 (AA). Fix rank to use a helper column AB (28)
        # — but 28 is readiness. Put the row index in column 31 (AE), hidden.
        # I'll rewrite rank after the loop using column AE. Placeholder here is replaced below.

        for col in range(21, 30):
            fmt = "0.00" if col <= 26 else None
            paint(ws.cell(r, col), GREY, fmt)

        ws.cell(r, 31, f"=ROW()")
        paint(ws.cell(r, 31), GREY, "0")
        # Rank sits in column 27. PS is column 26 (Z). Eligible is column 20 (T).
        # Row index is column 31 (AE).
        ws.cell(r, 27, (
            f'=IF(T{r}<>1,"—",1+COUNTIFS($T$5:$T${LINE_LAST},1,$Z$5:$Z${LINE_LAST},">"&Z{r})'
            f'+COUNTIFS($T$5:$T${LINE_LAST},1,$Z$5:$Z${LINE_LAST},Z{r},$AE$5:$AE${LINE_LAST},"<"&AE{r}))'
        ))
        paint(ws.cell(r, 27), GREY)

    ws.conditional_formatting.add(
        f"AB5:AB{LINE_LAST}",
        FormulaRule(formula=['LEFT(AB5,5)="READY"'], fill=GREEN),
    )
    ws.conditional_formatting.add(
        f"AB5:AB{LINE_LAST}",
        FormulaRule(formula=['AND(AB5<>"—",ISERROR(SEARCH("READY",AB5)),AB5<>"N/A")'], fill=RED),
    )
    # Readiness is column 28 = AB. Yes AB is 28.
    widths(ws, {
        "A": 26, "B": 22, "C": 16, "D": 14, "E": 14, "F": 16, "G": 8, "H": 12, "I": 14,
        "J": 12, "K": 12, "L": 12, "M": 10, "N": 10, "O": 10, "P": 10, "Q": 10, "R": 10,
        "S": 12, "T": 12, "U": 10, "V": 10, "W": 10, "X": 10, "Y": 10, "Z": 10,
        "AA": 10, "AB": 24, "AC": 14, "AE": 8,
    })
    ws.freeze_panes = "C5"
    ws.auto_filter.ref = f"A4:AC{LINE_LAST}"
    ws.column_dimensions["AE"].hidden = True
    return ws


def winner_formula(score_sheet, id_col="B", rank_col="AA"):
    return (
        f'=IF(Request!$B$22=0,"NO REQUEST",'
        f'IF(OR(Policy!$B$10<>"OK",Request!$B$24<>"OK","X"="Y"),"POLICY_BLOCKED",'
        f'IF(AND(Request!$B$6="",Request!$B$7<>"Y"),"POLICY_BLOCKED",'
        f'IF(COUNTIF({score_sheet}!T$5:T${LINE_LAST},1)=0,"NONE ELIGIBLE",'
        f'INDEX({score_sheet}!{id_col}$5:{id_col}${LINE_LAST},'
        f'MATCH(1,{score_sheet}!{rank_col}$5:{rank_col}${LINE_LAST},0))))))'
    )


def build_allocation(wb):
    ws = wb.create_sheet("Allocation")
    ws["A1"] = "Allocation result and customer seed"
    ws["A1"].font = H1
    ws["A2"] = "This is the placement decision for the request. The seed block is the PLC-003 record. It is displayed, not stored."
    ws["A2"].font = SMALL

    ws["A4"] = "Customer"
    ws["C4"] = "=Request!B5"
    ws["A5"] = "Geography"
    ws["C5"] = "=Request!B4"
    ws["A6"] = "Model"
    ws["C6"] = "=Request!B9"
    for row in (4, 5, 6):
        ws.cell(row, 1).font = BOLD
        paint(ws.cell(row, 3), TEAL, align=LEFT)

    headers = ("Environment", "Role", "Region id", "Region", "Placement score", "Readiness", "Binding")
    for col, label in enumerate(headers, 1):
        cell = ws.cell(8, col, label)
        cell.font = WHITE
        cell.fill = HEAD
        cell.alignment = CTR
        cell.border = THIN

    # Prod
    ws["A9"] = "Prod"
    ws["B9"] = "Production"
    ws["C9"] = (
        '=IF(Request!B22=0,"NO REQUEST",'
        'IF(OR(Policy!B10<>"OK",Request!B24<>"OK"),"POLICY_BLOCKED",'
        'IF(AND(Request!B6="",Request!B7<>"Y"),"POLICY_BLOCKED",'
        'IF(COUNTIF(Score_Prod!T5:T18,1)=0,"NONE ELIGIBLE",'
        'INDEX(Score_Prod!B5:B18,MATCH(1,Score_Prod!AA5:AA18,0))))))'
    )
    # CVAL — does not re-check the prod-path policy; it follows the Prod winner.
    ws["A10"] = "CVAL"
    ws["B10"] = "NonProd"
    ws["C10"] = (
        '=IF(OR(C9="NO REQUEST",C9="POLICY_BLOCKED"),C9,'
        'IF(C9="NONE ELIGIBLE","NONE ELIGIBLE",'
        'IF(COUNTIF(Score_CVAL!T5:T18,1)=0,"NONE ELIGIBLE",'
        'INDEX(Score_CVAL!B5:B18,MATCH(1,Score_CVAL!AA5:AA18,0)))))'
    )
    ws["A11"] = "DR"
    ws["B11"] = '=IF(Request!B8="Y","Disaster recovery","Not offered")'
    ws["C11"] = (
        '=IF(Request!B8<>"Y","NOT_OFFERED",'
        'IF(OR(C9="NO REQUEST",C9="POLICY_BLOCKED",C9="NONE ELIGIBLE",C10="NONE ELIGIBLE"),"NONE ELIGIBLE",'
        'IF(COUNTIF(Score_DR!T5:T18,1)=0,"NONE ELIGIBLE",'
        'INDEX(Score_DR!B5:B18,MATCH(1,Score_DR!AA5:AA18,0)))))'
    )

    for row, sheet in ((9, "Score_Prod"), (10, "Score_CVAL"), (11, "Score_DR")):
        ws.cell(row, 4, f'=IF(OR(C{row}="NO REQUEST",C{row}="POLICY_BLOCKED",C{row}="NONE ELIGIBLE",C{row}="NOT_OFFERED"),"—",VLOOKUP(C{row},Region_Catalogue!B5:J18,1,FALSE))')
        # VLOOKUP id in column B returns column A name — VLOOKUP needs the lookup column to be the first.
        # Region_Catalogue column A is name, B is id. Use INDEX/MATCH instead.
        ws.cell(row, 4, f'=IF(OR(C{row}="NO REQUEST",C{row}="POLICY_BLOCKED",C{row}="NONE ELIGIBLE",C{row}="NOT_OFFERED"),"—",INDEX(Region_Catalogue!A5:A18,MATCH(C{row},Region_Catalogue!B5:B18,0)))')
        ws.cell(row, 5, f'=IF(OR(C{row}="NO REQUEST",C{row}="POLICY_BLOCKED",C{row}="NONE ELIGIBLE",C{row}="NOT_OFFERED"),"—",INDEX({sheet}!Z5:Z18,MATCH(C{row},{sheet}!B5:B18,0)))')
        ws.cell(row, 6, f'=IF(C{row}="NOT_OFFERED","NOT_OFFERED",IF(OR(C{row}="NO REQUEST",C{row}="POLICY_BLOCKED",C{row}="NONE ELIGIBLE"),C{row},INDEX({sheet}!AB5:AB18,MATCH(C{row},{sheet}!B5:B18,0))))')
        ws.cell(row, 7, f'=IF(OR(C{row}="NO REQUEST",C{row}="POLICY_BLOCKED",C{row}="NONE ELIGIBLE",C{row}="NOT_OFFERED"),"—",INDEX({sheet}!AC5:AC18,MATCH(C{row},{sheet}!B5:B18,0)))')
        for col in range(1, 8):
            paint(ws.cell(row, col), TEAL, "0.00" if col == 5 else None, LEFT if col in (2, 3, 4) else CTR)
        ws.cell(row, 1).font = BOLD

    ws["A13"] = "Overall readiness"
    ws["C13"] = (
        '=IF(C9="NO REQUEST","NO REQUEST",'
        'IF(C9="POLICY_BLOCKED","POLICY_BLOCKED",'
        'IF(OR(C9="NONE ELIGIBLE",C10="NONE ELIGIBLE"),"CAPACITY_UNAVAILABLE",'
        'IF(AND(Request!B8="Y",C11="NONE ELIGIBLE"),"CAPACITY_UNAVAILABLE",'
        'IF(OR(F9="READY_WITH_RISK",F10="READY_WITH_RISK",AND(Request!B8="Y",F11="READY_WITH_RISK")),"READY_WITH_RISK","READY")))))'
    )
    ws["A14"] = "Allocation applied"
    ws["C14"] = '=IF(OR(C13="READY",C13="READY_WITH_RISK"),1,0)'
    ws["D14"] = '=IF(C14=1,"Post_Allocation and Quota_After include this request","Post-state is unchanged")'
    for row in (13, 14):
        ws.cell(row, 1).font = BOLD
        paint(ws.cell(row, 3), ORANGE, align=LEFT)
    paint(ws["D14"], None, align=LEFT)
    ws["D14"].font = SMALL

    ws["A16"] = "Seed record (PLC-003)"
    ws["A16"].font = H2
    seed = [
        (17, "Customer", "=C4"),
        (18, "Geography", "=C5"),
        (19, "Production region", "=C9"),
        (20, "CVAL region", "=C10"),
        (21, "DR region", '=IF(C11="NOT_OFFERED","NOT_OFFERED",C11)'),
        (22, "Co-location",
         '=IF(OR(C9="NONE ELIGIBLE",C10="NONE ELIGIBLE"),"—",'
         'IF(AND(Request!B9="cross-geo",C9=C10),"Prod = CVAL, DR in Europe",'
         'IF(AND(Request!B9="2-region",C10=C11),"CVAL = DR",'
         'IF(AND(C9<>C10,C10<>C11,C9<>C11),"Three distinct regions","Check separation"))))'),
        (23, "Policy version", "=Policy!B16"),
        (24, "Snapshot", "MOCK-SNAPSHOT"),
        (25, "Exception", '=IF(Request!B6="",IF(Request!B7="Y","Geography-only selection","—"),"Named Prod region")'),
    ]
    for row, label, formula in seed:
        ws.cell(row, 1, label).font = BOLD
        cell = ws.cell(row, 3, formula)
        paint(cell, GREY, align=LEFT)
        ws.merge_cells(start_row=row, start_column=3, end_row=row, end_column=5)

    ws["A27"] = "Separation checks"
    ws["A27"].font = H2
    checks = [
        (28, "HC-1 Prod is not CVAL (except Middle East)",
         '=IF(C14<>1,"—",IF(Request!B9="cross-geo",IF(C9=C10,"PASS","FAIL"),IF(C9<>C10,"PASS","FAIL")))'),
        (29, "HC-1 Prod is not DR",
         '=IF(OR(C14<>1,C11="NOT_OFFERED"),"—",IF(C9<>C11,"PASS","FAIL"))'),
        (30, "PLC-010a CVAL = DR in a 2-region geography",
         '=IF(OR(C14<>1,Request!B9<>"2-region"),"N/A",IF(C10=C11,"PASS","FAIL"))'),
        (31, "PLC-010b Middle East DR is in Europe",
         '=IF(OR(C14<>1,Request!B9<>"cross-geo"),"N/A",IF(VLOOKUP(C11,Region_Catalogue!B5:C18,2,FALSE)="EU","PASS","FAIL"))'),
    ]
    # VLOOKUP of region id won't work: catalogue col B is not the first column.
    # Fix row 31 after writing, using INDEX/MATCH.
    checks[3] = (
        31, "PLC-010b Middle East DR is in Europe",
        '=IF(OR(C14<>1,Request!B9<>"cross-geo"),"N/A",IF(INDEX(Region_Catalogue!C5:C18,MATCH(C11,Region_Catalogue!B5:B18,0))="EU","PASS","FAIL"))',
    )
    for row, label, formula in checks:
        ws.cell(row, 1, label).font = BOLD
        paint(ws.cell(row, 3, formula), GREY)
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)

    ws["A33"] = "Even zone target for the Prod placement (PLC-011)"
    ws["A33"].font = H2
    ws["A34"] = "Target share is 1 / AZ. This mock has no per-zone inventory, so it does not raise a rebalance action."
    ws["A34"].font = SMALL
    for col, label in enumerate(("SKU", "VMs", "Prod AZ", "Even share", "Target VMs / zone"), 1):
        cell = ws.cell(35, col, label)
        cell.font = WHITE
        cell.fill = HEAD
        cell.alignment = CTR
        cell.border = THIN
    for i, req in enumerate(range(REQ_FIRST, REQ_LAST + 1)):
        r = 36 + i
        ws.cell(r, 1, f'=IF(Request!F{req}=1,Request!A{req},"")')
        ws.cell(r, 2, f'=IF(Request!F{req}=1,Request!B{req},"")')
        ws.cell(r, 3, f'=IF(OR(A{r}="",C9="NONE ELIGIBLE",C9="POLICY_BLOCKED",C9="NO REQUEST"),"",INDEX(Region_Catalogue!D5:D18,MATCH(C9,Region_Catalogue!B5:B18,0)))')
        ws.cell(r, 4, f'=IF(C{r}="","",1/C{r})')
        ws.cell(r, 5, f'=IF(C{r}="","",ROUND(B{r}/C{r},0))')
        for col in range(1, 6):
            paint(ws.cell(r, col), GREY, "0%" if col == 4 else ("0" if col in (2, 3, 5) else None),
                  LEFT if col == 1 else CTR)

    ws.conditional_formatting.add("C13", CellIsRule(operator="equal", formula=['"READY"'], fill=GREEN))
    ws.conditional_formatting.add("C13", CellIsRule(operator="equal", formula=['"READY_WITH_RISK"'], fill=PatternFill("solid", fgColor="FFEB9C")))
    ws.conditional_formatting.add("F9:F11", FormulaRule(formula=['LEFT(F9,5)="READY"'], fill=GREEN))

    widths(ws, {"A": 56, "B": 24, "C": 28, "D": 28, "E": 20, "F": 26, "G": 14})
    ws.freeze_panes = "A9"
    ws.sheet_properties.tabColor = "548235"
    return ws


def build_post(wb):
    ws = wb.create_sheet("Post_Allocation")
    ws["A1"] = "Capacity after a successful allocation"
    ws["A1"].font = H1
    ws["A2"] = '=IF(Allocation!C14=1,"Applied. Prod and CVAL take the requested cores. DR takes the bootstrap cores.","Not applied. Every Added cell is 0 because the placement is not READY.")'
    ws["A2"].font = BOLD
    ws.merge_cells("A2:P2")
    labels = (
        "Region", "Region id", "Geography", "Environment", "SKU", "Family",
        "Allocated before", "Buffer", "Reserved before", "Free before",
        "Added cores", "Allocated after", "Free after", "Shortfall", "Reserved after", "Note",
    )
    header_row(ws, 4, labels)
    for i in range(N_REG * len(ENVS) * N_SKU):
        src = 5 + i
        r = 5 + i
        for col, formula in enumerate((
            f"=Capacity_Reservations!A{src}",
            f"=Capacity_Reservations!B{src}",
            f"=Capacity_Reservations!C{src}",
            f"=Capacity_Reservations!D{src}",
            f"=Capacity_Reservations!E{src}",
            f"=Capacity_Reservations!F{src}",
            f"=Capacity_Reservations!I{src}",
            f"=Capacity_Reservations!J{src}",
            f"=Capacity_Reservations!K{src}",
            f"=Capacity_Reservations!L{src}",
        ), 1):
            paint(ws.cell(r, col, formula), None, "#,##0" if col >= 7 else None,
                  LEFT if col in (1, 2, 5) else CTR)
        ws.cell(r, 11, (
            f'=IF(Allocation!$C$14<>1,0,'
            f'IF(D{r}="Prod",IF(B{r}=Allocation!$C$9,SUMIF(Request!$A$13:$A$20,E{r},Request!$D$13:$D$20),0),'
            f'IF(D{r}="NonProd",IF(B{r}=Allocation!$C$10,SUMIF(Request!$A$13:$A$20,E{r},Request!$D$13:$D$20),0),'
            f'IF(AND(D{r}="DR",B{r}=Allocation!$C$11),ROUND(SUMIF(Request!$A$13:$A$20,E{r},Request!$D$13:$D$20)*Policy!$B$15,0),0))))'
        ))
        ws.cell(r, 12, f"=G{r}+K{r}")
        ws.cell(r, 13, f"=MAX(0,J{r}-K{r})")
        ws.cell(r, 14, f"=MAX(0,K{r}-J{r})")
        ws.cell(r, 15, f"=L{r}+H{r}")
        ws.cell(r, 16, f'=IF(K{r}=0,"",IF(N{r}>0,"Request exceeded free cores","Placed"))')
        for col in range(11, 17):
            paint(ws.cell(r, col), GREY, "#,##0" if col < 16 else None)
    ws.conditional_formatting.add(
        f"K5:K{CAP_LAST}",
        CellIsRule(operator="greaterThan", formula=["0"], fill=ORANGE),
    )
    widths(ws, {"A": 26, "B": 22, "C": 16, "D": 14, "E": 24, "F": 12, "G": 18, "H": 12,
                "I": 18, "J": 14, "K": 14, "L": 18, "M": 14, "N": 12, "O": 16, "P": 28})
    ws.freeze_panes = "A5"
    ws.auto_filter.ref = f"A4:P{CAP_LAST}"
    ws.sheet_properties.tabColor = "548235"
    return ws


def build_quota_after(wb):
    ws = wb.create_sheet("Quota_After")
    ws["A1"] = "Quota groups after a successful allocation"
    ws["A1"].font = H1
    ws["A2"] = "Added cores are the Prod, CVAL, and DR amounts placed in that region for that family. Available falls by the same number."
    ws["A2"].font = SMALL
    labels = (
        "Quota group", "Region", "Region id", "Geography", "Family",
        "Limit", "Used before", "Available before", "Added", "Used after", "Available after",
    )
    header_row(ws, 4, labels)
    for i in range(N_REG * N_FAM):
        src = 5 + i
        r = 5 + i
        for col, formula in enumerate((
            f"=Quota_Groups!A{src}",
            f"=Quota_Groups!B{src}",
            f"=Quota_Groups!C{src}",
            f"=Quota_Groups!D{src}",
            f"=Quota_Groups!E{src}",
            f"=Quota_Groups!F{src}",
            f"=Quota_Groups!G{src}",
            f"=Quota_Groups!H{src}",
        ), 1):
            paint(ws.cell(r, col, formula), None, "#,##0" if col >= 6 else None,
                  LEFT if col in (1, 2, 3, 5) else CTR)
        ws.cell(r, 9, (
            f'=SUMIFS(Post_Allocation!$K$5:$K${CAP_LAST},Post_Allocation!$B$5:$B${CAP_LAST},C{r},'
            f'Post_Allocation!$F$5:$F${CAP_LAST},E{r})'
        ))
        ws.cell(r, 10, f"=G{r}+I{r}")
        ws.cell(r, 11, f"=F{r}-J{r}")
        for col in range(9, 12):
            paint(ws.cell(r, col), GREY, "#,##0")
    ws.conditional_formatting.add(
        f"I5:I{QUOTA_LAST}",
        CellIsRule(operator="greaterThan", formula=["0"], fill=ORANGE),
    )
    widths(ws, {"A": 22, "B": 26, "C": 22, "D": 16, "E": 12, "F": 12, "G": 14, "H": 18, "I": 12, "J": 14, "K": 18})
    ws.freeze_panes = "A5"
    ws.auto_filter.ref = f"A4:K{QUOTA_LAST}"
    ws.sheet_properties.tabColor = "548235"
    return ws


def build():
    cap_rows = capacity_rows()
    limits = quota_limits(cap_rows)
    wb = Workbook()
    build_readme(wb)
    build_request(wb)
    build_policy(wb)
    build_catalogue(wb)
    build_skus(wb)
    build_capacity(wb, cap_rows)
    build_quota(wb, cap_rows, limits)
    build_line_check(wb)
    build_score(wb, "prod", "Production score — PS_Prod")
    build_score(wb, "cval", "CVAL / NonProd score — PS_NonProd")
    build_score(wb, "dr", "DR score — PS_DR")
    build_allocation(wb)
    build_post(wb)
    build_quota_after(wb)
    # Drop the unused chart import side effects by not adding a chart.
    wb.calculation.calcMode = "auto"
    wb.calculation.fullCalcOnLoad = True
    order = [
        "ReadMe", "Request", "Policy", "Region_Catalogue", "SKU_Catalogue",
        "Capacity_Reservations", "Quota_Groups", "Line_Check",
        "Score_Prod", "Score_CVAL", "Score_DR", "Allocation",
        "Post_Allocation", "Quota_After",
    ]
    for i, name in enumerate(order):
        wb.move_sheet(name, offset=i - wb.sheetnames.index(name))
    wb.save(OUT)
    print(f"Wrote {OUT}")
    print(f"Capacity rows {CAP_FIRST}-{CAP_LAST}, quota rows {QUOTA_FIRST}-{QUOTA_LAST}")
    return OUT


if __name__ == "__main__":
    build()
