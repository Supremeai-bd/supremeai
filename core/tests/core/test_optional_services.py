"""Tests for optional service behavior (FR-003, FR-014, Drill 3).

Verifies:
1. When optional services (Redis, Scraper, Ollama) are unset, health endpoints
   distinguish 'not_configured' and do NOT return 503 or mark overall health as degraded.
2. Ollama remains strictly optional: missing OLLAMA_URL does not impede boot or health.
"""

from __future__ import annotations

import os
from unittest import mock

import pytest
from fastapi import Response


@pytest.mark.asyncio
async def test_optional_services_unconfigured_do_not_degrade_health():
    """When REDIS_URL, SCRAPER_URL, OLLAMA_URL are unset, deep health is healthy and not 503."""
    with mock.patch.dict(
        os.environ,
        {"REDIS_URL": "", "SCRAPER_URL": "", "OLLAMA_URL": ""},
        clear=False,
    ):
        with (
            mock.patch("api.routes.health._check_database", return_value="healthy"),
            mock.patch("api.routes.health._check_redis", return_value="not_configured"),
            mock.patch(
                "core.agent_supervisor.agent_supervisor.get_health",
                return_value={"agent1": {"status": "running"}},
            ),
        ):
            from api.routes.health import deep_health_check

            response = Response()
            health_status = await deep_health_check(response)

            assert response.status_code != 503
            assert health_status.status == "healthy"
            assert health_status.services["redis"]["status"] == "not_configured"
            assert health_status.services["scraper"]["status"] == "not_configured"
            assert health_status.services["ollama"]["status"] == "not_configured"


@pytest.mark.asyncio
async def test_ollama_optionality_and_absence():
    """Missing OLLAMA_URL defaults safely and does not raise exceptions."""
    with mock.patch.dict(os.environ, {"OLLAMA_URL": ""}, clear=False):
        from core.integrations.registry import get_integration

        ollama = get_integration("ollama")
        assert ollama is not None
        assert ollama.required_for_core is False
        assert ollama.enabled is False
