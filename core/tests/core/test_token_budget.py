import os
from unittest.mock import patch

import pytest

from core.llm.token_budget import (
    TokenBudgetManager,
    estimate_tokens,
    truncate_to_token_limit,
)


def test_estimate_tokens_empty():
    assert estimate_tokens("") == 0


def test_truncate_to_token_limit_from_end_keeps_tail():
    txt = "Sentence one. Sentence two. Sentence three." * 50
    out = truncate_to_token_limit(txt, max_tokens=50, from_end=True)
    assert len(out) > 0


@pytest.mark.anyio
async def test_prepare_prompt_truncates_when_exceeds_budget(monkeypatch):
    mgr = TokenBudgetManager(
        custom_budgets={"default": {"max_input_tokens": 200, "max_output_tokens": 50}}
    )

    long_prompt = "hello " * 1000
    _processed, meta = mgr.prepare_prompt(long_prompt, provider="default", system_prompt="sys")

    assert meta["truncated"] is True
    assert meta["estimated_input_tokens"] > 0
    assert "tokens_saved" in meta


@pytest.mark.anyio
async def test_prepare_prompt_budget_exhaustion_raises_and_emits(monkeypatch):
    # system_prompt consumes almost entire budget
    mgr = TokenBudgetManager(
        custom_budgets={"default": {"max_input_tokens": 100, "max_output_tokens": 50}}
    )

    # patch emit so it won't require real bus
    from core.llm import token_budget

    monkeypatch.setattr(token_budget.error_event_bus, "emit", lambda *args, **kwargs: None)

    with pytest.raises(ValueError):
        mgr.prepare_prompt("user", provider="default", system_prompt="x" * 10000)


# ─────────────────────────────────────────────────────────────────────────────
# CRITICAL-PATH COVERAGE (final-test hardening-2): core/llm/** is tier-critical
# in coverage_policy.yaml; these tests lock the remaining sync + Redis contracts.
# ─────────────────────────────────────────────────────────────────────────────
import asyncio  # noqa: E402
import time  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402

from core.llm.token_budget import (  # noqa: E402
    PROVIDER_TOKEN_BUDGETS,
    TokenBudgetStats,
    get_budget_manager,
    truncate_to_token_limit,
)


class TestEstimateTokens:
    def test_empty_and_short(self):
        assert estimate_tokens("") == 0
        assert estimate_tokens("a") == 1  # max(1, ...) floor

    def test_english_ratio(self):
        # 40 chars at 4 chars/token ≈ 10 tokens
        text = "a" * 40
        assert estimate_tokens(text) == 10

    def test_code_ratio_detected(self):
        code = "def function_name():\n    return value\n" * 2
        # code has 'def ' → 3.5 chars/token → MORE tokens per char than the
        # plain-english 4 chars/token for the same length.
        assert estimate_tokens(code) > estimate_tokens("a" * len(code))

    def test_cjk_ratio_detected(self):
        cjk = "你好世界" * 30  # CJK chars in first 100 → 2 chars/token
        assert estimate_tokens(cjk) == int(len(cjk) / 2)


class TestTruncate:
    def test_no_truncation_within_budget(self):
        txt = "short"
        assert truncate_to_token_limit(txt, max_tokens=100) is txt

    def test_hard_cut_when_no_boundary(self):
        txt = "a" * 1000  # no sentence boundary
        out = truncate_to_token_limit(txt, max_tokens=10)
        assert len(out) <= 10 * 4 + 1

    def test_from_end_trims_to_first_boundary_of_tail(self):
        sentences = ". ".join([f"Sentence {i} here" for i in range(60)]) + "."
        out = truncate_to_token_limit(sentences, max_tokens=30, from_end=True)
        assert len(out) > 0
        assert len(out) < len(sentences)


class TestTokenBudgetStats:
    def test_record_call_accumulates(self):
        stats = TokenBudgetStats(provider="groq")
        stats.record_call(input_tokens=10, output_tokens=5)
        stats.record_call(input_tokens=20, output_tokens=8, was_truncated=True, tokens_saved=15)
        d = stats.to_dict()
        assert d["total_calls"] == 2
        assert d["total_input_tokens"] == 30
        assert d["total_output_tokens"] == 13
        assert d["avg_input_tokens"] == 15
        assert d["truncated_calls"] == 1
        assert d["tokens_saved_by_truncation"] == 15

    def test_to_dict_avg_zero_when_no_calls(self):
        d = TokenBudgetStats(provider="x").to_dict()
        assert d["avg_input_tokens"] == 0
        assert d["total_calls"] == 0


class TestManagerContracts:
    def _mgr(self) -> TokenBudgetManager:
        return TokenBudgetManager(
            custom_budgets={"default": {"max_input_tokens": 500, "max_output_tokens": 100}}
        )

    def test_fits_in_budget_true_and_false(self):
        mgr = self._mgr()
        assert mgr.fits_in_budget("hello world") is True
        assert mgr.fits_in_budget("a" * 10_000) is False

    def test_get_provider_budget_defaults(self):
        mgr = TokenBudgetManager()
        for provider, limits in PROVIDER_TOKEN_BUDGETS.items():
            assert mgr.get_provider_budget(provider) == limits
        unknown = mgr.get_provider_budget("no-such-provider")
        assert unknown == mgr.get_provider_budget("default")

    def test_record_usage_updates_output_tokens(self):
        mgr = self._mgr()
        _p, meta = mgr.prepare_prompt("hello", provider="default")
        mgr.record_usage(
            provider="default", input_tokens=meta["estimated_input_tokens"], output_tokens=42
        )
        stats = mgr.get_stats()["default"]
        assert stats["total_output_tokens"] == 42
        assert stats["total_calls"] == 1

    def test_prepare_prompt_records_truncation_stats(self):
        mgr = self._mgr()
        _p, meta = mgr.prepare_prompt("a" * 10_000, provider="default")
        assert meta["truncated"] is True
        assert meta["tokens_saved"] > 0
        stats = mgr.get_stats()["default"]
        assert stats["truncated_calls"] == 1

    def test_get_stats_idempotent_keys(self):
        mgr = self._mgr()
        mgr.prepare_prompt("x", provider="default")
        assert set(mgr.get_stats().keys()) == {"default"}

    async def test_check_user_budget_env_aware_failure_policy(self):
        """B-V2-03 (audit V3) + issue #1687: Redis ভাঙলে সিদ্ধান্ত env-অনুযায়ী —
        production/staging-এ conservative LOCAL fallback (cap ছাড়িয়ে গেলে
        fail-CLOSED), dev/test-এ fail-open + loud log। পুরনো নীরব fail-open
        (unlimited spend) এখনো প্রত্যাখ্যাত।"""
        mgr = self._mgr()

        async def broken_redis():
            raise RuntimeError("redis down")

        mgr._get_redis = broken_redis

        # dev/test (ডিফল্ট) → fail-open
        assert await mgr.check_user_budget("user-1") is True

        # production → local fallback active; cap ছাড়ালে fail-closed
        with patch("core.config.settings") as mock_settings:
            mock_settings.env = "production"
            # cap পার করাই (10% of 100000 = 10000)
            for _ in range(11):
                await mgr.record_user_usage("user-2", tokens=1000)
            assert await mgr.check_user_budget("user-2") is False

        # staging → cap পার হলে fail-closed
        with patch("core.config.settings") as mock_settings:
            mock_settings.env = "staging"
            for _ in range(11):
                await mgr.record_user_usage("user-3", tokens=1000)
            assert await mgr.check_user_budget("user-3") is False

    async def test_check_user_budget_unconfigured_redis_honest_error(self):
        """B-V2-03 (audit V3): placeholder/unset Redis URL-এ সৎ RuntimeError —
        আগে `redis://<your-redis-url>` দিয়ে ক্লায়েন্ট বানিয়ে নীরব fail-open হতো।"""
        mgr = self._mgr()
        mgr._redis = None
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("REDIS_URL", None)
            with patch("core.config.settings") as mock_settings:
                mock_settings.redis_url = None
                with pytest.raises(RuntimeError, match="Redis URL not configured"):
                    await mgr._get_redis()

    async def test_check_user_budget_blocks_over_limit(self):
        mgr = self._mgr()
        redis = MagicMock()
        redis.get = AsyncMock(return_value="100001")
        mgr._redis = redis
        assert await mgr.check_user_budget("user-2", daily_limit=100000) is False

    async def test_check_user_budget_allows_under_limit(self):
        mgr = self._mgr()
        redis = MagicMock()
        redis.get = AsyncMock(return_value="5")
        mgr._redis = redis
        assert await mgr.check_user_budget("user-3", daily_limit=100000) is True

    async def test_record_user_usage_increments_and_sets_ttl(self):
        mgr = self._mgr()
        redis = MagicMock()
        redis.incrby = AsyncMock(return_value=100)  # == tokens → first write
        redis.expire = AsyncMock(return_value=True)
        mgr._redis = redis
        await mgr.record_user_usage("user-4", tokens=100)
        redis.incrby.assert_awaited_once()
        # First write of the day must attach the 24h TTL.
        args, _ = redis.expire.await_args
        assert args[1] == 86400

    async def test_record_user_usage_ignores_nonpositive(self):
        mgr = self._mgr()
        redis = MagicMock()
        redis.incrby = AsyncMock(return_value=0)
        redis.expire = AsyncMock(return_value=True)
        mgr._redis = redis
        await mgr.record_user_usage("user-5", tokens=0)
        await mgr.record_user_usage("user-5", tokens=-5)
        redis.incrby.assert_not_awaited()  # nothing recorded for tokens <= 0


class TestLocalFallbackBudgetTracker:
    """Issue #1687: Redis-down degraded mode — conservative local fallback.
    পুরনো আচরণ: prod-এ Redis down = সব deny (outage) / মূল বাগ: সব allow
    (unlimited spend)। নতুন: local cap-এর ভেতরে allow, cap-এ deny।"""

    def _mgr(self) -> TokenBudgetManager:
        return TokenBudgetManager(
            custom_budgets={"default": {"max_input_tokens": 500, "max_output_tokens": 100}}
        )

    def test_fallback_limit_is_conservative(self):
        from core.llm.token_budget import (
            _LOCAL_FALLBACK_MIN,
            _LOCAL_FALLBACK_RATIO,
            _LocalBudgetTracker,
        )

        t = _LocalBudgetTracker()
        assert _LOCAL_FALLBACK_RATIO == 0.1
        assert t.fallback_limit(100_000) == 10_000
        assert t.fallback_limit(10_000) == 1_000
        assert t.fallback_limit(100) == _LOCAL_FALLBACK_MIN  # floor 1000

    def test_record_and_get_today_increments(self):
        from core.llm.token_budget import _LocalBudgetTracker

        t = _LocalBudgetTracker()
        t.record("u", 100)
        t.record("u", 50)
        assert t.get_today("u") == 150
        t.record("u", 0)
        t.record("u", -5)
        assert t.get_today("u") == 150  # non-positive ignored
        assert t.get_today("unknown-user") == 0

    def test_record_is_thread_safe(self):
        from concurrent.futures import ThreadPoolExecutor

        from core.llm.token_budget import _LocalBudgetTracker

        t = _LocalBudgetTracker()
        with ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(lambda _: t.record("u", 10), range(200)))
        assert t.get_today("u") == 2000

    async def test_redis_down_prod_allows_within_then_denies_over_cap(self):
        mgr = self._mgr()

        async def broken_redis():
            raise RuntimeError("redis down")

        mgr._get_redis = broken_redis
        with patch("core.config.settings") as mock_settings:
            mock_settings.env = "production"
            # Fresh user, no local usage → degraded-mode allow (not outage)
            assert await mgr.check_user_budget("u-fb-1", daily_limit=100_000) is True
            # Accumulate 10,000 tokens (= cap) → next check denies
            await mgr.record_user_usage("u-fb-1", tokens=10_000)
            assert await mgr.check_user_budget("u-fb-1", daily_limit=100_000) is False

    async def test_redis_down_dev_ignores_local_cap(self):
        mgr = self._mgr()

        async def broken_redis():
            raise RuntimeError("redis down")

        mgr._get_redis = broken_redis
        await mgr.record_user_usage("u-fb-2", tokens=500_000)
        # dev/test এখনো fail-open (cap শুধু prod/staging-এ)
        assert await mgr.check_user_budget("u-fb-2", daily_limit=100_000) is True

    async def test_local_mirror_kept_when_redis_ok(self):
        mgr = self._mgr()
        redis = MagicMock()
        redis.incrby = AsyncMock(return_value=100)
        redis.expire = AsyncMock(return_value=True)
        mgr._redis = redis
        await mgr.record_user_usage("u-fb-3", tokens=100)
        redis.incrby.assert_awaited_once()
        # মিররও আপডেট হয়েছে — Redis মাঝপথে মরলে fallback এটা দেখবে
        assert mgr._local.get_today("u-fb-3") == 100

    async def test_redis_recovery_prefers_redis_truth(self):
        """Redis ফিরে এলে Redis-ই truth — local cap ভাঙলেও Redis-এর সিদ্ধান্ত
        প্রাধান্য পায় (মিরর শুধু degraded-mode fallback)।"""
        mgr = self._mgr()
        redis = MagicMock()
        redis.get = AsyncMock(return_value="100001")  # Redis: over daily limit
        mgr._redis = redis
        assert await mgr.check_user_budget("u-fb-4", daily_limit=100_000) is False

    async def test_other_users_unaffected_by_one_users_local_burst(self):
        mgr = self._mgr()

        async def broken_redis():
            raise RuntimeError("redis down")

        mgr._get_redis = broken_redis
        await mgr.record_user_usage("u-fb-5", tokens=999_999)
        with patch("core.config.settings") as mock_settings:
            mock_settings.env = "production"
            assert await mgr.check_user_budget("u-fb-5", daily_limit=100_000) is False
            # ভিন্ন ইউজারের কাউন্ট আলাদা → allow
            assert await mgr.check_user_budget("u-fb-6", daily_limit=100_000) is True


class TestManagerFactory:
    def test_get_budget_manager_is_per_user_cached(self):
        from core.llm import token_budget as tb

        m1 = tb.get_budget_manager(user_id="cache-test-user-a")
        m2 = tb.get_budget_manager(user_id="cache-test-user-a")
        other = tb.get_budget_manager(user_id="cache-test-user-b")
        assert m1 is m2
        assert m1 is not other

    def test_estimate_via_manager(self):
        mgr = TokenBudgetManager()
        assert mgr.estimate("a" * 40) == 10
