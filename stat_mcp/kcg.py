"""11-高雄市 高雄市 PX-Web 2007 多維度資料庫（pxweb.kcg.gov.tw/pxweb2007p）。

2026-10-07 實測：
  目錄：/pxweb2007p/dialog/ 根頁直接列出全部表（約 508）：連結 varval.asp?ma=<矩陣>&ti=<表名>&path=<目錄>&lang=9&strList=L
  ⚠ 舊式 ASP，網址參數須以 **Big5** 百分比編碼，UTF-8 會回 HTTP 500。
  查詢：varval.asp 表單（values1..N 多選、noofvar、matrix、root…）→ POST Saveshow.asp，pxkonv 選「螢幕顯示表格」→ HTML 表。
CLI：python stat_mcp/kcg.py crawl ｜ python stat_mcp/kcg.py query AG300401RA 113 114
"""
import io
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote, unquote

import requests
import urllib3
from lxml import html as LH

urllib3.disable_warnings()
B = "https://pxweb.kcg.gov.tw/pxweb2007p/Dialog/"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "資料庫" / "11_各縣市主計處資料庫查詢平台" / "高雄市"


def _session():
    s = requests.Session()
    s.verify = False
    s.headers["User-Agent"] = "Mozilla/5.0"
    return s


def _b5(params):
    return "&".join(f"{k}={quote(v, encoding='big5', safe='/.')}" for k, v in params)


def _get(s, url, data=None):
    for k in range(4):
        try:
            r = s.post(url, data=data, timeout=120) if data is not None else s.get(url, timeout=90)
            r.encoding = "big5"
            return r
        except requests.RequestException:
            time.sleep(5 * (k + 1))
    raise RuntimeError(f"讀不到 {url}")


def crawl():
    s = _session()
    d = LH.fromstring(_get(s, B).text)
    tabs = []
    for a in d.xpath("//a[@href]"):
        h = a.get("href").replace("\\", "/")
        m = re.search(r"varval\.asp\?(.*)", h)
        if not m:
            continue
        p = dict(x.split("=", 1) for x in m.group(1).split("&") if "=" in x)
        path = p.get("path", "")
        tabs.append({"name": " ".join(a.text_content().split()), "ma": p.get("ma", ""), "ti": p.get("ti", ""),
                     "path": path, "group": path.rstrip("/").split("/")[-1] if path else ""})
    groups = {}
    for t in tabs:
        groups.setdefault(t["group"], []).append(t)
    tree = [{"name": g, "children": v} for g, v in groups.items()]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "目錄.json").write_text(json.dumps(tree, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = [f"# 高雄市 PX-Web 資料庫 目錄（{B}）", "", "代碼為 PX 矩陣（ma），供 `stat_query_kcg` 使用。", ""]
    for g in tree:
        lines.append(f"- **{g['name']}**（{len(g['children'])} 表）")
        lines += [f"  - {t['name']}  `{t['ma']}`" for t in g["children"]]
    (OUT / "目錄.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(tabs)


def find(ma):
    for g in json.loads((OUT / "目錄.json").read_text(encoding="utf-8")):
        for t in g["children"]:
            if t["ma"] == ma:
                return t
    raise ValueError(f"目錄中沒有 {ma}")


def query(ma, years=None, areas=None):
    """全選各維度（年度維度依 years 過濾、含地區名的維度依 areas 過濾），回傳 {table, dims, rows}。"""
    t = find(ma)
    s = _session()
    url = B + "varval.asp?" + _b5([("ma", t["ma"]), ("ti", t["ti"]), ("path", t["path"]), ("lang", "9"), ("strList", "L")])
    v = LH.fromstring(_get(s, url).text)
    form = []
    dims = {}
    for el in v.xpath("//form//input[@name]"):
        if el.get("type", "").lower() not in ("submit", "button"):
            form.append((el.get("name"), el.get("value") or ""))
    nvar = int(dict(form).get("noofvar", "0") or 0)
    for i in range(1, nvar + 1):
        name = dict(form).get(f"var{i}", f"var{i}")
        opts = [(o.get("value"), o.text_content().strip()) for o in v.xpath(f'//select[@name="values{i}"]/option')]
        dims[name] = [lbl for _, lbl in opts]
        chosen = opts
        if years and re.search(r"年|期|時間", name):
            def ok(lbl):
                m = re.search(r"\d{3,4}", lbl)
                return bool(m) and any(int(m.group()) in (y, y + 1911, y - 1911) for y in map(int, years))
            chosen = [x for x in opts if ok(x[1])] or opts
        elif areas and any(any(a in lbl for a in areas) for _, lbl in opts):
            chosen = [x for x in opts if any(a in x[1] for a in areas)]
        form += [(f"values{i}", val) for val, _ in chosen]
        form = [(k, (str(len(chosen)) if k == f"Valdavarden{i}" else val)) for k, val in form]
    form += [("pxkonv", "asp1"), ("sel", "繼續")]
    body = "&".join(f"{quote(k, encoding='big5')}={quote(val, encoding='big5')}" for k, val in form)
    r = s.post(B + "Saveshow.asp", data=body.encode("ascii"), timeout=180,
               headers={"Content-Type": "application/x-www-form-urlencoded", "Referer": url})
    r.encoding = "big5"
    dd = LH.fromstring(r.text)

    def numcells(x):
        return sum(1 for c in x.xpath(".//td") if re.fullmatch(r"[-\d,\.]+", " ".join(c.text_content().split()) or "x"))
    tbs = sorted(dd.xpath("//table"), key=numcells, reverse=True)
    rows = [] if not tbs or not numcells(tbs[0]) else [[" ".join(c.text_content().split()) for c in tr.xpath("./td|./th")] for tr in tbs[0].xpath(".//tr")]
    return {"table": t, "dims": dims, "rows": rows}


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    if sys.argv[1] == "crawl":
        print("表數", crawl())
    else:
        r = query(sys.argv[2], [int(x) for x in sys.argv[3:]] or None)
        print(r["table"]["name"], {k: (len(v), v[:3]) for k, v in r["dims"].items()})
        for row in r["rows"][:10]:
            print(row[:9])
