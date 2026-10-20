"""近十年（105/1～114/12）臺北市土地開發熱區，三種交易分開統計，皆以小段（552 個）的「交易筆數」計，不除以面積。

三類：
  土地買賣：kind a、交易標的＝土地；僅計開發用地（排除公共設施用地，全筆或持分 ≥ 10%）
  二手房屋：kind a、交易標的＝房地（土地+建物）或房地+車位，含新成屋未滿一年者；不分屋齡
  預售屋　：kind b、交易標的＝房地（土地+建物）或房地+車位；每戶一筆（另列案數：土地地號組合不重複）
小段歸屬：每筆交易所附土地明細中出現最多次的地段。
熱區＝該類筆數在有交易小段中前 10% 且筆數 ≥ 10。
輸出：案件/臺北市_不動產交易分析/土地開發熱區_三類/小段_三類交易筆數.shp、圖_土地買賣／二手房屋／預售屋 熱區（PNG＋手機版）、圖_三類並列
執行：python scripts/analyze_臺北市_土地開發熱區_三類.py
"""
import importlib.util
import sqlite3
import warnings
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch
from PIL import Image

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent


def _load(name, fn):
    s = importlib.util.spec_from_file_location(name, ROOT / "scripts" / fn)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    return m
H = _load("heat", "analyze_臺北市_土地開發熱區.py")           # 用 sections()；載入時已把 stdout 設為 UTF-8（勿再載入 base10，會重複包裝 stdout）
B = H.B                                                       # zone()
CASE = ROOT / "案件" / "臺北市_不動產交易分析"
OUT = CASE / "土地開發熱區_三類"
plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "PMingLiU", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False
D0, D1 = 1050101, 1141231
TYPES = [("N_LAND", "土地買賣", "#4C78A8", ["#F3F3F3", "#DCE9F5", "#A9C8E4", "#4C78A8", "#12385F"]),
         ("N_USED", "二手房屋", "#F58518", ["#F3F3F3", "#FFFFB2", "#FECC5C", "#FD8D3C", "#E31A1C"]),
         ("N_PRE", "預售屋", "#54A24B", ["#F3F3F3", "#E5F2DC", "#B5DBA0", "#6BBF5E", "#1E6B2E"])]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sec = H.sections()
    c = sqlite3.connect(ROOT / "資料庫" / "lvr.sqlite")
    q = ("select t.kind, t.編號 as id, t.交易標的, t.交易日 from lvr_tx t where t.county='臺北市' and t.交易日 between %d and %d and "
         "((t.kind='a' and (t.交易標的='土地' or t.交易標的 like '房地%%')) or (t.kind='b' and t.交易標的 like '房地%%'))" % (D0, D1))
    tx = pd.read_sql(q, c)
    ld = pd.read_sql("select l.kind as kind, l.編號 as id, l.土地位置 as seg, l.地號 as no8, l.面積 as area, l.使用分區或編定 as zn, l.持分分母 as dn, l.持分分子 as nu "
                     "from lvr_land l join lvr_tx t on t.kind=l.kind and t.編號=l.編號 where t.county='臺北市' and t.交易日 between %d and %d" % (D0, D1), c)
    ld["zone"] = ld["zn"].apply(B.zone)
    ld["ratio"] = pd.to_numeric(ld["nu"], errors="coerce") / pd.to_numeric(ld["dn"], errors="coerce")
    ld["key"] = ld["seg"].fillna("") + ld["no8"].fillna("")

    def agg(d):
        r = d.loc[d["area"].idxmax()] if d["area"].notna().any() else d.iloc[0]
        return pd.Series({"seg": d["seg"].value_counts().index[0], "zone": r["zone"], "ratio": d["ratio"].max(), "proj": "|".join(sorted(set(d["key"])))})
    s = ld.groupby(["kind", "id"]).apply(agg).reset_index()
    tx = tx.merge(s, on=["kind", "id"], how="left")
    tx["年"] = tx["交易日"] // 10000
    print(f"交易 {len(tx):,} 筆（無土地明細 {int(tx['seg'].isna().sum())}，對不到小段 {int((~tx['seg'].isin(sec['KCNT']) & tx['seg'].notna()).sum())}）")
    land = tx[(tx["kind"] == "a") & (tx["交易標的"] == "土地")]
    keep = (land["zone"] != "公共設施用地") & (land["ratio"] >= 0.10)
    print(f"純土地買賣 {len(land):,} 筆 → 開發用地 {int(keep.sum()):,} 筆（公共設施用地 {int((land['zone'] == '公共設施用地').sum()):,}）")
    sets = {"N_LAND": land[keep], "N_USED": tx[(tx["kind"] == "a") & tx["交易標的"].str.startswith("房地")], "N_PRE": tx[tx["kind"] == "b"]}
    g = sec.copy()
    for k, d in sets.items():
        g[k] = g["KCNT"].map(d.groupby("seg").size()).fillna(0).astype(int)
    g["CASE_PRE"] = g["KCNT"].map(sets["N_PRE"].drop_duplicates("proj").groupby("seg").size()).fillna(0).astype(int)
    bnd = gpd.read_file(CASE / "行政區建物分析" / "shp" / "臺北市行政區_建物交易分析.shp", encoding="utf-8").to_crs(3826)[["TOWNNAME", "geometry"]]
    pts = g.copy(); pts["geometry"] = g.representative_point()
    g["TOWN"] = gpd.sjoin(pts, bnd, how="left", predicate="within")["TOWNNAME"].values
    for k in sets:
        v = g[k]; cut = v[v > 0].quantile(0.9)
        g["H_" + k[2:]] = ((v >= cut) & (v >= 10)).astype(int)
        print(f"{k}：總 {int(v.sum()):,} 筆；有交易小段 {int((v > 0).sum())}；熱區門檻 ≥ {cut:.0f} 筆；熱區 {int(g['H_' + k[2:]].sum())} 個，占筆數 {g.loc[g['H_' + k[2:]] == 1, k].sum() / v.sum() * 100:.1f}%")
    out = g.rename(columns={"KCNT": "SECTION", "AA48": "SEC_CODE"})[["SECTION", "SEC_CODE", "TOWN", "KM2", "N_LAND", "N_USED", "N_PRE", "CASE_PRE", "H_LAND", "H_USED", "H_PRE", "geometry"]]
    out["KM2"] = out["KM2"].round(3)
    out.to_file(OUT / "小段_三類交易筆數.shp", driver="ESRI Shapefile", encoding="utf-8")
    for k, nm, _, _ in TYPES:
        print(f"\n=== {nm} 前 10 小段 ===")
        print(out.sort_values(k, ascending=False).head(10)[["SECTION", "TOWN", k]].to_string(index=False))
        print(f"{nm} 各行政區：", out.groupby("TOWN")[k].sum().sort_values(ascending=False).to_dict())
        print(f"{nm} 年度：", sets[k].groupby("年").size().to_dict())
    # 地圖
    def draw(ax, k, nm, cols, title_extra=""):
        v = out[k]
        pos = v[v > 0]
        edges = [0, 1] + [float(np.ceil(pos.quantile(p))) for p in (0.5, 0.8, 0.95)]
        edges = sorted(set(edges)); 
        cls = np.digitize(v.to_numpy(), edges[1:], right=False) if False else np.searchsorted(edges, v.to_numpy(), side="right") - 1
        cls = np.clip(cls, 0, len(cols) - 1)
        out.plot(ax=ax, color=[cols[i] for i in cls], edgecolor="white", linewidth=0.25)
        out[out["H" + k[1:]] == 1].boundary.plot(ax=ax, color="#4a0d67", linewidth=1.4)
        bnd.boundary.plot(ax=ax, color="#555", linewidth=0.6)
        for _, r in out.sort_values(k, ascending=False).head(8).iterrows():
            p = r.geometry.representative_point(); ax.annotate(f"{r['SECTION']}\n{int(r[k])}", (p.x, p.y), ha="center", fontsize=6.5, color="#222", bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.75))
        labs = ["0 筆", f"1～{int(edges[2]) - 1 if len(edges) > 2 else 1}"] + [f"{int(edges[i])}～{int(edges[i + 1]) - 1}" for i in range(2, len(edges) - 1)] + [f"{int(edges[-1])} 以上"]
        labs = labs[:len(cols)]
        n = np.bincount(cls, minlength=len(cols))
        ax.legend(handles=[Patch(facecolor=c_, edgecolor="#999", linewidth=0.3, label=f"{l_}（{m} 個小段）") for c_, l_, m in zip(cols, labs, n)] + [Patch(facecolor="none", edgecolor="#4a0d67", linewidth=1.6, label=f"熱區（{int(out['H' + k[1:]].sum())} 個小段）")],
                  title=f"{nm}交易筆數", loc="lower left", fontsize=7.5, title_fontsize=8.5, framealpha=0.95)
        ax.set_axis_off()
        ax.set_title(f"{nm}（共 {int(v.sum()):,} 筆）{title_extra}", fontsize=11.5)
    for k, nm, _, cols in TYPES:
        fig, ax = plt.subplots(figsize=(8.5, 10))
        draw(ax, k, nm, cols)
        fig.suptitle(f"臺北市近十年土地開發熱區：{nm}（105～114 年，以小段交易筆數計）", fontsize=12.5, y=0.98)
        fig.text(0.5, 0.01, "資料：內政部實價登錄；小段界：地政局段界圖層；紫框＝該類筆數前 10% 且 10 筆以上；EPSG:3826", ha="center", fontsize=7.5, color="#555")
        fig.tight_layout(rect=(0, 0.02, 1, 0.96))
        f = OUT / f"圖_{nm}熱區.png"; fig.savefig(f, dpi=170); plt.close(fig)
        im = Image.open(f).convert("RGB"); im.resize((1000, int(im.height * 1000 / im.width)), Image.LANCZOS).save(OUT / f"圖_{nm}熱區_手機版.jpg", quality=88)
    fig, axs = plt.subplots(1, 3, figsize=(19, 8.5))
    for ax, (k, nm, _, cols) in zip(axs, TYPES):
        draw(ax, k, nm, cols)
    fig.suptitle("臺北市近十年土地開發熱區：三類交易並列（105～114 年，小段交易筆數）", fontsize=14, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.96)); fig.savefig(OUT / "圖_三類並列.png", dpi=150); plt.close(fig)


if __name__ == "__main__":
    main()
