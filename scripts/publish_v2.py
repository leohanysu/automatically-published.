import asyncio, sys, traceback
from playwright.async_api import async_playwright

VIDEO_PATH = r"C:\Users\Administrator\Downloads\feishu_videos\8e4cbc7ef635812f05bec4b59753dd51_raw.mp4"
CDP_PORT = 52841
CAPTION = "This vacuum rolled sofa pops right open, no assembly required.\n\n#Squishy #FidgetToys #StressRelief #DeskAccessories #DIY"
META_URL = "https://business.facebook.com/latest/reels_composer/?asset_id=1289480590904839&business_id=1364096915701521"

async def main():
    with open(r"C:\Users\Administrator\Downloads\feishu_videos\publish_log.txt", "w") as log:
        try:
            log.write("Connecting CDP...\n")
            log.flush()
            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
                contexts = browser.contexts
                page = await contexts[0].new_page()
                
                log.write("Navigating to Meta...\n"); log.flush()
                await page.goto(META_URL, timeout=30000)
                await page.wait_for_timeout(3000)
                
                log.write("Uploading video...\n"); log.flush()
                async with page.expect_file_chooser(timeout=15000) as fc_info:
                    btn = page.locator('text="添加视频"').first
                    await btn.click()
                fc = await fc_info.value
                await fc.set_files(VIDEO_PATH)
                await page.wait_for_timeout(10000)
                
                log.write("Filling caption...\n"); log.flush()
                box = page.locator('[aria-label*="对话框中输入"]').first
                await box.wait_for(state="visible", timeout=15000)
                await box.click()
                await box.fill(CAPTION)
                await page.wait_for_timeout(2000)
                
                log.write("Clicking next...\n"); log.flush()
                await page.evaluate("""() => {
                    const btns = document.querySelectorAll('button, [role="button"]');
                    for (const b of btns) {
                        if ((b.textContent || '').includes('下一页')) { b.click(); return 'ok'; }
                    }
                    return 'no';
                }""")
                await page.wait_for_timeout(5000)
                
                log.write("Clicking share...\n"); log.flush()
                await page.evaluate("""() => {
                    const btns = [...document.querySelectorAll('button, [role="button"]')];
                    const share = btns.filter(b => (b.textContent||'').trim()==='分享');
                    if (share.length>=2) { share[share.length-1].click(); return 'ok'; }
                    return 'no';
                }""")
                await page.wait_for_timeout(8000)
                
                processing = await page.locator('text="正在处理"').count()
                log.write(f"DONE processing={processing>0}\n"); log.flush()
                await page.close()
        except Exception as e:
            log.write(f"ERROR: {traceback.format_exc()}\n"); log.flush()

asyncio.run(main())
print("Script finished")
