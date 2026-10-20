"""下載全中山區地號（27,056 個）的地號面與屬性。

來源：https://maps.land.gov.taipei/server/rest/services/Dynamic3857/LandDyn/MapServer/2（地政局「地號」圖層，公開 ArcGIS REST；AA46＝'10' 為中山區）
輸出：資料庫/原始檔/臺北市中山區地號_LandDyn/page_XXXXXX.json（座標 EPSG:3826；每頁 1,000 筆，已存在者略過）
欄位：KCNT 段名、AA48 段碼、AA49 地號 8 碼、AA10 面積、AA16 公告現值、AA17 公告地價 等
執行：python scripts/fetch_中山區_全部地號.py
"""
import io
import json
import sys
import time
from pathlib import Path

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "資料庫" / "原始檔" / "臺北市中山區地號_LandDyn"
B = "https://maps.land.gov.taipei/server/rest/services/Dynamic3857/LandDyn/MapServer/2"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    s = requests.Session(); s.headers.update({"User-Agent": "Mozilla/5.0", "Referer": "https://cloud.land.gov.taipei/urland/urban.html"})
    where = "AA46='10'"
    total = s.get(B + "/query", params={"where": where, "returnCountOnly": "true", "f": "json"}, timeout=60).json()["count"]
    print("中山區地號", total, flush=True)
    for off in range(0, total, 1000):
        f = OUT / f"page_{off:06d}.json"
        if f.exists() and f.stat().st_size > 1000:
            continue
        for k, wait in enumerate((0, 5, 15, 30)):
            time.sleep(wait)
            try:
                j = s.get(B + "/query", params={"where": where, "outFields": "*", "returnGeometry": "true", "outSR": 3826, "orderByFields": "OBJECTID",
                                                "resultOffset": off, "resultRecordCount": 1000, "f": "json"}, timeout=180).json()
                if j.get("features"):
                    f.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
                    print(off, len(j["features"]), flush=True)
                    break
            except Exception as e:  # noqa: BLE001
                print(off, "retry", k, e, flush=True)
        else:
            print(off, "FAILED", flush=True)
            return
        time.sleep(1)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
