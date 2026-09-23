#!/usr/bin/env python3
"""ACRME Region-Selection WHAT-IF on the ACTUAL ACRME region catalogue.

Change vs the first what-if: candidate regions are now the AUTHORITATIVE ACRME
in-scope catalogue (baseline v2.4 Section 6), NOT the regions that happen to
appear in the usage files. The real usage is DISTRIBUTED onto those catalogue
regions (geography totals preserved; per-region weight ∝ real usage where a
catalogue region exists in the data, floor share where it does not; regions in
the data that are not ACRME regions — East US, Central India, South Africa North
— fold into their geography total).

Per user instruction for THIS mockup: every region is a STANDARD (engine-
selectable) region — so East US 2 / North Europe / West Europe are NO LONGER
restricted — EXCEPT the Middle East, whose regions are RESTRICTED
(production-only; not auto-selected unless explicitly supplied as the Prod
region, per the Section 6 'Restricted deployment regions' definition).
"""
import openpyxl, math
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.chart import BarChart, Reference
from openpyxl.utils import get_column_letter
from collections import defaultdict

SRC  = "/home/ubuntu/Uploads/SKU_USage (1).xlsx"
SUBS = "/home/ubuntu/Uploads/sku_usage_prod_v1.xlsx"
OUT  = "/home/ubuntu/acrme-capacity-reservation/Mockups/acrme_region_selection_whatif_acrme_regions.xlsx"

# ---------------------------------------------------------------- read usage
GEO_OF_DATA = {
 'East US 2':'US','Central US':'US','East US':'US','West US 3':'US',
 'West Europe':'EU','North Europe':'EU','Sweden Central':'EU','Switzerland North':'EU',
 'Australia East':'Australia','Australia Southeast':'Australia',
 'Southeast Asia':'Asia Pacific','East Asia':'Asia Pacific','Central India':'Asia Pacific',
 'South Africa North':'Middle East',
}
def is_prod(t):
    t=(t or '').strip().lower(); return t=='prod' and 'non' not in t
wb0=openpyxl.load_workbook(SRC,data_only=True); ws0=wb0['Sheet1']
rp=defaultdict(float); rn=defaultdict(float); raks=defaultdict(float); rtot=defaultdict(float)
for r in range(2,ws0.max_row+1):
    env=ws0.cell(r,1).value; reg=ws0.cell(r,2).value; rtype=ws0.cell(r,3).value; cores=ws0.cell(r,9).value or 0
    if reg not in GEO_OF_DATA: continue
    if is_prod(env): rp[reg]+=cores
    else: rn[reg]+=cores
    rtot[reg]+=cores
    if rtype=='AKS': raks[reg]+=cores
# geography totals (fold ALL data regions, incl orphans, into their geography)
gp=defaultdict(float); gn=defaultdict(float); gtot=defaultdict(float)
for reg in rtot:
    g=GEO_OF_DATA[reg]; gp[g]+=rp[reg]; gn[g]+=rn[reg]; gtot[g]+=rtot[reg]
# unique subs per region
wbs=openpyxl.load_workbook(SUBS,data_only=True); wsr=wbs['By Region']
subs=dict()
for r in range(5,19):
    reg=wsr.cell(r,1).value; s=wsr.cell(r,2).value
    if reg: subs[reg]=s or 0

# ---------------------------------------------------------------- ACRME catalogue (baseline v2.4 Section 6)
# geo, region_name, region_id, az, model, dr_scope, class, mock_subs_if_absent
CATALOGUE = [
 ('US','West US 3','westus3',3,'3-region','US','Standard',None),
 ('US','Central US','centralus',3,'3-region','US','Standard',None),
 ('US','Canada Central','canadacentral',3,'3-region','US','Standard',10),   # absent in data -> mock subs
 ('US','East US 2','eastus2',3,'3-region','US','Standard',None),            # now STANDARD (was restricted)
 ('EU','Switzerland North','switzerlandnorth',3,'2-region','EU','Standard',None),
 ('EU','Sweden Central','swedencentral',3,'2-region','EU','Standard',None),
 ('EU','North Europe','northeurope',3,'2-region','EU','Standard',None),     # now STANDARD (was restricted)
 ('EU','West Europe','westeurope',3,'2-region','EU','Standard',None),       # now STANDARD (was restricted)
 ('Australia','Australia East','australiaeast',3,'2-region','Australia','Standard',None),
 ('Australia','Australia Southeast','australiasoutheast',2,'2-region','Australia','Standard',None),
 ('Asia Pacific','East Asia','eastasia',3,'2-region','Asia Pacific','Standard',None),
 ('Asia Pacific','Southeast Asia','southeastasia',3,'2-region','Asia Pacific','Standard',None),
 ('Middle East','Saudi Arabia East','saudiarbiaeast',3,'cross-geo','EU','Restricted',4),  # RESTRICTED — FUTURE REGION (not yet GA; Microsoft target Q4 2026, Eastern Province)
 ('Middle East','UAE North','uaenorth',3,'cross-geo','EU','Restricted',4),                 # RESTRICTED
]
GEO_MODEL={'US':('3-region','US'),'EU':('2-region','EU'),'Australia':('2-region','Australia'),
           'Asia Pacific':('2-region','Asia Pacific'),'Middle East':('cross-geo','EU')}

# Middle East has ~no real usage -> mock geography pool so it can be exercised (flagged)
ME_MOCK_PROD=2400.0; ME_MOCK_NP=3400.0
gp['Middle East']=ME_MOCK_PROD; gn['Middle East']=ME_MOCK_NP; gtot['Middle East']=ME_MOCK_PROD+ME_MOCK_NP

# distribution weights per catalogue region within its geography
regions_by_geo=defaultdict(list)
for row in CATALOGUE: regions_by_geo[row[0]].append(row)
def raw_weight(geo,name):
    present=rtot.get(name,0)
    if present>0: return present
    return max(50.0, 0.015*gtot[geo])   # floor share for catalogue regions absent from data

def rup(x,step=2): return int(math.ceil(max(x,0)/step)*step)

REGIONS=[]; USAGE_ROWS=[]
for geo in ['US','EU','Australia','Asia Pacific','Middle East']:
    grs=regions_by_geo[geo]
    n=len(grs)
    weights={row[1]:raw_weight(geo,row[1]) for row in grs}
    wsum=sum(weights.values()) or 1.0
    for (g,name,rid,az,model,drscope,cls,mocksub) in grs:
        w=weights[name]/wsum
        p_alloc=gp[geo]*w          # mock-distributed current Prod alloc
        n_alloc=gn[geo]*w          # mock-distributed current NP alloc
        # balanced planning pool = geography total distributed EVENLY across its regions
        p_bal=gp[geo]/n; np_bal=gn[geo]/n
        # Reserved capacity = the LARGER of the even 'balanced target' and the region's own
        # distributed allocation, plus an 8% headroom margin. This keeps every region's headroom
        # POSITIVE but VARYING: a low-usage region (alloc << even share) shows large free capacity
        # and scores high; a high-usage region (alloc >> even share) shows only the thin 8% margin
        # and scores low. The weightage model therefore selects by SCORE, not by gate elimination.
        p_res=max(p_bal, p_alloc)*1.08; np_res=max(np_bal, n_alloc)*1.08
        prodRes=rup(p_res); prodQL=rup(p_res*1.5); prodQU=rup(p_alloc); pAll=rup(p_alloc)
        npRes=rup(np_res); npQL=rup(np_res*1.5); npQU=rup(n_alloc); npAll=rup(n_alloc)
        npEF=max(0,npRes-npAll)
        if geo=='Middle East':
            drRes=0; drFree=0; drCov=0.0
        else:
            drRes=rup(p_bal*0.5); drFree=rup(p_bal*0.5*0.85); drCov=0.60
        cust=int(subs.get(name, mocksub if mocksub is not None else 4))
        aksv=int(raks.get(name,0))
        REGIONS.append([rid,name,geo,model,az, prodRes,pAll,prodQL,prodQU,
                        npRes,npAll,npEF,npQL,npQU, drRes,drFree,drCov, cust, cls])
        origin=("real" if rtot.get(name,0)>0
                else ("SYNTHETIC — FUTURE REGION (not yet GA; Microsoft target Q4 2026, Eastern Province; no real usage data exists)" if name=='Saudi Arabia East'
                      else ("SYNTHETIC (Middle East — no real usage; GA region absent from ACRME source data)" if geo=='Middle East'
                            else "mock (catalogue region absent from data)")))
        USAGE_ROWS.append([name,geo,cls, rup(p_alloc),rup(n_alloc),rup(p_alloc+n_alloc), aksv, cust, origin])

NR=len(REGIONS); FIRST,LAST=4,3+NR

# ---------------------------------------------------------------- styles
H1=Font(bold=True,size=16,color="1F3864"); H2=Font(bold=True,size=12,color="1F3864")
BOLD=Font(bold=True); WHITEB=Font(bold=True,color="FFFFFF")
HEADFILL=PatternFill("solid",fgColor="1F3864"); SUBFILL=PatternFill("solid",fgColor="D9E1F2")
INFILL=PatternFill("solid",fgColor="FFF2CC"); WARNFILL=PatternFill("solid",fgColor="FCE4D6")
SYNFILL=PatternFill("solid",fgColor="FDE9D9"); RESTFILL=PatternFill("solid",fgColor="E2EFDA")
thin=Side(style="thin",color="BFBFBF"); BORDER=Border(left=thin,right=thin,top=thin,bottom=thin)
CTR=Alignment(horizontal="center",vertical="center"); WRAP=Alignment(wrap_text=True,vertical="top")
green=PatternFill("solid",fgColor="C6EFCE"); red=PatternFill("solid",fgColor="FFC7CE")
grey=PatternFill("solid",fgColor="F2F2F2")

wb=Workbook()

# ============================================================ How_To_Use
ws=wb.active; ws.title="How_To_Use"; ws.sheet_view.showGridLines=False
ws.column_dimensions["A"].width=3; ws.column_dimensions["B"].width=112
def guide(r,text,style=None,fill=None):
    c=ws.cell(row=r,column=2,value=text)
    if style:c.font=style
    if fill:c.fill=fill
    c.alignment=WRAP
guide(1,"ACRME Region Selection — WHAT-IF on the ACRME Region Catalogue (Formula-Only)",H1)
guide(2,"Candidate regions = authoritative ACRME catalogue (baseline v2.4 Section 6). Usage distributed from the real SKU-usage files.",Font(italic=True,color="808080"))
rows=[
 ("",None),
 ("WHAT THIS WORKBOOK DOES",H2,SUBFILL),
 ("This what-if runs the ACRME weightage model over the ACTUAL ACRME in-scope regions (not the regions that happen to "
  "appear in the usage export). Your real usage is DISTRIBUTED onto those catalogue regions, and the engine scores every "
  "region so you can see where new workload should land. All results are live formulas — change any input and everything "
  "recalculates. No macros.",None),
 ("",None),
 ("REGION CLASSIFICATION FOR THIS MOCKUP (your instruction)",H2,SUBFILL),
 ("• ALL regions are STANDARD (engine-selectable). This deliberately promotes East US 2, North Europe and West Europe — "
  "normally 'Restricted / exception-only' in the baseline catalogue — to Standard so they compete for placement.",None),
 ("• EXCEPTION: the Middle East regions (Saudi Arabia East, UAE North) are RESTRICTED — production-only, and NOT "
  "auto-selected by the engine unless you explicitly supply one as the Prod region on Setup (cell B8). This matches the "
  "baseline 'Restricted deployment regions' definition. So for a Middle East run you must name a Prod region; DR still "
  "auto-selects cross-geo in a Standard Europe region.",None,RESTFILL),
 ("",None),
 ("HOW THE DISTRIBUTION WORKS",H2,SUBFILL),
 ("• Each geography's REAL total usage (Prod / Non-Prod cores) is preserved and spread across that geography's ACRME "
  "catalogue regions. Weight ∝ real usage where a catalogue region exists in the data; catalogue regions absent from the "
  "data (e.g. Canada Central) get a small floor share. Data regions that are NOT ACRME regions (East US, Central India, "
  "South Africa North) fold into their geography total.",None),
 ("• Current Alloc / Q-Used = this distributed real usage. Reserved / Quota = the LARGER of the geography's even "
  "'balanced target' share and the region's own distributed allocation, plus an 8% headroom margin. This keeps every "
  "region's headroom positive but VARYING: an under-used region (e.g. West US 3, Canada Central) shows large free "
  "capacity and scores high; a heavily-used region (e.g. East US 2) shows only the thin 8% margin and scores low — so "
  "the weightage model selects by SCORE rather than by gate elimination.",None),
 ("",None),
 ("SHEET MAP",H2,SUBFILL),
 ("1. How_To_Use — this guide.",None),
 ("2. Usage_Source — the REAL aggregated usage by region from the uploaded files (read-only provenance), with the "
  "geography roll-up and which regions fold in.",None),
 ("3. Setup — pick Geography, then add one or more SKU line items (SKU + VM count) for the SAME Customer ID & Geography/Region. "
  "vCPU/VM auto-fills from the SKU catalogue and Requested vCPU (total) auto-sums across all lines. Optional customer-supplied "
  "Prod region (required for Middle East), Customer ID.",None),
 ("4. Policy — the five weights (sum=1.0), total_customers mode, DR bootstrap / target, min headroom floors.",None),
 ("5. Capacity_Usage — the ACRME catalogue regions with distributed usage + a Class column (Standard / Restricted). "
  "Yellow = editable; grey = computed; green Class cell = Restricted (Middle East).",None),
 ("6. HC_Gate — HC-3 / HC-6 / HC-7 pass/fail and eligibility per region.",None),
 ("7. Scoring_Prod / 8. Scoring_CVAL / 9. Scoring_DR — PS component breakdown, AutoSelect flag and winners.",None),
 ("10. Result — final placement (Prod / CVAL / DR), readiness, DR sizing (max-not-sum), plus a RANKED CANDIDATE "
  "REGIONS table (Rank 1 = highest PS) across all catalogue regions for each mode.",None),
 ("",None),
 ("THE FORMULAS (from the baseline)",H2,SUBFILL),
 ("Clamp(x)=MIN(MAX(x,0),1). PS_Prod=α·(npEffFree/prodRes)+β·(prodQHeadroom/prodQLimit)+γ·(1−cust/total)+δ·drCov+ε·(az/3).",None),
 ("PS_NonProd=α·(npEffFree/npRes)+β·(npQHeadroom/npQLimit)+γ·(1−cust/total)+δ·(npEffFree/npRes)+ε·(az/3).",None),
 ("PS_DR=α·(drFree/drRes)+β·(npQHeadroom/npQLimit)+γ·(1−cust/total)+δ·(drCov/target)+ε·(az/3).",None),
 ("Auto-select rule: a region is an engine candidate only if InScope AND Eligible AND (Class=Standard OR it is the "
  "customer-supplied Prod region). Restricted (Middle East) regions therefore need an explicit Prod region.",None),
 ("DR sizing = MAX-NOT-SUM (A.6 / DR-017): DR req = MAX over source regions of (customers × vCPU).",None),
 ("",None),
 ("KNOWN GAPS / ASSUMPTIONS (surfaced, not hidden)",H2,SUBFILL),
 ("• Metric = Total Cores. Prod = environment tag 'Prod'; everything else = Non-Prod.",None,WARNFILL),
 ("• Reserved & Quota are DERIVED planning figures (max of even-share and actual alloc, +8% margin), not billed reservations — edit to model reality.",None,WARNFILL),
 ("• Middle East has ~no real usage in the data — its two regions use a flagged SYNTHETIC pool so the geography can be "
  "exercised. Saudi Arabia East is a FUTURE REGION (not yet GA; Microsoft target Q4 2026, Eastern Province; no real "
  "usage data will exist until launch). UAE North is GA but absent from ACRME source data. "
  "Japan East (Asia Pacific) is 'pending' in the catalogue and is excluded.",None,SYNFILL),
 ("• total_customers is undefined in baseline v2.4 — mode selector on Policy (Live/Constant/Manual). γ values illustrative.",None,WARNFILL),
 ("• PS_NonProd δ duplicates its α (baseline design-of-record). DR bootstrap / target are configurable placeholders.",None,WARNFILL),
]
r=3
for it in rows:
    guide(r,it[0],it[1], it[2] if len(it)>2 else None); r+=1

# ============================================================ Usage_Source
us=wb.create_sheet("Usage_Source"); us.sheet_view.showGridLines=False
us["A1"]="CURRENT USAGE — SOURCE SNAPSHOT (real, from uploaded files)"; us["A1"].font=H1
us.merge_cells("A1:I1")
note=us.cell(row=2,column=1,value="Real aggregation from SKU_USage (1).xlsx (Total Cores). Prod = tag 'Prod'; all other tags = Non-Prod. This is provenance; the engine reads the distributed Capacity_Usage sheet. ACRME catalogue regions absent from source data use SYNTHETIC capacity — see the footer section below. NOTE: Saudi Arabia East is a FUTURE REGION (not yet GA; Microsoft target Q4 2026, Eastern Province) — no real usage data exists; capacity figures are entirely SYNTHETIC.")
note.font=Font(italic=True,color="808080"); us.merge_cells("A2:I2")
uh=["Region (as in data)","Geography","Class in this mockup","Prod Cores","Non-Prod Cores","Total Cores","AKS Cores","Unique Subs","ACRME catalogue region?"]
for j,h in enumerate(uh):
    c=us.cell(row=3,column=1+j,value=h); c.font=WHITEB; c.fill=HEADFILL; c.alignment=CTR; c.border=BORDER
ACRME_NAMES={row[1] for row in CATALOGUE}
data_regions=sorted(rtot.keys(), key=lambda k:-rtot[k])
ur=4
for name in data_regions:
    geo=GEO_OF_DATA[name]
    incat = name in ACRME_NAMES
    cls = 'Restricted' if geo=='Middle East' else ('Standard' if incat else '—')
    origin = 'ACRME region' if incat else 'folds into geography (not an ACRME region)'
    vals=[name,geo,cls,int(rp.get(name,0)),int(rn.get(name,0)),int(rtot.get(name,0)),int(raks.get(name,0)),int(subs.get(name,0)),origin]
    for j,v in enumerate(vals):
        c=us.cell(row=ur,column=1+j,value=v); c.border=BORDER; c.alignment=CTR
        if j in (3,4,5,6): c.number_format="#,##0"
        if not incat and j==8: c.fill=WARNFILL
    ur+=1
tr=ur
us.cell(row=tr,column=1,value="TOTAL").font=BOLD
for col,letter in ((4,'D'),(5,'E'),(6,'F'),(7,'G')):
    us.cell(row=tr,column=col,value=f"=SUM({letter}4:{letter}{tr-1})").number_format="#,##0"
for c in range(1,10): us.cell(row=tr,column=c).font=BOLD
widths=[20,14,18,11,14,12,11,11,34]
for j,w in enumerate(widths): us.column_dimensions[get_column_letter(1+j)].width=w
us.freeze_panes="A4"
# ---- Usage_Source footer: ACRME catalogue regions with no real source data ----
absent_cat=[(g,name,cls,
             "FUTURE REGION — not yet GA (Microsoft target Q4 2026, Eastern Province); no real usage data; capacity figures SYNTHETIC"
             if name=="Saudi Arabia East"
             else ("absent from source data; mock subscription count used; capacity figures SYNTHETIC"
                   if name=="Canada Central"
                   else "GA region — absent from ACRME source data; capacity figures SYNTHETIC"))
            for (g,name,rid,az,model,drscope,cls,mocksub) in CATALOGUE if rtot.get(name,0)==0]
if absent_cat:
    af=tr+2
    hc2=us.cell(row=af,column=1,value="ACRME CATALOGUE REGIONS — ABSENT FROM SOURCE DATA (capacity figures are SYNTHETIC)")
    hc2.font=Font(bold=True,color="C00000"); us.merge_cells(f"A{af}:I{af}")
    af+=1
    for (g2,nm2,cls2,nt2) in absent_cat:
        us.cell(row=af,column=1,value=nm2).border=BORDER; us.cell(row=af,column=1).font=BOLD
        us.cell(row=af,column=2,value=g2).border=BORDER; us.cell(row=af,column=2).alignment=CTR
        cc=us.cell(row=af,column=3,value=cls2); cc.border=BORDER; cc.alignment=CTR
        cc.fill=(RESTFILL if cls2=='Restricted' else PatternFill("solid",fgColor="FDE9D9"))
        nc=us.cell(row=af,column=4,value=nt2)
        nc.font=Font(italic=True,color="C00000"); nc.alignment=WRAP
        us.merge_cells(f"D{af}:I{af}")
        for col in range(4,10): us.cell(row=af,column=col).border=BORDER
        us.row_dimensions[af].height=30; af+=1

# ============================================================ Setup
sp=wb.create_sheet("Setup"); sp.sheet_view.showGridLines=False
for col,w in {"A":28,"B":22,"C":11,"D":11,"E":3,"F":14,"G":9,"H":3,"I":14,"J":10,"K":14}.items():
    sp.column_dimensions[col].width=w
sp["A1"]="SETUP — Customer & Workload"; sp["A1"].font=H1
def lbl(ws_,cell,txt): ws_[cell]=txt; ws_[cell].font=BOLD
def inp(ws_,cell,val):
    ws_[cell]=val; ws_[cell].fill=INFILL; ws_[cell].border=BORDER; ws_[cell].alignment=CTR
def out(ws_,cell):
    ws_[cell].border=BORDER; ws_[cell].alignment=CTR

# --- SKU line-item table geometry (one Customer ID, one Geography/Region, MANY SKUs) ---
LINE_TOP=15; NLINES=8; LINE_BOT=LINE_TOP+NLINES-1   # rows 15..22

# --- Curated SKU catalogue (name -> vCPU). vCPU = the integer in the Azure size name for
#     standard (non-constrained) sizes — verified against Microsoft Learn for the Eadsv5/v6,
#     Dadsv5/Dasv5 and Fsv2 families. Selection = the highest-usage standard SKUs in the real
#     SKU_USage data (constrained-core and GPU/specialty SKUs excluded to keep vCPU unambiguous). ---
skus=[("E64ads_v6",64),("E64ads_v5",64),("E48ads_v5",48),("E32ads_v6",32),("E32ads_v5",32),
      ("E20ads_v5",20),("E16ads_v6",16),("E16ads_v5",16),("E8ads_v5",8),("E4ads_v5",4),("E2ads_v5",2),
      ("D64ads_v5",64),("D32ads_v5",32),("D16ads_v5",16),("D16as_v5",16),("D8ads_v5",8),("D8as_v5",8),
      ("D4ads_v5",4),("D4as_v5",4),("D2ads_v5",2),("D2as_v5",2),
      ("F32s_v2",32),("F16s_v2",16),("F8s_v2",8),("F4s_v2",4),("F2s_v2",2)]
SKU_TOP=3; SKU_BOT=SKU_TOP+len(skus)-1               # F/G rows 3..28
GEO_TOP=3; GEO_BOT=GEO_TOP+4                          # I/J/K rows 3..7
skurange=f"$F${SKU_TOP}:$G${SKU_BOT}"; skulist=f"$F${SKU_TOP}:$F${SKU_BOT}"
georange=f"$I${GEO_TOP}:$K${GEO_BOT}"

# --- Top single-value block (downstream contract: B3, B7, B8, B9, B10, B11 addresses fixed) ---
lbl(sp,"A3","Geography");          inp(sp,"B3","US")
lbl(sp,"A4","Total VMs (all SKUs)");   sp["B4"]=f"=SUM(B{LINE_TOP}:B{LINE_BOT})"; out(sp,"B4")
lbl(sp,"A5","SKU line count");         sp["B5"]=f"=COUNTA(A{LINE_TOP}:A{LINE_BOT})"; out(sp,"B5")
lbl(sp,"A6","Workload SKUs");           sp["B6"]=f'=_xlfn.TEXTJOIN(", ",TRUE,A{LINE_TOP}:A{LINE_BOT})'; out(sp,"B6")
lbl(sp,"A7","Requested vCPU (total)");  sp["B7"]=f"=SUM(D{LINE_TOP}:D{LINE_BOT})"; sp["B7"].font=BOLD; out(sp,"B7")
lbl(sp,"A8","Prod region (req. for Middle East)"); inp(sp,"B8","")
lbl(sp,"A9","Customer ID");        inp(sp,"B9","CUST-0042")
lbl(sp,"A10","Distribution model");sp["B10"]=f"=VLOOKUP(B3,{georange},2,FALSE)"; out(sp,"B10")
lbl(sp,"A11","DR scope geography");sp["B11"]=f"=VLOOKUP(B3,{georange},3,FALSE)"; out(sp,"B11")

# --- SKU line-item table: multiple SKUs for the SAME customer & region ---
sp.cell(row=13,column=1,value="WORKLOAD — SKU LINE ITEMS  (one Customer ID, one Geography/Region; add as many SKUs as needed)").font=H2
sp.merge_cells("A13:D13"); sp["A13"].fill=SUBFILL
lihdr=["SKU","VM count","vCPU/VM","Line vCPU"]
for j,h in enumerate(lihdr):
    c=sp.cell(row=14,column=1+j,value=h); c.font=WHITEB; c.fill=HEADFILL; c.alignment=CTR; c.border=BORDER
prefill=[("E16ads_v5",2),("D8ads_v5",2)]   # demo: 2×16 + 2×8 = 48 vCPU total (same as prior default)
for i in range(NLINES):
    r=LINE_TOP+i
    sku_v = prefill[i][0] if i<len(prefill) else None
    cnt_v = prefill[i][1] if i<len(prefill) else None
    ca=sp.cell(row=r,column=1,value=sku_v); ca.fill=INFILL; ca.border=BORDER; ca.alignment=CTR
    cb=sp.cell(row=r,column=2,value=cnt_v); cb.fill=INFILL; cb.border=BORDER; cb.alignment=CTR
    sp.cell(row=r,column=3,value=f'=IF($A{r}="","",VLOOKUP($A{r},{skurange},2,FALSE))'); out(sp,f"C{r}")
    sp.cell(row=r,column=4,value=f'=IF($A{r}="","",$B{r}*$C{r})'); out(sp,f"D{r}")
sp.cell(row=LINE_BOT+1,column=3,value="TOTAL").font=BOLD
sp.cell(row=LINE_BOT+1,column=4,value=f"=SUM(D{LINE_TOP}:D{LINE_BOT})").font=BOLD
out(sp,f"D{LINE_BOT+1}")

# --- Lookup tables (do not edit) ---
sp["F1"]="Lookup tables (do not edit)"; sp["F1"].font=Font(italic=True,color="808080")
sp["F2"]="SKU"; sp["G2"]="vCPU/VM"
for c in ("F2","G2"): sp[c].font=WHITEB; sp[c].fill=HEADFILL; sp[c].alignment=CTR
for i,(s,v) in enumerate(skus):
    sp.cell(row=SKU_TOP+i,column=6,value=s).border=BORDER
    sp.cell(row=SKU_TOP+i,column=7,value=v).border=BORDER
sp["I2"]="Geography"; sp["J2"]="Model"; sp["K2"]="DR Scope Geo"
for c in ("I2","J2","K2"): sp[c].font=WHITEB; sp[c].fill=HEADFILL; sp[c].alignment=CTR
geos=[("US","3-region","US"),("EU","2-region","EU"),("Australia","2-region","Australia"),
      ("Asia Pacific","2-region","Asia Pacific"),("Middle East","cross-geo","EU")]
for i,(g,m,d) in enumerate(geos):
    sp.cell(row=GEO_TOP+i,column=9,value=g).border=BORDER
    sp.cell(row=GEO_TOP+i,column=10,value=m).border=BORDER
    sp.cell(row=GEO_TOP+i,column=11,value=d).border=BORDER

dv_geo=DataValidation(type="list",formula1='"US,EU,Australia,Asia Pacific,Middle East"',allow_blank=False)
dv_sku=DataValidation(type="list",formula1=f"={skulist}",allow_blank=True)
dv_reg=DataValidation(type="list",formula1=f"=Capacity_Usage!$B${FIRST}:$B${LAST}",allow_blank=True)
sp.add_data_validation(dv_geo); dv_geo.add(sp["B3"])
sp.add_data_validation(dv_reg); dv_reg.add(sp["B8"])
sp.add_data_validation(dv_sku); dv_sku.add(f"A{LINE_TOP}:A{LINE_BOT}")

# ============================================================ Policy
pol=wb.create_sheet("Policy"); pol.sheet_view.showGridLines=False
for col,w in {"A":34,"B":14,"C":3,"D":16,"E":12}.items():
    pol.column_dimensions[col].width=w
pol["A1"]="POLICY — Weights & Parameters"; pol["A1"].font=H1
weights=[("alpha (α) — Capacity headroom",0.30),("beta (β) — Quota headroom",0.20),
         ("gamma (γ) — Distribution fairness",0.25),("delta (δ) — DR readiness",0.15),
         ("epsilon (ε) — Zone diversity",0.10)]
for i,(n,v) in enumerate(weights):
    lbl(pol,f"A{2+i}",n); inp(pol,f"B{2+i}",v)
lbl(pol,"A7","Weight sum"); pol["B7"]="=SUM(B2:B6)"; pol["B7"].font=BOLD; pol["B7"].alignment=CTR
lbl(pol,"A8","Validation"); pol["B8"]='=IF(ABS(B7-1)<=0.001,"VALID","INVALID — must sum to 1.0")'; pol["B8"].alignment=CTR
lbl(pol,"A10","total_customers mode (1=Live 2=Constant 3=Manual)"); inp(pol,"B10",1)
lbl(pol,"A11","Manual total_customers"); inp(pol,"B11",300)
lbl(pol,"A13","DR bootstrap qty (vCPU)"); inp(pol,"B13",40)
lbl(pol,"A14","DR coverage target"); inp(pol,"B14",0.80)
lbl(pol,"A15","Min Prod headroom (vCPU)"); inp(pol,"B15",20)
lbl(pol,"A16","Min NonProd headroom (vCPU)"); inp(pol,"B16",20)
lbl(pol,"A17","Min DR headroom (vCPU)"); inp(pol,"B17",16)
pol["D10"]="Geography"; pol["E10"]="Constant"
for c in ("D10","E10"): pol[c].font=WHITEB; pol[c].fill=HEADFILL; pol[c].alignment=CTR
consts=[("US",150),("EU",90),("Australia",40),("Asia Pacific",50),("Middle East",10)]
for i,(g,v) in enumerate(consts):
    pol.cell(row=11+i,column=4,value=g).border=BORDER
    pol.cell(row=11+i,column=5,value=v).border=BORDER
pol.conditional_formatting.add("B8",CellIsRule(operator="equal",formula=['"VALID"'],fill=green))
pol.conditional_formatting.add("B8",FormulaRule(formula=['LEFT(B8,7)="INVALID"'],fill=red))

# ============================================================ Capacity_Usage (Class column = V/22)
cu=wb.create_sheet("Capacity_Usage"); cu.sheet_view.showGridLines=False
headers=["Region ID","Region Name","Geography","Model","AZ",
         "Prod Reserved","Prod Alloc","Prod Free","Prod Q-Limit","Prod Q-Used","Prod Q-Headroom",
         "NP Reserved","NP Alloc","NP Eff-Free","NP Q-Limit","NP Q-Used","NP Q-Headroom",
         "DR Reserved","DR Free","DR Coverage","Cust Count","Class"]
cu["A1"]="ACRME CATALOGUE — CAPACITY & USAGE (real usage distributed across the actual ACRME regions)"; cu["A1"].font=H1
cu.merge_cells("A1:V1")
note=cu.cell(row=2,column=1,value="Alloc / Q-Used = real usage distributed onto ACRME regions (geography totals preserved). Reserved / Quota = max(even balanced-share, region alloc) + 8% margin (positive but varying headroom). Class: Standard = engine-selectable; Restricted (Middle East) = production-only, explicit Prod region required. Yellow = editable; grey = computed.")
note.font=Font(italic=True,color="808080"); cu.merge_cells("A2:V2")
HROW=3
for j,h in enumerate(headers):
    c=cu.cell(row=HROW,column=1+j,value=h); c.font=WHITEB; c.fill=HEADFILL; c.alignment=CTR; c.border=BORDER
COMPUTED={8,11,17}
dstart=HROW+1
for i,row in enumerate(REGIONS):
    xr=dstart+i
    rid,name,geo,model,az, pRes,pAll,pQL,pQU, npRes,npAll,npEF,npQL,npQU, drRes,drFree,drCov,cust,cls=row
    vals={1:rid,2:name,3:geo,4:model,5:az,
          6:pRes,7:pAll,8:f"=F{xr}-G{xr}",9:pQL,10:pQU,11:f"=I{xr}-J{xr}",
          12:npRes,13:npAll,14:npEF,15:npQL,16:npQU,17:f"=O{xr}-P{xr}",
          18:drRes,19:drFree,20:drCov,21:cust,22:cls}
    restricted=(cls=='Restricted')
    for col in range(1,23):
        c=cu.cell(row=xr,column=col,value=vals[col]); c.border=BORDER; c.alignment=CTR
        if col in COMPUTED: c.fill=grey
        elif col==22: c.fill=(RESTFILL if restricted else grey)
        elif col>=5: c.fill=(SYNFILL if restricted else INFILL)
        if col in (6,7,9,10,12,13,14,15,16): c.number_format="#,##0"
cu.freeze_panes="F4"
for col in range(1,23):
    cu.column_dimensions[get_column_letter(col)].width=13 if col==2 else (11 if col>=6 else 12)
cu.column_dimensions["B"].width=20; cu.column_dimensions["V"].width=12

# ============================================================ HC_Gate
hc=wb.create_sheet("HC_Gate"); hc.sheet_view.showGridLines=False
hc["A1"]="HARD CONSTRAINT GATE"; hc["A1"].font=H1
hh=["Region","Geography","Class","Req vCPU","HC-3 Prod","HC-3 NonProd","HC-3 DR","HC-6 DR Floor","HC-7 DR Integ",
    "Eligible Prod","Eligible NonProd","Eligible DR"]
HR=3
for j,h in enumerate(hh):
    c=hc.cell(row=HR,column=1+j,value=h); c.font=WHITEB; c.fill=HEADFILL; c.alignment=CTR; c.border=BORDER
for i in range(NR):
    xr=HR+1+i; cur=FIRST+i
    hc.cell(row=xr,column=1,value=f"=Capacity_Usage!B{cur}")
    hc.cell(row=xr,column=2,value=f"=Capacity_Usage!C{cur}")
    hc.cell(row=xr,column=3,value=f"=Capacity_Usage!V{cur}")
    hc.cell(row=xr,column=4,value="=Setup!$B$7")
    hc.cell(row=xr,column=5,value=f'=IF(AND(Capacity_Usage!K{cur}>=Setup!$B$7,Capacity_Usage!K{cur}-Setup!$B$7>=Policy!$B$15),"PASS","FAIL")')
    hc.cell(row=xr,column=6,value=f'=IF(AND(Capacity_Usage!N{cur}>=Setup!$B$7,Capacity_Usage!Q{cur}-Setup!$B$7>=Policy!$B$16),"PASS","FAIL")')
    hc.cell(row=xr,column=7,value=f'=IF(Capacity_Usage!S{cur}>=Policy!$B$13,"PASS","FAIL")')
    hc.cell(row=xr,column=8,value=f'=IF(Capacity_Usage!S{cur}+Capacity_Usage!N{cur}>=Policy!$B$13,"PASS","FAIL")')
    hc.cell(row=xr,column=9,value=f'=IF(Capacity_Usage!P{cur}+Setup!$B$7<=Capacity_Usage!O{cur}-Policy!$B$13,"PASS","FAIL")')
    hc.cell(row=xr,column=10,value=f'=IF(E{xr}="PASS","YES","NO")')
    hc.cell(row=xr,column=11,value=f'=IF(AND(F{xr}="PASS",I{xr}="PASS"),"YES","NO")')
    hc.cell(row=xr,column=12,value=f'=IF(AND(G{xr}="PASS",H{xr}="PASS"),"YES","NO")')
    for col in range(1,13):
        cc=hc.cell(row=xr,column=col); cc.border=BORDER; cc.alignment=CTR
last=HR+NR
for colrange in (f"E{HR+1}:I{last}",):
    hc.conditional_formatting.add(colrange,CellIsRule(operator="equal",formula=['"PASS"'],fill=green))
    hc.conditional_formatting.add(colrange,CellIsRule(operator="equal",formula=['"FAIL"'],fill=red))
for colrange in (f"J{HR+1}:L{last}",):
    hc.conditional_formatting.add(colrange,CellIsRule(operator="equal",formula=['"YES"'],fill=green))
    hc.conditional_formatting.add(colrange,CellIsRule(operator="equal",formula=['"NO"'],fill=red))
hc.conditional_formatting.add(f"C{HR+1}:C{last}",CellIsRule(operator="equal",formula=['"Restricted"'],fill=RESTFILL))
for col in range(1,13): hc.column_dimensions[get_column_letter(col)].width=14
hc.column_dimensions["A"].width=20

# ============================================================ Scoring builder
def total_cust_formula(cur):
    return (f'=IF(Policy!$B$10=1,SUMIFS(Capacity_Usage!$U${FIRST}:$U${LAST},Capacity_Usage!$C${FIRST}:$C${LAST},'
            f'Capacity_Usage!C{cur}),IF(Policy!$B$10=2,VLOOKUP(Capacity_Usage!C{cur},Policy!$D$11:$E$15,2,FALSE),Policy!$B$11))')

def build_scoring(name,alpha_num,alpha_den,beta_num,beta_den,delta_expr,elig_col,scope_ref,exclude_prod,title):
    s=wb.create_sheet(name); s.sheet_view.showGridLines=False
    s["A1"]=title; s["A1"].font=H1
    cols=["Region","Geography","InScope","Eligible","AutoSel","total_cust",
          "α_raw","α_c","β_raw","β_c","γ_raw","γ_c","δ_raw","δ_c","ε_raw","ε_c","PS","Candidate","Rank"]
    HRr=3
    for j,h in enumerate(cols):
        c=s.cell(row=HRr,column=1+j,value=h); c.font=WHITEB; c.fill=HEADFILL; c.alignment=CTR; c.border=BORDER
    for i in range(NR):
        xr=HRr+1+i; cur=FIRST+i
        s.cell(row=xr,column=1,value=f"=Capacity_Usage!B{cur}")
        s.cell(row=xr,column=2,value=f"=Capacity_Usage!C{cur}")
        s.cell(row=xr,column=3,value=f"=IF(Capacity_Usage!C{cur}={scope_ref},1,0)")
        s.cell(row=xr,column=4,value=f'=IF(HC_Gate!{elig_col}{xr}="YES",1,0)')
        # AutoSel: Standard OR (this is the customer-supplied Prod region)
        s.cell(row=xr,column=5,value=f'=IF(OR(Capacity_Usage!V{cur}="Standard",Capacity_Usage!B{cur}=Setup!$B$8),1,0)')
        s.cell(row=xr,column=6,value=total_cust_formula(cur))
        s.cell(row=xr,column=7,value=f"=IFERROR(Capacity_Usage!{alpha_num}{cur}/Capacity_Usage!{alpha_den}{cur},0)")
        s.cell(row=xr,column=8,value=f"=MIN(MAX(G{xr},0),1)")
        s.cell(row=xr,column=9,value=f"=IFERROR(Capacity_Usage!{beta_num}{cur}/Capacity_Usage!{beta_den}{cur},0)")
        s.cell(row=xr,column=10,value=f"=MIN(MAX(I{xr},0),1)")
        s.cell(row=xr,column=11,value=f"=IFERROR(1-Capacity_Usage!U{cur}/F{xr},0)")
        s.cell(row=xr,column=12,value=f"=MIN(MAX(K{xr},0),1)")
        s.cell(row=xr,column=13,value="=IFERROR("+delta_expr.format(cur=cur,xr=xr)[1:]+",0)")
        s.cell(row=xr,column=14,value=f"=MIN(MAX(M{xr},0),1)")
        s.cell(row=xr,column=15,value=f"=Capacity_Usage!E{cur}/3")
        s.cell(row=xr,column=16,value=f"=MIN(MAX(O{xr},0),1)")
        s.cell(row=xr,column=17,value=f"=Policy!$B$2*H{xr}+Policy!$B$3*J{xr}+Policy!$B$4*L{xr}+Policy!$B$5*N{xr}+Policy!$B$6*P{xr}")
        if exclude_prod:
            s.cell(row=xr,column=18,value=f'=IF(AND(C{xr}=1,D{xr}=1,E{xr}=1,A{xr}<>Scoring_Prod!$U$3),Q{xr},-1)')
        else:
            s.cell(row=xr,column=18,value=f"=IF(AND(C{xr}=1,D{xr}=1,E{xr}=1),Q{xr},-1)")
        # Rank (col 19 = S): 1 = highest candidate PS; blank for non-candidates (Candidate<0)
        s.cell(row=xr,column=19,value=f'=IF(R{xr}<0,"",COUNTIF($R${HRr+1}:$R${HRr+NR},">"&R{xr})+1)')
        for col in range(1,20):
            cc=s.cell(row=xr,column=col); cc.border=BORDER; cc.alignment=CTR
            if col in range(7,18): cc.number_format="0.000"
    for col in range(1,20): s.column_dimensions[get_column_letter(col)].width=9
    s.column_dimensions["A"].width=20; s.column_dimensions["B"].width=13
    return s,HRr

# winner column is now U (21) because we added AutoSel col (candidate is col 18=R)
sPr,HRr=build_scoring("Scoring_Prod","N","F","K","I","=Capacity_Usage!T{cur}","J","Setup!$B$3",False,
                      "PS_Prod — Production Placement Score")
top=HRr+1; bot=HRr+NR
CAND="R"  # candidate column letter (col 18)
sPr["T1"]="PROD WINNER"; sPr["T1"].font=H2; sPr["T1"].fill=SUBFILL
sPr["T2"]="Selection mode"; sPr["U2"]='=IF(Setup!$B$8="","Engine argmax","Customer-supplied")'
sPr["T3"]="Region"
sPr["U3"]=(f'=IF(Setup!$B$8<>"",Setup!$B$8,IF(MAX({CAND}{top}:{CAND}{bot})<0,"NONE ELIGIBLE",'
           f'INDEX(A{top}:A{bot},MATCH(MAX({CAND}{top}:{CAND}{bot}),{CAND}{top}:{CAND}{bot},0))))')
sPr["T4"]="Score"
sPr["U4"]=(f'=IF(Setup!$B$8<>"",INDEX(Q{top}:Q{bot},MATCH(Setup!$B$8,A{top}:A{bot},0)),'
           f'IF(MAX({CAND}{top}:{CAND}{bot})<0,"",MAX({CAND}{top}:{CAND}{bot})))')
for c in ("T2","T3","T4"): sPr[c].font=BOLD
sPr["U4"].number_format="0.000"
sPr.column_dimensions["T"].width=16; sPr.column_dimensions["U"].width=18

sCv,_=build_scoring("Scoring_CVAL","N","L","Q","O","=Capacity_Usage!N{cur}/Capacity_Usage!L{cur}","K","Setup!$B$3",True,
                    "PS_NonProd — CVAL Placement Score  (δ duplicates α — known design gap)")
sCv["T1"]="CVAL WINNER"; sCv["T1"].font=H2; sCv["T1"].fill=SUBFILL
sCv["T2"]="Region"
sCv["U2"]=(f'=IF(Setup!$B$3="Middle East",Scoring_Prod!$U$3,IF(MAX({CAND}{top}:{CAND}{bot})<0,"NONE ELIGIBLE",'
           f'INDEX(A{top}:A{bot},MATCH(MAX({CAND}{top}:{CAND}{bot}),{CAND}{top}:{CAND}{bot},0))))')
sCv["T3"]="Score"
sCv["U3"]=(f'=IF(Setup!$B$3="Middle East",Scoring_Prod!$U$4,IF(MAX({CAND}{top}:{CAND}{bot})<0,"",MAX({CAND}{top}:{CAND}{bot})))')
for c in ("T2","T3"): sCv[c].font=BOLD
sCv["U3"].number_format="0.000"
sCv.column_dimensions["T"].width=16; sCv.column_dimensions["U"].width=18

sDr,_=build_scoring("Scoring_DR","S","R","Q","O","=Capacity_Usage!T{cur}/Policy!$B$14","L","Setup!$B$11",True,
                    "PS_DR — DR Placement Score  (Middle East scores EU regions cross-geo)")
sDr["T1"]="DR WINNER"; sDr["T1"].font=H2; sDr["T1"].fill=SUBFILL
sDr["T2"]="Region"
sDr["U2"]=(f'=IF(Setup!$B$10="2-region",Scoring_CVAL!$U$2,IF(MAX({CAND}{top}:{CAND}{bot})<0,"NONE ELIGIBLE",'
           f'INDEX(A{top}:A{bot},MATCH(MAX({CAND}{top}:{CAND}{bot}),{CAND}{top}:{CAND}{bot},0))))')
sDr["T3"]="Score"
sDr["U3"]=(f'=IF(Setup!$B$10="2-region",Scoring_CVAL!$U$3,IF(MAX({CAND}{top}:{CAND}{bot})<0,"",MAX({CAND}{top}:{CAND}{bot})))')
for c in ("T2","T3"): sDr[c].font=BOLD
sDr["U3"].number_format="0.000"
sDr.column_dimensions["T"].width=16; sDr.column_dimensions["U"].width=18

# ============================================================ Result
rs=wb.create_sheet("Result"); rs.sheet_view.showGridLines=False
for col,w in {"A":26,"B":28,"C":14,"D":4,"E":30,"F":16}.items():
    rs.column_dimensions[col].width=w
rs["A1"]="RESULT — Region Selection (What-If, ACRME catalogue)"; rs["A1"].font=H1
def rlbl(cell,t): rs[cell]=t; rs[cell].font=BOLD
def rout(cell,f): rs[cell]=f; rs[cell].border=BORDER; rs[cell].alignment=CTR
rlbl("A3","Customer ID"); rout("B3","=Setup!B9")
rlbl("A4","Geography");   rout("B4","=Setup!B3")
rlbl("A5","Workload SKUs");rout("B5","=Setup!B6")
rlbl("A6","Requested vCPU");rout("B6","=Setup!B7")
rs["A8"]="Environment"; rs["B8"]="Region"; rs["C8"]="Score"
for c in ("A8","B8","C8"): rs[c].font=WHITEB; rs[c].fill=HEADFILL; rs[c].alignment=CTR; rs[c].border=BORDER
rlbl("A9","Prod");  rout("B9","=Scoring_Prod!U3"); rout("C9","=Scoring_Prod!U4")
rlbl("A10","CVAL"); rout("B10","=Scoring_CVAL!U2"); rout("C10","=Scoring_CVAL!U3")
rlbl("A11","DR");   rout("B11","=Scoring_DR!U2");  rout("C11","=Scoring_DR!U3")
for c in ("C9","C10","C11"): rs[c].number_format="0.000"
rlbl("A13","Readiness State")
rs["B13"]=('=IF(B9="NONE ELIGIBLE","QUOTA_DEFICIT / NEEDS EXPLICIT REGION (Prod)",'
           'IF(B10="NONE ELIGIBLE","CAPACITY_UNAVAILABLE (CVAL)",'
           'IF(B11="NONE ELIGIBLE","READY_WITH_RISK (no DR region)","READY")))')
rs["B13"].font=BOLD; rs["B13"].border=BORDER; rs["B13"].alignment=CTR
rs.conditional_formatting.add("B13",CellIsRule(operator="equal",formula=['"READY"'],fill=green))
rs.conditional_formatting.add("B13",FormulaRule(formula=['ISNUMBER(SEARCH("DEFICIT",B13))'],fill=red))
rs.conditional_formatting.add("B13",FormulaRule(formula=['ISNUMBER(SEARCH("UNAVAILABLE",B13))'],fill=red))
rs.conditional_formatting.add("B13",FormulaRule(formula=['ISNUMBER(SEARCH("RISK",B13))'],fill=PatternFill("solid",fgColor="FFEB9C")))
rlbl("A15","Policy version"); rout("B15",'="whatif-catalogue-v1  (weights "&TEXT(Policy!B7,"0.00")&" — "&Policy!B8&")"')
rs["E3"]="DR SIZING (max-not-sum, A.6 / DR-017)"; rs["E3"].font=H2; rs["E3"].fill=SUBFILL
rs.merge_cells("E3:F3")
rlbl("E5","DR region"); rout("F5","=B11")
rlbl("E6","Max source customers"); rout("F6",f"=SUMPRODUCT(MAX((Capacity_Usage!$C${FIRST}:$C${LAST}=Setup!$B$11)*Capacity_Usage!$U${FIRST}:$U${LAST}))")
rlbl("E7","× Requested vCPU"); rout("F7","=Setup!B7")
rlbl("E8","DR Requirement (max-not-sum)"); rout("F8","=F6*F7"); rs["F8"].font=BOLD
rlbl("E9","DR Reserved (region)"); rout("F9",f'=IFERROR(INDEX(Capacity_Usage!$R${FIRST}:$R${LAST},MATCH(B11,Capacity_Usage!$B${FIRST}:$B${LAST},0)),0)')
rlbl("E10","DR Gap"); rout("F10","=MAX(0,F8-F9)")
rs["E11"]="Note: illustrative — sources = regions in DR scope geography."; rs["E11"].font=Font(italic=True,color="808080",size=9)
rs.merge_cells("E11:F11")

# ---- RANKED CANDIDATE REGIONS across all catalogue regions (Rank 1 = highest PS) ----
for col,w in {"G":3,"H":6,"I":20,"J":9,"K":6,"L":20,"M":9,"N":6,"O":20,"P":9}.items():
    rs.column_dimensions[col].width=w
rs["H3"]=("RANKED CANDIDATE REGIONS  (Rank 1 = highest PS; blank = not a candidate for this mode)")
rs["H3"].font=H2; rs["H3"].fill=SUBFILL; rs.merge_cells("H3:P3")
# mode super-headers
rs["H4"]="Prod"; rs["K4"]="CVAL"; rs["N4"]="DR"
for c,mrng in (("H4","H4:J4"),("K4","K4:M4"),("N4","N4:P4")):
    rs[c].font=WHITEB; rs[c].fill=HEADFILL; rs[c].alignment=CTR; rs.merge_cells(mrng)
# column headers
subhdr={"H5":"Rank","I5":"Region","J5":"PS","K5":"Rank","L5":"Region","M5":"PS","N5":"Rank","O5":"Region","P5":"PS"}
for c,t in subhdr.items():
    rs[c]=t; rs[c].font=WHITEB; rs[c].fill=HEADFILL; rs[c].alignment=CTR; rs[c].border=BORDER
# one row per rank 1..NR; INDEX/MATCH the Rank column (S) in each Scoring sheet
RANK_TOP=6
for k in range(1,NR+1):
    r=RANK_TOP+k-1
    for (rankcol,regcol,pscol,sheet) in (("H","I","J","Scoring_Prod"),("K","L","M","Scoring_CVAL"),("N","O","P","Scoring_DR")):
        srng=f"{sheet}!$S${top}:$S${bot}"; arng=f"{sheet}!$A${top}:$A${bot}"; qrng=f"{sheet}!$Q${top}:$Q${bot}"
        rs[f"{rankcol}{r}"]=f'=IFERROR(IF(INDEX({srng},MATCH({k},{srng},0))="","",{k}),"")'
        rs[f"{regcol}{r}"]=f'=IFERROR(INDEX({arng},MATCH({k},{srng},0)),"")'
        rs[f"{pscol}{r}"]=f'=IFERROR(INDEX({qrng},MATCH({k},{srng},0)),"")'
        rs[f"{pscol}{r}"].number_format="0.000"
        for cc in (rankcol,regcol,pscol):
            rs[f"{cc}{r}"].border=BORDER; rs[f"{cc}{r}"].alignment=CTR

# charts
ch=BarChart(); ch.type="col"; ch.title="PS_Prod by ACRME Region"; ch.height=7.5; ch.width=18
data=Reference(sPr,min_col=17,min_row=HRr,max_row=bot)   # PS column = 17 (Q)
cats=Reference(sPr,min_col=1,min_row=top,max_row=bot)
ch.add_data(data,titles_from_data=True); ch.set_categories(cats); ch.legend=None
sPr.add_chart(ch,"T6")
ch2=BarChart(); ch2.type="col"; ch2.title="Chosen Placement Scores"; ch2.height=7.5; ch2.width=10
d2=Reference(rs,min_col=3,min_row=9,max_row=11); c2=Reference(rs,min_col=1,min_row=9,max_row=11)
ch2.add_data(d2); ch2.set_categories(c2); ch2.legend=None
rs.add_chart(ch2,"A18")
ch3=BarChart(); ch3.type="bar"; ch3.title="Current Total Cores by Region (real)"; ch3.height=10; ch3.width=16
d3=Reference(us,min_col=6,min_row=3,max_row=3+len(data_regions)-1)
c3=Reference(us,min_col=1,min_row=4,max_row=3+len(data_regions)-1)
ch3.add_data(d3,titles_from_data=True); ch3.set_categories(c3); ch3.legend=None
us.add_chart(ch3,"K3")


# ============================================================ Formula_Reference
fr=wb.create_sheet("Formula_Reference"); fr.sheet_view.showGridLines=False
fr.column_dimensions["A"].width=12; fr.column_dimensions["B"].width=30
fr.column_dimensions["C"].width=50; fr.column_dimensions["D"].width=10
fr.column_dimensions["E"].width=60; fr.column_dimensions["F"].width=35

fr["A1"]="PLACEMENT SCORING FORMULA REFERENCE"; fr["A1"].font=H1
fr.merge_cells("A1:F1")

# Introduction
fr["A3"]="This sheet explains the three placement scoring (PS) formulas used by the ACRME region-selection engine."
fr["A3"].font=Font(italic=True); fr.merge_cells("A3:F3")
fr["A4"]="Each formula evaluates candidate regions across five weighted components (α, β, γ, δ, ε) that sum to 1.0."
fr["A4"].font=Font(italic=True); fr.merge_cells("A4:F4")
fr["A5"]="All components are clamped to [0, 1] to prevent outliers from dominating the score."
fr["A5"].font=Font(italic=True); fr.merge_cells("A5:F5")

# PS_Prod Table
row=7
fr[f"A{row}"]="PS_Prod — PRODUCTION REGION SCORING"; fr[f"A{row}"].font=H2; fr[f"A{row}"].fill=HEADFILL
fr.merge_cells(f"A{row}:F{row}")
row+=1

headers_prod=[
    ("Component", "A"),
    ("What It Measures", "B"),
    ("Signal / Formula", "C"),
    ("Weight", "D"),
    ("Explanation", "E"),
    ("Excel Column References", "F")
]
for h, col in headers_prod:
    fr[f"{col}{row}"]=h; fr[f"{col}{row}"].font=WHITEB; fr[f"{col}{row}"].fill=HEADFILL
    fr[f"{col}{row}"].alignment=Alignment(horizontal="center", vertical="top", wrap_text=True)
    fr[f"{col}{row}"].border=BORDER

prod_components=[
    ("α",
     "Capacity headroom (forward-looking regional health)",
     "Clamp(nonprod_crg.effective_free / prod_crg.quantity)",
     "0.30",
     "Uses NonProd effective free capacity as a regional health indicator. A region with ample NonProd headroom signals overall capacity health, overflow capacity for Prod spikes, and readiness for future CVAL co-location (2-region model). This is NOT self-referential — it evaluates regional capacity resilience, not just Prod-specific capacity.",
     "Capacity_Usage: N (NP Eff-Free) ÷ F (Prod Reserved)\nScoring_Prod: G (α_raw), H (α_c)"),
    ("β",
     "Quota headroom (direct Prod capacity readiness)",
     "Clamp(prod_crg.quota_headroom / prod_crg.quota_limit)",
     "0.20",
     "Direct measure of Prod quota availability. High quota headroom means the region can accommodate the Prod workload without quota exhaustion. This complements α by providing a Prod-specific capacity signal while α measures regional health.",
     "Capacity_Usage: K (Prod Q-Headroom) ÷ I (Prod Q-Limit)\nScoring_Prod: I (β_raw), J (β_c)"),
    ("γ",
     "Distribution fairness (load balancing)",
     "Clamp(1 - prod_customer_count / total_customers)",
     "0.25",
     "Rewards regions with fewer existing Prod customers, promoting even distribution of workload across the geography. A region with lower customer count scores higher, preventing concentration in a single region. ⚠️ Note: total_customers is currently UNDEFINED in baseline v2.4 (scope and source unspecified).",
     "Capacity_Usage: U (Cust Count)\nScoring_Prod: F (total_cust for denominator), K (γ_raw), L (γ_c)\n⚠️ total_customers scope: geography-level (most likely) or global (pending clarification)"),
    ("δ",
     "DR readiness signal (destination DR coverage)",
     "Clamp(dr_crg.coverage_ratio)",
     "0.15",
     "Measures the region's existing DR coverage ratio — how much of its DR requirement is already met. A region with good DR coverage is more resilient and can potentially host additional DR workloads (multi-source DR hosting, DR-016).",
     "Capacity_Usage: T (DR Coverage)\nScoring_Prod: M (δ_raw), N (δ_c)"),
    ("ε",
     "Zone diversity (availability zone count)",
     "Clamp(az_count / 3)",
     "0.10",
     "Favors regions with more availability zones (max 3 in Azure). Higher zone count provides better fault isolation and distributes VMs more evenly (PLC-011 even zone-distribution target). A 3-AZ region scores 1.0; 2-AZ scores 0.67; 1-AZ scores 0.33.",
     "Capacity_Usage: E (AZ)\nScoring_Prod: O (ε_raw), P (ε_c)")
]

row+=1
for comp, measure, formula, weight, explanation, cols in prod_components:
    fr[f"A{row}"]=comp; fr[f"A{row}"].font=BOLD; fr[f"A{row}"].alignment=Alignment(horizontal="center", vertical="top")
    fr[f"B{row}"]=measure; fr[f"B{row}"].alignment=Alignment(vertical="top", wrap_text=True)
    fr[f"C{row}"]=formula; fr[f"C{row}"].font=Font(name="Courier New", size=9)
    fr[f"C{row}"].alignment=Alignment(vertical="top", wrap_text=True)
    fr[f"D{row}"]=weight; fr[f"D{row}"].alignment=Alignment(horizontal="center", vertical="top")
    fr[f"E{row}"]=explanation; fr[f"E{row}"].alignment=Alignment(vertical="top", wrap_text=True)
    fr[f"F{row}"]=cols; fr[f"F{row}"].font=Font(name="Courier New", size=8)
    fr[f"F{row}"].alignment=Alignment(vertical="top", wrap_text=True)
    for c in ("A","B","C","D","E","F"):
        fr[f"{c}{row}"].border=BORDER
    fr.row_dimensions[row].height=90
    row+=1

fr[f"A{row}"]="FINAL SCORE"; fr[f"A{row}"].font=BOLD; fr[f"A{row}"].fill=PatternFill("solid",fgColor="D9EAD3")
fr[f"A{row}"].alignment=Alignment(horizontal="center", vertical="center")
fr[f"B{row}"]="Weighted sum of all five components"
fr[f"C{row}"]="PS_Prod = 0.30×α + 0.20×β + 0.25×γ + 0.15×δ + 0.10×ε"
fr[f"C{row}"].font=Font(name="Courier New", size=10, bold=True)
fr[f"D{row}"]="1.00"; fr[f"D{row}"].font=BOLD; fr[f"D{row}"].alignment=Alignment(horizontal="center")
fr[f"E{row}"]="Range: [0, 1]. Highest score = best candidate. Winner = argmax(PS_Prod) over eligible Standard regions."
fr[f"F{row}"]="Scoring_Prod: Q (PS)"
fr[f"F{row}"].font=Font(name="Courier New", size=8)
for c in ("A","B","C","D","E","F"):
    fr[f"{c}{row}"].border=BORDER
    fr[f"{c}{row}"].fill=PatternFill("solid",fgColor="D9EAD3")
fr[f"C{row}"].alignment=Alignment(vertical="center", wrap_text=True)
fr[f"E{row}"].alignment=Alignment(vertical="top", wrap_text=True)
fr[f"F{row}"].alignment=Alignment(vertical="center", wrap_text=True)
fr.row_dimensions[row].height=50

# PS_NonProd Table
row+=3
fr[f"A{row}"]="PS_NonProd — CVAL (NON-PRODUCTION) REGION SCORING"; fr[f"A{row}"].font=H2; fr[f"A{row}"].fill=HEADFILL
fr.merge_cells(f"A{row}:F{row}")
row+=1

for h, col in headers_prod:
    fr[f"{col}{row}"]=h; fr[f"{col}{row}"].font=WHITEB; fr[f"{col}{row}"].fill=HEADFILL
    fr[f"{col}{row}"].alignment=Alignment(horizontal="center", vertical="top", wrap_text=True)
    fr[f"{col}{row}"].border=BORDER

nonprod_components=[
    ("α",
     "Capacity headroom (direct NonProd capacity)",
     "Clamp(nonprod_crg.effective_free / nonprod_crg.quantity)",
     "0.30",
     "Direct measure of NonProd effective free capacity. Unlike PS_Prod (which uses NonProd as a regional health signal), here we evaluate NonProd capacity directly for CVAL placement. High NonProd headroom = region can accommodate CVAL workload.",
     "Capacity_Usage: N (NP Eff-Free) ÷ L (NP Reserved)\nScoring_CVAL: G (α_raw), H (α_c)"),
    ("β",
     "Quota headroom (NonProd quota availability)",
     "Clamp(nonprod_crg.quota_headroom / nonprod_crg.quota_limit)",
     "0.20",
     "NonProd quota headroom. Ensures the region has sufficient NonProd quota to accommodate the CVAL workload without hitting quota limits.",
     "Capacity_Usage: Q (NP Q-Headroom) ÷ O (NP Q-Limit)\nScoring_CVAL: I (β_raw), J (β_c)"),
    ("γ",
     "Distribution fairness (load balancing)",
     "Clamp(1 - nonprod_customer_count / total_customers)",
     "0.25",
     "Rewards regions with fewer existing NonProd customers, promoting even CVAL distribution. Identical logic to PS_Prod but evaluated against NonProd customer counts. ⚠️ total_customers scope undefined.",
     "Capacity_Usage: U (Cust Count)\nScoring_CVAL: F (total_cust for denominator), K (γ_raw), L (γ_c)\n⚠️ total_customers scope: geography-level (most likely) or global (pending clarification)"),
    ("δ",
     "Overflow capacity health (redundant with α)",
     "Clamp(nonprod_crg.effective_free / nonprod_crg.quantity)",
     "0.15",
     "⚠️ DUPLICATE: This is identical to α. Combined α+δ weight = 0.45. This is the design-of-record formula (baseline v2.4). A pilot variant exists that removes this duplication and reallocates the weight.",
     "Capacity_Usage: N (NP Eff-Free) ÷ L (NP Reserved)\nScoring_CVAL: M (δ_raw), N (δ_c)\n⚠️ Same as α — duplication acknowledged in Calculation Logic Reference"),
    ("ε",
     "Zone diversity (availability zone count)",
     "Clamp(az_count / 3)",
     "0.10",
     "Identical to PS_Prod. Favors regions with more availability zones for better fault isolation.",
     "Capacity_Usage: E (AZ)\nScoring_CVAL: O (ε_raw), P (ε_c)")
]

row+=1
for comp, measure, formula, weight, explanation, cols in nonprod_components:
    fr[f"A{row}"]=comp; fr[f"A{row}"].font=BOLD; fr[f"A{row}"].alignment=Alignment(horizontal="center", vertical="top")
    fr[f"B{row}"]=measure; fr[f"B{row}"].alignment=Alignment(vertical="top", wrap_text=True)
    fr[f"C{row}"]=formula; fr[f"C{row}"].font=Font(name="Courier New", size=9)
    fr[f"C{row}"].alignment=Alignment(vertical="top", wrap_text=True)
    fr[f"D{row}"]=weight; fr[f"D{row}"].alignment=Alignment(horizontal="center", vertical="top")
    fr[f"E{row}"]=explanation; fr[f"E{row}"].alignment=Alignment(vertical="top", wrap_text=True)
    fr[f"F{row}"]=cols; fr[f"F{row}"].font=Font(name="Courier New", size=8)
    fr[f"F{row}"].alignment=Alignment(vertical="top", wrap_text=True)
    for c in ("A","B","C","D","E","F"):
        fr[f"{c}{row}"].border=BORDER
    fr.row_dimensions[row].height=90
    row+=1

fr[f"A{row}"]="FINAL SCORE"; fr[f"A{row}"].font=BOLD; fr[f"A{row}"].fill=PatternFill("solid",fgColor="D9EAD3")
fr[f"A{row}"].alignment=Alignment(horizontal="center", vertical="center")
fr[f"B{row}"]="Weighted sum of all five components"
fr[f"C{row}"]="PS_NonProd = 0.30×α + 0.20×β + 0.25×γ + 0.15×δ + 0.10×ε"
fr[f"C{row}"].font=Font(name="Courier New", size=10, bold=True)
fr[f"D{row}"]="1.00"; fr[f"D{row}"].font=BOLD; fr[f"D{row}"].alignment=Alignment(horizontal="center")
fr[f"E{row}"]="Range: [0, 1]. Highest score = best CVAL candidate. Winner = argmax(PS_NonProd) over eligible Standard regions (excluding Prod region). In 2-region model (EU, AU, AP): CVAL placement is deterministic (the other Standard region)."
fr[f"F{row}"]="Scoring_CVAL: Q (PS)"
fr[f"F{row}"].font=Font(name="Courier New", size=8)
for c in ("A","B","C","D","E","F"):
    fr[f"{c}{row}"].border=BORDER
    fr[f"{c}{row}"].fill=PatternFill("solid",fgColor="D9EAD3")
fr[f"C{row}"].alignment=Alignment(vertical="center", wrap_text=True)
fr[f"E{row}"].alignment=Alignment(vertical="top", wrap_text=True)
fr[f"F{row}"].alignment=Alignment(vertical="center", wrap_text=True)
fr.row_dimensions[row].height=60

# PS_DR Table
row+=3
fr[f"A{row}"]="PS_DR — DR (DISASTER RECOVERY) REGION SCORING"; fr[f"A{row}"].font=H2; fr[f"A{row}"].fill=HEADFILL
fr.merge_cells(f"A{row}:F{row}")
row+=1

for h, col in headers_prod:
    fr[f"{col}{row}"]=h; fr[f"{col}{row}"].font=WHITEB; fr[f"{col}{row}"].fill=HEADFILL
    fr[f"{col}{row}"].alignment=Alignment(horizontal="center", vertical="top", wrap_text=True)
    fr[f"{col}{row}"].border=BORDER

dr_components=[
    ("α",
     "Capacity headroom (DR CRG free slots)",
     "Clamp(dr_crg.free_slots / dr_crg.quantity)",
     "0.30",
     "Direct measure of DR capacity headroom. High DR free slots = region can accommodate additional DR workload. This evaluates the region's ability to serve as a DR destination (multi-source DR hosting, DR-016).",
     "Capacity_Usage: S (DR Free) ÷ R (DR Reserved)\nScoring_DR: G (α_raw), H (α_c)"),
    ("β",
     "Quota headroom (DR quota availability)",
     "Clamp(dr_crg.quota_headroom / dr_crg.quota_limit)",
     "0.20",
     "DR quota headroom. In practice, DR uses NonProd quota (DR VMs are in a NonProd environment), so this typically references NP Q-Headroom. Ensures the region has sufficient quota to accommodate the DR workload.",
     "Capacity_Usage: Q (NP Q-Headroom) ÷ O (NP Q-Limit)\nScoring_DR: I (β_raw), J (β_c)\n(DR uses NonProd quota per ENV-002)"),
    ("γ",
     "Distribution fairness (load balancing)",
     "Clamp(1 - dr_customer_count / total_customers)",
     "0.25",
     "Rewards regions with fewer existing DR customers, promoting even DR distribution. Prevents DR concentration in a single destination region. ⚠️ total_customers scope undefined.",
     "Capacity_Usage: U (Cust Count)\nScoring_DR: F (total_cust for denominator), K (γ_raw), L (γ_c)\n⚠️ total_customers scope: geography-level (most likely) or global (pending clarification)"),
    ("δ",
     "Coverage ratio health (DR sizing adequacy)",
     "min(1.0, dr_crg.coverage_ratio / dr_coverage_target)",
     "0.15",
     "Measures how close the region's existing DR coverage is to the configured target. Uses min(1.0, ...) instead of Clamp() for normalization. dr_coverage_target is a configurable scoring reference (per customer/product), NOT the retired 30-40% dr_ratio. DR sizing uses max-not-sum (A.6, DR-017).",
     "Capacity_Usage: T (DR Coverage)\nScoring_DR: M (δ_raw), N (δ_c)\ndr_coverage_target = configurable scoring parameter (Policy sheet or config)"),
    ("ε",
     "Zone diversity (availability zone count)",
     "Clamp(az_count / 3)",
     "0.10",
     "Identical to PS_Prod and PS_NonProd. Favors regions with more availability zones for better DR fault isolation.",
     "Capacity_Usage: E (AZ)\nScoring_DR: O (ε_raw), P (ε_c)")
]

row+=1
for comp, measure, formula, weight, explanation, cols in dr_components:
    fr[f"A{row}"]=comp; fr[f"A{row}"].font=BOLD; fr[f"A{row}"].alignment=Alignment(horizontal="center", vertical="top")
    fr[f"B{row}"]=measure; fr[f"B{row}"].alignment=Alignment(vertical="top", wrap_text=True)
    fr[f"C{row}"]=formula; fr[f"C{row}"].font=Font(name="Courier New", size=9)
    fr[f"C{row}"].alignment=Alignment(vertical="top", wrap_text=True)
    fr[f"D{row}"]=weight; fr[f"D{row}"].alignment=Alignment(horizontal="center", vertical="top")
    fr[f"E{row}"]=explanation; fr[f"E{row}"].alignment=Alignment(vertical="top", wrap_text=True)
    fr[f"F{row}"]=cols; fr[f"F{row}"].font=Font(name="Courier New", size=8)
    fr[f"F{row}"].alignment=Alignment(vertical="top", wrap_text=True)
    for c in ("A","B","C","D","E","F"):
        fr[f"{c}{row}"].border=BORDER
    fr.row_dimensions[row].height=90
    row+=1

fr[f"A{row}"]="FINAL SCORE"; fr[f"A{row}"].font=BOLD; fr[f"A{row}"].fill=PatternFill("solid",fgColor="D9EAD3")
fr[f"A{row}"].alignment=Alignment(horizontal="center", vertical="center")
fr[f"B{row}"]="Weighted sum of all five components"
fr[f"C{row}"]="PS_DR = 0.30×α + 0.20×β + 0.25×γ + 0.15×δ + 0.10×ε"
fr[f"C{row}"].font=Font(name="Courier New", size=10, bold=True)
fr[f"D{row}"]="1.00"; fr[f"D{row}"].font=BOLD; fr[f"D{row}"].alignment=Alignment(horizontal="center")
fr[f"E{row}"]="Range: [0, 1]. Highest score = best DR candidate. Winner = argmax(PS_DR) over eligible Standard regions (excluding Prod, CVAL). In 2-region model (EU, AU, AP): DR co-locates with CVAL (PLC-010a mandatory). Middle East: DR cross-geo in Europe (weighted-selected)."
fr[f"F{row}"]="Scoring_DR: Q (PS)"
fr[f"F{row}"].font=Font(name="Courier New", size=8)
for c in ("A","B","C","D","E","F"):
    fr[f"{c}{row}"].border=BORDER
    fr[f"{c}{row}"].fill=PatternFill("solid",fgColor="D9EAD3")
fr[f"C{row}"].alignment=Alignment(vertical="center", wrap_text=True)
fr[f"E{row}"].alignment=Alignment(vertical="top", wrap_text=True)
fr[f"F{row}"].alignment=Alignment(vertical="center", wrap_text=True)
fr.row_dimensions[row].height=60

# Footer notes
row+=2
fr[f"A{row}"]="KEY NOTES"; fr[f"A{row}"].font=Font(bold=True, size=11)
fr.merge_cells(f"A{row}:F{row}")
row+=1
notes=[
    "1. Clamp(x) = MIN(MAX(x, 0), 1) — ensures all component values stay in [0, 1] range to prevent outliers from dominating.",
    "2. Weight sum constraint: α + β + γ + δ + ε = 1.0 (enforced by Policy sheet validation).",
    "3. The three PS formulas are IDENTICAL across all region models (2-region, 3-region, 4-region, cross-geo). What changes: number of argmax passes, candidate pool, HC gate constraints.",
    "4. ⚠️ OPEN ISSUE: total_customers (γ component) is UNDEFINED in baseline v2.4 — no source, scope, or data type specified. Geography-level scope is most likely.",
    "5. PS_NonProd α and δ are identical (design-of-record v2.4) — combined weight 0.45. A pilot variant exists that removes this duplication.",
    "6. PS_DR δ uses min(1.0, ...) instead of Clamp() for coverage-ratio normalization.",
    "7. Column references: _raw = unclamped component; _c = clamped component; PS = final placement score.",
    "8. Winner selection: argmax(PS) over eligible Standard regions (or deterministic in 2-region co-located model)."
]
for note in notes:
    fr[f"A{row}"]=note; fr[f"A{row}"].alignment=Alignment(vertical="top", wrap_text=True)
    fr.merge_cells(f"A{row}:F{row}")
    fr.row_dimensions[row].height=30
    row+=1

wb.save(OUT)
print("Saved",OUT,"regions=",NR)
