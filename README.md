# AntigravityChinese (Antigravity IDE 汉化补丁)

这是一个同时服务于 **Antigravity 客户端汉化** 与 **Copilot CLI `app.js` 翻译补丁** 的项目。

当前结构按用途分为三层：

- `extension.js` + `translations\`：Antigravity 扩展与共享翻译资源
- `scripts\antigravity\` / `scripts\copilot_cli\`：按产品拆分的补丁脚本
- `scripts\shared\`：共享生成工具

为兼容旧用法，仓库根目录仍保留 `patch_zh.py`、`patch_app_zh.py`、`generate_replacements.py` 作为薄包装入口。

## 1. 自动汉化扩展插件（推荐）
- **适用场景**：这是作为 VS Code/Antigravity 扩展提供给用户的核心文件，具备优秀的跨平台适用性（支持 Windows、macOS 和 Linux）。
- **工作机制**：当扩展激活时，它会自动推导和寻找 IDE 的核心安装路径，并在后台动态应用硬编码文本的汉化替换。每次 Antigravity 更新后，只需重新加载窗口即可自动重新打补丁。因此它是最自动化及普适的方式。

### ✨ 扩展插件打包与安装指南
基于现有的项目文件，您可以通过 `@vscode/vsce` 将其打包成为一个可直接分发安装的 `.vsix` 文件：

1. **环境准备**：请确保您的系统已安装 [Node.js](https://nodejs.org/)。
2. **执行打包**：在项目根目录下，运行以下免安装依赖打包命令：
   ```bash
   npx -y @vscode/vsce package --no-dependencies
   ```
3. **完成打包**：命令执行成功后，会在当前目录下生成一个类似 `antigravitychinese-0.0.1.vsix`（版本号取决于 `package.json` 中的设置）的安装包文件。
4. **进行安装**：
   - 打开您的 Antigravity IDE，进入侧边栏的 **Extensions (扩展)** 面板。
   - 点击右上角的 `...` 菜单，选择 **Install from VSIX...**。
   - 在弹出的文件选择器中选择刚刚生成的 `.vsix` 文件。
5. **生效**：安装完成后，**完全重新启动 IDE** 或执行 **Reload Window (重新加载窗口)** 命令即可生效。

---

## 2. 本地热更新脚本（`scripts\antigravity\patch_zh.py` / `scripts\copilot_cli\patch_app_zh.py`）
- **适用场景**：主要适用于开发者用来在本地快速打补丁。当前默认配置的路径适用于 **Windows 环境**。
- **说明**：在这个独立的 Python 脚本中，当前自动推导 Windows 下 `LOCALAPPDATA` 中的 Antigravity 默认安装路径进行处理（例如 `C:\Users\用户名\AppData\Local\Programs\Antigravity\resources\app`）。
- **强制更新功能**：脚本已内置安全的强制更新（热更新）逻辑。
  - **首次使用**：会自动备份您的纯英文原始文件（后缀为 `.bak`）。
  - **后续更新**：如果检测到备份已存在，将自动先恢复英文原版文件，然后再应用全量最新的中文词条补丁。无需担心多次应用会导致汉化文本冲突。
  - **共享词条源**：硬编码字符串替换规则按产品拆分存放：`translations\patches\antigravity\*.replacements.json` 与 `translations\patches\copilot_cli\app.replacements.json`。
  - **`scripts\copilot_cli\patch_app_zh.py`**：默认会自动发现 `%USERPROFILE%\.copilot\pkg\universal\*\app.js` 中**最新且实际存在**的版本目录，不再依赖写死版本号；同时仍支持通过 `--target` 显式指定目标文件，并可通过 `--copilot-home` 覆盖 `.copilot` 根目录。

### Python 脚本使用指南

**应用 / 强制更新汉化**：
```bash
python scripts\antigravity\patch_zh.py
```
*(无论是否曾汉化过，此命令都将确保以安全的姿态为您应用最新的汉化包)*

**撤销汉化，彻底还原英文版**：
```bash
python scripts\antigravity\patch_zh.py --revert
```

**更新 Copilot `app.js` 翻译**：
```bash
python scripts\copilot_cli\patch_app_zh.py
```

**仅检查 Copilot `app.js` 翻译，不写入文件**：
```bash
python scripts\copilot_cli\patch_app_zh.py --dry-run
```

**恢复 Copilot `app.js` 原文件**：
```bash
python scripts\copilot_cli\patch_app_zh.py --revert
```

**指定自定义 Copilot 目录**：
```bash
python scripts\copilot_cli\patch_app_zh.py --copilot-home D:\Custom\.copilot
```

### 词条生成脚本

如果你更新了 `datafiles` 里的英文原文件或对应翻译结果，可以运行下面的脚本自动整理共享词条：

```bash
python scripts\shared\generate_replacements.py
```

它会基于 `datafiles` 下 `.bak` 与 `.js` 的对照，更新 `translations\patches\antigravity` 里的 JSON 替换表，并在写回后自动校验能否准确还原目标翻译结果。

如果你习惯旧命令，也可以继续使用根目录兼容入口：

```bash
python patch_zh.py
python patch_app_zh.py --dry-run
python generate_replacements.py
```
