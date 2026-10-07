"""臺南農再 表4-7（臺南市農林漁牧業家數成長綜整表）以主計總處三大普查動態查詢回測。

書中值：期中報告書（20261001 內文-<同事>，已送件版）表4-7，由 extract 步驟讀出後寫入 BOOK_JSON。
普查值：104、109 年農林漁牧業普查，4 個「普查家數」統計項 × 鄉鎮別。
輸出：案件/臺南農再/原始報表/普查_表4-7_104_109.json（原始回應）＋ 比對結果印出。
用法：python scripts/backtest_臺南農再_表4-7_普查.py <書件docx副本>
"""
import io
import json
import sys
from pathlib import Path

import docx
from docx.table import Table
from docx.text.paragraph import Paragraph

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "stat_mcp"))
import census  # noqa: E402

ITEMS = ["農牧業普查家數", "農事及畜牧服務業普查家數", "林業普查家數", "漁業普查家數"]
CATS = ["農牧業", "農事及畜牧服務業", "林業", "漁業"]
RAW = ROOT / "案件" / "臺南農再" / "原始報表" / "普查_表4-7_104_109.json"


def book_table(path):
    d = docx.Document(path)
    items = list(d.element.body.iterchildren())
    for i, el in enumerate(items):
        if el.tag.endswith("}p") and Paragraph(el, d).text.strip().startswith("表4-7、") and i > 500:
            for e in items[i + 1:i + 5]:
                if e.tag.endswith("}tbl"):
                    return [[c.text.strip() for c in r.cells] for r in Table(e, d).rows]
    raise RuntimeError("找不到表4-7")


def num(s):
    s = s.replace(",", "").strip()
    return None if s in ("", "-", "－") else int(s)


def main(docx_path):
    rows = book_table(docx_path)
    book = {}
    for r in rows[2:]:
        area = r[0]
        for k, cat in enumerate(CATS):
            book[(area, cat, 104)] = num(r[1 + 3 * k])
            book[(area, cat, 109)] = num(r[2 + 3 * k])
    cen, raw = {}, {}
    town_only = {"農事及畜牧服務業普查家數"}  # 動態查詢系統只有縣市別，無鄉鎮別（2026-10-07 實測）
    for y in ("104農林漁牧", "109農林漁牧"):
        yr = int(y[:3])
        res = census.query(y, [i for i in ITEMS if i not in town_only], ["鄉鎮別"])
        raw[y + "_鄉鎮別"] = res
        for d in res["data"]:
            town = d["鄉鎮別"]
            if not town.startswith("臺南市"):
                continue
            area = town.replace("臺南市", "")
            for it, cat in zip(ITEMS, CATS):
                if it not in town_only:
                    cen[(area, cat, yr)] = num(str(d.get(it, "")))
        res = census.query(y, sorted(town_only), ["縣市別"])
        raw[y + "_縣市別"] = res
        for d in res["data"]:
            if d["縣市別"] == "臺南市":
                for it, cat in zip(ITEMS, CATS):
                    if it in town_only:
                        cen[("總計", cat, yr)] = num(str(d.get(it, "")))
    RAW.parent.mkdir(parents=True, exist_ok=True)
    RAW.write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
    # 總計
    for cat in CATS:
        for yr in (104, 109):
            if ("總計", cat, yr) not in cen:
                cen[("總計", cat, yr)] = sum(v or 0 for (a, c, y), v in cen.items() if c == cat and y == yr and a != "總計")
    diffs, n = [], 0
    for key, bv in book.items():
        if key not in cen:  # 普查端無此格（農事及畜牧服務業的各區）→ 不比對
            continue
        cv = cen[key]
        n += 1
        if (bv or 0) != (cv or 0 if isinstance(cv, int) or cv is None else cv):
            diffs.append((key, bv, cv))
    print(json.dumps({"比對格數": n, "不符": len(diffs),
                      "不符明細": [{"行政區": k[0], "類別": k[1], "年": k[2], "書中": b, "普查": c} for k, b, c in diffs]},
                     ensure_ascii=False, indent=1))
    tot = {f"{c}{y}": cen[("總計", c, y)] for c in CATS for y in (104, 109)}
    print("普查臺南市合計：", tot)


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    main(sys.argv[1])
