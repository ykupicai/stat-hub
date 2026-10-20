"""全臺北市地籍圖 × 有容積率的使用分區 → 公有土地與私有土地比例（全市、依使用分區）。

輸入：
  地籍圖：資料庫/原始檔/臺北市地籍圖_LAND-ALL/page_*.json（fetch_臺北市_地籍圖_都發局.py，421,843 個地號，EPSG:3826）
  使用分區：分區容積使用/去重版/分區塊_容積使用狀況_去重.shp（15,511 個分區塊；FAR_LEG 為法定容積率，空值者視為無容積率，不納入）
  公有：公有土地/臺北市公有土地.shp（148,017 個地號；以 段碼＋地號 對應地籍圖，在其中者為公有，其餘為私有）
方法：地號面與分區塊求交集，依交集面積累計；公有＝地號在公有土地圖層內，私有＝其餘（含公私共有地號，圖層不含）。
  另以地號代表點所在的分區塊計地號數。
輸出：案件/臺北市_不動產交易分析/容積率分區公私有土地/總表.xlsx、圖1／圖2（PNG＋手機版）、臺北市地籍圖_公私有.shp（全市地號＋PUBLIC 欄）
執行：python scripts/analyze_臺北市_容積率分區_公私有土地.py
"""
import glob
import io
import json
import os
import re
import sys
import time
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
import shapely
from shapely.geometry import MultiPolygon, Polygon, shape

warnings.filterwarnings("ignore")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent
CASE = ROOT / "案件" / "臺北市_不動產交易分析"
NO_PF = os.environ.get("NO_PF") == "1"   # NO_PF=1：不計入公共設施用地（學校用地、機關與公用設施用地兩大類），輸出到「容積率分區公私有土地_不含公設」
RC_ONLY = os.environ.get("RC_ONLY") == "1"   # RC_ONLY=1：只統計住宅區與商業區，輸出到「容積率分區公私有土地_住宅商業區」
OUT = CASE / ("容積率分區公私有土地_住宅商業區" if RC_ONLY else "容積率分區公私有土地_不含公設" if NO_PF else "容積率分區公私有土地")
SUFFIX = "（只含住宅區與商業區）" if RC_ONLY else "（不含公共設施用地）" if NO_PF else ""
plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "PMingLiU", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False
TOPN = 14


def group_of(n):
    if re.search(r"專用區|風景區|文教區|行政區$|娛樂|保存|創意|業務設施|聯合開發|捷運開發|住商混合", n) and "學校" not in n and "大學" not in n:
        return "專用區與其他"
    if re.search(r"工業|工商|產業支援|軟體工業|汽車修護", n):
        return "工業區"
    if re.search(r"商業|特定業務區|辦公服務|一般商業|商業用地", n):
        return "商業區"
    if re.search(r"住宅區|住宅用地|市民住宅", n):
        return "住宅區"
    if re.search(r"國小|國中|高中|高職|大專|大學|學校", n):
        return "學校用地"
    return "機關與公用設施用地"


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    recs, geoms = [], []
    for f in sorted(glob.glob(str(ROOT / "資料庫" / "原始檔" / "臺北市地籍圖_LAND-ALL" / "page_*.json"))):
        for x in json.load(open(f, encoding="utf-8"))["features"]:
            p = x["properties"]
            recs.append({"key": p["sect_id"] + p["land_pnum"] + p["land_snum"], "SECT": p["sect_name"], "DIST": p["dist_name"], "LANDNO": p["land_no"]})
            geoms.append(shape(x["geometry"]))
    P = gpd.GeoDataFrame(recs, geometry=geoms, crs=3826)
    def polys(g):  # make_valid 對退化圖形可能產生線或集合，只保留面的部分
        g = shapely.make_valid(g)
        if g.geom_type in ("Polygon", "MultiPolygon"):
            return g
        parts = [q for q in getattr(g, "geoms", []) if q.geom_type in ("Polygon", "MultiPolygon")]
        return MultiPolygon([q for pp in parts for q in (pp.geoms if pp.geom_type == "MultiPolygon" else [pp])]) if parts else Polygon()
    P["geometry"] = P.geometry.apply(polys)
    log(f"圖形無面積（退化）的地號 {int((P.geometry.area == 0).sum()):,}")
    P["PID"] = np.arange(len(P))
    P["PAREA"] = P.area
    log(f"地號 {len(P):,}；不重複 key {P['key'].nunique():,}；總面積 {P['PAREA'].sum() / 1e6:.1f} km²")
    pub = gpd.read_file(CASE / "公有土地" / "臺北市公有土地.shp", encoding="utf-8", columns=["PL48", "PL49", "OWN_PER1"], ignore_geometry=True)
    pub["k"] = pub["PL48"].astype(str).str.zfill(4) + pub["PL49"].astype(str).str.zfill(8)
    # OWN_PER1＝私有持分（%）；公有持分＝1－私有持分。公私共有地號（約 1.77 萬個）只計公有持分的面積，其餘公有地號為全部公有
    pub["w"] = (1 - pd.to_numeric(pub["OWN_PER1"], errors="coerce").fillna(0) / 100).clip(0, 1)
    pubkeys = set(pub["k"])
    P["PUBW"] = P["key"].map(pub.groupby("k")["w"].max()).fillna(0)
    P["PUBLIC"] = (P["PUBW"] > 0).astype(int)
    log(f"公有地號 key {len(pubkeys):,}；對到地籍圖 {int(P['PUBLIC'].sum()):,}（地籍圖有 {int(P.loc[P['PUBLIC'] == 1, 'key'].nunique()):,} 個不重複 key；公有圖層中對不到者 {len(pubkeys - set(P['key'])):,}）")
    z = gpd.read_file(CASE / "分區容積使用" / "去重版" / "分區塊_容積使用狀況_去重.shp", encoding="utf-8").to_crs(3826)
    z = z[["ZONE_NAME", "FAR_LEG", "TOWN", "geometry"]].copy()
    n_all = len(z)
    z["FAR_LEG"] = pd.to_numeric(z["FAR_LEG"], errors="coerce")
    z = z[z["FAR_LEG"] > 0].copy()
    if RC_ONLY:
        z = z[z["ZONE_NAME"].map(group_of).isin(["住宅區", "商業區"])].copy()
        log(f"只統計住宅區與商業區，分區塊 {len(z):,}")
    elif NO_PF:
        z = z[~z["ZONE_NAME"].map(group_of).isin(["學校用地", "機關與公用設施用地"])].copy()
        log(f"不計入公共設施用地（學校用地、機關與公用設施用地）後，有容積率分區塊 {len(z):,}")
    z["geometry"] = z.geometry.make_valid()
    z["ZID"] = np.arange(len(z))
    log(f"分區塊 {n_all:,} → 有容積率 {len(z):,}（面積 {z.area.sum() / 1e6:.1f} km²）")
    t0 = time.time()
    ix = gpd.overlay(P[["PID", "PUBLIC", "PUBW", "geometry"]], z[["ZID", "geometry"]], how="intersection", keep_geom_type=True)
    ix["a"] = ix.area
    log(f"交集片 {len(ix):,}（{time.time() - t0:.0f} 秒）")
    ix = ix.merge(z[["ZID", "ZONE_NAME", "FAR_LEG"]], on="ZID")
    # 地號代表點所在分區塊（計地號數）
    pts = P[["PID", "PUBLIC"]].copy()
    pts["geometry"] = P.geometry.representative_point()
    pj = gpd.sjoin(gpd.GeoDataFrame(pts, geometry="geometry", crs=3826), z[["ZID", "ZONE_NAME", "geometry"]], how="inner", predicate="within")
    pj = pj.drop_duplicates("PID")
    log(f"代表點落在有容積率分區塊的地號 {len(pj):,}")
    # 彙總
    ix["pubA"] = ix["a"] * ix["PUBW"]
    ar = ix.groupby("ZONE_NAME").agg(PUB=("pubA", "sum"), AREA=("a", "sum"))
    ar["PRI"] = ar["AREA"] - ar["PUB"]
    ct = pj.groupby(["ZONE_NAME", "PUBLIC"]).size().unstack(fill_value=0).rename(columns={0: "N_PRI", 1: "N_PUB"})
    T = ar.join(ct, how="left").fillna(0)
    far = z.groupby("ZONE_NAME")["FAR_LEG"].agg(lambda s: "/".join(str(int(v)) for v in sorted(s.unique())[:4]))
    T["FAR"] = far
    T["pub_pct"] = T["PUB"] / T["AREA"] * 100
    T["n_pub_pct"] = T["N_PUB"] / (T["N_PUB"] + T["N_PRI"]) * 100
    T = T.sort_values("AREA", ascending=False)
    tot = T[["PRI", "PUB", "AREA", "N_PRI", "N_PUB"]].sum()
    log(f"全市有容積率分區：面積 {tot['AREA'] / 1e4:,.0f} 公頃；公有 {tot['PUB'] / 1e4:,.0f} 公頃（{tot['PUB'] / tot['AREA'] * 100:.1f}%）；私有 {tot['PRI'] / 1e4:,.0f} 公頃；地號 {int(tot['N_PRI'] + tot['N_PUB']):,}，公有 {int(tot['N_PUB']):,}（{tot['N_PUB'] / (tot['N_PRI'] + tot['N_PUB']) * 100:.1f}%）")
    print(T.head(25)[["FAR", "AREA", "PUB", "pub_pct", "N_PUB", "N_PRI", "n_pub_pct"]].assign(AREA=lambda d: (d.AREA / 1e4).round(0), PUB=lambda d: (d.PUB / 1e4).round(0), pub_pct=lambda d: d.pub_pct.round(1), n_pub_pct=lambda d: d.n_pub_pct.round(1)).to_string())
    # 以容積率級距彙整
    ix["FARC"] = pd.cut(ix["FAR_LEG"], [0, 100, 200, 300, 400, 600, 2000], labels=["100% 以下", "101～200%", "201～300%", "301～400%", "401～600%", "600% 以上"])
    F = ix.groupby("FARC").agg(PUB=("pubA", "sum"), AREA=("a", "sum"))
    F["PRI"] = F["AREA"] - F["PUB"]
    F["pub_pct"] = F["PUB"] / F["AREA"] * 100
    (OUT / "容積率級距.json").write_text(json.dumps({str(k): {"area_ha": float(r["AREA"] / 1e4), "pub_pct": float(r["pub_pct"])} for k, r in F.iterrows()}, ensure_ascii=False), encoding="utf-8")
    print((F.assign(AREA=lambda d: (d.AREA / 1e4).round(0))[["AREA", "pub_pct"]]).round(1).to_string())
    # Excel（唯一一張總表）
    wb = Workbook()
    ws = wb.active
    ws.title = "容積率分區公私有"
    ws.append(["臺北市有容積率之使用分區：公有與私有土地面積與地號數比例（地籍圖 421,843 個地號 × 分區塊；面積：公頃）"])
    ws.append(["使用分區", "法定容積率(%)", "分區面積(公頃)", "公有面積(公頃)", "私有面積(公頃)", "公有面積占比%", "私有面積占比%", "地號數", "含公有持分地號數", "含公有持分地號占比%"])
    ws.append(["全市合計", "", round(tot["AREA"] / 1e4, 1), round(tot["PUB"] / 1e4, 1), round(tot["PRI"] / 1e4, 1), round(tot["PUB"] / tot["AREA"] * 100, 1), round(tot["PRI"] / tot["AREA"] * 100, 1),
               int(tot["N_PRI"] + tot["N_PUB"]), int(tot["N_PUB"]), round(tot["N_PUB"] / (tot["N_PRI"] + tot["N_PUB"]) * 100, 1)])
    for nm, r in T.iterrows():
        ws.append([nm, r["FAR"], round(r["AREA"] / 1e4, 1), round(r["PUB"] / 1e4, 1), round(r["PRI"] / 1e4, 1), round(r["pub_pct"], 1), round(100 - r["pub_pct"], 1),
                   int(r["N_PRI"] + r["N_PUB"]), int(r["N_PUB"]), round(r["n_pub_pct"], 1) if r["N_PUB"] + r["N_PRI"] else None])
    ws.append(["註：有容積率＝分區塊法定容積率大於 0（保護區、農業區等若無容積率則不計）；面積以地號面與分區塊交集計；公有＝地政局公有土地圖層內地號，公私共有地號只計公有持分（1－私有持分）的面積，私有為其餘（含無地號的道路水域）；地號數以地號代表點所在分區塊計；法定容積率欄為該分區各分區塊的不同值。"])
    for c_ in ws[2]:
        c_.font = Font(bold=True)
        c_.fill = PatternFill("solid", fgColor="E8EDF4")
        c_.alignment = Alignment(horizontal="center", wrap_text=True)
    for c_ in ws[3]:
        c_.font = Font(bold=True)
    ws["A1"].font = Font(bold=True, size=12)
    for i, w in enumerate([18, 14, 13, 13, 13, 13, 13, 11, 11, 12], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A3"
    wb.save(OUT / "總表.xlsx")
    # 全市地籍圖 shp（附公私有）
    if not (NO_PF or RC_ONLY):
        P[["key", "SECT", "DIST", "LANDNO", "PUBLIC", "PUBW", "geometry"]].rename(columns={"key": "KEY"}).to_file(OUT / "臺北市地籍圖_公私有.shp", driver="ESRI Shapefile", encoding="utf-8")
        log("已寫地籍圖 shp")

    def save(fig, name, w=1100):
        f = OUT / f"{name}.png"
        fig.savefig(f, dpi=150)
        plt.close(fig)
        im = Image.open(f).convert("RGB")
        im.resize((w, int(im.height * w / im.width)), Image.LANCZOS).save(OUT / f"{name}_手機版.jpg", quality=88)
    top = T.head(TOPN).copy()
    rest = T.iloc[TOPN:]
    if len(rest):
        top.loc["其他分區"] = rest[["PRI", "PUB", "AREA"]].sum()
        top.loc["其他分區", "pub_pct"] = rest["PUB"].sum() / rest["AREA"].sum() * 100
    top.loc["全市合計"] = tot[["PRI", "PUB", "AREA"]]
    top.loc["全市合計", "pub_pct"] = tot["PUB"] / tot["AREA"] * 100
    fig, ax = plt.subplots(figsize=(10.5, 8))
    y = np.arange(len(top))
    pubp = top["pub_pct"].to_numpy()
    ax.barh(y, pubp, color="#C0392B", height=0.7, label="公有")
    ax.barh(y, 100 - pubp, left=pubp, color="#BFD4E8", height=0.7, label="私有")
    for yi, (nm, r) in zip(y, top.iterrows()):
        ax.text(1.2, yi, f"{r['pub_pct']:.0f}", va="center", fontsize=8.5, color="white" if r["pub_pct"] > 7 else "#C0392B")
    ax.set_yticks(y)
    ax.set_yticklabels([f"{n}（{r['AREA'] / 1e4:,.0f}公頃）" for n, r in top.iterrows()], fontsize=9)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.axhline(len(top) - 1.5, color="#333", lw=0.8)
    ax.set_xlabel("占分區面積比例（%）")
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.12), ncol=2, frameon=False)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.set_title("臺北市有容積率之使用分區：公有與私有土地面積比例" + SUFFIX, fontsize=13, loc="left")
    fig.text(0.01, 0.01, "資料：都發局地籍圖（421,843 地號）、容積使用分區塊、地政局公有土地圖層（公私共有地號依公有持分計）", fontsize=7.5, color="#555")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    save(fig, "圖1_各使用分區公私有面積比例")
    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    Fp = F.copy()
    ax.barh(range(len(Fp)), Fp["pub_pct"], color="#C0392B", height=0.65)
    ax.barh(range(len(Fp)), 100 - Fp["pub_pct"], left=Fp["pub_pct"], color="#BFD4E8", height=0.65)
    for yi, (nm, r) in enumerate(Fp.iterrows()):
        ax.text(1.2, yi, f"{r['pub_pct']:.0f}", va="center", fontsize=9, color="white" if r["pub_pct"] > 7 else "#C0392B")
    ax.set_yticks(range(len(Fp)))
    ax.set_yticklabels([f"{n}（{r['AREA'] / 1e4:,.0f}公頃）" for n, r in Fp.iterrows()])
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("占面積比例（%）　紅＝公有、藍＝私有")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.set_title("依法定容積率級距：公有土地面積占比" + SUFFIX, fontsize=12.5, loc="left")
    fig.tight_layout()
    save(fig, "圖2_容積率級距公私有面積比例")
    log("完成")


if __name__ == "__main__":
    main()
