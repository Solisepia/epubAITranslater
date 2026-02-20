# epub2zh-faithful

EPUB -> 简体中文（直译忠实）本地 CLI 翻译器。

## 安装

```bash
pip install -e .
```

## 命令行

```bash
translate-epub input.epub -o output.epub \
  --provider openai \
  --draft-provider openai \
  --revise-provider deepseek \
  --cache cache.sqlite \
  --config config.yaml \
  --termbase termbase.yaml \
  --resume
```

支持 provider：`openai|deepseek|mixed`（测试用额外支持 `mock`）。

## 自动生成术语表

```bash
generate-termbase input.epub -o termbase.generated.yaml --min-freq 2 --max-terms 300
```

常用参数：
- `--min-freq`：最小词频（默认 2）
- `--max-terms`：最多输出术语数（默认 300）
- `--include-single-word`：包含单词术语（默认关闭）
- `--no-merge-existing`：不与已有输出文件合并（默认会合并）

生成结果会写入 `terms[]`，默认 `target` 为空，建议人工补全后再用于翻译约束。

## 简单图形界面

安装后可直接启动：

```bash
translate-epub-ui
```

界面里可配置：
- 输入/输出 EPUB
- provider 与 model
- config / termbase / cache 路径
- resume / keep-workdir / max-concurrency
- OpenAI / DeepSeek key（可选，填入后会写入当前进程环境变量）

点击 `Start Translation` 后会显示运行状态和产物路径。
运行过程中 `Logs` 会实时输出阶段进度（解包、抽取、批次翻译、QA、打包）。
界面会自动保存大部分表单输入，并在下次启动时自动恢复（保存文件：`~/.epub2zh_faithful_ui_state.json`；API Key 不会自动保存）。
点击 `Generate Termbase` 会基于当前 `Input EPUB` 自动生成/更新 `Termbase` 文件。
点击 `Edit Config` 可在 UI 内直接填写/保存完整配置表（不需要手改 YAML）。

## 打包成 Windows 客户端（无命令行）

可使用内置脚本构建桌面客户端：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows_client.ps1
```

构建结果：
- 默认（目录版）：`dist\epub2zh-faithful-client\epub2zh-faithful-client.exe`
- 单文件版：`powershell -ExecutionPolicy Bypass -File scripts\build_windows_client.ps1 -OneFile`

目录版会同时拷贝：
- `README.md`
- `CONFIG_README.md`
- `config.yaml`
- `termbase.yaml`

## 配置模板

- `config.yaml`
- `termbase.yaml`
- `style.yaml`
- `CONFIG_README.md`（`config.yaml` 全量字段说明与配置教程）

## 环境变量

- `OPENAI_API_KEY`
- `DEEPSEEK_API_KEY`

## 产物

输出目录下会生成：

- `<output>.epub`
- `<output_stem>_artifacts/qa_report.json`
- `<output_stem>_artifacts/qa_summary.md`

## 退出码

- `0`: 成功且 QA error=0
- `2`: 翻译完成但 QA error>0
- `1`: 运行失败

## 测试

```bash
python scripts/generate_fixtures.py
pytest -q
```
