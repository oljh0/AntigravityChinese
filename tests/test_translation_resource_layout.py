import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class TranslationResourceLayoutTests(unittest.TestCase):
    def test_ide补丁读取按产品拆分后的资源目录(self):
        expected = REPO_ROOT / "translations" / "patches" / "ide" / "antigravity"

        self.assertTrue((expected / "main.replacements.json").exists())
        self.assertTrue((expected / "chat.replacements.json").exists())
        self.assertTrue((expected / "workbench.replacements.json").exists())

    def test_hub补丁读取按产品拆分后的资源目录(self):
        expected = REPO_ROOT / "translations" / "patches" / "hub" / "antigravity"

        for scope in ("utils", "menu", "main", "tray", "updater", "ipchandlers", "wizard"):
            self.assertTrue((expected / f"{scope}.replacements.json").exists(), scope)
        self.assertTrue((expected / "webui.dictionary.json").exists())
        self.assertTrue(
            (REPO_ROOT / "scripts" / "hub" / "antigravity" / "assets" / "zh-i18n.js").exists()
        )

    def test_copilot补丁读取按产品拆分后的资源目录(self):
        expected = REPO_ROOT / "translations" / "patches" / "cli" / "copilot" / "app.replacements.json"

        self.assertTrue(expected.exists())

    def test_generate_replacements写回ide资源目录(self):
        import importlib.util
        import sys

        module_path = REPO_ROOT / "scripts" / "shared" / "generate_replacements.py"
        spec = importlib.util.spec_from_file_location("generate_replacements_module", module_path)
        module = importlib.util.module_from_spec(spec)
        # dataclasses 解析字符串注解需要模块已注册进 sys.modules
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)
        finally:
            sys.modules.pop(spec.name, None)

        self.assertEqual(
            module.PATCHES_DIR,
            REPO_ROOT / "translations" / "patches" / "ide" / "antigravity",
        )
        for target in module.TARGETS:
            self.assertEqual(
                target.patch_path,
                module.PATCHES_DIR / target.patch_name,
            )
            self.assertTrue(target.patch_path.exists(), target.patch_name)


if __name__ == "__main__":
    unittest.main()
