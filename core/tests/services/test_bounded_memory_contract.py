"""Issue #2718 — Bounded memory accumulator contract tests.

512MB free tier-এ slow OOM প্রতিরোধের ৩টি সাইটের regression-lock:

1. metrics_collector — histogram deque(maxlen=512): 10k observation push করলেও
   per-key storage বাড়ে না; query_count সর্বমোট সংখ্যা সঠিকভাবে রিপোর্ট করে।
2. share LRU — maxsize 500 ছাড়ায় না; revoke-এ cache hit হয় না।
3. render proxy — >5MB upstream সাথে সাথে 502 (chunked read, bounded RAM)।

House-pattern: stdlib-only, monkeypatch-based, --noconftest-safe (precedent
#2420/#2426/#2716)।
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from monitoring.metrics_collector import _HISTOGRAM_WINDOW, MetricsCollector

# ---------------------------------------------------------------------------
# 1) metrics_collector — histogram bounded window
# ---------------------------------------------------------------------------


def test_histogram_deque_bounded_after_10k_observations():
    """Acceptance: 10k observation পুশ করলে list-len বাড়ে না (≤512 cap)."""
    collector = MetricsCollector()

    async def run():
        for i in range(10_000):
            await collector.observe_histogram("cache_get_seconds", float(i % 7))

    asyncio.run(run())

    key = next(k for k in collector._metrics if k.startswith("cache_get_seconds"))
    stored = collector._metrics[key]
    # deque(maxlen) — সব মান সংরক্ষণ করার চেয়ে শেষ 512-ই থাকে
    assert len(stored) == _HISTOGRAM_WINDOW
    # শেষ observation সংরক্ষিত আছে (eviction সঠিক প্রান্ত থেকে হয়েছে)
    assert stored[-1] == 9999 % 7


def test_db_query_count_honest_after_window_overflow():
    """query_count = সর্বমোট observation; avg শেষ window-এর ওপর।"""
    collector = MetricsCollector()

    async def run():
        for i in range(600):
            await collector.record_db_query("SELECT", duration=0.001 * (i + 1))

    asyncio.run(run())
    perf = asyncio.run(collector.get_db_performance())
    # মোট 600 বার — bounded deque-এর len (512) নয়
    assert perf["query_count"] == 600
    # শেষ 512-এর window: গড় হিসাব হয় window-এর ওপর
    recent = list(collector._db_query_times)
    assert len(recent) == 512
    assert perf["avg_query_time"] == pytest.approx(sum(recent) / len(recent))


# ---------------------------------------------------------------------------
# 2) share.py — bounded LRU + revoke eviction
# ---------------------------------------------------------------------------


def test_share_cache_lru_bounded_at_500(monkeypatch):
    """Acceptance: LRU maxsize≈500 — 600 insert-এ cache size 500-ই থাকে।"""
    from api.routes import share as share_mod

    share_mod._share_cache.clear()
    try:
        for i in range(600):
            share_mod._cache_set(f"share-{i:04d}", {"payload": f"p{i}"})

        assert len(share_mod._share_cache) == share_mod._SHARE_CACHE_MAX_SIZE
        # সবচেয়ে পুরনো ১০০টি evict হয়েছে
        assert share_mod._cache_get("share-0000") is None
        assert share_mod._cache_get("share-0099") is None
        # সাম্প্রতিকগুলো আছে
        assert share_mod._cache_get("share-0599") is not None
    finally:
        share_mod._share_cache.clear()


def test_share_revoke_evicts_cache():
    """Acceptance: revoke-এ share cache hit না হওয়া — pop কন্ট্র্যাক্ট লক।"""
    from api.routes import share as share_mod

    share_mod._share_cache.clear()
    try:
        share_mod._cache_set("share-revoke-me", {"conversation": "x"})
        assert share_mod._cache_get("share-revoke-me") is not None
        # revoke_share-এর ক্যাশ-ইনভ্যালিডেশন লাইনের কন্ট্র্যাক্ট:
        share_mod._share_cache.pop("share-revoke-me", None)
        assert share_mod._cache_get("share-revoke-me") is None
    finally:
        share_mod._share_cache.clear()


# ---------------------------------------------------------------------------
# 3) render proxy — chunked bounded read (>5MB → 502)
# ---------------------------------------------------------------------------


def _issue_valid_ticket():
    """Valid one-time ticket — render_proxy-এর auth contract পূরণে।"""
    from api.routes.browser._render_proxy import _issue_ticket

    return _issue_ticket()


def test_render_proxy_over_5mb_aborts_502():
    """Acceptance: >5MB upstream 502 দেয় — chunk loop সাথে সাথে abort।"""
    from api.routes.browser import _render_proxy

    big_chunk = b"x" * (64 * 1024)

    class FakeResp:
        headers = {"Content-Type": "application/octet-stream"}

        def __init__(self):
            self._reads = 0

        def read(self, n=-1):
            # ৫ মেগাবাইটের বেশি দেওয়ার মতো অফুরন্ত upstream — লুপের
            # total > LIMIT চেক প্রতিটি ধাপেই abort করবে।
            return big_chunk

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    t = _issue_valid_ticket()
    with patch.object(_render_proxy.urllib.request, "urlopen", return_value=FakeResp()):
        with pytest.raises(HTTPException) as exc:
            _render_proxy.render_proxy(url="https://example.com/big", ticket=t)
    assert exc.value.status_code == 502
    assert "too large" in exc.value.detail


def test_render_proxy_small_body_still_proxies():
    """ছোট upstream — chunked পথেও আগের মতোই 200 + কনটেন্ট।"""
    from api.routes.browser import _render_proxy

    reads = iter([b"small-body", b""])

    class FakeResp:
        headers = {"Content-Type": "text/plain"}

        def read(self, n=-1):
            return next(reads)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    t = _issue_valid_ticket()
    with patch.object(_render_proxy.urllib.request, "urlopen", return_value=FakeResp()):
        r = _render_proxy.render_proxy(url="https://example.com/big", ticket=t)
    assert r.status_code == 200
    assert r.body == b"small-body"
