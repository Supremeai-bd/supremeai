"""Which runner executes CI is a cost/availability decision — pin its ladder.

`resolve_tier` decides between the free local runner, the Render CI runner and
two GitHub fallbacks. Getting it wrong is expensive in either direction (Render
minutes burned, or a PR that never runs). Every branch is pinned here with the
probes stubbed, so no network or Render API is involved.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))

import resolve_execution_tier as tier  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
    monkeypatch.setenv("ALLOW_LOCAL_CI", "true")


def test_pull_request_never_uses_the_local_runner(monkeypatch):
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setattr(tier, "is_local_runner_online", lambda: True)
    monkeypatch.setattr(tier, "get_render_quota_remaining", lambda: (0.0, False))
    assert tier.resolve_tier() == "github-ubuntu-render-backend"


def test_offline_local_runner_falls_through_to_cloud(monkeypatch):
    monkeypatch.setattr(tier, "is_local_runner_online", lambda: False)
    monkeypatch.setattr(tier, "get_render_quota_remaining", lambda: (0.0, False))
    assert tier.resolve_tier() == "github-ubuntu-render-backend"


def test_unknown_quota_never_selects_the_render_runner(monkeypatch):
    monkeypatch.setattr(tier, "is_local_runner_online", lambda: False)
    monkeypatch.setattr(tier, "get_render_quota_remaining", lambda: (0.0, False))
    assert tier.resolve_tier() != "render-ci-runner"


def test_render_runner_requires_quota_and_availability(monkeypatch):
    monkeypatch.setattr(tier, "is_local_runner_online", lambda: False)
    monkeypatch.setattr(
        tier, "get_render_quota_remaining",
        lambda: (tier.RENDER_QUOTA_REMAINING_P2_MINS + 1, True),
    )
    monkeypatch.setattr(tier, "is_render_ci_worker_available", lambda: True)
    assert tier.resolve_tier() == "render-ci-runner"


def test_emergency_tier_is_the_last_resort(monkeypatch):
    monkeypatch.setattr(tier, "is_local_runner_online", lambda: False)
    # Known quota, below the P2 floor, and most of the monthly budget already used.
    monkeypatch.setattr(tier, "get_render_quota_remaining", lambda: (1.0, True))
    monkeypatch.setattr(tier, "is_render_ci_worker_available", lambda: True)
    assert tier.resolve_tier() == "github-ubuntu-emergency"
