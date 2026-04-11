#!/usr/bin/env python3
import sys
import subprocess
import os
import json
import re
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

def patch_file(filepath: Path, replacements: list[tuple[str, str]], dry_run: bool = False, min_length: int = 15, exact_match_threshold: int = 15) -> tuple[int, int]:
    """应用替换补丁到文件
    
    Args:
        filepath: 文件路径
        replacements: 替换规则列表
        dry_run: 是否只检查不写入
        min_length: 最小替换字符串长度，防止误替换代码关键字（默认5）
        exact_match_threshold: 小于等于此长度的规则将使用完全匹配逻辑（默认15）
    """
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
        # 跳过过短的替换规则，防止误替换代码关键字
        if len(old) < min_length:
            continue
        
        # 对于较短的规则（长度 <= threshold），使用单词边界完全匹配
        # 避免子字符串匹配导致破坏代码标识符
        if len(old) <= exact_match_threshold:
            # 使用正则表达式进行完全匹配
            # \b 表示单词边界，确保只匹配完整的单词
            # 转义特殊正则字符
            escaped_old = re.escape(old)
            # 对于包含非单词字符的模式（如标点符号），不使用 \b
            if re.search(r'[^\w\s]', old):
                pattern = escaped_old
            else:
                pattern = r'\b' + escaped_old + r'\b'
            
            # 检查是否已经替换过
            if new in content and not re.search(pattern, content):
                already += 1
                continue
            
            # 执行替换
            new_content = re.sub(pattern, new, content)
            if new_content != content:
                content = new_content
                applied += 1
        else:
            # 对于较长的规则，使用普通的子字符串替换
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
