"""The merge gate's protected-path classifier (tiny_brain_pr_guard.py).

This is the function that decides whether a PR needs a human: if it silently
stops recognising a protected prefix, PRs touching the gateway, the auth routes
or the constitution start self-merging. The paths below include the ones added
on 2026-11-19 (provider core) — a regression there would be a live-customer
blast radius, so each is pinned by name.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))

import tiny_brain_pr_guard as guard  # noqa: E402


def test_protected_prefixes_require_a_human():
    for path in (
        ".github/workflows/unified-pipeline.yml",
        ".github/constitution/rules.yml",
        ".github/scripts/constitution/gates.py",
        ".github/actions/setup/action.yml",
        "core/security/vault.py",
        "core/services/hitl/queue.py",
        "gateway/middleware/auth.py",
    ):
        assert guard.is_protected_path(path), f"{path} must need review"


def test_provider_core_paths_are_protected():
    """A single bad edit here degrades every chat request — human required."""
    for path in (
        "gateway/provider_chain.py",
        "gateway/circuit_breaker.py",
        "gateway/routing_policy.json",
        "gateway/main.py",
    ):
        assert guard.is_protected_path(path), f"{path} must need review"


def test_secret_files_are_protected_by_suffix():
    assert guard.is_protected_path("deploy/.env.production")
    assert guard.is_protected_path(".env")
    assert not guard.is_protected_path("docs/ENVIRONMENT_SECRETS_RUNBOOK.md")


def test_ordinary_paths_are_not_protected():
    for path in (
        "docs/README.md",
        "scripts/ci/sarif_permission_guard.py",
        "tests/test_sarif_permission_guard.py",
    ):
        assert not guard.is_protected_path(path), f"{path} must not need review"


def test_match_is_case_insensitive():
    assert guard.is_protected_path(".GITHUB/WORKFLOWS/x.yml")


def test_classify_tier_red_yellow_green():
    # Red tier: protected paths require owner review
    tier, paths = guard.classify_tier({".github/workflows/unified-pipeline.yml", "docs/README.md"})
    assert tier == "red"
    assert ".github/workflows/unified-pipeline.yml" in paths

    # Yellow tier: service or core api paths (safe to merge with canary soak)
    tier, paths = guard.classify_tier({"core/api/routes/items.py", "gateway/service/custom_helper.py"})
    assert tier == "yellow"
    assert "core/api/routes/items.py" in paths

    # Green tier: routine docs, tests, and non-security CI scripts (instant merge)
    tier, paths = guard.classify_tier({"docs/README.md", "tests/unit/test_app.py", "scripts/ci/sarif_permission_guard.py"})
    assert tier == "green"
    assert paths == []


def test_tower_session_auth_is_protected():
    """বাংলা মন্তব্য: Tower-এর session auth fail-open হলে anonymous admin পায় — মানুষ লাগবে।"""
    for path in (
        "infrastructure/mcp-control-plane/src/http_server.ts",
        "infrastructure/mcp-control-plane/src/lib/session_principal.ts",
    ):
        assert guard.is_protected_path(path), f"{path} must need review"
