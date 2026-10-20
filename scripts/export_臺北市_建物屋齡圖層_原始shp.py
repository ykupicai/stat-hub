"""把 BuildStat_Fage 圖層（已分頁下載於 資料庫/原始檔/臺北市建物屋齡_BuildStat_Fage/）原樣輸出成 shp：全部原欄位、原欄位名，EPSG:3826。

與 build_臺北市_行政區屋齡_地政局圖層.py 的差別：本檔不改欄位、不加行政區、不做統計。
輸出：案件/臺北市_不動產交易分析/行政區屋齡/現況_地政局圖層/原始圖層_BuildStat_Fage/BuildStat_Fage.shp
執行：python scripts/export_臺北市_建物屋齡圖層_原始shp.py
"""
import glob
import importlib.util
import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("age", ROOT / "scripts" / "build_臺北市_行政區屋齡_地政局圖層.py")
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
OUT = M.OUT / "原始圖層_BuildStat_Fage"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    recs, geoms = [], []
    for f in sorted(glob.glob(str(M.RAW / "page_*.json"))):
        j = json.load(open(f, encoding="utf-8"))
        for ft in j["features"]:
            recs.append(ft["attributes"])
            geoms.append(M.rings_to_geom(ft["geometry"]["rings"]))
    g = gpd.GeoDataFrame(pd.DataFrame(recs), geometry=geoms, crs=3826)
    assert len(g) == 152684 and g["OBJECTID"].is_unique
    g.to_file(OUT / "BuildStat_Fage.shp", driver="ESRI Shapefile", encoding="utf-8")
    back = gpd.read_file(OUT / "BuildStat_Fage.shp", encoding="utf-8")
    print("輸出", len(back), "筆；CRS", back.crs.to_epsg(), "；欄位", [c for c in back.columns if c != "geometry"])
    print("總面積 km2", round(back.area.sum() / 1e6, 1), "；範圍", [round(v) for v in back.total_bounds])


if __name__ == "__main__":
    main()
