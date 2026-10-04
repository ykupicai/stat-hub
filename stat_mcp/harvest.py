"""自動抓取 → 解析 → 存入 資料庫/stat.sqlite。

  02  農業部統計處 農業統計業務查詢：harvest_agrstat(qcode, 起年, 迄年)
      頁面把統計量與各維度代碼以 AES-ECB 加密放在隱藏欄位（金鑰寫在頁面 JS：'2025000000000000'），
      解開後全選、重組 hidInquireGroup、補上統計量 checkbox（panCode_N=on）再按「查詢」。
      單次上限 15,000 格，超過自動依年度分段。
  03  漁業署 漁業統計年報：harvest_fa(年度, 分包=[7])  → 下載 zip，解出 ods/xls/xlsx 逐表入庫
  06b 臺南市統計年報：harvest_tainan(年度, 章=['04'])   → 下載各章「資料表」ODS 逐分頁入庫

原始檔存 資料庫/原始檔/<來源>/<年度>/（不進版控，datasets 表留網址與 sha256 可回溯）。

CLI：
  python stat_mcp/harvest.py agrstat AB01 104 114
  python stat_mcp/harvest.py fa 114 7
  python stat_mcp/harvest.py tainan 114 04
"""
import base64
import io
import json
import math
import re
import sys
import zipfile
from urllib.parse import urljoin
from pathlib import Path

import requests
import urllib3
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from lxml import html as LH

sys.path.insert(0, str(Path(__file__).resolve().parent))
import store  # noqa: E402

urllib3.disable_warnings()


def _session():
    s = requests.Session()
    s.verify = False
    s.headers["User-Agent"] = "Mozilla/5.0"
    return s


def _download(s, url, dest, referer=None):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = s.get(url, timeout=300, headers={"Referer": referer} if referer else None)
    r.raise_for_status()
    dest.write_bytes(r.content)
    return dest


# ====================================================================== 02 agrstat
AGR = "https://agrstat.moa.gov.tw/moasdweb/inquire/InquireAdvance.aspx?qcode={}"
AGR_KEY = b"2025000000000000"
P = "ctl00$ContentPlaceHolder1$ucInquireAdvance$"
CELL_LIMIT = 14000


def _dec(s):
    d = Cipher(algorithms.AES(AGR_KEY), modes.ECB()).decryptor()
    b = d.update(base64.b64decode(s)) + d.finalize()
    u = padding.PKCS7(128).unpadder()
    return json.loads((u.update(b) + u.finalize()).decode("utf-8"))


def _enc(o):
    p = padding.PKCS7(128).padder()
    b = p.update(json.dumps(o, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) + p.finalize()
    e = Cipher(algorithms.AES(AGR_KEY), modes.ECB()).encryptor()
    return base64.b64encode(e.update(b) + e.finalize()).decode()


def _agr_form(s, qcode):
    url = AGR.format(qcode)
    d = LH.fromstring(s.get(url, timeout=60).text)
    form = {}
    for i in d.xpath("//input"):
        n = i.get("name")
        if n and i.get("type") not in ("submit", "checkbox"):
            form[n] = i.get("value") or ""
    for sl in d.xpath("//select[@name]"):
        o = sl.xpath("./option[@selected]") or sl.xpath("./option")
        form[sl.get("name")] = o[0].get("value") if o else ""
    years = [o.get("value") for o in d.xpath(f'//select[@name="{P}ddlYearBegin"]/option')]
    title = (d.xpath('//*[contains(@class,"Title") or self::h2 or self::h3]/text()') or [qcode])
    return url, form, years, d


def agrstat_meta(qcode):
    """回傳該表的統計量、維度與各維度項目數、可選年度（不查資料）。"""
    s = _session()
    url, form, years, d = _agr_form(s, qcode)
    meas = _dec(form[P + "ucItemCode$hidCode"])["OriginCodeArray"]
    dims = {}
    for n, v in form.items():
        if n.endswith("ucItemDimensionCode$hidCode") and v:
            o = _dec(v)
            if o.get("GroupCode"):
                dims[o["GroupCode"]] = o["OriginCodeArray"]
    groups = _dec(form[P + "hidInquireGroup"])
    names = {g["GroupCode"]: g["GroupName"] for g in groups if g["Kind"] == 0}
    return {"qcode": qcode, "url": url, "可選年度": f"{int(years[0])}~{int(years[-1])}" if years else "",
            "統計量": [m["CodeName"] for m in meas],
            "維度": {names.get(k, k): [c["CodeName"] for c in v] for k, v in dims.items()}}


def harvest_agrstat(qcode, year_begin, year_end, title=None):
    s = _session()
    url, form, years, d = _agr_form(s, qcode)
    meas = _dec(form[P + "ucItemCode$hidCode"])["OriginCodeArray"]
    dims = {}
    for n, v in list(form.items()):
        if n.endswith("hidCode") and v:
            o = _dec(v)
            for c in (o.get("OriginCodeArray") or []) + (o.get("CodeArray") or []):
                c["Selected"] = True
            form[n] = _enc(o)
            if n.endswith("ucItemDimensionCode$hidCode") and o.get("GroupCode"):
                dims[o["GroupCode"]] = o["OriginCodeArray"]
    groups = _dec(form[P + "hidInquireGroup"])
    for g in groups:
        if g["Kind"] == -3:
            for c in g["CodeArray"] or []:
                c["Selected"] = True
        elif g["Kind"] == 0 and g["GroupCode"] in dims:
            g["CodeArray"] = [dict(c, Selected=True) for c in dims[g["GroupCode"]]]
            g["Position"], g["SerialNo"] = g["DefaultPosition"], g["DefaultSerialNo"]
    form[P + "hidInquireGroup"] = _enc(groups)
    form[P + "chkYearData"] = "on"
    for c in meas:
        form[f"ctl00_ContentPlaceHolder1_ucInquireAdvance_ucItemCode_panCode_{c['SerialNo']}"] = "on"
    form[P + "btnInquire"] = "查詢"
    yb, ye = int(year_begin), int(year_end)
    per_year = len(meas) * math.prod(len(v) for v in dims.values())
    step = max(1, CELL_LIMIT // max(per_year, 1))
    if per_year > CELL_LIMIT:
        raise ValueError(f"{qcode} 單一年度就有 {per_year} 格，超過平台 15,000 格上限；需改為分維度查詢（尚未支援）")
    chunks, y = [], yb
    while y <= ye:
        chunks.append((y, min(ye, y + step - 1)))
        y += step
    rows_all = []
    raw_dir = store.RAW_DIR / "agrstat"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for a, b in chunks:
        f = dict(form)
        f[P + "ddlYearBegin"], f[P + "ddlYearEnd"] = f"{a:03d}", f"{b:03d}"
        r = s.post(url, data=f, timeout=300)
        dd = LH.fromstring(r.text)
        t = dd.xpath('//table[contains(@id,"tabResult")]')
        if not t:
            raise RuntimeError(f"{qcode} {a}-{b} 查無結果表（平台可能改版）")
        grid = store.html_table_grid(t[0])
        (raw_dir / f"{qcode}_{a}-{b}.html").write_text(r.text, encoding="utf-8")
        if not rows_all:
            rows_all = grid
        else:  # 後續分段只取資料列（表頭相同）
            meta, _ = store.parse_grid(grid)
            body_start = next(i for i, row in enumerate(grid) if any(store._num(store._clean(c)) is not None for c in row[1:]))
            rows_all += grid[body_start:]
    tmp = raw_dir / f"{qcode}_{yb}-{ye}.json"
    tmp.write_text(json.dumps(rows_all, ensure_ascii=False), encoding="utf-8")
    con = store.connect()
    name = title or (d.xpath("string(//title)") or qcode).strip()
    res = store.save_dataset(con, f"agrstat:{qcode}", "02", f"{qcode} {name}", ye, url, tmp,
                             [(qcode, rows_all)], note=f"{yb}-{ye} 全選查詢；{len(chunks)} 段")
    return res


# ====================================================================== 03 漁業署年報
FA_LIST = "https://www.fa.gov.tw/list.php?theme=FS_AR"


def _zip_name(info):
    if info.flag_bits & 0x800:
        return info.filename
    try:
        return info.filename.encode("cp437").decode("cp950")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return info.filename


def harvest_fa(year, packages=(7,)):
    s = _session()
    d = LH.fromstring(s.get(FA_LIST, timeout=60).text)
    page = next((a.get("href") for a in d.xpath('//a[contains(@href,"view.php?theme=FS_AR")]')
                 if f"民國{int(year)}年" in a.text_content()), None)
    if not page:
        raise ValueError(f"漁業署網站找不到民國 {year} 年漁業統計年報")
    purl = "https://www.fa.gov.tw/" + page
    d = LH.fromstring(s.get(purl, timeout=60).text)
    files = [(a.text_content().strip(), "https://www.fa.gov.tw/" + a.get("href"))
             for a in d.xpath('//a[contains(@href,"redirect_file")]')]
    con = store.connect()
    results = []
    for pk in packages:
        hit = next(((t, u) for t, u in files if re.match(rf"^{int(pk)}\.?\D", t)), None)
        if not hit:
            results.append({"package": pk, "error": "找不到該分包"})
            continue
        t, u = hit
        zname = re.sub(r"\s*\(.*$", "", t).strip()
        zpath = _download(s, u, store.RAW_DIR / "漁業署" / str(year) / zname, referer=purl)
        if not zipfile.is_zipfile(zpath):
            results.append({"package": pk, "file": zname, "note": "非 zip（多為 PDF），僅存原始檔"})
            continue
        with zipfile.ZipFile(zpath) as z:
            members = [(i, _zip_name(i)) for i in z.infolist() if not i.is_dir()]
            names = {Path(n).stem: n for _, n in members}
            for info, n in members:
                ext = Path(n).suffix.lower()
                if ext not in (".ods", ".xls", ".xlsx"):
                    continue
                if ext != ".ods" and Path(n).stem + ".ods" in [Path(x).name for x in names.values()]:
                    continue  # 同名有 ods 就用 ods
                out = zpath.parent / Path(zname).stem / Path(n).name
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(z.read(info))
                try:
                    sheets = store.read_workbook(out)
                except Exception as e:  # noqa: BLE001
                    results.append({"file": Path(n).name, "error": repr(e)[:200]})
                    continue
                r = store.save_dataset(con, f"fa:{year}:{Path(n).stem}", "03", f"{year}年漁業統計年報 {Path(n).stem}",
                                       int(year), u, out, sheets, note=f"第{pk}包 {zname}")
                results.append({k: r[k] for k in ("dataset_id", "sheets", "facts")})
    return results


# ====================================================================== 06b 臺南市統計年報
TN_LIST = "https://account.tainan.gov.tw/News.aspx?n=44"


def harvest_tainan(year, chapters=("04",)):
    s = _session()
    d = LH.fromstring(s.get(TN_LIST, timeout=60).text)
    page = next((a.get("href") for a in d.xpath('//a[contains(@href,"News_Content")]')
                 if a.text_content().strip().startswith(f"{int(year)}年臺南市統計年報")), None)
    if not page:
        raise ValueError(f"臺南市主計處網站找不到 {year} 年統計年報")
    purl = "https://account.tainan.gov.tw/" + page.lstrip("/")
    d = LH.fromstring(s.get(purl, timeout=60).text)
    chap, odss = None, {}
    for a in d.xpath("//a[@href]"):
        t, h = a.text_content().strip(), urljoin(purl, a.get("href"))
        m = re.match(r"^(\d{2})\s*(\S+)", t)
        if m and re.search(r"relfile|Download|attachment", h):
            chap = (m.group(1), m.group(2))
        elif chap and t.startswith("資料表") and ".ods" in h.lower():
            odss[chap[0]] = (chap[1], h)
    con = store.connect()
    results = []
    for c in chapters:
        c = f"{int(c):02d}"
        if c not in odss:
            results.append({"chapter": c, "error": f"找不到第 {c} 章資料表 ODS", "可用": {k: v[0] for k, v in odss.items()}})
            continue
        name, u = odss[c]
        out = _download(s, u, store.RAW_DIR / "臺南市統計年報" / str(year) / f"{c}{name}.ods", referer=purl)
        sheets = store.read_workbook(out)
        r = store.save_dataset(con, f"tainan:{year}:{c}", "06b", f"{year}年臺南市統計年報 {c}{name}",
                               int(year), u, out, sheets)
        results.append({k: r[k] for k in ("dataset_id", "sheets", "facts")})
    return results


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    kind, *args = sys.argv[1:]
    if kind == "agrstat":
        print(json.dumps(harvest_agrstat(args[0], args[1], args[2]), ensure_ascii=False, indent=1)[:3000])
    elif kind == "agrmeta":
        print(json.dumps(agrstat_meta(args[0]), ensure_ascii=False, indent=1)[:3000])
    elif kind == "fa":
        print(json.dumps(harvest_fa(args[0], [int(x) for x in args[1:]] or [7]), ensure_ascii=False, indent=1))
    elif kind == "tainan":
        print(json.dumps(harvest_tainan(args[0], args[1:] or ["04"]), ensure_ascii=False, indent=1))
