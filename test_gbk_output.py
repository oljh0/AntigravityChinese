#!/usr/bin/env python3
import sys

def test_gbk():
    test_str = "你好，这是 GBK 编码的测试文本。"
    print(f"尝试以 GBK 编码输出到 stdout (当前编码: {sys.stdout.encoding})")
    
    # 强制以 gbk 编码写入 buffer
    try:
        sys.stdout.buffer.write(test_str.encode('gbk') + b'\n')
        sys.stdout.buffer.flush()
    except Exception as e:
        print(f"GBK 输出失败: {e}")

if __name__ == "__main__":
    test_gbk()
