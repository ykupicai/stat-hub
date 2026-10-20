"""中山區全量地籍查詢成果圖：6,586 個查到的地號界址，依「圖面積與登記面積差異%」分級上色。
輸入：地號清單/中山區_全量/中山區_全部OK.shp（big5）、中山區_全部結果.csv　輸出：同資料夾 圖_中山區地籍查詢成果.png（另附手機版 jpg）
執行：python scripts/plot_中山區_地籍查詢成果.py
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
D = ROOT / "案件" / "臺北市_不動產交易分析" / "地號清單" / "中山區_全量"
BND = ROOT / "案件" / "臺北市_不動產交易分析" / "行政區建物分析" / "shp" / "臺北市行政區_建物交易分析.shp"
plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "PMingLiU", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False
CL = [(1, "#4C9F70", "差異 1% 以內"), (5, "#F2CF6B", "差異 1～5%"), (1e9, "#D6604D", "差異超過 5%"), (0, "#9A9A9A", "登記面積缺值，無法比較")]


def main():
    g = gpd.read_file(D / "中山區_全部OK.shp", encoding="big5")
    res = pd.read_csv(D / "中山區_全部結果.csv", encoding="utf-8-sig")
    st = res["狀態"].value_counts().to_dict()
    pc = [c for c in g.columns if c.startswith("差異")][0]
    d = g[pc].abs().to_numpy()
    cls = np.digitize(d, [CL[0][0], CL[1][0]], right=True)
    cls[np.isnan(d)] = 3  # 登記面積缺值，無法比較
    counts = np.bincount(cls, minlength=4)
    bnd = gpd.read_file(BND, encoding="utf-8").to_crs(3826)
    zs = bnd[bnd["TOWNNAME"] == "中山區"]
    fig, ax = plt.subplots(figsize=(9, 10.5))
    zs.plot(ax=ax, color="#f3f3f3", edgecolor="#333", linewidth=1.2)
    g.plot(ax=ax, color=[CL[i][1] for i in cls], edgecolor="white", linewidth=0.15)
    zs.boundary.plot(ax=ax, color="#333", linewidth=1.2)
    ax.legend(handles=[Patch(facecolor=c, label=f"{l}：{n:,} 筆") for (_, c, l), n in zip(CL, counts)], title=f"圖面積與登記面積差異（共 {len(g):,} 筆）",
              loc="lower left", fontsize=9.5, title_fontsize=10, framealpha=0.95)
    x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
    nx, ny = x1 - (x1 - x0) * 0.06, y1 - (y1 - y0) * 0.07
    ax.annotate("N", (nx, ny - (y1 - y0) * 0.045), ha="center", fontsize=13, weight="bold")
    ax.annotate("", xy=(nx, ny), xytext=(nx, ny - (y1 - y0) * 0.04), arrowprops=dict(arrowstyle="-|>", color="k"))
    bx, by = x1 - (x1 - x0) * 0.05, y0 + (y1 - y0) * 0.05
    ax.plot([bx - 1000, bx], [by, by], color="k", lw=3)
    ax.text(bx - 500, by + (y1 - y0) * 0.008, "1 km", ha="center", fontsize=9)
    ax.set_axis_off()
    ax.set_title(f"臺北市中山區地籍查詢成果\n清單 {len(res):,} 筆：查到 {st.get('OK', 0):,}、回傳別筆地 {st.get('MISMATCH', 0)}、已改號 {st.get('RESURVEYED', 0)}", fontsize=13)
    fig.text(0.5, 0.012, "資料：農業部地籍圖資（界址）、內政部地籍資料（登記面積）；圖資僅供評估，面積以登記值為準；EPSG:3826", ha="center", fontsize=8, color="#555")
    fig.tight_layout(rect=(0, 0.025, 1, 1))
    out = D / "圖_中山區地籍查詢成果.png"
    fig.savefig(out, dpi=170)
    im = Image.open(out).convert("RGB")
    im.resize((1100, int(im.height * 1100 / im.width)), Image.LANCZOS).save(D / "圖_中山區地籍查詢成果_手機版.jpg", quality=88)
    print(len(g), counts.tolist(), st)


if __name__ == "__main__":
    main()
