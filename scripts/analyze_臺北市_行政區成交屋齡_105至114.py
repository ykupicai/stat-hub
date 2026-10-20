"""臺北市各行政區（橫軸）× 成交時屋齡帶（縱軸）統計表（實價登錄買賣，交易日 105～114 年）。

沿用 analyze_臺北市_實價登錄_10年.py 的載入與屋齡計算：屋齡＝交易年－建築完成年（取建築完成年月前 3 碼，完成年須 ≤ 交易年）；
屋齡帶沿用分析報告表 3c：0-5、6-15、16-30、31-45、46 年以上。
母體＝所有買賣交易（不排除特殊交易、不分交易標的）；交易標的為土地或車位者列「無建物」，與行政區三表一致；
有建物但缺建築完成年月或完成年晚於交易年者列「屋齡無法計算」。
輸出：案件/臺北市_不動產交易分析/行政區三表_105至114/表5_*.csv 與 表5_成交時屋齡.xlsx
執行：python scripts/analyze_臺北市_行政區成交屋齡_105至114.py
"""
import importlib.util
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("base10", ROOT / "scripts" / "analyze_臺北市_實價登錄_10年.py")
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)
OUT = B.OUT / "行政區三表_105至114"
DIST = ["中山區", "大同區", "中正區", "萬華區", "松山區", "大安區", "信義區", "內湖區", "南港區", "士林區", "北投區", "文山區"]
BANDS = ["0-5年", "6-15年", "16-30年", "31-45年", "46年以上"]
NOBLD = "（無建物：純土地或純車位）"
NOAGE1 = "（有建物，建築完成年月空白）"
NOAGE2 = "（有建物，完成年晚於交易年）"


def main():
    B.D0 = 1050101  # 已補入 105S1～S3
    tx, land, bld = B.load()
    tx, last_ok = B.prep(tx)
    tx = tx[tx["年"] <= 114].copy()
    has_bld = ~tx["交易標的"].isin(["土地", "車位"])
    tx["屋齡帶"] = pd.cut(tx["屋齡"], [-1, 5, 15, 30, 45, 200], labels=BANDS).astype(object)
    cy = pd.to_numeric(tx["完成年月"].astype(str).str.zfill(7).str[:3], errors="coerce")
    blank = tx["屋齡帶"].isna() & has_bld & ~(cy > 0)
    later = tx["屋齡帶"].isna() & has_bld & (cy > tx["年"])
    tx.loc[blank, "屋齡帶"] = NOAGE1
    tx.loc[later, "屋齡帶"] = NOAGE2
    tx.loc[tx["屋齡帶"].isna() & has_bld, "屋齡帶"] = NOAGE1
    tx.loc[~has_bld, "屋齡帶"] = NOBLD
    t = tx.groupby(["屋齡帶", "鄉鎮市區"]).size().unstack(fill_value=0).reindex(columns=DIST, fill_value=0)
    t["全市"] = t.sum(axis=1)
    t = t.reindex(BANDS + [NOAGE1, NOAGE2, NOBLD])
    t.loc["合計"] = t.sum()
    assert t.loc["合計", "全市"] == len(tx)
    p = (t.drop(index="合計").div(t.loc["合計"], axis=1) * 100).round(1)
    p.loc["合計"] = 100.0
    # 有屋齡者的占比（排除無建物與無法計算）
    base = t.loc[BANDS].sum()
    p2 = (t.loc[BANDS].div(base, axis=1) * 100).round(1)
    p2.loc["合計"] = 100.0
    # 屋齡摘要（有屋齡者）
    ok = tx[tx["屋齡"].notna() & has_bld]
    g = ok.groupby("鄉鎮市區")["屋齡"]
    s = pd.DataFrame({"有屋齡筆數": g.size(), "屋齡中位數": g.median(), "屋齡平均": g.mean().round(1),
                      "屋齡第25百分位": g.quantile(.25), "屋齡第75百分位": g.quantile(.75)}).reindex(DIST).T
    s["全市"] = [len(ok), ok["屋齡"].median(), round(ok["屋齡"].mean(), 1), ok["屋齡"].quantile(.25), ok["屋齡"].quantile(.75)]
    T = {"表5a_行政區×成交時屋齡_交易筆數": t, "表5b_行政區×成交時屋齡_占比%（含無建物）": p, "表5c_行政區×成交時屋齡_占比%（僅有屋齡者）": p2, "表5d_行政區成交時屋齡摘要": s}
    with pd.ExcelWriter(OUT / "表5_成交時屋齡.xlsx", engine="openpyxl") as xw:
        for k, v in T.items():
            v.to_excel(xw, sheet_name=k[:31])
            v.to_csv(OUT / f"{k}.csv", encoding="utf-8-sig")
    print(f"交易日 105～114 年：買賣 {len(tx):,} 筆；有屋齡 {len(ok):,}（{len(ok) / len(tx):.1%}）")
    for k, v in T.items():
        print("\n##", k)
        print(v.to_string())


if __name__ == "__main__":
    main()
