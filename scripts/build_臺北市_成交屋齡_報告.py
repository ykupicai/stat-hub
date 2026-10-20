"""臺北市各行政區成交時屋齡（105～114 年）報告書式說明 .docx。

輸入：行政區三表_105至114/表5a、表5c、表5d 與 圖T5；行政區屋齡/成交時屋齡/圖_成交時屋齡中位數.png
輸出：同資料夾 臺北市成交屋齡_分析報告.docx
正文數字取自上述表。執行：python scripts/build_臺北市_成交屋齡_報告.py
"""
import importlib.util
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
_s = importlib.util.spec_from_file_location("rep", ROOT / "scripts" / "build_臺北市_行政區三表報告.py")
R = importlib.util.module_from_spec(_s); _s.loader.exec_module(R)
D = ROOT / "案件" / "臺北市_不動產交易分析" / "行政區三表_105至114"
R.D = D
AGE = ROOT / "案件" / "臺北市_不動產交易分析" / "行政區屋齡" / "成交時屋齡"
DIST = R.DIST


def main():
    c = pd.read_csv(D / "表5c_行政區×成交時屋齡_占比%（僅有屋齡者）.csv", index_col=0, encoding="utf-8-sig").drop(index="合計", errors="ignore")
    s = pd.read_csv(D / "表5d_行政區成交時屋齡摘要.csv", index_col=0, encoding="utf-8-sig")
    tb = c.T.loc[DIST + ["全市"]].copy()
    tb["31年以上合計"] = tb[["31-45年", "46年以上"]].sum(axis=1)
    tb["屋齡中位數(年)"] = s.loc["屋齡中位數"].reindex(tb.index)
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.left_margin = sec.right_margin = sec.top_margin = sec.bottom_margin = Cm(2.5)
    R.style_font(doc.styles["Normal"], R.BODY, 12)
    R.style_font(doc.styles["Title"], R.HEAD, 22, True, RGBColor(0x1F, 0x2A, 0x44))
    R.style_font(doc.styles["Heading 1"], R.HEAD, 16, True, RGBColor(0x1F, 0x2A, 0x44))
    R.style_font(doc.styles["Heading 2"], R.HEAD, 13, True, RGBColor(0x1F, 0x2A, 0x44))
    for st in ("Heading 1", "Heading 2"):
        doc.styles[st].paragraph_format.space_before = Pt(14)
        doc.styles[st].paragraph_format.space_after = Pt(6)
        doc.styles[st].paragraph_format.keep_with_next = True
    R.add_page_number(sec)
    tp = doc.add_paragraph(style="Title"); tp.alignment = WD_ALIGN_PARAGRAPH.LEFT
    tp.add_run("臺北市各行政區不動產買賣之成交時屋齡分析")
    sp = doc.add_paragraph()
    R.set_font(sp.add_run("實價登錄資料，交易日民國 105 年至 114 年"), R.HEAD, 12, color=RGBColor(0x55, 0x55, 0x55))
    sp.paragraph_format.space_after = Pt(14)
    P = lambda t: R.para(doc, t)

    R.heading(doc, "壹、前言與資料說明", 1)
    P("本文以內政部不動產交易實價查詢服務網之開放資料為基礎，統計臺北市 12 個行政區於民國 105 年至 114 年間不動產買賣交易的成交時屋齡，觀察各行政區成交的建物以新屋、中古屋或老屋為主，作為了解區域建物更新壓力與交易偏好的參考。")
    P("成交時屋齡為交易年減建築完成年。全部買賣交易 236,198 筆中，可算出屋齡者 168,611 筆（71.4%），其餘為純土地或純車位 36,225 筆（15.3%）、建築完成年月空白 14,450 筆（6.1%），以及建築完成年晚於交易年 16,912 筆（7.2%，多為預售或尚未完成登記的交易），這些均未納入屋齡占比。屋齡帶分為 0 至 5 年、6 至 15 年、16 至 30 年、31 至 45 年與 46 年以上；另以 20 年以下、21 至 30 年、31 年以上三級距輔助說明。屋齡為成交當年的屋齡，並非現況屋齡，亦不是各區建物存量的屋齡結構。")

    R.heading(doc, "貳、全市概況", 1)
    P("全市成交屋齡中位數為 29 年，四分位距為 11 至 40 年，即一半的交易集中在屋齡 11 至 40 年之間。以屋齡帶計，31 至 45 年的建物占 36.0%，為最大宗；16 至 30 年占 19.6%，6 至 15 年占 16.8%，0 至 5 年占 15.3%，46 年以上占 12.3%。31 年以上合計 48.3%，亦即全市近半數的成交建物已逾 30 年；20 年以下占 38.4%，21 至 30 年占 13.3%。")

    R.heading(doc, "參、各行政區差異", 1)
    R.heading(doc, "一、老屋為主的行政區", 2)
    P("士林區、大安區與松山區的成交屋齡最高。士林區屋齡中位數 37 年，31 年以上占 64.4%，46 年以上亦占 19.3%；大安區與松山區中位數均為 35 年，31 年以上分別占 62.5% 與 62.4%，且 0 至 5 年的新屋占比最低，松山區僅 7.2%，大安區 11.1%。信義區（中位數 32 年，31 年以上占 53.7%）、萬華區（32 年，52.3%）與中山區（31 年，50.7%）居次，其中萬華區 46 年以上占 18.1%，為僅次於士林區者。")
    R.heading(doc, "二、屋齡較新的行政區", 2)
    P("南港區是成交屋齡最新的行政區，中位數僅 15 年，20 年以下占 58.0%，6 至 15 年即占 33.9%，31 年以上僅 28.9%。內湖區（中位數 22 年）與文山區（23 年）次之，31 年以上占比分別為 33.5% 與 32.4%；內湖區 46 年以上僅 1.8%，為全市最低。內湖區與文山區以 16 至 30 年的建物居多（分別占 28.4% 與 31.5%）。")
    R.heading(doc, "三、兩端並存的行政區", 2)
    P("中正區、大同區與北投區的屋齡中位數分別為 24 年、28 年與 27 年，低於全市，但新屋與老屋並存：0 至 5 年新屋占比分別為 22.2%、23.6% 與 21.4%，同時 31 年以上也占 43.2%、46.1% 與 46.6%。萬華區亦有類似情形，0 至 5 年占 23.5%，46 年以上占 18.1%。這類行政區的交易呈現新建案與老屋並行，中間屋齡帶（16 至 30 年）占比相對偏低，在 10.8% 至 16.4% 之間（萬華區最低），顯示成交集中在近年新屋與較老的建物兩端。")
    R.figure(doc, "圖T5_成交時屋齡帶_堆疊橫條.png", "圖 1　臺北市各行政區成交時屋齡帶占比（僅計有屋齡者，依 31-45 年占比排序）")

    p = doc.add_paragraph(); p.paragraph_format.keep_with_next = True
    R.set_font(p.add_run("表 1　各行政區成交時屋齡帶占比與屋齡中位數（%，年）"), R.HEAD, 10.5, bold=True)
    cols = list(tb.columns)
    t = doc.add_table(rows=1, cols=len(cols) + 1); t.style = "Table Grid"
    for cell, h in zip(t.rows[0].cells, ["行政區"] + cols):
        cell.text = ""; r = cell.paragraphs[0].add_run(h); R.set_font(r, R.HEAD, 9, bold=True)
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER; R.shade(cell, "E8EDF4")
    for name, row in tb.iterrows():
        cells = t.add_row().cells
        cells[0].text = ""; R.set_font(cells[0].paragraphs[0].add_run(name), R.HEAD, 9, bold=(name == "全市"))
        for cell, v in zip(cells[1:], row):
            cell.text = ""; r = cell.paragraphs[0].add_run(f"{v:.0f}" if cell is cells[-1] else f"{v:.1f}")
            R.set_font(r, R.HEAD, 9, bold=(name == "全市")); cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
        if name == "全市":
            for cell in cells:
                R.shade(cell, "F4F6F9")
    n = doc.add_paragraph(); n.paragraph_format.space_after = Pt(10)
    R.set_font(n.add_run("註：僅計有建物且屋齡可算出者（168,611 筆）；31年以上合計＝31-45年與46年以上之和。"), R.HEAD, 9, color=RGBColor(0x55, 0x55, 0x55))

    R.heading(doc, "肆、綜合觀察與限制", 1)
    P("綜合而言，臺北市成交屋齡的空間分布呈現明顯的區域差異：士林、大安、松山以老屋為主，南港、內湖、文山則以較新的建物為主，中正、大同、北投與萬華則是新屋與老屋並存。全市近半數成交建物逾 30 年，顯示老屋更新需求長期存在。需說明的是，以上為組成比例的描述，彼此相關但未做因果檢定。")
    P("本分析有下列限制：（一）屋齡為成交當年屋齡，反映的是被交易的建物，並非各區建物存量的屋齡結構；（二）不含預售屋，且建築完成年空白或晚於交易年者不計入，故新屋占比可能被低估；（三）未排除特殊交易，亦不區分交易標的；（四）各表為 105 至 114 年累計，未分年度，無法呈現趨勢；（五）屋齡以年計算，未以月份精確換算，故 0 至 5 年等分級邊界附近可能有 1 年的誤差。")
    out = D.parent / "105至114_成果整理" / "臺北市成交屋齡_分析報告.docx"
    doc.save(out); print(out)


if __name__ == "__main__":
    main()
