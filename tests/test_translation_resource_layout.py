import unittest
from pathlib import Path

from scripts.antigravity import patch_zh as antigravity_patch
from scripts.copilot_cli import patch_app_zh as copilot_patch
from scripts.shared import generate_replacements as replacements_tool


REPO_ROOT = Path(__file__).resolve().parents[1]


class TranslationResourceLayoutTests(unittest.TestCase):
    def test_antigravity_patch_读取按产品拆分后的资源目录(self):
        expected = REPO_ROOT / "translations" / "patches" / "antigravity"

        self.assertEqual(antigravity_patch.TRANSLATIONS_DIR, expected)
        self.assertTrue((expected / "main.replacements.json").exists())
        self.assertTrue((expected / "chat.replacements.json").exists())
        self.assertTrue((expected / "workbench.replacements.json").exists())

    def test_copilot_patch_读取按产品拆分后的资源目录(self):
        expected = REPO_ROOT / "translations" / "patches" / "copilot_cli" / "app.replacements.json"

        self.assertEqual(copilot_patch.DEFAULT_REPLACEMENTS, expected)
        self.assertTrue(expected.exists())

    def test_generate_replacements_写回_antigravity_资源目录(self):
        target = replacements_tool.TARGETS[0]
        expected = REPO_ROOT / "translations" / "patches" / "antigravity" / target.patch_name

        self.assertEqual(target.patch_path, expected)


if __name__ == "__main__":
    unittest.main()
