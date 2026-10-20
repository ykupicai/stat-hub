# -*- coding: utf-8 -*-
"""比對交易地號清單的「地段」與農業部/內政部官方段名(cadastre-check moa.sections)。
輸出 案件/臺北市_不動產交易分析/地號清單/地段對照.csv (地段 -> 官方行政區/段名/段碼/狀態)。
用法: PYTHONUTF8=1 python -I scripts/check_臺北市_地段官方對照.py
"""
import sys, os, csv, collections
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.expanduser("~/.claude/skills/cadastre-check/scripts"))
import moa
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "案件", "臺北市_不動產交易分析", "地號清單")
c = moa._pick(moa.counties(), "臺北市")
off = {}                      # 官方段名 -> (行政區, 段碼)
for t in moa.towns(c):
    for n, code in moa.sections(c, t).items():
        assert n not in off, n  # 臺北市段名全市唯一
        off[n] = (t, code)
rows = list(csv.DictReader(open(os.path.join(D, "不重複地號清單.csv"), encoding="utf-8-sig")))
cnt = collections.Counter(); dists = collections.defaultdict(collections.Counter)
for r in rows:
    cnt[r["地段"]] += 1; dists[r["地段"]][r["行政區"]] += 1
out = []
for seg in sorted(cnt):
    if seg in off:
        t, code = off[seg]; fix = seg; note = "對得上"
        if t not in dists[seg] or len(dists[seg]) > 1:
            note = "段名對得上；實價登錄行政區與官方不同(段跨區或以交易標的所在區申報)，查詢請以官方行政區"
    elif "?" in seg and seg.replace("?", "犂") in off:
        fix = seg.replace("?", "犂"); t, code = off[fix]; note = "字元亂碼(?→犂)，修正後對得上"
    else:
        fix = ""; t = code = ""; note = "官方查無此段"
    out.append([seg, "/".join(f"{d}:{n}" for d, n in dists[seg].most_common()), cnt[seg], fix, t, code, note])
with open(os.path.join(D, "地段對照.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f); w.writerow(["實價登錄地段","出現行政區:不重複地號數","不重複地號數","官方段名","官方行政區","官方段碼","狀態"]); w.writerows(out)
bad = [o for o in out if o[6] == "官方查無此段"]
print("不同地段", len(out), "官方查無", len(bad), bad)
print("行政區不一致", sum(1 for o in out if "行政區與官方不同" in o[6]), "亂碼修正", sum(1 for o in out if "亂碼" in o[6]))
print("官方版次", moa.newest_version(), "官方段總數", len(off))
