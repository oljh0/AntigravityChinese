#!/usr/bin/env python3
r"""
Qoder CLI 中文翻译补丁脚本（v2 — JS 文本替换模式）。

从 qodercli.exe 提取的 JS bundle 上做 UTF-8 文本替换，
无等长限制，翻译后通过 bun run 运行。

用法：
  python -m scripts.cli.qoder.patch_app_zh              # 自动提取 + 打补丁
  python -m scripts.cli.qoder.patch_app_zh --dry-run    # 只检查
  python -m scripts.cli.qoder.patch_app_zh --revert     # 恢复
  python -m scripts.cli.qoder.patch_app_zh --target DIR # 指定已提取的目录
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from scripts.shared.patch_utils import load_replacements, patch_file, revert_file, init_terminal, print_status
from scripts.cli.qoder.extract_bundle import discover_target, DEFAULT_OUTPUT

TRANSLATIONS_DIR = REPO_ROOT / "translations" / "patches" / "cli" / "qoder"


def discover_extracted(output_dir: Path = DEFAULT_OUTPUT) -> Path | None:
    """定位已提取的 JS bundle 目录。"""
    index_js = output_dir / "index.js"
    if index_js.exists():
        return output_dir
    return None


def ensure_extracted(output_dir: Path) -> Path:
    """确保 JS bundle 已提取，未提取则自动执行。"""
    existing = discover_extracted(output_dir)
    if existing:
        return existing

    print_status("📌", "未找到已提取的 JS bundle，正在自动提取...")
    from scripts.cli.qoder.extract_bundle import parse_pe_sections, find_bun_section, extract_modules

    target = discover_target().expanduser().resolve()
    if not target.exists():
        print_status("❌", f"目标文件不存在: {target}")
        sys.exit(1)

    data = target.read_bytes()
    sections = parse_pe_sections(data)
    bun_sec = find_bun_section(sections)
    if bun_sec is None:
        print_status("❌", "未找到 .bun 节区")
        sys.exit(1)

    extracted = extract_modules(data, bun_sec, output_dir)
    if not extracted:
        print_status("❌", "提取失败")
        sys.exit(1)

    return output_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="为 Qoder CLI 应用中文翻译补丁（JS 文本替换）。")
    parser.add_argument("--target", type=Path, help="已提取的 JS bundle 目录；不传时使用默认路径")
    parser.add_argument("--revert", action="store_true", help="从 .bak 备份恢复原文件")
    parser.add_argument("--dry-run", action="store_true", help="只检查并输出结果，不写入文件")
    return parser.parse_args()


def main() -> int:
    init_terminal()
    args = parse_args()

    output_dir = args.target or DEFAULT_OUTPUT

    if args.revert:
        extracted_dir = discover_extracted(output_dir)
        if not extracted_dir:
            print_status("❌", f"未找到已提取的 JS bundle: {output_dir}")
            return 1
        print_status("♻️", f"正在恢复备份: {extracted_dir}")
        for filepath in extracted_dir.glob("*.js"):
            revert_file(filepath)
        print_status("✅", "恢复完成")
        return 0

    # 确保 bundle 已提取
    extracted_dir = ensure_extracted(output_dir)
    print_status("📌", f"JS bundle 目录: {extracted_dir}")

    # 加载所有替换表
    all_repls = (
        load_replacements(TRANSLATIONS_DIR / "common.replacements.json")
        + load_replacements(TRANSLATIONS_DIR / "main.replacements.json")
        + load_replacements(TRANSLATIONS_DIR / "ui.replacements.json")
    )
    # 按长度降序排序，避免短词条误伤长词条
    all_repls.sort(key=lambda item: (-len(item[0]), item[0]))

    print_status("📌", f"加载替换项总数: {len(all_repls)}")

    total_applied = 0
    files_patched = 0

    for filepath in extracted_dir.glob("*.js"):
        applied, already = patch_file(filepath, all_repls, args.dry_run, min_length=1)
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
