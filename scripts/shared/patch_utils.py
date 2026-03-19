#!/usr/bin/env python3
"""
共享的补丁工具函数。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path


def load_replacements(filepath: Path) -> list[tuple[str, str]]:
    if not filepath.exists():
        return []

    data = json.loads(filepath.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"替换表格式无效: {filepath}")

    replacements: list[tuple[str, str]] = []
    for pair in data:
        if (
            not isinstance(pair, list)
            or len(pair) != 2
            or not isinstance(pair[0], str)
            or not isinstance(pair[1], str)
        ):
            raise ValueError(f"替换表格式无效: {filepath}")
        replacements.append((pair[0], pair[1]))
    # 按长度降序排列，避免子串先被替换导致匹配失效
    return sorted(replacements, key=lambda item: (-len(item[0]), item[0]))


def patch_file(filepath: Path, replacements: list[tuple[str, str]], dry_run: bool) -> tuple[int, int]:
    if not replacements:
        return 0, 0

    if not filepath.exists():
        return 0, 0

    content = filepath.read_text(encoding="utf-8", errors="replace")
    updated = content
    applied = 0
    already = 0

    for old, new in replacements:
        if old in updated:
            updated = updated.replace(old, new)
            applied += 1
        elif new in updated:
            already += 1

    if applied > 0 and not dry_run:
        # 创建备份
        backup = filepath.with_name(filepath.name + ".bak")
        if not backup.exists():
            shutil.copy2(filepath, backup)
        filepath.write_text(updated, encoding="utf-8")
    
    return applied, already


def revert_file(filepath: Path):
    backup = filepath.with_name(filepath.name + ".bak")
    if backup.exists():
        shutil.copy2(backup, filepath)
