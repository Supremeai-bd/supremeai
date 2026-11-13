"""Tests for SupremeAI Customer Directory API (both /api/customers and /api/admin/customers)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.customers import router as customers_router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(customers_router)
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
