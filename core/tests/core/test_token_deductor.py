from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.llm.token_deductor import TokenDeductor


@pytest.mark.anyio
async def test_acquire_distributed_lock_fail_closed_in_production(monkeypatch):
    td = TokenDeductor()

    monkeypatch.setattr(td, "_acquire_distributed_lock", td._acquire_distributed_lock)

    from core.config import settings

    # Simulate redis unavailable
    monkeypatch.setattr(
        "core.llm.token_deductor.redis_queue.configured",
        False,
        raising=False,
    )
    monkeypatch.setattr(settings, "env", "production", raising=False)

    with pytest.raises(RuntimeError):
        td._acquire_distributed_lock("k", "v", ttl=1)


@pytest.mark.anyio
async def test_deduct_tokens_success_happy_path(monkeypatch):
    td = TokenDeductor()

    # Force lock acquired and release no-op
    monkeypatch.setattr(td, "_acquire_distributed_lock", lambda *args, **kwargs: True)
    monkeypatch.setattr(td, "_release_distributed_lock", lambda *args, **kwargs: None)

    # Fake session / wallet
    wallet = MagicMock()
    wallet.user_id = "u1"
    wallet.balance_usd = Decimal("1.000")
    wallet.monthly_allowance_usd = Decimal("1.000")

    # AsyncSession mock
    session = MagicMock()
    session.begin = AsyncMock()

    # session.execute returns object with scalars().first()
    class _Result:
        def scalars(self):
            return self

        def first(self):
            return wallet

    async def _execute(*args, **kwargs):
        return _Result()

    session.execute = AsyncMock(side_effect=_execute)
    session.add = MagicMock()

    res = await td.deduct_tokens(
        session, user_id="u1", input_tokens=100, output_tokens=100, model_name="m"
    )
    assert res is True
    assert session.add.call_count == 1


@pytest.mark.anyio
async def test_deduct_tokens_insufficient_funds(monkeypatch):
    td = TokenDeductor()

    monkeypatch.setattr(td, "_acquire_distributed_lock", lambda *args, **kwargs: True)
    monkeypatch.setattr(td, "_release_distributed_lock", lambda *args, **kwargs: None)

    wallet = MagicMock()
    wallet.user_id = "u1"
    wallet.balance_usd = Decimal("0.000")
    wallet.monthly_allowance_usd = Decimal("0.000")

    session = MagicMock()
    session.begin = AsyncMock()

    class _Result:
        def scalars(self):
            return self

        def first(self):
            return wallet

    session.execute = AsyncMock(return_value=_Result())
    session.add = MagicMock()

    res = await td.deduct_tokens(
        session, user_id="u1", input_tokens=100000, output_tokens=100000, model_name="m"
    )
    assert res is False
