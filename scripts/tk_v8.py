"""TikTok 发布 v8：DOM.querySelector 直接找 input[type=file] -> setFileInputFiles（不依赖 chooser 事件）
流程：上传 -> 编辑页 -> 标题 -> 标签(逐个+回车) -> 验证 -> Post
"""
import json, time, asyncio, os, sys, base64

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
        state = {"mid": 0}
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

        # 1. 确认在 upload 页
        url = await ev("location.href") or ""
        if "upload" not in url:
            print("导航到 upload...")
            await send_cmd("Page.navigate", {"url": "https://www.tiktok.com/tiktokstudio/upload"}, sid)
            await asyncio.sleep(10)
        # 2. 处理引导（Got it / Not now，不碰 Discard）
        for attempt in range(5):
            r = await ev('''(() => {
                const btns = [...document.querySelectorAll('button')].filter(b => b.offsetWidth > 0);
                const txt = (b) => (b.innerText||'').trim();
                const n = btns.find(b => txt(b) === 'Not now');
                if (n) { n.click(); return 'NOT_NOW'; }
                const g = btns.find(b => txt(b) === 'Got it');
                if (g) { g.click(); return 'GOT_IT'; }
                return 'NONE';
            })()''')
            print(f"引导: {r}")
            if r == 'NONE': break
            await asyncio.sleep(2)
        # 3. 上传：DOM.querySelector 找 input[type=file] 直接 setFileInputFiles
        await asyncio.sleep(1)
        # 先检查是否有 input[type=file]
        has_input = await ev("!!document.querySelector('input[type=file]')")
        print(f"input[type=file] 存在: {has_input}")
        if has_input:
            doc = await send_cmd("DOM.getDocument", None, sid)
            root = doc["result"]["root"]["nodeId"]
            q = await send_cmd("DOM.querySelector", {"nodeId": root, "selector": "input[type=file]"}, sid)
            node_id = q["result"]["nodeId"]
            if node_id:
                r = await send_cmd("DOM.setFileInputFiles", {"nodeId": node_id, "files": [video]}, sid, timeout=60)
                if "error" in r:
                    print(f"❌ setFileInputFiles: {r['error']}"); return False
                print("✅ 文件已设置（input 直连）")
            else:
                print("❌ 找不到 input nodeId")
                # 兜底：点 Select video + chooser
                await send_cmd("Page.setInterceptFileChooserDialog", {"enabled": True}, sid)
                pos_s = await ev('''(() => {
                    const els = [...document.querySelectorAll('button,[role=button]')];
                    const b = els.find(el => (el.textContent||'').trim() === 'Select video' && el.getBoundingClientRect().width > 50);
                    if (b) { const r = b.getBoundingClientRect(); return JSON.stringify({x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2)}); }
                    return null;
                })()''')
                if not pos_s:
                    print("❌ 无 Select video"); return False
                pos = json.loads(pos_s)
                await real_click(pos["x"], pos["y"])
                for i in range(30):
                    if state["chooser"]: break
                    await send_cmd("Runtime.evaluate", {"expression": "1", "returnByValue": True}, sid, timeout=5)
                    await asyncio.sleep(0.3)
                if not state["chooser"]:
                    print("❌ 未捕获 chooser"); return False
                r = await send_cmd("DOM.setFileInputFiles", {"backendNodeId": state["chooser"], "files": [video]}, sid, timeout=60)
                print(f"✅ chooser 设置完成")
        else:
            print("⚠️ 无 input[type=file]，尝试 Select video 按钮")
            await send_cmd("Page.setInterceptFileChooserDialog", {"enabled": True}, sid)
            pos_s = await ev('''(() => {
                const els = [...document.querySelectorAll('button,[role=button]')];
                const b = els.find(el => (el.textContent||'').trim() === 'Select video' && el.getBoundingClientRect().width > 50);
                if (b) { const r = b.getBoundingClientRect(); return JSON.stringify({x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2)}); }
                return null;
            })()''')
            if pos_s:
                pos = json.loads(pos_s)
                await real_click(pos["x"], pos["y"])
                for i in range(30):
                    if state["chooser"]: break
                    await send_cmd("Runtime.evaluate", {"expression": "1", "returnByValue": True}, sid, timeout=5)
                    await asyncio.sleep(0.3)
                if not state["chooser"]:
                    print("❌ 未捕获 chooser"); return False
                r = await send_cmd("DOM.setFileInputFiles", {"backendNodeId": state["chooser"], "files": [video]}, sid, timeout=60)
                print("✅ chooser 设置完成")
            else:
                print("❌ 无上传入口"); return False
        # 4. 等编辑页（Post + Description）
        for i in range(40):
            await asyncio.sleep(5)
            t = await ev("document.body.innerText") or ""
            has_editor = await ev("!!document.querySelector('[contenteditable=\"true\"]')")
            if has_editor and "Post" in t:
                print(f"✅ 编辑页就绪 ({i*5}s)")
                break
            print(f"   等待 {i*5}s...")
        # 5. 清空 + 标题
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
        print(f"输入标题 ({len(title)} 字符)...")
        for ch in title:
            await type_char(ch, 0.06)
        await asyncio.sleep(1)
        r = await ev('''(() => { const box=document.querySelector('[contenteditable="true"]'); return 'TITLE LEN=' + box.innerText.length + ' HEAD=' + box.innerText.slice(0,25); })()''')
        print(f"标题后: {r}")
        # 6. 逐个标签
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
        # 7. 验证
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
        # 8. Post
        pos_s = await ev('''(() => {
            const b = [...document.querySelectorAll('button')].find(b => (b.innerText||'').trim() === 'Post' && b.offsetWidth > 0);
            if (!b) return null;
            const r = b.getBoundingClientRect();
            return JSON.stringify({x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2)});
        })()''')
        if not pos_s:
            print("❌ 无 Post 按钮"); return False
        pos = json.loads(pos_s)
        print(f"点击 Post ({pos['x']},{pos['y']})")
        await real_click(pos["x"], pos["y"])
        for i in range(12):
            await asyncio.sleep(4)
            t = await ev("document.body.innerText") or ""
            url = await ev("location.href") or ""
            if "post/" in url or "being" in t.lower() or "posted" in t.lower():
                print(f"✅ 发布触发! ({i*4}s) URL={url[:70]}")
                break
            print(f"   {i*4}s 等待...")
        return True

if __name__ == "__main__":
    port, ws_path = get_cdp_info()
    video = os.environ["TK_VIDEO"]
    title = os.environ["TK_TITLE"]
    tags = json.loads(os.environ["TK_TAGS"])
    ok = asyncio.run(main(f"ws://127.0.0.1:{port}{ws_path}", video, title, tags))
    sys.exit(0 if ok else 1)
