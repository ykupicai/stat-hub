# -*- coding: utf-8 -*-
"""中山區全量:3 程序任務佇列(段按剩餘筆數由大到小),每程序一次一段、單線、間隔 gap。
任一 worker 連續5筆失敗(exit 3)→ 停止全部。節流/連線重設事件≥3 → 降為單程序、間隔 3 秒。
重跑可續(worker 會略過已完成者)。"""
import os, sys, csv, subprocess, time, json, glob
from collections import Counter
BASE = r"C:\Users\USER\OneDrive\文件\project\STATHUB\案件\臺北市_不動產交易分析\地號清單"
OUT = os.path.join(BASE, "中山區_全量")
SRC = os.path.join(BASE, "不重複地號清單_中山區_官方去重.csv")
W = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cadastre_stress.py")
os.makedirs(OUT, exist_ok=True)
rows = list(csv.DictReader(open(SRC, encoding="utf-8-sig")))
cnt = Counter(r["官方段名"] for r in rows)
queue = [(s, False) for s, _ in cnt.most_common()]
# 補幾何:先前已 OK(試跑/壓力/平行)的地號沒存界址環,最後重查一次只為取幾何
BFS = ["德惠段一小段", "北安段四小段", "德惠段二小段", "吉林段一小段", "榮星段五小段", "中山段二小段"]
queue += [(s, True) for s in BFS]
maxp, gap = 3, 1.5; running = {}; stop = False; degraded = False
env = dict(os.environ, PYTHONUTF8="1")
log = open(os.path.join(OUT, "orchestrator.log"), "a", encoding="utf-8")
def L(m):
    m = time.strftime("%H:%M:%S ") + m; print(m, flush=True); log.write(m + "\n"); log.flush()
t0 = time.time(); L("開始 段數 %d" % len(queue))
while queue or running:
    while queue and not stop and len(running) < (1 if degraded else maxp):
        s, bf = queue.pop(0); key = s + ("@補" if bf else "")
        f = open(os.path.join(OUT, "worker_%s.log" % key), "a", encoding="utf-8")
        running[key] = (subprocess.Popen([sys.executable, W, "--sec", s, "--tag", "補幾何" if bf else "全量", "--out", OUT, "--priors"] + (["--backfill"] if bf else []) + ["--gap", str(3.0 if degraded else gap)],
                                       stdout=f, stderr=subprocess.STDOUT, env=env), f)
        L("派工 %s (%d 筆)" % (key, cnt[s]))
    for s in list(running):
        p, f = running[s]
        if p.poll() is not None:
            f.close(); del running[s]
            ev = 0
            jp = os.path.join(OUT, ("補幾何_%s.log.json" if s.endswith("@補") else "全量_%s.log.json") % s.replace("@補", ""))
            if os.path.exists(jp):
                e = json.load(open(jp, encoding="utf-8")).get("事件", {}); ev = e.get("連線重設", 0) + e.get("節流疑似", 0)
            L("完成 %s exit=%s 節流/重設事件=%d" % (s, p.returncode, ev))
            if p.returncode == 3:
                stop = True; L("!! %s 連續5筆失敗,停止派工並等待其他程序收尾" % s)
                for s2, (p2, _) in running.items(): p2.terminate()
            elif ev >= 3 and not degraded:
                degraded = True; L("!! 偵測到節流/重設,降為單程序、間隔3秒")
            elif p.returncode not in (0,):
                stop = True; L("!! %s 異常結束 exit=%s,停止" % (s, p.returncode))
    if stop and not running: break
    time.sleep(5)
L("結束 stop=%s 總耗時 %.0f 秒" % (stop, time.time() - t0))
json.dump({"stop": stop, "elapsed_s": round(time.time() - t0)}, open(os.path.join(OUT, "orchestrator_done.json"), "w"))
