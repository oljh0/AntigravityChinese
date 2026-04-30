#!/usr/bin/env python3
r"""
从 Qoder CLI 提取的 JS bundle 中扫描可翻译的 UI 字符串。

分析 index.js 中 label:"...", describe:"...", description:"...", message:"..." 等模式，
提取用户可见的英文字符串，用于辅助维护翻译词条。

用法：
  python -m scripts.cli.qoder.extract_strings                    # 扫描默认路径
  python -m scripts.cli.qoder.extract_strings --target DIR       # 指定已提取目录
  python -m scripts.cli.qoder.extract_strings --output out.json  # 输出到 JSON
  python -m scripts.cli.qoder.extract_strings --diff             # 与现有词条对比
  python -m scripts.cli.qoder.extract_strings --all              # 显示所有模式
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from scripts.shared.patch_utils import init_terminal, print_status
from scripts.cli.qoder.extract_bundle import DEFAULT_OUTPUT

TRANSLATIONS_DIR = REPO_ROOT / "translations" / "patches" / "cli" / "qoder"

# 提取模式：从 JS 源码中抓取 key:"value" 形式的字符串
FIELD_PATTERNS = [
    # label:"Accept Edits"
    re.compile(r'label:"([^"]{2,80})"'),
    # describe:"Add a server"
    re.compile(r'describe:"([^"]{2,120})"'),
    # description:"Some long description..."
    re.compile(r'description:"([^"]{8,200})"'),
    # message:"Failed to load data"
    re.compile(r'message:"([^"]{4,120})"'),
    # placeholder:"Enter text..."
    re.compile(r'placeholder:"([^"]{4,80})"'),
    # title:"Settings"
    re.compile(r'title:"([^"]{2,80})"'),
    # tooltip:"Click to expand"
    re.compile(r'tooltip:"([^"]{4,80})"'),
    # text:"Some user-visible text"
    re.compile(r'text:"([^"]{4,80})"'),
]

# 排除模式 - 非用户可见的字符串
EXCLUDE_PATTERNS = [
    re.compile(r'^[a-z_][a-zA-Z0-9_]*$'),        # camelCase 标识符
    re.compile(r'^[A-Z_]{3,}$'),                   # 全大写常量
    re.compile(r'^https?://'),                      # URL
    re.compile(r'^\w+\.\w+\.\w+'),                 # 点分路径
    re.compile(r'^[{<\[]'),                         # JSON/HTML/模板
    re.compile(r'^[/\\]'),                          # 文件路径
    re.compile(r'^\$\{'),                           # 模板字符串
    re.compile(r'^[a-z]{1,3}$'),                    # 极短字符串
]


def extract_ui_strings(text: str, pattern_filter: str | None = None) -> dict[str, list[str]]:
    """从 JS 源码提取 UI 字符串，按字段类型分组。"""
    results: dict[str, list[str]] = {}

    for pat in FIELD_PATTERNS:
        field_name = pat.pattern.split(':"')[0].rstrip('\\')
        if pattern_filter and field_name != pattern_filter:
            continue

        strings = set()
        for match in pat.finditer(text):
            value = match.group(1)

            # 排除
            excluded = False
            for exc in EXCLUDE_PATTERNS:
                if exc.search(value):
                    excluded = True
                    break
            if excluded:
                continue

            # 必须包含空格或大写开头（自然语言特征）
            if not value[0].isupper() and ' ' not in value:
                continue

            strings.add(value)

        if strings:
            results[field_name] = sorted(strings)

    return results


def load_existing_replacements() -> set[str]:
    """加载现有翻译词条中的英文原文。"""
    existing = set()
    for fname in ['common.replacements.json', 'main.replacements.json', 'ui.replacements.json']:
        fp = TRANSLATIONS_DIR / fname
        if fp.exists():
            pairs = json.loads(fp.read_text('utf-8'))
            for pair in pairs:
                if isinstance(pair, list) and len(pair) == 2:
                    existing.add(pair[0])
    return existing


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="从 Qoder CLI JS bundle 提取可翻译的 UI 字符串。")
    parser.add_argument("--target", type=Path, help="已提取的 JS bundle 目录")
    parser.add_argument("--output", type=Path, help="输出 JSON 文件路径")
    parser.add_argument("--diff", action="store_true", help="显示现有词条未覆盖的字符串")
    parser.add_argument("--all", action="store_true", help="显示所有字段类型（含低频）")
    parser.add_argument("--field", type=str, help="只扫描指定字段（如 label, describe）")
    return parser.parse_args()


def main() -> int:
    init_terminal()
    args = parse_args()

    target_dir = args.target or DEFAULT_OUTPUT
    index_js = Path(target_dir) / "index.js"

    if not index_js.exists():
        print_status("❌", f"未找到 JS bundle: {index_js}")
        print_status("📌", "请先运行: python -m scripts.cli.qoder.extract_bundle")
        return 1

    print_status("📌", f"扫描文件: {index_js} ({index_js.stat().st_size / 1024 / 1024:.1f} MB)")

    text = index_js.read_text(encoding='utf-8', errors='replace')
    results = extract_ui_strings(text, pattern_filter=args.field)

    total = sum(len(v) for v in results.values())
    print_status("📌", f"提取 UI 字符串: {total}")

    for field, strings in sorted(results.items()):
        print_status("📌", f"  {field}: {len(strings)}")

    if args.diff:
        existing = load_existing_replacements()
        # 将现有词条中的原文提取出纯文本部分
        existing_values = set()
        for orig in existing:
            # 从 'label:"Accept Edits"' 提取 'Accept Edits'
            m = re.match(r'\w+:"(.+)"$', orig)
            if m:
                existing_values.add(m.group(1))
            else:
                existing_values.add(orig)

        uncovered: dict[str, list[str]] = {}
        for field, strings in results.items():
            unc = [s for s in strings if s not in existing_values]
            if unc:
                uncovered[field] = unc

        uncovered_total = sum(len(v) for v in uncovered.values())
        print_status("📌", f"现有词条: {len(existing)}, 未覆盖: {uncovered_total}")
        results = uncovered

    # 构建输出
    if args.all:
        display = results
    else:
        # 默认只显示高频字段
        display = {k: v for k, v in results.items() if k in ('label', 'describe', 'message', 'description')}

    if args.output:
        flat = []
        for field, strings in sorted(display.items()):
            for s in strings:
                flat.append(f'{field}:"{s}"')
        args.output.write_text(
            json.dumps(flat, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        print_status("✅", f"已输出到: {args.output}")
    else:
        for field, strings in sorted(display.items()):
            print(f"\n  === {field} ({len(strings)}) ===")
            for s in strings:
                print(f'    {field}:"{s}"')

    flat_total = sum(len(v) for v in display.values())
    print_status("🎉", f"共 {flat_total} 个字符串")
    return 0


if __name__ == "__main__":
    sys.exit(main())
