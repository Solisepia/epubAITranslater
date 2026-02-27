# Config README - 配置说明

本文档与当前代码实现同步，说明 `config.yaml` 中哪些字段会实际影响翻译，哪些字段仅为兼容保留。

This document is synchronized with the current code implementation, explaining which fields in `config.yaml` actually affect translation and which are retained for compatibility.

---

## 1. 加载规则 / Loading Rules

- **支持格式 / Supported Formats**: YAML / JSON
- **覆盖规则 / Override Rule**: 仅覆盖你显式填写的字段，未填写使用默认值  
  Only overrides fields you explicitly specify; unspecified fields use defaults.
- **未知字段 / Unknown Fields**: 未识别字段会被忽略（不会报错）  
  Unrecognized fields are ignored (no errors).
- **缓存注意 / Cache Note**: 开启 `--resume` 时，已命中的缓存段落不会重翻；配置改动想全面生效请关闭 `resume` 或更换 `cache.sqlite`。  
  With `--resume`, cached segments won't be retranslated. To apply config changes, disable `resume` or change the cache file.

---

## 2. 默认配置（建议）/ Default Config (Recommended)

当前项目默认模板最小化为：

The current project default template is minimized to:

```yaml
style: faithful_literal
translate_toc: true
translate_titles: true
```

其余项使用内置默认值（见下方 4.2）/ Other fields use built-in defaults (see section 4.2 below).

---

## 3. UI 中可编辑且实际生效的字段 / Fields Editable in UI and Effective

### 3.1 翻译风格 / Translation Style

- **目标语言 / Target Language**: 固定为简体中文（zh-Hans），不再通过 config 配置  
  Fixed to Simplified Chinese (zh-Hans), no longer configured via config.

- **`style`**
  - **作用 / Purpose**: 翻译/润色风格，会直接进入 LLM payload 的 `style_guide`  
    Translation/revision style, directly passed to LLM payload's `style_guide`.
  - **可选枚举 / Options**:
    | 风格 / Style | 说明 / Description | 推荐场景 / Recommended Use Case |
    |-------------|-------------------|-------------------------------|
    | `faithful_literal` | 忠实直译（默认） / Faithful literal (default) | 技术文档/术语敏感 |
    | `faithful_fluent` | 忠实但更顺畅 / Faithful but smoother | 通用阅读 |
    | `literary_cn` | 偏书面文风 / Literary style | 小说/散文 |
    | `concise_cn` | 更简洁凝练 / More concise | 摘要/速读 |
  - 非法值会自动回退到 `faithful_literal`  
    Invalid values automatically fallback to `faithful_literal`.

### 3.2 内容范围 / Content Scope

- **`translate_toc`**: 是否翻译目录文本  
  Whether to translate table of contents text.

- **`translate_titles`**: 是否翻译 HTML `title` 节点  
  Whether to translate HTML `title` nodes.

### 3.3 分段配置 / Segmentation

| 字段 / Field | 说明 / Description | 默认值 / Default |
|-------------|-------------------|-----------------|
| `segmentation.max_chars_per_segment` | 单段最大字符数 / Max chars per segment | 1200 |
| `segmentation.max_chars_per_batch` | 单批字符上限 / Max chars per batch | 12000 |
| `segmentation.max_segments_per_batch` | 单批段数上限 / Max segments per batch | 40 |

### 3.4 上下文 / Context

| 字段 / Field | 说明 / Description | 默认值 / Default |
|-------------|-------------------|-----------------|
| `context.prev_segment_chars` | 前文截断长度 / Previous segment context length | 300 |

### 3.5 LLM 调用 / LLM Invocation

| 字段 / Field | 说明 / Description | 默认值 / Default |
|-------------|-------------------|-----------------|
| `llm.temperature` | 采样温度 / Sampling temperature | 0.0 |
| `llm.max_retries` | 最大重试次数 / Max retries | 5 |
| `llm.retry_backoff_seconds` | 重试等待秒数列表 / Retry backoff seconds list | [1, 2, 4, 8, 16] |
| `llm.timeout_seconds` | 单次请求超时秒数 / Request timeout seconds | 120 |

### 3.6 QA 门槛 / QA Threshold

| 字段 / Field | 说明 / Description | 默认值 / Default |
|-------------|-------------------|-----------------|
| `qa.warn_ratio_limit` | QA 警告占比阈值（0~1） / QA warning ratio threshold | 0.005 |
| `qa.warn_min_cap` | QA 警告最小上限 / QA warning minimum cap | 20 |

**验收规则 / Acceptance Rule**:

```
warn_cap = max(int(total_segments * warn_ratio_limit), warn_min_cap)
```

仅当 `error_count == 0` 且 `warn_count <= warn_cap` 才通过 gate。  
Pass gate only when `error_count == 0` and `warn_count <= warn_cap`.

---

## 4. 兼容字段说明 / Compatibility Fields

### 4.1 已删除字段（旧配置里会被忽略）/ Removed Fields (Ignored in Old Configs)

- `quote_mode.*`
- `poetry_mode`
- `code_mode`
- `latin_mode.*`
- `table_mode.*`
- `segmentation.sentence_split_fallback`
- `context.use_prev_segment`
- `context.use_term_hints`

---

## 5. 常用调参模板 / Common Tuning Templates

### 5.1 稳定优先 / Stability First

适合网络不稳定或 API 限流严格的场景 / Suitable for unstable networks or strict API rate limits.

```yaml
segmentation:
  max_chars_per_segment: 800
  max_chars_per_batch: 8000
  max_segments_per_batch: 25

llm:
  max_retries: 6
  timeout_seconds: 180
```

### 5.2 速度优先 / Speed First

网络稳定时使用 / Use when network is stable.

```yaml
segmentation:
  max_chars_per_batch: 15000
  max_segments_per_batch: 60
```

并配合提高 `max_concurrency`（视 provider 限流而定）/ Also increase `max_concurrency` (depends on provider rate limits).

---

## 6. 常见问题 / FAQ

### Q: 改了配置但结果没变化？ / Config changed but no effect?

A: 先检查是否开启了 `resume` 命中缓存。  
A: First check if `resume` is enabled and hitting cache.

### Q: 可以写额外字段吗？ / Can I write additional fields?

A: 可以写，但未识别字段会被忽略。  
A: Yes, but unrecognized fields will be ignored.

### Q: 如何完全重置配置？ / How to fully reset config?

A: 删除 `config.yaml`，程序会使用内置默认值。  
A: Delete `config.yaml`; the program will use built-in defaults.

---

**最后更新 / Last Updated**: 2026-02-26
