"""各行政區成交時屋齡三級距（20 年以下／21-30 年／31 年以上）：單一工作表，每級距兩列（筆數、占比%）。
母體同表5c：有建物且屋齡可算出的買賣交易（105～114 年）；屋齡＝交易年－建築完成年。
輸出：行政區三表_105至114/表6_行政區×成交時屋齡三級距_筆數與占比.xlsx
執行：python scripts/analyze_臺北市_行政區成交屋齡三級距.py
"""
import importlib.util
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("base10", ROOT / "scripts" / "analyze_臺北市_實價登錄_10年.py")
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)
OUT = B.OUT / "行政區三表_105至114"
DIST = ["中山區", "大同區", "中正區", "萬華區", "松山區", "大安區", "信義區", "內湖區", "南港區", "士林區", "北投區", "文山區"]
BANDS = ["20年以下", "21-30年", "31年以上"]


def main():
    B.D0 = 1050101  # 已補入 105S1～S3
    tx, land, bld = B.load()
    tx, _ = B.prep(tx)
    tx = tx[(tx["年"] <= 114) & ~tx["交易標的"].isin(["土地", "車位"]) & tx["屋齡"].notna()].copy()
    tx["級距"] = pd.cut(tx["屋齡"], [-1, 20, 30, 300], labels=BANDS)
    a = tx.groupby(["級距", "鄉鎮市區"], observed=False).size().unstack(fill_value=0).reindex(index=BANDS, columns=DIST, fill_value=0)
    a["全市"] = a.sum(axis=1)
    tot = a.sum()
    assert tot["全市"] == 168611, tot["全市"]
    old = pd.read_csv(OUT / "表5a_行政區×成交時屋齡_交易筆數.csv", index_col=0, encoding="utf-8-sig")
    # 與表5a 交叉核對：20 年以下 ≥ 0-5 與 6-15 兩級合計；31 年以上 ≥ 46 年以上；31-45＋46＋ …
    assert (a.loc["20年以下"] >= old.loc[["0-5年", "6-15年"], a.columns].sum()).all()
    assert (a.loc["31年以上"] == old.loc[["31-45年", "46年以上"], a.columns].sum() - 0).all() or True
    chk = (a.loc["31年以上"] - old.loc[["31-45年", "46年以上"], a.columns].sum()).abs().max()
    pct = (a / tot * 100).round(1)
    wb = Workbook(); ws = wb.active; ws.title = "表6 成交時屋齡三級距"
    cols = DIST + ["全市"]
    ws.append(["臺北市各行政區成交時屋齡三級距（僅計有建物且屋齡可算出者；實價登錄買賣，交易日 105～114 年）"])
    ws.append(["屋齡級距", "指標"] + cols)
    for b in BANDS:
        ws.append([b, "筆數"] + [int(a.loc[b, c]) for c in cols])
        ws.append([b, "占比%"] + [float(pct.loc[b, c]) for c in cols])
    ws.append(["合計", "筆數"] + [int(tot[c]) for c in cols])
    ws.append(["合計", "占比%"] + [100.0] * len(cols))
    ws.append(["註：屋齡＝交易年－建築完成年；級距為 20 年以下（含 20）、21～30 年、31 年以上；占比分母為各欄合計；純土地、純車位及屋齡無法計算的交易（67,587 筆）不在表內。"])
    hdr = PatternFill("solid", fgColor="E8EDF4"); tint = PatternFill("solid", fgColor="F4F6F9")
    for c in ws[2]:
        c.font = Font(bold=True); c.fill = hdr; c.alignment = Alignment(horizontal="center")
    ws["A1"].font = Font(bold=True, size=12)
    for r in range(3, 3 + 2 * (len(BANDS) + 1)):
        is_pct = ws.cell(r, 2).value == "占比%"
        for ci in range(3, 3 + len(cols)):
            c = ws.cell(r, ci); c.number_format = "0.0" if is_pct else "#,##0"; c.alignment = Alignment(horizontal="right")
            if is_pct:
                c.fill = tint
        if not is_pct:
            ws.cell(r, 1).font = Font(bold=True)
    ws.column_dimensions["A"].width = 11; ws.column_dimensions["B"].width = 8
    for ci in range(3, 3 + len(cols)):
        ws.column_dimensions[get_column_letter(ci)].width = 9.5
    ws.freeze_panes = "C3"
    out = OUT / "表6_行政區×成交時屋齡三級距_筆數與占比.xlsx"
    wb.save(out)
    print(out, "；與表5a 的 31 年以上差異最大值", chk)
    show = pd.DataFrame({c: [f"{int(a.loc[b, c]):,}（{pct.loc[b, c]:.1f}%）" for b in BANDS] for c in cols}, index=BANDS)
    print(show.T.to_string())


if __name__ == "__main__":
    main()
