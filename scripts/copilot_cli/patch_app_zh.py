#!/usr/bin/env python3
r"""
Copilot CLI app.js 中文翻译补丁脚本。

默认目标文件：
  自动发现 %USERPROFILE%\.copilot\pkg\universal\*\app.js 中最新且存在的版本。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPLACEMENTS = REPO_ROOT / "translations" / "patches" / "copilot_cli" / "app.replacements.json"
DEFAULT_COPILOT_HOME = Path(os.environ.get("COPILOT_HOME", "~/.copilot")).expanduser()

IDENTIFIER_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")
SAFE_CONTEXT_RE = re.compile(
    r"""["'`]|(?:children|label|text|placeholder|tooltip|title|inputPlaceholder|textContent|description|help)\s*[:=]"""
)
VERSION_TOKEN_RE = re.compile(r"\d+|[A-Za-z]+")


def version_key(name: str) -> tuple[tuple[int, object], ...]:
    tokens = VERSION_TOKEN_RE.findall(name)
    if not tokens:
        return ((1, name.lower()),)
    parts: list[tuple[int, object]] = []
    for token in tokens:
        if token.isdigit():
            parts.append((0, int(token)))
        else:
            parts.append((1, token.lower()))
    return tuple(parts)


def find_latest_app_target(universal_dir: Path) -> Path:
    if not universal_dir.exists():
        raise FileNotFoundError(f"Copilot universal 目录不存在: {universal_dir}")

    candidates = [entry / "app.js" for entry in universal_dir.iterdir() if entry.is_dir() and (entry / "app.js").exists()]
    if not candidates:
        raise FileNotFoundError(f"未在 {universal_dir} 下找到任何可用的 app.js")

    return max(candidates, key=lambda path: version_key(path.parent.name))


def resolve_target_path(target: Path | None, copilot_home: Path) -> Path:
    if target is not None:
        return target.expanduser()
    return find_latest_app_target(copilot_home.expanduser() / "pkg" / "universal")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="为 Copilot CLI universal app.js 应用中文翻译补丁。")
    parser.add_argument("--target", type=Path, help="目标 app.js 路径；不传时自动发现最新版本目录")
    parser.add_argument(
        "--copilot-home",
        type=Path,
        default=DEFAULT_COPILOT_HOME,
        help="Copilot CLI 主目录，默认使用当前用户的 .copilot 目录",
    )
    parser.add_argument(
        "--replacements",
        type=Path,
        default=DEFAULT_REPLACEMENTS,
        help="JSON 替换表路径，格式为 [[old, new], ...]",
    )
    parser.add_argument("--revert", action="store_true", help="从 .bak 备份恢复原文件")
    parser.add_argument("--dry-run", action="store_true", help="只检查并输出结果，不写入文件")
    parser.add_argument(
        "--allow-unsafe",
        action="store_true",
        help="允许应用高风险替换（不推荐，可能误改方法名或属性名）",
    )
    return parser.parse_args()


def backup_path(target: Path) -> Path:
    return target.with_name(target.name + ".bak")


def load_replacements(filepath: Path) -> list[tuple[str, str]]:
    if not filepath.exists():
        raise FileNotFoundError(f"替换表不存在: {filepath}")

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
    return normalize_replacements(replacements)


def normalize_replacements(replacements: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen: dict[str, str] = {}
    for old, new in replacements:
        if not old or old == new:
            continue
        if old in seen and seen[old] != new:
            raise ValueError(f"同一英文片段存在冲突翻译: {old[:80]!r}")
        seen[old] = new

    return sorted(seen.items(), key=lambda item: (-len(item[0]), item[0], item[1]))


def is_risky_replacement(old: str, new: str) -> tuple[bool, str]:
    if IDENTIFIER_RE.fullmatch(old) or IDENTIFIER_RE.fullmatch(new):
        return True, "疑似纯标识符/方法名"
    if len(old) < 4:
        return True, "原片段过短，容易误伤"
    if not SAFE_CONTEXT_RE.search(old):
        return True, "缺少字符串字面量或可见字段上下文"
    if "\n" not in old and old.count(" ") == 0 and '"' not in old and "'" not in old and "`" not in old:
        return True, "缺少稳定上下文"
    return False, ""


def ensure_backup(target: Path, create_if_missing: bool = True) -> Path:
    backup = backup_path(target)
    if not target.exists() and not backup.exists():
        raise FileNotFoundError(f"目标文件不存在且无备份: {target}")

    if not backup.exists():
        if not create_if_missing:
            return target
        shutil.copy2(target, backup)
        print(f"  ✅ 已备份原始文件: {backup.name}")
    else:
        print(f"  ℹ️  检测到备份文件: {backup.name}")
    return backup


def apply_patch(target: Path, replacements_path: Path, dry_run: bool, allow_unsafe: bool) -> int:
    source = ensure_backup(target, create_if_missing=not dry_run)
    if source == target and dry_run:
        print("  ℹ️  dry-run 模式下未创建备份，直接基于当前目标文件做检查")
    content = source.read_text(encoding="utf-8", errors="replace")
    updated = content

    replacements = load_replacements(replacements_path)
    applied = 0
    already = 0
    missing: list[str] = []
    skipped: list[tuple[str, str]] = []

    for old, new in replacements:
        risky, reason = is_risky_replacement(old, new)
        if risky and not allow_unsafe:
            skipped.append((reason, old[:80]))
            continue

        if old in updated:
            updated = updated.replace(old, new)
            applied += 1
        elif new in updated:
            already += 1
        else:
            missing.append(old[:80])

    print(f"  📄 替换表: {replacements_path}")
    print(f"  🎯 目标文件: {target}")
    print(f"  ✅ 成功替换: {applied}/{len(replacements)}")
    if already:
        print(f"  ⏭️  已存在目标翻译: {already}")
    if skipped:
        print(f"  🛡️  已跳过高风险替换: {len(skipped)}")
        for reason, snippet in skipped[:20]:
            print(f"    - {reason}: {snippet}...")
        if len(skipped) > 20:
            print(f"    - 其余 {len(skipped) - 20} 项未展开")
    if missing:
        print(f"  ⚠️  未匹配到原片段: {len(missing)}")
        for snippet in missing[:20]:
            print(f"    - {snippet}...")
        if len(missing) > 20:
            print(f"    - 其余 {len(missing) - 20} 项未展开")

    if dry_run:
        print("  🧪 dry-run 模式：未写入任何文件")
        return applied

    target.write_text(updated, encoding="utf-8")
    print(f"  ♻️  已基于备份原文重新生成并覆盖: {target.name}")
    print("  🎉 已写入翻译补丁")
    return applied


def revert_patch(target: Path) -> None:
    backup = backup_path(target)
    if not backup.exists():
        print(f"  ⏭️  无可恢复备份: {backup}")
        return

    shutil.copy2(backup, target)
    print(f"  ✅ 已恢复原文件: {target}")


def main() -> int:
    args = parse_args()
    replacements_path = args.replacements.expanduser()

    try:
        target = resolve_target_path(args.target, args.copilot_home)
        if args.target is None:
            print(f"  🔎 自动发现目标版本: {target.parent.name}")

        if args.revert:
            revert_patch(target)
            return 0

        apply_patch(
            target=target,
            replacements_path=replacements_path,
            dry_run=args.dry_run,
            allow_unsafe=args.allow_unsafe,
        )
        return 0
    except Exception as exc:
        print(f"  ❌ 失败: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

