# 社媒自动化迁移包（跨 Agent 多平台发布）

> 打包时间：2026-08-20
> 状态：✅ 4 条视频全部发布完成（Meta FB+IG + TikTok + 飞书回写）

## 📦 包内容

```
社媒自动化迁移包/
├── 项目总结-社媒自动化发布-2026-08-20.md   ← 完整项目总结（含 12 条弯路与解法，必读）
├── README.md                               ← 本文件
├── scripts/                                ← 36 个发布脚本（含最终可用版）
├── logs/                                   ← 27 个过程日志（记录每次尝试与错误）
├── config/                                 ← 发布参数配置（标题/正文/标签 JSON）
└── skills/                                 ← 核心技能（adspower-cdp-automation + squishy-factory-copy）
```

## 🔧 最终可用脚本（直接用这些，别用旧版）

| 脚本 | 用途 | 状态 |
|------|------|------|
| `scripts/meta_publish_v2.py` | **Meta 发布最终版**（上传+文案+分享） | ✅ 2026-08-20 验证 |
| `scripts/tk_v10.py` | **TikTok 发布最终版**（DOM上传+标题+标签1.5s回车） | ✅ 2026-08-20 验证 |
| `scripts/meta_share_fix.py` | Meta 分享修正（立即分享+底部分享） | ✅ 验证 |
| `scripts/publish_dual.py` | 双发脚本（在 skills/squishy-factory-copy/scripts/） | ✅ 08-19 验证 |
| `skills/.../publish_ws.py` | 早期 websocket 发布 | ⚠️ 旧版参考 |

## ⚠️ 核心经验速查（详见项目总结）

1. **NO_PROXY 必须加**：`NO_PROXY="127.0.0.1,localhost"` 否则 websockets 连 CDP 被代理拦截
2. **端口现读**：浏览器重启后 DevToolsActivePort 会变，必须实时读取
3. **TikTok 只填标题+标签**，不要正文（Draft.js 光标坑）
4. **标签**：逐个输入 → 弹窗出现 → **等 1.5 秒** → 回车；不加空格
5. **真实鼠标/键盘**：React 应用只认 `Input.dispatchMouseEvent` / `dispatchKeyEvent`，不认 JS click/insertText
6. **上传**：TikTok 用 `DOM.querySelector('input[type=file]')` 直连（带 sessionId）；Meta 用 chooser 事件
7. **草稿弹窗**：点 Continue 不点 Discard（Discard 要二次确认卡死）
8. **视觉验证**：Codex 或已确认具备视觉能力的模型直接理解截图；只有纯文本模型或能力不确定时，才调用第三方视觉 API（默认 Comfly Gemini），不把 ds-vision 当作 Codex 必需依赖

## 🚀 恢复使用方法

1. 把 `skills/` 下两个技能复制回 `~/AppData/Local/hermes/skills/media/`
2. 用 `meta_publish_v2.py` 发 Meta、`tk_v10.py` 发 TikTok
3. 参数从 `config/pub_args*.json` 读取（或按飞书字段）
4. 记得先 `NO_PROXY="127.0.0.1,localhost"` 再跑

## 用户协作约定

- 未特别说明时，每次只发布 1 条视频。
- 同一问题超过 3 分钟未解决时，必须用大白话主动说明正在做什么、卡在哪里、可能原因和下一步；禁止静默长时间等待或连续重试。
