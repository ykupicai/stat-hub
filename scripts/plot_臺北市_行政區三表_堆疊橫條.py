"""臺北市行政區三表（analyze_臺北市_行政區三表_105至114.py 的輸出）→ 100% 堆疊橫條圖。

輸入：案件/臺北市_不動產交易分析/行政區三表_105至114/表*.csv（筆數表）
輸出：同資料夾 圖T1～圖T4 PNG。
口徑：表2、表3 的占比分母排除「無建物（純土地或純車位）」與「未填」，只比較有建物的交易；表1 以土地筆數為分母。
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "案件" / "臺北市_不動產交易分析" / "行政區三表_105至114"
plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "PMingLiU", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False
NOBLD = "（無建物：純土地或純車位）"
BLANK = "（未填）"
SRC = "資料：內政部不動產交易實價查詢服務網，臺北市不動產買賣，交易日 105～114 年"


def load(name):
    t = pd.read_csv(D / f"{name}.csv", index_col=0, encoding="utf-8-sig")
    return t.drop(index="合計", errors="ignore")


def stack(t, cats, colors, title, sub, fname, sort_by, note="", label_min=5.0):
    """t：列＝類別、欄＝行政區＋全市。畫各行政區（依 sort_by 由高到低）與全市的 100% 堆疊橫條。"""
    t = t.reindex(cats).fillna(0)
    pct = t.div(t.sum(axis=0), axis=1) * 100
    order = pct.drop(columns="全市").loc[sort_by].sort_values(ascending=True).index.tolist()  # barh 由下往上畫
    cols = ["全市"] + order
    fig, ax = plt.subplots(figsize=(10, 7.2))
    left = pd.Series(0.0, index=cols)
    for c, col in zip(cats, colors):
        v = pct.loc[c, cols]
        ax.barh(cols, v, left=left, color=col, edgecolor="white", linewidth=0.6, label=c, height=0.72)
        for y, (x0, w) in enumerate(zip(left, v)):
            if w >= label_min:
                dark = sum(int(col[i:i + 2], 16) for i in (1, 3, 5)) < 400
                ax.text(x0 + w / 2, y, f"{w:.0f}" if w >= 10 else f"{w:.1f}", ha="center", va="center", fontsize=8,
                        color="white" if dark else "#222")
        left = left + v
    ax.set_xlim(0, 100)
    ax.set_xlabel("占比（%）")
    ax.axhline(0.5, color="#555", lw=0.8, ls=":")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(ncol=min(len(cats), 6), loc="upper center", bbox_to_anchor=(0.5, -0.1), frameon=False, fontsize=9)
    ax.set_title(title + "\n" + sub, fontsize=12, loc="left")
    fig.text(0.01, 0.01, SRC + (("　" + note) if note else ""), fontsize=7, color="#555")
    fig.tight_layout(rect=(0, 0.025, 1, 1))
    fig.savefig(D / fname, dpi=150)
    plt.close(fig)


def main():
    # 圖T1 使用分區
    t = load("表1_行政區×使用分區_土地筆數")
    t.loc["其他"] = t.loc[["保護區", "農業區", "非都市土地", "（未標示）"]].sum()
    stack(t, ["住宅區", "商業區", "公共設施用地", "其他都市分區", "工業區", "其他"],
          ["#4C78A8", "#F58518", "#9D9D9D", "#B279A2", "#54A24B", "#E0C060"],
          "圖T1 臺北市各行政區：交易所涉土地的使用分區組成", "單位：土地筆數（交易所附地號列數）；依商業區占比排序",
          "圖T1_使用分區_堆疊橫條.png", "商業區", note="其他＝保護區、農業區、非都市土地、未標示")

    # 圖T2 建物用途
    t = load("表2_行政區×建物用途_交易筆數").drop(index=[NOBLD, BLANK])
    main_c = ["住家用", "商業用", "辦公用", "工業用", "住商用"]
    t.loc["其他用途"] = t.drop(index=main_c).sum()
    stack(t, main_c + ["其他用途"], ["#4C78A8", "#F58518", "#E45756", "#54A24B", "#B279A2", "#BBBBBB"],
          "圖T2 臺北市各行政區：有建物交易的主要用途組成", "單位：交易筆數；排除純土地或純車位與用途未填；依住家用占比排序",
          "圖T2_建物用途_堆疊橫條.png", "住家用", note="其他用途含見使用執照、見其他登記事項、農業用等")

    # 圖T2b 非住家用途（放大）
    u = t.loc[["商業用", "辦公用", "工業用", "住商用"]]
    tot = t.loc[main_c + ["其他用途"]].sum()  # 分母＝各用途加其他用途（t 內另含已併入「其他用途」的細項列，不可重複計）
    u2 = u.div(tot, axis=1) * 100
    order = u2.drop(columns="全市").sum().sort_values().index.tolist()
    cols = ["全市"] + order
    fig, ax = plt.subplots(figsize=(10, 6))
    left = pd.Series(0.0, index=cols)
    for c, col in zip(u2.index, ["#F58518", "#E45756", "#54A24B", "#B279A2"]):
        v = u2.loc[c, cols]
        ax.barh(cols, v, left=left, color=col, edgecolor="white", linewidth=0.6, label=c, height=0.72)
        for y, (x0, w) in enumerate(zip(left, v)):
            if w >= 1.5:
                ax.text(x0 + w / 2, y, f"{w:.1f}", ha="center", va="center", fontsize=8, color="white")
        left = left + v
    for y, name in enumerate(cols):
        ax.text(left[name] + 0.3, y, f"{left[name]:.1f}", va="center", fontsize=8.5, color="#222", weight="bold")
    ax.set_xlim(0, max(left) * 1.1)
    ax.axhline(0.5, color="#555", lw=0.8, ls=":")
    ax.set_xlabel("占有建物交易的比例（%）")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.1), frameon=False, fontsize=9)
    ax.set_title("圖T2b 臺北市各行政區：非住家用途建物交易占比\n依非住家合計排序（分母＝有建物且用途已填的交易）", fontsize=12, loc="left")
    fig.text(0.01, 0.01, SRC, fontsize=7, color="#555")
    fig.tight_layout(rect=(0, 0.025, 1, 1))
    fig.savefig(D / "圖T2b_非住家用途_堆疊橫條.png", dpi=150)
    plt.close(fig)

    # 圖T3 總樓層
    t = load("表3a_行政區×建物總樓層_交易筆數").drop(index=[NOBLD, BLANK])
    cats = ["5層以下", "6-10層", "11-15層", "16-25層", "26層以上"]
    stack(t, cats, ["#DCE9F5", "#A9C8E4", "#6FA3D0", "#3472AD", "#12385F"],
          "圖T3 臺北市各行政區：交易建物的總樓層分布", "單位：交易筆數；排除純土地或純車位與樓層未填；依 11 層以上占比排序",
          "圖T3_總樓層_堆疊橫條.png", "16-25層", note="")
    # 依 11 層以上排序需合併三欄，另行覆寫
    pct = t.reindex(cats).div(t.sum(), axis=1) * 100
    hi = pct.loc[["11-15層", "16-25層", "26層以上"]].sum().drop("全市").sort_values()
    order = ["全市"] + hi.index.tolist()
    fig, ax = plt.subplots(figsize=(10, 7.2))
    left = pd.Series(0.0, index=order)
    colors = ["#DCE9F5", "#A9C8E4", "#6FA3D0", "#3472AD", "#12385F"]
    for c, col in zip(cats, colors):
        v = pct.loc[c, order]
        ax.barh(order, v, left=left, color=col, edgecolor="white", linewidth=0.6, label=c, height=0.72)
        for y, (x0, w) in enumerate(zip(left, v)):
            if w >= 5:
                ax.text(x0 + w / 2, y, f"{w:.0f}" if w >= 10 else f"{w:.1f}", ha="center", va="center", fontsize=8,
                        color="white" if col in colors[2:] else "#222")
        left = left + v
    ax.set_xlim(0, 100)
    ax.set_xlabel("占比（%）")
    ax.axhline(0.5, color="#555", lw=0.8, ls=":")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(ncol=5, loc="upper center", bbox_to_anchor=(0.5, -0.1), frameon=False, fontsize=9)
    ax.set_title("圖T3 臺北市各行政區：交易建物的總樓層分布\n單位：交易筆數；排除純土地或純車位與樓層未填；依 11 層以上合計排序", fontsize=12, loc="left")
    fig.text(0.01, 0.01, SRC, fontsize=7, color="#555")
    fig.tight_layout(rect=(0, 0.025, 1, 1))
    fig.savefig(D / "圖T3_總樓層_堆疊橫條.png", dpi=150)
    plt.close(fig)

    # 圖T4 交易所在樓層
    t = load("表3b_行政區×交易所在樓層_交易筆數").drop(index=[NOBLD, BLANK])
    stack(t, ["地下層", "1樓", "2-5樓", "6-10樓", "11樓以上", "整棟(全)"],
          ["#7A7A7A", "#F2CF6B", "#A9C8E4", "#6FA3D0", "#12385F", "#E45756"],
          "圖T4 臺北市各行政區：交易標的所在樓層", "單位：交易筆數；排除純土地或純車位與樓層未填；依 6-10 樓占比排序",
          "圖T4_所在樓層_堆疊橫條.png", "6-10樓")


if __name__ == "__main__":
    main()
