# AntigravityChinese (Antigravity IDE 汉化补丁)

[![Version](https://img.shields.io/badge/version-1.0.3-green.svg)](package.json)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

本项目致力于为 **Antigravity** 提供全方位的简体中文本地化支持。它不仅包含官方扩展的翻译，还通过自动补丁技术汉化了 IDE 核心中硬编码的字符串。自 Antigravity 2.x 起，**「Antigravity 主程序（Hub）」与「Antigravity IDE」是两个独立应用**，本项目对两者均提供汉化。同时，本项目也为 **GitHub Copilot CLI**、**Google Gemini CLI**、**Kiro CLI** 和 **Qoder CLI** 提供汉化支持。

## 🌟 核心特性

- **全方位汉化**：涵盖 IDE 菜单、设置、聊天界面及核心工作台；Hub 主程序的原生菜单/托盘/对话框与网页主界面。
- **自动化补丁**：内置扩展插件自动识别安装路径，一键应用补丁。
- **Hub 网页词典翻译**：Hub 主界面内嵌于 `language_server.exe`，通过安装词典翻译组件（DOM 文本 + placeholder/aria 等属性 + 动态内容监听）实现汉化，词典热更新（改完 `Ctrl+R` 即生效）。
- **自动更新屏蔽**：可选屏蔽 IDE 自动更新，防止汉化失效。
- **多产品支持**：除了 Antigravity IDE/Hub，还支持 Copilot、Gemini、Kiro 和 Qoder CLI 的汉化。
- **安全可靠**：自动备份原始文件，支持随时还原。
- **跨平台**：支持 Windows、macOS 和 Linux。

---

## 🚀 快速开始：使用汉化扩展插件（推荐）

这是最简单、最自动化的汉化方式。

### 1. 打包与安装
1. **安装环境**：确保系统中已安装 [Node.js](https://nodejs.org/)。
2. **生成安装包**：在项目根目录下运行：
   ```bash
   npx -y @vscode/vsce package --no-dependencies
   ```
3. **安装扩展**：
   - 打开 Antigravity IDE。
   - 进入 **Extensions (扩展)** 面板。
   - 点击右上角 `...` → **Install from VSIX...**。
   - 选择生成的 `.vsix` 文件。
4. **生效**：安装后重启 IDE，扩展会自动检测并尝试应用补丁。

### 2. 手动管理补丁
您也可以通过命令面板（`Ctrl+Shift+P`）手动执行以下命令：
- `Antigravity 中文: 应用中文汉化补丁`
- `Antigravity 中文: 恢复英文原始文件`
- `Antigravity 中文: 切换屏蔽 Antigravity 自动更新`

### 3. 汉化 Antigravity 主程序 (Hub)
Hub 是独立于 IDE 的智能体桌面应用（Electron 外壳 `%LOCALAPPDATA%\Programs\Antigravity`，主界面由内嵌网页提供）。扩展提供两个命令：
- `Antigravity 中文: 汉化 Antigravity 主程序 (Hub)`
- `Antigravity 中文: 恢复 Antigravity 主程序英文原版`

补丁原理：将 `resources/app.asar` 解包为 `app/` 目录（Electron 优先加载目录，原包保留为 `app.asar.orig`），汉化原生菜单/托盘/对话框，并在 `resources/zh-patch/` 安装网页词典翻译组件。词典文件 `cockpit-zh.json` 支持热更新，修改后在 Hub 内 `Ctrl+R` 重载窗口即生效。注意：打补丁前需完全退出 Hub（含托盘图标）；Hub 自动更新后补丁会失效，重新执行即可。也可开启设置项 `antigravity-zh.patchHubApp` 让扩展在启动时自动补丁（Hub 未运行时）。

---

## 🛠️ 高级工具：CLI 汉化脚本

适用于开发者或需要对 CLI 工具进行汉化的场景。

### Antigravity IDE 汉化
```bash
python scripts/ide/antigravity/patch_zh.py
```
*该脚本会自动备份原文件并在更新时安全地重新应用补丁。自动发现新版 `Programs/Antigravity IDE` 与旧版 `Programs/Antigravity` 布局，也可用 `--target` 手动指定。*

### Antigravity 主程序 (Hub) 汉化
```bash
python scripts/hub/antigravity/patch_hub_zh.py
```
解包 `resources/app.asar` → 汉化原生 UI → 安装网页词典翻译组件。支持 `--dry-run`（预览）、`--revert`（恢复英文）、`--target <resources 目录>`（覆盖自动发现）、`--force`（跳过运行中检查）。原生替换表位于 `translations/patches/hub/antigravity/*.replacements.json`，网页词典为 `webui.dictionary.json`（dict 精确匹配 + rules 动态正则）。

### Copilot CLI 汉化
```bash
python scripts/cli/copilot/patch_app_zh.py
```
自动发现 `%USERPROFILE%\.copilot\pkg\universal\*\app.js` 中最新版本并应用补丁。

### Gemini CLI 汉化
```bash
python scripts/cli/gemini/patch_app_zh.py
```
自动发现 Gemini CLI 安装路径（支持 `GEMINI_CLI_HOME` 环境变量、`Program Files` 和 `APPDATA` 路径），同时处理主包和 `gemini-cli-core` 子包。

### Kiro CLI 汉化
```bash
python scripts/cli/kiro/patch_app_zh.py
```
默认处理 `C:\Program Files\Kiro-Cli\kiro-cli.exe`，也可通过 `KIRO_CLI_HOME` 或 `--target` 指定路径。Kiro CLI 是 Bun standalone 可执行文件，脚本会对二进制中的 UTF-8 明文字符串做等长替换；不等长词条会自动跳过，避免破坏可执行文件。

辅助维护词条时可扫描当前可执行文件：
```bash
python scripts/cli/kiro/extract_strings.py --diff
```

### Qoder CLI 汉化
```bash
python scripts/cli/qoder/extract_bundle.py
python scripts/cli/qoder/patch_app_zh.py
```
`extract_bundle.py` 会自动发现 `qodercli.exe`，提取 Bun `.bun` 节区中的 JS bundle 到 `%USERPROFILE%\.qoder\extracted`，并配置终端启动劫持，让 `qodercli` 指向汉化后的 `index.js`。Qoder CLI 的 `--help` 文本来自这个已提取的 JS bundle，不来自 `datafiles/`。`patch_app_zh.py` 会对已提取的 JS 文件应用文本替换；正式补丁成功后默认安装/升级终端启动劫持，使用 `--no-shim` 可只补丁 bundle。`--dry-run` 仅检查现有提取目录，不会提取、写入 JS 或修改 profile。

如果 PowerShell/Windows Terminal 中 `qodercli --help` 或交互界面仍然乱码，先确认 `Get-Command qodercli` 解析到 `Function`，而不是 npm 安装的 `qodercli.ps1`。新版 shim 会临时切换 active code page 到 65001 并设置 Console 输入/输出编码；Qoder bundle 还会补丁 stdout/stderr 写入入口，对交互模式和 `--list-sessions` 这类非帮助输出做 UTF-8 mojibake 纠偏。未生效时重新运行 `python scripts/cli/qoder/patch_app_zh.py` 以升级 profile 配置并重写 bundle。

辅助维护词条时可扫描已提取的 bundle：
```bash
python scripts/cli/qoder/extract_strings.py --diff
```

### 常用选项
| 选项 | 说明 |
|------|------|
| `--revert` | 撤销汉化，从 `.bak` 备份恢复原始英文版 |
| `--dry-run` | 仅检查匹配情况，不修改文件 |
| `--target <路径>` | 手动指定目标文件或目录（覆盖自动发现） |

---

## ⚡ 环境配置：Gemini CLI 子终端编码

在 Windows 下使用 Gemini CLI 时，为避免子终端中文乱码，建议在 **PowerShell Profile** 中添加以下内容：

```powershell
# 解决 Gemini CLI 子终端中文乱码
$env:PYTHONIOENCODING = "utf-8"
$env:LANG = 'en_US.UTF-8'
chcp 65001 > $null
```

> **原理**：`chcp 65001` 使 Gemini CLI 的编码探测模块 (`systemEncoding.js`) 自然返回 `utf-8`，`LANG` 环境变量通过白名单传递到 PTY 子进程。无需修改任何源文件即可解决编码问题。

---

## 📁 项目结构

```
AntigravityChinese/
├── extension.js                  # IDE 扩展核心：自动补丁引擎（含 Hub 补丁命令）
├── package.json                  # 扩展清单与元数据
├── README.md
│
├── scripts/                      # 各产品独立补丁脚本
│   ├── cli/
│   │   ├── copilot/
│   │   │   └── patch_app_zh.py   # Copilot CLI 汉化脚本
│   │   ├── gemini/
│   │   │   └── patch_app_zh.py   # Gemini CLI 汉化脚本
│   │   ├── kiro/
│   │   │   ├── patch_app_zh.py   # Kiro CLI 二进制汉化脚本
│   │   │   └── extract_strings.py # Kiro CLI 字符串提取工具
│   │   └── qoder/
│   │       ├── extract_bundle.py  # Qoder CLI Bun bundle 提取与启动配置
│   │       ├── patch_app_zh.py    # Qoder CLI JS bundle 汉化脚本
│   │       └── extract_strings.py # Qoder CLI 字符串提取工具
│   ├── hub/
│   │   └── antigravity/
│   │       ├── patch_hub_zh.py    # Hub 主程序 asar 解包+汉化脚本
│   │       └── assets/
│   │           └── zh-i18n.js     # Hub 网页 UI 词典翻译注入组件
│   ├── ide/
│   │   └── antigravity/
│   │       └── patch_zh.py       # IDE 汉化脚本
│   └── shared/
│       ├── patch_utils.py        # 共享工具：备份、替换、终端初始化
│       └── generate_replacements.py  # 从对照数据生成替换表
│
├── translations/                 # 所有翻译资源
│   ├── extensions/               # 官方扩展 i18n 翻译 (JSON)
│   │   ├── google.antigravity.i18n.json
│   │   ├── google.antigravity-browser-launcher.i18n.json
│   │   └── ...
│   └── patches/                  # 硬编码字符串替换规则
│       ├── cli/
│       │   ├── copilot/          # Copilot CLI 替换表
│       │   ├── gemini/           # Gemini CLI 替换表 (common/main/ui/qwen)
│       │   ├── kiro/             # Kiro CLI 替换表 (common/main/ui)
│       │   └── qoder/            # Qoder CLI 替换表 (common/main/ui)
│       ├── hub/
│       │   └── antigravity/      # Hub 主程序替换表 + webui.dictionary.json 网页词典
│       └── ide/
│           └── antigravity/      # IDE 替换表
│
├── tests/                        # 自动化测试
│   ├── test_patch_app_zh.py      # Copilot 补丁脚本测试
│   ├── test_patch_hub_zh.py      # Hub 补丁脚本测试（合成 asar 全链路）
│   ├── test_patch_gemini_zh.py   # Gemini 补丁脚本测试
│   ├── test_copilot_cli_doc_pairs.py
│   └── test_translation_resource_layout.py
│
└── datafiles/                    # 原始文件对照数据 (用于生成替换表)
```

---

## 🤝 贡献与反馈

如果您发现了遗漏的翻译或有任何改进建议，欢迎提交 Issue 或 Pull Request。

### 开发流程

1. **更新对照数据**：编辑 `datafiles/` 中的原始文件。
2. **生成替换表**：运行 `python scripts/shared/generate_replacements.py` 同步更新 `translations/patches/` 下的替换规则。
3. **运行测试**：执行 `pytest tests/` 确保补丁脚本正常工作。
4. **验证效果**：使用 `--dry-run` 模式预览变更，确认后正式应用。

---

## 📄 开源协议

本项目采用 [MIT License](https://opensource.org/licenses/MIT) 开源。
