# 发布验证截图怎么"看"：ds-vision-skill（2026-08-20 配置）

DeepSeek 等纯文本模型没有原生视觉能力，分析发布页/页面截图要绕道视觉 API。
本机已装 **ds-vision-skill**（https://github.com/Sorwcyra/ds-vision-skill，npx skills add 安装，
symlink 到 Hermes），GLM 免费竞速池 + comfly 兜底，超时自动降级。

## 日常用法（分析截图）

```bash
cd ~/.agents/skills/ds-vision-skill && powershell.exe -NoProfile -ExecutionPolicy Bypass \
  -File scripts/vision-router.ps1 -Path "<图片绝对路径>" -Prompt "<问题>" -Json -TimeoutSec 90
```

- 输出 JSON：`{task_type, tool_used, confidence, result, metadata}`
- 主模型用 `result` 继续推理；报告用户时提 `tool_used`（如 `glm:glm-4.6v-flash`）
- OCR 用 `-Intent ocr`；长文档走 mineru（需 MINERU_TOKEN）
- 截图流程：CDP `Page.captureScreenshot` 存 png → 调 vision-router → 读 result

## 降级链（本机已配）

`race(glm=glm-4.6v-flash, glm-thinking=glm-4.1v-thinking-flash) -> custom-1(glm-4v-flash, z.ai) -> custom-2(glm-4v, comfly)`

- z.ai key 格式 `<32hex>.<16hex>`，base `https://api.z.ai/api/paas/v4/chat/completions`
- GLM_API_KEY / GLM_BASE_URL 存 User scope 环境变量

## ⛔ 配置坑（2026-08-20 实测，改配置时看）

1. **模型名硬编码两处**：`scripts/vlm-vision.ps1` 的 `$channelDefaults` 和 `scripts/vision-router.ps1`
   的 `Get-RaceChannelConfig` 都要改（race 直接构造请求不走 vlm 默认值）。改完 `tool_used` 才显示新模型
2. **setup.ps1 只对 agnes 存 BaseUrl**：GLM_BASE_URL 要手动 `[Environment]::SetEnvironmentVariable(...,'User')`
3. **GLM 免费模型 1305 过载是常态**（`{"error":{"code":"1305","message":"service temporarily overloaded"}}`）——
   不是配置错，race 自动降级，日志 `code:3` = rate-limited 属正常降级
4. 单通道调试：`scripts/vlm-vision.ps1 -ImagePath <img> -Channel custom-2 -Json -TimeoutSec 60 -MaxTokens 50`

## ✅ 验证技巧（2026-08-20 发布验证实测）

- **TikTok 标签是否生效 = 视觉确认变蓝，别信 DOM 检测**：`box.querySelectorAll('a')` 常返回空（TikTok 不用 `<a>` 渲染标签，可能用 span/其他元素），但视觉上标签已是蓝色链接样式。截图 → vision-router 问"标签是蓝色链接还是普通黑字"是**唯一可靠验证**
- **截图前先滚动到目标区域**：`document.querySelector('.caption-container').scrollIntoView({block:'center'})` 再 `Page.captureScreenshot`，否则截到页面顶部看不到 Description
- **GLM OCR 会误读标签名**（如 `#desksetup`→`#desktop`、`#cozyvibes`→`#cozvybil`、`🍰`→`🎀`）：OCR 误差不影响判断"是否变蓝/是否完整"，但别拿 OCR 结果当精确文案
- 图片 >100KB 直接 base64 传 comfly 报 400 → 先 ffmpeg 压缩 `-vf scale=800:-1 -q:v 5` 再上传或 base64
