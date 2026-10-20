"""中山區公有地分布圖（依 全部公有／公私共有／非公有 上色）。
輸入：中山區_權屬/中山區_交易土地權屬.shp（含 PUB_CLS，由 merge_中山區_權屬公有地.py 產生）　輸出：中山區_權屬/圖R3_公有地分布.png（＋手機版 jpg）
執行：python scripts/plot_中山區_公有地分布圖.py
"""
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
CASE = ROOT / "案件" / "臺北市_不動產交易分析"
D = CASE / "中山區_權屬"
plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "PMingLiU", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False
CLS = [("全部公有", "#08519C", "全部公有"), ("公私共有（公有持分未滿 100%）", "#FD8D3C", "公私共有（公有持分未滿 100%）"),
       ("非公有（API 無公有所有權人）", "#D9D9D9", "非公有（由空值推定）"), ("無資料", "#FFFFFF", "無資料")]


def main():
    g = gpd.read_file(D / "中山區_交易土地權屬.shp", encoding="utf-8")
    bnd = gpd.read_file(CASE / "行政區建物分析" / "shp" / "臺北市行政區_建物交易分析.shp", encoding="utf-8").to_crs(3826)
    zs = bnd[bnd["TOWNNAME"] == "中山區"]
    fig, ax = plt.subplots(figsize=(9, 10.5))
    zs.plot(ax=ax, color="#F7F7F7", edgecolor="#333", linewidth=1.2)
    for key, col, _ in CLS[::-1]:  # 非公有在下、公有疊上
        sub = g[g["PUB_CLS"] == key]
        if len(sub):
            sub.plot(ax=ax, color=col, edgecolor="white" if key != "無資料" else "#999", linewidth=0.1)
    zs.boundary.plot(ax=ax, color="#333", linewidth=1.2)
    cnt = g["PUB_CLS"].value_counts()
    ax.legend(handles=[Patch(facecolor=c, edgecolor="#999", linewidth=0.4, label=f"{lab}：{cnt.get(k, 0):,}") for k, c, lab in CLS],
              title=f"中山區交易地號的公有地權屬（共 {len(g):,} 個地號）", loc="lower left", fontsize=9, title_fontsize=9.5, framealpha=0.95)
    x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
    nx, ny = x1 - (x1 - x0) * 0.06, y1 - (y1 - y0) * 0.07
    ax.annotate("N", (nx, ny - (y1 - y0) * 0.045), ha="center", fontsize=13, weight="bold")
    ax.annotate("", xy=(nx, ny), xytext=(nx, ny - (y1 - y0) * 0.04), arrowprops=dict(arrowstyle="-|>", color="k"))
    bx, by = x1 - (x1 - x0) * 0.05, y0 + (y1 - y0) * 0.05
    ax.plot([bx - 1000, bx], [by, by], color="k", lw=3); ax.text(bx - 500, by + (y1 - y0) * 0.008, "1 km", ha="center", fontsize=9)
    ax.set_axis_off()
    ax.set_title("臺北市中山區公有地分布（依權屬分類）\n僅含 105/10～114/12 曾有買賣交易的地號", fontsize=12.5)
    fig.text(0.5, 0.012, "權屬：內政部 getLandInfo（只回傳公有所有權人，私有地為空值）；界址：農業部地籍圖資；EPSG:3826", ha="center", fontsize=8, color="#555")
    fig.tight_layout(rect=(0, 0.025, 1, 1))
    f = D / "圖R3_公有地分布.png"
    fig.savefig(f, dpi=170); plt.close(fig)
    im = Image.open(f).convert("RGB")
    im.resize((1100, int(im.height * 1100 / im.width)), Image.LANCZOS).save(D / "圖R3_公有地分布_手機版.jpg", quality=88)
    print(cnt.to_dict())


if __name__ == "__main__":
    main()
