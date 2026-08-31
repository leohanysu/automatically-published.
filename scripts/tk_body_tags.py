"""TikTok 正文+标签：真实键盘逐字符输入正文 -> 逐个标签(输入+等弹窗+回车)"""
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

async def main(cdp_ws, body_text, tags):
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
            elif ch == "#":
                code = "Digit3"; key = "#"
            params_down = {"type": "keyDown", "key": key, "code": code or "", "text": ch, "unmodifiedText": ch, "windowsVirtualKeyCode": vk or 0, "nativeVirtualKeyCode": vk or 0}
            params_up = {"type": "keyUp", "key": key, "code": code or "", "windowsVirtualKeyCode": vk or 0, "nativeVirtualKeyCode": vk or 0}
            if ch == "\n":
                params_down.pop("text"); params_down.pop("unmodifiedText")
            await send_cmd("Input.dispatchKeyEvent", params_down, sid)
            await asyncio.sleep(0.015)
            await send_cmd("Input.dispatchKeyEvent", params_up, sid)
            await asyncio.sleep(0.015)
        async def key(k, code, modifiers=0, vk=0):
            await send_cmd("Input.dispatchKeyEvent", {"type": "keyDown", "key": k, "code": code, "modifiers": modifiers, "windowsVirtualKeyCode": vk}, sid)
            await send_cmd("Input.dispatchKeyEvent", {"type": "keyUp", "key": k, "code": code, "modifiers": modifiers, "windowsVirtualKeyCode": vk}, sid)

        # 1. 聚焦编辑器（光标应在末尾，标题已输入）
        pos_s = await ev('''(() => {
            const box = document.querySelector('[contenteditable="true"]');
            if (!box) return null;
            const r = box.getBoundingClientRect();
            return JSON.stringify({x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2)});
        })()''')
        if not pos_s:
            print("❌ 找不到编辑器"); return False
        pos = json.loads(pos_s)
        await real_click(pos["x"], pos["y"])
        await asyncio.sleep(0.8)
        # Ctrl+End 到末尾
        await key("End", "End", 2, 35)
        await asyncio.sleep(0.3)

        # 2. 输入正文（前面加两个换行分隔）
        sep = "\n\n"
        for ch in sep:
            await type_char(ch)
        total = len(body_text)
        print(f"输入正文 {total} 字符...")
        for i, ch in enumerate(body_text):
            await type_char(ch)
            if i % 100 == 0:
                print(f"   {i}/{total}...")
        await asyncio.sleep(0.8)
        cur = await ev('''(() => { const box=document.querySelector('[contenteditable="true"]'); return box ? box.innerText.length : -1; })()''')
        print(f"正文后长度: {cur}")

        # 3. 逐个标签
        for i, tag in enumerate(tags):
            tag_clean = tag.lstrip('#').strip()
            print(f"[{i+1}/{len(tags)}] #{tag_clean}")
            await type_char(" ")  # 空格分隔
            await asyncio.sleep(0.3)
            for ch in "#" + tag_clean:
                await type_char(ch)
                await asyncio.sleep(0.05)
            await asyncio.sleep(2.5)  # 等热度弹窗
            # 检查弹窗
            suggest = await ev('''(() => {
                const els = [...document.querySelectorAll('[role="option"], [class*="suggest"]')].filter(e => e.offsetWidth > 0);
                return JSON.stringify(els.map(e => (e.innerText||'').replace(/\\n/g,'|').slice(0,50)).slice(0,3));
            })()''')
            print(f"   弹窗: {suggest}")
            await key("Enter", "Enter", 0, 13)
            await asyncio.sleep(1.2)
            tail = await ev('''(() => { const box=document.querySelector('[contenteditable="true"]'); return box ? box.innerText.slice(-30) : 'NO'; })()''')
            print(f"   末尾: {repr(tail)}")
        return True

if __name__ == "__main__":
    port, ws_path = get_cdp_info()
    body_text = os.environ["TK_BODY"]
    tags = json.loads(os.environ["TK_TAGS"])
    ok = asyncio.run(main(f"ws://127.0.0.1:{port}{ws_path}", body_text, tags))
    sys.exit(0 if ok else 1)
