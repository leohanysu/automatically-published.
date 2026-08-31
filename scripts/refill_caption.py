"""重新填文案（用正确的 aria-label 选择器）+ 点下一页，供用户检查"""
import json, time, asyncio, urllib.request, os, base64

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
        # 1. 用正确 aria-label 聚焦输入框（记忆血泪教训：禁裸 div[contenteditable]）
        ok = await ev('''(() => { const b=document.querySelector('div[aria-label*="在对话框中输入"]'); if(!b)return false; b.focus(); b.click(); return true; })()''')
        print(f"聚焦输入框: {ok}")
        await asyncio.sleep(1)
        # 2. insertText 填入
        await send_cmd("Input.insertText", {"text": full}, sid)
        await asyncio.sleep(2)
        # 3. 验证
        ver = await ev('''(() => { const b=document.querySelector('div[aria-label*="在对话框中输入"]'); return b ? b.innerText.length : -1; })()''')
        preview = await ev('''(() => { const b=document.querySelector('div[aria-label*="在对话框中输入"]'); return b ? b.innerText.slice(0,200) : "NO_BOX"; })()''')
        print(f"文案: {ver} 字符")
        print(f"预览: {repr(preview)}")
        if ver < 100:
            print("❌ 文案填充异常"); return False
        # 4. 截图供用户检查
        r = await send_cmd("Page.captureScreenshot", {"format": "png"}, sid)
        b64 = r.get("result", {}).get("data", "")
        open(r"C:\Users\Administrator\Downloads\feishu_videos\caption_check.png", "wb").write(base64.b64decode(b64))
        print("✅ 截图已存 caption_check.png")
        # 5. 点「下一页」（用户要求：填好先点下一页，不点分享）
        nxt = await ev('''(() => { let a=[...document.querySelectorAll('button,[role=button]')].filter(b=>(b.textContent||'').includes('下一页')); if(a.length){a[a.length-1].click(); return a.length;} return 0; })()''')
        print(f"点击下一页: {nxt} 个按钮")
        await asyncio.sleep(4)
        t = await ev("document.body.innerText") or ""
        print("页面含分享:", "分享" in t)
        return True

if __name__ == "__main__":
    port, ws_path = get_cdp_info()
    ok = asyncio.run(main(f"ws://127.0.0.1:{port}{ws_path}"))
    sys.exit(0 if ok else 1)
