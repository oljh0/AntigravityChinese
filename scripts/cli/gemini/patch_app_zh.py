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
    parser.add_argument("--target", type=Path, help="Gemini CLI 根目录或 dist 目录路径；不传时尝试自动发现")
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
    
    dist_dir = root / "dist"
    if dist_dir.exists():
        targets.append(dist_dir)
    elif root.name == "dist":
        targets.append(root)
        dist_dir = root
    
    # 尝试寻找 gemini-cli-core
    core_dist = root / "node_modules" / "@google" / "gemini-cli-core" / "dist"
    if core_dist.exists():
        targets.append(core_dist)
        
    if not targets:
        print_status("❌", f"找不到任何 dist 目录: {dist_dir}")
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
    
    # 合并所有替换表，并按长度降序排序以防嵌套替换问题
    all_repls = common_repls + main_repls + ui_repls
    all_repls.sort(key=lambda item: (-len(item[0]), item[0]))

    # [已弃用] 子终端编码修复补丁 — 不再需要文件级硬替换。
    # 原因：
    #   - 补丁 #1~#3: 通过 PowerShell Profile 设置 `chcp 65001` + `$env:LANG='en_US.UTF-8'`
    #     即可让 systemEncoding.js 的探测链路自然返回 utf-8，无需替换源码。
    #   - 补丁 #4: 上游已原生实现 encodingCommand 变量 (shell-utils.js)，替换模式已失效。
    # 如需恢复，取消以下注释：
    core_encoding_repls = [
        # ("const encoding = getCachedEncodingForBuffer(data);", "const encoding = 'utf-8';"),
        # ("handleFlowControl: true,", "handleFlowControl: true, encoding: 'utf8',"),
        # ("TERM: 'xterm-256color',", "TERM: 'xterm-256color', LANG: 'en_US.UTF-8',"),
        # ("argsPrefix: ['-NoProfile', '-Command'],", "argsPrefix: ['-NoProfile', '-Command', '[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; [Console]::InputEncoding = [System.Text.Encoding]::UTF8;'],"),
    ]

    total_applied = 0
    files_patched = 0

    for t in targets:
        print_status("🎯", f"目标目录: {t}")
        
        # 如果是 core 目录，过去会注入编码修复补丁（已弃用，见 core_encoding_repls 注释）
        is_core = "gemini-cli-core" in str(t)
        current_repls = all_repls
        if is_core and core_encoding_repls:
            current_repls = all_repls + core_encoding_repls
            current_repls.sort(key=lambda item: (-len(item[0]), item[0]))
            print_status("🔧", "检测到 core 目录，已注入编码修复补丁")

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
