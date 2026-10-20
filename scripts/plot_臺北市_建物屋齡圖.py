"""臺北市建物屋齡分布圖（地號尺度，地政局 BuildStat_Fage 圖層；屋齡＝該地號建物屋齡平均，2026 推定基準）。
輸入：行政區屋齡/現況_地政局圖層/臺北市地號_建物屋齡.shp 與 臺北市行政區_現況屋齡.shp　輸出：同資料夾 圖_臺北市建物屋齡.png
執行：python scripts/plot_臺北市_建物屋齡圖.py
"""
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "案件" / "臺北市_不動產交易分析" / "行政區屋齡" / "現況_地政局圖層"
plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "PMingLiU", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False
BINS = [(0, 10), (11, 20), (21, 30), (31, 40), (41, 50), (51, 60), (61, 999)]
COLORS = ["#053061", "#2166ac", "#67a9cf", "#d1e5f0", "#fddbc7", "#ef8a62", "#b2182b"]
LABELS = ["0～10 年", "11～20 年", "21～30 年", "31～40 年", "41～50 年", "51～60 年", "61 年以上"]


def main():
    g = gpd.read_file(D / "臺北市地號_建物屋齡.shp", encoding="utf-8")
    d = gpd.read_file(D / "臺北市行政區_現況屋齡.shp", encoding="utf-8")
    cls = np.digitize(g["AGE_AVG"].to_numpy(), [b[0] for b in BINS[1:]])
    counts = np.bincount(cls, minlength=len(BINS))
    fig, ax = plt.subplots(figsize=(10, 11.2))
    g.assign(_c=[COLORS[i] for i in cls]).plot(ax=ax, color=[COLORS[i] for i in cls], linewidth=0)
    d.boundary.plot(ax=ax, color="#333", linewidth=0.9)
    for _, r in d.iterrows():
        p = r.geometry.representative_point()
        ax.annotate(f"{r['TOWNNAME']}\n{r['AGE_MED']:.0f}年", (p.x, p.y), ha="center", va="center", fontsize=8.5, weight="bold", color="#111",
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.7))
    ax.legend(handles=[Patch(facecolor=c, edgecolor="none", label=f"{l}（{n:,} 地號）") for c, l, n in zip(COLORS, LABELS, counts)],
              title="地號上建物屋齡平均", loc="lower left", fontsize=9, title_fontsize=10, frameon=True, framealpha=0.92)
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    nx, ny = x1 - (x1 - x0) * 0.06, y1 - (y1 - y0) * 0.06
    ax.annotate("N", (nx, ny - (y1 - y0) * 0.045), ha="center", fontsize=13, weight="bold")
    ax.annotate("", xy=(nx, ny), xytext=(nx, ny - (y1 - y0) * 0.04), arrowprops=dict(arrowstyle="-|>", color="k"))
    bx, by = x1 - (x1 - x0) * 0.05, y0 + (y1 - y0) * 0.05
    ax.plot([bx - 5000, bx], [by, by], color="k", lw=3)
    ax.text(bx - 2500, by + (y1 - y0) * 0.01, "5 km", ha="center", fontsize=9)
    ax.set_axis_off()
    ax.set_title("臺北市建物屋齡分布圖（地號尺度）\n圖上文字為各行政區屋齡中位數（以建物筆數加權）", fontsize=14)
    fig.text(0.5, 0.012, "資料：臺北市政府地政局都更門檻估算服務 BuildStat_Fage 圖層（152,684 個地號）；屋齡基準年依資料推定為 2026；"
             "屋齡剛好 55 年者占 23% 地號，疑為預設值，見說明。界線：內政部鄉鎮市區界；EPSG:3826",
             ha="center", fontsize=7.5, color="#555", wrap=True)
    fig.tight_layout(rect=(0, 0.025, 1, 1))
    fig.savefig(D / "圖_臺北市建物屋齡.png", dpi=170)
    print("saved", counts.tolist())


if __name__ == "__main__":
    main()
