#!/usr/bin/env python3
import sys
import io

def test_output():
    test_str = "你好，世界！这是一段中文测试文本。"
    
    print("--- 默认输出测试 ---")
    try:
        print(f"当前 stdout 编码: {sys.stdout.encoding}")
        print(test_str)
    except Exception as e:
        print(f"默认输出失败: {e}")

    print("\n--- 强制 UTF-8 重新配置测试 ---")
    try:
        # 尝试重新配置 stdout 为 utf-8
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
            print(f"重配置后 stdout 编码: {sys.stdout.encoding}")
            print(test_str)
        else:
            # 兼容旧版本 Python
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
            print("通过 TextIOWrapper 强制 UTF-8")
            print(test_str)
    except Exception as e:
        print(f"强制输出失败: {e}")

    print("\n--- 提示 ---")
    print("如果在 Windows 终端（CMD/PowerShell）看到乱码，请尝试执行：")
    print("chcp 65001")
    print("这会将当前终端的活动代码页切换为 UTF-8。")

if __name__ == "__main__":
    test_output()
