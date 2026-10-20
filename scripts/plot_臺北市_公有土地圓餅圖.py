"""兩張圓餅圖（PNG＋手機版 jpg＋PowerPoint 原生可編輯圖表）：
  圖1 全臺北市土地權屬（地籍圖圖面面積；公私共有地號只計公有持分，私有持分與無地號的道路水域併入私有）
  圖2 公有土地在各種使用分區的占比（公有面積依使用分區圖分類；使用分區圖涵蓋 237 km²，約為地籍圖面積的 91%）
輸入：容積率分區公私有土地/臺北市地籍圖_公私有.shp（KEY、PUBW）、公有土地/臺北市公有土地.shp（LANDTYPE2）、使用分區公私有土地/總表.xlsx
輸出：案件/臺北市_不動產交易分析/公有土地圓餅圖/圖1_全市土地權屬圓餅圖、圖2_公有土地使用分區圓餅圖（PNG＋手機版）、臺北市公有土地圓餅圖_可編輯圖表.pptx
執行：python scripts/plot_臺北市_公有土地圓餅圖.py
"""
import io
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import pyogrio
from PIL import Image
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.util import Inches, Pt

warnings.filterwarnings("ignore")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent
CASE = ROOT / "案件" / "臺北市_不動產交易分析"
OUT = CASE / "公有土地圓餅圖"
plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "PMingLiU", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False
FONT = "Microsoft JhengHei"


def save(fig, name, w=1000):
    f = OUT / f"{name}.png"
    fig.savefig(f, dpi=150, bbox_inches="tight")
    plt.close(fig)
    im = Image.open(f).convert("RGB")
    im.resize((w, int(im.height * w / im.width)), Image.LANCZOS).save(OUT / f"{name}_手機版.jpg", quality=88)


def pie(title, labels, vals, colors, fname, unit_note, sub=None):
    tot = float(sum(vals))
    fig, ax = plt.subplots(figsize=(10, 7.4))
    wedges, _ = ax.pie(vals, colors=colors, startangle=90, counterclock=False, wedgeprops=dict(edgecolor="white", linewidth=1.2))
    import numpy as np
    for w, v in zip(wedges, vals):
        pct = v / tot * 100
        ang = np.deg2rad((w.theta1 + w.theta2) / 2)
        x, y = np.cos(ang), np.sin(ang)
        if pct >= 4:
            ax.text(0.68 * x, 0.68 * y, f"{pct:.1f}%", ha="center", va="center", fontsize=11, color="white" if pct > 8 else "#222", weight="bold")
    ax.legend(wedges, [f"{l}　{v:,.0f} 公頃（{v / tot * 100:.1f}%）" for l, v in zip(labels, vals)], loc="center left", bbox_to_anchor=(1.0, 0.5), frameon=False, fontsize=11)
    ax.set_title(title + (f"\n{sub}" if sub else ""), fontsize=14, loc="left")
    fig.text(0.02, 0.02, unit_note, fontsize=8, color="#555")
    ax.axis("equal")
    save(fig, fname)


def native_pie(slide, labels, vals, colors, x, y, w, h, name):
    cd = CategoryChartData()
    cd.categories = labels
    cd.add_series("面積（公頃）", [round(float(v), 1) for v in vals])
    gf = slide.shapes.add_chart(XL_CHART_TYPE.PIE, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    gf.name = name
    ch = gf.chart
    ch.has_legend = True
    ch.legend.position = XL_LEGEND_POSITION.RIGHT
    ch.legend.include_in_layout = False
    ch.legend.font.size = Pt(12)
    ch.legend.font.name = FONT
    pl = ch.plots[0]
    for i, c in enumerate(colors):
        pt = pl.series[0].points[i]
        pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = RGBColor.from_string(c.lstrip("#").upper())
        pt.format.line.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    pl.has_data_labels = True
    dl = pl.data_labels
    dl.show_percentage = True
    dl.show_value = False
    dl.number_format = '0.0%'
    dl.number_format_is_linked = False
    dl.font.size = Pt(12)
    dl.font.name = FONT
    dl.font.bold = True
    dl.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    dl.position = XL_LABEL_POSITION.CENTER


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    g = pyogrio.read_dataframe(CASE / "容積率分區公私有土地" / "臺北市地籍圖_公私有.shp", columns=["KEY", "PUBW"])
    g["a"] = g.geometry.area
    g = g.drop(columns="geometry")
    pub = gpd.read_file(CASE / "公有土地" / "臺北市公有土地.shp", encoding="utf-8", columns=["PL48", "PL49", "LANDTYPE2"], ignore_geometry=True)
    pub["KEY"] = pub["PL48"].astype(str).str.zfill(4) + pub["PL49"].astype(str).str.zfill(8)
    g["T"] = g["KEY"].map(pub.drop_duplicates("KEY").set_index("KEY")["LANDTYPE2"])
    g["pubA"] = g["a"] * g["PUBW"]
    tot = g["a"].sum()
    s = g.groupby("T")["pubA"].sum()
    mixed = s.get("公、私共有", 0.0)
    cats = [("國有", ["國有"]), ("臺北市有", ["臺北市有"]), ("臺北市有及國有共有", ["臺北市有及國有共有"]),
            ("公私共有（公有持分）", ["公、私共有"]), ("其他政府機關有及其他共有", ["其他政府機關有", "臺北市有、國有及其他政府機關共有", "臺北市有及非國有政府機關共有"])]
    labs, vals = [], []
    for nm, ks in cats:
        labs.append(nm)
        vals.append(sum(s.get(k, 0.0) for k in ks) / 1e4)
    labs.append("私有（含公私共有私有持分、無地號道路水域）")
    vals.append(tot / 1e4 - sum(vals))
    cols1 = ["#C0392B", "#E67E22", "#F1C40F", "#9B59B6", "#16A085", "#BFD4E8"]
    print("圖1：", {l: round(v, 1) for l, v in zip(labs, vals)}, "總計", round(tot / 1e4, 1))
    pie("全臺北市土地權屬", labs, vals, cols1, "圖1_全市土地權屬圓餅圖", "資料：都發局地籍圖（421,843 個地號，圖面 26,120 公頃）、地政局公有土地圖層；公私共有地號只計公有持分；面積為圖面面積", "占全市地籍圖面積比例")
    # 圖2：公有土地在各使用分區
    t = pd.read_excel(CASE / "使用分區公私有土地" / "總表.xlsx", header=1)
    t = t[(t["行政區"] == "全市") & (t["使用分區"] != "全部分區") & t["使用分區"].notna()]
    order = t.sort_values("公有面積(公頃)", ascending=False)
    labs2, vals2 = order["使用分區"].tolist(), order["公有面積(公頃)"].tolist()
    nm = {"住宅區": "住宅區", "商業區": "商業區", "工業區": "工業區", "公共設施用地": "公共設施用地", "保護區": "保護區", "農業區": "農業區", "行水區": "行水區（河川區）", "國家公園": "國家公園", "其他專用區": "其他專用區"}
    labs2 = [nm.get(x, x) for x in labs2]
    cmap = {"住宅區": "#F2CF6B", "商業區": "#E45756", "工業區": "#9D6FB5", "公共設施用地": "#6FA3D0", "保護區": "#54A24B", "農業區": "#B5DBA0", "行水區（河川區）": "#7FC8D6", "國家公園": "#2F7A3A", "其他專用區": "#BBBBBB"}
    cols2 = [cmap[x] for x in labs2]
    # 使用分區圖沒有畫出分區的公有土地（實測幾乎全是道路用地）＝全市公有合計（圖 1）－使用分區圖範圍內公有面積
    resid = sum(vals[:-1]) - sum(vals2)
    vals2[labs2.index("公共設施用地")] += resid   # 道路用地併入公共設施用地
    print("圖2：", {l: round(v, 1) for l, v in zip(labs2, vals2)}, "總計", round(sum(vals2), 1))
    pie("公有土地在各種使用分區的占比", labs2, vals2, cols2, "圖2_公有土地使用分區圓餅圖",
        "資料：都發局使用分區圖、地政局公有土地圖層；公私共有地號只計公有持分；公共設施用地含使用分區圖未畫出的道路用地（全市公有合計扣除使用分區圖範圍內的公有面積，約 2,124 公頃）", f"公有土地合計 {sum(vals2):,.0f} 公頃")
    # PPT
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    for title, labs_, vals_, cols_, note in (("全臺北市土地權屬（占地籍圖面積）", labs, vals, cols1, "資料：都發局地籍圖、地政局公有土地圖層；公私共有地號只計公有持分；面積為圖面面積"),
                                             ("公有土地在各種使用分區的占比", labs2, vals2, cols2, "資料：都發局使用分區圖、地政局公有土地圖層；公私共有地號只計公有持分；公共設施用地含使用分區圖未畫出的道路用地")):
        sl = prs.slides.add_slide(prs.slide_layouts[6])
        tb = sl.shapes.add_textbox(Inches(0.5), Inches(0.35), Inches(12.3), Inches(0.9))
        tb.name = "標題"
        r = tb.text_frame.paragraphs[0].add_run()
        r.text = title
        r.font.size, r.font.bold, r.font.name = Pt(28), True, FONT
        r.font.color.rgb = RGBColor(0x1F, 0x2A, 0x44)
        native_pie(sl, labs_, vals_, cols_, 0.8, 1.4, 11.7, 5.4, "圖表：" + title)
        tb2 = sl.shapes.add_textbox(Inches(0.5), Inches(7.0), Inches(12.3), Inches(0.3))
        tb2.name = "資料來源"
        r2 = tb2.text_frame.paragraphs[0].add_run()
        r2.text = note
        r2.font.size, r2.font.name = Pt(10), FONT
        r2.font.color.rgb = RGBColor(0x5F, 0x6B, 0x7A)
    prs.save(OUT / "臺北市公有土地圓餅圖_可編輯圖表.pptx")
    print("完成")


if __name__ == "__main__":
    main()
