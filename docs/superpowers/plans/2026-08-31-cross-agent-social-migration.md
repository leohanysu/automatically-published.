# Cross-Agent Social Publishing Migration Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有社媒自动发布流程整理为可迁移、可恢复、兼容 Codex/Claude Code/Cursor 等 Agent 的本地项目包，并提供面向纯小白的“奶团”向导；默认每次只处理一个视频，所有视频分析经 Comfly Gemini，首次运行先做预检，发布前必须得到明确确认。

**Architecture:** 采用“统一本地核心引擎 + Agent 适配说明 + 浏览器平台适配器 + 飞书模板供应器”的分层结构。Agent 只负责理解用户和调用命令，核心引擎负责配置、权限预检、媒体分析路由、AdsPower 生命周期、发布证据与恢复。飞书多维表格作为视频仓库和发布数据库；模板只复制无数据的结构、字段、视图和默认值。

**Tech Stack:** Python 3.11+、标准库 `argparse`/`dataclasses`/`json`/`logging`、pytest、AdsPower CDP、现有 `skills/adspower-cdp-automation` 脚本、Comfly Gemini API、飞书 Base API 或用户 OAuth、Markdown Agent rules。

## Global Constraints

- [ ] 在第一次改动前创建并保留新的时间戳备份；不覆盖既有备份目录 `C:\Users\Administrator\.codex\Codex project\backups\codex社媒自动化迁移包-2026-08-20-baseline-20260830-204720`。
- [ ] 严禁把任何真实 API key、Cookie、Token、账号密码写入源码、Markdown、测试夹具、日志或发布包；仅允许环境变量名和脱敏示例。
- [ ] 默认一次只处理一条视频；只有用户明确要求时才扩大数量。
- [ ] Meta/TikTok 保留现有自动发布；X/YouTube 默认直接发布；Pinterest 仅在用户明确选择时发布；Reddit 不纳入本版本。
- [ ] YouTube 发布流程必须选择“不是面向儿童（Not made for kids）”。
- [ ] 所有视频分析调用 Comfly Gemini；图片分析按已验证的 Agent/模型视觉能力路由，纯文本或不确定时调用 Comfly Gemini 图片分析。
- [ ] 预检失败不得发布；首次预检通过后，只能在用户明确确认后发布每个平台的一条测试视频。
- [ ] AdsPower 卡住、CDP 超时或窗口不可见时，按“强制关闭当前 profile 进程树 → 重新打开 → 置前 → 验证窗口和视口 → 继续/停止”的顺序处理。
- [ ] 单一问题超过三分钟仍未解决时，向用户用大白话说明正在做什么、卡在哪里、原因、下一步和是否需要用户操作。
- [ ] 外部平台已发布内容不可由本地回滚；回滚只恢复本地配置、模板元数据、检查点和证据目录。

---

## Task 1: Establish a clean package boundary and baseline backup

**Files:** `social_migrator/`, `templates/`, `onboarding/`, `adapters/`, `config/`, `tests/`, `.gitignore`, `pyproject.toml`.

- [ ] 运行 `Get-ChildItem -Recurse -File`、`rg -n "api[_-]?key|token|cookie|password|COMFLY|FEISHU"`，登记现有脚本入口、硬编码路径、敏感信息和可复用的稳定 Meta/TikTok 流程。
- [ ] 将当前工作区复制到新的时间戳备份目录，并生成 `backup-manifest.json`（文件清单、哈希、时间、版本）；验证备份可读且与源文件数量一致。
- [ ] 建立包结构：`social_migrator/{__init__.py,__main__.py,cli.py,config.py,contracts.py,errors.py,redact.py,evidence.py,recovery.py,feishu.py,comfly.py,media_router.py,adspower.py}`。
- [ ] 建立发布器目录：`social_migrator/publishers/{__init__.py,base.py,meta.py,tiktok.py,x.py,youtube.py,pinterest.py}`，先只放接口和明确的未实现错误，不在此阶段触发浏览器。
- [ ] 建立 `config/.env.example`、`.gitignore`、`pyproject.toml`，忽略 `.env`、Cookie、下载视频、截图、运行时状态、证据中的机密字段。
- [ ] 验证 `python -m compileall social_migrator` 和 `pytest -q`（此时允许无测试或仅结构测试，但命令必须可运行）。

## Task 2: Implement configuration, redaction, and deterministic CLI contracts

**Files:** `social_migrator/config.py`, `contracts.py`, `errors.py`, `redact.py`, `cli.py`, `__main__.py`, `tests/test_config.py`, `tests/test_cli_contracts.py`.

- [ ] 定义配置模型：Agent 名称、模型名称/版本、是否原生视觉、Comfly 模型、飞书 Base URL/token、AdsPower profile、选定平台、运行数量、确认策略和超时。
- [ ] 只从环境变量、用户本地配置文件或向导输入读取秘密；启动时拒绝明显的占位 key 和缺失必需项，并给出新手可读的修复提示。
- [ ] 实现脱敏函数，保证异常、日志、JSON 证据和 CLI 输出中的 key/token/cookie 只显示前后少量字符或 `[REDACTED]`。
- [ ] 实现命令：`python -m social_migrator wizard`、`preflight`、`publish --platform PLATFORM_NAME`、`rollback --run-id RUN_ID`、`status --run-id RUN_ID`；统一 JSON 结果结构、退出码和 `--dry-run`。
- [ ] 为缺少输入、预检失败、用户拒绝、发布失败、可恢复/不可恢复错误分别定义错误码。
- [ ] 测试配置合并优先级、脱敏覆盖、非法平台拒绝、默认单视频和 CLI JSON 输出。

## Task 3: Build the beginner-first “奶团” onboarding wizard

**Files:** `onboarding/wizard.md`, `onboarding/concepts.md`, `onboarding/permissions.md`, `social_migrator/wizard.py`, `tests/test_wizard.py`.

- [ ] 编写“奶团”固定开场和概念解释：Agent、模型、Comfly Gemini、AdsPower、飞书、多维表格、发布平台、权限和备份，用生活化语言说明用途、原因、获取位置和安全边界。
- [ ] 设计状态机：询问 Agent（Codex/Claude Code/Cursor/其他）、模型精确名称/版本、视觉能力、Comfly key、飞书 Base 链接/是否需要创建、AdsPower profile、平台选择和是否进行一条测试发布。
- [ ] 当用户没有 Base 链接时，明确解释“它是视频仓库+发布数据库”，再询问是否创建；当没有权限时，逐条告诉用户需要重新授权什么。
- [ ] 支持中断后从本地 `state/wizard-state.json` 恢复，状态文件仅保存非敏感选择和脱敏标识。
- [ ] 在向导结束时输出预检摘要、缺失项、下一步命令和“尚未发布任何视频”的明确状态。
- [ ] 用脚本化答案测试首次安装、缺失 Base、纯文本模型、用户拒绝发布、恢复中断五条路径。

## Task 4: Provision and verify a data-free Feishu template copy

**Files:** `templates/feishu/template-manifest.json`, `templates/feishu/README.md`, `social_migrator/feishu.py`, `tests/test_feishu_template.py`.

- [ ] 从现有项目记录中整理字段、字段类型、视图、状态值、平台文案字段、Pinterest 标签字段及默认值，写入版本化 manifest；不得写入历史视频、历史文案、发布记录或凭据。
- [ ] 实现飞书鉴权和权限预检：读取 Base/表/字段/记录、创建 Base/表/字段/视图、写入记录、上传附件；每项失败都返回新手说明。
- [ ] 优先调用官方 Base 复制能力；不可用时按 manifest 重建 Base、表、字段和视图，并记录 `provisioning-method`。
- [ ] 复制完成后运行 schema drift 检查，确认字段名/类型/必填项/默认值/平台列齐全，并将用户 Base id 保存到本地非敏感配置。
- [ ] 增加“只复制结构”的断言；测试样例中不得出现真实链接、视频、文案、Token。
- [ ] 为 Pinterest 提供默认标签策略：沿用用户确认的同行标签集合，不自动覆盖用户后续手工修改。

## Task 5: Implement Comfly media analysis routing

**Files:** `social_migrator/comfly.py`, `social_migrator/media_router.py`, `tests/test_media_router.py`, `tests/fixtures/media-capabilities.json`.

- [ ] 封装 Comfly Gemini 视频分析请求，要求返回时间戳、镜头拆解、可见文字、商品/人物/动作、场景、可复用创意结构和不确定性；统一重试、超时和脱敏日志。
- [ ] 封装图片分析请求；支持 Codex 原生视觉、其他已验证视觉模型、纯文本/不确定模型三种路由。
- [ ] 加入模型能力注册表和低敏图片探针；探针失败或结果不确定时自动回退 Comfly，不把图片原文写入日志。
- [ ] 以协议测试覆盖视频永远走 Comfly、Codex 视觉走本地、纯文本走 Comfly、探针失败回退、API 超时重试。

## Task 6: Harden AdsPower/CDP lifecycle and foreground recovery

**Files:** `social_migrator/adspower.py`, `tests/test_adspower_lifecycle.py`, `skills/adspower-cdp-automation/scripts/restore_sunbrowser_window.py`（仅在需要时复用/修补）。

- [ ] 实现 profile 启动、动态 CDP 端口发现、连接、窗口置前、视口验证和安全断开。
- [ ] 实现卡死恢复：验证目标 profile 后强制关闭其进程树，重新打开 profile，等待 CDP，置前窗口并再次验证；禁止误杀其他 profile。
- [ ] 记录每一步时间戳和结果，超过三分钟通过进度回调输出面向小白的说明。
- [ ] 使用模拟进程和 CDP 客户端测试成功、端口变化、窗口不可见、超时重启和不可恢复停止；真实强杀只放在手工验收清单，不放入自动化测试。

## Task 7: Port and verify platform publisher adapters

**Files:** `social_migrator/publishers/base.py`, `meta.py`, `tiktok.py`, `x.py`, `youtube.py`, `pinterest.py`, `tests/test_publishers.py`, `tests/fixtures/platform-pages/`.

- [ ] 定义统一发布器接口：`preflight`、`prepare`、`publish`、`verify`、`checkpoint`，输入为单条 Feishu 记录和媒体分析结果。
- [ ] 将现有稳定 Meta/TikTok 流程适配到接口，保留现有登录态和页面等待策略，不复制任何真实 Cookie。
- [ ] 实现 X 直接发布并验证帖子/视频已提交；页面失败时保存截图、页面标题、脱敏 URL 和恢复点。
- [ ] 实现 YouTube 直接发布，明确选择“不是面向儿童”，发布后验证状态/视频 URL。
- [ ] 实现 Pinterest 显式选择后发布，文案带网站 `https://www.marshkiky.com/`，标签默认使用用户确认集合；未选择时不得触发 Pinterest。
- [ ] 平台执行器默认只取一条待发布记录；单平台失败停止后续平台并保留可恢复检查点。
- [ ] 用页面 fixture 和 mock 浏览器测试按钮定位、YouTube 儿童设置、Pinterest 标签、重复运行幂等和失败截图。

## Task 8: Add preflight, evidence, checkpoints, resume, and rollback

**Files:** `social_migrator/evidence.py`, `recovery.py`, `social_migrator/preflight.py`, `social_migrator/runner.py`, `tests/test_recovery.py`.

- [ ] 在任何写操作前生成运行目录 `state/runs/RUN_ID/`，备份配置、模板 manifest、向导状态和当前记录摘要，所有内容脱敏。
- [ ] 实现预检清单：依赖、环境变量、Agent/model 能力、Comfly 连通性、飞书 schema/权限、AdsPower profile、平台登录态、单视频可用性。
- [ ] 为每个平台和每条记录写入原子 checkpoint，至少记录 `pending/prepared/published/verified/failed`、时间、错误码和证据路径。
- [ ] 支持从最近 checkpoint 恢复，已验证发布的平台不重复发布；对不可确认的外部状态先要求用户检查，不盲目重发。
- [ ] 实现本地 rollback，恢复到运行开始前的配置/manifest/state；明确输出“外部平台已发布内容不会被删除”。
- [ ] 测试中断恢复、重复运行、部分平台失败、证据缺失、回滚校验和三分钟进度消息。

## Task 9: Create cross-Agent adapters and beginner documentation

**Files:** `START_HERE.md`, `adapters/AGENTS.md`, `adapters/CLAUDE.md`, `.cursor/rules/social-publishing.mdc`, `README.md`.

- [ ] 为 Codex、Claude Code、Cursor 和通用 Markdown Agent 分别提供可被自动发现的入口，统一指向 `奶团` 向导和 `python -m social_migrator` 命令。
- [ ] 在每个适配器中声明：视频分析必须 Comfly、图片路由规则、默认单视频、发布确认、YouTube 非儿童、Pinterest 显式启用、三分钟大白话汇报和备份/回滚边界。
- [ ] 编写从零开始教程：安装依赖、填写环境变量、登录 AdsPower、准备飞书 Base、运行 wizard、preflight、确认测试发布、查看证据和恢复。
- [ ] 说明不同 Agent 首次使用时需要用户提供什么，以及“只需要把视频放进哪个字段”这一最小操作路径。
- [ ] 测试检查四个入口文件存在、关键安全规则一致、示例命令可复制运行且不含秘密。

## Task 10: Build the integration harness and run verification

**Files:** `tests/integration/test_first_run.py`, `tests/integration/fixtures/`, `scripts/run_preflight.ps1`, `scripts/run_preflight.sh`.

- [ ] 用全 mock 环境跑通“向导 → 模板供应 → 媒体路由 → 预检 → 用户确认 → 单视频多平台发布 → 证据”的主链路，不接真实账号。
- [ ] 加入可选的用户本地集成模式：只读检查真实飞书 schema、Comfly 连通性和 AdsPower 可见性，默认不发布。
- [ ] 执行 `pytest -q`、`python -m compileall social_migrator`、配置脱敏扫描和文档秘密扫描；失败时定位到具体任务。
- [ ] 手工验收清单覆盖窗口置前、强制重启、YouTube 非儿童设置、Pinterest 文案/标签、Meta/TikTok 回归和 >3 分钟提示。
- [ ] 更新 Obsidian 项目 `index.md`、`log.md`、`open-questions.md`，记录验证结果、未解决风险和下一步。

## Task 11: Package a reusable distribution artifact

**Files:** `pyproject.toml`, `install.ps1`, `install.sh`, `RELEASE.md`, `VERSION`, `scripts/build_migration_package.ps1`.

- [ ] 固定 Python 版本、依赖哈希/版本范围和跨平台安装说明；安装脚本只创建项目虚拟环境和本地目录，不修改全局系统配置。
- [ ] 构建 zip/tar 分发包，包含源码、适配器、向导、无数据模板 manifest、示例配置和文档；排除备份、运行状态、Cookie、视频和日志。
- [ ] 生成包清单与 SHA-256，执行“解压到空目录后 wizard/preflight 可启动”的烟雾测试。
- [ ] 在 `RELEASE.md` 中写明兼容 Agent、所需权限、回滚边界、已知风险、升级/备份步骤和不支持 Reddit 的范围。
- [ ] 完成发布前最终扫描，确认分发包中没有真实凭据、历史发布数据或用户个人信息。

## Verification Checklist

- [ ] 设计文档 `docs/superpowers/specs/2026-08-31-cross-agent-social-migration-design.md` 的每一项验收标准都能在上述任务中找到对应实现和测试。
- [ ] 对计划文件执行未完成标记和尖括号占位符扫描，确认无遗留占位内容。
- [ ] `rg -n "sk-|AIza|cookie|access_token|refresh_token|password" social_migrator onboarding adapters templates config tests` 只命中脱敏说明或变量名，不命中真实值。
- [ ] `pytest -q`、`python -m compileall social_migrator` 和分发包烟雾测试全部通过后，才可向用户报告“迁移包完成”。
