import json
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.cli.qoder import extract_bundle, patch_app_zh


REPO_ROOT = Path(__file__).resolve().parents[1]
QODER_PATCH_DIR = REPO_ROOT / "translations" / "patches" / "cli" / "qoder"


class QoderReplacementTests(unittest.TestCase):
    def test_qoder_replacement_files_are_valid_json_pairs(self):
        for path in QODER_PATCH_DIR.glob("*.replacements.json"):
            with self.subTest(path=path.name):
                data = json.loads(path.read_text(encoding="utf-8"))
                self.assertIsInstance(data, list)
                for pair in data:
                    self.assertIsInstance(pair, list)
                    self.assertEqual(len(pair), 2)
                    self.assertTrue(all(isinstance(item, str) for item in pair))

    def test_main_replacements_include_help_output_terms(self):
        replacements = dict(json.loads((QODER_PATCH_DIR / "main.replacements.json").read_text(encoding="utf-8")))

        self.assertEqual(
            replacements[
                "Usage: ${hD} [options] [command]\n\n${R$} - Defaults to interactive mode. Use -p/--print for non-interactive output."
            ],
            "用法: ${hD} [选项] [命令]\n\n${R$} - 默认进入交互模式。使用 -p/--print 进行非交互式输出。",
        )
        self.assertEqual(replacements['deferY18nLookup("Show help")'], 'deferY18nLookup("显示帮助")')
        self.assertEqual(replacements['deferY18nLookup("Show version number")'], 'deferY18nLookup("显示版本号")')
        self.assertEqual(replacements['f("Commands:")'], 'f("命令:")')
        self.assertEqual(replacements['f("Options:")'], 'f("选项:")')
        self.assertEqual(replacements['f("choices:")'], 'f("可选值:")')
        self.assertEqual(replacements['CH=`[${f("boolean")}]`'], 'CH=`[${f("布尔")}]`')
        self.assertEqual(replacements['CH=`[${f("number")}]`'], 'CH=`[${f("数字")}]`')

    def test_type_marker_rules_do_not_match_schema_literals(self):
        old_values = {pair[0] for pair in json.loads((QODER_PATCH_DIR / "main.replacements.json").read_text(encoding="utf-8"))}

        self.assertNotIn('f("array")', old_values)
        self.assertNotIn('f("boolean")', old_values)
        self.assertNotIn('f("number")', old_values)
        self.assertNotIn('f("string")', old_values)

    def test_main_replacements_include_qoder_output_mojibake_guard(self):
        replacements = dict(json.loads((QODER_PATCH_DIR / "main.replacements.json").read_text(encoding="utf-8")))

        guard = replacements["function HI(...H){return ZEI(...H)}function NL(...H){return zEI(...H)}"]

        self.assertIn("__qoderZhFix", guard)
        self.assertIn("TextDecoder", guard)
        self.assertIn("\\u4e00-\\u9fff", guard)
        self.assertIn("H.map(__qoderZhFix)", guard)

    def test_ui_replacements_include_interactive_mode_terms(self):
        replacements = dict(json.loads((QODER_PATCH_DIR / "ui.replacements.json").read_text(encoding="utf-8")))

        self.assertEqual(replacements['"  Type your message or @path/to/file"'], '"  输入消息或 @path/to/file"')
        self.assertEqual(replacements['"  Type your shell command"'], '"  输入 Shell 命令"')
        self.assertEqual(replacements['`Welcome to ${R$}`'], '`欢迎使用 ${R$}`')
        self.assertEqual(replacements['title:"Do you trust the files in this folder?"'], 'title:"是否信任此文件夹中的文件？"')
        self.assertEqual(replacements['placeholder:"Enter your response"'], 'placeholder:"输入回复"')
        self.assertEqual(
            replacements['description:"Resume a session by identifier, or open the session browser"'],
            'description:"通过标识符恢复会话，或打开会话浏览器"',
        )
        self.assertEqual(replacements['`${R$} Help:`'], '`${R$} 帮助：`')
        self.assertEqual(replacements["Available sessions for this project"], "当前项目可用会话")


class QoderShimTests(unittest.TestCase):
    def test_profile_discovery_includes_current_user_fallback_paths(self):
        failed_result = mock.Mock(returncode=1, stdout="")

        with (
            mock.patch.object(extract_bundle.subprocess, "run", return_value=failed_result),
            mock.patch.dict(os.environ, {"USERPROFILE": r"C:\Users\TestUser", "HOME": ""}),
            mock.patch.object(extract_bundle.Path, "home", return_value=Path(r"C:\Users\TestUser")),
        ):
            profiles = extract_bundle._get_ps_profile_paths()

        paths = {path for _, path in profiles}
        self.assertIn(Path(r"C:\Users\TestUser\Documents\PowerShell\Microsoft.PowerShell_profile.ps1"), paths)
        self.assertIn(Path(r"C:\Users\TestUser\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1"), paths)

    def test_powershell_shim_sets_and_restores_utf8_console_state(self):
        shim = extract_bundle.PS_SHIM

        self.assertIn(extract_bundle.SHIM_VERSION_MARKER, shim)
        self.assertIn("ConvertFrom-QoderUtf8Mojibake", shim)
        self.assertIn("[System.Diagnostics.ProcessStartInfo]::new()", shim)
        self.assertIn("chcp 65001", shim)
        self.assertIn("[Console]::OutputEncoding", shim)
        self.assertIn("[Console]::InputEncoding", shim)
        self.assertIn("$env:LC_ALL = \"en_US.UTF-8\"", shim)
        self.assertIn("$env:PYTHONIOENCODING = \"utf-8\"", shim)
        self.assertIn("try {", shim)
        self.assertIn("finally {", shim)
        self.assertIn("& $bunExe run $extractedJs @args", shim)
        self.assertIn("bun.exe", shim)

    def test_outdated_shim_detection_requires_current_marker_and_encoding_guards(self):
        self.assertFalse(extract_bundle._is_shim_outdated(extract_bundle.PS_SHIM))

        old_shim = f"""
{extract_bundle.SHIM_MARKER}
function qodercli {{
    $bunExe = "$env:LOCALAPPDATA\\Kiro-Cli\\bun"
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    & $bunExe run $extractedJs @args
}}
# Qoder CLI 汉化版 - 结束
"""
        self.assertTrue(extract_bundle._is_shim_outdated(old_shim))


class QoderRuntimeResourceTests(unittest.TestCase):
    def test_embedded_file_record_scanner_finds_bun_virtual_resources(self):
        payload = (
            b"\x00B:/~BUN/root/sandbox-default-hsamzg57.toml\x00[modes.plan]\nnetwork = false\n"
            b"\x00B:/~BUN/root/SKILL-d480nw1n.md\x00---\nname: skill-creator\n"
        )
        data = struct.pack("<Q", len(payload)) + payload

        records = extract_bundle._iter_embedded_file_records(data, {"raw_offset": 0})

        self.assertEqual(
            records,
            [
                ("B:/~BUN/root/sandbox-default-hsamzg57.toml", b"[modes.plan]\nnetwork = false\n"),
                ("B:/~BUN/root/SKILL-d480nw1n.md", b"---\nname: skill-creator\n"),
            ],
        )

    def test_rewrite_virtual_paths_points_index_to_local_resource_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            index_js = output_dir / "index.js"
            index_js.write_text('var p="B:/~BUN/root/sandbox-default-hsamzg57.toml";', encoding="utf-8")

            changed = extract_bundle.rewrite_virtual_paths(output_dir)

            self.assertTrue(changed)
            text = index_js.read_text(encoding="utf-8")
            self.assertIn((output_dir / extract_bundle.VIRTUAL_ROOT_DIR / "sandbox-default-hsamzg57.toml").resolve().as_posix(), text)
            self.assertNotIn("B:/~BUN/root/", text)


class QoderPatchArgsTests(unittest.TestCase):
    def test_patch_script_accepts_no_shim_flag(self):
        with mock.patch.object(sys, "argv", ["patch_app_zh.py", "--dry-run", "--no-shim"]):
            args = patch_app_zh.parse_args()

        self.assertTrue(args.dry_run)
        self.assertTrue(args.no_shim)


if __name__ == "__main__":
    unittest.main()
