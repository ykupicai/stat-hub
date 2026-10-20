"""下載臺北市地政局「都更門檻估算服務」的建物屋齡統計圖層（BuildStat_Fage，公開 ArcGIS REST，約 15.3 萬個地號面）。

來源：https://maps.land.gov.taipei/server/rest/services/Dynamic3857/BuildStat_Fage/MapServer/0
  （cloud.land.gov.taipei/urland/urban.html 前端所用；不需登入，單次最多 1,000 筆）
輸出：資料庫/原始檔/臺北市建物屋齡_BuildStat_Fage/page_XXXXXX.json（每頁 1,000 筆，座標 EPSG:3826）；已存在的頁略過，可續跑。
每頁間隔 1 秒，失敗退避 5/15/30 秒；連續 3 頁失敗即停止。
執行：python scripts/fetch_臺北市_建物屋齡圖層.py
"""
import io
import json
import sys
import time
from pathlib import Path

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "資料庫" / "原始檔" / "臺北市建物屋齡_BuildStat_Fage"
B = "https://maps.land.gov.taipei/server/rest/services/Dynamic3857/BuildStat_Fage/MapServer/0"
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
                r = s.get(B + "/query", params={"where": "1=1", "outFields": "*", "returnGeometry": "true", "outSR": 3826,
                                                "orderByFields": "OBJECTID", "resultOffset": off, "resultRecordCount": PAGE, "f": "json"}, timeout=120)
                j = r.json()
                if "features" in j and j["features"]:
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
