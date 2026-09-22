# -*- coding: utf-8 -*-
"""嘉義縣政府資料庫查詢平台（主計處）資料擷取器"""
import requests, urllib3, sys, json
from lxml import html as LH
urllib3.disable_warnings()
BASE='https://cyhg.dgbas.gov.tw/dgbasweb/'
SHOW='https://cyhg.dgbas.gov.tw/%e7%b6%b2%e9%a0%81%e8%b3%87%e6%96%99%e6%9f%a5%e8%a9%a2/ShowQuery.aspx'

def fetch(varval_url, years=None, areas=None):
    s=requests.Session(); s.verify=False; s.headers['User-Agent']='Mozilla/5.0'
    d=LH.fromstring(s.get(varval_url,timeout=60).text)
    h={i.get('name'):(i.get('value') or '') for i in d.xpath('//input[@type="hidden"]') if i.get('name')}
    dates=[o.get('value') for o in d.xpath('//select[@id="LBDate"]/option')]
    dlabel={o.get('value'):o.text_content().strip() for o in d.xpath('//select[@id="LBDate"]/option')}
    if years: dates=[v for v in dates if dlabel[v].rstrip('年') in {str(y) for y in years}]
    alist=[(a.get('target'), (a.get('aria-label') or '').strip("'")) for a in d.xpath('//div[@id="TMenu"]//a[@target]')]
    if areas: alist=[x for x in alist if x[1] in areas]
    acodes=[x[0] for x in alist]
    cx={}
    for n in range(1,6):
        opts=[o.get('value') for o in d.xpath(f'//select[@id="LBComplex{n}"]/option')]
        if opts: cx[n]=opts
    h['axX']='[Measures]'+''.join(';'+cx[n][0][:5] for n in sorted(cx))
    h['axY']='[Date];[Place]'
    h['axDate']="','".join(dates)
    h['axPlace']=';'.join(acodes)
    h['axCode']=''.join(';'.join(cx[n])+';' for n in sorted(cx))+';'.join(acodes)
    h['axFunction']=''
    p=[(k,v) for k,v in h.items()]+[('functiontype','')]
    p+=[('LBDate',x) for x in dates]+[('chkBox',x) for x in acodes]
    for n in sorted(cx): p+=[(f'LBComplex{n}',x) for x in cx[n]]
    p.append(('goon','查詢'))
    r=s.post(SHOW,data=p,headers={'Referer':varval_url},timeout=180)
    dd=LH.fromstring(r.text)
    tbs=[t for t in dd.xpath('//table') if len(t.xpath('.//tr'))>2]
    if not tbs: return None
    return [[' '.join(c.text_content().split()) for c in tr.xpath('./td|./th')] for tr in tbs[0].xpath('.//tr')]

if __name__=='__main__':
    rows=fetch(sys.argv[1])
    for r in rows: print('\t'.join(r))
