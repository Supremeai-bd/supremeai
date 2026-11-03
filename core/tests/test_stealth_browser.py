"""
Stealth fingerprint layer tests (old plan, Feature 3).

টিয়ার: unit — Playwright ইনস্টল থাকুক বা না থাকুক, mock page দিয়েই চলে।
"""

from unittest.mock import AsyncMock

import pytest

from core.human_behavior import HumanBehaviorSimulators

pytestmark = pytest.mark.unit


def _make_page():
    page = AsyncMock()
    page.add_init_script = AsyncMock()
    page.set_viewport_size = AsyncMock()
    return page


@pytest.mark.asyncio
async def test_apply_stealth_fingerprint_injects_init_script():
    page = _make_page()
    await HumanBehaviorSimulators.apply_stealth_fingerprint(page)
    page.add_init_script.assert_awaited_once()
    script = page.add_init_script.await_args.args[0]
    # মূল stealth উপাদানগুলো স্ক্রিপ্টে থাকতে হবে
    assert "HTMLCanvasElement.prototype.toDataURL" in script  # canvas noise
    assert "WebGLRenderingContext.prototype.getParameter" in script  # WebGL spoof
    assert "37445" in script and "37446" in script  # vendor/renderer params
    assert "navigator, 'webdriver'" in script  # webdriver trace removal
    assert "navigator, 'plugins'" in script  # realistic plugins


@pytest.mark.asyncio
async def test_apply_stealth_fingerprint_randomizes_viewport():
    page = _make_page()
    await HumanBehaviorSimulators.apply_stealth_fingerprint(page)
    page.set_viewport_size.assert_awaited_once()
    viewport = page.set_viewport_size.await_args.args[0]
    assert viewport["width"] in HumanBehaviorSimulators._REAL_VIEWPORT_WIDTHS
    assert viewport["height"] in HumanBehaviorSimulators._REAL_VIEWPORT_HEIGHTS


@pytest.mark.asyncio
async def test_apply_stealth_never_raises_on_script_failure():
    page = _make_page()
    page.add_init_script = AsyncMock(side_effect=RuntimeError("page closed"))
    page.set_viewport_size = AsyncMock(side_effect=RuntimeError("page closed"))
    # কোনো exception propagate করবে না — stealth ব্যর্থ মানে scraping বন্ধ নয়
    await HumanBehaviorSimulators.apply_stealth_fingerprint(page)


def test_existing_human_behavior_methods_intact():
    # আগের API ভাঙেনি তা নিশ্চিত করা
    pts = HumanBehaviorSimulators._generate_bezier_points((0, 0), (10, 10), steps=5)
    assert len(pts) == 5
    assert callable(HumanBehaviorSimulators.natural_mouse_move_and_click)
    assert callable(HumanBehaviorSimulators.natural_type)


def test_browser_agent_module_imports_stealth():
    # browser_agent.py-তে stealth call wired আছে কিনা (source-level assert —
    # playwright ইনস্টল না থাকলেও টেস্ট চলে)
    import inspect

    import services.scraper.browser_agent as ba

    src = inspect.getsource(ba)
    assert "apply_stealth_fingerprint" in src
    assert src.count("apply_stealth_fingerprint") >= 2  # 2 call sites (navigate + recipe)
