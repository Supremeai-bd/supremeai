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

logger = logging.getLogger("supremeai.gateway")

def _registry_url(service_id: str) -> str:
    """Health URL for a service, from the registry (env first), or "".

    An empty string means "not configured", which the caller already renders as
    "unknown" rather than probing a meaningless localhost.
    """
    try:
        from repo_paths import service_endpoint  # scripts/ci on sys.path in tooling
    except ImportError:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "ci"))
            from repo_paths import service_endpoint
        except Exception:
            return ""
    try:
        return service_endpoint(service_id) or ""
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
    try:
        from repo_paths import service_endpoint  # scripts/ci on sys.path in tooling
    except ImportError:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "ci"))
            from repo_paths import service_endpoint
        except Exception:
            return ""
    try:
        return (service_endpoint(service_id, with_path=False) or "").rstrip("/")
    except Exception:  # pragma: no cover - defensive
        return ""

