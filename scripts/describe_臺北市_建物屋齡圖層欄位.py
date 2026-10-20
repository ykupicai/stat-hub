"""列出 BuildStat_Fage 圖層各欄位的型態、值域、範例（輸出 CSV，並印出）。
輸入：資料庫/原始檔/臺北市建物屋齡_BuildStat_Fage/page_*.json　輸出：行政區屋齡/現況_地政局圖層/欄位資料表_BuildStat_Fage.csv
"""
import glob
import io
import json
import sys
from pathlib import Path

import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "資料庫" / "原始檔" / "臺北市建物屋齡_BuildStat_Fage"
OUT = ROOT / "案件" / "臺北市_不動產交易分析" / "行政區屋齡" / "現況_地政局圖層"
MEANING = {  # 欄位意義：依樣本與分布推定，未經地政局書面確認
    "OBJECTID": "流水號", "OBJECTID_1": "流水號（重複）", "KCNT": "段名（含小段）", "LandNo": "地號（母-子）", "THEKEY": "段代碼＋地號 8 碼", "THEKEY1": "同 THEKEY",
    "UNIT": "地政事務所代碼（AA～AF）", "AA45": "地政事務所代碼（單字）", "AA46": "段代碼（兩碼）", "AA48": "小段代碼", "AA49": "地號 8 碼（母 4＋子 4）",
    "AA05": "（推測）日期欄，民國年月日 7 碼，同一值常出現在整批地號", "AA06": "（不明）兩碼代碼", "AA08": "（不明）單字代碼", "AA09": "（不明）多為「-」",
    "AA10": "（推測）土地登記面積㎡（與 Shape_Area 不同）", "AA11": "（不明）多為「-」", "AA12": "（不明）多為「-」",
    "AA16": "（推測）公告土地現值，元/㎡", "AA17": "（推測）公告地價，元/㎡", "TWD97E": "地號代表點 X（TWD97）", "TWD97N": "地號代表點 Y（TWD97）",
    "fageavg": "該地號建物屋齡平均（年）", "fagemax": "該地號建物屋齡最大（年）", "fagemin": "該地號建物屋齡最小（年）", "sumdd08": "（推測）該地號建物面積合計（㎡）",
    "ct": "（推測）該地號建物筆數", "DD12": "（推測）建物主要構造或用途代碼", "DD13H": "（推測）建物層數", "Shape_Length": "周長（m）", "Shape_Area": "面積（㎡）", "mapscale": "（空白）",
}


def main():
    rows = []
    for f in sorted(glob.glob(str(RAW / "page_*.json"))):
        for ft in json.load(open(f, encoding="utf-8"))["features"]:
            rows.append(ft["attributes"])
    df = pd.DataFrame(rows)
    out = []
    for c in df.columns:
        s = df[c]
        blank = int((s.isna() | (s.astype(str).str.strip().isin(["", "-"]))).sum())
        num = pd.api.types.is_numeric_dtype(s)
        out.append({"欄位": c, "型態": "數值" if num else "文字", "不重複值數": s.nunique(), "空白或「-」筆數": blank,
                    "最小": s.min() if num else "", "最大": s.max() if num else "", "範例": " ｜ ".join(map(str, s.drop_duplicates().head(3))),
                    "意義（推定）": MEANING.get(c, "")})
    t = pd.DataFrame(out)
    t.to_csv(OUT / "欄位資料表_BuildStat_Fage.csv", index=False, encoding="utf-8-sig")
    print(f"{len(df):,} 筆、{len(t)} 欄")
    print(t.drop(columns=["最小", "最大"]).to_string(index=False, max_colwidth=36))
    print(t[t["型態"] == "數值"][["欄位", "最小", "最大"]].to_string(index=False))


if __name__ == "__main__":
    main()
