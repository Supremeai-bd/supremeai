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
