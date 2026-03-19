#!/usr/bin/env python3
import sys
import subprocess
import os

def init_terminal():
    """初始化终端环境，解决 Windows 下的乱码问题"""
    # 在 Windows 下强制启用简单输出，不使用 Emoji
    if sys.platform == "win32":
        os.environ["SIMPLE_OUTPUT"] = "1"
        
        # 强制重配置标准流为 UTF-8，确保中文本身不乱码
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
        
        # 切换代码页
        try:
            subprocess.run(["chcp", "65001"], capture_output=True, shell=True)
        except Exception:
            pass

def print_status(icon, msg):
    """带图标的状态打印，自动处理环境降级"""
    # 强制进行降级处理，因为在 Windows CLI 捕获中 Emoji 极其不稳定
    icon_map = {
        "📦": "[STEP]",
        "✅": "[OK]",
        "❌": "[ERR]",
        "⚠️": "[WARN]",
        "♻️": "[REVERT]",
        "🎉": "[DONE]",
        "📌": "[INFO]",
        "⏭️": "[SKIP]",
        "⏳": "[WAIT]",
        "⚙️": "[CONFIG]"
    }
    icon = icon_map.get(icon, icon)
    print(f"{icon} {msg}")

def print_step(step_num, total_steps, description):
    print_status("📦", f"[{step_num}/{total_steps}] {description}")
