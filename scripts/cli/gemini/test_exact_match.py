#!/usr/bin/env python3
"""测试完全匹配逻辑是否正确"""

import re

def test_exact_match():
    """测试完全匹配逻辑"""
    
    # 测试用例
    test_cases = [
        # (原始文本, 规则, 预期结果, 说明)
        ("import { ExtensionManager } from 'extension'", "Extension", "ExtensionManager", False, "不应替换 ExtensionManager 中的 Extension"),
        ("import { ExtensionManager } from 'extension'", "ExtensionManager", "扩展管理器", True, "应替换完整的 ExtensionManager"),
        ("const server = 'test'", "server", "服务器", True, "应替换独立的 server 单词"),
        ("const serverName = 'test'", "server", "serverName", False, "不应替换 serverName 中的 server"),
        ("const Server = 'test'", "Server", "服务器", True, "应替换独立的 Server 单词"),
        ("const ServerList = []", "Server", "ServerList", False, "不应替换 ServerList 中的 Server"),
        ("Error: something", "Error", "错误", True, "应替换独立的 Error 单词"),
        ("const ErrorMsg = 'test'", "Error", "ErrorMsg", False, "不应替换 ErrorMsg 中的 Error"),
        ("tools:", "tools", "工具:", True, "应替换 tools（带冒号）"),
        ("const tools = []", "tools", "工具", True, "应替换独立的 tools"),
        ("toolbox", "tools", "toolbox", False, "不应替换 toolbox 中的 tools"),
        ("Settings:", "Settings", "设置:", True, "应替换 Settings（带冒号）"),
        ("const Settings = {}", "Settings", "设置", True, "应替换独立的 Settings"),
        ("UserSettings", "Settings", "UserSettings", False, "不应替换 UserSettings 中的 Settings"),
    ]
    
    print("测试完全匹配逻辑...\n")
    
    all_passed = True
    for text, old, expected, should_change, description in test_cases:
        # 使用与 patch_utils.py 相同的逻辑
        escaped_old = re.escape(old)
        if re.search(r'[^\w\s]', old):
            pattern = escaped_old
        else:
            pattern = r'\b' + escaped_old + r'\b'
        
        new_content = re.sub(pattern, "已替换", text)
        changed = new_content != text
        
        if changed == should_change:
            status = "✓ 通过"
        else:
            status = "✗ 失败"
            all_passed = False
        
        print(f"{status}: {description}")
        print(f"  原始: {text}")
        print(f"  规则: '{old}' -> '已替换'")
        print(f"  结果: {new_content}")
        print(f"  预期变化: {should_change}, 实际变化: {changed}")
        print()
    
    if all_passed:
        print("\n✅ 所有测试通过！")
    else:
        print("\n❌ 部分测试失败！")
    
    return all_passed

if __name__ == "__main__":
    test_exact_match()
