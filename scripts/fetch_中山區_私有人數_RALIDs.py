"""中山區 6,650 個地號的土地私有人數、私有面積、建物私有人數（臺北市都更門檻估算服務背後的 RALIDs API）。

API：https://maps.land.gov.taipei/urlandwa/api/RALIDs?landno=<段碼4＋地號8>&TName=<行政區代碼>（中山區＝10）
  回傳 LCount（土地筆數）、LArea（登記面積）、LPArea（私有面積）、Lmans（土地私有人數）、BCount／BArea／BPArea／Bmans（建物筆數、面積、私有面積、私有人數）、note（公同共有、見其他登記）
  已以 3 個地號對照網站畫面（土地私有人數 4 人、0.20 ㎡）驗證。單筆查詢；只回傳「私有」人數，不含所有權人姓名。
輸入：地號清單/不重複地號清單_中山區_官方去重.csv ＋ 地地段對照.csv（段碼）
輸出：地號清單/中山區_私有人數API/ralids_raw.jsonl（可續跑）
節流：3 個執行緒、每個間隔 1 秒；失敗退避 5/15/30 秒；連續 10 筆失敗即停止。
執行：python scripts/fetch_中山區_私有人數_RALIDs.py
"""
import csv
import io
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent
CASE = ROOT / "案件" / "臺北市_不動產交易分析" / "地號清單"
OUT = CASE / "中山區_私有人數API"
URL = "https://maps.land.gov.taipei/urlandwa/api/RALIDs"
lock = threading.Lock()
state = {"fail": 0, "stop": False, "done": 0}
local = threading.local()


def sess():
    if not hasattr(local, "s"):
        local.s = requests.Session()
        local.s.headers.update({"User-Agent": "Mozilla/5.0", "Referer": "https://cloud.land.gov.taipei/urland/urban.html"})
    return local.s


def work(code12, fh, total):
    if state["stop"]:
        return
    err = ""
    for k, wait in enumerate((0, 5, 15, 30)):
        time.sleep(wait)
        try:
            r = sess().get(URL, params={"landno": code12, "TName": "10"}, timeout=120)
            j = r.json()
            if isinstance(j, list) and j:
                with lock:
                    fh.write(json.dumps({"code12": code12, **{k2: j[0].get(k2) for k2 in ("LCount", "LArea", "LPArea", "Lmans", "BCount", "BArea", "BPArea", "Bmans", "note")}}, ensure_ascii=False) + "\n")
                    fh.flush(); state["fail"] = 0; state["done"] += 1
                    if state["done"] % 200 == 0:
                        print(f"{state['done']}/{total}", flush=True)
                time.sleep(3.0)
                return
            err = f"空回應 {str(j)[:80]}"
        except Exception as e:  # noqa: BLE001
            err = str(e)
    with lock:
        state["fail"] += 1
        print("失敗", code12, err, flush=True)
        if state["fail"] >= 10:
            state["stop"] = True
            print("連續 10 筆失敗，停止", flush=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    seg = {r["官方段名"]: r["官方段碼"] for r in csv.DictReader(open(CASE / "地段對照.csv", encoding="utf-8-sig")) if r["官方段碼"]}
    codes = []
    for r in csv.DictReader(open(CASE / "不重複地號清單_中山區_官方去重.csv", encoding="utf-8-sig")):
        m, _, c = r["地號_母子號"].partition("-")
        codes.append(seg[r["官方段名"]][2:] + f"{int(m):04d}{int(c or 0):04d}")  # 段碼 6 碼的後 4 碼 ＋ 地號 8 碼
    assert len(codes) == 6650 and len(set(codes)) == 6650 and all(len(c) == 12 for c in codes)
    if "--all" in sys.argv:  # 全中山區 27,056 個地號（先前 6,650 個已查者略過，沿用同一個結果檔）
        import glob
        full = []
        for p in sorted(glob.glob(str(ROOT / "資料庫" / "原始檔" / "臺北市中山區地號_LandDyn" / "page_*.json"))):
            full += [a["attributes"]["AA48"] + a["attributes"]["AA49"] for a in json.load(open(p, encoding="utf-8"))["features"]]
        assert len(full) == 27056 and len(set(full)) == 27056
        print(f"提醒：6,650 清單中有 {len(set(codes) - set(full))} 個不在全區地號圖層（沿用先前結果，不影響其餘）", flush=True)
        cs = set(codes)
        codes = [c for c in codes] + [c for c in full if c not in cs]
    f = OUT / "ralids_raw.jsonl"
    done = set()
    if f.exists():  # 容錯：檔內有壞行
        for l in f.read_bytes().split(b"\n"):
            try:
                done.add(json.loads(l.decode("utf-8", errors="replace"))["code12"])
            except Exception:
                pass
    todo = [c for c in codes if c not in done]
    print(f"總 {len(codes)}，已完成 {len(done)}，待查 {len(todo)}", flush=True)
    t0 = time.time()
    with open(f, "a", encoding="utf-8") as fh, ThreadPoolExecutor(max_workers=3) as ex:
        list(ex.map(lambda c: work(c, fh, len(todo)), todo))
    print(f"結束：本次完成 {state['done']}，耗時 {time.time() - t0:.0f} 秒", flush=True)


if __name__ == "__main__":
    main()
