#!/usr/bin/env python3
"""
Antigravity IDE 中文汉化补丁脚本。

同时修改三个关键文件：
  - jetskiAgent/main.js               → Settings 面板
  - out/media/chat.js                → Agent 聊天面板
  - workbench.desktop.main.js        → 快速设置面板
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

# 添加共享工具路径
sys.path.append(str(Path(__file__).resolve().parents[2] / "shared"))
from patch_utils import init_terminal, print_status, print_step

# 初始化终端环境
init_terminal()

REPO_ROOT = Path(__file__).resolve().parents[3]
TRANSLATIONS_DIR = REPO_ROOT / "translations" / "patches" / "ide" / "antigravity"

local_app_data = os.environ.get("LOCALAPPDATA")
if not local_app_data:
    print_status("❌", "无法获取 LOCALAPPDATA 环境变量，请确保在 Windows 环境下运行该脚本。")
    sys.exit(1)

BASE = Path(local_app_data) / "Programs" / "Antigravity" / "resources" / "app"
TARGETS = {
    "settings": BASE / "out" / "jetskiAgent" / "main.js",
    "chat": BASE / "extensions" / "antigravity" / "out" / "media" / "chat.js",
    "workbench": BASE / "out" / "vs" / "workbench" / "workbench.desktop.main.js",
}
PRODUCT_JSON = BASE / "product.json"


def load_replacements(name: str) -> list[tuple[str, str]]:
    filepath = TRANSLATIONS_DIR / f"{name}.replacements.json"
    with filepath.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, list) or any(
        not isinstance(pair, list) or len(pair) != 2 or any(not isinstance(item, str) for item in pair)
        for pair in data
    ):
        raise ValueError(f"替换表格式无效: {filepath}")

    return [tuple(pair) for pair in data]


def patch_file(filepath: Path, replacements: list[tuple[str, str]], name: str) -> int:
    backup = filepath.with_name(filepath.name + ".bak")

    if not filepath.exists() and not backup.exists():
        print_status("❌", f"文件不存在且无备份: {filepath}")
        return 0

    if not backup.exists():
        shutil.copy2(filepath, backup)
        print_status("✅", f"已备份英文原始文件: {backup.name}")
    else:
        shutil.copy2(backup, filepath)
        print_status("♻️", f"已从备份恢复英文原始文件，准备直接更新: {filepath.name}")

    content = filepath.read_text(encoding="utf-8", errors="replace")
    count = 0
    failed: list[str] = []

    for old, new in replacements:
        if old in content:
            content = content.replace(old, new)
            count += 1
        else:
            failed.append(old[:50])

    filepath.write_text(content, encoding="utf-8")

    print_status("🎉", f"{name}: 成功替换 {count}/{len(replacements)} 处")
    if failed:
        print_status("⚠️", f"未匹配 {len(failed)} 处:")
        for failed_snippet in failed:
            print(f"    - {failed_snippet}...")
    return count


def update_checksums() -> None:
    if not PRODUCT_JSON.exists():
        print_status("⚠️", "product.json 不存在，跳过 checksum 更新")
        return

    backup = PRODUCT_JSON.with_name(PRODUCT_JSON.name + ".bak")
    if not backup.exists():
        shutil.copy2(PRODUCT_JSON, backup)

    product = json.loads(PRODUCT_JSON.read_text(encoding="utf-8"))
    checksums = product.get("checksums", {})
    updated = 0

    for key in checksums:
        for prefix in (BASE / "out", BASE):
            filepath = prefix / key.replace("/", "\\")
            if filepath.exists():
                new_hash = base64.b64encode(hashlib.sha256(filepath.read_bytes()).digest()).decode("ascii").rstrip("=")
                if new_hash != checksums[key]:
                    checksums[key] = new_hash
                    updated += 1
                break

    if updated > 0:
        product["checksums"] = checksums
        PRODUCT_JSON.write_text(json.dumps(product, indent="\t", ensure_ascii=False), encoding="utf-8")
        print_status("✅", f"已更新 {updated} 个文件校验值")
    else:
        print_status("⏭️", "校验值无需更新")


def apply_patch() -> None:
    total = 0

    print_step(1, 4, "汉化 Settings 面板 (jetskiAgent/main.js)...")
    total += patch_file(TARGETS["settings"], load_replacements("main"), "Settings")

    print()
    print_step(2, 4, "汉化 Agent 聊天面板 (chat.js)...")
    total += patch_file(TARGETS["chat"], load_replacements("chat"), "Chat")

    print()
    print_step(3, 4, "汉化快速设置面板 (workbench.desktop.main.js)...")
    total += patch_file(TARGETS["workbench"], load_replacements("workbench"), "Workbench")

    print()
    print_step(4, 4, '更新文件校验值 (消除"安装损坏"提示)...')
    update_checksums()

    print_status("🎉", f"全部完成！共替换 {total} 处")
    print_status("📌", "请完全退出并重新启动 Antigravity 即可生效")


def revert_patch() -> None:
    for name, filepath in TARGETS.items():
        backup = filepath.with_name(filepath.name + ".bak")
        if backup.exists():
            shutil.copy2(backup, filepath)
            print_status("✅", f"已恢复: {name} ({filepath.name})")
        else:
            print_status("⏭️", f"无需恢复 (无备份): {name}")

    backup = PRODUCT_JSON.with_name(PRODUCT_JSON.name + ".bak")
    if backup.exists():
        shutil.copy2(backup, PRODUCT_JSON)
        print_status("✅", "已恢复: product.json")

    print_status("📌", "请完全退出并重新启动 Antigravity 即可生效")


def main() -> int:
    if "--revert" in sys.argv:
        revert_patch()
    else:
        apply_patch()
    return 0


if __name__ == "__main__":
    sys.exit(main())

