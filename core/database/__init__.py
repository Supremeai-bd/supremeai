"""core.database package initialization."""

from __future__ import annotations

import importlib
from typing import Any


def __getattr__(name: str) -> Any:
    mod = importlib.import_module("core.database.session")
    return getattr(mod, name)


__all__ = ["AsyncSessionLocal", "engine", "get_db_session_context"]
