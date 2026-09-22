# -*- coding: utf-8 -*-
"""臺南市統計年報 ODS 讀取器：展開 repeated cell，回傳純文字二維陣列"""
from odf.opendocument import load
from odf.table import Table, TableRow, TableCell
from odf.text import P

_CACHE = {}

def sheet_rows(path, name, maxrep=60):
    key=(path,name)
    if key in _CACHE: return _CACHE[key]
    doc = _CACHE.get(('_doc',path))
    if doc is None:
        doc = load(path); _CACHE[('_doc',path)] = doc
    for t in doc.spreadsheet.getElementsByType(Table):
        if t.getAttribute('name') != name:
            continue
        out = []
        for r in t.getElementsByType(TableRow):
            rrep = int(r.getAttribute('numberrowsrepeated') or 1)
            cells = []
            for c in r.getElementsByType(TableCell):
                crep = int(c.getAttribute('numbercolumnsrepeated') or 1)
                txt = ' '.join(str(p) for p in c.getElementsByType(P)).strip()
                cells.extend([txt] * min(crep, maxrep))
            while cells and cells[-1] == '':
                cells.pop()
            for _ in range(min(rrep, 5)):
                out.append(cells)
        _CACHE[key]=out
        return out
    raise KeyError(name)
