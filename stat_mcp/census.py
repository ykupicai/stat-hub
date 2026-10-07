"""09 行政院主計總處　三大普查動態查詢系統（dtable.dgbas.gov.tw/censuall）。

人口及住宅普查（89/99/109）、農林漁牧業普查（94/99/104/109）、工業及服務業普查（95/100/105/110）。

網站機制（2026-10-07 實測）：
  主頁 webMain.aspx?sys=210&x=2098&funid=advqry 內嵌全部 metadata 為 JS 變數：
    gfld   統計項樹（attr1=0 普查別／1 大類／2 中類／3 統計項／≥5 該統計項依可搭配分類組合的變體，codetype=可搭配的分類 fldid）
    gcode1 複分類（attr1<5 為分類名＋fldid，其後 attr1≥5 為該分類的選項 val/name）
    clsfld 各普查別的統計項代碼範圍（1 人口 231…、2 農林漁牧 211…216、3 工商 221…229）
  查詢＝把條件字串（& 以 @26@ 取代、每 1024 字一段）POST 到 webMain.aspx?sys=601&x=2489&setid=<session>，
       再 GET webQuery.aspx?sys=253&m02=stm08&funid=advqry&sesid=<session>，結果以 `var gData=[{…}]` JSON 內嵌於頁中。
  限制：一次最多 10 個統計項、3 組複分類。
"""
import json
import random
import re
import urllib.parse
from pathlib import Path

import requests
import urllib3

urllib3.disable_warnings()
BASE = "https://dtable.dgbas.gov.tw/censuall/"
MAIN = BASE + "webMain.aspx?sys=210&x=2098&funid=advqry"
ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "資料庫" / "09_主計總處_三大普查動態查詢"
STRUCT = OUT_DIR / "結構.json"
KIND = {1: "人口及住宅普查", 2: "農林漁牧業普查", 3: "工業及服務業普查"}


def _session():
    s = requests.Session()
    s.verify = False
    s.headers["User-Agent"] = "Mozilla/5.0"
    return s


def _js_array(text, name):
    m = re.search(r"\b" + name + r"\s*=\s*\[", text)
    i = m.end() - 1
    depth, j, instr = 0, i, False
    while j < len(text):
        c = text[j]
        if instr:
            if c == "\\":
                j += 1
            elif c == '"':
                instr = False
        elif c == '"':
            instr = True
        elif c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                break
        j += 1
    raw = re.sub(r",\s*([\]}])", r"\1", text[i:j + 1])
    return json.loads(raw)


def crawl():
    """抓主頁 metadata → 結構.json（統計項樹、分類與選項、各普查年度）。"""
    t = _session().get(MAIN, timeout=60).text
    gfld, gcode1 = _js_array(t, "gfld"), _js_array(t, "gcode1")
    years = re.findall(r'<option value="(\d+)"[^>]*>([^<]+普查)</option>', t)
    cls = re.findall(r"clsfld=\[([^\]]+)\]", t)[-1]
    clsfld = [x.strip().strip("'") for x in cls.split(",")]
    codes, cur = [], None
    for i, c in enumerate(gcode1):
        if c["attr1"] < 5:
            cur = {"idx": i, "fldid": c["fldid"], "name": c["name"], "values": []}
            codes.append(cur)
        elif cur:
            cur["values"].append({"val": c["val"], "name": c["name"]})
    code_names = {}
    for c in codes:
        code_names.setdefault(c["fldid"], []).append(c["name"])
    items, path, last = [], [""] * 5, None
    for i, f in enumerate(gfld):
        a = f["attr1"]
        if a < 5:
            path[a] = f["name"]
            for k in range(a + 1, 5):
                path[k] = ""
            last = (i, f["name"], path[0], " > ".join(p for p in path[1:a] if p))
            continue
        if last and (not items or items[-1]["idx"] != last[0]):  # 後面直接接變體的節點＝統計項
            items.append({"idx": last[0], "name": last[1], "kind": last[2], "path": last[3], "variants": []})
        if items:
            ct = [x for x in f["codetype"] if x]
            items[-1]["variants"].append({"fldid": f["fldid"], "unit": f.get("unit", ""), "codetype": ct,
                                          "分類": sorted({n for x in ct for n in code_names.get(x, [str(x)])})})
    out = {"source": MAIN, "years": [{"value": v, "name": n} for v, n in years], "clsfld": clsfld,
           "codes": codes, "items": items}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    STRUCT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    _write_md(out)
    return {"普查年度": len(years), "統計項": len(items), "複分類": len(codes)}


def _write_md(st):
    lines = ["# 主計總處　三大普查動態查詢系統－統計項目錄", "",
             f"來源：<{MAIN}>　（由 `python stat_mcp/census.py crawl` 產生，勿手改）", "",
             "普查年度：" + "、".join(y["name"] for y in st["years"]), ""]
    cur = None
    for it in st["items"]:
        if it["kind"] != cur:
            cur = it["kind"]
            lines += ["", f"## {cur}", "", "| 統計項 | 路徑 | 單位 | 可搭配複分類（任一變體） |", "|---|---|---|---|"]
        cls = sorted({n for v in it["variants"] for n in v["分類"]})
        unit = next((v["unit"] for v in it["variants"] if v["unit"]), "")
        lines.append(f"| {it['name']} | {it['path']} | {unit} | {'、'.join(cls)[:300]} |")
    (OUT_DIR / "目錄.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def load():
    if not STRUCT.exists():
        crawl()
    return json.loads(STRUCT.read_text(encoding="utf-8"))


def _year_value(st, census):
    """census 例：'109農林漁牧'、'109年農林漁牧業普查'、'1092'。回傳 (ymlist value, 年, 普查別序號)。"""
    c = str(census)
    for y in st["years"]:
        if c == y["value"] or c == y["name"]:
            return y["value"], int(y["value"]) // 10, int(y["value"]) % 10
    m = re.match(r"(\d{2,3})", c)
    for y in st["years"]:
        if m and y["name"].startswith(m.group(1) + "年") and any(k in y["name"] for k in re.findall(r"[一-鿿]{2}", c)):
            return y["value"], int(y["value"]) // 10, int(y["value"]) % 10
    raise ValueError(f"找不到普查：{census}；可用：{[y['name'] for y in st['years']]}")


def query(census, items, rows=(), cols=()):
    """census：普查（如 '109農林漁牧'）；items：統計項名稱或 idx（≤10）；
    rows／cols：複分類名稱（表側／表頭，合計 ≤3，如 ['鄉鎮別']、['縣市別']）。
    回傳 {'columns', 'data'(list of dict), 'items'(實際使用的 fldid 與單位)}。"""
    st = load()
    yv, ym, kind = _year_value(st, census)
    rng = st["clsfld"][kind]
    lo, hi = (int(x) for x in rng.split("-"))
    by_name = {}
    for c in st["codes"]:
        by_name.setdefault(c["name"], c)
    sel_codes = []
    for kind_, names in ((1, rows), (2, cols)):
        for n in names:
            if n not in by_name:
                raise ValueError(f"複分類「{n}」不存在")
            sel_codes.append((kind_, by_name[n]))
    if len(sel_codes) > 3:
        raise ValueError("複分類最多 3 組")
    want = {c["fldid"] for _, c in sel_codes}
    flds, used = [], []
    for it in items:
        cand = [x for x in st["items"] if (x["idx"] == it if isinstance(it, int) else x["name"] == it)]
        cand = [x for x in cand if any(lo <= v["fldid"] <= hi for v in x["variants"])] or cand
        if not cand:
            raise ValueError(f"統計項「{it}」不存在於 {census}")
        var = next((v for x in cand for v in x["variants"] if lo <= v["fldid"] <= hi and want <= set(v["codetype"])), None)
        if not var:
            opts = sorted({n for x in cand for v in x["variants"] if lo <= v["fldid"] <= hi for n in v["分類"]})
            raise ValueError(f"「{it}」不能搭配 {sorted(n for _, c in sel_codes for n in [c['name']])}；可搭配：{opts}")
        flds.append(f"{var['fldid']}!{cand[0]['name']}|")
        used.append({"name": cand[0]["name"], "fldid": var["fldid"], "unit": var["unit"]})
    if len(flds) > 10:
        raise ValueError("一次最多 10 個統計項")

    def codestr(k):
        out = ""
        for kk, c in sel_codes:
            if kk == k:
                out += f"{c['fldid']}!{c['name']}" + "".join(f"!{v['val']}!{v['name']}" for v in c["values"]) + "|"
        return out

    title = " 統計項:" + "、".join(u["name"] for u in used) + (" 複分類(列):" + "、".join(rows) if rows else "")
    y100 = ym * 100
    lurl = (f"&funid=advqry&outmode=0&ymf={y100}&ymt={y100}&ymlist={y100},&cyc=4"
            f"&clsym{kind}=[{y100},]&clsfld{kind}=[{rng}]"
            f"&fldlist=[{''.join(flds)}] ] &codelist=[{codestr(1)}] &codelist2=[{codestr(2)}] &title=[{title}]")
    s = _session()
    s.get(MAIN, timeout=60)
    sid = "S" + str(random.random() * 1000000)
    for i in range(0, len(lurl), 1024):
        chunk = lurl[i:i + 1024].replace("&", "@26@")
        s.post(BASE + "webMain.aspx?sys=601&x=2489&setid=" + sid, data="&setval={" + urllib.parse.quote(chunk, safe="") + "}",
               headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                        "X-Requested-With": "XMLHttpRequest"}, timeout=60)
    t = s.get(BASE + "webQuery.aspx?sys=253&m02=stm08&funid=advqry&sesid=" + sid, timeout=180).text
    if not re.search(r"\bgData\s*=\s*\[", t):
        raise RuntimeError("查無結果（網站可能改版，或此組合無資料）")
    data = _js_array(t, "gData")
    for r in data:
        for k, v in list(r.items()):
            if isinstance(v, str):
                r[k] = v.strip()
    cols_out = [k for k in (data[0].keys() if data else []) if k != "area"]
    return {"census": next(y["name"] for y in st["years"] if y["value"] == yv), "items": used,
            "rows": list(rows), "cols": list(cols), "columns": cols_out, "data": data}


def to_grid(res):
    cols = res["columns"]
    return [cols] + [[str(r.get(c, "")) for c in cols] for r in res["data"]]


if __name__ == "__main__":
    import io
    import sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    if sys.argv[1] == "crawl":
        print(crawl())
    else:
        r = query(sys.argv[1], sys.argv[2].split(","), sys.argv[3].split(",") if len(sys.argv) > 3 else [])
        print(json.dumps({k: r[k] for k in ("census", "items", "columns")}, ensure_ascii=False), len(r["data"]))
        print(r["data"][:3])
