"""臺北市「分區容積率（開發強度分級）」× 建物套繪圖（建築資訊e點通）→ 分區塊容積使用率。

資料：建物套繪圖-big5_build-All.gpkg（299,651 塊；NAME＝建物者 90,447 塊，其中有使照樓地板 floor_area 的約 49.6 千塊，使照年民國 45～115 年）。
  floor_area＝該建物所屬使用執照的樓地板面積（同一張使照有多塊建物時各塊相同，本檔依建物面積比例分攤）。
做法：建物面與分區塊交集，樓地板依交集面積占建物面積比例分配；使用率＝分配後樓地板 ÷ 法定總樓地板（只算有法定值的分區塊）。
  另以「建築面積×樓層數」（bud_area×bud_floor）估一個對照版（EST_FA2）。涵蓋率＝有使照樓地板的建物面積 ÷ 分區內全部建物面積。
輸入：G:\\我的雲端硬碟\\20261015\\台北市建物(來源-建築資訊e點通)…\\建物套繪圖-big5_build-All.gpkg；分區：地籍成果/台北市開發強度 gpkg
輸出：案件/臺北市_不動產交易分析/分區容積使用/建物套繪版/分區塊_容積使用狀況_建物套繪.shp、行政區_容積使用狀況_建物套繪.xlsx（唯一一張表）
執行：python scripts/analyze_臺北市_分區容積使用_建物套繪.py
"""
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
SRC = r"G:\我的雲端硬碟\20261015\台北市建物(來源-建築資訊e點通)-20261015T142147Z-1-001\台北市建物(來源-建築資訊e點通)\建物套繪圖-big5_build-All.gpkg"
ZONE = ROOT.parent / "地籍成果" / "台北市開發強度" / "台北市分區法定總樓地板_開發強度_v2_data.taipei.gpkg"
BASE = ROOT / "案件" / "臺北市_不動產交易分析" / "分區容積使用"
OUT = BASE / "建物套繪版"


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    b = gpd.read_file(SRC)
    b = b[b["NAME"] == "建物"].copy()
    b["geometry"] = b.geometry.buffer(0)
    b["b_area"] = b.area
    b["fa_lic"] = pd.to_numeric(b["floor_area"], errors="coerce")
    b["lic"] = b["lic_no"].fillna("")
    ok = (b["lic"] != "") & (b["fa_lic"] > 0)
    b["fa"] = np.nan
    b.loc[ok, "fa"] = b.loc[ok, "fa_lic"] * b.loc[ok, "b_area"] / b[ok].groupby("lic")["b_area"].transform("sum")
    b["fa2"] = pd.to_numeric(b["bud_area"], errors="coerce") * pd.to_numeric(b["bud_floor"], errors="coerce")
    b["fa2"] = b["fa2"].where(b["fa2"] > 0)
    log("建物面", len(b), "；有使照樓地板", int(ok.sum()), "；使照張數", b.loc[ok, "lic"].nunique(), "；分攤後樓地板合計(萬㎡)", round(b["fa"].sum() / 1e4, 1))
    # 與使照資料檢驗 floor_area 的口徑（使照民國 90～114）
    try:
        L = pd.read_csv(ROOT / "資料庫" / "原始檔" / "臺北市歷年使用執照摘要" / "使照_層級.csv", dtype={"執照號碼": str})
        L["lic"] = L["執照號碼"].str.replace("使字第", "-", regex=False).str.replace("號", "", regex=False)
        v = b[ok].drop_duplicates("lic")[["lic", "fa_lic"]].merge(L[["lic", "地上樓地板_明細", "地上樓地板_估"]], on="lic")
        v = v[v["地上樓地板_明細"] > 0]
        r = v["fa_lic"] / v["地上樓地板_明細"]
        log("floor_area ÷ 使照地上樓地板(明細)：n", len(v), "中位數", round(r.median(), 3), "P25", round(r.quantile(.25), 3), "P75", round(r.quantile(.75), 3))
    except Exception as e:  # noqa: BLE001
        log("使照檢驗略過", e)
    zones = gpd.read_file(ZONE, layer="分區法定總樓地板").to_crs(3826)
    zones["geometry"] = zones.geometry.buffer(0)
    zones = zones.rename(columns={"OBJECTID": "ZID"})[["ZID", "編號", "使用分區", "行政區_判定", "建蔽率", "容積率", "面積_m2", "法定總樓地板_m2", "geometry"]]
    ov = gpd.overlay(b[["fa", "fa2", "b_area", "geometry"]].reset_index(drop=True), zones[["ZID", "geometry"]], how="intersection", keep_geom_type=True)
    ov["frac"] = (ov.area / ov["b_area"]).clip(upper=1)
    ov = pd.DataFrame(ov.drop(columns="geometry"))
    ov["ov_area"] = ov["frac"] * ov["b_area"]
    log("交集片", len(ov))
    agg = pd.DataFrame({"EST_FA": (ov["fa"].fillna(0) * ov["frac"]).groupby(ov["ZID"]).sum(), "EST_FA2": (ov["fa2"].fillna(0) * ov["frac"]).groupby(ov["ZID"]).sum(),
                        "BLD_AREA": ov.groupby("ZID")["ov_area"].sum(), "LIC_AREA": ov[ov["fa"].notna()].groupby("ZID")["ov_area"].sum()})
    z = zones.merge(agg, left_on="ZID", right_index=True, how="left").fillna({"EST_FA": 0, "EST_FA2": 0, "BLD_AREA": 0, "LIC_AREA": 0})
    has = z["法定總樓地板_m2"].notna() & (z["法定總樓地板_m2"] > 0)
    z["USE_RATE"] = np.where(has, z["EST_FA"] / z["法定總樓地板_m2"] * 100, np.nan).round(1)
    z["USE_RATE2"] = np.where(has, z["EST_FA2"] / z["法定總樓地板_m2"] * 100, np.nan).round(1)
    z["FAR_NOW"] = (z["EST_FA"] / z["面積_m2"] * 100).round(1)
    z["COV_PCT"] = np.where(z["BLD_AREA"] > 0, z["LIC_AREA"] / z["BLD_AREA"] * 100, np.nan).round(1)
    z["BLD_PCT"] = (z["BLD_AREA"] / z["面積_m2"] * 100).round(1)
    cls = pd.cut(z["USE_RATE"], [-0.1, 0.0, 25, 50, 75, 100, 1e9], labels=["0 無使照樓地板", "1 0-25%", "2 25-50%", "3 50-75%", "4 75-100%", "5 超過100%"])
    z["USE_CLS"] = cls.astype(object).where(has, "無法定值")
    out = z.rename(columns={"編號": "ZONE_NO", "使用分區": "ZONE_NAME", "行政區_判定": "TOWN", "建蔽率": "BCR", "容積率": "FAR_LEG", "面積_m2": "AREA_M2", "法定總樓地板_m2": "LEG_FA"})
    for c in ("AREA_M2", "LEG_FA", "EST_FA", "EST_FA2"):
        out[c] = out[c].round(1)
    cols = ["ZID", "ZONE_NO", "ZONE_NAME", "TOWN", "AREA_M2", "BCR", "FAR_LEG", "LEG_FA", "EST_FA", "EST_FA2", "USE_RATE", "USE_RATE2", "FAR_NOW", "COV_PCT", "BLD_PCT", "USE_CLS", "geometry"]
    out[cols].to_file(OUT / "分區塊_容積使用狀況_建物套繪.shp", driver="ESRI Shapefile", encoding="utf-8")
    allx = out[has.values]

    def row(name, x):
        w = x["BLD_AREA"].sum()
        return {"行政區": name, "有法定值分區塊": len(x), "法定總樓地板_萬㎡": x["LEG_FA"].sum() / 1e4, "使照樓地板_萬㎡": x["EST_FA"].sum() / 1e4,
                "使用率%": x["EST_FA"].sum() / x["LEG_FA"].sum() * 100, "使用率%（建築面積×樓層版）": x["EST_FA2"].sum() / x["LEG_FA"].sum() * 100,
                "使用率超過100%的分區塊占比%": (x["USE_RATE"] > 100).mean() * 100,
                "使照涵蓋率%（建物面積）": (x["COV_PCT"].fillna(0) * x["BLD_AREA"]).sum() / w if w else np.nan}
    S = pd.DataFrame([row(d, x) for d, x in allx.groupby("TOWN")]).sort_values("使用率%", ascending=False)
    S = pd.concat([S, pd.DataFrame([row("全市", allx)])], ignore_index=True)
    wb = Workbook(); ws = wb.active; ws.title = "行政區容積使用狀況"
    ws.append(["臺北市各行政區分區容積使用狀況（建物套繪圖〔建築資訊e點通〕使照樓地板；民國 45～115 年使照）"])
    ws.append(list(S.columns))
    for _, r_ in S.iterrows():
        ws.append([r_["行政區"], int(r_["有法定值分區塊"])] + [round(float(r_[c]), 1) for c in S.columns[2:]])
    ws.append(["註：僅計有法定總樓地板的分區塊；floor_area 為使照樓地板面積（口徑與使照地上樓地板的比較見輸出摘要），同張使照多塊建物依建物面積分攤；"
               "只有約五成建物有使照樓地板，涵蓋率欄為有使照樓地板的建物面積占比；落在無法定值分區的樓地板不計入。"])
    hdr = PatternFill("solid", fgColor="E8EDF4")
    for c in ws[2]:
        c.font = Font(bold=True); c.fill = hdr; c.alignment = Alignment(horizontal="center", wrap_text=True)
    ws["A1"].font = Font(bold=True, size=12)
    for r_ in ws.iter_rows(min_row=3, max_row=2 + len(S)):
        for c in r_[1:]:
            c.alignment = Alignment(horizontal="right"); c.number_format = "#,##0.0" if c.column > 2 else "#,##0"
    for ci in range(1, len(S.columns) + 1):
        ws.column_dimensions[get_column_letter(ci)].width = 17
    ws.freeze_panes = "B3"
    wb.save(OUT / "行政區_容積使用狀況_建物套繪.xlsx")
    log("完成")
    print(S.round(1).to_string(index=False))
    print("使用率分級（分區塊數）", out["USE_CLS"].value_counts().to_dict())


if __name__ == "__main__":
    main()
