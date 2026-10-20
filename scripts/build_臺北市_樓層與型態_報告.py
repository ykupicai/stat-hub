"""臺北市房地買賣樓層與建物型態（105～114 年）報告書式說明 .docx。

輸入：案件/臺北市_不動產交易分析/樓層與型態_年度/總表.xlsx 與圖1～圖4 PNG（先跑 analyze_臺北市_樓層與型態_年度.py）
輸出：同資料夾 臺北市樓層與型態_分析報告.docx
正文數字取自總表與該腳本的終端摘要。
執行：python scripts/build_臺北市_樓層與型態_報告.py
"""
import importlib.util
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
_s = importlib.util.spec_from_file_location("rep", ROOT / "scripts" / "build_臺北市_行政區三表報告.py")
R = importlib.util.module_from_spec(_s); _s.loader.exec_module(R)
D = ROOT / "案件" / "臺北市_不動產交易分析" / "樓層與型態_年度"
R.D = D  # figure() 讀圖的資料夾


def main():
    S = pd.read_excel(D / "總表.xlsx", header=1)
    S = S[S["行政區"] == "全市"].dropna(subset=["年"]).copy()
    S["年"] = S["年"].astype(int)
    t = S.set_index("年")[["房地買賣筆數", "樓層中位數", "5層以下%", "6-10層%", "11-15層%", "16-25層%", "26層以上%", "11層以上%"]]
    t.columns = ["筆數", "樓層中位數", "5層以下", "6-10層", "11-15層", "16-25層", "26層以上", "11層以上合計"]
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.left_margin = sec.right_margin = sec.top_margin = sec.bottom_margin = Cm(2.5)
    R.style_font(doc.styles["Normal"], R.BODY, 12)
    R.style_font(doc.styles["Title"], R.HEAD, 22, True, RGBColor(0x1F, 0x2A, 0x44))
    R.style_font(doc.styles["Heading 1"], R.HEAD, 16, True, RGBColor(0x1F, 0x2A, 0x44))
    R.style_font(doc.styles["Heading 2"], R.HEAD, 13, True, RGBColor(0x1F, 0x2A, 0x44))
    for s in ("Heading 1", "Heading 2"):
        doc.styles[s].paragraph_format.space_before = Pt(14)
        doc.styles[s].paragraph_format.space_after = Pt(6)
        doc.styles[s].paragraph_format.keep_with_next = True
    R.add_page_number(sec)
    tp = doc.add_paragraph(style="Title"); tp.alignment = WD_ALIGN_PARAGRAPH.LEFT
    tp.add_run("臺北市房地買賣交易之樓層與建物型態歷年變化分析")
    sp = doc.add_paragraph()
    R.set_font(sp.add_run("實價登錄資料，交易日民國 105 年至 114 年；全市與 12 個行政區"), R.HEAD, 12, color=RGBColor(0x55, 0x55, 0x55))
    sp.paragraph_format.space_after = Pt(14)
    P = lambda s: R.para(doc, s)

    R.heading(doc, "壹、前言與資料說明", 1)
    P("本文以內政部不動產交易實價查詢服務網之開放資料為基礎，逐年統計臺北市房地買賣交易的建物總樓層與建物型態，期間為民國 105 年至 114 年，共 198,147 筆，並比較全市與 12 個行政區。目的在以成交結構觀察臺北市新近交易的建物高度與型態是否改變，作為開發強度評估的輔助依據。")
    P("統計口徑說明如下。母體為房地買賣，即交易標的含房地者，不含預售屋、租賃、純土地與純車位，且總樓層能解析者；不排除特殊交易。樓層為建物登記之總樓層數，總樓層帶分為 5 層以下、6 至 10 層、11 至 15 層、16 至 25 層與 26 層以上。建物型態在平台分類於 110 年起收斂為住宅大樓、華廈、公寓與透天厝四類，故型態占比僅呈現 110 至 114 年，分母為這四類型態的筆數。需說明的是，成交結構反映的是被交易的建物，包含大量中古屋，並不等於當年新增的供給，因此宜視為開發強度的間接指標。")

    R.heading(doc, "貳、全市樓層結構的年度變化", 1)
    P("全市房地買賣的樓層結構在觀察期間先升後降。11 層以上建物占比由 105 年的 44.0% 緩升，至 109 年達 48.9% 的高點，其後逐年下降，113 年為 39.8%，114 年略回升至 40.3%。樓層中位數同樣由 105 至 108 年的 9 層升至 109、110 年的 10 層，113 年降至 7 層，114 年回到 8 層。")
    P("從樓層帶來看，變化的另一面是 5 層以下建物（以公寓為主）的占比回升，由 109 年的 28.1% 增至 113 年的 36.1%，114 年為 35.3%。16 至 25 層建物占比由 109 年的 12.0% 降至 113 年的 7.6%，降幅為各樓層帶中最明顯者。26 層以上的超高層建物占比多在 1.5% 至 3.8% 之間；105 年（4.9%）與 110 年（3.8%）因新案集中成交而偏高，其後回落至 1.6% 至 1.7%。")
    R.figure(doc, "圖1_全市樓層結構.png", "圖 1　臺北市房地買賣的樓層結構年度變化（全市）")
    p = doc.add_paragraph(); p.paragraph_format.keep_with_next = True
    R.set_font(p.add_run("表 1　全市房地買賣之總樓層帶占比與樓層中位數（%，層）"), R.HEAD, 10.5, bold=True)
    tb = doc.add_table(rows=1, cols=len(t.columns) + 1); tb.style = "Table Grid"; tb.alignment = WD_TABLE_ALIGNMENT.CENTER
    for c, h in zip(tb.rows[0].cells, ["年"] + list(t.columns)):
        c.text = ""; r = c.paragraphs[0].add_run(h); R.set_font(r, R.HEAD, 9, bold=True)
        c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER; R.shade(c, "E8EDF4")
    for y, row in t.iterrows():
        cells = tb.add_row().cells
        for c, v in zip(cells, [str(y)] + [f"{int(row['筆數']):,}", f"{row['樓層中位數']:.0f}"] + [f"{row[k]:.1f}" for k in t.columns[2:]]):
            c.text = ""; r = c.paragraphs[0].add_run(v); R.set_font(r, R.HEAD, 9)
            c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    n = doc.add_paragraph(); n.paragraph_format.space_after = Pt(10)
    R.set_font(n.add_run("註：母體為房地買賣且總樓層可解析者；各區與型態的年度數字詳附件總表（Excel）。"), R.HEAD, 9, color=RGBColor(0x55, 0x55, 0x55))

    R.heading(doc, "參、各行政區的差異", 1)
    P("以 106 至 108 年與 112 至 114 年兩個三年期比較，多數行政區的 11 層以上成交占比下降。降幅最大者為萬華區（57.5% 降至 43.8%）、中正區（52.6% 降至 45.5%）、內湖區（43.0% 降至 33.6%）、北投區（39.1% 降至 31.1%）與文山區（40.6% 降至 32.1%）。松山區（44.9% 至 45.9%）、信義區、大安區與士林區則大致持平。")
    P("就樓層高度本身而言，中山區的 11 層以上占比與樓層中位數長期居全市之首，中位數維持在 11 層，11 層以上占比由 54.9% 微降至 51.6%。士林區則是全市最低，11 層以上占比約 26%，樓層中位數 5 至 6 層。")
    P("超高層的變化呈現相反方向。南港區 26 層以上占比由 0.1% 升至 4.8%，反映近年新案集中在超高層；內湖區（1.7% 至 0.5%）、文山區（5.3% 至 2.8%）與信義區（3.1% 至 1.1%）則下降。")
    R.figure(doc, "圖2_各區11層以上占比.png", "圖 2　各行政區 11 層以上成交占比的年度變化（灰虛線為全市）")
    R.figure(doc, "圖3_各區總樓層帶年度.png", "圖 3　各行政區總樓層帶占比的年度變化")

    R.heading(doc, "肆、建物型態（110 年起）", 1)
    P("全市住宅大樓占比由 110 年的 47.7% 降至 113 年的 39.8%，114 年為 40.3%；公寓則由 24.5% 升至 30% 至 31%，華廈穩定在 26% 上下，透天厝僅 2% 至 3%。型態與樓層的變化方向一致：成交重心由高樓住宅大樓回移至公寓。")
    P("以 110 至 114 年合計觀察，住宅大樓占比最高者為中山區（52.8%）、大同區（51.7%）與中正區（49.8%），最低者為士林區（27.6%）、北投區（33.0%）與內湖區（35.4%）。公寓占比以士林區最高（43.0%），其次為信義區（36.1%）與文山區（34.1%）。大同區（6.7%）與萬華區（4.9%）的透天厝占比明顯高於其他行政區。")
    R.figure(doc, "圖4_建物型態.png", "圖 4　臺北市房地買賣的建物型態（左：全市年度；右：各行政區 110 至 114 年合計）")

    R.heading(doc, "伍、綜合觀察與限制", 1)
    P("綜合而言，臺北市房地買賣的成交結構在 109 年之後由高樓層、住宅大樓逐步回移至低樓層、公寓，各行政區多數同步下降，僅南港區的超高層成交占比逆勢上升。")
    P("本分析有下列限制：（一）樓層與型態反映的是成交的建物，中古屋流通量大的區域公寓占比會被墊高，不等於新增供給；（二）不含預售屋，故新建案的影響僅限於已完成交屋後的成屋交易；（三）建物型態分類在 109 與 110 年間改變，故型態僅呈現 110 年起；（四）114 年資料未滿全年，且登記較晚的案件可能尚未入庫；（五）未排除特殊交易；各行政區部分年度樣本數較少，單年數字宜保守解讀。")
    out = D / "臺北市樓層與型態_分析報告.docx"
    doc.save(out); print(out)


if __name__ == "__main__":
    main()
