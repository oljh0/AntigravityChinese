#!/usr/bin/env python3
r"""
从 Kiro CLI kiro-cli.exe 中提取可翻译的 UI 字符串。

kiro-cli.exe 是 Bun standalone 可执行文件，JS 模块以混合格式
（源码 + Bun 字节码）嵌入 PE .rdata 节区，字符串字面量以 UTF-8 明文存储。

本工具扫描 .rdata 节区，提取看起来像用户可见 UI 文本的英文字符串，
用于辅助维护翻译词条。

用法：
  python extract_strings.py                    # 使用默认路径
  python extract_strings.py --target X.exe     # 指定 exe 路径
  python extract_strings.py --output out.json  # 输出到 JSON 文件
  python extract_strings.py --diff             # 与现有词条对比，显示未覆盖字符串
"""

from __future__ import annotations

import argparse
import json
import os
import re
import struct
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from scripts.shared.patch_utils import init_terminal, print_status

TRANSLATIONS_DIR = REPO_ROOT / "translations" / "patches" / "cli" / "kiro"

DEFAULT_KIRO_HOME = Path(
    os.environ.get("KIRO_CLI_HOME", r"C:\Program Files\Kiro-Cli")
)
DEFAULT_TARGET = DEFAULT_KIRO_HOME / "kiro-cli.exe"

# UI 可见文本的典型模式
UI_PATTERNS = [
    # 带省略号的动作状态
    re.compile(rb'[A-Z][a-z]+(?:\s+[a-z]+)*\.\.\.'),
    # "Press X to Y" 类交互提示
    re.compile(rb'Press\s+\w+(?:\s+\w+)*\s+to\s+\w+(?:\s+\w+)*'),
    # 错误/状态消息
    re.compile(rb'(?:Error|Failed|Success|Warning|Invalid|Unable|Cannot|Could not|No |Not )[\w\s]{8,60}'),
    # 命令描述（help text）
    re.compile(rb'(?:Show|List|Create|Delete|Update|Set|Get|Run|Start|Stop|Open|Close|Save|Load|Search|Find|Filter|Sort|Display|Enable|Disable|Configure|Initialize|Install|Uninstall|Remove|Add|Edit|View|Check|Verify|Validate|Test|Debug|Deploy|Build|Compile|Generate|Export|Import)s?\s+[\w\s]{4,50}'),
]

# 排除模式 - 代码标识符、URL、路径等
EXCLUDE_PATTERNS = [
    re.compile(rb'^https?://'),
    re.compile(rb'^[a-z_][a-zA-Z0-9_]*\('),  # 函数调用
    re.compile(rb'^[A-Z_]{3,}$'),  # 全大写常量
    re.compile(rb'^[a-z]+[A-Z]'),  # camelCase
    re.compile(rb'^\w+\.\w+\.\w+'),  # 点分路径
    re.compile(rb'^/[\w/]+'),  # Unix 路径
    re.compile(rb'^[A-Z]:\\'),  # Windows 路径
    re.compile(rb'^\{'),  # JSON/模板
    re.compile(rb'^<\w'),  # HTML 标签
]

# 更宽泛的可打印英文字符串提取
PRINTABLE_STRING_RE = re.compile(rb'[\x20-\x7e]{10,200}')


def parse_pe_sections(data: bytes) -> list[dict]:
    """解析 PE 文件的节区表。"""
    pe_sig_off = struct.unpack_from('<I', data, 0x3C)[0]
    coff_off = pe_sig_off + 4
    num_sections = struct.unpack_from('<H', data, coff_off + 2)[0]
    opt_hdr_size = struct.unpack_from('<H', data, coff_off + 16)[0]
    section_off = coff_off + 20 + opt_hdr_size

    sections = []
    for i in range(num_sections):
        off = section_off + i * 40
        name = data[off:off + 8].rstrip(b'\x00').decode('ascii', errors='replace')
        raw_size = struct.unpack_from('<I', data, off + 16)[0]
        raw_off = struct.unpack_from('<I', data, off + 20)[0]
        sections.append({
            'name': name,
            'raw_offset': raw_off,
            'raw_size': raw_size,
        })
    return sections


def extract_rdata_strings(data: bytes, sections: list[dict], min_len: int = 12) -> list[str]:
    """从 .rdata 节区提取可读英文字符串。"""
    rdata = None
    for sec in sections:
        if sec['name'] == '.rdata':
            rdata = sec
            break

    if rdata is None:
        print_status("❌", "未找到 .rdata 节区")
        return []

    start = rdata['raw_offset']
    end = start + rdata['raw_size']
    print_status("📌", f".rdata 范围: 0x{start:X} - 0x{end:X} ({rdata['raw_size'] / 1024 / 1024:.1f} MB)")

    region = data[start:end]
    strings = set()

    for match in PRINTABLE_STRING_RE.finditer(region):
        s = match.group()
        # 基本清理
        s = s.strip()
        if len(s) < min_len:
            continue

        # 排除代码标识符等
        excluded = False
        for pat in EXCLUDE_PATTERNS:
            if pat.search(s):
                excluded = True
                break
        if excluded:
            continue

        try:
            text = s.decode('utf-8')
        except UnicodeDecodeError:
            continue

        # 过滤：必须包含空格（自然语言特征）且以大写字母开头
        if ' ' not in text:
            continue
        if not text[0].isupper():
            continue
        # 排除纯数字/符号
        alpha_ratio = sum(1 for c in text if c.isalpha()) / len(text)
        if alpha_ratio < 0.5:
            continue

        strings.add(text)

    return sorted(strings)


def filter_ui_strings(strings: list[str]) -> list[str]:
    """从候选字符串中筛选最可能是 UI 文本的。"""
    ui_strings = []
    for s in strings:
        sb = s.encode('utf-8')
        for pat in UI_PATTERNS:
            if pat.search(sb):
                ui_strings.append(s)
                break
    return ui_strings


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
    parser = argparse.ArgumentParser(description="从 kiro-cli.exe 提取可翻译的 UI 字符串。")
    parser.add_argument("--target", type=Path, help="kiro-cli.exe 路径")
    parser.add_argument("--output", type=Path, help="输出 JSON 文件路径")
    parser.add_argument("--diff", action="store_true", help="显示现有词条未覆盖的字符串")
    parser.add_argument("--all", action="store_true", help="显示所有候选字符串（不仅限 UI 模式）")
    parser.add_argument("--min-len", type=int, default=12, help="最小字符串长度（默认 12）")
    return parser.parse_args()


def main() -> int:
    init_terminal()
    args = parse_args()

    target = (args.target or DEFAULT_TARGET).expanduser().resolve()
    if not target.exists():
        print_status("❌", f"目标文件不存在: {target}")
        return 1

    print_status("📌", f"目标文件: {target} ({target.stat().st_size // 1024 // 1024} MB)")

    data = target.read_bytes()
    sections = parse_pe_sections(data)

    for sec in sections:
        print_status("📌", f"节区: {sec['name']:10s} 偏移=0x{sec['raw_offset']:08X} 大小=0x{sec['raw_size']:08X}")

    all_strings = extract_rdata_strings(data, sections, min_len=args.min_len)
    print_status("📌", f"提取候选字符串: {len(all_strings)}")

    if args.all:
        display_strings = all_strings
    else:
        display_strings = filter_ui_strings(all_strings)
        print_status("📌", f"筛选 UI 字符串: {len(display_strings)}")

    if args.diff:
        existing = load_existing_replacements()
        uncovered = [s for s in display_strings if s not in existing]
        print_status("📌", f"现有词条: {len(existing)}, 未覆盖: {len(uncovered)}")
        display_strings = uncovered

    if args.output:
        args.output.write_text(
            json.dumps(display_strings, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        print_status("✅", f"已输出到: {args.output}")
    else:
        for s in display_strings:
            byte_len = len(s.encode('utf-8'))
            print(f"  [{byte_len:3d}B] {s}")

    print_status("🎉", f"共 {len(display_strings)} 个字符串")
    return 0


if __name__ == "__main__":
    sys.exit(main())
