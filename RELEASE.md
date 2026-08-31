# 发布包说明

当前版本：0.1.0

## 包含内容

- `social_migrator/`：统一 CLI、配置、预检、媒体路由、证据和平台适配器
- `templates/feishu/`：无历史数据的飞书结构模板
- `adapters/`、`.cursor/rules/`：不同 Agent 的入口说明
- `config/.env.example`：仅变量名示例

## 不包含内容

不会打包真实 API key、Cookie、飞书记录、视频、日志、运行状态或备份。Reddit 不在当前版本范围内。

## 发布前检查

```bash
python -m compileall social_migrator
pytest -q
python -m social_migrator preflight
```
