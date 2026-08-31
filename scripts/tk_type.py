"""TikTok 真实键盘输入：Input.dispatchKeyEvent 逐字符模拟真人打字"""
import json, time, asyncio, os, sys

def get_cdp_info(profile_id="k1dqriqs", suffix="h1msnw4"):
    port_file = rf"D:\.ADSPOWER_GLOBAL\cache\{profile_id}_{suffix}\DevToolsActivePort"
    with open(port_file) as f:
        port = f.readline().strip()
        ws_path = f.readline().strip()
    return port, ws_path

# 字符 -> 虚拟键码映射（常用 ASCII）
def char_to_vk(c):
    o = ord(c)
    if 48 <= o <= 57:   # 0-9
        return o
    if 65 <= o <= 90:   # A-Z
        return o
    if 97 <= o <= 122:  # a-z
        return o - 32
    return 0

async def main(cdp_ws, text):
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
        async def type_char(ch):
            """真实键盘事件：keyDown(text) + keyUp，模拟真人按键"""
            vk = char_to_vk(ch)
            key = ch.lower() if ch.isalpha() else ch
            code = None
            if ch.isalpha():
                code = "Key" + ch.upper()
            elif ch.isdigit():
                code = "Digit" + ch
            elif ch == " ":
                code = "Space"; key = " "
            elif ch == "\n":
                code = "Enter"; key = "Enter"
            params_down = {"type": "keyDown", "key": key, "code": code or "", "text": ch, "unmodifiedText": ch, "windowsVirtualKeyCode": vk or 0, "nativeVirtualKeyCode": vk or 0}
            params_up = {"type": "keyUp", "key": key, "code": code or "", "windowsVirtualKeyCode": vk or 0, "nativeVirtualKeyCode": vk or 0}
            if ch == "\n":
                # Enter 键：不传 text
                params_down.pop("text"); params_down.pop("unmodifiedText")
            await send_cmd("Input.dispatchKeyEvent", params_down, sid)
            await asyncio.sleep(0.02)
            await send_cmd("Input.dispatchKeyEvent", params_up, sid)
            await asyncio.sleep(0.02)

        # 1. 点击编辑器展开
        pos_s = await ev('''(() => {
            const box = document.querySelector('.public-DraftEditor-content, [contenteditable="true"]');
            if (!box) return null;
            box.scrollIntoView({block:'center', behavior:'instant'});
            const r = box.getBoundingClientRect();
            return JSON.stringify({x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2)});
        })()''')
        if not pos_s:
            print("❌ 找不到编辑器"); return False
        pos = json.loads(pos_s)
        await real_click(pos["x"], pos["y"])
        await asyncio.sleep(1.2)
        # 2. 清空现有内容（Ctrl+A + Backspace）
        await send_cmd("Input.dispatchKeyEvent", {"type": "keyDown", "key": "a", "code": "KeyA", "modifiers": 2, "windowsVirtualKeyCode": 65}, sid)
        await send_cmd("Input.dispatchKeyEvent", {"type": "keyUp", "key": "a", "code": "KeyA", "modifiers": 2, "windowsVirtualKeyCode": 65}, sid)
        await send_cmd("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8}, sid)
        await send_cmd("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8}, sid)
        await asyncio.sleep(0.5)
        # 3. 逐字符真实输入（打字速度 ~30ms/字符）
        total = len(text)
        for i, ch in enumerate(text):
            await type_char(ch)
            if i % 50 == 0:
                print(f"   已输入 {i}/{total} 字符...")
        await asyncio.sleep(1)
        # 4. 验证
        ver = await ev('''(() => { const box=document.querySelector('[contenteditable="true"]'); return box ? box.innerText.length : -1; })()''')
        head = await ev('''(() => { const box=document.querySelector('[contenteditable="true"]'); return box ? box.innerText.slice(0,60) : 'NO'; })()''')
        print(f"验证: {ver} 字符")
        print(f"开头: {repr(head)}")
        return ver and ver >= 100

if __name__ == "__main__":
    port, ws_path = get_cdp_info()
    text = os.environ["TK_TEXT"]
    ok = asyncio.run(main(f"ws://127.0.0.1:{port}{ws_path}", text))
    sys.exit(0 if ok else 1)
