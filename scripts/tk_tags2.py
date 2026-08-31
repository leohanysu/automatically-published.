"""TikTok 标签 v2：execCommand 光标末尾插入 #tag -> 等弹窗 -> 回车 -> 验证（先做1个）"""
import json, time, asyncio, os, sys

def get_cdp_info(profile_id="k1dqriqs", suffix="h1msnw4"):
    port_file = rf"D:\.ADSPOWER_GLOBAL\cache\{profile_id}_{suffix}\DevToolsActivePort"
    with open(port_file) as f:
        port = f.readline().strip()
        ws_path = f.readline().strip()
    return port, ws_path

async def main(cdp_ws, tag):
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
        async def key(k, code, modifiers=0):
            await send_cmd("Input.dispatchKeyEvent", {"type": "keyDown", "key": k, "code": code, "modifiers": modifiers}, sid)
            await send_cmd("Input.dispatchKeyEvent", {"type": "keyUp", "key": k, "code": code, "modifiers": modifiers}, sid)

        # 1. 用 JS 设置光标到末尾 + execCommand 插入（Draft.js 兼容）
        r = await ev('''(() => {
            const box = document.querySelector('[contenteditable="true"]');
            if (!box) return 'NO_BOX';
            box.focus();
            const range = document.createRange();
            range.selectNodeContents(box);
            range.collapse(false);
            const sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(range);
            const ok = document.execCommand('insertText', false, ' ''' + tag.lstrip('#') + ''');
            return 'EXEC=' + ok + ' LEN=' + box.innerText.length;
        })()''')
        print(f"插入: {r}")
        await asyncio.sleep(2.5)
        # 2. 检查弹窗（标签建议/热度）
        suggest = await ev('''(() => {
            const els = [...document.querySelectorAll('[class*="suggest"], [role="listbox"], [role="option"], [class*="hashtag"]')].filter(e => e.offsetWidth > 0);
            return JSON.stringify(els.slice(0,3).map(e => (e.innerText||'').replace(/\\n/g,'|').slice(0,60)));
        })()''')
        print(f"弹窗: {suggest}")
        # 3. 按回车确认
        await key("Enter", "Enter")
        await asyncio.sleep(1.5)
        # 4. 验证
        tail = await ev('''(() => { const box=document.querySelector('[contenteditable="true"]'); return box ? box.innerText.slice(-40) : 'NO'; })()''')
        print(f"末尾: {repr(tail)}")
        return True

if __name__ == "__main__":
    port, ws_path = get_cdp_info()
    tag = os.environ["TK_TAG"]
    ok = asyncio.run(main(f"ws://127.0.0.1:{port}{ws_path}", tag))
    sys.exit(0 if ok else 1)
