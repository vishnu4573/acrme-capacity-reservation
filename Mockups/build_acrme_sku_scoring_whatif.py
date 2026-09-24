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
 ("risk_factor  (READY_WITH_RISK if group_avail < requested x this)", 1.25, "B10"),
 ("min_buffer_floor (cores; buffer must stay >= this after placement)", 8, "B11"),
]
r = 10
for label, val, _ in thr:
    pol.cell(r, 1, label).border = BORDER
    c = pol.cell(r, 2, val); c.fill = INFILL; c.border = BORDER; c.alignment = CTR; r += 1
setw(pol, {"A": 58, "B": 12, "C": 4})

# ==================================================================== Request (inputs)
rq = wb.create_sheet("Request"); rq.sheet_view.showGridLines = False
rq["A1"] = "REQUEST  —  Customer placement request (edit yellow cells)"; rq["A1"].font = H1; rq.merge_cells("A1:D1")
rq["A2"] = "Phase 2 evaluates ONE SKU per run at SKU grain across the ACRME candidate regions for Prod / CVAL / DR."
rq["A2"].font = Font(italic=True, color="595959"); rq.merge_cells("A2:D2")

def rq_in(row, label, val, help_=""):
    rq.cell(row, 1, label).font = BOLD; rq.cell(row, 1).border = BORDER
    c = rq.cell(row, 2, val); c.fill = INFILL; c.border = BORDER; c.alignment = CTR
    if help_:
        rq.cell(row, 3, help_).font = Font(italic=True, color="595959")

def rq_out(row, label, formula):
    rq.cell(row, 1, label).font = BOLD; rq.cell(row, 1).border = BORDER
    c = rq.cell(row, 2, formula); c.border = BORDER; c.alignment = CTR; c.fill = RESTFILL

rq_in(4, "Geography", "US", "US or EU (candidate regions are filtered to this)")
rq_in(5, "Requested SKU", "Standard_E32ads_v5", "one of the SKU_Catalogue SKUs")
rq_in(6, "VM count", 6, "number of instances")
rq_in(7, "Customer ID", "CUST-0042", "")
rq_out(8, "Quota Family (derived)", "=VLOOKUP(B5,SKU_Family_Map!$A:$B,2,FALSE)")
rq_out(9, "vCPU / instance (derived)", "=VLOOKUP(B5,SKU_Catalogue!$A:$B,2,FALSE)")
rq_out(10, "Requested cores (VMs x vCPU)", "=B6*B9")
setw(rq, {"A": 30, "B": 22, "C": 46})
# dropdowns
dv_geo = DataValidation(type="list", formula1='"US,EU"', allow_blank=False); rq.add_data_validation(dv_geo); dv_geo.add(rq["B4"])
sku_list = ",".join([s for (s, v, f) in PHASE1_SKUS])
dv_sku = DataValidation(type="list", formula1=f'"{sku_list}"', allow_blank=False); rq.add_data_validation(dv_sku); dv_sku.add(rq["B5"])

# ==================================================================== scoring sheet builder
def build_scoring(sheet, env, title, exclude_regionmatch=False):
    """One scoring sheet per environment. Candidates = the 8 regions, evaluated for
    the REQUESTED SKU in this environment. Alpha reads per-SKU GROUP AVAIL."""
    ws = wb.create_sheet(sheet); ws.sheet_view.showGridLines = False
    ws["A1"] = title; ws["A1"].font = H1; ws.merge_cells("A1:V1")
    ws["A2"] = ("Alpha (availability fit) reads per-SKU GROUP AVAIL = MIN(reserved-free, family quota-avail) for the requested SKU. "
                "Eligible = in-geography AND group_avail >= requested cores AND readiness not a deficit.")
    ws["A2"].font = Font(italic=True, color="595959"); ws.merge_cells("A2:V2")
    heads = ["Region", "Geography", "Env", "Req SKU", "Family", "vCPU/inst", "Req Cores",
             "Reserved", "Reserved-Free", "Family Q-Limit", "Family Q-Avail", "GROUP AVAIL",
             "InGeo", "Meets-Cap", "Readiness (RDY-002)", "Eligible",
             "alpha_c", "beta_c", "eps_c", "PS", "Rank", "Binding"]
    HRs = 3
    hdr(ws, HRs, heads)
    r0 = HRs + 1
    for i, (rn, rid, g, mk) in enumerate(PHASE1_REGIONS):
        r = r0 + i
        # keyed lookups into Capacity_By_SKU for (region, env, requested SKU)
        key = f'Capacity_By_SKU!$A:$A,$A{r},Capacity_By_SKU!$C:$C,"{env}",Capacity_By_SKU!$D:$D,Request!$B$5'
        vals = {
            1: rn, 2: g, 3: env, 4: "=Request!$B$5", 5: "=Request!$B$8",
            6: "=Request!$B$9", 7: "=Request!$B$10",
            8:  f'=SUMIFS(Capacity_By_SKU!$J:$J,{key})',   # Reserved
            9:  f'=SUMIFS(Capacity_By_SKU!$K:$K,{key})',   # Reserved-Free
            10: f'=SUMIFS(Quota_Groups!$E:$E,Quota_Groups!$B:$B,$A{r},Quota_Groups!$D:$D,$E{r})',  # Family Q-Limit
            11: f'=SUMIFS(Quota_Groups!$G:$G,Quota_Groups!$B:$B,$A{r},Quota_Groups!$D:$D,$E{r})',  # Family Q-Avail
            12: f'=MIN(I{r},K{r})',                        # GROUP AVAIL (MIN)
            13: f'=IF(B{r}=Request!$B$4,1,0)',             # InGeo
            14: f'=IF(L{r}>=G{r},1,0)',                    # Meets-Cap
            15: (f'=IF(I{r}<=0,"RESERVATION_DEFICIT",IF(K{r}<=0,"QUOTA_DEFICIT",'
                 f'IF(L{r}<G{r},IF(I{r}<=K{r},"RESERVATION_DEFICIT","QUOTA_DEFICIT"),'
                 f'IF(L{r}<G{r}*Policy!$B$10,"READY_WITH_RISK","READY"))))'),
            16: f'=IF(AND(M{r}=1,N{r}=1),1,0)',            # Eligible
            # score components (only meaningful when eligible)
            17: f'=IF(P{r}=1,IFERROR(1-G{r}/L{r},0),0)',                       # alpha_c: headroom cushion left after placement (higher=safer, discriminates)
            18: f'=IF(P{r}=1,IFERROR(K{r}/MAX(J{r},1),0),0)',                   # beta_c: quota headroom ratio
            19: f'=IF(P{r}=1,IFERROR(I{r}/MAX(H{r},1),0),0)',                   # eps_c: buffer safety
            20: f'=IF(P{r}=1,ROUND(Policy!$B$4*Q{r}+Policy!$B$5*R{r}+Policy!$B$6*S{r},4),"")',  # PS
        }
        for c, val in vals.items():
            cell = ws.cell(r, c, val); cell.border = BORDER
            if c not in (1, 2, 3, 4, 5, 15): cell.alignment = CTR
        ws.cell(r, 12).fill = ORANGE; ws.cell(r, 12).font = BOLD
        # Rank (dense rank among eligible PS, higher = rank1)
        ws.cell(r, 21, f'=IF(P{r}=1,SUMPRODUCT(($P${r0}:$P${r0+len(PHASE1_REGIONS)-1}=1)*($T${r0}:$T${r0+len(PHASE1_REGIONS)-1}>T{r}))+1,"")').border = BORDER
        ws.cell(r, 21).alignment = CTR
        ws.cell(r, 22, f'=IF(I{r}<=K{r},"CAPACITY","QUOTA")').border = BORDER
        ws.cell(r, 22).alignment = CTR
        # readiness colour
        ws.cell(r, 20).fill = SUBFILL
    RS_LAST = r0 + len(PHASE1_REGIONS) - 1
    # top result cells (row 1 area on the right)
    ws["X1"] = "TOP PICK"; ws["X1"].font = H2
    ws["X2"] = "Region"; ws["Y2"] = f'=IFERROR(INDEX($A${r0}:$A${RS_LAST},MATCH(1,$U${r0}:$U${RS_LAST},0)),"NONE ELIGIBLE")'
    ws["X3"] = "PS";     ws["Y3"] = f'=IFERROR(INDEX($T${r0}:$T${RS_LAST},MATCH(1,$U${r0}:$U${RS_LAST},0)),"")'
    ws["X4"] = "Readiness"; ws["Y4"] = f'=IFERROR(INDEX($O${r0}:$O${RS_LAST},MATCH(1,$U${r0}:$U${RS_LAST},0)),"")'
    for cc in ("X2", "X3", "X4"): ws[cc].font = BOLD
    for cc in ("Y2", "Y3", "Y4"): ws[cc].alignment = CTR; ws[cc].fill = GREENF
    setw(ws, {"A": 16, "B": 10, "C": 8, "D": 20, "E": 9, "F": 9, "G": 9, "H": 9, "I": 12, "J": 12,
              "K": 12, "L": 12, "M": 7, "N": 9, "O": 20, "P": 8, "Q": 8, "R": 8, "S": 8, "T": 8,
              "U": 6, "V": 9, "X": 10, "Y": 16})
    return r0, RS_LAST

pr0, pr1 = build_scoring("Score_Prod", "Prod", "SCORE_PROD  —  SKU-grain placement score (Production)")
cr0, cr1 = build_scoring("Score_CVAL", "NonProd", "SCORE_CVAL  —  SKU-grain placement score (CVAL / NonProd)")
dr0, dr1 = build_scoring("Score_DR", "DR", "SCORE_DR  —  SKU-grain placement score (Disaster Recovery)")

# ==================================================================== Result
res = wb.create_sheet("Result"); res.sheet_view.showGridLines = False
res["A1"] = "RESULT  —  SKU-grain placement recommendation (What-If, Phase 2)"; res["A1"].font = H1; res.merge_cells("A1:H1")
res["A3"] = "Customer ID"; res["B3"] = "=Request!B7"
res["A4"] = "Geography";   res["B4"] = "=Request!B4"
res["A5"] = "Requested SKU"; res["B5"] = "=Request!B5"
res["A6"] = "Quota Family"; res["B6"] = "=Request!B8"
res["A7"] = "Requested cores"; res["B7"] = "=Request!B10"
for rr in range(3, 8):
    res.cell(rr, 1).font = BOLD; res.cell(rr, 1).border = BORDER
    res.cell(rr, 2).border = BORDER; res.cell(rr, 2).alignment = CTR

res["A9"] = "RECOMMENDED PLACEMENT (per environment, for the requested SKU)"; res["A9"].font = H2; res["A9"].fill = SUBFILL; res.merge_cells("A9:D9")
hdr(res, 10, ["Environment", "Region", "PS", "Readiness (RDY-002)"])
env_sheets = [("Prod", "Score_Prod"), ("CVAL", "Score_CVAL"), ("DR", "Score_DR")]
r = 11
for envlbl, sh in env_sheets:
    res.cell(r, 1, envlbl).font = BOLD; res.cell(r, 1).border = BORDER
    res.cell(r, 2, f"='{sh}'!Y2").border = BORDER; res.cell(r, 2).alignment = CTR
    res.cell(r, 3, f"='{sh}'!Y3").border = BORDER; res.cell(r, 3).alignment = CTR
    res.cell(r, 4, f"='{sh}'!Y4").border = BORDER; res.cell(r, 4).alignment = CTR; res.cell(r, 4).fill = BLUE
    r += 1
res.cell(15, 1, "Overall Readiness").font = BOLD; res.cell(15, 1).border = BORDER
res.cell(15, 2, '=IF(B11="NONE ELIGIBLE","QUOTA_DEFICIT / NEEDS ATTENTION (Prod)",'
                'IF(B12="NONE ELIGIBLE","CAPACITY_UNAVAILABLE (CVAL)",'
                'IF(B13="NONE ELIGIBLE","READY_WITH_RISK (no DR region)","READY")))')
res.cell(15, 2).border = BORDER; res.cell(15, 2).alignment = LEFT; res.cell(15, 2).fill = ORANGE; res.cell(15, 2).font = BOLD
res.merge_cells("B15:D15")

# ranked candidate table (Prod)
res["F9"] = "RANKED PROD CANDIDATES (for requested SKU)"; res["F9"].font = H2; res["F9"].fill = SUBFILL; res.merge_cells("F9:I9")
hdr(res, 10, ["Rank", "Region", "PS", "Readiness"], startcol=6)
for k in range(1, 9):
    rr = 10 + k
    res.cell(rr, 6, k).border = BORDER; res.cell(rr, 6).alignment = CTR
    res.cell(rr, 7, f'=IFERROR(INDEX(Score_Prod!$A${pr0}:$A${pr1},MATCH({k},Score_Prod!$U${pr0}:$U${pr1},0)),"")').border = BORDER
    res.cell(rr, 8, f'=IFERROR(INDEX(Score_Prod!$T${pr0}:$T${pr1},MATCH({k},Score_Prod!$U${pr0}:$U${pr1},0)),"")').border = BORDER
    res.cell(rr, 9, f'=IFERROR(INDEX(Score_Prod!$O${pr0}:$O${pr1},MATCH({k},Score_Prod!$U${pr0}:$U${pr1},0)),"")').border = BORDER
    for cc in (7, 8, 9):
        res.cell(rr, cc).alignment = CTR
setw(res, {"A": 18, "B": 20, "C": 10, "D": 24, "E": 3, "F": 6, "G": 20, "H": 10, "I": 22})

# ==================================================================== ReadMe
rm = wb.create_sheet("ReadMe"); rm.sheet_view.showGridLines = False
def g(row, text, style=None, fill=None):
    c = rm.cell(row, 1, text)
    if style: c.font = style
    if fill: c.fill = fill
    c.alignment = WRAP; rm.merge_cells(start_row=row, start_column=1, end_row=row, end_column=10)
lines = [
 ("ACRME SKU-LEVEL PLACEMENT WHAT-IF  —  PHASE 2 (SKU-grain scoring)", H1, None),
 ("", None, None),
 ("WHAT THIS IS", H2, SUBFILL),
 ("A DIFFERENT what-if from the region-selection model. That model scored capacity/quota as ONE blended number per region.", None, None),
 ("This model scores placement at SKU grain: it evaluates ONE requested SKU across the candidate regions and picks Prod / CVAL / DR.", None, None),
 ("The availability term (alpha) reads per-SKU GROUP AVAIL = MIN(reserved-free for the SKU, quota available for its family).", None, None),
 ("", None, None),
 ("HOW TO USE", H2, SUBFILL),
 ("1. Edit the Request sheet (yellow): Geography, Requested SKU, VM count, Customer ID.", None, None),
 ("2. (Optional) tune Policy weights/thresholds (yellow). Weights must sum to 1.00 (check cell B7).", None, None),
 ("3. Read Result: recommended Prod/CVAL/DR region for that SKU + ranked Prod candidates + readiness.", None, None),
 ("", None, None),
 ("SCORING (per candidate region, for the requested SKU in each environment)", H2, SUBFILL),
 ("Eligible = in-geography AND GROUP AVAIL >= requested cores AND readiness is not a deficit.", None, None),
 ("PS = w_alpha*alpha + w_beta*beta + w_eps*eps   (only for eligible candidates).", None, None),
 ("  alpha (availability fit) = 1 - requested cores / GROUP AVAIL  = headroom cushion left after placement (higher = safer)  <- the SKU-grain change", None, None),
 ("  beta  (quota headroom)   = family quota-available / family quota-limit", None, None),
 ("  eps   (buffer safety)    = reserved-free / reserved", None, None),
 ("Readiness (RDY-002): RESERVATION_DEFICIT, QUOTA_DEFICIT, READY_WITH_RISK, or READY.", None, None),
 ("", None, None),
 ("RULINGS BAKED IN (from Phase 1)", H2, SUBFILL),
 ("- ONE pooled quota group per region+family across Prod+NonProd+DR (QUA-004).", None, None),
 ("- ENV-003 hard separation applies to CAPACITY reservations only; quota pooled (separate planes).", None, None),
 ("- Quota hoarded to a single pool, distributed on demand (QUA-003).", None, None),
 ("- DR = 30% bootstrap of Prod (ENV-005), not a full duplicate.", None, None),
 ("", None, None),
 ("SCOPE / LIMITATIONS", H2, SUBFILL),
 ("- Read-only feasibility. Does NOT modify the v2.4 baseline or the Phase 1 workbook.", None, WARNFILL),
 ("- One SKU per run (SKU grain). Multi-SKU workloads = run per SKU.", None, WARNFILL),
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
