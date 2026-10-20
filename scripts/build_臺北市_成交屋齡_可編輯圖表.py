"""各行政區成交時屋齡統計表（表5）→ PowerPoint 原生（可編輯）統計圖。
輸入：行政區三表_105至114/表5c_*.csv（占比，僅有屋齡者）、表5d_*.csv（屋齡摘要）
輸出：同資料夾 臺北市行政區成交屋齡_可編輯圖表.pptx（第 1 頁：屋齡帶占比 100% 堆疊橫條；第 2 頁：屋齡中位數與四分位距橫條）
執行：python scripts/build_臺北市_成交屋齡_可編輯圖表.py
"""
import importlib.util
import sys
from pathlib import Path

import pandas as pd
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
sys.argv = [sys.argv[0]]
spec = importlib.util.spec_from_file_location("deck", ROOT / "scripts" / "build_臺北市_行政區三表簡報.py")
K = importlib.util.module_from_spec(spec)
spec.loader.exec_module(K)
D = K.D
SRC = "資料：內政部不動產交易實價查詢服務網，臺北市不動產買賣，交易日 105～114 年；屋齡＝交易年－建築完成年；僅計有建物且屋齡可算出者（168,611 筆）"


def main():
    p5c = pd.read_csv(D / "表5c_行政區×成交時屋齡_占比%（僅有屋齡者）.csv", index_col=0, encoding="utf-8-sig").drop(index="合計", errors="ignore")
    s5d = pd.read_csv(D / "表5d_行政區成交時屋齡摘要.csv", index_col=0, encoding="utf-8-sig")
    bands = list(p5c.index)
    cats = ["全市"] + p5c.drop(columns="全市").loc["46年以上"].sort_values().index.tolist()
    spec1 = dict(title="圖T5 臺北市各行政區：成交時屋齡帶占比（依 46 年以上占比排序）", cats=cats, stack100=True,
                 series=[(b, c, p5c.loc[b].to_dict()) for b, c in zip(bands, ["053061", "67A9CF", "D1E5F0", "EF8A62", "B2182B"])])
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    s = K.title_only(prs, "成交時屋齡：南港、內湖較新，士林、松山、大安、萬華較老", source=SRC)
    K.add_native_chart(s, spec1, 0.5, 1.5, 8.6, 5.35)
    px, pw = 9.4, 3.45
    panel = s.shapes.add_shape(1, Inches(px), Inches(1.5), Inches(pw), Inches(5.35))
    panel.fill.solid(); panel.fill.fore_color.rgb = K.TINT; panel.line.fill.background(); panel.shadow.inherit = False; panel.name = "說明底板"
    K.textbox(s, px + 0.15, 1.62, pw - 0.3, 0.4, ["重點"], size=18, color=K.NAVY, bold=True, space_after=0, name="說明標題")
    med = s5d.loc["屋齡中位數"]
    K.textbox(s, px + 0.15, 2.1, pw - 0.3, 3.4, [
        f"全市屋齡中位數 {med['全市']:.0f} 年，31-45 年的交易最多（{p5c.loc['31-45年', '全市']:.1f}%）。",
        f"中位數最高：士林 {med['士林區']:.0f} 年、松山 {med['松山區']:.0f} 年、大安 {med['大安區']:.0f} 年、萬華 {med['萬華區']:.0f} 年。",
        f"最低：南港 {med['南港區']:.0f} 年、內湖 {med['內湖區']:.0f} 年。",
        f"46 年以上占比最高的是士林（{p5c.loc['46年以上', '士林區']:.1f}%）與萬華（{p5c.loc['46年以上', '萬華區']:.1f}%）。"],
        size=13, bullets=True, space_after=7, name="說明內文")
    K.textbox(s, px + 0.15, 5.65, pw - 0.3, 1.1, ["分母：168,611 筆可算出屋齡的有建物交易。", "是成交當時的屋齡，與現況屋齡不同。"], size=11, color=K.MUTED, space_after=3, name="口徑註記")

    # 第 2 頁：屋齡中位數與四分位距（標準橫條：中位數）
    order = ["全市"] + s5d.drop(columns="全市").loc["屋齡中位數"].sort_values().index.tolist()
    s2 = K.title_only(prs, "各行政區成交時屋齡中位數與四分位距", source=SRC)
    cd = CategoryChartData()
    cd.categories = order
    cd.add_series("第 25 百分位", [float(s5d.loc["屋齡第25百分位", c]) for c in order])
    cd.add_series("中位數與第 25 百分位的差", [float(s5d.loc["屋齡中位數", c] - s5d.loc["屋齡第25百分位", c]) for c in order])
    cd.add_series("第 75 百分位與中位數的差", [float(s5d.loc["屋齡第75百分位", c] - s5d.loc["屋齡中位數", c]) for c in order])
    gf = s2.shapes.add_chart(XL_CHART_TYPE.BAR_STACKED, Inches(0.5), Inches(1.5), Inches(8.6), Inches(5.35), cd)
    gf.name = "圖表：屋齡四分位距"
    ch = gf.chart
    ch.font.name, ch.font.size = K.FONT, Pt(10)
    ch.has_title = True
    ch.chart_title.text_frame.text = "圖T5b 成交時屋齡：第 25 百分位、中位數、第 75 百分位（年；依中位數排序）"
    for r in ch.chart_title.text_frame.paragraphs[0].runs:
        r.font.size, r.font.bold, r.font.name = Pt(12), True, K.FONT
        r.font.color.rgb = K.NAVY
    ch.has_legend = True; ch.legend.position = XL_LEGEND_POSITION.BOTTOM; ch.legend.include_in_layout = False
    pl = ch.plots[0]; pl.gap_width, pl.overlap = 40, 100
    ch.value_axis.has_major_gridlines = False
    ch.value_axis.maximum_scale, ch.value_axis.minimum_scale = 50, 0
    ch.value_axis.tick_labels.font.size = Pt(10); ch.category_axis.tick_labels.font.size = Pt(11)
    s0, s1, s2_ = pl.series
    s0.format.fill.background()  # 隱形底座：讓第 2、3 段從 P25 起畫到 P75
    for sr, col in ((s1, "67A9CF"), (s2_, "2166AC")):
        sr.format.fill.solid(); sr.format.fill.fore_color.rgb = RGBColor.from_string(col)
        sr.format.line.color.rgb = RGBColor(255, 255, 255)
    for j, c in enumerate(order):
        for sr, txt, pos in ((s0, f"P25 {s5d.loc['屋齡第25百分位', c]:.0f}", XL_LABEL_POSITION.INSIDE_END), (s1, f"中位 {s5d.loc['屋齡中位數', c]:.0f}", XL_LABEL_POSITION.INSIDE_END),
                             (s2_, f"P75 {s5d.loc['屋齡第75百分位', c]:.0f}", XL_LABEL_POSITION.INSIDE_END)):
            lab = sr.points[j].data_label
            lab.position = pos
            lab.text_frame.text = txt
            for r in lab.text_frame.paragraphs[0].runs:
                r.font.size = Pt(9)
                r.font.color.rgb = RGBColor(0x22, 0x22, 0x22) if sr is s0 else RGBColor(255, 255, 255)
    # 隱藏底座的圖例項
    from lxml import etree
    from pptx.oxml.ns import qn
    leg = ch.legend._element
    le = etree.SubElement(leg, qn("c:legendEntry"))
    etree.SubElement(le, qn("c:idx")).set("val", "0")
    etree.SubElement(le, qn("c:delete")).set("val", "1")
    leg.remove(le); leg.insert(1, le)
    K.textbox(s2, 9.4, 2.0, 3.45, 3.6, ["淺藍段：中位數往下到第 25 百分位；深藍段：中位數往上到第 75 百分位。", "全市中位數 30 年、四分位距 12～41 年。",
                                        "南港的中位數僅 16 年，士林、松山、萬華在 34～37 年。"], size=13, bullets=True, space_after=8, name="說明內文")
    out = D / "臺北市行政區成交屋齡_可編輯圖表.pptx"
    prs.save(out)
    print(out)


if __name__ == "__main__":
    main()
