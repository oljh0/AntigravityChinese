import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "cli" / "copilot" / "patch_app_zh.py"


def load_module():
    spec = importlib.util.spec_from_file_location("patch_app_zh_module", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载模块: {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PatchAppZhPathDiscoveryTests(unittest.TestCase):
    def test_find_latest_app_target_选择存在_app_js_的最新版本目录(self):
        module = load_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            universal_dir = Path(temp_dir) / "pkg" / "universal"
            (universal_dir / "1.0.5").mkdir(parents=True)
            (universal_dir / "1.0.5" / "app.js").write_text("// v1.0.5", encoding="utf-8")
            (universal_dir / "1.0.9").mkdir(parents=True)
            (universal_dir / "1.0.9" / "app.js").write_text("// v1.0.9", encoding="utf-8")
            (universal_dir / "1.0.10").mkdir(parents=True)
            (universal_dir / "1.0.10" / "app.js").write_text("// v1.0.10", encoding="utf-8")

            result = module.find_latest_app_target(universal_dir)

        self.assertEqual(result, universal_dir / "1.0.10" / "app.js")

    def test_find_latest_app_target_跳过缺少_app_js_的更高版本目录(self):
        module = load_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            universal_dir = Path(temp_dir) / "pkg" / "universal"
            (universal_dir / "1.0.9").mkdir(parents=True)
            (universal_dir / "1.0.9" / "app.js").write_text("// v1.0.9", encoding="utf-8")
            (universal_dir / "1.0.10").mkdir(parents=True)

            result = module.find_latest_app_target(universal_dir)

        self.assertEqual(result, universal_dir / "1.0.9" / "app.js")


if __name__ == "__main__":
    unittest.main()
