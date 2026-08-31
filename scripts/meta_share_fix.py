"""Meta 分享修正：点「立即分享」radio -> 点底部「分享」发布按钮（最后一个，y>1000）"""
import json, time, asyncio, sys

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
        meta_pages = [t for t in targets["result"]["targetInfos"] if t.get("type") == "page" and "business.facebook.com" in t.get("url", "")]
        pt = None
        for t in meta_pages:
            if "reels_composer" in t.get("url", ""):
                pt = t["targetId"]; break
        if not pt and meta_pages:
            pt = meta_pages[-1]["targetId"]
        if not pt:
            print("❌ 无 Meta page"); return False
        att = await send_cmd("Target.attachToTarget", {"targetId": pt, "flatten": True})
        sid = att["result"]["sessionId"]
        for m in ["Page.enable", "Runtime.enable"]:
            await send_cmd(m, None, sid)
        async def ev(expr):
            r = await send_cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True}, sid)
            return r.get("result", {}).get("result", {}).get("value")
        async def real_click(x, y, label):
            for e in ["mouseMoved", "mousePressed", "mouseReleased"]:
                p = {"type": e, "x": x, "y": y}
                if e != "mouseMoved":
                    p["button"] = "left"; p["clickCount"] = 1
                await send_cmd("Input.dispatchMouseEvent", p, sid)
                await asyncio.sleep(0.15)
            print(f"✅ 点击{label} ({x},{y})")

        # 1. 确认状态
        t = await ev("document.body.innerText") or ""
        if "正在处理" in t:
            print("✅ 已发布(处理中)"); return True
        # 2. 点「立即分享」radio（真实点击坐标）
        pos_s = await ev('''(() => { const els=[...document.querySelectorAll('div,span,button,[role=radio]')]; const b=els.find(el=>(el.textContent||'').trim()==='立即分享'); if(!b)return null; const r=b.getBoundingClientRect(); return JSON.stringify({x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2)}); })()''')
        if pos_s:
            pos = json.loads(pos_s)
            await real_click(pos["x"], pos["y"], "立即分享")
            await asyncio.sleep(2)
        else:
            print("⚠️ 无立即分享 radio")
        # 3. 点底部「分享」发布按钮（取 y > 1000 的最后一个）
        pos_s = await ev('''(() => { const els=[...document.querySelectorAll('button,[role=button]')].filter(b=>(b.textContent||'').trim()==='分享'&&b.getBoundingClientRect().width>50); if(!els.length)return null; const b=els[els.length-1]; const r=b.getBoundingClientRect(); return JSON.stringify({x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2),y0:Math.round(r.y)}); })()''')
        if pos_s:
            pos = json.loads(pos_s)
            print(f"分享按钮位置: {pos}")
            await real_click(pos["x"], pos["y"], "分享(底部)")
        else:
            print("⚠️ 无分享按钮"); return False
        # 4. 验证
        await asyncio.sleep(10)
        t2 = await ev("document.body.innerText") or ""
        ok = "正在处理" in t2 or "已发布" in t2
        print(f"结果: {'✅ 发布已触发!' if ok else '⚠️ 请检查页面'}")
        if not ok:
            print("BODY尾:", t2[-200:])
        return ok

if __name__ == "__main__":
    port, ws_path = get_cdp_info()
    ok = asyncio.run(main(f"ws://127.0.0.1:{port}{ws_path}"))
    sys.exit(0 if ok else 1)
