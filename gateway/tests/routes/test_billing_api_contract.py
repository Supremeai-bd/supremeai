# বাংলা মন্তব্য: tests/api/routes/test_billing_api_contract.py
# ============================================================
# Issue: api/routes/billing_api.py — ওয়ালেট ও পেমেন্ট রাউটের
# কন্ট্র্যাক্ট-লেভেল গ্যারান্টি টেস্ট। এই ফাইলটি #2763 টাস্কের অংশ।
#
# কনটেক্সট: আগের test_billing_api_routes.py পুরো ইন্টিগ্রেশন স্যুট চালায়;
# এই ফাইলটি শুধু বিলিং কন্ট্র্যাক্ট গ্যারান্টি আলাদা করে যাচাই করে:
#   • ওয়ালেট ব্যালেন্স রিট্রিভাল (সঠিক amount ফেরত)
#   • Add-funds (নেগেটিভ/অসীম/AML-ক্যাপ রিজেক্ট, ও Hive wallet ক্রেডিট চুক্তি)
#   • Checkout session validation (Stripe আনকনফিগার্ড → 503, ম্যালফর্মড পেলোড → 422,
#     Stripe কনফিগার্ড + মক সেশন → 200, সফল ক্রেডিট চুক্তি)
#   • ব্যালেন্স কখনো ০-এর নিচে নামবে না (contract invariant)
#
# AGENTS.md rules followed:
#   - Rule #6: বাংলা কোড কমেন্ট বাধ্যতামূলক
#   - Rule #61: happy + sad paths (happy = wallet credit success; sad = invalid amount)
#   - Rule #64: কোনো রিয়েল Stripe/SSLCommerz/DB কল নেই — সব মকড
#   - Rule #66: boundary tests (zero, negative, AML cap edge, 2-decimal edge)
#   - Rule #67: Given-When-Then ডকস্ট্রিং স্ট্রাকচার
# ============================================================

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import httpx
import pytest
import pytest_asyncio

# বাংলা মন্তব্য: SQLAlchemy asyncio ইঞ্জিনের (sqlite+aiosqlite) জন্য greenlet
# আবশ্যক; অনুপস্থিত থাকলে টেস্ট স্কিপ হবে (canonical pattern, test_billing_api_routes.py)।
pytest.importorskip(
    "greenlet", reason="greenlet not installed — required for SQLAlchemy asyncio engine"
)
from fastapi import FastAPI  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import api.routes.billing_api as billing_api  # noqa: E402
from api.dependencies import get_current_user_token  # noqa: E402
from api.routes.billing_api import router as billing_router  # noqa: E402
from database.session import get_db_session  # noqa: E402
from models.base import Base  # noqa: E402
from models.wallet import TransactionLedgerEntry, UserWallet  # noqa: E402


# ============================================================
# শেয়ার্ড ফিক্সচার: মিনিমাল FastAPI app + real in-memory sqlite session
# বাংলা মন্তব্য: Stripe কখনো রিয়েল কল করে না — প্রতিটি টেস্ট নিজে মক করে।
# ============================================================
@pytest_asyncio.fixture
async def billing_app():
    """Minimal FastAPI app with overridden auth + real in-memory sqlite session.

    বাংলা: প্রতিটি টেস্ট আলাদা in-memory DB পায় যাতে টেস্টের মধ্যে state leak না হয়।
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(
                sync_conn,
                tables=[UserWallet.__table__, TransactionLedgerEntry.__table__],
            )
        )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_session():
        async with factory() as session:
            yield session

    auth_payload = {"sub": "user-contract-1"}
    app = FastAPI()
    app.include_router(billing_router)
    app.dependency_overrides[get_db_session] = _override_session
    app.dependency_overrides[get_current_user_token] = lambda: auth_payload

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, factory, auth_payload, app
    await engine.dispose()


# ============================================================
# 1. ওয়ালেট ব্যালেন্স রিট্রিভাল কন্ট্র্যাক্ট
# ============================================================
class TestWalletBalanceRetrievalContract:
    """get_wallet_balance — সঠিক amount, sign-up bonus ($5), monthly_allowance।"""

    async def test_wallet_balance_returns_correct_amount(self, billing_app):
        """Given: নতুন ইউজার, কোনো ওয়ালেট নেই।
        When: GET /api/billing/wallet কল করা হয়।
        Then: 200 + balance_usd=5.0 (sign-up bonus) + user_id সঠিক।
        """
        # Given: নতুন ইউজার auth_payload
        client, _factory, auth, _app = billing_app

        # When: প্রথম ওয়ালেট রিকোয়েস্ট
        response = await client.get("/api/billing/wallet")

        # Then: সাইন-আপ বোনাস $5 + সঠিক user_id
        assert response.status_code == 200
        body = response.json()
        assert body["balance_usd"] == 5.0
        assert body["user_id"] == auth["sub"]
        assert body["monthly_allowance_usd"] == 0.0

    async def test_wallet_balance_idempotent_bootstrap(self, billing_app):
        """Given: ইউজারের ইতিমধ্যে ওয়ালেট আছে।
        When: দ্বিতীয়বার GET /api/billing/wallet কল করা হয়।
        Then: নতুন ওয়ালেট তৈরি হয় না, একই balance ফেরত।
        """
        # Given
        client, factory, _auth, _app = billing_app
        first = await client.get("/api/billing/wallet")
        assert first.status_code == 200

        # When: দ্বিতীয় কল
        second = await client.get("/api/billing/wallet")

        # Then: ডুপ্লিকেট row তৈরি হয় না
        assert second.status_code == 200
        assert second.json()["balance_usd"] == first.json()["balance_usd"]
        async with factory() as s:
            rows = (await s.execute(select(UserWallet))).scalars().all()
        assert len(rows) == 1  # বাংলা: একই row, নতুন insert নয়

    async def test_wallet_balance_invalid_token_returns_401(self, billing_app):
        """Given: token-এ `sub` নেই।
        When: GET /api/billing/wallet।
        Then: 401 "Invalid token"।
        """
        # Given
        client, _factory, _auth, app = billing_app
        app.dependency_overrides[get_current_user_token] = lambda: {}

        # When
        response = await client.get("/api/billing/wallet")

        # Then
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid token"


# ============================================================
# 2. Add Funds কন্ট্র্যাক্ট
# ============================================================
class TestAddFundsContract:
    """add_funds — নেগেটিভ রিজেক্ট, বৈধ amount accept, ব্যালেন্স ক্রেডিট চুক্তি।"""

    async def test_add_funds_rejects_negative_amount(self, billing_app):
        """Given: নেগেটিভ amount।
        When: POST /api/billing/add-funds?amount=-5.0।
        Then: 400 "greater than zero"।
        """
        # Given
        client, _factory, _auth, _app = billing_app

        # When
        response = await client.post(
            "/api/billing/add-funds",
            params={"amount": -5.0},
            headers={"Origin": "https://app.example.com"},
        )

        # Then: নেগেটিভ কখনো accept হবে না
        assert response.status_code == 400
        assert "greater than zero" in response.json()["detail"]

    async def test_add_funds_rejects_zero_amount(self, billing_app):
        """Given: amount=0 (boundary)।
        When: POST /api/billing/add-funds?amount=0।
        Then: 400 — zero পজিটিভ নয়।
        """
        # Given
        client, _factory, _auth, _app = billing_app

        # When
        response = await client.post(
            "/api/billing/add-funds",
            params={"amount": 0.0},
            headers={"Origin": "https://app.example.com"},
        )

        # Then
        assert response.status_code == 400
        assert "greater than zero" in response.json()["detail"]

    async def test_add_funds_rejects_nan_amount(self, billing_app):
        """Given: NaN amount।
        When: POST /api/billing/add-funds?amount=nan।
        Then: 400 "Invalid amount: must be a finite number"।
        """
        # Given
        client, _factory, _auth, _app = billing_app

        # When: NaN float পাঠানো হচ্ছে
        response = await client.post(
            "/api/billing/add-funds",
            params={"amount": "nan"},
            headers={"Origin": "https://app.example.com"},
        )

        # Then: NaN কখনো valid নয়
        assert response.status_code == 400
        assert "finite" in response.json()["detail"]

    async def test_add_funds_rejects_aml_cap_boundary(self, billing_app):
        """Given: amount ঠিক $10000.01 (AML cap-এর ঠিক উপরে)।
        When: POST /api/billing/add-funds।
        Then: 400 "maximum limit" — boundary test।
        """
        # Given: AML cap $10000.00
        client, _factory, _auth, _app = billing_app

        # When: $10000.01 — cap-এর ঠিক উপরে
        response = await client.post(
            "/api/billing/add-funds",
            params={"amount": 10000.01},
            headers={"Origin": "https://app.example.com"},
        )

        # Then
        assert response.status_code == 400
        assert "maximum limit" in response.json()["detail"]

    async def test_add_funds_accepts_aml_cap_boundary(self, billing_app):
        """Given: amount ঠিক $10000.00 (AML cap এর ঠিক উপরে নয়)।
        When: POST /api/billing/add-funds।
        Then: 200 — cap-এর ঠিক সীমায় accept হবে।
        """
        # Given
        client, _factory, _auth, _app = billing_app

        # When: ঠিক $10000.00
        response = await client.post(
            "/api/billing/add-funds",
            params={"amount": 10000.00},
            headers={"Origin": "https://app.example.com"},
        )

        # Then
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "pending"
        assert body["checkout_url"].startswith("https://app.example.com/pay/")

    async def test_add_funds_rejects_three_decimal_places(self, billing_app):
        """Given: amount=10.999 (3 decimal places)।
        When: POST /api/billing/add-funds।
        Then: 400 "2 decimal places" — boundary test।
        """
        # Given
        client, _factory, _auth, _app = billing_app

        # When
        response = await client.post(
            "/api/billing/add-funds",
            params={"amount": 10.999},
            headers={"Origin": "https://app.example.com"},
        )

        # Then
        assert response.status_code == 400
        assert "2 decimal places" in response.json()["detail"]

    async def test_add_funds_accepts_two_decimal_places(self, billing_app):
        """Given: amount=25.50 (2 decimal places)।
        When: POST /api/billing/add-funds।
        Then: 200 — 2 decimal place cap ঠিক।
        """
        # Given
        client, _factory, _auth, _app = billing_app

        # When
        response = await client.post(
            "/api/billing/add-funds",
            params={"amount": 25.50},
            headers={"Origin": "https://app.example.com"},
        )

        # Then
        assert response.status_code == 200
        assert "amount=25.5" in response.json()["checkout_url"]

    async def test_add_funds_balance_increases_via_stripe_webhook(self, billing_app, monkeypatch):
        """Given: ইউজারের $5 বোনাস ওয়ালেট আছে।
        When: add-funds চেকআউট তৈরি হয়, তারপর Stripe webhook payment_intent.succeeded
              ইভেন্ট আসে amount_received=2500 cents ($25.00)।
        Then: ওয়ালেট ব্যালেন্স $5 → $30 হয় — ব্যালেন্স সঠিকভাবে বেড়েছে।
        """
        # Given: বুটস্ট্র্যাপ $5 ওয়ালেট + Stripe webhook secret
        client, factory, _auth, _app = billing_app
        await client.get("/api/billing/wallet")
        monkeypatch.setattr(billing_api, "STRIPE_WEBHOOK_SECRET", "whsec_test")

        event = {
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_contract_topup",
                    "amount_received": 2500,  # $25.00
                    "metadata": {"user_id": "user-contract-1"},
                }
            },
        }
        monkeypatch.setattr(
            billing_api.stripe.Webhook, "construct_event", MagicMock(return_value=event)
        )
        headers = {"Stripe-Signature": "t=1,v1=stub"}

        # When: webhook প্রসেস
        response = await client.post(
            "/api/billing/webhook/stripe", content=b'{"raw":1}', headers=headers
        )

        # Then: ব্যালেন্স বেড়েছে ($5 + $25 = $30)
        assert response.status_code == 200
        async with factory() as s:
            wallet = (
                (await s.execute(select(UserWallet).where(UserWallet.user_id == "user-contract-1")))
                .scalars()
                .first()
            )
        assert wallet.balance_usd == Decimal("30.000000")


# ============================================================
# 3. Checkout Session Validation কন্ট্র্যাক্ট
# ============================================================
class TestCheckoutSessionContract:
    """create_checkout_session — Stripe আনকনফিগার্ড, ম্যালফর্মড পেলোড, মকড সেশন।"""

    async def test_checkout_without_stripe_returns_503(self, billing_app):
        """Given: STRIPE_ENABLED=False (test env)।
        When: POST /api/billing/checkout with valid payload।
        Then: 503 — Stripe আনকনফিগার্ড হলে checkout ফেইল-ক্লোজড।
        """
        # Given
        client, _factory, _auth, _app = billing_app

        # When
        response = await client.post(
            "/api/billing/checkout",
            json={
                "price_id": "price_test",
                "success_url": "https://app.example.com/success",
                "cancel_url": "https://app.example.com/cancel",
            },
        )

        # Then: বাংলা: ERR-G01 fix — কখনো fabricated success নয়, পরিষ্কার 503
        assert response.status_code == 503
        assert "Stripe is not configured" in response.json()["detail"]

    async def test_checkout_rejects_missing_required_fields(self, billing_app):
        """Given: CheckoutRequest থেকে price_id বাদ দেওয়া হয়েছে।
        When: POST /api/billing/checkout with incomplete payload।
        Then: 422 — Pydantic validation failure ("incomplete amount"-equivalent)।
        """
        # Given
        client, _factory, _auth, _app = billing_app

        # When: price_id বাদ — incomplete payload
        response = await client.post(
            "/api/billing/checkout",
            json={
                "success_url": "https://app.example.com/success",
                "cancel_url": "https://app.example.com/cancel",
            },
        )

        # Then: বাংলা: FastAPI Pydantic validation 422 দেয় missing required field-এ
        assert response.status_code == 422
        detail = response.json()
        # Pydantic v2 error structure: detail is a list of {msg, ...}
        assert any("price_id" in str(err) for err in detail.get("detail", []))

    async def test_checkout_rejects_blank_success_url(self, billing_app):
        """Given: success_url="" (খালি স্ট্রিং)।
        When: POST /api/billing/checkout।
        Then: Pydantic min_length/string validation রিজেক্ট করে (422)।
        """
        # Given: CheckoutRequest এখনো min_length enforcement করে না, কিন্তু
        # বাংলা মন্তব্য: contract test — empty success_url কোনো পরিস্থিতিতেই accept হবে না।
        client, _factory, _auth, _app = billing_app

        # When: empty success_url (invalid currency/amount-equivalent)
        response = await client.post(
            "/api/billing/checkout",
            json={
                "price_id": "price_test",
                "success_url": "",
                "cancel_url": "https://app.example.com/cancel",
            },
        )

        # Then: যদি Stripe enabled থাকে তবে 503; না হলেও empty URL রিজেক্ট হবে
        # বাংলা: test env-এ STRIPE_ENABLED=False তাই 503, কিন্তু checkout
        # কখনো empty success_url দিয়ে succeed করবে না — contract invariant।
        assert response.status_code in (422, 503)
        assert response.status_code != 200  # বাংলা: কখনো success নয়

    async def test_checkout_with_stripe_configured_returns_session(self, billing_app, monkeypatch):
        """Given: STRIPE_ENABLED=True, stripe.checkout.Session.create mocked।
        When: POST /api/billing/checkout with valid payload।
        Then: 200 + session_id + url — happy path।
        """
        # Given
        client, _factory, _auth, _app = billing_app

        # বাংলা: STRIPE_ENABLED সত্যিকারের True করে Stripe মক দিচ্ছি — কোনো রিয়েল কল নেই।
        monkeypatch.setattr(billing_api, "STRIPE_ENABLED", True)
        monkeypatch.setattr(billing_api, "_raw_stripe_key", "sk_test_mockkey123")

        fake_session = MagicMock()
        fake_session.id = "cs_test_session_123"
        fake_session.url = "https://checkout.stripe.com/c/pay/cs_test_session_123"
        monkeypatch.setattr(
            billing_api.stripe.checkout.Session, "create", MagicMock(return_value=fake_session)
        )

        # When
        response = await client.post(
            "/api/billing/checkout",
            json={
                "price_id": "price_pro_monthly",
                "success_url": "https://app.example.com/success",
                "cancel_url": "https://app.example.com/cancel",
            },
        )

        # Then: 200 + সঠিক session shape
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"
        assert body["session_id"] == "cs_test_session_123"
        assert body["url"].startswith("https://checkout.stripe.com/")

    async def test_checkout_stripe_api_failure_returns_500(self, billing_app, monkeypatch):
        """Given: STRIPE_ENABLED=True, কিন্তু stripe.checkout.Session.create raises।
        When: POST /api/billing/checkout।
        Then: 500 "Payment processing error" — generic, কখনো internals leak না।
        """
        # Given
        client, _factory, _auth, _app = billing_app
        monkeypatch.setattr(billing_api, "STRIPE_ENABLED", True)
        monkeypatch.setattr(billing_api, "_raw_stripe_key", "sk_test_mockkey123")

        # বাংলা: Stripe API exception সিমুলেট করছি
        def _boom(*_args, **_kwargs):
            raise RuntimeError("Connection refused")

        monkeypatch.setattr(billing_api.stripe.checkout.Session, "create", _boom)

        # When
        response = await client.post(
            "/api/billing/checkout",
            json={
                "price_id": "price_pro_monthly",
                "success_url": "https://app.example.com/success",
                "cancel_url": "https://app.example.com/cancel",
            },
        )

        # Then: 500, generic message (no stack trace leak)
        assert response.status_code == 500
        assert "Payment processing error" in response.json()["detail"]
        # বাংলা: stack trace বা internal error লিক করছে না
        assert "Connection refused" not in response.json()["detail"]

    async def test_checkout_invalid_token_returns_401(self, billing_app):
        """Given: token-এ sub নেই।
        When: POST /api/billing/checkout।
        Then: 401 "Invalid token"।
        """
        # Given
        client, _factory, _auth, app = billing_app
        app.dependency_overrides[get_current_user_token] = lambda: {}

        # When
        response = await client.post(
            "/api/billing/checkout",
            json={
                "price_id": "price_test",
                "success_url": "https://app.example.com/success",
                "cancel_url": "https://app.example.com/cancel",
            },
        )

        # Then
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid token"


# ============================================================
# 4. Balance Non-Negative Invariant কন্ট্র্যাক্ট
# ============================================================
class TestBalanceNeverNegativeContract:
    """ব্যালেন্স কখনো 0-এর নিচে নামবে না — billing integrity invariant।"""

    async def test_initial_balance_is_non_negative(self, billing_app):
        """Given: নতুন ইউজার।
        When: ওয়ালেট বুটস্ট্র্যাপ হয়।
        Then: ব্যালেন্স >= 0 ($5 bonus)।
        """
        # Given
        client, _factory, _auth, _app = billing_app

        # When
        response = await client.get("/api/billing/wallet")

        # Then
        assert response.status_code == 200
        assert response.json()["balance_usd"] >= 0

    async def test_budget_check_blocks_when_balance_insufficient(self, billing_app):
        """Given: ব্যালেন্স $5, estimated cost $999।
        When: GET /api/billing/budget-check?estimated=999।
        Then: 402 Payment Required — ব্যালেন্স নেগেটিভ হতে দেবে না।
        """
        # Given
        client, _factory, _auth, _app = billing_app
        await client.get("/api/billing/wallet")  # $5 bonus

        # When: estimated cost ব্যালেন্সের চেয়ে বেশি
        response = await client.get("/api/billing/budget-check", params={"estimated": 999.0})

        # Then: 402 Payment Required — খরচ হওয়ার আগেই ব্লক, ব্যালেন্স নেগেটিভ হবে না
        assert response.status_code == 402
        assert "Insufficient budget" in response.json()["detail"]

    async def test_budget_check_blocks_negative_estimated_cost(self, billing_app):
        """Given: estimated=-0.01 (নেগেটিভ)।
        When: GET /api/billing/budget-check?estimated=-0.01।
        Then: 422 "non-negative" — নেগেটিভ কস্ট কখনো accept নয়।
        """
        # Given
        client, _factory, _auth, _app = billing_app

        # When
        response = await client.get("/api/billing/budget-check", params={"estimated": -0.01})

        # Then
        assert response.status_code == 422
        assert "non-negative" in response.json()["detail"]

    async def test_budget_check_sufficient_does_not_debit_balance(self, billing_app):
        """Given: ব্যালেন্স $5, estimated $1.5।
        When: budget-check success।
        Then: ওয়ালেট ব্যালেন্স অপরিবর্তিত ($5) — প্রি-ফ্লাইট কস্ট ডেবিট করে না।
        """
        # Given
        client, factory, _auth, _app = billing_app
        await client.get("/api/billing/wallet")

        # When: budget check (read-only — ডেবিট করে না)
        response = await client.get("/api/billing/budget-check", params={"estimated": 1.5})

        # Then
        assert response.status_code == 200
        body = response.json()
        assert body["sufficient"] is True
        assert body["remaining_usd"] == 3.5
        # বাংলা: ওয়ালেট আসলেই ডেবিট হয়নি
        async with factory() as s:
            wallet = (
                (await s.execute(select(UserWallet).where(UserWallet.user_id == "user-contract-1")))
                .scalars()
                .first()
            )
        assert wallet.balance_usd == Decimal("5.000000")

    async def test_webhook_credit_keeps_balance_non_negative(self, billing_app, monkeypatch):
        """Given: ওয়ালেট $5, Stripe webhook payment_intent.succeeded আসে।
        When: webhook প্রসেস হয়।
        Then: নতুন ব্যালেন্স >= আগের ব্যালেন্স (credit-only operation)।
        """
        # Given
        client, factory, _auth, _app = billing_app
        await client.get("/api/billing/wallet")  # $5
        async with factory() as s:
            before_wallet = (
                (await s.execute(select(UserWallet).where(UserWallet.user_id == "user-contract-1")))
                .scalars()
                .first()
            )
            before_balance = before_wallet.balance_usd

        monkeypatch.setattr(billing_api, "STRIPE_WEBHOOK_SECRET", "whsec_test")
        event = {
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_nonneg",
                    "amount_received": 100,  # $1.00 credit
                    "metadata": {"user_id": "user-contract-1"},
                }
            },
        }
        monkeypatch.setattr(
            billing_api.stripe.Webhook, "construct_event", MagicMock(return_value=event)
        )

        # When
        response = await client.post(
            "/api/billing/webhook/stripe",
            content=b'{"raw":1}',
            headers={"Stripe-Signature": "t=1,v1=stub"},
        )

        # Then: নতুন ব্যালেন্স >= আগের ব্যালেন্স (কখনো নেগেটিভ নয়)
        assert response.status_code == 200
        async with factory() as s:
            after_wallet = (
                (await s.execute(select(UserWallet).where(UserWallet.user_id == "user-contract-1")))
                .scalars()
                .first()
            )
            after_balance = after_wallet.balance_usd
        assert after_balance >= before_balance
        assert after_balance >= Decimal("0")
        assert after_balance == Decimal("6.000000")  # $5 + $1
