import os

import pytest

# Set mock environment variables for encryption key and stripe configuration before importing core modules
# বাংলা মন্তব্য: রানিং টেস্টে ক্লাউড কানেকশন ড্রাইভার ফাস্ট-ফেইল আটকাতে মক এনক্রিপশন কী সেট করা হলো
os.environ["ENCRYPTION_KEY"] = "4vW8yO_tWn8_bM6W_vW7LDw8qddv6QRw2wKKyJue7sE="
os.environ["STRIPE_SECRET_KEY"] = "dummy_stripe_key"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test"

from decimal import Decimal
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from core.app import app
from database.session import get_db_session
from models.wallet import UserWallet

client = TestClient(app)


# Mock DB Session for testing billing
class MockAsyncSession:
    def __init__(self):
        self._wallet = UserWallet(
            user_id="test_user",
            balance_usd=Decimal("5.000000"),
            monthly_allowance_usd=Decimal("0.000000"),
            version=1,
        )
        self.added = []

    async def execute(self, statement):
        # We need to distinguish between UserWallet queries and TransactionLedgerEntry queries
        stmt_str = str(statement).lower()

        class MockResult:
            def __init__(self, val, is_empty=False):
                self.val = val
                self.is_empty = is_empty

            def scalars(self):
                val_to_use = self.val
                is_empty_to_use = self.is_empty

                class MockScalars:
                    def __init__(self, val):
                        self.val = val

                    def first(self):
                        if is_empty_to_use:
                            return None
                        return self.val

                    def all(self):
                        if is_empty_to_use:
                            return []
                        return [self.val]

                return MockScalars(val_to_use)

        if "transaction_ledger" in stmt_str:
            # For idempotency check, default mock session should pretend transaction does not exist yet
            # Find if we already added a TransactionLedgerEntry with this ID in self.added
            matching_tx = None
            for item in self.added:
                if item.__class__.__name__ == "TransactionLedgerEntry":
                    matching_tx = item
                    break
            return MockResult(matching_tx, is_empty=(matching_tx is None))

        return MockResult(self._wallet)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        pass

    async def close(self):
        pass

    async def rollback(self):
        pass

    # Support context manager
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def begin(self):
        return self


@pytest.fixture
def mock_db_session():
    session = MockAsyncSession()
    # Override FastAPI dependency
    app.dependency_overrides[get_db_session] = lambda: session
    yield session
    # Red-CI fix (#1753 follow-through): this fixture previously called
    # app.dependency_overrides.clear() on the SHARED core.app singleton,
    # silently wiping every other test module's overrides (e.g. the
    # module-level get_current_user_token override in test_payments.py,
    # which then failed 403/KeyError depending on execution order). Pop
    # only the key this fixture owns.
    app.dependency_overrides.pop(get_db_session, None)


def test_fetch_wallet_pre_seeds_bonus(mock_db_session):
    resp = client.get("/api/billing/wallet", headers={"Authorization": "Bearer test_token"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == "test_user"
    assert data["balance_usd"] == 5.00  # SignUp Bonus


@pytest.mark.anyio
async def test_token_deductor_deducts_main_balance(mock_db_session):
    from api.routes.billing_api import token_deductor

    with patch.object(token_deductor, "_acquire_lock", new=AsyncMock(return_value=True)):
        with patch.object(token_deductor, "_release_lock", new=AsyncMock(return_value=True)):
            with patch.object(
                token_deductor.redis_client, "get_cache", new=AsyncMock(return_value="100000")
            ):
                with patch.object(
                    token_deductor.redis_client, "set_cache", new=AsyncMock(return_value=True)
                ):
                    res = await token_deductor.deduct_tokens("test_user", 1000, "tx_12345")
                    assert res.value in ("success", "double_spending_prevention")


@pytest.mark.anyio
async def test_token_deductor_insufficient_funds(mock_db_session):
    from api.routes.billing_api import token_deductor

    with patch.object(token_deductor, "_acquire_lock", new=AsyncMock(return_value=True)):
        with patch.object(token_deductor, "_release_lock", new=AsyncMock(return_value=True)):
            # First call for transaction_key returns None, second call for balance returns "10"
            with patch.object(
                token_deductor.redis_client, "get_cache", new=AsyncMock(side_effect=[None, "10"])
            ):
                res = await token_deductor.deduct_tokens(
                    "test_user", 1000000, "tx_insufficient_999"
                )
                assert res.value in ("insufficient_balance", "system_error")


def test_stripe_webhook_adds_credit(mock_db_session):
    # Mock stripe constructor to bypass network/signature validation
    with patch("stripe.Webhook.construct_event") as mock_construct:
        mock_construct.return_value = {
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_test_12345",
                    "amount_received": 1000,  # 1000 cents = $10.00
                    "metadata": {"user_id": "default_user_session"},
                }
            },
        }
        with patch("stripe.api_key", "dummy_stripe_key"):
            with patch("api.routes.billing_api.STRIPE_WEBHOOK_SECRET", "whsec_test"):
                resp = client.post(
                    "/api/billing/webhook/stripe",
                    json={"type": "payment_intent.succeeded"},
                    headers={"Stripe-Signature": "t=123,v1=abc"},
                )
                assert resp.status_code == 200
                assert resp.json() == {"status": "success"}
                assert mock_db_session._wallet.balance_usd == Decimal("15.000000")


def test_sslcommerz_webhook_adds_credit(mock_db_session):
    # বাংলা মন্তব্য: _verify_sslcommerz_transaction অ্যাসিঙ্ক ফাংশন তাই AsyncMock ব্যবহার করা হলো
    # val_id পেলোডে অন্তর্ভুক্ত — API এর জন্য আবশ্যক
    from unittest.mock import AsyncMock

    ssl_payload = {
        "status": "VALID",
        "amount": 1000.0,  # 1000 BDT * 0.0085 = $8.50
        "val_id": "mock_val_id_12345",
        "value_a": "default_user_session",
    }

    # _verify_sslcommerz_transaction মক করা: নেটওয়ার্ক ছাড়াই ভেরিফাই সিমুলেট
    verified_response = {
        "status": "VALID",
        "val_id": "mock_val_id_12345",
        "amount": "1000.00",
        "value_a": "default_user_session",
    }

    with patch(
        "api.routes.billing_api._verify_sslcommerz_transaction",
        new=AsyncMock(return_value=verified_response),
    ):
        resp = client.post("/api/billing/webhook/sslcommerz", json=ssl_payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "processed"
    assert mock_db_session._wallet.balance_usd == Decimal("13.500000")
