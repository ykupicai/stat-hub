# -*- coding: utf-8 -*-
"""臺南農再期中報告書：第三章第二節農業統計表更新至114年
   來源一律採 114年臺南市統計年報（臺南市政府農業局提供）；錨定索引＋內容比對，對不上即中止。"""
import sys, io, zipfile, os, json, copy
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from lxml import etree

W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
q=lambda t:'{%s}%s'%(W,t)
SRC="20260919_115年臺南市農村再生總體計畫（規劃階段）案-期中報告書-表3-1氣候更新至114年.docx"
OUT="20260919_115年臺南市農村再生總體計畫（規劃階段）案-期中報告書-表3-1氣候及農業統計更新至114年.docx"
D=json.load(open("new_tables.json",encoding="utf-8"))

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
def fill(tbl,start,data,label,grow=0):
    rs=tbl.findall(q('tr'))
    for _ in range(grow):
        new=copy.deepcopy(rs[-1]); tbl.append(new)
    rs=tbl.findall(q('tr'))
    assert len(rs)-start==len(data), '%s 列數不符 %d vs %d'%(label,len(rs)-start,len(data))
    for i,vals in enumerate(data):
        cs=rs[start+i].findall(q('tc'))
        assert len(cs)==len(vals), '%s 第%d列欄數不符 %d vs %d：%s'%(label,i,len(cs),len(vals),vals)
        for c,v in zip(cs,vals): set_cell(c,v)

P664=('依據114年臺南市統計年報，自民國104年至114年間，臺南市耕地面積由92,829.33公頃減少至90,015.37公頃，'
      '減少2,813.96公頃，減幅約3.03%，整體呈緩步下降趨勢。'
      '114年耕作地以長期耕作地30,464.54公頃及短期休閒29,065.49公頃為主要構成。')
P665=('114年臺南市耕地面積合計90,015.37公頃，其中耕作地84,992.61公頃，占94.42%，長期休閒地5,022.76公頃。'
      '行政區別以東山區6,361.40公頃最多，其次為白河區5,767.56公頃；'
      '長期休閒地則以玉井區1,090.89公頃為最大宗。')
P675=('臺南市水產養殖總面積由104年14,144.61公頃減少至114年10,956.91公頃，累計減少22.54%。'
      '其中海面養殖由1,912.80公頃減至1,516.65公頃，內陸養殖由12,231.81公頃減至9,440.26公頃，'
      '顯示近十年養殖面積整體呈縮減趨勢。')
P676=('114年水產養殖主要集中於沿海行政區，以七股區4,086.26公頃最多，其次為北門區、安南區及學甲區；'
      '前述四區合計占全市養殖面積約75.2%。七股、北門及安南以鹹水魚塭為主，學甲則以淡水魚塭為主，'
      '反映沿海環境、魚塭分布與內陸養殖條件的空間差異。')
P686=('依據114年臺南市統計年報，全市家畜飼養總數於104年至114年間由627,313頭增至657,156頭，增加約4.76%。'
      '114年豬隻611,248頭，占家畜總數約93.01%，顯示豬隻養殖仍為臺南市主要飼養類別。')
P687=('臺南市家禽總數由104年13,591千隻增加至114年16,686千隻，增幅約22.77%。'
      '114年雞隻16,176千隻，占家禽總數約96.94%；行政區別部分，113年家禽飼養以鹽水區2,084千隻、'
      '柳營區1,501千隻較為集中（114年各區資料因場數未滿3場而未完整揭露）。'
      '整體而言，臺南市家畜規模相對穩定，家禽飼養量則呈擴增趨勢。')
P717=('臺南市農田灌溉排水系統主要由農業部農田水利署嘉南管理處管理，灌溉設施包括埤、圳、幹支線渠道及排水系統。'
      '103年至112年間埤圳數維持34處埤及25條圳，113年起統計年報未再提供埤圳數統計；'
      '灌溉排水受益面積則呈緩步變化，反映既有農田水利系統持續支撐嘉南平原農業生產。')
P718=('103年臺南市灌溉排水受益地面積為46,164公頃，至114年為45,551公頃，減少613公頃，減幅約1.33%。'
      '其中灌溉受益面積由41,595公頃減至40,242公頃，排水受益面積則由4,569公頃增至5,309公頃，'
      '顯示灌溉面積略減，而排水服務範圍有所增加。')
P719=('實際耕種面積於103年至114年間呈現明顯年度波動，108年為71,817公頃，110年降至38,802公頃，'
      '114年為53,973公頃；若以108年至114年比較，減幅約24.85%。'
      '由於實際耕種面積可能受休耕制度、作物期作、調查時間及年度農業政策等因素影響，'
      '宜避免直接推論耕地長期閒置或農業衰退。')
S_41='資料來源：114年臺南市統計年報表4-1（臺南市政府農業局提供）；本計畫彙整'
S_412='資料來源：114年臺南市統計年報表4-12（臺南市政府農業局提供）；本計畫彙整'
S_311=('資料來源：114年臺南市統計年報表4-15、表4-18（臺南市政府農業局提供）；本計畫彙整。'
       '註：家畜合計為豬、羊、牛、鹿、馬之和，未計入兔；「牛」為牛隻總數（含乳牛）。')
S_312=('資料來源：113年臺南市統計年報；本計畫彙整。'
       '註：114年統計年報各行政區家畜、家禽數量因部分行政區場數未滿3場而以「*」遮蔽，'
       '無法完整呈現，爰維持113年資料。')
S_421=('資料來源：114年臺南市統計年報表4-21（臺南市政府農業局提供）；本計畫彙整。'
       '註：113年起年報未再提供埤圳數統計，以「…」表示；'
       '合計欄依年報口徑計入「農排下游具引灌需求」面積。')

def main():
    with zipfile.ZipFile(SRC) as z: xml=z.read('word/document.xml')
    root=etree.fromstring(xml); els=list(root.find(q('body')))
    def chk(i,exp):
        t=ptext(els[i]); assert exp in t,'索引 %d 內容不符：%s'%(i,t[:70])
    chk(664,'臺南市耕地面積由92,829.75公頃'); chk(665,'113年臺南市耕地面積合計90,220.82公頃')
    chk(667,'表3-7、臺南市歷年耕地土地面積統計表'); chk(669,'資料來源：農業部農糧署')
    chk(670,'表3-8、113年臺南市各區耕地面積統計表'); chk(672,'資料來源：113年臺南市統計年報')
    chk(675,'由104年14,144.61公頃減少至113年11,490.13公頃'); chk(676,'以七股區4,195.72公頃最多')
    chk(678,'表3-9、臺南市歷年水產養殖面積統計表'); chk(680,'資料來源：103年臺南市統計年報')
    chk(681,'表3-10、113年臺南市各區水產養殖面積統計表'); chk(683,'資料來源：113年臺南市統計年報')
    chk(686,'由約62.4萬頭增至63.5萬頭'); chk(687,'由104年13,591千隻增加至113年16,112千隻')
    chk(688,'表3-11、臺南市歷年家畜與家禽數量統計表'); chk(690,'資料來源：103年臺南市統計年報')
    chk(691,'表3-12、113年臺南市家畜與家禽數量統計表'); chk(693,'資料來源：113年臺南市統計年報')
    chk(717,'103年至112年間埤圳數維持34處埤及25條圳'); chk(718,'至112年為45,382公頃')
    chk(719,'112年回升至42,330公頃'); chk(720,'表3-17、臺南市灌溉排水受益地面積統計表')
    chk(722,'資料來源：112年臺南市統計年報')
    print('錨定比對全數通過')

    fill(els[668],3,D['T37'],'表3-7',grow=1)
    fill(els[671],3,D['T38'],'表3-8')
    fill(els[679],2,D['T39'],'表3-9',grow=1)
    fill(els[682],2,D['T310'],'表3-10')
    fill(els[689],2,D['T311'],'表3-11',grow=1)
    fill(els[721],3,D['T317'],'表3-17',grow=2)
    print('六張表格已填入')

    set_para(els[670],'表3-8、114年臺南市各區耕地面積統計表')
    set_para(els[681],'表3-10、114年臺南市各區水產養殖面積統計表')
    for i,t in ((664,P664),(665,P665),(675,P675),(676,P676),(686,P686),(687,P687),
                (717,P717),(718,P718),(719,P719),
                (669,S_41),(672,S_41),(680,S_412),(683,S_412),
                (690,S_311),(693,S_312),(722,S_421)):
        set_para(els[i],t)
    # 表目錄
    for idx,old,new in ((183,'113年臺南市各區水產養殖面積','114年臺南市各區水產養殖面積'),):
        pass
    print('段落與來源註已更新')

    newxml=etree.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
    with zipfile.ZipFile(SRC) as zin, zipfile.ZipFile(OUT,'w',zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data=zin.read(item.filename)
            if item.filename=='word/document.xml': data=newxml
            zi=zipfile.ZipInfo(item.filename,date_time=item.date_time)
            zi.compress_type=item.compress_type; zi.external_attr=item.external_attr
            zout.writestr(zi,data)
    print('已輸出：',OUT,os.path.getsize(OUT))
main()
