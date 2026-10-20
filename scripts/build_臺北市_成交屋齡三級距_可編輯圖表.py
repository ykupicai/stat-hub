"""各行政區成交時屋齡三級距（20 年以下／21-30 年／31 年以上）→ PowerPoint 原生（可編輯）100% 堆疊橫條圖，1 頁。
輸入：行政區三表_105至114/表6_*.xlsx　輸出：同資料夾 臺北市行政區成交屋齡三級距_可編輯圖表.pptx
執行：python scripts/build_臺北市_成交屋齡三級距_可編輯圖表.py
"""
import importlib.util
import sys
from pathlib import Path

import pandas as pd
from pptx import Presentation
from pptx.util import Inches

ROOT = Path(__file__).resolve().parent.parent
sys.argv = [sys.argv[0]]
spec = importlib.util.spec_from_file_location("deck", ROOT / "scripts" / "build_臺北市_行政區三表簡報.py")
K = importlib.util.module_from_spec(spec)
spec.loader.exec_module(K)
D = K.D
SRC = "資料：內政部不動產交易實價查詢服務網，臺北市不動產買賣，交易日 105～114 年；屋齡＝交易年－建築完成年；僅計有建物且屋齡可算出者（168,611 筆）"
BANDS = ["20年以下", "21-30年", "31年以上"]


def main():
    t = pd.read_excel(D / "表6_行政區×成交時屋齡三級距_筆數與占比.xlsx", header=1)
    t = t[t["指標"] == "占比%"].set_index("屋齡級距").drop(columns="指標").loc[BANDS]
    cats = ["全市"] + t.drop(columns="全市").loc["31年以上"].sort_values().index.tolist()
    spec1 = dict(title="圖T6 臺北市各行政區：成交時屋齡三級距占比（依 31 年以上占比排序）", cats=cats, stack100=True,
                 series=[(b, c, t.loc[b].astype(float).to_dict()) for b, c in zip(BANDS, ["2166AC", "D1E5F0", "B2182B"])])
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    s = K.title_only(prs, "31 年以上成交：士林、大安、松山逾六成，南港僅三成", source=SRC)
    K.add_native_chart(s, spec1, 0.5, 1.5, 8.6, 5.35)
    px, pw = 9.4, 3.45
    panel = s.shapes.add_shape(1, Inches(px), Inches(1.5), Inches(pw), Inches(5.35))
    panel.fill.solid(); panel.fill.fore_color.rgb = K.TINT; panel.line.fill.background(); panel.shadow.inherit = False; panel.name = "說明底板"
    K.textbox(s, px + 0.15, 1.62, pw - 0.3, 0.4, ["重點"], size=18, color=K.NAVY, bold=True, space_after=0, name="說明標題")
    g = lambda b, c: float(t.loc[b, c])
    K.textbox(s, px + 0.15, 2.1, pw - 0.3, 3.5, [
        f"全市 31 年以上占 {g('31年以上', '全市'):.1f}%，20 年以下占 {g('20年以下', '全市'):.1f}%，21-30 年占 {g('21-30年', '全市'):.1f}%。",
        f"31 年以上最高：士林 {g('31年以上', '士林區'):.1f}%、大安 {g('31年以上', '大安區'):.1f}%、松山 {g('31年以上', '松山區'):.1f}%。",
        f"最低：南港 {g('31年以上', '南港區'):.1f}%（20 年以下占 {g('20年以下', '南港區'):.1f}%）。",
        f"文山 21-30 年占 {g('21-30年', '文山區'):.1f}%，為各區最高。"], size=13, bullets=True, space_after=7, name="說明內文")
    K.textbox(s, px + 0.15, 5.65, pw - 0.3, 1.1, ["分母：168,611 筆可算出屋齡的有建物交易。", "級距：20 年以下（含 20）、21-30、31 年以上。"], size=11, color=K.MUTED, space_after=3, name="口徑註記")
    out = D / "臺北市行政區成交屋齡三級距_可編輯圖表.pptx"
    prs.save(out)
    print(out)


if __name__ == "__main__":
    main()
