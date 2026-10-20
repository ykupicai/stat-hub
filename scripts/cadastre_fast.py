# -*- coding: utf-8 -*-
"""cadastre-check 的「加速／可觀測」包裝(不改原 skill,import 後包裝)。

實測結論(2026-10-17):單筆延遲幾乎全在農業部 LandAddressToLocation_ring 的伺服器端
(TTFB 約 9 秒,連線/TLS 僅 0.06 秒,body 0.00 秒);內政部 getLandInfo 僅約 0.15 秒。
原版 check_one 的段清單/token/版次本來就在 moa 模組內快取,每筆重複成本≈0。
所以本包裝能做的是:
  1. 一次性前置:版次、token、段碼一次解析(prepare),每筆 0 額外請求。
  2. 快路徑:OK 情形只打 1 次農業部 + 1 次內政部;非 OK(MISMATCH/NOT_FOUND/重測)
     才退回原版 check_one(保留重測追蹤邏輯與 14 碼閘門)。
  3. 內政部屬性失敗不再被吞成「查無屬性」警告,而是明確判失敗並「只重試屬性」,
     不必重打 9 秒的農業部。
  4. 分段計時(moa_s / nlsc_s)。
真正的加速來自多程序平行(伺服器延遲可平行),不是單線程本身。
"""
import os, sys, time, json
SK = os.path.expanduser("~/.claude/skills/cadastre-check/scripts")
sys.path.insert(0, SK)
import config; config.use_utf8_console()
import cadlib as C, check, moa, api


def prepare(city, town, sections):
    """一次性:版次、token、官方寫法與段碼。回傳 ctx。"""
    t = time.time()
    ver = moa.newest_version()
    moa.config()
    secmap = {}
    for s in sections:
        c, t_, sname, code = moa.resolve(city, town, s, ver)
        secmap[s] = (c, t_, sname, code)
    return {"ver": ver, "cache": config.cache_dir(), "secmap": secmap,
            "prepare_s": round(time.time() - t, 2)}


def _land_info_strict(city_code, sec4, no8):
    """同 cadlib.get_land_info,但網路例外會拋出(原版吞掉變 None)。回傳 dict 或 None(真的查無)。"""
    txt = C._http(C.RALID, data={"city": city_code, "sect": sec4, "landno": no8},
                  referer=C.NLSC_REFERER)
    if not txt.strip():
        return None
    j = json.loads(txt)
    r = (j or {}).get("ralid")
    if not r or not r.get("AA49"):
        return None
    return {"面積": r.get("AA10"), "使用分區": C._b64(r.get("AA11")),
            "使用地類別": C._b64(r.get("AA12"))}


def fast_one(city, town, section, landno, ctx, memo=None):
    """回傳 dict:status(OK/NOT_FOUND/MISMATCH/RESURVEYED/ERROR), registry, map_area, dev, code14, moa_s, nlsc_s, path, note"""
    out = {"status": "ERROR", "registry": None, "map_area": None, "dev": None,
           "code14": None, "moa_s": 0.0, "nlsc_s": 0.0, "path": "fast", "note": ""}
    no8 = C.parse_landno(landno)
    memo = {} if memo is None else memo   # 重試時保留農業部結果,屬性失敗只重打屬性
    if "p" not in memo:
        t = time.time()
        memo["p"] = moa.parcel(city, town, section, no8, ctx["ver"])  # 段清單已快取;例外交呼叫端
        memo["moa_s"] = round(time.time() - t, 2)
    p = memo["p"]; out["moa_s"] = memo["moa_s"]
    if p is None or p.get("mismatch"):
        # 非快路徑:退回原版(含重測追蹤與完整閘門)。多花一次農業部請求,但這類很少。
        out["path"] = "fallback"
        res = check.check_one(city, town, section, landno, ctx, quiet=True)
        rec = api._record(res)
        out["status"] = res.get("verdict") or "ERROR"
        out["registry"] = (rec.get("registry") or {}).get("area")
        out["map_area"] = rec.get("map_area")
        out["dev"] = rec.get("deviation_pct")
        out["code14"] = (rec.get("parcel") or {}).get("code14")
        out["note"] = "|".join(rec.get("notes") or [])[:200]
        return out
    ring = p["ring"]
    mapa = round(abs(C.shoelace(ring)), 4)
    out["code14"] = p["code"]; out["map_area"] = mapa; out["ring"] = ring
    t = time.time()
    info = _land_info_strict(p["段碼"][0], p["段碼"][2:], no8)  # 例外交呼叫端;呼叫端只重試這一段
    out["nlsc_s"] = round(time.time() - t, 2)
    out["status"] = "OK"
    out["_ring_ok"] = True
    if info:
        try:
            r = float(info["面積"]); out["registry"] = r
            out["dev"] = round((mapa - r) / r * 100, 2) if r else 0
        except (TypeError, ValueError):
            pass
    else:
        out["note"] = "內政部查無屬性"
    return out


if __name__ == "__main__":
    # 與原版比對: 取前次試跑的前 5 筆
    import csv
    base = r"C:\Users\USER\OneDrive\文件\project\STATHUB\案件\臺北市_不動產交易分析\地號清單\試跑_中山區\試跑結果.csv"
    rows = list(csv.DictReader(open(base, encoding="utf-8-sig")))[:5]
    sec = rows[0]["段"]
    ctx = prepare("臺北市", "中山區", sorted({r["段"] for r in rows}))
    print("prepare", ctx["prepare_s"], "ver", ctx["ver"])
    res = []
    for r in rows:
        no = r["地號"]
        t = time.time(); o = check.check_one("臺北市", "中山區", r["段"], no, ctx, quiet=True); t_o = time.time() - t
        ro = api._record(o)
        t = time.time(); f = fast_one("臺北市", "中山區", r["段"], no, ctx); t_f = time.time() - t
        same = (ro["parcel"]["code14"] == f["code14"] and (ro["registry"] or {}).get("area") == f["registry"]
                and ro["map_area"] == f["map_area"] and ro["deviation_pct"] == f["dev"] and ro["status"] == f["status"])
        res.append((no, t_o, t_f, same))
        print(no, ro["status"], ro["parcel"]["code14"], (ro["registry"] or {}).get("area"), ro["map_area"], ro["deviation_pct"],
              "| 原版 %.2fs 快版 %.2fs (moa %.2f nlsc %.2f) 一致=%s" % (t_o, t_f, f["moa_s"], f["nlsc_s"], same), flush=True)
        time.sleep(1.5)
    so = sum(x[1] for x in res); sf = sum(x[2] for x in res)
    print("原版合計 %.1fs 快版合計 %.1fs 倍率 %.2fx 全部一致=%s" % (so, sf, so / sf, all(x[3] for x in res)))
