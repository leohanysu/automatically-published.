---
name: squishy-factory-copy
description: 捏捏乐工厂社媒视频全自动：飞书视频→Gemini文案→TTS配音→HyperFrames渲染→飞书回写。
version: 2.0.0
---

# 捏捏乐工厂社媒视频全自动生成

全链路：飞书视频 → 压缩 → comfly Gemini 文案 → Edge TTS 配音 → HyperFrames 渲染 → 飞书回写。

## 飞书配置

| 项 | 值 |
|----|-----|
| **base-token** | `${FEISHU_BASE_TOKEN}` |
| **table-id** | `tblDI9jnIMqCP59S`（捏捏乐社媒） |

### 字段映射

| 飞书字段 | field ID | 类型 | 用途 |
|---------|----------|------|------|
| 视频 | `fldaZm0opu` | attachment | **输入**：源视频 |
| 视频标题 | `fldbknGQ6e` | text | **输出**：最佳标题 |
| 发布正文 | `fld8QH5cfN` | text | **输出**：最佳正文 |
| 发布标题参考 | `fldr5zdALy` | text | **输出**：Gemini 完整回复 |
| 配音剪辑视频 | `fldOPdvuT4` | attachment | **输出**：带配音字幕的成品 MP4 |

## 操作流程

### Step 1: 读取飞书记录

```bash
lark-cli base +record-list --base-token ${FEISHU_BASE_TOKEN} --table-id tblDI9jnIMqCP59S --limit 50 --format json
```

筛选：fldaZm0opu（视频）非空 且 fldbknGQ6e（视频标题）为空 → 待处理。

### Step 2: 下载视频 + 格式转换（非压缩）

```bash
mkdir -p "$HOME/Downloads/feishu_videos"
cd "$HOME/Downloads/feishu_videos"
lark-cli base +record-download-attachment \
  --base-token ${FEISHU_BASE_TOKEN} \
  --table-id tblDI9jnIMqCP59S \
  --record-id <record_id> \
  --file-token <file_token> \
  --output ./video_source.mp4
```

⚠️ `--output` 必须是相对路径，先 cd。
⚠️ 文件名含特殊字符时用 `--output ./video_source.mp4` 覆盖。

**格式转换（根据用途分开处理）：**

```bash
SIZE=$(stat -c%s video_source.mp4)
SIZE_MB=$((SIZE / 1048576))

# A. 给 Gemini 分析用的视频（comfly 上传，限制 ~20MB）
if [ $SIZE_MB -le 19 ]; then
  cp video_source.mp4 video_for_gemini.mp4   # 直接用
else
  ffmpeg -y -i video_source.mp4 -c:v libx264 -crf 22 -preset fast -an video_for_gemini.mp4  # 压缩到20MB内
fi

# B. 给 HyperFrames 渲染用的视频（本地渲染，无大小限制）
ffmpeg -y -i video_source.mp4 -c:v libx264 -crf 1 -preset fast -an -r 30 -g 30 -keyint_min 30 -movflags +faststart video_prepped.mp4
```

- **Gemini 用**：只在 >20MB 时压缩（crf 22），正常大小直接用原视频
- **HyperFrames 用**：始终 crf 1（视觉无损），只需去原声 + 修 keyframe
- `-an` = 去掉原声，配音用 TTS 替换

### Step 3: 上传 comfly → Gemini 生成文案

上传视频：
```bash
curl -s --max-time 60 --noproxy "*" \
  "https://ai.comfly.org/v1/files" \
  -H "Authorization: Bearer ${COMFLY_API_KEY}" \
  -F "purpose=vision" \
  -F "file=@C:/Users/Administrator/Downloads/feishu_videos/video_for_gemini.mp4"
```

⚠️ 用 Windows 风格路径 `C:/...`。

调用 Gemini（3 级降级）：
1. `gemini-3.1-pro-preview`（优先）→ 429重试1次 → 降级
2. `gemini-3-flash-preview`（备选）
3. Chrome 浏览器 → `gemini.google.com`（兜底，无法传视频）

### Step 4: Gemini 提示词

```
你是中国硅胶捏捏乐源头工厂（China Silicone Squishy Factory — Direct Source）的海外社媒文案专家。

根据视频素材生成面向美国批发商（B2B）的高转化英文帖文，输出【必须是可直接发布的成品】。

工厂优势：
- 食品级硅胶 + 无毒检测认证（Food-grade silicone, lab-tested non-toxic）
- 每月 10+ 新款（10+ new styles every month）
- 源头工厂价格，无中间商（Factory-direct pricing, no middleman markup）

标题：从以下7种风格随机选1种，纯英文，30-80字符，1-2个emoji
1.身份直给 2.痛点共鸣 3.新品展示 4.质量打底 5.B端术语 6.社交证明 7.反转

正文骨架（150-250词，纯英文，5层结构）：
1.我是谁（1-2句亮明源头工厂）
2.我能解决什么（针对批发商痛点）
3.为什么选我（食品级硅胶+无毒检测 / 每月10+新款 / 源头价格）
4.结合素材（提及视频中的产品款式）
5.行动号召（DM us for wholesale catalog and factory pricing）

输出格式：标题 + 正文 + 标签（5-10个#标签）

【硬性禁止（违者重写）】：
- 禁止输出任何骨架标注词：[Who we are]、[Problem we solve]、[Why choose us]、[Video Context]、[Call to Action]、[标题]、[正文] 等一律不得出现在输出中
- 禁止中英双语对照，只输出英文
- 禁止解释性文字、专家建议、制作说明、开场白（如"好的！"、"以下是为您…"）
- 禁止用【】包裹段落，正文直接是连贯的英文段落
- 标题、正文、标签之间用空行分隔，不要任何多余标记
- 输出内容从标题开始，到最后一个标签结束，前后不得有任何多余文字
```

⚠️ 提示词硬编码在 skill 中，不从飞书读取文案提示词字段（省 token）。

### Step 5: 文案时长适配 + TTS 配音

**时长适配规则：**
- 用 `ffprobe` 获取视频时长
- 文案精简到约 25 词以内（英文语速 ~170wpm）
- 配音必须 ≤ 视频时长

**测试配音时长：**
```bash
edge-tts --voice en-US-AriaNeural --text "文案内容" --write-media "test.mp3"
ffprobe -v quiet -show_entries format=duration -of csv=p=0 test.mp3
```

**语速调整：** 如果超时，用 `--rate "+12%"` 加速；如果太短，用 `-5%` 减速。

**生成最终配音：**
```bash
edge-tts --voice en-US-AriaNeural --rate "+12%" \
  --text "精简后的文案" \
  --write-media "C:/Users/Administrator/Downloads/feishu_videos/voiceover.mp3"
```

Edge TTS 免费，`en-US-AriaNeural` 女声自然。`--rate` 范围 -50% 到 +100%。

### Step 6: HyperFrames 渲染

参考模板：`C:\Users\Administrator\Downloads\feishu_videos\squishy-overlay\index.html`

复制视频和配音到 `assets/`：
```bash
cp video_compressed.mp4 squishy-overlay/assets/source.mp4
cp voiceover.mp3 squishy-overlay/assets/voiceover.mp3
```

渲染：
```bash
cd squishy-overlay && npm run check && npm run render
```

渲染时视频已 `muted`，只有 TTS 配音输出。

### Step 7: 上传成品视频到飞书 + 回写文案

```bash
# 上传成品视频到"配音剪辑视频"字段
lark-cli base +record-upload-attachment \
  --base-token ${FEISHU_BASE_TOKEN} \
  --table-id tblDI9jnIMqCP59S \
  --record-id <record_id> \
  --field-id fldOPdvuT4 \
  --file "C:/Users/Administrator/Downloads/feishu_videos/squishy-overlay/renders/squishy-overlay_*.mp4"

# 回写文案字段
lark-cli base +record-upsert \
  --base-token ${FEISHU_BASE_TOKEN} \
  --table-id tblDI9jnIMqCP59S \
  --record-id <record_id> \
  --json '{"fldr5zdALy":"完整回复","fldbknGQ6e":"最佳标题","fld8QH5cfN":"最佳正文"}'
```

## 文案多样性策略

每天发多条视频，不重复使用固定话术。AI 需根据视频风格自动匹配不同的钩子和节奏。

### 钩子类型（前 3 秒）

| 类型 | 示例 | 适用场景 |
|------|------|---------|
| 痛点反问 | "Still getting last season's squishies?" | 唤醒批发商的选款焦虑 |
| 好奇心引发 | "What if your next shipment looked nothing like the last?" | 展示差异化 |
| 现状挑战 | "You're buying squishies. But are you getting factory-direct?" | 直接挑战中间商 |
| 社交证明 | "The squishies taking over US shelves start right here." | 建立信任 |
| 趋势赶超 | "This is what's trending next month. Are you in?" | 新品发布 |

每次生成时从钩子池中随机选择，不重复上个视频用过的类型。

### 语速策略

- 默认 `en-US-AriaNeural` `+45%`（约 3.2wps，快节奏带货风格）
- 视频时长 <10s → `+50%`
- 视频时长 >20s → `+30%`（留呼吸空间）
- 备选：`en-US-JennyNeural`（自然语速更快，`+25%`约等于 Aria `+45%`）
- 文案目标：12-13s 视频塞 35-40 词，内容丰富有画面感

### 分镜原则

- 配音 11-12 秒用 4 段分镜（钩子→解法→品质→CTA）
- 配音 >15 秒可扩展到 5-6 段
- 字幕和配音同时出现，不提前不滞后
- 每段字幕 1-2 行，不超过屏幕上文字太多

作为资深视频剪辑师，HyperFrames 字幕模板遵循：

1. **白色字体统一**：所有文字用 `#FFFFFF`，半透明黑底 `rgba(0,0,0,0.65)` 保证对比度
2. **三段式分镜**：标题卡→卖点三连击→CTA，每段无缝衔接
3. **GSAP 动画**：标题淡入、卖点逐个弹出、CTA 缩放，节奏自然
4. **配音优先**：视频用 `muted` + 单独 `<audio>` 轨道，确保只有 TTS 输出
5. **安全边距**：左右 30px，底部 140-200px，避免平台裁剪

## 常见陷阱

1. **文件名特殊字符**：下载时用 `--output ./video_source.mp4` 覆盖
2. **comfly 路径**：上传用 Windows 风格 `C:/...`，MSYS 路径会失败
3. **Gemini 模型**：先试 `gemini-3.1-pro-preview`，429 则降级 `gemini-3-flash-preview`
4. **视频用 `image_url` 引用**：comfly Gemini 不支持 `video_url`
5. **`--noproxy "*"`**：comfly 必须直连，不走代理
6. **lark-cli `--json`**：upsert 用 `--json`，不是 `--data`
7. **视频原声**：格式转换时加 `-an`，HyperFrames 用 `muted`。不要压缩画质（crf 1，视觉无损）。
8. **配音时长**：先测再调 `--rate`，确保 ≤ 视频时长
9. **edge-tts 路径**：用 Windows 风格 `C:/.../output.mp3`
10. **HyperFrames check**：渲染前必须 `npm run check` 通过

## 批量处理（一键脚本）

`scripts/batch_process.py` 封装完整流程，一次处理多条：

```bash
python ~/AppData/Local/hermes/skills/media/squishy-factory-copy/scripts/batch_process.py recvqXXXX recvqYYYY ...
```

脚本自动处理：读取→下载→上传→Gemini(3级降级)→解析→回写→TTS+Whisper对齐→HyperFrames→上传成品（覆盖式）。

### 剪映式字幕对齐

`scripts/tts_align.py`：Edge TTS 生成配音 → faster-whisper 识别逐句/逐词时间戳 → `alignment.json`。字幕出现时间和配音逐句精确同步（不是按比例均分）。

### 覆盖式上传

重新生成视频时，上传到「配音剪辑视频」字段前先移除旧附件再上传新视频（`+record-remove-attachment --yes` → `+record-upload-attachment`），不追加不堆积。

## 常见陷阱

0. **⛔ 血泪教训（2026-08-19 实测，禁止重犯）**：
   1. 压缩禁止 `-an`（去音频）——ASMR 声音是灵魂，必须 `-c:a aac -b:a 96k` 保留。**此条同时修正下方第 7 条旧规则**（旧规则说加 `-an` 是错的）
   2. 发布必须用原视频（飞书「视频」字段原文件），>50MB 走 websocket CDP 方案（见 adspower-cdp-automation skill），禁止降级压缩
   3. 填文案禁止裸 `div[contenteditable=true]`——Meta 有多个 contenteditable 会填错框，发布后显示"这条内容没有文字"。必须 `[aria-label*="在对话框中输入"]` + Input.insertText，发布前在预览区验证
   3.5. **⛔ JS `.focus()` 填文案必丢（2026-08-20 实测）**：Meta Reels composer 是 React 受控编辑器，JS `el.focus(); el.click()` 后 insertText 虽然 DOM 显示有字（innerText.length>0），但 React 状态未接收，页面一切换文字就消失。正确：用 CDP `Input.dispatchMouseEvent`（mouseMoved→mousePressed→mouseReleased）**真实点击**输入框坐标（`getBoundingClientRect` 中心），确认 `document.activeElement` 在框内，再 `Input.insertText`，3 秒后复查 innerText 仍在才算成功
   4. 上传进度看页面文本（NN% + 「删除」按钮），不是 video readyState（Meta 用 canvas 渲染无 video 元素）
   5. 大文件上传耐心等：66MB 需 3-4 分钟，5-6s 轮询最长 5 分钟，别在 48% 误判失败
   6. 杀 python 前先 wmic 查命令行：`hermes_cli.main serve` 是 Hermes 本体绝不能杀
   7. 动手前先重读 skill + 仓库脚本（meta_publisher.py / publish_ws.py），禁止临场发明流程
   8. 卡住先大白话告诉用户（在干嘛/为什么/卡在哪），2-3 次失败必须停下换方案或上报
   9. 中文路径用正斜杠 + 先 cd 再相对路径（bash 引号会炸）
   10. lark-cli 下载 `--output` 必须是相对路径
   11. **TikTok 填文案前必须彻底清空 Description**：TikTok 上传后会自动填入文件名作为默认标题（如 `recvsIyhOYiNaS`），Ctrl+A 全选删除不可靠（contenteditable 编辑器可能残留）——必须用 JS 直接清空（`box.innerText=''` + 触发 input 事件）再 insertText，否则文件名会粘在文案末尾（2026-08-19 实测翻车，用户手动删除）
   12. **TikTok 首次/更新后打开上传页会有引导弹窗**（"Preview your video on your phone" + Got it 按钮），必须先检测并点击 Got it / Skip 关闭，否则遮挡页面无法操作（2026-08-19 用户指出）

1. **文件名特殊字符**：下载时用 `--output ./video_source.mp4` 覆盖
2. **comfly 路径**：上传用 Windows 风格 `C:/...`，MSYS 路径会失败
3. **Gemini 模型**：先试 `gemini-3.1-pro-preview`，429 则降级 `gemini-3-flash-preview`
4. **视频用 `image_url` 引用**：comfly Gemini 不支持 `video_url`
5. **`--noproxy "*"`**：comfly 必须直连，不走代理
6. **lark-cli `--json`**：upsert 用 `--json`，不是 `--data`
7. **视频原声**：**保留音频**（`-c:a aac -b:a 96k`），禁止 `-an`。Gemini 分析压缩也保留音频。不要压缩画质（crf 1，视觉无损）
8. **配音时长**：先测再调 `--rate`，确保 ≤ 视频时长
9. **edge-tts 路径**：用 Windows 风格 `C:/.../output.mp3`
10. **HyperFrames check**：渲染前必须 `npm run check` 通过
11. **execute_code sandbox 无 lark-cli**：npm 全局目录不在 sandbox PATH。必须显式加 `NPM_BIN = ~/AppData/Roaming/npm` 到 PATH，或直接用 terminal 跑
12. **HyperFrames 时间轴**：分镜 (start, end) 必须无缝衔接，`duration = end - start`，不能重叠
13. **edge-tts 偶发失败**：生成后检查文件大小（>50KB），异常自动重试
14. **lark-cli 输出前缀**：输出可能带 "Uploading..." 前缀，解析 JSON 前先找到第一个 `{`
