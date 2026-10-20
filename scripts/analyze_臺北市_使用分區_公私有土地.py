"""臺北市各行政區 × 都市計畫使用分區的公有土地與私有土地面積比例。

分區：都發局使用分區圖（fetch_臺北市_使用分區圖_都發局.py，ublock97-TWD97，17,039 個多邊形，其中 768 個無圖形略過）；
  以 usekin 歸為 住宅區、商業區、工業區、公共設施用地（公園綠地、學校、機關、交通、市場、其他公共設施）、保護區、農業區、行水區、國家公園、其他專用區。
公有：地政局公有土地圖層（build_臺北市公有土地_shp.py，148,017 個地號，含 17,670 個公私共有地號）。公有面積＝地號與分區交集面積 × 公有持分
  （1－OWN_PER1 私有持分；OWN_PER_AL 恆為 100，是各類持分的總和，不是公有持分）。私有＝分區面積－公有面積（含無地號的水域道路等，未再細分）。
行政區：行政區建物分析 shp 的行政區界。
輸出：案件/臺北市_不動產交易分析/使用分區公私有土地/總表.xlsx、圖1_公有占比熱度圖、圖2_各行政區公私有比例、圖3_全市各分區公私有面積；行政區×分區 shp
執行：python scripts/analyze_臺北市_使用分區_公私有土地.py
"""
import glob
import io
import json
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from PIL import Image
from shapely.geometry import shape

warnings.filterwarnings("ignore")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent
CASE = ROOT / "案件" / "臺北市_不動產交易分析"
OUT = CASE / "使用分區公私有土地"
plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "PMingLiU", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False
DIST = ["中山區", "大同區", "中正區", "萬華區", "松山區", "大安區", "信義區", "內湖區", "南港區", "士林區", "北投區", "文山區"]
CLS = ["住宅區", "商業區", "工業區", "公共設施用地", "保護區", "農業區", "行水區", "國家公園", "其他專用區"]
PUBLIC_FAC = {"公園綠地", "學校用地", "機關用地", "交通用地", "公共設施", "市場用地"}


def cls_of(k):
    if k in ("住宅區", "商業區", "工業區", "保護區", "農業區", "行水區", "國家公園"):
        return k
    return "公共設施用地" if k in PUBLIC_FAC else "其他專用區"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    recs, geoms = [], []
    for f in sorted(glob.glob(str(ROOT / "資料庫" / "原始檔" / "臺北市使用分區圖_ublock97" / "page_*.json"))):
        for x in json.load(open(f, encoding="utf-8"))["features"]:
            if x["geometry"]:
                recs.append({"kin": x["properties"]["usekin"], "mem": x["properties"]["usemem"]})
                geoms.append(shape(x["geometry"]).buffer(0))
    z = gpd.GeoDataFrame(recs, geometry=geoms, crs=3826)
    z["cls"] = z["kin"].map(cls_of)
    bnd = gpd.read_file(CASE / "行政區建物分析" / "shp" / "臺北市行政區_建物交易分析.shp", encoding="utf-8").to_crs(3826)[["TOWNNAME", "geometry"]].rename(columns={"TOWNNAME": "TOWN"})
    bnd["geometry"] = bnd.geometry.buffer(0)
    zd = gpd.overlay(z[["cls", "geometry"]], bnd, how="intersection", keep_geom_type=True)
    zd["geometry"] = zd.geometry.buffer(0)
    zd = zd[zd.area > 0].reset_index(drop=True)
    zd["PID"] = zd.index
    print(f"分區多邊形 {len(z):,}（總面積 {z.area.sum() / 1e6:.1f} km²）→ 切行政區後 {len(zd):,}；分區重疊面積 {max(0, z.area.sum() - z.unary_union.area) / 1e6:.2f} km²")
    p = gpd.read_file(CASE / "公有土地" / "臺北市公有土地.shp", encoding="utf-8", columns=["OWN_PER1", "AA10_1"])
    p["w"] = (1 - pd.to_numeric(p["OWN_PER1"], errors="coerce").fillna(0) / 100).clip(0, 1)   # OWN_PER1＝私有持分（%）；公私共有地號只計公有持分
    p["geometry"] = p.geometry.buffer(0)
    print(f"公有土地地號 {len(p):,}；公有持分<100% 者 {int((p['w'] < 0.9999).sum()):,}（公私共有）；圖形面積 {p.area.sum() / 1e6:.1f} km²")
    ix = gpd.overlay(p[["w", "geometry"]], zd[["PID", "geometry"]], how="intersection", keep_geom_type=True)
    ix["a"] = ix.area
    ix["pub"] = ix["a"] * ix["w"]
    pub = ix.groupby("PID").agg(PUB=("pub", "sum"), PUBFULL=("a", "sum"))
    zd = zd.join(pub, on="PID").fillna({"PUB": 0, "PUBFULL": 0})
    zd["AREA"] = zd.area
    t = zd.groupby(["TOWN", "cls"]).agg(AREA=("AREA", "sum"), PUB=("PUB", "sum"), PUBFULL=("PUBFULL", "sum")).reset_index()
    allc = zd.groupby("cls").agg(AREA=("AREA", "sum"), PUB=("PUB", "sum"), PUBFULL=("PUBFULL", "sum")).reset_index()
    allc["TOWN"] = "全市"
    alld = zd.groupby("TOWN").agg(AREA=("AREA", "sum"), PUB=("PUB", "sum"), PUBFULL=("PUBFULL", "sum")).reset_index()
    alld["cls"] = "全部分區"
    tot = pd.DataFrame([{"TOWN": "全市", "cls": "全部分區", "AREA": zd["AREA"].sum(), "PUB": zd["PUB"].sum(), "PUBFULL": zd["PUBFULL"].sum()}])
    T = pd.concat([t, allc, alld, tot], ignore_index=True)
    T["PRI"] = (T["AREA"] - T["PUB"]).clip(lower=0)
    T["pub_pct"] = T["PUB"] / T["AREA"] * 100
    T["pri_pct"] = 100 - T["pub_pct"]
    for c_ in ("AREA", "PUB", "PRI"):
        T[c_ + "_ha"] = T[c_] / 1e4
    pv = T.pivot(index="TOWN", columns="cls", values="pub_pct").reindex(DIST + ["全市"])[CLS + ["全部分區"]]
    av = T.pivot(index="TOWN", columns="cls", values="AREA_ha").reindex(DIST + ["全市"])[CLS + ["全部分區"]]
    print("全市各分區 公有占比%：", T[T["TOWN"] == "全市"].set_index("cls")["pub_pct"].round(1).to_dict())
    print("全市各分區 面積公頃：", T[T["TOWN"] == "全市"].set_index("cls")["AREA_ha"].round(0).to_dict())
    print(pv.round(1).to_string())
    print(av.round(0).to_string())
    # Excel（唯一一張總表）
    wb = Workbook()
    ws = wb.active
    ws.title = "公私有土地比例"
    ws.append(["臺北市各行政區 × 使用分區：公有與私有土地面積比例（公有面積依公有持分計；面積：公頃）"])
    ws.append(["行政區", "使用分區", "分區面積(公頃)", "公有面積(公頃)", "私有面積(公頃)", "公有占比%", "私有占比%"])
    order = {n: i for i, n in enumerate(["全市"] + DIST)}
    co = {n: i for i, n in enumerate(["全部分區"] + CLS)}
    for _, r in T.sort_values(["TOWN", "cls"], key=lambda s: s.map(order) if s.name == "TOWN" else s.map(co)).iterrows():
        ws.append([r["TOWN"], r["cls"], round(r["AREA_ha"], 1), round(r["PUB_ha"], 1), round(r["PRI_ha"], 1), round(r["pub_pct"], 1), round(r["pri_pct"], 1)])
    ws.append(["註：分區面積為都發局使用分區圖多邊形與行政區界的交集；公有為公有土地圖層（地政局）地號與分區的交集面積，公私共有地號只計公有持分（1－私有持分）；私有＝分區面積－公有面積，含無地號的水域與道路。"])
    for c_ in ws[2]:
        c_.font = Font(bold=True)
        c_.fill = PatternFill("solid", fgColor="E8EDF4")
        c_.alignment = Alignment(horizontal="center")
    ws["A1"].font = Font(bold=True, size=12)
    for i, w in enumerate([10, 14, 14, 14, 14, 11, 11], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A3"
    wb.save(OUT / "總表.xlsx")
    dis = zd.dissolve(by=["TOWN", "cls"], aggfunc={"AREA": "sum", "PUB": "sum"}).reset_index()
    dis["PUB_PCT"] = (dis["PUB"] / dis["AREA"] * 100).round(1)
    dis["AREA_HA"] = (dis["AREA"] / 1e4).round(1)
    dis["PUB_HA"] = (dis["PUB"] / 1e4).round(1)
    dis.rename(columns={"cls": "ZONE_CLS"})[["TOWN", "ZONE_CLS", "AREA_HA", "PUB_HA", "PUB_PCT", "geometry"]].to_file(OUT / "行政區_使用分區_公有占比_持分加權.shp", driver="ESRI Shapefile", encoding="utf-8")

    def save(fig, name, w=1100):
        f = OUT / f"{name}.png"
        fig.savefig(f, dpi=150)
        plt.close(fig)
        im = Image.open(f).convert("RGB")
        im.resize((w, int(im.height * w / im.width)), Image.LANCZOS).save(OUT / f"{name}_手機版.jpg", quality=88)
    # 圖1 熱度圖
    fig, ax = plt.subplots(figsize=(11.5, 7.2))
    M = pv.to_numpy(dtype=float)
    im = ax.imshow(np.nan_to_num(M, nan=-1), cmap="YlOrRd", vmin=0, vmax=100, aspect="auto")
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            if np.isnan(M[i, j]) or av.iloc[i, j] < 0.5:
                ax.text(j, i, "—", ha="center", va="center", fontsize=9, color="#999")
            else:
                ax.text(j, i, f"{M[i, j]:.0f}", ha="center", va="center", fontsize=9.5, color="white" if M[i, j] > 62 else "#222")
    ax.set_xticks(range(M.shape[1]))
    ax.set_xticklabels(CLS + ["全部分區"], fontsize=9.5, rotation=20)
    ax.set_yticks(range(M.shape[0]))
    ax.set_yticklabels(pv.index, fontsize=10)
    ax.axhline(11.5, color="#333", lw=1)
    ax.axvline(8.5, color="#333", lw=1)
    cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cb.set_label("公有土地占比（%）")
    ax.set_title("臺北市各行政區 × 使用分區：公有土地面積占比（%）", fontsize=13, loc="left")
    fig.text(0.01, 0.01, "資料：都發局使用分區圖、地政局公有土地圖層（公私共有地號依公有持分計）；「—」為該區無此分區或面積不足 0.5 公頃", fontsize=7.5, color="#555")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    save(fig, "圖1_公有占比熱度圖")
    # 圖2 各行政區
    fig, axs = plt.subplots(3, 4, figsize=(15, 10), sharex=True)
    for ax, d in zip(axs.ravel(), DIST):
        s = T[(T["TOWN"] == d) & (T["cls"].isin(CLS))].set_index("cls").reindex(CLS).dropna(subset=["AREA"])
        s = s[s["AREA_ha"] >= 1]
        y = np.arange(len(s))
        ax.barh(y, s["pub_pct"], color="#C0392B", height=0.7)
        ax.barh(y, s["pri_pct"], left=s["pub_pct"], color="#BFD4E8", height=0.7)
        for yi, (_, r) in zip(y, s.iterrows()):
            ax.text(1.5, yi, f"{r['pub_pct']:.0f}", va="center", fontsize=7.5, color="white" if r["pub_pct"] > 8 else "#C0392B")
        ax.set_yticks(y)
        ax.set_yticklabels([f"{c_}（{a:.0f}公頃）" for c_, a in zip(s.index, s["AREA_ha"])], fontsize=7.5)
        ax.invert_yaxis()
        ax.set_xlim(0, 100)
        ax.set_title(f"{d}（公有 {T[(T.TOWN == d) & (T.cls == '全部分區')]['pub_pct'].iloc[0]:.0f}%）", fontsize=10)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
    fig.legend([plt.Rectangle((0, 0), 1, 1, color="#C0392B"), plt.Rectangle((0, 0), 1, 1, color="#BFD4E8")], ["公有", "私有"], loc="lower center", ncol=2, frameon=False)
    fig.suptitle("各行政區各使用分區的公有與私有土地比例（%，括號為分區面積）", fontsize=13.5, y=0.995)
    fig.tight_layout(rect=(0, 0.03, 1, 0.97))
    save(fig, "圖2_各行政區公私有比例", 1300)
    # 圖3 全市
    s = T[(T["TOWN"] == "全市") & (T["cls"].isin(CLS))].set_index("cls").reindex(CLS)
    fig, ax = plt.subplots(figsize=(10, 5.4))
    y = np.arange(len(s))
    ax.barh(y, s["PUB_ha"], color="#C0392B", label="公有")
    ax.barh(y, s["PRI_ha"], left=s["PUB_ha"], color="#BFD4E8", label="私有")
    for yi, (_, r) in zip(y, s.iterrows()):
        ax.text(r["AREA_ha"] + 80, yi, f"{r['pub_pct']:.0f}%公有（{r['AREA_ha']:,.0f}公頃）", va="center", fontsize=9)
    ax.set_yticks(y)
    ax.set_yticklabels(s.index)
    ax.invert_yaxis()
    ax.set_xlim(0, s["AREA_ha"].max() * 1.4)
    ax.set_xlabel("面積（公頃）")
    ax.legend(loc="lower right", frameon=False)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.set_title("臺北市各使用分區的公有與私有土地面積（全市）", fontsize=12.5, loc="left")
    fig.tight_layout()
    save(fig, "圖3_全市各分區公私有面積")


if __name__ == "__main__":
    main()
