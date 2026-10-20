# -*- coding: utf-8 -*-
"""合併中山區全量結果:CSV + SHP(只含 OK) + 說明.md。"""
import os, sys, csv, glob, json, collections, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cadastre_fast  # noqa  (載入 skill 路徑與 utf8 console)
import cadlib as C
BASE = r"C:\Users\USER\OneDrive\文件\project\STATHUB\案件\臺北市_不動產交易分析\地號清單"
OUT = os.path.join(BASE, "中山區_全量")
SRC = os.path.join(BASE, "不重複地號清單_中山區_官方去重.csv")
rd = lambda f: list(csv.DictReader(open(f, encoding="utf-8-sig")))
lst = [(r["官方段名"], r["地號_母子號"]) for r in rd(SRC)]
prior = {}
for f in [BASE + r"\試跑_中山區\試跑結果.csv"] + glob.glob(BASE + r"\壓力測試_中山區\*.csv"):
    for r in rd(f):
        if r["狀態"] == "OK": prior[(r["段"], r["地號"])] = r
full = {}
for f in glob.glob(OUT + r"\全量_*.csv"):
    for r in rd(f): full[(r["段"], r["地號"])] = r
geom = {}
for f in glob.glob(OUT + r"\*.geom.jsonl"):
    for ln in open(f, encoding="utf-8"):
        g = json.loads(ln); geom[(g["段"], g["地號"])] = g
F = ["段", "地號", "狀態", "登記面積", "圖面積", "差異%", "耗時秒", "重試次數", "14碼", "備註"]
rows, missing = [], []
for k in lst:
    r = full.get(k) or prior.get(k)
    if r is None: missing.append(k); continue
    rows.append({c: r.get(c, "") for c in F})
with open(os.path.join(OUT, "中山區_全部結果.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=F); w.writeheader(); w.writerows(rows)
# SHP
feats, nogeom = [], []
for r in rows:
    if r["狀態"] != "OK": continue
    g = geom.get((r["段"], r["地號"]))
    if not g: nogeom.append(r["段"] + r["地號"]); continue
    reg = r["登記面積"]
    feats.append({"ring": g["ring"], "attrs": {"段": r["段"], "地號": r["地號"], "段號": g["14碼"],
                  "登記面積": ("%.2f" % float(reg)) if reg != "" else "", "圖面積": r["圖面積"], "差異pct": r["差異%"]}})
FLD = [("段", "C", 24), ("地號", "C", 12), ("段號", "C", 14), ("登記面積", "N", 18), ("圖面積", "N", 18), ("差異pct", "N", 10)]
base = os.path.join(OUT, "中山區_全部OK")
C.write_shapefile(base, feats, FLD)
# 統計
n = len(rows); st = collections.Counter(r["狀態"] for r in rows)
bad = [r for r in rows if r["狀態"] != "OK"]
big = []
for r in rows:
    if r["狀態"] == "OK" and r["差異%"] != "" and abs(float(r["差異%"])) > 5: big.append(r)
def cls(a):
    a = float(a)
    return "<10 m²" if a < 10 else "10~30 m²" if a < 30 else "30~100 m²" if a < 100 else "≥100 m²"
order = ["<10 m²", "10~30 m²", "30~100 m²", "≥100 m²"]
tot = collections.Counter(cls(r["登記面積"]) for r in rows if r["狀態"] == "OK" and r["登記面積"] != "")
bc = collections.Counter(cls(r["登記面積"]) for r in big if r["登記面積"] != "")
el = ""
lg = os.path.join(OUT, "orchestrator.log")
if os.path.exists(lg): el = open(lg, encoding="utf-8").read()
md = ["# 中山區全量結果說明", "",
      "- 清單 %d 筆;合併 %d 筆;未取得結果 %d 筆。版次依各檔(115Jun)。" % (len(lst), n, len(missing)),
      "- 圖資僅供評估、非界址;面積一律以內政部登記面積為準,圖面積僅供對照。",
      "", "## 各狀態筆數", "", "| 狀態 | 筆數 | 比例 |", "|---|---|---|"]
for k, v in st.most_common(): md.append("| %s | %d | %.2f%% |" % (k, v, v / n * 100))
md += ["", "SHP:%d 個 OK 圖形(EPSG:3826);缺幾何 %d 筆。" % (len(feats), len(nogeom)), "",
       "## MISMATCH / 失敗清單(%d 筆)" % len(bad), "", "| 段 | 地號 | 狀態 | 備註 |", "|---|---|---|---|"]
for r in bad: md.append("| %s | %s | %s | %s |" % (r["段"], r["地號"], r["狀態"], r["備註"].replace("|", "/")[:120]))
md += ["", "## 圖面積與登記面積差超過 ±5%%(共 %d 筆,占 OK %.2f%%)" % (len(big), len(big) / max(st["OK"], 1) * 100), "",
       "| 登記面積分級 | OK 筆數 | 超過±5%筆數 | 比例 |", "|---|---|---|---|"]
for k in order: md.append("| %s | %d | %d | %.1f%% |" % (k, tot[k], bc[k], bc[k] / tot[k] * 100 if tot[k] else 0))
md += ["", "明細見 中山區_全部結果.csv(差異%欄)。", "", "## 實際耗時", "", "orchestrator.log 摘錄:", "```"] + [l for l in el.splitlines() if "開始" in l or "結束" in l or "!!" in l] + ["```"]
open(os.path.join(OUT, "說明.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
print(dict(st), "shp", len(feats), "nogeom", len(nogeom), "missing", len(missing), "big", len(big))
