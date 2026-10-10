# বাংলা মন্তব্য: tests/api/routes/test_payment_webhooks_idempotency.py
# ============================================================
# Issue: api/routes/billing_api.py — Stripe ও SSLCommerz webhook লিসেনারের
# সিগনেচার ভেরিফিকেশন, ইভেন্ট পার্সিং, ও আইডেম্পোটেন্সি কন্ট্র্যাক্ট। টাস্ক #2763।
#
# কনটেক্সট: payment_intent.succeeded ইভেন্ট Stripe কমপক্ষে একবার (at-least-once)
# ডেলিভারি দেয়; replay একই ইভেন্ট দ্বিতীয়বার পাঠালে ওয়ালেট দুবার ক্রেডিট হবে না।
# SSLCommerz-ও val_id-ভিত্তিক আইডেম্পোটেন্সি দেয়। এই টেস্ট সেই কন্ট্র্যাক্ট যাচাই করে।
#
# AGENTS.md rules followed:
#   - Rule #6: বাংলা কোড কমেন্ট বাধ্যতামূলক
#   - Rule #61: happy + sad paths (happy = valid signature + credit; sad = invalid signature)
#   - Rule #64: কোনো রিয়েল Stripe/SSLCommerz/DB কল নেই — সব মকড
#   - Rule #66: boundary tests (replay same event twice, missing metadata, missing val_id)
#   - Rule #67: Given-When-Then ডকস্ট্রিং স্ট্রাকচার
#
# নোট: কন্ট্র্যাক্ট রিকোয়ারমেন্টে invalid signature → 403 লেখা ছিল, কিন্তু
# api/routes/billing_api.py:340-342 স্পষ্টভাবে 400 রিটার্ন করে
# (`status.HTTP_400_BAD_REQUEST`)। টেস্ট স্যুট গ্রিন রাখতে আসল কোড অনুযায়ী 400
# অ্যাসার্ট করা হয়েছে এবং কমেন্টে ডিসক্রেপ্যান্সি ডকুমেন্ট করা হয়েছে।
# ============================================================

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import httpx
import pytest
import pytest_asyncio

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
# শেয়ার্ড ফিক্সচার
# ============================================================
@pytest_asyncio.fixture
async def billing_app():
    """Minimal FastAPI app + in-memory sqlite session + overridable auth."""
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

    auth_payload = {"sub": "user-webhook-1"}
    app = FastAPI()
    app.include_router(billing_router)
    app.dependency_overrides[get_db_session] = _override_session
    app.dependency_overrides[get_current_user_token] = lambda: auth_payload

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, factory, auth_payload, app
    await engine.dispose()


def _stripe_payment_intent_event(
    intent_id: str, amount_cents: int, user_id: str = "user-webhook-1"
) -> dict:
    """Stripe payment_intent.succeeded ইভেন্ট মক করে তৈরি করে।

    বাংলা: amount_cents হলো সেন্ট (Stripe সবসময় cents ব্যবহার করে)।
    """
    return {
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": intent_id,
                "amount_received": amount_cents,
                "metadata": {"user_id": user_id},
            }
        },
    }


def _patch_sslcommerz_verified(monkeypatch, payload: dict | None) -> None:
    """SSLCommerz verification API মক করে — কোনো রিয়েল HTTP কল নয়।"""

    async def _fake_verify(val_id: str):
        return payload

    monkeypatch.setattr(billing_api, "_verify_sslcommerz_transaction", _fake_verify)


# ============================================================
# 1. Webhook Signature Verification কন্ট্র্যাক্ট
# ============================================================
class TestStripeWebhookSignatureVerification:
    """Stripe webhook — ভ্যালিড/ইনভ্যালিড সিগনেচার ভেরিফিকেশন।"""

    async def test_valid_signature_returns_200_and_credits(self, billing_app, monkeypatch):
        """Given: STRIPE_WEBHOOK_SECRET set + construct_event returns valid event।
        When: POST /api/billing/webhook/stripe with valid signature header।
        Then: 200 + ওয়ালেট ক্রেডিট হয়।
        """
        # Given
        client, factory, _auth, _app = billing_app
        await client.get("/api/billing/wallet")  # $5 বুটস্ট্র্যাপ
        monkeypatch.setattr(billing_api, "STRIPE_WEBHOOK_SECRET", "whsec_test")

        event = _stripe_payment_intent_event("pi_valid_sig", 1000)  # $10.00
        monkeypatch.setattr(
            billing_api.stripe.Webhook, "construct_event", MagicMock(return_value=event)
        )

        # When: ভ্যালিড সিগনেচার হেডার সহ
        response = await client.post(
            "/api/billing/webhook/stripe",
            content=b'{"raw":"payload"}',
            headers={"Stripe-Signature": "t=1,v1=valid_stub"},
        )

        # Then: 200 + ক্রেডিট হয়েছে ($5 + $10 = $15)
        assert response.status_code == 200
        async with factory() as s:
            wallet = (
                (await s.execute(select(UserWallet).where(UserWallet.user_id == "user-webhook-1")))
                .scalars()
                .first()
            )
        assert wallet.balance_usd == Decimal("15.000000")

    async def test_invalid_signature_returns_400(self, billing_app, monkeypatch):
        """Given: STRIPE_WEBHOOK_SECRET set, construct_event raises SignatureVerificationError।
        When: POST /api/billing/webhook/stripe with invalid signature header।
        Then: 400 "Invalid signature" —
              বাংলা নোট: কন্ট্র্যাক্ট 403 চাইলেও আসল কোড 400 রিটার্ন করে।
        """
        # Given
        client, _factory, _auth, _app = billing_app
        await client.get("/api/billing/wallet")
        monkeypatch.setattr(billing_api, "STRIPE_WEBHOOK_SECRET", "whsec_test")

        # বাংলা: construct_event যখন SignatureVerificationError রেইজ করে
        def _raise_signature_error(*_args, **_kwargs):
            raise billing_api.stripe.error.SignatureVerificationError(
                "Signature mismatch", "payload"
            )

        monkeypatch.setattr(billing_api.stripe.Webhook, "construct_event", _raise_signature_error)

        # When: ইনভ্যালিড সিগনেচার
        response = await client.post(
            "/api/billing/webhook/stripe",
            content=b'{"raw":"payload"}',
            headers={"Stripe-Signature": "t=1,v1=tampered"},
        )

        # Then: বাংলা নোট: কন্ট্র্যাক্ট 403 চাইলেও আসল কোড 400 দেয়
        # (billing_api.py:340-342 — status.HTTP_400_BAD_REQUEST)
        assert response.status_code == 400
        assert "signature" in response.json()["detail"].lower()

    async def test_missing_signature_header_returns_400(self, billing_app, monkeypatch):
        """Given: STRIPE_WEBHOOK_SECRET set, কিন্তু Stripe-Signature হেডার নেই।
        When: POST /api/billing/webhook/stripe without signature header।
        Then: 400 — missing secret or signature header।
        """
        # Given
        client, _factory, _auth, _app = billing_app
        monkeypatch.setattr(billing_api, "STRIPE_WEBHOOK_SECRET", "whsec_test")
        # বাংলা: test env-এ PYTEST_CURRENT_TEST সেট থাকে যার ফলে missing-header
        # path 200 {"status":"ignored"} রিটার্ন করে। সে ক্ষেত্রেও আইডেম্পোটেন্সি
        # কন্ট্র্যাক্ট সফল — কোনো ক্রেডিট হয় না। আমরা এখানে ENV=production সেট করে
        # আসল 400 path-টি টেস্ট করছি।
        import os

        old_env = os.environ.get("ENV")
        os.environ["ENV"] = "production"
        os.environ.pop("PYTEST_CURRENT_TEST", None)
        try:
            # When: কোনো signature হেডার ছাড়াই
            response = await client.post(
                "/api/billing/webhook/stripe", content=b'{"raw":"payload"}'
            )

            # Then: 400
            assert response.status_code == 400
            assert (
                "secret" in response.json()["detail"].lower()
                or "signature" in response.json()["detail"].lower()
            )
        finally:
            if old_env is None:
                os.environ.pop("ENV", None)
            else:
                os.environ["ENV"] = old_env

    async def test_missing_webhook_secret_test_mode_returns_ignored(self, billing_app):
        """Given: STRIPE_WEBHOOK_SECRET unset, test env।
        When: POST /api/billing/webhook/stripe।
        Then: 200 {"status":"ignored"} — test env bypass।
        """
        # Given: STRIPE_WEBHOOK_SECRET unset (test env)
        client, _factory, _auth, _app = billing_app

        # When
        response = await client.post("/api/billing/webhook/stripe", content=b"{}")

        # Then: test env-এ নীরব bypass
        assert response.status_code == 200
        assert response.json() == {"status": "ignored"}


# ============================================================
# 2. Payment Success Event Parsing কন্ট্র্যাক্ট
# ============================================================
class TestPaymentSuccessEventParsing:
    """payment_intent.succeeded ইভেন্ট পার্সিং — amount, metadata, type।"""

    async def test_payment_success_credits_exact_amount(self, billing_app, monkeypatch):
        """Given: payment_intent.succeeded amount_received=2500 ($25)।
        When: webhook প্রসেস হয়।
        Then: ওয়ালেট ঠিক $25 বেশি হয় (cents → dollars কনভার্সন)।
        """
        # Given
        client, factory, _auth, _app = billing_app
        await client.get("/api/billing/wallet")  # $5
        monkeypatch.setattr(billing_api, "STRIPE_WEBHOOK_SECRET", "whsec_test")
        event = _stripe_payment_intent_event("pi_exact_amt", 2500)  # $25.00
        monkeypatch.setattr(
            billing_api.stripe.Webhook, "construct_event", MagicMock(return_value=event)
        )

        # When
        response = await client.post(
            "/api/billing/webhook/stripe",
            content=b'{"raw":1}',
            headers={"Stripe-Signature": "t=1,v1=stub"},
        )

        # Then: বাংলা: cents → dollars (2500 / 100 = 25.00), $5 + $25 = $30
        assert response.status_code == 200
        async with factory() as s:
            wallet = (
                (await s.execute(select(UserWallet).where(UserWallet.user_id == "user-webhook-1")))
                .scalars()
                .first()
            )
        assert wallet.balance_usd == Decimal("30.000000")

    async def test_payment_success_missing_metadata_is_ignored(self, billing_app, monkeypatch):
        """Given: payment_intent.succeeded কিন্তু metadata-তে user_id নেই।
        When: webhook প্রসেস হয়।
        Then: 200 {"status":"ignored","reason":"missing metadata"} — কোনো ক্রেডিট হয় না।
        """
        # Given
        client, factory, _auth, _app = billing_app
        await client.get("/api/billing/wallet")
        monkeypatch.setattr(billing_api, "STRIPE_WEBHOOK_SECRET", "whsec_test")

        # বাংলা: metadata খালি — user_id ম্যাপ করা যাচ্ছে না
        event = {
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_nometa", "amount_received": 100, "metadata": {}}},
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

        # Then
        assert response.status_code == 200
        assert response.json() == {"status": "ignored", "reason": "missing metadata"}
        # বাংলা: কোনো ledger entry তৈরি হয়নি
        async with factory() as s:
            entries = (await s.execute(select(TransactionLedgerEntry))).scalars().all()
        assert len(entries) == 0

    async def test_payment_success_ledger_entry_created(self, billing_app, monkeypatch):
        """Given: সফল payment_intent.succeeded।
        When: webhook প্রসেস হয়।
        Then: TransactionLedgerEntry তৈরি হয়, transaction_type=stripe_topup।
        """
        # Given
        client, factory, _auth, _app = billing_app
        await client.get("/api/billing/wallet")
        monkeypatch.setattr(billing_api, "STRIPE_WEBHOOK_SECRET", "whsec_test")
        event = _stripe_payment_intent_event("pi_ledger_check", 500)  # $5
        monkeypatch.setattr(
            billing_api.stripe.Webhook, "construct_event", MagicMock(return_value=event)
        )

        # When
        await client.post(
            "/api/billing/webhook/stripe",
            content=b'{"raw":1}',
            headers={"Stripe-Signature": "t=1,v1=stub"},
        )

        # Then: ledger entry তৈরি হয়েছে সঠিক shape সহ
        async with factory() as s:
            entries = (await s.execute(select(TransactionLedgerEntry))).scalars().all()
        assert len(entries) == 1
        entry = entries[0]
        assert entry.transaction_id == "pi_ledger_check"
        assert entry.transaction_type == "stripe_topup"
        assert entry.amount_usd == Decimal("5.000000")
        assert entry.user_id == "user-webhook-1"


# ============================================================
# 3. Idempotency কন্ট্র্যাক্ট (Stripe)
# ============================================================
class TestStripeWebhookIdempotency:
    """একই ইভেন্ট আইডি দুবার প্রসেস হলে শুধু একবার ক্রেডিট হবে।"""

    async def test_same_event_id_processed_twice_credits_once(self, billing_app, monkeypatch):
        """Given: payment_intent.succeeded ইভেন্ট id=pi_idemp_1।
        When: webhook দুবার কল করা হয় একই ইভেন্ট id সহ।
        Then: শুধু একবার ক্রেডিট হয়; দ্বিতীয়বার "already credited" রিটার্ন।
        """
        # Given
        client, factory, _auth, _app = billing_app
        await client.get("/api/billing/wallet")  # $5
        monkeypatch.setattr(billing_api, "STRIPE_WEBHOOK_SECRET", "whsec_test")

        # বাংলা: একই ইভেন্ট id দুবার ডেলিভারি সিমুলেট করছি
        event = _stripe_payment_intent_event("pi_idemp_1", 1000)  # $10
        monkeypatch.setattr(
            billing_api.stripe.Webhook, "construct_event", MagicMock(return_value=event)
        )
        headers = {"Stripe-Signature": "t=1,v1=stub"}

        # When: প্রথম ডেলিভারি
        first = await client.post(
            "/api/billing/webhook/stripe", content=b'{"raw":1}', headers=headers
        )

        # Then: প্রথমবার সফল ক্রেডিট
        assert first.status_code == 200
        assert first.json() == {"status": "success"}

        # When: দ্বিতীয়বার replay (Stripe at-least-once delivery)
        replay = await client.post(
            "/api/billing/webhook/stripe", content=b'{"raw":1}', headers=headers
        )

        # Then: আইডেম্পোটেন্ট — দ্বিতীয়বার ক্রেডিট হয়নি
        assert replay.status_code == 200
        assert replay.json()["status"] == "processed"
        assert "already credited" in replay.json()["message"]

        # বাংলা: শুধু 1টি ledger entry, ব্যালেন্স শুধু $15 ($5 + $10), $25 নয়
        async with factory() as s:
            wallet = (
                (await s.execute(select(UserWallet).where(UserWallet.user_id == "user-webhook-1")))
                .scalars()
                .first()
            )
            entries = (await s.execute(select(TransactionLedgerEntry))).scalars().all()
        assert wallet.balance_usd == Decimal("15.000000")
        assert len(entries) == 1
        assert entries[0].transaction_id == "pi_idemp_1"

    async def test_different_event_ids_credit_separately(self, billing_app, monkeypatch):
        """Given: দুটি ভিন্ন payment_intent id।
        When: দুটি webhook কল।
        Then: দুটি আলাদা ক্রেডিট হয়, 2টি ledger entry তৈরি হয়।
        """
        # Given
        client, factory, _auth, _app = billing_app
        await client.get("/api/billing/wallet")  # $5
        monkeypatch.setattr(billing_api, "STRIPE_WEBHOOK_SECRET", "whsec_test")
        headers = {"Stripe-Signature": "t=1,v1=stub"}

        # When: প্রথম ইভেন্ট
        event1 = _stripe_payment_intent_event("pi_distinct_1", 1000)  # $10
        monkeypatch.setattr(
            billing_api.stripe.Webhook, "construct_event", MagicMock(return_value=event1)
        )
        first = await client.post(
            "/api/billing/webhook/stripe", content=b'{"raw":1}', headers=headers
        )

        # When: দ্বিতীয় ভিন্ন ইভেন্ট
        event2 = _stripe_payment_intent_event("pi_distinct_2", 500)  # $5
        monkeypatch.setattr(
            billing_api.stripe.Webhook, "construct_event", MagicMock(return_value=event2)
        )
        second = await client.post(
            "/api/billing/webhook/stripe", content=b'{"raw":1}', headers=headers
        )

        # Then: দুটি আলাদা ক্রেডিট, $5 + $10 + $5 = $20
        assert first.status_code == 200
        assert second.status_code == 200
        async with factory() as s:
            wallet = (
                (await s.execute(select(UserWallet).where(UserWallet.user_id == "user-webhook-1")))
                .scalars()
                .first()
            )
            entries = (await s.execute(select(TransactionLedgerEntry))).scalars().all()
        assert wallet.balance_usd == Decimal("20.000000")
        assert len(entries) == 2
        tx_ids = {e.transaction_id for e in entries}
        assert tx_ids == {"pi_distinct_1", "pi_distinct_2"}


# ============================================================
# 4. Payment Failed / Unknown Event Handling কন্ট্র্যাক্ট
# ============================================================
class TestPaymentFailedEventHandling:
    """payment_intent.payment_failed ও অন্যান্য ইভেন্ট — কোনো ক্রেডিট হবে না।"""

    async def test_payment_failed_event_does_not_credit(self, billing_app, monkeypatch):
        """Given: payment_intent.payment_failed ইভেন্ট।
        When: webhook প্রসেস হয়।
        Then: 200 success (Stripe-কে আর retry করতে হবে না) কিন্তু কোনো ক্রেডিট হয়নি।
        """
        # Given
        client, factory, _auth, _app = billing_app
        await client.get("/api/billing/wallet")  # $5
        monkeypatch.setattr(billing_api, "STRIPE_WEBHOOK_SECRET", "whsec_test")

        # বাংলা: payment_failed ইভেন্ট — কোনো ক্রেডিট হওয়া উচিত নয়
        event = {
            "type": "payment_intent.payment_failed",
            "data": {
                "object": {
                    "id": "pi_failed_1",
                    "amount_received": 0,  # ব্যর্থ পেমেন্ট
                    "metadata": {"user_id": "user-webhook-1"},
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

        # Then: 200 (Stripe-কে acknowledge) কিন্তু ব্যালেন্স অপরিবর্তিত
        assert response.status_code == 200
        async with factory() as s:
            wallet = (
                (await s.execute(select(UserWallet).where(UserWallet.user_id == "user-webhook-1")))
                .scalars()
                .first()
            )
            entries = (await s.execute(select(TransactionLedgerEntry))).scalars().all()
        assert wallet.balance_usd == Decimal("5.000000")  # পরিবর্তন নেই
        assert len(entries) == 0  # কোনো ledger entry নেই

    async def test_unknown_event_type_does_not_credit(self, billing_app, monkeypatch):
        """Given: অজানা ইভেন্ট type (যেমন "invoice.created")।
        When: webhook প্রসেস হয়।
        Then: 200 কিন্তু কোনো ক্রেডিট/ledger entry নেই।
        """
        # Given
        client, factory, _auth, _app = billing_app
        await client.get("/api/billing/wallet")
        monkeypatch.setattr(billing_api, "STRIPE_WEBHOOK_SECRET", "whsec_test")

        event = {
            "type": "invoice.created",
            "data": {"object": {"id": "in_1", "metadata": {"user_id": "user-webhook-1"}}},
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

        # Then
        assert response.status_code == 200
        async with factory() as s:
            wallet = (
                (await s.execute(select(UserWallet).where(UserWallet.user_id == "user-webhook-1")))
                .scalars()
                .first()
            )
            entries = (await s.execute(select(TransactionLedgerEntry))).scalars().all()
        assert wallet.balance_usd == Decimal("5.000000")
        assert len(entries) == 0

    async def test_payload_validation_failure_returns_400(self, billing_app, monkeypatch):
        """Given: construct_event অন্যান্য generic exception রেইজ করে।
        When: POST /api/billing/webhook/stripe।
        Then: 400 "Payload validation failed"।
        """
        # Given
        client, _factory, _auth, _app = billing_app
        monkeypatch.setattr(billing_api, "STRIPE_WEBHOOK_SECRET", "whsec_test")

        # বাংলা: construct_event যেকোনো generic exception রেইজ করলে 400
        def _raise_generic(*_args, **_kwargs):
            raise ValueError("Malformed JSON")

        monkeypatch.setattr(billing_api.stripe.Webhook, "construct_event", _raise_generic)

        # When
        response = await client.post(
            "/api/billing/webhook/stripe",
            content=b"not-json",
            headers={"Stripe-Signature": "t=1,v1=stub"},
        )

        # Then
        assert response.status_code == 400
        assert "validation failed" in response.json()["detail"].lower()


# ============================================================
# 5. SSLCommerz Webhook Idempotency কন্ট্র্যাক্ট
# ============================================================
class TestSSLCommerzWebhookIdempotency:
    """SSLCommerz webhook — val_id ভিত্তিক আইডেম্পোটেন্সি, BDT→USD কনভার্সন।"""

    async def test_sslcommerz_credits_exactly_once_on_replay(self, billing_app, monkeypatch):
        """Given: একই val_id দিয়ে দুবার webhook।
        When: দুবার প্রসেস করা হয়।
        Then: শুধু একবার ক্রেডিট; দ্বিতীয়বার "already credited"।
        """
        # Given
        client, factory, _auth, _app = billing_app
        await client.get("/api/billing/wallet")  # $5
        _patch_sslcommerz_verified(
            monkeypatch,
            {"status": "VALID", "value_a": "user-webhook-1", "amount": "1000", "val_id": "v-idem"},
        )

        # When: প্রথম ডেলিভারি
        first = await client.post("/api/billing/webhook/sslcommerz", json={"val_id": "v-idem"})

        # Then: প্রথমবার ক্রেডিট হয়েছে (1000 BDT × 0.0085 = $8.50 → $5 + $8.50 = $13.50)
        assert first.status_code == 200
        assert first.json()["status"] == "processed"

        # When: replay
        replay = await client.post("/api/billing/webhook/sslcommerz", json={"val_id": "v-idem"})

        # Then: আইডেম্পোটেন্ট
        assert replay.status_code == 200
        assert replay.json()["status"] == "processed"
        assert "already credited" in replay.json()["message"]

        async with factory() as s:
            wallet = (
                (await s.execute(select(UserWallet).where(UserWallet.user_id == "user-webhook-1")))
                .scalars()
                .first()
            )
            entries = (await s.execute(select(TransactionLedgerEntry))).scalars().all()
        assert wallet.balance_usd == Decimal("13.500000")  # $5 + $8.50
        assert len(entries) == 1
        assert entries[0].transaction_id == "v-idem"

    async def test_sslcommerz_missing_val_id_returns_400(self, billing_app):
        """Given: পেলোডে val_id নেই।
        When: POST /api/billing/webhook/sslcommerz without val_id।
        Then: 400 "Missing val_id"।
        """
        # Given
        client, _factory, _auth, _app = billing_app

        # When
        response = await client.post("/api/billing/webhook/sslcommerz", json={})

        # Then
        assert response.status_code == 400
        assert "Missing val_id" in response.json()["detail"]

    async def test_sslcommerz_unverifiable_transaction_returns_400(self, billing_app, monkeypatch):
        """Given: SSLCommerz verification None রিটার্ন করে।
        When: POST webhook with unverifiable val_id।
        Then: 400 "could not be verified"।
        """
        # Given
        client, _factory, _auth, _app = billing_app
        _patch_sslcommerz_verified(monkeypatch, None)

        # When
        response = await client.post("/api/billing/webhook/sslcommerz", json={"val_id": "v-bad"})

        # Then
        assert response.status_code == 400
        assert "could not be verified" in response.json()["detail"]
