# 配置文件配置项使用情况分析

## 问题回答

**问：对于代码未使用的哪几项，是指存在对应功能的代码但是翻译或术语表生成时未使用吗？还是说连对应功能的代码都不存在？**

**答：是"连对应功能的代码都不存在"**。这 6 个配置项属于早期设计时预留的"空头配置"，代码中从未实现相应的逻辑。

---

## 详细分析

### 🔴 功能完全未实现的配置（4 项）

这些配置项**完全没有对应的功能代码**，修改配置不会有任何效果。

| 配置项 | GUI 帮助文本 | 实际情况 |
|--------|-------------|---------|
| `latin_mode.translate_normally` | 拉丁字母文本是否按普通文本翻译 | ❌ **代码中没有任何检查 `latin_mode` 的逻辑** |
| `table_mode.preserve_numbers` | 表格中是否强制保留数字 | ❌ **代码中没有任何检查 `table_mode` 的逻辑** |
| `table_mode.preserve_abbreviations` | 表格中是否保留缩写 | ❌ **代码中没有任何检查 `table_mode` 的逻辑** |
| `segmentation.sentence_split_fallback` | 分段超长时是否按句子兜底切分 | ❌ **`segmenter.py` 只按字符数切分，没有句子边界检测逻辑** |

**示例代码对比**：

```python
# config.py 中定义了
@dataclass(slots=True)
class LatinMode:
    translate_normally: bool = True  # ← 定义了但从未使用

# 实际代码中从未检查
# src/epub2zh_faithful/ 下没有任何代码读取 config.latin_mode
```

---

### ⚠️ 功能已实现但配置无效（2 项）

这些功能**代码已实现**，但**配置开关未使用**，代码固定为启用状态。

| 配置项 | GUI 帮助文本 | 实际情况 |
|--------|-------------|---------|
| `context.use_prev_segment` | 是否给模型传入上一段上下文 | ⚠️ **代码固定为 True，总是传递上段上下文** |
| `context.use_term_hints` | 是否把命中的术语提示传给模型 | ⚠️ **代码固定为 True，总是传递术语提示** |

**示例代码**：

```python
# src/epub2zh_faithful/segmenter.py:38
# 总是设置上段上下文，从未检查 config.context.use_prev_segment
prev_source = chunk[-config.context.prev_segment_chars:]

# src/epub2zh_faithful/llm_client.py:426
# 总是将 termbase_hits 加入 payload，从未检查 config.context.use_term_hits
return {
    "task": "draft_translate",
    "style_guide": style_guide,
    "termbase_hits": termbase_hits,  # ← 总是传递
    # ...
}
```

---

## 真正生效的配置（13 项）

这些配置项在代码中有实际逻辑支撑，修改会直接影响翻译行为。

| 配置项 | 使用位置 | 影响 |
|--------|---------|------|
| `style` | `llm_client.py` | 翻译风格指导 |
| `translate_toc` | `pipeline.py` | 是否翻译目录 |
| `translate_titles` | `xhtml_extractor.py` | 是否翻译 title 标签 |
| `segmentation.max_chars_per_segment` | `segmenter.py` | 分段最大字符数 |
| `segmentation.max_chars_per_batch` | `pipeline.py` | 每批最大字符数 |
| `segmentation.max_segments_per_batch` | `pipeline.py` | 每批最多段数 |
| `context.prev_segment_chars` | `segmenter.py` | 上段上下文字符数 |
| `llm.temperature` | `llm_client.py` | API 调用温度参数 |
| `llm.max_retries` | `llm_client.py` | 最大重试次数 |
| `llm.retry_backoff_seconds` | `llm_client.py` | 重试等待时间 |
| `llm.timeout_seconds` | `llm_client.py` | 请求超时时间 |
| `qa.warn_ratio_limit` | `qa_checker.py` | QA 警告比例阈值 |
| `qa.warn_min_cap` | `qa_checker.py` | QA 警告最小上限 |

---

## 建议

### 对于用户
- ✅ **可以安全调整的配置**：上述 13 项真正生效的配置
- ⚠️ **调整无效的配置**：6 项未实现/写死的配置（改了也没用）

### 对于开发者
1. **实现未实现的功能**（4 项）：
   - `latin_mode.translate_normally`：添加拉丁字母文本特殊处理逻辑
   - `table_mode.preserve_*`：添加表格内容保护逻辑
   - `segmentation.sentence_split_fallback`：添加句子边界检测逻辑

2. **修复写死的配置**（2 项）：
   - `context.use_prev_segment`：添加 `if config.context.use_prev_segment:` 判断
   - `context.use_term_hints`：添加 `if config.context.use_term_hints:` 判断

3. **或者清理配置**：
   - 如果决定不实现这些功能，从 `config.py` 和 GUI 中移除相关配置项
   - 避免用户混淆

---

**最后更新**: 2026-02-27
