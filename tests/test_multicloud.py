import pytest
from fastapi.testclient import TestClient
from core.app import app
from brain.parallel_cloud_router import ParallelCloudRouter

client = TestClient(app)

def test_parallel_cloud_router_initialization():
    router = ParallelCloudRouter()
    assert len(router.PROVIDERS) == 3
    assert "gcp_cloud_run" in router.PROVIDERS
    assert "railway" in router.PROVIDERS
    assert "render" in router.PROVIDERS

def test_get_provider_for_request_fallback():
    # Since env URLs are empty by default in tests, it should fallback to GCP or first provider
    router = ParallelCloudRouter()
    provider = router.get_provider_for_request()
    assert provider in ["gcp_cloud_run", "railway", "render"]

def test_router_weight_calculations():
    router = ParallelCloudRouter()
    # Mock status active and valid URLs
    for name, config in router.PROVIDERS.items():
        config["status"] = "active"
        config["url"] = "http://localhost:8000"
        config["latency_ms"] = 100.0
    
    # Should get a valid provider from active ones
    provider = router.get_provider_for_request()
    assert provider in ["gcp_cloud_run", "railway", "render"]

def test_get_distribution_stats():
    router = ParallelCloudRouter()
    stats = router.get_distribution_stats()
    assert "gcp_cloud_run" in stats
    assert "railway" in stats
    assert "render" in stats
    assert "utilization_pct" in stats["gcp_cloud_run"]

def test_rebalance():
    router = ParallelCloudRouter()
    # Mock active status for all providers so normalization distributes weights
    for name in router.PROVIDERS:
        router.PROVIDERS[name]["status"] = "active"
        
    router.PROVIDERS["gcp_cloud_run"]["current_requests"] = 1900000
    router.PROVIDERS["gcp_cloud_run"]["capacity"] = 2000000
    
    original_weight = router.PROVIDERS["gcp_cloud_run"]["weight"]
    router.rebalance()
    # Weight should decrease since utilization is > 80%
    assert router.PROVIDERS["gcp_cloud_run"]["weight"] < original_weight

def test_actuator_health_endpoint():
    response = client.get("/actuator/health")
    assert response.status_code == 200
    assert response.json()["status"] == "UP"

def test_cloud_distribution_endpoint():
    response = client.get("/admin/cloud-distribution")
    assert response.status_code == 200
    data = response.json()
    assert "distribution" in data
    assert "strategy" in data
    assert data["strategy"] == "parallel_active_active"
