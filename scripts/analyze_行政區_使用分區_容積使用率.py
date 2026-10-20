"""各行政區（橫軸）× 主要使用分區（縱軸）的容積使用率（去重後推算地上樓地板 ÷ 法定總樓地板）：一張表＋熱度圖。

輸入：分區容積使用/去重版/分區塊_容積使用狀況_去重.shp（USE_UP 口徑；UP_FA、LEG_FA）
分類：只計有法定容積率的分區塊；縱軸取法定總樓地板最大的 15 種使用分區，其餘併為「其他分區」。
儲存格：使用率＝Σ推算地上樓地板 ÷ Σ法定總樓地板；該格分區塊數 < 5 或法定總樓地板 < 5 萬㎡ 者不顯示（—），避免樣本過小。
輸出：分區容積使用/去重版/行政區×使用分區_容積使用率.xlsx（唯一一張表）、圖_行政區×使用分區_容積使用率.png（＋手機版 jpg）
執行：python scripts/analyze_行政區_使用分區_容積使用率.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyogrio
from matplotlib.colors import LinearSegmentedColormap
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "案件" / "臺北市_不動產交易分析" / "分區容積使用" / "去重版"
plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "PMingLiU", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False
DIST = ["中山區", "大同區", "中正區", "萬華區", "松山區", "大安區", "信義區", "內湖區", "南港區", "士林區", "北投區", "文山區"]
MIN_N, MIN_FA = 5, 50_000.0


def main():
    z = pyogrio.read_dataframe(D / "分區塊_容積使用狀況_去重.shp", read_geometry=False, encoding="utf-8")
    z = z[z["USE_UP"].notna() & (z["LEG_FA"] > 0)].copy()
    top = z.groupby("ZONE_NAME")["LEG_FA"].sum().sort_values(ascending=False).head(15).index.tolist()
    z["分區"] = np.where(z["ZONE_NAME"].isin(top), z["ZONE_NAME"], "其他分區")
    pref = ["第二種住宅區", "第三種住宅區", "第三之一種住宅區", "第三之二種住宅區", "第四種住宅區", "住宅區", "第三種商業區", "第三種商業區(特)", "第四種商業區",
            "第參種工業區", "機關用地", "國小用地", "國中用地", "大專用地", "公墓用地"]  # 住宅→商業→工業→公共設施，其餘依法定樓地板大小
    order = [n for n in pref if n in top] + [n for n in top if n not in pref] + ["其他分區"]

    def cell(x):
        if len(x) < MIN_N or x["LEG_FA"].sum() < MIN_FA:
            return np.nan
        return x["UP_FA"].sum() / x["LEG_FA"].sum() * 100
    rate = z.groupby(["分區", "TOWN"]).apply(cell).unstack().reindex(index=order, columns=DIST)
    rate["全市"] = z.groupby("分區").apply(cell).reindex(order)
    allrow = {t: cell(z[z["TOWN"] == t]) for t in DIST}
    allrow["全市"] = cell(z)
    rate.loc["全部分區"] = pd.Series(allrow)
    nz = z.groupby("分區").size().reindex(order)
    legw = (z.groupby("分區")["LEG_FA"].sum() / z["LEG_FA"].sum() * 100).reindex(order)
    print(f"有法定值分區塊 {len(z):,}；縱軸 {len(order)} 列（前 15 種占法定總樓地板 {z['分區'].isin(top).mul(z['LEG_FA']).sum() / z['LEG_FA'].sum():.1%}）")
    print(rate.round(0).to_string())
    # Excel（唯一一張表）
    wb = Workbook(); ws = wb.active; ws.title = "行政區×使用分區"
    ws.append(["臺北市各行政區各使用分區容積使用率（%；去重後推算地上樓地板 ÷ 法定總樓地板）"])
    ws.append(["使用分區", "分區塊數", "占法定總樓地板%"] + DIST + ["全市"])
    for name in rate.index:
        n = int(nz[name]) if name in nz.index else int(len(z)); w = float(legw[name]) if name in legw.index else 100.0
        ws.append([name, n, round(w, 1)] + [(None if pd.isna(v) else round(float(v), 1)) for v in rate.loc[name, DIST + ["全市"]]])
    ws.append([f"註：只計有法定容積率的分區塊；縱軸為法定總樓地板最大的 15 種使用分區，其餘併為「其他分區」；空白＝該格分區塊數少於 {MIN_N} 塊或法定總樓地板不足 5 萬㎡，不顯示；"
               "使用率＝Σ推算地上樓地板÷Σ法定總樓地板（容積率為上限，不含獎勵）。"])
    hdr = PatternFill("solid", fgColor="E8EDF4")
    for c in ws[2]:
        c.font = Font(bold=True); c.fill = hdr; c.alignment = Alignment(horizontal="center", wrap_text=True)
    ws["A1"].font = Font(bold=True, size=12)
    for r in ws.iter_rows(min_row=3, max_row=2 + len(rate)):
        for c in r[1:]:
            c.alignment = Alignment(horizontal="right"); c.number_format = "#,##0" if c.column == 2 else "#,##0.0"
    ws.column_dimensions["A"].width = 24
    for ci in range(2, 4 + len(DIST) + 1):
        ws.column_dimensions[get_column_letter(ci)].width = 10
    ws.freeze_panes = "D3"
    wb.save(D / "行政區×使用分區_容積使用率.xlsx")
    # 熱度圖
    rows = list(rate.index)
    M = rate.loc[rows, DIST + ["全市"]].to_numpy(float)
    cmap = LinearSegmentedColormap.from_list("use", ["#FFFFCC", "#FED976", "#FD8D3C", "#E31A1C", "#800026"])
    cmap.set_bad("#EEEEEE")
    fig, ax = plt.subplots(figsize=(11, 8.2))
    im = ax.imshow(np.ma.masked_invalid(M), cmap=cmap, vmin=0, vmax=250, aspect="auto")
    ax.set_xticks(range(M.shape[1])); ax.set_xticklabels(DIST + ["全市"], fontsize=10)
    ax.set_yticks(range(len(rows))); ax.set_yticklabels([f"{r}" for r in rows], fontsize=10)
    ax.xaxis.tick_top()
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v = M[i, j]
            if np.isnan(v):
                ax.text(j, i, "—", ha="center", va="center", fontsize=9, color="#999")
            else:
                ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=9.5, color="white" if v > 150 else "#222", weight="bold" if i == len(rows) - 1 or j == M.shape[1] - 1 else None)
    ax.axhline(len(rows) - 1.5, color="#333", lw=1.2); ax.axvline(M.shape[1] - 1.5, color="#333", lw=1.2)
    ax.set_xticks(np.arange(-.5, M.shape[1], 1), minor=True); ax.set_yticks(np.arange(-.5, len(rows), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.2); ax.tick_params(which="minor", length=0)
    cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02); cb.set_label("容積使用率（%）", fontsize=9)
    ax.set_title("臺北市各行政區 × 使用分區容積使用率（%）\n去重後推算地上樓地板 ÷ 法定總樓地板；— 表示樣本不足（分區塊 < 5 或法定總樓地板 < 5 萬㎡）", fontsize=12, pad=38)
    fig.text(0.5, 0.01, "資料：地政局 BuildStat_Fage sumdd08（去重、依使照比例回推地上）、臺北市都發局彙整表法定容積率；只計有法定容積率的分區塊", ha="center", fontsize=8, color="#555")
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    f = D / "圖_行政區×使用分區_容積使用率.png"
    fig.savefig(f, dpi=170); plt.close(fig)
    img = Image.open(f).convert("RGB")
    img.resize((1300, int(img.height * 1300 / img.width)), Image.LANCZOS).save(D / "圖_行政區×使用分區_容積使用率_手機版.jpg", quality=88)


if __name__ == "__main__":
    main()
