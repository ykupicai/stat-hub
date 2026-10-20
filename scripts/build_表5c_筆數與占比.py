"""表5c（僅有屋齡者）合併筆數與占比：單一工作表，每個屋齡帶兩列（筆數、占比%），橫軸為行政區與全市。
輸入：行政區三表_105至114/表5a_*.csv（筆數）；占比由筆數重算並與表5c 核對。
輸出：同資料夾 表5c_行政區×成交時屋齡_筆數與占比.xlsx
執行：python scripts/build_表5c_筆數與占比.py
"""
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "案件" / "臺北市_不動產交易分析" / "行政區三表_105至114"
BANDS = ["0-5年", "6-15年", "16-30年", "31-45年", "46年以上"]
DIST = ["中山區", "大同區", "中正區", "萬華區", "松山區", "大安區", "信義區", "內湖區", "南港區", "士林區", "北投區", "文山區", "全市"]


def main():
    a = pd.read_csv(D / "表5a_行政區×成交時屋齡_交易筆數.csv", index_col=0, encoding="utf-8-sig").loc[BANDS, DIST]
    old = pd.read_csv(D / "表5c_行政區×成交時屋齡_占比%（僅有屋齡者）.csv", index_col=0, encoding="utf-8-sig").loc[BANDS, DIST]
    tot = a.sum()
    pct = (a / tot * 100).round(1)
    assert (pct - old).abs().max().max() < 0.051, "占比與表5c 不一致"
    assert tot["全市"] == 168611 and a.loc[:, DIST[:-1]].sum().sum() == tot["全市"]
    wb = Workbook(); ws = wb.active; ws.title = "表5c 成交時屋齡"
    ws.append(["臺北市各行政區成交時屋齡（僅計有建物且屋齡可算出者；實價登錄買賣，交易日 105～114 年）"])
    ws.append(["屋齡帶", "指標"] + DIST)
    for b in BANDS:
        ws.append([b, "筆數"] + [int(a.loc[b, c]) for c in DIST])
        ws.append([b, "占比%"] + [float(pct.loc[b, c]) for c in DIST])
    ws.append(["合計", "筆數"] + [int(tot[c]) for c in DIST])
    ws.append(["合計", "占比%"] + [100.0] * len(DIST))
    ws.append(["註：屋齡＝交易年－建築完成年；占比的分母為各欄「合計筆數」；純土地、純車位及屋齡無法計算的交易（共 67,587 筆）不在表內。"])
    hdr = PatternFill("solid", fgColor="E8EDF4"); tint = PatternFill("solid", fgColor="F4F6F9")
    for c in ws[2]:
        c.font = Font(bold=True); c.fill = hdr; c.alignment = Alignment(horizontal="center")
    ws["A1"].font = Font(bold=True, size=12)
    for r in range(3, 3 + 2 * (len(BANDS) + 1)):
        is_pct = ws.cell(r, 2).value == "占比%"
        for ci in range(3, 3 + len(DIST)):
            c = ws.cell(r, ci)
            c.number_format = "0.0" if is_pct else "#,##0"
            c.alignment = Alignment(horizontal="right")
            if is_pct:
                c.fill = tint
        if not is_pct:
            ws.cell(r, 1).font = Font(bold=True)
    for ci in range(3, 3 + len(DIST)):
        ws.cell(2 + 2 * (len(BANDS) + 1), ci).font = Font(bold=True)
    ws.column_dimensions["A"].width = 10; ws.column_dimensions["B"].width = 8
    for ci in range(3, 3 + len(DIST)):
        ws.column_dimensions[get_column_letter(ci)].width = 9.5
    ws.freeze_panes = "C3"
    out = D / "表5c_行政區×成交時屋齡_筆數與占比.xlsx"
    wb.save(out)
    print(out)
    print(a.assign(合計=0).drop(columns="合計").to_string())
    print(tot.to_dict())


if __name__ == "__main__":
    main()
