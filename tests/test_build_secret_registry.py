"""`build_secret_registry.is_fake` decides what counts as a real secret.

If a placeholder is treated as real, the registry claims a secret exists that
nobody can rotate; if a real one is treated as fake, it drops out of the
registry and stops being monitored. Both directions are pinned.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))

import build_secret_registry as registry  # noqa: E402


def test_placeholders_are_fake():
    for key in ("TEST_TOKEN", "MOCK_KEY", "PLACEHOLDER_VALUE", "REDACTED_SECRET",
                "TOTALLY_UNKNOWN_KEY", "VAULT_TOKEN", "MY_SECRET"):
        assert registry.is_fake(key), key


def test_real_names_are_not_fake():
    for key in ("GITHUB_TOKEN", "RENDER_API_TOKEN", "SUPABASE_SERVICE_ROLE_KEY",
                "MCP_TOWER_AUTH_TOKEN"):
        assert not registry.is_fake(key), key


def test_matching_is_prefix_only():
    # A real name that merely CONTAINS a placeholder marker stays real.
    assert not registry.is_fake("GITHUB_TOKEN_ROTATION")
