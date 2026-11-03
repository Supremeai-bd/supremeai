# backend/tests/browser/test_vision_cascade_e2e.py
"""Vision-grounding ক্যাসকেড E2E (আসল chromium) — ৩-স্তর টেস্টিং প্ল্যান Tier-3।

পরিকল্পনার প্রশ্ন: "এজেন্টের চোখ (vision_grounding.py) স্ক্রিনশট ঠিকমতো
ডিটেক্ট করতে পারছে কি না" — আগে শুধু মক-টেস্ট ছিল (কোনো আসল ব্রাউজার নয়)।
এখানে আসল chromium পেজ রেন্ডার হয়, আসল স্ক্রিনশট নেওয়া হয়, শুধু VLM
(router) ফেক — তাই গ্রাউন্ডিং পাইপলাইনের বাকি সব অংশ আসল পথে চলে।

যাচাই:
- আসল স্ক্রিনশট base64 VLM prompt-এ পৌঁছেছে (len > 0);
- execute-band (≥0.85) কনফিডেন্সে সঠিক কোঅর্ডিনেট ফেরে;
- VLM বিকল হলে LowConfidenceGrounding — কোনো fabricated coordinate নয়;
- নিম্ন কনফিডেন্সে HITL ব্যান্ড (LowConfidenceGrounding)।
"""

from __future__ import annotations

from typing import Any

import pytest

try:
    from vision_grounding import LowConfidenceGrounding, VisionGrounding
except ImportError:
    from browser.vision_grounding import LowConfidenceGrounding, VisionGrounding

pytestmark = pytest.mark.e2e


class _FakeVLMRouter:
    """VLM প্রতিস্থাপন — prompt ক্যাপচার করে, কনফিগারযোগ্য রেসপন্স দেয়।"""

    def __init__(self, text: str) -> None:
        self.text = text
        self.prompts: list[str] = []

    def route_and_generate(self, prompt: str, **_kwargs: Any) -> dict[str, Any]:
        self.prompts.append(prompt)
        return {"text": self.text, "model": "fake-vlm", "cost": 0.0}


class TestVisionGroundingWithRealBrowser:
    async def test_real_screenshot_flows_into_vlm_prompt(self):
        """Given: আসল chromium পেজ (একটি বোতামসহ) + execute-band VLM রেসপন্স।
        When: locate() চালানো হলে।
        Then: VLM-এর প্রম্পটে আসল স্ক্রিনশটের দৈর্ঘ্য (len>0) এসেছে এবং
        সঠিক কোঅর্ডিনেট+ব্যান্ড ফেরত এসেছে।
        """
        from core.playwright_manager import get_global_browser, shutdown_global_browser

        browser = await get_global_browser()
        try:
            context = await browser.new_context(viewport={"width": 800, "height": 600})
            page = await context.new_page()
            await page.set_content(
                "<html><body style='margin:0'>"
                "<button id='target' style='position:absolute;left:200px;top:150px;"
                "width:120px;height:40px'>Login</button>"
                "</body></html>"
            )
            router = _FakeVLMRouter('{"x": 260, "y": 170, "confidence": 0.92}')
            grounding = VisionGrounding(page=page, router_factory=lambda: router)

            loc = await grounding.locate("Login button")

            assert loc["x"] == 260
            assert loc["y"] == 170
            assert loc["confidence"] == pytest.approx(0.92)
            assert loc["band"] == "execute", f"প্রত্যাশিত execute ব্যান্ড: {loc['band']}"
            # আসল স্ক্রিনশট প্রম্পটে পৌঁছেছে কি না — "len=<N>" ফ্র্যাগমেন্ট খোঁজা
            assert any("len=" in p and "len=0)" not in p for p in router.prompts), (
                "VLM প্রম্পটে স্ক্রিনশট পৌঁছায়নি — আসল রেন্ডার-পথ অতিক্রম হয়নি"
            )
            await context.close()
        finally:
            await shutdown_global_browser()

    async def test_vlm_garbage_never_fabricates_coordinates(self):
        """Given: VLM আসল ব্রাউজার থেকে স্ক্রিনশট পেয়েও garbage টেক্সট ফেরায়।
        When: locate() চালানো হলে।
        Then: LowConfidenceGrounding — কখনোই বানানো কোঅর্ডিনেট নয়
        (blind-fallback-click দুর্ঘটনা রোধ, ISSUE-1570)।
        """
        from core.playwright_manager import get_global_browser, shutdown_global_browser

        browser = await get_global_browser()
        try:
            context = await browser.new_context(viewport={"width": 800, "height": 600})
            page = await context.new_page()
            await page.set_content("<button id='b'>Pay now</button>")
            router = _FakeVLMRouter("totally not json at all {{{")
            grounding = VisionGrounding(page=page, router_factory=lambda: router)

            with pytest.raises(LowConfidenceGrounding):
                await grounding.locate("Pay now button")
            await context.close()
        finally:
            await shutdown_global_browser()

    async def test_low_confidence_goes_to_hitl_not_click(self):
        """Given: VLM কনফিডেন্স 0.4 (< HITL থ্রেশহোল্ড)।
        When: locate() চালানো হলে।
        Then: LowConfidenceGrounding — মানুষের হাতে যায়, অনুমানে ক্লিক নয়।
        """
        from core.playwright_manager import get_global_browser, shutdown_global_browser

        browser = await get_global_browser()
        try:
            context = await browser.new_context(viewport={"width": 800, "height": 600})
            page = await context.new_page()
            await page.set_content("<button id='b'>Delete everything</button>")
            router = _FakeVLMRouter('{"x": 100, "y": 100, "confidence": 0.4}')
            grounding = VisionGrounding(page=page, router_factory=lambda: router)

            with pytest.raises(LowConfidenceGrounding, match="confidence|Visual"):
                await grounding.locate("Delete button")
            await context.close()
        finally:
            await shutdown_global_browser()
