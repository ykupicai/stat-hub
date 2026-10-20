# -*- coding: utf-8 -*-
"""臺北市實價登錄買賣交易(交易日 105/10~114/12)所附地段地號 → 地籍評估工作流清單。
用法: PYTHONUTF8=1 python -I scripts/export_臺北市_交易地號清單.py
"""
import sqlite3, csv, sys, os
from collections import defaultdict
sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "資料庫", "lvr.sqlite")
OUT = os.path.join(ROOT, "案件", "臺北市_不動產交易分析", "地號清單")
os.makedirs(OUT, exist_ok=True)

con = sqlite3.connect(DB)
n_tx = con.execute("select count(*) from lvr_tx where kind='a' and county='臺北市' and 交易日 between 1051001 and 1141231").fetchone()[0]
n_land = con.execute("""select count(*) from lvr_land l join lvr_tx t on t.編號=l.編號 and t.kind=l.kind
 where t.kind='a' and t.county='臺北市' and t.交易日 between 1051001 and 1141231""").fetchone()[0]
n_notx_land = con.execute("""select count(*) from lvr_tx t where t.kind='a' and t.county='臺北市'
 and t.交易日 between 1051001 and 1141231
 and not exists(select 1 from lvr_land l where l.編號=t.編號 and l.kind=t.kind)""").fetchone()[0]

rows = con.execute("""select t.編號,t.交易日,t.交易標的,t.鄉鎮市區,l.土地位置,l.地號,l.移轉情形,
  l.使用分區或編定,l.持分分子,l.持分分母,l.面積
 from lvr_land l join lvr_tx t on t.編號=l.編號 and t.kind=l.kind
 where t.kind='a' and t.county='臺北市' and t.交易日 between 1051001 and 1141231
 order by t.交易日,t.編號""").fetchall()

def fmt(no8):
    no8 = (no8 or "").strip()
    if len(no8) != 8 or not no8.isdigit():
        return ""
    m, s = int(no8[:4]), int(no8[4:])
    return f"{m}-{s}" if s else f"{m}"

hdr = ["編號","交易日","交易標的","行政區","地段","地號_8碼","地號_母子號","移轉情形","使用分區或編定","持分分子","持分分母","登載面積"]
agg = {}
blank_seg = bad_no = 0
with open(os.path.join(OUT, "交易地號明細.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f); w.writerow(hdr)
    for (bid, d, tgt, dist, seg, no8, mv, zone, fn, fd, area) in rows:
        seg = (seg or "").strip()
        ms = fmt(no8)
        if not seg: blank_seg += 1
        if not ms: bad_no += 1
        w.writerow([bid, d, tgt, dist, seg, no8, ms, mv, zone, fn, fd, area])
        if seg and ms:
            k = (dist, seg, ms)
            a = agg.get(k)
            if a is None: agg[k] = [1, d, d, no8]
            else:
                a[0] += 1; a[1] = min(a[1], d); a[2] = max(a[2], d)
with open(os.path.join(OUT, "不重複地號清單.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f); w.writerow(["行政區","地段","地號_母子號","地號_8碼","出現交易次數","最早交易日","最晚交易日"])
    for (dist, seg, ms), (n, d0, d1, no8) in sorted(agg.items()):
        w.writerow([dist, seg, ms, no8, n, d0, d1])
n_uniq = len(agg)

md = f"""# 臺北市買賣交易地號清單說明

## 口徑
- 來源：資料庫/lvr.sqlite（實價登錄，臺北市 105S4～115S3 已入庫）。
- 篩選：lvr_tx.kind='a'（買賣）、county='臺北市'、交易日 1051001～1141231（民國年月日）。
- 行政區取自 lvr_tx.鄉鎮市區（以 編號+kind 對應）；地段取自 lvr_land.土地位置（僅「段／小段」，不含行政區）。
- 地號_8碼：前 4 碼母號、後 4 碼子號；母子號格式 `30-7`，子號 0 只寫母號。
- 不重複地號以 行政區+地段+地號_母子號 去重（地段空白或地號非 8 碼數字者不納入）。
- 「登載面積」為實價登錄該筆土地登載面積，僅供量級對照；評估一律以內政部登記面積為準。

## 筆數
| 項目 | 筆數 |
|---|---|
| 交易數 | {n_tx:,} |
| 土地明細列數 | {n_land:,} |
| 不重複地號數 | {n_uniq:,} |
| 無土地明細的交易數 | {n_notx_land:,} |
| 地段空白列數 | {blank_seg:,} |
| 地號格式異常列數 | {bad_no:,} |
"""
open(os.path.join(OUT, "說明.md"), "w", encoding="utf-8").write(md)
print(md)
