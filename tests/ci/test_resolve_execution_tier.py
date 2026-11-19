from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.ci import resolve_execution_tier as ret


def _patch(monkeypatch: pytest.MonkeyPatch, *, local: bool, remaining: float, known: bool, worker: bool) -> None:
    monkeypatch.setenv("GITHUB_EVENT_NAME", "schedule")
    monkeypatch.setenv("ALLOW_LOCAL_CI", "true")
    monkeypatch.setattr(ret, "is_local_runner_online", lambda: local)
    monkeypatch.setattr(ret, "get_render_quota_remaining", lambda: (remaining, known))
    monkeypatch.setattr(ret, "is_render_ci_worker_available", lambda: worker)


def test_priority1_local_online(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, local=True, remaining=0.0, known=True, worker=False)
    assert ret.resolve_tier() == "local-self-hosted"


def test_priority2_render_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, local=False, remaining=100.0, known=True, worker=True)
    assert ret.resolve_tier() == "render-ci-runner"


def test_priority2_requires_quota_known(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, local=False, remaining=100.0, known=False, worker=True)
    assert ret.resolve_tier() == "github-ubuntu-render-backend"


def test_priority2_requires_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, local=False, remaining=100.0, known=True, worker=False)
    assert ret.resolve_tier() == "github-ubuntu-render-backend"


def test_priority2_requires_50_remaining(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, local=False, remaining=40.0, known=True, worker=True)
    assert ret.resolve_tier() == "github-ubuntu-emergency"


def test_priority3_quota_unknown_prefers_p3(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, local=False, remaining=ret.QUOTA_UNKNOWN_REMAINING, known=False, worker=False)
    assert ret.resolve_tier() == "github-ubuntu-render-backend"


def test_priority3_used_under_450(monkeypatch: pytest.MonkeyPatch) -> None:
    # remaining=100 -> used=400 < 450
    _patch(monkeypatch, local=False, remaining=100.0, known=True, worker=False)
    assert ret.resolve_tier() == "github-ubuntu-render-backend"


def test_priority4_quota_exhausted(monkeypatch: pytest.MonkeyPatch) -> None:
    # remaining=10 -> used=490 >= 450, known
    _patch(monkeypatch, local=False, remaining=10.0, known=True, worker=False)
    assert ret.resolve_tier() == "github-ubuntu-emergency"


def test_local_probe_exception_continues(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> bool:
        raise RuntimeError("boom")
    monkeypatch.setattr(ret, "is_local_runner_online", boom)
    monkeypatch.setattr(ret, "get_render_quota_remaining", lambda: (100.0, True))
    monkeypatch.setattr(ret, "is_render_ci_worker_available", lambda: True)
    assert ret.resolve_tier() == "render-ci-runner"


def test_constants_values() -> None:
    assert ret.RENDER_FREE_MONTHLY_LIMIT_MINS == 500.0
    assert ret.RENDER_QUOTA_REMAINING_P2_MINS == 50.0
    assert ret.RENDER_QUOTA_MAX_USED_P3_MINS == 450.0
    assert ret.get_render_quota_remaining()[1] is False


@pytest.mark.parametrize("event", ["pull_request", "pull_request_target"])
def test_untrusted_events_never_probe_the_personal_runner(monkeypatch, event):
    monkeypatch.setenv("GITHUB_EVENT_NAME", event)
    monkeypatch.setattr(ret, "is_local_runner_online", lambda: pytest.fail("private runner probe"))
    monkeypatch.setattr(ret, "is_render_ci_worker_available", lambda: pytest.fail("quota unknown"))
    assert ret.resolve_tier() == "github-ubuntu-render-backend"
