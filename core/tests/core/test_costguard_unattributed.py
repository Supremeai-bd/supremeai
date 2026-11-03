"""#2732 — CostGuard fail-closed for unattributed (tenant-হীন) inference.

Contract being locked:
1. tenant_id=None/"anonymous"/"unattributed" → Redis daily cap enforcement
   (402 when cap exceeded, 402 when Redis down — fail-closed, never free-spend)
2. Named tenant → Firestore budget-doc path, behavior unchanged (regression pin)
3. Admin kill-switch (cap <= 0) disables the unattributed gate explicitly
4. Pre-flight estimate is accumulated immediately (thundering-herd safe)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from core.cost_guard import CostGuard
from core.llm.llm_gateway.completion import (
    UNATTRIBUTED_TENANT,
    enforce_preflight_budget,
)

# বাংলা মন্তব্য: টেস্টে প্রতিটি কেসে Redis mock বসানো হয় — বাস্তব Redis লাগে না।


def _redis_mock(spent_raw=None, fail_get=False, fail_incr=False):
    redis = MagicMock()
    if fail_get:
        redis.get_cache = AsyncMock(side_effect=RuntimeError("redis down"))
    else:
        redis.get_cache = AsyncMock(return_value=spent_raw)
    if fail_incr:
        redis.incrbyfloat = AsyncMock(side_effect=RuntimeError("redis down"))
    else:
        redis.incrbyfloat = AsyncMock(return_value=float(spent_raw or 0) + 0.01)
    return redis


@pytest.fixture
def _cap_1():
    """বাংলা মন্তব্য: ক্যাপ $১ — টেস্ট-ডিফল্ট। cost_guard settings-টা কল-টাইমে
    core.config থেকেই নেয় — তাই এক জায়গায় patch করলেই যথেষ্ট।"""
    with patch("core.config.settings") as mock_settings:
        mock_settings.costguard_unattributed_daily_cap = 1.0
        yield mock_settings


@pytest.mark.asyncio
async def test_unattributed_within_cap_accumulates_estimate(_cap_1):
    """ক্যাপের ভেতরে → True ফেরত + estimate সঙ্গে সঙ্গে জমা (herd-safe)।"""
    guard = CostGuard()  # db=None — unattributed লেনে db লাগেই না
    redis = _redis_mock(spent_raw="0.50")
    with patch("core.cache.redis_manager.redis_manager", redis):
        ok = await guard.check_unattributed_budget(0.01)
    assert ok is True
    redis.get_cache.assert_awaited_once_with(CostGuard.UNATTRIBUTED_SPEND_KEY)
    redis.incrbyfloat.assert_awaited_once_with(
        CostGuard.UNATTRIBUTED_SPEND_KEY, 0.01, ex_seconds=86400
    )


@pytest.mark.asyncio
async def test_unattributed_cap_exceeded_raises_402(_cap_1):
    """খরচ ক্যাপ ছাড়ালে → HTTPException 402 (fail-closed)।"""
    guard = CostGuard()
    redis = _redis_mock(spent_raw="0.999")
    with patch("core.cache.redis_manager.redis_manager", redis):
        with pytest.raises(HTTPException) as exc:
            await guard.check_unattributed_budget(0.01)
    assert exc.value.status_code == 402
    # বাংলা মন্তব্য: ছাড়ালে জমা হবে না — ক্যাপ-ব্রেক কল spend রেকর্ড করে না।
    redis.incrbyfloat.assert_not_awaited()


@pytest.mark.asyncio
async def test_unattributed_redis_down_fails_closed(_cap_1):
    """Redis ডাউন → 402 (fail-open নিষিদ্ধ — এটাই #2732-র মূল ফাঁক ছিল)।"""
    guard = CostGuard()
    redis = _redis_mock(fail_get=True)
    with patch("core.cache.redis_manager.redis_manager", redis):
        with pytest.raises(HTTPException) as exc:
            await guard.check_unattributed_budget(0.01)
    assert exc.value.status_code == 402


@pytest.mark.asyncio
async def test_unattributed_kill_switch_cap_zero(_cap_1):
    """cap<=0 → admin kill-switch: গেট পুরো বন্ধ, Redis-ও ধরা হয় না।"""
    guard = CostGuard()
    redis = _redis_mock()
    with (
        patch("core.config.settings") as mock_settings,
        patch("core.cache.redis_manager.redis_manager", redis),
    ):
        mock_settings.costguard_unattributed_daily_cap = 0.0
        ok = await guard.check_unattributed_budget(0.01)
    assert ok is True
    redis.get_cache.assert_not_awaited()


@pytest.mark.asyncio
async def test_gateway_preflight_routes_unattributed_lane(_cap_1):
    """acompletion প্রি-ফ্লাইট: tenant None/anonymous/unattributed → Redis গেট।"""
    redis = _redis_mock(spent_raw="0.0")
    fake_guard = MagicMock()
    fake_guard.check_unattributed_budget = AsyncMock(return_value=True)
    with (
        patch("core.cache.redis_manager.redis_manager", redis),
        patch("core.cost_guard.cost_guard", fake_guard),
        patch("core.llm.llm_gateway.get_firestore_db") as mock_db_resolver,
    ):
        for tenant in (None, "anonymous", UNATTRIBUTED_TENANT):
            await enforce_preflight_budget(tenant, "hello world")
    assert fake_guard.check_unattributed_budget.await_count == 3
    # বাংলা মন্তব্য: unattributed লেনে Firestore-এ হাতই দেওয়া হয় না।
    mock_db_resolver.assert_not_called()


@pytest.mark.asyncio
async def test_gateway_preflight_named_tenant_unchanged(_cap_1):
    """নাম-জানা tenant → Firestore budget গেট (আচরণ অপরিবর্তিত — regression pin)।"""
    fake_db = MagicMock()
    fake_guard_cls = MagicMock()
    fake_guard_cls.return_value.check_budget = AsyncMock(return_value=True)
    with (
        patch("core.llm.llm_gateway.completion.get_firestore_db", return_value=fake_db),
        patch("core.llm.llm_gateway.completion.CostGuard", fake_guard_cls),
    ):
        await enforce_preflight_budget("tenant-alpha", "hello world")
    fake_guard_cls.assert_called_once_with(fake_db)
    fake_guard_cls.return_value.check_budget.assert_awaited_once()
    args = fake_guard_cls.return_value.check_budget.await_args
    assert args.args[0] == "tenant-alpha"
    assert args.args[1] > 0  # বাংলা মন্তব্য: ধনাত্মক estimated cost যায়


@pytest.mark.asyncio
async def test_gateway_preflight_named_tenant_without_db_still_bypasses(_cap_1):
    """নাম-জানা tenant কিন্তু Firestore নেই → পুরোনো graceful আচরণ (skip)।"""
    fake_guard = MagicMock()
    fake_guard.check_unattributed_budget = AsyncMock(return_value=True)
    with (
        patch("core.llm.llm_gateway.completion.get_firestore_db", return_value=None),
        patch("core.cost_guard.cost_guard", fake_guard),
    ):
        await enforce_preflight_budget("tenant-alpha", "hello world")
    fake_guard.check_unattributed_budget.assert_not_awaited()
