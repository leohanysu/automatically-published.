"""继续发布：下一页 -> 立即分享 -> 分享 -> 验证"""
import json, time, asyncio, os, sys

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
        for m in ["Page.enable", "Runtime.enable"]:
            await send_cmd(m, None, sid)
        async def ev(expr):
            r = await send_cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True}, sid)
            return r.get("result", {}).get("result", {}).get("value")

        # 1. 先判断在哪个页面：有「立即分享」= 分享设置页，直接发；有文案框 = 编辑页，先复查文案
        has_immediate = await ev('''[...document.querySelectorAll('div,span,button,[role=radio]')].some(el=>(el.textContent||'').trim()==='立即分享')''')
        ver = -1
        if has_immediate:
            print("已在分享设置页，跳过文案复查")
        else:
            ver = await ev('''(() => { const b=document.querySelector('div[aria-label*="在对话框中输入"]'); return b ? b.innerText.length : -1; })()''')
            print(f"文案复查: {ver} 字符")
            if ver and ver >= 100:
                print("✅ 文案仍在，继续")
            else:
                print("⚠️ 文案丢失！停止"); return False

        # 2. 点「下一页」（可能已到分享页，则跳过）
        for step in range(4):
            has_next = await ev('''[...document.querySelectorAll('button,[role=button]')].filter(b=>(b.textContent||'').includes('下一页')).length''')
            has_share = await ev('''[...document.querySelectorAll('button,[role=button]')].some(b=>(b.textContent||'').trim()==='分享')''')
            if has_share:
                print("已到分享页 ✅")
                break
            if has_next:
                await ev('''(() => { let a=[...document.querySelectorAll('button,[role=button]')].filter(b=>(b.textContent||'').includes('下一页')); if(a.length)a[a.length-1].click(); return a.length; })()''')
                print(f"点击下一页 (step {step+1})")
                await asyncio.sleep(4)
            else:
                print(f"⚠️ 无下一页无分享 (step {step+1})"); return False

        # 3. 点「立即分享」
        t = await ev("document.body.innerText") or ""
        print("页面含正在处理:", "正在处理" in t)
        if "正在处理" in t:
            print("✅ 已发布(处理中)"); return True
        got = await ev('''(() => { const els=[...document.querySelectorAll('div,span,button,[role=radio]')]; const t=els.find(el=>(el.textContent||'').trim()==='立即分享'); if(t){t.click(); return true;} return false; })()''')
        print(f"点击立即分享: {got}")
        await asyncio.sleep(2)
        # 4. 点底部「分享」
        got2 = await ev('''(() => { let s=[...document.querySelectorAll('button,[role=button]')].filter(b=>(b.textContent||'').trim()==='分享'); if(s.length){s[s.length-1].click(); return s.length;} return 0; })()''')
        print(f"点击分享: {got2} 个")
        # 5. 验证
        await asyncio.sleep(10)
        t2 = await ev("document.body.innerText") or ""
        ok = "正在处理" in t2 or "已发布" in t2
        print(f"结果: {'✅ 发布已触发!' if ok else '⚠️ 请检查页面'}")
        if not ok:
            print("BODY:", t2[-300:])
        return ok

if __name__ == "__main__":
    port, ws_path = get_cdp_info()
    ok = asyncio.run(main(f"ws://127.0.0.1:{port}{ws_path}"))
    sys.exit(0 if ok else 1)
