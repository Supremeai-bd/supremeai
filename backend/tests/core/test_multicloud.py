import pytest
from fastapi.testclient import TestClient

from brain.parallel_cloud_router import ParallelCloudRouter
from core.app import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _hermetic_multicloud(monkeypatch):
    """#3685 — DNS-নির্ভর flaky pass/fail নির্মূল।

    বাংলা: ParallelCloudRouter.__init__ (এবং routing-পথ) আসল network I/O
    করে — provider HTTP probes + redis://mocked-redis-url-এ Redis write/read
    (conftest-ডিফল্ট)। DNS fast-fail হলে error caught→logged→টেস্ট পাস;
    DNS hang করলে socket.getaddrinfo ব্লক → pytest-timeout → FAIL।

    নিরাময় (টেস্ট-লজিক অপরিবর্তিত):
    ১. redis.from_url → None = "unconfigured" পথ — ঠিক যেমন আসল
       deployment-এ redis না থাকলে আচরণ করে (সব guard-চেক স্কিপ)।
    ২. _health_check_all → no-op — health সাইড-এফেক্ট কোনো assertion-এ
       অবদান রাখে না; বরং empty-URL পথে _set_status-এর Redis write-ই
       ডাকত।
    """
    monkeypatch.setattr("redis.from_url", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        ParallelCloudRouter, "_health_check_all", lambda self, force=False: None
    )


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
    for _name, config in router.PROVIDERS.items():
        config["status"] = "active"
        config["url"] = "http://127.0.0.1:8000"  # is_local()
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
    # Force the router to bypass any mock Redis clients and use the local dict
    router.redis_client = None

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
    assert response.status_code in (200, 404)


def test_cloud_distribution_endpoint():
    import jwt

    from core.config import settings

    token = jwt.encode({"role": "admin"}, settings.jwt_secret, algorithm="HS256")
    response = client.get("/admin/cloud-distribution", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert "distribution" in data
    assert "strategy" in data
    assert data["strategy"] == "parallel_active_active"
