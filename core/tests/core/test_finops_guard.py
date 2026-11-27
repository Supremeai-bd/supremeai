"""FinOps guard: limits are validated, enforced before chat, and usage is recorded after."""

from __future__ import annotations

import asyncio
import json

import pytest


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _fresh_cache(monkeypatch):
    from core.finops import guard

    guard._cache.update(at=0.0, value=dict(guard.DEFAULTS), source="default")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    yield


class FakeRedis:
    def __init__(self):
        self.kv: dict[str, int] = {}
        self.z: dict[str, dict[str, float]] = {}

    async def get(self, key):
        return self.kv.get(key)

    async def zrevrange(self, key, start, end, withscores=False):
        rows = sorted(self.z.get(key, {}).items(), key=lambda r: -r[1])
        return rows[start : end + 1]

    def pipeline(self):
        redis = self
        ops = []

        class Pipe:
            def incrby(self, k, n):
                ops.append(lambda: redis.kv.__setitem__(k, int(redis.kv.get(k, 0)) + n))

            def expire(self, *_):
                pass

            def zincrby(self, k, n, member):
                def op():
                    bucket = redis.z.setdefault(k, {})
                    bucket[member] = bucket.get(member, 0) + n

                ops.append(op)

            async def execute(self):
                for op in ops:
                    op()

        return Pipe()


def _install(monkeypatch, *, rpm_ok=True, budget_ok=True, redis=None):
    from core.finops import guard
    import core.llm.token_budget as tb
    import core.middleware.rate_limiter as rl

    recorded: list[tuple[str, int]] = []
    seen: dict[str, object] = {}

    class Limiter:
        async def acquire(self, key, limit=None, window=None):
            seen["rpm"] = (key, limit, window)
            return rpm_ok

    class Budget:
        async def check_user_budget(self, user_id, daily_limit=0):
            seen["daily"] = (user_id, daily_limit)
            return budget_ok

        async def record_user_usage(self, user_id, tokens):
            recorded.append((user_id, tokens))

    monkeypatch.setattr(rl, "AsyncRateLimiter", Limiter)
    monkeypatch.setattr(tb, "get_budget_manager", lambda *a, **k: Budget())

    async def fake_redis():
        return redis

    monkeypatch.setattr(guard, "_redis", fake_redis)
    return seen, recorded


def test_validate_settings_accepts_ints_and_rejects_junk():
    from core.finops.guard import validate_settings

    assert validate_settings({"user_rpm": 30, "enforce": False, "x": 1}) == {"user_rpm": 30, "enforce": False}
    for bad in ({"user_rpm": -1}, {"user_rpm": "10"}, {"user_daily_tokens": True}, {"enforce": "yes"}, {}):
        with pytest.raises(ValueError):
            validate_settings(bad)


def test_check_allows_and_uses_configured_limits(monkeypatch):
    from core.finops import guard

    seen, _ = _install(monkeypatch)
    decision = run(guard.check("u1", {"role": "user"}))
    assert decision.allowed
    assert seen["rpm"] == ("finops_rpm:u1", 20, 60)
    assert seen["daily"] == ("u1", 200_000)


def test_rpm_and_daily_limits_block_with_retry_after(monkeypatch):
    from core.finops import guard

    _install(monkeypatch, rpm_ok=False)
    d = run(guard.check("u1", {}))
    assert (d.allowed, d.reason, d.retry_after, d.limit) == (False, "rate_limited", 60, 20)

    _install(monkeypatch, budget_ok=False)
    d = run(guard.check("u1", {}))
    assert not d.allowed and d.reason == "user_daily_tokens" and d.retry_after >= 60


def test_global_cap_blocks_when_platform_usage_reached(monkeypatch):
    from core.finops import guard

    redis = FakeRedis()
    redis.kv[f"finops_global:{guard._today()}"] = 1000
    _install(monkeypatch, redis=redis)
    guard._cache.update(at=1e12, value={**guard.DEFAULTS, "global_daily_tokens": 1000})
    d = run(guard.check("u1", {}))
    assert not d.allowed and d.reason == "global_daily_tokens"


def test_admins_and_disabled_enforcement_are_never_blocked(monkeypatch):
    from core.finops import guard

    _install(monkeypatch, rpm_ok=False, budget_ok=False)
    assert run(guard.check("u1", {"role": "admin"})).allowed
    guard._cache.update(at=1e12, value={**guard.DEFAULTS, "enforce": False})
    assert run(guard.check("u1", {})).allowed


def test_guard_fails_open_on_internal_error(monkeypatch):
    from core.finops import guard

    async def boom(force=False):
        raise RuntimeError("x")

    monkeypatch.setattr(guard, "load_settings", boom)
    assert run(guard.check("u1", {})).allowed


def test_record_updates_user_global_and_leaderboard(monkeypatch):
    from core.finops import guard

    redis = FakeRedis()
    _, recorded = _install(monkeypatch, redis=redis)
    run(guard.record("u1", 120))
    run(guard.record("u2", 30))
    run(guard.record("u1", 0))  # ignored
    assert recorded == [("u1", 120), ("u2", 30)]
    snap = run(guard.usage_snapshot())
    assert snap["globalTokens"] == 150
    assert snap["topUsers"][0] == {"userId": "u1", "tokens": 120}


def test_metered_stream_records_prompt_plus_delta_text(monkeypatch):
    from core.api.routes import stream_chat_sse as sse

    calls: list[tuple[str, int]] = []

    async def fake_record(user_id, tokens):
        calls.append((user_id, tokens))

    monkeypatch.setattr(sse.finops_guard, "record", fake_record)

    def ev(kind, data):
        return f"event: {kind}\ndata: {json.dumps(data)}\n\n"

    async def events():
        yield ev("connected", {"user_id": "u1"})
        yield ev("token", {"delta": "a" * 40, "token": "a" * 40})
        yield ": ping\n\n"
        yield ev("done", {})

    async def consume():
        return [e async for e in sse._metered(events(), "u1", "b" * 40)]

    out = run(consume())
    assert len(out) == 4
    assert calls and calls[0][0] == "u1" and calls[0][1] > 0
    assert sse._delta_text(ev("token", {"delta": "hi"})) == "hi"
    assert sse._delta_text(ev("connected", {"delta": "x"})) == ""


def test_enforce_raises_429_with_reason(monkeypatch):
    from fastapi import HTTPException

    from core.api.routes import stream_chat_sse as sse
    from core.finops.guard import Decision

    async def deny(user_id, payload=None):
        return Decision(False, "user_daily_tokens", 3600, 200_000)

    monkeypatch.setattr(sse.finops_guard, "check", deny)
    with pytest.raises(HTTPException) as exc:
        run(sse._enforce_finops("u1", {}))
    assert exc.value.status_code == 429
    assert exc.value.headers["Retry-After"] == "3600"
    assert exc.value.detail["reason"] == "user_daily_tokens"
