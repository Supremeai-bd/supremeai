# বাংলা মন্তব্য: Issue #2759 — degraded-mode + circuit-breaker + failover contract টেস্ট।
"""Contract tests for the resilience plane (issue #2759).

বাংলা মন্তব্য: এই ফাইলটি `core/resilience/circuit_breaker.py`,
`core/resilience/circuit_breaker_manager.py`, এবং `core/degraded_mode.py`-
এর মিলিত আচরণ যাচাই করে:

  1. ডাউনস্ট্রিম সার্ভিস ডাউন → degraded mode সক্রিয়
  2. সার্কিট ব্রেকার OPEN → fallback চেইন ট্রিগার
  3. Failover: primary ডাউন → secondary কল পিক আপ
  4. Recovery: সার্কিট ব্রেকার HALF_OPEN সাফল্য → CLOSED (primary ফিরে আসে)

Rule #64: সব কিছু fully mocked — কোনো রিয়েল নেটওয়ার্ক/DB/LLM কল নেই।
Rule #6: বাংলা কমেন্ট + Given-When-Then docstring প্রতিটি টেস্টে।
Rule #61/#66: happy + sad + boundary কভার করা হয়েছে।
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.degraded_mode import (
    DEFAULT_IN_MEMORY_MAXLEN,
    InMemoryDocumentStore,
    InMemoryRing,
    SQLiteFallbackDisabledError,
    allow_db_degradation,
    db_degraded,
    is_production,
    is_test_context,
    reset_warned_features,
    sqlite_fallback_allowed,
)
from core.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitBreakerState,
)
from core.resilience.circuit_breaker_manager import (
    CircuitBreakerManager,
    get_circuit_breaker_manager,
)

# ---------------------------------------------------------------------------
# বাংলা মন্তব্য: হেল্পার — সিঙ্গেলটন ম্যানেজার রিসেট করে যাতে টেস্ট আইসোলেটেড থাকে।
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_manager_singleton():
    """প্রতিটি টেস্টের আগে/পরে CircuitBreakerManager singleton reset।"""
    # বাংলা: সিঙ্গেলটন _instance পরিষ্কার করে নতুন করে তৈরি হতে দিচ্ছি।
    CircuitBreakerManager._instance = None
    yield
    CircuitBreakerManager._instance = None


# ---------------------------------------------------------------------------
# 1. Degraded-mode activation contract (core/degraded_mode.py)
# ---------------------------------------------------------------------------


class TestDegradedModeActivation:
    """ডাউনস্ট্রিম সার্ভিস ডাউন হলে degraded-mode চালু হয় কিনা।"""

    def test_dev_env_allows_sqlite_fallback(self, monkeypatch):
        """Given ENV=test (non-production), When sqlite_fallback_allowed called,
        Then True ফেরত দেয় — dev/test-এ fallback চালু।"""
        # Given: env=test, production flag অফ
        monkeypatch.delenv("SUPABASE_ALLOW_DB_DEGRADATION", raising=False)
        # বাংলা: _effective_env settings.env আগে পড়ে — patch করছি।
        monkeypatch.setattr("core.degraded_mode._effective_env", lambda: "test")
        # When: feature fallback চেক
        allowed = sqlite_fallback_allowed("test_feature")
        # Then: dev/test-এ True
        assert allowed is True

    def test_production_blocks_sqlite_fallback_unconditionally(self, monkeypatch):
        """Given ENV=production + degradation flag=True, When sqlite_fallback_allowed,
        Then False — Wave 0.1 hard-fail (#1224): prod-এ SQLite fallback নিষিদ্ধ।"""
        # Given: production env + escape-hatch flag on
        monkeypatch.setenv("SUPABASE_ALLOW_DB_DEGRADATION", "true")
        # বাংলা: settings.env cached থাকে বলে _effective_env directly patch করা হচ্ছে।
        monkeypatch.setattr("core.degraded_mode._effective_env", lambda: "production")
        reset_warned_features()
        # When: feature fallback চেক
        allowed = sqlite_fallback_allowed("prod_feature")
        # Then: hard-fail — SQLite refused
        assert allowed is False

    def test_db_degraded_only_when_prod_flag_and_no_pooler(self, monkeypatch):
        """Given production+flag+no pooler URL, When db_degraded(), Then True —
        degraded REST-only boot শর্ত পূরণ।"""
        # Given
        monkeypatch.setenv("SUPABASE_ALLOW_DB_DEGRADATION", "true")
        monkeypatch.setattr("core.degraded_mode._effective_env", lambda: "production")
        monkeypatch.delenv("SUPABASE_DATABASE_URL_POOLER", raising=False)
        # When
        result = db_degraded()
        # Then
        assert result is True

    def test_db_degraded_false_when_pooler_present(self, monkeypatch):
        """Given production+flag+pooler URL set, When db_degraded(), Then False —
        pooler থাকলে degraded REST-only boot নয়।"""
        # Given
        monkeypatch.setenv("SUPABASE_ALLOW_DB_DEGRADATION", "true")
        monkeypatch.setattr("core.degraded_mode._effective_env", lambda: "production")
        monkeypatch.setenv("SUPABASE_DATABASE_URL_POOLER", "postgresql://pooler.example/db")
        # When
        result = db_degraded()
        # Then
        assert result is False

    def test_is_production_recognizes_prod_alias(self, monkeypatch):
        """Given ENV=prod, When is_production(), Then True — শর্ট-হ্যান্ড অ্যালিয়াস।"""
        monkeypatch.setattr("core.degraded_mode._effective_env", lambda: "prod")
        assert is_production() is True

    def test_is_test_context_true_under_pytest(self, monkeypatch):
        """Given pytest loaded + ENV=test, When is_test_context(), Then True।
        Boundary: production env-এ টেস্ট না হয়।"""
        monkeypatch.setattr("core.degraded_mode._effective_env", lambda: "test")
        assert is_test_context() is True

    def test_is_test_context_false_in_production(self, monkeypatch):
        """Given ENV=production, When is_test_context(), Then False —
        production সবসময় test context হতে পারে না।"""
        monkeypatch.setattr("core.degraded_mode._effective_env", lambda: "production")
        assert is_test_context() is False

    def test_allow_db_degradation_recognizes_legacy_alias(self, monkeypatch):
        """Given legacy ALLOW_DB_DEGRADATION=true, When allow_db_degradation(),
        Then True — backward-compat alias গ্রহণযোগ্য।"""
        monkeypatch.delenv("SUPABASE_ALLOW_DB_DEGRADATION", raising=False)
        monkeypatch.setenv("ALLOW_DB_DEGRADATION", "true")
        assert allow_db_degradation() is True

    def test_allow_db_degradation_false_when_unset(self, monkeypatch):
        """Given no flag set, When allow_db_degradation(), Then False।"""
        monkeypatch.delenv("SUPABASE_ALLOW_DB_DEGRADATION", raising=False)
        monkeypatch.delenv("ALLOW_DB_DEGRADATION", raising=False)
        assert allow_db_degradation() is False


class TestSQLiteFallbackFailClosed:
    """require_sqlite_allowed → SQLiteFallbackDisabledError in production."""

    def test_require_sqlite_allowed_raises_in_production(self, monkeypatch):
        """Given ENV=production, When require_sqlite_allowed called,
        Then SQLiteFallbackDisabledError raised — fail-closed।"""
        monkeypatch.setattr("core.degraded_mode._effective_env", lambda: "production")
        reset_warned_features()
        from core.degraded_mode import require_sqlite_allowed

        with pytest.raises(SQLiteFallbackDisabledError):
            require_sqlite_allowed("risky_feature")

    def test_require_sqlite_allowed_passes_in_dev(self, monkeypatch):
        """Given ENV=test, When require_sqlite_allowed called, Then no exception।"""
        monkeypatch.setattr("core.degraded_mode._effective_env", lambda: "test")
        from core.degraded_mode import require_sqlite_allowed

        # বাংলা: dev/test-এ কোনো exception না রেইজ হলেই পাস
        require_sqlite_allowed("safe_feature")


class TestInMemoryRingDegradedBuffer:
    """InMemoryRing — bounded FIFO event buffer for degraded mode (no DB)."""

    def test_append_and_snapshot_roundtrip(self):
        """Given empty ring, When 3 items appended, Then snapshot returns them in order।"""
        # Given
        ring = InMemoryRing(maxlen=10)
        # When
        for i in range(3):
            ring.append({"event": i})
        # Then
        snap = ring.snapshot()
        assert [e["event"] for e in snap] == [0, 1, 2]
        assert len(ring) == 3

    def test_maxlen_eviction_oldest_first(self):
        """Given ring maxlen=3, When 5 items appended, Then only last 3 survive।
        Boundary: FIFO eviction at exactly maxlen cap।"""
        # Given
        ring = InMemoryRing(maxlen=3)
        # When
        for i in range(5):
            ring.append(i)
        # Then
        snap = ring.snapshot()
        assert snap == [2, 3, 4]
        assert len(ring) == 3

    def test_remove_matching_drops_by_predicate(self):
        """Given ring with mixed items, When remove_matching(predicate),
        Then only matching items dropped, count returned।"""
        # Given
        ring = InMemoryRing(maxlen=10)
        ring.append({"kind": "error", "id": 1})
        ring.append({"kind": "info", "id": 2})
        ring.append({"kind": "error", "id": 3})
        # When
        removed = ring.remove_matching(lambda x: x.get("kind") == "error")
        # Then
        assert removed == 2
        assert ring.snapshot() == [{"kind": "info", "id": 2}]

    def test_default_maxlen_is_5000(self):
        """Given default-constructed ring, When len checked after overflow,
        Then capped at DEFAULT_IN_MEMORY_MAXLEN।"""
        # Given
        ring = InMemoryRing()
        # When: maxlen+5 items
        for i in range(DEFAULT_IN_MEMORY_MAXLEN + 5):
            ring.append(i)
        # Then
        assert len(ring) == DEFAULT_IN_MEMORY_MAXLEN


class TestInMemoryDocumentStoreDegraded:
    """Firestore-shaped InMemoryDocumentStore for prod-no-DB degraded mode."""

    def test_set_get_roundtrip(self):
        """Given store, When document set then get, Then data round-trips।"""
        # Given
        store = InMemoryDocumentStore()
        # When
        store.collection("tasks").document("t1").set({"status": "running"})
        snap = store.collection("tasks").document("t1").get()
        # Then
        assert snap.exists is True
        assert snap.to_dict() == {"status": "running"}

    def test_get_missing_returns_not_exists(self):
        """Given empty store, When document get, Then exists=False, dict={}।"""
        store = InMemoryDocumentStore()
        snap = store.collection("tasks").document("missing").get()
        assert snap.exists is False
        assert snap.to_dict() == {}

    def test_where_filter(self):
        """Given store with 3 docs, When where('status','==','ok'), Then only
        matching docs returned।"""
        # Given
        store = InMemoryDocumentStore()
        store.collection("jobs").document("j1").set({"status": "ok"})
        store.collection("jobs").document("j2").set({"status": "fail"})
        store.collection("jobs").document("j3").set({"status": "ok"})
        # When
        docs = store.collection("jobs").where("status", "==", "ok").stream()
        # Then
        ids = {d.id for d in docs}
        assert ids == {"j1", "j3"}

    def test_fifo_eviction_on_overflow(self):
        """Given store max_docs=2, When 3 docs added to same collection,
        Then oldest doc evicted। Boundary: at-max-cap eviction।"""
        # Given
        store = InMemoryDocumentStore(max_docs=2)
        col = store.collection("limited")
        # When
        col.document("a").set({"v": 1})
        col.document("b").set({"v": 2})
        col.document("c").set({"v": 3})  # overflow → "a" evicted
        # Then
        assert col.document("a").get().exists is False
        assert col.document("b").get().exists is True
        assert col.document("c").get().exists is True

    def test_update_merges_existing_doc(self):
        """Given existing doc, When update called, Then fields merged, not replaced।"""
        store = InMemoryDocumentStore()
        store.collection("tasks").document("t1").set({"status": "pending", "owner": "x"})
        store.collection("tasks").document("t1").update({"status": "done"})
        snap = store.collection("tasks").document("t1").get()
        assert snap.to_dict() == {"status": "done", "owner": "x"}

    def test_delete_removes_doc(self):
        """Given existing doc, When delete, Then subsequent get → exists=False।"""
        store = InMemoryDocumentStore()
        store.collection("tasks").document("t1").set({"status": "ok"})
        store.collection("tasks").document("t1").delete()
        assert store.collection("tasks").document("t1").get().exists is False


# ---------------------------------------------------------------------------
# 2. Circuit-breaker open → fallback chain triggers
# ---------------------------------------------------------------------------


class TestCircuitBreakerFallbackChain:
    """সার্কিট ব্রেকার OPEN হলে fallback চেইন ট্রিগার হয় কিনা।"""

    def test_threshold_consecutive_failures_opens_circuit(self):
        """Given CB threshold=3, When 3 consecutive failures, Then state=OPEN।"""
        # Given
        cb = CircuitBreaker("primary_svc", failure_threshold=3, recovery_timeout=30)
        # When
        for _ in range(3):
            with pytest.raises(ValueError):
                cb.call(lambda: (_ for _ in ()).throw(ValueError("down")))
        # Then
        assert cb.state == CircuitBreakerState.OPEN
        assert cb.is_open is True

    def test_open_circuit_rejects_next_request_fast(self):
        """Given OPEN circuit, When next call attempted, Then CircuitBreakerOpenError
        raised WITHOUT invoking the wrapped function।"""
        # Given
        cb = CircuitBreaker("svc", failure_threshold=1, recovery_timeout=30)
        sentinel = MagicMock()

        def fail():
            sentinel()
            raise ValueError("down")

        with pytest.raises(ValueError):
            cb.call(fail)
        assert cb.state == CircuitBreakerState.OPEN

        # When: next call should fail-fast
        sentinel.reset_mock()
        with pytest.raises(CircuitBreakerOpenError):
            cb.call(sentinel)
        # Then: underlying function NEVER invoked
        sentinel.assert_not_called()

    def test_fallback_chain_invoked_when_primary_open(self):
        """Given primary CB OPEN, When call_with_fallback invoked, Then fallback
        function executes instead of primary — graceful degradation।"""
        # Given
        cb = CircuitBreaker("primary", failure_threshold=1, recovery_timeout=30)
        primary_call = MagicMock(side_effect=ValueError("primary down"))
        fallback_call = MagicMock(return_value="fallback-result")

        def call_with_fallback(primary, fallback):
            # বাংলা: CB ফেইল-ক্লোজড — OPEN হলে primary না ডেকে fallback চালায়।
            try:
                return cb.call(primary)
            except CircuitBreakerOpenError:
                return fallback()

        # When: trip the breaker
        with pytest.raises(ValueError):
            call_with_fallback(primary_call, fallback_call)
        assert cb.state == CircuitBreakerState.OPEN

        # When: next call → fallback executes
        result = call_with_fallback(primary_call, fallback_call)

        # Then
        assert result == "fallback-result"
        # primary_call শুধুমাত্র প্রথমবারই ডাকা হয়েছে (tripped করার সময়); OPEN হওয়ার পরে নয়
        assert primary_call.call_count == 1
        assert fallback_call.call_count == 1

    def test_threshold_minus_one_stays_closed(self):
        """Given CB threshold=3, When only 2 failures, Then state stays CLOSED।
        Boundary: threshold-1 এখনো OPEN হয় না।"""
        cb = CircuitBreaker("svc", failure_threshold=3, recovery_timeout=30)
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(lambda: (_ for _ in ()).throw(ValueError("down")))
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 2

    def test_success_resets_failure_count(self):
        """Given 2 failures (below threshold), When one success, Then
        failure_count reset to 0।"""
        cb = CircuitBreaker("svc", failure_threshold=3, recovery_timeout=30)
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(lambda: (_ for _ in ()).throw(ValueError("down")))
        assert cb.failure_count == 2
        # When: success
        cb.call(lambda: "ok")
        # Then
        assert cb.failure_count == 0
        assert cb.success_count == 1
        assert cb.state == CircuitBreakerState.CLOSED


# ---------------------------------------------------------------------------
# 3. Failover: primary down → secondary picks up
# ---------------------------------------------------------------------------


class TestFailoverPrimaryToSecondary:
    """Primary down → secondary কল পিক আপ করে কিনা তার contract টেস্ট।"""

    @pytest.mark.asyncio
    async def test_failover_to_secondary_on_primary_error(self):
        """Given primary CB OPEN after first failure, When failover_chain called
        again, Then secondary is invoked and its result returned।"""
        # Given: primary CB + secondary function
        cb = CircuitBreaker("primary", failure_threshold=1, recovery_timeout=30)

        async def primary():
            raise ConnectionError("primary unreachable")

        async def secondary():
            return "secondary-ok"

        async def failover_chain():
            # বাংলা: CB ফেইল-ক্লোজড — OPEN হলে primary না ডেকে fallback চালায়।
            try:
                return await cb.acall(primary)
            except (CircuitBreakerOpenError, ConnectionError):
                return await secondary()

        # When: first call → primary raises ConnectionError → chain catches it
        result_first = await failover_chain()
        # Then: chain returns secondary result; CB now OPEN
        assert result_first == "secondary-ok"
        assert cb.state == CircuitBreakerState.OPEN

        # When: second call → CB OPEN → CircuitBreakerOpenError → secondary
        result_second = await failover_chain()
        # Then: secondary still serves
        assert result_second == "secondary-ok"

    @pytest.mark.asyncio
    async def test_primary_failure_propagates_without_chain(self):
        """Given primary fails, When cb.acall called directly (no fallback chain),
        Then ConnectionError raised and CB opens — sad path।"""
        cb = CircuitBreaker("primary", failure_threshold=1, recovery_timeout=30)

        async def primary():
            raise ConnectionError("primary unreachable")

        # When: direct call — no chain to catch
        with pytest.raises(ConnectionError):
            await cb.acall(primary)
        # Then
        assert cb.state == CircuitBreakerState.OPEN

    @pytest.mark.asyncio
    async def test_failover_skipped_when_primary_healthy(self):
        """Given healthy primary, When failover_chain called, Then primary used,
        secondary NOT called।"""
        # Given
        cb = CircuitBreaker("primary", failure_threshold=3, recovery_timeout=30)
        primary_calls = MagicMock()
        secondary_calls = MagicMock()

        async def primary():
            primary_calls()
            return "primary-ok"

        async def secondary():
            secondary_calls()
            return "secondary-ok"

        async def failover_chain():
            try:
                return await cb.acall(primary)
            except (CircuitBreakerOpenError, ConnectionError):
                return await secondary()

        # When
        result = await failover_chain()
        # Then
        assert result == "primary-ok"
        primary_calls.assert_called_once()
        secondary_calls.assert_not_called()

    @pytest.mark.asyncio
    async def test_failover_to_tertiary_when_secondary_also_fails(self):
        """Given primary+secondary both fail, When 3-tier failover chain called,
        Then tertiary result returned — deep fallback।"""
        # Given
        cb_primary = CircuitBreaker("primary", failure_threshold=1, recovery_timeout=30)
        cb_secondary = CircuitBreaker("secondary", failure_threshold=1, recovery_timeout=30)

        async def primary():
            raise ConnectionError("p-down")

        async def secondary():
            raise ConnectionError("s-down")

        async def tertiary():
            return "tertiary-ok"

        async def chain():
            # বাংলা: তিন-স্তরের fallback চেইন। প্রতিটি স্তরের CB আলাদা।
            try:
                return await cb_primary.acall(primary)
            except (CircuitBreakerOpenError, ConnectionError):
                pass
            try:
                return await cb_secondary.acall(secondary)
            except (CircuitBreakerOpenError, ConnectionError):
                return await tertiary()

        # When: first call → primary fails, secondary fails, tertiary ok
        result = await chain()
        # Then: tertiary picked up
        assert result == "tertiary-ok"
        # Both CBs now OPEN (each tripped once)
        assert cb_primary.state == CircuitBreakerState.OPEN
        assert cb_secondary.state == CircuitBreakerState.OPEN

        # When: second call → both CBs OPEN → tertiary
        result2 = await chain()
        assert result2 == "tertiary-ok"


# ---------------------------------------------------------------------------
# 4. Recovery: circuit breaker closes → primary resumes
# ---------------------------------------------------------------------------


class TestCircuitBreakerRecovery:
    """সার্কিট ব্রেকার recovery: HALF_OPEN → CLOSED → primary ফিরে আসে।"""

    @pytest.mark.asyncio
    async def test_half_open_probe_success_closes_circuit(self):
        """Given OPEN circuit after timeout, When probe call succeeds, Then
        state transitions OPEN→HALF_OPEN→CLOSED, primary resumes।"""
        # Given: CB with instant recovery (timeout=0)
        cb = CircuitBreaker("svc", failure_threshold=1, recovery_timeout=0)
        with pytest.raises(ValueError):
            await cb.acall(self._async_raise(ValueError("down")))
        assert cb.state == CircuitBreakerState.OPEN

        # When: allow time for recovery window
        await asyncio.sleep(0.01)
        result = await cb.acall(self._async_return("recovered"))

        # Then
        assert result == "recovered"
        assert cb.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_probe_failure_reopens_circuit(self):
        """Given OPEN circuit after timeout, When probe call FAILS, Then state
        goes HALF_OPEN→OPEN again (recovery test failed)।"""
        cb = CircuitBreaker("svc", failure_threshold=1, recovery_timeout=0)
        with pytest.raises(ValueError):
            await cb.acall(self._async_raise(ValueError("down")))
        assert cb.state == CircuitBreakerState.OPEN

        await asyncio.sleep(0.01)
        # When: probe fails
        with pytest.raises(ValueError):
            await cb.acall(self._async_raise(ValueError("still-down")))

        # Then: re-OPEN
        assert cb.state == CircuitBreakerState.OPEN

    @pytest.mark.asyncio
    async def test_primary_resumes_after_recovery(self):
        """Given primary CB recovered to CLOSED, When failover_chain called,
        Then primary used again (not fallback)।"""
        # Given
        cb = CircuitBreaker("primary", failure_threshold=1, recovery_timeout=0)
        primary_count = 0
        secondary_count = 0

        async def primary():
            nonlocal primary_count
            primary_count += 1
            if primary_count == 1:
                raise ConnectionError("transient")
            return "primary-recovered"

        async def secondary():
            nonlocal secondary_count
            secondary_count += 1
            return "secondary-ok"

        async def chain():
            try:
                return await cb.acall(primary)
            except (CircuitBreakerOpenError, ConnectionError):
                return await secondary()

        # When: first call → primary fails, chain catches → secondary serves
        result_first = await chain()
        assert result_first == "secondary-ok"
        assert cb.state == CircuitBreakerState.OPEN
        assert secondary_count == 1

        # When: wait for recovery, then call succeeds on primary
        await asyncio.sleep(0.01)
        result = await chain()

        # Then: primary was used (recovered), result is primary's
        assert result == "primary-recovered"
        assert cb.state == CircuitBreakerState.CLOSED
        assert secondary_count == 1  # no new secondary calls

    def test_force_close_immediately_resumes_traffic(self):
        """Given OPEN circuit, When force_close called, Then state=CLOSED
        immediately, requests pass through।"""
        cb = CircuitBreaker("svc", failure_threshold=1, recovery_timeout=30)
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("down")))
        assert cb.state == CircuitBreakerState.OPEN

        # When: operator force-close
        cb.force_close()
        # Then
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.call(lambda: "ok") == "ok"

    def test_force_open_for_maintenance(self):
        """Given CLOSED circuit, When force_open called, Then state=OPEN,
        all requests rejected (maintenance mode)।"""
        cb = CircuitBreaker("svc", failure_threshold=10, recovery_timeout=30)
        assert cb.state == CircuitBreakerState.CLOSED

        # When: maintenance mode
        cb.force_open()
        # Then
        assert cb.state == CircuitBreakerState.OPEN
        with pytest.raises(CircuitBreakerOpenError):
            cb.call(lambda: "should-not-reach")


# ---------------------------------------------------------------------------
# 5. CircuitBreakerManager shared-state contract
# ---------------------------------------------------------------------------


class TestCircuitBreakerManagerSharedState:
    """সিঙ্গেলটন ম্যানেজার — নাম ভেদে একই breaker শেয়ার করা হয়।"""

    def test_singleton_returns_same_instance(self):
        """Given two CircuitBreakerManager() calls, When compared, Then same instance।"""
        a = CircuitBreakerManager()
        b = CircuitBreakerManager()
        assert a is b

    def test_get_circuit_breaker_returns_same_for_name(self):
        """Given manager, When get_circuit_breaker('svc') called twice, Then
        same CircuitBreaker instance returned।"""
        manager = CircuitBreakerManager()
        cb1 = manager.get_circuit_breaker("svc-a")
        cb2 = manager.get_circuit_breaker("svc-a")
        assert cb1 is cb2
        assert cb1.name == "svc-a"

    def test_get_circuit_breaker_different_names_distinct(self):
        """Given manager, When get_circuit_breaker('a') and ('b') called, Then
        distinct instances returned।"""
        manager = CircuitBreakerManager()
        cb_a = manager.get_circuit_breaker("svc-a")
        cb_b = manager.get_circuit_breaker("svc-b")
        assert cb_a is not cb_b

    def test_get_all_states_aggregates_all_breakers(self):
        """Given manager with 2 breakers, When get_all_states called, Then dict
        with both breaker state-info returned।"""
        manager = CircuitBreakerManager()
        manager.get_circuit_breaker("svc-a")
        manager.get_circuit_breaker("svc-b")
        states = manager.get_all_states()
        assert set(states.keys()) == {"svc-a", "svc-b"}
        assert all("state" in v for v in states.values())

    def test_reset_breaker_clears_failure_count(self):
        """Given tripped breaker, When reset_breaker called, Then state=CLOSED,
        failure_count=0।"""
        manager = CircuitBreakerManager()
        cb = manager.get_circuit_breaker("svc-reset")
        for _ in range(getattr(cb, "failure_threshold", 3)):
            with pytest.raises(ValueError):
                cb.call(lambda: (_ for _ in ()).throw(ValueError("down")))
        assert cb.state == CircuitBreakerState.OPEN

        # When
        ok = manager.reset_breaker("svc-reset")
        # Then
        assert ok is True
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0

    def test_reset_unknown_breaker_returns_false(self):
        """Given manager, When reset_breaker('unknown') called, Then False।"""
        manager = CircuitBreakerManager()
        assert manager.reset_breaker("does-not-exist") is False

    def test_force_close_breaker_alias(self):
        """Given tripped breaker, When force_close_breaker called, Then state=CLOSED।"""
        manager = CircuitBreakerManager()
        cb = manager.get_circuit_breaker("svc-force")
        cb.force_open()
        assert cb.state == CircuitBreakerState.OPEN

        ok = manager.force_close_breaker("svc-force")
        assert ok is True
        assert cb.state == CircuitBreakerState.CLOSED


# ---------------------------------------------------------------------------
# 6. Boundary: state-info shape + metrics
# ---------------------------------------------------------------------------


class TestCircuitBreakerStateInfo:
    """get_state_info / get_metrics shape contract — observability।"""

    def test_state_info_includes_required_fields(self):
        """Given breaker, When get_state_info called, Then dict has required keys।"""
        cb = CircuitBreaker("svc", failure_threshold=5, recovery_timeout=60)
        info = cb.get_state_info()
        required = {
            "name",
            "state",
            "failure_count",
            "success_count",
            "failure_threshold",
            "recovery_timeout",
            "is_open",
        }
        assert required <= set(info.keys())
        assert info["name"] == "svc"
        assert info["state"] == "CLOSED"
        assert info["is_open"] is False

    def test_metrics_exposes_state_value(self):
        """Given breaker, When get_metrics called, Then state encoded as numeric
        (0=closed, 1=half_open, 2=open)।"""
        cb = CircuitBreaker("svc", failure_threshold=1, recovery_timeout=30)
        # CLOSED → 0
        m = cb.get_metrics()
        assert m['circuit_breaker_state{name="svc"}'] == 0

        # Trip → OPEN → 2
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("down")))
        m = cb.get_metrics()
        assert m['circuit_breaker_state{name="svc"}'] == 2
        assert m['circuit_breaker_failures_total{name="svc"}'] >= 1

    def test_state_info_does_not_deadlock(self):
        """Given breaker, When get_state_info called inside loop over many
        breakers, Then no self-deadlock (issue #1070 regression)।"""
        # বাংলা: #1070 — get_state_info একসময় self.is_open কল করে দ্বিতীয়বার lock
        # নিতে গিয়ে self-deadlock করত। এখন সরাসরি self.state পড়া হয়।
        manager = CircuitBreakerManager()
        for i in range(20):
            manager.get_circuit_breaker(f"svc-{i}")
        # When: get_all_states iterates all breakers
        states = manager.get_all_states()
        # Then: no hang — every breaker has state info
        assert len(states) == 20


# ---------------------------------------------------------------------------
# বাংলা মন্তব্য: অ্যাসিঙ্ক হেল্পার ফাংশন।
# ---------------------------------------------------------------------------


@staticmethod
def _async_return(value: Any):
    async def _fn():
        return value

    return _fn


@staticmethod
def _async_raise(exc: BaseException):
    async def _fn():
        raise exc

    return _fn


# Bind helpers to class namespace (test discovery doesn't need them as tests)
# বাংলা: টেস্ট ক্লাসের ভেতরে রেফারেন্স করা হয়েছে — module-level alias এড়ানো।
TestCircuitBreakerRecovery._async_return = _async_return  # type: ignore[attr-defined]
TestCircuitBreakerRecovery._async_raise = _async_raise  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# বাংলা মন্তব্য: টাইমিং-ইনডিপেন্ডেন্ট recovery টেস্ট — সরাসরি opened_at ম্যানিপুলেট।
# ---------------------------------------------------------------------------


class TestRecoveryTimeoutBoundary:
    """recovery_timeout পার হলেই HALF_OPEN probe চলে — টাইমিং বাউন্ডারি।"""

    def test_just_under_timeout_stays_open(self):
        """Given OPEN circuit, When time-since-opened < recovery_timeout,
        Then allow_request returns False (still OPEN)।"""
        cb = CircuitBreaker("svc", failure_threshold=1, recovery_timeout=30)
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("down")))
        assert cb.state == CircuitBreakerState.OPEN

        # বাংলা: opened_at এখনই সেট। ১ সেকেন্ড পর — এখনো ৩০ সেকেন্ডের নিচে।
        assert cb.opened_at is not None
        assert (time.monotonic() - cb.opened_at) < cb.recovery_timeout
        assert cb.allow_request() is False

    def test_zero_timeout_allows_immediate_recovery(self):
        """Given OPEN circuit with recovery_timeout=0, When allow_request called,
        Then True (immediate HALF_OPEN probe allowed)।"""
        cb = CircuitBreaker("svc", failure_threshold=1, recovery_timeout=0)
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("down")))
        assert cb.state == CircuitBreakerState.OPEN

        # When: allow_request immediately after open
        ok = cb.allow_request()
        # Then: transitions to HALF_OPEN
        assert ok is True
        assert cb.state == CircuitBreakerState.HALF_OPEN
