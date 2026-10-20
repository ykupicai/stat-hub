"""臺北市分區容積使用狀況分析過程簡報（PowerPoint，圖表為原生可編輯圖表）。

內容：資料來源 → 分析流程 → 四種口徑比較 → 問題一（sumdd08 含地下與附屬）→ 問題二（跨地號重複）→ 各行政區結果 → 分區塊地圖 → 限制。
輸入：分區容積使用/去重版/行政區_容積使用狀況_去重.xlsx 與地圖 PNG；數字取自各版本分析輸出。
輸出：案件/臺北市_不動產交易分析/分區容積使用/臺北市分區容積使用_分析過程.pptx
執行：python scripts/build_容積使用分析流程簡報.py
"""
import importlib.util
import sys
from pathlib import Path

import pandas as pd
from PIL import Image
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
sys.argv = [sys.argv[0]]
spec = importlib.util.spec_from_file_location("deck", ROOT / "scripts" / "build_臺北市_行政區三表簡報.py")
K = importlib.util.module_from_spec(spec)
spec.loader.exec_module(K)
BASE = ROOT / "案件" / "臺北市_不動產交易分析" / "分區容積使用"
FONT, NAVY, INK, MUTED, TINT = K.FONT, K.NAVY, K.INK, K.MUTED, K.TINT
SRC = "資料：臺北市都發局土地使用內容與使用管制彙整表（115/4/9 更新）、地政局 BuildStat_Fage、臺北市歷年使用執照摘要、建築資訊e點通建物套繪圖"


def rgb(h):
    return RGBColor.from_string(h)


def card(s, x, y, w, h, title, body, size=13):
    box = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    box.fill.solid(); box.fill.fore_color.rgb = TINT; box.line.fill.background(); box.shadow.inherit = False; box.name = "卡片：" + title[:8]
    K.textbox(s, x + 0.2, y + 0.15, w - 0.4, 0.45, [title], size=17, color=NAVY, bold=True, space_after=0, name="卡片標題")
    K.textbox(s, x + 0.2, y + 0.7, w - 0.4, h - 0.8, body, size=size, bullets=True, space_after=5, name="卡片內文")


def style_chart(ch, title, legend=True, vmax=None, fmt='0"%"'):
    ch.font.name, ch.font.size = FONT, Pt(10)
    ch.has_title = True
    ch.chart_title.text_frame.text = title
    for r in ch.chart_title.text_frame.paragraphs[0].runs:
        r.font.size, r.font.bold, r.font.name = Pt(12), True, FONT
        r.font.color.rgb = NAVY
    ch.has_legend = legend
    if legend:
        ch.legend.position = XL_LEGEND_POSITION.BOTTOM; ch.legend.include_in_layout = False
    va = ch.value_axis
    va.has_major_gridlines = False
    va.minimum_scale = 0
    if vmax:
        va.maximum_scale = vmax
    va.tick_labels.number_format, va.tick_labels.number_format_is_linked = fmt, False
    va.tick_labels.font.size = Pt(10)
    ch.category_axis.tick_labels.font.size = Pt(11)


def main():
    T = pd.read_excel(BASE / "去重版" / "行政區_容積使用狀況_去重.xlsx", header=1)
    T = T[T["行政區"].notna() & ~T["行政區"].astype(str).str.startswith("註")].copy()
    T["行政區"] = T["行政區"].astype(str).str.strip()
    c_old, c_new, c_up = [c for c in T.columns if c.startswith("使用率%（sumdd08 去重前")][0], [c for c in T.columns if c.startswith("使用率%（sumdd08 去重後")][0], [c for c in T.columns if "去重後推算地上" in c and c.startswith("使用率")][0]
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)

    # 1 封面
    s = prs.slides.add_slide(prs.slide_layouts[6]); K.add_bg(s, NAVY)
    K.textbox(s, 0.8, 2.2, 11.7, 1.8, ["臺北市分區容積使用狀況", "分析過程與方法"], size=40, color=RGBColor(255, 255, 255), bold=True, space_after=4, name="封面標題")
    K.textbox(s, 0.8, 4.3, 11.7, 0.9, ["如何用現況樓地板與法定容積率，推算各行政區容積使用率"], size=20, color=RGBColor(0xCA, 0xDC, 0xFC), name="封面副標")
    K.textbox(s, 0.8, 6.6, 11.7, 0.4, ["試作成果，數字僅供比較各區相對高低"], size=12, color=RGBColor(0xCA, 0xDC, 0xFC), name="封面註")

    # 2 資料來源
    s = K.title_only(prs, "四份圖資：一份法定強度，三種現況樓地板", source=SRC)
    card(s, 0.5, 1.5, 6.0, 2.55, "法定容積率圖層（分母）", ["15,511 個都市計畫分區塊，其中 12,235 塊有法定容積率", "法定總樓地板＝分區面積×容積率，合計約 1.74 億㎡", "容積率取自都發局彙整表（115 年 4 月 9 日更新），為容積率上限，不含獎勵"])
    card(s, 6.85, 1.5, 6.0, 2.55, "sumdd08（現況總樓地板）", ["地政局 BuildStat_Fage，152,684 個地號，每地號一個樓地板合計", "涵蓋所有現況建物，含地下室、停車空間、陽台、公設", "同一棟跨多個地號時各地號重複記載"])
    card(s, 0.5, 4.25, 6.0, 2.55, "使用執照摘要（口徑校準）", ["臺北市歷年使用執照摘要：8,762 張（民國 90～114 年）", "另加較早的使用執照 XML（至民國 105 年 10 月）", "有各樓層面積，可分出地上、地下、突出物"])
    card(s, 6.85, 4.25, 6.0, 2.55, "建物套繪圖（另一種現況樓地板）", ["建築資訊e點通，299,651 塊，其中建物 90,447 塊", "約 4.95 萬塊建物帶使照樓地板（民國 45～115 年）", "與使照比對約為地上樓地板的 1.44 倍，推測含地下層"])

    # 3 流程
    s = K.title_only(prs, "分析流程：五個步驟", source=SRC)
    steps = [("① 圖層準備", "法定容積率分區塊\n＋現況樓地板的來源圖層"), ("② 空間交集", "建物（或地號）面與\n分區塊交集"), ("③ 面積分配", "樓地板依交集面積比例\n分配到各分區塊"),
             ("④ 口徑校正", "去除重複記載，\n回推只計地上的樓地板"), ("⑤ 使用率", "分配後樓地板÷法定總樓地板\n彙整到行政區")]
    x0, w, gap = 0.5, 2.2, 0.32
    for i, (t, d) in enumerate(steps):
        x = x0 + i * (w + gap)
        b = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(2.3), Inches(w), Inches(2.3))
        b.fill.solid(); b.fill.fore_color.rgb = NAVY if i in (3,) else TINT; b.line.fill.background(); b.shadow.inherit = False; b.name = f"步驟{i + 1}"
        dark = i == 3
        K.textbox(s, x + 0.1, 2.45, w - 0.2, 0.5, [t], size=17, color=RGBColor(255, 255, 255) if dark else NAVY, bold=True, space_after=0, name=f"步驟標題{i + 1}")
        K.textbox(s, x + 0.1, 3.05, w - 0.2, 1.4, [d], size=13, color=RGBColor(255, 255, 255) if dark else INK, space_after=0, name=f"步驟說明{i + 1}")
        if i < len(steps) - 1:
            a = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x + w + 0.03), Inches(3.25), Inches(0.26), Inches(0.35))
            a.fill.solid(); a.fill.fore_color.rgb = MUTED; a.line.fill.background(); a.shadow.inherit = False; a.name = f"箭頭{i + 1}"
    K.textbox(s, 0.5, 5.1, 12.3, 1.6, ["只計有法定總樓地板的分區塊；公園、河川、保護區等無法定值的土地不納入分母，落在其中的建物樓地板也不計入。",
                                      "步驟④是這次分析最關鍵的地方：現況樓地板（sumdd08）有兩個問題，下面兩頁說明。"], size=14, bullets=True, space_after=8, name="流程備註")

    # 4 版本比較
    s = K.title_only(prs, "同一分母，不同現況樓地板，全市使用率差到六倍", source=SRC)
    cd = CategoryChartData()
    ver = [("使照版（2001 年後新建，建築面積×層數）", 24.8), ("建物套繪版（含地下層，涵蓋 77% 建物）", 83.9), ("sumdd08 去重＋回推地上（最終版）", 91.1), ("sumdd08 去重後（總樓地板）", 117.3), ("sumdd08 原始（未去重）", 156.6)]
    cd.categories = [v[0] for v in ver]
    cd.add_series("全市使用率", [v[1] for v in ver])
    gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.5), Inches(1.5), Inches(8.2), Inches(5.3), cd); gf.name = "圖表：版本比較"
    ch = gf.chart; style_chart(ch, "圖1 全市容積使用率（有法定值分區塊）", legend=False, vmax=180)
    pl = ch.plots[0]; pl.gap_width = 45; pl.has_data_labels = True
    pl.data_labels.number_format, pl.data_labels.number_format_is_linked = '0.0"%"', False
    pl.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END; pl.data_labels.font.size = Pt(11)
    for i, col in enumerate(["BBBBBB", "6FA3D0", "B2182B", "F58518", "999999"]):
        pt = pl.series[0].points[i]; pt.format.fill.solid(); pt.format.fill.fore_color.rgb = rgb(col)
    K.textbox(s, 9.0, 1.6, 3.9, 5.0, ["使照版只涵蓋 2001 年後新建的建物，使用率偏低。", "建物套繪版的樓地板約為使照地上樓地板的 1.44 倍，含地下層，且只涵蓋七成多的建物面積。",
                                      "sumdd08 涵蓋全部建物，但有重複與地下、附屬面積，需要校正。", "最終版以去重後、依使照比例回推地上樓地板，全市約 91%。"], size=13, bullets=True, space_after=9, name="版本說明")

    # 5 問題一
    s = K.title_only(prs, "問題一：sumdd08 含地下層與附屬面積，約只有 76% 是地上", source=SRC)
    g_items = [("屋齡 0-10 年", 0.652), ("11-25 年", 0.649), ("26-40 年", 0.817), ("41 年以上", 0.901), ("1-3 層", 0.931), ("4-5 層", 0.871), ("6-8 層", 0.719), ("9-12 層", 0.653), ("13-20 層", 0.644), ("21 層以上", 0.662)]
    cd = CategoryChartData(); cd.categories = [g[0] for g in g_items]; cd.add_series("地上樓地板÷sumdd08", [g[1] for g in g_items])
    gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.5), Inches(1.5), Inches(8.2), Inches(5.3), cd); gf.name = "圖表：校準比例"
    ch = gf.chart; style_chart(ch, "圖2 使照地上樓地板 ÷ sumdd08（中位數）", legend=False, vmax=1.1, fmt="0.0")
    pl = ch.plots[0]; pl.gap_width = 40; pl.has_data_labels = True
    pl.data_labels.number_format, pl.data_labels.number_format_is_linked = "0.00", False
    pl.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END; pl.data_labels.font.size = Pt(11)
    for i in range(len(g_items)):
        pt = pl.series[0].points[i]; pt.format.fill.solid(); pt.format.fill.fore_color.rgb = rgb("2166AC" if i < 4 else "EF8A62")
    K.textbox(s, 9.0, 1.6, 3.9, 5.0, ["以 7,737 個單一使照地號比對：使照地上樓地板 ÷ sumdd08，全體中位數 0.76。", "藍色為屋齡帶、橘色為地上層數帶。新建高樓地下室與停車空間占比大，比例低到 0.64；老舊低層幾乎無地下室，接近 0.9～0.93。",
                                      "回推時依「地上層數×屋齡帶」取中位數，樣本不足的格子退回邊際值；回測加總誤差 −1.1%，單一地號相對誤差中位數約 8%（樣本內）。"], size=13, bullets=True, space_after=9, name="校準說明")

    # 6 問題二
    s = K.title_only(prs, "問題二：同一棟跨多個地號，樓地板被重複計算", source=SRC)
    for i, (num, lab) in enumerate([("3.36 → 2.26 億㎡", "全市 sumdd08 去重前後（減少 32.6%）"), ("22,884 群", "同棟地號群組，涉及 64,509 個地號"), ("92%", "去重量有「地號放不下該樓地板」佐證")]):
        x = 0.5 + i * 4.2
        b = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(1.6), Inches(3.95), Inches(1.9)); b.fill.solid(); b.fill.fore_color.rgb = TINT; b.line.fill.background(); b.shadow.inherit = False; b.name = f"數字卡{i + 1}"
        K.textbox(s, x + 0.15, 1.75, 3.65, 0.8, [num], size=26, color=NAVY, bold=True, space_after=0, name=f"數字{i + 1}")
        K.textbox(s, x + 0.15, 2.65, 3.65, 0.8, [lab], size=13, color=INK, space_after=0, name=f"數字說明{i + 1}")
    K.textbox(s, 0.5, 3.8, 12.3, 3.0, ["發現：相鄰地號的 sumdd08、建物數、層數、屋齡完全相同，例如三玉段一小段 393、394、395 號的 sumdd08 都是 332.11 ㎡，但土地面積各僅 1 ㎡——是同一棟建物在每個地號各記一次。",
                                       "去重規則：相鄰（地號面相接）且上述屬性皆相同者視為同一棟，樓地板只算一次，依地號登記面積比例分配到各地號。",
                                       "區分真假重複：群組中若有地號放不下該樓地板（sumdd08 > 土地面積×（層數＋4）），視為確屬同棟；其餘約 8%（約 844 萬㎡）可能是相鄰的相同透天厝，被誤併的風險較高。",
                                       "去重後，全市 sumdd08 使用率從 157% 降到 117%；再回推只計地上，降到約 91%。"], size=14, bullets=True, space_after=9, name="去重說明")

    # 7 各區結果
    s = K.title_only(prs, "各行政區使用率：去重與回推地上之後，松山、中山仍居前", source=SRC)
    d = T[T["行政區"] != "全市"].sort_values(c_up)
    cats = ["全市"] + d["行政區"].tolist()
    allrow = T[T["行政區"] == "全市"].iloc[0]
    cd = CategoryChartData(); cd.categories = cats
    cd.add_series("sumdd08 去重前", [float(allrow[c_old])] + d[c_old].astype(float).tolist())
    cd.add_series("sumdd08 去重後", [float(allrow[c_new])] + d[c_new].astype(float).tolist())
    cd.add_series("去重後推算地上", [float(allrow[c_up])] + d[c_up].astype(float).tolist())
    gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.5), Inches(1.45), Inches(8.6), Inches(5.45), cd); gf.name = "圖表：各行政區"
    ch = gf.chart; style_chart(ch, "圖3 各行政區容積使用率（有法定值分區塊）", legend=True, vmax=300)
    pl = ch.plots[0]; pl.gap_width = 40; pl.overlap = -5
    for ser, col in zip(pl.series, ["CCCCCC", "F58518", "B2182B"]):
        ser.format.fill.solid(); ser.format.fill.fore_color.rgb = rgb(col)
    up = pl.series[2]; up.data_labels.show_value = True
    up.data_labels.number_format, up.data_labels.number_format_is_linked = '0', False
    up.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END; up.data_labels.font.size = Pt(9)
    hi = d.sort_values(c_up, ascending=False)
    K.textbox(s, 9.3, 1.6, 3.6, 5.0, [f"推算地上使用率最高：{hi.iloc[0]['行政區']} {hi.iloc[0][c_up]:.0f}%、{hi.iloc[1]['行政區']} {hi.iloc[1][c_up]:.0f}%、{hi.iloc[2]['行政區']} {hi.iloc[2][c_up]:.0f}%。",
                                      f"最低：{hi.iloc[-1]['行政區']} {hi.iloc[-1][c_up]:.0f}%、{hi.iloc[-2]['行政區']} {hi.iloc[-2][c_up]:.0f}%。",
                                      "去重影響最大的是中山（291%→156%）、松山、南港、大同，這些區跨地號的建物樓地板重複較多。", f"全市去重前 {allrow[c_old]:.0f}%、去重後 {allrow[c_new]:.0f}%、推算地上 {allrow[c_up]:.0f}%。"], size=13, bullets=True, space_after=9, name="結果說明")

    # 8 地圖
    s = K.title_only(prs, "分區塊分布：盆地中央與西側偏高，外圍山邊偏低", source=SRC)
    img = BASE / "去重版" / "圖_分區塊容積使用率_去重.png"
    iw, ih = Image.open(img).size
    h = 5.4; w = h * iw / ih
    s.shapes.add_picture(str(img), Inches(0.5), Inches(1.5), Inches(w), Inches(h)).name = "圖：分區塊容積使用率"
    K.textbox(s, 0.5 + w + 0.3, 1.6, 12.83 - (0.5 + w + 0.3), 5.0, ["使用率較高的深色街廓集中在盆地中央與西側（中山、松山、大安、中正），以及信義區東側的商業與特定業務區。",
                                                                  "山邊的士林、北投、文山與南港外圍偏淡；灰色為無法定容積率的土地（公園、河川、保護區、機場等）。",
                                                                  "此圖是以分區塊為單位，個別分區塊受地號與分區邊界不吻合影響較大，宜看整體分布。"], size=13, bullets=True, space_after=9, name="地圖說明")

    # 9 限制
    s = K.title_only(prs, "限制與後續", source=SRC)
    K.textbox(s, 0.5, 1.6, 12.3, 5.2, ["法定容積為「容積率上限」，不含容積獎勵、移轉與舊制放寬，現況高於法定的情形不一定代表違規。",
                                       "回推比例 g 來自單一使照的新建地號，多棟、增建或較複雜的建物沒有納入校準；老舊建物的校準樣本也較少。",
                                       "去重規則可能把相鄰、完全相同的透天厝誤併（估計約占去重量的 8%）。",
                                       "地號與分區塊邊界不完全吻合，樓地板依交集面積分配，個別分區塊誤差較大；行政區彙總相對穩定。",
                                       "法定總樓地板只涵蓋約三成的土地（有容積率的分區），落在無法定值分區的現況建物不計入。",
                                       "後續可行方向：以建物套繪圖的建物面為單位直接分配（避免地號層級的重複）；補齊較早年代的使照樓層資料；對照都更、危老範圍分析低使用率分區。"],
                size=15, bullets=True, space_after=11, name="限制內文")
    out = BASE / "臺北市分區容積使用_分析過程.pptx"
    prs.save(out)
    print(out)


if __name__ == "__main__":
    main()
