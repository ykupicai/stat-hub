"""12 內政部不動產交易實價查詢服務網 開放資料（plvr.land.moi.gov.tw/DownloadOpenData）。

2026-10-08 實測：
  季別清單：DownloadSeason_ajax_list（101S1～最新，約 59 季）。
  下載：/DownloadSeason?season=<115S2>&type=zip&fileName=lvr_landcsv.zip → 全國一包（約 15 MB），CSV 為 UTF-8，
        第 1 列中文欄名、第 2 列英文欄名。manifest.csv 列出檔名↔縣市↔類別：
        <縣市碼>_lvr_land_<a 不動產買賣｜b 預售屋買賣｜c 不動產租賃>[_land|_build|_park].csv
  季別＝**登記（申報）期間**，不是交易日期：107 年起 S1＝前一年 11/11～2/10、S2＝2/11～5/10、S3＝5/11～8/10、S4＝8/11～11/10
  （106 年以前約為 11/1～1/31 起算）。交易日期通常早於登記日期 1～2 個月。
資料是逐筆交易紀錄（不是統計表），存在獨立的 資料庫/lvr.sqlite（體積大，不進 stat.sqlite 快照、不進版控），用到哪季抓哪季。
CLI：python stat_mcp/lvr.py seasons ｜ python stat_mcp/lvr.py harvest 115S2 ｜ python stat_mcp/lvr.py query 臺南市 --district 新營區 --target 土地
"""
import csv
import hashlib
import io
import json
import re
import sqlite3
import statistics
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path

import requests
import urllib3

urllib3.disable_warnings()
B = "https://plvr.land.moi.gov.tw/"
ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "資料庫" / "lvr.sqlite"
RAW = ROOT / "資料庫" / "原始檔" / "12-實價登錄"
KINDS = {"a": "不動產買賣", "b": "預售屋買賣", "c": "不動產租賃"}
KIND_BY_NAME = {v: k for k, v in KINDS.items()} | {"買賣": "a", "預售屋": "b", "預售": "b", "租賃": "c"}
PING = 3.305785  # 1 坪＝3.305785 平方公尺
# 備註出現這些字眼者多為特殊交易（親友、債權債務、含增建等），統計單價時預設排除
SPECIAL = ["親友", "員工", "特殊關係", "共有人", "關係人", "債權債務", "法拍", "急買急賣", "畸零地", "含增建", "瑕疵", "受債權", "政府機關標讓售", "地上權"]

COLS = ["season", "county", "kind", "編號", "鄉鎮市區", "交易標的", "位置", "土地面積", "都市土地使用分區", "非都市土地使用分區",
        "非都市土地使用編定", "交易日", "筆棟數", "建物型態", "主要用途", "建物面積", "總價", "單價", "備註", "extra"]


def _session():
    s = requests.Session()
    s.verify = False
    s.headers["User-Agent"] = "Mozilla/5.0"
    return s


def _db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB)
    c.executescript("""
    create table if not exists lvr_seasons(season text primary key, fetched_at text, sha256 text, bytes int, rows int, period text);
    create table if not exists lvr_tx(season text, county text, kind text, 編號 text, 鄉鎮市區 text, 交易標的 text, 位置 text,
        土地面積 real, 都市土地使用分區 text, 非都市土地使用分區 text, 非都市土地使用編定 text, 交易日 int, 筆棟數 text,
        建物型態 text, 主要用途 text, 建物面積 real, 總價 real, 單價 real, 備註 text, extra text, primary key(kind, 編號));
    create index if not exists ix_tx_q on lvr_tx(county, kind, 鄉鎮市區, 交易日);
    create table if not exists lvr_land(kind text, 編號 text, 土地位置 text, 面積 real, 使用分區或編定 text, 持分分母 text,
        持分分子 text, 移轉情形 text, 地號 text);
    create index if not exists ix_land on lvr_land(kind, 編號);
    create table if not exists lvr_build(kind text, 編號 text, 屋齡 text, 面積 real, 主要用途 text, 主要建材 text,
        建築完成日期 text, 總層數 text, 建物分層 text, 移轉情形 text);
    create index if not exists ix_build on lvr_build(kind, 編號);
    """)
    have = {r[1] for r in c.execute("pragma table_info(lvr_seasons)")}
    for col in ("scope text", "has_build int"):  # scope：ALL 或逗號分隔的縣市；has_build：是否已入建物明細
        if col.split()[0] not in have:
            c.execute(f"alter table lvr_seasons add column {col}")
    return c


def seasons():
    """平台目前提供的季別（舊→新）。"""
    s = _session()
    s.get(B + "DownloadOpenData", timeout=60)
    h = s.get(B + "DownloadSeason_ajax_list", timeout=60).text
    return sorted(set(re.findall(r"\b(\d{3}S[1-4])\b", h)))


def _num(v):
    try:
        return float(str(v).replace(",", "")) if str(v).strip() not in ("", "nan") else None
    except ValueError:
        return None


def _int(v):
    v = re.sub(r"\D", "", str(v or ""))
    return int(v) if v else None


def harvest(season, force=False, counties=None, need_build=False):
    """下載一季全國 CSV 包並入 lvr.sqlite（同編號覆寫）。回傳 {season, rows, period}。
    counties：只入這些縣市（None＝全國）；已入庫且範圍涵蓋就略過。need_build：要求已有建物明細（lvr_build）。
    原始 zip 已在 資料庫/原始檔/12-實價登錄/ 者直接讀本機，不重抓。"""
    c = _db()
    row = c.execute("select rows, period, scope, has_build from lvr_seasons where season=?", (season,)).fetchone()
    old_scope = (row[2] or "ALL") if row else ""
    if not force and row:
        covered = old_scope == "ALL" or (counties and set(counties) <= set(old_scope.split(",")))
        if covered and (not need_build or row[3]):
            return {"season": season, "rows": row[0], "period": row[1], "cached": True}
    local = RAW / f"lvr_landcsv_{season}.zip"
    if local.exists() and local.stat().st_size > 1000:
        content = local.read_bytes()
    else:
        s = _session()
        s.get(B + "DownloadOpenData", timeout=60)
        for k in range(4):
            try:
                r = s.get(B + f"DownloadSeason?season={season}&type=zip&fileName=lvr_landcsv.zip", timeout=600)
                if r.content[:2] == b"PK":
                    break
            except requests.RequestException:
                pass
            time.sleep(10 * (k + 1))
        else:
            raise RuntimeError(f"{season} 下載失敗")
        content = r.content
        RAW.mkdir(parents=True, exist_ok=True)
        local.write_bytes(content)
    # 範圍只升不降；舊紀錄的 ALL 沒有建物明細，改以本次縣市為準（保守：其他縣市日後再查時由本機 zip 重入，不重抓）
    scope = "ALL" if counties is None else ",".join(sorted(set(counties) | (set(old_scope.split(",")) if row and old_scope != "ALL" else set())))
    z = zipfile.ZipFile(io.BytesIO(content))
    names = set(z.namelist())
    county = {}
    if "manifest.csv" in names:
        for row in csv.reader(io.StringIO(z.read("manifest.csv").decode("utf-8-sig"))):
            m = re.match(r"([a-z])_lvr_land_[abc]\.csv$", row[0] or "")
            if m and len(row) > 2:
                county[m.group(1)] = re.sub(r"(不動產買賣|預售屋買賣|不動產租賃)$", "", row[2])
    period = ""
    if "build_time.xml" in names:
        m = re.search(r"<lvr_time>(.*?)</lvr_time>", z.read("build_time.xml").decode("utf-8", "replace"), re.S)
        period = m.group(1).strip() if m else ""
    n = 0
    for name in sorted(names):
        m = re.match(r"([a-z])_lvr_land_([abc])(_land|_build)?\.csv$", name)
        if not m:
            continue
        cc, kind, sub = m.groups()
        land = sub == "_land"
        if counties and county.get(cc, cc) not in counties:
            continue
        rows = list(csv.reader(io.StringIO(z.read(name).decode("utf-8-sig", "replace"))))
        if len(rows) < 3:
            continue
        head, body = rows[0], rows[2:]  # 第 2 列為英文欄名
        if sub == "_build":
            c.executemany("delete from lvr_build where kind=? and 編號=?", {(kind, x[0]) for x in body if x})
            c.executemany("insert into lvr_build values(?,?,?,?,?,?,?,?,?,?)",
                          [(kind, x[0], x[1], _num(x[2]), x[3], x[4], x[5], x[6], x[7] if len(x) > 7 else "",
                            x[8] if len(x) > 8 else "") for x in body if len(x) >= 7])
            continue
        if land:
            c.executemany("delete from lvr_land where kind=? and 編號=?", {(kind, x[0]) for x in body if x})
            c.executemany("insert into lvr_land values(?,?,?,?,?,?,?,?,?)",
                          [(kind, x[0], x[1], _num(x[2]), x[3], x[4], x[5], x[6], x[7] if len(x) > 7 else "")
                           for x in body if len(x) >= 7])
            continue
        H = {h: i for i, h in enumerate(head)}

        def g(row, *keys):
            for k in keys:
                if k in H and H[k] < len(row):
                    return row[H[k]]
            return ""
        recs = []
        for x in body:
            if not x or not g(x, "編號"):
                continue
            used = {"鄉鎮市區", "交易標的", "土地位置建物門牌", "土地移轉總面積平方公尺", "土地面積平方公尺", "都市土地使用分區",
                    "非都市土地使用分區", "非都市土地使用編定", "交易年月日", "租賃年月日", "交易筆棟數", "租賃筆棟數", "建物型態",
                    "主要用途", "建物移轉總面積平方公尺", "建物總面積平方公尺", "總價元", "總額元", "單價元平方公尺", "備註", "編號"}
            extra = {h: x[i] for h, i in H.items() if h not in used and i < len(x) and x[i] not in ("", "0", "0.0")}
            recs.append((season, county.get(cc, cc), kind, g(x, "編號"), g(x, "鄉鎮市區"), g(x, "交易標的"), g(x, "土地位置建物門牌"),
                         _num(g(x, "土地移轉總面積平方公尺", "土地面積平方公尺")), g(x, "都市土地使用分區"), g(x, "非都市土地使用分區"),
                         g(x, "非都市土地使用編定"), _int(g(x, "交易年月日", "租賃年月日")), g(x, "交易筆棟數", "租賃筆棟數"),
                         g(x, "建物型態"), g(x, "主要用途"), _num(g(x, "建物移轉總面積平方公尺", "建物總面積平方公尺")),
                         _num(g(x, "總價元", "總額元")), _num(g(x, "單價元平方公尺")), g(x, "備註"),
                         json.dumps(extra, ensure_ascii=False) if extra else ""))
        c.executemany(f"insert or replace into lvr_tx values({','.join('?' * len(COLS))})", recs)
        n += len(recs)
    c.execute("insert or replace into lvr_seasons values(?,?,?,?,?,?,?,?)",
              (season, datetime.now().isoformat(timespec="seconds"), hashlib.sha256(content).hexdigest(), len(content),
               n, period, scope, 1))
    c.commit()
    return {"season": season, "rows": n, "period": period, "cached": False}


def seasons_for(date_from, date_to):
    """交易日期區間（民國 yyymm 或 yyy）→ 需要的季別：登記期間與 [起, 迄＋6 個月] 重疊者。"""
    def ym(v, end=False):
        v = str(v)
        return (int(v[:3]), int(v[3:5])) if len(v) >= 5 else (int(v), 12 if end else 1)
    y0, m0 = ym(date_from)
    y1, m1 = ym(date_to, True)
    lo, hi = y0 * 12 + m0, y1 * 12 + m1 + 6
    out = []
    for ss in seasons():
        y, q = int(ss[:3]), int(ss[-1])
        start = (y - 1) * 12 + 11 if q == 1 else y * 12 + 3 * q - 4  # S1 前一年 11 月；S2 2 月；S3 5 月；S4 8 月
        if start <= hi and start + 3 >= lo:
            out.append(ss)
    return out


def query(county, district=None, kind="買賣", target=None, zoning=None, date_from=None, date_to=None,
          season_list=None, exclude_special=True, limit=50, building_type=None, main_use=None,
          rent_type=None, rooms=None, furnished=None, elevator=None, rent_service=None):
    """逐筆查詢＋單價統計。日期為交易日期（民國 yyymm 或 yyy）；未給取最近 4 季。缺的季會先下載。
    building_type 建物型態片段（公寓、華廈、住宅大樓、透天厝、套房、店面…）；main_use 主要用途片段；
    rooms 房數：整數或 "3+"／"1-2"；以下僅租賃：rent_type 出租型態片段（整棟(戶)、獨立套房、分租套房、分層分租…）、
    furnished／elevator 有無附傢俱／電梯（True/False）、rent_service 租賃住宅服務片段（社會住宅、代管、包租、一般）。"""
    k = KIND_BY_NAME.get(kind, kind)
    if season_list:
        ss = list(season_list)
    elif date_from or date_to:
        ss = seasons_for(date_from or date_to, date_to or date_from)
    else:
        ss = seasons()[-4:]
    loaded = [harvest(x, counties=[county.replace("台", "臺")]) for x in ss]
    c = _db()
    sql = "select * from lvr_tx where county=? and kind=?"
    args = [county.replace("台", "臺"), k]
    if district:
        sql += " and 鄉鎮市區 like ?"
        args.append(f"%{district}%")
    if target:  # 「土地」「建物」「車位」精確比對（否則「土地」會吃到「房地(土地+建物)」）；「房地」等片段用模糊比對
        exact = target in ("土地", "建物", "車位", "房地(土地+建物)", "房地(土地+建物)+車位", "租賃房屋", "租賃土地")
        sql += " and 交易標的 = ?" if exact else " and 交易標的 like ?"
        args.append(target if exact else f"%{target}%")
    if zoning:
        sql += " and (都市土地使用分區 like ? or 非都市土地使用分區 like ? or 非都市土地使用編定 like ?)"
        args += [f"%{zoning}%"] * 3
    if building_type:
        sql += " and 建物型態 like ?"
        args.append(f"%{building_type}%")
    if main_use:
        sql += " and 主要用途 like ?"
        args.append(f"%{main_use}%")
    if date_from:
        v = str(date_from)
        sql += " and 交易日 >= ?"
        args.append(int(v.ljust(5, "0")[:5]) * 100 + 1 if len(v) >= 5 else int(v) * 10000 + 101)
    if date_to:
        v = str(date_to)
        sql += " and 交易日 <= ?"
        args.append(int(v[:5]) * 100 + 31 if len(v) >= 5 else int(v) * 10000 + 1231)
    sql += f" and season in ({','.join('?' * len(ss))}) order by 交易日 desc"
    args += ss
    rows = [dict(zip(COLS, r)) for r in c.execute(sql, args)]
    for r in rows:
        r["extra"] = json.loads(r["extra"]) if r["extra"] else {}

    def yn(v, want):  # 有／無 欄位
        return want is None or (v == "有") == bool(want)

    def room_ok(v):
        if rooms in (None, ""):
            return True
        try:
            n = int(v or 0)
        except ValueError:
            return False
        s = str(rooms).strip()
        if s.endswith("+"):
            return n >= int(s[:-1])
        if "-" in s:
            lo, hi = s.split("-", 1)
            return int(lo) <= n <= int(hi)
        return n == int(s)
    rows = [r for r in rows
            if (not rent_type or rent_type in r["extra"].get("出租型態", ""))
            and (not rent_service or rent_service in r["extra"].get("租賃住宅服務", ""))
            and yn(r["extra"].get("有無附傢俱"), furnished) and yn(r["extra"].get("有無電梯"), elevator)
            and room_ok(r["extra"].get("建物現況格局-房"))]
    special = [r for r in rows if any(w in (r["備註"] or "") for w in SPECIAL)]
    sp_ids = {r["編號"] for r in special}
    use = [r for r in rows if r["編號"] not in sp_ids] if exclude_special else rows
    def unit(r):  # 單價欄空白的純土地交易以 總價÷土地移轉面積 補算
        if r["單價"]:
            return r["單價"]
        if (r["交易標的"] or "") == "土地" and r["總價"] and r["土地面積"]:
            return r["總價"] / r["土地面積"]
        return None
    prices = sorted(v for v in map(unit, use) if v)

    def summ(v):
        if not v:
            return None
        q = statistics.quantiles(v, n=4) if len(v) >= 4 else [v[0], statistics.median(v), v[-1]]
        return {"筆數": len(v), "中位數_元每平方公尺": round(statistics.median(v)), "中位數_元每坪": round(statistics.median(v) * PING),
                "平均_元每平方公尺": round(statistics.mean(v)), "P25": round(q[0]), "P75": round(q[-1])}
    breakdown = None
    if k == "c":  # 租賃：依出租型態分組，附月租金中位數（單價混合套房與整戶意義不大）
        groups = {}
        for r in use:
            groups.setdefault(r["extra"].get("出租型態") or "（未填）", []).append(r)
        breakdown = {g: {"筆數": len(v),
                         "月租金中位數_元": round(statistics.median([x["總價"] for x in v if x["總價"]] or [0])),
                         "建物面積中位數_坪": round(statistics.median([x["建物面積"] for x in v if x["建物面積"]] or [0]) / PING, 1),
                         "單價中位數_元每坪": round(statistics.median([x["單價"] for x in v if x["單價"]] or [0]) * PING)}
                     for g, v in sorted(groups.items(), key=lambda kv: -len(kv[1]))}
    ids = [r["編號"] for r in rows[:limit]]
    lands = {}
    if ids:
        for x in c.execute(f"select 編號, 土地位置, 地號, 面積, 使用分區或編定, 持分分母, 持分分子, 移轉情形 from lvr_land "
                           f"where kind=? and 編號 in ({','.join('?' * len(ids))})", [k] + ids):
            lands.setdefault(x[0], []).append(dict(zip(["土地位置", "地號", "面積", "使用分區或編定", "持分分母", "持分分子", "移轉情形"], x[1:])))
    for r in rows[:limit]:
        r["土地明細"] = lands.get(r["編號"], [])
    return {"條件": {"縣市": county, "鄉鎮市區": district, "類別": KINDS[k], "交易標的": target, "使用分區關鍵字": zoning,
                     "交易日期": f"{date_from or ''}~{date_to or ''}", "季別": ss, "排除特殊交易": exclude_special,
                     "建物型態": building_type, "主要用途": main_use, "房數": rooms, "出租型態": rent_type,
                     "有無附傢俱": furnished, "有無電梯": elevator, "租賃住宅服務": rent_service},
            "季別登記期間": {x["season"]: x["period"] for x in loaded},
            "總筆數": len(rows), "特殊交易筆數": len(special),
            "單價統計": summ(prices),
            **({"租賃_依出租型態": breakdown} if breakdown is not None else {}),
            "注意": "單價為平台「單價元平方公尺」（房地交易含建物，車位價格未拆分）；季別依登記日期分包，交易日期篩選後才是區間內交易",
            "rows": rows[:limit]}


if __name__ == "__main__":
    import argparse
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--district")
    ap.add_argument("--target")
    ap.add_argument("--zoning")
    ap.add_argument("--kind", default="買賣")
    ap.add_argument("--from", dest="f")
    ap.add_argument("--to", dest="t")
    a = ap.parse_args()
    if a.cmd == "seasons":
        print(seasons())
    elif a.cmd == "harvest":
        print(harvest(a.arg, force=True))
    else:
        r = query(a.arg, a.district, a.kind, a.target, a.zoning, a.f, a.t, limit=5)
        print(json.dumps({k: v for k, v in r.items() if k != "rows"}, ensure_ascii=False, indent=1))
        for row in r["rows"]:
            print(row["交易日"], row["鄉鎮市區"], row["交易標的"], row["位置"], row["總價"], row["單價"], row["土地明細"][:2])
