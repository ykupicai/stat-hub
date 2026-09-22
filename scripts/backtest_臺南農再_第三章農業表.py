# -*- coding: utf-8 -*-
"""以114年臺南市統計年報(農業局提供)重算書中既有年度，逐格比對"""
import sys, io, zipfile, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from lxml import etree
from ods_read import sheet_rows
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
q=lambda t:'{%s}%s'%(W,t)
F="tainan114_04農林漁牧.ods"
with zipfile.ZipFile("期中報告書_工作副本.docx") as z: xml=z.read('word/document.xml')
els=list(etree.fromstring(xml).find(q('body')))
def tbl(i):
    return [[''.join(x.text or '' for x in tc.iter(q('t'))) for tc in tr.findall(q('tc'))] for tr in els[i].findall(q('tr'))]
def num(s):
    s=(s or '').replace(',','').strip()
    if s in ('','-','–','…','*'): return None
    try: return float(s)
    except: return None
def fmt(v,dec=2):
    if v is None: return '-'
    return f"{v:,.{dec}f}" if dec else f"{int(round(v)):,}"
def yrow(sheet, roc):
    for r in sheet_rows(F,sheet):
        if r and re.match(rf'民國{roc}年', r[0]): return r
    return None

bad=0
def cmp(label, book, calc, tol=0.005):
    global bad
    b,c=num(book),num(calc) if isinstance(calc,str) else calc
    ok = (b is None and c is None) or (b is not None and c is not None and abs(b-c)<=tol)
    if not ok:
        bad+=1
        d = (c-b) if (b is not None and c is not None) else None
        print(f"   ✗ {label}: 書={book}  年報={fmt(c) if c is not None else '-'}" + (f"  差={d:+,.2f}" if d is not None else ""))
    return ok

print("===== 表3-7 歷年耕地面積（書 104-113 vs 年報4-1）=====")
t=tbl(668)
for row in t[3:]:
    roc=row[0]; yr=yrow("4-1農耕土地面積",roc)
    if not yr: print(f"   {roc}年：年報無此年"); continue
    m=[yr[1],yr[2],yr[7],yr[4],yr[5],yr[6],yr[8]]
    n0=bad
    for k,(b,c) in enumerate(zip(row[1:],m)): cmp(f"{roc}年 第{k+1}欄",b,c)
    if bad==n0: print(f"   ✓ {roc}年 全部相符")

print("\n===== 表3-9 歷年水產養殖（書 104-113 vs 年報4-12）=====")
t=tbl(679)
for row in t[2:]:
    roc=row[0]; yr=yrow("4-12水產養殖",roc)
    if not yr: print(f"   {roc}年：年報無此年"); continue
    inland=sum(x for x in (num(yr[9]),num(yr[13]),num(yr[17]),num(yr[21])) if x is not None)
    m=[num(yr[1]),num(yr[5]),inland,num(yr[9]),num(yr[13]),num(yr[17]),num(yr[21])]
    n0=bad
    for k,(b,c) in enumerate(zip(row[1:],m)): cmp(f"{roc}年 第{k+1}欄",b,c)
    if bad==n0: print(f"   ✓ {roc}年 全部相符")

print("\n===== 表3-11 歷年家畜家禽（書 100-113 vs 年報4-15_修_/4-18_修）=====")
t=tbl(689)
for row in t[2:]:
    roc=row[0]; a=yrow("4-15牲畜數_修_",roc); b_=yrow("4-18家禽_修",roc)
    if not a or not b_: print(f"   {roc}年：年報無此年"); continue
    pig,goat,deer,horse=num(a[5]),num(a[8]),num(a[6]),num(a[4])
    cow_all,cow_milk=num(a[2]),num(a[3])
    cow = cow_all if abs((num(row[4]) or 0)-(cow_all or 0))<abs((num(row[4]) or 0)-(cow_milk or 0)) else cow_milk
    print(f'   [{roc}年 牛欄] 書={row[4]}  年報牛總數={cow_all}  年報乳牛={cow_milk}')
    tot=sum(x for x in (pig,goat,cow,deer,horse) if x is not None)
    ck,dk,gs,tk=num(b_[1]),num(b_[4]),num(b_[7]),num(b_[8])
    ptot=sum(x for x in (ck,dk,gs,tk) if x is not None)
    m=[tot,pig,goat,cow,deer,horse,ptot,ck,dk,gs,tk]
    n0=bad
    for k,(bb,c) in enumerate(zip(row[1:],m)): cmp(f"{roc}年 第{k+1}欄",bb,c,tol=0.5)
    if bad==n0: print(f"   ✓ {roc}年 全部相符")

print("\n===== 表3-17 灌溉排水（書 103-112 vs 年報4-21）=====")
t=tbl(721)
for row in t[3:]:
    roc=row[0]; yr=yrow("4-21灌溉服務面積",roc)
    if not yr: print(f"   {roc}年：年報無此年"); continue
    m=[num(yr[1]),num(yr[2]),num(yr[3]),num(yr[4]),num(yr[5]),num(yr[6]),num(yr[7]),num(yr[13]),num(yr[14]),num(yr[15])]
    n0=bad
    for k,(bb,c) in enumerate(zip(row[3:],m)): cmp(f"{roc}年 第{k+3}欄",bb,c,tol=0.5)
    if bad==n0: print(f"   ✓ {roc}年 全部相符")

print(f"\n===== 不符格數合計：{bad} =====")
