# -*- coding: utf-8 -*-
"""臺南農再期中報告書：表4-16 農村社區土地重劃一覽表，換為臺南市資料
   來源：內政部地政司「農村社區土地重劃建設地區一覽表」（編號25094）"""
import sys, io, zipfile, os, csv, copy
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from lxml import etree

W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
q=lambda t:'{%s}%s'%(W,t)
SRC="20260919_115年臺南市農村再生總體計畫（規劃階段）案-期中報告書-表3-1氣候及農業統計更新至114年.docx"
OUT="20260919_115年臺南市農村再生總體計畫（規劃階段）案-期中報告書-表3-1氣候_第三章農業統計_表4-16更新.docx"
CSV="rural_landreadj.csv"
# 原始資料罕用字轉碼遺失（顯示為「瓦?」），依官田區瓦磘里地名補正
FIX={'瓦?':'瓦磘'}

def ptext(p): return ''.join(t.text or '' for t in p.iter(q('t')))
def set_para(p,text):
    runs=p.findall(q('r'))
    if not runs: raise RuntimeError('段落無 run：'+ptext(p)[:40])
    first=runs[0]; ts=first.findall(q('t'))
    if not ts: ts=[etree.SubElement(first,q('t'))]
    ts[0].text=text; ts[0].set('{http://www.w3.org/XML/1998/namespace}space','preserve')
    for e in ts[1:]: first.remove(e)
    for r in runs[1:]: p.remove(r)
def set_cell(tc,text):
    ps=tc.findall(q('p'))
    for p in ps[1:]: tc.remove(p)
    p=ps[0]
    if not p.findall(q('r')):
        r=etree.SubElement(p,q('r')); etree.SubElement(r,q('t'))
    set_para(p,text)

rows=[r for r in csv.DictReader(io.open(CSV,encoding="utf-8-sig"))
      if '臺南' in r['City_or_County'] or '台南' in r['City_or_County']]
data=[]
for r in rows:
    name=FIX.get(r['Construction_Name'].strip(), r['Construction_Name'].strip())
    data.append([name+'社區', r['Township'].strip(), str(int(r['Fiscal_Year'])-1911), float(r['Area_ha'])])
data.sort(key=lambda x:(int(x[2]), x[1]))
total=round(sum(x[3] for x in data),2)
T416=[[a,b,c,f"{d:,.2f}"] for a,b,c,d in data]
assert len(T416)==8, '臺南筆數不符：%d'%len(T416)

from collections import Counter
cnt=Counter(x[1] for x in data)
multi='、'.join(f"{k}" for k,v in cnt.items() if v>1)
single='、'.join(f"{k}" for k,v in cnt.items() if v==1)
top=sorted(data,key=lambda x:-x[3])[:2]
P1252=(f"本市已辦理農村社區土地重劃者共計{len(data)}處，面積合計約{total:,.2f}公頃，"
       f"分別位於{multi}各2處，{single}各1處；"
       f"辦理年期自民國{data[0][2]}年至{data[-1][2]}年，"
       f"其中以{top[0][1]}{top[0][0]}{top[0][3]:,.2f}公頃面積最大，"
       f"其次為{top[1][1]}{top[1][0]}{top[1][3]:,.2f}公頃。")
SRCN=('資料來源：內政部地政司「農村社區土地重劃建設地區一覽表」（資料集編號25094）；本計畫彙整。'
      '註：官田區該重劃區名稱於原始資料因罕用字轉碼遺失（原檔顯示為「瓦?」），'
      '依官田區瓦磘里地名補正為「瓦磘」。')

def main():
    with zipfile.ZipFile(SRC) as z: xml=z.read('word/document.xml')
    root=etree.fromstring(xml); els=list(root.find(q('body')))
    def chk(i,exp):
        t=ptext(els[i]); assert exp in t,'索引 %d 內容不符：%s'%(i,t[:70])
    chk(246,'表4-16、臺南市農村社區土地重劃區位一覽表（需更換）')
    chk(1250,'三、農村社區土地重劃（需更換）')
    chk(1252,'本市已辦理農村社區土地重劃者共計有4處，面積合計約47.17公頃')
    chk(1253,'表4-16、臺南市農村社區土地重劃區位一覽表（需更換）')
    chk(1254,'好美社區')
    chk(1255,'資料來源：內政部地政司')
    print('錨定比對通過')

    tbl=els[1254]; rs=tbl.findall(q('tr'))
    assert len(rs)==6 and len(rs[5].findall(q('tc')))==2, '表4-16 結構與預期不符'
    tmpl=rs[1]                      # 以資料列為模板
    for _ in range(len(T416)-4):    # 原有 4 筆資料列，補到 8 筆
        tbl.insert(list(tbl).index(rs[5]), copy.deepcopy(tmpl))
    rs=tbl.findall(q('tr'))
    assert len(rs)==1+len(T416)+1, '列數不符：%d'%len(rs)
    for i,vals in enumerate(T416):
        cs=rs[1+i].findall(q('tc'))
        assert len(cs)==4, '第%d列欄數不符 %d'%(i,len(cs))
        for c,v in zip(cs,vals): set_cell(c,v)
    cs=rs[-1].findall(q('tc'))
    set_cell(cs[0],'合計'); set_cell(cs[1],f"{total:,.2f}")
    print(f'表4-16 已填入 {len(T416)} 筆，合計 {total:,.2f} 公頃')

    set_para(els[1250],'三、農村社區土地重劃')
    set_para(els[1252],P1252)
    set_para(els[1253],'表4-16、臺南市農村社區土地重劃區位一覽表')
    set_para(els[1255],SRCN)
    # 目錄：移除「（需更換）」
    done=False
    for t in els[246].iter(q('t')):
        if t.text and '（需更換）' in t.text:
            t.text=t.text.replace('（需更換）',''); done=True; break
    assert done, '目錄未替換'
    print('段落、標題、目錄已更新')

    newxml=etree.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
    with zipfile.ZipFile(SRC) as zin, zipfile.ZipFile(OUT,'w',zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data_=zin.read(item.filename)
            if item.filename=='word/document.xml': data_=newxml
            zi=zipfile.ZipInfo(item.filename,date_time=item.date_time)
            zi.compress_type=item.compress_type; zi.external_attr=item.external_attr
            zout.writestr(zi,data_)
    print('已輸出：',OUT,os.path.getsize(OUT))
main()
