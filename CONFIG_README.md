# Config README

本文档与当前代码实现同步，说明 `config.yaml` 中哪些字段会实际影响翻译，哪些字段仅为兼容保留。

## 1. 加载规则

- 支持 `YAML` / `JSON`。
- 仅覆盖你显式填写的字段，未填写使用默认值。
- 未识别字段会被忽略（不会报错）。
- 开启 `--resume` 时，已命中的缓存段落不会重翻；配置改动想全面生效请关闭 `resume` 或更换 `cache.sqlite`。

## 2. 默认配置（建议）

当前项目默认模板最小化为：

```yaml
target_lang: zh-Hans
style: faithful_literal
translate_toc: true
translate_titles: true
```

其余项使用内置默认值（见下文 4.2）。

## 3. UI 中可编辑且实际生效的字段

### 3.1 基础

- `target_lang`
  - 建议：`zh-Hans`
  - 作用：目标语言标识（segment 元信息、术语生成场景等）

- `style`
  - 作用：翻译/润色风格，会直接进入 LLM payload 的 `style_guide`
  - 可选枚举：
    - `faithful_literal`：忠实直译（默认，技术文档/术语敏感）
    - `faithful_fluent`：忠实但更顺畅（通用阅读）
    - `literary_cn`：偏书面文风（小说/散文）
    - `concise_cn`：更简洁凝练（摘要/速读）
  - 非法值会自动回退到 `faithful_literal`

### 3.2 内容范围

- `translate_toc`：是否翻译目录文本
- `translate_titles`：是否翻译 HTML `title` 节点

### 3.3 分段

- `segmentation.max_chars_per_segment`：单段最大字符数
- `segmentation.max_chars_per_batch`：单批字符上限
- `segmentation.max_segments_per_batch`：单批段数上限

### 3.4 上下文

- `context.prev_segment_chars`：前文截断长度

### 3.5 LLM 调用

- `llm.temperature`
- `llm.max_retries`
- `llm.retry_backoff_seconds`
- `llm.timeout_seconds`

### 3.6 QA 门槛

- `qa.warn_ratio_limit`
- `qa.warn_min_cap`

验收规则：

`warn_cap = max(int(total_segments * warn_ratio_limit), warn_min_cap)`  
仅当 `error_count == 0` 且 `warn_count <= warn_cap` 才通过 gate。

## 4. 兼容字段说明

### 4.1 已删除字段（旧配置里会被忽略）

- `quote_mode.*`
- `poetry_mode`
- `code_mode`

### 4.2 目前保留在配置模型中，但 UI 已隐藏（当前版本不驱动主流程）

这些字段仍有默认值并可写入配置，但当前逻辑不按它们分支：

- `latin_mode.translate_normally`
- `table_mode.preserve_numbers`
- `table_mode.preserve_abbreviations`
- `segmentation.sentence_split_fallback`
- `context.use_prev_segment`
- `context.use_term_hints`

## 5. 常用调参模板

### 5.1 稳定优先

```yaml
segmentation:
  max_chars_per_segment: 800
  max_chars_per_batch: 8000
  max_segments_per_batch: 25

llm:
  max_retries: 6
  timeout_seconds: 180
```

### 5.2 速度优先（网络稳定时）

```yaml
segmentation:
  max_chars_per_batch: 15000
  max_segments_per_batch: 60
```

并配合提高 `max_concurrency`（视 provider 限流而定）。

## 6. 常见问题

- 改了配置但结果没变化：
  - 先检查是否开启了 `resume` 命中缓存。
- 可以写额外字段吗：
  - 可以写，但未识别字段会被忽略。
