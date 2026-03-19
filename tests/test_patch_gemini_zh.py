import importlib.util
import tempfile
import unittest
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "cli" / "gemini" / "patch_app_zh.py"


def load_module():
    spec = importlib.util.spec_from_file_location("patch_gemini_zh_module", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载模块: {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PatchGeminiZhTests(unittest.TestCase):
    def test_patch_file_应用替换并创建备份(self):
        module = load_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "test.js"
            original_content = "console.log('Hello World');"
            temp_path.write_text(original_content, encoding="utf-8")

            replacements = [("Hello World", "你好世界")]
            applied, already = module.patch_file(temp_path, replacements, dry_run=False)

            self.assertEqual(applied, 1)
            self.assertEqual(already, 0)
            self.assertEqual(temp_path.read_text(encoding="utf-8"), "console.log('你好世界');")
            self.assertTrue(temp_path.with_name("test.js.bak").exists())

    def test_patch_file_已经翻译时不重复应用(self):
        module = load_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "test.js"
            original_content = "console.log('你好世界');"
            temp_path.write_text(original_content, encoding="utf-8")

            replacements = [("Hello World", "你好世界")]
            applied, already = module.patch_file(temp_path, replacements, dry_run=False)

            self.assertEqual(applied, 0)
            self.assertEqual(already, 1)
            self.assertEqual(temp_path.read_text(encoding="utf-8"), "console.log('你好世界');")


if __name__ == "__main__":
    unittest.main()
