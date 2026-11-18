"""Real-route coverage for api/routes/billing_api.py (critical tier).

The existing test_billing_api_integration.py only exercises the 401 paths.
This module mounts ONLY the billing router on a minimal FastAPI app with
dependency-overridden auth and a REAL in-memory sqlite session, so the actual
SQLAlchemy money paths are verified end-to-end:

- wallet bootstrap ($5 sign-up bonus, no duplicate rows)
- pre-flight budget check (200 / 402 Payment Required / 422)
- add-funds validation (non-positive, AML cap, decimal places, origin)
- checkout policy (mock session in test env, 503 in production when Stripe
  is unconfigured)
- Stripe webhook crediting with at-least-once idempotent replay
- SSLCommerz webhook crediting (BDT→USD conversion + idempotent replay)
- transaction history serialization

Loop-safety note: every request goes through httpx.ASGITransport inside the
test's own event loop, so the dependency-overridden sqlite sessions are
created and verified on the SAME loop (TestClient's portal loop would bind
aiosqlite connections to a foreign loop).

Ramp step 2 (hardening-2 round 2): api/routes/billing_api.py previously
measured 18% in the CI-combined coverage because only the 401 tests ran.
"""

from decimal import Decimal
from unittest.mock import MagicMock

import httpx
import pytest
import pytest_asyncio

# বাংলা মন্তব্য: #2585 — SQLAlchemy asyncio ইঞ্জিনের (sqlite+aiosqlite) জন্য greenlet
# আবশ্যক; CI poetry venv-এ অনুপস্থিত থাকলে রিপোর canonical প্যাটার্ন অনুযায়ী টেস্ট
# স্কিপ হবে (তুলনা: test_mcp_hub.py:38, test_missions_boundaries.py:44) —
# setup-এ ImportError-এর বদলে স্পষ্ট ও সৎ skip।
pytest.importorskip(
    "greenlet", reason="greenlet not installed — required for SQLAlchemy asyncio engine"
)
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import api.routes.billing_api as billing_api
from api.dependencies import get_current_user_token
from api.routes.billing_api import router as billing_router
from database.session import get_db_session
from models.base import Base
from models.wallet import TransactionLedgerEntry, UserWallet


@pytest_asyncio.fixture
async def billing_app():
    """Minimal app + real sqlite session + overridable auth payload."""
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

    auth_payload = {"sub": "user-1"}
    app = FastAPI()
    app.include_router(billing_router)
    app.dependency_overrides[get_db_session] = _override_session
    app.dependency_overrides[get_current_user_token] = lambda: auth_payload
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, factory, auth_payload
    await engine.dispose()


# ---------------------------------------------------------------------------
# Wallet bootstrap
# ---------------------------------------------------------------------------
async def test_wallet_bootstrap_creates_five_dollar_bonus(billing_app):
    client, _factory, _auth = billing_app
    first = await client.get("/api/billing/wallet")
    assert first.status_code == 200
    assert first.json()["balance_usd"] == 5.0
    assert first.json()["user_id"] == "user-1"

    # Idempotent bootstrap: a second call must NOT create a duplicate wallet.
    second = await client.get("/api/billing/wallet")
    assert second.status_code == 200
    assert second.json()["balance_usd"] == 5.0


async def test_wallet_bootstrap_single_row(billing_app):
    client, factory, _auth = billing_app
    await client.get("/api/billing/wallet")
    await client.get("/api/billing/wallet")
    async with factory() as s:
        rows = (await s.execute(select(UserWallet))).scalars().all()
    assert len(rows) == 1
    assert rows[0].balance_usd == Decimal("5.000000")


# ---------------------------------------------------------------------------
# Token branch (sub missing → 401 "Invalid token")
# ---------------------------------------------------------------------------
async def test_wallet_invalid_token_returns_401(billing_app):
    client, _factory, _auth = billing_app
    # Rebind the override to a token payload without a subject.
    client._transport.app.dependency_overrides[get_current_user_token] = lambda: {}
    response = await client.get("/api/billing/wallet")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"


async def test_history_invalid_token_returns_401(billing_app):
    client, _factory, _auth = billing_app
    client._transport.app.dependency_overrides[get_current_user_token] = lambda: {}
    response = await client.get("/api/billing/history")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"


# ---------------------------------------------------------------------------
# Pre-flight budget check
# ---------------------------------------------------------------------------
async def test_budget_check_sufficient(billing_app):
    client, _factory, _auth = billing_app
    response = await client.get("/api/billing/budget-check", params={"estimated": 1.5})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["sufficient"] is True
    assert body["balance_usd"] == 5.0
    assert body["remaining_usd"] == 3.5


async def test_budget_check_insufficient_returns_402(billing_app):
    client, _factory, _auth = billing_app
    response = await client.get("/api/billing/budget-check", params={"estimated": 999.0})
    assert response.status_code == 402
    assert "Insufficient budget" in response.json()["detail"]


async def test_budget_check_negative_estimated_returns_422(billing_app):
    client, _factory, _auth = billing_app
    response = await client.get("/api/billing/budget-check", params={"estimated": -0.01})
    assert response.status_code == 422
    assert "non-negative" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Transaction history
# ---------------------------------------------------------------------------
async def test_history_serializes_ledger_entries(billing_app):
    client, factory, _auth = billing_app
    response = await client.get("/api/billing/history")
    assert response.status_code == 200
    assert response.json() == []

    async with factory() as s:
        s.add(
            TransactionLedgerEntry(
                transaction_id="tx-1",
                user_id="user-1",
                amount_usd=Decimal("2.500000"),
                transaction_type="topup",
                description="test deposit",
            )
        )
        await s.commit()

    body = (await client.get("/api/billing/history")).json()
    assert len(body) == 1
    assert body[0]["transaction_id"] == "tx-1"
    assert body[0]["amount_usd"] == 2.5
    assert body[0]["transaction_type"] == "topup"


# ---------------------------------------------------------------------------
# Add funds / top-up checkout
# ---------------------------------------------------------------------------
async def test_add_funds_rejects_non_positive_amount(billing_app):
    client, _factory, _auth = billing_app
    for bad in (0.0, -5.0):
        response = await client.post(
            "/api/billing/add-funds",
            params={"amount": bad},
            headers={"Origin": "https://app.example.com"},
        )
        assert response.status_code == 400
        assert "greater than zero" in response.json()["detail"]


async def test_add_funds_rejects_over_limit_amount(billing_app):
    client, _factory, _auth = billing_app
    response = await client.post(
        "/api/billing/add-funds",
        params={"amount": 20000.0},
        headers={"Origin": "https://app.example.com"},
    )
    assert response.status_code == 400
    assert "maximum limit" in response.json()["detail"]


async def test_add_funds_rejects_extra_decimal_places(billing_app):
    client, _factory, _auth = billing_app
    response = await client.post(
        "/api/billing/add-funds",
        params={"amount": 10.999},
        headers={"Origin": "https://app.example.com"},
    )
    assert response.status_code == 400
    assert "2 decimal places" in response.json()["detail"]


async def test_add_funds_happy_path_uses_origin_header(billing_app):
    client, _factory, _auth = billing_app
    response = await client.post(
        "/api/billing/add-funds",
        params={"amount": 25.5},
        headers={"Origin": "https://app.example.com"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert body["checkout_url"].startswith("https://app.example.com/pay/")
    assert "amount=25.5" in body["checkout_url"]
    assert body["checkout_id"]


async def test_add_funds_invalid_token_returns_401(billing_app):
    client, _factory, _auth = billing_app
    client._transport.app.dependency_overrides[get_current_user_token] = lambda: {}
    response = await client.post(
        "/api/billing/add-funds",
        params={"amount": 25.5},
        headers={"Origin": "https://app.example.com"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Subscription plans + checkout policy
# ---------------------------------------------------------------------------
async def test_plans_route_returns_plan_catalog(billing_app):
    client, _factory, _auth = billing_app
    response = await client.get("/api/billing/plans")
    assert response.status_code == 200
    plans = response.json()["plans"]
    assert "free" in plans
    assert plans["free"]["name"]


# ERR-G01 FIX (2026-09-15): the fabricated "mock checkout session" path was
# removed — a paid-looking success state must never be manufactured in any
# environment. Without Stripe, checkout now returns 503 in ALL environments.
async def test_checkout_without_stripe_returns_503_in_all_environments(billing_app):
    client, _factory, _auth = billing_app
    response = await client.post(
        "/api/billing/checkout",
        json={
            "price_id": "price_test",
            "success_url": "https://app.example.com/success",
            "cancel_url": "https://app.example.com/cancel",
        },
    )
    assert response.status_code == 503
    assert "Stripe is not configured" in response.json()["detail"]


async def test_checkout_production_without_stripe_returns_503(billing_app, monkeypatch):
    client, _factory, _auth = billing_app
    from core.config import settings

    monkeypatch.setattr(settings, "env", "production")
    response = await client.post(
        "/api/billing/checkout",
        json={
            "price_id": "price_test",
            "success_url": "https://app.example.com/success",
            "cancel_url": "https://app.example.com/cancel",
        },
    )
    assert response.status_code == 503
    assert "Stripe is not configured" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Stripe webhook: money path + idempotent replay
# ---------------------------------------------------------------------------
def _stripe_payment_intent_event(intent_id: str, amount_cents: int) -> dict:
    return {
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": intent_id,
                "amount_received": amount_cents,
                "metadata": {"user_id": "user-1"},
            }
        },
    }


async def test_stripe_webhook_missing_secret_test_mode_returns_ignored(billing_app):
    client, _factory, _auth = billing_app
    response = await client.post("/api/billing/webhook/stripe", content=b"{}")
    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}


async def test_stripe_webhook_credits_wallet_exactly_once(billing_app, monkeypatch):
    client, factory, _auth = billing_app
    event = _stripe_payment_intent_event("pi_test_1", 2500)
    monkeypatch.setattr(billing_api, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(
        billing_api.stripe.Webhook, "construct_event", MagicMock(return_value=event)
    )

    # Wallet must pre-exist (production flow: wallet created at sign-up).
    await client.get("/api/billing/wallet")

    headers = {"Stripe-Signature": "t=1,v1=stub"}
    first = await client.post(
        "/api/billing/webhook/stripe", content=b'{"payload":"raw"}', headers=headers
    )
    assert first.status_code == 200
    assert first.json() == {"status": "success"}

    # At-least-once delivery: the replay must NOT double-credit.
    replay = await client.post(
        "/api/billing/webhook/stripe", content=b'{"payload":"raw"}', headers=headers
    )
    assert replay.status_code == 200
    assert replay.json()["status"] == "processed"
    assert "already credited" in replay.json()["message"]

    async with factory() as s:
        wallet = (
            (await s.execute(select(UserWallet).where(UserWallet.user_id == "user-1")))
            .scalars()
            .first()
        )
        entries = (await s.execute(select(TransactionLedgerEntry))).scalars().all()
    assert wallet.balance_usd == Decimal("30.000000")
    assert len(entries) == 1
    assert entries[0].transaction_id == "pi_test_1"
    assert entries[0].transaction_type == "stripe_topup"


async def test_stripe_webhook_missing_metadata_is_ignored(billing_app, monkeypatch):
    client, factory, _auth = billing_app
    event = {
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": "pi_nometa", "amount_received": 100, "metadata": {}}},
    }
    monkeypatch.setattr(billing_api, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(
        billing_api.stripe.Webhook, "construct_event", MagicMock(return_value=event)
    )
    await client.get("/api/billing/wallet")
    response = await client.post(
        "/api/billing/webhook/stripe",
        content=b'{"payload":"raw"}',
        headers={"Stripe-Signature": "t=1,v1=stub"},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ignored", "reason": "missing metadata"}


# ---------------------------------------------------------------------------
# SSLCommerz webhook: BDT→USD money path + idempotent replay
# ---------------------------------------------------------------------------
def _patch_sslcommerz_verified(monkeypatch, payload: dict | None) -> None:
    async def _fake_verify(val_id: str):
        return payload

    monkeypatch.setattr(billing_api, "_verify_sslcommerz_transaction", _fake_verify)


async def test_sslcommerz_webhook_missing_val_id_returns_400(billing_app):
    client, _factory, _auth = billing_app
    response = await client.post("/api/billing/webhook/sslcommerz", json={})
    assert response.status_code == 400
    assert "Missing val_id" in response.json()["detail"]


async def test_sslcommerz_webhook_unverifiable_transaction_returns_400(billing_app, monkeypatch):
    client, _factory, _auth = billing_app
    _patch_sslcommerz_verified(monkeypatch, None)
    response = await client.post("/api/billing/webhook/sslcommerz", json={"val_id": "v-1"})
    assert response.status_code == 400
    assert "could not be verified" in response.json()["detail"]


async def test_sslcommerz_webhook_missing_user_reference_returns_400(billing_app, monkeypatch):
    client, _factory, _auth = billing_app
    _patch_sslcommerz_verified(monkeypatch, {"status": "VALID", "amount": "1000"})
    response = await client.post("/api/billing/webhook/sslcommerz", json={"val_id": "v-1"})
    assert response.status_code == 400
    assert "Missing user reference" in response.json()["detail"]


async def test_sslcommerz_webhook_credits_wallet_exactly_once(billing_app, monkeypatch):
    client, factory, _auth = billing_app
    _patch_sslcommerz_verified(
        monkeypatch,
        {"status": "VALID", "value_a": "user-1", "amount": "1000", "val_id": "v-1"},
    )

    await client.get("/api/billing/wallet")  # bootstrap $5 wallet

    first = await client.post("/api/billing/webhook/sslcommerz", json={"val_id": "v-1"})
    assert first.status_code == 200
    assert first.json()["status"] == "processed"

    replay = await client.post("/api/billing/webhook/sslcommerz", json={"val_id": "v-1"})
    assert replay.status_code == 200
    assert replay.json()["status"] == "processed"
    assert "already credited" in replay.json()["message"]

    # 1000 BDT × default 0.0085 rate = $8.50 → 5 + 8.50 = 13.50
    async with factory() as s:
        wallet = (
            (await s.execute(select(UserWallet).where(UserWallet.user_id == "user-1")))
            .scalars()
            .first()
        )
        entries = (await s.execute(select(TransactionLedgerEntry))).scalars().all()
    assert wallet.balance_usd == Decimal("13.500000")
    assert len(entries) == 1
    assert entries[0].transaction_id == "v-1"


# ---------------------------------------------------------------------------
# Cost analytics (CostDashboard feed)
# ---------------------------------------------------------------------------
async def test_analytics_returns_cost_guard_aggregate(billing_app, monkeypatch):
    client, _factory, _auth = billing_app

    async def _fake_aggregate():
        return 12.5, {"gemini": 12.5}

    monkeypatch.setattr("api.routes.realtime_dashboard.aggregate_cost_guard_spend", _fake_aggregate)
    response = await client.get("/api/billing/analytics")
    assert response.status_code == 200
    body = response.json()
    assert body["total_spent"] == 12.5
    assert body["provider_breakdown"] == {"gemini": 12.5}
    assert body["total_saved"] == 0.0
    assert body["cached_queries"] == 0
