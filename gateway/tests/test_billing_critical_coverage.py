"""Billing plans critical coverage tests (#3267).

বাংলা: services/billing/billing_plans.py-এর আসল contract-গুলোর
critical-path coverage — real model schema, pricing SSOT (#1828),
fallback behaviour, CheckoutRequest validation।
প্রতিটি test আসল module-এর বিরুদ্ধে চলে (কোনো self-made mock নয়)।
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

# ── SubscriptionPlan real-schema tests (dataclass contract) ─────────────────


class TestSubscriptionPlanSchema:
    """#3267: SubscriptionPlan dataclass — আসল ফিল্ড: id, name, price, cost,
    currency, interval, features।"""

    def test_plan_has_all_three_tiers(self):
        from services.billing.billing_plans import SUBSCRIPTION_PLANS

        assert set(SUBSCRIPTION_PLANS.keys()) >= {"free", "pro", "enterprise"}

    def test_plan_fields_match_real_schema(self):
        from services.billing.billing_plans import SUBSCRIPTION_PLANS

        for key, plan in SUBSCRIPTION_PLANS.items():
            assert isinstance(plan.id, str) and plan.id, f"{key}: id"
            assert isinstance(plan.name, str) and plan.name, f"{key}: name"
            assert isinstance(plan.price, float), f"{key}: price float"
            assert isinstance(plan.cost, Decimal), f"{key}: cost Decimal"
            assert plan.currency == "usd", f"{key}: currency"
            assert plan.interval == "month", f"{key}: interval"
            assert isinstance(plan.features, list) and plan.features, f"{key}: features"

    def test_price_and_cost_are_consistent(self):
        # বাংলা: float price আর Decimal cost একই মান বহন করে
        from services.billing.billing_plans import SUBSCRIPTION_PLANS

        for key, plan in SUBSCRIPTION_PLANS.items():
            assert Decimal(str(plan.price)) == plan.cost, f"{key}: price/cost mismatch"

    def test_tier_ordering_monotonic(self):
        # বাংলা: free <= pro <= enterprise (pricing sanity)
        from services.billing.billing_plans import SUBSCRIPTION_PLANS

        assert SUBSCRIPTION_PLANS["free"].cost <= SUBSCRIPTION_PLANS["pro"].cost
        assert SUBSCRIPTION_PLANS["pro"].cost <= SUBSCRIPTION_PLANS["enterprise"].cost


# ── Pricing SSOT contract (#1828) ─────────────────────────────────────────────


class TestPricingSingleSourceOfTruth:
    """#3267 + #1828: SUBSCRIPTION_PLANS-এর দাম backend/config/pricing_tiers.json-এর
    সাথে অবশ্যই মিলবে — Stripe catalog আর quota enforcer কখনো disagree করবে না।"""

    def test_plans_match_pricing_tiers_json(self):
        # বাংলা: config path — billing_plans module থেকে relative (আসল SSOT ফাইল)
        from pathlib import Path

        import services.billing.billing_plans as bp
        from services.billing.billing_plans import SUBSCRIPTION_PLANS

        config_path = Path(bp.__file__).resolve().parents[2] / "config" / "pricing_tiers.json"
        data = json.loads(config_path.read_text(encoding="utf-8"))
        tiers = data["tiers"]
        for tier in ("free", "pro", "enterprise"):
            expected = Decimal(str(tiers[tier]["monthly_credits_usd"]))
            assert SUBSCRIPTION_PLANS[tier].cost == expected, (
                f"{tier}: plan cost {SUBSCRIPTION_PLANS[tier].cost} != "
                f"pricing_tiers.json {expected} — SSOT (#1828) ভাঙছে"
            )

    def test_unknown_tier_falls_back_to_defaults(self, monkeypatch):
        # বাংলা: config ফাইল না পেলে fallback দাম ব্যবহার হবে (0/10/100)
        import services.billing.billing_plans as bp

        monkeypatch.setenv("PRICING_TIERS_PATH", "/nonexistent/pricing.json")
        monkeypatch.setattr(bp, "_TIER_PRICES", None)  # cache reset
        assert bp._tier_price("free") == Decimal("0.00")
        assert bp._tier_price("pro") == Decimal("10.00")
        assert bp._tier_price("enterprise") == Decimal("100.00")

    def test_corrupt_config_never_raises_at_lookup(self, monkeypatch, tmp_path):
        # বাংলা: ভাঙা JSON → {} → fallback; import-time/lookup-time কখনো raise নয়
        import services.billing.billing_plans as bp

        bad = tmp_path / "bad.json"
        bad.write_text("{not-valid-json", encoding="utf-8")
        monkeypatch.setenv("PRICING_TIERS_PATH", str(bad))
        monkeypatch.setattr(bp, "_TIER_PRICES", None)
        assert bp._load_tier_prices() == {}
        assert bp._tier_price("pro") == Decimal("10.00")  # fallback

    def test_unknown_tier_name_raises_keyerror(self, monkeypatch):
        # বাংলা: অজানা tier fallback-এও নেই → দ্রুত fail (fail-loud)
        import services.billing.billing_plans as bp

        monkeypatch.setenv("PRICING_TIERS_PATH", "/nonexistent/pricing.json")
        monkeypatch.setattr(bp, "_TIER_PRICES", None)
        with pytest.raises(KeyError):
            bp._tier_price("platinum")


# ── CheckoutRequest validation contract (pydantic) ──────────────────────────


class TestCheckoutRequestContract:
    """#3267: CheckoutRequest — price_id/success_url/cancel_url আবশ্যক,
    user_id optional।"""

    def test_valid_checkout_request(self):
        from services.billing.billing_plans import CheckoutRequest

        req = CheckoutRequest(
            price_id="price_pro_monthly",
            success_url="https://app.example.com/success",
            cancel_url="https://app.example.com/cancel",
        )
        assert req.price_id == "price_pro_monthly"
        assert req.user_id is None  # optional, default None

    def test_missing_price_id_rejected(self):
        from pydantic import ValidationError

        from services.billing.billing_plans import CheckoutRequest

        with pytest.raises(ValidationError):
            CheckoutRequest(
                success_url="https://app.example.com/success",
                cancel_url="https://app.example.com/cancel",
            )

    def test_missing_urls_rejected(self):
        from pydantic import ValidationError

        from services.billing.billing_plans import CheckoutRequest

        with pytest.raises(ValidationError):
            CheckoutRequest(price_id="price_pro_monthly")

    def test_user_id_accepted(self):
        from services.billing.billing_plans import CheckoutRequest

        req = CheckoutRequest(
            price_id="price_free",
            success_url="https://a.example/s",
            cancel_url="https://a.example/c",
            user_id="user-123",
        )
        assert req.user_id == "user-123"


# ── Backward-compat list format ──────────────────────────────────────────────


class TestSubscriptionPlansListCompat:
    """#3267: SUBSCRIPTION_PLANS_LIST — legacy list format-এর চুক্তি।"""

    def test_list_format_keys(self):
        from services.billing.billing_plans import SUBSCRIPTION_PLANS, SUBSCRIPTION_PLANS_LIST

        assert len(SUBSCRIPTION_PLANS_LIST) == len(SUBSCRIPTION_PLANS)
        for entry in SUBSCRIPTION_PLANS_LIST:
            assert {"id", "name", "price", "currency", "interval", "features"} <= set(entry.keys())

    def test_list_matches_dict_values(self):
        from services.billing.billing_plans import SUBSCRIPTION_PLANS, SUBSCRIPTION_PLANS_LIST

        by_id = {p["id"]: p for p in SUBSCRIPTION_PLANS_LIST}
        for key, plan in SUBSCRIPTION_PLANS.items():
            assert by_id[plan.id]["name"] == plan.name
            assert by_id[plan.id]["price"] == plan.price
