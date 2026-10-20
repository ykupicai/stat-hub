"""以歷年建造執照摘要（民國 90～114 年）分析臺北市各行政區土地開發強度演變：年度新增樓地板（建築面積×地上層數）。

資料：資料庫/原始檔/臺北市歷年建造執照摘要/建照_層級.csv、建照_地號展開.csv（parse_臺北市歷年建造執照摘要.py）
口徑：建造類別＝新建、改建（增建、修建只增減部分面積，不計）；行政區取該建照第一個地號所屬行政區；年＝發照年（民國）。
  樓地板（估）＝建築面積×地上層數（依使用者指定估法；對高樓、大基地會高估，樓層明細版僅作對照）。
輸出：案件/臺北市_不動產交易分析/建照開發強度演變/行政區×年度_新增樓地板.xlsx（唯一一張表）、圖_各行政區年度新增樓地板.png（＋手機版 jpg）
執行：python scripts/analyze_臺北市_建照開發強度演變.py
"""
import io
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from PIL import Image

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
BP = ROOT / "資料庫" / "原始檔" / "臺北市歷年建造執照摘要"
OUT = ROOT / "案件" / "臺北市_不動產交易分析" / "建照開發強度演變"
plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "PMingLiU", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False
DIST = ["中山區", "大同區", "中正區", "萬華區", "松山區", "大安區", "信義區", "內湖區", "南港區", "士林區", "北投區", "文山區"]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    L = pd.read_csv(BP / "建照_層級.csv", dtype={"執照號碼": str, "發照日期": str})
    X = pd.read_csv(BP / "建照_地號展開.csv", dtype={"執照號碼": str}).drop_duplicates("執照號碼")[["執照號碼", "行政區"]]
    L = L.merge(X, on="執照號碼", how="left")
    L = L[L["類別"].isin(["新建", "改建"]) & L["地上樓地板_估"].notna() & L["行政區"].isin(DIST)].copy()
    L["年"] = L["發照日期"].str[:-4].astype(int)
    raw_total = L["地上樓地板_估"].sum()
    # 異常值處理：建築面積×層數對「多棟建物的校園／大基地」會嚴重高估（如臺大用地建築面積 23 萬㎡×7 層，樓層明細實際約 1 萬㎡）：
    #   (1) 有樓層明細且 明細 ÷ 估算 < 0.33 者，改用明細；(2) 其餘估算值以 基地面積×10（容積率 1000%）為上限
    est = L["地上樓地板_估"].copy()
    bad = L["地上樓地板_明細"].notna() & (L["地上樓地板_明細"] / est < 0.33)
    est[bad] = L.loc[bad, "地上樓地板_明細"]
    cap = (L["基地面積"].where(L["基地面積"] > 0) * 10)
    capped = (est > cap) & cap.notna()
    est[capped] = cap[capped]
    L["地上樓地板_估"] = est
    print(f"建照（新建、改建、有行政區）{len(L):,} 張；年 {L['年'].min()}～{L['年'].max()}；樓地板（估）原公式 {raw_total / 1e4:,.0f} 萬㎡ → 處理異常值後 {est.sum() / 1e4:,.0f} 萬㎡"
          f"（改用明細 {int(bad.sum())} 張、套上限 {int(capped.sum())} 張）")
    t = (L.groupby(["行政區", "年"])["地上樓地板_估"].sum() / 1e4).unstack(fill_value=0).reindex(index=DIST, columns=range(90, 115), fill_value=0)
    t.loc["全市"] = t.sum()
    n = L.groupby(["行政區", "年"]).size().unstack(fill_value=0).reindex(index=DIST, columns=range(90, 115), fill_value=0)
    # Excel（唯一一張表）：行政區 × 年度（萬㎡），附期間合計與各期占比
    periods = [("90～94 年", range(90, 95)), ("95～99 年", range(95, 100)), ("100～104 年", range(100, 105)), ("105～109 年", range(105, 110)), ("110～114 年", range(110, 115))]
    wb = Workbook(); ws = wb.active; ws.title = "行政區×年度"
    ws.append(["臺北市各行政區年度新增樓地板（萬㎡；建造執照＝新建＋改建，建築面積×地上層數，發照年）"])
    ws.append(["行政區"] + [f"{y}" for y in range(90, 115)] + [p for p, _ in periods] + ["合計"])
    for d in DIST + ["全市"]:
        row = [d] + [round(float(t.loc[d, y]), 1) for y in range(90, 115)] + [round(float(sum(t.loc[d, y] for y in r)), 1) for _, r in periods] + [round(float(t.loc[d].sum()), 1)]
        ws.append(row)
    ws.append([f"註：樓地板（估）＝建築面積×地上層數；為避免校園等多棟大基地被嚴重高估，有樓層明細且明細÷估算<0.33 的 {int(bad.sum())} 張改用明細，其餘以基地面積×10 為上限（{int(capped.sum())} 張）；"
               f"原公式全市合計 {raw_total / 1e4:,.0f} 萬㎡，處理後 {L['地上樓地板_估'].sum() / 1e4:,.0f} 萬㎡；增建、修建不計；建照只含民國 90 年以後發照者；行政區取第一個地號所屬行政區；全市共 {len(L):,} 張。"])
    hdr = PatternFill("solid", fgColor="E8EDF4")
    for c in ws[2]:
        c.font = Font(bold=True); c.fill = hdr; c.alignment = Alignment(horizontal="center", wrap_text=True)
    ws["A1"].font = Font(bold=True, size=12)
    for r in ws.iter_rows(min_row=3, max_row=2 + len(DIST) + 1):
        for c in r[1:]:
            c.alignment = Alignment(horizontal="right"); c.number_format = "#,##0.0"
    for ci in range(1, 2 + 25 + len(periods) + 1):
        ws.column_dimensions[get_column_letter(ci)].width = 8.5 if ci > 1 else 10
    ws.freeze_panes = "B3"
    wb.save(OUT / "行政區×年度_新增樓地板.xlsx")
    # 圖：小倍數折線
    fig, axs = plt.subplots(3, 4, figsize=(13, 8.4), sharex=True)
    ymax = float(t.loc[DIST].to_numpy().max()) * 1.08
    for ax, d in zip(axs.ravel(), DIST):
        v = t.loc[d].to_numpy(float)
        ax.plot(range(90, 115), v, color="#B2182B", lw=1.6, marker="o", ms=2.8)
        ax.plot(range(90, 115), pd.Series(v).rolling(3, center=True, min_periods=1).mean(), color="#2166AC", lw=1.2, ls="--")
        ax.set_title(f"{d}（合計 {v.sum():,.0f} 萬㎡）", fontsize=10.5)
        ax.set_ylim(0, ymax); ax.tick_params(labelsize=8); ax.grid(axis="y", color="#e6e6e6", lw=0.6)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        pk = int(np.argmax(v)); ax.annotate(f"{90 + pk}", (90 + pk, v[pk]), textcoords="offset points", xytext=(0, 4), ha="center", fontsize=7.5, color="#555")
    for ax in axs[-1]:
        ax.set_xticks([90, 95, 100, 105, 110, 114])
    fig.suptitle("臺北市各行政區年度新增樓地板（建造執照，民國 90～114 年）", fontsize=14, y=0.995)
    fig.text(0.5, 0.005, "新增樓地板＝建築面積×地上層數（萬㎡，新建＋改建）；紅線為年值、藍虛線為 3 年移動平均；數字為年值最高的年份；資料：臺北市歷年建造執照摘要", ha="center", fontsize=8, color="#555")
    fig.tight_layout(rect=(0, 0.015, 1, 0.97))
    f = OUT / "圖_各行政區年度新增樓地板.png"; fig.savefig(f, dpi=160); plt.close(fig)
    im = Image.open(f).convert("RGB"); im.resize((1300, int(im.height * 1300 / im.width)), Image.LANCZOS).save(OUT / "圖_各行政區年度新增樓地板_手機版.jpg", quality=88)
    # 摘要
    tot = t.loc["全市"]
    print("全市年值（萬㎡）：", {int(y): round(float(v)) for y, v in tot.items()})
    per = {p: float(sum(t.loc["全市", y] for y in r)) for p, r in periods}
    print("全市各期合計：", {k: round(v) for k, v in per.items()})
    for d in DIST:
        p5 = [float(sum(t.loc[d, y] for y in r)) for _, r in periods]
        pk = int(t.loc[d].idxmax())
        print(f"{d}：合計 {t.loc[d].sum():,.0f}；各期 {[round(x) for x in p5]}；最高年 {pk}（{t.loc[d, pk]:,.0f}）；占全市 {t.loc[d].sum() / tot.sum() * 100:.1f}%；後兩期/前兩期 {(p5[3] + p5[4]) / (p5[0] + p5[1]):.2f}")
    top_lic = L.sort_values("地上樓地板_估", ascending=False).head(8)[["執照號碼", "行政區", "地上樓地板_估", "地上層數", "建築面積", "地上樓地板_明細"]]
    print("單張最大："); print(top_lic.to_string(index=False))
    print("最大 20 張占全市比例", round(L.nlargest(20, "地上樓地板_估")["地上樓地板_估"].sum() / L["地上樓地板_估"].sum() * 100, 1), "%")


if __name__ == "__main__":
    main()
