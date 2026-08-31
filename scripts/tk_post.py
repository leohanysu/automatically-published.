"""TikTok 极简发布：打开upload -> Continue草稿(不碰Discard) -> 直接Post（草稿内容不管）
2026-08-20 用户明确：草稿内容不用管，直接发布
"""
import json, time, asyncio, os, sys, base64

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

        # 1. 确保在 upload 页（不在就导航过去）
        url = await ev("location.href") or ""
        if "upload" not in url:
            print(f"导航到 upload（当前 {url[:60]}）")
            await send_cmd("Page.navigate", {"url": "https://www.tiktok.com/tiktokstudio/upload"}, sid)
            await asyncio.sleep(8)
        # 2. 关弹窗：Continue（保留草稿）优先，Not now/Got it 其次；不碰 Discard
        for attempt in range(8):
            r = await ev('''(() => {
                const btns = [...document.querySelectorAll('button')].filter(b => b.offsetWidth > 0);
                const txt = (b) => (b.innerText||'').trim();
                const c = btns.find(b => txt(b) === 'Continue' && b.getBoundingClientRect().width > 50);
                if (c) { c.click(); return 'CONTINUE'; }
                const n = btns.find(b => txt(b) === 'Not now');
                if (n) { n.click(); return 'NOT_NOW'; }
                const g = btns.find(b => txt(b) === 'Got it');
                if (g) { g.click(); return 'GOT_IT'; }
                return 'NONE';
            })()''')
            print(f"弹窗: {r}")
            if r == 'NONE':
                break
            await asyncio.sleep(3)
        # 3. 确认草稿内容（只读，不改）
        ver = await ev('''(() => {
            const box = document.querySelector('[contenteditable="true"]');
            const t = box ? box.innerText : '';
            const html = box ? box.innerHTML : '';
            return JSON.stringify({
                len: t.length, head: t.slice(0,40), tail: t.slice(-60),
                strong: (html.match(/<strong>/g)||[]).length,
                hasPost: [...document.querySelectorAll('button')].some(b=>(b.innerText||'').trim()==='Post'&&b.offsetWidth>0)
            });
        })()''')
        print(f"草稿: {ver}")
        # 4. 点 Post（真实点击）
        pos_s = await ev('''(() => {
            const b = [...document.querySelectorAll('button')].find(b => (b.innerText||'').trim() === 'Post' && b.offsetWidth > 0);
            if (!b) return null;
            const r = b.getBoundingClientRect();
            return JSON.stringify({x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2)});
        })()''')
        if not pos_s:
            print("❌ 无 Post 按钮"); return False
        pos = json.loads(pos_s)
        print(f"点击 Post ({pos['x']},{pos['y']})")
        await real_click(pos["x"], pos["y"])
        # 5. 验证发布
        for i in range(12):
            await asyncio.sleep(4)
            t = await ev("document.body.innerText") or ""
            url = await ev("location.href") or ""
            if "post/" in url or "being" in t.lower() or "posted" in t.lower():
                print(f"✅ 发布触发! ({i*4}s) URL={url[:70]}")
                break
            print(f"   {i*4}s 等待...")
        return True

if __name__ == "__main__":
    port, ws_path = get_cdp_info()
    ok = asyncio.run(main(f"ws://127.0.0.1:{port}{ws_path}"))
    sys.exit(0 if ok else 1)
