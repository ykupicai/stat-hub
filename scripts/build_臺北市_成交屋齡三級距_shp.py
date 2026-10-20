"""各行政區成交時屋齡三級距 → 行政區面 shp（含三級距的筆數與占比）＋ 31 年以上占比的分層設色預覽。
輸入：行政區三表_105至114/表6_*.xlsx（20 年以下／21-30 年／31 年以上，168,611 筆）、行政區建物分析/shp 的行政區界線
輸出：行政區屋齡/成交時屋齡/臺北市行政區_成交時屋齡三級距_全年.shp（欄位見 欄位說明_三級距.csv）、圖_成交時屋齡三級距_31年以上占比.png（＋手機版 jpg）
執行：python scripts/build_臺北市_成交屋齡三級距_shp.py
"""
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
CASE = ROOT / "案件" / "臺北市_不動產交易分析"
OUT = CASE / "行政區屋齡" / "成交時屋齡"
plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "PMingLiU", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False
COLORS = ["#FFFFB2", "#FECC5C", "#FD8D3C", "#F03B20", "#BD0026"]
MAP = {"20年以下": ("N_20D", "P_20D"), "21-30年": ("N_2130", "P_2130"), "31年以上": ("N_31U", "P_31U")}


def main():
    t = pd.read_excel(CASE / "行政區三表_105至114" / "表6_行政區×成交時屋齡三級距_筆數與占比.xlsx", header=1).dropna(subset=["指標"])
    t = t[t["屋齡級距"].isin(list(MAP) + ["合計"])]
    rows = {}
    for _, r in t.iterrows():
        rows[(r["屋齡級距"], r["指標"])] = r
    dist = [c for c in t.columns if c.endswith("區")]
    d = pd.DataFrame({"TOWNNAME": dist})
    for b, (nc, pc) in MAP.items():
        d[nc] = [int(rows[(b, "筆數")][c]) for c in dist]
        d[pc] = [float(rows[(b, "占比%")][c]) for c in dist]
    d["N_ALL"] = [int(rows[("合計", "筆數")][c]) for c in dist]
    assert d["N_ALL"].sum() == 168611 and (d[["N_20D", "N_2130", "N_31U"]].sum(axis=1) == d["N_ALL"]).all()
    bnd = gpd.read_file(CASE / "行政區建物分析" / "shp" / "臺北市行政區_建物交易分析.shp", encoding="utf-8")[["TOWNID", "TOWNNAME", "geometry"]].to_crs(3826)
    g = bnd.merge(d, on="TOWNNAME", how="left")
    assert len(g) == 12 and g["N_ALL"].notna().all()
    g.to_file(OUT / "臺北市行政區_成交時屋齡三級距_全年.shp", driver="ESRI Shapefile", encoding="utf-8")
    pd.DataFrame({"欄位": ["TOWNID", "TOWNNAME", "N_20D", "P_20D", "N_2130", "P_2130", "N_31U", "P_31U", "N_ALL"],
                  "說明": ["行政區代碼", "行政區", "屋齡 20 年以下筆數（含 20）", "20 年以下占比%", "屋齡 21～30 年筆數", "21～30 年占比%", "屋齡 31 年以上筆數", "31 年以上占比%",
                         "有建物且屋齡可算出的買賣交易筆數（分母）"]}).to_csv(OUT / "欄位說明_三級距.csv", index=False, encoding="utf-8-sig")
    v = g["P_31U"].to_numpy(float)
    edges = np.quantile(v, [0.2, 0.4, 0.6, 0.8]); yb = np.digitize(v, edges, right=True)
    lo = [v.min()] + list(edges); hi = list(edges) + [v.max()]
    fig, ax = plt.subplots(figsize=(8, 9.2))
    g.plot(ax=ax, color=[COLORS[i] for i in yb], edgecolor="#555", linewidth=0.8)
    for (_, r), pt in zip(g.iterrows(), g.representative_point()):
        ax.annotate(f"{r['TOWNNAME']}\n{r['P_31U']:.1f}%", (pt.x, pt.y), ha="center", va="center", fontsize=8.5, weight="bold",
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.65))
    ax.legend(handles=[Patch(facecolor=COLORS[i], edgecolor="#555", label=f"{lo[i]:.1f}～{hi[i]:.1f}%（{int((yb == i).sum())} 區）") for i in range(5)],
              title="成交屋齡 31 年以上占比（分位數 5 級）", loc="lower left", fontsize=8.5, title_fontsize=9.5)
    ax.set_axis_off()
    ax.set_title("臺北市各行政區成交時屋齡 31 年以上的交易占比\n實價登錄買賣 105～114 年，有建物且屋齡可算出者（168,611 筆）", fontsize=12)
    fig.text(0.5, 0.01, "屋齡＝交易年－建築完成年；shp 另含 20 年以下、21-30 年的筆數與占比欄位；資料：內政部實價登錄；EPSG:3826", ha="center", fontsize=7.5, color="#555")
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    f = OUT / "圖_成交時屋齡三級距_31年以上占比.png"
    fig.savefig(f, dpi=160); plt.close(fig)
    im = Image.open(f).convert("RGB")
    im.resize((1000, int(im.height * 1000 / im.width)), Image.LANCZOS).save(OUT / "圖_成交時屋齡三級距_31年以上占比_手機版.jpg", quality=88)
    print(g.drop(columns="geometry").sort_values("P_31U").to_string(index=False))
    print([f"{lo[i]:.1f}-{hi[i]:.1f}:{int((yb == i).sum())}" for i in range(5)])


if __name__ == "__main__":
    main()
