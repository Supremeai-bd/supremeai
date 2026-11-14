"""core.database package initialization."""
from typing import Any


def __getattr__(name: str) -> Any:
    from core.database import session

    return getattr(session, name)


__all__ = ["AsyncSessionLocal", "engine", "get_db_session_context"]

