"""Stable zero-cost infrastructure boundary.

The implementation remains centralized under ``backend.core.zero_cost_architecture``.
This lazy facade avoids importing optional runtime dependencies during discovery.
"""

from __future__ import annotations

import importlib

_TARGET = "core.zero_cost_architecture.zero_cost_patch_phase1_4"


def __getattr__(name: str):
    module = importlib.import_module(_TARGET)
    try:
        return getattr(module, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__() -> list[str]:
    try:
        return sorted(set(globals()) | set(vars(importlib.import_module(_TARGET))))
    except ImportError:
        return sorted(globals())
