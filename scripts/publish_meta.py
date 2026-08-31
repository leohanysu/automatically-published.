import asyncio
from playwright.async_api import async_playwright

VIDEO_PATH = r"C:\Users\Administrator\Downloads\feishu_videos\8e4cbc7ef635812f05bec4b59753dd51_raw.mp4"
CDP_PORT = 52841
CAPTION = "This vacuum rolled sofa pops right open, no assembly required.\n\n#Squishy #FidgetToys #StressRelief #DeskAccessories #DIY"
META_URL = "https://business.facebook.com/latest/reels_composer/?asset_id=1289480590904839&business_id=1364096915701521"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
        contexts = browser.contexts
        if not contexts:
            print("ERROR: No browser contexts found")
            return
        context = contexts[0]
        page = await context.new_page()
        
        try:
            print("1. Navigating to Meta Reels composer...")
            await page.goto(META_URL, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)
            
            print("2. Uploading video...")
            async with page.expect_file_chooser(timeout=15000) as fc:
                add_video_btn = page.locator('text="添加视频"').first
                await add_video_btn.click()
            file_chooser = await fc.value
            await file_chooser.set_files(VIDEO_PATH)
            print("   Video upload triggered")
            await page.wait_for_timeout(8000)
            
            print("3. Filling caption...")
            caption_box = page.locator('[aria-label*="对话框中输入"]').first
            await caption_box.wait_for(state="visible", timeout=15000)
            await caption_box.click()
            await caption_box.fill(CAPTION)
            print("   Caption filled")
            await page.wait_for_timeout(2000)
            
            print("4. Clicking next...")
            await page.evaluate("""() => {
                const buttons = document.querySelectorAll('button, [role="button"]');
                for (const btn of buttons) {
                    if ((btn.textContent || '').includes('下一页')) {
                        btn.click();
                        return true;
                    }
                }
                return false;
            }""")
            await page.wait_for_timeout(5000)
            
            print("5. Clicking publish...")
            await page.evaluate("""() => {
                const btns = [...document.querySelectorAll('button, [role="button"]')];
                const shareBtns = btns.filter(b => (b.textContent || '').trim() === '分享');
                if (shareBtns.length >= 2) {
                    shareBtns[shareBtns.length - 1].click();
                    return 'clicked share';
                }
                for (const b of btns) {
                    if ((b.textContent || '').includes('publish') || (b.textContent || '').includes('Publish')) {
                        b.click();
                        return 'clicked publish';
                    }
                }
                return 'no button found';
            }""")
            await page.wait_for_timeout(8000)
            
            processing = await page.locator('text="正在处理"').count()
            print(f"   Processing indicator: {processing > 0}")
            print("\n✅ Done! Check Meta Business Suite")

        except Exception as e:
            print(f"ERROR: {e}")
        finally:
            await page.close()

asyncio.run(main())
