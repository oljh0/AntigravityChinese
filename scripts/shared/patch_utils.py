#!/usr/bin/env python3
import sys
import subprocess
import os
import json
import shutil
from pathlib import Path

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

def load_replacements(filepath: Path) -> list[tuple[str, str]]:
    """从 JSON 文件加载替换词条"""
    if not filepath.exists():
        return []

    try:
        data = json.loads(filepath.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []

        replacements = []
        for pair in data:
            if isinstance(pair, list) and len(pair) == 2:
                replacements.append((pair[0], pair[1]))
        return replacements
    except Exception as e:
        print(f"  ⚠️ 加载替换文件失败 {filepath}: {e}")
        return []

def patch_file(filepath: Path, replacements: list[tuple[str, str]], dry_run: bool = False) -> tuple[int, int]:
    """应用替换补丁到文件"""
    if not filepath.exists():
        return 0, 0
    
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return 0, 0
        
    original_content = content
    applied = 0
    already = 0
    
    for old, new in replacements:
        if new in content and old not in content:
            already += 1
            continue
        
        if old in content:
            content = content.replace(old, new)
            applied += 1
            
    if applied > 0 and not dry_run:
        bak_path = filepath.with_suffix(filepath.suffix + ".bak")
        if not bak_path.exists():
            shutil.copy2(filepath, bak_path)
        filepath.write_text(content, encoding="utf-8")
        
    return applied, already

def revert_file(filepath: Path) -> bool:
    """从备份恢复文件"""
    bak_path = filepath.with_suffix(filepath.suffix + ".bak")
    if bak_path.exists():
        shutil.move(bak_path, filepath)
        return True
    return False
