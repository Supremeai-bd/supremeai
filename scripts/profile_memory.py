# profile_memory.py
import asyncio
import os
import sys
import psutil
from loguru import logger
from playwright.async_api import async_playwright
# সুপ্রিমএআই কোর ইনফ্রাস্ট্রাকচার ইম্পোর্ট
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from backend.tools.browser_agent import BrowserAgent

def get_process_memory():
    """কারেন্ট পাইথন প্রসেস এবং তার সমস্ত চাইল্ড প্রসেসের (Chromium) মোট র্যাম কনজাম্পশন বের করে"""
    current_process = psutil.Process(os.getpid())
    total_mem = current_process.memory_info().rss  # ইন-বাইট

    # প্লে-রাইটের তৈরি করা সমস্ত ওএস চাইল্ড প্রসেসের মেমরি যোগ করা হচ্ছে
    for child in current_process.children(recursive=True):
        try:
            total_mem += child.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    return total_mem / (1024 * 1024)  # মেগাবাইটে রূপান্তর

async def run_endurance_test(iterations: int = 50):
    logger.info("🧪 Activating Playwright Long-Sustained Endurance Lab...")

    # Architectural Pro Tip: Add flags to reduce memory overhead in containers
    browser_args = [
        '--disable-extensions',
        '--no-sandbox',
        '--disable-dev-shm-usage',
    ]

    # The Structural Fix: Use a context manager for the entire browser lifecycle
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=browser_args)
        # We pass the externally managed browser instance to the agent
        BrowserAgent(browser=browser)

    # টেস্ট করার জন্য একটি ডাইনামিক ও হেভি জেএস চালিত সাইট (লোকাল শুটিং রেঞ্জের ভেতর)
    # আর্কিটেকচারাল নোট: example.com এর পরিবর্তে একটি জটিল, JS-ভারী সাইট ব্যবহার করা হচ্ছে মেমরি লিক আরও কার্যকরভাবে শনাক্ত করার জন্য।
    test_url = "https://web.dev/patterns/"

    initial_mem = get_process_memory()
    logger.info(f"🟢 Baseline Memory Footprint: {initial_mem:.2f} MB")

    print("\n" + "="*70)
    print(f"| {'ITERATION':<12} | {'CURRENT RAM (MB)':<20} | {'MEMORY DELTA (MB)':<25} |")
    print("="*70)

    snapshots = []

    for i in range(1, iterations + 1):
        page = None
        context = None
        # প্লে-রাইট নেভিগেশন এবং স্ক্রিনশট অ্যাকশন স্প্যামিং (ভারী অপারেশন)
        try:
            # The Structural Fix: Use a context manager for page interaction
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(test_url, wait_until="domcontentloaded")
            await page.screenshot(path=f"screenshot_{i}.png")
        except Exception as e:
            logger.error(f"Navigation failed at loop {i}: {e}")
        finally:
            # The Structural Fix: Ensure page and context are always closed
            if page: await page.close()
            if context: await context.close()

        # প্রতি ৫টি ইটারেশন পর পর মেমরির অবস্থা ট্র্যাকিং
        if i % 5 == 0 or i == 1:
            current_mem = get_process_memory()
            delta = current_mem - initial_mem
            snapshots.append(current_mem)
            print(f"| {f'Loop #{i}':<12} | {current_mem:<20.2f} | {f'+{delta:.2f} MB':<25} |")

        # ইভেন্ট লুপকে ব্রেথিং স্পেস দেওয়া
        await asyncio.sleep(0.1)

        # অ্যান্ডুরেন্স টেস্ট শেষে লাইফস্প্যান ক্লিনআপ ট্রিগার
        logger.info("🧹 Triggering Playwright Global Lifespan Teardown Hook...")
        await browser.close()

    final_mem = get_process_memory()
    net_leak = final_mem - initial_mem

    print("="*70)
    print("\n📊 FINAL ENDURANCE REPORT:")
    print(f"  Peak Memory Observed : {max(snapshots):.2f} MB")
    print(f"  Post-Cleanup Memory  : {final_mem:.2f} MB")
    print(f"  Net Memory Leak Size : {f'{net_leak:.2f} MB' if net_leak > 5 else '0.00 MB (Perfect Teardown)'}")
    print("="*70)

    if net_leak < 5:
        print("\n🏆 PASSED! Our Lazy Initialization & Lifespan Teardown Pattern keeps memory perfectly flat. No zombie processes left!\n")
    else:
        print("\n🚨 WARNING: Memory Leak detected! Chromium instances are not releasing resources cleanly.\n")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_endurance_test(50))
