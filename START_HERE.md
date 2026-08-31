# 奶团自动发布迁移包

奶团会先问你使用哪个 Agent、什么模型、是否能看图片、飞书表格在哪里，以及要启用哪些平台。

飞书多维表格可以把它理解成“视频仓库 + 发布数据库”：你只要把待发布视频放进约定的视频字段，奶团会根据视频分析补充标题、正文、标签和各平台发布状态。

先运行：

```bash
python -m social_migrator wizard
python -m social_migrator preflight
```

预检通过后，奶团仍会向你确认，才会发布一条视频。视频分析统一使用 Comfly Gemini；图片方面，Codex/GPT 或其他已确认具备视觉能力的模型直接看图，纯文本模型才调用 Comfly Gemini；YouTube 发布时会选择“不是面向儿童”。
