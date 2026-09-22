# -*- coding: utf-8 -*-
"""由114年臺南市統計年報(農業局)產出書件各表新資料"""
import sys, io, re, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from ods_read import sheet_rows
F="tainan114_04農林漁牧.ods"
def num(s):
    s=(s or '').replace(',','').strip()
    if s in ('','-','–','…','*','...'): return None
    try: return float(s)
    except: return None
def f2(v): return '-' if v is None else f"{v:,.2f}"
def f0(v): return '-' if v is None else f"{int(round(v)):,}"
def rows_of(sheet): return sheet_rows(F,sheet)
def year_rows(sheet):
    out={}
    for r in rows_of(sheet):
        if not r: continue
        m=re.match(r'民國(\d+)年', r[0])
        if m: out[int(m.group(1))]=r
    return out
def dist_rows(sheet, start):
    out=[]
    for r in rows_of(sheet)[start:]:
        if not r: continue
        lab=re.sub(r'\s+',' ',r[0]).strip()
        if re.match(r'資料來源|說明|註|^\d|^1\.|^2\.|^3\.',lab) or not lab: break
        out.append((re.sub(r'\s*[A-Za-z].*$','',lab).replace(' ',''), r))
    return out

D={}
# ---- 表3-7：104~114 耕地 ----
yr=year_rows("4-1農耕土地面積")
D['T37']=[[str(y)]+[f2(num(yr[y][i])) for i in (1,2,7,4,5,6,8)] for y in range(104,115)]
# ---- 表3-8：114 各區耕地 ----
d=dist_rows("4-1農耕土地面積",17)
D['T38']=[[n]+[f2(num(r[i])) for i in (1,2,7,4,5,6,8)] for n,r in d]
D['T38'].append(['總計']+[f2(num(yr[114][i])) for i in (1,2,7,4,5,6,8)])
# ---- 表3-9：104~114 水產養殖 ----
yr=year_rows("4-12水產養殖")
def aqua(r):
    br,fw,orn,oth=num(r[9]),num(r[13]),num(r[17]),num(r[21])
    inland=sum(x for x in (br,fw,orn,oth) if x is not None)
    return [f2(num(r[1])),f2(num(r[5])),f2(inland),f2(br),f2(fw),f2(orn),f2(oth)]
D['T39']=[[str(y)]+aqua(yr[y]) for y in range(104,115)]
# ---- 表3-10：114 各區水產養殖 ----
d=dist_rows("4-12水產養殖",42)
D['T310']=[[n]+aqua(r) for n,r in d]
D['T310'].append(['總計']+aqua(yr[114]))
# ---- 表3-11：100~114 家畜家禽（牛欄統一用年報「牛」總數）----
a=year_rows("4-15牲畜數_修_"); b=year_rows("4-18家禽_修")
def lv(r):
    pig,goat,cow,deer,horse=num(r[5]),num(r[8]),num(r[2]),num(r[6]),num(r[4])
    tot=sum(x for x in (pig,goat,cow,deer,horse) if x is not None)
    return [f0(tot),f0(pig),f0(goat),f0(cow),f0(deer),f0(horse)]
def pl(r):
    ck,dk,gs,tk=num(r[1]),num(r[4]),num(r[7]),num(r[8])
    tot=sum(x for x in (ck,dk,gs,tk) if x is not None)
    return [f0(tot),f0(ck),f0(dk),f0(gs),f0(tk)]
D['T311']=[[str(y)]+lv(a[y])+pl(b[y]) for y in range(100,115)]
# ---- 表3-17：103~114 灌溉排水（埤圳數年報未提供，113/114 標…）----
yr=year_rows("4-21灌溉服務面積")
PIZ={y:('34','25') for y in range(103,113)}
D['T317']=[]
for y in range(103,115):
    r=yr[y]; p,c=PIZ.get(y,('…','…'))
    D['T317'].append([str(y),p,c]+[f0(num(r[i])) for i in (1,2,3,4,5,6,7,13,14,15)])
json.dump(D, open("new_tables.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
for k in ("T37","T39","T311","T317"):
    print(f"\n=== {k} ===")
    for r in D[k]: print("  "+" | ".join(r))
print(f"\n表3-8 區數={len(D['T38'])} 末列={D['T38'][-1]}")
print(f"表3-10 區數={len(D['T310'])} 末列={D['T310'][-1]}")
