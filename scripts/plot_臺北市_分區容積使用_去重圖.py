"""去重版分區塊容積使用率地圖（去重後 sumdd08 依使照比例回推的地上樓地板 ÷ 法定總樓地板）。
輸入：分區容積使用/去重版/分區塊_容積使用狀況_去重.shp　輸出：同資料夾 圖_分區塊容積使用率_去重.png（＋手機版 jpg）
執行：python scripts/plot_臺北市_分區容積使用_去重圖.py
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
CASE = ROOT / "案件" / "臺北市_不動產交易分析"
D = CASE / "分區容積使用" / "去重版"
plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "PMingLiU", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False
BRK = [50, 100, 150, 250]
COLORS = ["#FFFFCC", "#FED976", "#FD8D3C", "#E31A1C", "#800026"]
LABELS = ["50% 以下", "50～100%", "100～150%", "150～250%", "250% 以上"]


def main():
    z = gpd.read_file(D / "分區塊_容積使用狀況_去重.shp", encoding="utf-8")
    b = gpd.read_file(CASE / "行政區建物分析" / "shp" / "臺北市行政區_建物交易分析.shp", encoding="utf-8").to_crs(3826)
    has = z["USE_UP"].notna()
    cls = np.digitize(z.loc[has, "USE_UP"].to_numpy(), BRK, right=True)
    counts = np.bincount(cls, minlength=5)
    fig, ax = plt.subplots(figsize=(8.5, 10.5))
    z[~has].plot(ax=ax, color="#DDDDDD", linewidth=0)
    z[has].plot(ax=ax, color=[COLORS[i] for i in cls], linewidth=0.05, edgecolor="white")
    b.boundary.plot(ax=ax, color="#333", linewidth=0.8)
    ax.legend(handles=[Patch(facecolor=c, edgecolor="#999", linewidth=0.3, label=f"{l}（{n:,} 塊）") for c, l, n in zip(COLORS, LABELS, counts)] +
              [Patch(facecolor="#DDDDDD", label=f"無法定容積率（{int((~has).sum()):,} 塊）")], title="容積使用率＝推算地上樓地板÷法定總樓地板", loc="lower left", fontsize=9, title_fontsize=9.5, framealpha=0.95)
    x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
    nx, ny = x1 - (x1 - x0) * 0.06, y1 - (y1 - y0) * 0.06
    ax.annotate("N", (nx, ny - (y1 - y0) * 0.045), ha="center", fontsize=13, weight="bold")
    ax.annotate("", xy=(nx, ny), xytext=(nx, ny - (y1 - y0) * 0.04), arrowprops=dict(arrowstyle="-|>", color="k"))
    bx, by = x1 - (x1 - x0) * 0.05, y0 + (y1 - y0) * 0.05
    ax.plot([bx - 5000, bx], [by, by], color="k", lw=3); ax.text(bx - 2500, by + (y1 - y0) * 0.008, "5 km", ha="center", fontsize=9)
    ax.set_axis_off()
    ax.set_title("臺北市分區塊容積使用率（sumdd08 去重後，依使照比例回推地上樓地板）", fontsize=12.5)
    fig.text(0.5, 0.012, "現況樓地板＝地政局 BuildStat_Fage sumdd08（同棟跨地號只算一次）×使照地上比例；法定容積率：臺北市都發局彙整表；EPSG:3826", ha="center", fontsize=7, color="#555")
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    f = D / "圖_分區塊容積使用率_去重.png"
    fig.savefig(f, dpi=170); plt.close(fig)
    im = Image.open(f).convert("RGB")
    im.resize((1100, int(im.height * 1100 / im.width)), Image.LANCZOS).save(D / "圖_分區塊容積使用率_去重_手機版.jpg", quality=88)
    print(counts.tolist(), int((~has).sum()))


if __name__ == "__main__":
    main()
