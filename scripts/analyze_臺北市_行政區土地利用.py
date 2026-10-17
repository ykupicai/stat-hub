"""臺北市各行政區土地利用類型分析（實價登錄買賣，105/10～115/6）。
沿用 analyze_臺北市_實價登錄_10年.py 的載入、特殊交易與使用分區歸類；輸出到 案件/臺北市_不動產交易分析/行政區土地利用/。
執行：python scripts/analyze_臺北市_行政區土地利用.py
口徑：「土地筆數」＝每筆交易所附地號的列數（同一地號多次交易會重複計）；面積為登載移轉面積，僅供參考；
      單價統計排除特殊交易與單價 2 萬～150 萬元/㎡ 以外者；表格 n 太小（<20 純土地、<30 房地）者不列。
"""
import importlib.util
import io
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("base10", ROOT / "scripts" / "analyze_臺北市_實價登錄_10年.py")
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)
OUT =B.OUT / "行政區土地利用"
PING = B.PING
ORDER = ["住宅區", "商業區", "公共設施用地", "其他都市分區", "工業區", "保護區", "農業區", "非都市土地", "（未標示）"]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tx, land, bld = B.load()
    tx, last_ok = B.prep(tx)
    land = land[land["編號"].isin(tx["編號"])].copy()
    info = tx.set_index("編號")[["鄉鎮市區", "年"]]
    land = land.join(info, on="編號")
    land["分區"] = land["使用分區或編定"].apply(B.zone)
    land["住商細類"] = land["使用分區或編定"].apply(B.zone_detail)
    land["原名"] = land["使用分區或編定"].apply(B.zone_raw)
    T = {}

    cnt = land.groupby(["鄉鎮市區", "分區"]).size().unstack(fill_value=0)
    cnt = cnt[[c for c in ORDER if c in cnt.columns]]
    cnt["合計"] = cnt.sum(axis=1)
    T["A1_行政區×使用分區_土地筆數"] = cnt
    sh = cnt.drop(columns="合計").div(cnt["合計"], axis=0).mul(100).round(1)
    T["A2_行政區×使用分區_占比"] = sh
    ar = land.groupby(["鄉鎮市區", "分區"])["面積"].sum().div(1e4).unstack(fill_value=0)
    T["A3_行政區×使用分區_登載面積公頃"] = ar[[c for c in ORDER if c in ar.columns]].round(1)

    d = land[land["住商細類"].notna()].copy()
    d["群"] = d["住商細類"].str.replace("（未分種）", "", regex=False)
    t = d.groupby(["鄉鎮市區", "群"]).size().unstack(fill_value=0)
    keep = t.sum().sort_values(ascending=False).head(8).index
    T["A4_行政區×住商細類_占住商筆數%"] = t[keep].div(t.sum(axis=1), axis=0).mul(100).round(1)

    # 變化：106–108 vs 112–114（完整年度）
    e = land[land["年"].between(106, 108)].groupby(["鄉鎮市區", "分區"]).size().unstack(fill_value=0)
    l = land[land["年"].between(112, 114)].groupby(["鄉鎮市區", "分區"]).size().unstack(fill_value=0)
    es, ls = e.div(e.sum(axis=1), axis=0) * 100, l.div(l.sum(axis=1), axis=0) * 100
    cols = [c for c in ["住宅區", "商業區", "公共設施用地"] if c in es.columns]
    chg = pd.concat({"106-108": es[cols].round(1), "112-114": ls[cols].round(1), "變化(百分點)": (ls[cols] - es[cols]).round(1)}, axis=1)
    T["A5_行政區使用分區占比變化"] = chg

    # 其他都市分區明細（特定專用區、國家公園區…）
    o = land[land["分區"] == "其他都市分區"].groupby(["鄉鎮市區", "原名"]).size().rename("筆數").reset_index()
    o = o.sort_values(["鄉鎮市區", "筆數"], ascending=[True, False]).groupby("鄉鎮市區").head(4)
    T["A6_行政區其他都市分區前4名"] = o.set_index(["鄉鎮市區", "原名"])

    # 交易層：主分區
    main = land.groupby("編號")["分區"].agg(lambda s: s.value_counts().index[0]).rename("主分區")
    g = tx.merge(main, left_on="編號", right_index=True, how="left")
    ok = g["價格有效"] & ~g["特殊"]
    ld = g[(g["交易標的"] == "土地") & ok]
    t = ld.groupby(["鄉鎮市區", "主分區"]).agg(筆數=("編號", "size"), 單價中位數_萬元每坪=("單價坪", lambda s: s.median() / 1e4),
                                           面積中位數_坪=("土地面積", lambda s: s.median() / PING))
    t = t[t["筆數"] >= 20].round(1)
    T["B1_純土地交易_行政區×主分區"] = t
    all_ld = g[g["交易標的"] == "土地"].groupby(["鄉鎮市區", "主分區"]).size().unstack(fill_value=0)
    all_ld = all_ld[[c for c in ORDER if c in all_ld.columns]]
    all_ld["合計"] = all_ld.sum(axis=1)
    T["B2_純土地交易筆數_行政區×主分區"] = all_ld

    hz = g[g["房地"] & ok]
    t = hz.groupby(["鄉鎮市區", "主分區"]).agg(筆數=("編號", "size"), 單價中位數_萬元每坪=("單價坪", lambda s: s.median() / 1e4),
                                           屋齡中位數=("屋齡", "median"))
    T["C1_房地交易_行政區×主分區"] = t[t["筆數"] >= 30].round(1)
    z = g[g["房地"]]
    z = z.assign(用途=z["主要用途"].fillna("").replace("", "（未填）"))
    z["用途"] = z["用途"].where(z["用途"].isin(["住家用", "商業用", "辦公用", "工業用", "住商用", "（未填）"]), "其他")
    t = z.groupby(["鄉鎮市區", "用途"]).size().unstack(fill_value=0)
    T["C2_房地交易主要用途_占比%"] = t.div(t.sum(axis=1), axis=0).mul(100).round(1)
    t = z[z["年"] >= 107].groupby(["鄉鎮市區", "主分區"]).size().unstack(fill_value=0)
    T["C3_房地交易主分區_占比%"] = t.div(t.sum(axis=1), axis=0).mul(100).round(1)

    with pd.ExcelWriter(OUT / "行政區土地利用分析表.xlsx", engine="openpyxl") as xw:
        for k, v in T.items():
            v.to_excel(xw, sheet_name=k[:31])
            v.to_csv(OUT / f"表_{k}.csv", encoding="utf-8-sig")
    charts(T)
    for k, v in T.items():
        print("\n##", k)
        print(v.head(30).iloc[:, :12].to_string(max_colwidth=20))


def charts(T):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "PMingLiU", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False
    s = T["A2_行政區×使用分區_占比"]
    s = s.loc[s["公共設施用地"].sort_values().index] if "公共設施用地" in s else s
    fig, ax = plt.subplots(figsize=(8, 5))
    left = pd.Series(0.0, index=s.index)
    pal = {"住宅區": "#e0a458", "商業區": "#c0504d", "公共設施用地": "#7f9db9", "其他都市分區": "#9bbb59", "工業區": "#8064a2",
           "保護區": "#4b8b5a", "農業區": "#d6c36a", "（未標示）": "#bbbbbb", "非都市土地": "#999999"}
    for c in s.columns:
        ax.barh(s.index, s[c], left=left, label=c, color=pal.get(c))
        left += s[c]
    ax.set_xlabel("土地筆數占比（%）"); ax.set_title("各行政區買賣交易所涉土地的使用分區組成（105/10～115/6）")
    ax.legend(ncol=5, fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.14))
    fig.tight_layout(); fig.savefig(OUT / "圖A1_行政區使用分區組成.png", dpi=150); plt.close(fig)
    c = T["A5_行政區使用分區占比變化"]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    idx = c.index; x = range(len(idx))
    ax.bar([i - 0.2 for i in x], c[("106-108", "公共設施用地")], 0.4, label="106～108 年", color="#b8c4cc")
    ax.bar([i + 0.2 for i in x], c[("112-114", "公共設施用地")], 0.4, label="112～114 年", color="#4f6d8a")
    ax.set_xticks(list(x)); ax.set_xticklabels(idx, fontsize=8); ax.set_ylabel("%")
    ax.set_title("各行政區公共設施用地占交易土地筆數比"); ax.legend()
    fig.tight_layout(); fig.savefig(OUT / "圖A2_公共設施用地占比變化.png", dpi=150); plt.close(fig)


if __name__ == "__main__":
    main()
