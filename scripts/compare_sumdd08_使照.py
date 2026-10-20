"""用使用執照 XML（含地段地號、建築面積、各層樓地板面積、竣工日期）檢驗 BuildStat_Fage 的 sumdd08 / fageavg 意義。

做法：取「使用分區＝住宅區、建造類別＝新建、只含單一地號」的使用執照，依 段名＋地號 對到 BuildStat_Fage 地號面，
  比較 sumdd08 與 (a) 建築面積（建築投影）(b) 地上樓地板面積 (c) 地上＋地下 (d) 含突出物之總樓地板面積；
  並比較 fageavg 與 2026－竣工年。只取該地號上僅有一張新建使照者，避免多棟疊加。
輸入：../taipei-house-age-map/使用執照/*.xml、資料庫/原始檔/臺北市建物屋齡_BuildStat_Fage/page_*.json
輸出：行政區屋齡/現況_地政局圖層/sumdd08檢驗_住宅區.csv（逐筆）與終端摘要
執行：python scripts/compare_sumdd08_使照.py
"""
import glob
import io
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from lxml import etree

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
LIC = ROOT.parent / "taipei-house-age-map" / "使用執照"
RAW = ROOT / "資料庫" / "原始檔" / "臺北市建物屋齡_BuildStat_Fage"
OUT = ROOT / "案件" / "臺北市_不動產交易分析" / "行政區屋齡" / "現況_地政局圖層"
FL = re.compile(r"(地上|地下|突出物)(\d+)樓,面積:([\d.]+)")
PARCEL = re.compile(r"臺北市.{2}區(.+?段.*?小段|.+?段)(\d{4})-(\d{4})號")


def txt(e, tag):
    x = e.find(tag)
    return (x.text or "").strip() if x is not None else ""


def num(s):
    try:
        return float(s)
    except ValueError:
        return np.nan


def parse_licenses():
    rows = []
    for f in sorted(glob.glob(str(LIC / "*.xml"))):
        try:
            root = etree.parse(f, etree.XMLParser(recover=True, huge_tree=True)).getroot()
        except Exception:  # noqa: BLE001
            continue
        for e in root.iter("執照"):
            pcs = [(m.group(1), m.group(2) + m.group(3)) for t in e.iterfind("全地段地號/地段地號")
                   if (m := PARCEL.search(t.text or ""))]
            area = {"地上": 0.0, "地下": 0.0, "突出物": 0.0}
            for t in e.iterfind("建築概要/樓層"):
                m = FL.search(t.text or "")
                if m:
                    area[m.group(1)] += float(m.group(3))
            rows.append({"id": e.get("號碼"), "發照日": txt(e, "發照日期"), "竣工": txt(e, "竣工日期"), "類別": txt(e, "建造類別"),
                         "分區": txt(e, "使用分區"), "地上層": num(txt(e, "建物資訊/地上層數")), "地下層": num(txt(e, "建物資訊/地下層數")),
                         "戶數": num(txt(e, "建物資訊/戶數")), "棟數": num(txt(e, "建物資訊/棟數")),
                         "基地面積": num(txt(e, "建物面積/其他基地面積")) + (num(txt(e, "建物面積/騎樓基地面積")) or 0),
                         "建築面積": num(txt(e, "建物面積/建築面積")), "地上樓地板": area["地上"], "地下樓地板": area["地下"], "突出物": area["突出物"],
                         "地號數": len(pcs), "地段": pcs[0][0] if pcs else "", "地號8碼": pcs[0][1] if pcs else ""})
    return pd.DataFrame(rows)


def main():
    lic = parse_licenses()
    print("使照 XML 解析", len(lic), "筆；有地段地號", int((lic["地號數"] > 0).sum()), "；住宅區", int((lic["分區"] == "住宅區").sum()))
    ok = lic[(lic["分區"] == "住宅區") & (lic["類別"] == "新建") & (lic["地號數"] == 1) & (lic["建築面積"] > 0) & (lic["地上樓地板"] > 0)].copy()
    cnt = ok.groupby(["地段", "地號8碼"]).size()
    allcnt = lic[lic["地號數"] >= 1].assign(k=lambda d: d["地段"] + d["地號8碼"]).groupby("k").size()
    ok["k"] = ok["地段"] + ok["地號8碼"]
    ok = ok[ok["k"].map(allcnt) == 1]  # 該地號只出現在這一張使照
    rows = []
    for f in sorted(glob.glob(str(RAW / "page_*.json"))):
        for ft in json.load(open(f, encoding="utf-8"))["features"]:
            rows.append(ft["attributes"])
    p = pd.DataFrame(rows)
    m = ok.merge(p, left_on=["地段", "地號8碼"], right_on=["KCNT", "AA49"], how="inner")
    m["竣工年"] = m["竣工"].map(lambda s: int(s[:-4]) + 1911 if len(s) >= 6 and s[:-4].isdigit() else np.nan)
    m["總含突出"] = m["地上樓地板"] + m["地下樓地板"] + m["突出物"]
    m["地上加地下"] = m["地上樓地板"] + m["地下樓地板"]
    print("住宅區、單一地號、單一使照者", len(ok), "；對到 BuildStat_Fage", len(m))
    m = m[m["sumdd08"] > 0]
    res = {}
    for name, col in [("建築面積(投影)", "建築面積"), ("地上樓地板", "地上樓地板"), ("地上+地下", "地上加地下"), ("地上+地下+突出物", "總含突出")]:
        r = m["sumdd08"] / m[col]
        res[name] = {"中位數比": round(r.median(), 3), "±2%內": f"{(r.sub(1).abs() <= 0.02).mean():.0%}", "±10%內": f"{(r.sub(1).abs() <= 0.10).mean():.0%}",
                     "P25": round(r.quantile(.25), 3), "P75": round(r.quantile(.75), 3)}
    print(pd.DataFrame(res).T.to_string())
    r = m["sumdd08"] / m["基地面積"]
    print("sumdd08／基地面積（容積率概念）中位數", round(r.median(), 2), "；建築面積／基地面積（建蔽率）中位數", round((m["建築面積"] / m["基地面積"]).median(), 2))
    print("AA10 / 基地面積 中位數", round((m["AA10"] / m["基地面積"]).median(), 3), "；Shape_Area / 基地面積", round((m["Shape_Area"] / m["基地面積"]).median(), 3))
    print("ct vs 戶數 相等比例", f"{(m['ct'] == m['戶數']).mean():.0%}", "；ct 中位數／戶數中位數", m["ct"].median(), m["戶數"].median())
    print("DD13H vs 地上層 相等比例", f"{(pd.to_numeric(m['DD13H'], errors='coerce') == m['地上層']).mean():.0%}")
    d = m["fageavg"] - (2026 - m["竣工年"])
    print("fageavg－(2026－竣工年)：中位數", d.median(), "；=0 比例", f"{(d == 0).mean():.0%}", "；±1 內", f"{(d.abs() <= 1).mean():.0%}")
    print("fageavg=55 者共", int((m["fageavg"] == 55).sum()), "；其竣工年分布", m.loc[m["fageavg"] == 55, "竣工年"].value_counts().head(6).to_dict())
    cols = ["id", "地段", "地號8碼", "竣工年", "地上層", "戶數", "基地面積", "建築面積", "地上樓地板", "地上加地下", "AA10", "sumdd08", "ct", "fageavg", "DD13H"]
    m[cols].to_csv(OUT / "sumdd08檢驗_住宅區.csv", index=False, encoding="utf-8-sig")
    print(m[cols].sort_values("竣工年", ascending=False).head(8).round(1).to_string(index=False))


if __name__ == "__main__":
    main()
