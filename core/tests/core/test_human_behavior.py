from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.human_behavior import HumanBehaviorSimulators


@pytest.mark.anyio
async def test_generate_bezier_points_sanity():
    pts = HumanBehaviorSimulators._generate_bezier_points((0, 0), (100, 50), steps=10)
    assert len(pts) == 10
    assert pts[0] is not None
    assert pts[-1] is not None


@pytest.mark.anyio
async def test_natural_mouse_move_and_click(monkeypatch):
    page = MagicMock()
    element = MagicMock()
    element.bounding_box = AsyncMock(return_value={"x": 10, "y": 20, "width": 20, "height": 10})
    page.wait_for_selector = AsyncMock(return_value=element)
    page.mouse.move = AsyncMock()
    page.mouse.click = AsyncMock()

    # Make deterministic randomness
    monkeypatch.setattr("core.human_behavior.random.uniform", lambda a, b: (a + b) / 2)
    monkeypatch.setattr("core.human_behavior.random.randint", lambda a, b: 10)

    with patch("core.human_behavior.asyncio.sleep", new=AsyncMock()) as _sleep:
        await HumanBehaviorSimulators.natural_mouse_move_and_click(page, "#btn")

    assert page.mouse.click.call_count == 1


@pytest.mark.anyio
async def test_natural_type(monkeypatch):
    page = MagicMock()
    element = MagicMock()
    element.focus = AsyncMock()
    page.wait_for_selector = AsyncMock(return_value=element)

    page.keyboard.type = AsyncMock()

    monkeypatch.setattr("core.human_behavior.random.gauss", lambda mean, std: mean)
    with patch("core.human_behavior.asyncio.sleep", new=AsyncMock()):
        await HumanBehaviorSimulators.natural_type(page, "input", "ab")

    assert page.keyboard.type.call_count == 2
