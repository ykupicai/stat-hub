# -*- coding: utf-8 -*-
"""臺北市中山區壓力/平行測試跑者(單一程序、單線、固定間隔;平行=多開程序)。
用法: python cadastre_stress.py --sec 德惠段二小段 [--limit N] [--gap 1.5] [--tag 壓力]
輸出: 壓力測試_中山區\<tag>_<段>.csv(每50筆寫一次、可續跑)+ <tag>_<段>.log.json
連續5筆失敗即停止。"""
import os, sys, csv, time, json, argparse, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cadastre_fast as F
import moa

BASE = r"C:\Users\USER\OneDrive\文件\project\STATHUB\案件\臺北市_不動產交易分析\地號清單"
SRC = os.path.join(BASE, "不重複地號清單_中山區_官方去重.csv")
OUT = os.path.join(BASE, "壓力測試_中山區")
BACKOFF = [5, 15, 30]
FIELDS = ["段", "地號", "狀態", "登記面積", "圖面積", "差異%", "耗時秒", "重試次數", "農業部秒", "內政部秒", "14碼", "備註"]

ap = argparse.ArgumentParser()
ap.add_argument("--sec", required=True); ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--gap", type=float, default=1.5); ap.add_argument("--tag", default="壓力")
ap.add_argument("--flush", type=int, default=50)
ap.add_argument("--backfill", action="store_true", help="只重跑先前 OK 者以取得幾何(補 SHP 用)")
ap.add_argument("--out", default=""); ap.add_argument("--priors", action="store_true",
                help="略過先前試跑/壓力/平行 CSV 中狀態為 OK 的地號(非 OK 者重試一次)")
a = ap.parse_args()
if a.out: OUT = a.out
os.makedirs(OUT, exist_ok=True)
rows = list(csv.DictReader(open(SRC, encoding="utf-8-sig")))
nos = [r["地號_母子號"] for r in rows if r["官方段名"] == a.sec]
if a.limit: nos = nos[:a.limit]
prior_ok = set()
if a.priors or a.backfill:
    import glob
    pri = [BASE + r"\試跑_中山區\試跑結果.csv"] + glob.glob(BASE + r"\壓力測試_中山區\*.csv")
    for pf in pri:
        for r in csv.DictReader(open(pf, encoding="utf-8-sig")):
            if r["段"] == a.sec and r["狀態"] == "OK": prior_ok.add(r["地號"])
    nos = [n for n in nos if n in prior_ok] if a.backfill else [n for n in nos if n not in prior_ok]
path = os.path.join(OUT, "%s_%s.csv" % (a.tag, a.sec))
gpath = os.path.join(OUT, "%s_%s.geom.jsonl" % (a.tag, a.sec))
done = {}
if os.path.exists(path):   # 續跑:已有非失敗的略過
    for r in csv.DictReader(open(path, encoding="utf-8-sig")):
        if r["狀態"] != "失敗": done[r["地號"]] = r
out = list(done.values())
ctx = F.prepare("臺北市", "中山區", [a.sec])
print("版次", ctx["ver"], "prepare", ctx["prepare_s"], "待跑", len(nos) - len(done), "/", len(nos), flush=True)

def flush():
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(out)

def classify(e):
    s = repr(e).lower()
    if "timed out" in s or "timeout" in s: return "逾時"
    if "10054" in s or "reset" in s or "aborted" in s or "10053" in s: return "連線重設"
    if "429" in s or "503" in s or "502" in s or "too many" in s: return "節流疑似"
    return "其他:" + repr(e)[:80]

events = {"逾時": 0, "連線重設": 0, "節流疑似": 0, "其他": 0}
consec = 0; stopped = None; chunk = []; chunk_trend = []
t_start = time.time(); n_new = 0
for no in nos:
    if no in done: continue
    t0 = time.time(); retries = 0; memo = {}; o = None; err = ""
    while True:
        try:
            o = F.fast_one("臺北市", "中山區", a.sec, no, ctx, memo); err = ""; break
        except Exception as e:
            c = classify(e); err = c; events[c.split(":")[0] if c.startswith("其他") else c] += 1
            if retries >= len(BACKOFF): o = None; break
            time.sleep(BACKOFF[retries]); retries += 1
    dt = time.time() - t0
    if o is None:
        st = "失敗"; rec = {"段": a.sec, "地號": no, "狀態": st, "耗時秒": round(dt, 2), "重試次數": retries, "備註": err}
        consec += 1
    else:
        st = {"ERROR": "失敗"}.get(o["status"], o["status"])
        rec = {"段": a.sec, "地號": no, "狀態": st,
               "登記面積": o["registry"] if o["registry"] is not None else "",
               "圖面積": round(o["map_area"], 2) if o["map_area"] is not None else "",
               "差異%": o["dev"] if o["dev"] is not None else "",
               "耗時秒": round(dt, 2), "重試次數": retries, "農業部秒": o["moa_s"], "內政部秒": o["nlsc_s"],
               "14碼": o["code14"] or "", "備註": (o["path"] + ("|" if o["note"] else "") + o["note"]) if (o["path"] != "fast" or o["note"]) else ""}
        consec = consec + 1 if st == "失敗" else 0
    if o is not None and o.get("ring") and st == "OK":
        with open(gpath, "a", encoding="utf-8") as gf:
            gf.write(json.dumps({"段": a.sec, "地號": no, "14碼": o["code14"], "ring": o["ring"]}) + "\n")
    out.append(rec); chunk.append(dt); n_new += 1
    print(a.sec, no, st, rec.get("登記面積", ""), rec.get("圖面積", ""), rec.get("差異%", ""), rec["耗時秒"], retries, err, flush=True)
    if len(chunk) % a.flush == 0:
        chunk_trend.append(round(sum(chunk) / len(chunk), 2)); chunk = []; flush()
        print("== 已 %d 筆;最近一批平均 %.2fs;事件 %s" % (n_new, chunk_trend[-1], events), flush=True)
    if consec >= 5:
        stopped = "連續5筆失敗,中止於 " + no; print("!!", stopped, flush=True); break
    time.sleep(a.gap)
if chunk: chunk_trend.append(round(sum(chunk) / len(chunk), 2))
flush()
wall = time.time() - t_start
from collections import Counter
cnt = Counter(r["狀態"] for r in out)
summ = {"段": a.sec, "版次": ctx["ver"], "筆數": len(out), "狀態": dict(cnt), "本次新跑": n_new,
        "總重試": sum(int(r["重試次數"] or 0) for r in out), "事件": events, "每批平均秒(依序)": chunk_trend,
        "牆鐘秒": round(wall, 1), "每筆牆鐘秒": round(wall / max(n_new, 1), 2), "中止": stopped}
summ["略過先前OK"] = len(prior_ok)
json.dump(summ, open(os.path.join(OUT, "%s_%s.log.json" % (a.tag, a.sec)), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(summ, ensure_ascii=False), flush=True)
sys.exit(3 if stopped else 0)
