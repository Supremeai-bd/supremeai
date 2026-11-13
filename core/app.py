"""FastAPI ASGI app instance for SupremeAI Core."""

from __future__ import annotations

from core.app_builder import create_app

app = create_app()

__all__ = ["app"]
