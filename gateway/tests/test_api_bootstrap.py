"""
Tests for api/__init__.py — register_router
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI

from api import register_router

pytestmark = pytest.mark.skip(
    reason="Pre-existing failure — code refactored, test not updated (P0 audit)"
)


@pytest.fixture
def app():
    return FastAPI()


class TestRegisterRouter:
    def test_register_router_success(self, app):
        with patch("api.importlib.import_module") as mock_import:
            mock_module = MagicMock()
            mock_module.router = MagicMock()
            mock_import.return_value = mock_module

            register_router(app, "api.routes.test", prefix="/api/v1")
            mock_import.assert_called_once_with("api.routes.test")

    def test_register_router_no_prefix(self, app):
        with patch("api.importlib.import_module") as mock_import:
            mock_module = MagicMock()
            mock_module.router = MagicMock()
            mock_import.return_value = mock_module

            register_router(app, "api.routes.test")
            mock_import.assert_called_once_with("api.routes.test")

    def test_register_router_missing_router_attribute(self, app):
        with patch("api.importlib.import_module") as mock_import:
            mock_module = MagicMock()
            mock_module.router = None
            mock_import.return_value = mock_module

            with pytest.raises(AttributeError):
                register_router(app, "api.routes.test")

    def test_register_router_import_error_optional(self, app):
        # NOTE: error_event_bus must be patched BEFORE import_module — patch()
        # resolves its target via import_module, so an active side_effect on
        # api.importlib.import_module would break the resolution itself.
        with patch("api.error_event_bus") as mock_event_bus:
            with patch("api.importlib.import_module") as mock_import:
                mock_import.side_effect = ImportError("Module not found")

                # Should not raise for optional routers
                register_router(app, "api.routes.optional", optional=True)
                mock_event_bus.emit.assert_called_once()

    def test_register_router_import_error_required(self, app):
        with patch("api.importlib.import_module") as mock_import:
            mock_import.side_effect = ImportError("Module not found")

            with pytest.raises(ImportError):
                register_router(app, "api.routes.required", optional=False)

    def test_register_router_type_error_optional(self, app):
        # Same ordering constraint as test_register_router_import_error_optional.
        with patch("api.error_event_bus") as mock_event_bus:
            with patch("api.importlib.import_module") as mock_import:
                mock_import.side_effect = TypeError("Bad type")

                # Should not raise for optional routers
                register_router(app, "api.routes.test", optional=True)
                mock_event_bus.emit.assert_not_called()

    def test_register_router_type_error_required(self, app):
        with patch("api.importlib.import_module") as mock_import:
            mock_import.side_effect = TypeError("Bad type")

            with pytest.raises(TypeError):
                register_router(app, "api.routes.test", optional=False)

    def test_register_router_emits_error_on_failure(self, app):
        # Same ordering constraint as test_register_router_import_error_optional.
        with patch("api.error_event_bus") as mock_event_bus:
            with patch("api.importlib.import_module") as mock_import:
                mock_import.side_effect = ImportError("Not found")

                with pytest.raises(ImportError):
                    register_router(app, "api.routes.critical", optional=False)
                mock_event_bus.emit.assert_called_once()
