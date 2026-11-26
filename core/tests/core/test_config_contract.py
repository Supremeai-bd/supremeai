"""specs/001 T010 — configuration contract tests (core lane).

লক করে:
  1. deployment_fallback_defaults কোনো hardcoded deployment hostname রাখে না;
  2. health_aggregation খালি URL-এ not_configured দেয় (localhost probe নয়);
  3. canonical env var আগে, খালি string fallback নয়;
  4. CORS resolver wildcard ছাড়ে না।
"""

from __future__ import annotations


class TestFallbackDefaultsContract:
    def test_no_hardcoded_deployment_hostname(self):
        import inspect

        from core import deployment_fallback_defaults as dfd

        src = inspect.getsource(dfd)
        # Doctrine: no https://<host> literals in the fallback module.
        assert "https://" not in src
        assert "http://localhost" not in src

    def test_backend_default_follows_env_chain(self, monkeypatch):
        import importlib

        from core import deployment_fallback_defaults as dfd

        monkeypatch.setenv("SUPREMEAI_USER_BACKEND_URL", "https://env-a.example")
        monkeypatch.setenv("USER_BACKEND_URL", "https://env-b.example")
        # Module-level constant — re-exec to pick up env.
        reloaded = importlib.reload(dfd)
        assert reloaded.BACKEND_URL_DEFAULT == "https://env-a.example"


class TestHealthAggregationNotConfigured:
    def test_empty_url_is_not_configured_not_unhealthy(self):
        import asyncio

        from api.routes.health_aggregation import (
            calculate_overall_status,
            check_single_service,
        )

        health = asyncio.run(
            check_single_service(
                {
                    "name": "scraper_service",
                    "display_name": "Scraper",
                    "url": "",
                    "critical": False,
                    "timeout": 1.0,
                }
            )
        )
        assert health.status == "not_configured"
        assert health.url == ""

        overall, counts = calculate_overall_status([health])
        assert counts["not_configured"] == 1
        # Optional unconfigured must not flip overall to unhealthy.
        assert overall in ("healthy", "degraded")

    def test_critical_not_configured_is_degraded_not_unhealthy(self):
        from datetime import datetime

        from api.routes.health_aggregation import (
            ServiceHealth,
            calculate_overall_status,
        )

        svc = ServiceHealth(
            name="main_backend",
            display_name="Main Backend",
            status="not_configured",
            last_check=datetime.utcnow(),
            url="",
            critical=True,
        )
        overall, _ = calculate_overall_status([svc])
        assert overall == "degraded"

    def test_registry_has_no_localhost_fallback(self):
        from api.routes.health_aggregation import SERVICE_REGISTRY

        for entry in SERVICE_REGISTRY:
            url = entry.get("url") or ""
            assert "localhost" not in url, entry["name"]


class TestCorsResolverContract:
    def test_resolver_drops_wildcard(self):
        from middleware.cors_policy import resolve_user_cors_origins

        resolved = resolve_user_cors_origins(
            ["*", "http://localhost:3000", "https://app.example.com"]
        )
        assert "*" not in resolved
        assert "https://app.example.com" in resolved
