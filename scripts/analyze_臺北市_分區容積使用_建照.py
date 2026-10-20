"""臺北市「分區容積率（開發強度分級）」× 建造執照 → 分區塊容積使用狀況（試作）。

樓地板估法（依使用者指定）：地上樓地板 ＝ 建築面積 × 地上層數（建照）；另以樓層明細加總（EST_FA2）做對照。
流程：
  1. 建照（新建、改建；增建與修建只加部分面積，不採用）依 地段號 對到 BuildStat_Fage 地號面（段名＋地號 8 碼）；
     同一地號只取「最近一張」建照；一張建照涵蓋多個地號時，樓地板依地號面積比例分配到各地號。
  2. 地號面與分區塊（分區法定總樓地板_開發強度_v2_data.taipei.gpkg）交集，樓地板依交集面積占地號面積比例分配到分區塊。
  3. 分區塊使用率 ＝ 估計地上樓地板 ÷ 法定總樓地板；只算有法定容積率的分區塊。
  4. 涵蓋率 ＝ 有建照對應的地號與分區交集面積 ÷ 分區內「現況有建物」的地號面積（BuildStat_Fage，ct>0）。
  限制：建照只涵蓋民國 90～114 年發照，之前蓋的建物不在內，使用率偏低、不能當總使用率；詳見輸出說明。
輸入：資料庫/原始檔/臺北市歷年建造執照摘要/建照_*.csv（先跑 parse_臺北市歷年建造執照摘要.py）、BuildStat_Fage 分頁、地籍成果/台北市開發強度 gpkg
輸出：案件/臺北市_不動產交易分析/分區容積使用/分區塊_容積使用狀況_建照.shp 與 行政區_容積使用狀況.xlsx（唯一一張表）
執行：python scripts/analyze_臺北市_分區容積使用_建照.py
"""
import glob
import importlib.util
import json
import sys
import time
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("age", ROOT / "scripts" / "build_臺北市_行政區屋齡_地政局圖層.py")
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
SRCKIND = "使照" if "使照" in sys.argv[1:] else "建照"  # 參數「使照」＝改用臺北市歷年使用執照摘要；預設為建造執照摘要
BP = ROOT / "資料庫" / "原始檔" / ("臺北市歷年使用執照摘要" if SRCKIND == "使照" else "臺北市歷年建造執照摘要")
ZONE = ROOT.parent / "地籍成果" / "台北市開發強度" / "台北市分區法定總樓地板_開發強度_v2_data.taipei.gpkg"
OUT = ROOT / "案件" / "臺北市_不動產交易分析" / "分區容積使用" / ("使照版" if SRCKIND == "使照" else "")
CACHE = OUT / "_cache_overlay.pkl"


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def load_parcels():
    recs, geoms = [], []
    for f in sorted(glob.glob(str(M.RAW / "page_*.json"))):
        for ft in json.load(open(f, encoding="utf-8"))["features"]:
            a = ft["attributes"]
            recs.append({"key": a["KCNT"] + "|" + a["AA49"], "ct": a["ct"], "OBJECTID": a["OBJECTID"]})
            geoms.append(M.rings_to_geom(ft["geometry"]["rings"]))
    g = gpd.GeoDataFrame(pd.DataFrame(recs), geometry=geoms, crs=3826)
    g["geometry"] = g.geometry.buffer(0)
    return g


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    zones = gpd.read_file(ZONE, layer="分區法定總樓地板").to_crs(3826)
    zones["geometry"] = zones.geometry.buffer(0)
    zones = zones.rename(columns={"OBJECTID": "ZID"})[["ZID", "編號", "使用分區", "行政區_判定", "建蔽率", "容積率", "面積_m2", "法定總樓地板_m2", "geometry"]]
    log("分區塊", len(zones))
    parcels = load_parcels()
    parcels["p_area"] = parcels.area
    log("地號面", len(parcels))
    # 1. 建照 → 地號
    L = pd.read_csv(BP / f"{SRCKIND}_層級.csv", dtype={"執照號碼": str, "發照日期": str})
    X = pd.read_csv(BP / f"{SRCKIND}_地號展開.csv", dtype={"地號8碼": str, "執照號碼": str})
    L = L[L["類別"].isin(["新建", "改建"]) & L["地上樓地板_估"].notna()]
    X["key"] = X["段名"] + "|" + X["地號8碼"]
    X = X.merge(L[["執照號碼", "發照日期", "地上樓地板_估", "地上樓地板_明細"]], on="執照號碼")
    X = X.merge(parcels[["key", "p_area"]], on="key", how="left")
    n_all = X["key"].nunique(); n_hit = X.dropna(subset=["p_area"])["key"].nunique()
    log(f"建照（新建、改建）地號 {n_all:,}，對到地號面 {n_hit:,}（{n_hit / n_all:.1%}）")
    Xm = X.dropna(subset=["p_area"]).sort_values("發照日期", ascending=False).drop_duplicates("key")  # 每地號取最近一張
    Xm["w"] = Xm["p_area"] / Xm.groupby("執照號碼")["p_area"].transform("sum")
    Xm["fa"] = Xm["地上樓地板_估"] * Xm["w"]
    Xm["fa2"] = Xm["地上樓地板_明細"].fillna(Xm["地上樓地板_估"]) * Xm["w"]
    Xm = Xm.drop_duplicates("key")
    log("有建照樓地板的地號", len(Xm), "；樓地板合計(萬㎡)", round(Xm["fa"].sum() / 1e4, 1))
    # 2. 交集
    if CACHE.exists():
        ov = pd.read_pickle(CACHE)
    else:
        ov = gpd.overlay(parcels[["key", "ct", "p_area", "geometry"]], zones[["ZID", "geometry"]], how="intersection", keep_geom_type=True)
        ov["ov_area"] = ov.area
        ov = pd.DataFrame(ov.drop(columns="geometry"))
        ov.to_pickle(CACHE)
    log("交集片數", len(ov))
    ov["frac"] = (ov["ov_area"] / ov["p_area"]).clip(upper=1)
    ov = ov.merge(Xm[["key", "fa", "fa2"]], on="key", how="left")
    ov["has_lic"] = ov["fa"].notna()
    agg = pd.DataFrame({
        "EST_FA": (ov["fa"].fillna(0) * ov["frac"]).groupby(ov["ZID"]).sum(),
        "EST_FA2": (ov["fa2"].fillna(0) * ov["frac"]).groupby(ov["ZID"]).sum(),
        "N_LIC_PCL": ov[ov["has_lic"]].groupby("ZID")["key"].nunique(),
        "BLD_AREA": ov[ov["ct"] > 0].groupby("ZID")["ov_area"].sum(),
        "LIC_AREA": ov[ov["has_lic"] & (ov["ct"] > 0)].groupby("ZID")["ov_area"].sum()})
    z = zones.merge(agg, left_on="ZID", right_index=True, how="left").fillna({"EST_FA": 0, "EST_FA2": 0, "N_LIC_PCL": 0, "BLD_AREA": 0, "LIC_AREA": 0})
    has = z["法定總樓地板_m2"].notna() & (z["法定總樓地板_m2"] > 0)
    z["USE_RATE"] = np.where(has, z["EST_FA"] / z["法定總樓地板_m2"] * 100, np.nan).round(1)
    z["USE_RATE2"] = np.where(has, z["EST_FA2"] / z["法定總樓地板_m2"] * 100, np.nan).round(1)
    z["FAR_NOW"] = (z["EST_FA"] / z["面積_m2"] * 100).round(1)
    z["COV_PCT"] = np.where(z["BLD_AREA"] > 0, z["LIC_AREA"] / z["BLD_AREA"] * 100, np.nan).round(1)
    z["BLD_PCT"] = (z["BLD_AREA"] / z["面積_m2"] * 100).round(1)
    cls = pd.cut(z["USE_RATE"], [-0.1, 0.0, 25, 50, 75, 100, 1e9], labels=["0 無建照對應", "1 0-25%", "2 25-50%", "3 50-75%", "4 75-100%", "5 超過100%"])
    z["USE_CLS"] = cls.astype(object).where(has, "無法定值")
    out = z.rename(columns={"編號": "ZONE_NO", "使用分區": "ZONE_NAME", "行政區_判定": "TOWN", "建蔽率": "BCR", "容積率": "FAR_LEG", "面積_m2": "AREA_M2", "法定總樓地板_m2": "LEG_FA"})
    cols = ["ZID", "ZONE_NO", "ZONE_NAME", "TOWN", "AREA_M2", "BCR", "FAR_LEG", "LEG_FA", "EST_FA", "EST_FA2", "N_LIC_PCL", "USE_RATE", "USE_RATE2", "FAR_NOW", "COV_PCT", "BLD_PCT", "USE_CLS", "geometry"]
    for c in ("AREA_M2", "LEG_FA", "EST_FA", "EST_FA2"):
        out[c] = out[c].round(1)
    out[cols].to_file(OUT / "分區塊_容積使用狀況_建照.shp", driver="ESRI Shapefile", encoding="utf-8")
    # 3. 行政區彙總（唯一一張表）
    rows = []
    for d, x in out[has.values].groupby("TOWN"):
        rows.append({"行政區": d, "有法定值分區塊": len(x), "法定總樓地板_萬㎡": x["LEG_FA"].sum() / 1e4, "估計地上樓地板_萬㎡": x["EST_FA"].sum() / 1e4,
                     "使用率%": x["EST_FA"].sum() / x["LEG_FA"].sum() * 100, "使用率%（樓層明細版）": x["EST_FA2"].sum() / x["LEG_FA"].sum() * 100,
                     "有建照對應的分區塊占比%": (x["N_LIC_PCL"] > 0).mean() * 100,
                     "建照涵蓋率%（地號面積）": x["COV_PCT"].mul(x["BLD_PCT"] * x["AREA_M2"]).sum() / (x["BLD_PCT"] * x["AREA_M2"]).sum() if x["BLD_PCT"].notna().any() else np.nan})
    S = pd.DataFrame(rows).sort_values("使用率%", ascending=False)
    allx = out[has.values]
    tot = {"行政區": "全市", "有法定值分區塊": len(allx), "法定總樓地板_萬㎡": allx["LEG_FA"].sum() / 1e4, "估計地上樓地板_萬㎡": allx["EST_FA"].sum() / 1e4,
           "使用率%": allx["EST_FA"].sum() / allx["LEG_FA"].sum() * 100, "使用率%（樓層明細版）": allx["EST_FA2"].sum() / allx["LEG_FA"].sum() * 100,
           "有建照對應的分區塊占比%": (allx["N_LIC_PCL"] > 0).mean() * 100,
           "建照涵蓋率%（地號面積）": allx["COV_PCT"].mul(allx["BLD_PCT"] * allx["AREA_M2"]).sum() / (allx["BLD_PCT"] * allx["AREA_M2"]).sum()}
    S = pd.concat([S, pd.DataFrame([tot])], ignore_index=True)
    wb = Workbook(); ws = wb.active; ws.title = "行政區容積使用狀況"
    ws.append([f"臺北市各行政區分區容積使用狀況（試作；估計地上樓地板＝建築面積×地上層數，{'使用執照' if SRCKIND == '使照' else '建造執照'}民國 90～114 年）"])
    ws.append(list(S.columns))
    for _, r in S.iterrows():
        ws.append([r["行政區"], int(r["有法定值分區塊"])] + [round(float(r[c]), 1) for c in S.columns[2:]])
    ws.append(["註：僅計有法定總樓地板的分區塊；建照只涵蓋民國 90 年以後發照者，之前興建的建物不在內，使用率偏低，僅供比較與試作；增建、修建不計；"
               "每地號取最近一張新建或改建建照，多地號建照依地號面積分配；涵蓋率＝有建照對應的地號面積÷現況有建物的地號面積。"])
    hdr = PatternFill("solid", fgColor="E8EDF4")
    for c in ws[2]:
        c.font = Font(bold=True); c.fill = hdr; c.alignment = Alignment(horizontal="center", wrap_text=True)
    ws["A1"].font = Font(bold=True, size=12)
    for r in ws.iter_rows(min_row=3, max_row=2 + len(S)):
        for c in r[1:]:
            c.alignment = Alignment(horizontal="right"); c.number_format = "#,##0.0" if c.column > 2 else "#,##0"
    for ci in range(1, len(S.columns) + 1):
        ws.column_dimensions[get_column_letter(ci)].width = 16
    ws.freeze_panes = "B3"
    wb.save(OUT / "行政區_容積使用狀況.xlsx")
    log("完成")
    print(S.round(1).to_string(index=False))
    print("使用率分級（分區塊數）", out["USE_CLS"].value_counts().to_dict())


if __name__ == "__main__":
    main()
