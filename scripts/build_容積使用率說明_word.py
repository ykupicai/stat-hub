"""各行政區與全市容積使用率說明（Word，報告書式文字，無表格）。
數字來源：分區容積使用/去重版/行政區_容積使用狀況_去重.xlsx（去重後 sumdd08、依使照比例回推地上）、法定容積率圖層（面積加權法定容積率、有值面積占比）。
輸出：分區容積使用/臺北市各行政區容積使用率說明.docx
執行：python scripts/build_容積使用率說明_word.py
"""
import importlib.util
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("rpt", ROOT / "scripts" / "build_臺北市_行政區三表報告.py")
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
BASE = ROOT / "案件" / "臺北市_不動產交易分析" / "分區容積使用"
ZONE = ROOT.parent / "地籍成果" / "台北市開發強度" / "台北市分區法定總樓地板_開發強度_v2_data.taipei.gpkg"


def main():
    T = pd.read_excel(BASE / "去重版" / "行政區_容積使用狀況_去重.xlsx", header=1)
    T = T[T["行政區"].notna() & ~T["行政區"].astype(str).str.startswith("註")].copy()
    T["行政區"] = T["行政區"].astype(str).str.strip()
    c_old = [c for c in T.columns if c.startswith("使用率%（sumdd08 去重前")][0]
    c_new = [c for c in T.columns if c.startswith("使用率%（sumdd08 去重後")][0]
    c_up = [c for c in T.columns if c.startswith("使用率%（去重後推算地上")][0]
    c_leg, c_now, c_upfa = "法定總樓地板_萬㎡", "sumdd08去重後_萬㎡", "推算地上樓地板_萬㎡"
    c_over = [c for c in T.columns if "超過100%" in c][0]
    g = gpd.read_file(ZONE, layer="分區法定總樓地板")
    ok = g["容積率"].notna() & (g["容積率"] > 0)
    far = g[ok].groupby("行政區_判定").apply(lambda d: np.average(d["容積率"], weights=d["面積_m2"]))
    cover = g[ok].groupby("行政區_判定")["面積_m2"].sum() / g.groupby("行政區_判定")["面積_m2"].sum() * 100
    far_rank = far.rank(ascending=False).astype(int)
    D = T[T["行政區"] != "全市"].sort_values(c_up, ascending=False).reset_index(drop=True)
    A = T[T["行政區"] == "全市"].iloc[0]

    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.left_margin = sec.right_margin = sec.top_margin = sec.bottom_margin = Cm(2.5)
    R.style_font(doc.styles["Normal"], R.BODY, 12)
    R.style_font(doc.styles["Title"], R.HEAD, 22, True, RGBColor(0x1F, 0x2A, 0x44))
    R.style_font(doc.styles["Heading 1"], R.HEAD, 16, True, RGBColor(0x1F, 0x2A, 0x44))
    R.style_font(doc.styles["Heading 2"], R.HEAD, 13, True, RGBColor(0x1F, 0x2A, 0x44))
    for s_ in ("Heading 1", "Heading 2"):
        doc.styles[s_].paragraph_format.space_before = Pt(14)
        doc.styles[s_].paragraph_format.space_after = Pt(6)
        doc.styles[s_].paragraph_format.keep_with_next = True
    R.add_page_number(sec)
    tp = doc.add_paragraph(style="Title"); tp.alignment = WD_ALIGN_PARAGRAPH.LEFT
    tp.add_run("臺北市各行政區分區容積使用率說明")
    sp = doc.add_paragraph()
    R.set_font(sp.add_run("依去重後 sumdd08 與使用執照比例推算之地上樓地板，對照法定總樓地板"), R.HEAD, 12, color=RGBColor(0x55, 0x55, 0x55))
    sp.paragraph_format.space_after = Pt(12)

    R.heading(doc, "壹、分析口徑", 1)
    R.para(doc, "容積使用率＝現況樓地板 ÷ 法定總樓地板。法定總樓地板為各分區面積乘以法定容積率（取自臺北市都市發展局土地使用內容與使用管制彙整表，民國 115 年 4 月 9 日更新，為容積率上限，不含獎勵），只計有法定容積率的分區塊，共 12,235 塊。現況樓地板取自地政局建物屋齡統計圖層的 sumdd08（地號上建物的樓地板合計，含地下室、停車空間與附屬面積）。")
    R.para(doc, "sumdd08 有兩個問題，本分析已先行處理。其一，同一棟建物跨多個地號時，各地號都重複記載同一個樓地板，故將相鄰且樓地板、建物數、層數、屋齡皆相同的地號視為同一棟，樓地板只計一次並依地號面積分配，全市 sumdd08 因此由 3.36 億平方公尺降為 2.26 億平方公尺。其二，sumdd08 含地下層與附屬面積，與只計地上的法定容積不同，故以使用執照的地上樓地板為基準，依地上層數與屋齡帶推算兩者比例（全體中位數 0.76），回推地上樓地板。下文以「推算地上使用率」為主要數字，並列去重後 sumdd08 與去重前的結果供對照。")

    R.heading(doc, "貳、全市整體情形", 1)
    R.para(doc, f"全市有法定容積率的分區塊，法定總樓地板合計約 {A[c_leg] / 1e4:.2f} 億平方公尺；去重後 sumdd08 現況總樓地板約 {A[c_now] / 1e4:.2f} 億平方公尺，使用率 {A[c_new]:.1f}%（去重前為 {A[c_old]:.1f}%）；回推只計地上後，現況樓地板約 {A[c_upfa] / 1e4:.2f} 億平方公尺，使用率 {A[c_up]:.1f}%。換言之，以最接近法定口徑的推算地上樓地板計算，全市整體的容積使用率約為九成，有 {A[c_over]:.0f}% 的分區塊使用率已超過 100%。")
    R.para(doc, "空間上，使用率較高的分區塊集中在盆地中央與西側的舊市區，以及信義區東側的商業與特定業務區；山邊的士林、北投、文山與南港外圍使用率較低，且大面積的山坡地、保護區、公園、河川等因沒有法定容積率，不在統計範圍內。各行政區使用率差異明顯：松山區、中山區、大安區與內湖區已超過 100%，信義區約為 100%，中正區接近，其餘行政區在 64% 至 78% 之間。")
    img = BASE / "去重版" / "圖_分區塊容積使用率_去重.png"
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(img), width=Cm(12.5))
    c = doc.add_paragraph(); c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    R.set_font(c.add_run("圖 1　臺北市分區塊容積使用率（去重後推算地上樓地板 ÷ 法定總樓地板）"), R.HEAD, 10, color=RGBColor(0x55, 0x55, 0x55))

    R.heading(doc, "參、各行政區說明", 1)
    R.para(doc, "各行政區依推算地上使用率由高至低排列。「法定平均容積率」為以分區面積加權、僅計有容積率的分區之平均值，反映該區法定強度；兩者並列可看出法定強度與現況使用的落差。")
    for i, r in D.iterrows():
        d = r["行政區"]
        up, new, old = r[c_up], r[c_new], r[c_old]
        level = ("屬全市使用最密集的行政區，現況樓地板平均已明顯超過法定總樓地板" if up >= 130 else
                 "現況樓地板略高於法定總樓地板" if up >= 105 else
                 "約與法定總樓地板相當" if up >= 95 else
                 "低於法定總樓地板，尚有相當的容積空間" if up >= 70 else
                 "明顯低於法定總樓地板，現況使用遠未達法定上限")
        f, fr = far[d], int(far_rank[d])
        tier = "偏高" if fr <= 4 else "居中" if fr <= 8 else "偏低"
        if up >= 105:
            tail = {"偏高": "現況使用也已超過法定總樓地板，顯示開發相當密集", "居中": "現況使用率卻已超過法定總樓地板", "偏低": "現況使用率卻已超過法定總樓地板，顯示建成區開發相當密集"}[tier]
        elif up >= 95:
            tail = "現況使用約達法定上限"
        else:
            tail = {"偏高": "但現況使用率偏低，可再開發的容積空間較多", "居中": "現況使用率低於法定總樓地板", "偏低": "現況使用率也偏低"}[tier]
        legal = f"該區法定平均容積率約 {f:.0f}%，居 12 區第 {fr}，法定強度{tier}，{tail}。"
        extra = ""
        if cover[d] < 40:
            extra = f"需留意，該區有法定容積率的土地僅占全區的 {cover[d]:.0f}%，其餘多為山坡地、保護區與公園等無法定值的土地，統計只反映平地建成區。"
        txt = (f"{d}的推算地上使用率為 {up:.0f}%，居 12 區第 {i + 1}，{level}；以去重後 sumdd08 直接計算為 {new:.0f}%，去重前為 {old:.0f}%。"
               f"該區有法定容積率的分區塊 {int(r['有法定值分區塊']):,} 塊，法定總樓地板約 {r[c_leg]:,.0f} 萬平方公尺，推算現況地上樓地板約 {r[c_upfa]:,.0f} 萬平方公尺，"
               f"其中使用率超過 100% 的分區塊占 {r[c_over]:.0f}%。{legal}{extra}")
        R.heading(doc, f"{d}", 2)
        R.para(doc, txt)

    R.heading(doc, "肆、解讀限制", 1)
    R.para(doc, "（一）法定容積為容積率上限，不含容積獎勵、移轉與舊制放寬，現況高於法定總樓地板不必然代表違規；（二）地上樓地板比例是依單一使用執照新建地號的樣本推算，多棟、增建或較複雜的建物未納入校準；（三）同棟判定以相鄰且屬性相同為準，約有 8% 的去重量缺乏「地號放不下該樓地板」的佐證，可能把相鄰的相同透天厝誤併，使對應地區的使用率略為低估；（四）地號與分區塊邊界不完全吻合，樓地板依交集面積分配，個別分區塊誤差較大，行政區彙總相對穩定；（五）法定總樓地板只涵蓋約三成土地，落在無法定值分區的現況建物不計入。因此本說明適合比較各行政區相對高低，絕對數字宜保守解讀。")
    out = BASE / "臺北市各行政區容積使用率說明.docx"
    doc.save(out)
    print(out)


if __name__ == "__main__":
    main()
