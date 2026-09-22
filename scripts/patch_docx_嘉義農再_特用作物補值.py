# -*- coding: utf-8 -*-
"""嘉義農再：表2-14、表2-15 的「特用作物」欄由「…」改填113年數值並改註"""
import zipfile, os, shutil, datetime
from lxml import etree

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
q = lambda t: '{%s}%s' % (W, t)

DOC = r"<個人案件目錄>\嘉義農再\03 計畫書件\20260917_修訂嘉義縣農村再生總體計畫(法定階段)_統計表更新至114年.docx"


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


def cell_text(tc):
    return ' '.join(''.join(tc.itertext()).split())


# 113 年特用作物（嘉義縣統計年報表4-4(2)）：面積(公頃), 產量(公噸)
SPECIAL = {
    '太保市': ('550', '37,704'), '朴子市': ('70', '5,080'), '布袋鎮': ('89', '7,514'),
    '大林鎮': ('111', '6,501'), '民雄鄉': ('39', '1,760'), '溪口鄉': ('28', '958'),
    '新港鄉': ('161', '10,083'), '六腳鄉': ('109', '12,471'), '東石鄉': ('18', '76'),
    '義竹鄉': ('286', '25,617'), '鹿草鄉': ('377', '28,851'), '水上鄉': ('133', '6,479'),
    '中埔鄉': ('132', '677'), '竹崎鄉': ('383', '495'), '梅山鄉': ('921', '1,127'),
    '番路鄉': ('291', '348'), '大埔鄉': ('16', '25'), '阿里山鄉': ('812', '949'),
    '合計': ('4,524', '146,715'),
}

NOTE = ('資料來源：農業部農糧署農情報告資源網、嘉義縣政府農業處公務統計報表20321-02-01；本計畫彙整。'
        '註：特用作物產量以製糖甘蔗為大宗，該項由臺灣糖業股份有限公司提供，114年資料尚未發布，'
        '爰特用作物欄仍列113年數值。')


def main():
    with zipfile.ZipFile(DOC) as z:
        xml = z.read('word/document.xml')
    root = etree.fromstring(xml)
    els = list(root.find(q('body')))

    assert '表2-14、104~114年' in ptext(els[358]), ptext(els[358])[:60]
    assert '表2-15、114年' in ptext(els[361]), ptext(els[361])[:60]

    # 表2-14：最後一列（114年）第 6、7 格
    rs = els[359].findall(q('tr'))
    last = rs[-1].findall(q('tc'))
    assert cell_text(last[0]) == '114', cell_text(last[0])
    if cell_text(last[5]) == '…':
        set_cell(last[5], SPECIAL['合計'][0])
        set_cell(last[6], SPECIAL['合計'][1])
        print('表2-14 已補值')
    else:
        assert (cell_text(last[5]), cell_text(last[6])) == SPECIAL['合計'],             '表2-14 特用作物欄已有其他值：' + cell_text(last[5]) + '/' + cell_text(last[6])
        print('表2-14 已是113年值，略過')

    # 表2-15：每個資料列第 6、7 格
    n = 0
    for tr in els[362].findall(q('tr'))[2:]:
        cs = tr.findall(q('tc'))
        town = cell_text(cs[0])
        assert town in SPECIAL, '未知列名：' + town
        assert cell_text(cs[5]) == '…' and cell_text(cs[6]) == '…', town + ' 特用作物欄非「…」'
        set_cell(cs[5], SPECIAL[town][0])
        set_cell(cs[6], SPECIAL[town][1])
        n += 1
    assert n == 19, n

    set_para(els[360], NOTE)
    set_para(els[363], NOTE)

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
