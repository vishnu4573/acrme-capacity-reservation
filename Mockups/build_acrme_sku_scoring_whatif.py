#!/usr/bin/env python3
"""ACRME SKU-Level Placement WHAT-IF  —  PHASE 2 (SKU-grain scoring).

DIFFERENT what-if from the region-selection model
(`acrme_region_selection_whatif_acrme_regions.xlsx`, which scores capacity/quota
as ONE blended number per region). This workbook scores placement at the grain
the baseline already mandates:

  * capacity is reserved PER SKU               (CAP-022 / CAP-023)
  * quota is granted PER VM/quota family       (QUA-002 / QUA-003 / QUA-004)
  * a candidate is only placeable when BOTH hold:
        group_availability = MIN( SKU reserved_free , family quota_available )

Phase 2 points the availability term (alpha) of the placement score at the
per-SKU group_availability for the REQUESTED SKU, and emits an RDY-002 readiness
state per candidate. It ranks the ACRME candidate regions for Prod / CVAL(NonProd)
/ DR for that specific SKU.

This is a STANDALONE mockup file (per user request: Phase 2 is a NEW file, a
different kind of what-if analysis). It does NOT modify the Phase 1 workbook or
the v2.4 baseline. It is read-only / feasibility: the freeze & logical-lock layer
is Phase 3.

Rulings carried from Phase 1:
  - ONE pooled quota group per (region x family) across Prod+NonProd+DR (QUA-004).
  - ENV-003 hard separation applies to CAPACITY reservations only; quota pooled.
  - Quota hoarded to a single pool, distributed on demand (QUA-003).
  - DR = 30% bootstrap of Prod (ENV-005), not a full duplicate.
"""
import openpyxl, math
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.utils import get_column_letter
from collections import defaultdict

SRC = "/home/ubuntu/Uploads/SKU_USage (1).xlsx"
OUT = "/home/ubuntu/acrme-capacity-reservation/Mockups/acrme_sku_placement_whatif.xlsx"

# ============================================================ styles
H1     = Font(bold=True, size=14, color="1F3864")
H2     = Font(bold=True, size=11, color="1F3864")
BOLD   = Font(bold=True)
WHITEB = Font(bold=True, color="FFFFFF")
HEADFILL = PatternFill("solid", fgColor="1F3864")
SUBFILL  = PatternFill("solid", fgColor="D9E1F2")
INFILL   = PatternFill("solid", fgColor="FFF2CC")   # yellow = user input
WARNFILL = PatternFill("solid", fgColor="FCE4D6")
RESTFILL = PatternFill("solid", fgColor="EDEDED")
ORANGE   = PatternFill("solid", fgColor="F4B183")   # the MIN join / decision cells
BLUE     = PatternFill("solid", fgColor="DDEBF7")
GREENF   = PatternFill("solid", fgColor="C6EFCE")
REDF     = PatternFill("solid", fgColor="FFC7CE")
thin = Side(style="thin", color="BFBFBF")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)
CTR  = Alignment(horizontal="center", vertical="center")
WRAP = Alignment(wrap_text=True, vertical="top")
LEFT = Alignment(horizontal="left", vertical="center")

# ============================================================ modelled SKU set
# (sku, vcpu/instance, quota family) — multiple SKUs per family on purpose
PHASE1_SKUS = [
 ("Standard_E32ads_v5", 32, "Eadsv5"),
 ("Standard_E64ads_v5", 64, "Eadsv5"),
 ("Standard_E16ads_v5", 16, "Eadsv5"),
 ("Standard_E32ads_v6", 32, "Eadsv6"),
 ("Standard_D8ads_v5",   8, "Dadsv5"),
 ("Standard_D16ads_v5", 16, "Dadsv5"),
 ("Standard_D8as_v5",    8, "Dasv5"),
 ("Standard_D16as_v5",  16, "Dasv5"),
]
FAM_OF_SKU  = {s: f for (s, _, f) in PHASE1_SKUS}
VCPU_OF_SKU = {s: v for (s, v, _) in PHASE1_SKUS}
FAMILIES    = ["Eadsv5", "Eadsv6", "Dadsv5", "Dasv5"]

# ============================================================ region scope (US + EU)
# (region_name, region_id, geography, is_mock)
PHASE1_REGIONS = [
 ("West US 3", "westus3", "US", False),
 ("Central US", "centralus", "US", False),
 ("Canada Central", "canadacentral", "US", True),   # absent in data -> mock (flagged)
 ("East US 2", "eastus2", "US", False),
 ("Switzerland North", "switzerlandnorth", "EU", False),
 ("Sweden Central", "swedencentral", "EU", False),
 ("North Europe", "northeurope", "EU", False),
 ("West Europe", "westeurope", "EU", False),
]
REGABBR = {"westus3": "wus3", "centralus": "cus", "canadacentral": "cac", "eastus2": "eus2",
           "switzerlandnorth": "chn", "swedencentral": "sec", "northeurope": "neu", "westeurope": "weu"}
ENVAB = {"Prod": "pr", "NonProd": "np", "DR": "dr"}
DR_BOOTSTRAP = 0.30

# ============================================================ real usage
def _isprod(t):
    t = (t or '').strip().lower(); return t == 'prod' and 'non' not in t
_alloc = defaultdict(float)
_wbP = openpyxl.load_workbook(SRC, data_only=True); _wsP = _wbP['Sheet1']
for _r in range(2, _wsP.max_row + 1):
    _env = _wsP.cell(_r, 1).value; _reg = _wsP.cell(_r, 2).value; _sku = _wsP.cell(_r, 5).value
    _cores = _wsP.cell(_r, 9).value or 0
    if _sku in FAM_OF_SKU:
        _e = 'Prod' if _isprod(_env) else 'NonProd'
        _alloc[(_reg, _e, _sku)] += _cores

def _mock_cc(env, sku):
    src = [_alloc[(rn, env, sku)] for (rn, rid, g, mk) in PHASE1_REGIONS if g == 'US' and not mk]
    m = sum(src) / max(1, len(src)); return round(0.5 * m)

def alloc_of(region, is_mock, env, sku):
    if env == 'DR':
        base = alloc_of(region, is_mock, 'Prod', sku); return round(DR_BOOTSTRAP * base)
    if is_mock:
        return _mock_cc(env, sku)
    return round(_alloc.get((region, env, sku), 0.0))

def buffer_of(a):
    return max(8, round(0.12 * a))

# pooled family-used per (region, family) across ALL envs -> quota limit basis
_famused = defaultdict(float)
for (rn, rid, g, mk) in PHASE1_REGIONS:
    for env in ("Prod", "NonProd", "DR"):
        for (s, v, f) in PHASE1_SKUS:
            _famused[(rn, f)] += alloc_of(rn, mk, env, s)
_LIMFACT = {"Eadsv5": 1.05, "Eadsv6": 1.15, "Dadsv5": 1.25, "Dasv5": 1.45}

wb = Workbook()

# ============================================================ helpers
def hdr(ws, row, headers, startcol=1, fill=HEADFILL, font=WHITEB):
    for i, h in enumerate(headers):
        c = ws.cell(row, startcol + i, h)
        c.fill = fill; c.font = font; c.alignment = WRAP; c.border = BORDER

def setw(ws, widths):
    for col, w in widths.items():
        ws.column_dimensions[col].width = w

# ==================================================================== SKU_Family_Map
fm = wb.active; fm.title = "SKU_Family_Map"; fm.sheet_view.showGridLines = False
fm["A1"] = "SKU -> QUOTA FAMILY MAP (drives all lookups)"; fm["A1"].font = H1; fm.merge_cells("A1:B1")
fm["A2"] = "Capacity is reserved per SKU; quota is granted per family. Many SKUs -> one family."
fm["A2"].font = Font(italic=True, color="595959"); fm.merge_cells("A2:B2")
hdr(fm, 3, ["SKU", "Quota Family"])
r = 4
for (s, v, f) in PHASE1_SKUS:
    fm.cell(r, 1, s).border = BORDER; fm.cell(r, 2, f).border = BORDER; r += 1
setw(fm, {"A": 24, "B": 16})

# ==================================================================== SKU_Catalogue
sc = wb.create_sheet("SKU_Catalogue"); sc.sheet_view.showGridLines = False
sc["A1"] = "SKU CATALOGUE (managed seed-matrix view, CAP-022)"; sc["A1"].font = H1; sc.merge_cells("A1:F1")
hdr(sc, 3, ["SKU", "vCPU/inst", "Quota Family", "Zonal? (CAP-020)", "Eligible?", "Notes"])
r = 4
for (s, v, f) in PHASE1_SKUS:
    sc.cell(r, 1, s).border = BORDER
    sc.cell(r, 2, v).border = BORDER; sc.cell(r, 2).alignment = CTR
    sc.cell(r, 3, f).border = BORDER
    sc.cell(r, 4, "Yes").border = BORDER; sc.cell(r, 4).alignment = CTR
    sc.cell(r, 5, "Yes").border = BORDER; sc.cell(r, 5).alignment = CTR
    sc.cell(r, 6, " Dadsv5/eadsv5/dasv5 general-purpose & memory-optimised").border = BORDER
    r += 1
setw(sc, {"A": 24, "B": 10, "C": 14, "D": 15, "E": 10, "F": 52})

# ==================================================================== Capacity_By_SKU  (source plane)
cs = wb.create_sheet("Capacity_By_SKU"); cs.sheet_view.showGridLines = False
cs["A1"] = "CAPACITY BY SKU  —  reservations at Region x Environment x SKU (CAP-023)"; cs["A1"].font = H1; cs.merge_cells("A1:P1")
cs["A2"] = "Reservation plane. GROUP AVAIL (col M) = MIN(reserved-free, family quota-available) is the placeable headroom for one SKU."
cs["A2"].font = Font(italic=True, color="595959"); cs.merge_cells("A2:P2")
HR = 4
cs["A3"] = ("NOTE: CRG modelled at REGIONAL scope (crg-...-reg). Per-AZ CRGs (crg-...-az1, CAP-023/CAP-011) are the next increment. "
            "Allocated is derived from real usage; Canada Central is a flagged mock; DR = 30% of Prod (ENV-005 bootstrap).")
cs["A3"].font = Font(italic=True, color="C00000"); cs.merge_cells("A3:P3")
cap_headers = ["Region", "Geography", "Environment", "SKU", "Family", "CRG (CAP-023)", "vCPU/inst",
               "Allocated", "Buffer", "Reserved", "Reserved-Free", "Family Quota-Avail",
               "GROUP AVAIL (MIN)", "Binding Constraint", "Readiness (RDY-002)", "Notes"]
hdr(cs, HR, cap_headers)
r = HR + 1
cap_row_of = {}   # (region, env, sku) -> row
for (rn, rid, g, mk) in PHASE1_REGIONS:
    for env in ("Prod", "NonProd", "DR"):
        for (s, v, f) in PHASE1_SKUS:
            a = alloc_of(rn, mk, env, s); b = buffer_of(a)
            crg = f"crg-{ENVAB[env]}-{REGABBR[rid]}-reg"
            cap_row_of[(rn, env, s)] = r
            vals = {1: rn, 2: g, 3: env, 4: s, 5: f"=VLOOKUP(D{r},SKU_Family_Map!$A:$B,2,FALSE)",
                    6: crg, 7: v, 8: a, 9: b, 10: f"=H{r}+I{r}", 11: f"=J{r}-H{r}",
                    12: f"=SUMIFS(Quota_Groups!$G:$G,Quota_Groups!$B:$B,A{r},Quota_Groups!$D:$D,E{r})",
                    13: f"=MIN(K{r},L{r})",
                    14: f'=IF(K{r}<=L{r},"CAPACITY","QUOTA")',
                    15: f'=IF(K{r}<=0,"RESERVATION_DEFICIT",IF(L{r}<=0,"QUOTA_DEFICIT",IF(M{r}<I{r}*0.5,"READY_WITH_RISK","READY")))',
                    16: "mock" if mk else ""}
            for c, val in vals.items():
                cell = cs.cell(r, c, val); cell.border = BORDER
                if c in (7, 8, 9, 10, 11, 12, 13): cell.alignment = CTR
            cs.cell(r, 13).fill = ORANGE; cs.cell(r, 13).font = BOLD
            r += 1
CAP_LAST = r - 1
setw(cs, {"A": 16, "B": 10, "C": 12, "D": 20, "E": 10, "F": 20, "G": 9, "H": 10, "I": 8,
          "J": 10, "K": 12, "L": 16, "M": 16, "N": 16, "O": 20, "P": 8})

# ==================================================================== Quota_Groups (source plane)
qg = wb.create_sheet("Quota_Groups"); qg.sheet_view.showGridLines = False
qg["A1"] = "QUOTA GROUPS  —  ONE pooled group per Region x Family (QUA-002/003/004)"; qg["A1"].font = H1; qg.merge_cells("A1:J1")
qg["A2"] = "Quota plane. ONE governed group per region+family, POOLED across Prod+NonProd+DR (QUA-004); hoarded, distributed on demand (QUA-003)."
qg["A2"].font = Font(italic=True, color="595959"); qg.merge_cells("A2:J2")
HRq = 3
qg_headers = ["Quota Group", "Region", "Geography", "Quota Family", "Group Limit (pooled)",
              "Group Used (all envs)", "Group Available", "Hoarded Contrib", "Pending Increase", "Notes"]
hdr(qg, HRq, qg_headers)
qr = HRq + 1
for (rn, rid, g, mk) in PHASE1_REGIONS:
    for fam in FAMILIES:
        used = _famused[(rn, fam)]; lim = round(used * _LIMFACT[fam]); hoard = round(0.10 * lim)
        vals = {1: f"qg-{REGABBR[rid]}-{fam.lower()}", 2: rn, 3: g, 4: fam, 5: lim,
                6: f"=SUMIFS(Capacity_By_SKU!$H:$H,Capacity_By_SKU!$A:$A,B{qr},Capacity_By_SKU!$E:$E,D{qr})",
                7: f"=E{qr}-F{qr}", 8: hoard, 9: 0, 10: "mock" if mk else ""}
        for c, val in vals.items():
            cell = qg.cell(qr, c, val); cell.border = BORDER
            if c in (5, 6, 7, 8, 9): cell.alignment = CTR
        qg.cell(qr, 7).fill = BLUE
        qr += 1
setw(qg, {"A": 22, "B": 16, "C": 10, "D": 14, "E": 18, "F": 18, "G": 16, "H": 14, "I": 14, "J": 8})

# ==================================================================== Policy (weights / thresholds)
pol = wb.create_sheet("Policy"); pol.sheet_view.showGridLines = False
pol["A1"] = "POLICY  —  Placement-score weights & thresholds (edit yellow cells)"; pol["A1"].font = H1; pol.merge_cells("A1:C1")
pol["A3"] = "Score weights (must sum to 1.00)"; pol["A3"].font = H2; pol["A3"].fill = SUBFILL; pol.merge_cells("A3:C3")
weights = [
 ("w_alpha  (availability fit: group_avail vs requested)", 0.50, "B4"),
 ("w_beta   (family quota headroom ratio)", 0.30, "B5"),
 ("w_epsilon (buffer safety: reserved-free vs reserved)", 0.20, "B6"),
]
r = 4
for label, val, _ in weights:
    pol.cell(r, 1, label).border = BORDER
    c = pol.cell(r, 2, val); c.fill = INFILL; c.border = BORDER; c.alignment = CTR; r += 1
pol.cell(7, 1, "Sum of weights (check = 1.00)").font = BOLD
pol.cell(7, 2, "=B4+B5+B6").font = BOLD; pol.cell(7, 2).alignment = CTR; pol.cell(7, 2).border = BORDER
pol["A9"] = "Thresholds"; pol["A9"].font = H2; pol["A9"].fill = SUBFILL; pol.merge_cells("A9:C9")
thr = [
 ("risk_threshold  (READY_WITH_RISK if alpha < this value; 0.10 = keep ≥10% buffer)", 0.10, "B10"),
 ("min_buffer_floor (cores; buffer must stay >= this after placement)", 8, "B11"),
]
r = 10
for label, val, _ in thr:
    pol.cell(r, 1, label).border = BORDER
    c = pol.cell(r, 2, val); c.fill = INFILL; c.border = BORDER; c.alignment = CTR; r += 1
setw(pol, {"A": 58, "B": 12, "C": 4})

# Row constants — referenced by build_scoring so define BEFORE that function
RQ_FIRST = 8   # first SKU line row
RQ_LAST  = 15  # last  SKU line row
RQ_ACT   = 17  # active-lines summary row
RQ_TOT   = 18  # total-cores summary row

# ==================================================================== Request (inputs)
rq = wb.create_sheet("Request"); rq.sheet_view.showGridLines = False
rq["A1"] = "REQUEST  —  Customer placement request (edit yellow cells)"; rq["A1"].font = H1; rq.merge_cells("A1:G1")
rq["A2"] = ("Phase 2 evaluates up to 8 SKU lines per deployment. "
             "Enter each SKU and VM count; ALL lines must be satisfiable in a candidate region for it to be Eligible.")
rq["A2"].font = Font(italic=True, color="595959"); rq.merge_cells("A2:G2")

# Row 4: Geography
rq.cell(4, 1, "Geography").font = BOLD; rq.cell(4, 1).border = BORDER
c = rq.cell(4, 2, "US"); c.fill = INFILL; c.border = BORDER; c.alignment = CTR
rq.cell(4, 3, "US or EU (candidate regions filtered to this)").font = Font(italic=True, color="595959")

# Row 5: Customer ID
rq.cell(5, 1, "Customer ID").font = BOLD; rq.cell(5, 1).border = BORDER
c = rq.cell(5, 2, "CUST-0042"); c.fill = INFILL; c.border = BORDER; c.alignment = CTR

# Row 7: table header
tbl_heads = ["Line #", "SKU", "VM Count", "vCPU / inst", "Line Cores", "Quota Family", "Notes"]
for ci, h in enumerate(tbl_heads, 1):
    c = rq.cell(7, ci, h); c.font = BOLD; c.fill = SUBFILL; c.border = BORDER; c.alignment = CTR

# Rows 8–15: SKU line items (8 lines)
SAMPLE_SKUS = [
    ("Standard_E32ads_v5", 4),
    ("Standard_D8as_v5",   2),
]
sku_list_str = ",".join([s for (s, v, f) in PHASE1_SKUS])
dv_geo = DataValidation(type="list", formula1='"US,EU"', allow_blank=False)
rq.add_data_validation(dv_geo); dv_geo.add(rq["B4"])
dv_sku = DataValidation(type="list", formula1=f'"{sku_list_str}"', allow_blank=True)
rq.add_data_validation(dv_sku)

for idx in range(8):
    r = RQ_FIRST + idx
    # Col A: line number (static label)
    c = rq.cell(r, 1, idx + 1); c.font = BOLD; c.border = BORDER; c.alignment = CTR
    # Col B: SKU (yellow dropdown)
    sku_val = SAMPLE_SKUS[idx][0] if idx < len(SAMPLE_SKUS) else ""
    c = rq.cell(r, 2, sku_val); c.fill = INFILL; c.border = BORDER; c.alignment = CTR
    dv_sku.add(rq.cell(r, 2))
    # Col C: VM count (yellow)
    vm_val = SAMPLE_SKUS[idx][1] if idx < len(SAMPLE_SKUS) else ""
    c = rq.cell(r, 3, vm_val); c.fill = INFILL; c.border = BORDER; c.alignment = CTR
    # Col D: vCPU / inst (derived) — blank if SKU blank
    vcpu_f = f'=IFERROR(IF(B{r}="","",VLOOKUP(B{r},SKU_Catalogue!$A:$B,2,FALSE)),"")'
    c = rq.cell(r, 4, vcpu_f); c.fill = RESTFILL; c.border = BORDER; c.alignment = CTR
    # Col E: line cores = VM count × vCPU (derived)
    cores_f = f'=IFERROR(IF(OR(B{r}="",C{r}=""),"",C{r}*D{r}),"")'
    c = rq.cell(r, 5, cores_f); c.fill = RESTFILL; c.border = BORDER; c.alignment = CTR
    # Col F: Quota Family (derived)
    fam_f = f'=IFERROR(IF(B{r}="","",VLOOKUP(B{r},SKU_Family_Map!$A:$B,2,FALSE)),"")'
    c = rq.cell(r, 6, fam_f); c.fill = RESTFILL; c.border = BORDER; c.alignment = CTR
    # Col G: Notes (free text — blank)
    rq.cell(r, 7).border = BORDER

# Row 16: separator (empty styled row)
for ci in range(1, 8):
    rq.cell(16, ci).border = BORDER

# Row 17: Active lines count
rq.cell(RQ_ACT, 1, "Active lines (SKU + VM both filled)").font = BOLD; rq.cell(RQ_ACT, 1).border = BORDER
act_f = f'=COUNTIFS(B{RQ_FIRST}:B{RQ_LAST},"<>",C{RQ_FIRST}:C{RQ_LAST},"<>")'
c = rq.cell(RQ_ACT, 2, act_f); c.border = BORDER; c.alignment = CTR; c.fill = RESTFILL
rq.merge_cells(f"A{RQ_ACT}:A{RQ_ACT}")

# Row 18: Total cores
rq.cell(RQ_TOT, 1, "Total requested cores (all active lines)").font = BOLD; rq.cell(RQ_TOT, 1).border = BORDER
tot_f = f'=SUMPRODUCT(IFERROR(E{RQ_FIRST}:E{RQ_LAST}*1,0))'
c = rq.cell(RQ_TOT, 2, tot_f); c.border = BORDER; c.alignment = CTR; c.fill = RESTFILL

# Row 19: constraint note
rq.cell(19, 1, "★ A region is Eligible only when every active line can be satisfied (Meets-All = 1).").font = Font(italic=True, color="595959")
rq.merge_cells("A19:G19")

setw(rq, {"A": 34, "B": 22, "C": 10, "D": 12, "E": 12, "F": 18, "G": 28})

# ==================================================================== scoring sheet builder
def build_scoring(sheet, env, title, exclude_regionmatch=False):
    """One scoring sheet per environment (Prod/CVAL/DR).
    Evaluates ALL active SKU lines in the Request sheet for EVERY candidate region.
    A region is Eligible only when EVERY active line has GROUP AVAIL >= line cores.
    Score components (alpha/beta/eps) are MIN across active lines (bottleneck drives score).
    """
    ws = wb.create_sheet(sheet); ws.sheet_view.showGridLines = False
    ws["A1"] = title; ws["A1"].font = H1; ws.merge_cells("A1:O1")
    ws["A2"] = ("Meets-All = 1 only when EVERY active SKU line has GROUP AVAIL \u2265 Line Cores. "
                "Alpha=MIN(1\u2212cores/GAVAIL), Beta=MIN(quota-avail/quota-limit), "
                "Eps=MIN(res-free/res) across all active lines.")
    ws["A2"].font = Font(italic=True, color="595959"); ws.merge_cells("A2:O2")

    heads = ["Region", "Geo", "Env", "Active Lines", "Total Req Cores",
             "InGeo", "Meets-All", "Readiness (RDY-002)", "Eligible",
             "alpha_c", "beta_c", "eps_c", "PS", "Rank", "Binding"]
    HRs = 3
    hdr(ws, HRs, heads)
    r0 = HRs + 1

    # ---- inner formula helpers (capture env from outer scope) ----

    def gavail_f(sk, rr):
        """Return (rf_formula, qa_formula, gavail_formula) for line sk in scoring row rr."""
        rkey = (f'Capacity_By_SKU!$A:$A,$A{rr},'
                f'Capacity_By_SKU!$C:$C,"{env}",'
                f'Capacity_By_SKU!$D:$D,Request!$B${sk}')
        fam  = f'IFERROR(VLOOKUP(Request!$B${sk},SKU_Family_Map!$A:$B,2,FALSE),"")'
        qkey = f'Quota_Groups!$B:$B,$A{rr},Quota_Groups!$D:$D,{fam}'
        rf   = f'SUMIFS(Capacity_By_SKU!$K:$K,{rkey})'
        qa   = f'SUMIFS(Quota_Groups!$G:$G,{qkey})'
        return rf, qa, f'MIN({rf},{qa})'

    def meets_line_f(sk, rr):
        """1 if line sk is satisfiable in rr, else 0. Blank line contributes 1."""
        _, _, ga = gavail_f(sk, rr)
        return (f'IF(OR(Request!$B${sk}="",Request!$C${sk}=""),1,'
                f'IF({ga}>=Request!$E${sk},1,0))')

    def meets_all_f(rr):
        parts = [meets_line_f(sk, rr) for sk in range(RQ_FIRST, RQ_LAST + 1)]
        return f'=IF(Request!$B${RQ_ACT}=0,0,MIN({",".join(parts)}))'

    def alpha_line_f(sk, rr):
        _, _, ga = gavail_f(sk, rr)
        return (f'IF(OR(Request!$B${sk}="",Request!$C${sk}=""),1,'
                f'IFERROR(1-Request!$E${sk}/{ga},0))')

    def beta_line_f(sk, rr):
        fam  = f'IFERROR(VLOOKUP(Request!$B${sk},SKU_Family_Map!$A:$B,2,FALSE),"")'
        qkey = f'Quota_Groups!$B:$B,$A{rr},Quota_Groups!$D:$D,{fam}'
        qa   = f'SUMIFS(Quota_Groups!$G:$G,{qkey})'
        ql   = f'SUMIFS(Quota_Groups!$E:$E,{qkey})'
        return (f'IF(OR(Request!$B${sk}="",Request!$C${sk}=""),1,'
                f'IFERROR({qa}/MAX({ql},1),0))')

    def eps_line_f(sk, rr):
        rkey = (f'Capacity_By_SKU!$A:$A,$A{rr},'
                f'Capacity_By_SKU!$C:$C,"{env}",'
                f'Capacity_By_SKU!$D:$D,Request!$B${sk}')
        rf  = f'SUMIFS(Capacity_By_SKU!$K:$K,{rkey})'
        res = f'SUMIFS(Capacity_By_SKU!$J:$J,{rkey})'
        return (f'IF(OR(Request!$B${sk}="",Request!$C${sk}=""),1,'
                f'IFERROR({rf}/MAX({res},1),0))')

    def readiness_f(rr):
        res_chks, qa_chks = [], []
        for sk in range(RQ_FIRST, RQ_LAST + 1):
            rf, qa, _ = gavail_f(sk, rr)
            act = f'Request!$B${sk}<>"",Request!$C${sk}<>""'
            res_chks.append(f'IF(AND({act},{rf}<=0),1,0)')
            qa_chks.append( f'IF(AND({act},{qa}<=0),1,0)')
        res_def   = f'SUM({",".join(res_chks)})>0'
        quota_def = f'SUM({",".join(qa_chks)})>0'
        alp = [alpha_line_f(sk, rr) for sk in range(RQ_FIRST, RQ_LAST + 1)]
        alpha_min = f'MIN({",".join(alp)})'
        return (f'=IF(Request!$B${RQ_ACT}=0,"NO_REQUEST",'
                f'IF({res_def},"RESERVATION_DEFICIT",'
                f'IF({quota_def},"QUOTA_DEFICIT",'
                f'IF(G{rr}=0,"CAPACITY_DEFICIT",'
                f'IF({alpha_min}<Policy!$B$10,"READY_WITH_RISK","READY")))))')

    # ---- per-region rows (pass 1: main columns) ----
    for i, (rn, rid, g, mk) in enumerate(PHASE1_REGIONS):
        rr = r0 + i
        ws.cell(rr, 1, rn).border = BORDER
        ws.cell(rr, 2, g).border  = BORDER; ws.cell(rr, 2).alignment = CTR
        ws.cell(rr, 3, env).border= BORDER; ws.cell(rr, 3).alignment = CTR
        ws.cell(rr, 4, f'=Request!$B${RQ_ACT}').border = BORDER; ws.cell(rr, 4).alignment = CTR
        ws.cell(rr, 5, f'=Request!$B${RQ_TOT}').border = BORDER; ws.cell(rr, 5).alignment = CTR
        ws.cell(rr, 6, f'=IF(B{rr}=Request!$B$4,1,0)').border = BORDER; ws.cell(rr, 6).alignment = CTR

        c = ws.cell(rr, 7, meets_all_f(rr))
        c.border = BORDER; c.alignment = CTR; c.fill = ORANGE; c.font = BOLD

        ws.cell(rr, 8, readiness_f(rr)).border = BORDER

        elig = f'=IF(AND(F{rr}=1,G{rr}=1,OR(H{rr}="READY",H{rr}="READY_WITH_RISK")),1,0)'
        ws.cell(rr, 9, elig).border = BORDER; ws.cell(rr, 9).alignment = CTR

        alpha_f = f'=IF(I{rr}=1,MAX(0,MIN({",".join(alpha_line_f(sk,rr) for sk in range(RQ_FIRST,RQ_LAST+1))})),0)'
        beta_f  = f'=IF(I{rr}=1,MAX(0,MIN({",".join(beta_line_f(sk,rr)  for sk in range(RQ_FIRST,RQ_LAST+1))})),0)'
        eps_f   = f'=IF(I{rr}=1,MAX(0,MIN({",".join(eps_line_f(sk,rr)   for sk in range(RQ_FIRST,RQ_LAST+1))})),0)'

        ws.cell(rr, 10, alpha_f).border = BORDER; ws.cell(rr, 10).alignment = CTR
        ws.cell(rr, 11, beta_f).border  = BORDER; ws.cell(rr, 11).alignment = CTR
        ws.cell(rr, 12, eps_f).border   = BORDER; ws.cell(rr, 12).alignment = CTR

        ps = f'=IF(I{rr}=1,ROUND(Policy!$B$4*J{rr}+Policy!$B$5*K{rr}+Policy!$B$6*L{rr},4),"")'
        c  = ws.cell(rr, 13, ps); c.border = BORDER; c.alignment = CTR; c.fill = SUBFILL

    RS_LAST = r0 + len(PHASE1_REGIONS) - 1

    # ---- per-region rows (pass 2: rank + binding, now RS_LAST is known) ----
    for i, _ in enumerate(PHASE1_REGIONS):
        rr = r0 + i
        rank = (f'=IF(I{rr}=1,'
                f'SUMPRODUCT(($I${r0}:$I${RS_LAST}=1)*($M${r0}:$M${RS_LAST}>M{rr}))+1,"")')
        ws.cell(rr, 14, rank).border = BORDER; ws.cell(rr, 14).alignment = CTR

        min_rf = f'MIN({",".join(eps_line_f(sk,rr)  for sk in range(RQ_FIRST,RQ_LAST+1))})'
        min_qa = f'MIN({",".join(beta_line_f(sk,rr) for sk in range(RQ_FIRST,RQ_LAST+1))})'
        bind   = f'=IF(I{rr}=0,"N/A",IF({min_rf}<={min_qa},"CAPACITY","QUOTA"))'
        ws.cell(rr, 15, bind).border = BORDER; ws.cell(rr, 15).alignment = CTR

    # ---- TOP PICK summary (cols Q / R) ----
    ws["Q1"] = "TOP PICK"; ws["Q1"].font = H2
    ws["Q2"] = "Region";    ws["Q3"] = "PS";    ws["Q4"] = "Readiness"
    ws["R2"] = f'=IFERROR(INDEX($A${r0}:$A${RS_LAST},MATCH(1,$N${r0}:$N${RS_LAST},0)),"NONE ELIGIBLE")'
    ws["R3"] = f'=IFERROR(INDEX($M${r0}:$M${RS_LAST},MATCH(1,$N${r0}:$N${RS_LAST},0)),"")'
    ws["R4"] = f'=IFERROR(INDEX($H${r0}:$H${RS_LAST},MATCH(1,$N${r0}:$N${RS_LAST},0)),"")'
    for cc in ("Q2","Q3","Q4"): ws[cc].font = BOLD
    for cc in ("R2","R3","R4"): ws[cc].alignment = CTR; ws[cc].fill = GREENF

    setw(ws, {"A": 16, "B": 8, "C": 8, "D": 11, "E": 13, "F": 7,
              "G": 11, "H": 20, "I": 8, "J": 9, "K": 9, "L": 9,
              "M": 9, "N": 7, "O": 10, "Q": 10, "R": 16})
    return r0, RS_LAST

pr0, pr1 = build_scoring("Score_Prod", "Prod", "SCORE_PROD  —  SKU-grain placement score (Production)")
cr0, cr1 = build_scoring("Score_CVAL", "NonProd", "SCORE_CVAL  —  SKU-grain placement score (CVAL / NonProd)")
dr0, dr1 = build_scoring("Score_DR", "DR", "SCORE_DR  —  SKU-grain placement score (Disaster Recovery)")

# ==================================================================== Result
res = wb.create_sheet("Result"); res.sheet_view.showGridLines = False
res["A1"] = "RESULT  —  Multi-SKU placement recommendation (What-If, Phase 2)"; res["A1"].font = H1; res.merge_cells("A1:I1")
# summary panel (rows 3-7)
summary_rows = [
    ("Customer ID",          "=Request!B5"),
    ("Geography",            "=Request!B4"),
    ("Active SKU lines",     f"=Request!B{RQ_ACT}"),
    ("Total requested cores",f"=Request!B{RQ_TOT}"),
    ("",                     ""),
]
for idx, (lbl, val) in enumerate(summary_rows, start=3):
    res.cell(idx, 1, lbl).font = BOLD; res.cell(idx, 1).border = BORDER
    res.cell(idx, 2, val).border = BORDER; res.cell(idx, 2).alignment = CTR

res["A9"] = "RECOMMENDED PLACEMENT (per environment — region satisfies ALL active SKU lines)"; res["A9"].font = H2; res["A9"].fill = SUBFILL; res.merge_cells("A9:D9")
hdr(res, 10, ["Environment", "Region", "PS", "Readiness (RDY-002)"])
env_sheets = [("Prod", "Score_Prod"), ("CVAL", "Score_CVAL"), ("DR", "Score_DR")]
r = 11
for envlbl, sh in env_sheets:
    res.cell(r, 1, envlbl).font = BOLD; res.cell(r, 1).border = BORDER
    res.cell(r, 2, f"='{sh}'!R2").border = BORDER; res.cell(r, 2).alignment = CTR
    res.cell(r, 3, f"='{sh}'!R3").border = BORDER; res.cell(r, 3).alignment = CTR
    res.cell(r, 4, f"='{sh}'!R4").border = BORDER; res.cell(r, 4).alignment = CTR; res.cell(r, 4).fill = BLUE
    r += 1
res.cell(15, 1, "Overall Readiness").font = BOLD; res.cell(15, 1).border = BORDER
res.cell(15, 2, '=IF(B11="NONE ELIGIBLE","QUOTA_DEFICIT / NEEDS ATTENTION (Prod)",'
                'IF(B12="NONE ELIGIBLE","CAPACITY_UNAVAILABLE (CVAL)",'
                'IF(B13="NONE ELIGIBLE","READY_WITH_RISK (no DR region)","READY")))')
res.cell(15, 2).border = BORDER; res.cell(15, 2).alignment = LEFT; res.cell(15, 2).fill = ORANGE; res.cell(15, 2).font = BOLD
res.merge_cells("B15:D15")

# ranked candidate table (Prod) — updated to new column refs (N=Rank, M=PS, H=Readiness)
res["F9"] = "RANKED PROD CANDIDATES (all active SKU lines satisfiable)"; res["F9"].font = H2; res["F9"].fill = SUBFILL; res.merge_cells("F9:I9")
hdr(res, 10, ["Rank", "Region", "PS", "Readiness"], startcol=6)
for k in range(1, 9):
    rr = 10 + k
    res.cell(rr, 6, k).border = BORDER; res.cell(rr, 6).alignment = CTR
    res.cell(rr, 7, f'=IFERROR(INDEX(Score_Prod!$A${pr0}:$A${pr1},MATCH({k},Score_Prod!$N${pr0}:$N${pr1},0)),"")').border = BORDER
    res.cell(rr, 8, f'=IFERROR(INDEX(Score_Prod!$M${pr0}:$M${pr1},MATCH({k},Score_Prod!$N${pr0}:$N${pr1},0)),"")').border = BORDER
    res.cell(rr, 9, f'=IFERROR(INDEX(Score_Prod!$H${pr0}:$H${pr1},MATCH({k},Score_Prod!$N${pr0}:$N${pr1},0)),"")').border = BORDER
    for cc in (7, 8, 9):
        res.cell(rr, cc).alignment = CTR
setw(res, {"A": 22, "B": 20, "C": 10, "D": 24, "E": 3, "F": 6, "G": 20, "H": 10, "I": 22})

# ==================================================================== ReadMe
rm = wb.create_sheet("ReadMe"); rm.sheet_view.showGridLines = False
def g(row, text, style=None, fill=None):
    c = rm.cell(row, 1, text)
    if style: c.font = style
    if fill: c.fill = fill
    c.alignment = WRAP; rm.merge_cells(start_row=row, start_column=1, end_row=row, end_column=10)
lines = [
 ("ACRME SKU-LEVEL PLACEMENT WHAT-IF  —  PHASE 2 (Multi-SKU deployment scoring)", H1, None),
 ("", None, None),
 ("WHAT THIS IS", H2, SUBFILL),
 ("A DIFFERENT what-if from the region-selection model (Phase 1). That model scores capacity/quota as ONE blended number per region.", None, None),
 ("This model scores placement at SKU grain for a MULTI-SKU deployment: enter up to 8 SKU lines (SKU + VM count each).", None, None),
 ("A candidate region is Eligible only when EVERY active SKU line has GROUP AVAIL >= Line Cores (Meets-All = 1).", None, None),
 ("Score components are aggregated across lines using MIN (bottleneck-SKU drives the score).", None, None),
 ("", None, None),
 ("HOW TO USE", H2, SUBFILL),
 ("1. Open the Request sheet. Fill yellow cells:", None, None),
 ("   - B4: Geography (US or EU).  B5: Customer ID.", None, None),
 ("   - Rows 8-15: For each SKU line, select SKU (col B dropdown) and enter VM count (col C).", None, None),
 ("   - vCPU/inst (col D), Line Cores (col E), and Quota Family (col F) are derived automatically.", None, None),
 ("   - Leave a row blank (B and C empty) to deactivate that line. At least 1 active line required.", None, None),
 ("2. (Optional) tune Policy weights/thresholds (yellow). Weights must sum to 1.00 (check cell B7).", None, None),
 ("3. Read Result: recommended Prod/CVAL/DR region for the deployment + ranked Prod candidates + readiness.", None, None),
 ("", None, None),
 ("SCORING (per candidate region, per environment)", H2, SUBFILL),
 ("Eligible = InGeo=1 AND Meets-All=1 AND Readiness is READY or READY_WITH_RISK.", None, None),
 ("Meets-All = MIN across active lines of: 1 if GROUP_AVAIL(line) >= Line_Cores(line), else 0.", None, None),
 ("PS = w_alpha * alpha_c + w_beta * beta_c + w_eps * eps_c   (only for eligible candidates).", None, None),
 ("  alpha_c = MAX(0, MIN(1 - Line_Cores/GAVAIL) across active lines)   [bottleneck line drives score]", None, None),
 ("  beta_c  = MAX(0, MIN(quota-avail / quota-limit) across active lines)", None, None),
 ("  eps_c   = MAX(0, MIN(reserved-free / reserved) across active lines)", None, None),
 ("  GAVAIL per line = MIN(reserved-free for that SKU in this env, quota-avail for its family).", None, None),
 ("Readiness (RDY-002) hierarchy: NO_REQUEST -> RESERVATION_DEFICIT -> QUOTA_DEFICIT -> CAPACITY_DEFICIT -> READY_WITH_RISK -> READY.", None, None),
 ("  NO_REQUEST: no active SKU lines.  RESERVATION_DEFICIT: any line has reserved-free=0.", None, None),
 ("  QUOTA_DEFICIT: any line's family has quota-avail=0.  CAPACITY_DEFICIT: Meets-All=0 (GAVAIL < Line Cores for some line).", None, None),
 ("  READY_WITH_RISK: Meets-All=1 but MIN(alpha) < risk_threshold (Policy!B10).  READY: all checks pass.", None, None),
 ("", None, None),
 ("RULINGS BAKED IN (from Phase 1)", H2, SUBFILL),
 ("- ONE pooled quota group per region+family across Prod+NonProd+DR (QUA-004).", None, None),
 ("- ENV-003 hard separation applies to CAPACITY reservations only; quota pooled (separate planes).", None, None),
 ("- Quota hoarded to a single pool, distributed on demand (QUA-003).", None, None),
 ("- DR = 30% bootstrap of Prod (ENV-005), not a full duplicate.", None, None),
 ("", None, None),
 ("SCOPE / LIMITATIONS", H2, SUBFILL),
 ("- Read-only feasibility. Does NOT modify the v2.4 baseline or the Phase 1 workbook.", None, WARNFILL),
 ("- SKU dropdown is constrained to the ACRME catalogue; new SKUs require updating the builder.", None, WARNFILL),
 ("- CRG scope is regional (crg-...-reg); per-AZ CRGs (CAP-023) are a later increment.", None, WARNFILL),
 ("- Freeze & logical lock (the LOCKED state + Allocation_Ledger) is Phase 3, not in this file.", None, WARNFILL),
 ("- SKU->family map is naming-derived; a canonical Azure family table would replace it.", None, WARNFILL),
]
for i, (t, st, fl) in enumerate(lines, start=1):
    g(i, t, st, fl)
rm.column_dimensions["A"].width = 120

# ==================================================================== order + save
order = ["ReadMe", "Request", "Policy", "SKU_Family_Map", "SKU_Catalogue",
         "Capacity_By_SKU", "Quota_Groups", "Score_Prod", "Score_CVAL", "Score_DR", "Result"]
wb._sheets.sort(key=lambda s: order.index(s.title) if s.title in order else 99)
wb.save(OUT)
print("Saved", OUT)
print("Sheets:", wb.sheetnames)
print("Capacity_By_SKU data rows:", CAP_LAST - HR, " Quota_Groups rows:", qr - HRq - 1)
