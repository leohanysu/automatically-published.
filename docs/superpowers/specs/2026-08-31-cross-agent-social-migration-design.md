# Cross-Agent Social Publishing Migration Package Design

**Date:** 2026-08-31  
**Status:** Design approved in conversation; awaiting written-spec review before implementation

## Goal

将当前已验证的社媒自动发布流程整理为一个可复制的迁移包，使首次使用者可以在 Codex、Claude Code、Cursor 或其他支持 Markdown 指令的 Agent 中，通过对话式向导完成环境、权限、飞书模板和平台配置，并安全地自动发布视频。

## Scope

第一版支持以下平台，安装时按用户勾选启用：

- Meta：Facebook + Instagram
- TikTok
- X
- YouTube
- Pinterest

Reddit 不纳入第一版。

第一版交付形态是通用项目迁移包，不创建或依赖 Codex 插件目录。包内提供 Agent 适配文件、统一 CLI、技能说明和本地安装向导。

## User Experience

用户将迁移包放入一个文件夹，用 Codex、Claude Code、Cursor 或其他 Agent 打开后输入“开始安装社媒自动发布”。Agent 的固定名称是“奶团”，语气必须像耐心的项目助理，面向完全没有技术背景的小白，不假设用户知道任何术语。

奶团在索要任何信息前，先用大白话解释三件事：这是什么、为什么需要、用户去哪里找。它不只说“请提供 token/API key”，而是解释“这是用来让奶团代表你访问某个服务的钥匙，不是登录密码，不要发到群里；你可以在这里复制给我，奶团只保存到本机私密配置”。

向导必须主动检查输入是否缺失，并指出具体缺口。例如用户没有提供飞书多维表格链接时，奶团要说：

> “我还缺一个飞书多维表格链接。飞书多维表格可以理解成你的‘视频仓库 + 发布数据库’：你把要发布的视频放进‘视频’字段，奶团会从这里读取视频，再补齐标题、正文、标签和发布状态。请打开你的多维表格，复制浏览器地址栏链接发给我；如果你还没有表格，我可以先帮你创建一份模板。”

对于每项输入，奶团都提供“已收到 / 还缺什么 / 下一步做什么”的明确反馈，不让用户猜状态。

奶团按顺序询问并解释：

1. 使用的 Agent 产品与具体模型版本。
2. 模型是否具备原生图片理解能力。
3. 要启用的社媒平台。
4. 飞书登录与目标工作空间/文件夹。
5. Comfly Gemini 凭证。
6. AdsPower 环境与平台登录状态。
7. 是否允许在安装完成后进行每个平台 1 条测试发布。

安装完成后，奶团还要用一段小白说明总结整个系统：飞书多维表格是“仓库和数据库”，Comfly Gemini 是“视频分析助手”，AdsPower 是“隔离的浏览器工作间”，社媒账号是“发布出口”，发布记录和备份是“账本”。同时说明用户日常只需把视频放入指定字段，奶团会补齐发布信息并按授权平台发布。

向导使用通俗中文说明每项权限用途、风险和缺失时的下一步。安装后的标准命令为：

```text
python -m social_migrator wizard
python -m social_migrator preflight
python -m social_migrator publish --count 1
python -m social_migrator rollback
```

首次验证先运行预检，不直接发布；预检通过后，只有用户明确确认才对每个已启用平台各发布 1 条测试视频。

## Architecture

### 1. Core engine

```text
social_migrator/
  cli.py                 # wizard / preflight / publish / rollback
  config.py              # local config loading and validation
  feishu.py              # auth, Base creation, schema, record IO, attachment IO
  media_router.py        # image/video analysis routing
  comfly.py              # Comfly Gemini and copy generation client
  adspower.py            # profile lifecycle, CDP, foreground recovery
  evidence.py            # manifests, screenshots, result records
  recovery.py            # retries, resume, rollback metadata
  publishers/
    meta.py
    tiktok.py
    x.py
    youtube.py
    pinterest.py
```

All core modules expose deterministic JSON results. Agent-specific Markdown files explain when and how to call the CLI; they do not duplicate business logic.

### 2. Agent adapters

```text
AGENTS.md
CLAUDE.md
.cursor/rules/social-publishing.mdc
START_HERE.md
```

Each adapter points to the same onboarding instructions and command contracts. `START_HERE.md` is the fallback for other agents. The package does not assume that a model name alone proves visual capability.

### 3. Local configuration and secrets

```text
.env.example
.gitignore
config/
  template-version.json
  local.example.json
state/
backups/
evidence/
```

Secrets are supplied through local environment variables or a local ignored configuration file. The migration package, Git history, evidence manifests, and normal logs never contain API keys, access tokens, or cookies. The installer validates presence without printing secret values.

## Media Analysis Routing

Video analysis is always sent to Comfly Gemini for every Agent and model.

Image analysis follows this decision tree:

```text
Codex with native vision      -> Agent-native image understanding
Other model with verified vision -> Agent-native image understanding
Pure-text or uncertain model  -> Comfly Gemini image API
```

If a model's capability is uncertain, the wizard performs a low-sensitivity image probe. A failed probe falls back to Comfly Gemini and records the reason. The user can override the result only through an explicit configuration choice.

## Feishu Template Provisioning

The package ships a versioned, data-free template manifest containing:

- Base and table display names
- Field names, types, select options and defaults
- Views, filters, sorting and required formulas
- Meta/TikTok/X/YouTube/Pinterest fields
- `Pinterest标题`, `Pinterest描述`, and `Pinterest标签`
- Default task status, publish time options, and user-controlled Pinterest tag default

The source manifest contains no historical videos, captions, publish records, account cookies, or long-lived tokens.

During installation:

1. Check for `lark-cli`; if missing, explain how to install it.
2. Authenticate the user account, using the CLI's QR/authorization flow when needed.
3. Check permissions to create a Base, create tables and fields, read/write records, and upload attachments.
4. Ask where the new Base should be created.
5. Prefer an official Base-copy operation when the account supports it.
6. Otherwise create a new Base and rebuild the structure from the manifest.
7. Create views and defaults, then read the result back for schema verification.
8. Save the new Base identifier only in local ignored configuration.

The new user receives a private, clean Base. Existing business data from the template owner is never copied. At most, a clearly marked, data-free example row may be included in a future version if explicitly enabled.

## Platform Behavior

- Meta and TikTok retain the currently validated automatic publish flow.
- X uploads, fills copy, and clicks the final publish action after preflight and user authorization.
- YouTube uploads, fills title/description, selects “not made for kids”, verifies privacy, and clicks Publish after authorization.
- Pinterest publishes only when the user explicitly requests it; the default Pinterest tag value is user-controlled and must not be overwritten by the installer.
- Each run defaults to one video unless the user explicitly requests a larger count.

Every platform publisher has a separate adapter, result schema, verification method, and retry boundary.

## Preflight and Permissions

Preflight checks:

- Agent and model are recorded.
- Image/video routing is resolved.
- Selected platform list is non-empty.
- Feishu authentication, Base schema, and writable fields are valid.
- Comfly credentials exist and the Gemini endpoint is reachable.
- AdsPower profile exists, browser is open, the target window is visible, and viewport height is usable.
- Selected platform sessions are logged in.
- Video file is readable and meets platform size/duration limits.
- YouTube audience and privacy fields are ready.

Permissions are grouped as required, publishing-related, and optional destructive actions. The wizard requests only permissions needed for selected platforms. It explains that platform login, browser automation, and Feishu access are separate approvals.

### Beginner-friendly explanation contract

Every permission or missing-input message must contain:

1. 人话名称：例如“飞书视频仓库权限”。
2. 用途：例如“让我读取你放进去的视频，并把标题、正文、标签写回同一行”。
3. 不提供会怎样：例如“没有它，我只能看到表格链接，不能读取视频或更新发布状态”。
4. 获取方式：给出页面位置、按钮名称或可点击链接类型。
5. 安全边界：说明是否只保存在本机、是否会读取历史内容、是否会执行发布。

The wizard must distinguish these states in plain language: link missing, link provided but not accessible, authentication missing, permission insufficient, table schema incomplete, and ready. It must not collapse them into a generic “配置失败”。

## Safety, Backup, and Recovery

Before the first mutation, create a timestamped backup containing:

- Package configuration and version metadata
- Feishu template/schema manifest
- Existing local state needed for rollback

The publisher uses a per-record, per-platform transaction:

1. Select one record.
2. Create an evidence entry before upload.
3. Publish to platforms sequentially.
4. Verify each result before writing success state.
5. Stop remaining platforms after a meaningful failure and record resume data.

AdsPower recovery is explicit: if the profile is occupied, CDP handshake times out, or the browser stops responding, force-close the current profile process tree, reopen the profile, bring the window to the foreground, verify the viewport, and resume from the last verified checkpoint.

Rollback restores local configuration and template metadata. It does not attempt to delete already-published external posts; evidence contains their URLs and clearly explains any manual cleanup required.

Any operation lasting longer than three minutes without resolution must produce a plain-language progress update stating what is happening, where it is stuck, why, and the next action. Retries have bounded counts and are logged.

## Testing Strategy

1. Unit tests for config validation, capability routing, template manifest validation, redaction, and retry state transitions.
2. Contract tests using mocked Feishu, Comfly, and publisher responses.
3. Installation tests for Codex, Claude Code, Cursor, and the generic `START_HERE.md` path.
4. A disposable Feishu workspace test that creates a clean Base from the manifest and verifies fields/views/defaults.
5. Browser smoke tests that verify AdsPower recovery, foreground restoration, upload completion, and platform-specific final confirmation.
6. End-to-end test mode that runs all preflight checks and requires explicit confirmation before one test publish per selected platform.

## Acceptance Criteria

- A new user can start the wizard from Codex, Claude Code, or Cursor without editing core code.
- The assistant presents itself as “奶团” and explains every requested concept and permission in plain language suitable for a first-time Feishu user.
- If the Feishu Base link is missing, the wizard explicitly asks for it, explains that the Base is the user's video repository/database, and explains where to place videos for future publishing.
- The wizard asks for Agent and model, determines image capability, and always routes video analysis through Comfly Gemini.
- A first-time Feishu user can authenticate and receive a clean personal copy of the template structure without historical records.
- Users can select any subset of the five supported platforms.
- Preflight catches missing permissions or login state before publishing.
- A confirmed test run publishes at most one video per selected platform and records verifiable results.
- X and YouTube click final publish; YouTube selects “not made for kids”.
- Pinterest respects the user-controlled default tag field.
- Secrets are absent from package files, logs, and evidence.
- A stalled AdsPower session is forcibly recovered according to the documented rule.
- All changes and external results are backed up and resumable.

## Non-Goals for Version 1

- No Codex plugin marketplace package.
- No Reddit publisher.
- No hosted multi-tenant service.
- No automatic deletion or rollback of posts already published to external platforms.
- No copying of template owner's historical content or credentials.

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Agent or model cannot access images | Capability probe and Comfly Gemini fallback |
| Feishu copy API unavailable | Manifest-based Base reconstruction |
| AdsPower window hidden or stale | Foreground/viewport check and forced profile restart |
| Platform UI changes | Platform-specific selectors, smoke tests, evidence-driven verification |
| Accidental duplicate posting | One-video default, per-platform checkpoints, bounded retries |
| Secret leakage during migration | Environment-only secrets, redaction tests, ignored local config |
