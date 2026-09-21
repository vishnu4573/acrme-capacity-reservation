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
 ('Middle East','Saudi Arabia Central','saudicentral',3,'cross-geo','EU','Restricted',4),  # RESTRICTED
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
        origin=("real" if rtot.get(name,0)>0 else ("SYNTHETIC (Middle East — no real usage)" if geo=='Middle East' else "mock (catalogue region absent from data)"))
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
 ("• EXCEPTION: the Middle East regions (Saudi Arabia Central, UAE North) are RESTRICTED — production-only, and NOT "
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
 ("3. Setup — pick Geography, SKU, VM count, optional customer-supplied Prod region (required for Middle East), Customer ID.",None),
 ("4. Policy — the five weights (sum=1.0), total_customers mode, DR bootstrap / target, min headroom floors.",None),
 ("5. Capacity_Usage — the ACRME catalogue regions with distributed usage + a Class column (Standard / Restricted). "
  "Yellow = editable; grey = computed; green Class cell = Restricted (Middle East).",None),
 ("6. HC_Gate — HC-3 / HC-6 / HC-7 pass/fail and eligibility per region.",None),
 ("7. Scoring_Prod / 8. Scoring_CVAL / 9. Scoring_DR — PS component breakdown, AutoSelect flag and winners.",None),
 ("10. Result — final placement (Prod / CVAL / DR), readiness, DR sizing (max-not-sum).",None),
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
  "exercised. Japan East (Asia Pacific) is 'pending' in the catalogue and is excluded.",None,SYNFILL),
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
note=us.cell(row=2,column=1,value="Real aggregation from SKU_USage (1).xlsx (Total Cores). Prod = tag 'Prod'; all other tags = Non-Prod. This is provenance; the engine reads the distributed Capacity_Usage sheet.")
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

# ============================================================ Setup
sp=wb.create_sheet("Setup"); sp.sheet_view.showGridLines=False
for col,w in {"A":26,"B":24,"C":3,"D":3,"E":20,"F":10,"G":16}.items():
    sp.column_dimensions[col].width=w
sp["A1"]="SETUP — Customer & Workload"; sp["A1"].font=H1
def lbl(ws_,cell,txt): ws_[cell]=txt; ws_[cell].font=BOLD
def inp(ws_,cell,val):
    ws_[cell]=val; ws_[cell].fill=INFILL; ws_[cell].border=BORDER; ws_[cell].alignment=CTR
lbl(sp,"A3","Geography");          inp(sp,"B3","US")
lbl(sp,"A4","SKU");                inp(sp,"B4","E16ads_v5")
lbl(sp,"A5","VM count");           inp(sp,"B5",3)
lbl(sp,"A6","vCPU per VM");        sp["B6"]="=VLOOKUP(B4,E3:F10,2,FALSE)"; sp["B6"].alignment=CTR
lbl(sp,"A7","Requested vCPU");     sp["B7"]="=B5*B6"; sp["B7"].font=BOLD; sp["B7"].alignment=CTR
lbl(sp,"A8","Prod region (req. for Middle East)"); inp(sp,"B8","")
lbl(sp,"A9","Customer ID");        inp(sp,"B9","CUST-0042")
lbl(sp,"A10","Distribution model");sp["B10"]="=VLOOKUP(B3,E13:G17,2,FALSE)"; sp["B10"].alignment=CTR
lbl(sp,"A11","DR scope geography");sp["B11"]="=VLOOKUP(B3,E13:G17,3,FALSE)"; sp["B11"].alignment=CTR
sp["E1"]="Lookup tables (do not edit)"; sp["E1"].font=Font(italic=True,color="808080")
sp["E2"]="SKU"; sp["F2"]="vCPU/VM"
for c in ("E2","F2"): sp[c].font=WHITEB; sp[c].fill=HEADFILL; sp[c].alignment=CTR
skus=[("E16ads_v5",16),("E32ads_v5",32),("E8ads_v5",8),("E4ads_v5",4),
      ("D8ads_v5",8),("D4ads_v5",4),("D2ads_v5",2),("D16ads_v5",16)]
for i,(s,v) in enumerate(skus):
    sp.cell(row=3+i,column=5,value=s).border=BORDER
    sp.cell(row=3+i,column=6,value=v).border=BORDER
sp["E12"]="Geography"; sp["F12"]="Model"; sp["G12"]="DR Scope Geo"
for c in ("E12","F12","G12"): sp[c].font=WHITEB; sp[c].fill=HEADFILL; sp[c].alignment=CTR
geos=[("US","3-region","US"),("EU","2-region","EU"),("Australia","2-region","Australia"),
      ("Asia Pacific","2-region","Asia Pacific"),("Middle East","cross-geo","EU")]
for i,(g,m,d) in enumerate(geos):
    sp.cell(row=13+i,column=5,value=g).border=BORDER
    sp.cell(row=13+i,column=6,value=m).border=BORDER
    sp.cell(row=13+i,column=7,value=d).border=BORDER
dv_geo=DataValidation(type="list",formula1='"US,EU,Australia,Asia Pacific,Middle East"',allow_blank=False)
dv_sku=DataValidation(type="list",formula1='"E16ads_v5,E32ads_v5,E8ads_v5,E4ads_v5,D8ads_v5,D4ads_v5,D2ads_v5,D16ads_v5"',allow_blank=False)
dv_reg=DataValidation(type="list",formula1=f"=Capacity_Usage!$B${FIRST}:$B${LAST}",allow_blank=True)
for dv,cell in ((dv_geo,"B3"),(dv_sku,"B4"),(dv_reg,"B8")):
    sp.add_data_validation(dv); dv.add(sp[cell])

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
          "α_raw","α_c","β_raw","β_c","γ_raw","γ_c","δ_raw","δ_c","ε_raw","ε_c","PS","Candidate"]
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
        for col in range(1,19):
            cc=s.cell(row=xr,column=col); cc.border=BORDER; cc.alignment=CTR
            if col in range(7,18): cc.number_format="0.000"
    for col in range(1,19): s.column_dimensions[get_column_letter(col)].width=9
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
rlbl("A5","SKU");         rout("B5","=Setup!B4")
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

wb.save(OUT)
print("Saved",OUT,"regions=",NR)
