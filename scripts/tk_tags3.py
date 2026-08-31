"""TikTok 标签 v3：逐字符 execCommand 输入 -> 等热度弹窗 -> 回车确认（严格按用户要求）"""
import json, time, asyncio, os, sys

def get_cdp_info(profile_id="k1dqriqs", suffix="h1msnw4"):
    port_file = rf"D:\.ADSPOWER_GLOBAL\cache\{profile_id}_{suffix}\DevToolsActivePort"
    with open(port_file) as f:
        port = f.readline().strip()
        ws_path = f.readline().strip()
    return port, ws_path

async def main(cdp_ws, tags):
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

        # 1. 聚焦编辑器，光标到末尾，删除 #testtag 残留（如果有）
        r = await ev('''(() => {
            const box = document.querySelector('[contenteditable="true"]');
            if (!box) return 'NO_BOX';
            box.focus();
            // 删除末尾的 #testtag (8字符) 如果存在
            let t = box.innerText;
            if (t.trimEnd().endsWith('#testtag')) {
                const range = document.createRange();
                range.selectNodeContents(box);
                range.collapse(false);
                const sel = window.getSelection();
                sel.removeAllRanges();
                sel.addRange(range);
                for (let i=0; i<9; i++) document.execCommand('delete');
            }
            return 'LEN=' + box.innerText.length + ' TAIL=' + box.innerText.slice(-15);
        })()''')
        print(f"清理: {r}")

        # 2. 逐个标签输入
        for i, tag in enumerate(tags):
            tag_clean = tag.lstrip('#').strip()
            print(f"[{i+1}/{len(tags)}] #{tag_clean}")
            # 先插一个空格（和前文分隔）
            await ev('''(() => { document.execCommand('insertText', false, ' '); return true; })()''')
            await asyncio.sleep(0.2)
            # 逐字符输入 #tag
            for ch in '#' + tag_clean:
                await ev('''(() => { document.execCommand('insertText', false, ''' + json.dumps(ch) + '''); return true; })()''')
                await asyncio.sleep(0.15)
            await asyncio.sleep(2.5)  # 等热度弹窗
            # 检查是否有标签建议弹窗出现
            suggest = await ev('''(() => {
                const els = [...document.querySelectorAll('[role="option"], [class*="suggest"]')].filter(e => e.offsetWidth > 0);
                const txt = els.map(e => (e.innerText||'').replace(/\\n/g,'|').slice(0,50));
                return JSON.stringify(txt.slice(0,3));
            })()''')
            print(f"   弹窗: {suggest}")
            # 按回车确认标签
            await key("Enter", "Enter")
            await asyncio.sleep(1.2)
            # 验证
            tail = await ev('''(() => { const box=document.querySelector('[contenteditable="true"]'); return box ? box.innerText.slice(-25) : 'NO'; })()''')
            print(f"   末尾: {repr(tail)}")
        return True

if __name__ == "__main__":
    port, ws_path = get_cdp_info()
    tags = json.loads(os.environ["TK_TAGS"])
    ok = asyncio.run(main(f"ws://127.0.0.1:{port}{ws_path}", tags))
    sys.exit(0 if ok else 1)
