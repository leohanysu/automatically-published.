"""TikTok Description 填文案（真实点击 Draft.js 编辑器 + insertText + 严格验证）"""
import json, time, asyncio, os, sys, base64

def get_cdp_info(profile_id="k1dqriqs", suffix="h1msnw4"):
    port_file = rf"D:\.ADSPOWER_GLOBAL\cache\{profile_id}_{suffix}\DevToolsActivePort"
    with open(port_file) as f:
        port = f.readline().strip()
        ws_path = f.readline().strip()
    return port, ws_path

async def main(cdp_ws, full_text):
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

        # 1. 找 Description 编辑框（DraftEditor-content）
        pos_s = await ev('''(() => {
            const box = document.querySelector('[contenteditable="true"], [contenteditable]');
            if (!box) return null;
            box.scrollIntoView({block:'center'});
            const r = box.getBoundingClientRect();
            return JSON.stringify({x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2), w: r.width, h: r.height});
        })()''')
        if not pos_s:
            print("❌ 找不到编辑框"); return False
        pos = json.loads(pos_s)
        print(f"编辑框: {pos}")
        # 2. 真实点击
        await real_click(pos["x"], pos["y"])
        await asyncio.sleep(1.5)
        # 3. 确认焦点
        focused = await ev('''(() => { const box=document.querySelector('[contenteditable="true"]'); return document.activeElement === box || box.contains(document.activeElement); })()''')
        print(f"焦点: {focused}")
        # 4. Ctrl+A 清空（如果之前有内容）
        await send_cmd("Input.dispatchKeyEvent", {"type": "keyDown", "key": "a", "code": "KeyA", "modifiers": 2}, sid)
        await send_cmd("Input.dispatchKeyEvent", {"type": "keyUp", "key": "a", "code": "KeyA", "modifiers": 2}, sid)
        await send_cmd("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Backspace", "code": "Backspace"}, sid)
        await send_cmd("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Backspace", "code": "Backspace"}, sid)
        await asyncio.sleep(0.5)
        # 5. insertText
        await send_cmd("Input.insertText", {"text": full_text}, sid)
        await asyncio.sleep(2)
        # 6. 严格验证
        ver = await ev('''(() => { const box=document.querySelector('[contenteditable="true"]'); return box ? JSON.stringify({len: box.innerText.length, head: box.innerText.slice(0,50), tail: box.innerText.slice(-40)}) : 'NO_BOX'; })()''')
        print(f"验证: {ver}")
        v = json.loads(ver)
        await asyncio.sleep(3)
        ver2 = await ev('''(() => { const box=document.querySelector('[contenteditable="true"]'); return box ? box.innerText.length : -1; })()''')
        print(f"3秒后复查: {ver2}")
        # 7. 截图
        r = await send_cmd("Page.captureScreenshot", {"format": "png"}, sid)
        b64 = r.get("result", {}).get("data", "")
        open(r"C:\Users\Administrator\Downloads\feishu_videos\tiktok_caption.png", "wb").write(base64.b64decode(b64))
        print("截图 tiktok_caption.png")
        return v.get("len", 0) >= 100 and ver2 >= 100

if __name__ == "__main__":
    port, ws_path = get_cdp_info()
    full = os.environ["TK_FULL"]
    ok = asyncio.run(main(f"ws://127.0.0.1:{port}{ws_path}", full))
    sys.exit(0 if ok else 1)
