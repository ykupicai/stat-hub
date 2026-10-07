"""11-新竹市 新竹市公務統計資訊系統（stat2.hccg.gov.tw/hccg_bas，預告統計資料發布時間表）。

新竹市沒有主計處「資料庫查詢平台」（統計年報查詢是 Power BI，無法程式取數）。可程式取數的是
發布時間表 calendar.aspx：每年一頁表格，列＝報表（發布單位、資料種類、資料項目、ReportDesc md），
各月欄位放當期已發布的報表檔（xlsx/ods/xls，路徑 data/report/<md-1>/<期別>/…）。
2026-10-07 實測：年度用 ddlQueryYear＋btnQuery、分頁用 ddlPages 回傳（__doPostBack）。
crawl() 掃 103 年起各年、各頁，依 md 合併成「報表 → 各期檔案」目錄；fetch(md, period) 下載該期檔並用通用解析器讀表。
CLI：python stat_mcp/hcc.py crawl ｜ python stat_mcp/hcc.py fetch 9 11506
"""
import io
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
import urllib3
from lxml import html as LH

urllib3.disable_warnings()
U = "https://stat2.hccg.gov.tw/hccg_bas/calendar.aspx"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "資料庫" / "11_各縣市主計處資料庫查詢平台" / "新竹市"


def _session():
    s = requests.Session()
    s.verify = False
    s.headers["User-Agent"] = "Mozilla/5.0"
    return s


def _req(s, data=None):
    for k in range(4):
        try:
            r = s.post(U, data=data, timeout=120) if data else s.get(U, timeout=90)
            return LH.fromstring(r.text)
        except requests.RequestException:
            time.sleep(5 * (k + 1))
    raise RuntimeError("讀不到 calendar.aspx")


def _form(d):
    f = {i.get("name"): i.get("value") or "" for i in d.xpath("//input[@name]")
         if i.get("type") not in ("submit", "button", "image")}
    for sel in d.xpath("//select[@name]"):
        o = sel.xpath("./option[@selected]") or sel.xpath("./option")
        f[sel.get("name")] = (o[0].get("value") if o else "") or ""
    return f


def _rows(d):
    tb = [t for t in d.xpath("//table") if t.xpath('.//a[contains(@href,"ReportDesc.aspx")]')]
    if not tb:
        return []
    t = min(tb, key=lambda x: len(x.xpath(".//table")))  # 最內層含報表連結的表
    head = [" ".join(c.text_content().split()) for c in t.xpath(".//tr[1]/td|.//tr[1]/th")]
    out = []
    for tr in t.xpath(".//tr")[1:]:
        cs = tr.xpath("./td|./th")
        a = tr.xpath('.//a[contains(@href,"ReportDesc.aspx")]')
        if len(cs) < 5 or not a:
            continue
        md = re.search(r"md=(\d+)", a[0].get("href")).group(1)
        files = {}
        for a2 in tr.xpath('.//a[contains(@href,"data/report/")]'):
            m = re.search(r"\(([^)]+)\)", a2.text_content())
            files[m.group(1) if m else a2.get("href").split("/")[-2]] = urljoin(U, a2.get("href"))
        txt = [" ".join(c.text_content().split()) for c in cs]
        out.append({"md": md, "單位": txt[1], "種類": txt[2], "名稱": txt[3], "週期": txt[-1] if re.search(r"報$", txt[-1]) else "",
                    "files": files})
    return out


def crawl(y0=103):
    s = _session()
    d = _req(s)
    years = [(o.get("value"), o.text_content().strip()) for o in d.xpath('//select[@name="ddlQueryYear"]/option')]
    reports = {}
    for val, lbl in years:
        if int(re.sub(r"\D", "", lbl) or 0) < y0:
            continue
        # 表格欄位是「起始月起 12 個月」，且列出的報表會隨起始月變（實測 115 年起始 1 月只 53 列、7 月 502 列），
        # 故每年用 1 月與 7 月各查一次再合併，涵蓋該年與次年上半年發布的各期檔。
        for month in ("1", "7"):
            f = _form(d)
            f.update({"ddlQueryYear": val, "ddlQueryMonth": month,
                      "ddlQueryUnit": d.xpath('//select[@name="ddlQueryUnit"]/option')[0].get("value") or "", "btnQuery": "搜尋"})
            dy = _req(s, f)
            pages = [o.get("value") for o in dy.xpath('//select[@name="ddlPages"]/option')] or ["1"]
            n = 0
            for i, pg in enumerate(pages):
                if i:
                    f = _form(dy)
                    f.update({"ddlPages": pg, "__EVENTTARGET": "ddlPages", "__EVENTARGUMENT": ""})
                    dy = _req(s, f)
                for r in _rows(dy):
                    n += 1
                    cur = reports.setdefault(r["md"], {k: r[k] for k in ("md", "單位", "種類", "名稱", "週期")} | {"files": {}})
                    cur["files"].update(r["files"])
                    if r["週期"]:
                        cur["週期"] = r["週期"]
                time.sleep(0.3)
            print(f"  {lbl} 起始 {month} 月：{len(pages)} 頁 {n} 列，累計報表 {len(reports)}", flush=True)
            d = dy
    tree = {}
    for r in sorted(reports.values(), key=lambda x: (x["單位"], x["種類"], x["名稱"])):
        r["files"] = dict(sorted(r["files"].items()))
        tree.setdefault(r["單位"], []).append(r)
    tree = [{"name": k, "children": v} for k, v in tree.items()]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "目錄.json").write_text(json.dumps(tree, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = [f"# 新竹市公務統計資訊系統 報表目錄（{U}）", "",
             "代碼為報表 md，供 `stat_hcc_report` 使用；期別為已發布的報表檔。", ""]
    for g in tree:
        lines.append(f"- **{g['name']}**（{len(g['children'])} 表）")
        for r in g["children"]:
            ps = list(r["files"])
            span = f"{ps[0]}～{ps[-1]}（{len(ps)} 期）" if ps else "無檔"
            lines.append(f"  - {r['種類']}｜{r['名稱']}（{r['週期']}）  `md={r['md']}`  {span}")
    (OUT / "目錄.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(reports)


def find(md):
    for g in json.loads((OUT / "目錄.json").read_text(encoding="utf-8")):
        for r in g["children"]:
            if r["md"] == str(md):
                return r
    raise ValueError(f"目錄中沒有 md={md}")


def fetch(md, period=None):
    """下載某報表某期（未給取最新一期）→ 回傳 {report, period, url, local, sheets:[{name, rows}]}。"""
    sys.path.insert(0, str(Path(__file__).parent))
    import store
    r = find(md)
    if not r["files"]:
        raise ValueError(f"md={md} 沒有已發布的報表檔")
    p = str(period) if period else list(r["files"])[-1]
    if p not in r["files"]:
        raise ValueError(f"md={md} 沒有 {p} 期；可用：{list(r['files'])}")
    url = r["files"][p]
    raw = _session().get(url, timeout=120).content
    ext = ".ods" if raw[:2] == b"PK" and b"opendocument" in raw[:200] else (
        ".xlsx" if raw[:2] == b"PK" else (".xls" if raw[:4] == b"\xd0\xcf\x11\xe0" else Path(url).suffix))
    local = ROOT / "資料庫" / "原始檔" / "11-新竹市" / f"md{md}_{p}{ext}"
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_bytes(raw)
    sheets = [{"name": n, "rows": g} for n, g in store.read_workbook(local)]
    return {"report": {k: r[k] for k in ("md", "單位", "種類", "名稱", "週期")}, "period": p, "url": url,
            "local": str(local.relative_to(ROOT)), "sheets": sheets}


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    if sys.argv[1] == "crawl":
        print("報表數", crawl())
    else:
        r = fetch(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
        print(r["report"], r["period"], r["local"])
        for sh in r["sheets"][:1]:
            for row in sh["rows"][:12]:
                print(row[:8])
