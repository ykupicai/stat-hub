"""建立「可搜尋、但還沒下載」的資料結構（只抓 metadata，不抓數值）。

  agrstat：207 張表逐一開查詢頁，解出 統計量／各維度與項目／可選年度／每年格數
           → 資料庫/02_農業部統計處_農業統計業務查詢/結構.json
  fa     ：漁業署各年度年報有哪些分包（檔名、大小、下載網址）
  tainan ：臺南市統計年報各年度有哪些章（資料表 ODS 網址）
           → 資料庫/索引/年報結構.json

每完成一項就寫回檔案（checkpoint），中斷後重跑會跳過已完成的。
用法：python stat_mcp/crawl_structure.py [agrstat|fa|tainan|all]
"""
import io
import json
import math
import re
import sys
import time
from urllib.parse import urljoin
from datetime import date
from pathlib import Path

from lxml import html as LH

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harvest  # noqa: E402
from index import DB  # noqa: E402

AGR_OUT = DB / "02_農業部統計處_農業統計業務查詢" / "結構.json"
REL_OUT = DB / "索引" / "年報結構.json"


def _load(p, default):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def _save(p, obj):
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    for k in range(10):  # Windows 偶有防毒／索引暫時鎖檔
        try:
            tmp.replace(p)
            return
        except PermissionError:
            time.sleep(0.5 * (k + 1))
    raise PermissionError(f"無法寫入 {p}")


def agrstat_structure(qcode, name):
    s = harvest._session()
    url, form, years, d = harvest._agr_form(s, qcode)
    meas = harvest._dec(form[harvest.P + "ucItemCode$hidCode"])["OriginCodeArray"]
    groups = harvest._dec(form[harvest.P + "hidInquireGroup"])
    gname = {g["GroupCode"]: g["GroupName"] for g in groups if g["Kind"] == 0}
    dims = []
    for n, v in form.items():
        if n.endswith("ucItemDimensionCode$hidCode") and v:
            o = harvest._dec(v)
            if o.get("GroupCode"):
                dims.append({"code": o["GroupCode"], "name": gname.get(o["GroupCode"], o["GroupCode"]),
                             "items": [c["CodeName"] for c in o["OriginCodeArray"]]})
    per_year = len(meas) * math.prod(len(x["items"]) for x in dims) if dims else len(meas)
    return {"qcode": qcode, "name": name, "url": url,
            "years": f"{int(years[0])}~{int(years[-1])}" if years else "",
            "year_last": int(years[-1]) if years else None,
            "measures": [m["CodeName"] for m in meas], "dims": dims,
            "cells_per_year": per_year, "fits_one_year": per_year <= harvest.CELL_LIMIT}


def crawl_agrstat():
    cat = json.loads((DB / "02_農業部統計處_農業統計業務查詢" / "目錄.json").read_text(encoding="utf-8"))
    todo = [(q, n, f"{c} > {sub}") for c, subs in cat.items() for sub, rows in subs.items() for q, n in rows]
    out = _load(AGR_OUT, {"crawled": str(date.today()), "tables": {}})
    for i, (q, n, path) in enumerate(todo, 1):
        if q in out["tables"] and "error" not in out["tables"][q]:
            continue
        try:
            t = agrstat_structure(q, n)
            t["path"] = path
        except Exception as e:  # noqa: BLE001
            t = {"qcode": q, "name": n, "path": path, "error": repr(e)[:200]}
        out["tables"][q] = t
        out["crawled"] = str(date.today())
        _save(AGR_OUT, out)
        print(f"[{i}/{len(todo)}] {q} {n} {t.get('years', '')} 每年 {t.get('cells_per_year', '?')} 格 {t.get('error', '')}", flush=True)
        time.sleep(0.5)
    bad = [q for q, t in out["tables"].items() if "error" in t]
    big = [q for q, t in out["tables"].items() if not t.get("fits_one_year", True)]
    print(f"完成 {len(out['tables'])} 張；錯誤 {len(bad)} {bad}；單年超過上限 {len(big)} {big}")


def crawl_fa(rel):
    s = harvest._session()
    d = LH.fromstring(s.get(harvest.FA_LIST, timeout=60).text)
    for a in d.xpath('//a[contains(@href,"view.php?theme=FS_AR")]'):
        m = re.search(r"民國(\d+)年", a.text_content())
        if not m:
            continue
        y = m.group(1)
        if y in rel["fa"]:
            continue
        purl = "https://www.fa.gov.tw/" + a.get("href")
        pd = LH.fromstring(s.get(purl, timeout=60).text)
        files = []
        for f in pd.xpath('//a[contains(@href,"redirect_file")]'):
            t = f.text_content().strip()
            pm = re.match(r"^(\d+)\.?\s*(.+?)\.(zip|pdf|ods|xlsx?|rar)\s*\(([^)]+)\)", t, re.I)
            files.append({"part": int(pm.group(1)) if pm else None, "name": pm.group(2) if pm else t,
                          "type": pm.group(3).lower() if pm else "", "size": pm.group(4) if pm else "",
                          "url": "https://www.fa.gov.tw/" + f.get("href")})
        rel["fa"][y] = {"page": purl, "files": files}
        _save(REL_OUT, rel)
        print("fa", y, len(files), flush=True)
        time.sleep(0.5)


def crawl_tainan(rel):
    s = harvest._session()
    d = LH.fromstring(s.get(harvest.TN_LIST, timeout=60).text)
    for a in d.xpath('//a[contains(@href,"News_Content")]'):
        m = re.match(r"^(\d+)年臺南市統計年報", a.text_content().strip())
        if not m or m.group(1) in rel["tainan"]:
            continue
        y = m.group(1)
        purl = "https://account.tainan.gov.tw/" + a.get("href").lstrip("/")
        pd = LH.fromstring(s.get(purl, timeout=60).text)
        chap, chapters = None, {}
        for x in pd.xpath("//a[@href]"):
            t, h = x.text_content().strip(), urljoin(purl, x.get("href"))
            cm = re.match(r"^(\d{2})\s*(\S+)", t)
            if cm and re.search(r"relfile|Download|attachment", h):
                chap = cm.group(1)
                chapters.setdefault(chap, {"name": cm.group(2), "pdf": h})
            elif chap and t.startswith("資料表"):
                chapters[chap]["data"] = h
        rel["tainan"][y] = {"page": purl, "chapters": chapters}
        _save(REL_OUT, rel)
        print("tainan", y, len(chapters), flush=True)
        time.sleep(0.5)


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    rel = _load(REL_OUT, {"fa": {}, "tainan": {}})
    if what in ("fa", "all"):
        crawl_fa(rel)
    if what in ("tainan", "all"):
        crawl_tainan(rel)
    if what in ("agrstat", "all"):
        crawl_agrstat()
