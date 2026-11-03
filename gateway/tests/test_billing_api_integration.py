from unittest.mock import patch

from fastapi.testclient import TestClient

from core.app import app

client = TestClient(app)


# বাংলা মন্তব্য: বিলিং এপিআই-এর আনঅথরাইজড রিকোয়েস্ট ৪০১ রিটার্ন করছে কিনা তা পরীক্ষা করা হচ্ছে।
@patch("core.security.authentication.auth_middleware.is_test_environment", return_value=False)
def test_billing_wallet_unauthorized(mock_is_test):
    response = client.get("/api/billing/wallet")
    assert response.status_code == 401
    assert response.json()["detail"] in {"Unauthorized", "Missing authentication token"}


@patch("core.security.authentication.auth_middleware.is_test_environment", return_value=False)
def test_billing_history_unauthorized(mock_is_test):
    response = client.get("/api/billing/history")
    assert response.status_code == 401
    assert response.json()["detail"] in {"Unauthorized", "Missing authentication token"}


@patch("core.security.authentication.auth_middleware.is_test_environment", return_value=False)
def test_billing_checkout_unauthorized(mock_is_test):
    response = client.post(
        "/api/billing/checkout",
        json={
            "price_id": "test_price",
            "success_url": "http://test",
            "cancel_url": "http://test",
        },
    )
    assert response.status_code == 401
    assert response.json()["detail"] in {"Unauthorized", "Missing authentication token"}
