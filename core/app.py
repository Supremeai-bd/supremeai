"""FastAPI ASGI app instance for SupremeAI Core."""

from __future__ import annotations

import sys
import os

_core_dir = os.path.dirname(os.path.abspath(__file__))
if _core_dir not in sys.path:
    sys.path.insert(0, _core_dir)

from core.app_builder import create_app

app = create_app()

__all__ = ["app"]
