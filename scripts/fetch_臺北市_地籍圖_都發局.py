"""下載臺北市地籍圖（都發局 zonemap.udd.gov.taipei 背後的 GeoServer WFS，圖層 Taipei:LAND-ALL-TWD97「台北市地籍圖」）。

欄位：sect_id 段碼、dist_name 行政區、sect_name 段名、land_no 地號、land_pnum 母號、land_snum 子號、dtmmapno／landmapno 圖號；EPSG:3826；約 421,843 個地號。
伺服器要求 Referer 為都發局網站（站內地圖本身的呼叫方式），其餘免登入。分頁 2,000 筆、間隔 1 秒、可續跑。
輸出：資料庫/原始檔/臺北市地籍圖_LAND-ALL/page_XXXXX.json
執行：python scripts/fetch_臺北市_地籍圖_都發局.py
"""
import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "資料庫" / "原始檔" / "臺北市地籍圖_LAND-ALL"
URL = "https://zonegeo.udd.gov.taipei/geoserver/Taipei/ows"
N, PAGE = 421843, 2000


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers.update({"Referer": "https://zonemap.udd.gov.taipei/", "User-Agent": "Mozilla/5.0"})
    t0 = time.time()
    for i, start in enumerate(range(0, N, PAGE)):
        f = OUT / f"page_{i:05d}.json"
        if f.exists() and f.stat().st_size > 100:
            continue
        for k in range(5):
            try:
                r = s.get(URL, params={"service": "WFS", "version": "1.0.0", "request": "GetFeature", "typeName": "Taipei:LAND-ALL-TWD97",
                                       "outputFormat": "application/json", "sortBy": "sect_id,land_pnum,land_snum", "startIndex": start, "maxFeatures": PAGE}, timeout=300)
                j = r.json()
                if not j.get("features"):
                    raise ValueError("空回應")
                break
            except Exception as e:  # noqa: BLE001
                print("重試", start, str(e)[:80], flush=True)
                time.sleep(15 * (k + 1))
        else:
            raise RuntimeError(f"offset {start} 下載失敗")
        f.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
        if i % 10 == 0:
            print(f"{start}+{len(j['features'])}（{time.time() - t0:.0f} 秒）", flush=True)
        time.sleep(1)
    print("完成", flush=True)


if __name__ == "__main__":
    main()
