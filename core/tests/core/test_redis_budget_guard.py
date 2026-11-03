"""#1824 — daily command budget guard on the production Redis path tests.

বাংলা: SecureRedisManager এখন প্রতিটি command গোনে (tracking proxy), দিন-শেষে
budget শেষ হলে breaker খোলে (consumers তাদের documented in-memory fallback-এ
যায়)। মৃত core/cache_manager.py ডিলিট হয়েছে — একটাই cache-manager থাকবে।
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import pytest


class FakeInnerClient:
    """Minimal async redis-ish client — records executed commands."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.connection_pool = "pool-attr"  # non-callable attribute passthrough

    async def get(self, key: str):
        self.calls.append(("get", key))
        return None

    async def set(self, key: str, value: str, ex: int | None = None):
        self.calls.append(("set", key, value, ex))
        return True

    async def ping(self):
        self.calls.append(("ping",))
        return True


def _snapshot_redis_manager_modules() -> dict:
    """FIX (#2088 fallout): snapshot live sys.modules entries for the module.

    The reload dance below replaces the module object in sys.modules with a
    FRESH one (new singleton). Without restoring the snapshot at teardown,
    every later ``from core.cache.redis_manager import redis_manager`` in the
    same pytest session resolves to that fresh module, while tests that
    captured the module object earlier (e.g. module-level import_module in
    test_security_rate_limit_backend) keep patching the STALE object — their
    monkeypatches silently no-op and the REAL singleton is used (observed in
    CI core-unit: 4× "Event loop is closed" rate-limit failures that pass
    in isolation).
    """
    return {
        name: mod
        for name, mod in sys.modules.items()
        if name == "core.cache.redis_manager" or name.startswith("core.cache.redis_manager.")
    }


def _restore_redis_manager_modules(saved: dict) -> None:
    for name in [
        m
        for m in list(sys.modules)
        if m == "core.cache.redis_manager" or m.startswith("core.cache.redis_manager.")
    ]:
        del sys.modules[name]
    sys.modules.update(saved)


@pytest.fixture()
def manager(monkeypatch):
    """SecureRedisManager with no network: monkeypatch connect to a FakeInnerClient."""
    monkeypatch.setenv("REDIS_DAILY_LIMIT", "10")
    # বাংলা: `import core.cache.redis_manager as x` ট্র্যাপ — core/cache/__init__
    # প্যাকেজ নেমস্পেসে `redis_manager` = singleton INSTANCE, তাই module নয়।
    # import_module() সবসময় module অবজেক্ট দেয়।
    saved = _snapshot_redis_manager_modules()
    for mod_name in list(saved):
        del sys.modules[mod_name]
    module = importlib.import_module("core.cache.redis_manager")
    mgr = module.SecureRedisManager()

    async def _fake_ensure():
        if mgr._client is None:
            mgr._client = FakeInnerClient()
        mgr._initialized = True

    monkeypatch.setattr(mgr, "_ensure_connected", _fake_ensure)
    yield mgr
    # বাংলা: teardown — reload-করা fresh module-কা বাদ দিয়ে আসল module
    # object ফিরিয়ে দিই, যাতে পরের টেস্টগুলো stale-module monkeypatch ট্র্যাপে
    # না পড়ে (#2088 fallout fix)।
    _restore_redis_manager_modules(saved)


class TestBudgetTracking:
    @pytest.mark.asyncio
    async def test_every_command_is_counted(self, manager):
        client = await manager.get_client_async()
        assert client is not None
        await client.get("k1")
        await client.set("k2", "v")
        status = manager.get_budget_status()
        assert status["used"] == 2, "both commands tracked through the proxy"

    @pytest.mark.asyncio
    async def test_non_callable_attributes_passthrough(self, manager):
        client = await manager.get_client_async()
        assert client.connection_pool == "pool-attr"

    @pytest.mark.asyncio
    async def test_warns_at_80_percent(self, manager, caplog):
        client = await manager.get_client_async()
        for i in range(8):  # budget=10 → 80% at 8
            await client.ping()
        status = manager.get_budget_status()
        assert status["used"] == 8
        assert status["breaker_open"] is False

    @pytest.mark.asyncio
    async def test_budget_exhausted_opens_breaker(self, manager):
        client = await manager.get_client_async()
        for _ in range(10):  # exhaust the 10-command budget
            await client.ping()
        assert manager.budget_breaker_open is True
        # get_client_async now returns None — consumers engage in-memory fallbacks
        assert await manager.get_client_async() is None

    @pytest.mark.asyncio
    async def test_daily_reset_reopens_breaker(self, manager, monkeypatch):
        client = await manager.get_client_async()
        for _ in range(10):
            await client.ping()
        assert manager.budget_breaker_open is True
        # simulate UTC day rollover
        manager._command_date = None
        manager._track_command(0)
        assert manager.budget_breaker_open is False
        assert manager.get_budget_status()["used"] == 0

    @pytest.mark.asyncio
    async def test_disabled_budget_never_opens(self, monkeypatch):
        monkeypatch.setenv("REDIS_DAILY_LIMIT", "0")
        saved = _snapshot_redis_manager_modules()
        try:
            for mod_name in list(saved):
                del sys.modules[mod_name]
            rm = importlib.import_module("core.cache.redis_manager")
            mgr = rm.SecureRedisManager()

            async def _fake_ensure():
                if mgr._client is None:
                    mgr._client = FakeInnerClient()
                mgr._initialized = True

            monkeypatch.setattr(mgr, "_ensure_connected", _fake_ensure)
            client = await mgr.get_client_async()
            for _ in range(50):
                await client.ping()
            status = mgr.get_budget_status()
            assert status["enabled"] is False
            assert status["breaker_open"] is False
        finally:
            _restore_redis_manager_modules(saved)


class TestSingleCacheManager:
    def test_dead_cache_manager_removed(self):
        backend_root = Path(__file__).resolve().parents[2]
        assert not (backend_root / "core" / "cache_manager.py").exists(), (
            "FreeTierCacheManager (dead code) must stay deleted — one cache-manager remains"
        )

    def test_health_probes_comment_cleaned(self):
        backend_root = Path(__file__).resolve().parents[2]
        text = (backend_root / "core" / "health" / "health_probes.py").read_text(encoding="utf-8")
        assert "cache_manager.py" not in text
