"""下載臺北市都市計畫使用分區圖（都發局 zonemap.udd.gov.taipei 背後的 GeoServer WFS，圖層 Taipei:ublock97-TWD97「台北市使用分區圖」）。

欄位：usecod 分區代碼、usenam 簡稱、usemem 全名、usecor 色碼、usekin 大類、usetxt 標註；EPSG:3826；17,039 個多邊形。
伺服器要求 Referer 為都發局網站（站內地圖本身的呼叫方式），其餘免登入。分頁 2,000 筆、間隔 1 秒。
輸出：資料庫/原始檔/臺北市使用分區圖_ublock97/page_XXX.json（可續跑）
執行：python scripts/fetch_臺北市_使用分區圖_都發局.py
"""
import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "資料庫" / "原始檔" / "臺北市使用分區圖_ublock97"
URL = "https://zonegeo.udd.gov.taipei/geoserver/Taipei/ows"
N, PAGE = 17039, 2000


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers.update({"Referer": "https://zonemap.udd.gov.taipei/", "User-Agent": "Mozilla/5.0"})
    for i, start in enumerate(range(0, N, PAGE)):
        f = OUT / f"page_{i:03d}.json"
        if f.exists() and f.stat().st_size > 1000:
            continue
        for k in range(4):
            try:
                r = s.get(URL, params={"service": "WFS", "version": "1.0.0", "request": "GetFeature", "typeName": "Taipei:ublock97-TWD97",
                                       "outputFormat": "application/json", "sortBy": "usecod", "startIndex": start, "maxFeatures": PAGE}, timeout=180)
                j = r.json()
                break
            except Exception as e:  # noqa: BLE001
                print("重試", start, e); time.sleep(10 * (k + 1))
        else:
            raise RuntimeError(f"offset {start} 下載失敗")
        r.encoding = "utf-8"
        f.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
        print(f"{start}+{len(j['features'])}", flush=True)
        time.sleep(1)


if __name__ == "__main__":
    main()
