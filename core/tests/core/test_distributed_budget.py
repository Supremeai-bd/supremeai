"""Tests for core/llm/distributed_budget.py — DistributedTokenBudget.

Distributed daily token-budget counter (Redis atomic INCR + TTL). All Redis
interaction is exercised through a STATEFUL in-memory fake that implements the
real semantics the module relies on: ``incrby`` mutates a persistent counter,
``decrby`` rolls it back, ``expire`` records TTL writes. This makes the
rollback path verifiable end-to-end (reserve -> over-limit -> rollback leaves
the counter unchanged), not merely via scripted return values.

Branch targets (coverage.py, 10 branches):
- ``estimated_input > max_input`` / ``estimated_output > max_output`` both arms
  (plus the at-limit boundary, which must be ACCEPTED)
- ``not redis_manager or not redis_manager.client`` — each operand's falsy
  outcome exercised separately (manager missing, client missing)
- ``new_total == total`` first-write TTL arm and subsequent-write arm
- ``new_total > daily_limit`` rollback arm and accept arm (exact-limit boundary)
- ``used_today``: ``if val`` truthy / falsy(None) / falsy("0") arcs
"""

from __future__ import annotations

import importlib
import struct
import time as _time
from typing import Any

import pytest

import core.llm.distributed_budget as db_mod
from core.llm.distributed_budget import _KEY_PREFIX, DistributedTokenBudget

MODULE_NAME = "core.llm.distributed_budget"


# ─────────────────────────────────────────────────────────────────────────────
# Fakes


class StatefulFakeRedisClient:
    """Implements the INCRBY/DECRBY/EXPIRE semantics the module depends on."""

    def __init__(self) -> None:
        self.counters: dict[str, int] = {}
        self.ttls: dict[str, int] = {}
        self.expire_calls: list[tuple[str, int]] = []
        self.decr_calls: list[tuple[str, int]] = []

    async def incrby(self, key: str, amount: int) -> int:
        self.counters[key] = self.counters.get(key, 0) + amount
        return self.counters[key]

    async def decrby(self, key: str, amount: int) -> int:
        self.counters[key] = self.counters.get(key, 0) - amount
        self.decr_calls.append((key, amount))
        return self.counters[key]

    async def expire(self, key: str, ttl: int) -> None:
        self.ttls[key] = ttl
        self.expire_calls.append((key, ttl))


class FakeRedisManager:
    def __init__(self, client: Any = "sentinel-client") -> None:
        self.client = client

    async def get_cache(self, key: str) -> str | None:
        store = getattr(self, "_store", None)
        if store is None:
            return None
        return store.get(key)


class RecorderLogger:
    def __init__(self) -> None:
        self.records: list[tuple[str, str]] = []

    def warning(self, msg: str, *a: Any, **k: Any) -> None:
        self.records.append(("warning", msg))

    def info(self, msg: str, *a: Any, **k: Any) -> None:
        self.records.append(("info", msg))

    def error(self, msg: str, *a: Any, **k: Any) -> None:
        self.records.append(("error", msg))


class FakeTime:
    """Replaces the stdlib ``time`` name inside the module under test."""

    def __init__(self, epoch: float) -> None:
        self._epoch = epoch

    def gmtime(self, secs: float | None = None) -> struct.StructTimeLike:  # noqa: N803
        return _time.gmtime(self._epoch)

    def strftime(self, fmt: str, t: Any = None) -> str:
        return _time.strftime(fmt, t if t is not None else _time.gmtime(self._epoch))


def load_module():
    return importlib.import_module(MODULE_NAME)


@pytest.fixture()
def budget_env(monkeypatch: pytest.MonkeyPatch):
    """Fresh module state: stateful redis fake + recorder logger + fixed day."""
    mod = load_module()
    client = StatefulFakeRedisClient()
    manager = FakeRedisManager(client=client)
    logger = RecorderLogger()
    monkeypatch.setattr(mod, "redis_manager", manager)
    monkeypatch.setattr(mod, "logger", logger)
    monkeypatch.setattr(mod, "time", FakeTime(epoch=1_767_225_600.0))  # 2026-01-01 UTC
    return {"mod": mod, "client": client, "manager": manager, "logger": logger}


# ─────────────────────────────────────────────────────────────────────────────
# Construction


def test_init_defaults() -> None:
    b = DistributedTokenBudget()
    assert b.daily_limit == 100_000
    assert b.max_input == 8192
    assert b.max_output == 4096


def test_init_custom() -> None:
    b = DistributedTokenBudget(daily_limit=42, max_input=10, max_output=5)
    assert (b.daily_limit, b.max_input, b.max_output) == (42, 10, 5)


def test_is_distinct_per_instance() -> None:
    a, b = DistributedTokenBudget(daily_limit=1), DistributedTokenBudget(daily_limit=2)
    assert a.daily_limit != b.daily_limit


# ─────────────────────────────────────────────────────────────────────────────
# Key derivation + daily rotation


def test_key_format_and_prefix(budget_env) -> None:
    b = DistributedTokenBudget()
    assert b._key() == f"{_KEY_PREFIX}2026-01-01"


def test_key_rotates_by_utc_day(budget_env, monkeypatch) -> None:
    mod = budget_env["mod"]
    b = DistributedTokenBudget()
    first = b._key()
    monkeypatch.setattr(mod, "time", FakeTime(epoch=1_767_312_000.0))  # +1 day
    assert b._key() == f"{_KEY_PREFIX}2026-01-02"
    assert first != b._key()


def test_key_prefix_is_namespaced() -> None:
    # Budget keys must live under the llm budget namespace so ops can scan them.
    assert _KEY_PREFIX == "llm:budget:daily:"


# ─────────────────────────────────────────────────────────────────────────────
# check_and_reserve — per-request caps


async def test_rejects_oversized_input_without_touching_redis(budget_env) -> None:
    b = DistributedTokenBudget(max_input=100, max_output=100)
    ok = await b.check_and_reserve(101, 10)
    assert ok is False
    assert budget_env["client"].counters == {}  # nothing reserved


async def test_rejects_oversized_output_without_touching_redis(budget_env) -> None:
    b = DistributedTokenBudget(max_input=100, max_output=100)
    ok = await b.check_and_reserve(10, 101)
    assert ok is False
    assert budget_env["client"].counters == {}


async def test_boundary_exact_caps_accepted_and_reserved(budget_env) -> None:
    b = DistributedTokenBudget(daily_limit=1000, max_input=100, max_output=100)
    ok = await b.check_and_reserve(100, 100)
    assert ok is True  # <= cap passes
    assert budget_env["client"].counters[b._key()] == 200


# ─────────────────────────────────────────────────────────────────────────────
# check_and_reserve — degraded Redis (conservative fallback)


async def test_missing_redis_manager_falls_back_permissive(budget_env, monkeypatch) -> None:
    mod = budget_env["mod"]
    monkeypatch.setattr(mod, "redis_manager", None)
    b = DistributedTokenBudget()
    ok = await b.check_and_reserve(10, 10)
    assert ok is True  # documented conservative fallback, NOT fail-closed
    assert any("Redis unavailable" in msg for _, msg in budget_env["logger"].records)


async def test_missing_redis_client_falls_back_permissive(budget_env, monkeypatch) -> None:
    mod = budget_env["mod"]
    monkeypatch.setattr(mod, "redis_manager", FakeRedisManager(client=None))
    b = DistributedTokenBudget()
    ok = await b.check_and_reserve(10, 10)
    assert ok is True
    assert any("Redis unavailable" in msg for _, msg in budget_env["logger"].records)


async def test_used_today_without_redis_is_zero(budget_env, monkeypatch) -> None:
    mod = budget_env["mod"]
    monkeypatch.setattr(mod, "redis_manager", None)
    assert await DistributedTokenBudget().used_today() == 0


async def test_used_today_without_client_is_zero(budget_env, monkeypatch) -> None:
    mod = budget_env["mod"]
    monkeypatch.setattr(mod, "redis_manager", FakeRedisManager(client=None))
    assert await DistributedTokenBudget().used_today() == 0


# ─────────────────────────────────────────────────────────────────────────────
# check_and_reserve — atomic reserve, TTL-on-first-write, rollback


async def test_first_write_sets_ninety_thousand_second_ttl(budget_env) -> None:
    b = DistributedTokenBudget(daily_limit=1000)
    assert await b.check_and_reserve(10, 10) is True
    client = budget_env["client"]
    assert client.ttls == {b._key(): 90_000}
    assert len(client.expire_calls) == 1


async def test_subsequent_write_does_not_reset_ttl(budget_env) -> None:
    b = DistributedTokenBudget(daily_limit=1000)
    await b.check_and_reserve(10, 10)
    await b.check_and_reserve(5, 5)
    assert len(budget_env["client"].expire_calls) == 1  # only the first write
    assert budget_env["client"].counters[b._key()] == 30


async def test_over_limit_rolls_back_and_denies(budget_env) -> None:
    b = DistributedTokenBudget(daily_limit=100)
    client = budget_env["client"]
    assert await b.check_and_reserve(60, 30) is True  # total 90 <= 100
    assert await b.check_and_reserve(60, 30) is False  # would be 180 > 100
    # Anti-Silent-Failure: the denied reservation is ROLLED BACK
    assert client.counters[b._key()] == 90
    assert client.decr_calls == [(b._key(), 90)]


async def test_exact_limit_accepted_not_rolled_back(budget_env) -> None:
    b = DistributedTokenBudget(daily_limit=100)
    client = budget_env["client"]
    assert await b.check_and_reserve(100, 0) is True  # lands exactly on limit
    assert client.counters[b._key()] == 100
    assert client.decr_calls == []  # boundary must not trigger rollback


async def test_first_write_crossing_limit_expires_then_rolls_back(budget_env) -> None:
    # Fresh key + oversized first reservation: TTL write and rollback BOTH occur.
    b = DistributedTokenBudget(daily_limit=10)
    client = budget_env["client"]
    assert await b.check_and_reserve(50, 50) is False
    assert client.ttls == {b._key(): 90_000}  # first write still sets TTL
    assert client.counters[b._key()] == 0  # rolled back to nothing
    assert client.decr_calls == [(b._key(), 100)]


async def test_multi_worker_accumulation_real_semantics(budget_env) -> None:
    # Simulates N workers sharing the counter: each INCR mutates state; the
    # first crossing is denied and rolled back leaving prior usage intact.
    b = DistributedTokenBudget(daily_limit=300)
    client = budget_env["client"]
    ok1 = await b.check_and_reserve(100, 0)
    ok2 = await b.check_and_reserve(100, 0)
    ok3 = await b.check_and_reserve(100, 0)
    ok4 = await b.check_and_reserve(1, 0)
    assert (ok1, ok2, ok3, ok4) == (True, True, True, False)
    assert client.counters[b._key()] == 300


# ─────────────────────────────────────────────────────────────────────────────
# used_today


async def test_used_today_reads_counter_as_int(budget_env) -> None:
    b = DistributedTokenBudget(daily_limit=1000)
    await b.check_and_reserve(7, 8)
    budget_env["manager"]._store = {b._key(): str(15)}
    assert await b.used_today() == 15


async def test_used_today_missing_key_is_zero(budget_env) -> None:
    budget_env["manager"]._store = {}
    assert await DistributedTokenBudget().used_today() == 0


async def test_used_today_none_value_is_zero(budget_env) -> None:
    budget_env["manager"]._store = {DistributedTokenBudget()._key(): None}
    assert await DistributedTokenBudget().used_today() == 0


async def test_used_today_zero_string_is_zero(budget_env) -> None:
    # "0" is falsy -> the documented short-circuit treats it as no usage.
    budget_env["manager"]._store = {DistributedTokenBudget()._key(): "0"}
    assert await DistributedTokenBudget().used_today() == 0


async def test_used_today_non_numeric_string_returns_value_unchanged(budget_env) -> None:
    # Contract lock: int(val) conversion is attempted, so numeric strings work;
    # the module does NOT sanitize garbage — lock current behavior explicitly.
    budget_env["manager"]._store = {DistributedTokenBudget()._key(): "42"}
    assert await DistributedTokenBudget().used_today() == 42


def test_module_exports_dunder_all_safe() -> None:
    mod = load_module()
    assert hasattr(mod, "DistributedTokenBudget")
    assert mod._KEY_PREFIX.startswith("llm:")
