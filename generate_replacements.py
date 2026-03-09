#!/usr/bin/env python3
"""
根据 datafiles 中的 .bak/.js 对照，整理并更新共享替换词条。

用途：
1. 读取 datafiles 下的英文原文件（.bak）与目标翻译文件（.js）
2. 加载 translations\patches 下现有词条作为基础词条
3. 如存在残余差异，尝试基于局部锚点自动提取新增替换项
4. 将结果规范化后写回 JSON，并校验能否把 .bak 精确转换为 .js
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parent
DATAFILES_DIR = REPO_ROOT / "datafiles"
PATCHES_DIR = REPO_ROOT / "translations" / "patches"
PATCH_MARKER_RE = re.compile(r"^/\* zh-hans-patched-[^*]*\*/\r?\n?")
LOCAL_WINDOW = 4000
MIN_ANCHOR = 8


@dataclass(frozen=True)
class Target:
    key: str
    source_name: str
    patch_name: str

    @property
    def original_path(self) -> Path:
        return DATAFILES_DIR / f"{self.source_name}.bak"

    @property
    def translated_path(self) -> Path:
        return DATAFILES_DIR / self.source_name

    @property
    def patch_path(self) -> Path:
        return PATCHES_DIR / self.patch_name


TARGETS = (
    Target("main", "main.js", "main.replacements.json"),
    Target("chat", "chat.js", "chat.replacements.json"),
    Target("workbench", "workbench.desktop.main.js", "workbench.replacements.json"),
)


def strip_patch_marker(text: str) -> str:
    return PATCH_MARKER_RE.sub("", text, count=1)


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
    return replacements


def save_replacements(filepath: Path, replacements: Iterable[tuple[str, str]]) -> None:
    filepath.parent.mkdir(parents=True, exist_ok=True)
    serializable = [[old, new] for old, new in replacements]
    filepath.write_text(
        json.dumps(serializable, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def apply_replacements(text: str, replacements: Iterable[tuple[str, str]]) -> str:
    result = text
    for old, new in replacements:
        result = result.replace(old, new)
    return result


def normalize_replacements(replacements: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    seen: dict[str, str] = {}
    for old, new in replacements:
        if not old or old == new:
            continue
        if old in seen and seen[old] != new:
            raise ValueError(f"同一英文片段存在冲突翻译: {old[:80]!r}")
        seen[old] = new

    return sorted(seen.items(), key=lambda item: (-len(item[0]), item[0], item[1]))


def derive_residual_replacements(original: str, translated: str) -> list[tuple[str, str]]:
    replacements: list[tuple[str, str]] = []
    i = 0
    j = 0

    while i < len(original) and j < len(translated):
        if original[i] == translated[j]:
            i += 1
            j += 1
            continue

        original_slice = original[i : i + LOCAL_WINDOW]
        translated_slice = translated[j : j + LOCAL_WINDOW]
        match = SequenceMatcher(None, original_slice, translated_slice, autojunk=False).find_longest_match(
            0, len(original_slice), 0, len(translated_slice)
        )

        if match.size < MIN_ANCHOR:
            replacements.append((original[i:], translated[j:]))
            return replacements

        old_chunk = original_slice[: match.a]
        new_chunk = translated_slice[: match.b]
        if old_chunk and new_chunk and old_chunk != new_chunk:
            replacements.append((old_chunk, new_chunk))

        i += match.a + match.size
        j += match.b + match.size

    if i < len(original) or j < len(translated):
        old_chunk = original[i:]
        new_chunk = translated[j:]
        if old_chunk and new_chunk and old_chunk != new_chunk:
            replacements.append((old_chunk, new_chunk))

    return replacements


def build_replacements(target: Target) -> list[tuple[str, str]]:
    original = target.original_path.read_text(encoding="utf-8", errors="replace")
    translated = strip_patch_marker(
        target.translated_path.read_text(encoding="utf-8", errors="replace")
    )

    replacements = normalize_replacements(load_replacements(target.patch_path))
    current = apply_replacements(original, replacements)

    if current != translated:
        residual = derive_residual_replacements(current, translated)
        if residual:
            replacements = normalize_replacements([*replacements, *residual])
            current = apply_replacements(original, replacements)

    if current != translated:
        raise RuntimeError(
            f"{target.source_name} 仍存在未覆盖差异，无法自动生成完整替换表。"
        )

    return replacements


def main() -> None:
    results: list[tuple[str, int]] = []

    for target in TARGETS:
        replacements = build_replacements(target)
        save_replacements(target.patch_path, replacements)
        results.append((target.patch_name, len(replacements)))

    for filename, count in results:
        print(f"{filename}: {count} 条")


if __name__ == "__main__":
    main()
