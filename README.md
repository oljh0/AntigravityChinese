# AntigravityChinese (Antigravity IDE 汉化补丁)

这是一个为 Antigravity IDE 提供中文汉化的项目。包含两种汉化机制，可以根据您的使用环境进行选择：

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

## 2. 本地热更新脚本（`patch_zh.py`）
- **适用场景**：主要适用于开发者用来在本地快速打补丁。当前默认配置的路径适用于 **Windows 环境**。
- **说明**：在这个独立的 Python 脚本中，当前自动推导 Windows 下 `LOCALAPPDATA` 中的 Antigravity 默认安装路径进行处理（例如 `C:\Users\用户名\AppData\Local\Programs\Antigravity\resources\app`）。
- **强制更新功能**：脚本已内置安全的强制更新（热更新）逻辑。
  - **首次使用**：会自动备份您的纯英文原始文件（后缀为 `.bak`）。
  - **后续更新**：如果检测到备份已存在，将自动先恢复英文原版文件，然后再应用全量最新的中文词条补丁。无需担心多次应用会导致汉化文本冲突。

### Python 脚本使用指南

**应用 / 强制更新汉化**：
```bash
python patch_zh.py
```
*(无论是否曾汉化过，此命令都将确保以安全的姿态为您应用最新的汉化包)*

**撤销汉化，彻底还原英文版**：
```bash
python patch_zh.py --revert
```