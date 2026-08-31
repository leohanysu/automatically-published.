# Meta Reels 发布 — 已验证成功代码（2026-08-01）

来源：会话 `20260724_052936_87900e`（recvqYltag0bqS 实测发布成功，FB+IG 双端）。

## 完整成功代码（Playwright CDP 直连）

```python
import time
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:57974"          # 从 DevToolsActivePort 读取
VIDEO = r"C:\Users\Administrator\Downloads\feishu_videos\xxx.mp4"
URL = "https://business.facebook.com/latest/reels_composer/?asset_id=890016627535163&business_id=3521484561351336"

FULL = f"{TITLE}\n\n{BODY}\n\n#Squishy #FidgetToys #StressRelief #DeskAccessories #DIY"

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP)
    pg = [x for x in b.contexts[0].pages if 'business.facebook.com' in x.url][0]

    # 1/4 导航（必须 domcontentloaded + sleep 4）
    pg.goto(URL, wait_until='domcontentloaded', timeout=30000)
    time.sleep(4)

    # 2/4 上传：expect_file_chooser（普通 set_input_files 不触发上传！）
    with pg.expect_file_chooser(timeout=15000) as fc:
        pg.locator('text="添加视频"').first.click(timeout=10000)
    fc.value.set_files(VIDEO)
    time.sleep(5)
    # ⚠️ 上传成功验证：不要用 querySelector('video')（Meta 用 canvas 预览，video 可能始终为 null）！
    #    正确：页面文本含文件名 + '100%'/'删除'：
    #    txt = pg.evaluate('() => document.body.innerText')
    #    ok = 'xxx.mp4' in txt and ('100%' in txt or '删除' in txt)

    # 3/4 文案：contenteditable div（比 aria-label 稳定，不同环境 label 不同）
    pg.locator('div[contenteditable="true"]').first.click(timeout=10000)
    pg.locator('div[contenteditable="true"]').first.fill(FULL)
    time.sleep(1)

    # 4/4 点「下一页」循环直到「分享」出现 → 点最后一个分享 → 验证「正在处理」
    for step in range(5):
        pg.evaluate('()=>{let a=[...document.querySelectorAll("button,[role=button]")].filter(b=>(b.textContent||"").includes("下一页"));if(a.length)a[a.length-1].click()}')
        time.sleep(3)
        has_share = pg.evaluate('()=>[...document.querySelectorAll("button,[role=button]")].some(b=>(b.textContent||"").trim()==="分享")')
        if '正在处理' in pg.evaluate('()=>document.body.innerText'):
            break
        if has_share:
            pg.evaluate('()=>{let s=[...document.querySelectorAll("button,[role=button]")].filter(b=>(b.textContent||"").trim()==="分享");s[s.length-1].click()}')
            time.sleep(5)
            ok = '正在处理' in pg.evaluate('()=>document.body.innerText')
            break
    b.close()
```

## 关键点（成功 vs 失败的差异）

| 环节 | ✅ 成功做法 | ❌ 失败做法 |
|------|------------|-----------|
| 上传 | `expect_file_chooser` + 点击「添加视频」+ `set_files` | 裸 `set_input_files`（不触发上传）|
| 上传验证 | 页面文本含**文件名** + `100%`/`删除` | `querySelector('video')` readyState（Meta 用 canvas 预览，video 可能始终为 null → 误判上传失败中止）|
| 文案 | `div[contenteditable="true"]` + `.fill()` | aria-label 选择器（label 因环境而异）；execCommand insertText（破坏编辑器）|
| 下一页 | JS 点**最后一个**「下一页」按钮，循环至多 5 次 | 点第一个/用 MCP click-element（被覆盖层拦）|
| 分享 | JS 点**最后一个**「分享」按钮 | `locator('text=分享').click()`（被覆盖层拦）|
| 验证 | `'正在处理' in body` | 看「编辑」按钮（顶部 tab 误报）|

⚠️ **上传后不要 reload**（清空已上传状态）；发布全程保持窗口可见（被遮挡 → occlusion → 视口 1px → 渲染冻结，详见 SKILL.md「发布中途视口回缩」）。

## 飞书回写（发布确认后）

```bash
lark-cli base +record-batch-update --base-token ${FEISHU_BASE_TOKEN} \
  --table-id tblDI9jnIMqCP59S \
  --json '{"record_id_list":["<record_id>"],"patch":{"任务状态":"已发布"}}'
```

## MCP 替代方案（当 MCP 工具可用时）

1. `connect-browser-with-ws`（wsUrl 从 open-browser 或 DevToolsActivePort 拿）
2. `navigate` 到 composer
3. **上传仍需 Playwright 直连补丁**（MCP 无 setInputFiles）
4. `fill-input`（selector=`[aria-label="在对话框中输入内容，即可为帖子添加文字。"]`）— 已验证成功
5. 点下一页/分享：`evaluate-script` + IIFE JS click（MCP click-element 会被 AIX 覆盖层拦）
6. `get-page-visible-text` / `screenshot` 验证

## 环境指纹

- 捏捏乐环境：k1dqriqs，CDP 常见端口 57974，asset_id=890016627535163，business_id=3521484561351336
- 压缩沙发环境：k1egodto，asset_id=1289480590904839，business_id=1364096915701521
