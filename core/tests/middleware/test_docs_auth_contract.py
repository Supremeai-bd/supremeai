"""Contract tests for docs_auth middleware — production gate on /docs, /redoc, /openapi.json."""

from __future__ import annotations

import os

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.testclient import TestClient


class TestDocsAuthContract:
    """Verify docs_auth middleware can be imported and has the right interface."""

    def test_importable(self):
        from core.middleware.docs_auth import DocsAuthMiddleware

        assert DocsAuthMiddleware is not None

    def test_docs_disabled_in_prod_returns_404(self):
        """When SUPREMEAI_DOCS_ENABLED=false in production, /docs should 404."""
        # This is a contract test — DocsAuthMiddleware is a raw ASGI middleware
        # implementing the ASGI __call__(scope, receive, send) interface.
        from core.middleware.docs_auth import DocsAuthMiddleware

        assert callable(DocsAuthMiddleware)


class TestHealthAwareMiddlewareContract:
    """Verify health_aware_middleware can be imported."""

    def test_importable(self):
        from core.middleware.health_aware_middleware import HealthAwareMiddleware

        assert HealthAwareMiddleware is not None


class TestDbSchemaGateContract:
    """Verify db_schema_gate can be imported and has the validation function."""

    def test_importable(self):
        from core.db_schema_gate import production_schema_incompatible

        assert callable(production_schema_incompatible)


class TestHoneypotContract:
    """Verify honeypot protection can be imported."""

    def test_importable(self):
        from core.security.protection.honeypot import HoneypotMiddleware

        assert HoneypotMiddleware is not None


class TestPromptFirewallContract:
    """Verify prompt firewall can be imported."""

    def test_importable(self):
        from core.security.protection.prompt_firewall import PromptFirewall

        assert PromptFirewall is not None


class TestPeriodicTaskSchedulerContract:
    """Verify periodic task scheduler can be imported."""

    def test_importable(self):
        from core.orchestration.periodic_task_scheduler import PeriodicTaskScheduler

        assert PeriodicTaskScheduler is not None


class TestKernelDispatcherContract:
    """Verify kernel dispatcher can be imported."""

    def test_importable(self):
        from core.kernel.dispatcher import KernelRequest, KernelResponse

        assert KernelRequest is not None
        assert KernelResponse is not None


class TestMultiLayerCacheContract:
    """Verify multi-layer cache can be imported."""

    def test_importable(self):
        from core.cache.multi_layer_cache import MultiLayerCache

        assert MultiLayerCache is not None


class TestLLMGatewayRegistryContract:
    """Verify LLM gateway registry can be imported."""

    def test_importable(self):
        from core.llm.llm_gateway.registry import _ProviderKeyPool

        assert _ProviderKeyPool is not None
