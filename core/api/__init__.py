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
    mounted = getattr(app.state, "mounted_routers", None)
    if mounted is None:
        mounted = app.state.mounted_routers = {}
    mount_key = (id(router), prefix)
    mount_dependencies = tuple(dependencies or ())
    if mount_key in mounted:
        if mounted[mount_key] != mount_dependencies:
            raise ValueError(f"Conflicting authentication dependencies for router {path}")
        return
    kwargs = {}
    if prefix:
        kwargs["prefix"] = prefix
    if dependencies:
        kwargs["dependencies"] = dependencies
    try:
        app.include_router(router, **kwargs)
        mounted[mount_key] = mount_dependencies
    except Exception as exc:  # noqa: BLE001
        if optional:
            _record(path, exc)
            logging.getLogger(__name__).warning("Router mount failed for %s: %s", path, exc)
            return
        raise


__all__ = ["register_router", "_registration_report"]
