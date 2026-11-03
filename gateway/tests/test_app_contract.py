from fastapi.testclient import TestClient

from core.app import app

client = TestClient(app)


def test_root_endpoint_exposes_service_metadata():
    response = client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "service" in data
    assert data["health_check"] == "/health"


def test_openapi_document_is_available():
    response = client.get("/api/v1/openapi.json")

    assert response.status_code == 200
    document = response.json()
    assert document["info"]["title"]
    assert "/" in document["paths"]
    assert "/health" in document["paths"]


def test_docs_route_is_available():
    response = client.get("/docs")

    assert response.status_code == 200
    assert "swagger" in response.text.lower()


def test_redoc_route_is_available():
    response = client.get("/redoc")

    assert response.status_code == 200
    assert "redoc" in response.text.lower()


def test_health_aggregated_route():
    response = client.get("/health/aggregated")

    assert response.status_code in (200, 503)
