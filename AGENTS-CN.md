# Repository Guidelines

## 项目结构与模块组织

本仓库为 Antigravity IDE、Antigravity 主程序（Hub 桌面应用）以及 Copilot、Gemini、Kiro、Qoder CLI 提供简体中文语言包和补丁工具。`extension.js` 是 VS Code/Antigravity 扩展入口。翻译资源位于 `translations/`：`extensions/` 保存官方 i18n JSON，`patches/` 按产品保存硬编码字符串替换表，例如 `ide/antigravity`、`hub/antigravity` 和 `cli/qoder`。Python 补丁和提取工具位于 `scripts/`，按 `ide/`、`hub/`、`cli/` 拆分，共享工具在 `scripts/shared/`。测试位于 `tests/`，根目录还保留少量历史测试文件。`datafiles/` 保存用于生成替换表的原始对照数据。

注意：Antigravity 2.x 起，Hub 主程序（`Programs/Antigravity`，Electron 外壳，主界面由 `resources/bin/language_server.exe` 内嵌网页提供）与 IDE 内核（`Programs/Antigravity IDE`）是两个独立安装。Hub 补丁会解包 `resources/app.asar` 为 `app/` 目录、汉化原生 UI 字符串，并在 `resources/zh-patch/` 安装网页词典翻译组件。

## 构建、测试与开发命令

- `npx -y @vscode/vsce package --no-dependencies`：打包生成 `.vsix` 扩展文件。
- `python -m pytest tests test_chinese_output.py test_gbk_output.py`：运行自动化测试。
- `python scripts/shared/generate_replacements.py`：从 `datafiles/` 重新生成替换 JSON。
- `python scripts/ide/antigravity/patch_zh.py --dry-run`：预览 IDE 补丁匹配情况，不修改安装文件。
- `python scripts/hub/antigravity/patch_hub_zh.py --dry-run`：预览 Hub 主程序 asar 解包与原生补丁匹配情况。
- `python scripts/cli/gemini/patch_app_zh.py --dry-run`：预览 Gemini CLI 汉化。
- `python scripts/cli/kiro/patch_app_zh.py --dry-run`：预览 Kiro 二进制等长替换。
- `python scripts/cli/qoder/extract_bundle.py`：提取 Qoder 的 Bun bundle 并配置终端 shim。
- `python scripts/cli/qoder/patch_app_zh.py --dry-run`：预览 Qoder JS bundle 替换。

## 编码风格与命名约定

所有源码和翻译文件使用 UTF-8。JavaScript 使用 CommonJS (`require`)，`extension.js` 采用 4 空格缩进；扩展命令保持 `antigravity-zh.*` 命名空间。Python 脚本优先使用 `pathlib.Path`、显式 UTF-8 文件读写，以及产品独立模块加共享工具的结构。替换表命名为 `<scope>.replacements.json`，条目保持二元数组格式：`[source, translation]`。

## 双语指南维护

`AGENTS.md` 是英文贡献者指南，`AGENTS-CN.md` 是中文注解版。修改任一文件时，必须在同一个 PR 中同步更新另一份文件，确保章节结构、命令示例和流程要求保持一致。

## 测试指南

测试使用 `unittest` 风格，通常通过 `pytest` 执行。改动路径发现、替换加载、编码处理或资源目录布局时，应在相邻测试中补充覆盖。补丁测试优先使用临时目录，避免触碰用户真实安装和文件。测试名可以包含中文描述，只要能更清楚表达预期行为。

## Commit 与 Pull Request 指南

近期历史采用 Conventional Commit 前缀，例如 `fix(qoder): ...` 和 `feat(kiro): ...`，摘要多为简洁中文说明。提交应按产品或子系统划分 scope。PR 需说明影响的产品、列出生成的翻译文件、附上测试结果，并注明是否执行过 `--dry-run` 或 VSIX 验证。只有涉及可见 IDE 翻译变化时才需要截图。

## 安全与配置提示

补丁命令可能修改外部安装目录。正式写入前先运行 `--dry-run`，依赖脚本内置备份与恢复能力；除非发布打包版本，否则不要提交生成的 `.vsix` 文件。
