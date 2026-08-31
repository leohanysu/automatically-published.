"""续传：等上传100% -> 下一页 -> 立即分享 -> 分享 -> 验证"""
import json, time, asyncio, os, sys, re

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

        # 1. 等上传完成（100% + 删除）
        for i in range(50):
            t = await ev("document.body.innerText") or ""
            m = re.search(r"(\d+)%", t)
            pct = m.group(1) if m else "?"
            if "100%" in t and "删除" in t:
                print(f"✅ 上传完成 (第{i+1}次轮询)")
                break
            if i % 2 == 0:
                print(f"   上传 {pct}%...")
            await asyncio.sleep(6)
        else:
            print("⚠️ 上传超时"); return False

        # 2. 复查文案仍在
        ver = await ev('''(() => { const b=document.querySelector('div[aria-label*="在对话框中输入"]'); return b ? b.innerText.length : -1; })()''')
        print(f"文案复查: {ver} 字符")
        if ver and ver >= 100:
            print("✅ 文案仍在")
        else:
            print("⚠️ 文案丢失"); return False

        # 3. 点「下一页」（真实点击，更稳）
        pos_s = await ev('''(() => { const els=[...document.querySelectorAll('button,[role=button]')].filter(b=>(b.textContent||'').includes('下一页')&&b.getBoundingClientRect().width>50); if(!els.length)return null; const b=els[els.length-1]; const r=b.getBoundingClientRect(); return JSON.stringify({x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2)}); })()''')
        if not pos_s:
            print("❌ 无下一页按钮"); return False
        pos = json.loads(pos_s)
        print(f"点击下一页 ({pos['x']},{pos['y']})")
        for e in ["mouseMoved", "mousePressed", "mouseReleased"]:
            p = {"type": e, "x": pos["x"], "y": pos["y"]}
            if e != "mouseMoved":
                p["button"] = "left"; p["clickCount"] = 1
            await send_cmd("Input.dispatchMouseEvent", p, sid)
            await asyncio.sleep(0.15)
        await asyncio.sleep(5)

        # 4. 确认分享设置页
        t = await ev("document.body.innerText") or ""
        print("含立即分享:", "立即分享" in t)
        if "正在处理" in t:
            print("✅ 已发布(处理中)"); return True

        # 5. 点「立即分享」（真实点击）
        pos_s = await ev('''(() => { const els=[...document.querySelectorAll('div,span,button,[role=radio]')]; const b=els.find(el=>(el.textContent||'').trim()==='立即分享'); if(!b)return null; const r=b.getBoundingClientRect(); return JSON.stringify({x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2)}); })()''')
        if pos_s:
            pos = json.loads(pos_s)
            print(f"点击立即分享 ({pos['x']},{pos['y']})")
            for e in ["mouseMoved", "mousePressed", "mouseReleased"]:
                p = {"type": e, "x": pos["x"], "y": pos["y"]}
                if e != "mouseMoved":
                    p["button"] = "left"; p["clickCount"] = 1
                await send_cmd("Input.dispatchMouseEvent", p, sid)
                await asyncio.sleep(0.15)
            await asyncio.sleep(2)
        else:
            print("⚠️ 无立即分享按钮")

        # 6. 点底部「分享」（真实点击）
        pos_s = await ev('''(() => { const els=[...document.querySelectorAll('button,[role=button]')].filter(b=>(b.textContent||'').trim()==='分享'&&b.getBoundingClientRect().width>50); if(!els.length)return null; const b=els[els.length-1]; const r=b.getBoundingClientRect(); return JSON.stringify({x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2)}); })()''')
        if pos_s:
            pos = json.loads(pos_s)
            print(f"点击分享 ({pos['x']},{pos['y']})")
            for e in ["mouseMoved", "mousePressed", "mouseReleased"]:
                p = {"type": e, "x": pos["x"], "y": pos["y"]}
                if e != "mouseMoved":
                    p["button"] = "left"; p["clickCount"] = 1
                await send_cmd("Input.dispatchMouseEvent", p, sid)
                await asyncio.sleep(0.15)
        else:
            print("⚠️ 无分享按钮"); return False

        # 7. 验证
        await asyncio.sleep(10)
        t2 = await ev("document.body.innerText") or ""
        ok = "正在处理" in t2 or "已发布" in t2
        print(f"结果: {'✅ 发布已触发!' if ok else '⚠️ 请检查页面'}")
        if not ok:
            print("BODY尾:", t2[-300:])
        return ok

if __name__ == "__main__":
    port, ws_path = get_cdp_info()
    ok = asyncio.run(main(f"ws://127.0.0.1:{port}{ws_path}"))
    sys.exit(0 if ok else 1)
