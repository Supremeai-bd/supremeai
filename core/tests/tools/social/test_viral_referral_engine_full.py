"""Full-coverage tests for tools/social/viral_referral_engine.py (Task 7-f).

Two modes are exercised for every persistence path:
- LOCAL mode  → ``db.client``/``db.service_client`` forced to None; the JSON
  store is redirected into ``tmp_path`` (never the real repo data dir).
- DB mode     → a fake supabase client whose ``execute()`` returns an object
  that is BOTH awaitable (for the awaited call-sites) and attribute-bearing
  (for the plain call-sites), mirroring the codebase's mixed usage.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import tools.social.viral_referral_engine as vre
from tools.social.viral_referral_engine import FRAUD_INDICATOR_THRESHOLD, ViralReferralEngine

# ──────────────────────────────── fake objects ────────────────────────────────


class FakeResult:
    """Awaitable result object: supports both ``res = q.execute()`` and
    ``res = await q.execute()`` call styles used across the engine."""

    def __init__(self, data: Any = None, count: int | None = None):
        self.data = data
        self.count = count

    def __await__(self):
        async def _co():
            return self

        return _co().__await__()


class FakeQuery:
    def __init__(self, table: FakeTable, action: str, payload: Any = None):
        self.table = table
        self.action = action
        self.payload = payload
        self.filters: list[tuple] = []

    def select(self, *cols, **kw):
        self.action = "select"
        return self

    def insert(self, row):
        self.action = "insert"
        self.payload = row
        return self

    def update(self, row):
        self.action = "update"
        self.payload = row
        return self

    def upsert(self, row):
        self.action = "upsert"
        self.payload = row
        return self

    def delete(self):
        return self

    def eq(self, col, val):
        self.filters.append(("eq", col, val))
        return self

    def order(self, col, desc=False):
        return self

    def limit(self, n):
        return self

    def execute(self):
        result = self.table.handle(self.action, self.payload, self.filters)
        return result if isinstance(result, FakeResult) else FakeResult(result)


class FakeTable:
    def __init__(self, handler):
        self._handler = handler

    def handle(self, action, payload, filters):
        return self._handler(action, payload, filters)

    def __call__(self, name: str) -> FakeQuery:
        self.name = name
        # default action "select"; chain methods (upsert/insert/update) override
        return FakeQuery(self, "select")


class FakeSupabase:
    """``db``-like double with programmable per-table handlers."""

    def __init__(self, handlers: dict[str, Any]):
        self._handlers = handlers
        self.tables: dict[str, FakeTable] = {}

    def table(self, name: str) -> FakeQuery:
        if name not in self.tables:
            self.tables[name] = FakeTable(
                self._handlers.get(name, lambda a, p, f: FakeResult(None))
            )
        return self.tables[name](name)


@pytest.fixture
def engine(monkeypatch, tmp_path) -> ViralReferralEngine:
    """Engine in LOCAL mode with its JSON store inside tmp_path."""
    from database.supabase_client import db

    monkeypatch.setattr(db, "client", None, raising=False)
    monkeypatch.setattr(db, "service_client", None, raising=False)
    eng = ViralReferralEngine()
    store = tmp_path / "referrals.json"
    monkeypatch.setattr(eng, "_local_store", lambda: str(store))
    return eng


def _db_mode(monkeypatch, handlers: dict[str, Any]) -> FakeSupabase:
    from database.supabase_client import db

    fake = FakeSupabase(handlers)
    monkeypatch.setattr(db, "client", fake, raising=False)
    monkeypatch.setattr(db, "service_client", fake, raising=False)
    return fake


# ───────────────────────────── code generation ────────────────────────────────


@pytest.mark.unit
class TestGenerateCodes:
    def test_generate_referral_code_local(self, engine):
        out = engine.generate_referral_code("u1")
        assert out["status"] == "success"
        assert out["code"].startswith("SUPREME-")
        assert isinstance(out["expires_at"], float) and out["expires_at"] > 0  # shape only
        saved = json.loads(Path(engine._local_store()).read_text(encoding="utf-8"))
        assert out["code"] in saved["codes"]
        assert saved["codes"][out["code"]]["referrer_id"] == "u1"

    def test_generate_codes_unique(self, engine):
        c1 = engine.generate_referral_code("u1")["code"]
        c2 = engine.generate_referral_code("u2")["code"]
        assert c1 != c2

    def test_list_user_codes_local(self, engine):
        out = engine.generate_referral_code("u1")["code"]
        engine.generate_referral_code("u2")["code"]
        codes = engine.list_user_codes("u1")
        assert [c["code"] for c in codes] == [out]

    def test_generate_referral_code_db_error_falls_back_to_local(self, engine, monkeypatch):
        def raise_exc(action, payload, filters):
            raise RuntimeError("db down")

        _db_mode(monkeypatch, {"referral_codes": raise_exc})
        # db.client truthy but service_client write fails → logged, still success
        out = engine.generate_referral_code("u9")
        assert out["status"] == "success"

    def test_db_mode_generate_and_list(self, monkeypatch):
        rows: list[dict] = []

        def handle(action, payload, filters):
            if action == "upsert":
                rows.append(payload)
                return FakeResult(payload)
            # select with eq(referrer_id)
            ref = next((v for _, c, v in filters if c == "referrer_id"), None)
            return FakeResult([r for r in rows if r.get("referrer_id") == ref])

        _db_mode(monkeypatch, {"referral_codes": handle})
        eng = ViralReferralEngine()
        code = eng.generate_referral_code("u1")["code"]
        assert rows and rows[0]["code"] == code
        listed = eng.list_user_codes("u1")
        assert listed[0]["code"] == code


# ─────────────────────────────── signup flow ──────────────────────────────────


@pytest.mark.unit
class TestProcessSignup:
    async def test_invalid_code_local(self, engine):
        out = await engine.process_signup("new1", "SUPREME-NOPE")
        assert out == {"status": "skipped", "reason": "invalid_code"}

    async def test_expired_code(self, engine):
        code = engine.generate_referral_code("ref1")["code"]
        data = json.loads(Path(engine._local_store()).read_text(encoding="utf-8"))
        data["codes"][code]["expires_at"] = 1.0  # epoch → expired
        with open(engine._local_store(), "w") as f:
            json.dump(data, f)
        out = await engine.process_signup("new1", code)
        assert out == {"status": "skipped", "reason": "expired_code"}

    async def test_fraud_detected(self, engine):
        code = engine.generate_referral_code("ref1")["code"]
        meta = {"ip_address": "1.2.3.4"}
        # Seed threshold identical-IP redemptions within 7 days
        data = json.loads(Path(engine._local_store()).read_text(encoding="utf-8"))
        data["redemptions"] = [
            {
                "referrer_id": "ref1",
                "created_at": vre.time.time(),
                "metadata": {"ip_address": "1.2.3.4"},
            }
            for _ in range(FRAUD_INDICATOR_THRESHOLD)
        ]
        with open(engine._local_store(), "w") as f:
            json.dump(data, f)
        out = await engine.process_signup("new1", code, meta)
        assert out == {"status": "skipped", "reason": "fraud_detected"}

    async def test_success_local_full_flow(self, engine):
        code = engine.generate_referral_code("ref1")["code"]
        out = await engine.process_signup("new1", code, {"ip_address": "5.6.7.8"})
        assert out["status"] == "success"
        assert out["referrer_id"] == "ref1"
        assert out["tier"] == "bronze"
        data = json.loads(Path(engine._local_store()).read_text(encoding="utf-8"))
        assert data["codes"][code]["redeemed_count"] == 1
        assert data["redemptions"][0]["new_user_id"] == "new1"

    async def test_success_second_redemption_silver_wallet_grows(self, engine):
        code = engine.generate_referral_code("ref1")["code"]
        await engine.process_signup("n1", code)
        out = await engine.process_signup("n2", code)
        assert out["credits_awarded"] == 10  # still bronze (count=1 → second is also bronze)
        wallet = engine.get_wallet_balance("ref1")
        assert wallet["balance"] == 20.0

    async def test_db_mode_success(self, monkeypatch):
        codes = {
            "SUPREME-ABC": {
                "code": "SUPREME-ABC",
                "referrer_id": "ref1",
                "status": "active",
                "redeemed_count": 0,
                "expires_at": vre.time.time() + 99999,
            }
        }
        redemptions: list[dict] = []

        def codes_handler(action, payload, filters):
            if action == "select":
                cval = next((v for _, c, v in filters if c == "code"), None)
                row = codes.get(cval)
                return FakeResult([row] if row else [])
            if action == "update":
                target = next((v for _, c, v in filters if c == "code"), None)
                codes[target]["redeemed_count"] += 1
                return FakeResult([codes[target]])
            return FakeResult(None)

        def redemptions_handler(action, payload, filters):
            if action == "insert":
                redemptions.append(payload)
                return FakeResult([payload])
            if action == "select":
                ref = next((v for _, c, v in filters if c == "referrer_id"), None)
                matched = [r for r in redemptions if r.get("referrer_id") == ref]
                # engine trusts res.count for the count="exact" aggregate query
                return FakeResult(matched, count=len(matched))
            return FakeResult(None)

        def ledger_handler(action, payload, filters):
            return FakeResult([payload] if action == "insert" else [])

        def wallets_handler(action, payload, filters):
            if action == "select":
                return FakeResult([])
            return FakeResult([payload])

        _db_mode(
            monkeypatch,
            {
                "referral_codes": codes_handler,
                "referral_redemptions": redemptions_handler,
                "credit_ledger": ledger_handler,
                "credit_wallets": wallets_handler,
            },
        )
        eng = ViralReferralEngine()
        out = await eng.process_signup("new1", "SUPREME-ABC", {"ip_address": "9.9.9.9"})
        assert out["status"] == "success"
        assert out["referrer_id"] == "ref1"
        assert codes["SUPREME-ABC"]["redeemed_count"] == 1

    async def test_db_mode_lookup_failure_skips(self, monkeypatch):
        def boom(action, payload, filters):
            raise RuntimeError("lookup exploded")

        _db_mode(monkeypatch, {"referral_codes": boom})
        eng = ViralReferralEngine()
        out = await eng.process_signup("n", "SUPREME-XYZ")
        assert out == {"status": "skipped", "reason": "invalid_code"}


# ─────────────────────────────── fraud logic ──────────────────────────────────


@pytest.mark.unit
class TestFraud:
    def test_is_fraudulent_same_device(self, engine):
        engine.generate_referral_code("ref1")
        meta = {"device_fingerprint": "dev-1"}
        data = json.loads(Path(engine._local_store()).read_text(encoding="utf-8"))
        data["redemptions"] = [
            {
                "referrer_id": "ref1",
                "created_at": vre.time.time(),
                "metadata": {"device_fingerprint": "dev-1"},
            }
            for _ in range(FRAUD_INDICATOR_THRESHOLD)
        ]
        with open(engine._local_store(), "w") as f:
            json.dump(data, f)
        assert engine._is_fraudulent("ref1", "new9", meta) is True

    def test_not_fraudulent_when_under_threshold(self, engine):
        data = {
            "redemptions": [
                {
                    "referrer_id": "r",
                    "created_at": vre.time.time(),
                    "metadata": {"ip_address": "1.1.1.1"},
                }
            ]
        }
        with open(engine._local_store(), "w") as f:
            json.dump(data, f)
        assert engine._is_fraudulent("r", "n", {"ip_address": "1.1.1.1"}) is False

    def test_old_redemptions_ignored(self, engine):
        data = {
            "redemptions": [
                {
                    "referrer_id": "r",
                    "created_at": vre.time.time() - 30 * 86400,
                    "metadata": {"ip_address": "2.2.2.2"},
                }
                for _ in range(5)
            ]
        }
        with open(engine._local_store(), "w") as f:
            json.dump(data, f)
        assert engine._is_fraudulent("r", "n", {"ip_address": "2.2.2.2"}) is False

    def test_db_mode_fraud_history_error(self, monkeypatch):
        def boom(action, payload, filters):
            raise RuntimeError("no history")

        _db_mode(monkeypatch, {"referral_redemptions": boom})
        eng = ViralReferralEngine()
        assert eng._is_fraudulent("r", "n", {"ip_address": None}) is False


# ─────────────────────────────── rewards / wallet ─────────────────────────────


@pytest.mark.unit
class TestRewards:
    def test_calculate_reward_local_counts(self, engine):
        data = {
            "redemptions": [{"referrer_id": "r1", "created_at": vre.time.time()} for _ in range(6)]
        }
        with open(engine._local_store(), "w") as f:
            json.dump(data, f)
        out = engine._calculate_reward("r1")
        assert out["count"] == 6
        assert out["tier"] == "silver"
        assert out["credit_bonus"] == 50

    def test_calculate_reward_db_count_attr(self, monkeypatch):
        def handler(action, payload, filters):
            return FakeResult(data=[], count=55)

        _db_mode(monkeypatch, {"referral_redemptions": handler})
        eng = ViralReferralEngine()
        out = eng._calculate_reward("r")
        assert out["tier"] == "platinum"
        assert out["count"] == 55

    def test_calculate_reward_db_error(self, monkeypatch):
        def boom(action, payload, filters):
            raise RuntimeError("count failed")

        _db_mode(monkeypatch, {"referral_redemptions": boom})
        eng = ViralReferralEngine()
        out = eng._calculate_reward("r")
        assert out["count"] == 0
        assert out["tier"] == "bronze"

    def test_credit_wallet_and_balance_local(self, engine):
        engine._credit_wallet("u1", 25.0, "bonus")
        engine._credit_wallet("u1", 5.0, "bonus2")
        assert engine.get_wallet_balance("u1")["balance"] == 30.0
        data = json.loads(Path(engine._local_store()).read_text(encoding="utf-8"))
        assert len(data["ledger"]) == 2

    def test_get_wallet_unknown_user(self, engine):
        assert engine.get_wallet_balance("ghost")["balance"] == 0.0

    def test_credit_wallet_db_mode(self, monkeypatch):
        wallets: dict[str, dict] = {}

        def w_handler(action, payload, filters):
            if action == "select":
                uid = next((v for _, c, v in filters if c == "user_id"), None)
                row = wallets.get(uid)
                return FakeResult([row] if row else [])
            if action == "upsert":
                wallets[payload["user_id"]] = payload
                return FakeResult([payload])
            return FakeResult(None)

        ledger: list = []

        def l_handler(action, payload, filters):
            if action == "insert":
                ledger.append(payload)
            return FakeResult([payload] if action == "insert" else [])

        _db_mode(monkeypatch, {"credit_wallets": w_handler, "credit_ledger": l_handler})
        eng = ViralReferralEngine()
        out = eng._credit_wallet("u", 10.0, "r")
        assert out["balance"] == 10.0
        assert len(ledger) == 1

    def test_get_ledger_local_and_limit(self, engine):
        for i in range(5):
            engine._credit_wallet("u1", 1.0, f"r{i}")
        engine._credit_wallet("u2", 9.0, "other")
        ledger = engine.get_ledger("u1", limit=3)
        assert len(ledger) == 3
        assert all(r["user_id"] == "u1" for r in ledger)

    def test_get_ledger_db_mode(self, monkeypatch):
        def handler(action, payload, filters):
            return FakeResult([{"user_id": "u", "amount": 1}])

        _db_mode(monkeypatch, {"credit_ledger": handler})
        eng = ViralReferralEngine()
        assert len(eng.get_ledger("u")) == 1

    def test_get_wallet_db_error(self, monkeypatch):
        def boom(action, payload, filters):
            raise RuntimeError("wallet down")

        _db_mode(monkeypatch, {"credit_wallets": boom})
        eng = ViralReferralEngine()
        assert eng.get_wallet_balance("u")["balance"] == 0.0


# ─────────────────────────────── deep links / shares ──────────────────────────


@pytest.mark.unit
class TestSharing:
    def test_deep_link_all_platforms(self, engine):
        base = engine.generate_deep_link("SUPREME-X", "generic")
        assert base.endswith("/invite/SUPREME-X")
        assert "twitter.com/intent/tweet" in engine.generate_deep_link("C", "twitter")
        assert "facebook.com/sharer" in engine.generate_deep_link("C", "facebook")
        assert "linkedin.com" in engine.generate_deep_link("C", "linkedin")
        assert "api.whatsapp.com" in engine.generate_deep_link("C", "whatsapp")
        assert "t.me/share" in engine.generate_deep_link("C", "telegram")
        # case-insensitive + unknown platform fallback
        assert engine.generate_deep_link("C", "TWITTER").startswith("https://twitter.com")
        assert engine.generate_deep_link("C", "myspace") == engine.generate_deep_link(
            "C", "generic"
        )

    def test_record_social_share_local(self, engine):
        out = engine.record_social_share("u1", "SUPREME-C", "twitter")
        assert out["status"] == "success"
        assert "twitter" in out["deep_link"]
        data = json.loads(Path(engine._local_store()).read_text(encoding="utf-8"))
        assert data["social_shares"][0]["platform"] == "twitter"

    def test_record_social_share_db_error_swallowed(self, engine, monkeypatch):
        def boom(action, payload, filters):
            raise RuntimeError("share insert failed")

        _db_mode(monkeypatch, {"referral_redemptions": boom})
        out = engine.record_social_share("u1", "C", "linkedin")
        assert out["status"] == "success"


# ─────────────────────────────── stripe payouts ───────────────────────────────


@pytest.mark.unit
class TestStripePayout:
    def test_payout_skipped_without_api_key(self, engine, monkeypatch):
        from core.config import settings

        monkeypatch.setattr(
            type(settings), "_get_cached_secret", lambda self, key: "", raising=False
        )
        out = engine._stripe_payout("u", 1000)
        assert out == {"status": "skipped", "reason": "stripe_not_configured"}

    def test_payout_success(self, engine, monkeypatch):
        import stripe as real_stripe
        from pydantic import SecretStr

        from core.config import settings

        monkeypatch.setattr(
            type(settings),
            "stripe_api_key",
            property(lambda self: SecretStr("sk_test_x")),
            raising=False,
        )
        monkeypatch.setattr(
            real_stripe.Payout,
            "create",
            classmethod(lambda cls, **kw: SimpleNamespace(id="po_123")),
        )
        out = engine._stripe_payout("u", 6000)
        assert out == {
            "status": "success",
            "payout_id": "po_123",
            "amount": 6000,
            "currency": "usd",
        }

    def test_payout_error(self, engine, monkeypatch):
        import stripe as real_stripe
        from pydantic import SecretStr

        from core.config import settings

        monkeypatch.setattr(
            type(settings),
            "stripe_api_key",
            property(lambda self: SecretStr("sk_test_x")),
            raising=False,
        )

        def boom(**kw):
            raise RuntimeError("card_declined")

        monkeypatch.setattr(real_stripe.Payout, "create", classmethod(lambda cls, **kw: boom()))
        out = engine._stripe_payout("u", 100)
        assert out["status"] == "error"
        assert "card_declined" in out["reason"]

    def test_credit_stripe_payout_below_threshold(self, engine, monkeypatch):
        from pydantic import SecretStr

        from core.config import settings

        monkeypatch.setattr(
            type(settings),
            "stripe_api_key",
            property(lambda self: SecretStr("sk_test_x")),
            raising=False,
        )
        out = engine._credit_stripe_payout("u", {"reward": 5.0})
        assert out["status"] == "credited"
        assert out["balance"] == 5.0

    def test_credit_stripe_payout_full_cycle(self, engine, monkeypatch):
        import stripe as real_stripe
        from pydantic import SecretStr

        from core.config import settings

        monkeypatch.setattr(
            type(settings),
            "stripe_api_key",
            property(lambda self: SecretStr("sk_test_x")),
            raising=False,
        )
        engine._credit_wallet("u", 49.0, "seed")
        monkeypatch.setattr(
            real_stripe.Payout,
            "create",
            classmethod(lambda cls, **kw: SimpleNamespace(id="po_9")),
        )
        out = engine._credit_stripe_payout("u", {"reward": 2.0})
        assert out["status"] == "paid"
        assert out["payout"]["payout_id"] == "po_9"
        # wallet zeroed after payout
        assert engine.get_wallet_balance("u")["balance"] == 0.0

    def test_credit_stripe_payout_failure_keeps_balance(self, engine, monkeypatch):
        import stripe as real_stripe
        from pydantic import SecretStr

        from core.config import settings

        monkeypatch.setattr(
            type(settings),
            "stripe_api_key",
            property(lambda self: SecretStr("sk_test_x")),
            raising=False,
        )
        engine._credit_wallet("u", 60.0, "seed")

        def boom(**kw):
            raise RuntimeError("network")

        monkeypatch.setattr(real_stripe.Payout, "create", classmethod(lambda cls, **kw: boom()))
        out = engine._credit_stripe_payout("u", {"reward": 0.0})
        assert out["status"] == "credited"
        assert engine.get_wallet_balance("u")["balance"] == 60.0


# ─────────────────────────────── module metadata ──────────────────────────────


@pytest.mark.unit
def test_reward_tier_table():
    names = [t["name"] for t in vre.REWARD_TIERS]
    assert names == ["bronze", "silver", "gold", "platinum"]
    thresholds = [t["threshold"] for t in vre.REWARD_TIERS]
    assert thresholds == sorted(thresholds)
