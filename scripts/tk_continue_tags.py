"""TikTok 继续输入剩余标签：光标到末尾 -> 逐个标签(弹窗一出现立即回车, 0.5s快检)"""
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

async def main(cdp_ws, tags):
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
        async def type_char(ch, delay=0.04):
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

        # 1. 点击编辑器 + Ctrl+End 到末尾
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
        await asyncio.sleep(0.8)
        await key("End", "End", 2, 35)
        await asyncio.sleep(0.3)
        cur = await ev('''(() => { const box=document.querySelector('[contenteditable="true"]'); return box ? box.innerText.slice(-40) : 'NO'; })()''')
        print(f"当前末尾: {repr(cur)}")
        # 2. 逐个标签（弹窗出现立即回车）
        for i, tag in enumerate(tags):
            tag_clean = tag.lstrip('#').strip()
            print(f"[{i+1}/{len(tags)}] #{tag_clean}")
            await type_char(" ", 0.04)
            await asyncio.sleep(0.2)
            for ch in "#" + tag_clean:
                await type_char(ch, 0.04)
            # 快检弹窗：0.5s 间隔，最多 10 次（5 秒），出现立即回车
            entered = False
            for wait in range(10):
                await asyncio.sleep(0.5)
                popup = await ev('''(() => {
                    const els = [...document.querySelectorAll('[role="option"], [class*="suggest"]')].filter(e => e.offsetWidth > 0);
                    return JSON.stringify(els.map(e => (e.innerText||'').replace(/\\n/g,'|').slice(0,40)).slice(0,4));
                })()''')
                if tag_clean in popup:
                    print(f"   弹窗出现 ({wait*0.5+0.5:.1f}s): {popup[:80]} → 回车")
                    await key("Enter", "Enter", 0, 13)
                    entered = True
                    break
            if not entered:
                print("   弹窗未出现，直接回车")
                await key("Enter", "Enter", 0, 13)
            await asyncio.sleep(1.0)
        # 3. 验证
        ver = await ev('''(() => {
            const box = document.querySelector('[contenteditable="true"]');
            const t = box.innerText;
            const html = box.innerHTML;
            return JSON.stringify({
                len: t.length, tail: t.slice(-120),
                strong: (html.match(/<strong>/g)||[]).length,
                a: (html.match(/<a[^>]*>/g)||[]).length
            });
        })()''')
        v = json.loads(ver)
        print(f"验证: len={v['len']}")
        print(f"末尾: {v['tail']}")
        print(f"strong={v['strong']} a-tags={v['a']}")
        return True

if __name__ == "__main__":
    port, ws_path = get_cdp_info()
    tags = json.loads(os.environ["TK_TAGS_REMAIN"])
    ok = asyncio.run(main(f"ws://127.0.0.1:{port}{ws_path}", tags))
    sys.exit(0 if ok else 1)
