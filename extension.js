// Antigravity IDE 中文汉化插件 - 自动补丁引擎
// 在插件激活时自动检测并应用硬编码字符串的中文翻译

const vscode = require('vscode');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const child_process = require('child_process');

// ══════════════════════════════════════════════════════════════════════
// 路径配置
// ══════════════════════════════════════════════════════════════════════
function getAppBase() {
    // Antigravity.app 的 Resources/app 路径
    const candidates = [
        '/Applications/Antigravity.app/Contents/Resources/app',
        path.join(process.env.HOME || '', 'Applications/Antigravity.app/Contents/Resources/app'),
    ];
    for (const c of candidates) {
        if (fs.existsSync(c)) return c;
    }
    // Fallback: 从 vscode 的 appRoot 推导
    const appRoot = vscode.env.appRoot;
    if (appRoot && fs.existsSync(appRoot)) return appRoot;
    return null;
}

function getTargets(base) {
    return {
        settings: path.join(base, 'out', 'jetskiAgent', 'main.js'),
        chat: path.join(base, 'extensions', 'antigravity', 'out', 'media', 'chat.js'),
        workbench: path.join(base, 'out', 'vs', 'workbench', 'workbench.desktop.main.js'),
    };
}

// ══════════════════════════════════════════════════════════════════════
// 替换规则定义
// ══════════════════════════════════════════════════════════════════════

const REPLACEMENTS_DIR = path.join(__dirname, 'translations', 'patches', 'ide', 'antigravity');
const REPLACEMENT_FILES = {
    main: 'main.replacements.json',
    chat: 'chat.replacements.json',
    workbench: 'workbench.replacements.json',
};
const replacementCache = new Map();

function loadReplacements(name) {
    if (replacementCache.has(name)) {
        return replacementCache.get(name);
    }

    const filename = REPLACEMENT_FILES[name];
    if (!filename) {
        throw new Error(`未知替换组: ${name}`);
    }

    const filepath = path.join(REPLACEMENTS_DIR, filename);
    if (!fs.existsSync(filepath)) {
        throw new Error(`替换文件不存在: ${filepath}`);
    }
    
    const data = JSON.parse(fs.readFileSync(filepath, 'utf-8'));
    if (!Array.isArray(data) || data.some(pair => !Array.isArray(pair) || pair.length !== 2 || pair.some(item => typeof item !== 'string'))) {
        throw new Error(`替换表格式无效: ${filepath}`);
    }

    replacementCache.set(name, data);
    return data;
}

function getSettingsReplacements() {
    return loadReplacements('main');
}

function getChatReplacements() {
    return loadReplacements('chat');
}

function getWorkbenchReplacements() {
    return loadReplacements('workbench');
}

// ══════════════════════════════════════════════════════════════════════
// 补丁引擎
// ══════════════════════════════════════════════════════════════════════

const PATCH_VERSION = 'v43';
const PATCH_MARKER = `/* zh-hans-patched-${PATCH_VERSION} */`;

function getPatchVersion(filepath) {
    try {
        const head = fs.readFileSync(filepath, { encoding: 'utf-8', flag: 'r' }).slice(0, 200);
        const m = head.match(/\/\* zh-hans-patched-(v\d+) \*\//);
        return m ? m[1] : (head.includes('/* zh-hans-patched */') ? 'v0' : null);
    } catch {
        return null;
    }
}

function isPatchCurrent(filepath) {
    return getPatchVersion(filepath) === PATCH_VERSION;
}

function patchFile(filepath, replacements, name) {
    if (!fs.existsSync(filepath)) {
        return { name, success: 0, total: replacements.length, error: '文件不存在' };
    }

    let content = fs.readFileSync(filepath, 'utf-8');

    // Remove old patch markers
    content = content.replace(/\/\* zh-hans-patched[^*]*\*\/\n?/, '');

    // Create backup (from clean content if no backup exists)
    const backup = filepath + '.bak';
    if (!fs.existsSync(backup)) {
        fs.writeFileSync(backup, content, 'utf-8');
    }

    let count = 0;
    const failed = [];

    for (const [oldStr, newStr] of replacements) {
        if (content.includes(oldStr)) {
            content = content.split(oldStr).join(newStr);
            count++;
        } else if (!content.includes(newStr)) {
            // Not found AND translation not already present
            failed.push(oldStr.substring(0, 50));
        } else {
            // Translation already present, count as success
            count++;
        }
    }

    // Add patch marker
    content = PATCH_MARKER + '\n' + content;
    fs.writeFileSync(filepath, content, 'utf-8');

    return { name, success: count, total: replacements.length, failed };
}

function revertFile(filepath) {
    const backup = filepath + '.bak';
    if (fs.existsSync(backup)) {
        fs.copyFileSync(backup, filepath);
        return true;
    }
    return false;
}

function updateChecksums(base) {
    const productJsonPath = path.join(base, 'product.json');
    if (!fs.existsSync(productJsonPath)) return 0;

    // Backup original product.json (only once)
    const backup = productJsonPath + '.bak';
    if (!fs.existsSync(backup)) {
        fs.copyFileSync(productJsonPath, backup);
    }

    const raw = fs.readFileSync(productJsonPath, 'utf-8');
    const product = JSON.parse(raw);

    // Clear checksums entirely to prevent integrity check failures.
    // Antigravity checks these checksums on startup BEFORE extensions load,
    // so recalculating hashes doesn't help - we must remove them.
    if (product.checksums && Object.keys(product.checksums).length > 0) {
        product.checksums = {};
        fs.writeFileSync(productJsonPath, JSON.stringify(product, null, '\t'), 'utf-8');
        return 1;
    }

    return 0;
}

function revertChecksums(base) {
    const backup = path.join(base, 'product.json.bak');
    const target = path.join(base, 'product.json');
    if (fs.existsSync(backup)) {
        fs.copyFileSync(backup, target);
        return true;
    }
    return false;
}

// ══════════════════════════════════════════════════════════════════════
// 自动更新屏蔽
// ══════════════════════════════════════════════════════════════════════

const BLOCKED_UPDATE_URL = 'https://localhost.invalid/no-update';

function isAutoUpdateBlocked(base) {
    const productJsonPath = path.join(base, 'product.json');
    const backup = productJsonPath + '.bak';
    if (!fs.existsSync(productJsonPath)) return false;
    try {
        const product = JSON.parse(fs.readFileSync(productJsonPath, 'utf-8'));
        // 如果 updateUrl 不存在或为空，且备份中有原始 updateUrl，则说明已屏蔽
        if (!product.updateUrl && fs.existsSync(backup)) {
            const original = JSON.parse(fs.readFileSync(backup, 'utf-8'));
            return !!original.updateUrl;
        }
        return product.updateUrl === BLOCKED_UPDATE_URL;
    } catch {
        return false;
    }
}

function blockAutoUpdate(base) {
    const productJsonPath = path.join(base, 'product.json');
    if (!fs.existsSync(productJsonPath)) return false;

    // Ensure backup exists
    const backup = productJsonPath + '.bak';
    if (!fs.existsSync(backup)) {
        fs.copyFileSync(productJsonPath, backup);
    }

    try {
        const product = JSON.parse(fs.readFileSync(productJsonPath, 'utf-8'));
        if (product.updateUrl) {
            delete product.updateUrl;
            fs.writeFileSync(productJsonPath, JSON.stringify(product, null, '\t'), 'utf-8');
        }
        return true;
    } catch (e) {
        console.error('[antigravity-zh] 屏蔽更新失败:', e);
        return false;
    }
}

function unblockAutoUpdate(base) {
    const productJsonPath = path.join(base, 'product.json');
    const backup = productJsonPath + '.bak';

    if (!fs.existsSync(backup)) return false;

    try {
        // Read backup to get original updateUrl
        const original = JSON.parse(fs.readFileSync(backup, 'utf-8'));
        const product = JSON.parse(fs.readFileSync(productJsonPath, 'utf-8'));
        if (original.updateUrl) {
            product.updateUrl = original.updateUrl;
        }
        fs.writeFileSync(productJsonPath, JSON.stringify(product, null, '\t'), 'utf-8');
        return true;
    } catch (e) {
        console.error('[antigravity-zh] 恢复更新失败:', e);
        return false;
    }
}

// ══════════════════════════════════════════════════════════════════════
// Antigravity 主程序 (Hub) 汉化补丁
// ══════════════════════════════════════════════════════════════════════
// Antigravity 2.x 起 Hub 与 IDE 是两个独立应用：
// Hub = %LOCALAPPDATA%/Programs/Antigravity，Electron 外壳为 resources/app.asar，
// 主界面由 resources/bin/language_server.exe 内嵌网页提供。
// 补丁策略：解包 asar → app 目录（Electron 优先加载目录），原生 UI 直接改中文，
// 网页 UI 安装词典翻译组件 (resources/zh-patch) 由主进程注入。

const HUB_TRANSLATIONS_DIR = path.join(__dirname, 'translations', 'patches', 'hub', 'antigravity');
const HUB_ASSET_ZH_I18N = path.join(__dirname, 'scripts', 'hub', 'antigravity', 'assets', 'zh-i18n.js');

const HUB_NATIVE_TARGETS = {
    'utils.replacements.json': path.join('dist', 'utils.js'),
    'menu.replacements.json': path.join('dist', 'menu.js'),
    'main.replacements.json': path.join('dist', 'main.js'),
    'tray.replacements.json': path.join('dist', 'tray.js'),
    'updater.replacements.json': path.join('dist', 'updater.js'),
    'ipchandlers.replacements.json': path.join('dist', 'ipcHandlers.js'),
    'wizard.replacements.json': path.join('dist', 'ideInstall', 'wizardHtml.js'),
};

function getHubResourcesDir() {
    if (process.platform === 'win32') {
        const localAppData = process.env.LOCALAPPDATA;
        if (!localAppData) return null;
        return path.join(localAppData, 'Programs', 'Antigravity', 'resources');
    }
    if (process.platform === 'darwin') {
        const candidates = [
            '/Applications/Antigravity.app/Contents/Resources',
            path.join(process.env.HOME || '', 'Applications/Antigravity.app/Contents/Resources'),
        ];
        for (const c of candidates) {
            if (fs.existsSync(c)) return c;
        }
        return candidates[0];
    }
    return null;
}

function isHubProcessRunning() {
    if (process.platform !== 'win32') return false;
    try {
        const output = child_process.execFileSync(
            'tasklist', ['/FI', 'IMAGENAME eq Antigravity.exe'],
            { encoding: 'utf-8', timeout: 10000 }
        );
        return output.toLowerCase().includes('antigravity.exe');
    } catch {
        return false;
    }
}

function isHubPatched(resourcesDir) {
    if (!resourcesDir) return false;
    return fs.existsSync(path.join(resourcesDir, 'app.asar.orig'))
        && fs.existsSync(path.join(resourcesDir, 'app'))
        && fs.existsSync(path.join(resourcesDir, 'zh-patch', 'zh-i18n.js'))
        && fs.existsSync(path.join(resourcesDir, 'zh-patch', 'cockpit-zh.json'));
}

function readAsarHeader(asarPath) {
    const fd = fs.openSync(asarPath, 'r');
    try {
        const pre = Buffer.alloc(16);
        fs.readSync(fd, pre, 0, 16, 0);
        const pickleLen = pre.readUInt32LE(4);
        const jsonLen = pre.readUInt32LE(12);
        const jsonBuf = Buffer.alloc(jsonLen);
        fs.readSync(fd, jsonBuf, 0, jsonLen, 16);
        return { header: JSON.parse(jsonBuf.toString('utf-8')), dataBase: 8 + pickleLen, fd };
    } catch (e) {
        fs.closeSync(fd);
        throw e;
    }
}

function unpackHubAsar(asarPath, outDir, unpackedRoot) {
    const { header, dataBase, fd } = readAsarHeader(asarPath);
    let fromAsar = 0, fromUnpacked = 0;
    try {
        const walk = (node, rel) => {
            for (const [name, meta] of Object.entries(node.files || {})) {
                const relPath = rel ? `${rel}/${name}` : name;
                const outPath = path.join(outDir, relPath);
                if (meta.files) {
                    fs.mkdirSync(outPath, { recursive: true });
                    walk(meta, relPath);
                } else if (meta.unpacked) {
                    if (unpackedRoot) {
                        fs.mkdirSync(path.dirname(outPath), { recursive: true });
                        fs.copyFileSync(path.join(unpackedRoot, relPath), outPath);
                        fromUnpacked++;
                    }
                } else {
                    const buf = Buffer.alloc(meta.size);
                    fs.readSync(fd, buf, 0, meta.size, dataBase + parseInt(meta.offset, 10));
                    fs.mkdirSync(path.dirname(outPath), { recursive: true });
                    fs.writeFileSync(outPath, buf);
                    fromAsar++;
                }
            }
        };
        fs.mkdirSync(outDir, { recursive: true });
        walk(header, '');
    } finally {
        fs.closeSync(fd);
    }
    return { fromAsar, fromUnpacked };
}

function patchHubNativeFile(filepath, replacements) {
    let content = fs.readFileSync(filepath, 'utf-8');
    let applied = 0;
    const failed = [];
    for (const [oldStr, newStr] of replacements) {
        if (content.includes(oldStr)) {
            content = content.split(oldStr).join(newStr);
            applied++;
        } else if (!content.includes(newStr)) {
            failed.push(oldStr.substring(0, 60).replace(/\n/g, '\\n'));
        }
    }
    fs.writeFileSync(filepath, content, 'utf-8');
    return { applied, failed, total: replacements.length };
}

function resetHubState(resourcesDir) {
    const asarPath = path.join(resourcesDir, 'app.asar');
    const asarOrig = path.join(resourcesDir, 'app.asar.orig');
    const appDir = path.join(resourcesDir, 'app');
    const kitDir = path.join(resourcesDir, 'zh-patch');
    let changed = false;
    if (fs.existsSync(asarOrig)) {
        if (fs.existsSync(asarPath)) fs.unlinkSync(asarPath);
        fs.renameSync(asarOrig, asarPath);
        changed = true;
    }
    if (fs.existsSync(appDir)) {
        fs.rmSync(appDir, { recursive: true, force: true });
        changed = true;
    }
    if (fs.existsSync(kitDir)) {
        fs.rmSync(kitDir, { recursive: true, force: true });
        changed = true;
    }
    return changed;
}

function applyHubPatch(silent) {
    const resourcesDir = getHubResourcesDir();
    if (!resourcesDir) {
        if (!silent) vscode.window.showErrorMessage('当前平台不支持自动发现 Antigravity 主程序安装目录');
        return false;
    }
    const asarPath = path.join(resourcesDir, 'app.asar');

    if (isHubPatched(resourcesDir)) {
        if (!silent) vscode.window.showInformationMessage('Antigravity 主程序汉化补丁已是最新状态');
        return true;
    }
    if (isHubProcessRunning()) {
        vscode.window.showErrorMessage('检测到 Antigravity 主程序正在运行，请先完全退出（含托盘图标）后重试。');
        return false;
    }
    if (resetHubState(resourcesDir)) {
        console.log('[antigravity-zh] 检测到旧的 Hub 汉化状态，已重置为英文原版');
    }
    if (!fs.existsSync(asarPath)) {
        vscode.window.showErrorMessage(`未找到 ${asarPath}`);
        return false;
    }

    // 1. 解包 asar
    const appDir = path.join(resourcesDir, 'app');
    const { fromAsar, fromUnpacked } = unpackHubAsar(
        asarPath, appDir, path.join(resourcesDir, 'app.asar.unpacked'));

    // 2. 应用原生 UI 补丁
    const results = [];
    for (const [tableFile, relPath] of Object.entries(HUB_NATIVE_TARGETS)) {
        const target = path.join(appDir, relPath);
        if (!fs.existsSync(target)) continue;
        const replacements = JSON.parse(
            fs.readFileSync(path.join(HUB_TRANSLATIONS_DIR, tableFile), 'utf-8'));
        results.push({ name: tableFile.replace('.replacements.json', ''), ...patchHubNativeFile(target, replacements) });
    }

    // 3. 安装网页 UI 翻译组件
    const kitDir = path.join(resourcesDir, 'zh-patch');
    fs.mkdirSync(kitDir, { recursive: true });
    fs.copyFileSync(HUB_ASSET_ZH_I18N, path.join(kitDir, 'zh-i18n.js'));
    fs.copyFileSync(
        path.join(HUB_TRANSLATIONS_DIR, 'webui.dictionary.json'),
        path.join(kitDir, 'cockpit-zh.json'));

    // 4. 停用原 asar
    fs.renameSync(asarPath, path.join(resourcesDir, 'app.asar.orig'));

    const totalSuccess = results.reduce((s, r) => s + r.applied, 0);
    const totalAll = results.reduce((s, r) => s + r.total, 0);
    const failedCount = results.reduce((s, r) => s + r.failed.length, 0);
    console.log(`[antigravity-zh] Hub 补丁: 解包 ${fromAsar}+${fromUnpacked} 文件, 原生替换 ${totalSuccess}/${totalAll}, 未匹配 ${failedCount}`);

    if (!silent) {
        const detail = results.map(r => `${r.name}: ${r.applied}/${r.total}`).join(' | ');
        vscode.window.showInformationMessage(
            `Antigravity 主程序汉化完成！(${detail})。词典位于 resources/zh-patch/cockpit-zh.json，修改后在应用内 Ctrl+R 生效。`
        );
    }
    return true;
}

function revertHubPatch() {
    const resourcesDir = getHubResourcesDir();
    if (!resourcesDir) {
        vscode.window.showErrorMessage('当前平台不支持自动发现 Antigravity 主程序安装目录');
        return;
    }
    if (isHubProcessRunning()) {
        vscode.window.showErrorMessage('检测到 Antigravity 主程序正在运行，请先完全退出（含托盘图标）后重试。');
        return;
    }
    if (resetHubState(resourcesDir)) {
        vscode.window.showInformationMessage('Antigravity 主程序已恢复英文原版，请重新启动它生效。');
    } else {
        vscode.window.showInformationMessage('未检测到 Antigravity 主程序汉化痕迹，无需恢复。');
    }
}

// ══════════════════════════════════════════════════════════════════════
// 插件激活 / 命令
// ══════════════════════════════════════════════════════════════════════

function applyAllPatches(silent) {
    const base = getAppBase();
    if (!base) {
        if (!silent) vscode.window.showErrorMessage('未找到 Antigravity 安装目录');
        return false;
    }

    const targets = getTargets(base);
    const results = [];

    // Check if all files have current patch version
    const allCurrent = Object.values(targets).every(f => isPatchCurrent(f));
    if (allCurrent) {
        if (!silent) vscode.window.showInformationMessage('汉化补丁已是最新状态');
        return true;
    }

    // Revert files that have old patches before re-applying
    for (const filepath of Object.values(targets)) {
        const ver = getPatchVersion(filepath);
        if (ver && ver !== PATCH_VERSION) {
            revertFile(filepath);
        }
    }

    // Apply patches
    results.push(patchFile(targets.settings, getSettingsReplacements(), 'Settings'));
    results.push(patchFile(targets.chat, getChatReplacements(), 'Chat'));
    results.push(patchFile(targets.workbench, getWorkbenchReplacements(), 'Workbench'));

    // Update checksums
    const checksumCount = updateChecksums(base);

    const totalSuccess = results.reduce((s, r) => s + r.success, 0);
    const totalAll = results.reduce((s, r) => s + r.total, 0);

    const detail = results.map(r => `${r.name}: ${r.success}/${r.total}`).join(' | ');

    if (!silent) {
        vscode.window.showInformationMessage(
            `汉化补丁已应用！共 ${totalSuccess} 处 (${detail})。请重启 Antigravity 生效。`,
            '重新加载窗口'
        ).then(choice => {
            if (choice === '重新加载窗口') {
                vscode.commands.executeCommand('workbench.action.reloadWindow');
            }
        });
    }

    return true;
}

function revertAllPatches() {
    const base = getAppBase();
    if (!base) {
        vscode.window.showErrorMessage('未找到 Antigravity 安装目录');
        return;
    }

    const targets = getTargets(base);
    let reverted = 0;

    for (const filepath of Object.values(targets)) {
        if (revertFile(filepath)) reverted++;
    }

    revertChecksums(base);

    vscode.window.showInformationMessage(
        `已恢复 ${reverted} 个文件。请重启 Antigravity 生效。`,
        '重新加载窗口'
    ).then(choice => {
        if (choice === '重新加载窗口') {
            vscode.commands.executeCommand('workbench.action.reloadWindow');
        }
    });
}

// 状态栏项（模块级变量）
let updateBlockStatusBar;

function updateStatusBar(base) {
    if (!updateBlockStatusBar) return;
    const blocked = base ? isAutoUpdateBlocked(base) : false;
    if (blocked) {
        updateBlockStatusBar.text = '$(shield) 更新已屏蔽';
        updateBlockStatusBar.tooltip = '已屏蔽 Antigravity 自动更新检测，点击恢复';
        updateBlockStatusBar.color = new vscode.ThemeColor('statusBarItem.warningForeground');
        updateBlockStatusBar.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
    } else {
        updateBlockStatusBar.text = '$(shield) 更新正常';
        updateBlockStatusBar.tooltip = '点击屏蔽 Antigravity 自动更新检测';
        updateBlockStatusBar.color = undefined;
        updateBlockStatusBar.backgroundColor = undefined;
    }
}

function activate(context) {
    const base = getAppBase();

    // ── 状态栏 ──
    updateBlockStatusBar = vscode.window.createStatusBarItem(
        vscode.StatusBarAlignment.Right, 100
    );
    updateBlockStatusBar.command = 'antigravity-zh.toggleBlockUpdate';
    updateStatusBar(base);
    updateBlockStatusBar.show();
    context.subscriptions.push(updateBlockStatusBar);

    // ── 注册命令 ──
    vscode.commands.registerCommand('antigravity-zh.applyHubPatch', () => {
        vscode.window.showWarningMessage(
            '将对 Antigravity 主程序（Hub）应用汉化补丁：解包 app.asar 并修改其安装文件。继续？',
            '应用补丁', '取消'
        ).then(choice => {
            if (choice === '应用补丁') {
                try {
                    applyHubPatch(false);
                } catch (e) {
                    vscode.window.showErrorMessage(`Hub 汉化失败: ${e.message}`);
                }
            }
        });
    });
    vscode.commands.registerCommand('antigravity-zh.revertHubPatch', () => {
        revertHubPatch();
    });
    context.subscriptions.push(
        vscode.commands.registerCommand('antigravity-zh.applyPatch', () => applyAllPatches(false)),
        vscode.commands.registerCommand('antigravity-zh.revertPatch', () => revertAllPatches()),
        vscode.commands.registerCommand('antigravity-zh.toggleBlockUpdate', () => {
            const b = getAppBase();
            if (!b) {
                vscode.window.showErrorMessage('未找到 Antigravity 安装目录');
                return;
            }

            const currentlyBlocked = isAutoUpdateBlocked(b);

            if (currentlyBlocked) {
                // 恢复更新
                if (unblockAutoUpdate(b)) {
                    updateStatusBar(b);
                    vscode.window.showInformationMessage(
                        '已恢复 Antigravity 自动更新。请重启 IDE 生效。',
                        '重新加载窗口'
                    ).then(choice => {
                        if (choice === '重新加载窗口') {
                            vscode.commands.executeCommand('workbench.action.reloadWindow');
                        }
                    });
                } else {
                    vscode.window.showErrorMessage('恢复更新失败，请检查文件权限。');
                }
            } else {
                // 屏蔽更新
                vscode.window.showWarningMessage(
                    '屏蔽自动更新后将无法收到新版本通知和安全补丁。确认屏蔽？',
                    '确认屏蔽', '取消'
                ).then(choice => {
                    if (choice === '确认屏蔽') {
                        if (blockAutoUpdate(b)) {
                            updateStatusBar(b);
                            vscode.window.showInformationMessage(
                                '已屏蔽 Antigravity 自动更新检测。请重启 IDE 生效。',
                                '重新加载窗口'
                            ).then(c => {
                                if (c === '重新加载窗口') {
                                    vscode.commands.executeCommand('workbench.action.reloadWindow');
                                }
                            });
                        } else {
                            vscode.window.showErrorMessage('屏蔽更新失败，请检查文件权限。');
                        }
                    }
                });
            }
        })
    );

    // ── 监听配置变更 ──
    context.subscriptions.push(
        vscode.workspace.onDidChangeConfiguration(e => {
            if (e.affectsConfiguration('antigravity-zh.blockAutoUpdate')) {
                const b = getAppBase();
                if (!b) return;
                const shouldBlock = vscode.workspace.getConfiguration('antigravity-zh').get('blockAutoUpdate', false);
                if (shouldBlock && !isAutoUpdateBlocked(b)) {
                    blockAutoUpdate(b);
                    updateStatusBar(b);
                } else if (!shouldBlock && isAutoUpdateBlocked(b)) {
                    unblockAutoUpdate(b);
                    updateStatusBar(b);
                }
            }
        })
    );

    // ── 启动时自动检测并应用汉化补丁 ──
    setTimeout(() => {
        try {
            applyAllPatches(true);
        } catch (e) {
            console.error('[antigravity-zh] 自动补丁失败:', e);
        }

        // 可选：同时自动汉化 Antigravity 主程序 (Hub)，默认关闭。
        // Hub 是另一个独立应用且可能正在运行，因此仅在实际可行时静默尝试。
        const patchHub = vscode.workspace.getConfiguration('antigravity-zh').get('patchHubApp', false);
        if (patchHub) {
            const hubDir = getHubResourcesDir();
            if (hubDir && !isHubPatched(hubDir) && !isHubProcessRunning()) {
                try {
                    applyHubPatch(true);
                    vscode.window.showInformationMessage(
                        'Antigravity 主程序 (Hub) 已自动完成汉化，重启 Hub 后生效。');
                } catch (e) {
                    console.error('[antigravity-zh] Hub 自动补丁失败:', e);
                }
            }
        }
    }, 3000);
}

function deactivate() { }

module.exports = { activate, deactivate };
