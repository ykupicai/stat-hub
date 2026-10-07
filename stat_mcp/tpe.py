"""11-臺北市 臺北市統計資料庫查詢系統（tsis.dbas.gov.taipei/statis）。

2026-10-07 實測（與主計總處普查動態查詢同一家廠商的 webMain.aspx 系統）：
  目錄：webMain.aspx?sys=100&keep=1&funid=tpemainTree → JSON 節點陣列（chkattr＝層級，有 funid 者為表）
  表定義：webMain.aspx?sys=212&x=2100&funid=<表> → JSON（fldName 統計項、codCnt/codName0 分類、dataYMF～dataYMT、cycleDef 週期）
  取數：webMain.aspx?sys=220&ym=<起>&ymt=<迄>&funid=<表>&cycle=<週期>&outmode=8&…&fldspc=<區段>&codspc0=<區段>
        → JSON（col 欄標題、row 列標題、orgdata 數值）。outmode=8＝JSON。
  區段編碼（stcom.js）：勾選項以「起始序號,連續數量,」串接；全選＝「0,總數,」。
  期別格式：月＝YYYMM、年＝YYY00（民國）。站台偶爾回應很慢，逾時放寬並重試。
CLI：python stat_mcp/tpe.py crawl ｜ python stat_mcp/tpe.py query a05013901 109 114
"""
import io
import json
import random
import sys
import time
from pathlib import Path

import requests
import urllib3

urllib3.disable_warnings()
B = "https://tsis.dbas.gov.taipei/statis/"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "資料庫" / "11_各縣市主計處資料庫查詢平台" / "臺北市"


def _session():
    s = requests.Session()
    s.verify = False
    s.headers["User-Agent"] = "Mozilla/5.0"
    return s


def _getjson(s, url):
    for k in range(4):
        try:
            return json.loads(s.get(url, timeout=180).text)
        except (requests.RequestException, ValueError):
            time.sleep(10 * (k + 1))
    raise RuntimeError(f"讀不到 {url}")


def crawl():
    s = _session()
    nodes = _getjson(s, B + "webMain.aspx?sys=100&keep=1&funid=tpemainTree")
    root, stack = [], []
    for n in nodes:
        if n.get("type") is None:
            continue
        lvl = int(n.get("chkattr") or 0) % 10 if int(n.get("chkattr") or 0) >= 10 else int(n.get("chkattr") or 0)
        node = {"name": n["funname"]}
        if n.get("funid"):
            node["funid"] = n["funid"].lower()
        else:
            node["children"] = []
        while stack and stack[-1][0] >= lvl:
            stack.pop()
        (stack[-1][1]["children"] if stack else root).append(node)
        if "children" in node:
            stack.append((lvl, node))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "目錄.json").write_text(json.dumps(root, ensure_ascii=False, indent=1), encoding="utf-8")

    def md(ns, d=0, out=None):
        out = out if out is not None else [f"# 臺北市統計資料庫查詢系統 目錄（{B}webMain.aspx?k=tpemain）", "",
                                           "代碼為表 funid，供 `stat_query_tpe` 使用。", ""]
        for n in ns:
            if "children" in n:
                out.append(f"{'  ' * d}- **{n['name']}**")
                md(n["children"], d + 1, out)
            else:
                out.append(f"{'  ' * d}- {n['name']}  `{n['funid']}`")
        return out
    (OUT / "目錄.md").write_text("\n".join(md(root)) + "\n", encoding="utf-8")

    def cnt(ns):
        return sum(cnt(n["children"]) if "children" in n else 1 for n in ns)
    return cnt(root)


def query(funid, years=None):
    """全選統計項與分類；years 給民國或西元年（取最小～最大），未給取最近 10 年。回傳 {meta, columns, rows}。"""
    s = _session()
    fid = funid.lower()
    m = _getjson(s, B + f"webMain.aspx?sys=212&x=2100&funid={fid}")
    cyc = int(m.get("cycleDef") or 4)
    ymf, ymt = int(m.get("dataYMF") or 0), int(m.get("dataYMT") or 0)
    yt = ymt // 100
    if years:
        ys = [int(y) - 1911 if int(y) > 1000 else int(y) for y in years]
        y0, y1 = min(ys), max(ys)
    else:
        y0, y1 = max(ymf // 100, yt - 9), yt
    if cyc == 1:  # 月
        f, t = y0 * 100 + 1, min(y1 * 100 + 12, ymt)
    else:
        f, t = y0 * 100, y1 * 100
    url = (B + f"webMain.aspx?sys=220&ym={f}&ymt={t}&kind=21&type=0&funid={fid}&cycle={cyc}&outmode=8&compmode=00"
           f"&plus=0&ohtml=q250&outkind=11&fldspc=0,{int(m.get('fldCnt') or 1)},")
    # 分類維度（codspc）不送：實測送出後只回部分分類、數值對不上（2026-10-07），規則未明。
    # 不送時網站用預設選項（通常為「總計」），先求正確；分類細項請到網站查或日後補。
    url += f"&rdm=R{random.randint(1000000, 9999999)}"
    j = _getjson(s, url)
    cols = [" / ".join(x for x in c if x) for c in j.get("col", [])]
    org, out = j.get("orgdata") or [], j.get("outdata") or []

    def cell(ci, ri):  # 顯示值為「-」者照原樣（orgdata 會把它變成 0，易誤讀為零）
        shown = (out[ci][ri] if ci < len(out) and ri < len(out[ci]) else "").strip()
        return "-" if shown in ("-", "…") else org[ci][ri]
    rows = [[" / ".join(x for x in r if x)] + [cell(ci, ri) for ci in range(len(org))]
            for ri, r in enumerate(j.get("row", []))]
    return {"meta": {"funid": fid, "表名": m.get("funname"), "週期": "月" if cyc == 1 else ("年" if cyc == 4 else cyc),
                     "可查期間": f"{ymf}~{ymt}", "統計項": m.get("fldName"), "來源": m.get("source")},
            "分類維度": [x for x in (m.get("codTitle") or []) if x],
            "注意": "有分類維度的表目前只取網站預設選項（多為總計），分類細項未支援" if any(m.get("codTitle") or []) else "",
            "columns": ["期別"] + cols, "rows": rows}


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    if sys.argv[1] == "crawl":
        print("表數", crawl())
    else:
        r = query(sys.argv[2], [int(x) for x in sys.argv[3:]] or None)
        print(r["meta"]); print(r["columns"][:8])
        for row in r["rows"][:8]:
            print(row[:8])
