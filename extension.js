// Antigravity IDE 中文汉化插件 - 自动补丁引擎
// 在插件激活时自动检测并应用硬编码字符串的中文翻译

const vscode = require('vscode');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

// ═══════════════════════════════════════════════════════════════
// 路径配置
// ═══════════════════════════════════════════════════════════════
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

// ═══════════════════════════════════════════════════════════════
// 替换规则定义
// ═══════════════════════════════════════════════════════════════

const REPLACEMENTS_DIR = path.join(__dirname, 'translations', 'patches');
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
        throw new Error(`未知替换表: ${name}`);
    }

    const filepath = path.join(REPLACEMENTS_DIR, filename);
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

// ═══════════════════════════════════════════════════════════════
// 补丁引擎
// ═══════════════════════════════════════════════════════════════

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
    // so recalculating hashes doesn't help — we must remove them.
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

// ═══════════════════════════════════════════════════════════════
// 自动更新屏蔽
// ═══════════════════════════════════════════════════════════════

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

// ═══════════════════════════════════════════════════════════════
// 插件激活 / 命令
// ═══════════════════════════════════════════════════════════════

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
    }, 3000);
}

function deactivate() { }

module.exports = { activate, deactivate };
