"""臺北市「分區容積率（開發強度分級）」× BuildStat_Fage 的 sumdd08 → 分區塊容積使用狀況。

sumdd08＝地政局圖層每個地號上建物的樓地板面積合計（含地下室與停車空間；經使照比對約為地上＋地下樓地板的 1.0～1.1 倍），涵蓋全部現況有建物的地號。
做法：地號面與分區塊交集（沿用 分區容積使用/_cache_overlay.pkl，由 analyze_臺北市_分區容積使用_建照.py 產生），
  sumdd08 依交集面積占地號面積比例分配到分區塊；使用率＝分配後樓地板 ÷ 法定總樓地板（只算有法定值的分區塊）。
限制：sumdd08 含地下層，使用率偏高，不能直接與「只算地上」的法定容積比較；落在無法定值分區（公園、保護區等）的樓地板不計入行政區使用率。
輸出：案件/臺北市_不動產交易分析/分區容積使用/sumdd08版/分區塊_容積使用狀況_sumdd08.shp 與 行政區_容積使用狀況_sumdd08.xlsx（唯一一張表）
執行：python scripts/analyze_臺北市_分區容積使用_sumdd08.py
"""
import glob
import json
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
RAW = ROOT / "資料庫" / "原始檔" / "臺北市建物屋齡_BuildStat_Fage"
ZONE = ROOT.parent / "地籍成果" / "台北市開發強度" / "台北市分區法定總樓地板_開發強度_v2_data.taipei.gpkg"
BASE = ROOT / "案件" / "臺北市_不動產交易分析" / "分區容積使用"
OUT = BASE / "sumdd08版"


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for f in sorted(glob.glob(str(RAW / "page_*.json"))):
        for ft in json.load(open(f, encoding="utf-8"))["features"]:
            a = ft["attributes"]
            rows.append({"key": a["KCNT"] + "|" + a["AA49"], "sumdd08": a["sumdd08"] or 0.0})
    P = pd.DataFrame(rows)
    ov = pd.read_pickle(BASE / "_cache_overlay.pkl")
    ov["frac"] = (ov["ov_area"] / ov["p_area"]).clip(upper=1)
    ov = ov.merge(P, on="key", how="left")
    log("地號", len(P), "；sumdd08 合計(萬㎡)", round(P["sumdd08"].sum() / 1e4, 1), "；交集片", len(ov))
    zones = gpd.read_file(ZONE, layer="分區法定總樓地板").to_crs(3826)
    zones = zones.rename(columns={"OBJECTID": "ZID"})[["ZID", "編號", "使用分區", "行政區_判定", "建蔽率", "容積率", "面積_m2", "法定總樓地板_m2", "geometry"]]
    agg = pd.DataFrame({"NOW_FA": (ov["sumdd08"] * ov["frac"]).groupby(ov["ZID"]).sum(), "N_PCL": ov[ov["ct"] > 0].groupby("ZID")["key"].nunique(),
                        "BLD_AREA": ov[ov["ct"] > 0].groupby("ZID")["ov_area"].sum()})
    z = zones.merge(agg, left_on="ZID", right_index=True, how="left").fillna({"NOW_FA": 0, "N_PCL": 0, "BLD_AREA": 0})
    has = z["法定總樓地板_m2"].notna() & (z["法定總樓地板_m2"] > 0)
    z["USE_RATE"] = np.where(has, z["NOW_FA"] / z["法定總樓地板_m2"] * 100, np.nan).round(1)
    z["FAR_NOW"] = (z["NOW_FA"] / z["面積_m2"] * 100).round(1)
    z["BLD_PCT"] = (z["BLD_AREA"] / z["面積_m2"] * 100).round(1)
    cls = pd.cut(z["USE_RATE"], [-0.1, 0.0, 25, 50, 75, 100, 1e9], labels=["0 無建物", "1 0-25%", "2 25-50%", "3 50-75%", "4 75-100%", "5 超過100%"])
    z["USE_CLS"] = cls.astype(object).where(has, "無法定值")
    out = z.rename(columns={"編號": "ZONE_NO", "使用分區": "ZONE_NAME", "行政區_判定": "TOWN", "建蔽率": "BCR", "容積率": "FAR_LEG", "面積_m2": "AREA_M2", "法定總樓地板_m2": "LEG_FA"})
    for c in ("AREA_M2", "LEG_FA", "NOW_FA"):
        out[c] = out[c].round(1)
    cols = ["ZID", "ZONE_NO", "ZONE_NAME", "TOWN", "AREA_M2", "BCR", "FAR_LEG", "LEG_FA", "NOW_FA", "N_PCL", "USE_RATE", "FAR_NOW", "BLD_PCT", "USE_CLS", "geometry"]
    out[cols].to_file(OUT / "分區塊_容積使用狀況_sumdd08.shp", driver="ESRI Shapefile", encoding="utf-8")
    inzone = out.loc[has.values, "NOW_FA"].sum() / out["NOW_FA"].sum() * 100
    log(f"分配到分區塊的樓地板合計(萬㎡) {out['NOW_FA'].sum() / 1e4:.1f}；落在有法定值分區的比例 {inzone:.1f}%")
    allx = out[has.values]
    def row(name, x):
        return {"行政區": name, "有法定值分區塊": len(x), "法定總樓地板_萬㎡": x["LEG_FA"].sum() / 1e4, "現況總樓地板_萬㎡（sumdd08）": x["NOW_FA"].sum() / 1e4,
                "使用率%": x["NOW_FA"].sum() / x["LEG_FA"].sum() * 100, "使用率超過100%的分區塊占比%": (x["USE_RATE"] > 100).mean() * 100,
                "無建物分區塊占比%": (x["N_PCL"] == 0).mean() * 100}
    S = pd.DataFrame([row(d, x) for d, x in allx.groupby("TOWN")]).sort_values("使用率%", ascending=False)
    S = pd.concat([S, pd.DataFrame([row("全市", allx)])], ignore_index=True)
    wb = Workbook(); ws = wb.active; ws.title = "行政區容積使用狀況"
    ws.append(["臺北市各行政區分區容積使用狀況（現況總樓地板＝BuildStat_Fage sumdd08，含地下室與停車空間）"])
    ws.append(list(S.columns))
    for _, r in S.iterrows():
        ws.append([r["行政區"], int(r["有法定值分區塊"])] + [round(float(r[c]), 1) for c in S.columns[2:]])
    ws.append(["註：僅計有法定總樓地板的分區塊；sumdd08 含地下層，與只計地上的法定容積比較會偏高（經使照比對約為地上＋地下樓地板的 1.0～1.1 倍）；"
               "樓地板依地號與分區交集面積比例分配；落在無法定值分區（公園、保護區等）的樓地板不計入。"])
    hdr = PatternFill("solid", fgColor="E8EDF4")
    for c in ws[2]:
        c.font = Font(bold=True); c.fill = hdr; c.alignment = Alignment(horizontal="center", wrap_text=True)
    ws["A1"].font = Font(bold=True, size=12)
    for r in ws.iter_rows(min_row=3, max_row=2 + len(S)):
        for c in r[1:]:
            c.alignment = Alignment(horizontal="right"); c.number_format = "#,##0.0" if c.column > 2 else "#,##0"
    for ci in range(1, len(S.columns) + 1):
        ws.column_dimensions[get_column_letter(ci)].width = 17
    ws.freeze_panes = "B3"
    wb.save(OUT / "行政區_容積使用狀況_sumdd08.xlsx")
    print(S.round(1).to_string(index=False))
    print("使用率分級（分區塊數）", out["USE_CLS"].value_counts().to_dict())


if __name__ == "__main__":
    main()
