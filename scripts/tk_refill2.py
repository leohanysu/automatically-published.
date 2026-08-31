"""TikTok 重新填文案 v2：清空 -> 标题 -> 逐个标签(等弹窗+回车)。只用 execCommand（Draft.js 兼容）
新规：TikTok 只填标题+标签，不要正文（2026-08-20 用户决定）
"""
import json, time, asyncio, os, sys, base64

def get_cdp_info(profile_id="k1dqriqs", suffix="h1msnw4"):
    port_file = rf"D:\.ADSPOWER_GLOBAL\cache\{profile_id}_{suffix}\DevToolsActivePort"
    with open(port_file) as f:
        port = f.readline().strip()
        ws_path = f.readline().strip()
    return port, ws_path

async def main(cdp_ws, title, tags):
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
        async def key(k, code, modifiers=0, vk=0):
            await send_cmd("Input.dispatchKeyEvent", {"type": "keyDown", "key": k, "code": code, "modifiers": modifiers, "windowsVirtualKeyCode": vk}, sid)
            await send_cmd("Input.dispatchKeyEvent", {"type": "keyUp", "key": k, "code": code, "modifiers": modifiers, "windowsVirtualKeyCode": vk}, sid)
        async def insert_via_exec(text):
            return await ev('''(() => {
                const box = document.querySelector('[contenteditable="true"]');
                if (!box) return 'NO_BOX';
                box.focus();
                const range = document.createRange();
                range.selectNodeContents(box);
                range.collapse(false);
                const sel = window.getSelection();
                sel.removeAllRanges();
                sel.addRange(range);
                const ok = document.execCommand('insertText', false, ''' + json.dumps(text) + ''');
                return 'EXEC=' + ok + ' LEN=' + box.innerText.length;
            })()''')

        # 1. 点击编辑器（确保可见）
        pos_s = await ev('''(() => {
            const box = document.querySelector('[contenteditable="true"]');
            if (!box) return null;
            box.scrollIntoView({block:'center', behavior:'instant'});
            const r = box.getBoundingClientRect();
            return JSON.stringify({x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2)});
        })()''')
        if not pos_s:
            print("❌ 找不到编辑器"); return False
        pos = json.loads(pos_s)
        await real_click(pos["x"], pos["y"])
        await asyncio.sleep(1)
        # 2. 清空（selectAll + delete via execCommand）
        r = await ev('''(() => {
            const box = document.querySelector('[contenteditable="true"]');
            box.focus();
            document.execCommand('selectAll');
            document.execCommand('delete');
            return 'CLEARED LEN=' + box.innerText.length;
        })()''')
        print(f"清空: {r}")
        await asyncio.sleep(0.5)
        # 3. 输入标题（execCommand）
        r = await insert_via_exec(title)
        print(f"标题: {r}")
        await asyncio.sleep(0.5)
        # 4. 逐个标签（execCommand 插入 + 等弹窗 + Enter 确认）
        for i, tag in enumerate(tags):
            tag_clean = tag.lstrip('#').strip()
            print(f"[{i+1}/{len(tags)}] #{tag_clean}")
            await ev('''(() => { document.execCommand('insertText', false, ' '); return true; })()''')
            await asyncio.sleep(0.3)
            for ch in '#' + tag_clean:
                await ev('''(() => { document.execCommand('insertText', false, ''' + json.dumps(ch) + '''); return true; })()''')
                await asyncio.sleep(0.08)
            await asyncio.sleep(2.5)  # 等热度弹窗
            suggest = await ev('''(() => {
                const els = [...document.querySelectorAll('[role="option"], [class*="suggest"]')].filter(e => e.offsetWidth > 0);
                return JSON.stringify(els.map(e => (e.innerText||'').replace(/\\n/g,'|').slice(0,40)).slice(0,2));
            })()''')
            print(f"   弹窗: {suggest}")
            await key("Enter", "Enter", 0, 13)
            await asyncio.sleep(1.2)
        # 5. 最终验证
        ver = await ev('''(() => { const box=document.querySelector('[contenteditable="true"]'); return box ? JSON.stringify({len: box.innerText.length, all: box.innerText}) : 'NO_BOX'; })()''')
        v = json.loads(ver)
        print(f"最终长度: {v['len']}")
        print(f"最终内容: {v['all'][:200]}")
        print(f"尾部: ...{v['all'][-100:]}")
        # 6. 截图
        r = await send_cmd("Page.captureScreenshot", {"format": "png"}, sid)
        b64 = r.get("result", {}).get("data", "")
        open(r"C:\Users\Administrator\Downloads\feishu_videos\tiktok_refill.png", "wb").write(base64.b64decode(b64))
        print("截图 tiktok_refill.png")
        return v["len"] >= 20

if __name__ == "__main__":
    port, ws_path = get_cdp_info()
    title = os.environ["TK_TITLE"]
    tags = json.loads(os.environ["TK_TAGS"])
    ok = asyncio.run(main(f"ws://127.0.0.1:{port}{ws_path}", title, tags))
    sys.exit(0 if ok else 1)
