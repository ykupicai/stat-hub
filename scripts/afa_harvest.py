# -*- coding: utf-8 -*-
"""農情報告資源網 鄉鎮作物查詢：抓嘉義縣各鄉鎮、各作物的結實(收穫)面積與收量"""
import requests, urllib3, json, time, sys
from lxml import html as LH

urllib3.disable_warnings()
COND = 'https://agr.afa.gov.tw/afa/pgcroptown_cond.jsp'
RES = 'https://agr.afa.gov.tw/afa/pgcroptown.jsp'
CITY = '0010'  # 嘉義縣


def session():
    s = requests.Session(); s.verify = False
    s.headers.update({'User-Agent': 'Mozilla/5.0'})
    s.get(COND, timeout=60)
    return s


def query(s, year, cat, crop):
    r = s.post(RES, data={'accountingyear': year, 'item': '03', 'corn001': cat,
                          'crop': crop, 'city': CITY, 'btnSend': '送　出', 'isPrint': ''}, timeout=120)
    d = LH.fromstring(r.text)
    out = {}
    for t in d.xpath('//table'):
        rows = [[' '.join(c.text_content().split()) for c in tr.xpath('./td|./th')] for tr in t.xpath('.//tr')]
        if len(rows) < 2 or not rows[0] or '縣市鄉鎮名稱' not in rows[0][0]:
            continue
        for row in rows[2:]:
            if len(row) < 5:
                continue
            place = row[0].replace('嘉義縣', '').replace(' ', '')
            if place.startswith('合'):
                place = '合計'
            def num(x):
                x = x.replace(',', '').strip()
                try: return float(x)
                except ValueError: return 0.0
            out[place] = (num(row[2]), num(row[4]))  # 結實面積(公頃), 收量(公斤)
    return out


def main(years=('113', '114')):
    codes = json.load(open('afa_crop_codes.json', encoding='utf-8'))
    s = session()
    data = {}
    for year in years:
        for cat, lst in codes.items():
            for code, name in lst:
                for attempt in range(3):
                    try:
                        d = query(s, year, cat, code)
                        break
                    except Exception as e:
                        print('retry', year, cat, code, e, flush=True); time.sleep(2); s = session()
                else:
                    d = {}
                if d:
                    data.setdefault(year, {}).setdefault(cat, {})[code] = {'name': name, 'rows': d}
            print('done', year, cat, len(data.get(year, {}).get(cat, {})), flush=True)
    json.dump(data, open('afa_data.json', 'w', encoding='utf-8'), ensure_ascii=False)
    print('SAVED')


if __name__ == '__main__':
    main()
