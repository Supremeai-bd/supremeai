"""Compatibility shim: re-exports router and endpoints from service.frontend_compat."""
from __future__ import annotations

try:
    from service.frontend_compat import *
    from service.frontend_compat import router
except ImportError:
    from gateway.service.frontend_compat import *
    from gateway.service.frontend_compat import router  # noqa: F401
