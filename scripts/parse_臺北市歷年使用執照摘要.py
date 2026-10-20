"""解析 臺北市歷年使用執照摘要（XML，民國 90～114 年）→ 使照層級表與「使照×地號」展開表。

每張使照：發照日期、竣工日期、建造類別、使用分區、地上層數、建築面積、地段號清單；
  地上樓地板（估）＝建築面積×地上層數（試作用，沿用使用者指定估法）；地上樓地板（明細）＝樓層明細中「地上」各層（含夾層）面積加總。
輸入：資料庫/原始檔/臺北市歷年使用執照摘要/使用執照摘要.xml　輸出：同資料夾 使照_層級.csv、使照_地號展開.csv
執行：python scripts/parse_臺北市歷年使用執照摘要.py
"""
import io
import re
import sys
from pathlib import Path

import pandas as pd
from lxml import etree

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "資料庫" / "原始檔" / "臺北市歷年使用執照摘要"
PARCEL = re.compile(r"臺北市(.{2}區)(.+?)(\d{4})-(\d{4})號")
UP = re.compile(r"地上(\d+)樓[^,]*,面積:([\d.]+)")


def num(s):
    m = re.search(r"-?\d+(?:\.\d+)?", s or "")
    return float(m.group()) if m else None


def main():
    lic, ex = [], []
    for _, e in etree.iterparse(str(D / "使用執照摘要.xml"), tag="Data", recover=True, huge_tree=True):
        g = lambda t: (e.findtext(t) or "").strip()
        ps = [m.groups() for t in e.iterfind("地段地號/地段號") if (m := PARCEL.search(t.text or ""))]
        up = sum(float(m.group(2)) for t in e.iterfind("建築概要/樓層") if "突出物" not in (t.text or "") and "地下" not in (t.text or "") and (m := UP.search(t.text or "")))
        fl = num(g("建物資訊/地上層數")); ba = num(g("建物面積/建築面積"))
        lic.append({"執照號碼": g("執照號碼"), "發照日期": g("發照日期"), "竣工日期": g("竣工日期"), "類別": g("建造類別"), "使用分區": g("使用分區"), "地上層數": fl,
                    "地下層數": num(g("建物資訊/地下層數")), "戶數": num(g("建物資訊/戶數")), "建築面積": ba,
                    "基地面積": (num(g("建物面積/騎樓基地面積")) or 0) + (num(g("建物面積/其他基地面積")) or 0), "地號數": len(ps),
                    "地上樓地板_估": ba * fl if ba is not None and fl is not None else None, "地上樓地板_明細": up or None})
        for p in ps:
            ex.append({"執照號碼": g("執照號碼"), "行政區": p[0], "段名": p[1], "地號8碼": p[2] + p[3]})
        e.clear()
    L = pd.DataFrame(lic); X = pd.DataFrame(ex)
    L.to_csv(D / "使照_層級.csv", index=False, encoding="utf-8-sig"); X.to_csv(D / "使照_地號展開.csv", index=False, encoding="utf-8-sig")
    print("使照", len(L), "；有地號", int((L["地號數"] > 0).sum()), "；地號展開", len(X), "；不重複(段,地號)", X.drop_duplicates(["段名", "地號8碼"]).shape[0])
    print("類別", L["類別"].value_counts().to_dict(), "；發照年", L["發照日期"].str[:-4].astype(int).min(), L["發照日期"].str[:-4].astype(int).max())
    ok = L.dropna(subset=["地上樓地板_估", "地上樓地板_明細"])
    r = ok["地上樓地板_明細"] / ok["地上樓地板_估"]
    print("明細／估算（地上樓地板）：n", len(ok), "中位數", round(r.median(), 3), "P25", round(r.quantile(.25), 3), "P75", round(r.quantile(.75), 3), "；加總比", round(ok["地上樓地板_明細"].sum() / ok["地上樓地板_估"].sum(), 3))
    print("缺建築面積或層數", int(L["地上樓地板_估"].isna().sum()))


if __name__ == "__main__":
    main()
