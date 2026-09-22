# -*- coding: utf-8 -*-
"""臺南農再期中報告書：表3-1／圖3-1／圖3-3 及氣候段落更新為近十年（2016-2025＝民國105-114年）
   自 NAS 原始底稿重跑；錨定索引＋內容比對，對不上即中止。"""
import sys, io, zipfile, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from lxml import etree

W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
q=lambda t:'{%s}%s'%(W,t)
SRC="期中報告書_工作副本.docx"
OUT="20260919_115年臺南市農村再生總體計畫（規劃階段）案-期中報告書-表3-1氣候更新至114年.docx"

def ptext(p): return ''.join(t.text or '' for t in p.iter(q('t')))

def set_para(p, text):
    runs=p.findall(q('r'))
    if not runs: raise RuntimeError('段落無 run：'+ptext(p)[:40])
    first=runs[0]; ts=first.findall(q('t'))
    if not ts: ts=[etree.SubElement(first,q('t'))]
    ts[0].text=text
    ts[0].set('{http://www.w3.org/XML/1998/namespace}space','preserve')
    for extra in ts[1:]: first.remove(extra)
    for r in runs[1:]: p.remove(r)

def set_cell(tc, text):
    ps=tc.findall(q('p'))
    for p in ps[1:]: tc.remove(p)
    p=ps[0]
    if not p.findall(q('r')):
        r=etree.SubElement(p,q('r')); etree.SubElement(r,q('t'))
    set_para(p,text)

def fill(tbl,start_row,data,label):
    rs=tbl.findall(q('tr'))
    assert len(rs)-start_row==len(data), '%s 列數不符 %d vs %d'%(label,len(rs)-start_row,len(data))
    for i,vals in enumerate(data):
        cs=rs[start_row+i].findall(q('tc'))
        assert len(cs)==len(vals), '%s 第%d列欄數不符 %d vs %d'%(label,i,len(cs),len(vals))
        for c,v in zip(cs,vals): set_cell(c,v)

# ---- 2016-2025（民國105-114年），CODiS 臺南站 467410，10 年完整無缺測 ----
T31=[
 ['最高溫度(°C)','23.1','23.9','26.5','29.3','31.3','32.6','33.0','32.3','32.6','31.0','28.3','24.4','29.0'],
 ['平均溫度(°C)','18.2','18.9','22.0','25.2','27.8','29.3','29.6','29.0','29.0','27.1','23.9','19.9','25.0'],
 ['最低溫度(°C)','15.1','15.6','18.5','22.3','25.2','26.8','26.9','26.6','26.5','24.4','21.1','17.0','22.2'],
 ['降水量(mm)','4.2','6.5','15.9','21.5','85.6','305.2','432.0','387.0','93.5','10.2','4.0','6.5','1864.9'],
]
P563=('依據交通部中央氣象署2016年至2025年統計資料，臺南平地年平均氣溫為25.0℃，'
      '月平均氣溫以7月29.6℃最高、1月18.2℃最低；全年平均最高溫度為29.0℃，平均最低溫度為22.2℃，'
      '顯示平地全年溫暖，夏季高溫特徵明顯。')
P564=('各月平均氣溫自春季逐步上升，6月至9月均達29℃以上，入秋後逐月下降。'
      '此一溫度條件使臺南市農業生產可涵蓋稻米、蔬菜、果品及雜糧等多元作物，'
      '但夏季高溫期間仍須留意作物熱害及農事作業風險。')
P566=('臺南市平地降雨主要集中於夏季，2016年至2025年全年降水量中位數為1,864.9毫米；'
      '5月至9月合計約1,303.3毫米，占全年降水量約69.9%，其中7月降水量432.0毫米最高；'
      '10月至翌年2月降雨較少，以11月4.0毫米最低。')
P577=('依據中央氣象署2016年至2025年統計資料顯示，臺南平地地區全年平均日照總時數為2,365小時，'
      '各月約介於178.6小時至214.8小時之間，以3月214.8小時最高、4月及6月208.6小時次之，'
      '8月178.6小時最低，整體日照條件充足。')
NOTE='註：溫度呈現平均值；降雨量呈現中位數'
SRCN='資料來源：交通部中央氣象署觀測資料查詢服務（CODiS）臺南站（467410）逐月觀測資料；本計畫統計。'

def main():
    with zipfile.ZipFile(SRC) as z: xml=z.read('word/document.xml')
    root=etree.fromstring(xml); body=root.find(q('body')); els=list(body)
    def chk(i,expect):
        t=ptext(els[i]); assert expect in t,'索引 %d 內容不符：%s'%(i,t[:80])
    chk(75,'圖3-1、1991年~2020年臺南平地溫度及降雨量月平均統計圖')
    chk(76,'圖3-3、1991年~2020年臺南平地平均日照時數統計圖')
    chk(176,'表3-1、1991年~2020年臺南平地溫度及降雨量月平均統計表')
    chk(563,'臺南平地年平均氣溫為24.6℃')
    chk(564,'6月至9月均高於28℃')
    chk(566,'全年降水量中位數為1,766.8毫米')
    chk(569,'表3-1、1991年~2020年臺南平地溫度及降雨量月平均統計表')
    chk(570,'最高溫度(°C)23.024.026.6')
    chk(571,'註：溫度呈現平均值；降雨量呈現中位數')
    chk(572,'資料來源：交通部中央氣象署')
    chk(574,'圖3-1、1991年~2020年')
    chk(577,'全年平均日照總時數為2,185小時')
    chk(578,'圖3-3、1991年~2020年')
    print('錨定比對全數通過')

    fill(els[570],1,T31,'表3-1')
    set_para(els[569],'表3-1、2016年~2025年臺南平地溫度及降雨量月平均統計表')
    set_para(els[571],NOTE); set_para(els[572],SRCN)
    set_para(els[563],P563); set_para(els[564],P564)
    set_para(els[566],P566); set_para(els[577],P577)

    n=0
    for idx in (75,76,176,574,578):
        for t in els[idx].iter(q('t')):
            if t.text and '1991' in t.text: t.text=t.text.replace('1991','2016'); n+=1
            if t.text and '~2020' in t.text: t.text=t.text.replace('~2020','~2025'); n+=1
    assert n==10, '年份替換處數不符：%d'%n
    print('年份字串替換：%d 處'%n)
    m=0
    for idx in (574,578):
        for t in els[idx].iter(q('t')):
            if t.text and t.text.strip()=='資料來源：交通部中央氣象署': t.text=SRCN; m+=1
    assert m==2, '圖說來源替換處數不符：%d'%m
    print('圖說來源替換：%d 處'%m)

    newxml=etree.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
    figs={"word/media/image10.png":open("new_fig3-1.png","rb").read(),
          "word/media/image11.png":open("new_fig3-3.png","rb").read()}
    hit=set()
    with zipfile.ZipFile(SRC) as zin, zipfile.ZipFile(OUT,'w',zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data=zin.read(item.filename)
            if item.filename=='word/document.xml': data=newxml
            elif item.filename in figs: data=figs[item.filename]; hit.add(item.filename)
            zi=zipfile.ZipInfo(item.filename,date_time=item.date_time)
            zi.compress_type=item.compress_type; zi.external_attr=item.external_attr
            zout.writestr(zi,data)
    assert hit==set(figs), '圖片未全部替換：%s'%(set(figs)-hit)
    print('圖片已替換：',sorted(hit))
    print('已輸出：',OUT,os.path.getsize(OUT))

main()
