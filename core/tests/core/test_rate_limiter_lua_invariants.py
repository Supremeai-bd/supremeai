"""Atomic invariant tests for the Upstash Lua sliding-window rate limiters.

Issue #476: during a rebase the atomic Lua limiter was silently dropped and
later recovered. These tests pin the ATOMICITY CONTRACT so any future
merge/rebase drop fails the suite loudly:

  1. Structural: the limit decision MUST be made inside a single Lua script
     (cleanup + count + conditional add in ONE EVAL round-trip).
  2. Structural: no non-atomic decide-then-write flow (GET/SET/DEL).
  3. Functional (fakeredis+lupa when available): a concurrent burst must allow
     EXACTLY ``limit`` calls — atomicity is observable, not just structural.
"""

from __future__ import annotations

import importlib

import pytest

ATOMIC_OPS = ("ZREMRANGEBYSCORE", "ZCARD", "ZADD", "EXPIRE")
NON_ATOMIC_DECIDE_OPS = ("'GET'", '"GET"', "'SET'", '"SET"', "'DEL'", '"DEL"')


def _load_lua_scripts() -> list[tuple[str, str]]:
    """Return (module_label, lua_script_text) for every atomic limiter."""
    scripts: list[tuple[str, str]] = []

    middleware = importlib.import_module("middleware.rate_limiter")
    scripts.append(("middleware.rate_limiter", middleware._SLIDING_WINDOW_LUA))

    return scripts


def test_lua_script_contains_single_roundtrip_atomic_ops():
    for label, lua in _load_lua_scripts():
        for op in ATOMIC_OPS:
            assert op in lua, (
                f"{label}: atomic op {op} missing from Lua script — the sliding "
                "window was likely de-atomized or dropped (issue #476)"
            )


def test_lua_script_has_no_non_atomic_decide_flow():
    for label, lua in _load_lua_scripts():
        for op in NON_ATOMIC_DECIDE_OPS:
            assert op not in lua, (
                f"{label}: non-atomic `{op}` found in Lua script — decide-then-"
                "write flows break the atomicity contract (issue #476)"
            )


def test_lua_script_decides_inside_the_script():
    for label, lua in _load_lua_scripts():
        normalized = lua.replace("current_count", "current").replace("current_requests", "current")
        assert "if current" in normalized, (
            f"{label}: the allow/deny decision must happen inside the Lua script"
        )


def _fakeredis_eval_or_skip():
    try:
        import fakeredis  # noqa: F401
        import lupa  # noqa: F401  # fakeredis Lua needs lupa
    except ImportError:
        pytest.skip("fakeredis+lupa not installed — structural invariants already verified")
    from fakeredis.aioredis import FakeRedis

    return FakeRedis()


def test_concurrent_burst_allows_exactly_limit_calls():
    """Observable atomicity with the PRODUCTION arg order (middleware path)."""
    import asyncio
    import time

    client = _fakeredis_eval_or_skip()
    middleware = importlib.import_module("middleware.rate_limiter")
    lua = middleware._SLIDING_WINDOW_LUA

    limit = 5
    window = 60
    now = time.time()

    async def attempt(i: int) -> bool:
        res = await client.eval(lua, 1, "invariant:key", str(now), str(window), str(limit), str(i))
        return bool(res[0])

    async def burst() -> list[bool]:
        return list(await asyncio.gather(*[attempt(i) for i in range(50)]))

    allowed = asyncio.run(burst())
    allowed_count = sum(1 for a in allowed if a)
    assert allowed_count == limit, (
        f"atomicity broken: {allowed_count} calls allowed, expected exactly {limit} "
        "(non-atomic limiter under concurrent load — issue #476)"
    )
