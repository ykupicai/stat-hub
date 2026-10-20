"""近十年（105/10～114/12）臺北市土地開發熱區：以小段（552 個）統計「純土地買賣＋預售屋」交易的密度。

指標：N_LAND＝純土地買賣筆數；N_PRE＝預售屋（含土地者）筆數；DENS＝（N_LAND＋N_PRE）÷小段面積（筆/km²）；
  熱區＝DENS 前 10% 且筆數 ≥ 10。另列前期（105/10～109/12，3.25 年）與後期（110～114，5 年）的年均筆數比較。
資料：lvr.sqlite（實價登錄，kind a 土地、kind b 預售屋）、地政局 LandDyn 段界圖層（552 個小段，公開 ArcGIS REST）
輸出：案件/臺北市_不動產交易分析/土地開發熱區/小段_土地開發熱度.shp、圖_土地開發熱區.png（＋手機版 jpg）；摘要印在終端
執行：python scripts/analyze_臺北市_土地開發熱區.py
"""
import io
import json
import sqlite3
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from matplotlib.patches import Patch
from PIL import Image
from shapely.geometry import MultiPolygon, Polygon

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location("base10", ROOT / "scripts" / "analyze_臺北市_實價登錄_10年.py")
B = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(B)   # 載入時已把 stdout 設為 UTF-8
CASE = ROOT / "案件" / "臺北市_不動產交易分析"
OUT = CASE / "土地開發熱區"
RAWD = ROOT / "資料庫" / "原始檔" / "臺北市段界_LandDyn"
plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "PMingLiU", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False


def rings_to_geom(rings):
    outers, holes = [], []
    for r in rings:
        if len(r) < 4:
            continue
        a = np.array(r); x, y = a[:, 0], a[:, 1]
        p = Polygon(r).buffer(0)
        (outers if 0.5 * np.sum(x[:-1] * y[1:] - x[1:] * y[:-1]) < 0 else holes).append(p)
    if not outers:
        outers, holes = holes, []
    g = MultiPolygon(outers) if len(outers) > 1 else outers[0]
    for h in holes:
        g = g.difference(h)
    return g


def sections():
    RAWD.mkdir(parents=True, exist_ok=True)
    f = RAWD / "段界.json"
    if not f.exists():
        s = requests.Session(); s.headers.update({"User-Agent": "Mozilla/5.0", "Referer": "https://cloud.land.gov.taipei/urland/urban.html"})
        j = s.get("https://maps.land.gov.taipei/server/rest/services/Dynamic3857/LandDyn/MapServer/1/query",
                  params={"where": "1=1", "outFields": "*", "returnGeometry": "true", "outSR": 3826, "f": "json"}, timeout=120).json()
        f.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
    j = json.load(open(f, encoding="utf-8"))
    g = gpd.GeoDataFrame([ft["attributes"] for ft in j["features"]], geometry=[rings_to_geom(ft["geometry"]["rings"]) for ft in j["features"]], crs=3826)
    g["KM2"] = g.area / 1e6
    return g[["KCNT", "AA48", "KM2", "geometry"]]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sec = sections()
    c = sqlite3.connect(ROOT / "資料庫" / "lvr.sqlite")
    tx = pd.read_sql("select kind, 編號 as id, 交易標的, 交易日 from lvr_tx where county='臺北市' and 交易日 between 1051001 and 1141231 and "
                     "((kind='a' and 交易標的='土地') or (kind='b' and 交易標的 like '房地%'))", c)
    ld = pd.read_sql("select l.kind as k, l.編號 as id, l.土地位置 as seg, l.地號 as no8, l.面積 as area, l.使用分區或編定 as zn, l.持分分母 as dn, l.持分分子 as nu, l.移轉情形 as tr "
                     "from lvr_land l join lvr_tx t on t.kind=l.kind and t.編號=l.編號 "
                     "where t.county='臺北市' and t.交易日 between 1051001 and 1141231 and ((t.kind='a' and t.交易標的='土地') or (t.kind='b' and t.交易標的 like '房地%'))", c)
    ld["zone"] = ld["zn"].apply(B.zone)
    ld["ratio"] = pd.to_numeric(ld["nu"], errors="coerce") / pd.to_numeric(ld["dn"], errors="coerce")
    ld["key"] = ld["seg"].fillna("") + ld["no8"].fillna("")

    def agg_trade(d):
        r = d.loc[d["area"].idxmax()] if d["area"].notna().any() else d.iloc[0]
        return pd.Series({"seg": d["seg"].value_counts().index[0], "area": d["area"].sum(), "zone": r["zone"], "ratio": d["ratio"].max(), "proj": "|".join(sorted(set(d["key"])))})
    seg = ld.groupby(["k", "id"]).apply(agg_trade).reset_index().rename(columns={"k": "kind"})
    tx = tx.merge(seg, on=["kind", "id"], how="left")
    tx["年"] = tx["交易日"] // 10000
    miss = tx["seg"].isna().sum()
    # 開發用地交易：純土地買賣中，非公共設施用地，且全筆或持分 ≥ 10%；預售屋以「案」（土地地號組合不重複）計
    a_all = tx[tx["kind"] == "a"]
    keep_a = (a_all["zone"] != "公共設施用地") & (a_all["ratio"] >= 0.10)
    print(f"純土地買賣 {len(a_all):,} 筆 → 非公共設施用地且持分≥10% 的開發用地交易 {int(keep_a.sum()):,} 筆（公共設施用地 {int((a_all['zone'] == '公共設施用地').sum()):,}）")
    b_all = tx[tx["kind"] == "b"]
    print(f"預售屋 {len(b_all):,} 戶 → 不重複土地組合（案）{b_all['proj'].nunique():,} 個")
    tx = pd.concat([a_all[keep_a], b_all.drop_duplicates("proj")]).copy()   # 預售屋每案取一筆，日期為該案最早成交
    first_b = b_all.sort_values("交易日").drop_duplicates("proj")[["proj", "交易日"]].set_index("proj")["交易日"]
    tx.loc[tx["kind"] == "b", "交易日"] = tx.loc[tx["kind"] == "b", "proj"].map(first_b)
    tx["年"] = tx["交易日"] // 10000
    units = b_all.groupby("seg").size()
    print(f"熱度事件：開發用地交易 {int((tx['kind'] == 'a').sum()):,} ＋ 預售屋案 {int((tx['kind'] == 'b').sum()):,}；無地段 {int(miss)}；對不到小段 {int((~tx['seg'].isin(sec['KCNT'])).sum())}")
    tx = tx[tx["seg"].isin(sec["KCNT"])]
    tx["前期"] = tx["交易日"] <= 1091231
    a = tx.groupby("seg").apply(lambda d: pd.Series({"N_LAND": int((d["kind"] == "a").sum()), "N_PRE": int((d["kind"] == "b").sum()), "A_LAND": float(d.loc[d["kind"] == "a", "area"].sum()),
                                                      "N_P1": int(d["前期"].sum()), "N_P2": int((~d["前期"]).sum())}))
    g = sec.merge(a, left_on="KCNT", right_index=True, how="left").fillna({"N_LAND": 0, "N_PRE": 0, "A_LAND": 0, "N_P1": 0, "N_P2": 0})
    g["UNITS"] = g["KCNT"].map(units).fillna(0).astype(int)
    bnd = gpd.read_file(CASE / "行政區建物分析" / "shp" / "臺北市行政區_建物交易分析.shp", encoding="utf-8").to_crs(3826)[["TOWNNAME", "geometry"]]
    pts = g.copy(); pts["geometry"] = g.representative_point()
    g["TOWN"] = gpd.sjoin(pts, bnd, how="left", predicate="within")["TOWNNAME"].values
    g["N_ALL"] = g["N_LAND"] + g["N_PRE"]
    g["DENS"] = (g["N_ALL"] / g["KM2"]).round(1)
    g["RATE1"] = (g["N_P1"] / 3.25).round(2); g["RATE2"] = (g["N_P2"] / 5.0).round(2)
    g["A_LAND"] = g["A_LAND"].round(0)
    cut = g.loc[g["N_ALL"] >= 10, "DENS"].quantile(0.9)
    g["HOT"] = ((g["DENS"] >= cut) & (g["N_ALL"] >= 10)).astype(int)
    g["KM2"] = g["KM2"].round(3)
    print(f"小段 {len(g)}；有交易 {int((g['N_ALL'] > 0).sum())}；熱區門檻 DENS≥{cut:.0f} 筆/km²；熱區 {int(g['HOT'].sum())} 個")
    out = g.rename(columns={"KCNT": "SECTION", "AA48": "SEC_CODE"})[["SECTION", "SEC_CODE", "TOWN", "KM2", "N_LAND", "N_PRE", "UNITS", "N_ALL", "A_LAND", "DENS", "N_P1", "N_P2", "RATE1", "RATE2", "HOT", "geometry"]]
    out.to_file(OUT / "小段_土地開發熱度.shp", driver="ESRI Shapefile", encoding="utf-8")
    top = out.sort_values("DENS", ascending=False).head(12)
    print("熱度前 12 小段："); print(top[["SECTION", "TOWN", "N_LAND", "N_PRE", "N_ALL", "KM2", "DENS", "RATE1", "RATE2"]].to_string(index=False))
    bigN = out.sort_values("N_ALL", ascending=False).head(8)
    print("總筆數前 8："); print(bigN[["SECTION", "TOWN", "N_LAND", "N_PRE", "N_ALL", "DENS"]].to_string(index=False))
    t = out.groupby("TOWN").agg(N_LAND=("N_LAND", "sum"), N_PRE=("N_PRE", "sum"), N_ALL=("N_ALL", "sum"), KM2=("KM2", "sum"), HOT=("HOT", "sum"), P1=("N_P1", "sum"), P2=("N_P2", "sum"))
    t["DENS"] = t["N_ALL"] / t["KM2"]; t["後期年均/前期年均"] = (t["P2"] / 5) / (t["P1"] / 3.25)
    print("各行政區："); print(t.sort_values("N_ALL", ascending=False).round(1).to_string())
    hot = out[out["HOT"] == 1]
    print("熱區占筆數", round(hot["N_ALL"].sum() / out["N_ALL"].sum() * 100, 1), "%；占面積", round(hot["KM2"].sum() / out["KM2"].sum() * 100, 1), "%；熱區行政區分布", hot["TOWN"].value_counts().to_dict())
    print("前後期（年均）整體", round(out["N_P1"].sum() / 3.25), "→", round(out["N_P2"].sum() / 5), "；熱區前後期", round(hot["N_P1"].sum() / 3.25), "→", round(hot["N_P2"].sum() / 5))
    yr = tx.groupby(["年", "kind"]).size().unstack(fill_value=0); print("年度（a 純土地／b 預售屋）：", yr.to_dict())
    # 地圖
    bins = [0, 5, 20, 50, 100, 1e9]; cols = ["#F3F3F3", "#FFFFB2", "#FECC5C", "#FD8D3C", "#E31A1C"]
    lab = ["0～5", "5～20", "20～50", "50～100", "100 以上"]
    cls = np.digitize(out["DENS"].where(out["N_ALL"] > 0, 0).to_numpy(), bins[1:-1], right=True)
    fig, ax = plt.subplots(figsize=(9, 10.5))
    out.plot(ax=ax, color=[cols[i] for i in cls], edgecolor="white", linewidth=0.25)
    out[out["HOT"] == 1].boundary.plot(ax=ax, color="#4a0d67", linewidth=1.4)
    bnd.boundary.plot(ax=ax, color="#555", linewidth=0.6)
    for _, r in top.head(10).iterrows():
        p = r.geometry.representative_point(); ax.annotate(r["SECTION"], (p.x, p.y), ha="center", fontsize=7, color="#222", bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.7))
    n = np.bincount(cls, minlength=5)
    ax.legend(handles=[Patch(facecolor=c_, edgecolor="#999", linewidth=0.3, label=f"{l_} 筆/km²（{k} 個小段）") for c_, l_, k in zip(cols, lab, n)] + [Patch(facecolor="none", edgecolor="#4a0d67", linewidth=1.6, label=f"熱區（前 10%，{int(out['HOT'].sum())} 個小段）")],
              title="純土地買賣＋預售屋交易密度", loc="lower left", fontsize=8.5, title_fontsize=9.5, framealpha=0.95)
    x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
    nx, ny = x1 - (x1 - x0) * 0.06, y1 - (y1 - y0) * 0.06
    ax.annotate("N", (nx, ny - (y1 - y0) * 0.045), ha="center", fontsize=13, weight="bold"); ax.annotate("", xy=(nx, ny), xytext=(nx, ny - (y1 - y0) * 0.04), arrowprops=dict(arrowstyle="-|>", color="k"))
    ax.set_axis_off()
    ax.set_title("臺北市近十年土地開發熱區（以小段計，105/10～114/12）\n純土地買賣＋預售屋交易筆數 ÷ 小段面積", fontsize=12.5)
    fig.text(0.5, 0.012, "資料：內政部實價登錄（純土地買賣、預售屋）；小段界：地政局段界圖層；紫框為密度前 10% 且交易 10 筆以上的熱區；EPSG:3826", ha="center", fontsize=7.5, color="#555")
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    f = OUT / "圖_土地開發熱區.png"; fig.savefig(f, dpi=170); plt.close(fig)
    im = Image.open(f).convert("RGB"); im.resize((1100, int(im.height * 1100 / im.width)), Image.LANCZOS).save(OUT / "圖_土地開發熱區_手機版.jpg", quality=88)


if __name__ == "__main__":
    main()
