# AntigravityChinese (Antigravity IDE 汉化补丁)

[![Version](https://img.shields.io/badge/version-1.0.3-green.svg)](package.json)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

本项目致力于为 **Antigravity IDE** 提供全方位的简体中文本地化支持。它不仅包含官方扩展的翻译，还通过自动补丁技术汉化了 IDE 核心中硬编码的字符串。同时，本项目也为 **GitHub Copilot CLI** 和 **Google Gemini CLI** 提供汉化支持。

## 🌟 核心特性

- **全方位汉化**：涵盖 IDE 菜单、设置、聊天界面及核心工作台。
- **自动化补丁**：内置扩展插件自动识别安装路径，一键应用补丁。
- **自动更新屏蔽**：可选屏蔽 IDE 自动更新，防止汉化失效。
- **多产品支持**：除了 IDE，还支持 Copilot CLI 和 Gemini CLI 的汉化。
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

---

## 🛠️ 高级工具：CLI 汉化脚本

适用于开发者或需要对 CLI 工具进行汉化的场景。

### Antigravity IDE 汉化
```bash
python scripts/ide/antigravity/patch_zh.py
```
*该脚本会自动备份原文件并在更新时安全地重新应用补丁。*

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

### 常用选项
| 选项 | 说明 |
|------|------|
| `--revert` | 撤销汉化，从 `.bak` 备份恢复原始英文版 |
| `--dry-run` | 仅检查匹配情况，不修改文件 |
| `--target <路径>` | 手动指定目标目录（覆盖自动发现） |

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
├── extension.js                  # IDE 扩展核心：自动补丁引擎
├── package.json                  # 扩展清单与元数据
├── README.md
│
├── scripts/                      # 各产品独立补丁脚本
│   ├── cli/
│   │   ├── copilot/
│   │   │   └── patch_app_zh.py   # Copilot CLI 汉化脚本
│   │   └── gemini/
│   │       └── patch_app_zh.py   # Gemini CLI 汉化脚本
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
│       │   └── gemini/           # Gemini CLI 替换表 (common/main/ui)
│       └── ide/
│           └── antigravity/      # IDE 替换表
│
├── tests/                        # 自动化测试
│   ├── test_patch_app_zh.py      # Copilot 补丁脚本测试
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
