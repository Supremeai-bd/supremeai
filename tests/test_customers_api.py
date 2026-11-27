"""Tests for SupremeAI Customer Directory API (both /api/customers and /api/admin/customers)."""

import asyncio
import copy
from unittest.mock import AsyncMock

import pytest
from api.routes import customers
from api.routes.customers import router as customers_router
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    # বাংলা: memory-only পরীক্ষা dependency override দিয়ে স্পষ্ট করা হয়েছে।
    app = FastAPI()
    app.include_router(customers_router)
    app.dependency_overrides[customers._db_session_or_none] = lambda: None
    return TestClient(app)


def test_get_customers_list(client):
    """Test retrieving customer list matching 12 seed customers."""
    response = client.get("/api/customers")
    assert response.status_code == 200
    data = response.json()
    assert "customers" in data
    assert isinstance(data["customers"], list)
    assert len(data["customers"]) >= 12

    # Verify first customer format
    cust = data["customers"][0]
    assert "id" in cust
    assert "name" in cust
    assert "email" in cust
    assert "tier" in cust
    assert "status" in cust
    assert "mrr" in cust


def test_get_admin_customers_list(client):
    """Test retrieving admin customers list."""
    response = client.get("/api/admin/customers")
    assert response.status_code == 200
    data = response.json()
    assert "customers" in data
    assert isinstance(data["customers"], list)
    assert len(data["customers"]) >= 12


def test_create_and_get_customer(client):
    """Test creating a new customer and retrieving it."""
    new_cust = {
        "name": "Integration Test User",
        "email": "test.integration@supremeai.bd",
        "tier": "Pro",
        "status": "active",
        "mrr": 29.0,
        "tokensUsed": 500,
        "tokenLimit": 1000000,
        "connectedRepos": 1,
        "githubHandle": "test-integration",
        "region": "Asia/Dhaka",
        "isDeveloperEligible": True,
    }
    create_res = client.post("/api/customers", json=new_cust)
    assert create_res.status_code == 201
    created = create_res.json()["customer"]
    cust_id = created["id"]
    assert created["name"] == "Integration Test User"
    assert created["email"] == "test.integration@supremeai.bd"

    # Get single customer
    get_res = client.get(f"/api/customers/{cust_id}")
    assert get_res.status_code == 200
    fetched = get_res.json()["customer"]
    assert fetched["id"] == cust_id
    assert fetched["name"] == "Integration Test User"

    # Update customer
    patch_res = client.patch(f"/api/customers/{cust_id}", json={"tier": "Enterprise", "mrr": 199.0})
    assert patch_res.status_code == 200
    updated = patch_res.json()["customer"]
    assert updated["tier"] == "Enterprise"
    assert updated["mrr"] == 199.0

    # Delete customer
    del_res = client.delete(f"/api/customers/{cust_id}")
    assert del_res.status_code == 200
    del_data = del_res.json()
    assert del_data["success"] is True

    # Verify deleted
    get_after_del = client.get(f"/api/customers/{cust_id}")
    assert get_after_del.status_code == 404


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("GET", "/api/customers", None),
        ("GET", "/api/customers/cust_001", None),
        ("POST", "/api/customers", {"name": "Test", "email": "new@example.com"}),
        ("PATCH", "/api/customers/cust_001", {"tier": "Pro"}),
        ("DELETE", "/api/customers/cust_001", None),
    ],
)
def test_database_failures_do_not_fall_back_to_memory(client, caplog, method, path, payload):
    session = AsyncMock()
    session.execute.side_effect = RuntimeError("private customer detail")
    client.app.dependency_overrides[customers._db_session_or_none] = lambda: session
    before = copy.deepcopy(customers._MEMORY_CUSTOMERS)
    response = client.request(method, path, json=payload)
    assert response.status_code == 503
    assert response.json()["detail"] == "Customer database unavailable"
    assert customers._MEMORY_CUSTOMERS == before
    assert "Customer database operation failed (RuntimeError)" in caplog.text
    assert "private customer detail" not in caplog.text


def test_database_session_setup_failure_is_not_memory_success(client, monkeypatch):
    async def failing_session():
        raise RuntimeError("private connection detail")
        yield  # pragma: no cover — async generator contract

    monkeypatch.setattr(customers, "get_db_session", failing_session)
    client.app.dependency_overrides.clear()
    response = client.get("/api/customers")
    assert response.status_code == 503
    assert response.json()["detail"] == "Customer database unavailable"


def test_dependency_does_not_yield_again_when_route_raises(client, monkeypatch):
    async def session():
        yield None

    monkeypatch.setattr(customers, "get_db_session", session)
    client.app.dependency_overrides.clear()
    response = client.get("/api/customers/no-such-customer")
    assert response.status_code == 404


def test_background_broadcast_failure_is_logged_without_customer_data(monkeypatch, caplog):
    class FailedBroadcaster:
        async def broadcast_customer_updated(self, payload):
            raise RuntimeError("private customer detail")

    monkeypatch.setattr(customers, "broadcaster", FailedBroadcaster())

    async def run():
        customers._schedule_customer_broadcast("updated", {"email": "private@example.com"})
        await asyncio.sleep(0)

    asyncio.run(run())
    assert "Customer broadcast updated failed (RuntimeError)" in caplog.text
    assert "private@example.com" not in caplog.text
    assert "private customer detail" not in caplog.text


def test_empty_database_does_not_serve_seed_customers(client):
    from unittest.mock import MagicMock

    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute.return_value = result
    client.app.dependency_overrides[customers._db_session_or_none] = lambda: session
    response = client.get("/api/customers")
    assert response.status_code == 200
    assert response.json()["customers"] == []


@pytest.mark.parametrize("method", ["GET", "PATCH", "DELETE"])
def test_missing_database_record_does_not_use_memory(client, method):
    from unittest.mock import MagicMock

    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result
    client.app.dependency_overrides[customers._db_session_or_none] = lambda: session
    before = copy.deepcopy(customers._MEMORY_CUSTOMERS)
    customer_id = before[0]["id"]
    response = client.request(method, f"/api/customers/{customer_id}", json={"tier": "Pro"} if method == "PATCH" else None)
    assert response.status_code == 404
    assert customers._MEMORY_CUSTOMERS == before


def test_missing_database_dependency_is_unavailable_not_mock_success(client, monkeypatch):
    monkeypatch.setattr(customers, "get_db_session", None)
    client.app.dependency_overrides.clear()
    response = client.get("/api/customers")
    assert response.status_code == 503
    assert response.json()["detail"] == "Customer database unavailable"


def test_duplicate_database_customer_remains_bad_request(client):
    from unittest.mock import MagicMock

    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = object()
    session.execute.return_value = result
    client.app.dependency_overrides[customers._db_session_or_none] = lambda: session
    response = client.post("/api/customers", json={"name": "Test", "email": "exists@example.com"})
    assert response.status_code == 400
    session.commit.assert_not_awaited()


def test_successful_database_list_is_returned(client):
    from unittest.mock import MagicMock

    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [MagicMock(to_dict=lambda: {"id": "real"})]
    session.execute.return_value = result
    client.app.dependency_overrides[customers._db_session_or_none] = lambda: session
    response = client.get("/api/customers")
    assert response.status_code == 200
    assert response.json()["customers"] == [{"id": "real"}]
