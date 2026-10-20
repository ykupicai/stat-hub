"""各行政區 × 使用分區容積使用率熱度圖 → PowerPoint 可編輯版（儲存格著色的原生表格，數字與顏色都可在 PowerPoint 內修改），1 頁。
輸入：分區容積使用/去重版/行政區×使用分區_容積使用率.xlsx　輸出：同資料夾 行政區×使用分區_容積使用率_可編輯熱度圖.pptx
執行：python scripts/build_行政區使用分區熱度圖_pptx.py
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt
from lxml import etree

ROOT = Path(__file__).resolve().parent.parent
sys.argv = [sys.argv[0]]
spec = importlib.util.spec_from_file_location("deck", ROOT / "scripts" / "build_臺北市_行政區三表簡報.py")
K = importlib.util.module_from_spec(spec)
spec.loader.exec_module(K)
D = ROOT / "案件" / "臺北市_不動產交易分析" / "分區容積使用" / "去重版"
STOPS = [(0, (0xFF, 0xFF, 0xCC)), (50, (0xFE, 0xD9, 0x76)), (100, (0xFD, 0x8D, 0x3C)), (150, (0xE3, 0x1A, 0x1C)), (250, (0x80, 0x00, 0x26))]
SRC = "資料：地政局 BuildStat_Fage sumdd08（去重、依使照比例回推地上）、臺北市都發局彙整表法定容積率；使用率＝推算地上樓地板÷法定總樓地板，只計有法定容積率的分區塊"


def color(v):
    v = min(max(v, 0), 250)
    for (a, ca), (b, cb) in zip(STOPS, STOPS[1:]):
        if a <= v <= b:
            t = (v - a) / (b - a)
            return tuple(int(round(ca[i] + (cb[i] - ca[i]) * t)) for i in range(3))
    return STOPS[-1][1]


def set_cell(cell, text, size=10, bold=False, fill=None, fc=(0x22, 0x22, 0x22), align=PP_ALIGN.CENTER):
    cell.text = ""
    p = cell.text_frame.paragraphs[0]
    p.alignment = align
    r = p.add_run(); r.text = text
    K.style(r, size, RGBColor(*fc), bold)
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    cell.margin_left = cell.margin_right = Inches(0.04); cell.margin_top = cell.margin_bottom = Inches(0.01)
    if fill is not None:
        cell.fill.solid(); cell.fill.fore_color.rgb = RGBColor(*fill)
    tcPr = cell._tc.get_or_add_tcPr()
    for tag in ("a:lnL", "a:lnR", "a:lnT", "a:lnB"):  # 白色細格線
        ln = etree.SubElement(tcPr, qn(tag)); ln.set("w", "12700")
        sf = etree.SubElement(ln, qn("a:solidFill")); etree.SubElement(sf, qn("a:srgbClr")).set("val", "FFFFFF")
    # tcPr 子元素順序：線條需在填色之前
    fills = [c for c in tcPr if c.tag in (qn("a:solidFill"), qn("a:noFill"))]
    for f in fills:
        tcPr.remove(f); tcPr.append(f)


def main():
    t = pd.read_excel(D / "行政區×使用分區_容積使用率.xlsx", header=1)
    t = t[t["使用分區"].notna() & ~t["使用分區"].astype(str).str.startswith("註")].copy()
    dist = [c for c in t.columns if c not in ("使用分區", "分區塊數", "占法定總樓地板%")]
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    s = K.title_only(prs, "各行政區 × 使用分區容積使用率：商三（特）偏高，國中小用地偏低", source=SRC)
    nrow, ncol = len(t) + 1, len(dist) + 1
    x, y, w, h = 0.5, 1.45, 12.33, 5.3
    gf = s.shapes.add_table(nrow, ncol, Inches(x), Inches(y), Inches(w), Inches(h)); gf.name = "熱度圖表格"
    tb = gf.table
    tblPr = gf._element.graphic.graphicData.tbl.tblPr
    for a in ("bandRow", "firstRow"):
        tblPr.set(a, "0")
    first_w = 2.0
    tb.columns[0].width = Inches(first_w)
    for j in range(1, ncol):
        tb.columns[j].width = Inches((w - first_w) / (ncol - 1))
    for i in range(nrow):
        tb.rows[i].height = Inches(h / nrow)
    set_cell(tb.cell(0, 0), "使用分區", 10.5, True, fill=(0x1F, 0x2A, 0x44), fc=(255, 255, 255))
    for j, d in enumerate(dist, 1):
        set_cell(tb.cell(0, j), d, 10.5, True, fill=(0x1F, 0x2A, 0x44), fc=(255, 255, 255))
    for i, (_, r) in enumerate(t.iterrows(), 1):
        last = r["使用分區"] == "全部分區"
        set_cell(tb.cell(i, 0), str(r["使用分區"]), 10.5, last, fill=(0xE8, 0xED, 0xF4) if last else (0xF4, 0xF6, 0xF9), align=PP_ALIGN.LEFT)
        for j, d in enumerate(dist, 1):
            v = r[d]
            if pd.isna(v):
                set_cell(tb.cell(i, j), "—", 10, False, fill=(0xEE, 0xEE, 0xEE), fc=(0x99, 0x99, 0x99))
            else:
                c = color(float(v))
                set_cell(tb.cell(i, j), f"{float(v):.0f}", 10.5, last or d == "全市", fill=c, fc=(255, 255, 255) if v > 150 else (0x22, 0x22, 0x22))
    # 色階圖例
    lx, ly = 0.5, 6.78
    K.textbox(s, lx, ly - 0.02, 1.6, 0.3, ["容積使用率（%）"], size=10, color=K.MUTED, space_after=0, name="圖例標題")
    for k, v in enumerate([0, 50, 100, 150, 200, 250]):
        b = s.shapes.add_shape(1, Inches(lx + 1.6 + k * 0.62), Inches(ly), Inches(0.58), Inches(0.24))
        b.fill.solid(); b.fill.fore_color.rgb = RGBColor(*color(v)); b.line.fill.background(); b.shadow.inherit = False; b.name = f"圖例色塊{v}"
        K.textbox(s, lx + 1.6 + k * 0.62, ly - 0.02, 0.58, 0.28, [f"{v}" + ("+" if v == 250 else "")], size=9, color=(RGBColor(255, 255, 255) if v >= 150 else K.INK), space_after=0, align=PP_ALIGN.CENTER, name=f"圖例標{v}")
    K.textbox(s, 6.0, ly - 0.02, 6.8, 0.3, ["— 表示樣本不足（分區塊 < 5 或法定總樓地板 < 5 萬㎡）；右欄為全市，最下列為全部分區"], size=9.5, color=K.MUTED, space_after=0, name="圖例說明")
    out = D / "行政區×使用分區_容積使用率_可編輯熱度圖.pptx"
    prs.save(out)
    print(out)


if __name__ == "__main__":
    main()
