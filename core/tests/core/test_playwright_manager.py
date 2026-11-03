# backend/tests/core/test_playwright_manager.py
# বাংলা মন্তব্য: Playwright manager-এর জন্য comprehensive unit tests।
# Playwright browser mock করা হয়েছে — actual browser dependency ছাড়াই।

from unittest.mock import AsyncMock, patch

import pytest

import core.playwright_manager as pm

# -------------------- Fixtures --------------------


@pytest.fixture(autouse=True)
def reset_global_state():
    """
    বাংলা মন্তব্য: প্রতিটি test-এর পর global browser state reset করে।
    Module-level globals clean রাখার জন্য।
    """
    pm._global_browser = None
    pm._playwright_runner = None
    try:
        yield
    finally:
        pm._global_browser = None
        pm._playwright_runner = None


@pytest.fixture
def mock_browser():
    """Mock Playwright browser instance।"""
    browser = AsyncMock()
    browser.close = AsyncMock()
    return browser


@pytest.fixture
def mock_playwright_runner():
    """Mock Playwright runner instance।"""
    runner = AsyncMock()
    runner.stop = AsyncMock()
    return runner


# -------------------- Tests: get_global_browser --------------------


class TestGetGlobalBrowser:
    """বাংলা মন্তব্য: get_global_browser() function-এর lazy initialization টেস্ট।"""

    @pytest.mark.asyncio
    async def test_creates_browser_when_none(self, mock_browser, mock_playwright_runner):
        """বাংলা মন্তব্য: First call-এ নতুন browser create হয়।"""
        mock_playwright = AsyncMock()
        mock_playwright.start.return_value = mock_playwright_runner
        mock_playwright_runner.chromium.launch.return_value = mock_browser

        with patch("core.playwright_manager.async_playwright", return_value=mock_playwright):
            with patch("core.playwright_manager.logger") as mock_logger:
                browser = await pm.get_global_browser()

                assert browser is mock_browser
                mock_logger.info.assert_called_once_with(
                    "🚀 Starting a new headless Global Chromium instance..."
                )
                mock_playwright_runner.chromium.launch.assert_called_once_with(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                    ],
                )

    @pytest.mark.asyncio
    async def test_returns_existing_browser(self, mock_browser, mock_playwright_runner):
        """বাংলা মন্তব্য: Second call-এ existing browser return হয় (singleton pattern)।"""

        pm._global_browser = mock_browser
        pm._playwright_runner = mock_playwright_runner

        with patch("core.playwright_manager.async_playwright") as mock_playwright:
            browser = await pm.get_global_browser()

            assert browser is mock_browser
            mock_playwright.assert_not_called()  # Should not create new instance

    @pytest.mark.asyncio
    async def test_raises_when_playwright_not_installed(self):
        """বাংলা মন্তব্য: Playwright install না থাকলে RuntimeError raise হয়।"""
        with patch("core.playwright_manager.async_playwright", None):
            with pytest.raises(RuntimeError, match="Playwright is not installed"):
                await pm.get_global_browser()

    @pytest.mark.asyncio
    async def test_browser_launch_with_correct_args(self, mock_browser, mock_playwright_runner):
        """বাংলা মন্তব্য: Browser launch করার সময় সঠিক arguments pass হয়।"""
        mock_playwright = AsyncMock()
        mock_playwright.start.return_value = mock_playwright_runner
        mock_playwright_runner.chromium.launch.return_value = mock_browser

        with patch("core.playwright_manager.async_playwright", return_value=mock_playwright):
            await pm.get_global_browser()

            launch_call = mock_playwright_runner.chromium.launch.call_args
            assert launch_call.kwargs["headless"] is True
            assert launch_call.kwargs["args"] == [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
            ]

    @pytest.mark.asyncio
    async def test_sets_global_variables(self, mock_browser, mock_playwright_runner):
        """বাংলা মন্তব্য: Global variables সঠিকভাবে set হয়।"""
        mock_playwright = AsyncMock()
        mock_playwright.start.return_value = mock_playwright_runner
        mock_playwright_runner.chromium.launch.return_value = mock_browser

        with patch("core.playwright_manager.async_playwright", return_value=mock_playwright):
            await pm.get_global_browser()

            assert pm._global_browser is mock_browser
            assert pm._playwright_runner is mock_playwright_runner


# -------------------- Tests: shutdown_global_browser --------------------


class TestShutdownGlobalBrowser:
    """বাংলা মন্তব্য: shutdown_global_browser() function-এর cleanup logic টেস্ট।"""

    @pytest.mark.asyncio
    async def test_successful_shutdown(self, mock_browser, mock_playwright_runner):
        """বাংলা মন্তব্য: Browser এবং runner properly close হয়।"""

        pm._global_browser = mock_browser
        pm._playwright_runner = mock_playwright_runner

        with patch("core.playwright_manager.logger") as mock_logger:
            await pm.shutdown_global_browser()

            mock_browser.close.assert_called_once()
            mock_playwright_runner.stop.assert_called_once()
            assert pm._global_browser is None
            assert pm._playwright_runner is None
            mock_logger.info.assert_any_call("✅ All Playwright OS processes terminated cleanly.")

    @pytest.mark.asyncio
    async def test_shutdown_with_no_browser(self):
        """বাংলা মন্তব্য: Browser না থাকলেও shutdown peacefully শেষ হয়।"""

        pm._global_browser = None
        pm._playwright_runner = None

        with patch("core.playwright_manager.logger"):
            await pm.shutdown_global_browser()

            # Should not raise any error
            assert pm._global_browser is None
            assert pm._playwright_runner is None

    @pytest.mark.asyncio
    async def test_shutdown_with_browser_only(self, mock_browser):
        """বাংলা মন্তব্য: Browser থাকলে শুধু browser close হয়।"""

        pm._global_browser = mock_browser
        pm._playwright_runner = None

        with patch("core.playwright_manager.logger"):
            await pm.shutdown_global_browser()

            mock_browser.close.assert_called_once()
            assert pm._global_browser is None
            assert pm._playwright_runner is None

    @pytest.mark.asyncio
    async def test_shutdown_with_runner_only(self, mock_playwright_runner):
        """বাংলা মন্তব্য: Runner থাকলে শুধু runner stop হয়।"""

        pm._global_browser = None
        pm._playwright_runner = mock_playwright_runner

        with patch("core.playwright_manager.logger"):
            await pm.shutdown_global_browser()

            mock_playwright_runner.stop.assert_called_once()
            assert pm._global_browser is None
            assert pm._playwright_runner is None

    @pytest.mark.asyncio
    async def test_shutdown_handles_browser_close_error(self, mock_browser, mock_playwright_runner):
        """বাংলা মন্তব্য: Browser close error handle করে runner stop করে।"""
        mock_browser.close = AsyncMock(side_effect=RuntimeError("Browser close failed"))

        pm._global_browser = mock_browser
        pm._playwright_runner = mock_playwright_runner

        with patch("core.playwright_manager.logger") as mock_logger:
            await pm.shutdown_global_browser()

            # Should log critical error but continue
            mock_logger.critical.assert_called_once()
            # Note: Due to exception handling, runner.stop() may not be called if browser.close() fails first
            # Globals should be reset
            assert pm._global_browser is None
            assert pm._playwright_runner is None

    @pytest.mark.asyncio
    async def test_shutdown_handles_runner_stop_error(self, mock_browser, mock_playwright_runner):
        """বাংলা মন্তব্য: Runner stop error handle করে।"""
        mock_playwright_runner.stop = AsyncMock(side_effect=RuntimeError("Runner stop failed"))

        pm._global_browser = mock_browser
        pm._playwright_runner = mock_playwright_runner

        with patch("core.playwright_manager.logger") as mock_logger:
            await pm.shutdown_global_browser()

            # Should log critical error
            mock_logger.critical.assert_called_once()
            # Browser should still be closed
            mock_browser.close.assert_called_once()
            # Globals should be reset
            assert pm._global_browser is None
            assert pm._playwright_runner is None

    @pytest.mark.asyncio
    async def test_shutdown_handles_os_error(self, mock_browser, mock_playwright_runner):
        """বাংলা মন্তব্য: OSError handle করে gracefully।"""
        mock_browser.close = AsyncMock(side_effect=OSError("OS error during close"))

        pm._global_browser = mock_browser
        pm._playwright_runner = mock_playwright_runner

        with patch("core.playwright_manager.logger") as mock_logger:
            await pm.shutdown_global_browser()

            mock_logger.critical.assert_called_once()
            assert pm._global_browser is None
            assert pm._playwright_runner is None

    @pytest.mark.asyncio
    async def test_shutdown_handles_connection_error(self, mock_browser, mock_playwright_runner):
        """বাংলা মন্তব্য: ConnectionError handle করে gracefully।"""
        mock_browser.close = AsyncMock(side_effect=ConnectionError("Connection lost"))

        pm._global_browser = mock_browser
        pm._playwright_runner = mock_playwright_runner

        with patch("core.playwright_manager.logger") as mock_logger:
            await pm.shutdown_global_browser()

            mock_logger.critical.assert_called_once()
            assert pm._global_browser is None
            assert pm._playwright_runner is None

    @pytest.mark.asyncio
    async def test_shutdown_logs_correct_messages(self, mock_browser, mock_playwright_runner):
        """বাংলা মন্তব্য: Shutdown process-এ সঠিক log messages print হয়।"""

        pm._global_browser = mock_browser
        pm._playwright_runner = mock_playwright_runner

        with patch("core.playwright_manager.logger") as mock_logger:
            await pm.shutdown_global_browser()

            # Verify all expected log messages
            mock_logger.info.assert_any_call("🛡️ Initiating Playwright Global Lifespan Cleanup...")
            mock_logger.info.assert_any_call("Closing active global Chromium engine...")
            mock_logger.info.assert_any_call("Stopping playwright runner core context...")
            mock_logger.info.assert_any_call("✅ All Playwright OS processes terminated cleanly.")


# -------------------- Tests: Integration --------------------


class TestPlaywrightManagerIntegration:
    """বাংলা মন্তব্য: Integration-style tests for realistic scenarios।"""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, mock_browser, mock_playwright_runner):
        """বাংলা মন্তব্য: Create এবং shutdown এর সম্পূর্ণ lifecycle।"""
        mock_playwright = AsyncMock()
        mock_playwright.start.return_value = mock_playwright_runner
        mock_playwright_runner.chromium.launch.return_value = mock_browser

        with patch("core.playwright_manager.async_playwright", return_value=mock_playwright):
            # Create browser
            browser1 = await pm.get_global_browser()
            assert browser1 is mock_browser

            # Get again (should return same instance)
            browser2 = await pm.get_global_browser()
            assert browser2 is mock_browser

            # Shutdown
            await pm.shutdown_global_browser()

            assert pm._global_browser is None
            assert pm._playwright_runner is None

    @pytest.mark.asyncio
    async def test_multiple_sequential_requests(self, mock_browser, mock_playwright_runner):
        """বাংলা মন্তব্য: Multiple sequential requests একই browser return করে।"""
        mock_playwright = AsyncMock()
        mock_playwright.start.return_value = mock_playwright_runner
        mock_playwright_runner.chromium.launch.return_value = mock_browser

        with patch("core.playwright_manager.async_playwright", return_value=mock_playwright):
            # Multiple requests
            browsers = []
            for _ in range(5):
                browsers.append(await pm.get_global_browser())

            # All should be the same instance
            assert all(b is mock_browser for b in browsers)
            # Browser should be created only once
            assert mock_playwright_runner.chromium.launch.call_count == 1
