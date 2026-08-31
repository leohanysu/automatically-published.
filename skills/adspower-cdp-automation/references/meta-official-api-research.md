# Meta 官方 API 发布调研结论（2026-08-01）

## 结论：官方 API 不适合本项目的多账号矩阵场景

用户场景是 AdsPower 多环境多账号（防关联指纹浏览器）运营外贸社媒。
直接用 Meta Graph API 发布会**把所有账号暴露在同一个 Developer App 下**，
等于告诉 Meta"这些号是同一个人"——击穿 AdsPower 的防关联体系，风控风险极高。
因此坚持浏览器自动化路线（MCP + Playwright CDP），不迁移到官方 API。

## 官方 API 事实（调研自 developers.facebook.com, v26.0）

### Facebook Reels 发布
- `POST /{page_id}/video_reels`
- 参数：`title`, `description`（支持 emoji）, `scheduled_publish_time`（定时发布）, `upload_phase` {START, FINISH}（两段式上传）, `video_id`, `video_state` {DRAFT, PUBLISHED, SCHEDULED}, `is_ai_generated`
- 错误码：368（滥用/不允许）、613（限流）、190（token 无效）、200（权限）、100（参数）、6000（上传失败）、104（签名）

### Instagram Reels 发布（两段式）
- `POST /{IG_ID>/media`（media_type=REELS，建容器）→ `POST /{IG_ID>/media_publish`（发布）
- 需要权限：`instagram_basic` + `instagram_content_publish`（FB 登录）或 `instagram_business_basic` + `instagram_business_content_publish`（IG 登录）
- 限流：24h 内 100 条/账户（media_publish 强制执行）
- 视频必须托管在公共 URL 上（Meta 会 cURL 你的视频）

### 配置门槛（为什么"麻烦"）
1. 注册 Meta 开发者（要真实 FB 个人号 + 手机验证）
2. 创建 App（选"管理公共主页"+"管理 Instagram"用例，要隐私政策 URL）
3. 绑定 Business Manager（主页和 IG 都要在 BM 下）
4. Business 登录授权（每账号一次）
5. 换 60 天长效 token（需 cron 续期）
6. 部分权限要 App Review（等几天）

## GitHub 现成项目（已搜）
- 官方 API 路线：`mrdotb/facebook-api-video-upload`（⭐57, node 分块上传）、`fbsamples/Facebook-Reels-Publishing-API-Postman-Collection`（官方示例）、`ralphcrisostomo/n8n-nodes-meta-publisher`（⭐19, n8n 节点，IG/FB/Threads 全支持，活跃维护）
- 非官方接口路线（⚠️ 封号风险）：`yuvraj108c/instagram-publisher`（⭐55, 邮箱密码登录发 IG，违反 ToS）
- 浏览器自动化路线：`xtea/auto-instagram`（Playwright + cookies）
- **没有**现成的"飞书 → Meta 自动发布"完整项目，飞书集成只能自己做

## 借鉴价值
- 学 n8n-nodes-meta-publisher 的"创建→轮询→发布→回写"流程设计
- 学官方 Postman 集合的 API 参数（万一某账号以后愿意正规授权，直接抄参数）
