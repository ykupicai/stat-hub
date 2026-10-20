"""把 RALIDs API 查到的私有人數併進 中山區_交易土地權屬.shp。

輸入：地號清單/中山區_私有人數API/ralids_raw.jsonl（fetch_中山區_私有人數_RALIDs.py）、中山區_權屬/中山區_交易土地權屬.shp
新增欄位：L_MANS（土地私有人數）、L_PAREA（土地私有面積 ㎡）、B_COUNT（建物登記筆數）、B_MANS（建物私有人數）、B_PAREA（建物私有面積）、R_NOTE（備註：公同共有、見其他登記）
輸出：覆寫 shp（舊版備份於 中山區_權屬/_備份_未含私有人數/）、更新 欄位說明.csv，並印出摘要
執行：python scripts/merge_中山區_私有人數.py
"""
import csv
import io
import json
import shutil
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
CASE = ROOT / "案件" / "臺北市_不動產交易分析"
OWN = CASE / "中山區_權屬"


def main():
    seg = {r["官方段名"]: r["官方段碼"] for r in csv.DictReader(open(CASE / "地號清單" / "地段對照.csv", encoding="utf-8-sig")) if r["官方段碼"]}
    raw = {}
    skipped = 0
    for l in open(CASE / "地號清單" / "中山區_私有人數API" / "ralids_raw.jsonl", encoding="utf-8", errors="replace"):
        if l.strip():
            try:
                j = json.loads(l); raw[j["code12"]] = j
            except (ValueError, KeyError):  # 兩個查詢程序曾同時寫檔，殘缺行略過（該地號會算成未查到）
                skipped += 1
    print("結果檔筆數", len(raw), "；殘缺行略過", skipped)
    g = gpd.read_file(OWN / "中山區_交易土地權屬.shp", encoding="utf-8")
    bk = OWN / "_備份_未含私有人數"
    if not bk.exists():
        bk.mkdir()
        for f in OWN.glob("中山區_交易土地權屬.*"):
            shutil.copy2(f, bk / f.name)

    def code(sec, lno):
        m, _, c = lno.partition("-")
        return seg[sec][2:] + f"{int(m):04d}{int(c or 0):04d}"
    recs = []
    for sec, lno in zip(g["SECTION"], g["LANDNO"]):
        j = raw.get(code(sec, lno))
        if j is None:
            recs.append({"L_MANS": np.nan, "L_PAREA": np.nan, "B_COUNT": np.nan, "B_MANS": np.nan, "B_PAREA": np.nan, "R_NOTE": "未查到"}); continue
        recs.append({"L_MANS": j["Lmans"], "L_PAREA": round(float(j["LPArea"] or 0), 2), "B_COUNT": j["BCount"], "B_MANS": j["Bmans"], "B_PAREA": round(float(j["BPArea"] or 0), 2),
                     "R_NOTE": (j.get("note") or "")[:120]})
    add = pd.DataFrame(recs, index=g.index)
    out = gpd.GeoDataFrame(pd.concat([g.drop(columns=[c for c in add.columns if c in g.columns]), add], axis=1), geometry="geometry", crs=g.crs)
    out.to_file(OWN / "中山區_交易土地權屬.shp", driver="ESRI Shapefile", encoding="utf-8")
    d = pd.read_csv(OWN / "欄位說明.csv", encoding="utf-8-sig")
    d = d[~d["欄位"].isin(add.columns)]
    new = pd.DataFrame({"欄位": list(add.columns), "說明": ["土地私有人數（RALIDs API；不含公有）", "土地私有面積（㎡）", "建物登記筆數", "建物私有人數", "建物私有面積（㎡）", "備註（公同共有、見其他登記）"]})
    pd.concat([d, new]).to_csv(OWN / "欄位說明.csv", index=False, encoding="utf-8-sig")
    ok = out[out["L_MANS"].notna()]
    print("shp 地號", len(out), "；有私有人數", len(ok), "；未查到", int(out["L_MANS"].isna().sum()))
    m = ok["L_MANS"]
    print("土地私有人數：中位數", float(m.median()), "；平均", round(float(m.mean()), 1), "；最大", int(m.max()), "；0 人（全公有）", int((m == 0).sum()), "；1 人", int((m == 1).sum()), "；2～5 人", int(m.between(2, 5).sum()),
          "；6～20 人", int(m.between(6, 20).sum()), "；21～50 人", int(m.between(21, 50).sum()), "；超過 50 人", int((m > 50).sum()))
    print("私有人數分位數", m.quantile([.25, .5, .75, .9, .99]).round(0).to_dict())
    print("依權屬類型的私有人數中位數", ok.groupby("TYPE")["L_MANS"].median().to_dict())
    print("依公有分類的私有人數中位數", ok.groupby("PUB_CLS")["L_MANS"].median().to_dict())
    print("面積與人數相關（私有面積>0）", round(float(np.corrcoef(ok.loc[ok["L_PAREA"] > 0, "REG_AREA"], ok.loc[ok["L_PAREA"] > 0, "L_MANS"])[0, 1]), 2))
    big = ok.sort_values("L_MANS", ascending=False).head(5)[["SECTION", "LANDNO", "L_MANS", "B_COUNT", "B_MANS", "REG_AREA"]]
    print(big.to_string(index=False))
    print("備註含公同共有／見其他登記者", int(ok["R_NOTE"].str.contains("公同共有:[1-9]|見其他登記:[1-9]", regex=True).sum()))


if __name__ == "__main__":
    main()
