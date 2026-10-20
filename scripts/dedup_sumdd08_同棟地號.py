"""BuildStat_Fage 的 sumdd08 去重：找出「同一棟建物跨多個地號、各地號重複記同一個總樓地板」的地號群。

規則（使用者指定）：相鄰（地號面相接，容差 0.3 m）、且 sumdd08、建物數 ct、層數 DD13H、屋齡（fageavg／fagemax／fagemin）皆相同的地號，視為同一棟。
  同棟的樓地板只算一次，依地號登記面積（AA10）比例分配到各地號：new_sumdd08 ＝ 群組 sumdd08 × AA10_i ÷ ΣAA10。
附帶檢查：群組中是否有地號放不下這麼多樓地板（sumdd08 > AA10×(層數+4)），作為「確屬同棟」的佐證，與「只是相鄰的相同透天厝」區分。
輸出：資料庫/原始檔/臺北市建物屋齡_BuildStat_Fage/dedup_components.csv（每個地號的群組代碼、群組大小、分配後 sumdd08）
執行：python scripts/dedup_sumdd08_同棟地號.py
"""
import glob
import importlib.util
import json
import time
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("age", ROOT / "scripts" / "build_臺北市_行政區屋齡_地政局圖層.py")
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
RAW = M.RAW
OUT = RAW / "dedup_components.csv"


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def main():
    recs, geoms = [], []
    for f in sorted(glob.glob(str(RAW / "page_*.json"))):
        for ft in json.load(open(f, encoding="utf-8"))["features"]:
            a = ft["attributes"]
            recs.append({"OBJECTID": a["OBJECTID"], "key": a["KCNT"] + "|" + a["AA49"], "sumdd08": a["sumdd08"] or 0.0, "ct": a["ct"], "DD13H": a["DD13H"] or "",
                         "age": (a["fageavg"], a["fagemax"], a["fagemin"]), "AA10": a["AA10"] or 0.0})
            geoms.append(M.rings_to_geom(ft["geometry"]["rings"]))
    P = gpd.GeoDataFrame(pd.DataFrame(recs), geometry=geoms, crs=3826)
    P["geometry"] = P.geometry.buffer(0)
    P["gid"] = P["sumdd08"].round(2).astype(str) + "|" + P["ct"].astype(str) + "|" + P["DD13H"].astype(str) + "|" + P["age"].astype(str)
    log("地號", len(P))
    cnt = P[P["sumdd08"] > 0].groupby("gid")["OBJECTID"].transform("size")
    cand = P[(P["sumdd08"] > 0)].loc[cnt[cnt > 1].index].copy()
    log("相同屬性的候選地號", len(cand), "；屬性組", cand["gid"].nunique())
    left = cand[["OBJECTID", "gid", "geometry"]].copy()
    left["geometry"] = left.geometry.buffer(0.3)
    pairs = gpd.sjoin(left, cand[["OBJECTID", "gid", "geometry"]], how="inner", predicate="intersects")
    pairs = pairs[(pairs["gid_left"] == pairs["gid_right"]) & (pairs["OBJECTID_left"] != pairs["OBJECTID_right"])]
    log("相鄰且屬性相同的配對", len(pairs))
    idx = {o: i for i, o in enumerate(cand["OBJECTID"])}
    r = pairs["OBJECTID_left"].map(idx).to_numpy(); c = pairs["OBJECTID_right"].map(idx).to_numpy()
    n = len(cand)
    _, lab = connected_components(coo_matrix((np.ones(len(r)), (r, c)), shape=(n, n)), directed=False)
    cand["comp"] = lab
    size = cand.groupby("comp")["OBJECTID"].transform("size")
    cand = cand[size > 1].copy()
    cand["comp_n"] = cand.groupby("comp")["OBJECTID"].transform("size")
    cand["sum_area"] = cand.groupby("comp")["AA10"].transform("sum")
    cand["new_sumdd08"] = np.where(cand["sum_area"] > 0, cand["sumdd08"] * cand["AA10"] / cand["sum_area"], cand["sumdd08"] / cand["comp_n"])
    fl = pd.to_numeric(cand["DD13H"].str.split(",").str[-1], errors="coerce").fillna(1).clip(lower=1)
    cand["over_cap"] = cand["sumdd08"] > cand["AA10"] * (fl + 4)
    cand["comp_over"] = cand.groupby("comp")["over_cap"].transform("max")
    tot = P["sumdd08"].sum()
    removed = (cand["sumdd08"] - cand["new_sumdd08"]).sum()
    log(f"同棟群組 {cand['comp'].nunique():,}，涉及地號 {len(cand):,}；去重前 sumdd08 合計 {tot / 1e4:,.0f} 萬㎡，去重後 {(tot - removed) / 1e4:,.0f} 萬㎡（減少 {removed / 1e4:,.0f} 萬㎡，{removed / tot:.1%}）")
    g = cand.groupby("comp").agg(n=("OBJECTID", "size"), over=("comp_over", "first"), dup=("sumdd08", lambda s: s.iloc[0] * (len(s) - 1)))
    log(f"群組中至少一個地號放不下該樓地板（佐證確屬同棟）：{int(g['over'].sum()):,} 群／{len(g):,}；其去重量 {g.loc[g['over'], 'dup'].sum() / 1e4:,.0f} 萬㎡；其餘群組去重量 {g.loc[~g['over'], 'dup'].sum() / 1e4:,.0f} 萬㎡")
    print("群組大小分布", g["n"].value_counts().sort_index().head(10).to_dict())
    out = P[["OBJECTID", "key", "sumdd08", "AA10"]].merge(cand[["OBJECTID", "comp", "comp_n", "new_sumdd08", "comp_over"]], on="OBJECTID", how="left")
    out["new_sumdd08"] = out["new_sumdd08"].fillna(out["sumdd08"])
    out["comp_n"] = out["comp_n"].fillna(1).astype(int)
    out.to_csv(OUT, index=False, encoding="utf-8-sig")
    log("輸出", OUT)


if __name__ == "__main__":
    main()
