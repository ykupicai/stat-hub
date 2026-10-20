"""有容積率之使用分區的公私有土地比例 → PowerPoint 原生（可編輯）圖表。

輸入：案件/臺北市_不動產交易分析/容積率分區公私有土地/總表.xlsx（analyze_臺北市_容積率分區_公私有土地.py）
輸出：同資料夾 臺北市容積率分區_公私有土地_可編輯圖表.pptx
  第 1 頁：六大類使用分區的公私有面積比例（100% 堆疊橫條）；第 2 頁：面積前 16 種使用分區；第 3 頁：公有土地面積由哪些分區構成（橫條）
執行：python scripts/build_容積率分區公私有_可編輯圖表.py
"""
import importlib.util
import os
import re
import sys
from pathlib import Path

import pandas as pd
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
sys.argv = [sys.argv[0]]
spec = importlib.util.spec_from_file_location("deck", ROOT / "scripts" / "build_臺北市_行政區三表簡報.py")
K = importlib.util.module_from_spec(spec)
spec.loader.exec_module(K)
NO_PF = os.environ.get("NO_PF") == "1"
RC_ONLY = os.environ.get("RC_ONLY") == "1"   # NO_PF=1：不計入公共設施用地（學校用地、機關與公用設施用地）
D = ROOT / "案件" / "臺北市_不動產交易分析" / ("容積率分區公私有土地_住宅商業區" if RC_ONLY else "容積率分區公私有土地_不含公設" if NO_PF else "容積率分區公私有土地")
SRC = "資料：都發局地籍圖（421,843 地號）、容積使用分區塊、地政局公有土地圖層；公私共有地號依公有持分計"
GROUPS = ["住宅區", "商業區"] if RC_ONLY else ["住宅區", "商業區", "工業區", "專用區與其他"] if NO_PF else ["住宅區", "商業區", "工業區", "學校用地", "機關與公用設施用地", "專用區與其他"]


def group_of(n):
    if re.search(r"專用區|風景區|文教區|行政區$|娛樂|保存|創意|業務設施|聯合開發|捷運開發|住商混合", n) and "學校" not in n and "大學" not in n:
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


def chart(slide, cats, pub, pri, x, y, w, h, name, number_font=10):
    cd = CategoryChartData()
    cd.categories = cats
    cd.add_series("公有", [v / 100 for v in pub])
    cd.add_series("私有", [v / 100 for v in pri])
    gf = slide.shapes.add_chart(XL_CHART_TYPE.BAR_STACKED_100, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    gf.name = name
    ch = gf.chart
    ch.has_legend = True
    ch.legend.include_in_layout = False
    ch.legend.font.size = Pt(11)
    ch.legend.font.name = K.FONT
    ch.has_title = False
    ca, va = ch.category_axis, ch.value_axis
    ca.reverse_order = True
    ca.tick_labels.font.size = Pt(11)
    ca.tick_labels.font.name = K.FONT
    ca.format.line.color.rgb = RGBColor(0x99, 0x99, 0x99)
    va.tick_labels.font.size = Pt(10)
    va.tick_labels.number_format, va.tick_labels.number_format_is_linked = "0%", False
    va.major_gridlines.format.line.color.rgb = RGBColor(0xE3, 0xE3, 0xE3)
    ch.plots[0].gap_width = 40
    ch.plots[0].overlap = 100
    for s_, col in zip(ch.plots[0].series, ["C0392B", "BFD4E8"]):
        s_.format.fill.solid()
        s_.format.fill.fore_color.rgb = RGBColor.from_string(col)
        dl = s_.data_labels
        dl.show_value = True
        dl.number_format = '0%'
        dl.number_format_is_linked = False
        dl.font.size = Pt(number_font)
        dl.font.name = K.FONT
        dl.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF) if col == "C0392B" else RGBColor(0x22, 0x2B, 0x3A)
        dl.position = XL_LABEL_POSITION.CENTER
    return gf


def main():
    d = pd.read_excel(D / "總表.xlsx", header=1)
    d = d[d["使用分區"].notna() & (d["使用分區"] != "全市合計") & d["公有面積(公頃)"].notna()].copy()
    d["大類"] = d["使用分區"].map(group_of)
    tot_a, tot_p = d["分區面積(公頃)"].sum(), d["公有面積(公頃)"].sum()
    g = d.groupby("大類")[["分區面積(公頃)", "公有面積(公頃)"]].sum().reindex(GROUPS)
    g["pub"] = g["公有面積(公頃)"] / g["分區面積(公頃)"] * 100
    cats1 = ["全市有容積率分區"] + GROUPS
    pub1 = [tot_p / tot_a * 100] + g["pub"].tolist()
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    t1 = (f"只統計住宅區與商業區：公有僅 {tot_p / tot_a * 100:.1f}%，住宅區 {g.loc['住宅區', 'pub']:.1f}%、商業區 {g.loc['商業區', 'pub']:.1f}%" if RC_ONLY
          else f"不含公共設施用地：全市有容積率分區公有僅 {tot_p / tot_a * 100:.1f}%，住宅區 {g.loc['住宅區', 'pub']:.1f}%、商業區 {g.loc['商業區', 'pub']:.1f}%" if NO_PF
          else f"有容積率的使用分區：公有 {tot_p / tot_a * 100:.1f}%；住宅區 {g.loc['住宅區', 'pub']:.1f}%、商業區 {g.loc['商業區', 'pub']:.1f}%，學校用地 {g.loc['學校用地', 'pub']:.1f}%")
    s = K.title_only(prs, t1, source=SRC)
    chart(s, [f"{c}（{a:,.0f}公頃）" for c, a in zip(cats1, [tot_a] + g["分區面積(公頃)"].tolist())], pub1, [100 - v for v in pub1], 0.5, 1.5, 8.6, 5.35, "圖表：大類公私有面積比例", 12)
    px, pw = 9.4, 3.45
    panel = s.shapes.add_shape(1, Inches(px), Inches(1.5), Inches(pw), Inches(5.35))
    panel.fill.solid(); panel.fill.fore_color.rgb = K.TINT; panel.line.fill.background(); panel.shadow.inherit = False; panel.name = "說明底板"
    K.textbox(s, px + 0.15, 1.62, pw - 0.3, 0.4, ["重點"], size=18, color=K.NAVY, bold=True, space_after=0, name="說明標題")
    K.textbox(s, px + 0.15, 2.1, pw - 0.3, 3.5, [
        f"全市有容積率分區 {tot_a:,.0f} 公頃，公有 {tot_p:,.0f} 公頃（{tot_p / tot_a * 100:.1f}%）。",
        f"住宅區（{g.loc['住宅區', '分區面積(公頃)']:,.0f} 公頃）公有 {g.loc['住宅區', 'pub']:.1f}%，商業區（{g.loc['商業區', '分區面積(公頃)']:,.0f} 公頃）{g.loc['商業區', 'pub']:.1f}%" + ("。" if RC_ONLY else f"，工業區 {g.loc['工業區', 'pub']:.1f}%。"),
        *([] if (NO_PF or RC_ONLY) else [f"學校用地公有 {g.loc['學校用地', 'pub']:.1f}%；機關與公用設施用地 {g.loc['機關與公用設施用地', 'pub']:.1f}%。"]),
        *([] if RC_ONLY else [f"專用區與其他 {g.loc['專用區與其他', 'pub']:.1f}%。"])] + (["只統計住宅區與商業區。"] if RC_ONLY else ["已不計入學校用地與機關、公用設施用地。"] if NO_PF else []), size=13, bullets=True, space_after=7, name="說明內文")
    K.textbox(s, px + 0.15, 5.65, pw - 0.3, 1.1, ["面積為地號面與分區塊的交集。", "公有＝公有土地圖層地號；公私共有地號只計公有持分。"], size=10, color=K.MUTED, space_after=2, name="口徑")
    # 第 2 頁：面積前 16 種
    top = d.sort_values("分區面積(公頃)", ascending=False).head(16).copy()
    top["pub"] = top["公有面積占比%"]
    top = top.sort_values("pub")
    s2 = K.title_only(prs, "面積前 16 種使用分區的公有與私有土地比例（依公有占比排序" + ("；不含公共設施用地" if NO_PF else "") + "）", source=SRC)
    chart(s2, [f"{n}（{a:,.0f}公頃）" for n, a in zip(top["使用分區"], top["分區面積(公頃)"])], top["pub"].tolist(), [100 - v for v in top["pub"]], 0.5, 1.4, 12.3, 5.5, "圖表：主要使用分區公私有比例", 10)
    # 第 3 頁：公有土地由哪些分區構成
    gg = g.sort_values("公有面積(公頃)", ascending=False)
    t3 = (f"{tot_p:,.0f} 公頃的公有土地中，住宅區占 {gg.loc['住宅區', '公有面積(公頃)'] / tot_p * 100:.0f}%、商業區占 {gg.loc['商業區', '公有面積(公頃)'] / tot_p * 100:.0f}%" if RC_ONLY
          else f"{tot_p:,.0f} 公頃的公有土地（不含公共設施用地），住宅區占 {gg.loc['住宅區', '公有面積(公頃)'] / tot_p * 100:.0f}%、專用區與其他占 {gg.loc['專用區與其他', '公有面積(公頃)'] / tot_p * 100:.0f}%" if NO_PF
          else f"{tot_p:,.0f} 公頃的公有土地，學校用地占 {gg.loc['學校用地', '公有面積(公頃)'] / tot_p * 100:.0f}%、機關與公用設施用地占 {gg.loc['機關與公用設施用地', '公有面積(公頃)'] / tot_p * 100:.0f}%")
    s3 = K.title_only(prs, t3, source=SRC)
    gg = g.sort_values("公有面積(公頃)", ascending=False)
    cd = CategoryChartData()
    cd.categories = gg.index.tolist()
    cd.add_series("公有面積（公頃）", [round(v, 1) for v in gg["公有面積(公頃)"]])
    gf = s3.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.5), Inches(1.5), Inches(8.6), Inches(5.35), cd)
    gf.name = "圖表：公有面積構成"
    ch = gf.chart
    ch.has_legend = False
    ch.category_axis.reverse_order = True
    ch.category_axis.tick_labels.font.size = Pt(12)
    ch.category_axis.tick_labels.font.name = K.FONT
    ch.value_axis.tick_labels.font.size = Pt(10)
    ch.value_axis.major_gridlines.format.line.color.rgb = RGBColor(0xE3, 0xE3, 0xE3)
    ch.plots[0].gap_width = 50
    sr = ch.plots[0].series[0]
    sr.format.fill.solid()
    sr.format.fill.fore_color.rgb = RGBColor(0xC0, 0x39, 0x2B)
    dl = sr.data_labels
    dl.show_value = True
    dl.number_format = '#,##0'
    dl.number_format_is_linked = False
    dl.font.size = Pt(12)
    dl.font.name = K.FONT
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    panel = s3.shapes.add_shape(1, Inches(px), Inches(1.5), Inches(pw), Inches(5.35))
    panel.fill.solid(); panel.fill.fore_color.rgb = K.TINT; panel.line.fill.background(); panel.shadow.inherit = False; panel.name = "說明底板"
    K.textbox(s3, px + 0.15, 1.62, pw - 0.3, 0.4, ["占公有土地"], size=18, color=K.NAVY, bold=True, space_after=0, name="說明標題")
    K.textbox(s3, px + 0.15, 2.1, pw - 0.3, 4.5, [f"{n}　{v:,.0f} 公頃（{v / tot_p * 100:.1f}%）" for n, v in zip(gg.index, gg["公有面積(公頃)"])], size=13, bullets=True, space_after=7, name="說明內文")
    out = D / ("臺北市容積率分區_公私有土地_可編輯圖表_住宅商業區.pptx" if RC_ONLY else "臺北市容積率分區_公私有土地_可編輯圖表_不含公設.pptx" if NO_PF else "臺北市容積率分區_公私有土地_可編輯圖表.pptx")
    prs.save(out)
    print(out)


if __name__ == "__main__":
    main()
