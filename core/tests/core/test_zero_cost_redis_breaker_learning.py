"""Coverage ramp — zero_cost_patch_phase1_4.py ROUND B (phases 2-4 + integration).

Round A (test_zero_cost_phase1_queue.py) covered the Phase-1 queue subsystem and
module utilities. This module covers everything from Phase 2 onward:

- UpstashRedisClient        (free-tier Redis client, aiohttp REST)
- AdaptiveCircuitBreaker    (states, acquire/record, adaptive threshold, status)
- PerformanceLearningEngine (metric recording, tuning loop, optimization)
- ZeroCostOrchestrator      (composition, execute_with_resilience, health)
- get_orchestrator / lifespan_manager (module globals + FastAPI lifespan)

CI-safe by construction:
- aiohttp is faked at the module's own namespace seam (monkeypatch zc.aiohttp);
  no network is ever attempted (UPSTASH_REDIS_URL unset -> client disabled, or
  the fake session answers synchronously).
- The tuning loop is driven by stubbed _run_tuning_cycle coroutines; intervals
  are 0 or irrelevant because the stub terminates the loop deterministically.
- No environment-specific assertions.

OWNER QUIRKS documented (never patched, wire-first):
1. UpstashRedisClient.set() sends params {"nex": "true"} — the Upstash REST API
   recognizes "nx"; "nex" is ignored, so the claimed set-if-not-exists semantics
   silently degrade into always-overwrite.
2. PerformanceLearningEngine.stop()'s silenced-await arm is unreachable via the
   real _auto_tuning_loop (the loop swallows CancelledError and breaks), so it
   is exercised through a coroutine that propagates cancellation, honestly
   simulating the only code shape that can reach it.
3. _calculate_performance_score's `if not recent: continue` guard is dead code:
   recent_count = max(1, len(samples)//5) with non-empty samples always yields a
   non-empty slice (the empty case is already skipped one branch earlier).
4. ZeroCostOrchestrator.health_check() computes uptime as
   `monotonic() - (start or 0)` — for a never-initialized orchestrator this
   reports the raw monotonic clock value as "uptime_seconds".
5. PerformanceLearningEngine._calculate_adjustment matches "queue" first in its
   elif chain, so the registered parameter "queue_task_timeout" (whose name
   contains "queue") can never reach the timeout-tuning branch; only a
   parameter named with "timeout" but without "queue" can. Covered with such
   a name.
6. ZeroCostOrchestrator.execute_with_resilience calls
   `enqueue(coro_func=..., args=args, kwargs=kwargs, ...)` — but
   InProcessAsyncQueue.enqueue's real signature is
   `(coro_func, *args, priority, task_id, timeout, max_retries, metadata,
   callback, **kwargs)` with NO args=/kwargs= parameters, so both land in
   **kwargs and every task is invoked as `coro_func(args=(...), kwargs={...})`.
   Any coroutine that does not accept those two keyword names (including
   zero-arg ones) raises TypeError after exhausting retries. Tests cover the
   de-facto contract (**kw coroutines receive the injected pairs) and the
   realistic breakage (zero-arg coro -> TypeError), and the PR body carries
   the one-line owner fix candidate
   (`enqueue(coro_func, *args, priority=priority, timeout=timeout, **kwargs)`).
"""

from __future__ import annotations

import asyncio
import json
import time
import types

import pytest

import core.zero_cost_architecture.zero_cost_patch_phase1_4 as zc
from core.zero_cost_architecture.zero_cost_patch_phase1_4 import (
    AdaptiveCircuitBreaker,
    AdaptiveCircuitBreakerState,
    BreakerMetrics,
    LearnedParameter,
    PerformanceLearningEngine,
    UpstashRedisClient,
    ZeroCostConfig,
    ZeroCostOrchestrator,
)


def small_config(**over) -> ZeroCostConfig:
    base = dict(
        QUEUE_MAX_CONCURRENT_TASKS=2,
        QUEUE_TASK_TIMEOUT_SECONDS=5.0,
        QUEUE_MAX_QUEUE_SIZE=100,
        QUEUE_PRIORITY_LEVELS=5,
        QUEUE_BACKPRESSURE_THRESHOLD=0.8,
        GRACEFUL_SHUTDOWN_TIMEOUT=1.0,
    )
    base.update(over)
    return ZeroCostConfig(**base)


# ───────────────────────── aiohttp fake (module seam) ─────────────────────────


class _FakeResponse:
    def __init__(self, status=200, payload=None):
        self.status = status
        self._payload = {} if payload is None else payload

    async def json(self):
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeCtx:
    def __init__(self, session, method, path, **extras):
        self._session = session
        self._method = method
        self._path = path
        self._extras = extras

    async def __aenter__(self):
        self._session.calls.append((self._method, self._path, self._extras))
        if self._session.error is not None:
            raise self._session.error
        return self._session.response

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    """Minimal aiohttp.ClientSession stand-in (no network)."""

    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.closed = False
        self.calls: list[tuple[str, str, dict]] = []

    def get(self, path, **kw):
        return _FakeCtx(self, "GET", path, **kw)

    def post(self, path, json=None, params=None, **kw):
        return _FakeCtx(self, "POST", path, json=json, params=params)

    async def close(self):
        self.closed = True


class FakeAiohttpModule:
    """Stands in for the aiohttp module inside zc's namespace.

    Every ClientSession(...) construction is recorded and yields a FakeSession
    pre-loaded with this module's canned response/error.
    """

    class ClientTimeout:
        def __init__(self, total=None):
            self.total = total

    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error
        self.sessions: list[FakeSession] = []
        self.init_kwargs: list[dict] = []

    def ClientSession(self, **kwargs):
        self.init_kwargs.append(kwargs)
        session = FakeSession(response=self._response, error=self._error)
        self.sessions.append(session)
        return session


@pytest.fixture
def aiohttp_factory(monkeypatch):
    """Install a canned FakeAiohttpModule as zc.aiohttp and hand it back."""

    def factory(response=None, error=None) -> FakeAiohttpModule:
        fake = FakeAiohttpModule(response=response, error=error)
        monkeypatch.setattr(zc, "aiohttp", fake)
        return fake

    return factory


def redis_cfg() -> ZeroCostConfig:
    return small_config(
        UPSTASH_REDIS_URL="https://example.upstash.io",
        UPSTASH_REDIS_TOKEN="tok123",
        RATE_LIMIT_REDIS_CALLS_PER_DAY=100,
        REDIS_CACHE_TTL_SECONDS=60,
    )


# ───────────────────────── UpstashRedisClient ─────────────────────────


async def test_upstash_init_disabled_logs_warning():
    client = UpstashRedisClient(small_config())
    assert client._enabled is False
    assert client._redis is None
    assert client._request_count == 0


async def test_upstash_init_enabled():
    client = UpstashRedisClient(redis_cfg())
    assert client._enabled is True
    assert client._last_reset_date  # date string set


async def test_upstash_get_session_disabled_returns_none():
    client = UpstashRedisClient(small_config())
    assert await client._get_session() is None


async def test_upstash_get_session_constructs_with_auth(aiohttp_factory):
    fake = aiohttp_factory()
    client = UpstashRedisClient(redis_cfg())
    s1 = await client._get_session()
    assert s1 is fake.sessions[0]
    kw = fake.init_kwargs[0]
    assert kw["base_url"] == "https://example.upstash.io"
    assert kw["headers"] == {"Authorization": "Bearer tok123"}
    assert kw["timeout"].total == 2.0
    s2 = await client._get_session()
    assert s2 is s1  # idempotent while open
    assert len(fake.sessions) == 1


async def test_upstash_get_session_recreates_after_close(aiohttp_factory):
    fake = aiohttp_factory()
    client = UpstashRedisClient(redis_cfg())
    s1 = await client._get_session()
    s1.closed = True
    s2 = await client._get_session()
    assert s2 is not s1
    assert len(fake.sessions) == 2


async def test_upstash_rate_limit_resets_on_new_day():
    client = UpstashRedisClient(small_config())
    client._request_count = 999
    client._last_reset_date = "2000-01-01"
    assert await client._check_rate_limit() is True
    assert client._request_count == 0


async def test_upstash_rate_limit_90_percent_margin():
    client = UpstashRedisClient(redis_cfg())
    client._request_count = 89
    assert await client._check_rate_limit() is True
    client._request_count = 90  # >= 100 * 0.9
    assert await client._check_rate_limit() is False


async def test_upstash_local_cache_expiry_deletes_entry():
    client = UpstashRedisClient(small_config())
    client._local_cache["k"] = ("v", time.time() - 1.0)
    assert client._get_local("k") is None
    assert "k" not in client._local_cache


async def test_upstash_set_local_default_ttl_uses_config():
    client = UpstashRedisClient(redis_cfg())
    before = time.time()
    client._set_local("k", "v")
    _, expiry = client._local_cache["k"]
    assert before + 55 < expiry <= before + 61


async def test_upstash_get_local_hit_skips_redis(aiohttp_factory):
    fake = aiohttp_factory()
    client = UpstashRedisClient(redis_cfg())
    client._set_local("k", "v")
    assert await client.get("k") == "v"
    assert fake.sessions == []  # no session ever constructed


async def test_upstash_get_rate_limited_returns_none():
    client = UpstashRedisClient(redis_cfg())
    client._request_count = 95
    assert await client.get("k") is None


async def test_upstash_get_disabled_returns_none():
    client = UpstashRedisClient(small_config())
    assert await client.get("k") is None


async def test_upstash_get_remote_hit_caches_and_counts(aiohttp_factory):
    fake = aiohttp_factory(response=_FakeResponse(200, {"result": "rv"}))
    client = UpstashRedisClient(redis_cfg())
    assert await client.get("k") == "rv"
    assert client._get_local("k") == "rv"
    assert client._request_count == 1
    method, path, _ = fake.sessions[0].calls[0]
    assert (method, path) == ("GET", "/get/supremeai:zca:k")


async def test_upstash_get_remote_null_result_no_cache(aiohttp_factory):
    aiohttp_factory(response=_FakeResponse(200, {"result": None}))
    client = UpstashRedisClient(redis_cfg())
    assert await client.get("k") is None
    assert client._request_count == 0
    assert "k" not in client._local_cache


async def test_upstash_get_exception_returns_none(aiohttp_factory):
    aiohttp_factory(error=RuntimeError("boom"))
    client = UpstashRedisClient(redis_cfg())
    assert await client.get("k") is None


async def test_upstash_get_non_200_returns_none_without_counting(aiohttp_factory):
    aiohttp_factory(response=_FakeResponse(500))
    client = UpstashRedisClient(redis_cfg())
    assert await client.get("k") is None
    assert client._request_count == 0  # only successful results count toward limit


async def test_upstash_set_always_caches_local_rate_limited_true():
    client = UpstashRedisClient(redis_cfg())
    client._request_count = 95
    assert await client.set("k", "v", ttl=30) is True
    assert client._get_local("k") == "v"


async def test_upstash_set_disabled_reports_false_but_caches():
    client = UpstashRedisClient(small_config())
    assert await client.set("k", "v") is False
    assert client._get_local("k") == "v"


async def test_upstash_set_remote_200_true_with_ttl_param(aiohttp_factory):
    fake = aiohttp_factory(response=_FakeResponse(200))
    client = UpstashRedisClient(redis_cfg())
    assert await client.set("k", "v", ttl=30) is True
    assert client._request_count == 1
    _, _, extras = fake.sessions[0].calls[0]
    assert extras["json"] == ["supremeai:zca:k", "v"]
    assert extras["params"] == {"nex": "true", "ex": 30}  # quirk: "nex" not "nx"


async def test_upstash_set_exception_false(aiohttp_factory):
    aiohttp_factory(error=RuntimeError("boom"))
    client = UpstashRedisClient(redis_cfg())
    assert await client.set("k", "v") is False


async def test_upstash_delete_removes_local_and_remote_arms(aiohttp_factory):
    fake = aiohttp_factory(response=_FakeResponse(200))
    client = UpstashRedisClient(redis_cfg())
    client._set_local("k", "v")
    assert await client.delete("k") is True
    assert "k" not in client._local_cache
    assert fake.sessions[0].calls[0][1] == "/del"


async def test_upstash_delete_rate_limited_true_disabled_false():
    client = UpstashRedisClient(redis_cfg())
    client._request_count = 95
    assert await client.delete("k") is True
    disabled = UpstashRedisClient(small_config())
    assert await disabled.delete("k") is False


async def test_upstash_delete_exception_false(aiohttp_factory):
    aiohttp_factory(error=RuntimeError("boom"))
    client = UpstashRedisClient(redis_cfg())
    assert await client.delete("k") is False


async def test_upstash_get_json_roundtrip_and_bad_payload():
    client = UpstashRedisClient(redis_cfg())
    client._set_local("good", json.dumps({"a": 1}))
    client._set_local("bad", "not-json{")
    assert await client.get_json("good") == {"a": 1}
    assert await client.get_json("bad") is None
    assert await client.get_json("missing") is None


async def test_upstash_set_json_serializes(aiohttp_factory):
    aiohttp_factory(response=_FakeResponse(200))
    client = UpstashRedisClient(redis_cfg())
    assert await client.set_json("s", {"x": 1}, ttl=5) is True
    assert client._get_local("s") == json.dumps({"x": 1})


async def test_upstash_increment_rate_limited_uses_local():
    client = UpstashRedisClient(redis_cfg())
    client._set_local("c", "7", ttl=120)
    client._request_count = 95
    assert await client.increment("c", amount=3) == 10


async def test_upstash_increment_disabled_returns_amount():
    client = UpstashRedisClient(small_config())
    assert await client.increment("c", amount=5) == 5


async def test_upstash_increment_remote_result(aiohttp_factory):
    aiohttp_factory(response=_FakeResponse(200, {"result": 42}))
    client = UpstashRedisClient(redis_cfg())
    assert await client.increment("c") == 42
    assert client._get_local("c") == "42"


async def test_upstash_increment_non_200_and_exception(aiohttp_factory):
    aiohttp_factory(response=_FakeResponse(500))
    client = UpstashRedisClient(redis_cfg())
    assert await client.increment("c", amount=4) == 4
    aiohttp_factory(error=RuntimeError("boom"))
    client2 = UpstashRedisClient(redis_cfg())
    assert await client2.increment("c", amount=6) == 6


async def test_upstash_health_check_disabled_shape():
    client = UpstashRedisClient(small_config())
    status = await client.health_check()
    assert status["status"] == "disabled"
    assert status["connected"] is False
    assert status["daily_limit"] == 10000
    assert status["usage_percent"] == 0.0


async def test_upstash_health_check_ping_healthy(aiohttp_factory):
    fake = aiohttp_factory(response=_FakeResponse(200))
    client = UpstashRedisClient(redis_cfg())
    status = await client.health_check()
    assert status["connected"] is True
    assert status["status"] == "healthy"
    assert fake.sessions[0].calls[0][1] == "/ping"
    assert isinstance(status["latency_ms"], float)


async def test_upstash_health_check_ping_unhealthy(aiohttp_factory):
    aiohttp_factory(response=_FakeResponse(503))
    client = UpstashRedisClient(redis_cfg())
    status = await client.health_check()
    assert status["connected"] is False
    assert status["status"] == "unhealthy"


async def test_upstash_health_check_session_error(monkeypatch):
    client = UpstashRedisClient(redis_cfg())

    async def none_session():
        return None

    monkeypatch.setattr(client, "_get_session", none_session)
    status = await client.health_check()
    assert status["status"] == "session_error"


async def test_upstash_health_check_exception(aiohttp_factory):
    aiohttp_factory(error=RuntimeError("boom"))
    client = UpstashRedisClient(redis_cfg())
    status = await client.health_check()
    assert status["status"].startswith("error:")


async def test_upstash_close_with_and_without_session():
    client = UpstashRedisClient(redis_cfg())
    await client.close()  # no-op, no session
    session = FakeSession()
    client._redis = session
    await client.close()
    assert session.closed is True


# ───────────────────────── AdaptiveCircuitBreaker ─────────────────────────


def test_breaker_metrics_defaults_and_state_values():
    m = BreakerMetrics()
    assert m.total_requests == 0 and m.rejected_requests == 0
    assert m.adaptive_threshold_history == []
    assert AdaptiveCircuitBreakerState.CLOSED.value == "closed"
    assert AdaptiveCircuitBreakerState.HALF_OPEN.value == "half_open"
    assert AdaptiveCircuitBreakerState.ISOLATED.value == "isolated"


def make_breaker(**over) -> AdaptiveCircuitBreaker:
    return AdaptiveCircuitBreaker("svc", config=small_config(**over))


def test_breaker_init_defaults_and_overrides():
    b = make_breaker()
    assert b.failure_threshold == 5
    assert b.recovery_timeout == 30.0
    assert b.half_open_max_calls == 3
    assert b._adaptive_enabled is True
    assert b.state is AdaptiveCircuitBreakerState.CLOSED
    assert b.health_score == 100.0
    b2 = AdaptiveCircuitBreaker(
        "svc", config=small_config(), initial_failure_threshold=9, initial_recovery_timeout=12.0
    )
    assert b2.failure_threshold == 9 and b2.recovery_timeout == 12.0


@pytest.mark.parametrize(
    ("state", "available"),
    [
        (AdaptiveCircuitBreakerState.CLOSED, True),
        (AdaptiveCircuitBreakerState.DEGRADED, True),
        (AdaptiveCircuitBreakerState.HALF_OPEN, True),
        (AdaptiveCircuitBreakerState.FORCE_CLOSED, True),
        (AdaptiveCircuitBreakerState.OPEN, False),
        (AdaptiveCircuitBreakerState.ISOLATED, False),
    ],
)
def test_breaker_is_available_matrix(state, available):
    b = make_breaker()
    b.state = state
    assert b.is_available is available


async def test_breaker_acquire_force_closed_allows():
    b = make_breaker()
    b.force_close()
    assert await b.acquire() is True
    assert b.metrics.total_requests == 1


async def test_breaker_acquire_isolated_rejects():
    b = make_breaker()
    b.isolate()
    assert await b.acquire() is False
    assert b.metrics.rejected_requests == 1


async def test_breaker_acquire_open_then_half_open_after_timeout():
    b = make_breaker(CIRCUIT_BREAKER_COOLDOWN_SECONDS=30.0)
    b.force_open()
    assert await b.acquire() is False  # inside cooldown
    assert b.metrics.rejected_requests == 1
    b._state_entry_time = time.monotonic() - (b.recovery_timeout + 1)
    assert await b.acquire() is True  # transitions to HALF_OPEN
    assert b.state is AdaptiveCircuitBreakerState.HALF_OPEN
    assert b._half_open_calls == 0  # reset by _transition_to


async def test_breaker_acquire_half_open_call_cap():
    b = make_breaker()  # half_open_max_calls = 3
    b._transition_to(AdaptiveCircuitBreakerState.HALF_OPEN)
    assert await b.acquire() is True
    assert await b.acquire() is True
    assert await b.acquire() is True
    assert await b.acquire() is False  # 4th exceeds cap
    assert b._half_open_calls == 3


async def test_breaker_success_from_half_open_closes():
    b = make_breaker()
    b.force_open()
    b._state_entry_time = time.monotonic() - (b.recovery_timeout + 1)
    await b.acquire()  # -> HALF_OPEN
    await b.record_success()
    assert b.state is AdaptiveCircuitBreakerState.CLOSED


async def test_breaker_degraded_exit_requires_consecutive_successes():
    b = make_breaker(CIRCUIT_BREAKER_FAILURE_THRESHOLD=5)
    b._transition_to(AdaptiveCircuitBreakerState.DEGRADED)
    await b.record_success()
    assert b.state is AdaptiveCircuitBreakerState.DEGRADED  # 1 < 5 // 2
    await b.record_success()
    await b.record_success()
    assert b.state is AdaptiveCircuitBreakerState.CLOSED  # 3 >= 2


async def test_breaker_failure_from_half_open_reopens():
    b = make_breaker()
    b._transition_to(AdaptiveCircuitBreakerState.HALF_OPEN)
    await b.record_failure()
    assert b.state is AdaptiveCircuitBreakerState.OPEN


async def test_breaker_degraded_opens_at_threshold():
    b = make_breaker(CIRCUIT_BREAKER_FAILURE_THRESHOLD=2)
    b._transition_to(AdaptiveCircuitBreakerState.DEGRADED)
    await b.record_failure()
    assert b.state is AdaptiveCircuitBreakerState.DEGRADED  # 1 < 2
    await b.record_failure()
    assert b.state is AdaptiveCircuitBreakerState.OPEN  # 2 >= 2


async def test_breaker_closed_to_degraded_via_moderate_health():
    # 1st failure: health 100*0.95-15 = 80 (outside 40..70, threshold not reached)
    # 2nd failure: 80*0.95-15-2**1.5 ~= 58.2 -> inside band -> DEGRADED (threshold 2)
    b = make_breaker(CIRCUIT_BREAKER_FAILURE_THRESHOLD=2)
    await b.record_failure()
    assert b.state is AdaptiveCircuitBreakerState.CLOSED
    await b.record_failure()
    assert b.state is AdaptiveCircuitBreakerState.DEGRADED


async def test_breaker_closed_opens_directly_on_poor_health():
    b = make_breaker(CIRCUIT_BREAKER_FAILURE_THRESHOLD=1)
    await b.record_failure()  # health ~80, outside band -> OPEN
    assert b.state is AdaptiveCircuitBreakerState.OPEN


async def test_breaker_adaptive_disabled_skips_adjustment(monkeypatch):
    b = make_breaker(CIRCUIT_BREAKER_ADAPTIVE_ENABLED=False)
    calls: list[int] = []

    async def spy():
        calls.append(1)

    monkeypatch.setattr(b, "_adjust_threshold", spy)
    await b.record_failure()
    assert calls == []


async def test_breaker_adaptive_enabled_runs_adjustment(monkeypatch):
    b = make_breaker(CIRCUIT_BREAKER_ADAPTIVE_ENABLED=True)
    calls: list[int] = []

    async def spy():
        calls.append(1)

    monkeypatch.setattr(b, "_adjust_threshold", spy)
    await b.record_failure()
    assert calls == [1]


def test_breaker_outcome_history_trimmed_to_half():
    b = make_breaker()
    b._max_history_size = 10
    for i in range(11):
        b._record_outcome(i % 2 == 0)
    assert len(b._failure_history) == 5  # keep = 10 // 2


def test_breaker_health_score_arms():
    b = make_breaker()

    b._health_score = 100.0
    b._update_health_score(success=True, response_time=100.0)  # +10 fast bonus +5
    assert b.health_score == 100.0  # clamped at ceiling

    b._health_score = 50.0
    b._update_health_score(success=True, response_time=3000.0)  # +10 slow penalty -5
    assert b.health_score == 52.5  # 50*0.95 + 10 - 5

    b._health_score = 50.0
    b.metrics.consecutive_successes = 5
    b._update_health_score(success=True)  # +10 + consecutive bonus min(5,10)
    assert b.health_score == 62.5  # 50*0.95 + 10 + 5
    b.metrics.consecutive_successes = 0

    b._health_score = 50.0
    b.metrics.consecutive_failures = 3
    b._update_health_score(success=False)  # -15 - min(3**1.5, 30)
    assert b.health_score == 50.0 * 0.95 - 15 - min(3**1.5, 30)
    b.metrics.consecutive_failures = 0

    b._health_score = 1.0
    b._update_health_score(success=False)  # clamped at floor
    assert b.health_score == 0.0


async def test_breaker_adjust_threshold_insufficient_data():
    b = make_breaker()
    for i in range(19):
        b._record_outcome(False)
    await b._adjust_threshold()
    assert b.failure_threshold == 5  # unchanged, < 20 samples
    assert b.metrics.adaptive_threshold_history == []


async def test_breaker_adjust_threshold_bursty_increases():
    b = make_breaker()  # threshold 5, max 20
    for i in range(30):
        b._record_outcome(i % 10 == 9)  # success only on i%10==9 -> 90% failures
    await b._adjust_threshold()
    assert b.failure_threshold == 7  # +2
    assert b.metrics.adaptive_threshold_history == [7]


async def test_breaker_adjust_threshold_reliable_decreases():
    b = make_breaker(CIRCUIT_BREAKER_FAILURE_THRESHOLD=5)
    for i in range(31):
        b._record_outcome(i != 30)  # 30 successes, 1 failure -> rate 1/31
    await b._adjust_threshold()
    assert b.failure_threshold == 4  # -1


async def test_breaker_adjust_threshold_maintains_middle():
    b = make_breaker()
    for i in range(30):
        b._record_outcome(i % 3 != 0)  # 20 successes, 10 failures -> rate ~0.33
    await b._adjust_threshold()
    assert b.failure_threshold == 5  # unchanged
    assert b.metrics.adaptive_threshold_history == []


async def test_breaker_force_transitions_and_reset():
    b = make_breaker()
    b.force_close()
    assert b.state is AdaptiveCircuitBreakerState.FORCE_CLOSED
    b.force_open()
    assert b.state is AdaptiveCircuitBreakerState.OPEN
    b.isolate()
    assert b.state is AdaptiveCircuitBreakerState.ISOLATED
    assert b.metrics.state_changes == 3
    await b.record_failure()
    b.reset()
    assert b.state is AdaptiveCircuitBreakerState.CLOSED
    assert b.metrics.total_requests == 0
    assert b.health_score == 100.0
    assert b._failure_history == []


def test_breaker_get_status_shape():
    b = make_breaker()
    status = b.get_status()
    assert status["name"] == "svc"
    assert status["state"] == "closed"
    assert status["is_available"] is True
    assert status["metrics"]["failure_rate"] == 0.0
    assert status["adaptive"] == {
        "enabled": True,
        "threshold_adjustments": 0,
        "recent_threshold": [],
    }
    assert status["time_in_current_state_s"] >= 0


def test_breaker_get_status_reflects_adjustments():
    b = make_breaker()
    b.metrics.adaptive_threshold_history.extend([7, 9])
    status = b.get_status()
    assert status["adaptive"]["threshold_adjustments"] == 2
    assert status["adaptive"]["recent_threshold"] == [7, 9]


# ───────────────────────── PerformanceLearningEngine ─────────────────────────


def make_engine(**over) -> PerformanceLearningEngine:
    return PerformanceLearningEngine(
        small_config(
            LEARNING_AUTO_TUNING_INTERVAL=0,
            LEARNING_SAMPLE_WINDOW=10,
            LEARNING_CONFIDENCE_THRESHOLD=0.8,
            **over,
        )
    )


def test_learning_engine_registers_default_parameters():
    e = make_engine()
    expected = {
        "queue_max_concurrent",
        "queue_task_timeout",
        "cb_failure_threshold",
        "cb_cooldown_seconds",
        "rate_limit_burst_allowance",
    }
    assert set(e._parameters) == expected
    assert e._enabled is True


def test_learning_engine_disabled_flag():
    e = make_engine(LEARNING_ENABLED=False)
    assert e._enabled is False
    assert e._tuning_task is None


async def test_learning_engine_start_disabled_noop():
    e = make_engine(LEARNING_ENABLED=False)
    await e.start()
    assert e._tuning_task is None


async def test_learning_engine_start_idempotent():
    e = make_engine()
    await e.start()
    first = e._tuning_task
    assert first is not None and not first.done()
    await e.start()
    assert e._tuning_task is first
    await e.stop()


async def test_learning_engine_stop_cancels_running_task():
    e = make_engine()
    await e.start()
    await e.stop()
    assert e._tuning_task.done()


async def test_learning_engine_stop_no_task_noop():
    e = make_engine()
    await e.stop()  # no task started — must not raise
    assert e._tuning_task is None


async def test_learning_engine_stop_silences_propagating_cancellation(caplog):
    e = make_engine()
    started = asyncio.Event()

    async def raw_loop():
        started.set()
        await asyncio.sleep(3600)  # no internal catch — CancelledError propagates

    e._tuning_task = asyncio.create_task(raw_loop(), name="raw_tuner")
    await started.wait()
    with caplog.at_level("WARNING"):
        await e.stop()
    assert e._tuning_task.cancelled() is True
    assert any("Silenced" in r.message for r in caplog.records)


async def test_learning_engine_record_metric_disabled_ignored():
    e = make_engine(LEARNING_ENABLED=False)
    await e.record_metric("m", 1)
    assert "m" not in e._metric_samples


async def test_learning_engine_record_metric_trims_above_two_windows():
    e = make_engine()  # window 10 -> trim only fires above 20 samples, keeps last 10
    for i in range(25):
        await e.record_metric("m", i)
    samples = e._metric_samples["m"]
    assert len(samples) == 14  # trimmed once at 21, then 4 more appends
    assert samples[0][1] == 11


async def test_tuning_loop_breaks_on_cancellation(monkeypatch):
    e = make_engine()
    calls = {"n": 0}

    async def cycle():
        calls["n"] += 1
        raise asyncio.CancelledError()

    monkeypatch.setattr(e, "_run_tuning_cycle", cycle)
    task = asyncio.create_task(e._auto_tuning_loop())
    await asyncio.wait_for(task, timeout=5)
    assert calls["n"] == 1
    assert task.cancelled() is False  # loop broke cleanly


async def test_tuning_loop_survives_generic_error_then_breaks(monkeypatch):
    e = make_engine()
    calls = {"n": 0}

    async def cycle():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        raise asyncio.CancelledError()

    monkeypatch.setattr(e, "_run_tuning_cycle", cycle)
    task = asyncio.create_task(e._auto_tuning_loop())
    await asyncio.wait_for(task, timeout=5)
    assert calls["n"] == 2  # error was swallowed, loop continued


async def test_tuning_cycle_counts_and_contains_param_errors(monkeypatch):
    e = make_engine()
    ok = LearnedParameter(name="ok_param", current_value=5, min_value=1, max_value=10)
    bad = LearnedParameter(name="bad_param", current_value=5, min_value=1, max_value=10)
    e._parameters = {"ok": ok, "bad": bad}
    seen: list[str] = []

    async def optimize(name, param):
        seen.append(name)
        if name == "bad":
            raise RuntimeError("param boom")

    monkeypatch.setattr(e, "_optimize_parameter", optimize)
    await e._run_tuning_cycle()
    assert e._learning_cycle == 1
    assert sorted(seen) == ["bad", "ok"]  # bad param's error contained per-param


async def test_optimize_parameter_no_metrics_returns_early():
    e = make_engine()
    param = e._parameters["queue_max_concurrent"]
    await e._optimize_parameter("queue_max_concurrent", param)
    assert param.optimal_value is None
    assert param.confidence == 0.0


async def test_optimize_parameter_applies_suggestion():
    e = make_engine()
    param = LearnedParameter(
        name="queue_max_concurrent", current_value=100, min_value=1, max_value=200
    )
    e._metric_samples["queue_active_tasks"] = [(time.monotonic(), 95.0)]
    await e._optimize_parameter("queue_max_concurrent", param)
    assert param.optimal_value == 110.0  # utilization 0.95 > 0.9 -> +10%
    assert param.confidence == pytest.approx(0.1)
    assert param.last_updated is not None


async def test_optimize_parameter_clamps_to_bounds():
    e = make_engine()
    param = LearnedParameter(
        name="queue_max_concurrent", current_value=195, min_value=1, max_value=200
    )
    e._metric_samples["queue_active_tasks"] = [(time.monotonic(), 195.0)]
    await e._optimize_parameter("queue_max_concurrent", param)
    assert param.optimal_value == 200  # 195 + 19.5 clamped


async def test_optimize_parameter_clamped_equal_skips_update():
    e = make_engine()
    param = LearnedParameter(
        name="queue_max_concurrent", current_value=200, min_value=1, max_value=200
    )
    e._metric_samples["queue_active_tasks"] = [(time.monotonic(), 195.0)]
    await e._optimize_parameter("queue_max_concurrent", param)
    assert param.optimal_value is None  # clamped value == current -> no update


async def test_optimize_parameter_confidence_caps_at_one():
    e = make_engine()
    param = LearnedParameter(
        name="queue_max_concurrent", current_value=100, min_value=1, max_value=200
    )
    param.confidence = 0.97
    e._metric_samples["queue_active_tasks"] = [(time.monotonic(), 95.0)]
    await e._optimize_parameter("queue_max_concurrent", param)
    assert param.confidence == 1.0


async def test_optimize_parameter_zero_adjustment_leaves_param_untouched():
    e = make_engine()
    param = LearnedParameter(
        name="queue_max_concurrent", current_value=100, min_value=1, max_value=200
    )
    e._metric_samples["queue_active_tasks"] = [(time.monotonic(), 50.0)]  # util 0.5 -> adjustment 0
    await e._optimize_parameter("queue_max_concurrent", param)
    assert param.optimal_value is None
    assert param.confidence == 0.0
    assert param.last_updated is None


def test_learning_relevant_metrics_filtering():
    e = make_engine()
    e._metric_samples.update(
        {
            "queue_active_tasks": [(1.0, 5)],
            "circuit_breaker_trips": [(1.0, 2)],
            "unrelated_metric": [(1.0, 9)],
        }
    )
    got = e._get_relevant_metrics("queue_max_concurrent")
    assert set(got) == {"queue_active_tasks"}
    assert set(e._get_relevant_metrics("cb_failure_threshold")) == {"circuit_breaker_trips"}
    assert e._get_relevant_metrics("mystery_param") == {}


def test_performance_score_empty_metrics_neutral():
    e = make_engine()
    assert e._calculate_performance_score({}) == 50.0
    assert e._calculate_performance_score({"m": []}) == 50.0


def test_performance_score_keyword_arms():
    e = make_engine()
    now = time.monotonic()
    assert e._calculate_performance_score({"task_success": [(now, 100.0)]}) == 70.0
    assert e._calculate_performance_score({"task_error": [(now, 50.0)]}) == 35.0
    assert e._calculate_performance_score({"task_duration": [(now, 100.0)]}) == 60.0
    assert e._calculate_performance_score({"task_duration": [(now, 1000.0)]}) == 55.0
    assert e._calculate_performance_score({"task_duration": [(now, 3000.0)]}) == 45.0


def test_performance_score_clamped():
    e = make_engine()
    now = time.monotonic()
    high = {  # three success-keyword metrics x +20 -> 110 -> clamped
        "task_success": [(now, 100.0)],
        "task_complete": [(now, 100.0)],
        "user_satisfy_score": [(now, 100.0)],  # must literally contain "satisfy"
    }
    assert e._calculate_performance_score(high) == 100.0
    low = {  # three error-keyword metrics x -30 -> -40 -> clamped
        "task_error": [(now, 100.0)],
        "task_failure": [(now, 100.0)],
        "task_timeout": [(now, 100.0)],
    }
    assert e._calculate_performance_score(low) == 0.0


def test_adjustment_queue_utilization_arms():
    e = make_engine()
    now = time.monotonic()
    hi = LearnedParameter(
        name="queue_max_concurrent", current_value=100, min_value=1, max_value=200
    )
    assert e._calculate_adjustment(hi, {"queue_active_tasks": [(now, 95.0)]}, 50.0) == 10.0
    lo = LearnedParameter(
        name="queue_max_concurrent", current_value=100, min_value=1, max_value=200
    )
    assert e._calculate_adjustment(lo, {"queue_active_tasks": [(now, 10.0)]}, 50.0) == -5.0
    mid = LearnedParameter(
        name="queue_max_concurrent", current_value=100, min_value=1, max_value=200
    )
    assert e._calculate_adjustment(mid, {"queue_active_tasks": [(now, 50.0)]}, 50.0) == 0
    zero = LearnedParameter(name="queue_max_concurrent", current_value=0, min_value=0, max_value=10)
    assert e._calculate_adjustment(zero, {"queue_active_tasks": [(now, 5.0)]}, 50.0) == 0


def test_adjustment_timeout_branch_requires_non_queue_name():
    # quirk 5: "queue_task_timeout" contains "queue" -> queue branch -> always 0
    e = make_engine()
    now = time.monotonic()
    registered = LearnedParameter(
        name="queue_task_timeout", current_value=100.0, min_value=1, max_value=600
    )
    assert e._calculate_adjustment(registered, {"task_timeout_count": [(now, 0.2)]}, 50.0) == 0
    # a timeout-named parameter without "queue" reaches the timeout branch
    timeout_param = LearnedParameter(
        name="task_timeout", current_value=100.0, min_value=1, max_value=600
    )
    assert (
        e._calculate_adjustment(timeout_param, {"task_timeout_count": [(now, 0.2)]}, 50.0) == 20.0
    )
    assert e._calculate_adjustment(timeout_param, {"task_timeout_count": [(now, 0.01)]}, 50.0) == 0


def test_adjustment_threshold_and_other_arms():
    e = make_engine()
    now = time.monotonic()
    thr_up = LearnedParameter(
        name="cb_failure_threshold", current_value=5, min_value=2, max_value=20
    )
    assert e._calculate_adjustment(thr_up, {"circuit_breaker_trips": [(now, 2.0)]}, 50.0) == 1
    thr_down = LearnedParameter(
        name="cb_failure_threshold", current_value=5, min_value=2, max_value=20
    )
    assert e._calculate_adjustment(thr_down, {"circuit_breaker_trips": [(now, 0.05)]}, 50.0) == -1
    thr_mid = LearnedParameter(
        name="cb_failure_threshold", current_value=5, min_value=2, max_value=20
    )
    assert e._calculate_adjustment(thr_mid, {"circuit_breaker_trips": [(now, 0.5)]}, 50.0) == 0
    other = LearnedParameter(name="mystery_param", current_value=5, min_value=1, max_value=10)
    assert e._calculate_adjustment(other, {"anything": [(now, 9.0)]}, 50.0) == 0
    # threshold param whose metrics lack the "trips" keyword -> trips None -> 0
    thr_no_trips = LearnedParameter(
        name="cb_failure_threshold", current_value=5, min_value=2, max_value=20
    )
    assert (
        e._calculate_adjustment(thr_no_trips, {"circuit_breaker_recovery_time": [(now, 5.0)]}, 50.0)
        == 0
    )


def test_extract_avg_last_twenty_and_missing():
    e = make_engine()
    now = time.monotonic()
    samples = [(now, float(i)) for i in range(25)]
    assert e._extract_avg({"queue_active_tasks": samples}, "active_tasks") == 14.5
    assert e._extract_avg({"queue_active_tasks": samples}, "missing") is None
    assert e._extract_avg({}, "active_tasks") is None


def test_learning_status_shape():
    e = make_engine()
    e._learning_cycle = 3
    e._metric_samples["queue_active_tasks"].append((time.monotonic(), 4.0))
    status = e.get_learning_status()
    assert status["enabled"] is True
    assert status["learning_cycles"] == 3
    assert "queue_max_concurrent" in status["parameters_being_learned"]
    assert status["metrics_collected"] == {"queue_active_tasks": 1}
    entry = status["parameters_being_learned"]["queue_max_concurrent"]
    assert entry["range"] == (1, 20)


def test_learning_recommendations_filter_and_sort():
    e = make_engine()
    a = LearnedParameter(name="a", current_value=5, min_value=1, max_value=10)
    a.optimal_value, a.confidence = 7, 0.9
    b = LearnedParameter(name="b", current_value=5, min_value=1, max_value=10)
    b.optimal_value, b.confidence = 7, 0.5  # below threshold -> excluded
    c = LearnedParameter(name="c", current_value=5, min_value=1, max_value=10)
    c.optimal_value, c.confidence = 5, 0.9  # optimal == current -> excluded
    d = LearnedParameter(name="d", current_value=5, min_value=1, max_value=10)
    d.optimal_value, d.confidence = 9, 0.95  # highest confidence -> first
    e._parameters = {"a": a, "b": b, "c": c, "d": d}
    recs = e.get_recommendations()
    assert [r["parameter"] for r in recs] == ["d", "a"]
    assert recs[0]["recommended_value"] == 9
    assert recs[0]["confidence"] == 0.95


# ───────────────────────── ZeroCostOrchestrator ─────────────────────────


def make_orchestrator(**cfg_over) -> ZeroCostOrchestrator:
    return ZeroCostOrchestrator(small_config(**cfg_over))


async def test_orchestrator_init_composes_components():
    o = make_orchestrator()
    assert isinstance(o.queue, zc.InProcessAsyncQueue)
    assert isinstance(o.redis, UpstashRedisClient)
    assert isinstance(o.learning_engine, PerformanceLearningEngine)
    assert o._circuit_breakers == {}
    assert o._initialized is False
    assert o._start_time is None


async def test_orchestrator_initialize_and_idempotent():
    o = make_orchestrator(GRACEFUL_SHUTDOWN_TIMEOUT=1.0)
    await o.initialize()
    assert o._initialized is True
    assert o._start_time is not None
    assert o.queue._worker_task is not None
    o._start_time = 123.0  # marker for early-return check
    await o.initialize()  # already initialized -> warning + early return
    assert o._start_time == 123.0
    await o.shutdown()


async def test_orchestrator_initialize_redis_connected_branch(monkeypatch):
    o = make_orchestrator(GRACEFUL_SHUTDOWN_TIMEOUT=1.0)

    async def healthy():
        return {"connected": True, "latency_ms": 2.5, "status": "healthy"}

    monkeypatch.setattr(o.redis, "health_check", healthy)
    await o.initialize()
    assert o._initialized is True
    await o.shutdown()


async def test_orchestrator_shutdown_stops_everything():
    o = make_orchestrator(GRACEFUL_SHUTDOWN_TIMEOUT=1.0)
    await o.initialize()
    await o.shutdown()
    assert o._initialized is False
    assert o.queue._worker_task.done()
    assert o.learning_engine._tuning_task.done()


async def test_get_circuit_breaker_caches_and_forwards_kwargs():
    o = make_orchestrator()
    b1 = o.get_circuit_breaker("svc", initial_failure_threshold=9)
    assert b1.failure_threshold == 9
    b2 = o.get_circuit_breaker("svc")
    assert b2 is b1
    assert o.get_circuit_breaker("other") is not b1


async def test_execute_with_resilience_injects_args_kwargs_pairs():
    # quirk 6: the **kw coroutine receives the (args, kwargs) pairs as keywords
    o = make_orchestrator(GRACEFUL_SHUTDOWN_TIMEOUT=1.0)
    await o.initialize()

    async def flexible(**kw):
        return ("ok", kw["args"], kw["kwargs"])

    result = await o.execute_with_resilience(flexible, 2, b=3)
    assert result == ("ok", (2,), {"b": 3})
    samples = o.learning_engine._metric_samples
    assert samples["task_success"][-1][1] == 1
    assert "task_duration" in samples
    await o.shutdown()


async def test_execute_with_resilience_records_breaker_success():
    o = make_orchestrator(GRACEFUL_SHUTDOWN_TIMEOUT=1.0)
    await o.initialize()
    breaker = o.get_circuit_breaker("svc")
    breaker.force_close()  # always allows

    async def flexible(**kw):
        return "ok"

    assert await o.execute_with_resilience(flexible, circuit_breaker="svc") == "ok"
    assert breaker.metrics.successful_requests == 1
    assert breaker.metrics.last_success_time is not None
    await o.shutdown()


async def test_execute_with_resilience_rejected_uses_fallback():
    o = make_orchestrator(GRACEFUL_SHUTDOWN_TIMEOUT=1.0)
    await o.initialize()
    o.get_circuit_breaker("svc").force_open()
    ran = {"coro": False, "fallback": False}

    async def work(**kw):
        ran["coro"] = True
        return "should-not"

    async def fallback():
        ran["fallback"] = True
        return "fallback-result"

    result = await o.execute_with_resilience(work, circuit_breaker="svc", fallback=fallback)
    assert result == "fallback-result"
    assert ran == {"coro": False, "fallback": True}
    assert "task_success" not in o.learning_engine._metric_samples
    await o.shutdown()


async def test_execute_with_resilience_rejected_without_fallback_raises():
    o = make_orchestrator(GRACEFUL_SHUTDOWN_TIMEOUT=1.0)
    await o.initialize()
    o.get_circuit_breaker("svc").force_open()

    async def work(**kw):
        return "x"

    with pytest.raises(zc.CircuitBreakerOpenError, match="circuit breaker 'svc' is open"):
        await o.execute_with_resilience(work, circuit_breaker="svc")
    await o.shutdown()


async def test_execute_with_resilience_task_failure_with_fallback():
    o = make_orchestrator(GRACEFUL_SHUTDOWN_TIMEOUT=1.0)
    await o.initialize()
    breaker = o.get_circuit_breaker("svc")

    async def work(**kw):
        raise zc.TaskFailedError("nope")

    async def fallback():
        return "salvaged"

    result = await o.execute_with_resilience(work, circuit_breaker="svc", fallback=fallback)
    assert result == "salvaged"
    assert breaker.metrics.failed_requests == 1
    assert "task_failure" in o.learning_engine._metric_samples
    await o.shutdown()


async def test_execute_with_resilience_fallback_failure_reraises_original():
    o = make_orchestrator(GRACEFUL_SHUTDOWN_TIMEOUT=1.0)
    await o.initialize()

    async def work(**kw):
        raise zc.TaskFailedError("original")

    async def fallback():
        raise RuntimeError("fallback boom")

    with pytest.raises(zc.TaskFailedError, match="original"):
        await o.execute_with_resilience(work, fallback=fallback)
    await o.shutdown()


async def test_execute_with_resilience_task_failure_without_fallback():
    o = make_orchestrator(GRACEFUL_SHUTDOWN_TIMEOUT=1.0)
    await o.initialize()

    async def work(**kw):
        raise zc.TaskFailedError("nope")

    with pytest.raises(zc.TaskFailedError):
        await o.execute_with_resilience(work)
    await o.shutdown()


async def test_execute_with_resilience_zero_arg_coro_breaks_on_injection():
    # quirk 6 manifestation: a zero-arg coroutine cannot absorb the injected
    # args/kwargs keyword pairs -> TypeError inside the worker (after retries)
    # is wrapped into TaskFailedError, then re-raised by the TaskFailedError arm
    o = make_orchestrator(GRACEFUL_SHUTDOWN_TIMEOUT=1.0)
    await o.initialize()
    breaker = o.get_circuit_breaker("svc")

    async def work():
        return "x"

    with pytest.raises(zc.TaskFailedError, match="args"):
        await o.execute_with_resilience(work, circuit_breaker="svc")
    assert breaker.metrics.failed_requests == 1
    assert "task_failure" in o.learning_engine._metric_samples
    await o.shutdown()


async def test_execute_with_resilience_timeout_hits_generic_error_arm():
    # a non-TaskFailedError failure (TaskTimeoutError) flows through the generic
    # `except Exception` arm: breaker failure recorded + task_error metric + raise
    o = make_orchestrator(GRACEFUL_SHUTDOWN_TIMEOUT=1.0)
    await o.initialize()
    breaker = o.get_circuit_breaker("svc")

    async def flexible_slow(**kw):
        await asyncio.sleep(1.0)
        return "late"

    with pytest.raises(zc.TaskTimeoutError):
        await o.execute_with_resilience(flexible_slow, timeout=0.05, circuit_breaker="svc")
    assert breaker.metrics.failed_requests == 1
    assert "task_error" in o.learning_engine._metric_samples
    await o.shutdown()


async def test_execute_with_resilience_timeout_without_breaker():
    # generic arm with breaker=None (TaskTimeoutError is not TaskFailedError):
    # no record_failure call, task_error metric still recorded, error re-raised
    o = make_orchestrator(GRACEFUL_SHUTDOWN_TIMEOUT=1.0)
    await o.initialize()

    async def flexible_slow(**kw):
        await asyncio.sleep(1.0)
        return "late"

    with pytest.raises(zc.TaskTimeoutError):
        await o.execute_with_resilience(flexible_slow, timeout=0.05)
    assert "task_error" in o.learning_engine._metric_samples
    await o.shutdown()


async def test_orchestrator_health_check_shapes():
    o = make_orchestrator(GRACEFUL_SHUTDOWN_TIMEOUT=1.0)
    status = await o.health_check()
    assert status["status"] == "initializing"  # quirk 4: uptime is raw monotonic here
    assert status["components"]["queue"]["status"] == "stopped"
    o.get_circuit_breaker("svc")
    await o.initialize()
    status = await o.health_check()
    assert status["status"] == "healthy"
    assert status["components"]["queue"]["status"] == "running"
    assert "svc" in status["components"]["circuit_breakers"]
    assert status["config_summary"]["max_concurrent"] == 2
    await o.shutdown()


async def test_orchestrator_recommendations_delegate(monkeypatch):
    o = make_orchestrator()
    sentinel = [{"parameter": "x", "recommended_value": 42}]
    monkeypatch.setattr(o.learning_engine, "get_recommendations", lambda: sentinel)
    assert o.get_optimization_recommendations() is sentinel


# ───────────────────────── Module globals + lifespan ─────────────────────────


def test_get_orchestrator_global_singleton(monkeypatch):
    monkeypatch.setattr(zc, "_global_orchestrator", None)
    monkeypatch.setattr(zc, "get_zero_cost_config", lambda: small_config())
    o1 = zc.get_orchestrator()
    o2 = zc.get_orchestrator()
    assert o1 is o2
    assert isinstance(o1, ZeroCostOrchestrator)


async def test_lifespan_manager_startup_and_shutdown(monkeypatch):
    monkeypatch.setattr(zc, "_global_orchestrator", None)
    monkeypatch.setattr(
        zc, "get_zero_cost_config", lambda: small_config(GRACEFUL_SHUTDOWN_TIMEOUT=1.0)
    )
    app = types.SimpleNamespace(state=types.SimpleNamespace())
    async with zc.lifespan_manager(app):
        o = zc.get_orchestrator()
        assert app.state.zero_cost_orchestrator is o
        assert o._initialized is True
    assert o._initialized is False
    assert o.queue._worker_task.done()


def test_module_exports_all_present():
    for name in zc.__all__:
        assert hasattr(zc, name), f"missing export: {name}"
