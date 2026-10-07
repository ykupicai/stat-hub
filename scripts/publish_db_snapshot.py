"""把本機 資料庫/stat.sqlite 發布成共用快照（給同事複製用）。

1. 用 SQLite backup API 產生一致快照（stat-hub 執行中也安全）＋ VACUUM ＋ integrity_check
2. 複製到 local_paths.json 的「資料庫快照」資料夾（公司 NAS，路徑不進版控），覆蓋 stat.sqlite
3. 逐 byte（SHA-256）核對，並改寫該資料夾 README.txt 的日期、雜湊與內容統計
用法：python scripts/publish_db_snapshot.py
"""
import hashlib
import io
import shutil
import sqlite3
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _local_paths import case_dir  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "資料庫" / "stat.sqlite"
NAMES = {"02": "農業部統計處", "03": "漁業署年報", "06b": "臺南市統計年報", "09": "普查動態查詢",
         "09t": "普查結果統計表", "10c": "屏東縣統計年報"}


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest().upper()


def main():
    dest_dir = case_dir("資料庫快照")
    tmp = Path(tempfile.gettempdir()) / f"stat_snapshot_{date.today():%Y%m%d}.sqlite"
    src, dst = sqlite3.connect(SRC), sqlite3.connect(tmp)
    src.backup(dst)
    dst.execute("VACUUM")
    ok = dst.execute("PRAGMA integrity_check").fetchone()[0]
    stats = dst.execute("""SELECT d.source, count(DISTINCT d.dataset_id),
                                  (SELECT count(*) FROM facts f WHERE f.source=d.source)
                           FROM datasets d GROUP BY d.source""").fetchall()
    has_docs = dst.execute("SELECT name FROM sqlite_master WHERE name='docs'").fetchone()
    ndocs = dst.execute("SELECT count(*) FROM docs").fetchone()[0] if has_docs else 0
    dst.close()
    src.close()
    if ok != "ok":
        raise SystemExit(f"快照完整性檢查失敗：{ok}")
    h = sha256(tmp)
    shutil.copyfile(tmp, dest_dir / "stat.sqlite")
    if sha256(dest_dir / "stat.sqlite") != h:
        raise SystemExit("NAS 檔案與快照雜湊不符，請重跑")
    lines = [f"- {NAMES.get(s, s)}（{s}）：{n} 個資料集、{f:,} 筆數值" for s, n, f in stats] + [f"- 文字全文：{ndocs:,} 份"]
    readme = (f"stat-hub 統計資料庫快照\n========================\n\n檔案：stat.sqlite（約 {tmp.stat().st_size / 2**20:,.0f} MB）\n"
              f"快照日期：{date.today():%Y-%m-%d}\nSHA-256：{h}\n程式：https://github.com/ykupicai/stat-hub（私人 repo，安裝見 INSTALL.md）\n\n"
              "怎麼用\n------\n1. 先照 INSTALL.md 安裝好 stat-hub。\n"
              "2. 把本資料夾的 stat.sqlite「複製」到自己電腦的  統計資料庫\\資料庫\\stat.sqlite\n"
              "   （若已有自己的 stat.sqlite 會被覆蓋——自己抓過、快照沒有的表會不見，需要時再抓一次即可）。\n"
              "3. 重開 Claude session。\n※ 請複製到本機使用，不要讓 stat-hub 直接讀寫 NAS 上這個檔（多人同時寫入會鎖檔或損壞）。\n\n"
              "快照內容（已入庫的數值，其餘表用到時會自動下載）\n------------------------------------------------\n"
              + "\n".join(lines) + "\n\n更新方式\n--------\n維護者在本機執行 python scripts/publish_db_snapshot.py。\n")
    (dest_dir / "README.txt").write_text(readme.replace("\n", "\r\n"), encoding="utf-8-sig")
    tmp.unlink()
    print(f"已發布：{dest_dir / 'stat.sqlite'}\nSHA-256：{h}\n" + "\n".join(lines))


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    main()
