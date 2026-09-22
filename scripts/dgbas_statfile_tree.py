# -*- coding: utf-8 -*-
"""主計處「資料庫查詢平台」(statfile2.aspx) 目錄樹擷取器。

同一套系統的縣市皆適用（實測臺南 tainan.dgbas.gov.tw、嘉義 cyhg.dgbas.gov.tw）。
DOM 結構：div#TMenu > ul > li.isFolder(大類) > ul > li.isFolder(報表) > ul > li > a(統計項目)

用法：
    python dgbas_tree.py https://tainan.dgbas.gov.tw/DgbasWeb/ 28 目錄_統計年報
"""
import sys, io, json, requests, urllib3
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from lxml import html as LH
urllib3.disable_warnings()


def txt(el):
    t = (el.text or '').strip()
    if t:
        return ' '.join(t.split())
    return ' '.join(el.text_content().split())[:80]


def walk(ul, base):
    out = []
    for li in ul.xpath('./li'):
        subs = li.xpath('./ul')
        a = li.xpath('./a[contains(@href,"varval")]')
        if subs:
            out.append({"name": txt(li), "children": walk(subs[0], base)})
        elif a:
            out.append({"name": ' '.join(a[0].text_content().split()),
                        "url": base + a[0].get('href')})
    return out


def fetch_tree(base, cate_no):
    s = requests.Session(); s.verify = False
    s.headers['User-Agent'] = 'Mozilla/5.0'
    r = s.get(f"{base}statfile2.aspx?Mode=3&CateNo={cate_no}", timeout=120)
    r.raise_for_status()
    d = LH.fromstring(r.text)
    menu = d.xpath('//div[@id="TMenu"]/ul')
    if not menu:
        raise RuntimeError('找不到 div#TMenu > ul')
    return walk(menu[0], base)


def to_md(tree, title, depth=0, lines=None):
    if lines is None:
        lines = [f"# {title}", ""]
    for n in tree:
        if 'children' in n:
            lines.append(f"{'  ' * depth}- **{n['name']}**")
            to_md(n['children'], title, depth + 1, lines)
        else:
            lines.append(f"{'  ' * depth}- {n['name']}  `{n['url'].split('varval3.aspx?')[-1]}`")
    return lines


def count_leaves(tree):
    return sum(count_leaves(n['children']) if 'children' in n else 1 for n in tree)


if __name__ == '__main__':
    base, cate, stem = sys.argv[1], sys.argv[2], sys.argv[3]
    tree = fetch_tree(base, cate)
    json.dump(tree, io.open(stem + '.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    io.open(stem + '.md', 'w', encoding='utf-8').write('\n'.join(to_md(tree, stem)) + '\n')
    print(f"{stem}: 大類 {len(tree)} 個、統計項目 {count_leaves(tree)} 個")
