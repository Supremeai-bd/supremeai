from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts" / "billing"))

from fraud_detector import FraudDetector, FraudAlert, FraudReport  # noqa: E402


@pytest.fixture
def mock_db_session():
    session = AsyncMock()
    yield session


@pytest.fixture
def mock_http():
    client = AsyncMock()
    yield client


class TestFraudDetectorInit:
    def test_defaults(self):
        with patch.dict(os.environ, {"DATABASE_URL": "", "GOOGLE_CLOUD_PROJECT": "", "SLACK_WEBHOOK_URL": ""}):
            detector = FraudDetector()
            assert detector.database_url == ""
            assert detector.project_id == ""
            assert detector.slack_webhook == ""
            assert detector.fraud_spend_threshold == 3.0
            assert detector.db_session is None
            assert detector._http is None

    def test_custom_threshold(self):
        detector = FraudDetector(threshold=5.0)
        assert detector.fraud_spend_threshold == 5.0


class TestFraudDetectorContextManager:
    @pytest.mark.asyncio
    async def test_aenter_without_services(self):
        detector = FraudDetector()
        async with detector:
            assert detector.db_session is None
            assert detector._http is None

    @pytest.mark.asyncio
    async def test_aenter_with_db(self, mock_db_session):
        with patch.dict(os.environ, {"DATABASE_URL": "sqlite+aiosqlite:///:memory:"}):
            with patch("sqlalchemy.ext.asyncio.create_async_engine") as mock_engine:
                mock_engine.return_value = MagicMock()
                detector = FraudDetector()
                async with detector:
                    assert detector.db_session is not None

    @pytest.mark.asyncio
    async def test_aenter_with_slack(self, mock_http):
        with patch.dict(os.environ, {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/test"}):
            with patch("httpx.AsyncClient") as mock_async_client:
                mock_async_client.return_value = mock_http
                detector = FraudDetector()
                async with detector:
                    assert detector._http is not None

    @pytest.mark.asyncio
    async def test_aexit_closes_resources(self, mock_db_session, mock_http):
        detector = FraudDetector()
        detector.db_session = mock_db_session
        detector._http = mock_http
        async with detector:
            pass
        mock_db_session.close.assert_called_once()
        mock_http.aclose.assert_called_once()


class TestFraudDetectorTenantListing:
    @pytest.mark.asyncio
    async def test_get_tenant_ids_no_db(self):
        detector = FraudDetector()
        tenant_ids = await detector.get_tenant_ids()
        assert tenant_ids == []

    @pytest.mark.asyncio
    async def test_get_tenant_ids_with_db(self, mock_db_session):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("t1",), ("t2",)]
        mock_db_session.execute.return_value = mock_result
        detector = FraudDetector()
        detector.db_session = mock_db_session
        tenant_ids = await detector.get_tenant_ids()
        assert tenant_ids == ["t1", "t2"]

    @pytest.mark.asyncio
    async def test_get_tenant_ids_db_error(self, mock_db_session):
        mock_db_session.execute.side_effect = Exception("db error")
        detector = FraudDetector()
        detector.db_session = mock_db_session
        tenant_ids = await detector.get_tenant_ids()
        assert tenant_ids == []


class TestFraudDetectorLedger:
    @pytest.mark.asyncio
    async def test_get_ledger_entries_no_db(self):
        detector = FraudDetector()
        entries = await detector.get_ledger_entries("t1", datetime.now(UTC), datetime.now(UTC))
        assert entries == []

    @pytest.mark.asyncio
    async def test_get_ledger_entries_with_data(self, mock_db_session):
        from models.wallet import TransactionLedgerEntry
        entry = TransactionLedgerEntry(
            transaction_id="tx1",
            user_id="t1",
            amount_usd=Decimal("1.00"),
            transaction_type="charge",
            description="test",
            timestamp=datetime.now(UTC),
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [entry]
        mock_db_session.execute.return_value = mock_result
        detector = FraudDetector()
        detector.db_session = mock_db_session
        start = datetime.now(UTC) - timedelta(days=7)
        end = datetime.now(UTC)
        entries = await detector.get_ledger_entries("t1", start, end)
        assert len(entries) == 1
        assert entries[0]["transaction_id"] == "tx1"

    @pytest.mark.asyncio
    async def test_get_ledger_entries_db_error(self, mock_db_session):
        mock_db_session.execute.side_effect = Exception("db error")
        detector = FraudDetector()
        detector.db_session = mock_db_session
        entries = await detector.get_ledger_entries("t1", datetime.now(UTC), datetime.now(UTC))
        assert entries == []


class TestFraudDetectorAnomalyDetection:
    @pytest.mark.asyncio
    async def test_scan_tenant_no_db(self):
        detector = FraudDetector()
        alerts = await detector.scan_tenant("t1", days=7)
        assert alerts == []

    @pytest.mark.asyncio
    async def test_scan_tenant_with_entries(self, mock_db_session):
        from models.wallet import TransactionLedgerEntry
        entries = []
        now = datetime.now(UTC)
        for i in range(6):
            entries.append(TransactionLedgerEntry(
                transaction_id=f"tx{i}",
                user_id="t1",
                amount_usd=Decimal("10.00"),
                transaction_type="topup",
                description="topup failed: insufficient funds",
                timestamp=now - timedelta(hours=i),
            ))
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = entries
        mock_db_session.execute.return_value = mock_result
        detector = FraudDetector()
        detector.db_session = mock_db_session
        alerts = await detector.scan_tenant("t1", days=1)
        assert len(alerts) == 1
        assert alerts[0].alert_type == "repeated_failed_topups"


class TestFraudDetectorScanAll:
    @pytest.mark.asyncio
    async def test_scan_all(self, mock_db_session):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("t1",)]
        mock_db_session.execute.return_value = mock_result
        detector = FraudDetector()
        detector.db_session = mock_db_session
        report = await detector.scan_all()
        assert report.report_id != ""
        assert report.generated_at != ""

    @pytest.mark.asyncio
    async def test_scan_all_db_error(self, mock_db_session):
        mock_db_session.execute.side_effect = Exception("db error")
        detector = FraudDetector()
        detector.db_session = mock_db_session
        report = await detector.scan_all()
        assert report.alerts == []
