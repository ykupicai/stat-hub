"""臺北市行政區三表（使用分區、建物用途、建物樓層）報告書式說明 .docx。

輸入：案件/臺北市_不動產交易分析/行政區三表_105至114/ 的表 CSV 與圖T*.png
輸出：同資料夾 臺北市行政區三表_分析報告.docx
正文數字取自各表（口徑同圖）；文中占比若與表末位差 0.1 屬四捨五入。
執行：python scripts/build_臺北市_行政區三表報告.py
"""
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "案件" / "臺北市_不動產交易分析" / "行政區三表_105至114"
BODY, HEAD = "標楷體", "微軟正黑體"
NO, BL = "（無建物：純土地或純車位）", "（未填）"
DIST = ["中山區", "大同區", "中正區", "萬華區", "松山區", "大安區", "信義區", "內湖區", "南港區", "士林區", "北投區", "文山區"]


def load(name):
    return pd.read_csv(D / f"{name}.csv", index_col=0, encoding="utf-8-sig").drop(index="合計", errors="ignore")


def pct(t):
    return (t.div(t.sum(), axis=1) * 100)


def set_font(run, name, size=None, bold=None, color=None):
    run.font.name = name
    rPr = run._r.get_or_add_rPr()
    rf = rPr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rPr.insert(0, rf)
    for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rf.set(qn(a), name)
    if size:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if color:
        run.font.color.rgb = color


def style_font(style, name, size, bold=False, color=None):
    style.font.name = name
    style.font.size = Pt(size)
    style.font.bold = bold
    if color:
        style.font.color.rgb = color
    rPr = style.element.get_or_add_rPr()
    rf = rPr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rPr.insert(0, rf)
    for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rf.set(qn(a), name)
    for a in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        if rf.get(qn(a)) is not None:
            del rf.attrib[qn(a)]


def shade(cell, hex_):
    tcPr = cell._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear")
    sh.set(qn("w:color"), "auto")
    sh.set(qn("w:fill"), hex_)
    tcPr.append(sh)


def para(doc, text, indent=True, after=6, align=None):
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = 1.5
    p.paragraph_format.space_after = Pt(after)
    if indent:
        p.paragraph_format.first_line_indent = Cm(0.85)
    if align:
        p.alignment = align
    r = p.add_run(text)
    set_font(r, BODY, 12)
    return p


def figure(doc, img, caption, width_cm=15.5):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_before = Pt(6)
    p.add_run().add_picture(str(D / img), width=Cm(width_cm))
    c = doc.add_paragraph()
    c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    c.paragraph_format.space_after = Pt(10)
    set_font(c.add_run(caption), HEAD, 10, color=RGBColor(0x55, 0x55, 0x55))


def table(doc, title, df, note):
    """df：列＝行政區（含全市），欄＝類別；數值為占比。"""
    p = doc.add_paragraph()
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(3)
    set_font(p.add_run(title), HEAD, 10.5, bold=True)
    t = doc.add_table(rows=1, cols=len(df.columns) + 1)
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = t.rows[0].cells
    for c, h in zip(hdr, ["行政區"] + list(df.columns)):
        c.text = ""
        r = c.paragraphs[0].add_run(h)
        set_font(r, HEAD, 9, bold=True)
        c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        shade(c, "E8EDF4")
    for name, row in df.iterrows():
        cells = t.add_row().cells
        cells[0].text = ""
        set_font(cells[0].paragraphs[0].add_run(name), HEAD, 9, bold=(name == "全市"))
        for c, v in zip(cells[1:], row):
            c.text = ""
            r = c.paragraphs[0].add_run(f"{v:.1f}")
            set_font(r, HEAD, 9, bold=(name == "全市"))
            c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
        if name == "全市":
            for c in cells:
                shade(c, "F4F6F9")
    for row in t.rows:
        row.cells[0].width = Cm(2.2)
    # 表頭跨頁重複
    trPr = t.rows[0]._tr.get_or_add_trPr()
    th = OxmlElement("w:tblHeader")
    th.set(qn("w:val"), "true")
    trPr.append(th)
    n = doc.add_paragraph()
    n.paragraph_format.space_after = Pt(10)
    set_font(n.add_run(note), HEAD, 9, color=RGBColor(0x55, 0x55, 0x55))


def heading(doc, text, level):
    h = doc.add_heading(text, level=level)
    return h


def add_page_number(section):
    p = section.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for kind, txt in (("begin", None), (None, "PAGE"), ("end", None)):
        r = p.add_run()
        set_font(r, HEAD, 9)
        if kind:
            fc = OxmlElement("w:fldChar")
            fc.set(qn("w:fldCharType"), kind)
            r._r.append(fc)
        else:
            it = OxmlElement("w:instrText")
            it.set(qn("xml:space"), "preserve")
            it.text = txt
            r._r.append(it)


def main():
    t1 = load("表1_行政區×使用分區_土地筆數")
    t1.loc["其他分區"] = t1.loc[["保護區", "農業區", "非都市土地", "（未標示）"]].sum()
    p1 = pct(t1.loc[["住宅區", "商業區", "公共設施用地", "其他都市分區", "工業區", "其他分區"]])
    p1 = p1.T.loc[DIST + ["全市"]]
    p1.columns = ["住宅區", "商業區", "公共設施用地", "其他都市分區", "工業區", "保護區、農業區等"]

    t2 = load("表2_行政區×建物用途_交易筆數").drop(index=[NO, BL])
    main_c = ["住家用", "商業用", "辦公用", "工業用", "住商用"]
    t2.loc["其他用途"] = t2.drop(index=main_c).sum()
    p2 = pct(t2.loc[main_c + ["其他用途"]]).T.loc[DIST + ["全市"]]
    p2["非住家合計"] = p2[["商業用", "辦公用", "工業用", "住商用"]].sum(axis=1)

    t3 = load("表3a_行政區×建物總樓層_交易筆數").drop(index=[NO, BL])
    p3 = pct(t3).T.loc[DIST + ["全市"]]
    p3["11層以上合計"] = p3[["11-15層", "16-25層", "26層以上"]].sum(axis=1)

    t4 = load("表3b_行政區×交易所在樓層_交易筆數").drop(index=[NO, BL])
    p4 = pct(t4).T.loc[DIST + ["全市"]]
    p4["6樓以上合計"] = p4[["6-10樓", "11樓以上"]].sum(axis=1)

    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2.5)
    sec.top_margin = sec.bottom_margin = Cm(2.5)
    style_font(doc.styles["Normal"], BODY, 12)
    style_font(doc.styles["Title"], HEAD, 22, True, RGBColor(0x1F, 0x2A, 0x44))
    style_font(doc.styles["Heading 1"], HEAD, 16, True, RGBColor(0x1F, 0x2A, 0x44))
    style_font(doc.styles["Heading 2"], HEAD, 13, True, RGBColor(0x1F, 0x2A, 0x44))
    for s in ("Heading 1", "Heading 2"):
        doc.styles[s].paragraph_format.space_before = Pt(14)
        doc.styles[s].paragraph_format.space_after = Pt(6)
        doc.styles[s].paragraph_format.keep_with_next = True
    add_page_number(sec)

    # 標題
    tp = doc.add_paragraph(style="Title")
    tp.alignment = WD_ALIGN_PARAGRAPH.LEFT
    tp.add_run("臺北市各行政區不動產買賣交易之使用分區、建物用途與樓層分析")
    sp = doc.add_paragraph()
    set_font(sp.add_run("實價登錄資料，交易日民國 105 年至 114 年"), HEAD, 12, color=RGBColor(0x55, 0x55, 0x55))
    sp.paragraph_format.space_after = Pt(14)

    heading(doc, "壹、前言與資料說明", 1)
    para(doc, "本文以內政部不動產交易實價查詢服務網之開放資料為基礎，統計臺北市 12 個行政區於民國 105 年至 114 年間的不動產買賣交易，共 236,198 筆，所附土地明細共 360,346 筆。目的在比較各行政區的交易標的於土地使用分區、建物主要用途及建物樓層三個面向的組成差異，供後續區位評估參考。")
    para(doc, "統計口徑說明如下。母體為不動產買賣，不含預售屋與租賃；「所有交易」不排除備註為親友、債權債務等之特殊交易，亦不區分交易標的（土地、建物、房地、車位均計入）。105 年資料已補入第 1 至第 3 季，涵蓋全年。使用分區係以交易所附地號之土地筆數計算，同一地號多次交易重複計入，反映的是成交土地的組成，並非各區土地面積結構；建物用途與樓層則以交易筆數計算，並排除純土地、純車位交易及欄位未填者，僅呈現有建物交易的組成。各圖橫軸為占比，縱軸為行政區，最下列為全市。")

    heading(doc, "貳、使用分區", 1)
    heading(doc, "一、整體情形", 2)
    para(doc, "全市 360,346 筆土地中，位於住宅區者占 52.4%，商業區占 27.0%，公共設施用地占 13.8%，三者合計 93.2%；其他都市分區占 3.3%，工業區占 1.9%，保護區占 1.0%，農業區占 0.3%。另有 882 筆（0.2%）未標示使用分區，13 筆為非都市土地。")
    figure(doc, "圖T1_使用分區_堆疊橫條.png", "圖 1　臺北市各行政區交易所涉土地之使用分區組成（依商業區占比排序）")
    heading(doc, "二、各區差異", 2)
    para(doc, "依商業區與住宅區之相對比重，各區可分為三類。第一類為商業區主導，包括中山區（商業區 56.6%）、萬華區（48.0%）、中正區（44.9%）與大同區（43.2%）；其中中正區住宅區占 45.3%，與商業區相當，大同區則另有 14.2% 位於其他都市分區（主要為特定專用區），為各區最高。第二類為住宅區主導，包括文山區（住宅區 69.2%）、北投區（64.1%）、南港區（62.6%）、內湖區（62.2%）與士林區（56.2%），這些行政區的商業區占比僅 9.8% 至 14.6%。第三類為住商混合，包括信義區（住宅區 54.8%、商業區 24.5%）、松山區（54.4%、30.0%）與大安區（48.6%、25.9%）。")
    para(doc, "特定分區方面，工業區集中於南港區（11.4%）與內湖區（7.6%），其餘各區均在 2.6% 以下；農業區僅北投區較為明顯（2.9%）；保護區以士林區（3.7%）與南港區（3.5%）最高。公共設施用地占比以士林區（22.2%）與大安區（18.6%）最高，中山區（7.9%）最低。由於一筆房地交易常附帶多筆含道路用地持分的土地，公共設施用地占比反映的是成交土地的附帶組成，不宜解讀為各區公共設施用地的實際比例。")
    table(doc, "表 1　各行政區交易土地之使用分區占比（%）", p1, "註：單位為土地筆數；「保護區、農業區等」含保護區、農業區、非都市土地與未標示。")

    heading(doc, "參、建物主要用途", 1)
    heading(doc, "一、整體情形", 2)
    para(doc, "排除純土地、純車位及用途未填者後，有建物之交易共 196,625 筆。全市以住家用為主，占 81.2%；商業用占 10.7%，辦公用占 2.6%，工業用占 1.1%，住商用占 0.8%，其他用途（含見使用執照、見其他登記事項等）占 3.7%。")
    figure(doc, "圖T2_建物用途_堆疊橫條.png", "圖 2　臺北市各行政區有建物交易之主要用途組成（依住家用占比排序）")
    heading(doc, "二、住家用與非住家用途", 2)
    para(doc, "住家用占比最高者為文山區（91.9%）、士林區（88.8%）與北投區（88.4%）；最低者為中山區（70.3%），其次為大同區（72.9%）與中正區（76.4%）。換言之，住家用占比與前述使用分區的分群大致吻合，商業區占比高的行政區，住家用占比相對較低。")
    para(doc, "將商業用、辦公用、工業用與住商用合計為非住家用途，全市占 15.1%。各區以中山區最高（27.4%），其中商業用即占 23.6%；大同區次之（23.7%，商業用 17.2%），中正區（18.1%）、萬華區（16.8%）、松山區（16.6%）與內湖區（15.9%）亦高於全市；文山區最低（4.6%），士林區（8.6%）與北投區（8.7%）亦偏低。")
    figure(doc, "圖T2b_非住家用途_堆疊橫條.png", "圖 3　臺北市各行政區非住家用途建物交易占比（依非住家合計排序，條端數字為合計）", 14.5)
    heading(doc, "三、辦公用與工業用", 2)
    para(doc, "辦公用以中正區（5.2%）、萬華區（4.7%）與信義區（4.2%）較高，全市為 2.6%。工業用則集中於南港區（6.2%）與內湖區（4.0%），萬華區為 1.9%，其餘各區均在 1% 以下，與南港、內湖工業區占比較高的特徵一致。另需說明，純土地或純車位交易占全市交易之 15.3%，其中士林區達 26.2%，為各區最高，這部分交易因無建物，未納入上述占比。")
    table(doc, "表 2　各行政區有建物交易之主要用途占比（%）", p2, "註：分母為排除純土地、純車位與用途未填後之交易筆數（185,658 筆）；非住家合計＝商業用、辦公用、工業用、住商用之和。")

    heading(doc, "肆、建物總樓層", 1)
    heading(doc, "一、整體情形", 2)
    para(doc, "排除純土地、純車位及樓層未填者後，有建物之交易共 199,648 筆。全市建物總樓層在 5 層以下者占 31.9%，6 至 10 層占 23.7%，11 至 15 層占 32.4%，16 至 25 層占 9.7%，26 層以上占 2.4%；11 層以上合計 44.5%。")
    figure(doc, "圖T3_總樓層_堆疊橫條.png", "圖 4　臺北市各行政區交易建物之總樓層分布（依 11 層以上合計排序）")
    heading(doc, "二、各區差異", 2)
    para(doc, "11 層以上建物占比超過半數者有中山區（53.9%）、萬華區（53.7%）、大同區（53.2%）與中正區（51.0%），其中中山區 11 至 15 層即占 44.9%；松山區（47.2%）、大安區（47.1%）與南港區（46.9%）接近半數；信義區（40.8%）、文山區（39.7%）、內湖區（39.1%）與北投區（35.3%）較低，士林區最低（28.8%），且 5 層以下占 48.0%，為各區最高。")
    para(doc, "就 16 層以上之高層建物而言，南港區占 19.4%、萬華區占 18.9%、文山區占 15.5%，高於全市的 12.1%；26 層以上以萬華區（7.6%）、文山區（6.9%）與南港區（5.2%）較高，松山區則無 26 層以上之交易。樓層為建物登記之總樓層數，反映的是交易建物的建築型態，並非交易標的所在樓層。")
    table(doc, "表 3　各行政區有建物交易之總樓層占比（%）", p3, "註：分母為排除純土地、純車位與樓層未填後之交易筆數（188,346 筆）。")

    heading(doc, "伍、交易標的所在樓層", 1)
    heading(doc, "一、整體情形", 2)
    para(doc, "交易標的所在樓層取移轉層次之第一個樓層，含地下者歸為地下層，「全」表示整棟。排除純土地、純車位及移轉層次未填者後，共 199,639 筆。全市以 2 至 5 樓為主，占 49.2%；6 至 10 樓占 24.8%，11 樓以上占 13.6%，1 樓占 9.2%，整棟占 2.6%，地下層占 0.7%。")
    figure(doc, "圖T4_所在樓層_堆疊橫條.png", "圖 5　臺北市各行政區交易標的所在樓層分布（依 6-10 樓占比排序）")
    heading(doc, "二、各區差異", 2)
    para(doc, "6 樓以上之交易占比以中山區最高（46.9%），其次為萬華區（43.4%）、大同區（43.2%）、中正區（41.7%）與大安區（41.5%）；士林區最低（26.4%）。1 樓交易占比以士林區（12.6%）、信義區（11.2%）與文山區（10.3%）較高，中山區最低（6.5%）。整棟交易以大同區（6.4%）、萬華區（5.0%）、士林區（4.6%）與北投區（3.6%）較高，其餘各區均在 2.5% 以下。")
    para(doc, "所在樓層與前節之總樓層不同：同一棟 15 層建物於 3 樓成交，總樓層歸入 11 至 15 層，所在樓層則歸入 2 至 5 樓，故所在樓層之分布較集中於低樓層。")
    table(doc, "表 4　各行政區有建物交易之所在樓層占比（%）", p4, "註：分母為排除純土地、純車位與移轉層次未填後之交易筆數（188,355 筆）；6 樓以上合計＝6-10 樓與 11 樓以上之和。")

    heading(doc, "陸、綜合觀察與限制", 1)
    para(doc, "綜合三個面向，各區的交易標的呈現相互呼應的組成。中山區、大同區、萬華區與中正區的商業區占比高，非住家用途比重大，建物亦以較高樓層居多，屬商業機能較強的區域；文山區、北投區與士林區以住宅區與住家用為主，建物樓層偏低；南港區與內湖區則因工業區集中，工業用建物占比明顯高於他區，南港區並有較高比例的 16 層以上建物。需說明的是，以上為組成比例的描述，彼此相關但未做因果檢定。")
    para(doc, "本分析有下列限制：（一）各表為 105 年至 114 年之累計，未分年度，無法呈現趨勢；（二）所有交易未排除特殊交易，也未區分交易標的；（三）使用分區欄位填寫方式不一，已歸併為住宅區、商業區、工業區、公共設施用地、保護區、農業區與其他都市分區，仍有 882 筆未標示；（四）使用分區以土地筆數計，並非面積，亦非各區土地利用現況。")

    out = D / "臺北市行政區三表_分析報告.docx"
    doc.save(out)
    print(out)


if __name__ == "__main__":
    main()
