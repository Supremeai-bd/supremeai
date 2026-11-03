"""core.api package — register_router helper."""

from __future__ import annotations

import importlib
import logging
from typing import Any, List

from fastapi import FastAPI

_registration_report: List[dict] = []


def _record(module: str, exc: Exception) -> None:
    _registration_report.append(
        {"module": module, "error_type": type(exc).__name__, "message": str(exc)}
    )


def register_router(
    app: FastAPI,
    path: str,
    prefix: str = "",
    optional: bool = True,
    dependencies: Any = None,
) -> None:
    global _registration_report
    try:
        mod = importlib.import_module(path)
    except Exception as exc:  # noqa: BLE001
        if optional:
            _record(path, exc)
            logging.getLogger(__name__).warning("Router import failed for %s: %s", path, exc)
            return
        raise
    router = getattr(mod, "router", None)
    if router is None:
        exc = AttributeError(f"{path} has no 'router'")
        if optional:
            _record(path, exc)
            logging.getLogger(__name__).warning("Router missing for %s: %s", path, exc)
            return
        raise exc
    kwargs = {}
    if prefix:
        kwargs["prefix"] = prefix
    if dependencies:
        kwargs["dependencies"] = dependencies
    try:
        app.include_router(router, **kwargs)
    except Exception as exc:  # noqa: BLE001
        if optional:
            _record(path, exc)
            logging.getLogger(__name__).warning("Router mount failed for %s: %s", path, exc)
            return
        raise


__all__ = ["register_router", "_registration_report"]
