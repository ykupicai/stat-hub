"""把下載的公有土地圖層（PublicLand，148,017 個地號）轉成 shp，並印出摘要。
輸入：資料庫/原始檔/臺北市公有土地_PublicLand/page_*.json（fetch_臺北市公有土地圖層.py；EPSG:3826）
輸出：案件/臺北市_不動產交易分析/公有土地/臺北市公有土地.shp（保留全部原欄位；欄位名超過 10 字元者由 shp 自動截斷）
執行：python scripts/build_臺北市公有土地_shp.py
"""
import glob
import importlib.util
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("age", ROOT / "scripts" / "build_臺北市_行政區屋齡_地政局圖層.py")
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
RAW = ROOT / "資料庫" / "原始檔" / "臺北市公有土地_PublicLand"
OUT = ROOT / "案件" / "臺北市_不動產交易分析" / "公有土地"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    recs, geoms = [], []
    for f in sorted(glob.glob(str(RAW / "page_*.json"))):
        for ft in json.load(open(f, encoding="utf-8"))["features"]:
            recs.append(ft["attributes"]); geoms.append(M.rings_to_geom(ft["geometry"]["rings"]))
    g = gpd.GeoDataFrame(pd.DataFrame(recs), geometry=geoms, crs=3826)
    assert len(g) == 148017 and g["OBJECTID"].is_unique, len(g)
    g.to_file(OUT / "臺北市公有土地.shp", driver="ESRI Shapefile", encoding="utf-8")
    print("地號", len(g), "；欄位", [c for c in g.columns if c != "geometry"])
    a = g.groupby("LANDTYPE2").agg(n=("OBJECTID", "size"), 公頃=("AA10_1", lambda s: s.sum() / 1e4)).sort_values("n", ascending=False)
    print(a.round(1).to_string())
    t = g.groupby("PL46_N").agg(n=("OBJECTID", "size"), 公頃=("AA10_1", lambda s: s.sum() / 1e4)).sort_values("公頃", ascending=False)
    print(t.round(1).to_string())
    print("空地(IS_VACANTLOT=Y)", int((g["IS_VACANTLOT"] == "Y").sum()), "；面積公頃", round(g.loc[g["IS_VACANTLOT"] == "Y", "AA10_1"].sum() / 1e4, 1))
    print("管理機關前 6（地號數）", g["MNGR"].value_counts().head(6).to_dict())
    print("地目前 6", g["AF09"].value_counts().head(6).to_dict())


if __name__ == "__main__":
    main()
