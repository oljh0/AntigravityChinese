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

from scripts.shared.patch_utils import load_replacements, patch_file, revert_file

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
    parser.add_argument("--target", type=Path, help="Gemini CLI 根目录或 dist 目录路径；不传时尝试自动发现")
    parser.add_argument("--revert", action="store_true", help="从 .bak 备份恢复原文件")
    parser.add_argument("--dry-run", action="store_true", help="只检查并输出结果，不写入文件")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    
    root = args.target
    if root is None:
        root = find_gemini_cli_root()
        if root is None:
            print("  ❌ 未找到 Gemini CLI 安装目录，请使用 --target 指定")
            return 1
    
    dist_dir = root / "dist"
    if not dist_dir.exists():
        if root.name == "dist":
            dist_dir = root
        else:
            print(f"  ❌ 找不到 dist 目录: {dist_dir}")
            return 1

    if args.revert:
        print(f"  ⏪ 正在恢复备份: {dist_dir}")
        for filepath in dist_dir.rglob("*.js"):
            revert_file(filepath)
        print("  ✅ 恢复完成")
        return 0

    # 加载不同类型的替换表
    common_repls = load_replacements(TRANSLATIONS_DIR / "common.replacements.json")
    main_repls = load_replacements(TRANSLATIONS_DIR / "main.replacements.json")
    ui_repls = load_replacements(TRANSLATIONS_DIR / "ui.replacements.json")

    print(f"  🎯 目标目录: {dist_dir}")
    print(f"  📚 加载替换表: common({len(common_repls)}), main({len(main_repls)}), ui({len(ui_repls)})")
    
    total_applied = 0
    files_patched = 0

    for filepath in dist_dir.rglob("*.js"):
        if filepath.name.endswith(".test.js") or filepath.name.endswith(".map"):
            continue
            
        # 确定适用的替换表
        file_repls = list(common_repls)
        
        # 相对路径
        rel_path = filepath.relative_to(dist_dir).as_posix()
        
        # 特定文件匹配
        if rel_path == "src/gemini.js" or rel_path == "index.js":
            file_repls.extend(main_repls)
        
        # UI 目录匹配
        if "src/ui/" in rel_path:
            file_repls.extend(ui_repls)
            
        # 重新排序以防万一
        file_repls.sort(key=lambda item: (-len(item[0]), item[0]))

        applied, already = patch_file(filepath, file_repls, args.dry_run)
        if applied > 0:
            files_patched += 1
            total_applied += applied

    print(f"  ✅ 成功替换: {total_applied} 处 (涉及 {files_patched} 个文件)")
    
    if args.dry_run:
        print("  🧪 dry-run 模式：未写入任何文件")
    else:
        print("  🎉 翻译补丁已应用")
        
    return 0


if __name__ == "__main__":
    sys.exit(main())
