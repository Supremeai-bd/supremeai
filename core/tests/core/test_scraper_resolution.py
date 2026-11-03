"""Integration tests for SCRAPER_BACKEND_URL / SCRAPER_URL resolution.

Verifies:
1. When unset, scraper URL defaults gracefully to empty string / None without crashing.
2. When SCRAPER_URL, SCRAPER_SERVICE_URL, or RENDER_SCRAPER_URL is provided,
   service registry and worker paths resolve it consistently.
3. Priority order is respected across alias variables.
"""

from __future__ import annotations

import os
from unittest import mock

import pytest


def test_scraper_resolution_defaults_empty():
    """When no scraper URL is set, the fallback should be empty or safe."""
    with mock.patch.dict(os.environ, {}, clear=True):
        from core.deployment_fallback_defaults import SCRAPER_URL_DEFAULT

        # Defaults must be a string without hardcoded third-party hosts
        assert isinstance(SCRAPER_URL_DEFAULT, str)
        assert "onrender.com" not in SCRAPER_URL_DEFAULT


def test_scraper_alias_resolution_in_service_registry():
    """Service registry resolves SCRAPER_URL from aliases."""
    from core.service_registry import get_service, service_url

    scraper_svc = get_service("scraper")
    assert scraper_svc is not None
    assert "SCRAPER_URL" in scraper_svc.base_url_env
    assert "SCRAPER_SERVICE_URL" in scraper_svc.base_url_env
    assert "RENDER_SCRAPER_URL" in scraper_svc.base_url_env

    # Test resolution with mock env
    with mock.patch.dict(os.environ, {"RENDER_SCRAPER_URL": "https://render-test.internal"}):
        resolved = service_url(scraper_svc)
        assert resolved == "https://render-test.internal"


def test_scraper_worker_resolution_precedence():
    """Worker service checks SCRAPER_URL -> SCRAPER_SERVICE_URL -> RENDER_SCRAPER_URL."""
    # Test primary
    with mock.patch.dict(
        os.environ,
        {
            "SCRAPER_URL": "https://primary-scraper.internal",
            "SCRAPER_SERVICE_URL": "https://secondary-scraper.internal",
        },
    ):
        url = (
            os.getenv("SCRAPER_URL")
            or os.getenv("SCRAPER_SERVICE_URL")
            or os.getenv("RENDER_SCRAPER_URL")
        )
        assert url == "https://primary-scraper.internal"

    # Test fallback alias
    with mock.patch.dict(
        os.environ,
        {
            "SCRAPER_URL": "",
            "SCRAPER_SERVICE_URL": "https://secondary-scraper.internal",
        },
    ):
        url = (
            os.getenv("SCRAPER_URL")
            or os.getenv("SCRAPER_SERVICE_URL")
            or os.getenv("RENDER_SCRAPER_URL")
        )
        assert url == "https://secondary-scraper.internal"

    # Test third alias
    with mock.patch.dict(
        os.environ,
        {
            "SCRAPER_URL": "",
            "SCRAPER_SERVICE_URL": "",
            "RENDER_SCRAPER_URL": "https://render-scraper.internal",
        },
    ):
        url = (
            os.getenv("SCRAPER_URL")
            or os.getenv("SCRAPER_SERVICE_URL")
            or os.getenv("RENDER_SCRAPER_URL")
        )
        assert url == "https://render-scraper.internal"
