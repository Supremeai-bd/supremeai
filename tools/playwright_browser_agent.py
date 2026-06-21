from __future__ import annotations

from typing import Any, Dict


class PlaywrightBrowserAgent:
    def __init__(self, headless: bool = True, timeout_ms: int = 15000) -> None:
        self.headless = headless
        self.timeout_ms = timeout_ms

    def is_available(self) -> bool:
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
            return True
        except ImportError:
            return False

    def open(self, url: str) -> Dict[str, Any]:
        if not self.is_available():
            raise RuntimeError("playwright is not installed")
        from playwright.sync_api import sync_playwright  # type: ignore
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()
            page.set_default_timeout(self.timeout_ms)
            page.goto(url)
            title = page.title()
            browser.close()
            return {"success": True, "url": url, "title": title}

    def screenshot(self, url: str, path: str = "browser_screenshot.png") -> Dict[str, Any]:
        if not self.is_available():
            raise RuntimeError("playwright is not installed")
        from playwright.sync_api import sync_playwright  # type: ignore
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()
            page.set_default_timeout(self.timeout_ms)
            page.goto(url)
            page.screenshot(path=path, full_page=False)
            browser.close()
            return {"success": True, "path": path}

    def click(self, url: str, selector: str) -> Dict[str, Any]:
        if not self.is_available():
            raise RuntimeError("playwright is not installed")
        from playwright.sync_api import sync_playwright  # type: ignore
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()
            page.set_default_timeout(self.timeout_ms)
            page.goto(url)
            page.click(selector)
            browser.close()
            return {"success": True}

    def text(self, url: str, selector: str) -> Dict[str, Any]:
        if not self.is_available():
            raise RuntimeError("playwright is not installed")
        from playwright.sync_api import sync_playwright  # type: ignore
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()
            page.set_default_timeout(self.timeout_ms)
            page.goto(url)
            content = page.text_content(selector) or ""
            browser.close()
            return {"success": True, "text": content}
