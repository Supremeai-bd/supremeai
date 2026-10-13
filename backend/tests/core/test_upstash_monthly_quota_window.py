"""#26 — Upstash কোটা-উইন্ডো সংশোধনের রিগ্রেশন টেস্ট (monthly default).

বাংলা মন্তব্য: Upstash free-tier-এর `ERR max requests limit exceeded`
("Limit: 500000") একটি **মাসিক** ক্যাপ (দৈনিক নয়) — প্রমাণ: 2026-10-07-এ
usage=500002 রিপোর্টের ৬ দিন পরেও (2026-10-13) হুবহু 500002; দৈনিক উইন্ডো হলে
মধ্যরাতে রিসেট হয়ে গণনা বদলাত। এই টেস্টগুলো নিশ্চিত করে:

1. ডিফল্ট উইন্ডো `monthly` — cooldown/soft-cap রিসেট মাসের ১ তারিখ 00:00 UTC।
2. দৈনিক-উইন্ডোর পুরনো আচরণ `UPSTASH_QUOTA_WINDOW=daily` দিয়ে ফেরানো যায়।
3. Soft-cap এখন মাসিক গণনার বিপৰীতে কাজ করে (legacy env alias সহ)।
4. quota_status উইন্ডো-সচেতন কী + legacy alias দুটোই রাখে (observability)।

Hermetic: কোনো বাস্তব নেটওয়ার্ক কল নেই — httpx client mock করা হয়।
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.messaging.upstash_redis_queue import (
    QuotaExhaustedError,
    UpstashRedisQueue,
    _next_quota_reset_epoch,
    _next_utc_reset_epoch,
    _quota_window,
)

# বাংলা মন্তব্য: ছোট পুল — দুটি ভুল URL (বাস্তব কল হবে না, client mock)
POOL = [
    ("https://acct-primary.example", "tok-0"),
    ("https://acct-second.example", "tok-1"),
]


def _make_queue(monkeypatch, cap: int | None = None, env: dict | None = None) -> UpstashRedisQueue:
    # বাংলা মন্তব্য: মডিউল-লেভেল settings রেফারেন্স প্যাচ করি — বাস্তব pydantic
    # Settings-এর property-তে setter নেই, তাই SimpleNamespace দিয়ে পুল বসাই।
    monkeypatch.setattr(
        "core.messaging.upstash_redis_queue.settings",
        SimpleNamespace(upstash_redis_rest_pool=POOL, upstash_redis_rest_pool_enabled=True),
    )
    environ: dict[str, str] = {}
    if cap is not None:
        environ["UPSTASH_QUOTA_SOFT_CAP"] = str(cap)
    environ.update(env or {})
    with patch.dict("os.environ", environ):
        q = UpstashRedisQueue(rest_url=POOL[0][0], token=POOL[0][1])
    # বাংলা মন্তব্য: বাস্তব httpx client-কে mock দিয়ে বদলে দিই — ২০০ OK ফেরত
    calls: list[str] = []

    def _fake_post(url, headers=None, json=None):
        calls.append(url)
        # raise_for_status() নিঃশব্দে পাস — 200 OK সিমুলেশন
        return SimpleNamespace(
            status_code=200, json=lambda: {"result": "OK"}, raise_for_status=lambda: None
        )

    q._client = SimpleNamespace(post=_fake_post)
    q._test_calls = calls  # টেস্ট দৃশ্যমালার জন্য
    return q


# ── #26: উইন্ডো-নিরূপণ ───────────────────────────────────────────────────────


def test_default_window_is_monthly(monkeypatch):
    """ডিফল্ট উইন্ডো monthly — Upstash 500k মাসিক ক্যাপ।"""
    monkeypatch.delenv("UPSTASH_QUOTA_WINDOW", raising=False)
    assert _quota_window() == "monthly"


def test_monthly_reset_lands_on_first_of_next_month_utc(monkeypatch):
    """monthly রিসেট = মাসের ১ তারিখ 00:00 UTC + grace, সবসময় আগামী মাসে।"""
    monkeypatch.delenv("UPSTASH_QUOTA_WINDOW", raising=False)
    nxt = datetime.fromtimestamp(_next_quota_reset_epoch(), UTC)
    # বাংলা মন্তব্য: reset টার্গেট = মাসের ১ তারিখ 00:00 UTC; +60s grace → 00:01
    assert nxt.day == 1
    assert nxt.hour == 0
    assert nxt.minute <= 1  # 0 (exact) অথবা 1 (60s grace) — দুটোই মাসের ১ তারিখ
    assert nxt > datetime.now(UTC)
    # বাংলা মন্তব্য: মাসের ১ তারিখ হলে রোলওভার সাল বদলায় — ডিসেম্বরের পর জানুয়ারি
    now = datetime.now(UTC)
    assert nxt.month == (1 if now.month == 12 else now.month + 1)


def test_daily_window_is_legacy_opt_out(monkeypatch):
    """UPSTASH_QUOTA_WINDOW=daily — পুরনো দৈনিক আচরণ ফেরায় (backwards compat)।"""
    monkeypatch.setenv("UPSTASH_QUOTA_WINDOW", "daily")
    assert _quota_window() == "daily"
    assert _next_quota_reset_epoch() == _next_utc_reset_epoch()


# ── #26: cooldown মাসিক উইন্ডোতে ─────────────────────────────────────────────


def _quota_400_queue(monkeypatch) -> UpstashRedisQueue:
    """HTTP 400 quota-marker ফেরত দেওয়া mock-client সহ queue — সব account ৪০০।

    #26: monthly window-এ সবগুলো account exhausted হলে সৎ QuotaExhaustedError
    ওঠ�্য (মিথ্যা 'Redis down' নয়) এবং সক্রিয় account-গুলোকে মাসের শেষ পর্যন্ত
    cooldown-এ রাখে।
    """
    q = _make_queue(monkeypatch, cap=0)

    def _fake_post_400(url, headers=None, json=None):
        # বাংলা মন্তব্য: সব account-এই 400 quota-marker — monthly উইন্ডোতে সব exhaust হলে
        # সৎ QuotaExhaustedError + সকলক monthly-restart-এর পর্যন্ত cooldown।
        return SimpleNamespace(
            status_code=400,
            text='{"error":"ERR max requests limit exceeded. Limit: 500000"}',
            raise_for_status=lambda: (_ for _ in ()).throw(RuntimeError("400")),
            json=lambda: {},
        )

    q._client = SimpleNamespace(post=_fake_post_400)
    return q


def test_quota_exhausted_cools_down_until_month_end(monkeypatch):
    """HTTP 400 quota-marker → cooldown মাসের শেষ পর্যন্ত (দৈনিক মধ্যরাত নয়)।"""
    monkeypatch.delenv("UPSTASH_QUOTA_WINDOW", raising=False)
    q = _quota_400_queue(monkeypatch)
    with pytest.raises(QuotaExhaustedError):
        q._request("GET", "k")
    st = q.quota_status()
    assert st["window"] == "monthly"
    # বাংলা মন্তব্য: সব account exhausted — cooldown_accounts-এ উভয়ই (monthly সব কালার্ড)
    assert POOL[0][0] in st["cooldown_accounts"]
    assert POOL[1][0] in st["cooldown_accounts"]
    until = datetime.fromisoformat(st["cooldown_accounts"][POOL[0][0]])
    assert until.day == 1 and until.hour == 0  # মাসের ১ তারিখ 00:00 UTC (+60s grace)
    assert until > datetime.now(UTC)
    assert st["stats"]["quota_cooldowns"] == 2  # প্রতিটি exhausted account-এর ১টি


# ── #26: soft-cap monthly গণনা ──────────────────────────────────────────────


def test_monthly_softcap_counts_across_window(monkeypatch):
    """monthly soft-cap উইন্ডোর মোট গণনার বিপৰীতে — ২ command-এর পরেই shift।"""
    monkeypatch.delenv("UPSTASH_QUOTA_WINDOW", raising=False)
    q = _make_queue(monkeypatch, cap=2)
    assert q._request("PING") == {"result": "OK"}
    assert q._request("PING") == {"result": "OK"}
    assert q._test_calls == [POOL[0][0]] * 2
    # বাংলা মন্তব্য: ২টি command-এই monthly soft-cap — তৃতীয় second account-এ
    assert q._request("PING") == {"result": "OK"}
    assert q._test_calls[-1] == POOL[1][0]
    st = q.quota_status()
    assert st["window"] == "monthly"
    assert st["window_counts"][POOL[0][0]] == 2
    assert st["stats"]["softcap_shifts"] == 1


def test_legacy_daily_env_alias_still_honored(monkeypatch):
    """পুরনো UPSTASH_DAILY_SOFT_CAP env monthly window-এও সম্মানিত (alias)।"""
    monkeypatch.delenv("UPSTASH_QUOTA_WINDOW", raising=False)
    monkeypatch.delenv("UPSTASH_QUOTA_SOFT_CAP", raising=False)
    monkeypatch.setenv("UPSTASH_DAILY_SOFT_CAP", "2")
    q = _make_queue(monkeypatch)  # env-এ DAILY সেট করা আছে
    assert q._soft_cap_limit == 2
    assert q._request("PING") == {"result": "OK"}
    assert q._request("PING") == {"result": "OK"}
    assert q._request("PING") == {"result": "OK"}
    assert q._test_calls[-1] == POOL[1][0]  # soft-cap ছুঁলে shift
    assert q.quota_status()["daily_soft_cap"] == 2  # legacy alias


def test_daily_window_keeps_midnight_softcap_behavior(monkeypatch):
    """daily opt-out: soft-cap reset UTC মধ্যরাতে (legacy আচরণ অপরিবর্তিত)।"""
    monkeypatch.setenv("UPSTASH_QUOTA_WINDOW", "daily")
    q = _make_queue(monkeypatch, cap=1)
    assert q._request("PING") == {"result": "OK"}
    assert POOL[0][0] in q.quota_status()["softcap_accounts"]
    # বাংলা মন্তব্য: দিন-বাকেট অতীতে ঠেলে রোলওভার বাধ্যতামূলক
    q._day_bucket_until = time.time() - 1
    assert q._request("PING") == {"result": "OK"}
    assert q._test_calls[-1] == POOL[0][0]  # নতুন দিনে প্রথম কল আবার primary-তে
    assert q.quota_status()["window"] == "daily"


# ── #26: observability shape ─────────────────────────────────────────────────


def test_quota_status_exposes_window_and_legacy_aliases(monkeypatch):
    """quota_status নতুন কী + legacy alias দুইই রাখা — consumer break নয়।"""
    monkeypatch.delenv("UPSTASH_QUOTA_WINDOW", raising=False)
    q = _make_queue(monkeypatch, cap=5)
    st = q.quota_status()
    for key in (
        "window",
        "window_counts",
        "window_soft_cap",
        "daily_counts",
        "daily_soft_cap",
        "cooldown_accounts",
        "softcap_accounts",
        "stats",
    ):
        assert key in st, f"quota_status-এ '{key}' অনুপস্থিত"
    assert st["window"] == "monthly"
    assert st["window_soft_cap"] == 5
    assert st["window_counts"] == st["daily_counts"]  # alias same object content
