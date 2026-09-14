import importlib.util
import json
import re
import struct
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "hub" / "antigravity" / "patch_hub_zh.py"
TRANSLATIONS_DIR = REPO_ROOT / "translations" / "patches" / "hub" / "antigravity"
ASSETS_DIR = REPO_ROOT / "scripts" / "hub" / "antigravity" / "assets"


def load_module():
    spec = importlib.util.spec_from_file_location("patch_hub_zh_module", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载模块: {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_replacements(scope: str) -> list[list[str]]:
    data = json.loads((TRANSLATIONS_DIR / f"{scope}.replacements.json").read_text(encoding="utf-8"))
    return data


def build_synthetic_asar(files: dict[str, bytes], unpacked: dict[str, bytes]) -> bytes:
    """按 asar 磁盘格式构造内存包：[4][pickle_len][json_len+4][json_len][json][data...]

    files: 相对路径 → 内容（打入 asar）
    unpacked: 相对路径 → 内容（仅登记为 unpacked 条目，实际内容由测试写入 unpacked 目录）
    """
    tree: dict = {}
    data_parts: list[bytes] = []
    cursor = 0

    def ensure_node(rel_path: str) -> dict:
        node = tree
        parts = rel_path.split("/")
        for part in parts[:-1]:
            node = node.setdefault(part, {"files": {}})["files"]
        return node

    for rel_path, payload in files.items():
        ensure_node(rel_path)[rel_path.split("/")[-1]] = {
            "size": len(payload),
            "offset": str(cursor),
        }
        data_parts.append(payload)
        cursor += len(payload)

    for rel_path in unpacked:
        ensure_node(rel_path)[rel_path.split("/")[-1]] = {"unpacked": True}

    header_json = json.dumps({"files": tree}, ensure_ascii=False).encode("utf-8")
    # 真实格式: [4][8+H][4+H][H]，数据区起始 = 8 + (8+H) = 16 + H（紧跟 JSON 之后）
    pickle_len = 8 + len(header_json)
    prefix = struct.pack("<IIII", 4, pickle_len, len(header_json) + 4, len(header_json))
    return prefix + header_json + b"".join(data_parts)


def make_resources_dir(root: Path) -> Path:
    """构造一个合成 Hub resources 目录（含真实英文片段的 dist 文件）。"""
    resources = root / "resources"
    resources.mkdir(parents=True)

    native_contents: dict[str, bytes] = {
        "package.json": json.dumps({"name": "antigravity", "version": "0.0.0"}).encode("utf-8"),
        "icon.png": b"\x89PNG fake",
    }
    unpacked_contents: dict[str, bytes] = {}

    for scope, rel_path in {
        "utils": "dist/utils.js",
        "menu": "dist/menu.js",
        "main": "dist/main.js",
        "tray": "dist/tray.js",
        "updater": "dist/updater.js",
        "ipchandlers": "dist/ipcHandlers.js",
        "wizard": "dist/ideInstall/wizardHtml.js",
    }.items():
        pairs = load_replacements(scope)
        content = "\n".join(old for old, _ in pairs)
        native_contents[rel_path] = content.encode("utf-8")

    unpacked_rel = "node_modules/demo-native/index.js"
    unpacked_contents[unpacked_rel] = b"module.exports = 1;\n"

    asar_bytes = build_synthetic_asar(native_contents, {unpacked_rel})
    (resources / "app.asar").write_bytes(asar_bytes)
    unpacked_root = resources / "app.asar.unpacked"
    for rel_path, payload in unpacked_contents.items():
        target = unpacked_root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    return resources


class PatchHubZhTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()

    def test_解包asar并合并unpacked条目(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            resources = make_resources_dir(Path(temp_dir))
            out_dir = resources / "app"

            from_asar, from_unpacked = self.module.unpack_asar(
                resources / "app.asar", out_dir, resources / "app.asar.unpacked")

            self.assertEqual(from_asar, 9)  # package.json + icon + 7 个 dist 文件
            self.assertEqual(from_unpacked, 1)
            self.assertEqual(
                (out_dir / "node_modules/demo-native/index.js").read_bytes(),
                b"module.exports = 1;\n")
            self.assertIn(b"fake", (out_dir / "icon.png").read_bytes())

    def test_应用补丁_解包汉化并安装翻译组件(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            resources = make_resources_dir(Path(temp_dir))

            exit_code = self.module.apply_patch(resources, dry_run=False)
            self.assertEqual(exit_code, 0)

            # asar 已停用，原版保留
            self.assertFalse((resources / "app.asar").exists())
            self.assertTrue((resources / "app.asar.orig").exists())

            # 原生补丁全部生效（合成文件包含每个 find 片段，翻译必须全覆盖）
            for scope, rel_path in self.module.NATIVE_TARGETS.items():
                patched = (resources / "app" / rel_path).read_text(encoding="utf-8")
                for old, new in load_replacements(scope):
                    self.assertIn(new, patched, f"{scope}: 缺少译文 {new[:40]!r}")
                    if old in new:
                        # 插入型补丁（译文包含原文）：原文应恰好保留一份，不得重复
                        self.assertEqual(patched.count(old), 1, f"{scope}: 原文重复 {old[:40]!r}")
                    else:
                        self.assertNotIn(old, patched, f"{scope}: 仍存在英文片段 {old[:40]!r}")

            # 注入的 require 使用相对路径指向翻译组件
            utils_patched = (resources / "app" / "dist" / "utils.js").read_text(encoding="utf-8")
            self.assertIn('require("../../zh-patch/zh-i18n")', utils_patched)
            self.assertIn("zhI18n.attachWebTranslator(win);", utils_patched)

            # 翻译组件已安装
            kit = resources / "zh-patch"
            self.assertTrue((kit / "zh-i18n.js").exists())
            self.assertTrue((kit / "cockpit-zh.json").exists())

    def test_重复应用_先重置再打补丁保持幂等(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            resources = make_resources_dir(Path(temp_dir))

            self.module.apply_patch(resources, dry_run=False)
            asar_orig_bytes = (resources / "app.asar.orig").read_bytes()
            patched_marker = "新建窗口"

            self.assertEqual(self.module.apply_patch(resources, dry_run=False), 0)
            self.assertEqual((resources / "app.asar.orig").read_bytes(), asar_orig_bytes)
            menu_patched = (resources / "app" / "dist" / "menu.js").read_text(encoding="utf-8")
            self.assertEqual(menu_patched.count(patched_marker), 1)

    def test_还原_恢复asar并清理目录(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            resources = make_resources_dir(Path(temp_dir))
            original_bytes = (resources / "app.asar").read_bytes()

            self.module.apply_patch(resources, dry_run=False)
            self.assertEqual(self.module.revert_patch(resources), 0)

            self.assertEqual((resources / "app.asar").read_bytes(), original_bytes)
            self.assertFalse((resources / "app.asar.orig").exists())
            self.assertFalse((resources / "app").exists())
            self.assertFalse((resources / "zh-patch").exists())

    def test_dry_run_不修改任何文件(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            resources = make_resources_dir(Path(temp_dir))
            before = (resources / "app.asar").read_bytes()

            self.assertEqual(self.module.apply_patch(resources, dry_run=True), 0)

            self.assertEqual((resources / "app.asar").read_bytes(), before)
            self.assertFalse((resources / "app").exists())
            self.assertFalse((resources / "app.asar.orig").exists())
            self.assertFalse((resources / "zh-patch").exists())

    def test_空目录还原_报告无需恢复(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            resources = Path(temp_dir) / "resources"
            resources.mkdir()
            self.assertEqual(self.module.revert_patch(resources), 0)
            self.assertEqual(list(resources.iterdir()), [])


class HubResourceFormatTests(unittest.TestCase):
    def test_原生替换表_均为二元字符串数组(self):
        for table in sorted(TRANSLATIONS_DIR.glob("*.replacements.json")):
            data = json.loads(table.read_text(encoding="utf-8"))
            self.assertIsInstance(data, list, table.name)
            for pair in data:
                self.assertIsInstance(pair, list, table.name)
                self.assertEqual(len(pair), 2, table.name)
                self.assertTrue(all(isinstance(item, str) and item for item in pair), table.name)
                self.assertNotEqual(pair[0], pair[1], table.name)

    def test_网页词典_dict为字符串映射且rules可编译(self):
        data = json.loads((TRANSLATIONS_DIR / "webui.dictionary.json").read_text(encoding="utf-8"))
        dictionary = data["dict"]
        self.assertIsInstance(dictionary, dict)
        self.assertGreater(len(dictionary), 100)
        for key, value in dictionary.items():
            self.assertIsInstance(key, str)
            self.assertIsInstance(value, str)
            self.assertNotEqual(key, value)

        for rule in data["rules"]:
            self.assertIsInstance(rule, list)
            self.assertIn(len(rule), (2, 3))
            pattern = rule[0]
            replacement = rule[1]
            self.assertIsInstance(pattern, str)
            self.assertIsInstance(replacement, str)
            re.compile(pattern)  # 规则必须是合法正则

    def test_注入器资产_语法完整(self):
        source = (ASSETS_DIR / "zh-i18n.js").read_text(encoding="utf-8")
        for marker in (
            "exports.translateMenu",
            "exports.attachWebTranslator",
            "cockpit-zh.json",
            "MutationObserver",
        ):
            self.assertIn(marker, source)


if __name__ == "__main__":
    unittest.main()
