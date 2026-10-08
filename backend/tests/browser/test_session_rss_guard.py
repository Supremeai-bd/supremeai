# backend/tests/browser/test_session_rss_guard.py
"""সেশন-ক্লোজের পরে মেমরি-লিক/OOM গার্ড — ৩-স্তর টেস্টিং প্ল্যান Tier-3।

পরিকল্পনার প্রশ্ন: "ব্রাউজার সেশন শেষ হওয়ার পর মেমোরি সম্পূর্ণ খালি হচ্ছে
কি না" — আসল chromium দিয়ে যাচাই:
- shutdown_global_browser()-এর পরে কোনো chromium/chrome কিল্ড-প্রসেস বাঁচে না;
- প্রধান প্রসেসের RSS বেসলাইনে ফেরত যায় (যুক্তিসঙ্গত slack সহ)।

`e2e` marker — PR-CI deselect করে; nightly e2e job (browser deps সহ) চালায়।
playwright import লেজি (ফাংশনের ভেতরে) যাতে playwright-বিহীন পরিবেশে
collection না ভাঙে।
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e

_RSS_SLACK_MB = 48.0  # chromium shutdown-পরবর্তী যুক্তিসঙ্গত slack


def _chromium_descendants() -> list:
    """এই প্রসেসের সন্তানদের মধ্যে chromium/chrome নামযুক্ত প্রসেস।"""
    import psutil

    try:
        me = psutil.Process()
        names = []
        for child in me.children(recursive=True):
            try:
                names.append(child.name().lower())
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return [n for n in names if "chrom" in n or "headless" in n]
    except Exception:
        return []


class TestBrowserShutdownMemoryGuard:
    async def test_shutdown_leaves_no_chromium_orphans_and_rss_returns(self):
        """Given: আসল chromium + কয়েকটি পেজ-সেশন।
        When: সব সেশন বন্ধ + shutdown_global_browser() চালালে।
        Then: (ক) কোনো chromium descendant-প্রসেস বাঁচে না;
              (খ) প্রধান প্রসেসের RSS বেসলাইন+slack-এর মধ্যে ফেরে।
        """
        import psutil

        from core.playwright_manager import (
            get_global_browser,
            shutdown_global_browser,
        )

        before_rss = psutil.Process().memory_info().rss

        browser = await get_global_browser()
        contexts = []
        for _ in range(3):
            context = await browser.new_context(viewport={"width": 1280, "height": 800})
            page = await context.new_page()
            await page.set_content(
                "<button id='b'>ok</button><p>" + "x" * 5000 + "</p>"
            )
            contexts.append(context)

        assert _chromium_descendants(), "chromium প্রসেসই চালু হয়নি — পরীক্ষার পূর্বশর্ত ভাঙছে"

        for context in contexts:
            await context.close()
        await shutdown_global_browser()

        # (ক) orphan প্রসেস গার্ড — কিছুক্ষণ অপেক্ষা করে যাচাই (cleanup অ্যাসিনক্রোনাস হতে পারে)
        import asyncio

        for _ in range(10):
            if not _chromium_descendants():
                break
            await asyncio.sleep(0.5)
        assert not _chromium_descendants(), (
            "shutdown-এর পরেও chromium প্রসেস বেঁচে আছে — মেমরি লিক!"
        )

        # (খ) RSS ফেরত — slack সহ (allocator ক্যাশে পুরোপুরি ছাড়ে না)
        import gc

        gc.collect()
        after_rss = psutil.Process().memory_info().rss
        growth_mb = (after_rss - before_rss) / (1024 * 1024)
        assert growth_mb <= _RSS_SLACK_MB, (
            f"RSS বেসলাইনে ফেরেনি (+{growth_mb:.1f} MB > {_RSS_SLACK_MB} MB slack) — মেমরি লিকের সন্দেহ"
        )

    async def test_relaunch_after_shutdown_works_cleanly(self):
        """Given: একবার ব্রাউজার চালু→বন্ধ করা হয়েছে।
        When: আবার চালু করলে।
        Then: নতুন ইনস্ট্যান্স কাজ করে — shutdown-পরবর্তী পুনরায় চালু নষ্ট নয়।
        """
        from core.playwright_manager import (
            get_global_browser,
            shutdown_global_browser,
        )

        browser = await get_global_browser()
        assert browser is not None
        await shutdown_global_browser()

        browser2 = await get_global_browser()
        try:
            page = await browser2.new_page()
            await page.set_content("<h1>relaunched</h1>")
            title = await page.title()  # শুধু ইন্টারঅ্যাকশন সফলতা যাচাই
            assert isinstance(title, str)
        finally:
            await shutdown_global_browser()
