"""
Health Endpoint Tests — System Monitoring Validation
v4.0: Verifies /health endpoints work correctly
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


class TestHealthEndpoint:
    """Test /health endpoint responses."""

    @pytest.mark.unit
    async def test_health_returns_200_when_healthy(self, client):
        """Health endpoint returns 200 when all checks pass."""
        from core.health_routes import HealthCheck, HealthResult, HealthStatus, _checks

        dummy_check = HealthCheck(name="database", check_fn=lambda: True, critical=True)
        _checks.append(dummy_check)
        try:
            # #468 TTL cache: a previous test's healthy outcome may still be
            # inside the 10s window — reset so the simulated failure runs the
            # real check path (failures are NEVER cached, see contract test).
            from core.health_routes import reset_health_cache

            reset_health_cache()
            with patch("core.health_routes._run_check") as mock_check:
                mock_result = HealthResult(
                    name="database",
                    status=HealthStatus.HEALTHY,
                    latency_ms=5.0,
                )
                mock_check.return_value = mock_result

                response = await client.get("/health")

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "healthy"
                assert "uptime_seconds" in data
                assert "checks" in data
        finally:
            _checks.remove(dummy_check)

    # #468 TTL cache: the module-level health cache persists across tests
    # (a previous test's HEALTHY outcome may legitimately sit inside its 10s
    # window). Reset around every test in this class so failure-simulation
    # tests observe the real check path — and lock the safety contract that
    # unhealthy outcomes are never cached.
    @pytest.fixture(autouse=True)
    def _reset_health_ttl_cache(self):
        from core.health_routes import reset_health_cache

        reset_health_cache()
        yield
        reset_health_cache()

    @pytest.mark.unit
    async def test_health_returns_503_when_unhealthy(self, client):
        """Health endpoint returns 503 when critical check fails."""
        from core.health_routes import HealthCheck, HealthResult, HealthStatus, _checks

        # বাংলা মন্তব্য: httpx ASGITransport টেস্ট ক্লায়েন্ট lifespan startup
        # ট্রিগার করে না, তাই _checks registry খালি থাকে এবং mock করা
        # _run_check কখনো কল হয় না (খালি লিস্টের ওপর কম্প্রিহেনশন)। এখানে
        # ম্যানুয়ালি একটা dummy check রেজিস্টার করে সেটা নিশ্চিত করা হচ্ছে।
        dummy_check = HealthCheck(name="database", check_fn=lambda: True, critical=True)
        _checks.append(dummy_check)
        try:
            # বাংলা মন্তব্য (#468 TTL cache): আগের টেস্টের healthy ফল এখনো ১০s
            # TTL-উইন্ডোতে থাকতে পারে — রিসেট ছাড়া এই টেস্ট ক্যাশ-হিট (200,
            # cache_hit=true) পাবে এবং সত্য 503-পথ কখনোই চলবে না। 200-টেস্টের
            # মতোই টেস্ট-শুরুতেই রিসেট — কেবল finally-তে নয়।
            from core.health_routes import reset_health_cache

            reset_health_cache()
            with patch("core.health_routes._run_check") as mock_check:
                mock_result = HealthResult(
                    name="database",
                    status=HealthStatus.UNHEALTHY,
                    latency_ms=5000.0,
                    error="Connection refused",
                    critical=True,
                )
                mock_check.return_value = mock_result

                response = await client.get("/health")

                assert response.status_code == 503
                data = response.json()
                assert data["status"] == "unhealthy"
                # Contract lock (#468): the unhealthy outcome must NOT have
                # been cached — incident detection is never served stale.
                assert data["cache_hit"] is False
        finally:
            _checks.remove(dummy_check)
            from core.health_routes import reset_health_cache as _rh

            _rh()

    @pytest.mark.unit
    async def test_readiness_probe(self, client):
        """Readiness probe checks critical services only."""
        response = await client.get("/health/ready")

        assert response.status_code in (200, 503)
        data = response.json()
        assert "status" in data
        assert data["status"] in ("ready", "not_ready")

    @pytest.mark.unit
    async def test_liveness_probe(self, client):
        """Liveness probe confirms process is alive."""
        response = await client.get("/health/live")

        assert response.status_code == 200
        data = response.json()
        assert data["alive"] is True
        assert "timestamp" in data

    @pytest.mark.unit
    async def test_root_endpoint_includes_health_link(self, client):
        """Root endpoint should include health check URL."""
        response = await client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "health_check" in data
        assert data["health_check"] == "/health"


class TestConfigPublicEndpoint:
    """Test public configuration endpoint."""

    @pytest.mark.unit
    async def test_config_public_accessible_without_auth(self, client):
        """Public config should be accessible without auth."""
        response = await client.get("/api/config/public")

        assert response.status_code == 200
        data = response.json()
        assert "features" in data
        assert "version" in data

    @pytest.mark.unit
    async def test_config_public_no_secrets(self, client):
        """Public config must not expose secrets."""
        response = await client.get("/api/config/public")

        assert response.status_code == 200
        data = response.json()

        # Ensure no sensitive keys leaked
        sensitive_keys = ["jwt_secret", "api_key", "password", "database_url"]
        for key in sensitive_keys:
            assert key not in data, f"Sensitive key '{key}' exposed in public config"
