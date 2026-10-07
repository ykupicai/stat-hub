"""統計資料機器人（stat-hub）MCP server。

仿 TwinkleHub 的「先搜尋 → 看 metadata → 拉資料」流程，對象是本專案收錄的
嘉義農再、臺南農再用過的全部統計來源：

  找：stat_search / stat_topic / stat_case_usage / stat_pitfalls
  看：stat_get_source（含該來源 操作說明.md 全文：網站層級、口徑與陷阱）
  拉：stat_query_dgbas（嘉義/臺南主計處平台）、stat_query_afa（農糧署鄉鎮×作物）、
      stat_climate（CODiS 測站期間統計）、stat_cyhg_reports（嘉義公務統計報表清冊）、
      stat_read_local（案件已歸檔的原始報表）

啟動：python stat_mcp/server.py   （stdio；由 .mcp.json 註冊）
"""
import json
import re
import sys
from pathlib import Path

import pandas  # noqa: F401  ← 必須在 mcp.run() 前載入：Windows 上於 stdio 服務中才首次 import pandas 會卡死
from mcp.server.fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetchers  # noqa: E402
import census  # noqa: E402
import census_tables  # noqa: E402
import pingtung_yearbook  # noqa: E402
import ntpc  # noqa: E402
import kcg  # noqa: E402
import tpe  # noqa: E402
import harvest  # noqa: E402
import store  # noqa: E402
from index import ROOT, build_index  # noqa: E402

INSTRUCTIONS = """統計資料機器人：查「某項統計資料該去哪裡拿、口徑是什麼、怎麼取數」，並可即時向政府平台取數。
涵蓋 20 個來源（嘉義縣/臺南市/屏東縣主計處、農業部統計處、漁業署、農糧署、氣象署、臺南市農業局、data.gov.tw，
以及無公開來源時的索取窗口 X1–X4）、3,300+ 個平台目錄細項、兩案（嘉義農再、臺南農再）實際用表與口徑地雷。

典型流程：
1. stat_search("關鍵字") 找候選：同時回主題速查、案件用表、地雷、來源、目錄細項（細項附查詢網址）。
   不確定該用哪個來源時先 stat_topic("主題", region)。
2. stat_get_source(id) 看來源規格與操作說明（口徑與陷阱段一定要讀）。
3. 拉資料：
   - 01a/06a/10a 目錄細項的 varval3 網址 → stat_query_dgbas(url, years, areas)（嘉義、臺南、屏東同一套系統）
   - 縣市公務統計報表清冊 → stat_cyhg_reports(county="嘉義縣"|"屏東縣", office, year)
   - 屏東縣統計年報（107～114 年版）→ stat_pingtung_yearbook(year, table="4-1")
   - 鄉鎮×作物 → stat_afa_crops(類別) 取代號 → stat_query_afa(...)
   - 氣候表 → stat_climate(測站, 起年, 迄年)
   - 嘉義公務統計報表有哪些表號／期別 → stat_cyhg_reports(機關代碼, 年度)
   - 已歸檔原始報表 → stat_list_local_files → stat_read_local

鐵律（回答時要提醒使用者）：
- 寫進書件的縣內數字走「公務統計報表」原始小數（01b、06b）；01a 資料庫查詢平台把小數四捨五入掉了，只適合看趨勢。
- 同一張表不可混用來源；改書件前先用新來源回測書中既有年度，逐格相符才寫新年度。
- 農業部 AB04 水產養殖「養殖合計」不含休養；年報/漁業署「總計」含休養。

普查（人口及住宅／農林漁牧業／工業及服務業，含鄉鎮別）：stat_census_items 查統計項與可搭配分類 → stat_census_query 即時查並入庫。
  動態查詢查不到的細項（如農事及畜牧服務業各區家數）→ stat_census_tables（普查結果統計表，按縣市別每縣市約 40 張，用到才下載）。

本機統計資料庫（資料庫/stat.sqlite）：
- 02 農業部統計處（qcode 全選查詢）、03 漁業署年報（分包 zip）、06b 臺南市統計年報（各章 ODS）可自動下載解析入庫：
  一般用 stat_fetch（用到才下載：已入庫直接查、沒有就當場抓）；stat_search 會標示「已入庫」與每年格數。
  手動控制：stat_db_harvest → stat_db_list／stat_db_find 找表 → stat_db_sheet 看原始格子 → stat_db_query 用 SQL 取數。
- facts 的 col_label／year／area 是解析器推定的；寫進書件前一定要用 stat_db_sheet 對照原始格子。
"""

mcp = FastMCP("stat-hub", instructions=INSTRUCTIONS)
_IDX = None


def idx():
    global _IDX
    if _IDX is None:
        _IDX = build_index()
    return _IDX


def _terms(q):
    return [t for t in (q or "").lower().split() if t]


def _hit(text, terms):
    low = text.lower()
    return all(t in low for t in terms)


def _region_ok(src_id, region):
    if not region or region == "全部":
        return True
    s = next((x for x in idx()["sources"] if x["id"] == src_id), None)
    if not s:
        return True
    if region.startswith("全國"):
        return s["地區"].startswith("全國")
    return s["地區"] == region.replace("台", "臺")


def _src_brief(s):
    return {k: s.get(k) for k in ("id", "名稱", "機關", "地區", "空間解析度", "精度", "最新年度", "網址")}


def _loaded_ids():
    if not store.DB_PATH.exists():
        return set()
    try:
        return {r[0] for r in _ro().execute("SELECT dataset_id || '|' || coalesce(note,'') FROM datasets")}
    except Exception:  # noqa: BLE001
        return set()


def _is_loaded(item, loaded):
    c = item["c"]
    if item["s"] == "02":
        return any(x.startswith(f"agrstat:{c}|") for x in loaded)
    if c.startswith("fa:") and c.count(":") == 2:
        _, y, part = c.split(":")
        return any(x.startswith(f"fa:{y}:") and f"|第{part}包" in x for x in loaded)
    if c.startswith("tainan:"):
        return any(x.startswith(c + "|") for x in loaded)
    return False


@mcp.tool()
def stat_search(query: str, region: str = "全部", kinds: list[str] | None = None, limit: int = 30) -> dict:
    """關鍵字搜尋全部統計來源知識（空白分隔＝同時符合）。

    query: 中文關鍵字、表號或代碼，如「養殖」「家禽 臺南」「20351」「AB04」「氣溫」。
    region: 全部｜嘉義縣｜臺南市｜全國（只影響來源與目錄細項）。
    kinds: 限定類別子集 ["topic","usage","pitfall","source","item"]，預設全部。
    limit: 目錄細項最多回幾筆。
    回傳各類命中；目錄細項的 url 可直接丟給 stat_query_dgbas（01a/06a）或給使用者開。
    """
    d, t = idx(), _terms(query)
    kinds = set(kinds or ["topic", "usage", "pitfall", "source", "item"])
    out = {}
    if "topic" in kinds:
        out["主題速查"] = [x for x in d["topics"] if _hit(" ".join(x.values()), t)]
    if "usage" in kinds:
        out["案件用表"] = [x for x in d["usage"] if _hit(" ".join(x.values()), t)]
    if "pitfall" in kinds:
        out["口徑地雷"] = [x for x in d["pitfalls"] if _hit(x["地雷"] + " " + x["說明"], t)]
    if "source" in kinds:
        out["來源"] = [_src_brief(s) for s in d["sources"]
                     if _region_ok(s["id"], region) and _hit(json.dumps(s, ensure_ascii=False), t)]
    if "item" in kinds:
        names = {s["id"]: s["名稱"] + s["機關"] + s["地區"] for s in d["sources"]}
        hits = [i for i in d["items"]
                if _region_ok(i["s"], region) and _hit(" ".join([i["n"], i["p"], i["c"], i.get("k", ""), names.get(i["s"], "")]), t)]
        # 表名直接命中的排前面，只靠維度項目命中的排後面
        region_of = {s["id"]: s["地區"] for s in d["sources"]}

        def rank(i):
            direct = _hit(" ".join([i["n"], i["p"], i["c"], region_of.get(i["s"], "")]), t)
            pdf_only = i.get("meta", {}).get("格式") == ["pdf"]
            return (0 if direct else 1, 2 if pdf_only else (1 if i["s"] == "09t" else 0))
        hits.sort(key=rank)
        loaded = _loaded_ids()
        out["目錄細項_總數"] = len(hits)
        out["目錄細項"] = []
        for i in hits[:limit]:
            row = {"id": i["id"], "來源": i["s"], "名稱": i["n"], "代碼": i["c"], "路徑": i["p"], "url": i["u"]}
            if i.get("meta"):
                row.update(i["meta"])
            if i["s"] in ("02", "03", "06b"):
                row["已入庫"] = _is_loaded(i, loaded)
                row["取數"] = "stat_fetch 會自動下載入庫" if not row["已入庫"] else "stat_fetch 直接查庫"
            out["目錄細項"].append(row)
    return {k: v for k, v in out.items() if v not in ([], None)} or {"結果": f"查無「{query}」，試同義詞（養殖／魚塭、家禽／雞、雨量／降水）"}


@mcp.tool()
def stat_get_source(source_id: str, include_guide: bool = True) -> dict:
    """取得單一來源的完整規格：入口網址、解析度、精度、最新年度、適合查什麼、相關腳本，
    以及該來源 操作說明.md 全文（網站層級、查詢操作、口徑與陷阱）。
    source_id: 01a 01b 01c 02 03 04 05a 05b 06a 06b 07 08 X1–X4（可先 stat_search 取得）。"""
    s = next((x for x in idx()["sources"] if x["id"].lower() == source_id.lower()), None)
    if not s:
        return {"錯誤": "查無來源", "可用": [x["id"] + " " + x["名稱"] for x in idx()["sources"]]}
    out = dict(s)
    out["目錄細項數"] = sum(1 for i in idx()["items"] if i["s"] == s["id"])
    out["相關地雷"] = [p for p in idx()["pitfalls"] if p.get("來源") == s["id"]]
    out["用過的案件表"] = [u for u in idx()["usage"] if u["來源"] == s["id"]]
    if include_guide and s.get("說明檔"):
        out["操作說明全文"] = (ROOT / s["說明檔"]).read_text(encoding="utf-8")
    return out


@mcp.tool()
def stat_topic(query: str = "", region: str = "全部") -> list[dict]:
    """主題速查：某類資料（耕地、養殖、畜牧、作物、稻米、氣候、灌溉、重劃、非都市土地、農機林漁、人口）
    在嘉義縣／臺南市／全國各該去哪個來源、哪個表號拿。query 空白回全部主題。"""
    cols = ["嘉義縣", "臺南市", "屏東縣", "全國／跨縣市"] if region in ("", "全部") else [
        "全國／跨縣市" if region.startswith("全國") else region.replace("台", "臺")]
    t = _terms(query)
    return [{"主題": x["主題"], **{c: x.get(c, "—（尚未整理）") for c in cols}} for x in idx()["topics"] if _hit(" ".join(x.values()), t)]


@mcp.tool()
def stat_case_usage(case: str = "", query: str = "") -> list[dict]:
    """案件實際用過的表：表號、來源、更新狀態、回測與口徑備註。
    case: 嘉義農再｜臺南農再｜空白＝全部；query: 再以關鍵字過濾（如 表2-9、養殖、待辦）。"""
    t = _terms(query)
    return [u for u in idx()["usage"] if (not case or case.replace("台", "臺") in u["案件"]) and _hit(" ".join(u.values()), t)]


@mcp.tool()
def stat_pitfalls(query: str = "") -> list[dict]:
    """跨來源口徑地雷清單（休養口徑、平年值 vs 自算、表號改制、ODS 分頁、遮蔽值…）。query 空白回全部。"""
    t = _terms(query)
    return [p for p in idx()["pitfalls"] if _hit(p["地雷"] + " " + p["說明"], t)]


@mcp.tool()
def stat_query_dgbas(url: str, years: list[int] | None = None, areas: list[str] | None = None, max_rows: int = 300) -> dict:
    """即時查詢嘉義縣（01a）、臺南市（06a）或屏東縣（10a）主計處資料庫查詢平台的統計項目。

    url: stat_search 目錄細項的 varval3.aspx 網址。
    years: 年度，民國或西元皆可（如 [113,114]）；空白＝全部年度。
    areas: 地區名稱片段（如 ["嘉義縣","民雄"]、["臺南市","新營"]）；空白＝全部。
    ⚠ 01a 嘉義平台數值已四捨五入成整數，不可直接寫進書件（改走公務統計報表 01b）；屏東平台保留小數。"""
    r = fetchers.dgbas_query(url, years, areas)
    total = len(r["rows"])
    r["rows"] = r["rows"][:max_rows]
    r["total_rows"] = total
    if "cyhg" in url:
        r["提醒"] = "嘉義資料庫查詢平台已四捨五入；書件數字請改抓公務統計報表（stat_cyhg_reports 查表號）"
    return r


@mcp.tool()
def stat_afa_crops(category: str) -> dict:
    """農糧署作物代號清單。category: 01雜糧 02蔬菜 03果品 04牧草 05特用作物 06花卉 07綠肥 08其他。
    農糧署沒有類別合計，類別值要自己加總代號（蔬菜要剔除菇類 951 以後；柑橘類＝603–618）。"""
    return {"類別": fetchers.AFA_CATS.get(category, category), "作物": fetchers.afa_crops(category)}


@mcp.tool()
def stat_query_afa(year: int, county: str, category: str, crop: str, season: str = "03") -> dict:
    """即時查詢農糧署農情報告資源網「鄉鎮作物」：某年×縣市×作物 的各鄉鎮種植／收穫面積與收量。

    year: 民國年（86–114）；county: 縣市全名，如 嘉義縣、臺南市；
    category: 作物類別碼（01–08）；crop: 作物代號（stat_afa_crops 查）；
    season: 00裡作 01一期作 02二期作 03全年作（預設）。"""
    rows = fetchers.afa_query(year, county, category, crop, season)
    return {"year": year, "county": county, "crop": crop, "rows": rows,
            "note": "收量單位為公斤；書件多用公噸（÷1000）。製糖甘蔗不在此站（台糖提供）。"}


@mcp.tool()
def stat_climate(station_id: str, start_year: int, end_year: int, refresh: bool = False) -> dict:
    """CODiS 測站逐月觀測 → 指定期間氣候統計表（月均最高/平均/最低溫、降水中位數、日照），
    並回報缺測月份。常用測站：臺南 467410、嘉義 467480。資料快取 7 天，refresh=True 強制重抓。
    ⚠ 官方 30 年平年值（1991–2020）有補遺，降水量會與自算值差很多；換統計期間要在書件註明。"""
    return fetchers.climate_stats(station_id, start_year, end_year, refresh)


@mcp.tool()
def stat_cyhg_reports(office: str = "", year: str = "", query: str = "", county: str = "嘉義縣") -> dict:
    """即時查詢縣市主計處「公務統計報表查詢」(stat08) 的報表清冊（表號、表名、格式、期別）。書件數字應走這裡的原始報表。
    county：嘉義縣｜屏東縣（同一套系統）。office：機關代碼，各縣市不同——
      嘉義：農業處 3007、民政處 3002、地政處 3008、社會局 5007；屏東：農業處 3005、地政處 3007、海洋及漁業事務管理所 5007。
      不給 office → 回傳該縣市機關代碼表。year：民國年，空白＝最新；query：表名關鍵字再過濾。
    ⚠ 嘉義表號在 113／114 年改制，舊表號查新年度會查無資料。
    下載報表本體請到該縣市 stat08.aspx 以表號查詢。"""
    if not office:
        return {"county": county, "機關代碼": fetchers.stat08_offices(county.replace("台", "臺")), "網址": fetchers.STAT08.get(county.replace("台", "臺"))}
    r = fetchers.stat08_report_list(county, office, year)
    t = _terms(query)
    r["rows"] = [x for x in r["rows"] if _hit(x["no"] + " " + x["name"], t)]
    return r

@mcp.tool()
def stat_list_local_files(filter: str = "") -> list[dict]:
    """列出案件資料夾已歸檔的原始報表與中繼資料（ods/xlsx/xls/csv/json/pdf）。filter: 路徑片段，如 嘉義、臺南、2241。"""
    return fetchers.list_local(filter)


@mcp.tool()
def stat_read_local(path: str, sheet: str | None = None, max_rows: int = 200) -> dict:
    """讀取已歸檔的原始報表。試算表不給 sheet 時先回分頁清單。
    path: stat_list_local_files 回傳的 repo 相對路徑。"""
    return fetchers.read_local(path, sheet, max_rows)


# ====================================================================== 本機統計資料庫
@mcp.tool()
def stat_db_harvest(source: str, year: int | None = None, qcode: str = "", year_begin: int | None = None,
                    year_end: int | None = None, parts: list[str] | None = None) -> dict:
    """自動上網下載 → 解析 → 存入本機統計資料庫（同一資料集重抓即覆蓋）。

    source="agrstat"：農業部統計處，需 qcode（如 AB01、AB04、CC05），year_begin～year_end 民國年（預設近 11 年）。
        所有統計量與維度全選；超過平台 15,000 格上限會自動依年度分段。先用 stat_agrstat_meta 看維度。
    source="fa"：漁業署漁業統計年報，year＝民國年，parts＝分包號（預設 ["7"] 漁業生產量／水產養殖面積）。
    source="tainan"：臺南市統計年報，year＝民國年，parts＝章號（預設 ["04"] 農林漁牧；01土地、02人口…）。
    原始檔存 資料庫/原始檔/，datasets 表記錄網址與 sha256。"""
    if source == "agrstat":
        if not qcode:
            return {"錯誤": "需要 qcode"}
        ye = year_end or 114
        return harvest.harvest_agrstat(qcode.upper(), year_begin or ye - 10, ye)
    if source == "fa":
        return {"results": harvest.harvest_fa(year, [int(p) for p in (parts or ["7"])])}
    if source == "tainan":
        return {"results": harvest.harvest_tainan(year, parts or ["04"])}
    return {"錯誤": "source 只接受 agrstat／fa／tainan"}


@mcp.tool()
def stat_agrstat_meta(qcode: str) -> dict:
    """農業部統計處某 qcode 的統計量、維度與各維度項目、可選年度（不查資料，用來判斷要不要入庫、格數多大）。"""
    return harvest.agrstat_meta(qcode.upper())


def _ro():
    import sqlite3
    if not store.DB_PATH.exists():
        raise ValueError("本機統計資料庫尚未建立，先用 stat_db_harvest 入庫")
    return sqlite3.connect(f"file:{store.DB_PATH.as_posix()}?mode=ro", uri=True)


@mcp.tool()
def stat_db_list(query: str = "") -> list[dict]:
    """列出已入庫的資料集與工作表（sheet_id、表名、筆數、取得時間、原始檔）。query 以關鍵字過濾表名／分頁名。"""
    con = _ro()
    rows = con.execute("""SELECT d.dataset_id, d.source, d.title, d.year, d.fetched_at, d.local_path,
                                 s.sheet_id, s.sheet_name, s.title, s.unit, s.n_facts
                          FROM sheets s JOIN datasets d USING(dataset_id) ORDER BY d.dataset_id, s.sheet_id""").fetchall()
    t = _terms(query)
    out = []
    for r in rows:
        if _hit(" ".join(str(x) for x in r), t):
            out.append({"dataset_id": r[0], "來源": r[1], "資料集": r[2], "年度": r[3], "取得時間": r[4], "原始檔": r[5],
                        "sheet_id": r[6], "分頁": r[7], "表名": r[8], "單位": r[9], "數值筆數": r[10]})
    return out


@mcp.tool()
def stat_db_find(query: str, year: int | None = None, area: str = "", source: str = "", limit: int = 100) -> dict:
    """在已入庫的數值中找資料：query 關鍵字（空白分隔＝同時符合）比對 分頁名＋表名＋列標籤＋欄標籤。
    year：民國年；area：地區（如 嘉義縣、新營區）；source：02／03／06b。
    回傳每筆的 sheet_id、列欄標籤、數值與原始字樣。"""
    con = _ro()
    sql = """SELECT f.sheet_id, s.sheet_name, s.title, f.row_label, f.col_label, f.year, f.area, f.value, f.raw, s.unit
             FROM facts f JOIN sheets s USING(sheet_id) WHERE 1=1"""
    args = []
    for term in _terms(query):
        sql += " AND (lower(s.sheet_name||' '||coalesce(s.title,'')||' '||f.row_label||' '||f.col_label) LIKE ?)"
        args.append(f"%{term}%")
    if year is not None:
        sql += " AND f.year=?"; args.append(year)
    if area:
        sql += " AND (f.area LIKE ? OR f.row_label LIKE ? OR f.col_label LIKE ?)"; args += [f"%{area}%"] * 3
    if source:
        sql += " AND f.source=?"; args.append(source)
    rows = con.execute(sql + " LIMIT ?", args + [limit + 1]).fetchall()
    keys = ["sheet_id", "分頁", "表名", "列", "欄", "年度", "地區", "數值", "原始", "單位"]
    return {"筆數": min(len(rows), limit), "還有更多": len(rows) > limit, "rows": [dict(zip(keys, r)) for r in rows[:limit]]}


@mcp.tool()
def stat_db_sheet(sheet_id: int, start_row: int = 0, max_rows: int = 80, max_cols: int = 40) -> dict:
    """看某工作表的原始格子（合併格已填滿），用來核對解析出來的欄位對應。"""
    con = _ro()
    r = con.execute("SELECT dataset_id, sheet_name, title, unit, n_header, n_label, raw_json FROM sheets WHERE sheet_id=?",
                    (sheet_id,)).fetchone()
    if not r:
        return {"錯誤": "查無 sheet_id"}
    grid = json.loads(r[6])
    return {"dataset_id": r[0], "分頁": r[1], "表名": r[2], "單位": r[3], "表頭列數": r[4], "標籤欄數": r[5],
            "總列數": len(grid), "rows": [row[:max_cols] for row in grid[start_row:start_row + max_rows]]}


@mcp.tool()
def stat_db_query(sql: str, limit: int = 500) -> dict:
    """唯讀 SQL 查詢本機統計資料庫（SQLite）。表：
    datasets(dataset_id, source, title, year, url, local_path, sha256, fetched_at, note)
    sheets(sheet_id, dataset_id, sheet_name, title, unit, n_header, n_label, n_facts, raw_json)
    facts(sheet_id, dataset_id, source, row_no, col_no, row_label, col_label, year, area, value, raw)
    例：SELECT row_label, col_label, value FROM facts WHERE dataset_id='agrstat:AB01' AND area='嘉義縣' AND year=114"""
    if not re.match(r"^\s*(select|with)\b", sql, re.I):
        return {"錯誤": "只允許 SELECT／WITH"}
    con = _ro()
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchmany(limit + 1)
    return {"columns": cols, "rows": [list(r) for r in rows[:limit]], "truncated": len(rows) > limit}

@mcp.tool()
def stat_fetch(source: str, qcode: str = "", year: int | None = None, year_begin: int | None = None,
               year_end: int | None = None, part: str = "", query: str = "", area: str = "",
               refresh: bool = False, limit: int = 200) -> dict:
    """「用到才下載」取數：資料庫已有就直接查；沒有（或年度不夠）就當場上網下載、解析、入庫後再查。

    source="agrstat"：qcode 必填；year_begin～year_end 民國年（預設該表最近 11 年）。
    source="fa"：year（民國年）、part（分包號，預設 "7" 漁業生產量／水產養殖面積）。
    source="tainan"：year（民國年）、part（章號，預設 "04" 農林漁牧）。
    query／area：在取回的數值中再以關鍵字、地區過濾（同 stat_db_find）。refresh=True 強制重抓。
    先用 stat_search 找 qcode／分包／章；回傳的 sheet_id 可用 stat_db_sheet 核對原始格子。"""
    import sqlite3
    downloaded = None
    con = store.connect()
    if source == "agrstat":
        q = qcode.upper()
        st = next((i.get("meta") for i in idx()["items"] if i["s"] == "02" and i["c"] == q), None)
        last = int(st["年度"].split("~")[1]) if st and st.get("年度") else 114
        yb, ye = year_begin or last - 10, year_end or last
        row = con.execute("SELECT note FROM datasets WHERE dataset_id=?", (f"agrstat:{q}",)).fetchone()
        have = re.match(r"(\d+)-(\d+)", row[0]) if row and row[0] else None
        if refresh or not have or int(have.group(1)) > yb or int(have.group(2)) < ye:
            if have and not refresh:  # 與既有範圍合併，避免縮小
                yb, ye = min(yb, int(have.group(1))), max(ye, int(have.group(2)))
            downloaded = harvest.harvest_agrstat(q, yb, ye)
        ds_filter, args = "f.dataset_id=?", [f"agrstat:{q}"]
        if year_begin or year_end:
            ds_filter += " AND f.year BETWEEN ? AND ?"
            args += [year_begin or 0, year_end or 999]
    elif source == "fa":
        y, pk = int(year), str(part or "7")
        n = con.execute("SELECT count(*) FROM datasets WHERE dataset_id LIKE ? AND note LIKE ?",
                        (f"fa:{y}:%", f"第{pk}包%")).fetchone()[0]
        if refresh or not n:
            downloaded = harvest.harvest_fa(y, [int(pk)])
        ds_filter = "f.dataset_id IN (SELECT dataset_id FROM datasets WHERE dataset_id LIKE ? AND note LIKE ?)"
        args = [f"fa:{y}:%", f"第{pk}包%"]
    elif source == "tainan":
        y, c = int(year), f"{int(part or 4):02d}"
        n = con.execute("SELECT count(*) FROM datasets WHERE dataset_id=?", (f"tainan:{y}:{c}",)).fetchone()[0]
        if refresh or not n:
            downloaded = harvest.harvest_tainan(y, [c])
        ds_filter, args = "f.dataset_id=?", [f"tainan:{y}:{c}"]
    else:
        return {"錯誤": "source 只接受 agrstat／fa／tainan"}
    con.close()
    sql = f"""SELECT f.sheet_id, s.sheet_name, s.title, f.row_label, f.col_label, f.year, f.area, f.value, f.raw, s.unit
              FROM facts f JOIN sheets s USING(sheet_id) WHERE {ds_filter}"""
    for term in _terms(query):
        sql += " AND (lower(s.sheet_name||' '||coalesce(s.title,'')||' '||f.row_label||' '||f.col_label) LIKE ?)"
        args.append(f"%{term}%")
    if area:
        sql += " AND (f.area LIKE ? OR f.row_label LIKE ? OR f.col_label LIKE ?)"
        args += [f"%{area}%"] * 3
    rows = _ro().execute(sql + " ORDER BY f.sheet_id, f.row_no, f.col_no LIMIT ?", args + [limit + 1]).fetchall()
    keys = ["sheet_id", "分頁", "表名", "列", "欄", "年度", "地區", "數值", "原始", "單位"]
    sheets = sorted({r[0] for r in rows})
    return {"本次下載": downloaded or "否（資料庫已有）", "筆數": min(len(rows), limit), "還有更多": len(rows) > limit,
            "sheet_ids": sheets[:50], "rows": [dict(zip(keys, r)) for r in rows[:limit]],
            "提醒": "欄位標籤為解析器推定，寫進書件前用 stat_db_sheet 對照原始格子"}

# ====================================================================== 09 三大普查
@mcp.tool()
def stat_census_items(query: str = "", kind: str = "", limit: int = 40) -> dict:
    """主計總處三大普查動態查詢系統的統計項清單（不連網，讀結構.json）。
    query：關鍵字（空白分隔＝同時符合，比對統計項名稱、路徑、可搭配複分類）；
    kind：人口／農林漁牧／工業（只看該普查）。回傳每個統計項可搭配的複分類（如 縣市別、鄉鎮別、經營種類別）與單位。
    普查年度：人口及住宅 89/99/109、農林漁牧業 94/99/104/109、工業及服務業 95/100/105/110（5 或 10 年一次）。"""
    st = census.load()
    t = _terms(query)
    hits = []
    for it in st["items"]:
        if kind and kind not in it["kind"]:
            continue
        cls = sorted({n for v in it["variants"] for n in v["分類"]})
        if _hit(" ".join([it["name"], it["path"], it["kind"]] + cls), t):
            hits.append({"idx": it["idx"], "統計項": it["name"], "普查": it["kind"], "路徑": it["path"],
                         "單位": next((v["unit"] for v in it["variants"] if v["unit"]), ""), "可搭配複分類": cls})
    return {"普查年度": [y["name"] for y in st["years"]], "總數": len(hits), "items": hits[:limit]}


@mcp.tool()
def stat_census_query(census_name: str, items: list[str], rows: list[str] | None = None, cols: list[str] | None = None,
                      area: str = "", save: bool = True, limit: int = 400) -> dict:
    """即時查詢三大普查動態查詢系統，並（預設）存入本機統計資料庫。

    census_name：如 "109農林漁牧"、"104年農林漁牧業普查"、"110工業及服務"、"109人口"。
    items：統計項名稱（≤10，用 stat_census_items 查，例 ["農牧業普查家數"]）。
    rows／cols：表側／表頭複分類（合計 ≤3，例 rows=["鄉鎮別"]、cols=["經營種類別"]），統計項必須能搭配。
    area：只回傳含此字串的列（如 "嘉義縣"、"臺南市"），不影響入庫內容。
    ⚠ 普查是 5 年一次；農林漁牧業普查最新為 109 年（114 年普查結果尚未發布），工業及服務業最新 110 年。"""
    r = census.query(census_name, items, rows or [], cols or [])
    saved = None
    if save and r["data"] and not r["warnings"]:
        import hashlib
        key = hashlib.md5(json.dumps([r["census"], r["items"], r["rows"], r["cols"]], ensure_ascii=False).encode()).hexdigest()[:10]
        tmp = store.RAW_DIR / "census" / f"{key}.json"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
        con = store.connect()
        title = f"{r['census']} {'、'.join(i['name'] for i in r['items'])} × {'、'.join(r['rows'] + r['cols']) or '全國'}"
        saved = store.save_dataset(con, f"census:{key}", "09", title, int(re.match(r'\d+', r['census']).group()),
                                   census.MAIN, tmp, [(title[:60], census.to_grid(r))])
        con.close()
    data = [{k: v for k, v in d.items() if k != "area"} for d in r["data"]
            if not area or any(area.replace("台", "臺") in str(v) for v in d.values())]
    return {"普查": r["census"], "統計項": r["items"], "表側": r["rows"], "表頭": r["cols"], "總列數": len(r["data"]),
            "回傳列數": min(len(data), limit), "data": data[:limit],
            "警告": r["warnings"], "入庫": {k: saved[k] for k in ("dataset_id", "facts")} if saved else "未入庫"}

@mcp.tool()
def stat_census_tables(census_name: str, year: int, part: str = "", table: str = "", query: str = "", area: str = "",
                       refresh: bool = False, limit: int = 300) -> dict:
    """主計總處「普查結果統計表」（靜態 ODS／XLSX），用到才下載入庫。動態查詢（stat_census_query）查不到的
    鄉鎮別細項（例：農事及畜牧服務業各區家數）多半在這裡。

    census_name：農林漁牧／人口／工業；year：普查年（農林漁牧 84–109、人口 79–109、工商 95–110）。
    part：子頁，通常是縣市名（臺南市、嘉義縣）或業別（農牧業、漁業…）。
    table：表名關鍵字（空白分隔＝同時符合），如「統計結果摘要」「農事及畜牧服務業家數」。
      不給 table → 只列出該子頁有哪些表（不下載）。
    query／area：在取回的數值中再以關鍵字、地區過濾。refresh=True 強制重新下載。
    範例：stat_census_tables("農林漁牧", 109, part="臺南市", table="統計結果摘要", area="新營區")"""
    tabs = census_tables.list_tables(census_name, year, part, table)
    if not table:
        return {"說明": "未指定 table，僅列出可用統計表；指定 table 後會下載入庫並回傳數值",
                "總數": len(tabs), "tables": [{"子頁": x["path"] + ("（" + x["sub"] + "）" if x["sub"] not in x["path"] else ""), "表名": x["table"],
                                              "格式": [f["title"].rsplit(".", 1)[-1] for f in x["files"]]} for x in tabs[:200]]}
    cname = census_tables._census_name(census_name)
    con = store.connect()
    have = {r[0] for r in con.execute("SELECT dataset_id FROM datasets WHERE dataset_id LIKE ?", (f"censustab:{cname}:{year}:%",))}
    con.close()
    need = [x for x in tabs if refresh or f"censustab:{cname}:{year}:{x['sub']}:{x['table']}" not in have]
    downloaded = census_tables.harvest(cname, year, part, table) if need else "否（資料庫已有）"
    ids = []
    for x in tabs:
        ids.append(f"censustab:{cname}:{year}:{x['sub']}:{x['table']}")
    sql = f"""SELECT f.sheet_id, s.dataset_id, s.title, f.row_label, f.col_label, f.year, f.area, f.value, f.raw, s.unit
              FROM facts f JOIN sheets s USING(sheet_id) WHERE f.dataset_id IN ({','.join('?' * len(ids))})"""
    args = list(ids)
    for term in _terms(query):
        sql += " AND (lower(s.title||' '||f.row_label||' '||f.col_label) LIKE ?)"
        args.append(f"%{term}%")
    if area:
        sql += " AND (f.area LIKE ? OR f.row_label LIKE ?)"
        args += [f"%{area.replace('台', '臺')}%"] * 2
    rows = _ro().execute(sql + " ORDER BY f.sheet_id, f.row_no, f.col_no LIMIT ?", args + [limit + 1]).fetchall()
    keys = ["sheet_id", "dataset_id", "表名", "列", "欄", "年度", "地區", "數值", "原始", "單位"]
    return {"本次下載": downloaded, "符合統計表": [x["table"] for x in tabs], "筆數": min(len(rows), limit),
            "還有更多": len(rows) > limit, "rows": [dict(zip(keys, r)) for r in rows[:limit]],
            "提醒": "數值以空白為千分位、「-」＝0；欄位標籤為推定，寫書件前用 stat_db_sheet 對照原始格子"}

@mcp.tool()
def stat_pingtung_yearbook(year: int | None = None, table: str = "", query: str = "", area: str = "", limit: int = 200) -> dict:
    """屏東縣統計年報（10c，統計刊物整份 zip，107～114 年），用到才下載。
    year：年報年度（民國，預設最新）；table：表號如 "4-1"；query：關鍵字；area：鄉鎮（如 萬丹）。
      - 只給 year → 列出該年各表（章、表號、表名、格式）。
      - 給 query、不給 table → 全文搜尋已下載年度的年報文字，回傳命中表與片段。
      - 給 table → 107～113 年版為試算表（XLS／XLSX／ODS）：回傳解析後數值（可再用 query／area 過濾）；
        114 年版只有文字型 PDF：回傳原文文字，數值請改用附上的 10a 平台同號表網址（stat_query_dgbas）。
    ⚠ 屏東首頁的「統計年報資料庫」（winstapx PX-Web）已下線；可程式查詢的後繼為 10a 平台「統計年報查詢」，表號相同。"""
    eds = pingtung_yearbook.editions()
    y = int(year or max(int(k) for k in eds))
    info = pingtung_yearbook.ensure(y)
    con = store.connect()
    con.execute(pingtung_yearbook.DOCS_SQL)
    if not table and query:
        hits = []
        for doc_id, yy, tno, title, text in con.execute(
                "SELECT doc_id, year, table_no, title, text FROM docs WHERE source='10c' ORDER BY year DESC, table_no"):
            if _hit(text + " " + title, _terms(query)):
                i = max(0, min(text.find(t) for t in _terms(query) if t in text) - 40) if any(t in text for t in _terms(query)) else 0
                hits.append({"doc_id": doc_id, "年報": yy, "表號": tno, "表名": title, "片段": " ".join(text[i:i + 160].split())})
        con.close()
        return {"已下載年度": [r for r in sorted(eds)], "命中": len(hits), "results": hits[:limit]}
    if not table:
        rows = con.execute("SELECT chapter, table_no, title, local_path FROM docs WHERE source='10c' AND year=? ORDER BY chapter, table_no", (y,)).fetchall()
        con.close()
        return {"年報": y, "下載": info, "表數": len(rows),
                "tables": [{"章": c, "表號": n, "表名": ti, "格式": p.rsplit(".", 1)[-1]} for c, n, ti, p in rows]}
    tno = table.replace("表", "").replace(" ", "")
    g = pingtung_yearbook.get(y, tno)
    con.close()
    eq = pingtung_yearbook.titles_10a().get(tno, {})
    out = {"年報": y, "表號": tno, "表名": g["表名"], "章": g["章"], "原始檔": g["原始檔"],
           "10a平台同號表": {"表名": eq.get("title"), "統計項目": eq.get("items", [])[:10],
                         "說明": "數值可用 stat_query_dgbas(url, years, areas) 程式查（保留小數）"}}
    if g["原始檔"].lower().endswith(".pdf"):
        out["格式"] = "PDF（文字型，欄位擠在一起，不自動拆數值）"
        out["text"] = g["text"][:6000]
        return out
    sql = """SELECT f.sheet_id, f.row_label, f.col_label, f.year, f.area, f.value, f.raw FROM facts f
             WHERE f.dataset_id=?"""
    args = [f"ptyb:{y}:{tno}"]
    for term in _terms(query):
        sql += " AND lower(f.row_label||' '||f.col_label) LIKE ?"
        args.append(f"%{term}%")
    if area:
        sql += " AND (f.area LIKE ? OR f.row_label LIKE ?)"
        args += [f"%{area}%"] * 2
    rows = _ro().execute(sql + " ORDER BY f.sheet_id, f.row_no, f.col_no LIMIT ?", args + [limit + 1]).fetchall()
    out["格式"] = "試算表（" + g["原始檔"].rsplit(".", 1)[-1].upper() + "，已解析數值）"
    out["筆數"] = min(len(rows), limit)
    out["還有更多"] = len(rows) > limit
    out["rows"] = [dict(zip(["sheet_id", "列", "欄", "年度", "地區", "數值", "原始"], r)) for r in rows[:limit]]
    return out

@mcp.tool()
def stat_query_ntpc(table_id: str, years: list[int] | None = None, areas: list[str] | None = None, max_rows: int = 300) -> dict:
    """即時查詢新北市政府資料庫查詢平台（11-新北市，改版介面，不能用 stat_query_dgbas）。
    table_id：表 ID（stat_search 目錄細項代碼為 ntpc:<ID>，例 11878＝農耕土地面積_103年以後）。
    years：民國或西元年；areas：區名片段（如 ["新北市","板橋"]），空白＝全部 29 區＋全市。"""
    r = ntpc.query(str(table_id).replace("ntpc:", ""), years, areas)
    total = len(r["rows"])
    r["rows"] = r["rows"][:max_rows]
    r["total_rows"] = total
    return r

@mcp.tool()
def stat_query_kcg(ma: str, years: list[int] | None = None, areas: list[str] | None = None, max_rows: int = 300) -> dict:
    """即時查詢高雄市 PX-Web 多維度資料庫（11-高雄市，約 508 表）。
    ma：PX 矩陣代碼（stat_search 目錄細項代碼為 kcg:<ma>，例 AG300401RA＝耕地面積(2014~)）。
    years：民國或西元年（只篩「年／期」維度）；areas：地區名片段（只在有該名稱的維度生效）。
    ⚠ 部分表只有全市值、沒有區別（例：耕地面積），以回傳的 dims 為準。"""
    r = kcg.query(ma.replace("kcg:", ""), years, areas)
    total = len(r["rows"])
    r["rows"] = r["rows"][:max_rows]
    r["total_rows"] = total
    return r

@mcp.tool()
def stat_query_tpe(funid: str, years: list[int] | None = None, max_rows: int = 300) -> dict:
    """即時查詢臺北市統計資料庫查詢系統（11-臺北市，約 1,513 表）。
    funid：表代碼（stat_search 目錄細項代碼為 tpe:<funid>，例 a05013901＝農牧戶概況）。
    years：民國或西元年（取最小～最大；月資料取該區間各月），未給取最近 10 年。
    ⚠ 有分類維度的表目前只取網站預設選項（多為「總計」）；「-」照原樣保留。"""
    r = tpe.query(funid.replace("tpe:", ""), years)
    total = len(r["rows"])
    r["rows"] = r["rows"][:max_rows]
    r["total_rows"] = total
    return r


if __name__ == "__main__":
    mcp.run()
