"""臺北市房地買賣的樓層與建物型態：完整年份（105～114 年）、全市＋12 個行政區的年度統計與圖表。

項目：總樓層帶占比（5 層以下、6-10、11-15、16-25、26 層以上）、樓層中位數與 11 層以上／26 層以上占比、建物型態占比（住宅大樓、華廈、公寓、透天厝；110 年起分類才一致）。
母體：房地買賣（交易標的含房地；不含預售屋、租賃、純土地與純車位），樓層數可解析者；不排除特殊交易。
輸出：案件/臺北市_不動產交易分析/樓層與型態_年度/總表.xlsx（唯一一張表）、圖1～圖4 PNG（＋手機版 jpg）；摘要印在終端
執行：python scripts/analyze_臺北市_樓層與型態_年度.py
"""
import importlib.util
import warnings
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

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("base10", ROOT / "scripts" / "analyze_臺北市_實價登錄_10年.py")
B = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(B)   # 載入後 stdout 已為 UTF-8
OUT = ROOT / "案件" / "臺北市_不動產交易分析" / "樓層與型態_年度"
plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "PMingLiU", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False
DIST = ["中山區", "大同區", "中正區", "萬華區", "松山區", "大安區", "信義區", "內湖區", "南港區", "士林區", "北投區", "文山區"]
BANDS = ["5層以下", "6-10層", "11-15層", "16-25層", "26層以上"]
BC = ["#DCE9F5", "#A9C8E4", "#6FA3D0", "#3472AD", "#12385F"]
TYPES = ["公寓", "華廈", "住宅大樓", "透天厝"]
TC = ["#F2CF6B", "#A9C8E4", "#3472AD", "#E45756"]
YEARS = list(range(105, 115))


def stats(d):
    f = d["樓層數"]
    s = {"房地買賣筆數": len(d), "樓層中位數": float(f.median()), "樓層平均": float(f.mean())}
    cut = pd.cut(f, [-1, 5, 10, 15, 25, 300], labels=BANDS)
    for b in BANDS:
        s[b + "%"] = float((cut == b).mean() * 100)
    s["11層以上%"] = float((f >= 11).mean() * 100)
    return s


def save(fig, name, w=1300):
    p = OUT / f"{name}.png"
    fig.savefig(p, dpi=150); plt.close(fig)
    im = Image.open(p).convert("RGB"); im.resize((w, int(im.height * w / im.width)), Image.LANCZOS).save(OUT / f"{name}_手機版.jpg", quality=88)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    B.D0 = 1050101  # 已補入 105S1～S3，起點放寬到 105 年 1 月
    tx, land, bld = B.load()
    tx, _ = B.prep(tx)
    z = tx[tx["房地"] & tx["樓層數"].notna() & (tx["年"] <= 114)].copy()
    z["區"] = z["鄉鎮市區"]
    print(f"房地買賣有樓層 {len(z):,} 筆（年 {z['年'].min()}～{z['年'].max()}）")
    # 統計：全市＋各區 × 年
    rows = []
    for name, d0 in [("全市", z)] + [(d, z[z["區"] == d]) for d in DIST]:
        for y in YEARS:
            d = d0[d0["年"] == y]
            if len(d) == 0:
                continue
            r = {"行政區": name, "年": y, **stats(d)}
            if y >= 110:
                t = d[d["型態"].isin(TYPES)]
                for ty in TYPES:
                    r[ty + "%"] = float((t["型態"] == ty).mean() * 100) if len(t) else np.nan
                r["型態有效筆數"] = len(t)
            rows.append(r)
    S = pd.DataFrame(rows)
    # Excel：唯一一張總表（長表）
    cols = ["行政區", "年", "房地買賣筆數", "樓層中位數", "樓層平均"] + [b + "%" for b in BANDS] + ["11層以上%"] + [t + "%" for t in TYPES] + ["型態有效筆數"]
    wb = Workbook(); ws = wb.active; ws.title = "樓層與型態"
    ws.append(["臺北市房地買賣樓層與建物型態：全市與各行政區年度統計（105～114 年；型態自 110 年起）"])
    ws.append(cols)
    for _, r in S.sort_values(["行政區", "年"], key=lambda s: s.map({n: i for i, n in enumerate(["全市"] + DIST)}) if s.name == "行政區" else s).iterrows():
        ws.append([r["行政區"], int(r["年"]), int(r["房地買賣筆數"])] + [None if pd.isna(r.get(c)) else round(float(r[c]), 1) for c in cols[3:12]] + [None if pd.isna(r.get(c)) else round(float(r[c]), 1) for c in cols[12:16]] + [None if pd.isna(r.get("型態有效筆數")) else int(r["型態有效筆數"])])
    ws.append(["註：母體為房地買賣（含房地；不含預售屋、租賃、純土地與純車位）且總樓層可解析者；樓層為建物登記總樓層數；建物型態平台分類自 110 年起收斂為公寓、華廈、住宅大樓、透天厝，型態占比分母為這四種型態的筆數。"])
    hdr = PatternFill("solid", fgColor="E8EDF4")
    for c in ws[2]:
        c.font = Font(bold=True); c.fill = hdr; c.alignment = Alignment(horizontal="center", wrap_text=True)
    ws["A1"].font = Font(bold=True, size=12)
    for r in ws.iter_rows(min_row=3, max_row=ws.max_row - 1):
        for c in r[1:]:
            c.alignment = Alignment(horizontal="right")
    for ci in range(1, len(cols) + 1):
        ws.column_dimensions[get_column_letter(ci)].width = 12
    ws.freeze_panes = "C3"
    wb.save(OUT / "總表.xlsx")
    C = S[S["行政區"] == "全市"].set_index("年")
    # 圖1：全市
    fig, axs = plt.subplots(1, 2, figsize=(13, 5.6), gridspec_kw={"width_ratios": [1.25, 1]})
    ax = axs[0]; bottom = np.zeros(len(C))
    for b, col in zip(BANDS, BC):
        v = C[b + "%"].to_numpy()
        ax.bar([str(y) for y in C.index], v, bottom=bottom, color=col, label=b, edgecolor="white", linewidth=0.5)
        for i, (x0, w) in enumerate(zip(bottom, v)):
            if w >= 6:
                ax.text(i, x0 + w / 2, f"{w:.0f}", ha="center", va="center", fontsize=8, color="white" if col in BC[2:] else "#222")
        bottom += v
    ax.set_ylim(0, 100); ax.set_ylabel("占比（%）"); ax.set_title("總樓層帶占比（房地買賣）", fontsize=11, loc="left")
    ax.legend(ncol=5, loc="upper center", bbox_to_anchor=(0.5, -0.08), frameon=False, fontsize=8.5)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax2 = axs[1]
    ax2.plot(C.index, C["11層以上%"], marker="o", color="#B2182B", label="11 層以上占比（%）")
    ax2.plot(C.index, C["26層以上%"] if "26層以上%" in C else C["26層以上%"], marker="s", color="#12385F", label="26 層以上占比（%）")
    for y, v in C["11層以上%"].items():
        ax2.annotate(f"{v:.1f}", (y, v), textcoords="offset points", xytext=(0, 6), ha="center", fontsize=8, color="#B2182B")
    ax2.set_ylabel("占比（%）"); ax2.set_ylim(0, max(60, C["11層以上%"].max() * 1.15)); ax2.set_xticks(YEARS)
    ax3 = ax2.twinx(); ax3.bar(C.index, C["樓層中位數"], alpha=0.18, color="#6FA3D0", width=0.55, label="樓層中位數（右軸）"); ax3.set_ylim(0, 14); ax3.set_ylabel("樓層中位數")
    for y, v in C["樓層中位數"].items():
        ax3.text(y, 0.4, f"{v:.0f}", ha="center", fontsize=8, color="#3472AD")
    h1, l1 = ax2.get_legend_handles_labels(); h2, l2 = ax3.get_legend_handles_labels()
    ax2.legend(h1 + h2, l1 + l2, loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=3, frameon=False, fontsize=8.5)
    ax2.set_title("11 層以上與 26 層以上占比、樓層中位數", fontsize=11, loc="left")
    fig.suptitle("臺北市房地買賣的樓層結構年度變化（全市，105～114 年）", fontsize=13.5, y=0.99)
    fig.text(0.5, 0.005, "資料：內政部實價登錄房地買賣（含房地者，總樓層可解析）", ha="center", fontsize=8, color="#555")
    fig.tight_layout(rect=(0, 0.02, 1, 0.95)); save(fig, "圖1_全市樓層結構")
    # 圖2：各區 11 層以上占比
    fig, axs = plt.subplots(3, 4, figsize=(13.5, 8.6), sharex=True, sharey=True)
    for ax, d in zip(axs.ravel(), DIST):
        s = S[S["行政區"] == d].set_index("年")
        ax.plot(C.index, C["11層以上%"], color="#999", ls="--", lw=1, label="全市")
        ax.plot(s.index, s["11層以上%"], color="#B2182B", marker="o", ms=3, lw=1.6)
        ax.set_title(f"{d}（樓層中位 {s['樓層中位數'].median():.0f}；均 {s['11層以上%'].mean():.0f}%）", fontsize=9.5)
        ax.set_ylim(0, 80); ax.grid(axis="y", color="#e6e6e6", lw=0.6); ax.tick_params(labelsize=8)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
    for ax in axs[-1]:
        ax.set_xticks([105, 107, 109, 111, 113])
    fig.suptitle("各行政區 11 層以上成交占比（%，紅線；灰虛線為全市）", fontsize=13.5, y=0.995)
    fig.text(0.5, 0.005, "資料：內政部實價登錄房地買賣", ha="center", fontsize=8, color="#555")
    fig.tight_layout(rect=(0, 0.015, 1, 0.97)); save(fig, "圖2_各區11層以上占比")
    # 圖3：各區總樓層帶 年度堆疊
    fig, axs = plt.subplots(3, 4, figsize=(13.5, 8.8), sharex=True, sharey=True)
    for ax, d in zip(axs.ravel(), DIST):
        s = S[S["行政區"] == d].set_index("年").reindex(YEARS); bottom = np.zeros(len(s))
        for b, col in zip(BANDS, BC):
            v = s[b + "%"].fillna(0).to_numpy(); ax.bar(YEARS, v, bottom=bottom, color=col, width=0.85, linewidth=0); bottom += v
        ax.set_title(d, fontsize=10); ax.set_ylim(0, 100); ax.tick_params(labelsize=8)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
    for ax in axs[-1]:
        ax.set_xticks([105, 107, 109, 111, 113])
    fig.legend([plt.Rectangle((0, 0), 1, 1, color=c) for c in BC], BANDS, loc="lower center", ncol=5, frameon=False, fontsize=9)
    fig.suptitle("各行政區總樓層帶占比的年度變化（%）", fontsize=13.5, y=0.995)
    fig.tight_layout(rect=(0, 0.04, 1, 0.97)); save(fig, "圖3_各區總樓層帶年度")
    # 圖4：建物型態（110 年起）
    T = S[(S["年"] >= 110)]
    fig, axs = plt.subplots(1, 2, figsize=(13, 5.8), gridspec_kw={"width_ratios": [1, 1.25]})
    ax = axs[0]; Ct = T[T["行政區"] == "全市"].set_index("年"); bottom = np.zeros(len(Ct))
    for ty, col in zip(TYPES, TC):
        v = Ct[ty + "%"].to_numpy(); ax.bar([str(y) for y in Ct.index], v, bottom=bottom, color=col, label=ty, edgecolor="white", linewidth=0.5)
        for i, (x0, w) in enumerate(zip(bottom, v)):
            if w >= 5:
                ax.text(i, x0 + w / 2, f"{w:.0f}", ha="center", va="center", fontsize=8.5, color="white" if col in ("#3472AD", "#E45756") else "#222")
        bottom += v
    ax.set_ylim(0, 100); ax.set_title("全市建物型態占比（110～114 年）", fontsize=11, loc="left"); ax.set_ylabel("占比（%）")
    ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.07), frameon=False, fontsize=8.5)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    d5 = z[(z["年"] >= 110) & z["型態"].isin(TYPES)]
    P = pd.crosstab(d5["區"], d5["型態"], normalize="index").reindex(DIST)[TYPES] * 100
    P = P.sort_values("住宅大樓")
    ax = axs[1]; left = np.zeros(len(P))
    for ty, col in zip(TYPES, TC):
        ax.barh(P.index, P[ty], left=left, color=col, label=ty, edgecolor="white", linewidth=0.5)
        for i, (x0, w) in enumerate(zip(left, P[ty])):
            if w >= 6:
                ax.text(x0 + w / 2, i, f"{w:.0f}", ha="center", va="center", fontsize=8.5, color="white" if col in ("#3472AD", "#E45756") else "#222")
        left += P[ty].to_numpy()
    ax.set_xlim(0, 100); ax.set_title("各行政區建物型態占比（110～114 年合計，依住宅大樓占比排序）", fontsize=11, loc="left")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    fig.suptitle("臺北市房地買賣的建物型態（110 年起分類一致）", fontsize=13.5, y=0.99)
    fig.text(0.5, 0.005, "資料：內政部實價登錄房地買賣；型態僅計公寓、華廈、住宅大樓、透天厝（110 年起平台分類收斂）", ha="center", fontsize=8, color="#555")
    fig.tight_layout(rect=(0, 0.02, 1, 0.95)); save(fig, "圖4_建物型態")
    # 摘要
    print("全市年度：")
    print(C[["房地買賣筆數", "樓層中位數", "11層以上%"] + [b + "%" for b in BANDS]].round(1).to_string())
    print("全市型態：")
    print(Ct[[t + "%" for t in TYPES]].round(1).to_string())
    for d in DIST:
        s = S[S["行政區"] == d].set_index("年")
        a = z[(z["區"] == d) & z["年"].between(106, 108)]; b_ = z[(z["區"] == d) & z["年"].between(112, 114)]
        print(f"{d}: 11層以上 106-108 {(a['樓層數'] >= 11).mean() * 100:.1f}% → 112-114 {(b_['樓層數'] >= 11).mean() * 100:.1f}%；樓層中位 {a['樓層數'].median():.0f}→{b_['樓層數'].median():.0f}；26層以上 {(a['樓層數'] >= 26).mean() * 100:.1f}→{(b_['樓層數'] >= 26).mean() * 100:.1f}%")
    t5 = z[(z["年"] >= 110) & z["型態"].isin(TYPES)]
    print("110-114 型態占比（各區）"); print((pd.crosstab(t5["區"], t5["型態"], normalize="index").reindex(DIST)[TYPES] * 100).round(1).to_string())
    print("樓層最大值", int(z["樓層數"].max()), "；30 層以上筆數", int((z["樓層數"] >= 30).sum()), "；5 層以下占比", round((z["樓層數"] <= 5).mean() * 100, 1))


if __name__ == "__main__":
    main()
