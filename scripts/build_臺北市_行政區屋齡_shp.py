"""臺北市各行政區屋齡（建築使用執照）→ 行政區面 shp ＋ 門牌點 shp。

資料：github.com/imdataman/taipei-house-age-map（已 clone 到 ../taipei-house-age-map）的 台北市建築年份加經緯度.csv。
  原作者以臺北市政府開放資料的建築使用執照（新建）整理：同一門牌取最新一筆、地址轉座標，age＝2016－使照年。
口徑：
  * 單位＝門牌（value 唯一）；只含「新建」且地址轉座標成功者（約 87%），未成功者原檔無使照日期，無法歸區。
  * 資料涵蓋使照年 1949～2016，2017 年以後完工的建物不在其中；屋齡以 2016 為基準（AGE_*），要換算成其他年份請用 YR_*。
  * 行政區以地址文字（TOWN 欄）歸屬，與座標落點另做一致性檢查。
  * 行政區界線沿用 案件/臺北市_不動產交易分析/行政區建物分析/shp（內政部鄉鎮市區界 108/11，EPSG:3826）。
輸出：案件/臺北市_不動產交易分析/行政區屋齡/（shp、CSV、說明.md）
執行：python scripts/build_臺北市_行政區屋齡_shp.py
"""
import io
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT.parent / "taipei-house-age-map" / "台北市建築年份加經緯度.csv"
BND = ROOT / "案件" / "臺北市_不動產交易分析" / "行政區建物分析" / "shp" / "臺北市行政區_建物交易分析.shp"
OUT = ROOT / "案件" / "臺北市_不動產交易分析" / "行政區屋齡"
REF = 2016
BANDS = [(0, 10, "P_0_10"), (11, 20, "P_11_20"), (21, 30, "P_21_30"), (31, 40, "P_31_40"), (41, 50, "P_41_50"), (51, 999, "P_51UP")]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    a = pd.read_csv(SRC, encoding="utf-8", low_memory=False)
    n_all = len(a)
    a = a[a["TOWN"].notna() & a["date"].notna() & a["X"].notna()].copy()
    a["yr"] = pd.to_datetime(a["date"]).dt.year
    a["age"] = REF - a["yr"]
    assert (a["age"] == a["age"].astype(int)).all() and (a["age"] == (REF - a["yr"])).all()
    chk = pd.read_csv(SRC, encoding="utf-8", low_memory=False, usecols=["age", "date"]).dropna()
    assert (chk["age"] == REF - pd.to_datetime(chk["date"]).dt.year).all(), "原檔 age 與 2016－年 不一致"
    print(f"原檔 {n_all:,} 列；可用（有行政區、使照日期、座標）{len(a):,} 列（{len(a) / n_all:.1%}）")

    bnd = gpd.read_file(BND, encoding="utf-8")[["TOWNID", "TOWNNAME", "geometry"]].to_crs(3826)
    g = a.groupby("TOWN")
    st = pd.DataFrame({
        "N_ADDR": g.size(),
        "N_LIC": g["id"].nunique(),
        "YR_MIN": g["yr"].min(), "YR_MAX": g["yr"].max(),
        "YR_MED": g["yr"].median(),
        "AGE_MED": g["age"].median(), "AGE_AVG": g["age"].mean().round(1),
        "AGE_P25": g["age"].quantile(0.25), "AGE_P75": g["age"].quantile(0.75),
    })
    for lo, hi, name in BANDS:
        st[name] = g["age"].apply(lambda s, lo=lo, hi=hi: round(s.between(lo, hi).mean() * 100, 1))
    st["P_GE41"] = (st["P_41_50"] + st["P_51UP"]).round(1)
    lic = a.drop_duplicates("id").groupby("TOWN")["yr"].median().rename("YR_MED_LIC")
    st = st.join(lic)
    st.index.name = "TOWNNAME"
    gdf = bnd.merge(st.reset_index(), on="TOWNNAME", how="left")
    assert gdf["N_ADDR"].notna().all() and len(gdf) == 12, "行政區對不上"
    gdf["REF_YEAR"] = REF
    shp_dir = OUT / "shp"
    shp_dir.mkdir(exist_ok=True)
    gdf.to_file(shp_dir / "臺北市行政區_屋齡.shp", driver="ESRI Shapefile", encoding="utf-8")
    desc = {
        "TOWNID": "行政區代碼", "TOWNNAME": "行政區", "N_ADDR": "門牌數（新建、地址轉座標成功者）", "N_LIC": "使用執照件數（不重複）",
        "YR_MIN": "最早使照年（西元）", "YR_MAX": "最晚使照年（西元，資料至 2016）", "YR_MED": "使照年中位數（以門牌計）",
        "AGE_MED": "屋齡中位數（年，2016 為基準）", "AGE_AVG": "屋齡平均（年，2016 為基準）", "AGE_P25": "屋齡第 25 百分位", "AGE_P75": "屋齡第 75 百分位",
        "P_0_10": "屋齡 0～10 年占比%", "P_11_20": "11～20 年占比%", "P_21_30": "21～30 年占比%", "P_31_40": "31～40 年占比%",
        "P_41_50": "41～50 年占比%", "P_51UP": "51 年以上占比%", "P_GE41": "屋齡 41 年以上占比%", "YR_MED_LIC": "使照年中位數（以使照件數計）",
        "REF_YEAR": "屋齡基準年"}
    pd.DataFrame({"欄位": list(desc), "說明": list(desc.values())}).to_csv(shp_dir / "欄位說明.csv", index=False, encoding="utf-8-sig")
    gdf.drop(columns="geometry").to_csv(OUT / "行政區屋齡統計.csv", index=False, encoding="utf-8-sig")

    # 門牌點 shp ＋ 行政區一致性檢查
    pts = gpd.GeoDataFrame(
        a[["FULL_ADDR", "TOWN", "VILLAGE", "id", "yr", "age"]].rename(columns={"FULL_ADDR": "ADDR", "TOWN": "TOWNNAME", "VILLAGE": "VILLAGE", "id": "LIC_ID", "yr": "YEAR"}),
        geometry=gpd.points_from_xy(a["X"], a["Y"]), crs=3826)
    pts = pts.rename(columns={"age": "AGE16"})
    joined = gpd.sjoin(pts, bnd[["TOWNNAME", "geometry"]].rename(columns={"TOWNNAME": "T_GEO"}), how="left", predicate="within")
    joined = joined[~joined.index.duplicated()]
    agree = (joined["T_GEO"] == joined["TOWNNAME"])
    print(f"座標落點與地址行政區一致：{agree.mean():.1%}；落在界外：{joined['T_GEO'].isna().sum():,}；不一致：{(~agree & joined['T_GEO'].notna()).sum():,}")
    pts["T_GEO"] = joined["T_GEO"].fillna("")
    pts.to_file(shp_dir / "臺北市門牌_屋齡點.shp", driver="ESRI Shapefile", encoding="utf-8")

    print(gdf.drop(columns="geometry").set_index("TOWNNAME").round(1).to_string())
    return len(a), n_all, agree.mean(), int(joined["T_GEO"].isna().sum())


if __name__ == "__main__":
    main()
