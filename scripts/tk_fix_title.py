"""修复 TikTok Description：开头补 'Melt y' + 删末尾多余 'y'（真实键盘）"""
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

async def main(cdp_ws):
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
        async def type_char(ch):
            vk = char_to_vk(ch)
            key = ch.lower() if ch.isalpha() else ch
            code = None
            if ch.isalpha():
                code = "Key" + ch.upper()
            elif ch == " ":
                code = "Space"; key = " "
            params_down = {"type": "keyDown", "key": key, "code": code or "", "text": ch, "unmodifiedText": ch, "windowsVirtualKeyCode": vk or 0, "nativeVirtualKeyCode": vk or 0}
            params_up = {"type": "keyUp", "key": key, "code": code or "", "windowsVirtualKeyCode": vk or 0, "nativeVirtualKeyCode": vk or 0}
            await send_cmd("Input.dispatchKeyEvent", params_down, sid)
            await asyncio.sleep(0.04)
            await send_cmd("Input.dispatchKeyEvent", params_up, sid)
            await asyncio.sleep(0.04)

        # 1. 点击编辑器聚焦
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
        # 2. 光标移到开头（Ctrl+Home）
        await key("Home", "Home", 2, 36)
        await asyncio.sleep(0.5)
        # 3. 输入 "Melt y"（补齐标题开头）
        print("补标题开头 'Melt y'...")
        for ch in "Melt y":
            await type_char(ch)
        await asyncio.sleep(0.8)
        # 4. 光标移到末尾（Ctrl+End）
        await key("End", "End", 2, 35)
        await asyncio.sleep(0.5)
        # 5. 删末尾多余的 'y'（#cozyvibesy -> #cozyvibes）
        print("删末尾多余 'y'...")
        await key("Backspace", "Backspace", 0, 8)
        await asyncio.sleep(0.8)
        # 6. 验证
        ver = await ev('''(() => {
            const box = document.querySelector('[contenteditable="true"]');
            const t = box ? box.innerText : '';
            return JSON.stringify({
                len: t.length,
                first40: t.slice(0, 40),
                last100: t.slice(-100)
            });
        })()''')
        v = json.loads(ver)
        print(f"长度: {v['len']}")
        print(f"开头: {v['first40']}")
        print(f"末尾: {v['last100']}")
        return True

if __name__ == "__main__":
    port, ws_path = get_cdp_info()
    ok = asyncio.run(main(f"ws://127.0.0.1:{port}{ws_path}"))
    sys.exit(0 if ok else 1)
