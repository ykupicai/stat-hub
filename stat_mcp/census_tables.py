"""09t 主計總處　三大普查「普查結果統計表」（統計資訊網靜態 ODS／XLSX）。

和 09 動態查詢互補：動態查詢查不到的鄉鎮別細項（例：農事及畜牧服務業各區家數），
多半在「按縣市別」統計表裡（每縣市每次普查約 40 張）。

入口（統計資訊網 www.stat.gov.tw，同一套 CMS）：
  人口及住宅普查  News.aspx?n=2755&sms=11065
  工業及服務業普查 News.aspx?n=2740&sms=11059
  農林漁牧業普查  News.aspx?n=2763&sms=11069
各年度頁 News_Content.aspx?n=..&s=.. → 子頁（按業別／按縣市別／綜合報告…，可能再一層）→ 每張表有 ODS＋XLSX（或 XLS）。

crawl()：遞迴收集所有子頁與檔案清單 → 資料庫/09_主計總處_三大普查動態查詢/統計表結構.json（逐年度 checkpoint）
harvest(...)：依 普查／年度／子頁（縣市名或業別）／表名關鍵字 下載 ODS（無則 XLSX/XLS）→ 解析入庫 stat.sqlite
CLI：python stat_mcp/census_tables.py crawl [農林漁牧|人口|工業]
     python stat_mcp/census_tables.py get 農林漁牧 109 臺南市 統計結果摘要
"""
import io
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, parse_qs, urlparse

import requests
import urllib3
from lxml import html as LH

sys.path.insert(0, str(Path(__file__).resolve().parent))
import store  # noqa: E402

urllib3.disable_warnings()
SITE = "https://www.stat.gov.tw/"
CENSUS = {"人口及住宅普查": ("2755", "11065"), "工業及服務業普查": ("2740", "11059"), "農林漁牧業普查": ("2763", "11069")}
OUT = Path(__file__).resolve().parent.parent / "資料庫" / "09_主計總處_三大普查動態查詢" / "統計表結構.json"
EXT = (".ods", ".xlsx", ".xls", ".pdf")


def _session():
    s = requests.Session()
    s.verify = False
    s.headers["User-Agent"] = "Mozilla/5.0"
    return s


def _sid(url):
    return parse_qs(urlparse(url).query).get("s", [""])[0]


def _page(s, url):
    for k in range(3):
        try:
            return LH.fromstring(s.get(url, timeout=60).text)
        except requests.RequestException:
            time.sleep(2 * (k + 1))
    raise RuntimeError(f"讀不到 {url}")


FMT = re.compile(r"[\(（]?\s*(ODS|XLSX|XLS|PDF|CSV)\s*[\)）]?", re.I)


def _label_before(a):
    """連結文字只有「(ODS)」「(XLSX)」時，表名在連結前面的文字裡（人口、工商普查統計表的版型）。"""
    from lxml import etree
    box = a
    while box.getparent() is not None and box.tag not in ("p", "li", "td", "div"):
        box = box.getparent()
    last = ""
    for ev, el in etree.iterwalk(box, events=("start", "end")):
        if ev == "start":
            if el is a:
                return last
            txt = el.text
        else:
            txt = el.tail
        if txt:
            clean = FMT.sub("", txt).strip(" 　\t\r\n、|｜")
            if re.search(r"[一-鿿]", clean):
                last = " ".join(clean.split())
    return last


def _files(d, base):
    out = []
    for a in d.xpath("//a[@href]"):
        ti = (a.get("title") or "").replace("(另開視窗)", "").strip()
        h = a.get("href")
        name = ti or " ".join(a.text_content().split())
        if not (name.lower().endswith(EXT) or re.search(r"\.(ods|xlsx?|pdf)(\?|$)", h, re.I)):
            continue
        ext = (re.search(r"\.(ods|xlsx|xls|pdf)(\?|$)", h, re.I) or re.search(r"(ODS|XLSX|XLS|PDF)", name, re.I))
        ext = ext.group(1).lower() if ext else ""
        stem = re.sub(r"\.(ods|xlsx|xls|pdf)$", "", name, flags=re.I)
        if not re.search(r"[一-鿿]", FMT.sub("", stem)):  # 只有格式字樣或代碼（T001）→ 取前文
            stem = _label_before(a) or stem
        out.append({"title": re.sub(r"\s+", "", stem) + (f".{ext}" if ext else ""), "url": urljoin(base, h)})
    return out


def _children(d, base, n):
    seen, out = set(), []
    for a in d.xpath("//a[@href]"):
        h = urljoin(base, a.get("href"))
        t = " ".join(a.text_content().split())
        if "News_Content" in h and f"n={n}" in h and "Create=1" in h and t and _sid(h) not in seen:
            seen.add(_sid(h))
            out.append((t, h))
    return out


def _walk(s, url, n, path, depth, visited, acc):
    sid = _sid(url)
    if sid in visited or depth > 3:
        return
    visited.add(sid)
    d = _page(s, url)
    files = _files(d, url)
    if files:
        acc.append({"path": " > ".join(path), "heading": d.xpath("string(//title)").strip(), "page": url, "files": files})
    for t, h in _children(d, url, n):
        _walk(s, h, n, path + [t], depth + 1, visited, acc)
        time.sleep(0.3)


def crawl(only=""):
    data = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    s = _session()
    for cname, (n, sms) in CENSUS.items():
        if only and only not in cname:
            continue
        lst = _page(s, f"{SITE}News.aspx?n={n}&sms={sms}")
        years = [(" ".join(a.text_content().split()), urljoin(SITE, a.get("href"))) for a in lst.xpath("//a[@href]")
                 if re.match(r"^\d+年普查(結果)?統計(結果)?表", " ".join(a.text_content().split())) and "News_Content" in a.get("href")]
        for t, u in years:
            y = re.match(r"\d+", t).group()
            key = f"{cname}:{y}"
            if key in data:
                continue
            acc = []
            _walk(s, u, n, [t], 0, set(), acc)
            data[key] = {"census": cname, "year": int(y), "page": u, "pages": acc}
            OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            print(key, "子頁", len(acc), "檔案", sum(len(p["files"]) for p in acc), flush=True)
    return {k: sum(len(p["files"]) for p in v["pages"]) for k, v in data.items()}


def load():
    return json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}


def _census_name(c):
    for k in CENSUS:
        if c and (c in k or k.startswith(c[:2])):
            return k
    raise ValueError(f"普查名稱不符：{c}；可用 {list(CENSUS)}")


def list_tables(census, year, part="", query=""):
    """回傳符合的 (子頁路徑, 表名, 檔案清單)；同一張表的 ODS/XLSX/XLS 歸成一組。"""
    st = load().get(f"{_census_name(census)}:{int(year)}")
    if not st:
        raise ValueError(f"結構中沒有 {census} {year} 年；可先跑 crawl")
    terms = [t for t in query.split() if t]
    out = []
    pt = part.replace("台", "臺") if part else ""
    cnt = {}
    for p in st["pages"]:
        cnt[p["path"]] = cnt.get(p["path"], 0) + 1
    for p in st["pages"]:
        last = p["path"].split(" > ")[-1]
        sub = (p.get("heading") or last) if cnt[p["path"]] > 1 else last  # 子頁名重複（工商「報告書統計表」）→ 用頁標題
        sub = re.sub(r'[\\/:*?"<>|]', "_", sub)
        groups = {}
        for f in p["files"]:
            stem = re.sub(r"\.(ods|xlsx|xls|pdf)$", "", f["title"], flags=re.I)
            groups.setdefault(stem, []).append(f)
        for stem, fs in groups.items():
            if pt and pt not in p["path"] and pt not in sub and pt not in stem:
                continue
            if all(t in stem for t in terms):
                out.append({"path": p["path"], "sub": sub, "table": stem, "files": fs})
    return out


def harvest(census, year, part="", query="", max_tables=60):
    """下載並入庫符合條件的統計表（優先 ODS，其次 XLSX、XLS；PDF 不入庫）。"""
    cname = _census_name(census)
    tabs = list_tables(cname, year, part, query)
    if not tabs:
        raise ValueError("沒有符合的統計表；用 stat_search 或 list_tables 查表名")
    if len(tabs) > max_tables:
        raise ValueError(f"符合 {len(tabs)} 張，超過上限 {max_tables}；請加 part（縣市／業別）或 query 縮小範圍")
    s = _session()
    con = store.connect()
    res = []
    for t in tabs:
        f = next((x for e in (".ods", ".xlsx", ".xls") for x in t["files"] if x["title"].lower().endswith(e)), None)
        if not f:
            res.append({"table": t["table"], "note": "只有 PDF，未入庫"})
            continue
        sub = t["sub"]
        dest = store.RAW_DIR / "普查統計表" / cname / str(year) / sub / f["title"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        r = s.get(f["url"], timeout=180)
        r.raise_for_status()
        dest.write_bytes(r.content)
        dsid = f"censustab:{cname}:{year}:{sub}:{t['table']}"
        sv = store.save_dataset(con, dsid, "09t", f"{year}年{cname} {sub} {t['table']}", int(year), f["url"], dest,
                                store.read_workbook(dest), note=t["path"])
        res.append({"dataset_id": dsid, "sheets": sv["sheets"], "facts": sv["facts"]})
        time.sleep(0.3)
    con.close()
    return res


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    if sys.argv[1] == "crawl":
        print(crawl(sys.argv[2] if len(sys.argv) > 2 else ""))
    elif sys.argv[1] == "list":
        print(json.dumps(list_tables(*sys.argv[2:]), ensure_ascii=False, indent=1)[:3000])
    elif sys.argv[1] == "get":
        print(json.dumps(harvest(*sys.argv[2:]), ensure_ascii=False, indent=1))
