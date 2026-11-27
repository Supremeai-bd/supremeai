"""Watchdog must not invent evidence or dispatch against unknown queue state."""
import base64
import sys

import pytest

from scripts.ci import schedule_watchdog as watchdog


@pytest.fixture
def run_watchdog(monkeypatch, capsys):
    monkeypatch.setenv("GH_TOKEN", "test-token")
    monkeypatch.setenv("GH_REPO", "owner/repo")
    monkeypatch.setattr(sys, "argv", ["schedule_watchdog.py"])
    workflow = base64.b64encode(b"on:\n  schedule:\n    - cron: '0 3 * * *'\n  workflow_dispatch:\n").decode()

    def run(fail=None, malformed=None, busy=None):
        calls = []

        def fake_api(method, path, token, body=None):
            calls.append((method, path, body))
            if path == "/repos/owner/repo":
                return 200, {"default_branch": "main"}
            if path == "/repos/owner/repo/contents/.github/workflows":
                return 200, [{"path": ".github/workflows/example.yml"}]
            if path == "/repos/owner/repo/actions/workflows?per_page=100":
                return 200, {"workflows": [{"id": 42, "path": ".github/workflows/example.yml"}]}
            if path == "/repos/owner/repo/contents/.github/workflows/example.yml":
                return 200, {"content": workflow}
            if fail and fail in path:
                return 403, {}
            if malformed and malformed in path:
                return 200, {}
            if method in ("PUT", "POST"):
                return 204, {}
            if "status=" in path:
                return 200, {"workflow_runs": [{"id": 99}] if busy and busy in path else []}
            if "/runs?" in path:
                return 200, {"workflow_runs": [{"created_at": "2020-01-01T00:00:00Z"}]}
            raise AssertionError((method, path))

        monkeypatch.setattr(watchdog, "api", fake_api)
        rc = watchdog.main()
        return rc, calls, capsys.readouterr()

    return run


@pytest.mark.parametrize("failed", ["event=schedule", "runs?per_page=1"])
@pytest.mark.parametrize("malformed", [False, True])
def test_missing_history_evidence_does_not_mutate_workflows(run_watchdog, failed, malformed):
    rc, calls, output = run_watchdog(malformed=failed) if malformed else run_watchdog(fail=failed)
    assert rc == 1
    assert not any(method in {"POST", "PUT"} for method, _, _ in calls)
    assert "evidence unavailable" in output.out


@pytest.mark.parametrize("failed", ["status=queued", "status=in_progress"])
@pytest.mark.parametrize("malformed", [False, True])
def test_unknown_queue_state_never_dispatches(run_watchdog, failed, malformed):
    rc, calls, output = run_watchdog(malformed=failed) if malformed else run_watchdog(fail=failed)
    assert rc == 1
    assert not any(method in {"POST", "PUT"} for method, _, _ in calls)
    assert "comp=skipped(queue-state-unavailable)" in output.out


def test_confirmed_stale_idle_workflow_remains_dispatchable(run_watchdog):
    rc, calls, _ = run_watchdog()
    assert rc == 0
    assert [method for method, _, _ in calls if method in {"PUT", "POST"}] == ["PUT", "PUT", "POST"]


@pytest.mark.parametrize("failed", ["/disable", "/enable", "/dispatches"])
def test_failed_self_healing_action_is_reported_as_failure(run_watchdog, failed):
    rc, calls, output = run_watchdog(fail=failed)
    assert rc == 1
    assert "self-heal failed" in output.err
    if failed != "/dispatches":
        assert any(path.endswith("/enable") for method, path, _ in calls if method == "PUT")
        assert not any(method == "POST" for method, _, _ in calls)


@pytest.mark.parametrize("busy", ["status=queued", "status=in_progress"])
def test_busy_workflow_is_neither_rearmed_nor_dispatched(run_watchdog, busy):
    rc, calls, output = run_watchdog(busy=busy)
    assert rc == 0
    assert not any(method in {"POST", "PUT"} for method, _, _ in calls)
    assert "comp=skipped(already-queued-or-running)" in output.out
