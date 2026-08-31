"""TikTok 点 Post（滚动到按钮 + 真实点击 + 验证跳转）"""
import json, time, asyncio, sys, os

def get_cdp_info(profile_id="k1dqriqs", suffix="h1msnw4"):
    port_file = rf"D:\.ADSPOWER_GLOBAL\cache\{profile_id}_{suffix}\DevToolsActivePort"
    with open(port_file) as f:
        port = f.readline().strip()
        ws_path = f.readline().strip()
    return port, ws_path

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
        for m in ["Page.enable", "Runtime.enable"]:
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
        # 1. 滚动 Post 到视口
        r = await ev('''(() => {
            const b = [...document.querySelectorAll('button')].find(b => (b.innerText||'').trim() === 'Post' && b.offsetWidth > 0);
            if (!b) return 'NO_POST';
            b.scrollIntoView({block:'center', behavior:'instant'});
            return 'SCROLLED';
        })()''')
        print(r)
        await asyncio.sleep(1)
        # 2. 取坐标点击
        pos_s = await ev('''(() => {
            const b = [...document.querySelectorAll('button')].find(b => (b.innerText||'').trim() === 'Post' && b.offsetWidth > 0);
            if (!b) return null;
            const r = b.getBoundingClientRect();
            return JSON.stringify({x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2), vis: r.y >= 0 && r.y < innerHeight});
        })()''')
        pos = json.loads(pos_s)
        print(f"Post: {pos}")
        await real_click(pos["x"], pos["y"])
        print("已点击 Post")
        # 3. 验证
        for i in range(12):
            await asyncio.sleep(4)
            t = await ev("document.body.innerText") or ""
            url = await ev("location.href") or ""
            if "post/" in url or "being" in t.lower() or "posted" in t.lower():
                print(f"✅ 发布触发! ({i*4}s) URL={url[:70]}")
                return True
            print(f"   {i*4}s...")
        return False

if __name__ == "__main__":
    port, ws_path = get_cdp_info()
    ok = asyncio.run(main(f"ws://127.0.0.1:{port}{ws_path}"))
    sys.exit(0 if ok else 1)
