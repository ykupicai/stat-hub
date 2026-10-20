"""用不動產成交資料看臺北市土地開發強度（小段，110～114 年買賣）：樓層與型態結構、單價與每單位容積地價、成交容積比對照法定容積。

① 樓層／型態：房地買賣的總樓層中位數、11 層以上占比、大樓＋華廈占比（型態自 110 年起分類收斂）。
② 單價：房地單價中位數（元/坪，排除特殊交易）；純土地單價中位數（住宅區、商業區、全筆或持分≥10%）；
   每單位容積地價＝土地單價（元/坪）÷（小段住商區法定加權容積率÷100）＝「每 1 坪容積樓地板的地價」。
③ 成交容積比：房地買賣「建物面積÷土地面積」的中位數（區分所有時土地面積為持分，比值近似整棟的總樓地板÷基地面積），
   除以小段住商區法定加權容積率＝達成率（粗略代理，建物面積含公設與附屬，故偏高）。
法定容積率：分區容積率圖層（面積加權，只計住宅區與商業區）；小段界：地政局段界圖層。小段樣本不足（見門檻）者留白。
輸出：案件/臺北市_不動產交易分析/開發強度_成交資料/小段_開發強度指標.shp、圖1～圖3 PNG（＋手機版 jpg）
執行：python scripts/analyze_臺北市_開發強度_成交資料.py
"""
import importlib.util
import warnings
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("hot", ROOT / "scripts" / "analyze_臺北市_土地開發熱區.py")
H = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(H)   # 載入後 stdout 已為 UTF-8；沿用 sections() 與 B（實價登錄載入）
B = H.B
CASE = ROOT / "案件" / "臺北市_不動產交易分析"
OUT = CASE / "開發強度_成交資料"
ZONE = ROOT.parent / "地籍成果" / "台北市開發強度" / "台北市分區法定總樓地板_開發強度_v2_data.taipei.gpkg"
plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "PMingLiU", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False
PING = B.PING
Y0 = 110


def med(s):
    return float(np.nanmedian(s)) if len(s) else np.nan


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sec = H.sections()
    tx, land, bld = B.load()
    tx, _ = B.prep(tx)
    tx = tx[(tx["年"] <= 114) & (tx["年"] >= Y0)].copy()
    land = land[land["編號"].isin(tx["編號"])].copy()
    land["zone"] = land["使用分區或編定"].apply(B.zone)
    land["ratio"] = pd.to_numeric(land["持分分子"], errors="coerce") / pd.to_numeric(land["持分分母"], errors="coerce")
    ag = land.groupby("編號").apply(lambda d: pd.Series({"seg": d["土地位置"].value_counts().index[0], "zone": d.loc[d["面積"].idxmax(), "zone"] if d["面積"].notna().any() else d["zone"].iloc[0],
                                                           "ratio": d["ratio"].max()}))
    tx = tx.merge(ag, left_on="編號", right_index=True, how="left")
    tx = tx[tx["seg"].isin(sec["KCNT"])]
    # 法定容積（小段，住商區面積加權）
    z = gpd.read_file(ZONE, layer="分區法定總樓地板").to_crs(3826)
    z = z[(z["容積率"] > 0) & (z["使用分區"].str.contains("住宅|商業"))][["容積率", "geometry"]].copy()
    z["geometry"] = z.geometry.buffer(0)
    ov = gpd.overlay(sec[["KCNT", "geometry"]], z, how="intersection", keep_geom_type=True)
    ov["a"] = ov.area
    far = ov.groupby("KCNT").apply(lambda d: np.average(d["容積率"], weights=d["a"]))
    # ① 樓層／型態：房地買賣
    f = tx[tx["房地"] & tx["樓層數"].notna()]
    A1 = f.groupby("seg").apply(lambda d: pd.Series({"N_BLD": len(d), "FLR_MED": med(d["樓層數"]), "HI11": (d["樓層數"] >= 11).mean() * 100}))
    t10 = f[f["型態"].isin(["住宅大樓", "華廈", "公寓", "透天厝"])]
    A1["BIG"] = t10.groupby("seg").apply(lambda d: d["型態"].isin(["住宅大樓", "華廈"]).mean() * 100)
    # ② 單價
    ok = tx["價格有效"] & ~tx["特殊"]
    A2 = tx[tx["房地"] & ok].groupby("seg").apply(lambda d: pd.Series({"N_P": len(d), "P_BLD": med(d["單價坪"]) / 1e4}))
    lnd = tx[(tx["交易標的"] == "土地") & ok & tx["zone"].isin(["住宅區", "商業區"]) & (tx["ratio"] >= 0.10)]
    A2L = lnd.groupby("seg").apply(lambda d: pd.Series({"N_L": len(d), "P_LAND": med(d["單價坪"]) / 1e4}))
    # ③ 成交容積比
    r = tx[(tx["交易標的"] == "房地(土地+建物)") & (tx["土地面積"] > 0) & (tx["建物面積"] > 0)].copy()
    r["far_t"] = r["建物面積"] / r["土地面積"] * 100
    r = r[r["far_t"].between(20, 3000)]
    A3 = r.groupby("seg").apply(lambda d: pd.Series({"N_F": len(d), "FAR_TRD": med(d["far_t"])}))
    g = sec.merge(A1, left_on="KCNT", right_index=True, how="left").merge(A2, left_on="KCNT", right_index=True, how="left").merge(A2L, left_on="KCNT", right_index=True, how="left") \
        .merge(A3, left_on="KCNT", right_index=True, how="left")
    g["FAR_LEG"] = g["KCNT"].map(far)
    g.loc[g["N_BLD"] < 10, ["FLR_MED", "HI11", "BIG"]] = np.nan
    g.loc[g["N_P"] < 10, "P_BLD"] = np.nan
    g.loc[g["N_L"] < 5, "P_LAND"] = np.nan
    g.loc[g["N_F"] < 10, "FAR_TRD"] = np.nan
    g["P_FAR"] = g["P_LAND"] / (g["FAR_LEG"] / 100)          # 萬元／坪容積
    g["ACH"] = g["FAR_TRD"] / g["FAR_LEG"] * 100
    bnd = gpd.read_file(CASE / "行政區建物分析" / "shp" / "臺北市行政區_建物交易分析.shp", encoding="utf-8").to_crs(3826)[["TOWNNAME", "geometry"]]
    pts = g.copy(); pts["geometry"] = g.representative_point()
    g["TOWN"] = gpd.sjoin(pts, bnd, how="left", predicate="within")["TOWNNAME"].values
    out = g.rename(columns={"KCNT": "SECTION"})[["SECTION", "TOWN", "KM2", "N_BLD", "FLR_MED", "HI11", "BIG", "N_P", "P_BLD", "N_L", "P_LAND", "FAR_LEG", "P_FAR", "N_F", "FAR_TRD", "ACH", "geometry"]]
    for c in ("KM2", "FLR_MED", "HI11", "BIG", "P_BLD", "P_LAND", "FAR_LEG", "P_FAR", "FAR_TRD", "ACH"):
        out[c] = out[c].round(1)
    out.to_file(OUT / "小段_開發強度指標.shp", driver="ESRI Shapefile", encoding="utf-8")
    print(f"成交（{Y0}～114 年）{len(tx):,} 筆；房地買賣有樓層 {len(f):,}；房地單價有效 {int((tx['房地'] & ok).sum()):,}；純土地（住商、持分≥10%、有效）{len(lnd):,}；成交容積比有效 {len(r):,}")
    for c, n in (("HI11", "11層以上占比"), ("P_BLD", "房地單價(萬/坪)"), ("P_LAND", "土地單價(萬/坪)"), ("P_FAR", "每容積坪地價(萬)"), ("FAR_TRD", "成交容積比%"), ("ACH", "達成率%")):
        print(n, "有值小段", int(out[c].notna().sum()), out[c].describe(percentiles=[.5]).round(1).to_dict())
    # 行政區彙總（中位數）
    t = tx.merge(out[["SECTION", "FAR_LEG"]], left_on="seg", right_on="SECTION", how="left")
    ft = t[t["房地"] & t["樓層數"].notna()]
    okm = t["價格有效"] & ~t["特殊"]   # 合併後索引已重置，不可沿用先前的 ok
    d = pd.DataFrame({"房地N": ft.groupby("鄉鎮市區").size(), "樓層中位": ft.groupby("鄉鎮市區")["樓層數"].median(), "11層以上%": ft.groupby("鄉鎮市區")["樓層數"].apply(lambda s: (s >= 11).mean() * 100),
                      "房地單價萬/坪": t[t["房地"] & okm].groupby("鄉鎮市區")["單價坪"].median() / 1e4})
    ll = t[(t["交易標的"] == "土地") & okm & t["zone"].isin(["住宅區", "商業區"]) & (t["ratio"] >= 0.10)]
    d["土地單價萬/坪"] = ll.groupby("鄉鎮市區")["單價坪"].median() / 1e4
    d["住商法定FAR%"] = out.groupby("TOWN").apply(lambda x: np.average(x["FAR_LEG"].dropna(), weights=x.loc[x["FAR_LEG"].notna(), "KM2"]))
    d["每容積坪地價萬"] = d["土地單價萬/坪"] / (d["住商法定FAR%"] / 100)
    rr = t[(t["交易標的"] == "房地(土地+建物)") & (t["土地面積"] > 0) & (t["建物面積"] > 0)].assign(far_t=lambda x: x["建物面積"] / x["土地面積"] * 100)
    rr = rr[rr["far_t"].between(20, 3000)]
    d["成交容積比中位%"] = rr.groupby("鄉鎮市區")["far_t"].median(); d["達成率%"] = d["成交容積比中位%"] / d["住商法定FAR%"] * 100
    print(d.round(1).sort_values("每容積坪地價萬", ascending=False).to_string())
    # 地圖
    specs = [("圖1_樓層與型態", [("HI11", "11 層以上成交占比（%）", "YlOrRd", None), ("BIG", "大樓＋華廈占比（%）", "PuBu", None)], "房地買賣的總樓層結構"),
             ("圖2_單價與容積地價", [("P_BLD", "房地單價中位數（萬元/坪）", "YlGnBu", None), ("P_FAR", "每容積坪地價（萬元/坪容積）", "YlOrRd", None)], "成交單價與每單位容積地價"),
             ("圖3_成交容積與法定容積", [("FAR_TRD", "成交容積比中位數（%）", "PuBuGn", None), ("ACH", "達成率＝成交容積比÷法定容積率（%）", "RdPu", (0, 200))], "成交容積比對照法定容積")]
    for fn, panels, ttl in specs:
        fig, axs = plt.subplots(1, 2, figsize=(14, 8.2))
        for ax, (col, lab, cm, vr) in zip(axs, panels):
            v = out[col]
            vmin, vmax = (vr if vr else (v.quantile(0.03), v.quantile(0.97)))
            out.plot(ax=ax, color="#EEEEEE", edgecolor="white", linewidth=0.2)
            out[v.notna()].plot(ax=ax, column=col, cmap=cm, vmin=vmin, vmax=vmax, edgecolor="white", linewidth=0.2, legend=True, legend_kwds={"shrink": 0.5, "label": lab})
            bnd.boundary.plot(ax=ax, color="#555", linewidth=0.5)
            ax.set_axis_off(); ax.set_title(f"{lab}\n（有值小段 {int(v.notna().sum())} 個）", fontsize=10.5)
        fig.suptitle(f"臺北市{ttl}（小段，{Y0}～114 年買賣）", fontsize=13.5, y=0.985)
        fig.text(0.5, 0.008, "資料：內政部實價登錄；小段樣本不足者灰色（樓層、單價、成交容積需 10 筆以上，土地單價需 5 筆以上）；法定容積：臺北市都發局彙整表（住宅區、商業區面積加權）；EPSG:3826", ha="center", fontsize=7.5, color="#555")
        fig.tight_layout(rect=(0, 0.015, 1, 0.96))
        p = OUT / f"{fn}.png"; fig.savefig(p, dpi=150); plt.close(fig)
        im = Image.open(p).convert("RGB"); im.resize((1300, int(im.height * 1300 / im.width)), Image.LANCZOS).save(OUT / f"{fn}_手機版.jpg", quality=88)


if __name__ == "__main__":
    main()
