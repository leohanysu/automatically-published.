"""TikTok 彻底重填 v4（纯真实键盘）：全选删除 -> 慢速标题 -> 逐个标签(等弹窗+回车) -> 验证变粗
修复：不用 execCommand（会搞乱 Draft.js 内部状态），全程 Input.dispatchKeyEvent
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

async def main(cdp_ws, title, tags):
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

        # 1. 点击编辑器
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
        # 2. 全选删除（Ctrl+A + Backspace x2 确保干净）
        await key("a", "KeyA", 2, 65)
        await asyncio.sleep(0.3)
        await key("Backspace", "Backspace", 0, 8)
        await asyncio.sleep(0.5)
        await key("a", "KeyA", 2, 65)
        await asyncio.sleep(0.3)
        await key("Backspace", "Backspace", 0, 8)
        await asyncio.sleep(0.5)
        r = await ev('''(() => { const box=document.querySelector('[contenteditable="true"]'); return 'CLEARED LEN=' + box.innerText.length; })()''')
        print(f"清空: {r}")
        # 3. 慢速输入标题（每字符 60ms，确保不丢字）
        print(f"输入标题 ({len(title)} 字符)...")
        for ch in title:
            await type_char(ch, 0.06)
        await asyncio.sleep(1)
        r = await ev('''(() => { const box=document.querySelector('[contenteditable="true"]'); return 'TITLE LEN=' + box.innerText.length + ' HEAD=' + box.innerText.slice(0,25); })()''')
        print(f"标题后: {r}")
        # 4. 逐个标签（真实键盘 + 等当前标签弹窗 + 回车）
        for i, tag in enumerate(tags):
            tag_clean = tag.lstrip('#').strip()
            print(f"[{i+1}/{len(tags)}] #{tag_clean}")
            await type_char(" ", 0.04)
            await asyncio.sleep(0.3)
            for ch in "#" + tag_clean:
                await type_char(ch, 0.04)
                await asyncio.sleep(0.02)
            # 等当前标签的热度弹窗（最多 12 秒）
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
        # 5. 验证
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
        # 6. 截图
        r = await send_cmd("Page.captureScreenshot", {"format": "png"}, sid)
        b64 = r.get("result", {}).get("data", "")
        open(r"C:\Users\Administrator\Downloads\feishu_videos\tiktok_refill4.png", "wb").write(base64.b64decode(b64))
        print("截图 tiktok_refill4.png")
        return True

if __name__ == "__main__":
    port, ws_path = get_cdp_info()
    title = os.environ["TK_TITLE"]
    tags = json.loads(os.environ["TK_TAGS"])
    ok = asyncio.run(main(f"ws://127.0.0.1:{port}{ws_path}", title, tags))
    sys.exit(0 if ok else 1)
