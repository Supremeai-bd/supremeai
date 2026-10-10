"""MESH-7 (issue #962) — Tower GitHub write-op tool tests (mocked httpx).

বাংলা সারসংক্ষেপ:
------------------
প্রতিটি নতুন write tool-এর জন্য চুক্তি যাচাই:
1. ইনপুট ভ্যালিডেশন (pydantic): বৈধ ইনপুট + required field অনুপস্থিতি
2. Admin gate fail-closed: is_admin_authorized()=False → json_error
3. Token absence fail-closed: _get_github_token()="" → json_error
4. Happy path (fake httpx client): সঠিক endpoint/method/payload, সফল ফলাফল
5. 403/422 HTTP error path: handle_api_error-র মানবপঠনযোগ্য মেসেজ
6. Rate limit: সব write op শেয়ার্ড sliding-window (30/min) সম্মান করে
7. Audit: প্রতিটি op tenant_id="platform-admin" সহ audit হয় (Law #19)

কোনো নেটওয়ার্ক কল নেই — httpx.AsyncClient সম্পূর্ণভাবে fake।
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

import tools.mcp.mcp_github_cicd as gh


def _mk_response(status_code: int, data: dict[str, Any] | None = None) -> httpx.Response:
    request = httpx.Request("GET", "https://api.github.com/test")
    content = json.dumps(data).encode("utf-8") if data is not None else b""
    return httpx.Response(status_code=status_code, content=content, request=request)


class FakeAsyncClient:
    """httpx.AsyncClient স্ট্যান্ড-ইন — সব কল রেকর্ড করে।"""

    calls: list[tuple[str, str]]

    def __init__(self, responses: dict[str, httpx.Response] | None = None):
        # key: f"{method} {url}" — না থাকলে 200 {}
        self.responses = responses or {}
        self.calls = []
        self.payloads: list[Any] = []

    async def __aenter__(self) -> FakeAsyncClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None

    def _resolve(self, method: str, url: str) -> httpx.Response:
        self.calls.append((method, url))
        return self.responses.get(f"{method} {url}", _mk_response(200, {}))

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self._resolve("GET", url)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        self.payloads.append(kwargs.get("json"))
        return self._resolve("POST", url)

    async def put(self, url: str, **kwargs: Any) -> httpx.Response:
        self.payloads.append(kwargs.get("json"))
        return self._resolve("PUT", url)


@pytest.fixture()
def authorized(monkeypatch: pytest.MonkeyPatch):
    """Admin + token সহ সাধারণ পরিবেশ; audit কল ক্যাপচার করে।"""
    monkeypatch.setattr(gh, "is_admin_authorized", lambda: True)
    monkeypatch.setattr(gh, "_get_github_token", lambda: "test-token")
    captured: list[tuple[str, str, str | None]] = []
    monkeypatch.setattr(
        gh,
        "audit_tool_call",
        lambda name, decision, risk_level, latency_ms=0.0, error=None, tenant_id=None: (
            captured.append((name, decision, error))
        ),
    )
    gh._write_op_times.clear()
    yield captured
    gh._write_op_times.clear()


def _install(monkeypatch: pytest.MonkeyPatch, client: FakeAsyncClient) -> None:
    monkeypatch.setattr(gh, "GITHUB_REPO", "SaifulHaqueNiloy/supremeai")
    monkeypatch.setattr(gh.httpx, "AsyncClient", lambda timeout=30.0: client)


class TestInputValidation:
    """৫টি নতুন ইনপুট মডেলের চুক্তি।"""

    def test_create_branch_valid_defaults_base_main(self):
        inp = gh.CreateBranchInput(branch="mesh/task-42")
        assert inp.branch == "mesh/task-42"
        assert inp.base == "main"

    def test_create_branch_missing_branch_rejected(self):
        with pytest.raises(ValidationError):
            gh.CreateBranchInput()

    def test_push_commit_valid(self):
        inp = gh.PushCommitInput(branch="mesh/task-1", path="a/b.txt", content="hello", message="m")
        assert inp.encoding == "utf-8"

    def test_push_commit_bad_encoding_rejected(self):
        with pytest.raises(ValidationError):
            gh.PushCommitInput(branch="b", path="p", content="c", message="m", encoding="rot13")

    def test_push_commit_missing_message_rejected(self):
        with pytest.raises(ValidationError):
            gh.PushCommitInput(branch="b", path="p", content="c")

    def test_create_issue_valid_labels_optional(self):
        inp = gh.CreateIssueInput(title="T")
        assert inp.labels == []
        assert inp.body == ""

    def test_create_issue_missing_title_rejected(self):
        with pytest.raises(ValidationError):
            gh.CreateIssueInput()

    def test_issue_comment_valid(self):
        inp = gh.IssueCommentInput(issue_number=5, body="done")
        assert inp.issue_number == 5

    def test_issue_comment_negative_number_rejected(self):
        with pytest.raises(ValidationError):
            gh.IssueCommentInput(issue_number=0, body="b")

    def test_merge_pr_valid_default_method(self):
        inp = gh.MergePRInput(pr_number=9)
        assert inp.merge_method == "merge"

    def test_merge_pr_bad_method_rejected(self):
        with pytest.raises(ValidationError):
            gh.MergePRInput(pr_number=9, merge_method="force")


class TestAuthAndTokenGates:
    """Fail-closed গেট: admin → rate-limit → token ক্রম।"""

    async def test_admin_gate_blocks(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(gh, "is_admin_authorized", lambda: False)
        result = json.loads(await gh.github_create_branch(gh.CreateBranchInput(branch="x")))
        assert "error" in result
        assert "Admin authorization" in result["error"]

    async def test_token_absence_blocks(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(gh, "is_admin_authorized", lambda: True)
        monkeypatch.setattr(gh, "_get_github_token", lambda: "")
        result = json.loads(await gh.github_create_issue(gh.CreateIssueInput(title="t")))
        assert "GITHUB_TOKEN not configured" in result["error"]


class TestRateLimit:
    """শেয়ার্ড sliding-window — ৩০/মিনিট পার হলে সব write op ব্লক।"""

    async def test_limit_blocks_after_max(self, authorized, monkeypatch: pytest.MonkeyPatch):
        import time as _time

        gh._write_op_times.clear()
        now = _time.monotonic()
        gh._write_op_times.extend([now] * gh.WRITE_MAX_PER_WINDOW)
        result = json.loads(
            await gh.github_add_issue_comment(gh.IssueCommentInput(issue_number=1, body="x"))
        )
        assert "rate limit" in result["error"].lower()
        assert gh._write_op_times[0] == now  # নতুন timestamp যোগ হয়নি


class TestHappyPaths:
    """Fake httpx দিয়ে প্রতিটি টুলের সফল পথ।"""

    async def test_create_branch(self, authorized, monkeypatch: pytest.MonkeyPatch):
        client = FakeAsyncClient(
            {
                "GET https://api.github.com/repos/SaifulHaqueNiloy/supremeai/git/ref/heads/main": _mk_response(
                    200, {"object": {"sha": "abc123def456"}}
                ),
                "POST https://api.github.com/repos/SaifulHaqueNiloy/supremeai/git/refs": _mk_response(
                    201, {"ref": "refs/heads/mesh/task-1", "url": "https://api.github.com/refs/x"}
                ),
            }
        )
        _install(monkeypatch, client)
        result = json.loads(
            await gh.github_create_branch(gh.CreateBranchInput(branch="mesh/task-1"))
        )
        assert result["success"] is True
        assert result["branch"] == "mesh/task-1"
        assert result["base_sha"] == "abc123def456"
        assert (
            authorized
            and authorized[0][0] == "github_create_branch"
            and authorized[0][1] == "ALLOW"
        )

    async def test_push_commit_update_existing(self, authorized, monkeypatch: pytest.MonkeyPatch):
        client = FakeAsyncClient(
            {
                "GET https://api.github.com/repos/SaifulHaqueNiloy/supremeai/contents/src/a.py": _mk_response(
                    200, {"sha": "file-sha-1"}
                ),
                "PUT https://api.github.com/repos/SaifulHaqueNiloy/supremeai/contents/src/a.py": _mk_response(
                    200, {"commit": {"sha": "c0ffee", "html_url": "https://github.com/c/1"}}
                ),
            }
        )
        _install(monkeypatch, client)
        result = json.loads(
            await gh.github_push_commit(
                gh.PushCommitInput(
                    branch="mesh/task-1", path="src/a.py", content="print(1)", message="m"
                )
            )
        )
        assert result["success"] is True
        assert result["created"] is False
        assert result["commit_sha"] == "c0ffee"
        put_payload = client.payloads[-1]
        assert put_payload["sha"] == "file-sha-1"
        assert put_payload["branch"] == "mesh/task-1"

    async def test_push_commit_create_new_file(self, authorized, monkeypatch: pytest.MonkeyPatch):
        client = FakeAsyncClient(
            {
                "GET https://api.github.com/repos/SaifulHaqueNiloy/supremeai/contents/new.txt": _mk_response(
                    404, {"message": "Not Found"}
                ),
                "PUT https://api.github.com/repos/SaifulHaqueNiloy/supremeai/contents/new.txt": _mk_response(
                    201, {"commit": {"sha": "abc"}}
                ),
            }
        )
        _install(monkeypatch, client)
        result = json.loads(
            await gh.github_push_commit(
                gh.PushCommitInput(branch="main", path="new.txt", content="data", message="add")
            )
        )
        assert result["created"] is True
        put_payload = client.payloads[-1]
        assert "sha" not in put_payload

    async def test_create_issue_with_labels(self, authorized, monkeypatch: pytest.MonkeyPatch):
        client = FakeAsyncClient(
            {
                "POST https://api.github.com/repos/SaifulHaqueNiloy/supremeai/issues": _mk_response(
                    201, {"number": 77, "html_url": "https://github.com/i/77", "state": "open"}
                )
            }
        )
        _install(monkeypatch, client)
        result = json.loads(
            await gh.github_create_issue(
                gh.CreateIssueInput(title="Bug", body="b", labels=["P1-high"])
            )
        )
        assert result["issue_number"] == 77
        assert client.payloads[-1]["labels"] == ["P1-high"]

    async def test_add_issue_comment(self, authorized, monkeypatch: pytest.MonkeyPatch):
        client = FakeAsyncClient(
            {
                "POST https://api.github.com/repos/SaifulHaqueNiloy/supremeai/issues/5/comments": _mk_response(
                    201, {"id": 999, "html_url": "https://github.com/c/999"}
                )
            }
        )
        _install(monkeypatch, client)
        result = json.loads(
            await gh.github_add_issue_comment(gh.IssueCommentInput(issue_number=5, body="verified"))
        )
        assert result["comment_id"] == 999

    async def test_merge_pull_request(self, authorized, monkeypatch: pytest.MonkeyPatch):
        # MESH-7 Phase 2 (#925): merge-এর আগে CI-green check বাধ্যতামূলক —
        # PR head SHA + combined status মক করা হয়েছে।
        head_sha = "abc123def456"
        client = FakeAsyncClient(
            {
                "GET https://api.github.com/repos/SaifulHaqueNiloy/supremeai/pulls/12": _mk_response(
                    200, {"head": {"sha": head_sha}}
                ),
                f"GET https://api.github.com/repos/SaifulHaqueNiloy/supremeai/commits/{head_sha}/status": _mk_response(
                    200, {"state": "success"}
                ),
                "PUT https://api.github.com/repos/SaifulHaqueNiloy/supremeai/pulls/12/merge": _mk_response(
                    200,
                    {
                        "merged": True,
                        "sha": "merge-sha",
                        "message": "Pull Request successfully merged",
                    },
                ),
            }
        )
        _install(monkeypatch, client)
        result = json.loads(
            await gh.github_merge_pull_request(gh.MergePRInput(pr_number=12, merge_method="squash"))
        )
        assert result["merged"] is True
        assert result["merge_sha"] == "merge-sha"
        assert result["ci_head_sha"] == head_sha
        assert client.payloads[-1]["merge_method"] == "squash"


class TestErrorPaths:
    """403/422 → handle_api_error-র মানবপঠনযোগ্য মেসেজ + ERROR audit।"""

    async def test_create_branch_422_already_exists(
        self, authorized, monkeypatch: pytest.MonkeyPatch
    ):
        client = FakeAsyncClient(
            {
                "GET https://api.github.com/repos/SaifulHaqueNiloy/supremeai/git/ref/heads/main": _mk_response(
                    200, {"object": {"sha": "abc"}}
                ),
                "POST https://api.github.com/repos/SaifulHaqueNiloy/supremeai/git/refs": _mk_response(
                    422, {"message": "Reference already exists"}
                ),
            }
        )
        _install(monkeypatch, client)
        result = await gh.github_create_branch(gh.CreateBranchInput(branch="exists"))
        assert result.startswith("Error:")
        assert any(a[0] == "github_create_branch" and a[1] == "ERROR" for a in authorized)

    async def test_merge_405_not_mergeable(self, authorized, monkeypatch: pytest.MonkeyPatch):
        # MESH-7 Phase 2 (#925): CI-green check পাস করার পরেই merge endpoint কল হয় —
        # তাই PR head SHA + combined status=success মক করা হয়েছে।
        head_sha = "head_405_test"
        client = FakeAsyncClient(
            {
                "GET https://api.github.com/repos/SaifulHaqueNiloy/supremeai/pulls/3": _mk_response(
                    200, {"head": {"sha": head_sha}}
                ),
                f"GET https://api.github.com/repos/SaifulHaqueNiloy/supremeai/commits/{head_sha}/status": _mk_response(
                    200, {"state": "success"}
                ),
                "PUT https://api.github.com/repos/SaifulHaqueNiloy/supremeai/pulls/3/merge": _mk_response(
                    405, {"message": "Pull Request is not mergeable"}
                ),
            }
        )
        _install(monkeypatch, client)
        result = await gh.github_merge_pull_request(gh.MergePRInput(pr_number=3))
        # handle_api_error-তে 405 ম্যাপ নেই → generic মানবপঠনযোগ্য মেসেজ
        assert result == "Error: API request failed - HTTPStatusError"
        assert any(a[0] == "github_merge_pull_request" and a[1] == "ERROR" for a in authorized)

    async def test_push_commit_unexpected_http_error(
        self, authorized, monkeypatch: pytest.MonkeyPatch
    ):
        client = FakeAsyncClient(
            {
                "GET https://api.github.com/repos/SaifulHaqueNiloy/supremeai/contents/x.txt": _mk_response(
                    500, {"message": "boom"}
                )
            }
        )
        _install(monkeypatch, client)
        result = await gh.github_push_commit(
            gh.PushCommitInput(branch="b", path="x.txt", content="c", message="m")
        )
        assert result.startswith("Error:")


class TestAuditTrail:
    """Constitution Law #19 — প্রতিটি op-এর tenant-স্পষ্ট audit।"""

    async def test_audit_called_with_platform_admin_tenant(
        self, authorized, monkeypatch: pytest.MonkeyPatch
    ):
        client = FakeAsyncClient(
            {
                "POST https://api.github.com/repos/SaifulHaqueNiloy/supremeai/issues": _mk_response(
                    201, {"number": 1, "state": "open"}
                )
            }
        )
        _install(monkeypatch, client)
        await gh.github_create_issue(gh.CreateIssueInput(title="t"))
        assert authorized, "audit_tool_call was not called"
        name, decision, _ = authorized[0]
        assert name == "github_create_issue"
        assert decision == "ALLOW"
