"""中山區 6,650 個地號的權屬欄位（只打內政部 NLSC S09_Ralid/getLandInfo，不打農業部）。

API 回傳的 land.userList 只有「公有土地」會有所有權人（名稱、類別如 直轄市有／國有、管理機關、持分分子分母）；私有地為 null。
輸入：地號清單/中山區_全量/中山區_全部結果.csv 的 14碼（事務所2＋段碼4＋地號8；city＝事務所碼第 1 碼）
輸出：地號清單/中山區_權屬API/ralid_raw.jsonl（每行一個地號，含 ralid 欄位與 userList；可續跑）
節流：3 個執行緒、每個間隔 1 秒；失敗退避 5/15/30 秒；連續 5 筆失敗即停。
執行：python scripts/fetch_中山區_權屬_NLSC.py
"""
import csv
import io
import json
import sys
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent
CASE = ROOT / "案件" / "臺北市_不動產交易分析" / "地號清單"
OUT = CASE / "中山區_權屬API"
URL = "https://api.nlsc.gov.tw/S09_Ralid/getLandInfo"
lock = threading.Lock()
state = {"fail": 0, "stop": False, "done": 0}


def call(code14):
    d = urllib.parse.urlencode({"city": code14[0], "sect": code14[2:6], "landno": code14[6:]}).encode()
    req = urllib.request.Request(URL, data=d, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://maps.nlsc.gov.tw/"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8") or "{}")


def work(code, fh, total):
    if state["stop"]:
        return
    for k, wait in enumerate((0, 5, 15, 30)):
        time.sleep(wait)
        try:
            j = call(code)
            land = j.get("land") or {}
            r = j.get("ralid") or {}
            rec = {"14碼": code, "有資料": bool(r.get("AA49")), "ralid": {k2: r.get(k2) for k2 in ("AA05", "AA06", "AA10", "AA16", "AA17", "ABMAX", "ACMAX", "AA27")},
                   "userList": land.get("userList")}
            with lock:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n"); fh.flush()
                state["fail"] = 0; state["done"] += 1
                if state["done"] % 200 == 0:
                    print(f"{state['done']}/{total}", flush=True)
            time.sleep(1.0)
            return
        except Exception as e:  # noqa: BLE001
            err = str(e)
    with lock:
        state["fail"] += 1
        print("失敗", code, err, flush=True)
        if state["fail"] >= 5:
            state["stop"] = True
            print("連續 5 筆失敗，停止", flush=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    # 14碼＝官方段碼 6 碼（地段對照.csv）＋地號 8 碼（母 4＋子 4）；結果 CSV 的 14碼 欄是 API 實際回傳者，MISMATCH 與部分列為空，故不採用
    seg = {r["官方段名"]: r["官方段碼"] for r in csv.DictReader(open(CASE / "地段對照.csv", encoding="utf-8-sig")) if r["官方段碼"]}
    lst = list(csv.DictReader(open(CASE / "不重複地號清單_中山區_官方去重.csv", encoding="utf-8-sig")))
    codes = []
    for r in lst:
        m, _, c = r["地號_母子號"].partition("-")
        codes.append(seg[r["官方段名"]] + f"{int(m):04d}{int(c or 0):04d}")
    assert len(lst) == 6650 and len(set(codes)) == 6650 and all(len(c) == 14 for c in codes)
    ok = {r["14碼"] for r in csv.DictReader(open(CASE / "中山區_全量" / "中山區_全部結果.csv", encoding="utf-8-sig")) if r["14碼"] and r["狀態"] == "OK"}
    print("與結果 CSV 的 14碼（OK）交集", len(ok & set(codes)), "/", len(ok), flush=True)
    f = OUT / "ralid_raw.jsonl"
    done = set()
    if f.exists():
        done = {json.loads(l)["14碼"] for l in open(f, encoding="utf-8") if l.strip()}
    todo = [c for c in codes if c not in done]
    print(f"總 {len(codes)}，已完成 {len(done)}，待查 {len(todo)}", flush=True)
    t0 = time.time()
    with open(f, "a", encoding="utf-8") as fh, ThreadPoolExecutor(max_workers=3) as ex:
        list(ex.map(lambda c: work(c, fh, len(todo)), todo))
    print(f"結束：本次完成 {state['done']}，耗時 {time.time() - t0:.0f} 秒", flush=True)


if __name__ == "__main__":
    main()
