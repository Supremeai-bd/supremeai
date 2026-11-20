#!/usr/bin/env python3
"""RenderClient.trigger_deploy must stay able to pin an exact commit.

The failure this pins (real, 2026-11-20)
----------------------------------------
Commit e24921b92d36 refactored typing in scripts/lib/render_client.py and, in the
same edit, dropped `commit_id` from `trigger_deploy`'s signature.

`scripts/ci/render_trigger_deploy.py` calls it as
`client.trigger_deploy(svc_id, commit_id=commit_id)` under
REQUIRE_EXPECTED_SHA=1. With the parameter gone, every call raised TypeError.
The caller's `except (OSError, ValueError)` did not catch TypeError, so the
retry loop ran five times and then returned 1.

Result: every Render deploy job failed in ~10 seconds with only
"Process completed with exit code 1" as evidence. Twelve of twelve executed
deploys failed on main between 12:43 and 19:03 across five services. The job is
path-filtered, so on most runs it reported `skipped` and the pipeline looked
green — which is why it went unnoticed for hours and read as flaky infra.

These tests fail loudly if the parameter is removed again, and also assert the
caller fails fast instead of retrying a code defect.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))

from render_client import RenderClient  # noqa: E402

PIPELINE = REPO_ROOT / ".github" / "workflows" / "unified-pipeline.yml"
CALLER = REPO_ROOT / "scripts" / "ci" / "render_trigger_deploy.py"


class _Stub(RenderClient):
    """Records the request instead of performing it."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, dict | None]] = []

    def _request(self, method, path, body=None, query=None):  # noqa: D102
        self.sent.append((method, path, body))
        return {"deploy": {"id": "dep-abc123", "status": "created"}}


def test_trigger_deploy_accepts_commit_id():
    params = inspect.signature(RenderClient.trigger_deploy).parameters
    assert "commit_id" in params, (
        "trigger_deploy lost its commit_id parameter again — the CI deploy step "
        "calls it with commit_id= and will raise TypeError for every service"
    )


def test_commit_id_is_sent_in_the_request_body():
    stub = _Stub()
    stub.trigger_deploy("srv-x", commit_id="a" * 40)

    method, path, body = stub.sent[-1]
    assert method == "POST"
    assert path.endswith("/services/srv-x/deploys")
    assert body["commitId"] == "a" * 40, "the pinned SHA did not reach the API body"


def test_omitting_commit_id_keeps_branch_head_behaviour():
    """No key at all — Render must not receive commitId: None."""
    stub = _Stub()
    stub.trigger_deploy("srv-x")

    body = stub.sent[-1][2]
    assert "commitId" not in body
    assert body["clearCache"] == "do_not_clear"


def test_caller_still_pins_the_commit():
    """The other half of the contract: the caller must keep passing it."""
    src = CALLER.read_text(encoding="utf-8")
    assert "trigger_deploy(svc_id, commit_id=commit_id)" in src, (
        "render_trigger_deploy no longer pins the commit; strict SHA attestation "
        "would then verify a deploy of an arbitrary HEAD"
    )


def test_caller_fails_fast_on_a_signature_mismatch():
    """A TypeError is a code defect, not a transient API error — never retried."""
    src = CALLER.read_text(encoding="utf-8")
    assert "except TypeError:" in src, (
        "render_trigger_deploy no longer fails fast on TypeError; a signature "
        "break would again surface as 5 silent retries and a bare exit code 1"
    )


def test_http_client_has_a_timeout():
    """Without a timeout a hung API stalls the job until the workflow timeout."""
    src = (REPO_ROOT / "scripts" / "lib" / "render_client.py").read_text(encoding="utf-8")
    assert "urlopen(req, timeout=" in src, (
        "the Render transport lost its per-request timeout (dropped in "
        "e24921b92d36, restored here)"
    )


def test_exhausted_retries_name_the_cause():
    """The terminal message must carry the last error, not just "no deploy".

    On 2026-11-20 the brain deploy failed after the 5x retry loop and the only
    evidence was "Process completed with exit code 1" — the loop discarded what
    Render actually said. A named cause is the difference between a five-minute
    diagnosis and an hour of guessing.
    """
    src = CALLER.read_text(encoding="utf-8")
    assert "last_reason" in src, (
        "render_trigger_deploy no longer records why the last attempt failed"
    )
    assert "last error:" in src, (
        "the terminal failure message no longer includes the underlying error"
    )


def test_deploy_job_sets_strict_sha_mode():
    """Guards the workflow side: strict mode is what makes pinning mandatory."""
    workflow = PIPELINE.read_text(encoding="utf-8")
    assert 'REQUIRE_EXPECTED_SHA: "1"' in workflow, (
        "the Render deploy step no longer runs in strict SHA mode, so commit "
        "pinning could regress without any test noticing"
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))


# ---------------------------------------------------------------------------
# Deploy-id recovery (2026-11-21: the `mcp` deploy job failed rc 2 because the
# trigger body carried no id — the deploy existed, we just never learned its id)
# ---------------------------------------------------------------------------
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))


def _caller():
    """Import the caller script (scripts/lib is already on sys.path)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("render_trigger_deploy_t", CALLER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _LatestDeployClient:
    def __init__(self, record: dict | Exception) -> None:
        self.record = record
        self.calls = 0

    def get_latest_deploy(self, svc_id: str):  # noqa: D102
        self.calls += 1
        if isinstance(self.record, Exception):
            raise self.record
        return self.record


SHA = "2a7c2e0a742b7f9a9055c869e9f52e435e4630d2"


def test_recovers_the_id_when_the_trigger_body_carried_none():
    caller = _caller()
    client = _LatestDeployClient({"id": "dep-recovered1", "commit": {"id": SHA}})
    recovered = caller.recover_deploy_id(client, "srv-abc", {}, SHA)
    assert recovered == "dep-recovered1"
    assert client.calls == 1


def test_recovery_refuses_a_deploy_building_another_commit():
    """Polling someone else's deploy is how a false green happens."""
    caller = _caller()
    client = _LatestDeployClient({"id": "dep-old", "commit": {"id": "b5809960"}})
    assert caller.recover_deploy_id(client, "srv-abc", {}, SHA) is None


def test_recovery_refuses_a_body_without_a_usable_id():
    caller = _caller()
    client = _LatestDeployClient({"message": "not a deploy", "commit": {"id": SHA}})
    assert caller.recover_deploy_id(client, "srv-abc", {}, SHA) is None


def test_recovery_survives_a_transport_error():
    caller = _caller()
    client = _LatestDeployClient(RuntimeError("network down"))
    assert caller.recover_deploy_id(client, "srv-abc", {}, SHA) is None


def test_strict_failure_surfaces_the_trigger_body():
    """rc 2 used to say only "carried no id" — with no way to see what came back."""
    src = CALLER.read_text(encoding="utf-8")
    assert "_brief(trigger_body)" in src, (
        "the rc-2 message no longer includes the trigger body; the next failure "
        "will again be undiagnosable from the annotation alone"
    )


def test_wait_polls_a_recovered_id_instead_of_failing_strict_mode():
    """End-to-end: trigger body has no id, recovery finds it, poll verifies live.

    Without recovery this run returns 2 (the real `mcp` failure on 2026-11-21).
    """
    caller = _caller()

    class _Client(RenderClient):
        def __init__(self) -> None:
            self.paths: list[str] = []

        def _request(self, method, path, body=None, query=None):  # noqa: D102
            self.paths.append(path)
            if path.endswith("/deploys"):
                return [{"id": "dep-rec1", "commit": {"id": SHA}}]
            return {"id": "dep-rec1", "status": "live", "commit": {"id": SHA}}

    client = _Client()
    rc = caller.wait_for_terminal_state(client, "srv-x", {}, expected_sha=SHA)

    assert rc == 0, f"strict deploy did not verify (rc={rc}); paths={client.paths}"
    assert any(p.endswith("/deploys/dep-rec1") for p in client.paths), (
        f"the recovered id was never polled: {client.paths}"
    )
