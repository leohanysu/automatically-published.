"""Meta 发布第四条：Playwright connect_over_cdp + CDPSession DOM.setFileInputFiles 上传
流程：上传视频 -> 真实点击文案框 + insertText -> 下一页 -> 立即分享 -> 分享
"""
import json, time, sys, re, asyncio

def get_cdp_info(profile_id="k1dqriqs", suffix="h1msnw4"):
    port_file = rf"D:\.ADSPOWER_GLOBAL\cache\{profile_id}_{suffix}\DevToolsActivePort"
    with open(port_file) as f:
        port = f.readline().strip()
        ws_path = f.readline().strip()
    return port, ws_path

async def main(video, title, body, tags, port, ws_path):
    from playwright.async_api import async_playwright
    full = f"{title}\n\n{body}\n\n{tags}"
    async with async_playwright() as p:
        # ⛔ 必须用 ws:// 连接（AdsPower 新版本 http:// 返回 503，2026-08-20 实测）
        browser = await p.chromium.connect_over_cdp(f"ws://127.0.0.1:{port}{ws_path}")
        context = browser.contexts[0]
        # 找 business.facebook.com 页面
        meta_page = None
        for pg in context.pages:
            if "business.facebook.com" in pg.url:
                meta_page = pg
                break
        if not meta_page:
            print("❌ 无 Meta 页面")
            return False
        # 确保 composer
        if "reels_composer" not in meta_page.url:
            await meta_page.goto("https://business.facebook.com/latest/reels_composer/?asset_id=890016627535163&business_id=3521484561351336", wait_until="domcontentloaded", timeout=40000)
            await asyncio.sleep(8)
        print(f"页面: {meta_page.url[:80]}")

        # 1. 上传视频：点击「添加视频」+ file_chooser（Playwright 原生，CDP 直连无 50MB 限制）
        cdp = await context.new_cdp_session(meta_page)
        await cdp.send("DOM.enable")
        await asyncio.sleep(2)
        async with meta_page.expect_file_chooser(timeout=15000) as fc_info:
            # ⛔ 必须用 Playwright 原生 click（JS dispatchEvent 不触发 file chooser 拦截）
            clicked = await meta_page.evaluate("""(() => {
                const els=[...document.querySelectorAll('div,span,button')];
                const b=els.find(el=>el.textContent.trim()==='添加视频'&&el.getBoundingClientRect().width>50);
                if(!b) return null;
                const r=b.getBoundingClientRect();
                return {x: Math.round(r.x+r.width/2), y: Math.round(r.y+r.height/2)};
            })()""")
            if not clicked:
                print("❌ 找不到添加视频按钮")
                return False
            await meta_page.mouse.move(clicked["x"], clicked["y"])
            await meta_page.mouse.down()
            await meta_page.mouse.up()
            print(f"真实点击添加视频 ({clicked['x']},{clicked['y']})")
        fc = await fc_info.value
        await fc.set_files(video)
        print("✅ 视频已设置 (file_chooser)")
        # 2. 等上传完成
        for i in range(50):
            await asyncio.sleep(6)
            t = await meta_page.evaluate("document.body.innerText") or ""
            m = re.search(r"(\d+)%", t)
            pct = m.group(1) if m else "?"
            if "100%" in t and "删除" in t:
                print(f"✅ 上传完成")
                break
            if i % 2 == 0:
                print(f"   上传 {pct}%...")
        # 3. 填文案（真实点击 + insertText）
        await asyncio.sleep(2)
        pos = await meta_page.evaluate("""(() => {
            const b = document.querySelector('div[aria-label*="在对话框中输入"]');
            if(!b) return null;
            b.scrollIntoView({block:'center'});
            const r = b.getBoundingClientRect();
            return {x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2)};
        })()""")
        if not pos:
            print("❌ 找不到文案框")
            return False
        await meta_page.mouse.move(pos["x"], pos["y"])
        await meta_page.mouse.down()
        await meta_page.mouse.up()
        await asyncio.sleep(1)
        await meta_page.keyboard.insert_text(full)
        await asyncio.sleep(2)
        ver = await meta_page.evaluate("""(() => {
            const b = document.querySelector('div[aria-label*="在对话框中输入"]');
            return b ? b.innerText.length : -1;
        })()""")
        print(f"文案: {ver} 字符")
        if not ver or ver < 100:
            print("❌ 文案填充异常")
            return False
        await asyncio.sleep(3)
        ver2 = await meta_page.evaluate("""(() => {
            const b = document.querySelector('div[aria-label*="在对话框中输入"]');
            return b ? b.innerText.length : -1;
        })()""")
        print(f"3秒复查: {ver2}")
        if ver2 < 100:
            print("❌ 文案丢失")
            return False
        # 4. 下一页
        for step in range(5):
            nxt = await meta_page.evaluate("""(() => {
                let a=[...document.querySelectorAll('button,[role=button]')].filter(b=>(b.textContent||'').includes('下一页'));
                if(a.length){a[a.length-1].click(); return a.length;}
                return 0;
            })()""")
            print(f"下一页: {nxt}")
            await asyncio.sleep(4)
            t = await meta_page.evaluate("document.body.innerText") or ""
            has_share = await meta_page.evaluate("""[...document.querySelectorAll('button,[role=button]')].some(b=>(b.textContent||'').trim()==='分享')""")
            if "正在处理" in t:
                print("✅ 已发布(处理中)")
                return True
            if has_share:
                break
        # 5. 立即分享 + 分享（真实点击）
        pos = await meta_page.evaluate("""(() => {
            const els=[...document.querySelectorAll('div,span,button,[role=radio]')];
            const t=els.find(el=>(el.textContent||'').trim()==='立即分享');
            if(!t) return null;
            const r=t.getBoundingClientRect();
            return {x: Math.round(r.x+r.width/2), y: Math.round(r.y+r.height/2)};
        })()""")
        if pos:
            await meta_page.mouse.move(pos["x"], pos["y"])
            await meta_page.mouse.down()
            await meta_page.mouse.up()
            print("点击立即分享")
            await asyncio.sleep(2)
        # 分享（最后一个）
        pos = await meta_page.evaluate("""(() => {
            const els=[...document.querySelectorAll('button,[role=button]')].filter(b=>(b.textContent||'').trim()==='分享'&&b.getBoundingClientRect().width>50);
            if(!els.length) return null;
            const b=els[els.length-1];
            const r=b.getBoundingClientRect();
            return {x: Math.round(r.x+r.width/2), y: Math.round(r.y+r.height/2)};
        })()""")
        if not pos:
            print("❌ 无分享按钮")
            return False
        await meta_page.mouse.move(pos["x"], pos["y"])
        await meta_page.mouse.down()
        await meta_page.mouse.up()
        print("点击分享")
        await asyncio.sleep(10)
        t2 = await meta_page.evaluate("document.body.innerText") or ""
        ok = "正在处理" in t2 or "已发布" in t2
        print(f"结果: {'✅ 发布已触发!' if ok else '⚠️ 请检查页面'}")
        return ok

if __name__ == "__main__":
    video, title, body, tags = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    port, ws_path = get_cdp_info()
    print(f"CDP: ws://127.0.0.1:{port}{ws_path[:40]}")
    ok = asyncio.run(main(video, title, body, tags, port, ws_path))
    sys.exit(0 if ok else 1)
