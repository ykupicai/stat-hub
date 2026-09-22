# -*- coding: utf-8 -*-
"""中央氣象署 CODiS 觀測資料查詢服務：單站全歷史逐月觀測值擷取器。

用法：
    python cwa_codis_fetch.py 467410 out.json      # 臺南站
    python cwa_codis_fetch.py 467480 out.json      # 嘉義站

回傳 JSON 的 data[0].dts 為該站「建站至今」的逐月統計（DataYearMonth）。
臺南站 467410 實測 1897-01 ~ 迄今共 1557 筆。

口徑對應（對應氣象署「氣候月平均」公布值）：
    最高溫度 = AirTemperature.MeanDailyMaximum   （月平均最高氣溫，非月極端最高）
    平均溫度 = AirTemperature.Mean
    最低溫度 = AirTemperature.MeanDailyMinimum
    降水量   = Precipitation.Accumulation        （月總量）
    日照時數 = SunshineDuration.Total

注意：政府網站憑證常缺 Subject Key Identifier，一律 verify=False。
"""
import sys, json, requests, urllib3

urllib3.disable_warnings()
API = "https://codis.cwa.gov.tw/api/station"


def fetch_monthly(stn_id: str, stn_type: str = "cwb") -> dict:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://codis.cwa.gov.tw/StationData",
    })
    # type=report_year 回傳「該站全歷史逐月」；date 僅作為請求參數，不影響回傳範圍
    body = {"date": "2020-01-01T00:00:00", "type": "report_year",
            "stn_ID": stn_id, "stn_type": stn_type, "more": "", "start": "", "end": ""}
    r = s.post(API, data=body, verify=False, timeout=180)
    r.raise_for_status()
    return r.json()


if __name__ == "__main__":
    stn = sys.argv[1] if len(sys.argv) > 1 else "467410"
    out = sys.argv[2] if len(sys.argv) > 2 else f"codis_{stn}_monthly_raw.json"
    j = fetch_monthly(stn)
    dts = j["data"][0]["dts"]
    with open(out, "w", encoding="utf-8") as f:
        json.dump(j, f, ensure_ascii=False)
    print(f"{stn}: {len(dts)} 筆，{dts[0]['DataYearMonth'][:7]} ~ {dts[-1]['DataYearMonth'][:7]} -> {out}")
