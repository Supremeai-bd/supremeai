"""Safe re-exports of API routers from core.api.routes (SSOT #751)."""

from __future__ import annotations

from core.api.routes import *
from core.api.routes import _ROUTER_DEFINITIONS, _safe_imports  # noqa: F401

