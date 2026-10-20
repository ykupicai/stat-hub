"""下載臺北市地政局公有土地圖層（PublicLand，148,017 個公有地號，含所有權類別、持分比例、管理機關、面積、公告現值／地價、空地、取得原因）。

來源：https://maps.land.gov.taipei/server/rest/services/Tiled3857/PublicLand/MapServer/0（公開 ArcGIS REST，單次最多 1,000 筆；都更門檻估算服務所用）
輸出：資料庫/原始檔/臺北市公有土地_PublicLand/page_XXXXXX.json（座標 EPSG:3826；每頁 1,000 筆，已存在者略過，可續跑）
節流：每頁間隔 1 秒，失敗退避 5/15/30 秒；連續 3 頁失敗即停止。
執行：python scripts/fetch_臺北市公有土地圖層.py
"""
import io
import json
import sys
import time
from pathlib import Path

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "資料庫" / "原始檔" / "臺北市公有土地_PublicLand"
B = "https://maps.land.gov.taipei/server/rest/services/Tiled3857/PublicLand/MapServer/0"
PAGE = 1000


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0", "Referer": "https://cloud.land.gov.taipei/urland/urban.html"})
    total = s.get(B + "/query", params={"where": "1=1", "returnCountOnly": "true", "f": "json"}, timeout=60).json()["count"]
    print("總筆數", total, flush=True)
    fails = 0
    for off in range(0, total, PAGE):
        f = OUT / f"page_{off:06d}.json"
        if f.exists() and f.stat().st_size > 1000:
            continue
        for k, wait in enumerate((0, 5, 15, 30)):
            time.sleep(wait)
            try:
                j = s.get(B + "/query", params={"where": "1=1", "outFields": "*", "returnGeometry": "true", "outSR": 3826, "orderByFields": "OBJECTID",
                                                "resultOffset": off, "resultRecordCount": PAGE, "f": "json"}, timeout=180).json()
                if j.get("features"):
                    f.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
                    print(off, len(j["features"]), flush=True)
                    fails = 0
                    break
            except Exception as e:  # noqa: BLE001
                print(off, "retry", k, e, flush=True)
        else:
            fails += 1
            print(off, "FAILED", flush=True)
            if fails >= 3:
                print("連續 3 頁失敗，停止", flush=True)
                return
        time.sleep(1)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
