# -*- coding: utf-8 -*-
"""cadastre-check 小批量試跑:臺北市中山區 德惠段一小段/北安段四小段(31 筆)。
重試退避 5/15/30 秒、每筆間隔 1.5 秒;結果 CSV + 合併 SHP + 計時 JSON。"""
import os, sys, csv, time, json
SK = os.path.expanduser("~/.claude/skills/cadastre-check/scripts")
sys.path.insert(0, SK)
import config; config.use_utf8_console()
import cadlib as C, check, moa, api

BASE = r"C:\Users\USER\OneDrive\文件\project\STATHUB\案件\臺北市_不動產交易分析\地號清單"
SRC = os.path.join(BASE, "不重複地號清單_中山區_官方去重.csv")
OUT = os.path.join(BASE, "試跑_中山區")
SECS = ["德惠段一小段", "北安段四小段"]
BACKOFF = [5, 15, 30]; GAP = 1.5

rows = list(csv.DictReader(open(SRC, encoding="utf-8-sig")))
ver = moa.newest_version()
ctx = {"ver": ver, "cache": config.cache_dir()}
print("版次", ver)
out, results, secstat = [], [], {}
for sec in SECS:
    nos = [r["地號_母子號"] for r in rows if r["官方段名"] == sec]
    t_sec = time.time(); sec_retry = 0
    for no in nos:
        t0 = time.time(); retries = 0; res = None
        while True:
            try:
                res = check.check_one("臺北市", "中山區", sec, no, ctx, quiet=True)
            except Exception as e:
                res = {"verdict": "ERROR", "結論": "例外", "說明": [repr(e)]}
            if res.get("verdict") != "ERROR" or retries >= len(BACKOFF):
                break
            time.sleep(BACKOFF[retries]); retries += 1
        dt = time.time() - t0; sec_retry += retries
        rec = api._record(res) if res.get("查詢") else {"registry": None, "map_area": None, "deviation_pct": None, "message": res.get("結論"), "notes": res.get("說明", []), "status": "ERROR"}
        st = res.get("verdict") or "ERROR"
        st_out = {"ERROR": "失敗"}.get(st, st)
        reg = (rec.get("registry") or {}).get("area")
        out.append({"段": sec, "地號": no, "狀態": st_out, "登記面積": reg if reg is not None else "",
                    "圖面積": round(rec["map_area"], 2) if rec.get("map_area") is not None else "",
                    "差異%": rec["deviation_pct"] if rec.get("deviation_pct") is not None else "",
                    "耗時秒": round(dt, 2), "重試次數": retries,
                    "備註": ("|".join(rec.get("notes") or []) + "|" + "|".join(rec.get("warnings") or []))[:200] if st != "OK" or rec.get("warnings") else ""})
        results.append(res)
        print(sec, no, st_out, reg, out[-1]["圖面積"], out[-1]["差異%"], out[-1]["耗時秒"], retries, flush=True)
        time.sleep(GAP)
    secstat[sec] = {"筆數": len(nos), "總耗時秒": round(time.time() - t_sec, 1),
                    "每筆平均秒": round((time.time() - t_sec) / len(nos), 2), "重試次數": sec_retry}
with open(os.path.join(OUT, "試跑結果.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
base, qa = check.build_shapefile(results, OUT, "trial", quiet=True)
json.dump({"版次": ver, "段統計": secstat, "shp": base}, open(os.path.join(OUT, "計時.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(secstat, base)
