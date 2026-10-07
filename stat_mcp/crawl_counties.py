"""11 各縣市主計處資料庫查詢平台：依 資料庫/索引/縣市平台.json 抓各縣市目錄樹。

輸出：資料庫/11_各縣市主計處資料庫查詢平台/<縣市>/目錄.json＋目錄.md
  多個 CateNo（如彰化、雲林、花蓮依章節分 15～18 個）合併成一棵樹，最上層節點前加「[分類名]」。
逐縣市 checkpoint：已有 目錄.json 的縣市跳過（刪檔即重抓）。各站之間間隔數秒（部分站會擋連續請求）。
用法：python stat_mcp/crawl_counties.py [縣市名…]
"""
import io
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import dgbas_statfile_tree as tree  # noqa: E402

CONF = ROOT / "資料庫" / "索引" / "縣市平台.json"
OUT = ROOT / "資料庫" / "11_各縣市主計處資料庫查詢平台"


def crawl_by_org(base):
    """臺中版型：左側 TMenu 是「機關別／區公所」→ 機關頁 index.aspx?OrgNo= 列出該機關分類（statfile2 cateno）
    → 分類頁的統計表樹在 div#RTMenu（不是 TMenu）。"""
    import re
    from urllib.parse import urljoin

    import requests
    import urllib3
    from lxml import html as LH
    urllib3.disable_warnings()
    s = requests.Session()
    s.verify = False
    s.headers["User-Agent"] = "Mozilla/5.0"

    def get(u):
        for k in range(4):
            try:
                return LH.fromstring(s.get(u, timeout=90).text)
            except requests.RequestException:
                time.sleep(5 * (k + 1))
        raise RuntimeError(f"讀不到 {u}")

    root = get(base + "statfile2.aspx?Mode=3&CateNo=01")
    out = []
    for grp in root.xpath('//div[@id="TMenu"]/ul/li'):
        gname = (grp.text or "").strip() or "機關"
        orgs = []
        for a in grp.xpath('.//a[contains(@href,"OrgNo=")]'):
            org = {"name": a.text_content().strip(), "children": []}
            page = get(urljoin(base, a.get("href")))
            cats = {}
            for c in page.xpath("//a[@href]"):
                m = re.search(r"statfile2\.aspx\?mode=3&cateno=(\d+)", c.get("href"), re.I)
                if m:
                    cats.setdefault(m.group(1), c.text_content().strip())
            for no, cname in cats.items():
                cp = get(f"{base}statfile2.aspx?mode=3&cateno={no}")
                ul = cp.xpath('//div[@id="RTMenu"]/ul') or cp.xpath('//div[@id="RTMenu"]//ul')
                kids = tree.walk(ul[0], base) if ul else []
                if kids:
                    org["children"].append({"name": f"{cname}（cateno={no}）", "children": kids})
                time.sleep(1)
            if org["children"]:
                orgs.append(org)
            print(f"  {gname} {org['name']}：分類 {len(cats)}、項目 {tree.count_leaves(org['children'])}", flush=True)
            time.sleep(1)
        out.append({"name": gname, "children": orgs})
    return out


def crawl(only=()):
    conf = json.loads(CONF.read_text(encoding="utf-8"))["縣市"]
    summary = {}
    for county, c in conf.items():
        if only and county not in only:
            continue
        d = OUT / county
        if c.get("no_db"):
            summary[county] = "平台無資料庫內容，略過（只登記公務統計報表）"
            continue
        if (d / "目錄.json").exists():
            summary[county] = "已存在，略過"
            continue
        merged = []
        if c.get("mode") == "org":
            merged = crawl_by_org(c["base"])
        for no, name in ({} if c.get("mode") == "org" else c["catenos"]).items():
            for k in range(4):
                try:
                    t = tree.fetch_tree(c["base"], no)
                    break
                except Exception as e:  # noqa: BLE001
                    if k == 3:
                        raise
                    print(f"  {county} CateNo={no} 重試：{repr(e)[:80]}", flush=True)
                    time.sleep(5 * (k + 1))
            label = name if len(c["catenos"]) > 1 else ""
            for node in t:
                if label and not node["name"].startswith(label):
                    node["name"] = f"[{label}] {node['name']}" if node["name"] != label else node["name"]
                merged.append(node)
            time.sleep(2)
        d.mkdir(parents=True, exist_ok=True)
        (d / "目錄.json").write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
        (d / "目錄.md").write_text("\n".join(tree.to_md(merged, f"{county}主計處資料庫查詢平台 目錄（{c['base']}）")) + "\n", encoding="utf-8")
        summary[county] = f"大類 {len(merged)}、統計項目 {tree.count_leaves(merged)}"
        print(county, summary[county], flush=True)
        time.sleep(3)
    return summary


if __name__ == "__main__":
    print(crawl(sys.argv[1:]))  # stdout 已由 dgbas_statfile_tree 於 import 時設為 UTF-8，勿重設（會關閉底層緩衝）
