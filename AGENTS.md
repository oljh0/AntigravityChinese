# Repository Guidelines

## Project Structure & Module Organization

This repository builds a Simplified Chinese language pack and patching tools for the Antigravity IDE, the Antigravity Hub desktop app, plus Copilot, Gemini, Kiro, and Qoder CLIs. `extension.js` is the VS Code/Antigravity extension entry point. Translation assets live in `translations/`: `extensions/` holds official i18n JSON files, while `patches/` holds replacement tables grouped by product, such as `ide/antigravity`, `hub/antigravity`, and `cli/qoder`. Python patching and extraction tools live in `scripts/`, split into `ide/`, `hub/`, `cli/`, and shared helpers in `scripts/shared/`. Tests are under `tests/`, with a few legacy root-level test files. `datafiles/` stores source comparison data used to generate replacement tables.

Note: since Antigravity 2.x the Hub app (`Programs/Antigravity`, Electron shell + embedded web UI served by `resources/bin/language_server.exe`) and the IDE kernel (`Programs/Antigravity IDE`) are separate installs. Hub patching unpacks `resources/app.asar` into an `app/` directory, patches native UI strings, and installs a web-UI dictionary translator under `resources/zh-patch/`.

## Build, Test, and Development Commands

- `npx -y @vscode/vsce package --no-dependencies`: package the extension into a `.vsix` file.
- `python -m pytest tests test_chinese_output.py test_gbk_output.py`: run the automated test suite.
- `python scripts/shared/generate_replacements.py`: regenerate replacement JSON from `datafiles/`.
- `python scripts/ide/antigravity/patch_zh.py --dry-run`: preview IDE patch matches without modifying installed files.
- `python scripts/hub/antigravity/patch_hub_zh.py --dry-run`: preview Hub asar unpack and native patch matches.
- `python scripts/cli/gemini/patch_app_zh.py --dry-run`: preview Gemini CLI patching.
- `python scripts/cli/kiro/patch_app_zh.py --dry-run`: preview Kiro binary equal-length replacements.
- `python scripts/cli/qoder/extract_bundle.py`: extract Qoder's Bun bundle and configure the shell shim.
- `python scripts/cli/qoder/patch_app_zh.py --dry-run`: preview Qoder JS bundle replacements.

## Coding Style & Naming Conventions

Use UTF-8 for all source and translation files. JavaScript uses CommonJS (`require`) and 4-space indentation in `extension.js`; keep extension commands under the `antigravity-zh.*` namespace. Python scripts should use `pathlib.Path`, explicit UTF-8 file I/O, and small product-specific modules backed by shared utilities. Name replacement files as `<scope>.replacements.json` and keep entries as two-item arrays: `[source, translation]`.

## Bilingual Guide Maintenance

`AGENTS.md` is the English contributor guide. `AGENTS-CN.md` is the Chinese annotated counterpart. Any contributor who changes one file must update the other in the same PR so structure, commands, and workflow requirements stay consistent.

## Testing Guidelines

Tests use `unittest` style and are normally executed with `pytest`. Add tests near the behavior changed, especially path discovery, replacement loading, encoding handling, and resource layout. Prefer temporary directories for patch tests so installed tools and user files are not touched. Test names may include Chinese descriptions when they clarify the expected behavior.

## Commit & Pull Request Guidelines

Recent history uses Conventional Commit prefixes such as `fix(qoder): ...` and `feat(kiro): ...`, with concise Chinese summaries. Follow that pattern and scope commits by product or subsystem. Pull requests should describe the affected product, list generated translation files, include test results, and mention any manual `--dry-run` or VSIX validation. Include screenshots only for visible IDE translation changes.

## Safety & Configuration Tips

Patch commands can edit external installations. Use `--dry-run` first, rely on built-in backup/revert support, and avoid committing generated `.vsix` files unless intentionally releasing a packaged version.
