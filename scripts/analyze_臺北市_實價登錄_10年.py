"""臺北市 實價登錄 近十年（105/10～）買賣市場：交易概況、土地利用、建物現況、權屬（移轉型態與持分）。

輸入：資料庫/lvr.sqlite（先以 stat_mcp/lvr.py 的 harvest(season, counties=['臺北市'], need_build=True) 入庫 105S4～115S3）
輸出：案件/臺北市_不動產交易分析/（表格 CSV、分析表.xlsx、圖 PNG）。報告文字 分析報告.md 由人工依輸出撰寫。
執行：python scripts/analyze_臺北市_實價登錄_10年.py
口徑：買賣（kind a）；單價統計排除備註含特殊關係／債權債務／含增建等的交易，並排除單價落在 2 萬～150 萬元/㎡ 以外者；
      房地單價含建物；權屬＝移轉情形與持分（開放資料不含買賣雙方身分）。
"""
import io
import json
import re
import sqlite3
import statistics
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "stat_mcp"))
import lvr  # noqa: E402

OUT = ROOT / "案件" / "臺北市_不動產交易分析"
PING = lvr.PING
# 特殊交易只取各年度備註寫法一致者；「增建」另列（105～108 寫「增建或未登記建物」、109 年後寫「增建」，lvr.SPECIAL 的「含增建」會漏掉後者）
SPECIAL = ["親友", "員工", "特殊關係", "共有人", "關係人", "債權債務", "法拍", "拍賣", "急買急賣", "畸零地", "受債權", "政府機關標讓售", "地上權"]
D0 = 1051001
_CN = {c: i for i, c in enumerate("零一二三四五六七八九")}


def cn_floor(s):
    """「十八層」「二十五層」→ 整數；地下層、全、空白回 NaN。"""
    s = str(s or "").replace("層", "").strip()
    if not s or any(ch not in "零一二三四五六七八九十" for ch in s):
        return float("nan")
    if "十" in s:
        a, b = s.split("十", 1)
        return (_CN.get(a, 1) if a else 1) * 10 + (_CN.get(b, 0) if b else 0)
    return _CN.get(s, float("nan"))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def load():
    c = sqlite3.connect(lvr.DB)
    tx = pd.read_sql("select * from lvr_tx where county='臺北市' and kind='a'", c)
    land = pd.read_sql("select l.* from lvr_land l join lvr_tx t on t.kind=l.kind and t.編號=l.編號 "
                       "where t.county='臺北市' and l.kind='a'", c)
    bld = pd.read_sql("select b.* from lvr_build b join lvr_tx t on t.kind=b.kind and t.編號=b.編號 "
                      "where t.county='臺北市' and b.kind='a'", c)
    return tx, land, bld


def prep(tx):
    tx = tx[(tx["交易日"] >= D0) & (tx["交易日"] <= 1151231)].copy()
    tx["年"] = tx["交易日"] // 10000
    tx["月"] = tx["交易日"] // 100
    # 末端未登記完整的月份不納入：月筆數低於前 12 個月中位數 60% 者截掉
    mc = tx.groupby("月").size()
    base = mc.iloc[-24:-12].median()
    last_ok = max(m for m in mc.index if mc[m] >= 0.6 * base and all(mc.get(x, 0) >= 0.6 * base for x in mc.index if x <= m and x >= m - 3))
    tx = tx[tx["月"] <= last_ok].copy()
    ex = tx["extra"].apply(lambda s: json.loads(s) if s else {})
    tx["完成年月"] = ex.apply(lambda d: d.get("建築完成年月", ""))
    tx["總樓層"] = ex.apply(lambda d: d.get("總樓層數", ""))
    tx["建材"] = ex.apply(lambda d: d.get("主要建材", ""))
    tx["房"] = pd.to_numeric(ex.apply(lambda d: d.get("建物現況格局-房", "")), errors="coerce")
    tx["管理組織"] = ex.apply(lambda d: d.get("有無管理組織", ""))
    tx["電梯"] = ex.apply(lambda d: d.get("電梯", ""))
    tx["移轉層次"] = ex.apply(lambda d: d.get("移轉層次", ""))
    cy = pd.to_numeric(tx["完成年月"].astype(str).str.zfill(7).str[:3], errors="coerce")
    tx["屋齡"] = (tx["年"] - cy).where((cy > 0) & (cy <= tx["年"]))
    tx["特殊"] = tx["備註"].fillna("").apply(lambda s: any(w in s for w in SPECIAL))
    tx["增建"] = tx["備註"].fillna("").str.contains("增建|未登記建物")
    tx["樓層數"] = tx["總樓層"].apply(cn_floor)
    tx["房地"] = tx["交易標的"].isin(["房地(土地+建物)", "房地(土地+建物)+車位"])
    tx["住宅"] = tx["建物型態"].str.contains("公寓|華廈|住宅大樓|透天|套房", na=False) & tx["主要用途"].fillna("").str.contains("住")
    tx["單價坪"] = tx["單價"] * PING
    tx["價格有效"] = tx["單價"].between(20000, 1500000)
    tx["型態"] = tx["建物型態"].fillna("").str.replace(r"\(.*\)", "", regex=True).replace("", "（無建物）")
    return tx, last_ok


_NUM = str.maketrans("壹貳參肆", "一二三四")
_PUBLIC = "道路|公園|學校|綠地|廣場|市場|停車|變電|機關|河川|河道|溝渠|水道|堤|公用|公共設施|醫院|兒童|體育|墓|社教|garden|消防|警察|郵政|港|鐵路|捷運|軌道|污水|垃圾|加油"


def zone_raw(s):
    """使用分區字串 → 去掉公告日期、括號說明後的名稱。"""
    s = s or ""
    t = s.split("：", 1)[-1].translate(_NUM)
    t = re.sub(r"^其他[:：]", "", t)
    t = re.sub(r"^使用分區[:：]", "", t)
    t = re.sub(r"^[(（]([^)）]*)[)）]", r"\1", t)  # 「(道路用地)」整段在括號內
    return re.split(r"[。(（【,，]", t)[0].strip()


def zone(s):
    """大類：住宅區／商業區／工業區／公共設施用地／保護區／農業區／其他都市分區／非都市土地。"""
    if (s or "").startswith("非都市"):
        return "非都市土地"
    t = zone_raw(s)
    if not t:
        return "（未標示）"
    if t == "住" or "住宅" in t:
        return "住宅區"
    if t == "商" or "商業" in t or re.fullmatch(r"商[一二三四]特?", t):
        return "商業區"
    if t == "工" or "工業" in t:
        return "工業區"
    if "保護區" in t or "保謢區" in t:
        return "保護區"
    if "農業" in t or t == "農":
        return "農業區"
    if t == "道" or re.search(_PUBLIC + "|公設|步道|行水", t) or t.endswith("用地"):
        return "公共設施用地"
    return "其他都市分區"


def zone_detail(s):
    """住宅區／商業區細分：第N種。"""
    t = zone_raw(s)
    if t == "住":
        return "住宅區（未分種）"
    if t == "商":
        return "商業區（未分種）"
    m = re.match(r"第([一二三四五]+(?:之[一二三四五]+)?)種(住宅|商業)區", t)
    return f"{m.group(2)}區第{m.group(1)}種" if m else None


def med(s):
    s = s.dropna()
    return float(s.median()) if len(s) else None


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tx, land, bld = load()
    tx, last_ok = prep(tx)
    land = land[land["編號"].isin(tx["編號"])].copy()
    bld = bld[bld["編號"].isin(tx["編號"])].copy()
    yr = tx.set_index("編號")["年"]
    land["年"] = land["編號"].map(yr)
    bld["年"] = bld["編號"].map(yr)
    land["分區"] = land["使用分區或編定"].apply(zone)
    land["持分比"] = pd.to_numeric(land["持分分子"], errors="coerce") / pd.to_numeric(land["持分分母"], errors="coerce")
    tables = {}
    notes = {"資料範圍": f"交易日 民國{D0 // 10000}年10月 ～ {last_ok // 100}年{last_ok % 100}月（末端登記未完整月份已截掉）",
             "買賣筆數": int(len(tx)), "特殊交易筆數": int(tx["特殊"].sum()),
             "房地買賣有效單價筆數": int((tx["房地"] & tx["價格有效"] & ~tx["特殊"]).sum())}

    # 1 交易概況
    t = tx.groupby(["年", "交易標的"]).size().unstack(fill_value=0)
    t["合計"] = t.sum(axis=1)
    tables["1a_年度×交易標的筆數"] = t
    h = tx[tx["房地"] & tx["價格有效"] & ~tx["特殊"]]
    t = h.groupby("年").agg(筆數=("編號", "size"), 單價中位數_元每坪=("單價坪", "median"), 總價中位數_萬=("總價", lambda s: s.median() / 1e4),
                          建物面積中位數_坪=("建物面積", lambda s: s.median() / PING))
    t["單價中位數_元每坪"] = t["單價中位數_元每坪"].round()
    t["備註含增建占比%"] = h.groupby("年")["增建"].mean().mul(100)
    t["排除增建後單價中位數_元每坪"] = h[~h["增建"]].groupby("年")["單價坪"].median().round()
    t["備註含增建單價中位數_元每坪"] = h[h["增建"]].groupby("年")["單價坪"].median().round()
    tables["1b_年度房地行情"] = t.round(1)
    t = h.groupby(["鄉鎮市區", "年"])["單價坪"].median().unstack().round()
    t["筆數"] = h.groupby("鄉鎮市區").size()
    tables["1c_行政區×年度房地單價中位數_元每坪"] = t

    # 2 土地利用
    t = land.groupby(["年", "分區"]).size().unstack(fill_value=0)
    tables["2a_年度×使用分區_土地筆數"] = t
    share = t.div(t.sum(axis=1), axis=0).mul(100).round(1)
    tables["2b_年度×使用分區_占比"] = share
    a = land.groupby("分區").agg(土地筆數=("編號", "size"), 登載移轉面積_公頃=("面積", lambda s: s.sum() / 1e4)).sort_values("土地筆數", ascending=False)
    a["占比%"] = (a["土地筆數"] / a["土地筆數"].sum() * 100).round(1)
    tables["2c_使用分區總表"] = a.round(2)
    land["住商細類"] = land["使用分區或編定"].apply(zone_detail)
    t = land.dropna(subset=["住商細類"]).groupby("住商細類").agg(土地筆數=("編號", "size"), 登載移轉面積_公頃=("面積", lambda s: s.sum() / 1e4))
    t["占比%"] = (t["土地筆數"] / t["土地筆數"].sum() * 100).round(1)
    tables["2g_住商細類"] = t.sort_values("土地筆數", ascending=False).round(2)
    g = tx.merge(land.groupby("編號")["分區"].agg(lambda s: s.value_counts().index[0]).rename("主分區"), left_on="編號", right_index=True, how="left")
    hh = g[g["房地"] & g["價格有效"] & ~g["特殊"]]
    t = hh.groupby("主分區").agg(筆數=("編號", "size"), 單價中位數_元每坪=("單價坪", "median"), 屋齡中位數=("屋齡", "median")).sort_values("筆數", ascending=False)
    tables["2d_主使用分區×房地單價"] = t.round(1)
    ld = g[(g["交易標的"] == "土地") & g["價格有效"] & ~g["特殊"]]
    t = ld.groupby("主分區").agg(筆數=("編號", "size"), 單價中位數_元每坪=("單價坪", "median"), 土地面積中位數_坪=("土地面積", lambda s: s.median() / PING)).sort_values("筆數", ascending=False)
    tables["2e_純土地交易_分區×地價"] = t.round(1)
    nu = land[land["分區"] == "非都市土地"]["使用分區或編定"].str.replace("非都市：", "", regex=False).value_counts().head(12)
    tables["2f_非都市土地_分區編定"] = nu.to_frame("土地筆數")

    # 3 建物現況
    z = tx[tx["房地"]]
    t = z.groupby(["年", "型態"]).size().unstack(fill_value=0)
    tables["3a_年度×建物型態_筆數"] = t
    tables["3b_年度×建物型態_占比"] = t.div(t.sum(axis=1), axis=0).mul(100).round(1)
    bands = pd.cut(z["屋齡"], [-1, 5, 15, 30, 45, 200], labels=["0-5年", "6-15年", "16-30年", "31-45年", "46年以上"])
    z = z.assign(屋齡帶=bands)
    t = z.groupby(["年", "屋齡帶"], observed=True).size().unstack(fill_value=0)
    tables["3c_年度×屋齡帶_占比"] = t.div(t.sum(axis=1), axis=0).mul(100).round(1)
    hz = z[z["價格有效"] & ~z["特殊"]]
    t = hz.groupby("屋齡帶", observed=True).agg(筆數=("編號", "size"), 單價中位數_元每坪=("單價坪", "median")).round(0)
    tables["3d_屋齡帶×單價"] = t
    t = hz.groupby("型態").agg(筆數=("編號", "size"), 單價中位數_元每坪=("單價坪", "median"), 屋齡中位數=("屋齡", "median"),
                              建物面積中位數_坪=("建物面積", lambda s: s.median() / PING)).sort_values("筆數", ascending=False)
    tables["3e_建物型態×單價屋齡面積"] = t.round(1)
    fl = pd.cut(z["樓層數"], [0, 5, 10, 15, 25, 200], labels=["5層以下", "6-10層", "11-15層", "16-25層", "26層以上"])
    u = z["主要用途"].fillna("").replace("", "（未填）")
    u = u.where(u.isin(["住家用", "商業用", "辦公用", "工業用", "住商用", "（未填）"]), "其他")
    t = z.assign(用途=u).groupby(["年", "用途"]).size().unstack(fill_value=0)
    tables["3k_年度×主要用途_占比（建物型態109年後分類收斂，用途較可跨年比）"] = t.div(t.sum(axis=1), axis=0).mul(100).round(1)
    t = z.assign(樓層帶=fl).groupby(["年", "樓層帶"], observed=True).size().unstack(fill_value=0)
    tables["3f_年度×總樓層帶_占比"] = t.div(t.sum(axis=1), axis=0).mul(100).round(1)
    t = z[z["住宅"]].groupby(["年", "房"]).size().unstack(fill_value=0)
    t = t[[c for c in t.columns if c in (0, 1, 2, 3, 4, 5)]]
    tables["3g_住宅_年度×房數_占比"] = t.div(t.sum(axis=1), axis=0).mul(100).round(1)
    t = z.groupby("年").agg(有管理組織=("管理組織", lambda s: round((s == "有").mean() * 100, 1)),
                          有電梯=("電梯", lambda s: round((s == "有").mean() * 100, 1)))
    tables["3h_年度×管理組織與電梯_占比"] = t
    t = z["建材"].replace("", "（未填）").value_counts().head(8).to_frame("筆數")
    t["占比%"] = (t["筆數"] / len(z) * 100).round(1)
    tables["3i_主要建材"] = t
    t = bld[bld["主要用途"].notna()].copy()
    t["用途"] = t["主要用途"].apply(lambda s: "共有部分" if "共有部分" in s else s)
    t = t["用途"].value_counts().head(10).to_frame("建物筆數")
    tables["3j_建物登記_主要用途"] = t

    # 4 權屬
    t = land.groupby(["年", "移轉情形"]).size().unstack(fill_value=0)
    tables["4a_年度×土地移轉情形_筆數"] = t
    tables["4b_年度×土地移轉情形_占比"] = t.div(t.sum(axis=1), axis=0).mul(100).round(1)
    lp = land[land["移轉情形"].str.contains("持分", na=False)].copy()
    lp["持分帶"] = pd.cut(lp["持分比"], [0, 0.01, 0.1, 0.5, 0.9999, 1.0001], labels=["<1%", "1-10%", "10-50%", "50-<100%", "100%"])
    t = lp.groupby("持分帶", observed=True).size().to_frame("持分移轉土地筆數")
    t["占比%"] = (t["持分移轉土地筆數"] / t["持分移轉土地筆數"].sum() * 100).round(1)
    tables["4c_持分比分布"] = t
    t = land.groupby("分區")["移轉情形"].agg(土地筆數="size", 持分移轉占比=lambda s: round(s.str.contains("持分", na=False).mean() * 100, 1))
    tables["4d_使用分區×持分移轉占比"] = t.sort_values("土地筆數", ascending=False).head(12)
    n = tx["筆棟數"].str.extract(r"土地(\d+)建物(\d+)車位(\d+)").astype(float)
    n.columns = ["土地筆", "建物棟", "車位數"]
    tx = pd.concat([tx, n], axis=1)
    tx["土地筆帶"] = pd.cut(tx["土地筆"], [-1, 1, 2, 5, 10, 10000], labels=["1筆", "2筆", "3-5筆", "6-10筆", "11筆以上"])
    t = tx.groupby(["年", "土地筆帶"], observed=True).size().unstack(fill_value=0)
    tables["4e_年度×單筆交易土地筆數_占比"] = t.div(t.sum(axis=1), axis=0).mul(100).round(1)
    t = tx[tx["土地筆"] >= 11].groupby("交易標的").agg(筆數=("編號", "size"), 總價中位數_萬=("總價", lambda s: s.median() / 1e4))
    tables["4f_土地11筆以上交易_標的"] = t.round(1).sort_values("筆數", ascending=False)
    lm = land.merge(tx[["編號", "交易標的"]], on="編號")
    lm["標的群"] = lm["交易標的"].where(lm["交易標的"].isin(["土地", "房地(土地+建物)", "房地(土地+建物)+車位", "建物"]), "其他")
    t = lm.groupby(["標的群", "移轉情形"]).size().unstack(fill_value=0)
    t["持分移轉占比%"] = (t.get("持分移轉", 0) / t.sum(axis=1) * 100).round(1)
    tables["4h_交易標的×土地移轉情形（持分＝區分所有或共有）"] = t
    ld2 = lm[lm["交易標的"] == "土地"]
    t = ld2.assign(持分=ld2["移轉情形"].str.contains("持分", na=False)).groupby("分區").agg(
        土地筆數=("編號", "size"), 持分移轉占比=("持分", lambda s: round(s.mean() * 100, 1)))
    tables["4i_純土地交易×分區_持分占比"] = t.sort_values("土地筆數", ascending=False)
    cats = {"親友／員工／特殊關係": "親友|員工|特殊關係|共有人|關係人", "債權債務／法拍": "債權債務|法拍|拍賣", "增建／未登記建物（未列入特殊）": "增建|未登記建物",
            "地上權／預售換約等": "地上權|預售|換約|畸零地", "急買急賣": "急買急賣"}
    bz = tx["備註"].fillna("")
    t = pd.DataFrame({k: tx.assign(f=bz.str.contains(v)).groupby("年")["f"].mean().mul(100).round(1) for k, v in cats.items()})
    t["特殊交易合計"] = tx.groupby("年")["特殊"].mean().mul(100).round(1)
    tables["4g_年度×備註特殊交易_占比"] = t
    t = tx[tx["交易標的"] == "房地(土地+建物)"]
    t = t.groupby("年").apply(lambda d: pd.Series({"全筆移轉占比": round((d["土地筆"] <= 3).mean() * 100, 1)}), include_groups=False)

    # 輸出
    with pd.ExcelWriter(OUT / "分析表.xlsx", engine="openpyxl") as xw:
        for k, v in tables.items():
            v.to_excel(xw, sheet_name=k[:31])
            v.to_csv(OUT / f"表_{k}.csv", encoding="utf-8-sig")
    (OUT / "口徑與統計.json").write_text(json.dumps(notes, ensure_ascii=False, indent=1), encoding="utf-8")
    charts(tables)
    for k, v in tables.items():
        print("\n##", k)
        print(v.head(15).iloc[:, :14].to_string(max_colwidth=24))
    print("\n", notes)


def charts(t):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "PMingLiU", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False
    b = t["1b_年度房地行情"]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(b.index.astype(str), b["筆數"], color="#9bb5a8")
    ax.set_ylabel("房地買賣筆數（排除特殊交易）")
    a2 = ax.twinx()
    a2.plot(b.index.astype(str), b["單價中位數_元每坪"] / 1e4, color="#a8442f", marker="o")
    a2.set_ylabel("單價中位數（萬元/坪）")
    ax.set_title("臺北市房地買賣：筆數與單價（105 年僅 10～12 月、末年未滿）")
    fig.tight_layout(); fig.savefig(OUT / "圖1_年度筆數與單價.png", dpi=150); plt.close(fig)
    d = t["1c_行政區×年度房地單價中位數_元每坪"].drop(columns="筆數") / 1e4
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for r in d.index:
        ax.plot(d.columns.astype(str), d.loc[r], marker=".", label=r)
    ax.legend(ncol=4, fontsize=7); ax.set_ylabel("萬元/坪"); ax.set_title("各行政區房地單價中位數")
    fig.tight_layout(); fig.savefig(OUT / "圖2_行政區單價.png", dpi=150); plt.close(fig)
    for key, name, title in [("3b_年度×建物型態_占比", "圖3_建物型態", "房地買賣：建物型態占比（%）"),
                             ("3c_年度×屋齡帶_占比", "圖4_屋齡帶", "房地買賣：屋齡帶占比（%）"),
                             ("4b_年度×土地移轉情形_占比", "圖5_持分", "土地移轉情形占比（%）")]:
        d = t[key]
        if name == "圖3_建物型態":  # 罕見型態併入其他（避免色盤重複），並標出 110 年起分類收斂
            keep = ["住宅大樓", "華廈", "公寓", "透天厝", "套房", "店面", "辦公商業大樓"]
            d = d[[c for c in keep if c in d.columns]].assign(其他=lambda x: 100 - x.sum(axis=1)).round(1)
        fig, ax = plt.subplots(figsize=(8, 4))
        bottom = None
        for col in d.columns:
            ax.bar(d.index.astype(str), d[col], bottom=bottom, label=str(col))
            bottom = d[col] if bottom is None else bottom + d[col]
        if name == "圖3_建物型態":
            ax.axvline(4.5, color="k", ls="--", lw=0.8)
            ax.text(4.55, 3, "110年起平台只剩\n住宅大樓／華廈／公寓／透天", fontsize=7, color="white")
        ax.legend(fontsize=7, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.1)); ax.set_title(title)
        fig.tight_layout(); fig.savefig(OUT / f"{name}.png", dpi=150); plt.close(fig)


if __name__ == "__main__":
    main()
