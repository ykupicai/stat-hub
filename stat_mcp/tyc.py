"""11-桃園市 桃園市統計報表資料庫 API（statbas.tycg.gov.tw/SDBTool_2，OData／REST）。

2026-10-07 實測（OpenAPI：/SDBTool_2/swagger/openapi.json）：
  清單：RestfulAPI/StatDB/EffectiveComplex/StatSPIUrlList/<類別>?type=JSON → {DataClassName, UrlList:[{EffectiveComplexName, Url}]}
        類別代碼 02～31、99（共 24 類：民政、地政…農糧、漁業…）。每個統計單元名稱帶週期，例「人口數依性別分(年)」。
  取數：…/StatData/<cuid>?periodNo=Y|M|…&begin=YYYYMMDD&end=YYYYMMDD&type=JSON
        → {Header, Data:[{DataDate, PlaceName（行政區）, ComplexName1..N（分類）, FValue}]}，長表，含各區。
  說明：…/InterpretationData/<cuid>?periodNo=…&type=JSON → MetaData（Freq、TimeExist、PlaceExist、加總方式）。
資料來自各機關公務統計報表，數值為原始值（未四捨五入）。
CLI：python stat_mcp/tyc.py crawl ｜ python stat_mcp/tyc.py query 8291 Y 113 114
"""
import io
import json
import re
import sys
import time
from pathlib import Path

import requests
import urllib3

urllib3.disable_warnings()
B = "https://statbas.tycg.gov.tw/SDBTool_2/RestfulAPI/StatDB/EffectiveComplex/"
CLASSES = ["02", "03", "06", "07", "08", "09", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
           "23", "24", "25", "26", "30", "31", "99"]
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "資料庫" / "11_各縣市主計處資料庫查詢平台" / "桃園市"


def _session():
    s = requests.Session()
    s.verify = False
    s.headers["User-Agent"] = "Mozilla/5.0"
    return s


def _getjson(s, url):
    for k in range(4):
        try:
            r = s.get(url, timeout=180)
            r.encoding = "utf-8-sig"
            return json.loads(r.text)
        except (requests.RequestException, ValueError):
            time.sleep(5 * (k + 1))
    raise RuntimeError(f"讀不到 {url}")


def crawl():
    s = _session()
    tree = []
    for c in CLASSES:
        j = _getjson(s, B + f"StatSPIUrlList/{c}?type=JSON")
        items = []
        for u in j.get("UrlList") or []:
            m = re.search(r"StatData/(\d+)\?periodNo=(\w+)", u.get("Url", ""))
            if m:
                items.append({"name": u.get("EffectiveComplexName", ""), "cuid": m.group(1), "period": m.group(2)})
        items.sort(key=lambda x: x["name"])
        tree.append({"name": j.get("DataClassName") or c, "class": c, "children": items})
        print(f"  {c} {j.get('DataClassName')}：{len(items)}", flush=True)
        time.sleep(0.5)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "目錄.json").write_text(json.dumps(tree, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = ["# 桃園市統計報表資料庫 API 目錄（https://statbas.tycg.gov.tw/SDBTool_2/StatDBAPIQuery）", "",
             "代碼為 `cuid/週期`，供 `stat_query_tyc` 使用。資料多含行政區別。", ""]
    for g in tree:
        lines.append(f"- **{g['name']}**（{len(g['children'])} 項）")
        lines += [f"  - {t['name']}  `{t['cuid']}/{t['period']}`" for t in g["children"]]
    (OUT / "目錄.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return sum(len(g["children"]) for g in tree)


def query(cuid, period="Y", years=None, areas=None):
    """years 給民國或西元年（取最小～最大），未給取全部。回傳 {meta, columns, rows}（長表）。"""
    s = _session()
    url = B + f"StatData/{cuid}?periodNo={period}&type=JSON"
    if years:
        ys = [int(y) + 1911 if int(y) < 1000 else int(y) for y in years]
        url += f"&begin={min(ys)}0101&end={max(ys)}1231"
    j = _getjson(s, url)
    h = j.get("Header") or {}
    ckeys = sorted((k for k in h if re.fullmatch(r"ComplexHeaderName\d+", k)), key=lambda k: int(k[17:]))
    cols = [h.get("DataDateHeaderName", "資料日期"), h.get("PlaceHeaderName", "行政區")] + [h[k] for k in ckeys] + \
           [h.get("FValueHeaderName", "數值")]
    rows = []
    for d in j.get("Data") or []:
        if areas and not any(a in (d.get("PlaceName") or "") for a in areas):
            continue
        dt = (d.get("DataDate") or "")[:10]
        rows.append([dt, d.get("PlaceName")] + [d.get(f"ComplexName{k[17:]}") for k in ckeys] + [d.get("FValue")])
    return {"meta": {"cuid": str(cuid), "週期": period, "名稱": j.get("EffectiveComplexName"),
                     "說明網址": f"https://statbas.tycg.gov.tw/SDBTool/StatDBAPIQuery/EffectiveComplexSpecification?cuid={cuid}&periodNo={period}"},
            "columns": cols, "rows": rows}


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    if sys.argv[1] == "crawl":
        print("項數", crawl())
    else:
        r = query(sys.argv[2], sys.argv[3], [int(x) for x in sys.argv[4:]] or None)
        print(r["meta"], r["columns"], len(r["rows"]))
        for row in r["rows"][:8]:
            print(row)
