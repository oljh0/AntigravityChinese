#!/usr/bin/env python3
"""
Antigravity 主程序（Hub 智能体桌面应用）中文汉化补丁脚本。

Antigravity 2.x 起，「Antigravity」(Hub) 与「Antigravity IDE」是两个独立应用：
Hub 是 Electron 外壳 (resources/app.asar)，主界面由 resources/bin/language_server.exe
内嵌的网页 UI 提供。本脚本做三件事：

  1. 将 resources/app.asar 解包为 resources/app 目录（Electron 优先加载目录），
     原 asar 保留为 app.asar.orig 作为还原备份；
  2. 按 translations/patches/hub/antigravity/*.replacements.json 汉化原生
     菜单/托盘/对话框/安装向导等硬编码字符串；
  3. 安装网页 UI 词典翻译组件 (zh-i18n.js + cockpit-zh.json) 到 resources/zh-patch/，
     由主进程在窗口加载后注入（词典支持热更新：修改后在应用内 Ctrl+R 生效）。

用法：
  python scripts/hub/antigravity/patch_hub_zh.py             # 应用汉化
  python scripts/hub/antigravity/patch_hub_zh.py --dry-run   # 仅预览匹配情况
  python scripts/hub/antigravity/patch_hub_zh.py --revert    # 恢复英文原版
  python scripts/hub/antigravity/patch_hub_zh.py --target <resources 目录>
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

# 添加共享工具路径
sys.path.append(str(Path(__file__).resolve().parents[2] / "shared"))
from patch_utils import init_terminal, print_status, print_step  # noqa: E402

init_terminal()

REPO_ROOT = Path(__file__).resolve().parents[3]
TRANSLATIONS_DIR = REPO_ROOT / "translations" / "patches" / "hub" / "antigravity"
ASSETS_DIR = Path(__file__).resolve().parent / "assets"

APP_DIR_NAME = "app"
ASAR_NAME = "app.asar"
ASAR_ORIG_NAME = "app.asar.orig"
UNPACKED_NAME = "app.asar.unpacked"
KIT_DIR_NAME = "zh-patch"

# 原生 UI 补丁表：scope → dist 内相对路径
NATIVE_TARGETS = {
    "utils": "dist/utils.js",
    "menu": "dist/menu.js",
    "main": "dist/main.js",
    "tray": "dist/tray.js",
    "updater": "dist/updater.js",
    "ipchandlers": "dist/ipcHandlers.js",
    "wizard": "dist/ideInstall/wizardHtml.js",
}

PROCESS_NAME_WINDOWS = "Antigravity.exe"


def discover_resources_dir() -> Path | None:
    """自动发现 Hub 安装的 resources 目录。"""
    candidates: list[Path] = []
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            candidates.append(Path(local_app_data) / "Programs" / "Antigravity" / "resources")
    elif sys.platform == "darwin":
        candidates.append(Path("/Applications/Antigravity.app/Contents/Resources"))
        home = os.environ.get("HOME", "")
        if home:
            candidates.append(Path(home) / "Applications/Antigravity.app/Contents/Resources")
    for candidate in candidates:
        if (candidate / ASAR_NAME).exists():
            return candidate
    return candidates[0] if candidates else None


def is_hub_running() -> bool:
    """检查 Hub 是否正在运行（运行中无法安全替换文件）。"""
    if sys.platform != "win32":
        return False
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {PROCESS_NAME_WINDOWS}"],
            capture_output=True, text=True, timeout=10,
        )
        return PROCESS_NAME_WINDOWS.lower() in (result.stdout or "").lower()
    except Exception:
        return False


def load_replacements(scope: str) -> list[tuple[str, str]]:
    filepath = TRANSLATIONS_DIR / f"{scope}.replacements.json"
    data = json.loads(filepath.read_text(encoding="utf-8"))
    if not isinstance(data, list) or any(
        not isinstance(pair, list) or len(pair) != 2 or any(not isinstance(item, str) for item in pair)
        for pair in data
    ):
        raise ValueError(f"替换表格式无效: {filepath}")
    return [(pair[0], pair[1]) for pair in data]


# ══════════════════════════════════════════════════════════════════════
# asar 解包（纯 Python 实现，格式与 @electron/asar 兼容）
# ══════════════════════════════════════════════════════════════════════

def read_asar_header(asar_path: Path) -> tuple[dict, int]:
    """解析 asar 头部，返回 (文件树 JSON, 数据区起始偏移)。"""
    with asar_path.open("rb") as handle:
        pre = handle.read(16)
        if len(pre) < 16:
            raise ValueError(f"asar 头部不完整: {asar_path}")
        pickle_len = struct.unpack_from("<I", pre, 4)[0]
        json_len = struct.unpack_from("<I", pre, 12)[0]
        header = json.loads(handle.read(json_len).decode("utf-8"))
    return header, 8 + pickle_len


def unpack_asar(asar_path: Path, out_dir: Path, unpacked_root: Path | None = None) -> tuple[int, int]:
    """将 asar 内容解包到 out_dir。

    unpacked_root: app.asar.unpacked 目录，标记为 "unpacked" 的条目从这里复制；
    若为 None 则仅处理 asar 内的条目。
    返回 (来自 asar 的文件数, 来自 unpacked 的文件数)。
    """
    header, data_base = read_asar_header(asar_path)
    from_asar = 0
    from_unpacked = 0

    def walk(node: dict, rel: str) -> None:
        nonlocal from_asar, from_unpacked
        for name, meta in (node.get("files") or {}).items():
            rel_path = f"{rel}/{name}" if rel else name
            out_path = out_dir / rel_path
            if "files" in meta:
                out_path.mkdir(parents=True, exist_ok=True)
                walk(meta, rel_path)
            elif meta.get("unpacked"):
                if unpacked_root is not None:
                    shutil.copy2(unpacked_root / rel_path, out_path)
                    from_unpacked += 1
            else:
                with asar_path.open("rb") as handle:
                    handle.seek(data_base + int(meta["offset"]))
                    payload = handle.read(meta["size"])
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(payload)
                from_asar += 1

    out_dir.mkdir(parents=True, exist_ok=True)
    walk(header, "")
    return from_asar, from_unpacked


# ══════════════════════════════════════════════════════════════════════
# 原生 UI 补丁与词典安装
# ══════════════════════════════════════════════════════════════════════

def patch_native_file(filepath: Path, replacements: list[tuple[str, str]]) -> tuple[int, int, list[str]]:
    """对单个文件应用替换，返回 (成功数, 已是中文数, 未匹配列表)。"""
    content = filepath.read_text(encoding="utf-8", errors="replace")
    applied = 0
    already = 0
    failed: list[str] = []

    for old, new in replacements:
        if old in content:
            content = content.replace(old, new, 1)
            applied += 1
        elif new in content:
            already += 1
        else:
            failed.append(old[:60].replace("\n", "\\n"))

    filepath.write_text(content, encoding="utf-8")
    return applied, already, failed


def apply_native_patches(app_dir: Path, dry_run: bool = False) -> tuple[int, int]:
    total_applied = 0
    total_all = 0
    for scope, rel_path in NATIVE_TARGETS.items():
        replacements = load_replacements(scope)
        total_all += len(replacements)
        filepath = app_dir / rel_path
        if not filepath.exists():
            print_status("❌", f"文件不存在，跳过 {scope}: {rel_path}")
            continue
        if dry_run:
            content = filepath.read_text(encoding="utf-8", errors="replace")
            matched = sum(1 for old, _ in replacements if old in content)
            print_status("⚙️", f"[dry-run] {scope}: 预计替换 {matched}/{len(replacements)} 处 ({rel_path})")
            total_applied += matched
            continue
        applied, already, failed = patch_native_file(filepath, replacements)
        total_applied += applied + already
        state = f"{scope}: 成功 {applied}/{len(replacements)}"
        if already:
            state += f"（另 {already} 处已是中文）"
        print_status("✅" if not failed else "⚠️", state)
        for snippet in failed:
            print(f"    - 未匹配: {snippet}...")
    return total_applied, total_all


def install_kit(resources_dir: Path, dry_run: bool = False) -> None:
    """安装网页 UI 翻译组件到 resources/zh-patch/。"""
    kit_dir = resources_dir / KIT_DIR_NAME
    if dry_run:
        print_status("⚙️", f"[dry-run] 将安装翻译组件到: {kit_dir}")
        return
    kit_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ASSETS_DIR / "zh-i18n.js", kit_dir / "zh-i18n.js")
    shutil.copy2(TRANSLATIONS_DIR / "webui.dictionary.json", kit_dir / "cockpit-zh.json")
    print_status("✅", f"已安装网页 UI 翻译组件: {kit_dir}")


# ══════════════════════════════════════════════════════════════════════
# 状态重置 / 还原
# ══════════════════════════════════════════════════════════════════════

def reset_to_clean(resources_dir: Path) -> bool:
    """恢复备份的 asar 并删除已解包/已补丁的目录，返回是否发生了变更。"""
    changed = False
    asar_path = resources_dir / ASAR_NAME
    asar_orig = resources_dir / ASAR_ORIG_NAME
    app_dir = resources_dir / APP_DIR_NAME
    kit_dir = resources_dir / KIT_DIR_NAME

    if asar_orig.exists():
        if asar_path.exists():
            asar_path.unlink()
        asar_orig.rename(asar_path)
        changed = True
    if app_dir.exists():
        shutil.rmtree(app_dir)
        changed = True
    if kit_dir.exists():
        shutil.rmtree(kit_dir)
        changed = True
    return changed


# ══════════════════════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════════════════════

def apply_patch(resources_dir: Path, dry_run: bool = False) -> int:
    asar_path = resources_dir / ASAR_NAME

    if dry_run:
        if not asar_path.exists():
            print_status("❌", f"未找到 {asar_path}")
            return 1
        with tempfile.TemporaryDirectory(prefix="antigravity-hub-dryrun-") as temp:
            staging = Path(temp) / APP_DIR_NAME
            from_asar, from_unpacked = unpack_asar(
                asar_path, staging, resources_dir / UNPACKED_NAME)
            print_status("⚙️", f"[dry-run] 解包预览: {from_asar} 个文件 (unpacked {from_unpacked} 个)")
            apply_native_patches(staging, dry_run=True)
            install_kit(resources_dir, dry_run=True)
        print_status("🎉", "dry-run 完成，未修改任何文件")
        return 0

    # 正式应用：先重置，保证从干净英文状态开始
    if reset_to_clean(resources_dir):
        print_status("♻️", "检测到旧的汉化状态，已重置为英文原版")

    if not asar_path.exists():
        print_status("❌", f"未找到 {asar_path}，请用 --target 指定 Hub 的 resources 目录")
        return 1

    print_step(1, 4, f"解包 {ASAR_NAME} → {APP_DIR_NAME}/ ...")
    app_dir = resources_dir / APP_DIR_NAME
    from_asar, from_unpacked = unpack_asar(asar_path, app_dir, resources_dir / UNPACKED_NAME)
    print_status("✅", f"解包完成: {from_asar} 个文件来自 asar，{from_unpacked} 个来自 unpacked")

    print()
    print_step(2, 4, "汉化原生菜单/托盘/对话框...")
    apply_native_patches(app_dir)

    print()
    print_step(3, 4, "安装网页 UI 翻译组件...")
    install_kit(resources_dir)

    print()
    print_step(4, 4, "停用原 asar (保留为备份)...")
    asar_path.rename(resources_dir / ASAR_ORIG_NAME)
    print_status("✅", f"原版备份: {ASAR_ORIG_NAME}")

    print_status("🎉", "汉化完成！请启动 Antigravity 查看效果")
    print_status("📌", "词典热更新: 修改 resources/zh-patch/cockpit-zh.json 后在应用内 Ctrl+R")
    print_status("📌", "Hub 自动更新后汉化会失效，重新运行本脚本即可")
    return 0


def revert_patch(resources_dir: Path) -> int:
    if reset_to_clean(resources_dir):
        print_status("♻️", "已恢复英文原版 (app 目录与翻译组件已移除)")
    else:
        print_status("⏭️", "未检测到汉化痕迹，无需恢复")
    print_status("📌", "请重新启动 Antigravity 生效")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Antigravity 主程序 (Hub) 中文汉化补丁")
    parser.add_argument("--revert", action="store_true", help="撤销汉化，恢复英文原版")
    parser.add_argument("--dry-run", action="store_true", help="仅预览匹配情况，不修改文件")
    parser.add_argument("--target", type=Path, default=None, help="手动指定 Hub 的 resources 目录")
    parser.add_argument("--force", action="store_true", help="跳过运行中进程检查")
    args = parser.parse_args()

    resources_dir = args.target if args.target else discover_resources_dir()
    if resources_dir is None:
        print_status("❌", "无法自动发现 Antigravity 安装目录，请用 --target 指定 resources 目录")
        return 1

    print_status("📌", f"目标目录: {resources_dir}")

    if not args.revert and not args.dry_run:
        if is_hub_running() and not args.force:
            print_status("❌", f"检测到 {PROCESS_NAME_WINDOWS} 正在运行，请先完全退出 Antigravity（含托盘图标）后重试，或使用 --force")
            return 1

    if args.revert:
        return revert_patch(resources_dir)
    return apply_patch(resources_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
