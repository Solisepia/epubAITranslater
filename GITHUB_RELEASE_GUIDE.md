# GitHub Release 上传指南 / GitHub Release Upload Guide

## 自动推送已完成 / Automatic Push Completed

✅ 代码已推送到 GitHub  
✅ 标签 v0.1.0 已创建并推送  
✅ RELEASE_NOTES.md 已生成  

## 手动上传发布文件 / Manual Upload Steps

### 方法 1：GitHub Web 界面（推荐）/ Method 1: GitHub Web UI (Recommended)

1. **打开创建 Release 页面** / **Open Create Release Page**
   ```
   https://github.com/Solisepia/epubAITranslater/releases/new
   ```

2. **填写发布信息** / **Fill Release Information**
   - **Tag version**: `v0.1.0` (已存在，选择即可)
   - **Release title**: `v0.1.0 - DashScope Support`
   - **Description**: 复制 RELEASE_NOTES.md 的内容

3. **上传文件** / **Upload Files**
   - 点击 "Attach binaries by dropping them here or selecting them"
   - 上传以下文件：
     - `dist/epub2zh-faithful-client-v0.1.0.zip` (便携版 / Portable)
     - `dist/installer/epub2zh-faithful-client-setup.exe` (安装版 / Installer)
   - 等待上传完成（每个约 24MB）

4. **发布** / **Publish**
   - 点击 "Publish release" 按钮

---

### 方法 2：使用 gh CLI / Method 2: Using gh CLI

如果已安装 GitHub CLI：

```bash
# 1. 登录 GitHub
gh auth login

# 2. 上传发布文件
cd F:\Inventarium\epubTranslater\epubAITranslater

gh release upload v0.1.0 \
  dist/epub2zh-faithful-client-v0.1.0.zip \
  --clobber

# 3. 验证上传
gh release view v0.1.0
```

---

### 方法 3：使用 PowerShell 和 GitHub API / Method 3: Using PowerShell and GitHub API

```powershell
# 设置变量
$token = "YOUR_GITHUB_TOKEN"
$repo = "Solisepia/epubAITranslater"
$tag = "v0.1.0"
$zipPath = "F:\Inventarium\epubTranslater\epubAITranslater\dist\epub2zh-faithful-client-v0.1.0.zip"

# 获取上传 URL
$release = Invoke-RestMethod `
  -Uri "https://api.github.com/repos/$repo/releases/tags/$tag" `
  -Headers @{ Authorization = "token $token" }

$uploadUrl = $release.upload_url -replace "\{.*$", ""

# 上传文件
Invoke-RestMethod `
  -Uri "$uploadUrl?name=epub2zh-faithful-client-v0.1.0.zip" `
  -Method POST `
  -Headers @{
    Authorization = "token $token"
    "Content-Type" = "application/zip"
  } `
  -InFile $zipPath
```

---

## 获取 GitHub Token / Get GitHub Token

1. 访问 https://github.com/settings/tokens/new
2. 输入 Note: `epub-translator-release`
3. 勾选权限 / Select scopes:
   - ✅ `repo` (Full control of private repositories)
4. 点击 "Generate token"
5. **复制并保存 token**（只显示一次）

---

## 验证发布 / Verify Release

上传完成后，访问：
```
https://github.com/Solisepia/epubAITranslater/releases/tag/v0.1.0
```

确认：
- ✅ 发布说明显示正确
- ✅ epub2zh-faithful-client-v0.1.0.zip 在 Assets 列表中
- ✅ 文件大小约 24MB

---

## 后续操作 / Next Steps

1. 在项目中发布更新公告
2. 更新项目文档的下载链接
3. 通知用户使用新版本

---

## 文件位置 / File Locations

- **发布包**: `dist/epub2zh-faithful-client-v0.1.0.zip`
- **发布说明**: `RELEASE_NOTES.md`
- **源代码**: 已推送到 GitHub main 分支

---

**创建日期 / Created**: 2026-02-26
