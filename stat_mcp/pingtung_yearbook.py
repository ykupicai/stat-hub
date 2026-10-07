"""10c 屏東縣統計年報（統計刊物整份 zip，內含每表一個 PDF）。

來源（2026-10-07 實測）：
  屏東縣統計資訊服務網 › 統計刊物  https://pthg.dgbas.gov.tw/STATWeb/Page/BookCatalog_Main.aspx（最新年度）
  歷年版本  BookCatalog_Record.aspx?rbno=4&orgno=3001&bookname=屏東縣統計年報&uid=57（107～113）
  ⚠ 屏東首頁的「統計年報資料庫」連結 winstapx.dgbas.gov.tw（PX-Web）已下線，DNS 不存在；
    其可查詢的後繼版本就是 10a 平台「統計年報查詢」（statfile2 Mode=3 CateNo=01），表號相同。

zip 內為「<章>/<表號>.<副檔名>」：**舊版本多為 XLS/XLSX**（解析數值入 facts＋文字入 docs），
  **近年為文字型 PDF**（欄位擠在一起不適合自動拆數值 → 只抽文字入 docs，數值以 10a 平台同號表為準）。
CLI：python stat_mcp/pingtung_yearbook.py crawl | get 114 4-1
"""
import io
import json
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, unquote

import requests
import urllib3
from lxml import html as LH

sys.path.insert(0, str(Path(__file__).resolve().parent))
import store  # noqa: E402

urllib3.disable_warnings()
MAIN = "https://pthg.dgbas.gov.tw/STATWeb/Page/BookCatalog_Main.aspx"
RECORD = "https://pthg.dgbas.gov.tw/STATWeb/Page/BookCatalog_Record.aspx?rbno=4&orgno=3001&bookname=屏東縣統計年報&uid=57"
REL = store.ROOT / "資料庫" / "索引" / "年報結構.json"
PT10A = store.ROOT / "資料庫" / "10_屏東縣主計處_資料庫查詢平台" / "目錄_統計年報查詢.json"
RAW = store.RAW_DIR / "屏東縣統計年報"
DOCS_SQL = """CREATE TABLE IF NOT EXISTS docs(
  doc_id TEXT PRIMARY KEY, source TEXT, year INTEGER, chapter TEXT, table_no TEXT, title TEXT,
  pages INTEGER, local_path TEXT, url TEXT, fetched_at TEXT, text TEXT);"""


def _session():
    s = requests.Session()
    s.verify = False
    s.headers["User-Agent"] = "Mozilla/5.0"
    return s


def crawl():
    """各年度 zip 下載網址 → 年報結構.json 的 "pingtung" 鍵。"""
    s = _session()
    eds = {}
    for page in (MAIN, RECORD):
        d = LH.fromstring(s.get(page, timeout=60).text)
        for a in d.xpath("//a[@href]"):
            h = urljoin(page, a.get("href"))
            m = re.search(r"(\d+)年\+?\s*屏東縣統計年報\.zip", unquote(h))
            if m and ("Download" in h or "HitCount" in h):
                eds.setdefault(m.group(1), h)
    rel = json.loads(REL.read_text(encoding="utf-8")) if REL.exists() else {}
    rel["pingtung"] = {y: {"zip": u} for y, u in sorted(eds.items(), key=lambda x: int(x[0]))}
    REL.write_text(json.dumps(rel, ensure_ascii=False, indent=1), encoding="utf-8")
    return list(rel["pingtung"])


def editions():
    rel = json.loads(REL.read_text(encoding="utf-8")) if REL.exists() else {}
    return rel.get("pingtung") or {y: {"zip": None} for y in crawl()}


def titles_10a():
    """10a 平台「統計年報查詢」的表名與各統計項目網址（表號相同，用來補 PDF 表名、指向可程式查詢的數值）。"""
    out = {}
    if not PT10A.exists():
        return out
    for cat in json.loads(PT10A.read_text(encoding="utf-8")):
        for tb in cat.get("children", []):
            m = re.match(r"表\s*(\d+-\d+)\s*(.*)", tb["name"])
            if m:
                out[m.group(1)] = {"title": m.group(2).strip(), "items": [{"name": x["name"], "url": x["url"]}
                                                                          for x in tb.get("children", []) if x.get("url")]}
    return out


def _zip_name(info):
    if info.flag_bits & 0x800:
        return info.filename
    try:
        return info.filename.encode("cp437").decode("cp950")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return info.filename


def ensure(year):
    """下載（若尚未）並把整份年報各表文字入 docs 表。回傳入庫張數。"""
    import fitz
    year = str(int(year))
    con = store.connect()
    con.execute(DOCS_SQL)
    n = con.execute("SELECT count(*) FROM docs WHERE source='10c' AND year=?", (int(year),)).fetchone()[0]
    if n:
        return {"year": int(year), "tables": n, "本次下載": False}
    eds = editions()
    if year not in eds:
        eds = {y: {"zip": u} for y, u in ((k, v["zip"]) for k, v in eds.items())}
        if year not in eds:
            crawl()
            eds = editions()
    if year not in eds:
        raise ValueError(f"找不到 {year} 年屏東縣統計年報；可用年度：{list(eds)}")
    url = eds[year]["zip"]
    zpath = RAW / year / f"{year}年屏東縣統計年報.zip"
    zpath.parent.mkdir(parents=True, exist_ok=True)
    if not zpath.exists():
        r = _session().get(url, timeout=600, headers={"Referer": MAIN})
        r.raise_for_status()
        zpath.write_bytes(r.content)
    t10a = titles_10a()
    rows = []
    with zipfile.ZipFile(zpath) as z:
        for info in z.infolist():
            name = _zip_name(info)
            ext = Path(name).suffix.lower()
            if ext not in (".pdf", ".xls", ".xlsx", ".ods"):
                continue
            parts = Path(name).parts
            chapter = parts[-2] if len(parts) >= 2 else ""
            tno = Path(name).stem.replace(" ", "")
            out = zpath.parent / "files" / chapter / Path(name).name
            out.parent.mkdir(parents=True, exist_ok=True)
            data = z.read(info)
            out.write_bytes(data)
            title = (t10a.get(tno) or {}).get("title") or ""
            if ext == ".pdf":  # 近年版本：文字型 PDF，欄位擠在一起 → 只存文字
                doc = fitz.open(stream=data, filetype="pdf")
                text, pages = "\n".join(p.get_text() for p in doc), len(doc)
            else:  # 舊版本：試算表 → 解析數值入 facts，文字版也存一份供搜尋
                sheets = store.read_workbook(out)
                text = "\n".join("\t".join(c for c in r if c) for _, g in sheets for r in g if any(r))
                pages = len(sheets)
                store.save_dataset(con, f"ptyb:{year}:{tno}", "10c", f"{year}年屏東縣統計年報 表{tno} {title}",
                                   int(year), url, out, sheets, note=chapter)
            if not title:
                m = re.search(r"表\s*" + re.escape(tno) + r"\s*([^\n\t]+)", text)
                title = m.group(1).strip() if m else ""
            rows.append((f"ptyb:{year}:{tno}", "10c", int(year), chapter, tno, title, pages,
                         str(out.relative_to(store.ROOT)).replace("\\", "/"), url,
                         datetime.now().isoformat(timespec="seconds"), text))
    con.executemany("INSERT OR REPLACE INTO docs VALUES(?,?,?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    con.close()
    return {"year": int(year), "tables": len(rows), "本次下載": True}


def get(year, table):
    ensure(year)
    con = store.connect()
    con.execute(DOCS_SQL)
    r = con.execute("SELECT doc_id, chapter, table_no, title, pages, local_path, url, text FROM docs WHERE doc_id=?",
                    (f"ptyb:{int(year)}:{table.replace('表', '').replace(' ', '')}",)).fetchone()
    con.close()
    if not r:
        raise ValueError(f"{year} 年年報沒有表 {table}")
    k = ["doc_id", "章", "表號", "表名", "頁數或分頁數", "原始檔", "來源zip", "text"]
    return dict(zip(k, r))


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    if sys.argv[1] == "crawl":
        print(crawl())
    elif sys.argv[1] == "get":
        g = get(sys.argv[2], sys.argv[3])
        print({k: v for k, v in g.items() if k != "text"})
        print(g["text"][:800])
