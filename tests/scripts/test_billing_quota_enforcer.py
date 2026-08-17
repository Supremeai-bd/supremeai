from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts" / "billing"))

from quota_enforcer import QuotaEnforcer, QuotaStatus, EnforcementReport  # noqa: E402


@pytest.fixture
def mock_firestore():
    return MagicMock()


@pytest.fixture
def mock_db_session():
    session = AsyncMock()
    yield session


@pytest.fixture
def mock_redis():
    return AsyncMock()


@pytest.fixture
def pricing_tiers_path(tmp_path):
    tiers = {
        "signup_bonus_usd": 5.0,
        "tiers": {
            "free": {"monthly_credits_usd": 10.0},
            "pro": {"monthly_credits_usd": 100.0},
            "enterprise": {"monthly_credits_usd": 1000.0},
        },
    }
    p = tmp_path / "pricing_tiers.json"
    p.write_text(json.dumps(tiers))
    return str(p)


class TestQuotaEnforcerInit:
    def test_defaults(self, pricing_tiers_path):
        enforcer = QuotaEnforcer(pricing_path=pricing_tiers_path)
        assert enforcer.project_id == os.getenv("GOOGLE_CLOUD_PROJECT", "")
        assert enforcer.database_url == os.getenv("DATABASE_URL", "")
        assert enforcer.redis_url == os.getenv("REDIS_URL", "")
        assert enforcer.slack_webhook == os.getenv("SLACK_WEBHOOK_URL", "")
        assert enforcer.discord_webhook == os.getenv("DISCORD_WEBHOOK_URL", "")
        assert "free" in enforcer.pricing_tiers.get("tiers", {})

    def test_custom_pricing_path(self, pricing_tiers_path):
        enforcer = QuotaEnforcer(pricing_path=pricing_tiers_path)
        assert "pro" in enforcer.pricing_tiers.get("tiers", {})

    def test_pricing_path_missing(self):
        enforcer = QuotaEnforcer(pricing_path="nonexistent.json")
        assert enforcer.pricing_tiers == {}


class TestQuotaEnforcerContextManager:
    @pytest.mark.asyncio
    async def test_aenter_without_services(self):
        with patch.dict(os.environ, {"DATABASE_URL": "", "GOOGLE_CLOUD_PROJECT": "", "REDIS_URL": "", "SLACK_WEBHOOK_URL": ""}):
            enforcer = QuotaEnforcer()
            async with enforcer:
                assert enforcer.firestore_client is None
                assert enforcer.db_session is None
                assert enforcer._redis_lock is None

    @pytest.mark.asyncio
    async def test_aenter_with_firestore(self):
        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"}):
            with patch("google.cloud.firestore.Client") as mock_client:
                mock_instance = MagicMock()
                mock_client.return_value = mock_instance
                enforcer = QuotaEnforcer()
                async with enforcer:
                    assert enforcer.firestore_client is not None

    @pytest.mark.asyncio
    async def test_aenter_with_redis(self):
        with patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379/0"}):
            with patch("redis.asyncio.from_url") as mock_from_url:
                mock_instance = AsyncMock()
                mock_from_url.return_value = mock_instance
                enforcer = QuotaEnforcer()
                async with enforcer:
                    assert enforcer._redis_lock is not None

    @pytest.mark.asyncio
    async def test_aexit_closes_resources(self, mock_db_session, mock_redis):
        with patch.dict(os.environ, {"DATABASE_URL": "", "GOOGLE_CLOUD_PROJECT": "", "REDIS_URL": "", "SLACK_WEBHOOK_URL": ""}):
            enforcer = QuotaEnforcer()
            enforcer.db_session = mock_db_session
            enforcer._redis_lock = mock_redis
            await enforcer.__aexit__(None, None, None)
            mock_db_session.close.assert_called_once()
            mock_redis.aclose.assert_called_once()


class TestQuotaEnforcerPricingTiers:
    def test_get_tier_allowance_free(self, pricing_tiers_path):
        enforcer = QuotaEnforcer(pricing_path=pricing_tiers_path)
        allowance = enforcer.get_tier_allowance("free")
        assert allowance == Decimal("10.0")

    def test_get_tier_allowance_pro(self, pricing_tiers_path):
        enforcer = QuotaEnforcer(pricing_path=pricing_tiers_path)
        allowance = enforcer.get_tier_allowance("pro")
        assert allowance == Decimal("100.0")

    def test_get_tier_allowance_missing_tier(self, pricing_tiers_path):
        enforcer = QuotaEnforcer(pricing_path=pricing_tiers_path)
        allowance = enforcer.get_tier_allowance("nonexistent")
        assert allowance == Decimal("10.0")

    def test_get_tier_allowance_empty_tiers(self):
        enforcer = QuotaEnforcer(pricing_path="nonexistent.json")
        allowance = enforcer.get_tier_allowance("free")
        assert allowance == Decimal("0")


class TestQuotaEnforcerTenantListing:
    @pytest.mark.asyncio
    async def test_get_all_tenant_ids_no_firestore(self):
        enforcer = QuotaEnforcer()
        tenant_ids = await enforcer.get_all_tenant_ids()
        assert tenant_ids == []

    @pytest.mark.asyncio
    async def test_get_all_tenant_ids_with_firestore(self, mock_firestore):
        mock_doc = MagicMock()
        mock_doc.to_dict.return_value = {"tenant_id": "t1"}

        async def _stream():
            yield mock_doc

        mock_firestore.collection.return_value.stream.return_value = _stream()
        enforcer = QuotaEnforcer()
        enforcer.firestore_client = mock_firestore
        tenant_ids = await enforcer.get_all_tenant_ids()
        assert tenant_ids == ["t1"]

    @pytest.mark.asyncio
    async def test_get_all_tenant_ids_firestore_error(self, mock_firestore):
        mock_firestore.collection.return_value.stream.side_effect = Exception("firestore error")
        enforcer = QuotaEnforcer()
        enforcer.firestore_client = mock_firestore
        tenant_ids = await enforcer.get_all_tenant_ids()
        assert tenant_ids == []


class TestQuotaEnforcerWallet:
    @pytest.mark.asyncio
    async def test_get_wallet_no_db(self):
        enforcer = QuotaEnforcer()
        wallet = await enforcer.get_wallet("t1")
        assert wallet is None

    @pytest.mark.asyncio
    async def test_get_wallet_found(self, mock_db_session):
        from models.wallet import UserWallet
        wallet = UserWallet(
            user_id="t1",
            balance_usd=Decimal("50.0"),
            monthly_allowance_usd=Decimal("100.0"),
            version=1,
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = wallet
        mock_db_session.execute.return_value = mock_result
        enforcer = QuotaEnforcer()
        enforcer.db_session = mock_db_session
        result = await enforcer.get_wallet("t1")
        assert result is not None
        assert result["user_id"] == "t1"
        assert result["balance_usd"] == Decimal("50.0")

    @pytest.mark.asyncio
    async def test_get_wallet_not_found(self, mock_db_session):
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db_session.execute.return_value = mock_result
        enforcer = QuotaEnforcer()
        enforcer.db_session = mock_db_session
        result = await enforcer.get_wallet("t1")
        assert result is None


class TestQuotaEnforcerUsage:
    @pytest.mark.asyncio
    async def test_get_current_usage_no_db(self):
        enforcer = QuotaEnforcer()
        usage = await enforcer.get_current_usage_usd("t1")
        assert usage == Decimal("0")

    @pytest.mark.asyncio
    async def test_get_current_usage_with_data(self, mock_db_session):
        from models.wallet import TransactionLedgerEntry
        entry = TransactionLedgerEntry(
            transaction_id="tx1",
            user_id="t1",
            amount_usd=Decimal("25.0"),
            transaction_type="charge",
            description="test",
            timestamp=datetime.now(UTC),
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [entry]
        mock_db_session.execute.return_value = mock_result
        enforcer = QuotaEnforcer()
        enforcer.db_session = mock_db_session
        usage = await enforcer.get_current_usage_usd("t1")
        assert usage == Decimal("25.0")

    @pytest.mark.asyncio
    async def test_get_current_usage_db_error(self, mock_db_session):
        mock_db_session.execute.side_effect = Exception("db error")
        enforcer = QuotaEnforcer()
        enforcer.db_session = mock_db_session
        usage = await enforcer.get_current_usage_usd("t1")
        assert usage == Decimal("0")


class TestQuotaEnforcerQuotaStatus:
    def test_within_quota(self):
        status = QuotaStatus(
            tenant_id="t1",
            tier="free",
            monthly_allowance_usd=Decimal("100.0"),
            current_usage_usd=Decimal("50.0"),
            remaining_usd=Decimal("50.0"),
            utilization_pct=50.0,
            status="within_quota",
        )
        assert status.status == "within_quota"
        assert status.action == ""

    def test_over_quota(self):
        status = QuotaStatus(
            tenant_id="t1",
            tier="free",
            monthly_allowance_usd=Decimal("100.0"),
            current_usage_usd=Decimal("120.0"),
            remaining_usd=Decimal("-20.0"),
            utilization_pct=120.0,
            status="over_quota",
            action="suspend",
        )
        assert status.status == "over_quota"
        assert status.action == "suspend"


class TestQuotaEnforcerEnforcement:
    @pytest.mark.asyncio
    async def test_check_tenant_quota_no_db(self):
        enforcer = QuotaEnforcer()
        status = await enforcer.check_tenant_quota("t1")
        assert status is None

    @pytest.mark.asyncio
    async def test_check_tenant_quota_within_quota(self, mock_db_session, pricing_tiers_path):
        from models.wallet import UserWallet
        wallet = UserWallet(
            user_id="t1",
            balance_usd=Decimal("50.0"),
            monthly_allowance_usd=Decimal("100.0"),
            version=1,
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = wallet
        mock_db_session.execute.return_value = mock_result
        enforcer = QuotaEnforcer(pricing_path=pricing_tiers_path)
        enforcer.db_session = mock_db_session
        mock_firestore = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_firestore.collection.return_value.document.return_value.collection.return_value.document.return_value.get.return_value = mock_doc
        enforcer.firestore_client = mock_firestore
        status = await enforcer.check_tenant_quota("t1")
        assert status is not None
        assert status.status == "ok"

    @pytest.mark.asyncio
    async def test_check_tenant_quota_over_quota(self, mock_db_session, pricing_tiers_path):
        from models.wallet import UserWallet
        from models.wallet import TransactionLedgerEntry
        wallet = UserWallet(
            user_id="t1",
            balance_usd=Decimal("150.0"),
            monthly_allowance_usd=Decimal("100.0"),
            version=1,
        )
        wallet_result = MagicMock()
        wallet_result.scalars.return_value.first.return_value = wallet
        usage_entry = TransactionLedgerEntry(
            transaction_id="tx1",
            user_id="t1",
            amount_usd=Decimal("150.0"),
            transaction_type="charge",
            description="test",
            timestamp=datetime.now(UTC),
        )
        usage_result = MagicMock()
        usage_result.scalars.return_value.all.return_value = [usage_entry]
        mock_db_session.execute.side_effect = [wallet_result, usage_result]
        enforcer = QuotaEnforcer(pricing_path=pricing_tiers_path)
        enforcer.db_session = mock_db_session
        mock_firestore = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_firestore.collection.return_value.document.return_value.collection.return_value.document.return_value.get.return_value = mock_doc
        enforcer.firestore_client = mock_firestore
        status = await enforcer.check_tenant_quota("t1")
        assert status is not None
        assert status.status == "exceeded"

    @pytest.mark.asyncio
    async def test_enforce_all_dry_run(self, mock_db_session, pricing_tiers_path):
        from models.wallet import UserWallet
        wallet = UserWallet(
            user_id="t1",
            balance_usd=Decimal("50.0"),
            monthly_allowance_usd=Decimal("100.0"),
            version=1,
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = wallet
        mock_db_session.execute.return_value = mock_result
        enforcer = QuotaEnforcer(pricing_path=pricing_tiers_path)
        enforcer.db_session = mock_db_session
        mock_firestore = MagicMock()
        mock_doc = MagicMock()
        mock_doc.to_dict.return_value = {}
        mock_doc.exists = False

        async def _stream():
            yield mock_doc

        mock_firestore.collection.return_value.stream.return_value = _stream()
        mock_firestore.collection.return_value.document.return_value.collection.return_value.document.return_value.get.return_value = mock_doc
        enforcer.firestore_client = mock_firestore
        report = await enforcer.enforce_all(notify=False, dry_run=True)
        assert report.scanned_count == 1


class TestQuotaEnforcerFirestore:
    @pytest.mark.asyncio
    async def test_suspend_tenant_no_firestore(self):
        enforcer = QuotaEnforcer()
        result = await enforcer.suspend_tenant("t1")
        assert result is False

    @pytest.mark.asyncio
    async def test_suspend_tenant_success(self, mock_firestore):
        tenant_ref = MagicMock()
        tenant_ref.update = AsyncMock(return_value=None)
        mock_firestore.collection.return_value.document.return_value = tenant_ref
        enforcer = QuotaEnforcer()
        enforcer.firestore_client = mock_firestore
        result = await enforcer.suspend_tenant("t1")
        assert result is True

    @pytest.mark.asyncio
    async def test_suspend_tenant_error(self, mock_firestore):
        mock_firestore.collection.return_value.document.return_value.update.side_effect = Exception("firestore error")
        enforcer = QuotaEnforcer()
        enforcer.firestore_client = mock_firestore
        result = await enforcer.suspend_tenant("t1")
        assert result is False
