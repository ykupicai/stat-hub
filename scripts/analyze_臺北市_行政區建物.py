"""臺北市各行政區的建物樓層、用途、建物型態分析（實價登錄房地買賣，105/10～115/6）＋分層設色圖＋shp。

沿用 analyze_臺北市_實價登錄_10年.py 的載入與欄位處理。行政區界線讀 local_paths.json 的「鄉鎮市區界線」（內政部 TOWN_MOI_*.shp）。
輸出：案件/臺北市_不動產交易分析/行政區建物分析/（表 CSV、分析表.xlsx、圖 M1～M3、shp/）。
口徑：母體＝房地買賣（交易標的含房地）；樓層、型態、用途、屋齡不排除特殊交易；單價排除特殊交易與 2 萬～150 萬元/㎡ 以外者。
      建物型態自 110 年起平台分類收斂（只剩住宅大樓、華廈、公寓、透天厝），故型態占比取 110 年起；主要用途 106 年以前空白較多，取 107 年起。
執行：python scripts/analyze_臺北市_行政區建物.py
"""
import importlib.util
import re
import sys
from pathlib import Path

import geopandas as gpd
import mapclassify
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from _local_paths import case_dir  # noqa: E402

spec = importlib.util.spec_from_file_location("base10", ROOT / "scripts" / "analyze_臺北市_實價登錄_10年.py")
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)
OUT = B.OUT / "行政區建物分析"
PING = B.PING
TYPES = ["住宅大樓", "華廈", "公寓", "透天厝"]
USES = ["住家用", "商業用", "辦公用", "工業用", "住商用"]


def first_floor(s):
    """移轉層次：取第一個樓層；「全」＝整棟，回 -1；地下層與無法判讀回 NaN。"""
    s = str(s or "").strip()
    if s.startswith("全"):
        return -1
    tok = re.split(r"[，,、\s]", s)[0]
    if "地下" in tok:
        return float("nan")
    return B.cn_floor(tok)


def share(g, col, cats, pct=True):
    t = g.groupby(["鄉鎮市區", col]).size().unstack(fill_value=0)
    t = t.reindex(columns=cats, fill_value=0)
    return (t.div(g.groupby("鄉鎮市區").size(), axis=0) * (100 if pct else 1)).round(1)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tx, land, bld = B.load()
    tx, last_ok = B.prep(tx)
    z = tx[tx["房地"]].copy()
    z["所在層"] = z["移轉層次"].apply(first_floor)
    z["用途"] = z["主要用途"].fillna("").replace("", "（未填）")
    z["用途"] = z["用途"].where(z["用途"].isin(USES + ["（未填）"]), "其他")
    z["樓層帶"] = pd.cut(z["樓層數"], [0, 5, 10, 15, 25, 200], labels=["5層以下", "6-10層", "11-15層", "16-25層", "26層以上"])
    ok = z["價格有效"] & ~z["特殊"]
    T = {}

    # 樓層
    t = share(z.dropna(subset=["樓層數"]), "樓層帶", ["5層以下", "6-10層", "11-15層", "16-25層", "26層以上"])
    t["11層以上"] = (t["11-15層"] + t["16-25層"] + t["26層以上"]).round(1)
    g = z.groupby("鄉鎮市區")
    t["總樓層中位數"] = g["樓層數"].median()
    t["總樓層平均"] = g["樓層數"].mean().round(1)
    T["E1_行政區×總樓層帶_占比%"] = t
    fl = z.dropna(subset=["所在層"]).copy()
    fl["所在層帶"] = pd.cut(fl["所在層"], [-2, -0.5, 1, 5, 10, 200], labels=["整棟(全)", "1樓", "2-5樓", "6-10樓", "11樓以上"])
    t = share(fl, "所在層帶", ["整棟(全)", "1樓", "2-5樓", "6-10樓", "11樓以上"])
    t["交易所在樓層中位數"] = fl[fl["所在層"] > 0].groupby("鄉鎮市區")["所在層"].median()
    T["E2_行政區×交易所在樓層_占比%"] = t
    y = z.dropna(subset=["樓層數"]).assign(高=lambda d: d["樓層數"] >= 11)
    T["E3_行政區×年度_11層以上占比%"] = y.groupby(["鄉鎮市區", "年"])["高"].mean().mul(100).round(1).unstack()
    a, b = (y[y["年"].between(*r)].groupby("鄉鎮市區")["高"].mean().mul(100) for r in ((106, 108), (112, 114)))
    T["E4_行政區11層以上占比變化"] = pd.DataFrame({"106-108": a, "112-114": b, "變化(點)": b - a}).round(1)

    # 型態（110 年起）
    z10 = z[z["年"] >= 110]
    t = share(z10, "型態", TYPES)
    t["其他"] = (100 - t.sum(axis=1)).clip(lower=0).round(1)
    T["F1_行政區×建物型態_占比%（110年起）"] = t
    T["F2_行政區×年度_公寓占比%（110年起）"] = z10.assign(公=lambda d: d["型態"] == "公寓").groupby(["鄉鎮市區", "年"])["公"].mean().mul(100).round(1).unstack()
    e, l = z[z["年"].between(110, 111)], z[z["年"].between(114, 115)]
    chg = pd.concat({"110-111": share(e, "型態", TYPES), "114-115": share(l, "型態", TYPES)}, axis=1)
    for c in TYPES:
        chg[("變化(點)", c)] = (chg[("114-115", c)] - chg[("110-111", c)]).round(1)
    T["F3_行政區建物型態占比變化"] = chg
    zz = z[ok & z["型態"].isin(TYPES)]
    t = zz.groupby(["鄉鎮市區", "型態"]).agg(筆數=("編號", "size"), 單價中位數_萬元每坪=("單價坪", lambda s: s.median() / 1e4),
                                          屋齡中位數=("屋齡", "median"), 建物面積中位數_坪=("建物面積", lambda s: s.median() / PING))
    T["F4_行政區×建物型態_單價屋齡面積"] = t[t["筆數"] >= 30].round(1)

    # 用途（107 年起）
    z7 = z[z["年"] >= 107]
    t = share(z7, "用途", USES + ["其他", "（未填）"])
    t["非住家用途"] = (t["商業用"] + t["辦公用"] + t["工業用"] + t["住商用"]).round(1)
    T["G1_行政區×主要用途_占比%（107年起）"] = t
    T["G2_行政區×年度_非住家用途占比%（107年起）"] = z7.assign(非=lambda d: d["用途"].isin(["商業用", "辦公用", "工業用", "住商用"])).groupby(["鄉鎮市區", "年"])["非"].mean().mul(100).round(1).unstack()
    e, l = z[z["年"].between(107, 109)], z[z["年"].between(113, 115)]
    cats = USES + ["其他"]
    chg = pd.concat({"107-109": share(e, "用途", cats), "113-115": share(l, "用途", cats)}, axis=1)
    for c in ["住家用", "商業用", "辦公用", "工業用"]:
        chg[("變化(點)", c)] = (chg[("113-115", c)] - chg[("107-109", c)]).round(1)
    T["G3_行政區建物主要用途占比變化"] = chg

    # 屋齡、面積、價格
    g = z.groupby("鄉鎮市區")
    a = z.dropna(subset=["屋齡"])
    t = pd.DataFrame({"筆數": g.size(), "屋齡中位數": a.groupby("鄉鎮市區")["屋齡"].median(),
                      "屋齡5年內%": a.groupby("鄉鎮市區")["屋齡"].apply(lambda s: round((s <= 5).mean() * 100, 1)),
                      "屋齡46年以上%": a.groupby("鄉鎮市區")["屋齡"].apply(lambda s: round((s >= 46).mean() * 100, 1)),
                      "建物面積中位數_坪": (g["建物面積"].median() / PING).round(1),
                      "單價中位數_萬元每坪_全期間": (z[ok].groupby("鄉鎮市區")["單價坪"].median() / 1e4).round(1),
                      "單價中位數_萬元每坪_113至115": (z[ok & (z["年"] >= 113)].groupby("鄉鎮市區")["單價坪"].median() / 1e4).round(1)})
    T["H1_行政區屋齡面積價格"] = t

    # shp 屬性
    e1, f1, g1 = T["E1_行政區×總樓層帶_占比%"], T["F1_行政區×建物型態_占比%（110年起）"], T["G1_行政區×主要用途_占比%（107年起）"]
    e2 = T["E2_行政區×交易所在樓層_占比%"]
    att = pd.DataFrame({"N_TX": g.size(), "FL_MED": e1["總樓層中位數"], "FL_AVG": e1["總樓層平均"],
                        "P_FL5": e1["5層以下"], "P_FL6_10": e1["6-10層"], "P_FL11_15": e1["11-15層"], "P_FL16_25": e1["16-25層"],
                        "P_FL26UP": e1["26層以上"], "P_FL11UP": e1["11層以上"], "P_ON_1F": e2["1樓"], "P_ON_11UP": e2["11樓以上"],
                        "P_DALOU": f1["住宅大樓"], "P_HUACH": f1["華廈"], "P_GONGY": f1["公寓"], "P_TIAN": f1["透天厝"],
                        "P_USE_RES": g1["住家用"], "P_USE_COM": g1["商業用"], "P_USE_OFF": g1["辦公用"], "P_USE_IND": g1["工業用"],
                        "P_USE_MIX": g1["住商用"], "P_NONRES": g1["非住家用途"],
                        "AGE_MED": t["屋齡中位數"], "P_AGE5": t["屋齡5年內%"], "P_AGE46UP": t["屋齡46年以上%"],
                        "AREA_MED": t["建物面積中位數_坪"], "PRC_ALL": t["單價中位數_萬元每坪_全期間"],
                        "PRC_1315": t["單價中位數_萬元每坪_113至115"]}).reset_index().rename(columns={"鄉鎮市區": "TOWNNAME"})
    desc = {"N_TX": "房地買賣筆數（105/10～115/6）", "FL_MED": "建物總樓層中位數", "FL_AVG": "建物總樓層平均",
            "P_FL5": "總樓層5層以下占比%", "P_FL6_10": "總樓層6-10層占比%", "P_FL11_15": "總樓層11-15層占比%",
            "P_FL16_25": "總樓層16-25層占比%", "P_FL26UP": "總樓層26層以上占比%", "P_FL11UP": "總樓層11層以上占比%（地圖1）",
            "P_ON_1F": "交易所在樓層為1樓占比%", "P_ON_11UP": "交易所在樓層11樓以上占比%",
            "P_DALOU": "住宅大樓占比%（110年起）", "P_HUACH": "華廈占比%（110年起）", "P_GONGY": "公寓占比%（110年起，地圖3）",
            "P_TIAN": "透天厝占比%（110年起）", "P_USE_RES": "主要用途住家用占比%（107年起）", "P_USE_COM": "商業用占比%（107年起）",
            "P_USE_OFF": "辦公用占比%（107年起）", "P_USE_IND": "工業用占比%（107年起）", "P_USE_MIX": "住商用占比%（107年起）",
            "P_NONRES": "非住家用途（商業、辦公、工業、住商）占比%（107年起，地圖2）", "AGE_MED": "屋齡中位數（年）",
            "P_AGE5": "屋齡5年內占比%", "P_AGE46UP": "屋齡46年以上占比%", "AREA_MED": "建物面積中位數（坪）",
            "PRC_ALL": "房地單價中位數（萬元/坪，全期間，排除特殊交易）", "PRC_1315": "房地單價中位數（萬元/坪，113～115年）"}

    with pd.ExcelWriter(OUT / "行政區建物分析表.xlsx", engine="openpyxl") as xw:
        for k, v in T.items():
            v.to_excel(xw, sheet_name=k[:31])
            v.to_csv(OUT / f"表_{k}.csv", encoding="utf-8-sig")

    # 空間資料
    # 這份 dbf 實際是 UTF-8（預設讀法會變亂碼，COUNTYNAME 篩不到臺北市）
    bnd = gpd.read_file(Path(case_dir("鄉鎮市區界線")) / "TOWN_MOI_1081121.shp", encoding="utf-8")
    bnd = bnd[bnd["COUNTYNAME"] == "臺北市"][["TOWNID", "TOWNNAME", "geometry"]].to_crs(3826)
    gdf = bnd.merge(att, on="TOWNNAME", how="left")
    assert gdf["N_TX"].notna().all() and len(gdf) == 12, "行政區對不上"
    shp_dir = OUT / "shp"
    shp_dir.mkdir(exist_ok=True)
    gdf.to_file(shp_dir / "臺北市行政區_建物交易分析.shp", driver="ESRI Shapefile", encoding="utf-8")
    pd.DataFrame({"欄位": list(desc), "說明": list(desc.values())}).to_csv(shp_dir / "欄位說明.csv", index=False, encoding="utf-8-sig")
    maps(gdf)
    for k, v in T.items():
        print("\n##", k)
        print(v.head(14).iloc[:, :12].to_string(max_colwidth=18))
    print("\n", att.round(1).to_string())


def maps(gdf):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "PMingLiU", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False
    spec = [("M1_樓層_11層以上占比", "P_FL11UP", "圖M1 房地買賣：總樓層 11 層以上建物占比（%）", "交易期間 105/10～115/6", "YlOrRd"),
            ("M2_用途_非住家用途占比", "P_NONRES", "圖M2 房地買賣：非住家用途（商業、辦公、工業、住商）建物占比（%）", "交易期間 107～115 年", "PuBu"),
            ("M3_型態_公寓占比", "P_GONGY", "圖M3 房地買賣：公寓（5 樓以下無電梯）占比（%）", "交易期間 110～115 年（建物型態分類自 110 年起收斂）", "YlGn")]
    pts = gdf.representative_point()
    for fname, col, title, sub, cmap in spec:
        clf = mapclassify.Quantiles(gdf[col].values, k=5)
        cols = plt.get_cmap(cmap)([0.2, 0.4, 0.6, 0.8, 1.0])
        fig, ax = plt.subplots(figsize=(8, 9.2))
        gdf.assign(_c=[cols[i] for i in clf.yb]).plot(ax=ax, color=gdf.assign(_c=[cols[i] for i in clf.yb])["_c"], edgecolor="#555", linewidth=0.8)
        for (_, r), p in zip(gdf.iterrows(), pts):
            dark = clf.yb[_] >= 3
            ax.annotate(f"{r['TOWNNAME']}\n{r[col]:.1f}", (p.x, p.y), ha="center", va="center", fontsize=7.5,
                        color="white" if dark else "black", weight="bold")
        lo = [gdf[col].min()] + list(clf.bins[:-1])
        labels = [f"{a:.1f} – {b:.1f}（{int((clf.yb == i).sum())} 區）" for i, (a, b) in enumerate(zip(lo, clf.bins))]
        ax.legend(handles=[Patch(facecolor=c, edgecolor="#555", label=l) for c, l in zip(cols, labels)], title="分級（分位數法，每級 2～3 區）",
                  loc="lower left", fontsize=8, title_fontsize=9, frameon=True)
        x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
        bx, by = x1 - (x1 - x0) * 0.08, y0 + (y1 - y0) * 0.06  # 指北針與比例尺
        ax.annotate("N", (x1 - (x1 - x0) * 0.06, y1 - (y1 - y0) * 0.12), ha="center", fontsize=12, weight="bold")
        ax.annotate("", xy=(x1 - (x1 - x0) * 0.06, y1 - (y1 - y0) * 0.075), xytext=(x1 - (x1 - x0) * 0.06, y1 - (y1 - y0) * 0.115),
                    arrowprops=dict(arrowstyle="-|>", color="k"))
        ax.plot([bx - 5000, bx], [by, by], color="k", lw=3)
        ax.text(bx - 2500, by + (y1 - y0) * 0.012, "5 km", ha="center", fontsize=8)
        ax.set_axis_off()
        ax.set_title(title + "\n" + sub, fontsize=12)
        fig.text(0.5, 0.01, "資料：內政部不動產交易實價查詢服務網（105/10～115/6）；界線：內政部鄉鎮市區界（108/11）；座標系 TWD97 TM2 / EPSG:3826",
                 ha="center", fontsize=7, color="#555")
        fig.tight_layout(rect=(0, 0.02, 1, 1))
        fig.savefig(OUT / f"{fname}.png", dpi=150)
        plt.close(fig)


if __name__ == "__main__":
    main()
