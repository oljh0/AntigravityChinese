# Gemini CLI 汉化补丁修复说明

## 问题描述

执行 `python scripts/cli/gemini/patch_app_zh.py` 后，gemini-cli 启动时出现语法错误：

```
SyntaxError: Unexpected token '{'
imp或t {
      ^
```

## 根本原因

替换规则文件 `translations/patches/cli/gemini/qwen.replacements.json` 中包含大量过短的替换规则（如 `"or"` → `"或"`、`"Extension"` → `"扩展"`），这些规则会错误地匹配和替换 JavaScript 代码中的标识符和关键字：

- `import` → `imp或t`（因为 `"or"` → `"或"`）
- `ExtensionManager` → `扩展Manager`（因为 `"Extension"` → `"扩展"`）
- `forEach` → `f或Each`
- `workspace` → `w或rkspace`

## 解决方案

### 1. 修改 `patch_utils.py` 添加智能匹配逻辑

**文件**: `scripts/shared/patch_utils.py`

**修改内容**:
- 添加 `exact_match_threshold` 参数（默认值：15）
- 对于长度 ≤ 15 的替换规则，使用正则表达式 `\b` 单词边界进行**完全匹配**
- 对于长度 > 15 的规则，使用普通的子字符串替换

**核心逻辑**:
```python
if len(old) <= exact_match_threshold:
    # 使用完全匹配，避免破坏复合标识符
    escaped_old = re.escape(old)
    if re.search(r'[^\w\s]', old):
        pattern = escaped_old
    else:
        pattern = r'\b' + escaped_old + r'\b'
    new_content = re.sub(pattern, new, content)
else:
    # 长规则安全使用子字符串替换
    content = content.replace(old, new)
```

### 2. 清理危险的超短规则

**文件**: `translations/patches/cli/gemini/qwen.replacements.json`

**操作**: 删除了 274 条长度 < 5 的极短规则，如：
- `"or"` → `"或"` ❌ (会破坏 import, for, error 等)
- `"No"` → `"否"` ❌ (会破坏 Node, Note 等)
- `"OS"` → `"操作系统"` ❌ (会破坏 close, cost 等)

**保留**: 长度在 5-15 之间的规则现在可以安全使用，因为会使用完全匹配逻辑。

## 验证结果

### ✅ JavaScript 关键字保持完好
- `import` ✓
- `ExtensionManager` ✓
- `McpPromptLoader` ✓
- `SessionError` ✓
- `canLoadServer` ✓

### ✅ UI 文本正确汉化
- `description: '模型'` ✓
- `label: '最大会话轮次'` ✓
- `title: '设置'` ✓
- `description: '恢复之前的会话...'` ✓

### ✅ 替换统计
- 总替换规则数: 1162 条
- 成功替换: 923 处
- 涉及文件: 20 个

## 测试脚本

创建了 `scripts/cli/gemini/test_exact_match.py` 来验证完全匹配逻辑的正确性：

```bash
python scripts/cli/gemini/test_exact_match.py
```

测试结果: **✅ 所有 14 个测试用例通过**

## 使用建议

1. **替换规则设计原则**:
   - 长度 < 5: 不应使用（过于危险）
   - 长度 5-15: 使用完全匹配逻辑（安全）
   - 长度 > 15: 可以使用子字符串替换（通常安全）

2. **避免的规则模式**:
   - ❌ 单个字母或极短单词（如 `"o"`, `"or"`, `"no"`）
   - ❌ 常见代码标识符的一部分（如 `"Extension"`, `"Server"`）
   - ✅ 完整的短语或句子（如 `"Loading..."`, `"Show version number"`）

3. **最佳实践**:
   - 优先翻译用户可见的 UI 文本
   - 避免翻译可能在代码中出现的独立单词
   - 使用上下文更丰富的短语而非孤立单词
