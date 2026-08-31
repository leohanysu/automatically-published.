"""Meta Reels 完整发布（websocket CDP 直连，支持 >50MB 原视频）
用法: python publish_ws.py <video_path> "<title>" "<body>" "<tags>"
前置: SunBrowser 运行中, 视口正常(>500px), 页面已打开 composer
"""
import json, time, sys, re, asyncio, urllib.request, os

def get_cdp_info(profile_id="k1dqriqs", suffix="h1msnw4"):
    port_file = rf"D:\.ADSPOWER_GLOBAL\cache\{profile_id}_{suffix}\DevToolsActivePort"
    with open(port_file) as f:
        port = f.readline().strip()
        ws_path = f.readline().strip()
    return port, ws_path

async def main(video, title, body, tags, cdp_ws):
    full = f"{title}\n\n{body}\n\n{tags}"
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
        state = {"mid": 0, "chooser": None}
        async def send_cmd(method, params=None, sid=None, timeout=20):
            state["mid"] += 1
            mid = state["mid"]
            msg = {"id": mid, "method": method, "params": params or {}}
            if sid: msg["sessionId"] = sid
            await ws.send(json.dumps(msg))
            while True:
                data = await asyncio.wait_for(msg_q.get(), timeout=timeout)
                if data.get("id") == mid:
                    return data
                if data.get("method") == "Page.fileChooserOpened":
                    state["chooser"] = data["params"].get("backendNodeId")
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
        h = await ev("innerHeight")
        if not h or h < 500:
            print(f"❌ 视口异常 h={h}"); return False
        await send_cmd("Page.setInterceptFileChooserDialog", {"enabled": True}, sid)
        pos_s = await ev("""(() => { const els=[...document.querySelectorAll('div,span,button')];
            const b=els.find(el=>el.textContent.trim()==='添加视频'&&el.getBoundingClientRect().width>50);
            if(!b)return null; const r=b.getBoundingClientRect();
            return JSON.stringify({x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2)}); })()""")
        if not pos_s:
            print("❌ 无添加视频按钮（可能已上传过，跳过上传）"); pos = None
        else:
            pos = json.loads(pos_s)
            for e in ["mouseMoved","mousePressed","mouseReleased"]:
                p = {"type": e, "x": pos["x"], "y": pos["y"]}
                if e != "mouseMoved": p["button"]="left"; p["clickCount"]=1
                await send_cmd("Input.dispatchMouseEvent", p, sid)
                await asyncio.sleep(0.1)
            for i in range(20):
                if state["chooser"]: break
                await send_cmd("Runtime.evaluate", {"expression":"1","returnByValue":True}, sid, timeout=5)
                await asyncio.sleep(0.3)
            if not state["chooser"]:
                print("❌ 未捕获 chooser"); return False
            r = await send_cmd("DOM.setFileInputFiles", {"backendNodeId": state["chooser"], "files": [video]}, sid, timeout=60)
            if "error" in r:
                print(f"❌ set: {r['error']}"); return False
            print("✅ 视频已设置")
            for i in range(40):
                await asyncio.sleep(6)
                t = await ev("document.body.innerText") or ""
                m = re.search(r"(\d+)%", t)
                pct = m.group(1) if m else "?"
                if "100%" in t and "删除" in t:
                    print("✅ 上传完成"); break
                print(f"   上传 {pct}%...")
        # 填文案
        await ev("""(() => { const b=document.querySelector('div[contenteditable="true"]'); if(b){b.focus();return true;} return false; })()""")
        await asyncio.sleep(0.5)
        await send_cmd("Input.insertText", {"text": full}, sid)
        await asyncio.sleep(2)
        ver = await ev("""(() => { const b=document.querySelector('div[contenteditable="true"]'); return b?b.innerText.length:-1; })()""")
        print(f"文案: {ver} 字符")
        if ver < 100:
            print("❌ 文案填充异常"); return False
        # 下一页 -> 分享
        for step in range(5):
            await ev("""(() => { let a=[...document.querySelectorAll('button,[role=button]')].filter(b=>(b.textContent||'').includes('下一页')); if(a.length)a[a.length-1].click(); return a.length; })()""")
            await asyncio.sleep(3)
            t = await ev("document.body.innerText") or ""
            has_share = await ev("""[...document.querySelectorAll('button,[role=button]')].some(b=>(b.textContent||'').trim()==='分享')""")
            if "正在处理" in t:
                print("✅ 已发布(处理中)"); return True
            if has_share:
                await ev("""(() => { const els=[...document.querySelectorAll('div,span,button,[role=radio]')]; const t=els.find(el=>(el.textContent||'').trim()==='立即分享'); if(t)t.click(); return !!t; })()""")
                await asyncio.sleep(2)
                await ev("""(() => { let s=[...document.querySelectorAll('button,[role=button]')].filter(b=>(b.textContent||'').trim()==='分享'); if(s.length)s[s.length-1].click(); return s.length; })()""")
                await asyncio.sleep(8)
                t2 = await ev("document.body.innerText") or ""
                ok = "正在处理" in t2 or "已发布" in t2
                print(f"结果: {'✅ 发布已触发!' if ok else '⚠️ 请检查页面'}")
                return ok
        print("❌ 未到分享页"); return False

if __name__ == "__main__":
    import websockets
    video, title, body, tags = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    port, ws_path = get_cdp_info()
    ok = asyncio.run(main(video, title, body, tags, f"ws://127.0.0.1:{port}{ws_path}"))
    sys.exit(0 if ok else 1)
