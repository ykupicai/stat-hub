# -*- coding: utf-8 -*-
"""嘉義縣主計處「公務統計報表查詢」(statweb/Page/stat08.aspx) 報表清冊擷取器。

以「製表機關」逐一查詢並翻頁，收集 (機關, 表號, 表名, 資料時間) 清冊。
表名輸入框有 watermark extender，不要帶關鍵字查；用機關拉全清單再自己過濾。
"""
import sys, io, re, json, time, requests, urllib3
from lxml import html as LH
urllib3.disable_warnings()

URL = "https://cyhg.dgbas.gov.tw/statweb/Page/stat08.aspx"
PFX = "ctl00$ContentPlaceHolder1$"
OFFICES = {
    "3001": "主計處", "3002": "民政處", "3003": "教育處", "3004": "經濟發展處",
    "3005": "建設處", "3006": "水利處", "3007": "農業處", "3008": "地政處",
    "3010": "行政處", "3012": "人事處", "3013": "政風處", "3014": "勞工暨青年發展處",
    "5001": "警察局", "5002": "消防局", "5003": "衛生局", "5004": "環境保護局",
    "5005": "財政稅務局", "5006": "文化觀光局", "5007": "社會局",
}


def hidden(doc):
    return {i.get('name'): (i.get('value') or '')
            for i in doc.xpath('//input[@type="hidden"]') if i.get('name')}


def parse(doc):
    out, pages = [], set()
    for tr in doc.xpath('//table[@id="tbReport"]//tr'):
        tds = tr.xpath('./td')
        if len(tds) < 4:
            continue
        cells = [' '.join(td.text_content().split()) for td in tds]
        if cells[1] and re.match(r'^[\d-]+$', cells[1].replace(' ', '')):
            name = re.sub(r'\s*(XLS|XLSX|ODS|PDF|DOC|DOCX)\s*$', '', cells[2], flags=re.I)
            fmt = (re.search(r'(XLSX|XLS|ODS|PDF|DOCX|DOC)\s*$', cells[2], re.I) or [None])
            out.append({"office": cells[0], "no": cells[1], "name": name,
                        "format": (fmt.group(1).upper() if hasattr(fmt, 'group') else ''),
                        "period": cells[3]})
    for a in doc.xpath('//a[contains(@href,"__doPostBack")]'):
        m = re.search(r"__doPostBack\('([^']+)','([^']*)'\)", a.get('href') or '')
        t = ' '.join(a.text_content().split())
        if m and t.isdigit():
            pages.add((int(t), m.group(1), m.group(2)))
    return out, sorted(pages)


def fetch_office(s, code, year="", sleep=0.3, max_pages=40):
    """查某機關某年度的報表清冊，翻完所有頁。

    ⚠ 翻頁 POST 必須把 ddlYear/ddlPeriod/ddlOffice/textbox* 一起帶上。
      只送 __EVENTTARGET 的話 ASP.NET 會把下拉選單視為預設值，
      第 2 頁之後篩選條件就失效，回傳變成「全機關最新月報」。
    """
    sel = {PFX + "ddlYear": year, PFX + "ddlPeriod": "請選擇週期",
           PFX + "ddlOffice": code, PFX + "textboxRPTNo": "", PFX + "textboxRPTNM": ""}
    doc = LH.fromstring(s.get(URL, timeout=60).text)
    form = hidden(doc); form.update(sel)
    form[PFX + "buttonSearch"] = "查詢"
    doc = LH.fromstring(s.post(URL, data=form, timeout=90).text)
    rows, pages = parse(doc)
    seen = {(r['no'], r['period']) for r in rows}
    done = {1}
    while len(done) < max_pages:
        nxt = [p for p in pages if p[0] not in done]
        if not nxt:
            break
        num, tgt, arg = nxt[0]
        form = hidden(doc); form.update(sel)          # ← 關鍵：翻頁也要帶篩選條件
        form.update({"__EVENTTARGET": tgt, "__EVENTARGUMENT": arg})
        doc = LH.fromstring(s.post(URL, data=form, timeout=90).text)
        more, pages = parse(doc)
        done.add(num)
        bad = [r for r in more if r['office'] != OFFICES.get(code, '')]
        if bad:
            raise RuntimeError(f"第{num}頁篩選失效，混入其他機關：{sorted({r['office'] for r in bad})}")
        for r in more:
            if (r['no'], r['period']) not in seen:
                seen.add((r['no'], r['period'])); rows.append(r)
        time.sleep(sleep)
    return rows


if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    codes = sys.argv[1:] or list(OFFICES)
    s = requests.Session(); s.verify = False
    s.headers['User-Agent'] = 'Mozilla/5.0'
    all_rows = []
    for c in codes:
        rs = fetch_office(s, c)
        print(f"{c} {OFFICES.get(c,'?')}: {len(rs)} 筆")
        all_rows += rs
    json.dump(all_rows, io.open("cyhg_stat08_清冊.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("總計", len(all_rows), "筆 ->  cyhg_stat08_清冊.json")
