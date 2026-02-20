# SQLite 缓存与迁移

当前版本会在首次运行自动创建以下表：

- `runs`
- `segments`
- `translations`
- `errors`

如需迁移，请在发布新版本时新增 `schema_version` 表并维护 SQL migration 脚本。
当前 `0.1.0` 为初始 schema，无历史迁移步骤。
