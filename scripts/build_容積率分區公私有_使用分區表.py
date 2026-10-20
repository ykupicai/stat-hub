"""以使用分區為主體整理「有容積率之使用分區」的公私有土地比例（唯一一張表）。

輸入：容積率分區公私有土地/總表.xlsx（analyze_臺北市_容積率分區_公私有土地.py；128 種使用分區）
分類：住宅區、商業區、工業區、學校用地、機關與公用設施用地、專用區與其他六大類；各大類列出面積 50 公頃以上的使用分區，其餘併為「其他」。
輸出：同資料夾 使用分區表.xlsx；摘要印在終端
執行：python scripts/build_容積率分區公私有_使用分區表.py
"""
import io
import os
import re
import sys
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
NO_PF = os.environ.get("NO_PF") == "1"
RC_ONLY = os.environ.get("RC_ONLY") == "1"   # NO_PF=1：讀寫「容積率分區公私有土地_不含公設」（不計入學校用地、機關與公用設施用地）
D = Path(__file__).resolve().parent.parent / "案件" / "臺北市_不動產交易分析" / ("容積率分區公私有土地_住宅商業區" if RC_ONLY else "容積率分區公私有土地_不含公設" if NO_PF else "容積率分區公私有土地")
GROUPS = ["住宅區", "商業區"] if RC_ONLY else ["住宅區", "商業區", "工業區", "專用區與其他"] if NO_PF else ["住宅區", "商業區", "工業區", "學校用地", "機關與公用設施用地", "專用區與其他"]
MIN_HA = 50


def group_of(n):
    if re.search(r"專用區|風景區|文教區|行政區$|娛樂|保存|創意|業務設施|聯合開發|捷運開發|住商混合", n) and "學校" not in n and "大學" not in n:
        if "商業" in n and "專用區" in n:
            return "專用區與其他"
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


def main():
    d = pd.read_excel(D / "總表.xlsx", header=1)
    d = d[d["使用分區"].notna() & (d["使用分區"] != "全市合計") & d["公有面積(公頃)"].notna()].copy()
    d["大類"] = d["使用分區"].map(group_of)
    d["含公有持分地號數"] = d["含公有持分地號數"].fillna(0)
    d["私有地號數"] = d["地號數"] - d["含公有持分地號數"]
    tot_area = d["分區面積(公頃)"].sum()

    def row(label, g, level):
        a, pu = g["分區面積(公頃)"].sum(), g["公有面積(公頃)"].sum()
        n, npu = g["地號數"].sum(), g["含公有持分地號數"].sum()
        return [level, label, len(g), round(a, 1), round(a / tot_area * 100, 1), round(pu, 1), round(a - pu, 1), round(pu / a * 100, 1), round(100 - pu / a * 100, 1),
                int(n), int(npu), round(npu / n * 100, 1) if n else None]
    rows = [row("全市有容積率之使用分區" + ("（只含住宅區與商業區）" if RC_ONLY else "（不含公共設施用地）" if NO_PF else ""), d, 0)]
    for gname in GROUPS:
        g = d[d["大類"] == gname]
        rows.append(row(gname, g, 1))
        big = g[g["分區面積(公頃)"] >= MIN_HA].sort_values("分區面積(公頃)", ascending=False)
        for _, r in big.iterrows():
            rr = row(r["使用分區"], g[g["使用分區"] == r["使用分區"]], 2)
            rr[2] = r["法定容積率(%)"]
            rows.append(rr)
        rest = g[g["分區面積(公頃)"] < MIN_HA]
        if len(rest):
            rows.append(row(f"其他{gname}（{len(rest)} 種，各未滿 {MIN_HA} 公頃）", rest, 2))
    cols = ["層級", "使用分區", "種數／法定容積率(%)", "分區面積(公頃)", "占全市有容積率面積%", "公有面積(公頃)", "私有面積(公頃)", "公有面積占比%", "私有面積占比%", "地號數", "含公有持分地號數", "含公有持分地號占比%"]
    wb = Workbook()
    ws = wb.active
    ws.title = "使用分區公私有土地"
    ws.append(["臺北市有容積率之使用分區：公有與私有土地比例（以使用分區為主體" + ("；只含住宅區與商業區" if RC_ONLY else "；不含公共設施用地" if NO_PF else "") + "；面積：公頃）"])
    ws.append(cols[1:])
    for r in rows:
        ws.append(r[1:])
        c = ws[ws.max_row]
        if r[0] == 0:
            for x in c:
                x.font = Font(bold=True)
                x.fill = PatternFill("solid", fgColor="D9E2F3")
        elif r[0] == 1:
            for x in c:
                x.font = Font(bold=True)
                x.fill = PatternFill("solid", fgColor="F2F2F2")
        else:
            c[0].alignment = Alignment(indent=2)
    ws.append(["註：有容積率＝分區塊法定容積率大於 0；面積以全市地籍圖（421,843 個地號）與分區塊交集計；公有＝地政局公有土地圖層內地號，公私共有地號只計公有持分（1－私有持分）的面積；私有＝分區面積－公有面積，含無地號的道路與水域；地號數以地號代表點所在分區塊計。"])
    for c_ in ws[2]:
        c_.font = Font(bold=True)
        c_.fill = PatternFill("solid", fgColor="E8EDF4")
        c_.alignment = Alignment(horizontal="center", wrap_text=True)
    ws["A1"].font = Font(bold=True, size=12)
    for i, w in enumerate([30, 16, 13, 13, 13, 13, 13, 13, 11, 11, 12], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "B3"
    wb.save(D / "使用分區表.xlsx")
    pd.set_option("display.width", 250, "display.max_rows", 200)
    print(pd.DataFrame(rows, columns=cols).drop(columns=["層級"]).to_string(index=False))


if __name__ == "__main__":
    main()
