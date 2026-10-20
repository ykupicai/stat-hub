"""各行政區成交時屋齡平均 → 行政區面 shp ＋ 分層設色圖預覽（分位數 5 級）。

輸入：行政區三表_105至114/表5d_行政區成交時屋齡摘要.csv（有建物且屋齡可算出者，159,007 筆）、行政區建物分析/shp 的行政區界線
輸出：案件/臺北市_不動產交易分析/行政區屋齡/成交時屋齡/臺北市行政區_成交時屋齡.shp、bins.json、圖_成交時屋齡平均.png（＋手機版 jpg）
執行：python scripts/build_臺北市_成交時屋齡平均_shp.py
"""
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Patch
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
CASE = ROOT / "案件" / "臺北市_不動產交易分析"
OUT = CASE / "行政區屋齡" / "成交時屋齡"
plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "PMingLiU", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False
COLORS = ["#FFFFB2", "#FECC5C", "#FD8D3C", "#F03B20", "#BD0026"]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    s = pd.read_csv(CASE / "行政區三表_105至114" / "表5d_行政區成交時屋齡摘要.csv", index_col=0, encoding="utf-8-sig")
    st = s.drop(columns="全市").T.rename(columns={"有屋齡筆數": "N_AGE", "屋齡中位數": "AGE_MED", "屋齡平均": "AGE_AVG", "屋齡第25百分位": "AGE_P25", "屋齡第75百分位": "AGE_P75"})
    st["N_AGE"] = st["N_AGE"].astype(int)
    st.index.name = "TOWNNAME"
    bnd = gpd.read_file(CASE / "行政區建物分析" / "shp" / "臺北市行政區_建物交易分析.shp", encoding="utf-8")[["TOWNID", "TOWNNAME", "geometry"]].to_crs(3826)
    g = bnd.merge(st.reset_index(), on="TOWNNAME", how="left")
    assert len(g) == 12 and g["AGE_AVG"].notna().all()
    v = g["AGE_AVG"].to_numpy(float)
    edges = np.quantile(v, [0.2, 0.4, 0.6, 0.8])           # 分位數 5 級（每級約 2～3 區）
    hi_b = [float(e) for e in edges] + [float(v.max())]
    lo = [float(v.min())] + [float(e) for e in edges]
    yb = np.digitize(v, edges, right=True)

    class _C:  # 與 mapclassify 介面相容的簡單容器
        pass
    clf = _C(); clf.yb = yb; clf.bins = hi_b
    bins = [{"lo": a, "hi": float(b), "label": f"{a:.1f}～{b:.1f} 年（{int((yb == i).sum())} 區）", "color": COLORS[i]} for i, (a, b) in enumerate(zip(lo, hi_b))]
    (OUT / "bins.json").write_text(json.dumps(bins, ensure_ascii=False), encoding="utf-8")
    g.to_file(OUT / "臺北市行政區_成交時屋齡_全年.shp", driver="ESRI Shapefile", encoding="utf-8")
    pd.DataFrame({"欄位": ["TOWNID", "TOWNNAME", "N_AGE", "AGE_MED", "AGE_AVG", "AGE_P25", "AGE_P75"],
                  "說明": ["行政區代碼", "行政區", "有建物且屋齡可算出的買賣交易筆數", "成交時屋齡中位數（年）", "成交時屋齡平均（年）", "第 25 百分位", "第 75 百分位"]}
                 ).to_csv(OUT / "欄位說明.csv", index=False, encoding="utf-8-sig")
    fig, ax = plt.subplots(figsize=(8, 9.2))
    g.assign(_c=[COLORS[i] for i in clf.yb]).plot(ax=ax, color=[COLORS[i] for i in clf.yb], edgecolor="#555", linewidth=0.8)
    for (_, r), pt in zip(g.iterrows(), g.representative_point()):
        ax.annotate(f"{r['TOWNNAME']}\n{r['AGE_AVG']:.1f}", (pt.x, pt.y), ha="center", va="center", fontsize=8.5, weight="bold",
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.65))
    ax.legend(handles=[Patch(facecolor=b["color"], edgecolor="#555", label=b["label"]) for b in bins], title="成交時屋齡平均（分位數 5 級）", loc="lower left", fontsize=8.5, title_fontsize=9.5)
    ax.set_axis_off()
    ax.set_title("臺北市各行政區成交時屋齡平均\n實價登錄買賣 105～114 年，有建物且屋齡可算出者（159,007 筆）", fontsize=12)
    fig.text(0.5, 0.01, "屋齡＝交易年－建築完成年；資料：內政部實價登錄；界線：內政部鄉鎮市區界；EPSG:3826", ha="center", fontsize=7.5, color="#555")
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(OUT / "圖_成交時屋齡平均.png", dpi=160); plt.close(fig)
    im = Image.open(OUT / "圖_成交時屋齡平均.png").convert("RGB")
    im.resize((1000, int(im.height * 1000 / im.width)), Image.LANCZOS).save(OUT / "圖_成交時屋齡平均_手機版.jpg", quality=88)
    print(g.drop(columns="geometry").sort_values("AGE_AVG").to_string(index=False))
    print([b["label"] for b in bins])


if __name__ == "__main__":
    main()
