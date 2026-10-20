"""用使用執照資料推算 sumdd08 與「地上樓地板」的比例，回推全部地號的地上樓地板，再算分區塊／行政區容積使用率。

校準：單一地號、單一使照、新建、且 BuildStat_Fage 的屋齡與使照竣工年相符（差 ≤1 年）的地號，
  比例 g ＝ 使照地上樓地板（樓層明細，不含地下與突出物） ÷ sumdd08；依「地上層數（DD13H）×屋齡帶」取中位數，樣本不足（<30）的格子退回屋齡帶或層數帶的中位數。
  g 同時吸收了地下層、停車空間、陽台、公設等「sumdd08 有而使照地上樓層沒有」的部分。
使照來源：taipei-house-age-map 的使用執照 XML（至民國 105 年 10 月，含較老建物）＋ 臺北市歷年使用執照摘要（民國 90～114 年）。
回推：每個地號地上樓地板（推算）＝ sumdd08 × g；再依 分區容積使用/_cache_overlay.pkl 的交集比例分配到分區塊。
輸出：案件/臺北市_不動產交易分析/分區容積使用/sumdd08地上推算版/分區塊_容積使用狀況_sumdd08地上推算.shp、行政區_容積使用狀況_sumdd08地上推算.xlsx（唯一一張表）
執行：python scripts/analyze_sumdd08_地上樓地板推算.py
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
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("cmp", ROOT / "scripts" / "compare_sumdd08_使照.py")
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)
RAW = ROOT / "資料庫" / "原始檔" / "臺北市建物屋齡_BuildStat_Fage"
NEW = ROOT / "資料庫" / "原始檔" / "臺北市歷年使用執照摘要"
ZONE = ROOT.parent / "地籍成果" / "台北市開發強度" / "台北市分區法定總樓地板_開發強度_v2_data.taipei.gpkg"
BASE = ROOT / "案件" / "臺北市_不動產交易分析" / "分區容積使用"
OUT = BASE / "sumdd08地上推算版"
FB = [(0, 3, "1-3層"), (4, 5, "4-5層"), (6, 8, "6-8層"), (9, 12, "9-12層"), (13, 20, "13-20層"), (21, 999, "21層以上")]
AB = [(0, 10, "0-10年"), (11, 25, "11-25年"), (26, 40, "26-40年"), (41, 999, "41年以上")]


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def band(v, bands):
    for lo, hi, lab in bands:
        if lo <= v <= hi:
            return lab
    return None


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    # 地號屬性
    rows = []
    for f in sorted(glob.glob(str(RAW / "page_*.json"))):
        for ft in json.load(open(f, encoding="utf-8"))["features"]:
            a = ft["attributes"]
            rows.append({"key": a["KCNT"] + "|" + a["AA49"], "sumdd08": a["sumdd08"] or 0.0, "floors": pd.to_numeric(a["DD13H"], errors="coerce"), "age": a["fageavg"], "ct": a["ct"]})
    P = pd.DataFrame(rows)
    # 使照（舊 XML＋新摘要）
    old = C.parse_licenses()
    old = old[(old["類別"] == "新建") | True].rename(columns={"id": "lic", "地上樓地板": "up", "地段": "seg", "地號8碼": "no8", "竣工": "done"})[["lic", "類別", "up", "地號數", "seg", "no8", "done"]]
    L = pd.read_csv(NEW / "使照_層級.csv", dtype={"執照號碼": str, "竣工日期": str})
    X = pd.read_csv(NEW / "使照_地號展開.csv", dtype={"地號8碼": str, "執照號碼": str})
    X1 = X.groupby("執照號碼").agg(seg=("段名", "first"), no8=("地號8碼", "first"))
    new = L.merge(X1, left_on="執照號碼", right_index=True, how="left").rename(columns={"執照號碼": "lic", "地上樓地板_明細": "up", "竣工日期": "done"})[["lic", "類別", "up", "地號數", "seg", "no8", "done"]]
    U = pd.concat([new, old[~old["lic"].isin(new["lic"])]], ignore_index=True)
    U["key"] = U["seg"].fillna("") + "|" + U["no8"].fillna("")
    cnt = U[U["地號數"] >= 1].groupby("key")["lic"].nunique()
    S = U[(U["地號數"] == 1) & (U["類別"] == "新建") & (U["up"] > 0)].copy()
    S = S[S["key"].map(cnt) == 1]
    S["yr"] = S["done"].map(lambda s: int(s[:-4]) + 1911 if isinstance(s, str) and len(s) >= 6 and s[:-4].isdigit() else np.nan)
    S = S.merge(P, on="key", how="inner")
    S = S[(S["sumdd08"] > 0) & S["floors"].notna() & S["yr"].notna() & ((S["age"] - (2026 - S["yr"])).abs() <= 1)]
    S["g"] = S["up"] / S["sumdd08"]
    S["fb"] = S["floors"].map(lambda v: band(v, FB)); S["ab"] = S["age"].map(lambda v: band(v, AB))
    log(f"校準樣本 {len(S):,} 個地號（使照 {S['lic'].nunique():,} 張）；g 中位數 {S['g'].median():.3f}，四分位 {S['g'].quantile(.25):.3f}～{S['g'].quantile(.75):.3f}")
    cell = S.groupby(["ab", "fb"])["g"].agg(["median", "size"])
    by_a = S.groupby("ab")["g"].median(); by_f = S.groupby("fb")["g"].median(); overall = S["g"].median()
    print("屋齡帶 g 中位數", by_a.round(3).to_dict()); print("層數帶 g 中位數", by_f.round(3).to_dict())
    print(cell.round(3).to_string())

    def gfun(ab, fb):
        if (ab, fb) in cell.index and cell.loc[(ab, fb), "size"] >= 30:
            return cell.loc[(ab, fb), "median"]
        if ab in by_a.index and fb in by_f.index:
            return float(np.sqrt(by_a[ab] * by_f[fb] / overall))  # 退回：兩個邊際中位數的相乘修正
        return overall
    P["fb"] = P["floors"].map(lambda v: band(v, FB) if pd.notna(v) else None); P["ab"] = P["age"].map(lambda v: band(v, AB))
    P["g"] = [gfun(a, f) for a, f in zip(P["ab"], P["fb"])]
    P["up_est"] = P["sumdd08"] * P["g"]
    log(f"全部地號 {len(P):,}；sumdd08 合計 {P['sumdd08'].sum() / 1e4:.0f} 萬㎡ → 推算地上 {P['up_est'].sum() / 1e4:.0f} 萬㎡（平均 g={P['up_est'].sum() / P['sumdd08'].sum():.3f}）")
    # 回測：校準地號用 gfun 推算 vs 使照實際（含個別誤差）
    S["pred"] = [gfun(a, f) * s for a, f, s in zip(S["ab"], S["fb"], S["sumdd08"])]
    err = (S["pred"] - S["up"]) / S["up"]
    log(f"回測（校準樣本內）：加總誤差 {(S['pred'].sum() / S['up'].sum() - 1) * 100:+.1f}%；個別地號相對誤差中位數 {err.abs().median() * 100:.0f}%，四分位 {err.quantile(.25) * 100:+.0f}%～{err.quantile(.75) * 100:+.0f}%")
    # 分區塊
    ov = pd.read_pickle(BASE / "_cache_overlay.pkl")
    ov["frac"] = (ov["ov_area"] / ov["p_area"]).clip(upper=1)
    ov = ov.merge(P[["key", "sumdd08", "up_est"]], on="key", how="left")
    zones = gpd.read_file(ZONE, layer="分區法定總樓地板").to_crs(3826)
    zones = zones.rename(columns={"OBJECTID": "ZID"})[["ZID", "編號", "使用分區", "行政區_判定", "建蔽率", "容積率", "面積_m2", "法定總樓地板_m2", "geometry"]]
    agg = pd.DataFrame({"NOW_FA": (ov["sumdd08"] * ov["frac"]).groupby(ov["ZID"]).sum(), "UP_FA": (ov["up_est"] * ov["frac"]).groupby(ov["ZID"]).sum()})
    z = zones.merge(agg, left_on="ZID", right_index=True, how="left").fillna({"NOW_FA": 0, "UP_FA": 0})
    has = z["法定總樓地板_m2"].notna() & (z["法定總樓地板_m2"] > 0)
    z["USE_ALL"] = np.where(has, z["NOW_FA"] / z["法定總樓地板_m2"] * 100, np.nan).round(1)
    z["USE_UP"] = np.where(has, z["UP_FA"] / z["法定總樓地板_m2"] * 100, np.nan).round(1)
    z["FAR_UP"] = (z["UP_FA"] / z["面積_m2"] * 100).round(1)
    cls = pd.cut(z["USE_UP"], [-0.1, 0.0, 25, 50, 75, 100, 1e9], labels=["0 無建物", "1 0-25%", "2 25-50%", "3 50-75%", "4 75-100%", "5 超過100%"])
    z["USE_CLS"] = cls.astype(object).where(has, "無法定值")
    out = z.rename(columns={"編號": "ZONE_NO", "使用分區": "ZONE_NAME", "行政區_判定": "TOWN", "建蔽率": "BCR", "容積率": "FAR_LEG", "面積_m2": "AREA_M2", "法定總樓地板_m2": "LEG_FA"})
    for c in ("AREA_M2", "LEG_FA", "NOW_FA", "UP_FA"):
        out[c] = out[c].round(1)
    out[["ZID", "ZONE_NO", "ZONE_NAME", "TOWN", "AREA_M2", "BCR", "FAR_LEG", "LEG_FA", "NOW_FA", "UP_FA", "USE_ALL", "USE_UP", "FAR_UP", "USE_CLS", "geometry"]].to_file(
        OUT / "分區塊_容積使用狀況_sumdd08地上推算.shp", driver="ESRI Shapefile", encoding="utf-8")
    allx = out[has.values]

    def row(name, x):
        return {"行政區": name, "有法定值分區塊": len(x), "法定總樓地板_萬㎡": x["LEG_FA"].sum() / 1e4, "sumdd08總樓地板_萬㎡": x["NOW_FA"].sum() / 1e4,
                "推算地上樓地板_萬㎡": x["UP_FA"].sum() / 1e4, "使用率%（sumdd08 總樓地板）": x["NOW_FA"].sum() / x["LEG_FA"].sum() * 100,
                "使用率%（推算地上）": x["UP_FA"].sum() / x["LEG_FA"].sum() * 100, "推算地上使用率超過100%的分區塊占比%": (x["USE_UP"] > 100).mean() * 100}
    T = pd.DataFrame([row(d, x) for d, x in allx.groupby("TOWN")]).sort_values("使用率%（推算地上）", ascending=False)
    T = pd.concat([T, pd.DataFrame([row("全市", allx)])], ignore_index=True)
    wb = Workbook(); ws = wb.active; ws.title = "行政區容積使用狀況"
    ws.append(["臺北市各行政區分區容積使用狀況（sumdd08 依使照比例回推地上樓地板）"])
    ws.append(list(T.columns))
    for _, r in T.iterrows():
        ws.append([r["行政區"], int(r["有法定值分區塊"])] + [round(float(r[c]), 1) for c in T.columns[2:]])
    ws.append([f"註：回推比例 g＝使照地上樓地板÷sumdd08，依地上層數×屋齡帶取中位數（校準樣本 {len(S):,} 個單一使照地號，全體中位數 {overall:.2f}）；全市平均 g＝{P['up_est'].sum() / P['sumdd08'].sum():.2f}；"
               "g 吸收地下層、停車空間、陽台、公設等差異；僅計有法定總樓地板的分區塊；校準樣本涵蓋各屋齡帶（" + "、".join(f"{k} {v:,} 筆" for k, v in S["ab"].value_counts().reindex([b[2] for b in AB]).items()) + "）。"])
    hdr = PatternFill("solid", fgColor="E8EDF4")
    for c in ws[2]:
        c.font = Font(bold=True); c.fill = hdr; c.alignment = Alignment(horizontal="center", wrap_text=True)
    ws["A1"].font = Font(bold=True, size=12)
    for r in ws.iter_rows(min_row=3, max_row=2 + len(T)):
        for c in r[1:]:
            c.alignment = Alignment(horizontal="right"); c.number_format = "#,##0.0" if c.column > 2 else "#,##0"
    for ci in range(1, len(T.columns) + 1):
        ws.column_dimensions[get_column_letter(ci)].width = 17
    ws.freeze_panes = "B3"
    wb.save(OUT / "行政區_容積使用狀況_sumdd08地上推算.xlsx")
    log("完成")
    print(T.round(1).to_string(index=False))
    print("使用率分級（分區塊數）", out["USE_CLS"].value_counts().to_dict())


if __name__ == "__main__":
    main()
