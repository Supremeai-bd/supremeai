#!/usr/bin/env python3
"""The Studio origin the gateway allows must include the one it actually serves.

The bug this pins: `_default_cors` listed the Vercel and pages.dev Studio hosts
but not the registry's canonical `frontend` origin. The deployed frontend's real
origin was therefore the single origin missing from the allowlist — every
cross-origin request from it failed preflight, while retired hosts stayed
allowed.

These tests read the registry, never a literal, so a future host migration moves
the expectation with it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))


def _registry() -> dict:
    with open(REPO_ROOT / "config" / "service_registry.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _canonical_frontend_origin() -> str:
    """The frontend origin the registry declares (via repo_paths, env-first)."""
    from repo_paths import service_endpoint

    return (service_endpoint("frontend", with_path=False) or "").rstrip("/")


def test_registry_declares_a_frontend_origin():
    """If this fails, the CORS test below would pass vacuously."""
    origin = _canonical_frontend_origin()
    assert origin.startswith("https://"), f"no usable frontend origin: {origin!r}"
    spec = _registry()["services"]["frontend"]
    assert spec.get("production_url"), "frontend has no production_url in the registry"


def test_cors_defaults_include_the_registry_frontend_origin():
    """The real deployed origin must be allowed. This is the regression."""
    app_src = (REPO_ROOT / "gateway" / "service" / "app.py").read_text(encoding="utf-8")
    origin = _canonical_frontend_origin()

    # The origin must arrive via the registry helper, not by being typed in.
    assert '_registry_origin("frontend")' in app_src, (
        "the CORS allowlist no longer consults the registry for the frontend origin"
    )
    # And it must not be re-literalized next to it, which would drift again.
    assert f'"{origin}"' not in app_src, (
        f"{origin} is hardcoded in app.py; it belongs to config/service_registry.yaml"
    )


def test_registry_origin_helper_returns_no_health_path():
    """An Origin header must match exactly; a /health suffix would never match."""
    import importlib.util

    # Exercise the helper's contract without importing the whole gateway
    # (which needs fastapi). Same call the module makes.
    from repo_paths import service_endpoint

    origin = service_endpoint("frontend", with_path=False)
    assert origin
    for suffix in ("/health", "/healthz", "/health/live", "/ready"):
        assert not origin.endswith(suffix), f"origin carries a probe path: {origin}"


def test_core_cors_floor_includes_the_registry_frontend_origin():
    """Same bug, second file: core's CORS floor listed five Studio hosts and
    omitted the canonical one."""
    sys.path.insert(0, str(REPO_ROOT))
    from core.middleware.cors_policy import DEFAULT_USER_ALLOWED_ORIGINS

    origin = _canonical_frontend_origin()
    assert origin in DEFAULT_USER_ALLOWED_ORIGINS, (
        f"{origin} (registry canonical) is not in the user CORS floor: "
        f"{DEFAULT_USER_ALLOWED_ORIGINS}"
    )


def test_core_cors_floor_keeps_its_existing_origins():
    """Adding the canonical origin must not have evicted a working one."""
    sys.path.insert(0, str(REPO_ROOT))
    from core.middleware.cors_policy import DEFAULT_USER_ALLOWED_ORIGINS

    for kept in (
        "https://supremeai-a.web.app",
        "https://supremeai-studio.pages.dev",
        "https://supremeai-studio.paykaribazaronline.workers.dev",
    ):
        assert kept in DEFAULT_USER_ALLOWED_ORIGINS, f"{kept} was dropped from the floor"


def test_core_cors_floor_has_no_duplicates_or_empties():
    sys.path.insert(0, str(REPO_ROOT))
    from core.middleware.cors_policy import DEFAULT_USER_ALLOWED_ORIGINS

    assert len(DEFAULT_USER_ALLOWED_ORIGINS) == len(set(DEFAULT_USER_ALLOWED_ORIGINS))
    assert all(o and o.startswith("http") for o in DEFAULT_USER_ALLOWED_ORIGINS)


def test_config_fields_floor_is_not_a_hand_copy():
    """config_fields used to hand-list a subset while a comment claimed it was
    'kept in sync with cors_policy.py'. It had drifted by three origins. The
    Field must now derive from the policy module, so drift is impossible."""
    sys.path.insert(0, str(REPO_ROOT))
    from core.config_fields import _DEFAULT_USER_CORS_FLOOR
    from core.middleware.cors_policy import DEFAULT_USER_ALLOWED_ORIGINS

    assert list(_DEFAULT_USER_CORS_FLOOR) == list(DEFAULT_USER_ALLOWED_ORIGINS), (
        "config_fields and cors_policy disagree on the user-origin floor"
    )

    src = (REPO_ROOT / "core" / "config_fields.py").read_text(encoding="utf-8")
    assert "default=list(_DEFAULT_USER_CORS_FLOOR)" in src, (
        "user_cors_origins no longer derives its default from the policy module"
    )


def test_brain_origins_derive_from_the_shared_floor():
    """The brain's default was a comma-joined literal: it could not be extended by
    env, and it lacked the canonical Studio origin. It now composes from
    cors_policy like the gateway does."""
    src = (REPO_ROOT / "core" / "services" / "brain" / "main.py").read_text(encoding="utf-8")

    assert "DEFAULT_USER_ALLOWED_ORIGINS" in src, (
        "brain/main.py no longer derives its CORS floor from cors_policy"
    )
    # The old form: a single literal string holding several comma-joined origins.
    assert "supremeai-studio.vercel.app,http" not in src, (
        "the comma-joined origin literal is back in brain/main.py"
    )


def test_brain_floor_resolves_to_include_the_canonical_origin():
    """Execute just the origin-resolution stanza (booting FastAPI is not needed)."""
    src = (REPO_ROOT / "core" / "services" / "brain" / "main.py").read_text(encoding="utf-8")
    start = src.index("_DEV_ORIGINS")
    end = src.index("app.add_middleware")
    sys.path.insert(0, str(REPO_ROOT))
    from core.middleware.cors_policy import DEFAULT_USER_ALLOWED_ORIGINS

    ns = {"os": __import__("os"), "_BRAIN_ORIGIN_FLOOR": DEFAULT_USER_ALLOWED_ORIGINS}
    exec(src[start:end], ns)  # noqa: S102 - stanza has no imports of its own

    resolved = ns["ALLOWED_ORIGINS"]
    assert _canonical_frontend_origin() in resolved
    assert "http://localhost:5173" in resolved, "dev origin dropped"


def test_localhost_origins_are_still_allowed():
    """The fix must not drop dev origins — that would break local frontend work."""
    app_src = (REPO_ROOT / "gateway" / "service" / "app.py").read_text(encoding="utf-8")
    for dev in ("http://localhost:5173", "http://localhost:3000"):
        assert dev in app_src, f"dev origin {dev} vanished from the CORS defaults"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
