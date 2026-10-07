"""11-新北市 新北市政府資料庫查詢平台（oas.bas.ntpc.gov.tw/DgbasWeb/Page/）。

主計處系統的改版介面（2026-10-07 實測）：
  目錄：StatFile2.aspx?Mode=3&CateNo=<主題>&ParentNo=null<主題><章>，表名為 __doPostBack('lbtGUID','<表ID>') 連結，
        放在 div#rightTree 的 ul 內（前端再用 easytree 美化）。
  查詢：對 StatFile2 回傳 lbtGUID=<表ID> → 頁面帶出查詢視窗（lisDate 時間、#areaTree 地區勾選、lisComplexN 分類、
        axCycle/axEffect/axMode/axSubjectNo_Server）→ 依頁面 toShowReport() 規則組 ax* 欄位 →
        整份表單 POST 到 /網頁資料查詢/ShowQuery.aspx（與嘉義、臺南、屏東同一個查詢端點）。
CLI：python stat_mcp/ntpc.py crawl ｜ python stat_mcp/ntpc.py query 11878 113 114
"""
import io
import json
import re
import sys
import time
from pathlib import Path

import requests
import urllib3
from lxml import html as LH

urllib3.disable_warnings()
BASE = "https://oas.bas.ntpc.gov.tw/DgbasWeb/Page/"
SHOW = "https://oas.bas.ntpc.gov.tw/%e7%b6%b2%e9%a0%81%e8%b3%87%e6%96%99%e6%9f%a5%e8%a9%a2/ShowQuery.aspx"
P = "ctl00$ctl00$ContentPlaceHolder3$ContentPlaceHolder1$"
PID = "ContentPlaceHolder3_ContentPlaceHolder1_"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "資料庫" / "11_各縣市主計處資料庫查詢平台" / "新北市"
SECTIONS = {"121": "新北市市政統計", "337": "新北市性別統計", "338": "新北市高齡統計", "339": "新北市幼齡統計"}


def _session():
    s = requests.Session()
    s.verify = False
    s.headers["User-Agent"] = "Mozilla/5.0"
    return s


def _get(s, url, data=None):
    for k in range(4):
        try:
            r = s.post(url, data=data, timeout=120) if data is not None else s.get(url, timeout=90)
            return LH.fromstring(r.text)
        except requests.RequestException:
            time.sleep(5 * (k + 1))
    raise RuntimeError(f"讀不到 {url}")


def _form(d):
    f = {}
    for i in d.xpath("//input[@name]"):
        if i.get("type") in ("submit", "button", "checkbox", "radio", "image"):
            continue
        f[i.get("name")] = i.get("value") or ""
    return f


def crawl():
    """各主題 × 各章 → 表（ID、名稱、週期）。"""
    s = _session()
    tree = []
    for cate, cname in SECTIONS.items():
        d = _get(s, f"{BASE}StatFile2.aspx?Mode=3&CateNo={cate}&ParentNo=null{cate}01")
        chapters = []
        for a in d.xpath("//a[@href]"):
            m = re.search(rf"StatFile2\.aspx\?Mode=3&CateNo={cate}&ParentNo=(null{cate}\d+)", a.get("href"))
            if m and (m.group(1), a.text_content().strip()) not in chapters:
                chapters.append((m.group(1), a.text_content().strip()))
        cnode = {"name": cname, "children": []}
        for pno, chname in chapters:
            dd = _get(s, f"{BASE}StatFile2.aspx?Mode=3&CateNo={cate}&ParentNo={pno}")
            tabs = []
            for a in dd.xpath('//div[@id="rightTree"]//a[contains(@href,"lbtGUID")]'):
                m = re.search(r"lbtGUID','(\d+)'", a.get("href"))
                li = a.getparent()  # 原始 HTML：<li title='週期：年'><a aria-label='表名' href=…></a>表名</li>
                name = (a.get("aria-label") or a.text_content() or a.tail or "").strip()
                cyc = (li.get("title") or "").replace("週期：", "").strip()
                if m:
                    tabs.append({"name": name, "id": m.group(1), "週期": cyc,
                                 "page": f"{BASE}StatFile2.aspx?Mode=3&CateNo={cate}&ParentNo={pno}"})
            cnode["children"].append({"name": chname, "children": tabs})
            print(f"  {cname} {chname}：{len(tabs)} 表", flush=True)
            time.sleep(1)
        tree.append(cnode)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "目錄.json").write_text(json.dumps(tree, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = [f"# 新北市政府資料庫查詢平台 目錄（{BASE}Default.aspx）", "", "表 ID 供 `stat_query_ntpc` 使用。", ""]
    for c in tree:
        lines.append(f"- **{c['name']}**")
        for ch in c["children"]:
            lines.append(f"  - **{ch['name']}**")
            for t in ch["children"]:
                lines.append(f"    - {t['name']}（{t['週期']}）  `id={t['id']}`")
    (OUT / "目錄.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return sum(len(ch["children"]) for c in tree for ch in c["children"])


def find_table(table_id):
    tree = json.loads((OUT / "目錄.json").read_text(encoding="utf-8"))
    for c in tree:
        for ch in c["children"]:
            for t in ch["children"]:
                if t["id"] == str(table_id):
                    return t
    raise ValueError(f"目錄中沒有表 ID {table_id}")


def query(table_id, years=None, areas=None):
    """回傳 {table, years_available, areas_available, rows}；rows 版型同 fetchers.dgbas_query。"""
    t = find_table(table_id)
    s = _session()
    d = _get(s, t["page"])
    f = _form(d)
    f.update({"__EVENTTARGET": "lbtGUID", "__EVENTARGUMENT": str(table_id)})
    d = _get(s, t["page"], f)  # 回傳後頁面帶出查詢視窗的選項
    dates = [(o.get("value"), o.text_content().strip()) for o in d.xpath(f'//select[@id="{PID}lisDate"]/option')]
    area_boxes = [(a.get("target"), (a.tail or "").strip())  # <a target='代碼'><input></a>名稱
                  for a in d.xpath('//*[@id="areaTree"]//a[@target]')]
    complexes = [[o.get("value") for o in sel.xpath("./option")]
                 for sel in d.xpath(f'//select[starts-with(@id,"{PID}lisComplex")]')]
    years_avail = [lbl for _, lbl in dates]
    areas_avail = [n for _, n in area_boxes]

    def ymatch(lbl):
        m = re.search(r"\d{3,4}", lbl)
        if not m or not years:
            return not years
        v = int(m.group())
        return any(v in (int(y), int(y) + 1911, int(y) - 1911) for y in years)

    sel_dates = [v for v, lbl in dates if ymatch(lbl)]
    sel_areas = [v for v, n in area_boxes if not areas or any(a in n for a in areas)]
    if not sel_dates or (area_boxes and not sel_areas):
        return {"table": t, "years_available": years_avail, "areas_available": areas_avail, "rows": [],
                "note": "年度或地區篩選後為空"}
    f = _form(d)
    f["axCycle"] = f.get(P + "axCycle_Server", "")
    f["axY"] = "[Date]" + (";[Place]" if sel_areas else "")
    f["axDate"] = "','".join(sel_dates)
    f["axEffect"] = f.get(P + "axEffect_Server", "")
    f["axFunction"] = "統計數值"
    f["axMode"] = f.get(P + "axMode_Server", "")
    f["axSubjectNo"] = f.get(P + "axSubjectNo_Server", "")
    f["ShowQueryReturnUrl"] = t["page"]
    f["axX"] = "[Measures]" + "".join(";" + c[0][:5] for c in complexes if c)
    f["axCode"] = "".join(";".join(c) + ";" for c in complexes) + ";".join(sel_areas)
    f[P + "ddlFunctiontype"] = "統計數值"
    form = list(f.items()) + [(P + "lisDate", v) for v in sel_dates]
    for k, c in enumerate(complexes, 1):
        form += [(f"{P}lisComplex{k}", v) for v in c]
    form.append((P + "goon", "查詢"))
    r = s.post(SHOW, data=form, headers={"Referer": t["page"]}, timeout=180)
    dd = LH.fromstring(r.text)
    def numcells(x):  # 結果頁另有「欄合計／列合計」功能表，挑數字格最多的那張才是資料表
        return sum(1 for c in x.xpath(".//td") if re.fullmatch(r"[-\d,\.]+", " ".join(c.text_content().split()) or "x"))
    tbs = sorted(dd.xpath("//table"), key=numcells, reverse=True)
    rows = [] if not tbs or not numcells(tbs[0]) else [[" ".join(c.text_content().split()) for c in tr.xpath("./td|./th")] for tr in tbs[0].xpath(".//tr")]
    return {"table": t, "years_available": years_avail, "areas_available": areas_avail, "rows": rows}


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    if sys.argv[1] == "crawl":
        print("表數", crawl())
    else:
        r = query(sys.argv[2], [int(x) for x in sys.argv[3:]] or None)
        print(r["table"]["name"], r["years_available"][-3:], len(r["areas_available"]), r["areas_available"][:4])
        for row in r["rows"][:8]:
            print(row[:8])
