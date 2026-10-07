"""本機路徑設定：案件書件放在內網 NAS 或個人目錄，路徑不進版控。

讀 repo 根目錄的 local_paths.json（已列入 .gitignore）；格式見 local_paths.example.json。
用法：
    from _local_paths import case_file
    DOC = case_file("嘉義農再書件", "20260917_…統計表更新至114年.docx")
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONF = ROOT / "local_paths.json"


def case_dir(key):
    if not CONF.exists():
        raise SystemExit(f"找不到 {CONF.name}：請複製 local_paths.example.json 為 local_paths.json 並填入本機路徑")
    paths = json.loads(CONF.read_text(encoding="utf-8"))
    if key not in paths:
        raise SystemExit(f"{CONF.name} 沒有「{key}」；可用：{list(paths)}")
    return Path(paths[key])


def case_file(key, name):
    return str(case_dir(key) / name)
