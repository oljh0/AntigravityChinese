# AntigravityChinese (Antigravity IDE 汉化补丁)

[![Version](https://img.shields.io/badge/version-1.0.3-green.svg)](package.json)

本项目致力于为 **Antigravity IDE** 提供全方位的简体中文本地化支持。它不仅包含官方扩展的翻译，还通过自动补丁技术汉化了 IDE 核心中硬编码的字符串。同时，本项目也为 **Copilot CLI** 和 **Gemini CLI** 提供汉化支持。

## 🌟 核心特性

- **全方位汉化**：涵盖 IDE 菜单、设置、聊天界面及核心工作台。
- **自动化补丁**：内置扩展插件自动识别安装路径，一键应用补丁。
- **自动更新屏蔽**：可选屏蔽 IDE 自动更新，防止汉化失效。
- **多产品支持**：除了 IDE，还支持 Copilot CLI 和 Gemini CLI 的汉化。
- **安全可靠**：自动备份原始文件，支持随时还原。

---

## 🚀 快速开始：使用汉化扩展插件（推荐）

这是最简单、最自动化的汉化方式，支持 Windows、macOS 和 Linux。

### 1. 打包与安装
1. **安装环境**：确保系统中已安装 [Node.js](https://nodejs.org/)。
2. **生成安装包**：在项目根目录下运行：
   ```bash
   npx -y @vscode/vsce package --no-dependencies
   ```
3. **安装扩展**：
   - 打开 Antigravity IDE。
   - 进入 **Extensions (扩展)** 面板。
   - 点击右上角 `...` -> **Install from VSIX...**。
   - 选择生成的 `.vsix` 文件。
4. **生效**：安装后重启 IDE，扩展会自动检测并尝试应用补丁。

### 2. 手动管理补丁
您也可以通过命令面板（`Ctrl+Shift+P`）手动执行以下命令：
- `Antigravity 中文: 应用中文汉化补丁`
- `Antigravity 中文: 恢复英文原始文件`
- `Antigravity 中文: 切换屏蔽 Antigravity 自动更新`

---

## 🛠️ 高级工具：本地热更新脚本

适用于开发者或需要对 CLI 工具进行汉化的场景。

### 1. Antigravity IDE 汉化
```bash
python scripts/ide/antigravity/patch_zh.py
```
*该脚本会自动备份原文件并在更新时安全地重新应用补丁。*

### 2. Copilot CLI 汉化
```bash
python scripts/cli/copilot/patch_app_zh.py
```

### 3. Gemini CLI 汉化
```bash
python scripts/cli/gemini/patch_app_zh.py
```

### 4. 常用选项
- `--revert`: 撤销汉化，恢复原始英文版。
- `--dry-run`: 仅检查匹配情况，不修改文件。

---

## 📁 项目结构

- `extension.js`: 核心扩展逻辑，负责 IDE 动态补丁。
- `translations/`: 存放所有翻译资源。
  - `extensions/`: 官方扩展的 i18n 翻译。
  - `patches/`: 硬编码字符串的替换规则。
- `scripts/`: 各产品的独立补丁脚本。
- `datafiles/`: 原始文件备份与对照数据。

---

## 🤝 贡献与反馈

如果您发现了遗漏的翻译或有任何改进建议，欢迎提交 Issue 或 Pull Request。

- **词条生成**：如果您更新了对照数据，运行 `python scripts/shared/generate_replacements.py` 即可同步更新替换表。

---

## 📄 开源协议
本项目采用 [MIT License](https://opensource.org/licenses/MIT) 开源。
