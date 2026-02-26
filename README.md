# epub2zh-faithful

**EPUB 到简体中文的直译忠实翻译器** / **EPUB to Simplified Chinese Faithful Literal Translator**

[![GitHub Release](https://img.shields.io/github/v/release/Solisepia/epubAITranslater)](https://github.com/Solisepia/epubAITranslater/releases)
[![License](https://img.shields.io/github/license/Solisepia/epubAITranslater)](LICENSE)

---

## 功能特性 / Features

- **忠实直译**：保持原文结构和术语准确性 / **Faithful Translation**: Preserves source structure and terminology accuracy
- **术语表支持**：自动抽取和翻译术语，保持全书一致性 / **Termbase Support**: Auto-extract and translate terms for consistency
- **断点续翻**：支持缓存，中断后可继续 / **Resume Support**: Cache-based translation, resume from interruption
- **质量控制**：自动 QA 检查，输出质量报告 / **Quality Assurance**: Automatic QA checks with quality reports
- **图形界面**：简单易用的 GUI / **GUI**: Easy-to-use graphical interface
- **多模型支持**：OpenAI / DeepSeek / 阿里云百炼 / **Multi-Model**: OpenAI / DeepSeek / Alibaba DashScope

---

## 快速开始 / Quick Start

### 下载安装包 / Download Installer

从 [GitHub Releases](https://github.com/Solisepia/epubAITranslater/releases) 下载：
- **最新版本**：[Latest Release](https://github.com/Solisepia/epubAITranslater/releases/latest)
- **安装包**：`epub2zh-faithful-client-setup.exe`

### 环境要求 / Requirements

- Windows 10/11
- Python 3.11+（源码安装需要）/ Python 3.11+ (for source installation)

---

## 使用方法 / Usage

### 图形界面 / GUI

1. 启动程序 / Launch the application:
   ```bash
   translate-epub-ui
   ```

2. 配置参数 / Configure:
   - **Input EPUB**: 输入 EPUB 文件 / Input EPUB file
   - **Output EPUB**: 输出路径 / Output path
   - **Provider**: 选择 AI 服务商 / Select AI provider
   - **Model**: 选择模型 / Select model
   - **API Key**: 填写对应服务商的密钥 / Enter API key

3. 点击 **Start Translation** 开始翻译 / Click **Start Translation** to start

### 命令行 / CLI

```bash
translate-epub input.epub -o output.epub \
  --provider dashscope \
  --model qwen-plus \
  --cache cache.sqlite \
  --config config.yaml \
  --termbase termbase.yaml \
  --resume
```

#### 支持的服务商 / Supported Providers

| Provider | 环境变量 / Env Var | 默认模型 / Default Model | 说明 / Description |
|----------|-------------------|-------------------------|-------------------|
| `dashscope` | `DASHSCOPE_API_KEY` | `qwen-plus` | 阿里云百炼通用模型 |
| `dashscope-mt` | `DASHSCOPE_API_KEY` | `qwen-mt-plus` | 阿里云百炼专用翻译模型（自动检测源语言） |
| `openai` | `OPENAI_API_KEY` | `gpt-5-mini` | OpenAI GPT 模型 |
| `deepseek` | `DEEPSEEK_API_KEY` | `deepseek-chat` | 深度求索模型 |
| `mixed` | 多个 / Multiple | 分别配置 / Configure separately | 初译和润色使用不同服务商 |
| `mock` | 无需 / None | 测试用 / For testing | 测试用，不实际调用 API |

#### 模型选择逻辑 / Model Selection Logic

**正式翻译时**（优先级从高到低）：
1. 用户指定 `--model` 或 GUI Model 输入框的值
2. Provider 的默认模型（见上表）
3. 全局 fallback：`gpt-5-mini`

**术语表填充时**：
- GUI：使用当前选择的 Model 或 `qwen-plus`
- CLI：`--fill-model` 参数或默认 `qwen-plus`
- ⚠️ 术语表填充**不会**自动跟随 `--provider` 的默认模型

#### 术语表填充默认配置 / Termbase Fill Defaults

| Provider | 术语表填充默认模型 | 推荐场景 |
|----------|------------------|---------|
| `dashscope` | `qwen-plus` | ✅ 推荐：遵循 JSON Schema，可靠 |
| `dashscope-mt` | 不推荐用于术语 | ⚠️ 仅返回纯文本，不适合术语翻译 |
| `openai` | `gpt-5-mini` | ✅ 推荐：遵循 JSON Schema |
| `deepseek` | `deepseek-chat` | ✅ 推荐：遵循 JSON Schema |

---

## 自动生成术语表 / Auto-Generate Termbase

```bash
generate-termbase input.epub -o termbase.yaml \
  --min-freq 2 \
  --max-terms 300 \
  --fill-empty-targets \
  --fill-provider dashscope \
  --fill-model qwen-plus
```

### 常用参数 / Common Options

| 参数 / Option | 说明 / Description | 默认值 / Default |
|---------------|-------------------|-----------------|
| `--min-freq` | 最小词频 / Minimum frequency | 2 |
| `--max-terms` | 最多术语数 / Max terms | 300 |
| `--include-single-word` | 包含单词术语 / Include single words | false |
| `--fill-empty-targets` | AI 填充空译文 / AI-fill empty targets | false |
| `--fill-provider` | 填充服务商 / Fill provider | dashscope |
| `--fill-model` | 填充模型 / Fill model | qwen-plus |

---

## 配置说明 / Configuration

### 基础配置 / Basic Config (`config.yaml`)

```yaml
style: faithful_literal
translate_toc: true
translate_titles: true
```

### 风格选项 / Style Options

| 风格 / Style | 说明 / Description | 适用场景 / Use Case |
|-------------|-------------------|-------------------|
| `faithful_literal` | 忠实直译（默认） / Faithful literal (default) | 技术文档 / 术语敏感 |
| `faithful_fluent` | 忠实流畅 / Faithful fluent | 通用阅读 |
| `literary_cn` | 文学风格 / Literary | 小说/散文 |
| `concise_cn` | 简洁风格 / Concise | 摘要/速读 |

### 高级配置 / Advanced Config

详见 [CONFIG_README.md](CONFIG_README.md) / See [CONFIG_README.md](CONFIG_README.md) for details.

---

## 环境变量 / Environment Variables

| 变量 / Variable | 服务商 / Provider | 获取方式 / How to Get |
|----------------|------------------|---------------------|
| `DASHSCOPE_API_KEY` | 阿里云百炼 / Alibaba DashScope | [百炼控制台](https://bailian.console.aliyun.com/) |
| `OPENAI_API_KEY` | OpenAI | [OpenAI Platform](https://platform.openai.com/) |
| `DEEPSEEK_API_KEY` | 深度求索 / DeepSeek | [DeepSeek Platform](https://platform.deepseek.com/) |

---

## 产物说明 / Output Artifacts

翻译完成后，输出目录下生成：
After translation, the following files are generated:

| 文件 / File | 说明 / Description |
|------------|-------------------|
| `<output>.epub` | 翻译后的 EPUB / Translated EPUB |
| `<output>_artifacts/qa_report.json` | QA 详细报告 / QA detailed report |
| `<output>_artifacts/qa_summary.md` | QA 摘要 / QA summary |

---

## 退出码 / Exit Codes

| 代码 / Code | 含义 / Meaning |
|------------|---------------|
| `0` | 成功，QA 无错误 / Success, QA passed |
| `2` | 翻译完成，但 QA 有警告 / Translated, QA has warnings |
| `1` | 运行失败 / Execution failed |

---

## 打包构建 / Build & Package

### 依赖安装 / Install Dependencies

```bash
pip install -e .
```

### 构建 Windows 客户端 / Build Windows Client

```powershell
# 目录版 / Directory version
powershell -ExecutionPolicy Bypass -File scripts\build_windows_client.ps1

# 单文件版 / Single-file version
powershell -ExecutionPolicy Bypass -File scripts\build_windows_client.ps1 -OneFile

# 安装包版 / Installer version
powershell -ExecutionPolicy Bypass -File scripts\build_windows_installer.ps1
```

### 构建产物 / Build Output

- **目录版**：`dist\epub2zh-faithful-client\`
- **安装包**：`dist\installer\epub2zh-faithful-client-setup.exe`

---

## 测试 / Testing

```bash
# 生成测试数据 / Generate test fixtures
python scripts\generate_fixtures.py

# 运行测试 / Run tests
pytest -q
```

---

## 常见问题 / FAQ

### Q: 改了配置但结果没变化？ / Config changed but no effect?

A: 检查是否开启了 `--resume` 命中缓存。关闭 resume 或更换 cache 文件。
A: Check if `--resume` is enabled and hitting cache. Disable resume or change cache file.

### Q: 术语表有什么用？ / What's the use of termbase?

A: 术语表保证专业术语翻译一致性，避免同一名词多种译法。
A: Termbase ensures consistent translation of terminology throughout the book.

### Q: 如何选择服务商？ / How to choose a provider?

A: 推荐顺序：阿里云百炼 > DeepSeek > OpenAI（根据成本和可用性选择）
A: Recommended: Alibaba DashScope > DeepSeek > OpenAI (based on cost and availability)

---

## 项目结构 / Project Structure

```
epubAITranslater/
├── src/epub2zh_faithful/    # 源代码 / Source code
├── scripts/                  # 构建脚本 / Build scripts
├── tests/                    # 测试 / Tests
├── config.yaml               # 配置模板 / Config template
├── termbase.yaml             # 术语表模板 / Termbase template
└── README.md                 # 本文件 / This file
```

---

## 许可证 / License

MIT License - 详见 [LICENSE](LICENSE) 文件 / See [LICENSE](LICENSE) file

---

## 相关链接 / Links

- [GitHub Repository](https://github.com/Solisepia/epubAITranslater)
- [Issues](https://github.com/Solisepia/epubAITranslater/issues)
- [Releases](https://github.com/Solisepia/epubAITranslater/releases)

---

**最后更新 / Last Updated**: 2026-02-26
