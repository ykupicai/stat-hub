"""產生中山區私有人數 RALIDs 查詢的進度頁（單檔 HTML），並記錄歷史點以估速度與剩餘時間。
執行：python scripts/make_私有人數進度頁.py [輸出html路徑]
"""
import json, os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "案件" / "臺北市_不動產交易分析" / "地號清單" / "中山區_私有人數API"
RAW, HIST = D / "ralids_raw.jsonl", D / "進度歷史.json"
P1, ALL = 6650, 27056
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else D / "進度頁.html"


def read():
    ok = {}
    for line in RAW.read_bytes().split(b"\n"):
        try:
            j = json.loads(line.decode("utf-8", errors="replace")); ok[j["code12"]] = j
        except Exception:
            pass
    return ok


def alive():
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
                            "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'RALIDs' }).Count"],
                           capture_output=True, text=True, timeout=30)
        return int((r.stdout or "0").strip() or 0)
    except Exception:
        return -1


ok = read()
n = len(ok)
p1 = sum(1 for k in ok if True) if False else None
now = time.time()
hist = json.loads(HIST.read_text(encoding="utf-8")) if HIST.exists() else []
hist.append([now, n]); hist = [h for h in hist if now - h[0] < 6 * 3600][-200:]
HIST.write_text(json.dumps(hist), encoding="utf-8")
base = next((h for h in hist if now - h[0] <= 1800), hist[0])
rate = (n - base[1]) / max(now - base[0], 1) * 60 if now - base[0] > 60 else None  # 筆/分
left = ALL - n
eta = f"約 {left / rate / 60:.1f} 小時" if rate and rate > 0.5 else "速度不足，無法估算"
proc = alive()
state = "執行中" if proc >= 1 else ("已停止" if proc == 0 else "未知")
cnt = sum(1 for j in ok.values() if (j.get("Lmans") or 0) > 0)
html = f"""<title>中山區私有人數進度</title>
<meta name="claude:viewport-fit-sides" content="cover">
<style>
:root{{--bg:#f6f7f5;--fg:#1d2a26;--mut:#66736e;--line:#d9dfdb;--bar:#2f7d6b;--bar2:#a9cfc5;--warn:#b4561c;--card:#fff}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#151b19;--fg:#e5ece8;--mut:#92a09a;--line:#2b3733;--bar:#5cc2a8;--bar2:#2d4a42;--warn:#f0a064;--card:#1c2421;color-scheme:dark}}}}
:root[data-theme="dark"]{{--bg:#151b19;--fg:#e5ece8;--mut:#92a09a;--line:#2b3733;--bar:#5cc2a8;--bar2:#2d4a42;--warn:#f0a064;--card:#1c2421;color-scheme:dark}}
body{{background:var(--bg);color:var(--fg);font:15px/1.6 "Noto Sans TC","Microsoft JhengHei",system-ui,sans-serif;padding-block:20px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}}
main{{max-width:560px;margin:0 auto;display:grid;gap:18px}}
h1{{font-size:1.25rem;margin:0}} .sub{{color:var(--mut);font-size:.85rem}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 16px;display:grid;gap:8px}}
.big{{font-size:2rem;font-weight:700;font-variant-numeric:tabular-nums}} .big small{{font-size:.9rem;color:var(--mut);font-weight:400}}
.bar{{height:12px;background:var(--bar2);border-radius:6px;overflow:hidden}} .bar i{{display:block;height:100%;background:var(--bar)}}
dl{{display:grid;grid-template-columns:1fr auto;gap:6px 12px;margin:0;font-variant-numeric:tabular-nums}} dt{{color:var(--mut)}} dd{{margin:0;text-align:right}}
.st{{color:{'var(--bar)' if proc>=1 else 'var(--warn)'};font-weight:700}}
</style>
<main>
<div><h1>中山區私有人數查詢進度</h1><div class="sub">資料時間 {time.strftime('%m/%d %H:%M', time.localtime(now))}（快照，需重新產生才會更新）</div></div>
<div class="card"><div class="sub">第一階段：交易地號 6,650 個</div><div class="big">{min(n,P1):,}<small> / {P1:,}</small></div>
<div class="bar"><i style="width:{min(n,P1)/P1*100:.1f}%"></i></div></div>
<div class="card"><div class="sub">全中山區 27,056 個地號</div><div class="big">{n:,}<small> / {ALL:,}（{n/ALL:.1%}）</small></div>
<div class="bar"><i style="width:{n/ALL*100:.1f}%"></i></div></div>
<div class="card"><dl>
<dt>爬蟲狀態</dt><dd class="st">{state}（{proc} 個程序）</dd>
<dt>近 30 分鐘速度</dt><dd>{f'{rate:.1f} 筆/分' if rate is not None else '資料點不足'}</dd>
<dt>剩餘</dt><dd>{left:,} 個</dd>
<dt>預估還需</dt><dd>{eta}</dd>
<dt>已查到且有私有所有權人者</dt><dd>{cnt:,}</dd></dl></div>
</main>
"""
OUT.write_text(html, encoding="utf-8")
print(OUT, n, state, rate, eta)
