# Release Notes - v0.1.0

## 发布说明 / Release Notes

**发布日期 / Release Date**: 2026-02-26

---

## 新增功能 / New Features

### 阿里云百炼支持 / Alibaba DashScope Support
- ✅ 新增 `dashscope` 服务商支持
- ✅ 默认服务商改为阿里云百炼
- ✅ 默认模型改为 `qwen-plus`
- ✅ 支持 JSON Schema 和 JSON Object 两种格式自动检测
- ✅ 支持多种千问系列模型（qwen-plus, qwen-max, qwen-turbo 等）

### UI 改进 / UI Improvements
- ✅ 新增 DashScope API Key 输入框
- ✅ Provider 下拉列表增加 `dashscope` 选项
- ✅ 术语表生成支持 dashscope
- ✅ 修复术语表生成日志显示问题

### CLI 改进 / CLI Improvements
- ✅ `--provider` 增加 `dashscope` 选项
- ✅ `--fill-provider` 增加 `dashscope` 选项
- ✅ 默认值更新为 dashscope 配置

### 文档更新 / Documentation
- ✅ 双语 README（中英文）
- ✅ 双语 CONFIG_README
- ✅ 更新服务商表格和配置说明

---

## Bug 修复 / Bug Fixes

- 🔧 修复 DashScopeProvider JSON Schema 支持检测逻辑
- 🔧 修复 pipeline 默认模型匹配问题
- 🔧 修复术语表生成 provider 回退逻辑
- 🔧 修复 UI 日志显示错误的服务商名称

---

## 安装包信息 / Installer Info

**文件名 / Filename**: `epub2zh-faithful-client-v0.1.0.zip`
**大小 / Size**: ~24 MB
**包含内容 / Contents**:
- epub2zh-faithful-client.exe (主程序)
- _internal/ (运行环境)
- config.yaml (配置模板)
- termbase.yaml (术语表模板)
- README.md (使用说明)
- CONFIG_README.md (配置说明)

---

## 使用方法 / Usage

### 1. 解压并运行 / Extract and Run
```
解压 epub2zh-faithful-client-v0.1.0.zip
双击 epub2zh-faithful-client.exe 启动图形界面
```

### 2. 配置 API Key / Configure API Key
在界面中输入阿里云百炼 API Key：
- 获取地址：https://bailian.console.aliyun.com/
- 环境变量：`DASHSCOPE_API_KEY`

### 3. 开始翻译 / Start Translation
1. 选择输入 EPUB 文件
2. 设置输出路径
3. 选择模型（推荐 `qwen-plus`）
4. 点击 "Start Translation"

---

## 系统要求 / System Requirements

- Windows 10/11 (64-bit)
- 无需 Python 环境 / No Python required
- 需要网络连接（调用 API）/ Internet connection required

---

## 已知问题 / Known Issues

- Inno Setup 安装包构建需要单独安装 ISCC
- 某些杀毒软件可能误报（PyInstaller 打包导致）

---

## 变更日志 / Changelog

```
commit: Add DashScope provider support
- llm_client.py: Add DashScopeProvider class
- gui.py: Add dashscope UI options
- cli.py: Add dashscope CLI options
- pipeline.py: Fix default model selection
- termbase_generator.py: Update default provider
- pyproject.toml: Add dashscope dependency

commit: docs: update bilingual README
- Rewrite README.md with Chinese-English bilingual content
- Update CONFIG_README.md
- Add build instructions and FAQ
```

---

## 相关链接 / Links

- [GitHub Repository](https://github.com/Solisepia/epubAITranslater)
- [Issue Tracker](https://github.com/Solisepia/epubAITranslater/issues)
- [阿里云百炼控制台](https://bailian.console.aliyun.com/)

---

## 上传到 GitHub Release / Upload to GitHub Release

### 方法 1：使用 GitHub UI / Using GitHub UI

1. 访问 https://github.com/Solisepia/epubAITranslater/releases/new
2. 输入 Tag version: `v0.1.0`
3. 输入 Release title: `v0.1.0 - DashScope Support`
4. 粘贴上述发布说明
5. 上传 `epub2zh-faithful-client-v0.1.0.zip`
6. 点击 "Publish release"

### 方法 2：使用命令行 / Using Command Line

```bash
# 安装 gh CLI (如未安装)
# https://github.com/cli/cli

cd F:\Inventarium\epubTranslater\epubAITranslater

# 创建 release
gh release create v0.1.0 \
  --title "v0.1.0 - DashScope Support" \
  --notes-file RELEASE_NOTES.md \
  dist/epub2zh-faithful-client-v0.1.0.zip
```

---

**构建者 / Built by**: Automated Build Script
**构建时间 / Build Time**: 2026-02-26
