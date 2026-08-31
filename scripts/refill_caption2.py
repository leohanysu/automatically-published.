"""真鼠标点击输入框 + insertText + 验证（修复 React 不认 JS focus 的问题）"""
import json, time, asyncio, os, base64, sys

def get_cdp_info(profile_id="k1dqriqs", suffix="h1msnw4"):
    port_file = rf"D:\.ADSPOWER_GLOBAL\cache\{profile_id}_{suffix}\DevToolsActivePort"
    with open(port_file) as f:
        port = f.readline().strip()
        ws_path = f.readline().strip()
    return port, ws_path

async def main(cdp_ws):
    import websockets
    async with websockets.connect(cdp_ws, max_size=2**30) as ws:
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
        pt = None
        for t in targets["result"]["targetInfos"]:
            if t.get("type") == "page" and "business.facebook.com" in t.get("url", ""):
                pt = t["targetId"]; break
        if not pt:
            print("❌ 无 Meta page"); return False
        att = await send_cmd("Target.attachToTarget", {"targetId": pt, "flatten": True})
        sid = att["result"]["sessionId"]
        for m in ["Page.enable", "Runtime.enable", "DOM.enable"]:
            await send_cmd(m, None, sid)
        async def ev(expr):
            r = await send_cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True}, sid)
            return r.get("result", {}).get("result", {}).get("value")

        full = os.environ["PW_FULL"]
        # 1. 找输入框坐标（真实点击）
        pos_s = await ev('''(() => {
            const b = document.querySelector('div[aria-label*="在对话框中输入"]');
            if(!b) return null;
            b.scrollIntoView({block:'center'});
            const r = b.getBoundingClientRect();
            return JSON.stringify({x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2), w: r.width, h: r.height});
        })()''')
        if not pos_s:
            print("❌ 找不到输入框"); return False
        pos = json.loads(pos_s)
        print(f"输入框坐标: {pos}")
        # 2. 真实鼠标点击（CDP Input 事件，非 JS click）
        for e in ["mouseMoved", "mousePressed", "mouseReleased"]:
            p = {"type": e, "x": pos["x"], "y": pos["y"]}
            if e != "mouseMoved":
                p["button"] = "left"; p["clickCount"] = 1
            await send_cmd("Input.dispatchMouseEvent", p, sid)
            await asyncio.sleep(0.15)
        await asyncio.sleep(1)
        # 3. 确认焦点在输入框
        focused = await ev('''(() => { const b=document.querySelector('div[aria-label*="在对话框中输入"]'); return document.activeElement === b || b.contains(document.activeElement); })()''')
        print(f"焦点确认: {focused}")
        # 4. insertText
        await send_cmd("Input.insertText", {"text": full}, sid)
        await asyncio.sleep(2)
        # 5. 验证（innerText + 重新查 DOM）
        ver = await ev('''(() => { const b=document.querySelector('div[aria-label*="在对话框中输入"]'); return b ? b.innerText.length : -1; })()''')
        preview = await ev('''(() => { const b=document.querySelector('div[aria-label*="在对话框中输入"]'); return b ? b.innerText.slice(0,120) : "NO_BOX"; })()''')
        print(f"文案: {ver} 字符")
        print(f"预览: {repr(preview)}")
        # 6. 等 3 秒再查一次（确认 React 状态持久）
        await asyncio.sleep(3)
        ver2 = await ev('''(() => { const b=document.querySelector('div[aria-label*="在对话框中输入"]'); return b ? b.innerText.length : -1; })()''')
        print(f"3秒后复查: {ver2} 字符")
        # 7. 截图
        r = await send_cmd("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False}, sid)
        b64 = r.get("result", {}).get("data", "")
        open(r"C:\Users\Administrator\Downloads\feishu_videos\caption_check2.png", "wb").write(base64.b64decode(b64))
        print("✅ 截图 caption_check2.png")
        return ver2 >= 100

if __name__ == "__main__":
    port, ws_path = get_cdp_info()
    ok = asyncio.run(main(f"ws://127.0.0.1:{port}{ws_path}"))
    sys.exit(0 if ok else 1)
