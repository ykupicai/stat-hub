"""把內政部 getLandInfo 回傳的公有地權屬（land.userList）併進 中山區_交易土地權屬.shp。

輸入：地號清單/中山區_權屬API/ralid_raw.jsonl（fetch_中山區_權屬_NLSC.py 產生）、中山區_權屬/中山區_交易土地權屬.shp
新增欄位：PUB（1＝有公有所有權人）、PUB_CLS（權屬分類）、PUB_SHARE（公有持分合計%）、OWN_TYPE（類別，如 國有、直轄市有）、OWN_NAME（所有權人）、MANAGER（管理機關）、N_OWNER（公有所有權人數）
說明：API 只回傳公有土地的所有權人；私有地回傳空值，故「私有」是由空值推定；公私共有者只看得到公有部分，以公有持分合計是否達 100% 區分。
輸出：覆寫 中山區_權屬/中山區_交易土地權屬.shp（舊版備份於 中山區_權屬/_備份_未含公有地/）、更新 欄位說明.csv
執行：python scripts/merge_中山區_權屬公有地.py
"""
import csv
import io
import json
import shutil
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
CASE = ROOT / "案件" / "臺北市_不動產交易分析"
OWN = CASE / "中山區_權屬"


def main():
    seg = {r["官方段名"]: r["官方段碼"] for r in csv.DictReader(open(CASE / "地號清單" / "地段對照.csv", encoding="utf-8-sig")) if r["官方段碼"]}
    raw = {}
    for l in open(CASE / "地號清單" / "中山區_權屬API" / "ralid_raw.jsonl", encoding="utf-8"):
        if l.strip():
            j = json.loads(l); raw[j["14碼"]] = j
    g = gpd.read_file(OWN / "中山區_交易土地權屬.shp", encoding="utf-8")
    # 備份舊版
    bk = OWN / "_備份_未含公有地"
    if not bk.exists():
        bk.mkdir()
        for f in OWN.glob("中山區_交易土地權屬.*"):
            shutil.copy2(f, bk / f.name)

    def code(sec, lno):
        m, _, c = lno.partition("-")
        return seg[sec] + f"{int(m):04d}{int(c or 0):04d}"

    recs = []
    for sec, lno in zip(g["SECTION"], g["LANDNO"]):
        j = raw.get(code(sec, lno))
        if j is None or not j["有資料"]:
            recs.append({"PUB": None, "PUB_CLS": "無資料", "PUB_SHARE": None, "OWN_TYPE": "", "OWN_NAME": "", "MANAGER": "", "N_OWNER": 0}); continue
        ul = j["userList"] or []
        if not ul:
            recs.append({"PUB": 0, "PUB_CLS": "非公有（API 無公有所有權人）", "PUB_SHARE": 0.0, "OWN_TYPE": "", "OWN_NAME": "", "MANAGER": "", "N_OWNER": 0}); continue
        sh = 0.0
        for u in ul:
            try:
                sh += float(u["numerator"]) / float(u["denominator"])
            except (TypeError, ValueError, ZeroDivisionError):
                pass
        sh = min(sh, 1.0)
        recs.append({"PUB": 1, "PUB_CLS": "全部公有" if sh >= 0.9999 else "公私共有（公有持分未滿 100%）", "PUB_SHARE": round(sh * 100, 4),
                     "OWN_TYPE": "、".join(dict.fromkeys(u.get("type") or "" for u in ul))[:100], "OWN_NAME": "、".join(dict.fromkeys(u.get("name") or "" for u in ul))[:100],
                     "MANAGER": "、".join(dict.fromkeys(u.get("manage") or "" for u in ul))[:200], "N_OWNER": len(ul)})
    add = pd.DataFrame(recs, index=g.index)
    out = pd.concat([g.drop(columns=[c for c in add.columns if c in g.columns]), add], axis=1)
    out = gpd.GeoDataFrame(out, geometry="geometry", crs=g.crs)
    out.to_file(OWN / "中山區_交易土地權屬.shp", driver="ESRI Shapefile", encoding="utf-8")
    d = pd.read_csv(OWN / "欄位說明.csv", encoding="utf-8-sig")
    d = d[~d["欄位"].isin(add.columns)]
    new = pd.DataFrame({"欄位": list(add.columns), "說明": ["是否有公有所有權人（1／0；無資料為空）", "權屬分類：全部公有／公私共有／非公有（由空值推定）／無資料", "公有持分合計（%）", "公有所有權人類別（國有、直轄市有、鄉(鎮、市)有）",
                                                    "公有所有權人名稱", "管理機關", "公有所有權人數"]})
    pd.concat([d, new]).to_csv(OWN / "欄位說明.csv", index=False, encoding="utf-8-sig")
    print("shp 地號", len(out), "；欄位", [c for c in out.columns if c != "geometry"])
    print("權屬分類", out["PUB_CLS"].value_counts().to_dict())
    pub = out[out["PUB"] == 1]
    print("公有地號", len(pub), f"（占有資料者 {len(pub) / out['PUB'].notna().sum():.1%}）")
    print("類別", pub["OWN_TYPE"].value_counts().to_dict())
    print("管理機關(前8)", pub["MANAGER"].value_counts().head(8).to_dict())
    print("公有持分合計 中位數/最大", pub["PUB_SHARE"].median(), pub["PUB_SHARE"].max(), "；全部公有", int((pub["PUB_CLS"] == "全部公有").sum()))
    print("權屬類型(原) × 是否公有", pd.crosstab(out["TYPE"], out["PUB_CLS"]).to_string())


if __name__ == "__main__":
    main()
