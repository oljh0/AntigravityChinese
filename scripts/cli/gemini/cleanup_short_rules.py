#!/usr/bin/env python3
"""清理 gemini 替换规则，删除长度小于5的规则"""

import json
from pathlib import Path

REPLACEMENTS_FILE = Path(r"F:\OpenAI\AntigravityChinese\translations\patches\cli\gemini\qwen.replacements.json")
MIN_LENGTH = 15  # 只保留较长的替换规则，避免误替换代码标识符

def main():
    with open(REPLACEMENTS_FILE, 'r', encoding='utf-8') as f:
        replacements = json.load(f)
    
    original_count = len(replacements)
    filtered = []
    removed = []
    
    for pair in replacements:
        if len(pair) == 2 and len(pair[0]) >= MIN_LENGTH:
            filtered.append(pair)
        else:
            removed.append(pair)
    
    with open(REPLACEMENTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(filtered, f, ensure_ascii=False, indent=4)
    
    print(f"原始规则数: {original_count}")
    print(f"保留规则数: {len(filtered)}")
    print(f"删除规则数: {len(removed)}")
    print("\n已删除的规则:")
    for old, new in removed:
        print(f"  [{old}] -> [{new}]")

if __name__ == "__main__":
    main()
