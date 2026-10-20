"""臺北市有容積率之使用分區的公私有土地比例（以使用分區為主體）報告書式說明 .docx；正文數字全部取自表，隨資料重產。

三種範圍（環境變數）：預設＝全部有容積率分區；NO_PF=1＝不計入公共設施用地（學校用地、機關與公用設施用地）；RC_ONLY=1＝只含住宅區與商業區。
輸入：各範圍資料夾內 使用分區表.xlsx、容積率級距.json、圖1_各使用分區公私有面積比例.png
  （analyze_臺北市_容積率分區_公私有土地.py → build_容積率分區公私有_使用分區表.py）
輸出：同資料夾 臺北市容積率分區_公私有土地_分析報告[_不含公設|_住宅商業區].docx
公有面積＝公有土地圖層地號與分區的交集面積；公私共有地號只計公有持分（1－OWN_PER1 私有持分）。
執行：python scripts/build_容積率分區公私有_報告.py（NO_PF=1／RC_ONLY=1 同）
"""
import importlib.util
import json
import os
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
_s = importlib.util.spec_from_file_location("rep", ROOT / "scripts" / "build_臺北市_行政區三表報告.py")
R = importlib.util.module_from_spec(_s)
_s.loader.exec_module(R)
NO_PF = os.environ.get("NO_PF") == "1"
RC_ONLY = os.environ.get("RC_ONLY") == "1"
SUB = "容積率分區公私有土地_住宅商業區" if RC_ONLY else "容積率分區公私有土地_不含公設" if NO_PF else "容積率分區公私有土地"
D = ROOT / "案件" / "臺北市_不動產交易分析" / SUB
R.D = D
GROUPS = ["住宅區", "商業區"] if RC_ONLY else ["住宅區", "商業區", "工業區", "專用區與其他"] if NO_PF else ["住宅區", "商業區", "工業區", "學校用地", "機關與公用設施用地", "專用區與其他"]
SUFFIX = "（只含住宅區與商業區）" if RC_ONLY else "（不含公共設施用地）" if NO_PF else ""
FILE = "臺北市容積率分區_公私有土地_分析報告" + ("_住宅商業區" if RC_ONLY else "_不含公設" if NO_PF else "") + ".docx"
COLS = ["使用分區", "種數／法定容積率(%)", "分區面積(公頃)", "占全市有容積率面積%", "公有面積(公頃)", "私有面積(公頃)", "公有面積占比%", "私有面積占比%", "地號數", "含公有持分地號數", "含公有持分地號占比%"]


def main():
    t = pd.read_excel(D / "使用分區表.xlsx", header=1)
    t.columns = COLS
    t = t[t["使用分區"].notna() & t["分區面積(公頃)"].notna()].reset_index(drop=True)
    tot = t.iloc[0]
    blocks, cur, seen = {}, None, set()
    for i in range(1, len(t)):
        n = str(t.loc[i, "使用分區"])
        if n in GROUPS and n not in seen:
            seen.add(n)
            cur = n
            blocks[cur] = {"row": t.loc[i], "subs": []}
        else:
            blocks[cur]["subs"].append(t.loc[i])
    far = json.load(open(D / "容積率級距.json", encoding="utf-8"))
    TA, TP = float(tot["分區面積(公頃)"]), float(tot["公有面積(公頃)"])

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
    tp = doc.add_paragraph(style="Title")
    tp.alignment = WD_ALIGN_PARAGRAPH.LEFT
    tp.add_run("臺北市有容積率之使用分區的公有與私有土地比例" + SUFFIX)
    sp = doc.add_paragraph()
    R.set_font(sp.add_run("全市地籍圖與使用分區交集分析"), R.HEAD, 12, color=RGBColor(0x55, 0x55, 0x55))
    sp.paragraph_format.space_after = Pt(14)
    P = lambda s: R.para(doc, s)

    R.heading(doc, "壹、前言與資料說明", 1)
    scope = ("本版只統計住宅區與商業區兩類使用分區。" if RC_ONLY else
             "本版不計入公共設施用地（學校用地、機關用地、公墓與各類公用設施用地），僅就住宅區、商業區、工業區及專用區等分區進行分析，以免公共設施用地的高公有比例拉高整體數字。" if NO_PF else
             "本文涵蓋全部有法定容積率的使用分區，含學校、機關等公共設施用地。")
    P("本文以使用分區為主體，說明臺北市有法定容積率的使用分區內，公有土地與私有土地所占的比例，作為評估各類分區土地取得難易與開發條件的參考。" + scope)
    P(f"分析方法為：以都發局地籍圖（421,843 個地號）與有法定容積率的使用分區塊求交集，依交集面積累計；地號在地政局公有土地圖層內者計入公有，其中公私共有的地號只計公有持分（圖層記載之私有持分以外的部分）的面積，其餘為私有。納入的使用分區共 {int(tot['種數／法定容積率(%)'])} 種，面積 {TA:,.0f} 公頃，歸為" + "、".join(GROUPS) + f"共 {len(GROUPS)} 大類。私有面積為分區面積扣除公有面積，包含無地號的道路與水域。")

    R.heading(doc, "貳、全市概況", 1)
    P(f"{('只含住宅區與商業區' if RC_ONLY else '不計入公共設施用地後' if NO_PF else '')}全市有容積率的使用分區共 {TA:,.0f} 公頃，其中公有 {TP:,.0f} 公頃，占 {tot['公有面積占比%']:.1f}%，私有 {tot['私有面積(公頃)']:,.0f} 公頃，占 {tot['私有面積占比%']:.1f}%。以地號數計，這些分區內共有 {int(tot['地號數']):,} 個地號，含公有持分的地號 {int(tot['含公有持分地號數']):,} 個，占 {tot['含公有持分地號占比%']:.1f}%。" +
      ("含公有持分地號數是計入公私共有地號的，因此地號占比不等於面積占比。" if not RC_ONLY else ""))
    R.figure(doc, "圖1_各使用分區公私有面積比例.png", "圖 1　臺北市有容積率之使用分區" + SUFFIX + "：公有與私有土地面積比例", 15)

    R.heading(doc, "參、各類使用分區", 1)
    cn = "一二三四五六"
    for k, gname in enumerate(GROUPS):
        b = blocks[gname]
        r = b["row"]
        subs = [s for s in b["subs"] if not str(s["使用分區"]).startswith("其他")]
        top3 = sorted(subs, key=lambda s: -s["分區面積(公頃)"])[:3]
        R.heading(doc, f"{cn[k]}、{gname}", 2)
        txt = f"{gname}面積 {r['分區面積(公頃)']:,.0f} 公頃，占 {r['占全市有容積率面積%']:.1f}%，公有 {r['公有面積(公頃)']:,.0f} 公頃，占 {r['公有面積占比%']:.1f}%，私有占 {r['私有面積占比%']:.1f}%；地號數 {int(r['地號數']):,} 個，含公有持分者占 {r['含公有持分地號占比%']:.1f}%。"
        if top3:
            txt += "面積較大的分區為" + "、".join(f"{s['使用分區']}（{s['分區面積(公頃)']:,.0f} 公頃，公有 {s['公有面積占比%']:.1f}%）" for s in top3) + "。"
        if len(subs) >= 2:
            hi = max(subs, key=lambda s: s["公有面積占比%"])
            lo = min(subs, key=lambda s: s["公有面積占比%"])
            txt += f"各分區中公有占比最高者為{hi['使用分區']}（{hi['公有面積占比%']:.1f}%，{hi['分區面積(公頃)']:,.0f} 公頃），最低者為{lo['使用分區']}（{lo['公有面積占比%']:.1f}%，{lo['分區面積(公頃)']:,.0f} 公頃）。"
        P(txt)

    p = doc.add_paragraph()
    p.paragraph_format.keep_with_next = True
    R.set_font(p.add_run("表 1　有容積率之使用分區" + SUFFIX + "的公有與私有土地比例（面積：公頃）"), R.HEAD, 10.5, bold=True)
    heads = ["使用分區", "分區面積", "占全市%", "公有面積", "公有占比%", "私有占比%", "地號數", "含公有持分地號占比%"]
    cols = ["使用分區", "分區面積(公頃)", "占全市有容積率面積%", "公有面積(公頃)", "公有面積占比%", "私有面積占比%", "地號數", "含公有持分地號占比%"]
    tb = doc.add_table(rows=1, cols=len(heads))
    tb.style = "Table Grid"
    tb.alignment = WD_TABLE_ALIGNMENT.CENTER
    for c, h in zip(tb.rows[0].cells, heads):
        c.text = ""
        r_ = c.paragraphs[0].add_run(h)
        R.set_font(r_, R.HEAD, 9, bold=True)
        c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        R.shade(c, "E8EDF4")
    big = {str(tot["使用分區"])} | set(GROUPS)
    seen2 = set()
    for _, row in t[cols].iterrows():
        name = str(row["使用分區"])
        is_group = name in big and name not in seen2
        if is_group:
            seen2.add(name)
        cells = tb.add_row().cells
        for j, (c, v) in enumerate(zip(cells, row.tolist())):
            c.text = ""
            txt = str(v) if j == 0 else (f"{v:,.0f}" if j in (1, 3, 6) else f"{v:.1f}") if pd.notna(v) else ""
            r_ = c.paragraphs[0].add_run(("　" if (j == 0 and not is_group) else "") + txt)
            R.set_font(r_, R.HEAD, 9, bold=is_group)
            c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.LEFT if j == 0 else WD_ALIGN_PARAGRAPH.RIGHT
            if is_group:
                R.shade(c, "F2F2F2")
    n_ = doc.add_paragraph()
    n_.paragraph_format.space_after = Pt(10)
    R.set_font(n_.add_run(f"註：各大類下列出面積 50 公頃以上的使用分區，其餘併入「其他」，完整 {int(tot['種數／法定容積率(%)'])} 種見總表。"), R.HEAD, 9, color=RGBColor(0x55, 0x55, 0x55))

    R.heading(doc, "肆、依法定容積率級距與公有土地的構成", 1)
    order = ["100% 以下", "101～200%", "201～300%", "301～400%", "401～600%", "600% 以上"]
    fr = [(k, far[k]) for k in order if k in far]
    big_f = max(fr, key=lambda x: x[1]["area_ha"])
    P("依法定容積率級距觀察，" + "；".join(f"{k}（{v['area_ha']:,.0f} 公頃）公有占 {v['pub_pct']:.1f}%" for k, v in fr) + f"。其中面積最大的是 {big_f[0]} 一級。公有占比並不隨容積率單調變化。")
    comp = sorted(((g_, float(blocks[g_]["row"]["公有面積(公頃)"])) for g_ in GROUPS), key=lambda x: -x[1])
    P(f"{TP:,.0f} 公頃的公有土地中，" + "，".join(f"{g_}占 {v / TP * 100:.1f}%（{v:,.0f} 公頃）" for g_, v in comp) + "。")
    P("本分析有下列限制：（一）公私共有地號只計公有持分，持分資料取自地政局公有土地圖層，若圖層持分欄位缺漏（少數地號為空值）則視為全部公有；（二）有容積率僅指分區塊法定容積率大於零，保護區、農業區、河川區等無容積率者不在範圍內" + ("，並已排除學校用地、機關用地、公墓與各類公用設施用地" if NO_PF else "，且本版只含住宅區與商業區" if RC_ONLY else "") + "；（三）面積以地號面與分區塊交集計，分區邊界與地籍邊界不完全吻合時會有微小誤差；（四）私有面積含無地號的道路與水域，並非全為私人所有的地號；（五）使用分區的歸類依分區名稱比對，少數混合性質的分區（如住商混合區、特定商業區）歸入專用區與其他。")
    out = D / FILE
    doc.save(out)
    print(out)


if __name__ == "__main__":
    main()
