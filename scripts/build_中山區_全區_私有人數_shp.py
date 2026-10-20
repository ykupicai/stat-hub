"""中山區全區地號（都發局地籍圖）併入 RALIDs 私有人數與公有土地圖層屬性 → 全區 shp 與分布摘要。

輸入：資料庫/原始檔/臺北市地籍圖_LAND-ALL/page_*.json（dist_name＝中山區）；地號清單/中山區_私有人數API/ralids_raw.jsonl（27,056 個地號全部查完）；
  公有土地/臺北市公有土地.shp（LANDTYPE2、OWN_PER1 私有持分、MNGR 管理機關）
欄位：KEY（段碼4＋母號4＋子號4）、SECT、LANDNO、AREA_M2（圖面面積）、L_MANS 土地私有人數、L_PAREA 私有面積、B_COUNT／B_MANS／B_PAREA 建物筆數／私有人數／私有面積、R_NOTE、
  PUB_CLS（公有分類）、PUB_PCT（公有持分%）、HAS_TX（105～114 年有無買賣交易）
輸出：案件/臺北市_不動產交易分析/中山區_權屬/中山區_全區_私有人數.shp、欄位說明_全區.csv；摘要印在終端
執行：python scripts/build_中山區_全區_私有人數_shp.py
"""
import glob
import io
import json
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import shape

warnings.filterwarnings("ignore")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent
CASE = ROOT / "案件" / "臺北市_不動產交易分析"
OWN = CASE / "中山區_權屬"


def main():
    recs, geoms = [], []
    for f in sorted(glob.glob(str(ROOT / "資料庫" / "原始檔" / "臺北市地籍圖_LAND-ALL" / "page_*.json"))):
        for x in json.load(open(f, encoding="utf-8"))["features"]:
            p = x["properties"]
            if p["dist_name"] != "中山區":
                continue
            recs.append({"KEY": p["sect_id"] + p["land_pnum"] + p["land_snum"], "SECT": p["sect_name"], "LANDNO": p["land_no"]})
            geoms.append(shape(x["geometry"]).buffer(0))
    g = gpd.GeoDataFrame(recs, geometry=geoms, crs=3826)
    g["AREA_M2"] = g.area.round(2)
    print(f"中山區地籍圖地號 {len(g):,}（不重複 key {g['KEY'].nunique():,}）")
    raw = {}
    for l in open(CASE / "地號清單" / "中山區_私有人數API" / "ralids_raw.jsonl", encoding="utf-8", errors="replace"):
        try:
            j = json.loads(l)
            raw[j["code12"]] = j
        except (ValueError, KeyError):
            pass
    for k, c in (("Lmans", "L_MANS"), ("LPArea", "L_PAREA"), ("BCount", "B_COUNT"), ("Bmans", "B_MANS"), ("BPArea", "B_PAREA"), ("note", "R_NOTE")):
        g[c] = g["KEY"].map(lambda x, k=k: raw[x][k] if x in raw else None)
    got = g["KEY"].isin(raw)
    print(f"對到 RALIDs 結果 {int(got.sum()):,} / {len(g):,}（RALIDs 檔共 {len(raw):,} 筆，含非中山區或不在圖層的地號）")
    pub = gpd.read_file(CASE / "公有土地" / "臺北市公有土地.shp", encoding="utf-8", columns=["PL48", "PL49", "LANDTYPE2", "OWN_PER1", "MNGR", "PL46_N"], ignore_geometry=True)
    pub = pub[pub["PL46_N"] == "中山區"].copy()
    pub["KEY"] = pub["PL48"].astype(str).str.zfill(4) + pub["PL49"].astype(str).str.zfill(8)
    pub["PUB_PCT"] = (100 - pd.to_numeric(pub["OWN_PER1"], errors="coerce").fillna(0)).round(2)
    pub = pub.drop_duplicates("KEY").set_index("KEY")
    g["PUB_CLS"] = g["KEY"].map(pub["LANDTYPE2"]).fillna("非公有")
    g["PUB_PCT"] = g["KEY"].map(pub["PUB_PCT"]).fillna(0)
    g["MNGR"] = g["KEY"].map(pub["MNGR"]).fillna("").astype(str).str.slice(0, 60)
    tx = gpd.read_file(OWN / "中山區_交易土地權屬.shp", encoding="utf-8", columns=["SECTION", "LANDNO"], ignore_geometry=True)
    txs = set(zip(tx["SECTION"], tx["LANDNO"]))
    g["HAS_TX"] = [int((a, b) in txs) for a, b in zip(g["SECT"], g["LANDNO"])]
    print(f"其中有 105～114 年買賣交易者 {int(g['HAS_TX'].sum()):,}")
    out = g[["KEY", "SECT", "LANDNO", "AREA_M2", "L_MANS", "L_PAREA", "B_COUNT", "B_MANS", "B_PAREA", "R_NOTE", "PUB_CLS", "PUB_PCT", "MNGR", "HAS_TX", "geometry"]].copy()
    for c in ("L_MANS", "B_COUNT", "B_MANS"):
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out["L_PAREA"] = pd.to_numeric(out["L_PAREA"], errors="coerce")
    out["B_PAREA"] = pd.to_numeric(out["B_PAREA"], errors="coerce")
    out["R_NOTE"] = out["R_NOTE"].fillna("").astype(str).str.slice(0, 30)
    out.to_file(OWN / "中山區_全區_私有人數.shp", driver="ESRI Shapefile", encoding="utf-8")
    pd.DataFrame({"欄位": ["KEY", "SECT", "LANDNO", "AREA_M2", "L_MANS", "L_PAREA", "B_COUNT", "B_MANS", "B_PAREA", "R_NOTE", "PUB_CLS", "PUB_PCT", "MNGR", "HAS_TX"],
                  "說明": ["段碼4＋母號4＋子號4", "段名", "地號", "圖面面積(㎡，僅供對照，登記面積以地政為準)", "土地私有人數（RALIDs）", "土地私有面積(㎡)", "建物筆數", "建物私有人數", "建物私有面積(㎡)", "備註(公同共有、見其他登記)",
                         "公有分類（公有土地圖層 LANDTYPE2；不在圖層者為非公有）", "公有持分%（100－私有持分）", "公有管理機關", "105～114 年有無買賣交易(1/0)"]}).to_csv(OWN / "欄位說明_全區.csv", index=False, encoding="utf-8-sig")
    v = out["L_MANS"]
    ok = v.notna()
    print(f"土地私有人數：有值 {int(ok.sum()):,}；中位數 {v.median():.0f}；平均 {v.mean():.1f}；最大 {v.max():.0f}")
    bins = [(-1, 0), (0, 1), (1, 5), (5, 20), (20, 50), (50, 1e9)]
    labs = ["0 人", "1 人", "2～5 人", "6～20 人", "21～50 人", "51 人以上"]
    cut = pd.cut(v[ok], [-1, 0, 1, 5, 20, 50, 1e9], labels=labs)
    print("分布：", cut.value_counts().reindex(labs).to_dict())
    print("交易地號 vs 未交易地號 私有人數中位數：", out.groupby("HAS_TX")["L_MANS"].median().to_dict(), "；平均", out.groupby("HAS_TX")["L_MANS"].mean().round(1).to_dict())
    print("公有分類：", out["PUB_CLS"].value_counts().to_dict())
    print("面積（圖面 ha）：", round(out["AREA_M2"].sum() / 1e4, 1), "；公有分類面積 ha：", (out.groupby("PUB_CLS")["AREA_M2"].sum() / 1e4).round(1).to_dict())
    big = out.sort_values("L_MANS", ascending=False).head(8)[["SECT", "LANDNO", "L_MANS", "AREA_M2", "B_COUNT", "HAS_TX"]]
    print(big.to_string(index=False))
    pa = out[ok & (out["L_PAREA"] > 0)]
    print("私有面積>0 的地號 ", len(pa), "；私有面積占圖面面積", round(pa["L_PAREA"].sum() / pa["AREA_M2"].sum() * 100, 1), "%")
    print("建物：有建物（B_COUNT>0）", int((out["B_COUNT"] > 0).sum()), "；建物私有人數中位數", out.loc[out["B_COUNT"] > 0, "B_MANS"].median())


if __name__ == "__main__":
    main()
