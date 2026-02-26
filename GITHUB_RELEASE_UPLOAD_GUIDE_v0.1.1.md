# GitHub Release 上传指南 / GitHub Release Upload Guide

## 版本信息 / Release Information

- **Tag**: v0.1.1
- **Title**: v0.1.1 - qwen-mt-plus Support & Bug Fixes
- **Commit**: d2850f4

---

## 安装包文件 / Installer Files

### 主要安装包 / Main Installer

| 文件 / File | 大小 / Size | 路径 / Path |
|------------|------------|-------------|
| Inno Setup 安装包 | 19 MB | `dist/installer/epub2zh-faithful-client-setup-0.1.0.exe` |
| 便携版 ZIP | 24 MB | `dist/epub2zh-faithful-client-v0.1.1-hotfix.zip` |

---

## 上传步骤 / Upload Steps

### 方法 1：GitHub Web 界面（推荐）/ Method 1: GitHub Web UI (Recommended)

1. **访问创建 Release 页面** / **Visit Create Release Page**
   ```
   https://github.com/Solisepia/epubAITranslater/releases/new
   ```

2. **填写发布信息** / **Fill Release Information**
   
   **Tag version**: `v0.1.1` (新建)
   
   **Release title**: 
   ```
   v0.1.1 - qwen-mt-plus Support & Bug Fixes
   ```
   
   **Description** (复制以下内容):
   ```markdown
   ## 新版本特性 / What's New
   
   ### qwen-mt-plus 支持 / qwen-mt-plus Support
   - ✅ 新增阿里云百炼专用翻译模型 qwen-mt-plus 支持
   - ✅ 自动检测源语言，目标语言为简体中文
   - ✅ 支持 translation_options 参数配置
   - ✅ 术语表生成和正式翻译均可使用
   
   ### Provider 默认模型 / Provider Default Models
   | Provider | 默认模型 |
   |----------|---------|
   | dashscope | qwen-plus |
   | dashscope-mt | qwen-mt-plus |
   | deepseek | deepseek-chat |
   | openai | gpt-5-mini |
   
   ### Bug 修复 / Bug Fixes
   - 🔧 修复 qwen-mt API 响应解析（纯文本非 JSON）
   - 🔧 修复 DashScope system 角色错误
   - 🔧 修复术语表生成卡在 MT 模型的问题
   - 🔧 修复术语表填充默认模型配置
   
   ### 文档更新 / Documentation
   - 📝 README 更新 Provider 默认模型说明
   - 📝 添加模型选择逻辑说明
   - 📝 添加术语表填充配置说明
   
   ## 下载 / Downloads
   
   - **Inno Setup 安装包**: `epub2zh-faithful-client-setup-0.1.0.exe` (19MB) - 推荐
   - **便携版 ZIP**: `epub2zh-faithful-client-v0.1.1-hotfix.zip` (24MB)
   
   ## 使用建议 / Usage Tips
   
   - 正式翻译推荐使用 `dashscope` + `qwen-plus`
   - 纯文本翻译可使用 `dashscope-mt` + `qwen-mt-plus`
   - 术语表填充推荐使用 `qwen-plus`（遵循 JSON Schema）
   ```

3. **上传文件** / **Upload Files**
   
   点击 "Attach binaries by dropping them here or selecting them"
   
   上传以下文件：
   - [ ] `dist/installer/epub2zh-faithful-client-setup-0.1.0.exe` (19 MB)
   - [ ] `dist/epub2zh-faithful-client-v0.1.1-hotfix.zip` (24 MB)
   
   等待上传完成。

4. **发布** / **Publish**
   - 勾选 "Set as the latest release"
   - 点击 "Publish release"

---

### 方法 2：使用 gh CLI / Method 2: Using gh CLI

如果已安装 GitHub CLI：

```bash
# 1. 登录 GitHub
gh auth login

# 2. 创建 release 并上传文件
cd F:\Inventarium\epubTranslater\epubAITranslater

# 创建 release
gh release create v0.1.1 \
  --title "v0.1.1 - qwen-mt-plus Support & Bug Fixes" \
  --notes "## 新版本特性\n\n### qwen-mt-plus 支持\n- 新增阿里云百炼专用翻译模型支持\n- 自动检测源语言\n\n### Provider 默认模型\n- dashscope: qwen-plus\n- dashscope-mt: qwen-mt-plus\n- deepseek: deepseek-chat\n- openai: gpt-5-mini\n\n### Bug 修复\n- 修复 qwen-mt API 响应解析\n- 修复术语表生成问题" \
  dist/installer/epub2zh-faithful-client-setup-0.1.0.exe \
  dist/epub2zh-faithful-client-v0.1.1-hotfix.zip

# 3. 验证上传
gh release view v0.1.1
```

---

## 验证发布 / Verify Release

上传完成后，访问：
```
https://github.com/Solisepia/epubAITranslater/releases/tag/v0.1.1
```

确认：
- [ ] Release title 正确
- [ ] 发布说明显示完整
- [ ] 两个安装包都在 Assets 列表中
- [ ] 文件大小正确（19MB 和 24MB）

---

## 后续操作 / Post-Release Tasks

- [ ] 在项目 README 中更新下载链接
- [ ] 通知用户使用新版本
- [ ] 创建 Issue 收集用户反馈

---

## 安装包说明 / Installer Notes

### Inno Setup 安装包 (推荐)
- 真正的 Windows 安装程序
- 自动创建快捷方式
- 可选择安装目录
- 包含卸载程序

### 便携版 ZIP
- 解压即用
- 不写注册表
- 可放在 U 盘
- 多个版本共存

---

**创建日期 / Created**: 2026-02-26  
**Commit**: d2850f4
