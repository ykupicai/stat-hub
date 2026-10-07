# -*- coding: utf-8 -*-
"""嘉義農再：表2-13 更新至114年（特用作物列因製糖甘蔗未發布，仍為113年值）"""
import zipfile, os, shutil, datetime
from lxml import etree

from _local_paths import case_file  # 書件路徑讀本機 local_paths.json（不進版控）

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
q = lambda t: '{%s}%s' % (W, t)

DOC = case_file("嘉義農再書件", "20260917_修訂嘉義縣農村再生總體計畫(法定階段)_統計表更新至114年.docx")


def ptext(p):
    return ''.join(t.text or '' for t in p.iter(q('t')))


def set_para(p, text):
    runs = p.findall(q('r'))
    if not runs:
        raise RuntimeError('段落無 run：' + ptext(p)[:40])
    first = runs[0]
    ts = first.findall(q('t'))
    if not ts:
        ts = [etree.SubElement(first, q('t'))]
    ts[0].text = text
    ts[0].set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    for extra in ts[1:]:
        first.remove(extra)
    for r in runs[1:]:
        p.remove(r)


def set_cell(tc, text):
    ps = tc.findall(q('p'))
    for p in ps[1:]:
        tc.remove(p)
    p = ps[0]
    if not p.findall(q('r')):
        r = etree.SubElement(p, q('r'))
        etree.SubElement(r, q('t'))
    set_para(p, text)


# 表2-13：15 筆（5 類 × 前三名）。每列 5 格，第 1 格是「項目」(僅各類第一列有字)
T213 = [
    ['稻米', '第一名', '民雄鄉', '稉稻(蓬萊)', '27,763'],
    ['', '第二名', '新港鄉', '稉稻(蓬萊)', '23,272'],
    ['', '第三名', '溪口鄉', '稉稻(蓬萊)', '19,417'],
    ['雜糧', '第一名', '義竹鄉', '硬質玉米', '17,945'],
    ['', '第二名', '六腳鄉', '硬質玉米', '8,302'],
    ['', '第三名', '東石鄉', '硬質玉米', '3,945'],
    ['特用作物', '第一名', '太保市', '製糖甘蔗', '37,608'],
    ['', '第二名', '鹿草鄉', '製糖甘蔗', '28,655'],
    ['', '第三名', '義竹鄉', '製糖甘蔗', '25,614'],
    ['蔬菜', '第一名', '水上鄉', '甘藍', '7,296'],
    ['', '第二名', '六腳鄉', '甘藍', '6,983'],
    ['', '第三名', '番路鄉', '竹筍', '6,668'],
    ['果品', '第一名', '竹崎鄉', '柑橘類', '19,299'],
    ['', '第二名', '民雄鄉', '鳳梨', '18,408'],
    ['', '第三名', '大林鎮', '鳳梨', '10,521'],
]

P351 = ('依據農業部農糧署公布114年主要作物產量統計，民雄鄉與新港鄉為嘉義縣主要稻米生產區，'
        '而雜糧則主要集中於義竹鄉及六腳鄉等地區，特用作物以製糖甘蔗為生產大宗，主要生產區域為太保市，'
        '其因為原嘉義糖廠主要生產地區，蔬菜類亦以水上鄉、六腳鄉等地區，屬主要生產區域，'
        '至於果品類別，竹崎鄉以生產柑橘類產量居冠，'
        '可見嘉義縣各鄉鎮因其地理環境及過往農業投資等因素，呈現明顯區域農業分工之特性。')

SRC213 = ('資料來源：農業部農糧署農情報告資源網、嘉義縣政府農業處公務統計報表20321-02-01；本計畫彙整。'
          '註：特用作物（製糖甘蔗）由臺灣糖業股份有限公司提供，114年資料尚未發布，該項仍列113年數值。')


def main():
    with zipfile.ZipFile(DOC) as z:
        xml = z.read('word/document.xml')
    root = etree.fromstring(xml)
    els = list(root.find(q('body')))

    assert '表2-13、嘉義縣113年主要作物產量前三名一覽表' in ptext(els[352]), ptext(els[352])[:60]
    assert '依據農業部農糧署公布113年主要作物產量統計' in ptext(els[351]), ptext(els[351])[:60]
    assert '表2-13、嘉義縣113年' in ptext(els[137]), ptext(els[137])[:60]

    tbl = els[353]
    rs = tbl.findall(q('tr'))
    assert len(rs) - 1 == len(T213), '列數不符 %d' % len(rs)
    for i, vals in enumerate(T213):
        cs = rs[1 + i].findall(q('tc'))
        assert len(cs) == 5, '第%d列欄數 %d' % (i, len(cs))
        for c, v in zip(cs, vals):
            set_cell(c, v)

    set_para(els[352], '表2-13、嘉義縣114年主要作物產量前三名一覽表')
    set_para(els[354], SRC213)
    set_para(els[351], P351)

    done = False
    for t in els[137].iter(q('t')):
        if t.text and '113' in t.text:
            t.text = t.text.replace('113', '114', 1); done = True; break
    print('TOC[137]', done, ptext(els[137])[:40])

    newxml = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
    bak = DOC.replace('.docx', '_備份%s.docx' % datetime.datetime.now().strftime('%H%M%S'))
    shutil.copy2(DOC, bak)
    tmp = DOC + '.tmp'
    with zipfile.ZipFile(DOC) as zin, zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == 'word/document.xml':
                data = newxml
            zi = zipfile.ZipInfo(item.filename, date_time=item.date_time)
            zi.compress_type = item.compress_type
            zi.external_attr = item.external_attr
            zout.writestr(zi, data)
    os.replace(tmp, DOC)
    print('備份：', bak)
    print('已更新：', DOC, os.path.getsize(DOC))


if __name__ == '__main__':
    main()
