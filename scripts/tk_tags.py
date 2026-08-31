"""TikTok 标签逐个输入：光标到末尾 -> 输入 #tag -> 等弹窗 -> 回车确认 -> 验证"""
import json, time, asyncio, os, sys

def get_cdp_info(profile_id="k1dqriqs", suffix="h1msnw4"):
    port_file = rf"D:\.ADSPOWER_GLOBAL\cache\{profile_id}_{suffix}\DevToolsActivePort"
    with open(port_file) as f:
        port = f.readline().strip()
        ws_path = f.readline().strip()
    return port, ws_path

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
        async def key(k, code, modifiers=0):
            await send_cmd("Input.dispatchKeyEvent", {"type": "keyDown", "key": k, "code": code, "modifiers": modifiers}, sid)
            await send_cmd("Input.dispatchKeyEvent", {"type": "keyUp", "key": k, "code": code, "modifiers": modifiers}, sid)

        # 1. 点击 Description 编辑器（保持焦点）
        pos_s = await ev('''(() => {
            const box = document.querySelector('.public-DraftEditor-content, [contenteditable="true"]');
            if (!box) return null;
            const r = box.getBoundingClientRect();
            return JSON.stringify({x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2)});
        })()''')
        if not pos_s:
            print("❌ 找不到编辑器"); return False
        pos = json.loads(pos_s)
        await real_click(pos["x"], pos["y"])
        await asyncio.sleep(0.8)
        # 2. Ctrl+End 到末尾
        await key("End", "End", 2)
        await asyncio.sleep(0.3)
        # 3. 逐个输入标签
        for i, tag in enumerate(tags):
            tag_clean = tag.lstrip('#').strip()
            print(f"[{i+1}/{len(tags)}] 输入 #{tag_clean}")
            # 输入空格 + #tag（用 Input.insertText，模拟真实键盘）
            await send_cmd("Input.insertText", {"text": f" #{tag_clean}"}, sid)
            await asyncio.sleep(2.0)  # 等热度弹窗
            # 检查是否出现标签建议弹窗
            suggest = await ev('''(() => {
                const all = document.body.innerText;
                const m = all.match(/(\\d+(?:\\.\\d+)?[KMB]?)\\s*(?:views|posts|videos)?/i);
                const els = [...document.querySelectorAll('[class*="suggest"], [class*="mention"], [role="listbox"], [role="option"]')];
                return JSON.stringify({listbox: els.length, sample: (els[0]?.innerText||'').slice(0,60)});
            })()''')
            print(f"   弹窗检查: {suggest}")
            # 按回车确认
            await key("Enter", "Enter")
            await asyncio.sleep(1.0)
            # 验证当前文本
            cur = await ev('''(() => { const box=document.querySelector('[contenteditable="true"]'); return box ? box.innerText.length : -1; })()''')
            tail = await ev('''(() => { const box=document.querySelector('[contenteditable="true"]'); return box ? box.innerText.slice(-30) : ''; })()''')
            print(f"   当前长度: {cur} 末尾: {repr(tail)}")
        return True

if __name__ == "__main__":
    port, ws_path = get_cdp_info()
    tags = json.loads(os.environ["TK_TAGS"])
    ok = asyncio.run(main(f"ws://127.0.0.1:{port}{ws_path}", tags))
    sys.exit(0 if ok else 1)
