"use strict";
// Antigravity 主程序汉化模块：原生菜单词典 + 网页 UI 词典翻译注入
// 词典文件位于 ../cockpit-zh.json（zh-patch 目录下），可随时编辑，重载窗口后生效
Object.defineProperty(exports, "__esModule", { value: true });
exports.translateMenu = translateMenu;
exports.attachWebTranslator = attachWebTranslator;
exports.MENU_LABELS = void 0;
const fs = require('fs');
const path = require('path');
// Electron 默认菜单及本应用菜单的英文 → 中文映射（保留 role，仅改显示文本）
const MENU_LABELS = {
    'File': '文件',
    'Edit': '编辑',
    'View': '查看',
    'Go': '前往',
    'Window': '窗口',
    'Help': '帮助',
    'New Window': '新建窗口',
    'New Tab': '新建标签页',
    'New Conversation': '新建对话',
    'Undo': '撤销',
    'Redo': '重做',
    'Cut': '剪切',
    'Copy': '复制',
    'Paste': '粘贴',
    'Paste and Match Style': '粘贴并匹配样式',
    'Delete': '删除',
    'Select All': '全选',
    'Start Dictation': '开始听写',
    'Emoji & Symbols': '表情与符号',
    'Speech': '语音',
    'Reload': '重新加载',
    'Force Reload': '强制重新加载',
    'Toggle Developer Tools': '切换开发者工具',
    'Toggle Full Screen': '切换全屏',
    'Enter Full Screen': '进入全屏',
    'Exit Full Screen': '退出全屏',
    'Reset Zoom': '重置缩放',
    'Zoom In': '放大',
    'Zoom Out': '缩小',
    'Actual Size': '实际大小',
    'Minimize': '最小化',
    'Zoom': '缩放',
    'Bring All to Front': '全部置于顶层',
    'Close': '关闭',
    'Close Window': '关闭窗口',
    'Close Tab': '关闭标签页',
    'Learn More': '了解更多',
    'Services': '服务',
    'Hide': '隐藏',
    'Hide Others': '隐藏其他',
    'Show All': '全部显示',
    'Preferences': '偏好设置',
    'Settings': '设置',
    'About': '关于',
    'Quit': '退出',
    'Docs': '文档',
    'Check for Updates': '检查更新',
    'Checking for Updates...': '正在检查更新...',
    'Downloading Update...': '正在下载更新...',
    'Restart to Update': '重启以安装更新',
};
exports.MENU_LABELS = MENU_LABELS;
function translateMenu(menu) {
    if (!menu || !menu.items) {
        return;
    }
    for (const item of menu.items) {
        const zh = MENU_LABELS[item.label];
        if (zh && item.label !== zh) {
            item.label = zh;
        }
        if (item.submenu) {
            translateMenu(item.submenu);
        }
    }
}
function loadDictionary() {
    const dicPath = path.join(__dirname, 'cockpit-zh.json');
    const raw = JSON.parse(fs.readFileSync(dicPath, 'utf-8'));
    return { dict: raw.dict || {}, rules: raw.rules || [] };
}
// 注入到页面上下文的翻译器（字符串拼接，避免模板字面量冲突）
const TRANSLATOR_BODY = [
    'var D=__DATA__;var dict=D.dict,rules=D.rules;',
    'var SKIP={SCRIPT:1,STYLE:1,NOSCRIPT:1,CODE:1,PRE:1,TEXTAREA:1,SVG:1,MATH:1};',
    'function tr(s){var core=s.replace(/^\\s+|\\s+$/g,"");if(!core){return null;}',
    '  if(Object.prototype.hasOwnProperty.call(dict,core)){var v=dict[core];return s.replace(core,function(){return v;});}',
    '  for(var i=0;i<rules.length;i++){var r=rules[i];var re=new RegExp(r[0],r[2]||"");',
    '    if(re.test(core)){return s.replace(core,function(){return core.replace(re,r[1]);});}}',
    '  return null;}',
    'function trNode(n){var v=tr(n.nodeValue);if(v!==null&&v!==n.nodeValue){n.nodeValue=v;}}',
    'var ATTRS=["placeholder","title","aria-label","aria-placeholder","data-tooltip","alt"];',
    'function walk(root){if(!root){return;}',
    '  if(root.nodeType===3){trNode(root);return;}',
    '  if(root.querySelectorAll){var tw=document.createTreeWalker(root,NodeFilter.SHOW_TEXT,null,false);var n;',
    '    while((n=tw.nextNode())){var p=n.parentElement;if(!p||SKIP[p.tagName]||p.isContentEditable){continue;}trNode(n);}',
    '    var els=root.querySelectorAll("[placeholder],[title],[aria-label],[data-tooltip],[alt]");',
    '    for(var i=0;i<els.length;i++){for(var j=0;j<ATTRS.length;j++){var a=ATTRS[j];var val=els[i].getAttribute(a);',
    '      if(!val){continue;}var nv=tr(val);if(nv!==null&&nv!==val){els[i].setAttribute(a,nv);}}}}}',
    'var timer=null,pending=[];',
    'function flush(){var list=pending;pending=[];for(var i=0;i<list.length;i++){try{walk(list[i]);}catch(e){}}}',
    'function schedule(nodes){for(var i=0;i<nodes.length;i++){pending.push(nodes[i]);}',
    '  if(timer){clearTimeout(timer);}timer=setTimeout(flush,120);}',
    'var mo=new MutationObserver(function(muts){',
    '  for(var i=0;i<muts.length;i++){var m=muts[i];',
    '    if(m.type==="childList"&&m.addedNodes.length){schedule(m.addedNodes);}',
    '    else if(m.type==="characterData"){schedule([m.target]);}}});',
    'var rootEl=document.documentElement||document.body;',
    'mo.observe(rootEl,{childList:true,subtree:true,characterData:true});',
    'window.__antigravityZh={retranslate:function(){walk(document.body);var t=tr(document.title);if(t){document.title=t;}}};',
    'walk(document.body);var t0=tr(document.title);if(t0){document.title=t0;}'
].join('\n');
function buildScript(dic) {
    return '(function(){if(window.__antigravityZh){window.__antigravityZh.retranslate();return;}' +
        TRANSLATOR_BODY.replace('__DATA__', JSON.stringify(dic)) + '})()';
}
/**
 * 为窗口附加网页 UI 翻译：每次 did-finish-load 后注入词典翻译脚本。
 * 词典热更新：修改 cockpit-zh.json 后重载窗口即可生效。
 */
function attachWebTranslator(win) {
    win.webContents.on('did-finish-load', () => {
        if (win.isDestroyed()) {
            return;
        }
        let dic;
        try {
            dic = loadDictionary();
        }
        catch (e) {
            console.error('[zh-i18n] 读取词典失败:', e.message);
            return;
        }
        win.webContents.executeJavaScript(buildScript(dic), true).catch(() => { });
    });
}
