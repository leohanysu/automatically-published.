---
name: adspower-cdp-automation
description: 用 AdsPower SunBrowser 做浏览器自动化时先看这里（CDP/MCP 要点、覆盖层绕过、进程清理）。
version: 1.0.0
author: Hermes Agent
metadata:
  hermes:
    tags: [adspower, cdp, playwright, mcp, sunbrowser, automation, windows]
    related_skills: [feishu-adspower-meta-publish, computer-use-fallback, comfly-proxy]
---

# AdsPower CDP 浏览器自动化（通用技术栈）

## When to Use

- 需要通过 AdsPower SunBrowser 环境做任何浏览器自动化（Meta 发布、社媒操作、爬取等）
- 用 MCP `adspower-local-api` 或 Playwright CDP 直连驱动指纹浏览器
- 遇到点击被拦截、MCP 调用返回空、连接超时等 Adspower 环境特有问题

## 核心事实

- 环境 = AdsPower profile（如 `k1dqriqs` 海外捏捏乐 / `k1egodto` 美区压缩沙发）
- CDP 端口从 `D:\.ADSPOWER_GLOBAL\cache\<profile_id>_<suffix>\DevToolsActivePort` 读取（第一行端口，第二行 ws 路径）
- **Playwright 连接必须用 `ws://`（AdsPower 新版 7.7.x 实测，2026-08-20）**：`p.chromium.connect_over_cdp("http://127.0.0.1:<port>")` 返回 **503 "This does not look like a DevTools server, try connecting via ws://"**；`http://` 的 /json/version、/json/list 也全 503。正确：`connect_over_cdp(f"ws://127.0.0.1:{port}{ws_path}")`（ws_path 读 DevToolsActivePort 第二行，如 `/devtools/browser/<uuid>`）
- **优先复用已打开的 SunBrowser 窗口**，不要重复开环境
- **venv 的 playwright 损坏修复**（报 `ModuleNotFoundError: No module named 'greenlet._greenlet'`）：`python -m pip install --force-reinstall greenlet`（只重装 greenlet，不动 playwright）

## ⛔ CDP websocket 连接失败三查（2026-08-20 实测，缺一不可）

报 `did not receive a valid HTTP response` / `InvalidMessage` / 连接直接 EOF 时，按序排查：

1. **系统代理拦截 localhost（最坑，本日复现）**：本机有 HTTP 代理 `127.0.0.1:10808`，`websockets.connect("ws://127.0.0.1:<port>/...")` 会**走代理** → 握手失败。修复：python 命令前加 `NO_PROXY="127.0.0.1,localhost" no_proxy="127.0.0.1,localhost"`（或脚本内 `os.environ["NO_PROXY"]="127.0.0.1,localhost"`）。**MCP connect_browser_with_ws 能连但自写 websockets 连不上 = 先怀疑代理**（MCP 内部不走代理）
2. **浏览器整个没在跑**：`wmic process where "name='SunBrowser.exe'"` 无输出 = 环境浏览器挂了（非最小化，是进程没了）。修复：MCP `open_browser`（`headless:"0"`，profile_id）重新拉起 → 拿新端口（`debug_port`）→ 重新 `connect_browser_with_ws`。注意 `--remote-debugging-port=0` = 端口随机，必须重新读 DevToolsActivePort
3. **端口过期**：环境重启后 DevToolsActivePort 重写，旧端口全废。每次脚本运行前**现读**端口文件，禁止硬编码

- **MCP 连接是独立会话**：`connect_browser_with_ws` 成功后操作走 MCP 工具；MCP 的 evaluate-script 必须 IIFE（见下表）。自写 websockets 脚本则另起连接，两者互不共享会话

## MCP (adspower-local-api) 使用要点

MCP 服务器 = `local-api-mcp-typescript`（node 直连 `build/index.js`），已接入 Hermes（47 工具，`mcp_adspower_local_api_*`）。

| 规则 | 说明 |
|------|------|
| **evaluate-script 必须 IIFE** | 裸箭头函数 `() => 'x'` 被当表达式求值返回空；必须 `(function(){...})()` 或 `(async function(){...})()` |
| **无 setInputFiles 工具** | 文件上传（如 Meta 视频）仍需 Playwright 直连补丁，MCP 覆盖不了 |
| **fill-input 安全** | 填 Meta 文案用 `fill-input`（Playwright fill 机制）；**禁用 execCommand insertText**（破坏 React 富文本编辑器 → 视频丢失/表单重置） |
| **click-element 会被覆盖层拦截** | AIX Downloader 全屏透明层导致 timeout → 改用 evaluate-script JS `b.click()` |
| **残留进程阻塞** | 脚本超时后 node MCP 服务器进程残留，占住 playwright 连接 → 查 `wmic process where "name='node.exe'" get ProcessId,CommandLine` 后 `taskkill /F /PID <pid>`；**禁止 `taskkill /IM node.exe`**（连 playwright driver 一起杀） |

## AIX Downloader 覆盖层（曾被误判为高频坑）

SunBrowser 环境装了 AIX Downloader 扩展，页面底部有 "Drag & drop here to download" 浮层。**实测（2026-08-01）它只是右下角 222×154 的小浮窗，不是全屏透明层，并不拦截点击**——之前把 "subtree intercepts pointer events" 归咎于它是误判。

**真正的拦截根因（已验证）：窗口最小化/被移到屏幕外时，Chromium 把视口压缩到 ~932×100（100px 高）**，Meta 页面布局完全错乱，「添加视频」等按钮被自身布局元素盖住 → 点击永远报 `subtree intercepts pointer events`。凌晨窗口正常时同一代码一次成功，窗口异常后同样的代码反复失败，差异就在视口。

**排查顺序（先视口后覆盖层）：**
1. **检查视口**：`pg.evaluate("() => JSON.stringify({w: innerWidth, h: innerHeight})")` — 若 `h` 只有 ~100，就是窗口/视口问题
2. **恢复窗口**（Win32 API 强制）：
   ```python
   import ctypes; from ctypes import wintypes
   user32 = ctypes.windll.user32
   hwnd = user32.FindWindowW("Chrome_WidgetWin_1", "<环境名> - SunBrowser")  # 或 EnumWindows 找标题含 SunBrowser
   user32.ShowWindow(hwnd, 9)   # SW_RESTORE
   user32.SetWindowPos(hwnd, 0, 100, 50, 1280, 1400, 0x0040)
   ```
   （`cua-driver bring_to_front` 能恢复可见性但**不保证恢复视口**；Win32 SetWindowPos 才可靠）
3. **刷新页面**让布局按新视口重排，再验证 `innerHeight > 500` 后才操作
4. 若确实遇到浮层挡点击（少见），再按 JS 点击/隐藏浮层绕过

## 上传成功验证（重要，曾导致误判中止）

Meta 上传区用 canvas/div 渲染预览，**`document.querySelector('video')` 可能始终为 null**——不要用 video 元素或 readyState 判断上传是否成功（曾因 readyState 一直 0 误判"上传失败"而中止流程，实际视频已 100% 传好）。

正确验证——页面文本包含**文件名**且出现 `100%` 或「删除」按钮：

```python
txt = pg.evaluate('() => document.body.innerText')
ok = 'pub_007.mp4' in txt and ('100%' in txt or '删除' in txt)
```

## 发布中途视口回缩（occlusion，2026-08-01 实测）

窗口即使已恢复可见，一旦被其他窗口盖住（如 Hermes 桌面全屏在前），Chromium 的 occlusion 会把视口压回 ~1px 并**暂停渲染**——发布流程**中途**也会发生（症状：视频上传后一直不处理、文案框点击报 `<html> intercepts pointer events`、body 文本骤减到几百字符）。

要点：
- **每次操作前** `pg.evaluate('() => innerHeight')` 复核，`< 500` 就先 Win32 恢复窗口再继续（SetForegroundWindow + SetWindowPos 1280×1400）
- ⚠️ **`Emulation.setDeviceMetricsOverride` 不可靠，勿作主路径**：能临时把视口拉到 1280×1400 但（a）连接断开即失效（每次新连接都要重设），（b）窗口被遮挡/目标异常时重设报 `Target does not support metrics override`。且 override 会随窗口状态回缩失效。正确顺序始终是：Win32 恢复窗口 → 刷新（仅上传前）→ 验证 innerHeight。
- **上传完成后不要 reload**——刷新会清空已上传状态；若视口在填文案阶段回缩，改用纯 JS 操作（evaluate 内 click / 填值），JS 不依赖视口命中测试，可绕过布局错乱
- 最稳模式：置前窗口 + **同一脚本连接内一口气完成** 上传→文案→下一页→分享，中途不切走窗口

## 窗口可见性

- SunBrowser 窗口可能被最小化/移到屏幕外（bounds 如 -31993,-32000），此时**视口被压缩到 ~100px 高 → 页面布局错乱 → 所有点击失败**（见上文根因）。这是"看不见窗口"和"点击失败"的同一根因。
- 修复：Win32 `ShowWindow(SW_RESTORE)` + `SetWindowPos(1280x1400)`（cua-driver bring_to_front 只恢复可见性，不保证恢复视口），然后刷新页面验证 `innerHeight`。
- **操作本身不需要窗口在前台**：CDP 驱动后台/任务栏中的窗口完全正常（用户明确认可"在任务栏中你也可以操作"）。只有用户想亲眼看到过程时才恢复窗口；不要为了"可见"而频繁 bring_to_front 打断用户。
- **用户说"没看到你在操作"时 = 窗口被最小化/移出屏幕（2026-08-20 实测）**：SunBrowser 窗口 minimized=true 且 bounds 在 -32000 时，用户完全看不到页面，会质问"你这是在哪里操作"。处理：`cua-driver.exe bring_to_front`（`echo '{\"pid\":<pid>}' | cua-driver.exe bring_to_front`）恢复可见 → `Target.activateTarget` 激活目标标签页（可能同时有 Meta/TikTok 多个标签，激活当前操作的 tab）。**启动长流程前先确认窗口可见**，避免用户全程看着空白
- **刷新仅限上传前**：恢复窗口后如需刷新页面验证布局，必须在上传视频**之前**做；一旦视频已上传，任何 `reload()` 都会清空上传状态（React 内存态）。
- **JS 填 contenteditable 的 React setter 不可靠**：`Object.getOwnPropertyDescriptor(HTMLDivElement.prototype, 'innerText').set` 在 Meta 页面可能为 undefined（TypeError），execCommand insertText 也会破坏编辑器——视口异常时优先恢复窗口后用 Playwright `.fill()`；JS 填值只作最后手段并先验证 setter 存在。
- **上传验证用页面文本不用 video 标签**：Meta 用 canvas 渲染预览，无 `<video>` 元素。轮询 `document.body.innerText` 看 `NN%` 进度，`'100%' in body and '删除' in body` 即上传完成。大文件（30MB+）上传慢，轮询间隔 5-9s、最长等 3-5 分钟（66MB 实测约 3 分钟）
- **Playwright set_files 有 50MB 传输上限**（CDP 远程连接 base64 传输）：报 `Cannot transfer files larger than 50Mb` 时**不要用 ffmpeg 压小**（会丢画质且用户明确要求发布用原视频），改用下面的 websocket 直连方案
- **>50MB 视频上传 = CDP websocket 直连（实测 66MB 成功，2026-08-19）**：
  1. 读 DevToolsActivePort 拿端口 + browser ws URL（环境重启后 ws ID 会变，必须现读 `cat DevToolsActivePort`）
  2. Python `websockets` 连 browser ws，`Target.getTargets` 找 `type=="page"` 且 url 含 business.facebook.com 的 target（**必须过滤 type=page**，否则 attach 到 iframe/worker 后 evaluate 报 `innerHeight is not defined`）
  3. `Target.attachToTarget({targetId, flatten:true})` 拿 sessionId → 启用 Page/Runtime/DOM 域 → `Page.setInterceptFileChooserDialog({enabled:true})`
  4. `Runtime.evaluate` 读「添加视频」按钮中心坐标，`Input.dispatchMouseEvent` 发 mouseMoved/mousePressed/mouseReleased 真实点击（React 才响应）
  5. 监听 `Page.fileChooserOpened` 拿 `backendNodeId`（**事件可能不带 sessionId，过滤条件不要卡 sessionId**；轮询等事件时用空命令 `Runtime.evaluate("1")` 消费消息队列，否则事件积压读不到）
  6. `DOM.setFileInputFiles({backendNodeId, files:[本地绝对路径]})` — 浏览器端直读磁盘，**无 50MB 限制**
  - 完整可运行脚本：`C:\Users\Administrator\test_ws_upload.py`；文件放规范路径 `Downloads/feishu_videos/<飞书表名>/<record_id>.mp4`（用户要求按表头建文件夹）
- **Playwright file_chooser 方案（Meta composer 无 input[type=file]，2026-08-20 实测）**：Meta composer 页面**没有** `input[type=file]`（DOM 直连 input 方案在这里失效），上传必须 `expect_file_chooser()` + 点击「添加视频」。⛔ **JS `dispatchEvent(MouseEvent)` 模拟点击不触发 Playwright 的 file chooser 拦截**（等 15s 超时）——必须 `meta_page.mouse.move(x,y)` + `mouse.down()` + `mouse.up()` 真实点击。Playwright CDP 直连（ws://）下 set_files 无 50MB 限制（本地直读）
- **分享按钮两步走**：第二步页面先 JS 点「立即分享」确保选中，再点**最后一个**（底部）「分享」按钮；顶部 tab 也有"分享"文字，必须取最后一个
- **⛔ 点击前先 scrollIntoView（2026-08-20 实测点错两次）**：底部按钮可能在视口外（`getBoundingClientRect().y > innerHeight`），直接取坐标点击会点空或点错位置。正确顺序：JS `el.scrollIntoView({block:'center', behavior:'instant'})` → sleep 1s → **重新** `getBoundingClientRect` 取坐标 → 真实点击 → 验证 `vis = r.y >= 0 && r.y < innerHeight`。Meta 分享按钮 (732,1518) 在 1271 视口外，必须滚动后取 (732,1171) 才点中；TikTok Post 按钮同理
- 用户会实时看着窗口，操作前先说明可行性/卡点，不要闷头反复试。

## 工作流纪律（用户明确纠正过，违反会被批评）

1. **先加载 skill + 本地仓库脚本再动手**：用户原话"一个这么简单的自动发布流程被你搞的这么复杂呢？你有好好看之前的一整个发布流程是怎么样的吗？"——发布前必须重读本 skill、`feishu-adspower-meta-publish`、以及本地仓库 `C:\Users\Administrator\.codex\Codex project\ADS指纹浏览器自动化\scripts\meta_publisher.py`，严格按已验证代码执行，**禁止临场发明新流程**
2. **动手前先说明可行性和卡点**：用户原话"你先告诉我可行性，卡在哪里来，别之后闷头干"——多步尝试前先一句话说清"卡在哪、为什么、打算怎么解决"
3. 逐步验证，不要连续 3+ 个未验证动作
4. 失败先诊断根因（截图/读 DOM/看进程/查视口），不要盲目重试同样命令
5. 简单流程心法（用户口述）：打开环境 → 查看有没有对应网页 → 有就点首页去发布 → 没有就输入网址打开 → 一步一步发布。不要绕远路
6. **连续失败立即止损并上报**：同一卡点失败 2-3 次后必须停止换方案，向用户/Codex 报告现状（卡在哪、已确认什么、下一步选项），等待指示。2026-08-01 教训：窗口遮挡导致视口 1px，我却连续 5+ 轮换着试 set_input_files / force click / JS click / override / Win32 恢复，用户在旁全程看不到进展，最终情绪爆发（"你就是sb，别搞了"）。**用户看不到后台操作时，反复闷头重试比失败本身更伤信任**——每次尝试前先说明"将做什么、预期看到什么"，失败后先解释再动手，绝不静默重试

## 🏆 大文件上传终极方案（>50MB 原视频，2026-08-19 实测成功）

**背景**：Playwright `set_files` 对 CDP 远程连接有 50MB 传输上限（`Cannot transfer files larger than 50Mb`）。66MB 原视频传不进去。

**解法：websocket 直连 CDP + `DOM.setFileInputFiles` 传本地路径**（浏览器端直读磁盘，无大小限制）：

1. 连浏览器级 ws：`ws://127.0.0.1:<port>/devtools/browser/<browser_id>`（DevToolsActivePort 第二行；环境重启后 browser_id 会变，必须重读）
2. `Target.getTargets` 找 `type=="page"` 且 url 含 business.facebook.com 的 target（**勿选 iframe/worker**！选错 evaluate 报 `innerHeight is not defined`）
3. `Target.attachToTarget flatten=True` 拿 sessionId
4. `Page.enable + Runtime.enable + DOM.enable + Page.setInterceptFileChooserDialog(enabled=True)`
5. `Runtime.evaluate` 拿「添加视频」按钮中心坐标 → `Input.dispatchMouseEvent` 真实点击（moved/pressed/released；JS `el.click()` 不触发 React）
6. 监听 `Page.fileChooserOpened` 拿 backendNodeId——**flatten 下事件不一定带 sessionId，匹配时不要要求该字段**；轮询等待时必须发空命令消费队列，否则事件躺在队列里不被处理
7. `DOM.setFileInputFiles {"backendNodeId": id, "files": [本地路径]}` ← 关键：无 50MB 限制
8. 轮询页面文本 `NN%` + 「删除」判断上传完成（66MB 约 3-4 分钟）

**配套要点**：
- 消息处理用**单一 reader 进 asyncio.Queue**，命令按 id 匹配，事件在循环中捕获（禁止两个协程同时 recv）
- **文案输入用 `Input.insertText`**（真实键盘事件，React 接收）：**⛔ 禁止 JS `box.focus()` 后直接 insertText（2026-08-20 Meta+TikTok 双平台实测会丢字）**——React 受控编辑器不认 JS focus，insertText 后 DOM 虽显示有字但 React 状态未接收，页面一切换文字就消失（表现为发布后无文案/下次进页面文字空）。正确顺序：`Runtime.evaluate` 拿输入框中心坐标 → `Input.dispatchMouseEvent`（mouseMoved/mousePressed/mouseReleased）**真实点击**聚焦 → 确认 `document.activeElement` 在框内 → insertText → **3 秒后复查 innerText 仍在**才算成功
- **分享两步**：先点「立即分享」radio，再点**最后一个**「分享」按钮（顶部 tab + 底部发布共 2 个）
- **Meta 定时发布（2026-08-19 实测）**：
  - 第二步点「发定时帖」radio → 展开日期+时间输入框（日期框 placeholder "年-月-日"，时间框 role=spinbutton aria-label=小时/分钟）
  - **双击时间框后直接输入数字**（如双击小时框输 "17"，双击分钟框输 "0"）——Input.insertText / char 按键均可；**spinbutton 的 value 属性不回显（永远空）但实际已生效**，不要用 value 验证，用截图或页面文本验证
  - 时间框下拉也会弹出推荐时间（05:00/11:30），直接选或手动输都行
  - **定时模式下底部提交按钮文字是「发定时帖」不是「分享」**！找 w>80 的按钮点最后一个
  - **预约成功标志**：页面出现「Reels 已预设发布时间」+ "预定在<日期>发布到 Facebook/Instagram"；不出现就还没提交
  - 日期/时区显示为浏览器环境时区（如 America/Los_Angeles），用户说"美国时间下午5点"= 页面本地 17:00 直接填
- **TikTok 发布（2026-08-19 实测跑通）**：
  - 页面：tiktok.com/tiktokstudio/upload（从 tiktok.com/upload 会自动跳转）；TikTok 已登录时显示上传界面
  - 首次/更新后打开有引导弹窗「Preview your video on your phone」+ 红色 Got it 按钮 → 必须先点击关闭（检测 `button` 文本 Got it / Skip / Next）
  - 上传入口：「Select video」按钮（点击触发 file chooser，和 Meta 同机制）；file input 隐藏时点按钮
  - **⛔ 弹窗处理（2026-08-20 实测）**：打开 upload 页若弹「A video you were editing wasn't saved. Continue editing?」= 上次未发布的草稿还在 → **点 Continue 继续编辑，禁止点 Discard**（Discard 会再弹确认框，循环弹窗卡死；草稿箱不用管，Continue 后直接进入已有视频的编辑页，跳过上传步骤）。引导弹窗（Not now / Got it）也要点掉
  - 上传后自动进入编辑页（有 Description 框、Post 按钮）
  - **Description 框会自动填入文件名**（如 recvsIyhOYiNaS）→ 必须先 JS 清空（`innerText=''` + dispatch input 事件）再填文案，否则文件名粘在文案末尾
  - **2026-08-20 用户新规：TikTok 只填「标题+标签」，不要正文**。Draft.js 光标坑：正文输入后光标不在末尾，后续标签会被插到正文中间 → 发布文案顺序错乱（实测标签出现在 "Comment your favorite below!" 后、正文后半段被挤到末尾）。只输标题+标签天然规避
  - **输入方式**：`Input.insertText` 对 TikTok Draft.js 无效（实测 LEN=0）→ **唯一正确方式 = 真实键盘 `Input.dispatchKeyEvent` 逐字符**（带 text/unmodifiedText 参数）
  - **标签必须逐个输入**：输 `#tag` → 等热度弹窗出现 → **再等 1.5 秒让标签完全渲染 → 按 Enter** → 下一个。⛔ 回车太快=标签不生效（被当换行，实测 links=0 全部没变蓝）；⛔ 标签前**不要输空格**（2026-08-20 用户两次纠正后定稿：先试 2s→太慢改 1.5s，空格去掉）。实现：0.5s 间隔快检 `[role=option]` 弹窗（最多 8s），弹窗 JSON 里出现 `tag_clean`（**裸字符串，不要用 json.dumps('#'+tag)——带引号永远匹配不上**）后 sleep 1.5s 再 Enter。禁止一次 insertText 全部标签（不触发热度弹窗、不生效）
  - **⛔ 上传 video 文件优先用 DOM 直连 input 而非 chooser 事件**：TikTok 页面有隐藏 `input[type=file]`，`Target.attachToTarget` 后 `DOM.getDocument`（**必须带 sessionId**，否则 KeyError: 'result'）→ `DOM.querySelector input[type=file]` → `DOM.setFileInputFiles({nodeId, files})` 直接完成，无需点击 Select video 也不用等 chooser 事件（chooser 捕获在 TikTok 上实测失败 2 次）。DOM.* 命令全都要传 sessionId
  - **⛔ 血泪教训（2026-08-20 复现 3 次，禁止重犯）**：
    1. **标签生效标准 = 变粗**（innerHTML 出现 `<strong>` 或 font-weight:bold），不是 innerText 有文字！execCommand 塞进去的文字不会变粗 = 没用上
    2. **`document.execCommand('delete')` 严禁使用**——会触发 Draft.js 内部状态错乱，导致已删除的旧文本重新渲染、两段内容叠加（实测 len 从 118 变 287）
    3. **清空后必须等 1 秒再输入，且慢速（60ms/字符）**——否则丢开头字符（实测 "Melt your day away" 丢了 "Melt y"）
    4. **弹窗检测匹配当前标签**：`'#tag名' in popup_json`，历史标签（`# softlife` 带空格）不算
    5. **犯错后不要修补**（补字符/删字符越修越乱）→ 直接 Ctrl+A 全选删除清空重来
    6. 能用真实键盘（dispatchKeyEvent）就别用 JS（focus/execCommand）——React/Draft.js 只认真实事件流
  - 验证：Post 后 URL 变为 tiktokstudio/upload/post/<id>，页面 Caption 区显示文案；**也可能是跳转到 tiktokstudio/content（2026-08-20 实测）**——content 页列表**顶部**出现刚发布的标题+标签（如 "00:39 Turn your volume all the way up 🎧✨#squishy..."）即发布成功，不要在 upload 页死等 post/ URL。发布确认后回写飞书（`fldcZoAlOt` = 已发布）
- 视频下载存 `Downloads/feishu_videos/<表名>/<record_id>.mp4`（用户指定：文件夹名与多维表格表头一致）

## 验证清单

- [ ] SunBrowser 运行中、视口正常（`pg.evaluate("innerHeight")` > 500；异常时跑 `scripts/restore_sunbrowser_window.py`）
- [ ] CDP 端口从 DevToolsActivePort 读取且 curl /json/version 通
- [ ] MCP/Playwright 无残留进程（wmic 查 node/python）
- [ ] playwright driver 正常（报 "Connection closed while reading from the driver" 时 `python -m playwright install chromium`）

## 进程识别陷阱

- `tasklist` 看到 **7+ 个 SunBrowser.exe 是正常的**——它们是同一个环境的子进程（渲染/GPU/网络），不是多个环境
- 判断是否多环境要看进程命令行里的 `user-data-dir`（`wmic process where "name='SunBrowser.exe'" get CommandLine | findstr user-data-dir`），只有 user-data-dir 不同才是不同环境
- `PYTHONPATH` 指向 Hermes venv 时，Python314 会加载 venv 的包导致二进制不兼容（pydantic_core 等）——用 `env -u PYTHONPATH` 或直接用 venv 的 python

## 参考资料

- `references/mcp-publish-flow.md` — 已验证成功的 Meta Reels 发布完整代码 + MCP 调用序列
- `references/tiktok-publish.md` — **TikTok 发布流程（2026-08-19 实测成功）**：tiktokstudio/upload 入口、引导弹窗(Got it)处理、Select video 上传、Description 默认文件名清空坑、Post 验证；与 Meta 双发顺序（2026-08-20 追加：填字验证误报、React 真实点击聚焦、多页面 attach、轮询输出控制、**草稿弹窗点 Continue 禁 Discard、DOM 直连 input 上传、标签弹窗立即回车、TikTok 只填标题+标签**）
- `references/lark-cli-reauth-flow.md` — lark-cli token 过期时的二维码重授权完整流程（后台登录→PNG 二维码→URL+MEDIA 展示→poll 确认）
- `references/vision-screenshot-analysis.md` — **发布验证截图怎么"看"**（2026-08-20）：ds-vision-skill（GLM 竞速池+comfly 兜底，DeepSeek 无原生视觉时的截图分析入口）；含降级链、配置坑（模型名硬编码两处、GLM_BASE_URL 手动设置、1305 过载是常态）
- `references/meta-official-api-research.md` — Meta Graph API 发布调研结论（为什么不用官方 API：多账号矩阵会击穿防关联；含端点/权限/门槛/GitHub 项目清单）
- `scripts/restore_sunbrowser_window.py` — 恢复被最小化/移出屏幕的 SunBrowser 窗口（修复视口 100px 导致的点击失败）

## Composer URL 陷阱（2026-08-20 实测）

- **Meta composer 链接参数会过期**：`asset_id=1289480590904839&business_id=1364096915701521` 曾报「链接可能已过期/仅指定用户可见」（页面标题退化为纯 "Facebook"，body 含「很抱歉，目前无法显示内容」）；用户提供新参数 `asset_id=890016627535163&business_id=3521484561351336` 才正常加载
- 发布前先打开 composer 验证页面（看是否出现「创建 Reels」「添加视频」），URL 失效就问用户要最新参数
- **多 business.facebook.com 页面**：浏览器可能同时有 content_calendar + reels_composer，`Target.getTargets` 取第一个匹配会 attach 到内容日历 → 找不到「添加视频」。必须优先匹配 url 含 `reels_composer` 的 target
- **大文件上传轮询输出撑爆**：66MB 级视频轮询时打印整个 `body.innerText` 会让终端日志截断、看起来像「卡住」。轮询只打百分比 `re.search(r"(\d+)%", t)`；页面已到分享设置页时写轻量脚本直接点「立即分享」+「分享」，不要重跑全流程（会重复上传）
