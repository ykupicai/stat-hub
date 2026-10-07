"""統計資料機器人的索引層：把本專案收錄的所有統計來源、各平台完整目錄樹、
案件用表紀錄與口徑地雷彙整成一份記憶體內索引，供 stat_mcp/server.py 的工具查詢。

資料來源（全部在 repo 內，不連網）：
  資料庫/索引/來源與用表.json   人工維護：來源、主題速查、案件用表、補充地雷
  資料庫/來源總表.md            「跨來源已知口徑地雷」表格（自動解析）
  資料庫/01/目錄.json、公務統計報表_農業處清冊.json
  資料庫/02/目錄.json
  資料庫/06/目錄_*.json
  以及下方 MANUAL_ITEMS（03 年報分包、04 查詢頁、05 項目代碼、06b 年報分頁、07 年報表目）

自我檢查：python stat_mcp/index.py   （印出各來源項目數）
"""
import json
import re
from collections import OrderedDict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "資料庫"
CURATED = DB / "索引" / "來源與用表.json"

AGRSTAT_Q = "https://agrstat.moa.gov.tw/moasdweb/inquire/InquireAdvance.aspx?qcode={}"
CYHG_STAT08 = "https://cyhg.dgbas.gov.tw/statweb/Page/stat08.aspx"

# 沒有 目錄.json 的來源，把操作說明裡列出的細目登記在這裡（s=來源id, p=路徑, n=名稱, c=代碼, u=網址）
MANUAL_ITEMS = [
    *[{"s": "03", "p": "漁業統計年報 > 年度頁 zip", "n": n, "c": f"第{i}包", "u": "https://www.fa.gov.tw/list.php?theme=FS_AR"}
      for i, n in enumerate(["漁業統計概要及說明", "統計圖", "漁會", "漁戶數及漁戶人口數", "漁業從業人數", "漁船筏數量",
                             "漁業生產量統計相關報表（含 11409_水產養殖面積.ods：縣市×魚種，總計＝單養＋混養＋休養）",
                             "水產品貿易", "魚貝苗", "水產製品", "水產罐頭", "水產加工廠數", "製冰冷藏", "魚市場",
                             "水產配合飼料", "僱用外籍船員", "附錄"], start=1)],
    {"s": "03", "p": "漁業署 統計與出版品", "n": "漁家經濟調查年報", "c": "", "u": "https://www.fa.gov.tw/cht/PublicationsFishEco/index.aspx"},
    {"s": "03", "p": "漁業署 統計與出版品", "n": "提供 FAO 之漁業統計資料", "c": "", "u": "https://www.fa.gov.tw/cht/PublicationsFao/index.aspx"},
    *[{"s": "04", "p": "農情報告資源網 > 作物（非稻作）", "n": n, "c": c, "u": "https://agr.afa.gov.tw/afa/afa_frame.jsp"}
      for n, c in [("鄉鎮作物查詢（各鄉鎮×各作物收穫面積、產量）", "pgcroptown_cond.jsp"),
                   ("縣市作物查詢", "pgcropcity_cond.jsp"), ("作物比較", "pgcropcomp_cond.jsp"),
                   ("面積產量查詢", "pgcropmeaqty_cond.jsp"), ("重要作物產量", "pgcropsigqty_cond.jsp"),
                   ("生產面積／生產作物", "pgprodmea_cond.jsp")]],
    {"s": "04", "p": "農情報告資源網 > 稻作", "n": "稻作鄉鎮查詢（水稻、稻米）", "c": "pgricetown_cond.jsp", "u": "https://agr.afa.gov.tw/afa/afa_frame.jsp"},
    *[{"s": "05a", "p": "氣候月平均 > 項目", "n": n, "c": c,
       "u": f"https://www.cwa.gov.tw/V8/C/C/Statistics/MonthlyMean/MOD/Taiwan_{c}.html"}
      for c, n in [("tx", "氣溫（月平均）"), ("meantxmax", "最高氣溫（月平均最高，非極端最高）"), ("meantxmin", "最低氣溫（月平均最低）"),
                   ("precp", "降水量（平均）"), ("precp-median", "降水量（中位數）"), ("precpday", "降水量>=0.1mm日數"),
                   ("sunshine", "日照時數"), ("rh", "相對濕度"), ("ws", "風速"), ("stnpres", "測站氣壓"),
                   ("txmaxge30day", "最高氣溫>=30℃日數"), ("txminle10day", "最低氣溫<=10℃日數"),
                   ("txge25day", "氣溫>=25℃日數"), ("CamtMean", "雲量")]],
    {"s": "05b", "p": "CODiS", "n": "逐站逐月觀測值（氣溫、雨量、日照…）；臺南站 467410", "c": "api/station", "u": "https://codis.cwa.gov.tw/StationData"},
    *[{"s": "06b", "p": "臺南市統計年報 > 04農林漁牧 ODS 分頁", "n": n, "c": c, "u": "https://account.tainan.gov.tw/News.aspx?n=44"}
      for c, n in [("4-1", "農耕土地面積（歷年＋37區）"), ("4-2", "農戶人口"), ("4-3", "稻米"), ("4-4", "農產品"),
                   ("4-5", "造林"), ("4-6", "森林採伐"), ("4-7", "森林災害"), ("4-8", "漁業人員"), ("4-9", "漁戶"),
                   ("4-10", "漁船"), ("4-11", "漁業產量"), ("4-12", "水產養殖面積（96–114，37區，含休養）"),
                   ("4-13", "遭難漁船"), ("4-14", "遭難漁民"),
                   ("4-15", "牲畜數（舊分頁：只到110年、無區別，勿用）"),
                   ("4-15牲畜數_修_", "牲畜數（★到114年＋37區）"), ("4-16", "牲畜屠宰"), ("4-17", "乳母牛"),
                   ("4-18", "家禽（舊分頁：只到110年、無區別，勿用）"), ("4-18家禽_修", "家禽（★到114年＋37區）"),
                   ("4-19", "水土保持"), ("4-20", "農路改善"), ("4-21", "灌溉服務面積（81–114）")]],
    *[{"s": "07", "p": f"農業局統計年報 > {p}", "n": n, "c": c, "u": ""}
      for p, c, n in [("壹 行政組織", "1-1~1-6", "行政組織系統、預算員額、員工人數、公務人員職等／教育程度／年齡"),
                      ("貳 農業", "2-1", "臺南市農耕土地面積（歷年＋37區，與主計處年報 4-1 同源）"),
                      ("貳 農業", "2-2", "現有農機數"), ("貳 農業", "2-3", "有效農機使用證之農機數量"),
                      ("貳 農業", "2-4", "農路改善及維護工程"), ("貳 農業", "2-5", "各級農會團體及會員數"),
                      ("参 林業", "3-1~3-4", "森林主產物砍伐生產、主產物採伐生產、副產物生產量值、苗圃育苗數量"),
                      ("肆 漁業", "4-1~4-9", "漁戶及漁戶人口數、漁業從業人數、漁港別漁產量及漁船筏數、漁筏數、動力漁船數、水產加工廠、製冰冷藏、遭難漁民、遭難漁船")]],
    {"s": "08", "p": "data.gov.tw", "n": "農村社區土地重劃建設地區一覽表（全國 57 筆，2022 以前）", "c": "25094", "u": "https://data.gov.tw/dataset/25094"},
]


def load(p):
    return json.loads(p.read_text(encoding="utf-8"))


def walk_tree(nodes, src, prefix, out):
    """臺南 06 的三層樹：{name, children} … 葉節點帶 url。"""
    for nd in nodes:
        path = prefix + [nd["name"]]
        if nd.get("url"):
            out.append({"s": src, "p": " > ".join(prefix), "n": nd["name"], "c": "", "u": nd["url"]})
        for ch in nd.get("children", []):
            walk_tree([ch], src, path, out)


def code_of(path_part):
    m = re.match(r"^([0-9][0-9\-]+[0-9])\s*(.*)$", path_part)
    return m.groups() if m else ("", path_part)


def build_items():
    items = []
    # 01a 嘉義資料庫查詢平台
    d = load(DB / "01_嘉義縣主計處_資料庫查詢平台" / "目錄.json")
    for cat, v in d.items():
        for g in v["groups"]:
            for it in g["items"]:
                items.append({"s": "01a", "p": f"{cat} > {g['group']}", "n": it["name"], "c": "", "u": it["url"]})
    # 01b 公務統計報表 農業處清冊（表號×期別 → 每表一列）
    agg = OrderedDict()
    for r in load(DB / "01_嘉義縣主計處_資料庫查詢平台" / "公務統計報表_農業處清冊.json"):
        a = agg.setdefault(r["no"], {"name": re.sub(r"\s+(XLS|ODS|PDF)$", "", r["name"]), "periods": [], "fmt": set(), "office": r["office"]})
        a["periods"].append(r["period"])
        a["fmt"].add(r["format"])
    for no, a in agg.items():
        per = "、".join(sorted(set(a["periods"])))
        items.append({"s": "01b", "p": f"{a['office']} > 期別 {per}", "n": a["name"], "c": no, "u": CYHG_STAT08})
    # 02 農業部統計處（有 結構.json 時附上統計量／維度／項目當搜尋關鍵字）
    struct_p = DB / "02_農業部統計處_農業統計業務查詢" / "結構.json"
    struct = load(struct_p)["tables"] if struct_p.exists() else {}
    for cat, subs in load(DB / "02_農業部統計處_農業統計業務查詢" / "目錄.json").items():
        for sub, rows in subs.items():
            for q, n in rows:
                it = {"s": "02", "p": f"{cat} > {sub}", "n": n, "c": q, "u": AGRSTAT_Q.format(q)}
                st = struct.get(q)
                if st and "error" not in st:
                    it["k"] = " ".join(st["measures"] + [d["name"] + " " + " ".join(d["items"]) for d in st["dims"]])
                    it["meta"] = {"年度": st["years"], "統計量": st["measures"],
                                  "維度": {d["name"]: len(d["items"]) for d in st["dims"]},
                                  "每年格數": st["cells_per_year"], "可一次下載": st["fits_one_year"]}
                items.append(it)
    # 03 漁業署、06b 臺南市統計年報 各年度可下載的分包／章（年報結構.json）
    rel_p = DB / "索引" / "年報結構.json"
    rel = load(rel_p) if rel_p.exists() else {"fa": {}, "tainan": {}}
    for y, v in rel.get("fa", {}).items():
        for f in v["files"]:
            items.append({"s": "03", "p": f"漁業統計年報 > 民國{y}年", "n": f"{f['name']}（{f['type']} {f['size']}）",
                          "c": f"fa:{y}:{f['part']}" if f["part"] else f"fa:{y}", "u": f["url"]})
    for y, v in rel.get("tainan", {}).items():
        for c, ch in v["chapters"].items():
            items.append({"s": "06b", "p": f"臺南市統計年報 > {y}年", "n": f"{c}{ch['name']}" + ("（資料表 ODS）" if ch.get("data") else "（僅 PDF）"),
                          "c": f"tainan:{y}:{c}", "u": ch.get("data") or ch.get("pdf", "")})
    # 06a 臺南三個目錄
    for fn, label in [("目錄_統計年報查詢平臺.json", "統計年報查詢平臺"),
                      ("目錄_內部報表年資料.json", "內部報表(年)"),
                      ("目錄_共通性報表年資料.json", "共通性報表(年)")]:
        tmp = []
        walk_tree(load(DB / "06_臺南市主計處_資料庫查詢平台" / fn), "06a", [label], tmp)
        for it in tmp:  # 把「表號 報表名」拆出代碼
            parts = it["p"].split(" > ")
            c, rest = code_of(parts[-1])
            if c:
                it["c"] = c
            items.append(it)
    # 10a 屏東縣主計處資料庫查詢平台（與嘉義、臺南同一套系統）
    for fn, label in [("目錄_統計年報查詢.json", "統計年報查詢"), ("目錄_其他常用查詢_年.json", "其他常用查詢(年)"),
                      ("目錄_其他常用查詢_月.json", "其他常用查詢(月)")]:
        fp = DB / "10_屏東縣主計處_資料庫查詢平台" / fn
        if fp.exists():
            tmp = []
            walk_tree(load(fp), "10a", [label], tmp)
            for it in tmp:
                c, rest = code_of(it["p"].split(" > ")[-1])
                if c:
                    it["c"] = c
                items.append(it)
    # 10b 屏東縣公務統計報表清冊（農業處＋海洋及漁業事務管理所）
    pt_p = DB / "10_屏東縣主計處_資料庫查詢平台" / "公務統計報表_農業清冊.json"
    if pt_p.exists():
        agg = OrderedDict()
        for r in load(pt_p):
            a = agg.setdefault((r["office"], r["no"]), {"name": r["name"], "periods": set()})
            a["periods"].add(r["period"])
        for (off, no), a in agg.items():
            items.append({"s": "10b", "p": f"{off} > 期別 {'、'.join(sorted(a['periods']))}", "n": a["name"], "c": no,
                          "u": "https://pthg.dgbas.gov.tw/statweb/Page/stat08.aspx"})
    # 10c 屏東縣統計年報（整份 zip；表號同 10a「統計年報查詢」，表名借用 10a）
    pt_tree = DB / "10_屏東縣主計處_資料庫查詢平台" / "目錄_統計年報查詢.json"
    if pt_tree.exists():
        for cat in load(pt_tree):
            for tb in cat.get("children", []):
                m = re.match(r"表\s*(\d+-\d+)\s*(.*)", tb["name"])
                if m:
                    items.append({"s": "10c", "p": f"屏東縣統計年報 > {cat['name']}", "n": f"表{m.group(1)} {m.group(2).strip()}",
                                  "c": f"ptyb:{m.group(1)}", "u": "https://pthg.dgbas.gov.tw/STATWeb/Page/BookCatalog_Main.aspx",
                                  "meta": {"年報年度": "107～114（107～113 為試算表可解析；114 為 PDF）",
                                           "取數": f"stat_pingtung_yearbook(year, table=\"{m.group(1)}\")"}})
    # 11 各縣市主計處資料庫查詢平台（同一套系統；來源 id 為「11-縣市」）
    cty = DB / "11_各縣市主計處資料庫查詢平台"
    if cty.exists():
        for d in sorted(cty.iterdir()):
            fp = d / "目錄.json"
            if d.is_dir() and fp.exists() and d.name == "臺北市":  # webMain 系統：funid
                def tp(ns, path):
                    for n in ns:
                        if "children" in n:
                            tp(n["children"], path + [n["name"]])
                        else:
                            items.append({"s": "11-臺北市", "p": " > ".join(path), "n": n["name"], "c": f"tpe:{n['funid']}",
                                          "u": f"https://tsis.dbas.gov.taipei/statis/webMain.aspx?k1={n['funid']}&barf=1",
                                          "meta": {"取數": f"stat_query_tpe(\"{n['funid']}\", years)"}})
                tp(load(fp), ["臺北市"])
                continue
            if d.is_dir() and fp.exists() and d.name == "高雄市":  # PX-Web：矩陣代碼
                for g in load(fp):
                    for tb in g["children"]:
                        items.append({"s": "11-高雄市", "p": f"高雄市 PX-Web > {g['name']}", "n": tb["name"], "c": f"kcg:{tb['ma']}",
                                      "u": "https://pxweb.kcg.gov.tw/pxweb2007p/dialog/",
                                      "meta": {"取數": f"stat_query_kcg(\"{tb['ma']}\", years, areas)"}})
                continue
            if d.is_dir() and fp.exists() and d.name == "新北市":  # 改版介面：表 ID 結構
                for c in load(fp):
                    for ch in c["children"]:
                        for tb in ch["children"]:
                            items.append({"s": "11-新北市", "p": f"新北市 > {c['name']} > {ch['name']}", "n": tb["name"],
                                          "c": f"ntpc:{tb['id']}", "u": tb["page"],
                                          "meta": {"週期": tb["週期"], "取數": f"stat_query_ntpc(\"{tb['id']}\", years, areas)"}})
                continue
            if d.is_dir() and fp.exists():
                tmp = []
                walk_tree(load(fp), f"11-{d.name}", [d.name], tmp)
                for it in tmp:
                    c, rest = code_of(it["p"].split(" > ")[-1])
                    if c:
                        it["c"] = c
                    items.append(it)
    # 09 三大普查動態查詢（統計項×可搭配複分類）
    cen_p = DB / "09_主計總處_三大普查動態查詢" / "結構.json"
    if cen_p.exists():
        for it in load(cen_p)["items"]:
            cls = sorted({n for v in it["variants"] for n in v["分類"]})
            items.append({"s": "09", "p": f"{it['kind']} > {it['path']}", "n": it["name"], "c": f"census:{it['idx']}",
                          "u": "https://dtable.dgbas.gov.tw/censuall/webMain.aspx?sys=210&x=2098&funid=advqry",
                          "k": " ".join(cls), "meta": {"可搭配複分類": cls[:30], "取數": "stat_census_query"}})
    # 09t 普查結果統計表（靜態 ODS／XLSX）
    tab_p = DB / "09_主計總處_三大普查動態查詢" / "統計表結構.json"
    if tab_p.exists():
        for key, v in load(tab_p).items():
            cnt = {}
            for pg in v["pages"]:
                cnt[pg["path"]] = cnt.get(pg["path"], 0) + 1
            for pg in v["pages"]:
                last = pg["path"].split(" > ")[-1]
                part = (pg.get("heading") or last) if cnt[pg["path"]] > 1 else last
                stems = {}
                for f in pg["files"]:
                    stems.setdefault(re.sub(r"\.(ods|xlsx|xls|pdf)$", "", f["title"], flags=re.I), []).append(f["title"].rsplit(".", 1)[-1])
                for stem, exts in stems.items():
                    items.append({"s": "09t", "p": pg["path"] + ("（" + part + "）" if part != last else ""), "n": stem, "c": f"censustab:{v['census']}:{v['year']}",
                                  "u": pg["page"], "meta": {"格式": exts, "取數": f"stat_census_tables(\"{v['census'][:4]}\", {v['year']}, part=\"{part}\", table=\"{stem}\")"}})
    items.extend(MANUAL_ITEMS)
    return items


def parse_pitfalls():
    md = (DB / "來源總表.md").read_text(encoding="utf-8")
    sec = md.split("## 跨來源已知口徑地雷", 1)[1].split("\n## ", 1)[0]
    rows = []
    for line in sec.splitlines():
        if line.startswith("|") and not line.startswith("|---") and "地雷 | 說明" not in line:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 2:
                rows.append({"地雷": cells[0].replace("`", ""), "說明": cells[1].replace("`", "").replace("**", ""), "來源": "來源總表"})
    return rows


def build_index():
    cur = load(CURATED)
    items = build_items()
    for i, it in enumerate(items):
        it["id"] = f"{it['s']}:{i}"
    return {
        "built": date.today().isoformat(),
        "sources": cur["來源"],
        "topics": cur["主題速查"],
        "usage": cur["案件用表"],
        "pitfalls": parse_pitfalls() + cur["補充地雷"],
        "items": items,
    }


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    d = build_index()
    by = OrderedDict()
    for it in d["items"]:
        by[it["s"]] = by.get(it["s"], 0) + 1
    print(f"來源 {len(d['sources'])}、主題 {len(d['topics'])}、案件用表 {len(d['usage'])}、"
          f"地雷 {len(d['pitfalls'])}、目錄項目 {len(d['items'])}")
    print("各來源項目數：", dict(by))