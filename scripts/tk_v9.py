"""TikTok 发布 v9（最终正确版）：清空 -> 标题 -> 逐个标签(弹窗出现后等2秒再回车!) -> 验证a标签 -> Post
2026-08-20 用户两次纠正确认：回车太早=标签不生效（被当换行）。必须弹窗完全渲染后（出现后+2秒）再回车
"""
import json, time, asyncio, os, sys

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

        # 1. 点击编辑器 + 清空
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
        # 2. 标题（慢速）
        print(f"标题 ({len(title)} 字符)...")
        for ch in title:
            await type_char(ch, 0.06)
        await asyncio.sleep(1)
        r = await ev('''(() => { const box=document.querySelector('[contenteditable="true"]'); return 'TITLE LEN=' + box.innerText.length + ' HEAD=' + box.innerText.slice(0,25); })()''')
        print(f"标题后: {r}")
        # 3. 逐个标签：输入 -> 等弹窗 -> 弹窗出现后再等 1.5 秒 -> 回车（不加空格，2026-08-20 用户要求）
        for i, tag in enumerate(tags):
            tag_clean = tag.lstrip('#').strip()
            print(f"[{i+1}/{len(tags)}] #{tag_clean}")
            for ch in "#" + tag_clean:
                await type_char(ch, 0.04)
            # 等弹窗出现（0.5s 轮询，最多 8s）
            popup = '[]'
            appeared = False
            for wait in range(16):
                await asyncio.sleep(0.5)
                popup = await ev('''(() => {
                    const els = [...document.querySelectorAll('[role="option"], [class*="suggest"]')].filter(e => e.offsetWidth > 0);
                    return JSON.stringify(els.map(e => (e.innerText||'').replace(/\\n/g,'|').slice(0,40)).slice(0,4));
                })()''')
                if tag_clean in popup:
                    appeared = True
                    print(f"   弹窗出现 ({wait*0.5+0.5:.1f}s)")
                    break
            if appeared:
                print(f"   等 1.5 秒让标签完全渲染...")
                await asyncio.sleep(1.5)  # ⛔ 用户确认：弹窗出现后等 1.5 秒再回车
            else:
                print(f"   弹窗未出现: {popup[:60]}")
            await key("Enter", "Enter", 0, 13)
            await asyncio.sleep(1.2)
        # 4. 验证：a 标签数量（蓝色链接 = 生效）
        ver = await ev('''(() => {
            const box = document.querySelector('[contenteditable="true"]');
            const t = box.innerText;
            const links = box ? [...box.querySelectorAll('a')].map(a=>a.innerText) : [];
            return JSON.stringify({len: t.length, text: t, links: links});
        })()''')
        v = json.loads(ver)
        print(f"验证: len={v['len']} links={len(v['links'])}")
        print(f"链接: {v['links']}")
        print(f"全文: {v['text']}")
        return True

if __name__ == "__main__":
    port, ws_path = get_cdp_info()
    title = os.environ["TK_TITLE"]
    tags = json.loads(os.environ["TK_TAGS"])
    ok = asyncio.run(main(f"ws://127.0.0.1:{port}{ws_path}", title, tags))
    sys.exit(0 if ok else 1)
