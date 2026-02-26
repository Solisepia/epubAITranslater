# 发布上传检查清单 / Release Upload Checklist

## v0.1.0 发布文件 / Release Files for v0.1.0

### 已生成的文件 / Generated Files

| 文件 / File | 大小 / Size | 类型 / Type | 路径 / Path |
|------------|------------|------------|-------------|
| 便携版 ZIP | ~24 MB | 主要发布文件 | `dist/epub2zh-faithful-client-v0.1.0.zip` |
| 安装版 EXE | ~24 MB | 安装包（ZIP 格式） | `dist/installer/epub2zh-faithful-client-setup.exe` |
| 安装脚本 | 1.2 KB | 批处理安装程序 | `dist/installer/install.bat` |

### 待上传到 GitHub Release / To Upload to GitHub Release

- [ ] `dist/epub2zh-faithful-client-v0.1.0.zip` (便携版 / Portable)
- [ ] `dist/installer/epub2zh-faithful-client-setup.exe` (安装版 / Installer)

---

## 上传步骤 / Upload Steps

### 使用 GitHub Web 界面 / Using GitHub Web UI

1. **访问 Release 页面** / **Visit Release Page**
   ```
   https://github.com/Solisepia/epubAITranslater/releases/new
   ```

2. **填写发布信息** / **Fill Release Information**
   
   **Tag version**: `v0.1.0` (从下拉列表选择)
   
   **Release title**: 
   ```
   v0.1.0 - DashScope Support
   ```
   
   **Description** (复制以下内容):
   ```markdown
   ## 新版本特性 / What's New
   
   ### 阿里云百炼支持 / Alibaba DashScope Support
   - ✅ 新增 dashscope 服务商
   - ✅ 默认服务商改为阿里云百炼
   - ✅ 默认模型改为 qwen-plus
   - ✅ 支持 JSON Schema 和 JSON Object 自动检测
   
   ### 文档更新 / Documentation
   - ✅ 中英文双语 README
   - ✅ 更新配置说明
   - ✅ 添加 FAQ 和使用指南
   
   ### Bug 修复 / Bug Fixes
   - 🔧 修复 DashScopeProvider 模型匹配
   - 🔧 修复术语表生成 provider 显示
   - 🔧 修复 pipeline 默认模型选择
   
   ## 下载 / Downloads
   
   - **便携版**: `epub2zh-faithful-client-v0.1.0.zip` - 解压即用
   - **安装版**: `epub2zh-faithful-client-setup.exe` - 运行 install.bat 安装
   ```

3. **上传文件** / **Upload Files**
   
   拖放或选择以下文件：
   - [ ] `F:\Inventarium\epubTranslater\epubAITranslater\dist\epub2zh-faithful-client-v0.1.0.zip`
   - [ ] `F:\Inventarium\epubTranslater\epubAITranslater\dist\installer\epub2zh-faithful-client-setup.exe`

4. **确认发布** / **Confirm Publish**
   - [ ] 设置为 "Latest release" (如果是最新版)
   - [ ] 点击 "Publish release"

---

## 验证发布 / Verify Release

发布后访问：
```
https://github.com/Solisepia/epubAITranslater/releases/tag/v0.1.0
```

确认：
- [ ] 两个文件都在 Assets 列表中
- [ ] 文件大小正确（约 24MB 每个）
- [ ] 发布说明显示完整

---

## 后续操作 / Post-Release Tasks

- [ ] 在项目 README 中更新下载链接
- [ ] 在项目文档中发布更新公告
- [ ] 通知用户使用新版本
- [ ] 创建新的 GitHub Issue 收集反馈

---

## 文件校验 / File Verification

### 便携版 / Portable Version
```powershell
# 验证 ZIP 内容
cd F:\Inventarium\epubTranslater\epubAITranslater\dist
tar -tf epub2zh-faithful-client-v0.1.0.zip | Select-String "epub2zh-faithful-client.exe"
```

### 安装版 / Installer Version
```powershell
# 验证安装包包含必要文件
cd F:\Inventarium\epubTranslater\epubAITranslater\dist\installer
tar -tf epub2zh-faithful-client-setup.exe | Select-String "install.bat"
```

---

## 已知问题 / Known Issues

- 安装包为 ZIP 格式，需要重命名为 `.zip` 或使用 7-Zip 打开
- 某些杀毒软件可能误报 PyInstaller 打包的程序
- Windows SmartScreen 可能警告未知发布者

---

**创建时间** / **Created**: 2026-02-26  
**创建者** / **By**: Automated Build Script  
**版本** / **Version**: v0.1.0
