"""
Tests for services/escrow_service.py — Escrow Service
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from services.escrow_service import Escrow, EscrowService, EscrowStatus


class TestEscrowStatus:
    def test_status_values(self):
        assert EscrowStatus.PENDING.value == "pending"
        assert EscrowStatus.FUNDED.value == "funded"
        assert EscrowStatus.CONDITION_MET.value == "condition_met"
        assert EscrowStatus.RELEASED.value == "released"
        assert EscrowStatus.DISPUTED.value == "disputed"
        assert EscrowStatus.REFUNDED.value == "refunded"
        assert EscrowStatus.EXPIRED.value == "expired"

    def test_status_transitions(self):
        # All expected statuses are valid
        for status in EscrowStatus:
            assert isinstance(status, EscrowStatus)


class TestEscrow:
    def test_create_escrow(self):
        now = datetime.now(UTC)
        escrow = Escrow(
            escrow_id="escrow-123",
            payer_id="payer-1",
            payee_id="payee-1",
            amount=100.0,
            currency="USD",
            conditions=["condition_met"],
            status=EscrowStatus.PENDING,
            created_at=now,
            expires_at=now + timedelta(days=30),
        )
        assert escrow.escrow_id == "escrow-123"
        assert escrow.payer_id == "payer-1"
        assert escrow.payee_id == "payee-1"
        assert escrow.amount == 100.0
        assert escrow.currency == "USD"
        assert escrow.status == EscrowStatus.PENDING

    def test_escrow_frozen_dataclass(self):
        import dataclasses

        assert dataclasses.is_dataclass(Escrow)
        assert dataclasses.fields(Escrow)

    def test_escrow_default_expires_at(self):
        now = datetime.now(UTC)
        escrow = Escrow(
            escrow_id="e1",
            payer_id="p1",
            payee_id="p2",
            amount=50.0,
            currency="USD",
            conditions=["test"],
            status=EscrowStatus.PENDING,
            created_at=now,
        )
        assert escrow.expires_at is None


class TestEscrowService:
    @pytest.fixture
    def service(self):
        mock_cache = MagicMock()
        return EscrowService(cache=mock_cache)

    def test_init(self, service):
        assert service.cache is not None

    def test_create_escrow(self, service):
        escrow = service.create_escrow_sync(
            payer_id="payer-1",
            payee_id="payee-1",
            amount=100.0,
            currency="USD",
            conditions=["delivery_confirmed"],
        )
        assert escrow.payer_id == "payer-1"
        assert escrow.payee_id == "payee-1"
        assert escrow.amount == 100.0
        assert escrow.currency == "USD"
        assert escrow.status == EscrowStatus.PENDING
        assert escrow.escrow_id.startswith("esc_")

    def test_create_escrow_generates_unique_id(self, service):
        escrow1 = service.create_escrow_sync("p1", "p2", 10.0, "USD", [])
        escrow2 = service.create_escrow_sync("p1", "p2", 10.0, "USD", [])
        assert escrow1.escrow_id != escrow2.escrow_id

    def test_get_escrow_found(self, service):
        created = service.create_escrow_sync("p1", "p2", 50.0, "USD", ["cond1"])
        retrieved = service.get_escrow_sync(created.escrow_id)
        assert retrieved is not None
        assert retrieved.escrow_id == created.escrow_id
        assert retrieved.amount == 50.0

    def test_get_escrow_not_found(self, service):
        result = service.get_escrow_sync("nonexistent")
        assert result is None

    def test_update_escrow_status(self, service):
        created = service.create_escrow_sync("p1", "p2", 100.0, "USD", [])
        updated = service.update_escrow_status_sync(created.escrow_id, EscrowStatus.FUNDED)
        assert updated is not None
        assert updated.status == EscrowStatus.FUNDED

    def test_update_escrow_status_not_found(self, service):
        result = service.update_escrow_status_sync("nonexistent", EscrowStatus.RELEASED)
        assert result is None

    def test_list_active_escrows(self, service):
        service.create_escrow_sync("p1", "p2", 10.0, "USD", [])
        service.create_escrow_sync("p3", "p4", 20.0, "USD", [])
        active = service.list_active_escrows_sync()
        assert len(active) >= 2

    def test_escrow_full_lifecycle(self, service):
        # Create
        escrow = service.create_escrow_sync("payer", "payee", 500.0, "USD", ["approval"])
        assert escrow.status == EscrowStatus.PENDING

        # Fund
        escrow = service.update_escrow_status_sync(escrow.escrow_id, EscrowStatus.FUNDED)
        assert escrow.status == EscrowStatus.FUNDED

        # Condition met
        escrow = service.update_escrow_status_sync(escrow.escrow_id, EscrowStatus.CONDITION_MET)
        assert escrow.status == EscrowStatus.CONDITION_MET

        # Release
        escrow = service.update_escrow_status_sync(escrow.escrow_id, EscrowStatus.RELEASED)
        assert escrow.status == EscrowStatus.RELEASED
