from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts" / "billing"))

from usage_reporter import UsageReporter, TenantUsage  # noqa: E402


def async_iter(items):
    async def _gen():
        for item in items:
            yield item
    return _gen()


@pytest.fixture
def mock_firestore():
    with patch("usage_reporter.firestore") as mock:
        instance = MagicMock()
        mock.Client.return_value = instance
        yield instance


@pytest.fixture
def mock_db_session():
    session = AsyncMock()
    yield session


@pytest.fixture
def mock_http():
    client = AsyncMock()
    yield client


class TestTenantUsageDataclass:
    def test_defaults(self):
        usage = TenantUsage(
            tenant_id="t1",
            period_start=datetime.now(UTC),
            period_end=datetime.now(UTC),
            total_spend_usd=Decimal("0"),
            total_transactions=0,
            token_input_count=0,
            token_output_count=0,
            topup_count=0,
            byoc_deployments=0,
        )
        assert usage.tenant_id == "t1"
        assert usage.total_spend_usd == Decimal("0")
        assert usage.total_transactions == 0

    def test_to_dict(self):
        usage = TenantUsage(
            tenant_id="t1",
            period_start=datetime.now(UTC),
            period_end=datetime.now(UTC),
            total_spend_usd=Decimal("10.50"),
            total_transactions=3,
            token_input_count=100,
            token_output_count=200,
            topup_count=1,
            byoc_deployments=0,
        )
        data = usage.to_dict()
        assert data["tenant_id"] == "t1"
        assert data["total_spend_usd"] == 10.5
        assert data["total_transactions"] == 3


class TestUsageReporterInit:
    def test_defaults(self):
        with patch.dict(os.environ, {"DATABASE_URL": "", "GOOGLE_CLOUD_PROJECT": "", "REDIS_URL": "", "SLACK_WEBHOOK_URL": ""}):
            reporter = UsageReporter()
            assert reporter.database_url == ""
            assert reporter.project_id == ""
            assert reporter.redis_url == ""
            assert reporter.slack_webhook == ""
            assert reporter.db_session is None
            assert reporter.firestore_client is None
            assert reporter._http is None


class TestUsageReporterContextManager:
    @pytest.mark.asyncio
    async def test_aenter_without_services(self):
        with patch.dict(os.environ, {"DATABASE_URL": "", "GOOGLE_CLOUD_PROJECT": "", "REDIS_URL": "", "SLACK_WEBHOOK_URL": ""}):
            reporter = UsageReporter()
            async with reporter:
                assert reporter.firestore_client is None
                assert reporter.db_session is None
                assert reporter._http is None

    @pytest.mark.asyncio
    async def test_aenter_with_firestore(self, mock_firestore):
        reporter = UsageReporter(project_id="test-project")
        async with reporter:
            assert reporter.firestore_client is not None

    @pytest.mark.asyncio
    async def test_aenter_firestore_failure(self):
        with patch("usage_reporter.firestore") as mock_fs:
            mock_fs.Client.side_effect = Exception("auth failed")
            reporter = UsageReporter(project_id="test-project")
            async with reporter:
                assert reporter.firestore_client is None

    @pytest.mark.asyncio
    async def test_aexit_closes_resources(self, mock_db_session, mock_http):
        with patch.dict(os.environ, {"DATABASE_URL": "", "GOOGLE_CLOUD_PROJECT": "", "REDIS_URL": "", "SLACK_WEBHOOK_URL": ""}):
            reporter = UsageReporter()
            reporter.db_session = mock_db_session
            reporter._http = mock_http
            await reporter.__aexit__(None, None, None)
            mock_db_session.close.assert_called_once()
            mock_http.aclose.assert_called_once()


class TestUsageReporterTenantListing:
    @pytest.mark.asyncio
    async def test_get_all_tenants_no_firestore(self):
        reporter = UsageReporter()
        tenant_ids = await reporter.get_all_tenants()
        assert tenant_ids == []

    @pytest.mark.asyncio
    async def test_get_all_tenants_with_firestore(self, mock_firestore):
        doc1 = MagicMock()
        doc1.id = "t1"
        doc1.to_dict.return_value = {}
        doc2 = MagicMock()
        doc2.id = "t2"
        doc2.to_dict.return_value = {}
        mock_firestore.collection.return_value.stream.return_value = async_iter([doc1, doc2])
        reporter = UsageReporter()
        reporter.firestore_client = mock_firestore
        tenant_ids = await reporter.get_all_tenants()
        assert tenant_ids == ["t1", "t2"]

    @pytest.mark.asyncio
    async def test_get_all_tenants_firestore_error(self, mock_firestore):
        mock_firestore.collection.return_value.stream.side_effect = Exception("firestore error")
        reporter = UsageReporter()
        reporter.firestore_client = mock_firestore
        tenant_ids = await reporter.get_all_tenants()
        assert tenant_ids == []


class TestUsageReporterFirestore:
    @pytest.mark.asyncio
    async def test_get_usage_from_firestore_no_client(self):
        reporter = UsageReporter()
        usage = await reporter.get_tenant_usage_from_firestore("t1", datetime.now(UTC), datetime.now(UTC))
        assert usage["api_calls"] == 0
        assert usage["storage_mb"] == 0

    @pytest.mark.asyncio
    async def test_get_usage_from_firestore_with_data(self, mock_firestore):
        doc1 = MagicMock()
        doc1.to_dict.return_value = {"current_period": {"api_calls": 10, "storage_mb": 100}}
        doc2 = MagicMock()
        doc2.to_dict.return_value = {"current_period": {"api_calls": 5, "storage_mb": 50}}
        mock_firestore.collection.return_value.document.return_value.collection.return_value.stream.return_value = async_iter([doc1, doc2])
        reporter = UsageReporter()
        reporter.firestore_client = mock_firestore
        start = datetime.now(UTC) - timedelta(days=30)
        end = datetime.now(UTC)
        usage = await reporter.get_tenant_usage_from_firestore("t1", start, end)
        assert usage["api_calls"] == 15
        assert usage["storage_mb"] == 150

    @pytest.mark.asyncio
    async def test_get_usage_from_firestore_error(self, mock_firestore):
        mock_firestore.collection.return_value.document.return_value.collection.return_value.stream.side_effect = Exception("firestore error")
        reporter = UsageReporter()
        reporter.firestore_client = mock_firestore
        usage = await reporter.get_tenant_usage_from_firestore("t1", datetime.now(UTC), datetime.now(UTC))
        assert usage["api_calls"] == 0


class TestUsageReporterLedger:
    @pytest.mark.asyncio
    async def test_get_ledger_entries_no_db(self):
        reporter = UsageReporter()
        entries = await reporter.get_ledger_entries("t1", datetime.now(UTC), datetime.now(UTC))
        assert entries == []

    @pytest.mark.asyncio
    async def test_get_ledger_entries_with_data(self, mock_db_session):
        from models.wallet import TransactionLedgerEntry
        entry = TransactionLedgerEntry(
            transaction_id="tx1",
            user_id="t1",
            amount_usd=Decimal("1.50"),
            transaction_type="charge",
            description="test",
            timestamp=datetime.now(UTC),
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [entry]
        mock_db_session.execute.return_value = mock_result
        reporter = UsageReporter()
        reporter.db_session = mock_db_session
        start = datetime.now(UTC) - timedelta(days=30)
        end = datetime.now(UTC)
        entries = await reporter.get_ledger_entries("t1", start, end)
        assert len(entries) == 1
        assert entries[0]["transaction_id"] == "tx1"
        assert entries[0]["amount_usd"] == 1.5

    @pytest.mark.asyncio
    async def test_get_ledger_entries_db_error(self, mock_db_session):
        mock_db_session.execute.side_effect = Exception("db error")
        reporter = UsageReporter()
        reporter.db_session = mock_db_session
        entries = await reporter.get_ledger_entries("t1", datetime.now(UTC), datetime.now(UTC))
        assert entries == []


class TestUsageReporterReportGeneration:
    @pytest.mark.asyncio
    async def test_generate_tenant_report_no_services(self):
        reporter = UsageReporter()
        start = datetime.now(UTC) - timedelta(days=30)
        end = datetime.now(UTC)
        report = await reporter.generate_tenant_report("t1", start, end)
        assert report.tenant_id == "t1"
        assert report.total_spend_usd == Decimal("0")
        assert report.total_transactions == 0

    @pytest.mark.asyncio
    async def test_generate_tenant_report_with_data(self, mock_firestore, mock_db_session):
        from models.wallet import TransactionLedgerEntry
        entry = TransactionLedgerEntry(
            transaction_id="tx1",
            user_id="t1",
            amount_usd=Decimal("5.00"),
            transaction_type="charge",
            description="test",
            timestamp=datetime.now(UTC),
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [entry]
        mock_db_session.execute.return_value = mock_result
        doc = MagicMock()
        doc.to_dict.return_value = {"current_period": {"api_calls": 10}}
        mock_firestore.collection.return_value.document.return_value.collection.return_value.stream.return_value = async_iter([doc])
        reporter = UsageReporter()
        reporter.firestore_client = mock_firestore
        reporter.db_session = mock_db_session
        start = datetime.now(UTC) - timedelta(days=30)
        end = datetime.now(UTC)
        report = await reporter.generate_tenant_report("t1", start, end)
        assert report.tenant_id == "t1"
        assert report.total_transactions == 1
        assert report.total_spend_usd == Decimal("5.00")
