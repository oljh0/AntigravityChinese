import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PATCH_PATH = REPO_ROOT / "translations" / "patches" / "copilot_cli" / "app.replacements.json"

EXPECTED_KEYS = {
    "help:\"Display changelog for CLI versions. Add 'summarize' to get an AI summary.\"",
    "help:\"Display version information and check for updates\"",
    "help:\"Manage CLI extensions\"",
    "help:\"View or set color mode\"",
    "description:\"cancel / clear input / copy selection\"",
    "description:\"Cancel\"",
    "description:\"exit from the CLI\"",
    "text:\"No changelogs found.\"",
    "text:\"Usage: /lsp test <server-name>\"",
    "text:\"Usage: /mcp delete <server-name>\"",
    "text:\"Init suggestion is already suppressed for this repository.\"",
    "text:\"Init suggestion suppressed for this repository.\"",
    "text:`Failed to share session: ${de(a)}`",
    "text:`Created agent at ${rs}`",
    "text:\"Loading extensions...\"",
    "title:\"Hook permission request\"",
    "title:\"Reloading extensions\"",
    "title:\"Managing extensions\"",
    "label:\"User\"",
    "label:\"Repository\"",
    "label:\"Working Directory\"",
    "label:\"Yes, and add these directories to the allowed list\"",
    "label:\"Running\"",
    "`${m} background /tasks`",
    '$c.default.createElement(H,{bold:!0},"right-click")," copy"',
    '$c.default.createElement(H,{bold:!0},"ctrl+c")," again to exit"',
}


class CopilotCliDocPairsTests(unittest.TestCase):
    def test_当前文档对应的关键可见文案已有配对翻译(self):
        replacements = json.loads(PATCH_PATH.read_text(encoding="utf-8"))
        old_values = {pair[0] for pair in replacements}

        missing = sorted(EXPECTED_KEYS - old_values)
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
