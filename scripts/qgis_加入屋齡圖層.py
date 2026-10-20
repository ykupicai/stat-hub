# -*- coding: utf-8 -*-
"""在「目前開著的」QGIS 專案加入屋齡圖層（在 QGIS 的 Python 主控台執行，不會讀寫 qgz 檔，加完請自行 Ctrl+S 存檔）。

加入下列群組（已存在則略過，可重複執行）：
  1. 建物屋齡（地政局 BuildStat_Fage，2026 基準）：地號面（7 級）＋行政區外框與標註
  2. 成交時屋齡平均（實價登錄 105～114 年）：行政區分層設色（分位數 5 級）
用法（QGIS → 外掛程式 → Python 主控台）：
  exec(open(r"C:\\Users\\USER\\OneDrive\\文件\\project\\STATHUB\\scripts\\qgis_加入屋齡圖層.py", encoding="utf-8").read())
"""
import json

from qgis.core import (QgsFillSymbol, QgsGraduatedSymbolRenderer, QgsPalLayerSettings, QgsProject, QgsRendererRange, QgsTextBufferSettings,
                       QgsTextFormat, QgsVectorLayer, QgsVectorLayerSimpleLabeling)
from qgis.PyQt.QtGui import QColor, QFont

_BASE = r"C:\Users\USER\OneDrive\文件\project\STATHUB\案件\臺北市_不動產交易分析\行政區屋齡"
_S1 = _BASE + r"\現況_地政局圖層"
_S2 = _BASE + r"\成交時屋齡"


def _labels(lyr, expr):
    ls = QgsPalLayerSettings()
    ls.fieldName, ls.isExpression = expr, True
    tf = QgsTextFormat(); tf.setFont(QFont("Microsoft JhengHei")); tf.setSize(10)
    buf = QgsTextBufferSettings(); buf.setEnabled(True); buf.setSize(1.0); buf.setColor(QColor("white")); tf.setBuffer(buf)
    ls.setFormat(tf); ls.placement = QgsPalLayerSettings.OverPoint
    lyr.setLabeling(QgsVectorLayerSimpleLabeling(ls)); lyr.setLabelsEnabled(True)


def _add_group(p, name):
    root = p.layerTreeRoot()
    if root.findGroup(name):
        print("已存在，略過：", name)
        return None
    idx = 0
    for i, ch in enumerate(root.children()):
        if ch.name().startswith("行政區界"):
            idx = i + 1
            break
    return root.insertGroup(idx, name)


def _graduated(field, bins):
    rs = []
    for i, (lo, hi, lab, col) in enumerate(bins):
        sym = QgsFillSymbol.createSimple({"color": col, "outline_style": "no"})
        rs.append(QgsRendererRange(lo, hi, sym, lab))
    return QgsGraduatedSymbolRenderer(field, rs)


def add_all():
    p = QgsProject.instance()
    crs = p.crs()
    # 1. 建物屋齡
    g = _add_group(p, "建物屋齡（地政局 BuildStat_Fage，2026 基準）")
    if g is not None:
        parcel = QgsVectorLayer(_S1 + r"\臺北市地號_建物屋齡.shp|option:ENCODING=UTF-8", "建物屋齡－地號（地號上建物屋齡平均）", "ogr")
        dist = QgsVectorLayer(_S1 + r"\臺北市行政區_現況屋齡.shp|option:ENCODING=UTF-8", "建物屋齡－行政區（中位數標註）", "ogr")
        bins = [(-0.5, 10.5, "0～10 年", "#053061"), (10.5, 20.5, "11～20 年", "#2166ac"), (20.5, 30.5, "21～30 年", "#67a9cf"),
                (30.5, 40.5, "31～40 年", "#d1e5f0"), (40.5, 50.5, "41～50 年", "#fddbc7"), (50.5, 60.5, "51～60 年", "#ef8a62"), (60.5, 999, "61 年以上", "#b2182b")]
        parcel.setRenderer(_graduated("AGE_AVG", bins))
        dist.renderer().setSymbol(QgsFillSymbol.createSimple({"style": "no", "outline_color": "#333333", "outline_width": "0.5"}))
        _labels(dist, "\"TOWNNAME\" || '\n' || to_string(round(\"AGE_MED\",0)) || '年'")
        for l in (parcel, dist):
            l.setCrs(crs)
            p.addMapLayer(l, False)
        g.addLayer(dist); g.addLayer(parcel)
        print("已加入：建物屋齡（地號 %d、行政區 %d）" % (parcel.featureCount(), dist.featureCount()))
    # 0. 成交時屋齡兩個群組改用 105～114 全年資料的新 shp：舊群組先移除，再由下面重建
    for nm in ("成交時屋齡中位數（實價登錄 105/10～114/12）", "成交時屋齡中位數（實價登錄 105～114 年）", "成交時屋齡三級距（實價登錄，31 年以上占比）"):
        og = p.layerTreeRoot().findGroup(nm)
        if og is not None:
            for ly in og.findLayers():
                p.removeMapLayer(ly.layerId())
            og.parent().removeChildNode(og)
            print("已移除舊群組：", nm)
    # 2. 成交時屋齡平均
    # 2. 成交時屋齡中位數（原「平均」版已改為中位數；若專案內有舊的「成交時屋齡平均」群組會先移除）
    old = p.layerTreeRoot().findGroup("成交時屋齡平均（實價登錄 105～114 年）")
    if old is not None:
        for ly in old.findLayers():
            p.removeMapLayer(ly.layerId())
        old.parent().removeChildNode(old)
        print("已移除舊的「成交時屋齡平均」群組")
    g = _add_group(p, "成交時屋齡中位數（實價登錄 105～114 年）")
    if g is not None:
        lyr = QgsVectorLayer(_S2 + r"\臺北市行政區_成交時屋齡_全年.shp|option:ENCODING=UTF-8", "成交時屋齡中位數－行政區（分層設色）", "ogr")
        vals = sorted(f["AGE_MED"] for f in lyr.getFeatures())
        def q2(pp):  # 線性內插分位數，與 numpy.quantile 預設一致
            k = (len(vals) - 1) * pp
            lo_ = int(k)
            return vals[lo_] + (vals[min(lo_ + 1, len(vals) - 1)] - vals[lo_]) * (k - lo_)
        edges = [q2(0.2), q2(0.4), q2(0.6), q2(0.8)]
        lows = [vals[0]] + edges
        highs = edges + [vals[-1]]
        cols = ["#FFFFB2", "#FECC5C", "#FD8D3C", "#F03B20", "#BD0026"]
        rs = []
        for i in range(5):
            n = sum(1 for v in vals if (v > lows[i] if i else v >= lows[i]) and v <= highs[i])
            sym = QgsFillSymbol.createSimple({"color": cols[i], "outline_color": "#555555", "outline_width": "0.4"})
            rs.append(QgsRendererRange(lows[i] - (0.0001 if i == 0 else 0.0), highs[i] + (0.0001 if i == 4 else 0.0), sym, "%.1f～%.1f 年（%d 區）" % (lows[i], highs[i], n)))
        lyr.setRenderer(QgsGraduatedSymbolRenderer("AGE_MED", rs))
        _labels(lyr, "\"TOWNNAME\" || '\n' || to_string(round(\"AGE_MED\",0)) || '年'")
        lyr.setCrs(crs)
        p.addMapLayer(lyr, False)
        g.addLayer(lyr)
        print("已加入：成交時屋齡中位數（%d 區）" % lyr.featureCount())
    # 3. 成交時屋齡三級距（以 31 年以上占比分層設色；shp 另含 20 年以下、21-30 年的筆數與占比欄位）
    g = _add_group(p, "成交時屋齡三級距（實價登錄，31 年以上占比）")
    if g is not None:
        lyr = QgsVectorLayer(_S2 + r"\臺北市行政區_成交時屋齡三級距_全年.shp|option:ENCODING=UTF-8", "成交屋齡 31 年以上占比－行政區（分層設色）", "ogr")
        vals = sorted(f["P_31U"] for f in lyr.getFeatures())
        def q(pp):  # 線性內插分位數，與 numpy.quantile 預設一致
            k = (len(vals) - 1) * pp
            lo_ = int(k)
            return vals[lo_] + (vals[min(lo_ + 1, len(vals) - 1)] - vals[lo_]) * (k - lo_)
        edges = [q(0.2), q(0.4), q(0.6), q(0.8)]
        lows = [vals[0]] + edges
        highs = edges + [vals[-1]]
        cols = ["#FFFFB2", "#FECC5C", "#FD8D3C", "#F03B20", "#BD0026"]
        rs = []
        for i in range(5):
            n = sum(1 for v in vals if (v > lows[i] if i else v >= lows[i]) and v <= highs[i])
            sym = QgsFillSymbol.createSimple({"color": cols[i], "outline_color": "#555555", "outline_width": "0.4"})
            rs.append(QgsRendererRange(lows[i] - (0.0001 if i == 0 else 0.0), highs[i] + (0.0001 if i == 4 else 0.0), sym, "%.1f～%.1f%%（%d 區）" % (lows[i], highs[i], n)))
        lyr.setRenderer(QgsGraduatedSymbolRenderer("P_31U", rs))
        _labels(lyr, "\"TOWNNAME\" || '\n' || to_string(round(\"P_31U\",1)) || '%'")
        lyr.setCrs(crs)
        p.addMapLayer(lyr, False)
        g.addLayer(lyr)
        print("已加入：成交屋齡 31 年以上占比（%d 區）" % lyr.featureCount())
    # 4. 分區塊容積使用率（去重後推算地上樓地板 ÷ 法定總樓地板；無法定值者灰色）
    from qgis.core import QgsRuleBasedRenderer, QgsSymbol
    g = _add_group(p, "分區塊容積使用率（去重後推算地上）")
    if g is not None:
        lyr = QgsVectorLayer(r"C:\Users\USER\OneDrive\文件\project\STATHUB\案件\臺北市_不動產交易分析\分區容積使用\去重版\分區塊_容積使用狀況_去重.shp|option:ENCODING=UTF-8",
                             "分區塊容積使用率（去重後推算地上）", "ogr")
        specs = [('"USE_UP" IS NULL', "無法定容積率", "#DDDDDD"), ('"USE_UP" <= 50', "50% 以下", "#FFFFCC"), ('"USE_UP" > 50 AND "USE_UP" <= 100', "50～100%", "#FED976"),
                 ('"USE_UP" > 100 AND "USE_UP" <= 150', "100～150%", "#FD8D3C"), ('"USE_UP" > 150 AND "USE_UP" <= 250', "150～250%", "#E31A1C"), ('"USE_UP" > 250', "250% 以上", "#800026")]
        root_rule = QgsRuleBasedRenderer.Rule(None)
        for expr, lab, col in specs:
            sym = QgsFillSymbol.createSimple({"color": col, "outline_style": "no"})
            root_rule.appendChild(QgsRuleBasedRenderer.Rule(sym, 0, 0, expr, lab))
        lyr.setRenderer(QgsRuleBasedRenderer(root_rule))
        lyr.setCrs(crs)
        p.addMapLayer(lyr, False)
        g.addLayer(lyr)
        print("已加入：分區塊容積使用率（%d 塊）" % lyr.featureCount())
    # 5. 中山區公有地分布（依權屬分類：全部公有／公私共有／非公有／無資料）
    from qgis.core import QgsCategorizedSymbolRenderer, QgsRendererCategory
    g = _add_group(p, "中山區公有地分布（依權屬分類）")
    if g is not None:
        lyr = QgsVectorLayer(r"C:\Users\USER\OneDrive\文件\project\STATHUB\案件\臺北市_不動產交易分析\中山區_權屬\中山區_交易土地權屬.shp|option:ENCODING=UTF-8", "中山區交易地號－公有地權屬", "ogr")
        cats = [("全部公有", "全部公有", "#08519C"), ("公私共有（公有持分未滿 100%）", "公私共有（公有持分未滿 100%）", "#FD8D3C"),
                ("非公有（API 無公有所有權人）", "非公有（由空值推定）", "#D9D9D9"), ("無資料", "無資料", "#FFFFFF")]
        rcs = []
        for val, lab, col in cats:
            rcs.append(QgsRendererCategory(val, QgsFillSymbol.createSimple({"color": col, "outline_color": "#999999", "outline_width": "0.1"}), lab))
        lyr.setRenderer(QgsCategorizedSymbolRenderer("PUB_CLS", rcs))
        lyr.setCrs(crs)
        p.addMapLayer(lyr, False)
        g.addLayer(lyr)
        print("已加入：中山區公有地分布（%d 個地號）" % lyr.featureCount())
    # 6. 行政區×使用分區 公有土地占比（都發局使用分區圖 × 地政局公有土地圖層；公有僅含全部公有地號）
    g = _add_group(p, "使用分區公有土地占比（行政區×使用分區）")
    if g is not None:
        lyr = QgsVectorLayer(r"C:\Users\USER\OneDrive\文件\project\STATHUB\案件\臺北市_不動產交易分析\使用分區公私有土地\行政區_使用分區_公有占比_持分加權.shp|option:ENCODING=UTF-8", "公有土地占比－行政區×使用分區（可依 ZONE_CLS 篩選）", "ogr")
        bins = [(-0.1, 10, "0～10%", "#FFFFB2"), (10, 25, "10～25%", "#FED976"), (25, 50, "25～50%", "#FD8D3C"), (50, 75, "50～75%", "#E31A1C"), (75, 100.1, "75～100%", "#800026")]
        lyr.setRenderer(_graduated("PUB_PCT", bins))
        lyr.setCrs(crs)
        p.addMapLayer(lyr, False)
        g.addLayer(lyr)
        print("已加入：行政區×使用分區公有占比（%d 塊）" % lyr.featureCount())
    # 7. 土地開發熱區（三類交易筆數，小段；105～114 年）：土地買賣、二手房屋、預售屋各一層，僅土地買賣預設顯示
    g = _add_group(p, "土地開發熱區（三類交易筆數，小段）")
    if g is not None:
        shp = r"C:\Users\USER\OneDrive\文件\project\STATHUB\案件\臺北市_不動產交易分析\土地開發熱區_三類\小段_三類交易筆數.shp|option:ENCODING=UTF-8"
        for fld, nm, cols, vis in (("N_LAND", "土地買賣", ["#F3F3F3", "#DCE9F5", "#A9C8E4", "#4C78A8", "#12385F"], True),
                                    ("N_USED", "二手房屋", ["#F3F3F3", "#FFFFB2", "#FECC5C", "#FD8D3C", "#E31A1C"], False),
                                    ("N_PRE", "預售屋", ["#F3F3F3", "#E5F2DC", "#B5DBA0", "#6BBF5E", "#1E6B2E"], False)):
            lyr = QgsVectorLayer(shp, "熱區－%s（小段交易筆數）" % nm, "ogr")
            vals = sorted(f[fld] for f in lyr.getFeatures() if f[fld] > 0)

            def qq(pp, vals=vals):
                k = (len(vals) - 1) * pp
                lo_ = int(k)
                return vals[lo_] + (vals[min(lo_ + 1, len(vals) - 1)] - vals[lo_]) * (k - lo_)
            e = [round(qq(0.5)), round(qq(0.8)), round(qq(0.95))]
            bins = [(-0.5, 0.5, "0 筆", cols[0]), (0.5, e[0], "1～%d 筆" % e[0], cols[1]), (e[0], e[1], "%d～%d 筆" % (e[0] + 1, e[1]), cols[2]),
                    (e[1], e[2], "%d～%d 筆" % (e[1] + 1, e[2]), cols[3]), (e[2], 1e9, "%d 筆以上" % (e[2] + 1), cols[4])]
            lyr.setRenderer(_graduated(fld, bins))
            lyr.setCrs(crs)
            p.addMapLayer(lyr, False)
            node = g.addLayer(lyr)
            node.setItemVisibilityChecked(vis)
        print("已加入：土地開發熱區三類（各 %d 個小段）" % lyr.featureCount())
    print("完成。請按 Ctrl+S 儲存專案。")


add_all()
