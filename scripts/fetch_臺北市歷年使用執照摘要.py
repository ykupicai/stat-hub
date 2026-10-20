"""下載「臺北市歷年使用執照摘要」（data.taipei c876ff02-af2e-4eb8-bd33-d444f5052733；民國 114 年以前使用執照摘要，XML，約 65 MB）。
來源：https://data.taipei/api/frontstage/tpeod/dataset/resource.download?rid=0f3f9675-8356-4f1a-9908-1ce8892012fa
輸出：資料庫/原始檔/臺北市歷年使用執照摘要/使用執照摘要.xml
執行：python scripts/fetch_臺北市歷年使用執照摘要.py
"""
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "資料庫" / "原始檔" / "臺北市歷年使用執照摘要"
URL = "https://data.taipei/api/frontstage/tpeod/dataset/resource.download?rid=0f3f9675-8356-4f1a-9908-1ce8892012fa"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / "使用執照摘要.xml"
    s = requests.Session(); s.headers["User-Agent"] = "Mozilla/5.0"
    with s.get(URL, stream=True, timeout=600, allow_redirects=True) as r:
        r.raise_for_status()
        print("狀態", r.status_code, "大小", r.headers.get("Content-Length"), "類型", r.headers.get("Content-Type"))
        with open(f, "wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
    print("完成", f, round(f.stat().st_size / 1e6, 1), "MB")


if __name__ == "__main__":
    main()
