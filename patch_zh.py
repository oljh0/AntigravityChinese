#!/usr/bin/env python3
"""
Antigravity IDE 中文汉化补丁脚本
同时修改三个关键文件：
  - jetskiAgent/main.js               → Settings 面板（Agent/Tab/Browser/Editor/Account 设置项）
  - out/media/chat.js                  → Agent 聊天面板（对话模式、Customizations、导航栏等）
  - workbench.desktop.main.js          → 快速设置面板（状态栏弹窗）

用法:
  python3 patch_zh.py          # 应用汉化
  python3 patch_zh.py --revert # 恢复原文件
"""

import shutil
import os
import sys
import json
import hashlib
import base64

# 获取当前用户的 Local AppData 目录
local_app_data = os.environ.get('LOCALAPPDATA')
if not local_app_data:
    print('  ❌ 无法获取 LOCALAPPDATA 环境变量，请确保在 Windows 环境下运行该脚本。')
    sys.exit(1)

BASE = os.path.join(local_app_data, 'Programs', 'Antigravity', 'resources', 'app')
TARGETS = {
    'settings': f'{BASE}\\out\\jetskiAgent\\main.js',
    'chat': f'{BASE}\\extensions\\antigravity\\out\\media\\chat.js',
    'workbench': f'{BASE}\\out\\vs\\workbench\\workbench.desktop.main.js',
}
PRODUCT_JSON = f'{BASE}\\product.json'
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def load_replacements(name):
    """从共享 JSON 文件加载替换对"""
    filepath = os.path.join(SCRIPT_DIR, 'translations', 'patches', f'{name}.replacements.json')
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not isinstance(data, list) or any(
        not isinstance(pair, list) or len(pair) != 2 or any(not isinstance(item, str) for item in pair)
        for pair in data
    ):
        raise ValueError(f'替换表格式无效: {filepath}')

    return [tuple(pair) for pair in data]


def get_settings_replacements():
    """Settings 面板 (jetskiAgent/main.js) 的替换对"""
    return load_replacements('main')


def get_chat_replacements():
    """Agent 聊天面板 (chat.js) 的替换对"""
    return load_replacements('chat')


def get_workbench_replacements():
    """快速设置面板 (workbench.desktop.main.js) 的替换对"""
    return load_replacements('workbench')


def patch_file(filepath, replacements, name):
    """对单个文件应用替换"""
    backup = filepath + '.bak'

    if not os.path.exists(filepath) and not os.path.exists(backup):
        print(f'  ❌ 文件不存在且无备份: {filepath}')
        return 0

    # 强制更新逻辑：确保我们在英文原版文件上应用补丁
    if not os.path.exists(backup):
        # 英文原始文件务必备份好方便还原
        shutil.copy2(filepath, backup)
        print(f'  ✅ 已备份英文原始文件: {os.path.basename(backup)}')
    else:
        # 已有备份说明可能已经汉化过，先恢复英文原始文件再应用新的中文补丁，实现直接更新
        shutil.copy2(backup, filepath)
        print(f'  ♻️  已从备份恢复英文原始文件，准备直接更新: {os.path.basename(filepath)}')

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    count = 0
    failed = []

    for old, new in replacements:
        if old in content:
            content = content.replace(old, new)
            count += 1
        else:
            failed.append(old[:50])

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f'  🎉 {name}: 成功替换 {count}/{len(replacements)} 处')
    if failed:
        print(f'  ⚠️  未匹配 {len(failed)} 处:')
        for f_str in failed:
            print(f'    - {f_str}...')
    return count


def update_checksums():
    """更新 product.json 中的文件校验值，消除'安装似乎损坏'提示"""
    if not os.path.exists(PRODUCT_JSON):
        print('  ⚠️  product.json 不存在，跳过 checksum 更新')
        return

    # Backup
    backup = PRODUCT_JSON + '.bak'
    if not os.path.exists(backup):
        shutil.copy2(PRODUCT_JSON, backup)

    with open(PRODUCT_JSON, 'r', encoding='utf-8') as f:
        product = json.load(f)

    checksums = product.get('checksums', {})
    updated = 0
    for key in checksums:
        for prefix in [f'{BASE}\\out\\', f'{BASE}\\']:
            # 注意：product.json 里面的 key 可能是正斜杠形式的，在 Windows 也需要转成反斜杠拼接真实路径
            filepath = os.path.join(prefix, key.replace('/', '\\'))
            if os.path.exists(filepath):
                with open(filepath, 'rb') as f:
                    data = f.read()
                new_hash = base64.b64encode(hashlib.sha256(data).digest()).decode('ascii').rstrip('=')
                if new_hash != checksums[key]:
                    checksums[key] = new_hash
                    updated += 1
                break

    if updated > 0:
        product['checksums'] = checksums
        with open(PRODUCT_JSON, 'w', encoding='utf-8') as f:
            json.dump(product, f, indent='\t', ensure_ascii=False)
        print(f'  ✅ 已更新 {updated} 个文件校验值')
    else:
        print('  ⏭️  校验值无需更新')


def get_workbench_replacements():
    """快速设置面板 (workbench.desktop.main.js) 的替换对"""
    return [
        # ============================================================
        # 1. On/Off 枚举（全局生效，影响所有设置项的 On/Off 显示）
        # ============================================================
        ('i.ON="On",i.OFF="Off"', 'i.ON="开",i.OFF="关"'),

        # ============================================================
        # 2. 面板底部标签页
        # ============================================================
        # NOTE: label:"Settings" 是面板 tab 的路由 key，不翻译
        ('label:"AI Shortcuts"', 'label:"AI 快捷键"'),

        # ============================================================
        # 3. 面板内 textContent 文本
        # ============================================================
        ('textContent="Advanced Settings"', 'textContent="高级设置"'),
        ('textContent="Customizations"', 'textContent="自定义"'),
        ('textContent="Manage"', 'textContent="管理"'),
        ('textContent="Snooze"', 'textContent="暂停"'),
        ('textContent=o?"Cancel":"Start"', 'textContent=o?"取消":"开始"'),
        ('textContent="Manage MCP servers"', 'textContent="管理 MCP 服务器"'),
        ('textContent="View raw config"', 'textContent="查看原始配置"'),

        # ============================================================
        # 4. 安全面板 textContent（Terminal/Review/JS execution policy）
        # ============================================================
        ('textContent="Terminal execution policy"', 'textContent="终端执行策略"'),
        ('textContent="Review policy"', 'textContent="审查策略"'),
        ('textContent="JavaScript execution policy"', 'textContent="JavaScript 执行策略"'),
        # 下拉选项 textContent
        ('textContent="Always Proceed"', 'textContent="始终继续"'),
        ('textContent="Request Review"', 'textContent="请求审查"'),
        ('textContent="Agent Decides"', 'textContent="Agent 决定"'),
        ('textContent="Disabled"', 'textContent="已禁用"'),

        # ============================================================
        # 5. Settings 项的 label（显示名称）
        # ============================================================
        ('label:"Agent Auto-Fix Lints"', 'label:"Agent 自动修复 Lint"'),
        ('label:"Auto Execution"', 'label:"自动执行"'),
        ('label:"Review Policy"', 'label:"审查策略"'),
        ('label:"Agent Gitignore Access"', 'label:"Agent Gitignore 访问"'),
        ('label:"Tab Gitignore Access"', 'label:"Tab Gitignore 访问"'),
        ('label:"Tab Speed"', 'label:"Tab 速度"'),
        ('label:"Tab to Jump"', 'label:"Tab 跳转"'),
        ('label:"Tab to Import"', 'label:"Tab 导入"'),
        ('label:"Auto-Open Edited Files"', 'label:"自动打开已编辑文件"'),
        ('label:"Open Agent on Reload"', 'label:"重新加载时打开 Agent"'),
        ('label:"Clipboard Context"', 'label:"剪贴板上下文"'),
        ('label:"Highlight After Accept"', 'label:"接受后高亮"'),
        ('label:"Suggestions in Editor"', 'label:"编辑器中的建议"'),
        ('label:"Enable Tab Sounds (Beta)"', 'label:"启用 Tab 声音 (Beta)"'),

        # ============================================================
        # 6. Settings 项的 description
        # ============================================================
        ('description:["Set the speed of tab suggestions"]',
         'description:["设置 Tab 建议的速度"]'),
        ('description:["Open files in the background if the agent creates or edits them"]',
         'description:["当 Agent 创建或编辑文件时在后台打开它们"]'),
        ('description:["Open Agent panel on window reload"]',
         'description:["窗口重新加载时打开 Agent 面板"]'),
        ('description:["Predict the location of your next edit and navigates you there with a tab keypress"]',
         'description:["预测下一个编辑位置，按 Tab 键即可跳转到该位置"]'),
        ('description:["Quickly add and update imports with a tab keypress."]',
         'description:["按 Tab 键快速添加和更新导入语句。"]'),
        ('description:["Highlight newly inserted text after accepting a Tab completion."]',
         'description:["接受 Tab 补全后高亮新插入的文本。"]'),

        # ============================================================
        # 7. Review Policy 下拉选项（label + description）
        # ============================================================
        ('{value:B5.TURBO,label:"Always Proceed",description:"Agent never asks for review. This maximizes the autonomy of the Agent, but also has the highest risk of the Agent operating over unsafe or injected Artifact content.",disabledInSecureMode:!0}',
         '{value:B5.TURBO,label:"始终继续",description:"Agent 从不请求审查。这最大化了 Agent 的自主性，但也具有 Agent 操作不安全或注入的 Artifact 内容的最高风险。",disabledInSecureMode:!0}'),
        ('{value:B5.AUTO,label:"Agent Decides",description:"Agent will decide when to ask for review based on task complexity and user preference."}',
         '{value:B5.AUTO,label:"Agent 决定",description:"Agent 将根据任务复杂性和用户偏好决定何时请求审查。"}'),
        ('{value:B5.ALWAYS,label:"Request Review",description:"Agent always asks for review.",disabledInSecureMode:!1}',
         '{value:B5.ALWAYS,label:"请求审查",description:"Agent 始终请求审查。",disabledInSecureMode:!1}'),

        # ============================================================
        # 8. Auto Execution 下拉选项
        # ============================================================
        ('{label:"Always Proceed",value:W1.EAGER,description:"Always auto-execute commands unless they are in your deny list. This also allows Agent to auto-execute Browser controls."}',
         '{label:"始终继续",value:W1.EAGER,description:"始终自动执行命令，除非它们在您的拒绝列表中。这也允许 Agent 自动执行浏览器控制。"}'),

        # ============================================================
        # 9. Tab Speed 下拉选项
        # ============================================================
        ('{label:"Slow",value:RV.SLOW}', '{label:"慢速",value:RV.SLOW}'),
        ('{label:"Fast",value:RV.FAST,isDefaultWhenAvailable:!0}', '{label:"快速",value:RV.FAST,isDefaultWhenAvailable:!0}'),

        # ============================================================
        # 10. Hover 提示文本
        # ============================================================
        ('"View and manage Agent memories, workflows, and rules"',
         '"查看和管理 Agent 记忆、工作流和规则"'),
        # === Accept / Add / Edit / Loading ===
        ('children:"Accept"', 'children:"接受"'),
        ('children:"Accept all"', 'children:"全部接受"'),
        ('children:"Add Model"', 'children:"添加模型"'),
        ('children:"Add context"', 'children:"添加上下文"'),
        ('children:"Add them to allow future interactions"', 'children:"将它们添加到允许列表以允许未来的交互"'),
        ('children:"Edit Model"', 'children:"编辑模型"'),
        ('children:"Edit rule"', 'children:"编辑规则"'),
        ('children:"Edit workflow"', 'children:"编辑工作流"'),
        ('children:"Edit your SSH configuration"', 'children:"编辑你的 SSH 配置"'),
        ('children:"Loading..."', 'children:"加载中..."'),
        ('children:"Loading MCP servers"', 'children:"正在加载 MCP 服务器"'),
        ('children:"Loading models..."', 'children:"正在加载模型..."'),
        ('children:"Loading Browser recording..."', 'children:"正在加载浏览器录制..."'),
        ('label:"Accept hunk"', 'label:"接受代码块"'),
        ('label:"Run"', 'label:"运行"'),
        ('label:"Running"', 'label:"运行中"'),
        ('label:"Open Agent"', 'label:"打开 Agent"'),
        ('label:"Reset to default"', 'label:"重置为默认"'),
        ('label:"Submit"', 'label:"提交"'),
        
        ('"Ask anything, @ to mention, / for workflows"', '"输入任何内容，@ 用于提及，/ 用于调用工作流"'),
    ]


def apply_patch():
    """应用汉化补丁"""
    total = 0

    print('📦 [1/4] 汉化 Settings 面板 (jetskiAgent/main.js)...')
    total += patch_file(TARGETS['settings'], get_settings_replacements(), 'Settings')

    print()
    print('📦 [2/4] 汉化 Agent 聊天面板 (chat.js)...')
    total += patch_file(TARGETS['chat'], get_chat_replacements(), 'Chat')

    print()
    print('📦 [3/4] 汉化快速设置面板 (workbench.desktop.main.js)...')
    total += patch_file(TARGETS['workbench'], get_workbench_replacements(), 'Workbench')

    print()
    print('📦 [4/4] 更新文件校验值 (消除"安装损坏"提示)...')
    update_checksums()

    print(f'\n🎉 全部完成！共替换 {total} 处')
    print('📌 请完全退出 Antigravity (Cmd+Q) 后重新打开即可生效')


def revert_patch():
    """恢复所有原文件"""
    for name, filepath in TARGETS.items():
        backup = filepath + '.bak'
        if os.path.exists(backup):
            shutil.copy2(backup, filepath)
            print(f'  ✅ 已恢复: {name} ({os.path.basename(filepath)})')
        else:
            print(f'  ⏭️  无需恢复 (无备份): {name}')

    # Restore product.json
    pj_backup = PRODUCT_JSON + '.bak'
    if os.path.exists(pj_backup):
        shutil.copy2(pj_backup, PRODUCT_JSON)
        print(f'  ✅ 已恢复: product.json')

    print('📌 请完全退出 Antigravity (Cmd+Q) 后重新打开即可生效')


if __name__ == '__main__':
    if '--revert' in sys.argv:
        revert_patch()
    else:
        apply_patch()
