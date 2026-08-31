"""TikTok 全流程 v5（纯真实键盘）：Discard旧草稿 -> Select video上传 -> 关引导 -> 慢速标题 -> 逐个标签(等弹窗+回车) -> 验证变粗"""
import json, time, asyncio, os, sys, base64, re

def get_cdp_info(profile_id="k1dqriqs", suffix="h1msnw4"):
    port_file = rf"D:\.ADSPOWER_GLOBAL\cache\{profile_id}_{suffix}\DevToolsActivePort"
    with open(port_file) as f:
        port = f.readline().strip()
        ws_path = f.readline().strip()
    return port, ws_path

def char_to_vk(c):
    o = ord(c)
    if 48 <= o <= 57: return o
    if 65 <= o <= 90: return o
    if 97 <= o <= 122: return o - 32
    return 0

async def main(cdp_ws, video, title, tags):
    import websockets
    async with websockets.connect(cdp_ws, max_size=2**30, open_timeout=15) as ws:
        msg_q = asyncio.Queue()
        async def reader():
            try:
                while True:
                    raw = await ws.recv()
                    await msg_q.put(json.loads(raw))
            except Exception:
                pass
        asyncio.create_task(reader())
        state = {"mid": 0, "chooser": None}
        async def send_cmd(method, params=None, sid=None, timeout=30):
            state["mid"] += 1
            mid = state["mid"]
            msg = {"id": mid, "method": method, "params": params or {}}
            if sid: msg["sessionId"] = sid
            await ws.send(json.dumps(msg))
            while True:
                data = await asyncio.wait_for(msg_q.get(), timeout=timeout)
                if data.get("id") == mid:
                    return data
                if data.get("method") == "Page.fileChooserOpened":
                    state["chooser"] = data["params"].get("backendNodeId")
        targets = await send_cmd("Target.getTargets")
        pts = [t for t in targets["result"]["targetInfos"] if t.get("type") == "page" and "tiktok.com" in t.get("url", "")]
        pt = None
        for t in pts:
            if "upload" in t.get("url", ""):
                pt = t["targetId"]; break
        if not pt and pts:
            pt = pts[-1]["targetId"]
        if not pt:
            print("❌ 无 TikTok 页面"); return False
        att = await send_cmd("Target.attachToTarget", {"targetId": pt, "flatten": True})
        sid = att["result"]["sessionId"]
        for m in ["Page.enable", "Runtime.enable", "DOM.enable"]:
            await send_cmd(m, None, sid)
        async def ev(expr):
            r = await send_cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True}, sid)
            return r.get("result", {}).get("result", {}).get("value")
        async def real_click(x, y):
            for e in ["mouseMoved", "mousePressed", "mouseReleased"]:
                p = {"type": e, "x": x, "y": y}
                if e != "mouseMoved":
                    p["button"] = "left"; p["clickCount"] = 1
                await send_cmd("Input.dispatchMouseEvent", p, sid)
                await asyncio.sleep(0.15)
        async def key(k, code, modifiers=0, vk=0):
            await send_cmd("Input.dispatchKeyEvent", {"type": "keyDown", "key": k, "code": code, "modifiers": modifiers, "windowsVirtualKeyCode": vk}, sid)
            await send_cmd("Input.dispatchKeyEvent", {"type": "keyUp", "key": k, "code": code, "modifiers": modifiers, "windowsVirtualKeyCode": vk}, sid)
        async def type_char(ch, delay=0.06):
            vk = char_to_vk(ch)
            key = ch.lower() if ch.isalpha() else ch
            code = None
            if ch.isalpha():
                code = "Key" + ch.upper()
            elif ch.isdigit():
                code = "Digit" + ch
            elif ch == " ":
                code = "Space"; key = " "
            elif ch == "#":
                code = "Digit3"; key = "#"
            params_down = {"type": "keyDown", "key": key, "code": code or "", "text": ch, "unmodifiedText": ch, "windowsVirtualKeyCode": vk or 0, "nativeVirtualKeyCode": vk or 0}
            params_up = {"type": "keyUp", "key": key, "code": code or "", "windowsVirtualKeyCode": vk or 0, "nativeVirtualKeyCode": vk or 0}
            await send_cmd("Input.dispatchKeyEvent", params_down, sid)
            await asyncio.sleep(delay)
            await send_cmd("Input.dispatchKeyEvent", params_up, sid)
            await asyncio.sleep(delay)

        # 1. 关引导弹窗 + Discard 未保存草稿
        for attempt in range(5):
            r = await ev('''(() => {
                // Discard 未保存视频
                const discard = [...document.querySelectorAll('button')].find(b => (b.innerText||'').trim() === 'Discard' && b.offsetWidth > 0);
                if (discard) { discard.click(); return 'DISCARD'; }
                // Got it 引导
                const gotIt = [...document.querySelectorAll('button')].find(b => (b.innerText||'').trim() === 'Got it' && b.offsetWidth > 0);
                if (gotIt) { gotIt.click(); return 'GOT_IT'; }
                return 'NONE';
            })()''')
            print(f"弹窗处理: {r}")
            if r == 'NONE':
                break
            await asyncio.sleep(2)
        # 2. 上传视频（真实点击 Select video + chooser）
        await send_cmd("Page.setInterceptFileChooserDialog", {"enabled": True}, sid)
        await asyncio.sleep(0.5)
        pos_s = await ev('''(() => {
            const els = [...document.querySelectorAll('button,[role=button]')];
            const b = els.find(el => (el.textContent||'').trim() === 'Select video' && el.getBoundingClientRect().width > 50);
            if (b) { const r = b.getBoundingClientRect(); return JSON.stringify({x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2)}); }
            return null;
        })()''')
        if not pos_s:
            print("❌ 无 Select video 按钮"); return False
        pos = json.loads(pos_s)
        print(f"点击 Select video ({pos['x']},{pos['y']})")
        await real_click(pos["x"], pos["y"])
        for i in range(30):
            if state["chooser"]: break
            await send_cmd("Runtime.evaluate", {"expression": "1", "returnByValue": True}, sid, timeout=5)
            await asyncio.sleep(0.3)
        if not state["chooser"]:
            print("❌ 未捕获 chooser"); return False
        r = await send_cmd("DOM.setFileInputFiles", {"backendNodeId": state["chooser"], "files": [video]}, sid, timeout=60)
        if "error" in r:
            print(f"❌ set: {r['error']}"); return False
        print("✅ 视频已设置，等待上传处理...")
        # 3. 等上传完成（进入编辑页：有 Post 按钮）
        for i in range(40):
            await asyncio.sleep(5)
            t = await ev("document.body.innerText") or ""
            if "Post" in t and ("Description" in t or "Details" in t):
                print(f"✅ 进入编辑页 ({i*5}s)")
                break
            print(f"   等待上传 {i*5}s...")
        # 4. 等编辑器可用
        for i in range(10):
            await asyncio.sleep(2)
            has_editor = await ev("!!document.querySelector('[contenteditable=\"true\"]')")
            if has_editor:
                print("✅ 编辑器就绪")
                break
        # 5. 点击编辑器 + 清空（Ctrl+A + Backspace x2）
        pos_s = await ev('''(() => {
            const box = document.querySelector('[contenteditable="true"]');
            if (!box) return null;
            box.scrollIntoView({block:'center', behavior:'instant'});
            const r = box.getBoundingClientRect();
            return JSON.stringify({x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2)});
        })()''')
        if not pos_s:
            print("❌ 找不到编辑器"); return False
        pos = json.loads(pos_s)
        await real_click(pos["x"], pos["y"])
        await asyncio.sleep(1)
        await key("a", "KeyA", 2, 65)
        await asyncio.sleep(0.3)
        await key("Backspace", "Backspace", 0, 8)
        await asyncio.sleep(0.5)
        await key("a", "KeyA", 2, 65)
        await asyncio.sleep(0.3)
        await key("Backspace", "Backspace", 0, 8)
        await asyncio.sleep(0.8)
        r = await ev('''(() => { const box=document.querySelector('[contenteditable="true"]'); return 'CLEARED LEN=' + box.innerText.length; })()''')
        print(f"清空: {r}")
        # 6. 慢速输入标题
        print(f"输入标题 ({len(title)} 字符)...")
        for ch in title:
            await type_char(ch, 0.06)
        await asyncio.sleep(1)
        r = await ev('''(() => { const box=document.querySelector('[contenteditable="true"]'); return 'TITLE LEN=' + box.innerText.length + ' HEAD=' + box.innerText.slice(0,25); })()''')
        print(f"标题后: {r}")
        # 7. 逐个标签（等当前标签弹窗 + 回车）
        for i, tag in enumerate(tags):
            tag_clean = tag.lstrip('#').strip()
            print(f"[{i+1}/{len(tags)}] #{tag_clean}")
            await type_char(" ", 0.04)
            await asyncio.sleep(0.3)
            for ch in "#" + tag_clean:
                await type_char(ch, 0.04)
                await asyncio.sleep(0.02)
            popup = '[]'
            got_popup = False
            for wait in range(12):
                await asyncio.sleep(1)
                popup = await ev('''(() => {
                    const els = [...document.querySelectorAll('[role="option"], [class*="suggest"]')].filter(e => e.offsetWidth > 0);
                    return JSON.stringify(els.map(e => (e.innerText||'').replace(/\\n/g,'|').slice(0,40)).slice(0,4));
                })()''')
                if json.dumps('#' + tag_clean) in popup:
                    got_popup = True
                    break
            print(f"   弹窗: {popup} (got={got_popup})")
            await key("Enter", "Enter", 0, 13)
            await asyncio.sleep(1.5)
        # 8. 验证（变粗 = 标签生效）
        ver = await ev('''(() => {
            const box = document.querySelector('[contenteditable="true"]');
            const t = box.innerText;
            const html = box.innerHTML;
            return JSON.stringify({
                len: t.length, head: t.slice(0,30), tail: t.slice(-90),
                strong: (html.match(/<strong>/g)||[]).length,
                bold: (html.match(/font-weight:\\s*bold|font-weight:\\s*700/gi)||[]).length
            });
        })()''')
        v = json.loads(ver)
        print(f"验证: len={v['len']} head={v['head']}")
        print(f"末尾: {v['tail']}")
        print(f"粗体: strong={v['strong']} bold-style={v['bold']}")
        r = await send_cmd("Page.captureScreenshot", {"format": "png"}, sid)
        b64 = r.get("result", {}).get("data", "")
        open(r"C:\Users\Administrator\Downloads\feishu_videos\tiktok_v5.png", "wb").write(base64.b64decode(b64))
        print("截图 tiktok_v5.png")
        return True

if __name__ == "__main__":
    port, ws_path = get_cdp_info()
    video = os.environ["TK_VIDEO"]
    title = os.environ["TK_TITLE"]
    tags = json.loads(os.environ["TK_TAGS"])
    ok = asyncio.run(main(f"ws://127.0.0.1:{port}{ws_path}", video, title, tags))
    sys.exit(0 if ok else 1)
