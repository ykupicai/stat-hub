"""臺北市各行政區現況屋齡（地政局 BuildStat_Fage 圖層）→ 行政區面 shp ＋ 地號面 shp。

輸入：資料庫/原始檔/臺北市建物屋齡_BuildStat_Fage/page_*.json（先跑 fetch_臺北市_建物屋齡圖層.py；EPSG:3826）
欄位（ArcGIS 圖層原名 → 本檔意義；意義依樣本與分布推定，未經地政局書面確認）：
  KCNT 段名、LandNo 地號、fageavg/fagemax/fagemin 該地號上建物屋齡平均/最大/最小、ct 建物筆數、sumdd08 建物面積合計（㎡）。
  屋齡基準推定為民國 115 年（2026）：最大屋齡 115、屋齡 0 者 72 個地號、河堤段新大樓屋齡 9。
口徑：行政區以地號面的代表點落入行政區界（沿用 行政區建物分析/shp 的 108/11 界線）判定，界外者取最近行政區；
  屋齡統計以建物筆數（ct）加權；另列「扣除屋齡 55」版本——屋齡 55 年的地號占 23%，與鄰近年份落差極大（對照 2016 年使照資料無該年尖峰），疑為缺值預設，故保留原值並另提供對照欄位。
輸出：案件/臺北市_不動產交易分析/行政區屋齡/現況_地政局圖層/
執行：python scripts/build_臺北市_行政區屋齡_地政局圖層.py
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
from shapely.geometry import MultiPolygon, Polygon

warnings.filterwarnings("ignore")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "資料庫" / "原始檔" / "臺北市建物屋齡_BuildStat_Fage"
BND = ROOT / "案件" / "臺北市_不動產交易分析" / "行政區建物分析" / "shp" / "臺北市行政區_建物交易分析.shp"
OUT = ROOT / "案件" / "臺北市_不動產交易分析" / "行政區屋齡" / "現況_地政局圖層"
REF = 115
BANDS = [(0, 10, "P_0_10"), (11, 20, "P_11_20"), (21, 30, "P_21_30"), (31, 40, "P_31_40"), (41, 50, "P_41_50"), (51, 999, "P_51UP")]


def rings_to_geom(rings):
    """ArcGIS rings（外環順時針、孔逆時針）→ shapely。"""
    outers, holes = [], []
    for r in rings:
        if len(r) < 4:
            continue
        p = Polygon(r)
        if p.is_empty:
            continue
        # shapely 的 area 為正；方向用 shoelace 判斷
        x, y = np.array(r)[:, 0], np.array(r)[:, 1]
        signed = 0.5 * np.sum(x[:-1] * y[1:] - x[1:] * y[:-1])
        (outers if signed < 0 else holes).append(p.buffer(0))
    if not outers:
        outers, holes = holes, []
    geom = MultiPolygon(outers) if len(outers) > 1 else outers[0]
    for h in holes:
        geom = geom.difference(h)
    return geom


def wmedian(v, w):
    o = np.argsort(v)
    v, w = np.asarray(v)[o], np.asarray(w)[o]
    c = np.cumsum(w)
    return float(v[np.searchsorted(c, c[-1] / 2.0)])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    recs, geoms = [], []
    for f in sorted(glob.glob(str(RAW / "page_*.json"))):
        j = json.load(open(f, encoding="utf-8"))
        for ft in j["features"]:
            recs.append(ft["attributes"])
            geoms.append(rings_to_geom(ft["geometry"]["rings"]))
    g = gpd.GeoDataFrame(pd.DataFrame(recs), geometry=geoms, crs=3826)
    assert len(g) == 152684 and g["OBJECTID"].is_unique, "筆數不符"
    print("地號面", len(g), "；無效幾何", (~g.is_valid).sum())

    bnd = gpd.read_file(BND, encoding="utf-8")[["TOWNID", "TOWNNAME", "geometry"]].to_crs(3826)
    pts = g[["OBJECTID", "geometry"]].copy()
    pts["geometry"] = g.representative_point()
    j = gpd.sjoin(pts, bnd[["TOWNNAME", "geometry"]], how="left", predicate="within")
    j = j[~j.index.duplicated()]
    miss = j["TOWNNAME"].isna()
    if miss.any():
        near = gpd.sjoin_nearest(pts[miss.values], bnd[["TOWNNAME", "geometry"]], how="left")
        near = near[~near.index.duplicated()]
        j.loc[miss, "TOWNNAME"] = near["TOWNNAME"]
        print("界外以最近行政區歸屬：", int(miss.sum()), "個")
    g["TOWNNAME"] = j["TOWNNAME"]
    assert g["TOWNNAME"].notna().all()

    g = g.rename(columns={"KCNT": "SECTION", "LandNo": "LANDNO", "fageavg": "AGE_AVG", "fagemax": "AGE_MAX", "fagemin": "AGE_MIN",
                          "ct": "N_BLD", "sumdd08": "BLD_AREA"})
    g["AGE_55"] = (g["AGE_AVG"] == 55).astype(int)
    parcel_cols = ["TOWNNAME", "SECTION", "LANDNO", "THEKEY", "AGE_AVG", "AGE_MAX", "AGE_MIN", "N_BLD", "BLD_AREA", "AGE_55", "geometry"]
    parcels = g[parcel_cols]
    parcels.to_file(OUT / "臺北市地號_建物屋齡.shp", driver="ESRI Shapefile", encoding="utf-8")

    rows = []
    for t, d in g.groupby("TOWNNAME"):
        w = d["N_BLD"].to_numpy(float)
        d55 = d[d["AGE_55"] == 0]
        row = {"TOWNNAME": t, "N_PARCEL": len(d), "N_BLD": int(d["N_BLD"].sum()), "BLD_AREA": round(d["BLD_AREA"].sum() / 1e4, 1),
               "AGE_MED": wmedian(d["AGE_AVG"], w), "AGE_AVG": round(float(np.average(d["AGE_AVG"], weights=w)), 1),
               "AGE_MED_P": float(d["AGE_AVG"].median()),
               "AGE_MED_A": wmedian(d["AGE_AVG"], d["BLD_AREA"].clip(lower=0.01).to_numpy(float)),
               "AGE_MED_X55": wmedian(d55["AGE_AVG"], d55["N_BLD"].to_numpy(float)),
               "P_AGE55": round(float(np.average(d["AGE_55"], weights=w)) * 100, 1)}
        for lo, hi, name in BANDS:
            row[name] = round(float(np.average(d["AGE_AVG"].between(lo, hi), weights=w)) * 100, 1)
        row["P_GE41"] = round(row["P_41_50"] + row["P_51UP"], 1)
        rows.append(row)
    st = pd.DataFrame(rows)
    gd = bnd.merge(st, on="TOWNNAME")
    gd["REF_YEAR"] = 2026
    assert len(gd) == 12
    gd.to_file(OUT / "臺北市行政區_現況屋齡.shp", driver="ESRI Shapefile", encoding="utf-8")
    gd.drop(columns="geometry").to_csv(OUT / "行政區現況屋齡統計.csv", index=False, encoding="utf-8-sig")
    desc = {"TOWNID": "行政區代碼", "TOWNNAME": "行政區", "N_PARCEL": "地號數（圖層內有建物統計者）", "N_BLD": "建物筆數合計（ct）", "BLD_AREA": "建物面積合計（萬㎡，sumdd08）",
            "AGE_MED": "屋齡中位數（年，以建物筆數加權，2026 為基準）", "AGE_AVG": "屋齡平均（年，建物筆數加權）", "AGE_MED_P": "屋齡中位數（以地號計，不加權）",
            "AGE_MED_A": "屋齡中位數（以建物面積加權）", "AGE_MED_X55": "屋齡中位數（扣除屋齡 55 的地號，建物筆數加權）", "P_AGE55": "屋齡剛好 55 年的建物占比%（疑似預設值）",
            "P_0_10": "屋齡 0～10 年占建物%", "P_11_20": "11～20 年占建物%", "P_21_30": "21～30 年占建物%", "P_31_40": "31～40 年占建物%", "P_41_50": "41～50 年占建物%",
            "P_51UP": "51 年以上占建物%", "P_GE41": "41 年以上占建物%", "REF_YEAR": "屋齡基準年（推定）"}
    pd.DataFrame({"欄位": list(desc), "說明": list(desc.values())}).to_csv(OUT / "欄位說明_行政區.csv", index=False, encoding="utf-8-sig")
    print(gd.drop(columns="geometry").set_index("TOWNNAME").round(1).to_string())
    print("全市：建物", int(g["N_BLD"].sum()), "地號", len(g), "屋齡中位數", wmedian(g["AGE_AVG"], g["N_BLD"].to_numpy(float)),
          "屋齡 55 占建物%", round(float(np.average(g["AGE_55"], weights=g["N_BLD"])) * 100, 1))


if __name__ == "__main__":
    main()
