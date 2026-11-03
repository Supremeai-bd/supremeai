"""#1828 billing — single pricing source of truth + scheduled quota enforcer tests.

বাংলা: billing_plans এখন pricing_tiers.json থেকে tier price পড়ে (checkout ও
quota allowance আর কখনো আলাদা সংখ্যা দেখাবে না); quota enforcer একটি
supervisor loop-এ নির্ধারিতভাবে চলে (ENABLE_QUOTA_ENFORCER=true)।
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest


@pytest.fixture()
def pricing_file(tmp_path: Path) -> Path:
    data = {
        "signup_bonus_usd": 5.0,
        "tiers": {
            "free": {"name": "Free Tier", "monthly_credits_usd": 0.0, "max_parallel_tasks": 1},
            "pro": {"name": "Pro Tier", "monthly_credits_usd": 10.0, "max_parallel_tasks": 5},
            "enterprise": {
                "name": "Enterprise Tier",
                "monthly_credits_usd": 100.0,
                "max_parallel_tasks": 50,
            },
        },
    }
    path = tmp_path / "pricing_tiers.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture()
def reload_billing_plans(monkeypatch):
    """Import billing_plans fresh with a controlled PRICING_TIERS_PATH."""

    def _load(path: Path | None):
        import importlib
        import sys

        monkeypatch.setenv("PRICING_TIERS_PATH", str(path or "/nonexistent/pricing_tiers.json"))
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        for mod_name in [m for m in sys.modules if m.endswith("billing_plans")]:
            del sys.modules[mod_name]
        import services.billing.billing_plans as bp  # noqa: PLC0415 — test-scoped reload

        module = importlib.reload(bp)
        yield module
        sys.path.pop(0)

    return _load


class TestPricingSourceOfTruth:
    def test_prices_loaded_from_config_file(self, pricing_file, reload_billing_plans):
        bp = next(reload_billing_plans(pricing_file))
        assert bp.SUBSCRIPTION_PLANS["pro"].cost == Decimal("10.00")
        assert bp.SUBSCRIPTION_PLANS["pro"].price == pytest.approx(10.00)
        assert bp.SUBSCRIPTION_PLANS["enterprise"].cost == Decimal("100.00")
        assert bp.SUBSCRIPTION_PLANS["free"].cost == Decimal("0.00")

    def test_prices_match_quota_enforcer_allowance(self, pricing_file, reload_billing_plans):
        """Checkout price == quota allowance — the #1828 core contract."""
        bp = next(reload_billing_plans(pricing_file))
        cfg = json.loads(pricing_file.read_text(encoding="utf-8"))
        for tier in ("free", "pro", "enterprise"):
            allowance = Decimal(str(cfg["tiers"][tier]["monthly_credits_usd"]))
            assert bp.SUBSCRIPTION_PLANS[tier].cost == allowance

    def test_missing_config_falls_back_to_config_defaults(self, reload_billing_plans):
        bp = next(reload_billing_plans(None))
        # Fallbacks mirror backend/config/pricing_tiers.json (10.00 / 100.00)
        assert bp.SUBSCRIPTION_PLANS["pro"].cost == Decimal("10.00")
        assert bp.SUBSCRIPTION_PLANS["enterprise"].cost == Decimal("100.00")
        assert bp.SUBSCRIPTION_PLANS["free"].cost == Decimal("0.00")

    def test_stripe_price_ids_stable(self, pricing_file, reload_billing_plans):
        """Only Stripe price IDs stay hardcoded — checkout integration intact."""
        bp = next(reload_billing_plans(pricing_file))
        assert bp.SUBSCRIPTION_PLANS["free"].id == "price_free"
        assert bp.SUBSCRIPTION_PLANS["pro"].id == "price_pro_monthly"
        assert bp.SUBSCRIPTION_PLANS["enterprise"].id == "price_enterprise_monthly"

    def test_list_format_backward_compatible(self, pricing_file, reload_billing_plans):
        bp = next(reload_billing_plans(pricing_file))
        ids = [p["id"] for p in bp.SUBSCRIPTION_PLANS_LIST]
        assert ids == ["price_free", "price_pro_monthly", "price_enterprise_monthly"]


class TestQuotaEnforcerScheduler:
    def test_startup_module_registers_quota_enforcer_agent(self):
        """The scheduled supervisor agent exists in startup wiring (#1828)."""
        import core.startup as startup_pkg  # noqa: F401 — package import sanity

        source = Path(startup_pkg.__file__).resolve().parent / "agents.py"
        text = source.read_text(encoding="utf-8")
        assert "quota-enforcer" in text
        assert "ENABLE_QUOTA_ENFORCER" in text
        assert "--enforce-all" in text
        assert "QUOTA_ENFORCE_INTERVAL_HOURS" in text
        assert "--notify" in text

    def test_enforcer_cli_supports_enforce_all(self):
        """CLI contract the scheduler relies on (--enforce-all + --notify)."""
        repo_root = Path(__file__).resolve().parents[3]
        cli = repo_root / "scripts" / "billing" / "quota_enforcer.py"
        text = cli.read_text(encoding="utf-8")
        assert '"--enforce-all"' in text
        assert '"--notify"' in text
        assert '"--dry-run"' in text
        assert '"--grace-hours"' in text
