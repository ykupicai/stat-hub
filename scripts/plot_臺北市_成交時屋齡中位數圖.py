"""各行政區成交時屋齡中位數分層設色預覽（分位數 5 級），讀 成交時屋齡/臺北市行政區_成交時屋齡.shp 的 AGE_MED。
輸出：成交時屋齡/圖_成交時屋齡中位數.png（＋手機版 jpg）。與平均版並排比較時看 圖_成交時屋齡平均。
執行：python scripts/plot_臺北市_成交時屋齡中位數圖.py
"""
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "案件" / "臺北市_不動產交易分析" / "行政區屋齡" / "成交時屋齡"
plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "PMingLiU", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False
COLORS = ["#FFFFB2", "#FECC5C", "#FD8D3C", "#F03B20", "#BD0026"]


def main():
    g = gpd.read_file(D / "臺北市行政區_成交時屋齡.shp", encoding="utf-8")
    v = g["AGE_MED"].to_numpy(float)
    edges = np.quantile(v, [0.2, 0.4, 0.6, 0.8])
    yb = np.digitize(v, edges, right=True)
    lo = [v.min()] + list(edges); hi = list(edges) + [v.max()]
    fig, ax = plt.subplots(figsize=(8, 9.2))
    g.plot(ax=ax, color=[COLORS[i] for i in yb], edgecolor="#555", linewidth=0.8)
    for (_, r), pt in zip(g.iterrows(), g.representative_point()):
        ax.annotate(f"{r['TOWNNAME']}\n{r['AGE_MED']:.0f}", (pt.x, pt.y), ha="center", va="center", fontsize=8.5, weight="bold",
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.65))
    ax.legend(handles=[Patch(facecolor=COLORS[i], edgecolor="#555", label=f"{lo[i]:.1f}～{hi[i]:.1f} 年（{int((yb == i).sum())} 區）") for i in range(5)],
              title="成交時屋齡中位數（分位數 5 級）", loc="lower left", fontsize=8.5, title_fontsize=9.5)
    ax.set_axis_off()
    ax.set_title("臺北市各行政區成交時屋齡中位數\n實價登錄買賣 105～114 年，有建物且屋齡可算出者（159,007 筆）", fontsize=12)
    fig.text(0.5, 0.01, "屋齡＝交易年－建築完成年；資料：內政部實價登錄；界線：內政部鄉鎮市區界；EPSG:3826", ha="center", fontsize=7.5, color="#555")
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(D / "圖_成交時屋齡中位數.png", dpi=160); plt.close(fig)
    im = Image.open(D / "圖_成交時屋齡中位數.png").convert("RGB")
    im.resize((1000, int(im.height * 1000 / im.width)), Image.LANCZOS).save(D / "圖_成交時屋齡中位數_手機版.jpg", quality=88)
    order = np.argsort(v)
    print([(g["TOWNNAME"].iloc[i], v[i], int(yb[i])) for i in order])
    avg = g["AGE_AVG"].to_numpy(float); ya = np.digitize(avg, np.quantile(avg, [0.2, 0.4, 0.6, 0.8]), right=True)
    print("分級與平均版不同的行政區：", [g["TOWNNAME"].iloc[i] for i in range(len(g)) if yb[i] != ya[i]])


if __name__ == "__main__":
    main()
