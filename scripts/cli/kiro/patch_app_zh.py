#!/usr/bin/env python3
r"""
Kiro CLI kiro-cli.exe 中文翻译补丁脚本。

kiro-cli.exe 是 Bun standalone 可执行文件（bun build --compile），
JS 模块以混合格式（源码 + Bun 字节码）嵌入 PE .rdata 节区，
字符串字面量以 UTF-8 明文存储，
可直接对二进制做等长字节替换（len(old_utf8) == len(new_utf8)）。

注意：由于 Bun bytecode 无法反编译，不支持提取 JS 后重打包或用 Node.js 运行。

默认目标文件：
  C:\Program Files\Kiro-Cli\kiro-cli.exe
  或由 KIRO_CLI_HOME 环境变量指定安装目录。
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from scripts.shared.patch_utils import load_replacements, init_terminal, print_status

TRANSLATIONS_DIR = REPO_ROOT / "translations" / "patches" / "cli" / "kiro"

DEFAULT_KIRO_HOME = Path(
    os.environ.get("KIRO_CLI_HOME", r"C:\Program Files\Kiro-Cli")
)
DEFAULT_TARGET = DEFAULT_KIRO_HOME / "kiro-cli.exe"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="为 Kiro CLI kiro-cli.exe 应用中文翻译补丁（二进制等长替换）。")
    parser.add_argument("--target", type=Path, help="kiro-cli.exe 路径；不传时使用默认路径或 KIRO_CLI_HOME")
    parser.add_argument("--revert", action="store_true", help="从 .bak 备份恢复原文件")
    parser.add_argument("--dry-run", action="store_true", help="只检查并输出结果，不写入文件")
    return parser.parse_args()


def patch_exe(target: Path, replacements: list[tuple[str, str]], dry_run: bool) -> int:
    if not target.exists():
        print_status("❌", f"目标文件不存在: {target}")
        return 1

    bak = target.with_suffix(target.suffix + ".bak")
    source = bak if bak.exists() else target

    print_status("📌", f"读取源文件: {source.name} ({source.stat().st_size // 1024 // 1024} MB)")
    data = source.read_bytes()
    updated = data

    applied = already = missing = skipped = 0

    for old, new in replacements:
        old_b = old.encode("utf-8")
        new_b = new.encode("utf-8")

        if len(old_b) != len(new_b):
            skipped += 1
            continue

        if old_b in updated:
            updated = updated.replace(old_b, new_b)
            applied += 1
        elif new_b in updated:
            already += 1
        else:
            missing += 1

    print_status("✅", f"成功替换: {applied}/{len(replacements)}")
    if already:
        print_status("⏭️", f"已存在目标翻译: {already}")
    if skipped:
        print_status("⚠️", f"跳过（字节不等长）: {skipped}")
    if missing:
        print_status("⚠️", f"未匹配到原片段: {missing}")

    if dry_run:
        print_status("⏳", "dry-run 模式：未写入任何文件")
        return 0

    if not bak.exists():
        shutil.copy2(target, bak)
        print_status("✅", f"已备份原始文件: {bak.name}")
    else:
        print_status("📌", f"检测到备份文件: {bak.name}")

    target.write_bytes(updated)
    print_status("🎉", "翻译补丁已写入")
    return 0


def revert_exe(target: Path) -> int:
    bak = target.with_suffix(target.suffix + ".bak")
    if not bak.exists():
        print_status("⏭️", f"无可恢复备份: {bak}")
        return 1
    shutil.copy2(bak, target)
    print_status("♻️", f"已恢复原文件: {target.name}")
    return 0


def main() -> int:
    init_terminal()
    args = parse_args()

    target = (args.target or DEFAULT_TARGET).expanduser().resolve()
    print_status("📌", f"目标文件: {target}")

    if args.revert:
        return revert_exe(target)

    # 加载并合并三个翻译词条文件
    replacements = (
        load_replacements(TRANSLATIONS_DIR / "common.replacements.json")
        + load_replacements(TRANSLATIONS_DIR / "main.replacements.json")
        + load_replacements(TRANSLATIONS_DIR / "ui.replacements.json")
    )
    # 按字节长度降序排序，避免短词条误伤长词条
    replacements.sort(key=lambda p: -len(p[0].encode("utf-8")))

    print_status("📌", f"加载替换项总数: {len(replacements)}")
    return patch_exe(target, replacements, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
