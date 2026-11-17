"""SupremeAI core package — import-light public surface (#1347).

This package root intentionally stays thin. The old 16 KB god-init eagerly
imported every subsystem, so ``import core`` paid the cost (and failure
modes) of the whole platform; the self-check helpers that used to live
inline here were extracted to :mod:`core.selfcheck`. The public names
below are resolved lazily via PEP 562 ``__getattr__`` — importing the
package itself pulls in no heavy dependency.

Contract (guarded by tests/test_core_exports.py):
  * every name in ``__all__`` must resolve to a real object;
  * a listed name may only be ``None`` when it is a declared lazy export
    (``_EVOLUTION_LAZY_EXPORTS`` / ``_QA_LAZY_EXPORTS``) whose optional
    heavy dependency is absent;
  * deleted symbols must stay deleted — do not re-add them to ``__all__``.
"""

from __future__ import annotations

import importlib
from typing import Any

# Public name -> defining submodule. Resolved on first attribute access,
# never at package import time.
_LAZY_EXPORTS: dict[str, str] = {
    "AccessibilityComplianceEngine": "core.accessibility.wcag_compliance",
    "ProductionDeploymentSystem": "core.deployment.production_deploy",
    "get_performance_optimizer": "core.optimization.performance_optimizer",
    "logger": "core.monitoring.logging_config",
}

# Lazy exports that are allowed to resolve to None when an optional heavy
# dependency (torch, aiohttp, ...) is not installed. Currently empty: every
# public export resolves to a real object. Add a name here — together with
# a conditional-None branch in __getattr__ — before listing any new
# optional-dependency symbol in __all__.
_EVOLUTION_LAZY_EXPORTS: frozenset[str] = frozenset()
_QA_LAZY_EXPORTS: frozenset[str] = frozenset()

__all__ = sorted(_LAZY_EXPORTS)


def __getattr__(name: str) -> Any:
    module_path = _LAZY_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(importlib.import_module(module_path), name)
    globals()[name] = value  # cache: resolve each export at most once
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
