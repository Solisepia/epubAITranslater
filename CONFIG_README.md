# Config README

本文档说明 `config.yaml` 每个配置项的用途、效果、建议值与调参方法。

> 注意：`quote_mode` 已移除。旧配置中的 `quote_mode.*` 字段会被忽略，不再影响翻译行为。

## 1. 配置加载规则

- 支持 `YAML` 与 `JSON`。
- 只覆盖你写出来的字段，未写字段使用默认值。
- 未识别字段会被忽略（不会报错）。
- 每次点击 UI 的 `Start Translation` 或执行 CLI 都会重新读取配置。

注意：如果你开启了 `--resume`，已命中的缓存段落不会重翻。配置改动想全面生效，请关闭 `resume` 或换新 `cache.sqlite`。

## 2. 完整字段说明

下面以当前默认配置为例：

```yaml
target_lang: zh-Hans
style: faithful_literal

translate_toc: true
translate_titles: true

quote_mode:
  preserve_original: true
  add_translation: true
  translation_node_class: ai-quote-translation

latin_mode:
  translate_normally: true

poetry_mode: line_by_line
code_mode: skip
table_mode:
  preserve_numbers: true
  preserve_abbreviations: true

segmentation:
  max_chars_per_segment: 1200
  max_chars_per_batch: 12000
  max_segments_per_batch: 40
  sentence_split_fallback: true

context:
  use_prev_segment: true
  prev_segment_chars: 300
  use_term_hints: true

llm:
  temperature: 0.0
  max_retries: 5
  retry_backoff_seconds: [1, 2, 4, 8, 16]
  timeout_seconds: 120

qa:
  warn_ratio_limit: 0.005
  warn_min_cap: 20
```

### 2.1 基础项

- `target_lang`
  - 作用：目标语言标识（主要用于 segment 元信息和提示语语境）。
  - 建议：固定 `zh-Hans`。
  - 生效状态：`已生效`。

- `style`
  - 作用：风格标识（逻辑语义字段）。
  - 建议：`faithful_literal`。
  - 生效状态：`部分生效`（当前主要作为配置与哈希的一部分，未深度驱动模板分支）。

### 2.2 目录/标题

- `translate_toc`
  - 作用：是否翻译 TOC 文本（`href` 不改）。
  - 可选：`true/false`。
  - 生效状态：`已生效`。

- `translate_titles`
  - 作用：是否翻译 `<title>` 与章节标题。
  - 可选：`true/false`。
  - 生效状态：`已生效`。

### 2.3 引句（blockquote/q/cite）

- `quote_mode.preserve_original`
  - 作用：是否保留引句原文节点内容。
  - 可选：`true/false`。
  - 生效状态：`已生效`。

- `quote_mode.add_translation`
  - 作用：在保留原文时，是否额外插入译文伴随节点。
  - 可选：`true/false`。
  - 生效状态：`已生效`。

- `quote_mode.translation_node_class`
  - 作用：伴随译文节点的 class 名。
  - 建议：保持 `ai-quote-translation`。
  - 生效状态：`已生效`。

常见组合：
- 原文+译文并存：`preserve_original: true` + `add_translation: true`
- 只保留原文：`preserve_original: true` + `add_translation: false`
- 只保留译文：`preserve_original: false` + `add_translation: false`

### 2.4 拉丁语 / 诗歌 / 代码 / 表格

- `latin_mode.translate_normally`
  - 作用：拉丁语策略开关。
  - 生效状态：`预留字段`（当前版本未单独分支处理）。

- `poetry_mode`
  - 作用：诗歌处理策略。
  - 生效状态：`预留字段`（当前以结构识别诗歌块并执行行数 QA，尚未按字符串策略分支）。

- `code_mode`
  - 作用：代码块处理策略。
  - 生效状态：`预留字段`（当前默认跳过 code/pre 等容器）。

- `table_mode.preserve_numbers`
- `table_mode.preserve_abbreviations`
  - 作用：表格数字/缩写保留策略。
  - 生效状态：`部分生效`（数字/缩写保护由占位符机制全局执行，不仅限表格）。

### 2.5 分段

- `segmentation.max_chars_per_segment`
  - 作用：单段最大字符，超出会拆分。
  - 影响：越小越稳，调用次数越多。
  - 生效状态：`已生效`。

- `segmentation.max_chars_per_batch`
  - 作用：单次请求累计字符上限。
  - 生效状态：`已生效`。

- `segmentation.max_segments_per_batch`
  - 作用：单次请求段数上限。
  - 生效状态：`已生效`。

- `segmentation.sentence_split_fallback`
  - 作用：是否启用句界回退切分。
  - 生效状态：`预留字段`（当前切分总是启用回退逻辑）。

### 2.6 上下文

- `context.use_prev_segment`
  - 作用：是否使用前文上下文。
  - 生效状态：`预留字段`（当前未按该开关切换）。

- `context.prev_segment_chars`
  - 作用：前文截断长度。
  - 生效状态：`已生效`（用于 segment 上下文截断）。

- `context.use_term_hints`
  - 作用：是否附带术语提示。
  - 生效状态：`预留字段`（当前默认会带命中术语）。

### 2.7 LLM 调用

- `llm.temperature`
  - 作用：采样温度。
  - 建议：`0.0`（确定性更高）。
  - 注意：部分模型不支持非默认温度，程序会自动回退到默认温度。
  - 生效状态：`已生效`。

- `llm.max_retries`
  - 作用：最大重试次数（JSON 失败/网络失败等）。
  - 生效状态：`已生效`。

- `llm.retry_backoff_seconds`
  - 作用：重试退避序列（秒）。
  - 生效状态：`已生效`。

- `llm.timeout_seconds`
  - 作用：单次 HTTP 超时。
  - 生效状态：`已生效`。

### 2.8 QA

- `qa.warn_ratio_limit`
  - 作用：warn 比例上限。
  - 生效状态：`已生效`。

- `qa.warn_min_cap`
  - 作用：warn 最低阈值封底。
  - 生效状态：`已生效`。

验收门槛计算：`warn_cap = max(total_segments * warn_ratio_limit, warn_min_cap)`。

## 3. 配置教程（推荐流程）

### 3.1 第一次跑（推荐）

1. 使用默认 `config.yaml`。
2. `resume` 先开启。
3. 先跑一本小书或样章，检查 `qa_report.json` 与阅读器显示。

### 3.2 切成“只导出译文”

```yaml
quote_mode:
  preserve_original: false
  add_translation: false
  translation_node_class: ai-quote-translation
```

然后：
- 关闭 `Resume` 或换新 `cache.sqlite`，再重跑。

### 3.3 提升稳定性（减少坏格式/超时）

```yaml
segmentation:
  max_chars_per_segment: 800
  max_chars_per_batch: 8000
  max_segments_per_batch: 25

llm:
  max_retries: 6
  timeout_seconds: 180
```

### 3.4 提升速度（网络稳定时）

```yaml
segmentation:
  max_chars_per_batch: 15000
  max_segments_per_batch: 60
```

并在 UI/CLI 把 `max_concurrency` 调高（例如 6~10，视 provider 限流而定）。

### 3.5 QA 太严格/太宽松怎么调

- 更严格：降低 `warn_ratio_limit`，降低 `warn_min_cap`。
- 更宽松：提高 `warn_ratio_limit`，提高 `warn_min_cap`。

示例：
```yaml
qa:
  warn_ratio_limit: 0.01
  warn_min_cap: 30
```

## 4. 常见问题

- 改了配置但输出没变化？
  - 大概率命中缓存。请关 `resume` 或换 `cache.sqlite`。

- 配置写错会怎样？
  - 未识别字段会被忽略。
  - 路径错误会在启动时报错。

- 可以用 JSON 配置吗？
  - 可以，和 YAML 字段等价。

## 5. 建议的配置管理方式

为不同场景建立多份配置文件：
- `config.default.yaml`
- `config.translation_only.yaml`
- `config.fast.yaml`
- `config.safe.yaml`

运行时按任务选择对应文件（UI 的 `Config` 路径或 CLI 的 `--config`）。
