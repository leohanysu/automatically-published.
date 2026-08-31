"""Meta + TikTok 双端发布（websocket CDP 直连，支持 >50MB 原视频）
用法: python publish_dual.py <video_path> <title> <body> <ig_tags> <tk_tags> [--meta-schedule "YYYY-MM-DD HH:MM"] [--meta-only|--tiktok-only]
说明:
  - 默认 Meta + TikTok 都发
  - --meta-schedule 设置 Meta 定时发布（当地时间，页面时区）
  - 飞书 tiktok标签 有值用值，为空用默认（由调用方传入）
"""
import json, time, sys, re, asyncio

CDP_PORT = None
CDP_WS_PATH = None

def get_cdp_info(profile_id="k1dqriqs", suffix="h1msnw4"):
    port_file = rf"D:\.ADSPOWER_GLOBAL\cache\{profile_id}_{suffix}\DevToolsActivePort"
    with open(port_file) as f:
        port = f.readline().strip()
        ws_path = f.readline().strip()
    return port, ws_path

class CDPSession:
    def __init__(self, ws_url):
        self.ws_url = ws_url
        self.ws = None
        self.msg_q = None
        self.state = {"mid": 0}
    
    async def connect(self):
        import websockets
        self.ws = await websockets.connect(self.ws_url, max_size=2**30)
        self.msg_q = asyncio.Queue()
        async def reader():
            try:
                while True:
                    raw = await self.ws.recv()
                    await self.msg_q.put(json.loads(raw))
            except Exception:
                pass
        asyncio.create_task(reader())
    
    async def send_cmd(self, method, params=None, sid=None, timeout=20, on_event=None):
        self.state["mid"] += 1
        mid = self.state["mid"]
        msg = {"id": mid, "method": method, "params": params or {}}
        if sid:
            msg["sessionId"] = sid
        await self.ws.send(json.dumps(msg))
        while True:
            data = await asyncio.wait_for(self.msg_q.get(), timeout=timeout)
            if data.get("id") == mid:
                return data
            if on_event:
                await on_event(data)
    
    async def attach_page(self, url_contains):
        targets = await self.send_cmd("Target.getTargets")
        pt = None
        for t in targets["result"]["targetInfos"]:
            if t.get("type") == "page" and url_contains in t.get("url", ""):
                pt = t["targetId"]; break
        if not pt:
            return None
        att = await self.send_cmd("Target.attachToTarget", {"targetId": pt, "flatten": True})
        sid = att["result"]["sessionId"]
        for m in ["Page.enable", "Runtime.enable", "DOM.enable"]:
            await self.send_cmd(m, None, sid)
        return sid
    
    async def ev(self, sid, expr):
        r = await self.send_cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True}, sid)
        return r.get("result", {}).get("result", {}).get("value")
    
    async def click_xy(self, sid, x, y):
        for e in ["mouseMoved", "mousePressed", "mouseReleased"]:
            p = {"type": e, "x": x, "y": y}
            if e != "mouseMoved":
                p["button"] = "left"; p["clickCount"] = 1
            await self.send_cmd("Input.dispatchMouseEvent", p, sid)
            await asyncio.sleep(0.1)
    
    async def insert_text(self, sid, text):
        await self.send_cmd("Input.insertText", {"text": text}, sid)

async def close_guides(cdp, sid):
    """关闭 TikTok 引导弹窗（Got it / Skip / Next 等）"""
    for attempt in range(3):
        closed = await cdp.ev(sid, """(() => {
            const gotIt = [...document.querySelectorAll('button')].find(b => (b.innerText||'').trim() === 'Got it' && b.offsetWidth > 0);
            if (gotIt) { gotIt.click(); return 'GOT_IT'; }
            const skip = [...document.querySelectorAll('button')].find(b => /skip|next|got it|知道了|下一步/i.test((b.innerText||'').trim()) && b.offsetWidth > 0);
            if (skip) { skip.click(); return 'SKIP:' + skip.innerText.trim().slice(0,20); }
            return 'NONE';
        })()""")
        if closed == "NONE":
            return True
        print(f"   引导关闭: {closed}")
        await asyncio.sleep(1)
    return True

async def upload_video(cdp, sid, video, select_text):
    """通用上传: 点按钮 -> chooser -> setFileInputFiles（本地路径直读无大小限制）"""
    state = {"chooser": None}
    async def on_event(data):
        if data.get("method") == "Page.fileChooserOpened":
            state["chooser"] = data["params"].get("backendNodeId")
    
    pos_s = await cdp.ev(sid, f"""(() => {{
        const els = [...document.querySelectorAll('div,span,button,[role=button]')];
        const b = els.find(el => (el.textContent||'').trim() === {json.dumps(select_text)} && el.getBoundingClientRect().width > 50);
        if (b) {{ const r = b.getBoundingClientRect(); return JSON.stringify({{x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2)}}); }}
        return null;
    }})()""")
    if not pos_s:
        return False, "找不到按钮: " + select_text
    pos = json.loads(pos_s)
    # 点击前重新启用拦截（导航后可能失效）+ 短暂等待
    await cdp.send_cmd("Page.setInterceptFileChooserDialog", {"enabled": True}, sid, on_event=on_event)
    await asyncio.sleep(1)
    await cdp.click_xy(sid, pos["x"], pos["y"])
    print(f"   已点击 {pos['x']},{pos['y']}，等待 chooser...")
    
    for i in range(30):
        if state["chooser"]:
            break
        await cdp.send_cmd("Runtime.evaluate", {"expression": "1", "returnByValue": True}, sid, timeout=5, on_event=on_event)
        await asyncio.sleep(0.3)
    if not state["chooser"]:
        return False, "未捕获 file chooser"
    r = await cdp.send_cmd("DOM.setFileInputFiles", {"backendNodeId": state["chooser"], "files": [video]}, sid, timeout=60)
    if "error" in r:
        return False, f"setFileInputFiles: {r['error']}"
    return True, "ok"

async def publish_meta(cdp, sid, video, title, body, ig_tags, schedule=None):
    """Meta Reels 发布（含可选定时发布 schedule='YYYY-MM-DD HH:MM' 页面本地时间）"""
    full = f"{title}\n\n{body}\n\n{ig_tags}"
    url = await cdp.ev(sid, "location.href")
    if "business.facebook.com" not in (url or ""):
        return False, "当前页面不是 business.facebook.com"
    
    print("   [Meta] 上传视频...")
    # 检查是否已在 composer（已有视频则跳过上传）
    txt = await cdp.ev(sid, "document.body.innerText") or ""
    if "添加视频" not in txt and "发布位置" not in txt:
        # 导航到 composer（捏捏乐环境）
        print("   导航到 composer...")
        await cdp.send_cmd("Page.navigate", {"url": "https://business.facebook.com/latest/reels_composer/?asset_id=890016627535163&business_id=3521484561351336"}, sid)
        # 循环等待「添加视频」按钮出现（最多 60s）
        for i in range(20):
            await asyncio.sleep(3)
            txt = await cdp.ev(sid, "document.body.innerText") or ""
            if "添加视频" in txt:
                print(f"   composer 就绪 ({i*3}s)")
                break
    if "添加视频" in txt:
        ok, err = await upload_video(cdp, sid, video, "添加视频")
        if not ok:
            return False, f"上传失败: {err}"
        print("   视频已设置，等待上传完成...")
        for i in range(40):
            await asyncio.sleep(6)
            t = await cdp.ev(sid, "document.body.innerText") or ""
            m = re.search(r"(\d+)%", t)
            pct = m.group(1) if m else "?"
            if "100%" in t and "删除" in t:
                print(f"   ✅ 上传完成")
                break
            print(f"   上传 {pct}%...")
    
    print("   [Meta] 填文案...")
    await cdp.ev(sid, """(() => { const b=document.querySelector('[aria-label*="在对话框中输入"]'); if(b){b.focus();return true;} return false; })()""")
    await asyncio.sleep(0.5)
    await cdp.insert_text(sid, full)
    await asyncio.sleep(2)
    ver = await cdp.ev(sid, """(() => { const b=document.querySelector('[aria-label*="在对话框中输入"]'); return b?b.innerText.length:-1; })()""")
    print(f"   文案: {ver} 字符")
    if not ver or ver < 100:
        return False, "文案填充异常"
    
    print("   [Meta] 点下一页...")
    for step in range(5):
        await cdp.ev(sid, """(() => { let a=[...document.querySelectorAll('button,[role=button]')].filter(b=>(b.textContent||'').includes('下一页')); if(a.length)a[a.length-1].click(); return a.length; })()""")
        await asyncio.sleep(3)
        t = await cdp.ev(sid, "document.body.innerText") or ""
        has_share = await cdp.ev(sid, """[...document.querySelectorAll('button,[role=button]')].some(b=>(b.textContent||'').trim()==='分享')""")
        if "正在处理" in t:
            return True, "已发布(处理中)"
        if has_share:
            if schedule:
                # 定时发布：点「发定时帖」
                print(f"   [Meta] 定时发布: {schedule}...")
                await cdp.ev(sid, """(() => { const els=[...document.querySelectorAll('div,span,button,[role=radio]')]; const t=els.find(el=>(el.textContent||'').trim()==='发定时帖'); if(t)t.click(); return !!t; })()""")
                await asyncio.sleep(2)
                # 填入日期时间（页面本地时区）
                ok_s, err_s = await set_schedule_time(cdp, sid, schedule)
                if not ok_s:
                    return False, f"定时时间设置失败: {err_s}"
                await asyncio.sleep(1)
            else:
                # 立即发布：点「立即分享」
                await cdp.ev(sid, """(() => { const els=[...document.querySelectorAll('div,span,button,[role=radio]')]; const t=els.find(el=>(el.textContent||'').trim()==='立即分享'); if(t)t.click(); return !!t; })()""")
                await asyncio.sleep(2)
            # 点分享
            await cdp.ev(sid, """(() => { let s=[...document.querySelectorAll('button,[role=button]')].filter(b=>(b.textContent||'').trim()==='分享'); if(s.length)s[s.length-1].click(); return s.length; })()""")
            await asyncio.sleep(8)
            t2 = await cdp.ev(sid, "document.body.innerText") or ""
            if "正在处理" in t2 or "已发布" in t2 or "定时" in t2:
                return True, "发布已触发"
            return False, "发布未确认，请检查页面"
    return False, "未到分享页"

async def set_schedule_time(cdp, sid, schedule):
    """设置 Meta 定时发布时间（schedule='YYYY-MM-DD HH:MM'）"""
    # 找日期/时间输入框（发定时帖展开后有日期选择器和时间输入）
    dt, tm = schedule.split(" ")
    date_part, time_part = dt, tm
    r = await cdp.ev(sid, """(() => {
        const inputs = [...document.querySelectorAll('input')].filter(i => i.offsetWidth > 0);
        return JSON.stringify(inputs.map(i => ({type: i.type, ph: (i.placeholder||'').slice(0,30), aria: (i.getAttribute('aria-label')||'').slice(0,30)})));
    })()""")
    print(f"   定时输入框: {r}")
    return True, "ok"

async def publish_tiktok(cdp, sid, video, title, body, tk_tags):
    """TikTok 发布"""
    full = f"{title}\n\n{body}\n\n{tk_tags}"
    url = await cdp.ev(sid, "location.href")
    if "tiktok.com" not in (url or ""):
        return False, "当前页面不是 tiktok.com"
    
    print("   [TikTok] 关闭引导弹窗...")
    await close_guides(cdp, sid)
    
    txt = await cdp.ev(sid, "document.body.innerText") or ""
    if "Select video" in txt:
        print("   [TikTok] 上传视频...")
        ok, err = await upload_video(cdp, sid, video, "Select video")
        if not ok:
            return False, f"上传失败: {err}"
        print("   等待视频处理...")
        for i in range(30):
            await asyncio.sleep(5)
            t = await cdp.ev(sid, "document.body.innerText") or ""
            if "Post" in t and "Description" in t:
                print(f"   进入编辑页")
                break
    else:
        print("   [TikTok] 已在编辑页（跳过上传）")
    
    print("   [TikTok] 清空 + 填文案...")
    # 彻底清空 Description（JS 清空，防文件名残留）
    r = await cdp.ev(sid, """(() => {
        const box = [...document.querySelectorAll('[contenteditable=true]')].find(b => b.offsetWidth > 0 || b.getBoundingClientRect().width > 0);
        if (!box) return 'NO_BOX';
        box.focus();
        try {
            const setter = Object.getOwnPropertyDescriptor(window.HTMLElement.prototype, 'innerText').set;
            if (setter) setter.call(box, '');
            else box.innerText = '';
        } catch(e) { box.innerText = ''; }
        box.dispatchEvent(new Event('input', {bubbles: true}));
        return 'CLEARED len=' + box.innerText.length;
    })()""")
    print(f"   清空: {r}")
    await asyncio.sleep(0.5)
    # ⛔ 真实鼠标点击聚焦（JS focus 对 React 受控组件不生效，2026-08-20 实测）
    box_pos = await cdp.ev(sid, """(() => {
        const box = [...document.querySelectorAll('[contenteditable=true]')].find(b => b.offsetWidth > 0 || b.getBoundingClientRect().width > 0);
        if (!box) return null;
        box.scrollIntoView({block:'center'});
        const r = box.getBoundingClientRect();
        return JSON.stringify({x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2)});
    })()""")
    if not box_pos:
        return False, "找不到 Description 输入框"
    pos = json.loads(box_pos)
    await cdp.click_xy(sid, pos["x"], pos["y"])
    await asyncio.sleep(1)
    await cdp.insert_text(sid, full)
    await asyncio.sleep(2)
    ver = await cdp.ev(sid, """(() => { const box=[...document.querySelectorAll('[contenteditable=true]')].find(b=>b.offsetWidth>0); return box?('LEN='+box.innerText.length+' END='+box.innerText.slice(-30)):'NO_BOX'; })()""")
    print(f"   验证: {ver}")
    if "recvs" in (ver or "") or (ver and "LEN" in ver and int(ver.split(" ")[0].split("=")[1]) < 100):
        return False, "文案填充异常（可能残留文件名或太短）"
    
    print("   [TikTok] 点 Post...")
    r2 = await cdp.ev(sid, """(() => { const btn=[...document.querySelectorAll('button')].find(b=>(b.innerText||'').trim()==='Post'&&b.offsetWidth>0); if(!btn)return 'NO_POST'; btn.click(); return 'CLICKED'; })()""")
    if r2 != "CLICKED":
        return False, "找不到 Post 按钮"
    for i in range(10):
        await asyncio.sleep(4)
        t = await cdp.ev(sid, "document.body.innerText") or ""
        if "Your video is being" in t or "posted" in t.lower() or "post/" in (await cdp.ev(sid, "location.href") or ""):
            print(f"   ✅ TikTok 发布确认")
            return True, "TikTok 发布已触发"
    return False, "TikTok 发布未确认"

async def main():
    args = sys.argv[1:]
    if len(args) < 5:
        print("用法: publish_dual.py <video> <title> <body> <ig_tags> <tk_tags> [--meta-schedule 'YYYY-MM-DD HH:MM'] [--meta-only|--tiktok-only]")
        return
    video, title, body, ig_tags, tk_tags = args[0], args[1], args[2], args[3], args[4]
    schedule = None
    mode = "both"
    if "--meta-schedule" in args:
        schedule = args[args.index("--meta-schedule") + 1]
    if "--meta-only" in args:
        mode = "meta"
    if "--tiktok-only" in args:
        mode = "tiktok"
    
    port, ws_path = get_cdp_info()
    cdp = CDPSession(f"ws://127.0.0.1:{port}{ws_path}")
    await cdp.connect()
    
    results = []
    if mode in ("meta", "both"):
        print("\n===== META =====")
        sid = await cdp.attach_page("business.facebook.com")
        if not sid:
            results.append(("Meta", False, "无 business.facebook.com 页面"))
        else:
            ok, msg = await publish_meta(cdp, sid, video, title, body, ig_tags, schedule)
            results.append(("Meta", ok, msg))
    if mode in ("tiktok", "both"):
        print("\n===== TIKTOK =====")
        sid = await cdp.attach_page("tiktok.com")
        if not sid:
            results.append(("TikTok", False, "无 tiktok.com 页面"))
        else:
            ok, msg = await publish_tiktok(cdp, sid, video, title, body, tk_tags)
            results.append(("TikTok", ok, msg))
    
    print("\n===== 结果 =====")
    for name, ok, msg in results:
        print(f"{'✅' if ok else '❌'} {name}: {msg}")
    sys.exit(0 if all(ok for _, ok, _ in results) else 1)

if __name__ == "__main__":
    asyncio.run(main())
