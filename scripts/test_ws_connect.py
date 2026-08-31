"""测试 Playwright 用 ws:// 直连 AdsPower CDP"""
import asyncio, sys

async def main():
    from playwright.async_api import async_playwright
    ws_url = "ws://127.0.0.1:56951/devtools/browser/62f52ba5-07f8-4254-be2f-3e5db2d26f50"
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp(ws_url, timeout=20000)
            print("✅ 连接成功!")
            ctxs = browser.contexts
            print(f"contexts: {len(ctxs)}")
            for ctx in ctxs:
                print(f"  pages: {[pg.url[:60] for pg in ctx.pages]}")
            await browser.close()
        except Exception as e:
            print(f"❌ 失败: {type(e).__name__}: {str(e)[:200]}")

asyncio.run(main())
