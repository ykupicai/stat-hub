"""下載「臺北市歷年建造執照摘要」（data.gov.tw 128204；民國 114 年以前建造執照摘要，XML，約 91 MB）。
來源：https://data.taipei/api/dataset/e20ea68e-c79d-4882-a2f9-2f3eeb45384b/resource/2d9396af-863b-496a-9893-0d2f2a8d8b71/download
輸出：資料庫/原始檔/臺北市歷年建造執照摘要/建造執照摘要.xml（已存在且大小相符則略過）
執行：python scripts/fetch_臺北市歷年建造執照摘要.py
"""
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "資料庫" / "原始檔" / "臺北市歷年建造執照摘要"
URL = "https://data.taipei/api/dataset/e20ea68e-c79d-4882-a2f9-2f3eeb45384b/resource/2d9396af-863b-496a-9893-0d2f2a8d8b71/download"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / "建造執照摘要.xml"
    s = requests.Session(); s.headers["User-Agent"] = "Mozilla/5.0"
    size = int(s.head(URL, allow_redirects=True, timeout=60).headers.get("Content-Length", 0))
    if f.exists() and f.stat().st_size == size > 0:
        print("已存在，略過", f.stat().st_size)
        return
    with s.get(URL, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(f, "wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
    print("完成", f, f.stat().st_size, "（預期", size, "）")


if __name__ == "__main__":
    main()
