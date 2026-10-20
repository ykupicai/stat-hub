"""臺北市各行政區（橫軸）× 使用分區／建物用途／建物樓層（縱軸）統計表（實價登錄買賣，交易日 105～114 年）。

沿用 analyze_臺北市_實價登錄_10年.py 的載入、使用分區歸類與樓層解析；母體＝不動產買賣（不含預售屋、租賃），
「所有交易」不排除特殊交易、不分交易標的（土地、建物、房地、車位都計）。
輸出：案件/臺北市_不動產交易分析/行政區三表_105至114/（表 CSV、行政區三表.xlsx）。
口徑：
  表1 使用分區：單位＝土地筆數（交易所附地號的列數，同一地號多次交易重複計）；歸類沿用 B.zone。
  表2 建物用途：單位＝交易筆數，取平台「主要用途」；無建物（純土地、純車位）另列，房地未填另列。
  表3 建物樓層：單位＝交易筆數；3a 為建物「總樓層數」、3b 為「移轉層次」（交易所在樓層）；無建物另列。
      105 年已補入 105S1～S3（全年）。
執行：python scripts/analyze_臺北市_行政區三表_105至114.py
"""
import importlib.util
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("base10", ROOT / "scripts" / "analyze_臺北市_實價登錄_10年.py")
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)
OUT = B.OUT / "行政區三表_105至114"
ZONES = ["住宅區", "商業區", "公共設施用地", "其他都市分區", "工業區", "保護區", "農業區", "非都市土地", "（未標示）"]
NOBLD = "（無建物：純土地或純車位）"
BLANK = "（未填）"


def floor_band_total(n, has_bld):
    if not has_bld:
        return NOBLD
    if pd.isna(n):
        return BLANK
    for hi, lab in ((5, "5層以下"), (10, "6-10層"), (15, "11-15層"), (25, "16-25層")):
        if n <= hi:
            return lab
    return "26層以上"


def floor_band_on(s, has_bld):
    """移轉層次 → 交易所在樓層帶。「全」＝整棟；含地下者歸地下層；第一個樓層為準。"""
    if not has_bld:
        return NOBLD
    s = str(s or "").strip()
    if not s:
        return BLANK
    if s.startswith("全"):
        return "整棟(全)"
    tok = re.split(r"[，,、\s]", s)[0]
    if "地下" in tok:
        return "地下層"
    n = B.cn_floor(tok)
    if pd.isna(n):
        return BLANK
    if n <= 1:
        return "1樓"
    if n <= 5:
        return "2-5樓"
    if n <= 10:
        return "6-10樓"
    return "11樓以上"


def xtab(df, row_col, order=None):
    """縱軸＝row_col、橫軸＝行政區，附全市合計欄；回傳 (筆數表, 占比表)。"""
    t = df.groupby([row_col, "鄉鎮市區"]).size().unstack(fill_value=0)
    t["全市"] = t.sum(axis=1)
    if order:
        t = t.reindex([r for r in order if r in t.index] + [r for r in t.index if r not in order])
    t.loc["合計"] = t.sum()
    p = (t.drop(index="合計").div(t.loc["合計"], axis=1) * 100).round(1)
    p.loc["合計"] = 100.0
    return t, p


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    B.D0 = 1050101  # 已補入 105S1～S3
    tx, land, bld = B.load()
    tx, last_ok = B.prep(tx)
    tx = tx[tx["年"] <= 114].copy()
    districts = ["中正區", "大同區", "中山區", "松山區", "大安區", "萬華區", "信義區", "士林區", "北投區", "內湖區", "南港區", "文山區"]
    assert set(tx["鄉鎮市區"]) <= set(districts), set(tx["鄉鎮市區"]) - set(districts)

    # 表1 使用分區
    land = land[land["編號"].isin(tx["編號"])].join(tx.set_index("編號")["鄉鎮市區"], on="編號")
    land["使用分區"] = land["使用分區或編定"].apply(B.zone)
    T = {}
    T["表1_行政區×使用分區_土地筆數"], T["表1_行政區×使用分區_占比%"] = xtab(land, "使用分區", ZONES)

    # 表2 建物用途
    has_bld = ~tx["交易標的"].isin(["土地", "車位"])
    tx["有建物"] = has_bld
    u = tx["主要用途"].fillna("").str.strip()
    tx["建物用途"] = u.where(u != "", BLANK).where(has_bld, NOBLD)
    order = ["住家用", "商業用", "辦公用", "工業用", "住商用", "農業用", "國民住宅", "停車空間", "見其他登記事項", "其他"]
    T["表2_行政區×建物用途_交易筆數"], T["表2_行政區×建物用途_占比%"] = xtab(tx, "建物用途", order + [BLANK, NOBLD])

    # 表3 建物樓層
    tx["總樓層帶"] = [floor_band_total(n, h) for n, h in zip(tx["樓層數"], tx["有建物"])]
    tx["所在樓層帶"] = [floor_band_on(s, h) for s, h in zip(tx["移轉層次"], tx["有建物"])]
    T["表3a_行政區×建物總樓層_交易筆數"], T["表3a_行政區×建物總樓層_占比%"] = xtab(
        tx, "總樓層帶", ["5層以下", "6-10層", "11-15層", "16-25層", "26層以上", BLANK, NOBLD])
    T["表3b_行政區×交易所在樓層_交易筆數"], T["表3b_行政區×交易所在樓層_占比%"] = xtab(
        tx, "所在樓層帶", ["地下層", "1樓", "2-5樓", "6-10樓", "11樓以上", "整棟(全)", BLANK, NOBLD])

    # 驗算：各表合計＝母體
    n_tx, n_land = len(tx), len(land)
    for k, v in T.items():
        if "筆數" in k:
            want = n_land if k.startswith("表1") else n_tx
            assert v.loc["合計", "全市"] == want, (k, v.loc["合計", "全市"], want)

    def cols(v):
        return v[districts + ["全市"]]

    with pd.ExcelWriter(OUT / "行政區三表.xlsx", engine="openpyxl") as xw:
        for k, v in T.items():
            cols(v).to_excel(xw, sheet_name=k[:31])
            cols(v).to_csv(OUT / f"{k}.csv", encoding="utf-8-sig")
    print(f"交易日 105～114 年：買賣 {n_tx:,} 筆、土地筆數 {n_land:,}（資料末月 {last_ok}）")
    for k, v in T.items():
        print("\n##", k)
        print(cols(v).to_string())


if __name__ == "__main__":
    main()
