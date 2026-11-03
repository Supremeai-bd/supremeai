"""Backwards-compatibility shim — FastAPI app assembly.

The implementation moved to ``core.app_builder.create_app``. This shim builds
the singleton so all existing ``from core.app import app`` call sites keep
working.
"""

from __future__ import annotations

import os
import sys

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)
_core_dir = os.path.join(_backend_dir, "core")
if _core_dir not in sys.path:
    sys.path.insert(0, _core_dir)

try:
    from monitoring import init_observability

    init_observability()
except Exception:
    pass

try:
    from core.app_builder import create_app

    app = create_app()
except Exception as _exc:  # pragma: no cover - defensive
    import logging

    logging.getLogger(__name__).exception("app build failed: %s", _exc)
    app = None

try:
    from core.memory_manager import MemoryAwareMiddleware

    if app is not None:
        app.add_middleware(MemoryAwareMiddleware)
except Exception:
    pass

__all__ = ["app"]
