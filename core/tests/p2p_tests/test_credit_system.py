import pytest

from p2p.credit_system import CreditLedger, ResourceBroker


class TestCreditLedger:
    @pytest.mark.asyncio
    async def test_earn(self):
        ledger = CreditLedger()
        result = await ledger.earn("user1", 10.0, "task_completed")
        assert result["user_id"] == "user1"
        assert result["amount"] == 10.0
        assert result["type"] == "credit"
        assert "tx_id" in result

    @pytest.mark.asyncio
    async def test_spend(self):
        ledger = CreditLedger()
        result = await ledger.spend("user1", 5.0, "api_call")
        assert result["user_id"] == "user1"
        assert result["amount"] == -5.0
        assert result["type"] == "debit"

    @pytest.mark.asyncio
    async def test_balance(self):
        ledger = CreditLedger()
        balance = await ledger.balance("user1")
        assert balance == 0.0

    @pytest.mark.asyncio
    async def test_opt_in(self):
        ledger = CreditLedger()
        await ledger.opt_in("user1")

    @pytest.mark.asyncio
    async def test_opt_out(self):
        ledger = CreditLedger()
        await ledger.opt_out("user1")


class TestResourceBroker:
    @pytest.mark.asyncio
    async def test_match(self):
        broker = ResourceBroker()
        result = await broker.match({"task_id": "t1"})
        assert "matched" in result
        assert result["matched"] is False
        assert result["reason"] == "no_available_peers"
