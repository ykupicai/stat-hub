"""即時查詢層：直接向各政府統計平台取數。邏輯沿用 scripts/ 內已驗證的擷取器，
差別在於回傳結構化資料（給 MCP 工具用），而不是寫檔。

政府網站憑證常缺 Subject Key Identifier，一律 verify=False。
"""
import json
import re
import statistics as st
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
import urllib3
from lxml import html as LH

urllib3.disable_warnings()
ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(__file__).resolve().parent / ".cache"
sys.path.insert(0, str(ROOT / "scripts"))


def _session(referer=None):
    s = requests.Session()
    s.verify = False
    s.headers["User-Agent"] = "Mozilla/5.0"
    if referer:
        s.headers["Referer"] = referer
    return s


def _year_match(label, years):
    """平台年度標籤可能是民國（113年）或西元（2024），兩種都接受。"""
    m = re.search(r"\d{3,4}", label or "")
    if not m:
        return False
    v = int(m.group())
    want = set()
    for y in years:
        y = int(y)
        want |= {y, y + 1911} if y < 1000 else {y, y - 1911}
    return v in want


# ---------------------------------------------------------------- 01a / 06a 主計處資料庫查詢平台
DGBAS_HOSTS = {"cyhg.dgbas.gov.tw": "嘉義縣", "tainan.dgbas.gov.tw": "臺南市"}


def dgbas_query(varval_url, years=None, areas=None):
    """嘉義／臺南主計處資料庫查詢平台（同一套系統）varval3.aspx 統計項目查詢。
    回傳 {years_available, areas_available, rows}；rows[0..1] 為表頭。"""
    host = urlparse(varval_url).netloc.lower()
    if host not in DGBAS_HOSTS or "varval3.aspx" not in varval_url:
        raise ValueError("只接受 cyhg.dgbas.gov.tw 或 tainan.dgbas.gov.tw 的 varval3.aspx 網址（可由 stat_search 取得）")
    show = f"https://{host}/%e7%b6%b2%e9%a0%81%e8%b3%87%e6%96%99%e6%9f%a5%e8%a9%a2/ShowQuery.aspx"
    s = _session()
    d = LH.fromstring(s.get(varval_url, timeout=60).text)
    h = {i.get("name"): (i.get("value") or "") for i in d.xpath('//input[@type="hidden"]') if i.get("name")}
    dopts = [(o.get("value"), o.text_content().strip()) for o in d.xpath('//select[@id="LBDate"]/option')]
    alist = [(a.get("target"), (a.get("aria-label") or "").strip("'")) for a in d.xpath('//div[@id="TMenu"]//a[@target]')]
    years_avail = [lbl for _, lbl in dopts]
    areas_avail = [n for _, n in alist]
    dates = [v for v, lbl in dopts if not years or _year_match(lbl, years)]
    if areas:
        alist = [x for x in alist if any(a in x[1] for a in areas)]
    if not dates or not alist:
        return {"years_available": years_avail, "areas_available": areas_avail, "rows": [],
                "note": "年度或地區篩選後為空，請改用 years_available／areas_available 中的值"}
    acodes = [x[0] for x in alist]
    cx = {}
    for n in range(1, 6):
        opts = [o.get("value") for o in d.xpath(f'//select[@id="LBComplex{n}"]/option')]
        if opts:
            cx[n] = opts
    h["axX"] = "[Measures]" + "".join(";" + cx[n][0][:5] for n in sorted(cx))
    h["axY"] = "[Date];[Place]"
    h["axDate"] = "','".join(dates)
    h["axPlace"] = ";".join(acodes)
    h["axCode"] = "".join(";".join(cx[n]) + ";" for n in sorted(cx)) + ";".join(acodes)
    h["axFunction"] = ""
    p = list(h.items()) + [("functiontype", "")]
    p += [("LBDate", x) for x in dates] + [("chkBox", x) for x in acodes]
    for n in sorted(cx):
        p += [(f"LBComplex{n}", x) for x in cx[n]]
    p.append(("goon", "查詢"))
    r = s.post(show, data=p, headers={"Referer": varval_url}, timeout=180)
    dd = LH.fromstring(r.text)
    tbs = [t for t in dd.xpath("//table") if len(t.xpath(".//tr")) > 2]
    rows = [] if not tbs else [[" ".join(c.text_content().split()) for c in tr.xpath("./td|./th")]
                               for tr in tbs[0].xpath(".//tr")]
    return {"years_available": years_avail, "areas_available": areas_avail, "rows": rows}


# ---------------------------------------------------------------- 04 農糧署 農情報告資源網
AFA_COND = "https://agr.afa.gov.tw/afa/pgcroptown_cond.jsp"
AFA_RES = "https://agr.afa.gov.tw/afa/pgcroptown.jsp"
AFA_CROPS = "https://agr.afa.gov.tw/afa/ajax/jsonAfaCode1.jsp?corn001={}&input803="
AFA_CATS = {"01": "雜糧", "02": "蔬菜", "03": "果品", "04": "牧草", "05": "特用作物", "06": "花卉", "07": "綠肥", "08": "其他"}


def _afa_session():
    s = _session()
    d = LH.fromstring(s.get(AFA_COND, timeout=60).text)
    cities = {o.text_content().strip().split(".", 1)[-1]: o.get("value") for o in d.xpath('//select[@name="city"]/option')}
    return s, cities


def afa_crops(category):
    """作物代號清單（優先用 repo 內已驗證的 scripts/afa_crop_codes.json，缺的類別才連網）。"""
    local = json.loads((ROOT / "scripts" / "afa_crop_codes.json").read_text(encoding="utf-8"))
    if category in local:
        return [{"code": c, "name": n} for c, n in local[category]]
    r = _session().get(AFA_CROPS.format(category), timeout=60)
    try:
        data = r.json()
    except ValueError:
        data = json.loads(r.text.strip().strip(";"))
    out = []
    for x in data if isinstance(data, list) else data.get("data", []):
        if isinstance(x, dict):
            vals = list(x.values())
            out.append({"code": str(vals[0]), "name": str(vals[1]) if len(vals) > 1 else ""})
    return out


def afa_query(year, county, category, crop, season="03"):
    """單一年度×縣市×作物 → 各鄉鎮 結實(收穫)面積(公頃)、收量(公斤)。"""
    s, cities = _afa_session()
    code = cities.get(county.replace("台", "臺"))
    if not code:
        raise ValueError(f"縣市名稱不符，可用：{list(cities)}")
    r = s.post(AFA_RES, data={"accountingyear": str(year).zfill(3), "item": season, "corn001": category,
                              "crop": crop, "city": code, "btnSend": "送　出", "isPrint": ""}, timeout=120)
    d = LH.fromstring(r.text)

    def num(x):
        x = x.replace(",", "").strip()
        try:
            return float(x)
        except ValueError:
            return None

    out = []
    for t in d.xpath("//table"):
        rows = [[" ".join(c.text_content().split()) for c in tr.xpath("./td|./th")] for tr in t.xpath(".//tr")]
        if len(rows) < 2 or not rows[0] or "縣市鄉鎮名稱" not in rows[0][0]:
            continue
        for row in rows[2:]:
            if len(row) < 5:
                continue
            place = row[0].replace(" ", "").replace("台", "臺").replace(county.replace("台", "臺"), "")
            out.append({"鄉鎮": "合計" if place.startswith("合") else place,
                        "種植面積_公頃": num(row[1]), "收穫面積_公頃": num(row[2]),
                        "每公頃收量_公斤": num(row[3]), "收量_公斤": num(row[4])})
    return out


# ---------------------------------------------------------------- 05b CODiS
def codis_monthly(station_id, refresh=False):
    CACHE.mkdir(exist_ok=True)
    f = CACHE / f"codis_{station_id}.json"
    if f.exists() and not refresh and time.time() - f.stat().st_mtime < 7 * 86400:
        return json.loads(f.read_text(encoding="utf-8"))
    from cwa_codis_fetch import fetch_monthly
    j = fetch_monthly(station_id)
    f.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
    return j


def climate_stats(station_id, start_year, end_year, refresh=False):
    """依原書口徑統計期間氣候表：溫度取月平均之平均、降水取中位數、日照取平均；
    全年降水＝各完整年總量之中位數。回報每月有效年數與缺測月份。"""
    j = codis_monthly(station_id, refresh)
    rec = {}
    for dt in j["data"][0]["dts"]:
        ym = dt["DataYearMonth"][:7]
        y, m = int(ym[:4]), int(ym[5:7])
        at = dt.get("AirTemperature") or {}
        pr = dt.get("Precipitation") or {}
        sd = dt.get("SunshineDuration") or {}
        rec[(y, m)] = {"最高溫度": at.get("MeanDailyMaximum"), "平均溫度": at.get("Mean"),
                       "最低溫度": at.get("MeanDailyMinimum"), "降水量": pr.get("Accumulation"),
                       "日照時數": sd.get("Total")}
    keys = ["最高溫度", "平均溫度", "最低溫度", "降水量", "日照時數"]
    missing = [f"{y}-{m:02d}" for y in range(start_year, end_year + 1) for m in range(1, 13)
               if not rec.get((y, m)) or rec[(y, m)]["平均溫度"] is None]
    table = {k: [] for k in keys}
    n_years = []
    for m in range(1, 13):
        for k in keys:
            vs = [rec[(y, m)][k] for y in range(start_year, end_year + 1)
                  if rec.get((y, m)) and rec[(y, m)][k] is not None]
            agg = st.median if k == "降水量" else st.mean
            table[k].append(round(agg(vs), 1) if vs else None)
        n_years.append(len([1 for y in range(start_year, end_year + 1)
                            if rec.get((y, m)) and rec[(y, m)]["平均溫度"] is not None]))

    def annual(k):
        tot = []
        for y in range(start_year, end_year + 1):
            vs = [rec[(y, m)][k] for m in range(1, 13) if rec.get((y, m)) and rec[(y, m)][k] is not None]
            if len(vs) == 12:
                tot.append(sum(vs))
        return tot

    full = {"最高溫度": round(st.mean([v for v in table["最高溫度"] if v is not None]), 1),
            "平均溫度": round(st.mean([v for v in table["平均溫度"] if v is not None]), 1),
            "最低溫度": round(st.mean([v for v in table["最低溫度"] if v is not None]), 1),
            "降水量": round(st.median(annual("降水量")), 1) if annual("降水量") else None,
            "日照時數": round(st.mean(annual("日照時數")), 1) if annual("日照時數") else None}
    dts = j["data"][0]["dts"]
    return {"station": station_id, "period": f"{start_year}-{end_year}",
            "data_range": f"{dts[0]['DataYearMonth'][:7]} ~ {dts[-1]['DataYearMonth'][:7]}",
            "months": [f"{m}月" for m in range(1, 13)], "monthly": table, "annual": full,
            "years_per_month": n_years, "missing_months": missing,
            "口徑": "最高/最低溫度＝月平均最高/最低（非極端值）；降水量月值與全年皆取中位數；溫度、日照取平均"}


# ---------------------------------------------------------------- 01b 嘉義縣公務統計報表清冊
def cyhg_report_list(office="3007", year=""):
    from cyhg_stat08_清冊 import fetch_office, OFFICES
    if office not in OFFICES:
        raise ValueError(f"機關代碼不符，可用：{OFFICES}")
    rows = fetch_office(_session(), office, year)
    return {"office": OFFICES[office], "rows": rows}


# ---------------------------------------------------------------- 本機原始報表
READABLE = {".ods", ".xlsx", ".xls", ".csv", ".json"}


def list_local(sub=""):
    base = ROOT / "案件"
    out = []
    for p in sorted(base.rglob("*")):
        if p.is_file() and p.suffix.lower() in READABLE | {".pdf"} and sub in str(p.relative_to(base)):
            out.append({"path": str(p.relative_to(ROOT)).replace("\\", "/"), "size": p.stat().st_size})
    return out


def read_local(path, sheet=None, max_rows=200):
    import pandas as pd
    p = (ROOT / path).resolve()
    if ROOT not in p.parents or not p.is_file():
        raise ValueError("路徑必須是 repo 內既有檔案（先用 stat_list_local_files 查）")
    ext = p.suffix.lower()
    if ext == ".json":
        txt = p.read_text(encoding="utf-8")
        return {"path": path, "json_preview": txt[:20000], "truncated": len(txt) > 20000}
    if ext == ".csv":
        df = pd.read_csv(p, encoding="utf-8-sig", dtype=str)
        return {"path": path, "rows": [list(df.columns)] + df.fillna("").values.tolist()[:max_rows], "total_rows": len(df)}
    engine = {".ods": "odf", ".xls": "xlrd", ".xlsx": "openpyxl"}[ext]
    xl = pd.ExcelFile(p, engine=engine)
    if sheet is None:
        return {"path": path, "sheets": xl.sheet_names, "note": "指定 sheet 參數讀取分頁內容"}
    df = xl.parse(sheet, header=None, dtype=str).fillna("")
    rows = [[c for c in r] for r in df.values.tolist()]
    while rows and not any(rows[-1]):
        rows.pop()
    return {"path": path, "sheet": sheet, "rows": rows[:max_rows], "total_rows": len(rows)}
