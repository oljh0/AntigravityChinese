#!/usr/bin/env python3
r"""
Gemini CLI 翻译补丁脚本。

按 antigravity 的方式，为 Gemini CLI 的不同模块应用专门的翻译补丁。
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# 添加 Repo 根目录到 sys.path 以加载共享工具
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from scripts.shared.patch_utils import load_replacements, patch_file, revert_file, init_terminal, print_status

TRANSLATIONS_DIR = REPO_ROOT / "translations" / "patches" / "cli" / "gemini"

# 尝试发现 gemini-cli 的安装路径
def find_gemini_cli_root() -> Path | None:
    candidates = [
        Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "nodejs" / "node_modules" / "@google" / "gemini-cli",
        Path(os.environ.get("APPDATA", "")) / "npm" / "node_modules" / "@google" / "gemini-cli",
    ]
    gemini_home = os.environ.get("GEMINI_CLI_HOME")
    if gemini_home:
        candidates.insert(0, Path(gemini_home))

    for c in candidates:
        if (c / "package.json").exists():
            return c
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="为 Gemini CLI 应用分模块中文翻译补丁。")
    parser.add_argument("--target", type=Path, help="Gemini CLI 根目录或 bundle/dist 目录路径；不传时尝试自动发现")
    parser.add_argument("--revert", action="store_true", help="从 .bak 备份恢复原文件")
    parser.add_argument("--dry-run", action="store_true", help="只检查并输出结果，不写入文件")
    return parser.parse_args()


def main() -> int:
    init_terminal()
    args = parse_args()
    
    root = args.target
    if root is None:
        root = find_gemini_cli_root()
        if root is None:
            print_status("❌", "未找到 Gemini CLI 安装目录，请使用 --target 指定")
            return 1
    
    # 定义需要打补丁的目录列表
    targets = []

    # v0.36+ 使用 bundle 目录；旧版使用 dist 目录
    bundle_dir = root / "bundle"
    dist_dir = root / "dist"
    if bundle_dir.exists():
        targets.append(bundle_dir)
    elif dist_dir.exists():
        targets.append(dist_dir)
    elif root.name in ("dist", "bundle"):
        targets.append(root)

    # 尝试寻找 gemini-cli-core（旧版结构）
    core_dist = root / "node_modules" / "@google" / "gemini-cli-core" / "dist"
    if core_dist.exists():
        targets.append(core_dist)

    if not targets:
        print_status("❌", f"找不到 bundle 或 dist 目录: {root}")
        return 1

    if args.revert:
        for t in targets:
            print_status("♻️", f"正在恢复备份: {t}")
            for filepath in t.rglob("*.js"):
                revert_file(filepath)
        print_status("✅", "恢复完成")
        return 0

    # 加载所有替换表
    common_repls = load_replacements(TRANSLATIONS_DIR / "common.replacements.json")
    main_repls = load_replacements(TRANSLATIONS_DIR / "main.replacements.json")
    ui_repls = load_replacements(TRANSLATIONS_DIR / "ui.replacements.json")
    qwen_repls = load_replacements(TRANSLATIONS_DIR / "qwen.replacements.json")
    
    # 合并所有替换表，并按长度降序排序以防嵌套替换问题
    all_repls = common_repls + main_repls + ui_repls + qwen_repls
    all_repls.sort(key=lambda item: (-len(item[0]), item[0]))

    # 子终端编码修复补丁：
    # 上游 systeminformation 模块已自带 _psToUTF8 编码设置，但 getShellConfiguration
    # 返回的 argsPrefix 没有注入编码设置，导致工具执行的子进程输出中文可能乱码。
    # 通过在 argsPrefix 中追加编码设置参数来修复。
    # 注意：v0.36+ bundle 使用双引号，旧版 dist 使用单引号，两种都需要覆盖。
    core_encoding_repls = [
        (
            'argsPrefix: ["-NoProfile", "-Command"],',
            'argsPrefix: ["-NoProfile", "-Command", "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; [Console]::InputEncoding = [System.Text.Encoding]::UTF8;"],',
        ),
        (
            "argsPrefix: ['-NoProfile', '-Command'],",
            "argsPrefix: ['-NoProfile', '-Command', '[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; [Console]::InputEncoding = [System.Text.Encoding]::UTF8;'],",
        ),
    ]

    total_applied = 0
    files_patched = 0

    # v0.36+ 合并了 gemini-cli-core 到 bundle，编码修复补丁始终注入
    if core_encoding_repls:
        all_repls = all_repls + core_encoding_repls
        all_repls.sort(key=lambda item: (-len(item[0]), item[0]))

    for t in targets:
        print_status("🎯", f"目标目录: {t}")
        current_repls = all_repls

        print_status("📚", f"加载替换项总数: {len(current_repls)}")
        
        for filepath in t.rglob("*.js"):
            if filepath.name.endswith(".test.js") or filepath.name.endswith(".map"):
                continue
            
            applied, already = patch_file(filepath, current_repls, args.dry_run)
            if applied > 0:
                files_patched += 1
                total_applied += applied

    print_status("✅", f"成功替换: {total_applied} 处 (涉及 {files_patched} 个文件)")
    
    if args.dry_run:
        print_status("⏳", "dry-run 模式：未写入任何文件")
    else:
        print_status("🎉", "翻译补丁已应用")
        
    return 0


if __name__ == "__main__":
    sys.exit(main())
