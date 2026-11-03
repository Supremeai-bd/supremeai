"""#2710 (R2.5) — Upstash REST queue-এর দৈনিক soft-cap বাজেট ইঞ্জিনের ইউনিট-টেস্ট।

বাংলা মন্তব্য: এই টেস্টগুলো নিশ্চিত করে যে কোনো account তার দৈনিক soft-cap ছুঁলে
HTTP 400 (quota-exhausted) দেখার **আগেই** চেইনের পরবর্তী account-এ shift হয়ে
যায় — ফলে primary আর কখনো 500k-স্পর্শ করে না (#2452/#2710-র রিগ্রেশন বন্ধ)।

Hermetic: কোনো বাস্তব নেটওয়ার্ক কল নেই — httpx client mock করা হয়।
"""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.messaging.upstash_redis_queue import (
    QuotaExhaustedError,
    UpstashRedisQueue,
    _next_utc_reset_epoch,
)

# বাংলা মন্তব্য: ছোট পুল — দুটি ভুল URL (বাস্তব কল হবে না, client mock)
POOL = [
    ("https://acct-primary.example", "tok-0"),
    ("https://acct-second.example", "tok-1"),
]


def _make_queue(monkeypatch, cap: int | None = 400_000) -> UpstashRedisQueue:
    # বাংলা মন্তব্য: মডিউল-লেভেল settings রেফারেন্স প্যাচ করি — বাস্তব pydantic
    # Settings-এর property-তে setter নেই, তাই SimpleNamespace দিয়ে পুল বসাই।
    monkeypatch.setattr(
        "core.messaging.upstash_redis_queue.settings",
        SimpleNamespace(upstash_redis_rest_pool=POOL, upstash_redis_rest_pool_enabled=True),
    )
    env = {"UPSTASH_DAILY_SOFT_CAP": str(cap) if cap is not None else "400000"}
    with patch.dict("os.environ", env):
        q = UpstashRedisQueue(rest_url=POOL[0][0], token=POOL[0][1])
    # বাংলা মন্তব্য: বাস্তব httpx client-কে mock দিয়ে বদলে দিই — ২০০ OK ফেরত
    calls: list[str] = []

    def _fake_post(url, headers=None, json=None):
        calls.append(url)
        # বাংলা মন্তব্য: raise_for_status() নিঃশব্দে পাস — 200 OK সিমুলেশন
        return SimpleNamespace(
            status_code=200, json=lambda: {"result": "OK"}, raise_for_status=lambda: None
        )

    q._client = SimpleNamespace(post=_fake_post)
    q._test_calls = calls  # টেস্ট দৃশ্যমালার জন্য
    return q


def test_softcap_shifts_account_before_real_quota_error(monkeypatch):
    """বাংলা মন্তব্য: cap=3 — ৩টি command-এর পরেই primary skip হবে, 400 ছাড়াই।"""
    q = _make_queue(monkeypatch, cap=3)
    for _ in range(3):
        assert q._request("PING") == {"result": "OK"}
    # বাংলা মন্তব্য: প্রথম ৩টি primary-তে গেছে
    assert q._test_calls == [POOL[0][0]] * 3
    # চতুর্থ command এখন সরাসরি second account-এ — primary-তে 4ম কল যায়নি
    assert q._request("PING") == {"result": "OK"}
    assert q._test_calls == [POOL[0][0]] * 3 + [POOL[1][0]]
    st = q.quota_status()
    assert POOL[0][0] in st["softcap_accounts"]
    assert st["daily_counts"][POOL[0][0]] == 3
    assert st["stats"]["softcap_shifts"] == 1


def test_softcap_reset_at_utc_day_rollover(monkeypatch):
    """বাংলা মন্তব্য: দিন বদলালে গণনা+skip রিসেট — account আবার তার বাজেট পায়।"""
    q = _make_queue(monkeypatch, cap=1)
    assert q._request("PING") == {"result": "OK"}
    assert POOL[0][0] in q.quota_status()["softcap_accounts"]
    # বাংলা মন্তব্য: সময়-বাকেট অতীতে ঠেলে দিই (রোলওভার পাথ জোর করে চালানো)
    q._day_bucket_until = time.time() - 1
    # নতুন দিনে primary আবার ঠিক ১টি (cap=1) command পরিবেশন করতে পারে
    assert q._request("PING") == {"result": "OK"}
    assert q._test_calls == [POOL[0][0]] * 2  # দুই দিনেই প্রথম কল primary-তেই গেছে
    # এরপর আবার soft-capped (নতুন দিনের বাজেটও শেষ) — তৃতীয় কল second-এ
    assert q._request("PING") == {"result": "OK"}
    assert q._test_calls[-1] == POOL[1][0]
    st = q.quota_status()
    assert st["daily_counts"][POOL[0][0]] == 1  # নতুন দিনের গণনা আলাদা বাকেটে


def test_softcap_zero_disables_budget(monkeypatch):
    """বাংলা মন্তব্য: cap=0 মানে বাজেট-ইঞ্জিন নিষ্ক্রিয় — আচরণ আগের মতো।"""
    q = _make_queue(monkeypatch, cap=0)
    for _ in range(5):
        assert q._request("PING") == {"result": "OK"}
    assert q._test_calls == [POOL[0][0]] * 5
    assert q.quota_status()["softcap_accounts"] == {}


def test_all_softcapped_raises_honest_quota_error(monkeypatch):
    """বাংলা মন্তব্য: সব account soft-cap-এ পড়লে QuotaExhaustedError (মিথ্যা 'Redis down' নয়)।"""
    q = _make_queue(monkeypatch, cap=1)
    q._request("PING")  # primary → soft-capped
    q._request("PING")  # second → soft-capped
    with pytest.raises(QuotaExhaustedError):
        q._request("PING")


def test_quota_status_shape_stable(monkeypatch):
    """বাংলা মন্তব্য: quota_status-এর নতুন কী-গুলো উপস্থিত — observability contract।"""
    q = _make_queue(monkeypatch)
    st = q.quota_status()
    for key in (
        "cooldown_accounts",
        "daily_counts",
        "daily_soft_cap",
        "softcap_accounts",
        "stats",
    ):
        assert key in st, f"quota_status-এ '{key}' অনুপস্থিত"
    assert st["daily_soft_cap"] == 400_000
    assert _next_utc_reset_epoch() > time.time()
