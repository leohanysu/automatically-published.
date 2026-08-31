# TikTok 发布流程（websocket CDP，2026-08-19 实测成功）

## 入口
- 上传页：`https://www.tiktok.com/tiktokstudio/upload`（创作者中心，会自动从 tiktok.com/upload 跳转）
- 登录态：环境 k1dqriqs 已登录 @marshkiky（cookie 正常，无需重复登录）
- 若页面显示官网引导页（About/Newsroom...），是加载中间态或未登录——等 3-5 秒或检查 cookie

## 关键步骤（与 Meta 同机制，复用 websocket CDP 方案）

1. **关引导弹窗（首次/更新后必现，否则挡住后续操作）**
   - 弹窗特征："Preview your video on your phone" + 红色 **"Got it"** 按钮
   - 处理：循环找 `button` 文本 == "Got it"（或 /skip|next|got it|知道了|下一步/i）点击，最多 3 次直到 NONE
   - 用户原话："很久没有发布视频，或第一次打开上传页面，以及后续有更新的话都会出现这种引导，需要先点击掉"

2. **上传视频**
   - 页面有 `input[type=file]`（accept=video/*）但**是隐藏的**（rect 0,0）——不能点它
   - 要点可见的 **"Select video"** 按钮（`button` 文本精确匹配 + offsetWidth > 0）
   - 复用 Meta 的完整链路：`Page.setInterceptFileChooserDialog(enabled=True)` → `Input.dispatchMouseEvent` 真实点击 → 监听 `Page.fileChooserOpened` 拿 backendNodeId → `DOM.setFileInputFiles` 本地路径直传（无 50MB 限制，原视频直传）
   - 等 chooser 事件时必须发空命令消费队列（`Runtime.evaluate "1"`）
   - **⛔ 更稳方案（2026-08-20 实测，chooser 事件在 TikTok 上捕获失败 2 次）**：直接用 DOM 定位隐藏 input 直连上传——`DOM.getDocument`（**必须传 sessionId**，否则 `KeyError: 'result'`）→ `DOM.querySelector input[type=file]` → `DOM.setFileInputFiles({nodeId, files})`，**跳过点击按钮和 chooser 事件**。所有 `DOM.*` 命令都要带 sessionId
   - **草稿弹窗（2026-08-20）**：打开 upload 页弹「A video you were editing wasn't saved. Continue editing?」= 上次未发布草稿还在 → **点 Continue 继续编辑，禁止点 Discard**（Discard 弹确认框循环卡死）；Continue 后直接进编辑页跳过上传。引导弹窗（Not now / Got it）同样要点掉

3. **等待上传完成**
   - 页面文本出现 "Uploaded（xxMB）" + 编辑表单（Details/Description/Post 按钮）= 上传完成
   - 48MB 约 1 分钟内；大文件同样 5-6s 轮询

4. **填 Description（坑！）**
   - 输入框：`[contenteditable=true]` 且 offsetWidth > 0（TikTok 只有一个可见的）
   - **默认内容 = 文件名**（如 `recvsIyhOYiNaS`，14 字符）——必须先清空！
   - 清空方法：Ctrl+A（`Input.dispatchKeyEvent` key="a" modifiers=2）+ Backspace，然后 `Input.insertText`
   - ⚠️ **实测坑**：Ctrl+A+Backspace 可能没清干净，文件名残留在文案末尾！修复：清空后**验证 innerText 为空**再 insertText；若残留，改用 evaluate 直接 `box.innerText = ''` + 触发 input 事件（contenteditable 可用 innerText 赋值清空）
   - 发布前验证：`box.innerText.length` + 开头/末尾文本，确保无文件名残留

5. **发布**
   - 点 **"Post"** 按钮（`button` 文本精确匹配 + offsetWidth > 0）
   - 验证：URL 跳到 `/tiktokstudio/upload/post/<id>` 即发布成功；页面出现 Caption 内容

## 发布内容规则
- 文案 = 视频标题 + 发布正文 + **tiktok标签**（飞书 `tiktok标签` 字段 fld0Qx2af5；有值用值，空用默认，不生成不覆盖）
- 与 Meta 的 IG/FB标签 分开：Meta 用 IG/FB标签，TikTok 用 tiktok标签

## 双发流程（Meta + TikTok）
```
发 Meta（现有流程）成功 → 同视频发 TikTok（本流程）→ 双端成功 → 回写飞书"已发布"
```
- 注意：TikTok 上传页会记住上次状态，重新打开时可能直接是编辑页（视频已传）——脚本要兼容"已有视频在页"的情况（跳过上传，直接填文案+Post）
- 当前问题（待解决）：TikTok 网页版详情页无编辑 caption 入口，文案错误只能删除重发

## 环境
- CDP 端口/ws 从 `D:\.ADSPOWER_GLOBAL\cache\k1dqriqs_h1msnw4\DevToolsActivePort` 读取（重启会变）
- attach 时选 `type=="page"` 且 url 含 tiktok.com 的 target

## 2026-08-20 实测补充（防重犯）

### 填字验证会误报（重要！）
- 脚本验证 `[contenteditable=true]` 的 innerText 时**可能匹配到隐藏的标签输入框** → 报 `LEN=0`「文案填充失败」，但实际文案已填入（页面字符计数如 `2260/4000` 可见）
- 正确验证：`document.body.innerText` 是否包含标题关键词（如 `Melt your day`），不要只看 contenteditable 的 innerText

### Description 与 Meta 一样是 React 受控组件
- JS `box.focus()` 后 `Input.insertText` **会丢字**（Meta 2026-08-19/20 双平台实测）。必须先 `Input.dispatchMouseEvent` 真实点击输入框坐标（`scrollIntoView` + `getBoundingClientRect` 中心），确认 `document.activeElement` 在框内，再 insertText，3 秒后复查仍在才算成功（publish_dual.py 已按此修复）

### ⛔ TikTok Description 是 Draft.js，insertText 彻底无效（2026-08-20 实测）
- **CDP `Input.insertText` 对 Draft.js 免疫**：即使真实点击聚焦（activeElement 确认在框内）、Ctrl+A 清空都做了，insertText 后 `box.innerText.length` 仍为 0 —— 与 Meta 不同，Meta 是真实点击+insertText 就能成，TikTok 不行
- **唯一可靠输入方式 = 真实键盘逐字符** `Input.dispatchKeyEvent`（type=keyDown 带 text/unmodifiedText + keyUp）：模拟真人打字，TikTok 完整接收
- ⚠️ **`document.execCommand('insertText')` 能塞文字但标签不变粗 = 没用上**（用户 2026-08-20 明确：标签要变粗才是正确用到）。execCommand 不触发 TikTok 标签检测/热度弹窗，只作普通文本插入，**不要用作标签输入**
- ⚠️ **`document.execCommand('delete')` 严禁使用**：会触发 Draft.js 内部状态错乱，已删除的旧文本重新渲染、两段内容叠加（实测 len 118→287）
- 清空：Ctrl+A（真实键盘）+ Backspace ×2，然后**等 1 秒再慢速输入（60ms/字符）**，否则丢开头字符（实测标题丢 "Melt y"）

### 标签必须逐个输入 + 热度弹窗回车（用户亲授，2026-08-20）
- **TikTok 标签不能一次性 insertText 全部**：Draft.js 不接收，且不触发标签检测
- 正确流程（用户原话：「标签需要手动一个一个逐字输入，输入完一个后过一会会有对应的标签热度弹窗，这时候你按一下回车就把标签用上了」）：
  1. 光标置末尾（真实点击 + Ctrl+End）
  2. 真实键盘输入空格 + `#tag`（逐字符 dispatchKeyEvent，**必须真实键盘**——execCommand 只塞文字不变粗）
  3. **弹窗一出现立即回车**（用户 2026-08-20 纠正："有弹窗出来就能回车了都"，不要傻等 2-3s）。实现：0.5s 间隔快检 `[role=option]`（最多 5s），弹窗 JSON 出现 `tag_clean` 即 Enter——**用裸字符串匹配，不要 json.dumps('#'+tag)（带引号永远匹配不上）**；历史标签（`# softlife` 带空格）不算当前标签弹窗
  4. 按 **Enter** 确认 → 标签才真正"用上"（变粗/变蓝 chip）
  5. 下一个标签：重复 2-4
- 验证：标签生效 = **变粗**（用户标准），不是 innerText 有字；`#tag` 在 innerText 中 + 弹窗出现过
- **2026-08-20 用户新规：TikTok 只填「标题+标签」，不要正文**——正文输入后光标不在末尾，后续标签会被插到正文中间（Draft.js 光标坑），只输标题+标签天然规避

### 多页面 attach 陷阱
- 浏览器可能同时开多个业务页面（如 business.facebook.com 的 content_calendar + reels_composer），`Target.getTargets` 取第一个匹配可能 attach 到错误页面 → 找不到上传按钮
- 修复：优先匹配 URL 含具体页面特征（如 `reels_composer`）的 target，否则取最后一个匹配

### 大文件上传轮询输出撑爆
- 66MB 级视频上传轮询时若打印整个 `body.innerText`，日志会被截断，看起来像「卡住」
- 轮询只打百分比：`re.search(r"(\d+)%", t)`；怀疑卡住先查进程/日志文件大小再判断，页面已到分享设置页时直接写轻量脚本点「立即分享」+「分享」，不要重跑全流程（会重复上传）
