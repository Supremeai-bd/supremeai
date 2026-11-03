# backend/tests/core/test_redis_manager_memory_fallback.py
"""Regression tests for the SecureRedisManager memory:// fallback contract.

ROOT CAUSE (fixed this round, source change in core/cache/redis_manager.py):
REDIS_URL="memory://" is the codebase's documented in-memory fallback scheme,
but ``config_secrets.redis_url`` normalizes it into a VALID-looking TCP URL
("redis://memory://"), and ``SecureRedisManager._ensure_connected`` used to
build a real TCP connection pool from it and cache that broken client on the
module SINGLETON. Any consumer running after that initialization — e.g.
``TenantRateLimiter(redis_client=None)`` falling back to the shared
``redis_manager.client`` — then attempted real TCP connects to host "memory"
and failed with ConnectionError instead of using its own in-memory path.

Observed contamination: ``tests/core/test_advanced_wiring.py::
test_health_check_predictive_wiring`` (via ``health_checker.check_all`` →
``check_redis`` → ``_ensure_connected``) poisoned the singleton, and the four
``test_billing_zero_cost.py`` tests that ran after it failed with
"Redis quota check failed; rejecting request" — order-dependent, group-only,
and invisible in CI (CI runs a real redis service on localhost:6379, where the
same cached client WORKS, which is why CI stayed green).

These tests pin the contract: the memory scheme (plain AND mangled forms)
must leave the manager fail-closed (client None) so every consumer engages
its documented in-memory fallback; real redis URLs must still create a client.

WIRE-FIRST: pins fixed behavior, adds no deletion.
"""

import asyncio
import sys

import pytest

import core.cache.redis_manager  # noqa: F401 — ensures the module is in sys.modules
from core.cache.redis_manager import SecureRedisManager, redis_manager
from tools.tenant_rate_limiter import TenantRateLimiter

# GOTCHA: `core.cache.__init__` re-exports the SINGLETON under the name
# `redis_manager`, shadowing the submodule attribute on the package — so
# `import core.cache.redis_manager as m` binds the INSTANCE, not the module.
# sys.modules still holds the real module object.
redis_manager_module = sys.modules["core.cache.redis_manager"]


def make_manager(url: str) -> SecureRedisManager:
    """Fresh manager instance (NOT the singleton) with a controlled URL."""
    mgr = SecureRedisManager()
    mgr.url = url
    return mgr


@pytest.mark.asyncio
async def test_mangled_memory_url_stays_fail_closed():
    """The mangled normalizer form ("redis://memory://") must NOT create a client.

    This is the exact poisoning chain observed in group runs: health check →
    _ensure_connected → broken TCP pool cached on the singleton.
    """
    mgr = make_manager("redis://memory://")

    await mgr._ensure_connected()

    assert mgr.client is None
    assert mgr.is_connected is False
    assert mgr._initialized is True


@pytest.mark.asyncio
async def test_plain_memory_url_stays_fail_closed():
    """The documented plain form ("memory://") must behave identically."""
    mgr = make_manager("memory://")

    await mgr._ensure_connected()

    assert mgr.client is None
    assert mgr.is_connected is False
    assert mgr._initialized is True


@pytest.mark.asyncio
async def test_real_url_still_creates_client():
    """Guard the guard: real redis URLs must still produce a client.

    from_url is lazy (no connection attempt), so this is offline-safe.
    """
    mgr = make_manager("redis://localhost:6379/0")

    await mgr._ensure_connected()

    assert mgr.client is not None
    assert mgr._initialized is True


@pytest.mark.asyncio
async def test_empty_url_enters_fail_closed_state():
    """No URL configured → documented fail-closed path (existing behavior)."""
    mgr = make_manager("")

    await mgr._ensure_connected()

    assert mgr.client is None
    assert mgr._initialized is True


@pytest.mark.asyncio
async def test_memory_init_is_idempotent_under_concurrency():
    """The memory branch must respect the same single-init contract as TCP init."""
    mgr = make_manager("memory://")

    await asyncio.gather(*(mgr._ensure_connected() for _ in range(5)))

    assert mgr.client is None
    assert mgr._initialized is True


@pytest.mark.asyncio
async def test_tenant_rate_limiter_falls_back_without_poisoned_singleton(monkeypatch):
    """THE contamination regression: limiter with redis_client=None must use its
    in-memory path ("no_redis" → allowed), never a poisoned TCP client."""
    fresh = make_manager("redis://memory://")
    await fresh._ensure_connected()
    # NOTE: `core.cache.redis_manager` cannot be used as a monkeypatch string
    # target — the package's __init__ re-exports the SINGLETON under the same
    # name, shadowing the submodule attribute. Patch the module object directly.
    monkeypatch.setattr(redis_manager_module, "redis_manager", fresh)

    limiter = TenantRateLimiter(redis_client=None)

    # queue resolves to the (fail-closed, None) singleton client, NOT a TCP client
    assert limiter.queue is None

    res = await limiter.check_quota("tenant-1", cost=0.0)
    assert res["allowed"] is True
    assert res["reason"] == "no_redis"


@pytest.mark.asyncio
async def test_module_singleton_remains_usable_after_memory_init():
    """The real singleton must not be poisoned by a memory-scheme init path.

    Runs the memory flow through the SHARED manager if its URL is a memory
    scheme; otherwise (real URL, e.g. CI's localhost redis) only asserts the
    singleton still exposes a consistent client after _ensure_connected.
    """
    if redis_manager.url and "memory://" in redis_manager.url:
        await redis_manager._ensure_connected()
        assert redis_manager.client is None
    else:
        await redis_manager._ensure_connected()
        # real URL: client creation is by design; ensure init flag settled
        assert redis_manager._initialized is True
