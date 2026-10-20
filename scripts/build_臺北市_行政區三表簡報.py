"""臺北市行政區三表（T1 使用分區、T2/T2b 建物用途、T3 總樓層、T4 所在樓層）圖文說明簡報。

輸入：案件/臺北市_不動產交易分析/行政區三表_105至114/ 的圖T*.png（先跑 plot_臺北市_行政區三表_堆疊橫條.py）
輸出：同資料夾 臺北市行政區三表_圖文說明.pptx
說明文字的數字取自 行政區三表_105至114 的表（占比分母口徑同圖）。
執行：python scripts/build_臺北市_行政區三表簡報.py
"""
import sys
from pathlib import Path

import pandas as pd
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt
from PIL import Image
from lxml import etree

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "案件" / "臺北市_不動產交易分析" / "行政區三表_105至114"
FONT = "Microsoft JhengHei"
NAVY, INK, MUTED, TINT, ORANGE = RGBColor(0x1F, 0x2A, 0x44), RGBColor(0x22, 0x2B, 0x3A), RGBColor(0x5F, 0x6B, 0x7A), RGBColor(0xF1, 0xF4, 0xF8), RGBColor(0xF5, 0x85, 0x18)
SRC = "資料：內政部不動產交易實價查詢服務網，臺北市不動產買賣，交易日 105～114 年"


def style(run, size, color=INK, bold=False):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = FONT
    rPr = run._r.get_or_add_rPr()
    for tag in ("a:ea", "a:cs"):
        el = rPr.find(qn(tag))
        if el is None:
            el = etree.SubElement(rPr, qn(tag))
        el.set("typeface", FONT)


def textbox(slide, x, y, w, h, paras, size=14, color=INK, bold=False, bullets=False, space_after=8, anchor=MSO_ANCHOR.TOP, align=PP_ALIGN.LEFT, name=None):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.05)
    tf.margin_top = tf.margin_bottom = Inches(0.03)
    for i, p_ in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(space_after)
        parts = p_ if isinstance(p_, list) else [(p_, bold)]
        for text, b in parts:
            r = p.add_run()
            r.text = text
            style(r, size, color, b)
        if bullets:
            pPr = p._p.get_or_add_pPr()
            pPr.set("marL", str(int(Inches(0.22))))
            pPr.set("indent", str(-int(Inches(0.22))))
            bu = etree.SubElement(pPr, qn("a:buChar"))
            bu.set("char", "■")
    return tb


def add_bg(slide, rgb):
    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = rgb


def title_only(prs, title, source=SRC):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(s, RGBColor(0xFF, 0xFF, 0xFF))
    textbox(s, 0.5, 0.35, 12.3, 0.95, [title], size=28, color=NAVY, bold=True, anchor=MSO_ANCHOR.MIDDLE, name="標題")
    if source:
        textbox(s, 0.5, 7.0, 12.3, 0.3, [source], size=10, color=MUTED, space_after=0, name="資料來源")
    return s


NATIVE = "--native" in sys.argv  # 以 PowerPoint 原生（可編輯）圖表取代 PNG 圖
NO, BL = "（無建物：純土地或純車位）", "（未填）"


def _pct(name, drop=()):
    t = pd.read_csv(D / f"{name}.csv", index_col=0, encoding="utf-8-sig").drop(index="合計", errors="ignore")
    t = t.drop(index=[r for r in drop if r in t.index])
    return t, t.div(t.sum(), axis=1) * 100


def native_specs():
    """圖檔名 → 圖表規格：標題、類別（由下往上，最後一個在最上方）、系列[(名稱, 色, {類別: 值})]、是否 100% 堆疊、條端合計。"""
    S = {}
    t, p = _pct("表1_行政區×使用分區_土地筆數")
    p.loc["其他"] = p.loc[["保護區", "農業區", "非都市土地", "（未標示）"]].sum()
    cats = ["全市"] + p.drop(columns="全市").loc["商業區"].sort_values().index.tolist()
    S["圖T1_使用分區_堆疊橫條.png"] = dict(
        title="圖T1 臺北市各行政區：交易所涉土地的使用分區組成（依商業區占比排序）", cats=cats, stack100=True,
        series=[(n, c, p.loc[n].to_dict()) for n, c in [("住宅區", "4C78A8"), ("商業區", "F58518"), ("公共設施用地", "9D9D9D"),
                                                         ("其他都市分區", "B279A2"), ("工業區", "54A24B"), ("其他", "E0C060")]])
    t, p = _pct("表2_行政區×建物用途_交易筆數", drop=[NO, BL])
    main_c = ["住家用", "商業用", "辦公用", "工業用", "住商用"]
    other = p.drop(index=main_c).sum()
    p = p.loc[main_c]
    p.loc["其他用途"] = other
    cats = ["全市"] + p.drop(columns="全市").loc["住家用"].sort_values().index.tolist()
    cols2 = dict(zip(main_c + ["其他用途"], ["4C78A8", "F58518", "E45756", "54A24B", "B279A2", "BBBBBB"]))
    S["圖T2_建物用途_堆疊橫條.png"] = dict(
        title="圖T2 臺北市各行政區：有建物交易的主要用途組成（依住家用占比排序）", cats=cats, stack100=True,
        series=[(n, c, p.loc[n].to_dict()) for n, c in cols2.items()])
    u = p.loc[["商業用", "辦公用", "工業用", "住商用"]]
    tot = u.sum()
    cats = ["全市"] + tot.drop("全市").sort_values().index.tolist()
    S["圖T2b_非住家用途_堆疊橫條.png"] = dict(
        title="圖T2b 臺北市各行政區：非住家用途建物交易占比（依非住家合計排序）", cats=cats, stack100=False,
        series=[(n, cols2[n], u.loc[n].to_dict()) for n in u.index], totals=tot.to_dict(), axis_max=30)
    t, p = _pct("表3a_行政區×建物總樓層_交易筆數", drop=[NO, BL])
    hi = p.loc[["11-15層", "16-25層", "26層以上"]].sum()
    cats = ["全市"] + hi.drop("全市").sort_values().index.tolist()
    S["圖T3_總樓層_堆疊橫條.png"] = dict(
        title="圖T3 臺北市各行政區：交易建物的總樓層分布（依 11 層以上合計排序）", cats=cats, stack100=True,
        series=[(n, c, p.loc[n].to_dict()) for n, c in zip(["5層以下", "6-10層", "11-15層", "16-25層", "26層以上"],
                                                          ["DCE9F5", "A9C8E4", "6FA3D0", "3472AD", "12385F"])])
    t, p = _pct("表3b_行政區×交易所在樓層_交易筆數", drop=[NO, BL])
    cats = ["全市"] + p.drop(columns="全市").loc["6-10樓"].sort_values().index.tolist()
    S["圖T4_所在樓層_堆疊橫條.png"] = dict(
        title="圖T4 臺北市各行政區：交易標的所在樓層（依 6-10 樓占比排序）", cats=cats, stack100=True,
        series=[(n, c, p.loc[n].to_dict()) for n, c in zip(["地下層", "1樓", "2-5樓", "6-10樓", "11樓以上", "整棟(全)"],
                                                          ["7A7A7A", "F2CF6B", "A9C8E4", "6FA3D0", "12385F", "E45756"])])
    return S


def add_native_chart(slide, spec, x, y, w, h):
    cd = CategoryChartData()
    cd.categories = spec["cats"]
    for name, _, vals in spec["series"]:
        cd.add_series(name, [round(float(vals[c]), 4) for c in spec["cats"]])
    if spec.get("totals"):
        cd.add_series("合計", [0.0001] * len(spec["cats"]))
    kind = XL_CHART_TYPE.BAR_STACKED_100 if spec["stack100"] else XL_CHART_TYPE.BAR_STACKED
    gf = slide.shapes.add_chart(kind, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    gf.name = "圖表：" + spec["title"][:6]
    ch = gf.chart
    ch.font.name, ch.font.size = FONT, Pt(10)
    ch.has_title = True
    ch.chart_title.text_frame.text = spec["title"]
    for r in ch.chart_title.text_frame.paragraphs[0].runs:
        r.font.size, r.font.bold, r.font.name = Pt(12), True, FONT
        r.font.color.rgb = NAVY
    ch.has_legend = True
    ch.legend.position = XL_LEGEND_POSITION.BOTTOM
    ch.legend.include_in_layout = False
    ch.legend.font.size = Pt(10)
    plot = ch.plots[0]
    plot.gap_width, plot.overlap = 35, 100
    va = ch.value_axis
    va.has_major_gridlines = False
    va.tick_labels.font.size = Pt(10)
    if spec["stack100"]:
        va.tick_labels.number_format, va.tick_labels.number_format_is_linked = "0%", False
    else:
        va.maximum_scale, va.minimum_scale = spec["axis_max"], 0
        va.tick_labels.number_format, va.tick_labels.number_format_is_linked = '0"%"', False
    ch.category_axis.tick_labels.font.size = Pt(11)
    ch.category_axis.format.line.color.rgb = RGBColor(0x88, 0x88, 0x88)
    for i, (name, hexc, _) in enumerate(spec["series"]):
        ser = plot.series[i]
        ser.format.fill.solid()
        ser.format.fill.fore_color.rgb = RGBColor.from_string(hexc)
        ser.format.line.color.rgb = RGBColor(255, 255, 255)
        ser.format.line.width = Pt(0.5)
        dl = ser.data_labels
        dl.show_value = True
        dl.number_format = '[<5]"";[<10]0.0;0' if spec["stack100"] else '[<1.5]"";0.0'
        dl.number_format_is_linked = False
        dl.position = XL_LABEL_POSITION.CENTER
        dark = sum(int(hexc[k:k + 2], 16) for k in (0, 2, 4)) < 400
        dl.font.size = Pt(9)
        dl.font.color.rgb = RGBColor(255, 255, 255) if dark else RGBColor(0x22, 0x22, 0x22)
    if spec.get("totals"):
        ser = plot.series[len(spec["series"])]
        ser.format.fill.background()
        ser.format.line.fill.background()
        for j, c in enumerate(spec["cats"]):
            lab = ser.points[j].data_label
            lab.position = XL_LABEL_POSITION.INSIDE_BASE
            lab.text_frame.text = f"{spec['totals'][c]:.1f}"
            for r in lab.text_frame.paragraphs[0].runs:
                r.font.size, r.font.bold = Pt(10), True
                r.font.color.rgb = INK
        # 隱藏「合計」圖例項
        leg = ch.legend._element
        le = etree.SubElement(leg, qn("c:legendEntry"))
        etree.SubElement(le, qn("c:idx")).set("val", str(len(spec["series"])))
        etree.SubElement(le, qn("c:delete")).set("val", "1")
        leg.remove(le)
        leg.insert(1, le)  # legendPos 之後


def chart_slide(prs, title, img, bullets, note, base):
    s = title_only(prs, title)
    if NATIVE:
        w, h = 7.9, 5.35
        add_native_chart(s, native_specs()[img], 0.5, 1.5, w, h)
    else:
        iw, ih = Image.open(D / img).size
        h = 5.35
        w = h * iw / ih
        max_w = 7.9
        if w > max_w:
            w, h = max_w, max_w * ih / iw
        s.shapes.add_picture(str(D / img), Inches(0.5), Inches(1.5), Inches(w), Inches(h)).name = "圖：" + img
    px = 0.5 + w + 0.35
    pw = 13.333 - 0.5 - px
    panel = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(px), Inches(1.5), Inches(pw), Inches(5.35))
    panel.name = "說明底板"
    panel.fill.solid()
    panel.fill.fore_color.rgb = TINT
    panel.line.fill.background()
    panel.shadow.inherit = False
    textbox(s, px + 0.15, 1.62, pw - 0.3, 0.4, ["重點"], size=18, color=NAVY, bold=True, space_after=0, name="說明標題")
    textbox(s, px + 0.15, 2.1, pw - 0.3, 3.5, bullets, size=14, bullets=True, space_after=7, name="說明內文")
    textbox(s, px + 0.15, 5.7, pw - 0.3, 1.1, [base, note], size=11, color=MUTED, space_after=3, name="口徑註記")
    return s


def main():
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)

    # 封面
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(s, NAVY)
    textbox(s, 0.8, 2.3, 11.7, 1.6, ["臺北市各行政區不動產買賣交易", "使用分區、建物用途與樓層"], size=40, color=RGBColor(255, 255, 255), bold=True, space_after=4, name="封面標題")
    textbox(s, 0.8, 4.3, 11.7, 0.9, ["交易日 105～114 年，共 236,198 筆買賣交易的圖文說明"], size=20, color=RGBColor(0xCA, 0xDC, 0xFC), name="封面副標")
    textbox(s, 0.8, 6.6, 11.7, 0.4, ["資料來源：內政部不動產交易實價查詢服務網"], size=12, color=RGBColor(0xCA, 0xDC, 0xFC), name="封面來源")

    # 摘要
    s = title_only(prs, "各區的土地、用途、樓層呈現三種不同的組成")
    cards = [("商業核心區", "中山、萬華、中正、大同的商業區占土地筆數 43～57%，非住家用途與 11 層以上建物的占比也都在全市前列。"),
             ("住宅型外圍區", "文山、北投、士林的住宅區占 56～69%，住家用占 88～92%，建物以 5 層以下居多。"),
             ("產業型區域", "南港、內湖的工業區占 11.4%、7.6%，工業用建物占 6.2%、4.0%，是全市工業用交易最集中的兩區。"),
             ("高樓層", "全市 44.5% 的交易建物在 11 層以上；中山、萬華、大同超過 53%，士林只有 28.8%。")]
    for i, (h, t) in enumerate(cards):
        x = 0.5 + (i % 2) * 6.25
        y = 1.6 + (i // 2) * 2.65
        box = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(6.0), Inches(2.45))
        box.name = f"摘要卡{i + 1}"
        box.fill.solid(); box.fill.fore_color.rgb = TINT; box.line.fill.background(); box.shadow.inherit = False
        textbox(s, x + 0.25, y + 0.2, 5.5, 0.5, [h], size=20, color=NAVY, bold=True, space_after=0, name=f"摘要標題{i + 1}")
        textbox(s, x + 0.25, y + 0.8, 5.5, 1.5, [t], size=15, space_after=0, name=f"摘要內文{i + 1}")

    chart_slide(prs, "商業區主導在中山、萬華、中正，山邊區以住宅區為主", "圖T1_使用分區_堆疊橫條.png", [
        "全市 360,346 筆土地：住宅區 52.4%、商業區 27.0%、公共設施用地 13.8%。",
        "商業區占比最高：中山 56.6%、萬華 48.0%、中正 44.9%、大同 43.2%；住宅區最高是文山 69.2%。",
        "工業區集中在南港 11.4%、內湖 7.6%；農業區只有北投明顯（2.9%）；保護區以士林 3.7%、南港 3.5% 最高。",
        "公共設施用地以士林 22.2%、大安 18.6% 最高，多為道路用地的持分；大同的其他都市分區 14.2%（特定專用區）。"],
        "單位是交易所附地號的列數，同一地號多次交易重複計，不是面積。", "分母：360,346 筆土地。")

    chart_slide(prs, "住家用占八成，中山的商業用占比最高", "圖T2_建物用途_堆疊橫條.png", [
        "全市有建物交易中，住家用 81.2%、商業用 10.7%、辦公用 2.6%、工業用 1.1%、住商用 0.8%。",
        "住家用最高：文山 91.9%、士林 88.8%、北投 88.4%；最低是中山 70.3%。",
        "商業用最高：中山 23.6%、大同 17.2%、松山 12.9%、中正 12.1%。",
        "辦公用以中正 5.2%、萬華 4.7%、信義 4.2% 較高。"],
        "排除純土地、純車位與用途未填；其他用途含見使用執照等。", "分母：185,658 筆有建物且用途已填的交易。")

    chart_slide(prs, "非住家用途集中在中山與大同，工業用在南港與內湖", "圖T2b_非住家用途_堆疊橫條.png", [
        "非住家用途合計（商業、辦公、工業、住商）全市 15.1%。",
        "最高：中山 27.4%、大同 23.7%、中正 18.1%；最低：文山 4.6%。",
        "工業用：南港 6.2%、內湖 4.0%、萬華 1.9%，其他區都在 1% 以下。",
        "橫條右端數字為各區非住家合計；條內標籤為單項占比。"],
        "與前一張圖同一母體，只放大非住家的部分。", "分母：185,658 筆有建物且用途已填的交易（含其他用途）。")

    chart_slide(prs, "中山、大同、萬華建物較高層，士林、北投以 5 層以下為主", "圖T3_總樓層_堆疊橫條.png", [
        "全市：5 層以下 31.9%、6-10 層 23.7%、11-15 層 32.4%、16-25 層 9.7%、26 層以上 2.4%；11 層以上合計 44.5%。",
        "11 層以上占比最高：中山 53.9%、萬華 53.7%、大同 53.2%、中正 51.0%；最低是士林 28.8%（5 層以下占 48.0%）。",
        "16 層以上的高樓：南港 19.4%、萬華 18.9%、文山 15.5%；26 層以上以萬華 7.6%、文山 6.9%、南港 5.2% 較高。"],
        "樓層是建物登記的總樓層數，不是交易標的所在樓層。", "分母：188,346 筆有建物且樓層已填的交易。")

    chart_slide(prs, "交易標的多在 2-5 樓，中山高樓層交易比例最高", "圖T4_所在樓層_堆疊橫條.png", [
        "全市：2-5 樓 49.2%、6-10 樓 24.8%、11 樓以上 13.6%、1 樓 9.2%、整棟 2.6%、地下 0.7%。",
        "6 樓以上占比最高：中山 46.9%、萬華 43.4%、大同 43.2%；最低是士林 26.4%。",
        "1 樓交易：士林 12.6%、信義 11.2%、文山 10.3% 較高。",
        "整棟（全）交易：大同 6.4%、萬華 5.0%、士林 4.6%，其餘區都在 3.6% 以下。"],
        "所在樓層取移轉層次的第一個樓層；含地下者歸地下層。", "分母：188,355 筆有建物且移轉層次已填的交易。")

    # 口徑
    s = title_only(prs, "口徑與限制")
    textbox(s, 0.5, 1.6, 12.3, 5.2, [
        "母體：臺北市不動產買賣，交易日 105～114 年，共 236,198 筆；不含預售屋與租賃。",
        "105 年已補入第 1～3 季，涵蓋全年。",
        "「所有交易」不排除特殊交易（親友、債權債務等），也不分交易標的（土地、建物、房地、車位都算）。",
        "T1 以土地筆數為單位（交易所附地號列數，同一地號多次交易重複計）；T2～T4 以交易筆數為單位。",
        "T2～T4 的占比不含純土地、純車位交易（全市 15.3%）以及用途或樓層未填者，只比較有建物的交易。",
        "使用分區欄位寫法不統一，已歸為住宅區、商業區、工業區、公共設施用地、保護區、農業區、其他都市分區；另有少數未標示。",
        "各表為累計 10 年的合計，沒有分年度的趨勢；建物型態分類 110 年起收斂，本簡報未使用。"],
        size=16, bullets=True, space_after=12, name="口徑內文")

    out = D / ("臺北市行政區三表_圖文說明_可編輯圖表.pptx" if NATIVE else "臺北市行政區三表_圖文說明.pptx")
    prs.save(out)
    print(out)


if __name__ == "__main__":
    main()
