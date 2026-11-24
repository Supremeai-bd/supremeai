"""Service-registry lookup helpers for the gateway.

Shared by ``gateway.service.app`` (CORS origin floor) and
``gateway.service.auth_verification`` (Studio-host cost guard). Extracted from
``app.py`` on 2026-11-24 (God-file split) to avoid a circular import between
the two modules.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger("supremeai.gateway")


def _get_service_endpoint() -> Optional[Callable[..., Any]]:
    # বাংলা মন্তব্য: DRY নীতি পালন — রিপো পাথ ইমপোর্ট একবার একক হেল্পারে সংজ্ঞায়িত করা হলো যাতে jscpd ডুপ্লিকেশন না ধরে
    try:
        from repo_paths import service_endpoint  # scripts/ci on sys.path in tooling
        return service_endpoint
    except ImportError:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "ci"))
            from repo_paths import service_endpoint
            return service_endpoint
        except Exception:
            return None


def _registry_url(service_id: str) -> str:
    """Health URL for a service, from the registry (env first), or "".

    An empty string means "not configured", which the caller already renders as
    "unknown" rather than probing a meaningless localhost.
    """
    fn = _get_service_endpoint()
    if not fn:
        return ""
    try:
        return fn(service_id) or ""
    except Exception as exc:  # pragma: no cover - defensive
        # Never swallow silently: an empty URL renders as "unknown", and a
        # warning is what tells you the registry drifted rather than the
        # service being down.
        logger.warning("service registry lookup failed for %r: %s", service_id, exc)
        return ""


def _registry_origin(service_id: str) -> str:
    """Scheme+host only, for use as a CORS origin (never a health URL).

    `_registry_url` appends the health path on purpose — right for a probe,
    wrong for an Origin header, which must match exactly.
    """
    fn = _get_service_endpoint()
    if not fn:
        return ""
    try:
        return (fn(service_id, with_path=False) or "").rstrip("/")
    except Exception:  # pragma: no cover - defensive
        return ""
