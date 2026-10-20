"""臺北市中山區交易土地的權屬（移轉情形與持分）分析 → 表、圖、地號面 shp。

資料：資料庫/lvr.sqlite（實價登錄買賣，交易日 105/10～114/12）的土地明細；開放資料只有「移轉情形（全筆／持分）」與「持分分子／分母」，
  不含買賣雙方身分，因此這裡的「權屬」指移轉型態與持分，不是所有權人（公有／私有）。
範圍：官方段名屬中山區的 36 個段（來自 地號清單/不重複地號清單_中山區_官方去重.csv 的段名）；一個（段，地號）為一個地號。
幾何：地號清單/中山區_全量/中山區_全部OK.shp（農業部界址；6,586 個，改號與回傳別筆地者無幾何）。
輸出：案件/臺北市_不動產交易分析/中山區_權屬/
執行：python scripts/analyze_中山區_交易土地權屬.py
"""
import importlib.util
import io
import sqlite3
import sys
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
spec = importlib.util.spec_from_file_location("base10", ROOT / "scripts" / "analyze_臺北市_實價登錄_10年.py")
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)
CASE = ROOT / "案件" / "臺北市_不動產交易分析"
OUT = CASE / "中山區_權屬"
GEOM = CASE / "地號清單" / "中山區_全量" / "中山區_全部OK.shp"
LIST = CASE / "地號清單" / "不重複地號清單_中山區_官方去重.csv"
BND = CASE / "行政區建物分析" / "shp" / "臺北市行政區_建物交易分析.shp"
plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "PMingLiU", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False
LEVELS = [(0.9999, 1.01, "全筆移轉（持分 100%）"), (0.5, 0.9999, "50%～未滿 100%"), (0.25, 0.5, "25%～未滿 50%"), (0.10, 0.25, "10%～未滿 25%"),
          (0.05, 0.10, "5%～未滿 10%"), (0.01, 0.05, "1%～未滿 5%"), (0.001, 0.01, "0.1%～未滿 1%"), (0, 0.001, "未滿 0.1%")]
TYPES = ["全筆移轉（無持分交易）", "全筆與持分混合", "持分：中位持分 25% 以上", "持分：中位持分 5～25%", "持分：中位持分 1～5%", "持分：中位持分 <1%"]
TCOL = ["#1B7837", "#A6DBA0", "#762A83", "#9970AB", "#C2A5CF", "#E7D4E8"]


def mid(d):
    return f"{d['母']}-{d['子']}" if d["子"] else f"{d['母']}"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    segs = set(pd.read_csv(LIST, dtype=str)["官方段名"])
    c = sqlite3.connect(ROOT / "資料庫" / "lvr.sqlite")
    l = pd.read_sql("select l.編號, l.土地位置, l.面積, l.使用分區或編定, l.持分分母, l.持分分子, l.移轉情形, l.地號, t.交易標的, t.交易日 "
                    "from lvr_land l join lvr_tx t on t.kind=l.kind and t.編號=l.編號 "
                    "where t.county='臺北市' and l.kind='a' and t.交易日 between 1051001 and 1141231", c)
    z = l[l["土地位置"].isin(segs)].copy()
    z["比"] = pd.to_numeric(z["持分分子"], errors="coerce") / pd.to_numeric(z["持分分母"], errors="coerce")
    z["年"] = z["交易日"] // 10000
    z["分區"] = z["使用分區或編定"].apply(B.zone)
    z["標的"] = z["交易標的"].map(lambda s: "純土地" if s == "土地" else "房地（含車位）" if s.startswith("房地") else "純車位／純建物")
    z["全筆"] = z["移轉情形"] == "全筆移轉"
    z["母"] = z["地號"].str[:4].astype(int); z["子"] = z["地號"].str[4:].astype(int)
    z["地號名"] = z.apply(mid, axis=1)
    assert z["比"].notna().all() and ((z["比"] > 0) & (z["比"] <= 1)).all()
    T = {}

    # 表 A：級距與移轉情形
    z["持分級距"] = pd.cut(z["比"], [lo for lo, _, _ in reversed(LEVELS)] + [1.01], right=False, labels=[n for _, _, n in reversed(LEVELS)])
    a = z["持分級距"].value_counts().reindex([n for _, _, n in LEVELS]).rename("土地列數").to_frame()
    a["占比%"] = (a["土地列數"] / a["土地列數"].sum() * 100).round(1)
    T["A1_持分比級距分布"] = a
    T["A2_交易標的×移轉情形"] = pd.crosstab(z["標的"], z["移轉情形"], margins=True, margins_name="合計")
    t = pd.crosstab(z["分區"], z["移轉情形"])
    t["合計"] = t.sum(axis=1)
    t["持分移轉占比%"] = (t["持分移轉"] / t["合計"] * 100).round(1)
    t["持分比中位數%"] = (z[~z["全筆"]].groupby("分區")["比"].median() * 100).round(2)
    T["A3_使用分區×移轉情形"] = t.sort_values("合計", ascending=False)
    y = pd.crosstab(z["年"], z["移轉情形"])
    y["合計"] = y.sum(axis=1); y["持分移轉占比%"] = (y["持分移轉"] / y["合計"] * 100).round(1)
    T["A4_年度×移轉情形"] = y

    # 地號層級
    g = z.groupby(["土地位置", "地號名"])
    p = pd.DataFrame({"N_TX": g.size(), "N_FULL": g["全筆"].sum(), "SH_MED": g.apply(lambda d: d.loc[~d["全筆"], "比"].median()),
                      "SH_MAX": g.apply(lambda d: d.loc[~d["全筆"], "比"].max()), "SH_SUM": g.apply(lambda d: d.loc[~d["全筆"], "比"].sum()),
                      "N_LONLY": g.apply(lambda d: (d["標的"] == "純土地").sum()), "N_BLDG": g.apply(lambda d: (d["標的"] == "房地（含車位）").sum()),
                      "ZONE": g["分區"].agg(lambda s: s.value_counts().index[0]), "LAST_YR": g["年"].max()}).reset_index()
    p["N_SHARE"] = p["N_TX"] - p["N_FULL"].astype(int)
    p["N_FULL"] = p["N_FULL"].astype(int)
    p["P_FULL"] = (p["N_FULL"] / p["N_TX"] * 100).round(1)

    def typ(r):
        if r["N_SHARE"] == 0:
            return TYPES[0]
        if r["N_FULL"] > 0:
            return TYPES[1]
        m = r["SH_MED"]
        return TYPES[2] if m >= 0.25 else TYPES[3] if m >= 0.05 else TYPES[4] if m >= 0.01 else TYPES[5]
    p["TYPE"] = p.apply(typ, axis=1)
    for col in ("SH_MED", "SH_MAX", "SH_SUM"):
        p[col] = p[col].round(4)
    T["A5_地號權屬類型"] = p["TYPE"].value_counts().reindex(TYPES).rename("地號數").to_frame().assign(**{"占比%": lambda d: (d["地號數"] / d["地號數"].sum() * 100).round(1)})
    s = p.groupby("土地位置").agg(地號數=("N_TX", "size"), 交易列數=("N_TX", "sum"), 全筆移轉列數=("N_FULL", "sum"))
    s["持分移轉占比%"] = (100 - s["全筆移轉列數"] / s["交易列數"] * 100).round(1)
    s["地號持分比中位數%"] = (z[~z["全筆"]].groupby("土地位置")["比"].median() * 100).round(2)
    T["A6_各段權屬"] = s.sort_values("交易列數", ascending=False)

    # 幾何
    geo = gpd.read_file(GEOM, encoding="big5")
    seg_c = [x for x in geo.columns if x == "段"][0]
    geo["key"] = geo[seg_c] + "|" + geo["地號"].astype(str)
    p["key"] = p["土地位置"] + "|" + p["地號名"]
    reg = [x for x in geo.columns if x.startswith("登記")][0]
    m = geo[["key", reg, "geometry"]].merge(p, on="key", how="inner")
    m = m.rename(columns={"土地位置": "SECTION", "地號名": "LANDNO", reg: "REG_AREA"}).drop(columns="key")
    m = gpd.GeoDataFrame(m, geometry="geometry", crs=geo.crs)
    print(f"清單 {len(p):,} 個地號；有幾何 {len(m):,}；無幾何 {len(p) - len(m)}")
    m.to_file(OUT / "中山區_交易土地權屬.shp", driver="ESRI Shapefile", encoding="utf-8")
    p.drop(columns="key").to_csv(OUT / "中山區_地號權屬明細.csv", index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(OUT / "中山區_交易土地權屬分析表.xlsx", engine="openpyxl") as xw:
        for k, v in T.items():
            v.to_excel(xw, sheet_name=k[:31]); v.to_csv(OUT / f"表_{k}.csv", encoding="utf-8-sig")
    desc = {"SECTION": "段名", "LANDNO": "地號（母-子）", "REG_AREA": "登記面積（㎡）", "N_TX": "交易的土地列數（含重複交易）", "N_FULL": "全筆移轉次數",
            "SH_MED": "持分移轉的持分比中位數", "SH_MAX": "持分比最大值", "SH_SUM": "持分移轉的持分比累計（1＝相當於整筆地被移轉一輪）",
            "N_LONLY": "純土地交易次數", "N_BLDG": "房地（含車位）交易次數", "ZONE": "使用分區（出現最多者）", "LAST_YR": "最近交易年（民國）",
            "N_SHARE": "持分移轉次數", "P_FULL": "全筆移轉占比%", "TYPE": "權屬類型"}
    pd.DataFrame({"欄位": list(desc), "說明": list(desc.values())}).to_csv(OUT / "欄位說明.csv", index=False, encoding="utf-8-sig")

    # 圖 R1：持分級距＋使用分區
    fig, axs = plt.subplots(2, 1, figsize=(8, 9.4), gridspec_kw={"height_ratios": [1, 1.05]})
    ax = axs[0]
    a1 = T["A1_持分比級距分布"]
    cols = plt.get_cmap("Purples")(np.linspace(0.95, 0.25, len(a1)))
    cols[0] = (0.106, 0.471, 0.216, 1)
    ax.barh(a1.index[::-1], a1["占比%"][::-1], color=cols[::-1])
    for i, (v, n) in enumerate(zip(a1["占比%"][::-1], a1["土地列數"][::-1])):
        ax.text(v + 0.6, i, f"{v:.1f}%（{n:,}）", va="center", fontsize=9)
    ax.set_xlim(0, max(a1["占比%"]) * 1.3); ax.set_xlabel("占土地列數比例（%）")
    ax.set_title(f"圖R1a 中山區交易土地：每筆交易移轉的持分比分布（共 {len(z):,} 列）", fontsize=11, loc="left")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax = axs[1]
    zt = pd.crosstab(z["分區"], z["標的"])
    zt = zt.loc[zt.sum(axis=1).sort_values().index]
    pc = zt.div(zt.sum(axis=1), axis=0) * 100
    left = pd.Series(0.0, index=pc.index)
    for col, cc in zip(["房地（含車位）", "純土地", "純車位／純建物"], ["#4C78A8", "#F58518", "#BBBBBB"]):
        if col in pc.columns:
            ax.barh(pc.index, pc[col], left=left, color=cc, label=col)
            left += pc[col]
    pshare = (1 - z.groupby("分區")["全筆"].mean()).reindex(pc.index) * 100
    for i, (n, ps) in enumerate(zip(zt.sum(axis=1), pshare)):
        ax.text(101, i, f"{n:,} 列｜持分 {ps:.0f}%", va="center", fontsize=8.5)
    ax.set_xlim(0, 135); ax.set_xticks(range(0, 101, 20)); ax.set_xlabel("交易標的占比（%）")
    ax.legend(loc="lower center", bbox_to_anchor=(0.4, -0.3), ncol=3, frameon=False, fontsize=9)
    ax.set_title("圖R1b 依使用分區：交易標的組成（右側為土地列數與持分移轉占比）", fontsize=11, loc="left")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    fig.text(0.01, 0.005, "資料：內政部不動產交易實價查詢服務網，中山區 36 個段，交易日 105/10～114/12；開放資料不含買賣雙方身分，權屬指移轉型態與持分", fontsize=7, color="#555")
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(OUT / "圖R1_持分與使用分區.png", dpi=170); plt.close(fig)

    # 圖 R2：地圖
    bnd = gpd.read_file(BND, encoding="utf-8").to_crs(3826)
    zs = bnd[bnd["TOWNNAME"] == "中山區"]
    fig, ax = plt.subplots(figsize=(9, 10.5))
    zs.plot(ax=ax, color="#f3f3f3", edgecolor="#333", linewidth=1.2)
    m.plot(ax=ax, color=[TCOL[TYPES.index(t)] for t in m["TYPE"]], edgecolor="white", linewidth=0.12)
    zs.boundary.plot(ax=ax, color="#333", linewidth=1.2)
    cnt = m["TYPE"].value_counts()
    ax.legend(handles=[Patch(facecolor=c_, edgecolor="#999", linewidth=0.3, label=f"{t}：{cnt.get(t, 0):,}") for t, c_ in zip(TYPES, TCOL)],
              title=f"權屬類型（地號數，共 {len(m):,}）", loc="lower left", fontsize=9, title_fontsize=10, framealpha=0.95)
    x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
    nx, ny = x1 - (x1 - x0) * 0.06, y1 - (y1 - y0) * 0.07
    ax.annotate("N", (nx, ny - (y1 - y0) * 0.045), ha="center", fontsize=13, weight="bold")
    ax.annotate("", xy=(nx, ny), xytext=(nx, ny - (y1 - y0) * 0.04), arrowprops=dict(arrowstyle="-|>", color="k"))
    bx, by = x1 - (x1 - x0) * 0.05, y0 + (y1 - y0) * 0.05
    ax.plot([bx - 1000, bx], [by, by], color="k", lw=3); ax.text(bx - 500, by + (y1 - y0) * 0.008, "1 km", ha="center", fontsize=9)
    ax.set_axis_off()
    ax.set_title("臺北市中山區交易土地的權屬類型（移轉情形與持分）\n依地號歷次交易的全筆／持分移轉及持分比中位數分類", fontsize=12.5)
    fig.text(0.5, 0.012, "資料：實價登錄 105/10～114/12；界址：農業部地籍圖資（6,586 個，改號與回傳別筆地者未畫）；EPSG:3826", ha="center", fontsize=8, color="#555")
    fig.tight_layout(rect=(0, 0.025, 1, 1))
    fig.savefig(OUT / "圖R2_權屬類型地圖.png", dpi=170); plt.close(fig)
    for f in ("圖R1_持分與使用分區", "圖R2_權屬類型地圖"):
        im = Image.open(OUT / f"{f}.png").convert("RGB")
        im.resize((1100, int(im.height * 1100 / im.width)), Image.LANCZOS).save(OUT / f"{f}_手機版.jpg", quality=88)
    for k, v in T.items():
        print("\n##", k); print(v.head(12).to_string())


if __name__ == "__main__":
    main()
