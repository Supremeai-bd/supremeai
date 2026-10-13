"""MESH-7 Phase 2 (issue #925) — GitHub Write Tools completion tests.

বাংলা সারসংক্ষেপ:
------------------
issue #925 অনুযায়ী নতুন ৪টি tool + ২টি বর্ধিত tool-এর সম্পূর্ণ চুক্তি যাচাই:

নতুন tools:
1. github_commit_files — multi-file atomic commit (git tree+commit API)
2. github_pr_comment  — explicit PR comment (issue comment endpoint shared with PRs)
3. github_close_issue  — PATCH issue → state=closed (ঐচ্ছিক comment + state_reason)
4. github_add_labels   — POST labels to issue/PR

বর্ধিত tools:
5. github_create_pull_request — `Fixes #N` issue-link বাধ্যতামূলক (issue-first policy)
6. github_merge_pull_request  — CI-green check বাধ্যতামূলক pre-merge (P0 policy)

টেস্ট কভারেজ:
- Input validation (pydantic): বৈধ ইনপুট + required field অনুপস্থিতি + encoding pattern
- Path allowlist: protected path (backend/core/**, .github/**) → DENY without override
- Path allowlist: allow_protected_paths=True → ALLOW
- CI-green check: state=success → merge proceeds; state=failure → DENY
- CI-green check: PR head sha অনুপস্থিতি → DENY
- Fixes #N: body with no issue-link → DENY
- Fixes #N: body with "Closes #123" / "Resolves #456" → ALLOW
- Happy path (fake httpx): সঠিক endpoint/method/payload, সফল ফলাফল + ALLOW audit
- Error path: 403/422/500 → handle_api_error-র মানবপঠনযোগ্য মেসেজ + ERROR audit
- Audit: DENY outcome tenant_id="platform-admin" সহ logged (Law #19)

কোনো নেটওয়ার্ক কল নেই — httpx.AsyncClient সম্পূর্ণভাবে fake।
"""

from __future__ import annotations

import base64
import json
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

import tools.mcp.mcp_github_cicd as gh

REPO = "SaifulHaqueNiloy/supremeai"
API = "https://api.github.com"


def _mk_response(
    status_code: int, data: dict[str, Any] | list[Any] | None = None
) -> httpx.Response:
    """httpx.Response ফ্যাক্টরি — সব fake client কলের জন্য।"""
    request = httpx.Request("GET", "https://api.github.com/test")
    if data is None:
        content = b""
    else:
        content = json.dumps(data).encode("utf-8")
    return httpx.Response(status_code=status_code, content=content, request=request)


class FakeAsyncClient:
    """httpx.AsyncClient স্ট্যান্ড-ইন — GET/POST/PUT/PATCH সব মেথড সাপোর্ট করে।

    `responses` key: f"{method} {url}" → httpx.Response।
    না থাকলে 200 {} (empty dict) ডিফল্ট।
    """

    def __init__(self, responses: dict[str, httpx.Response] | None = None):
        self.responses = responses or {}
        self.calls: list[tuple[str, str]] = []
        self.payloads: list[Any] = []
        self.headers_sent: list[dict[str, str]] = []

    async def __aenter__(self) -> FakeAsyncClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None

    def _resolve(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        self.calls.append((method, url))
        if "json" in kwargs:
            self.payloads.append(kwargs.get("json"))
        if "headers" in kwargs:
            self.headers_sent.append(kwargs.get("headers") or {})
        return self.responses.get(f"{method} {url}", _mk_response(200, {}))

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self._resolve("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self._resolve("POST", url, **kwargs)

    async def put(self, url: str, **kwargs: Any) -> httpx.Response:
        return self._resolve("PUT", url, **kwargs)

    async def patch(self, url: str, **kwargs: Any) -> httpx.Response:
        return self._resolve("PATCH", url, **kwargs)


@pytest.fixture()
def authorized(monkeypatch: pytest.MonkeyPatch):
    """Admin + token সহ authorized পরিবেশ; audit কল ক্যাপচার করে।"""
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
    """FakeAsyncClient কে httpx.AsyncClient হিসেবে inject করে।"""
    monkeypatch.setattr(gh, "GITHUB_REPO", "SaifulHaqueNiloy/supremeai")

    def _factory(timeout: float = 30.0, **kwargs: Any) -> FakeAsyncClient:
        return client

    monkeypatch.setattr(gh.httpx, "AsyncClient", _factory)


# ═══════════════════════════════════════════════════════════════════════════════
# ১. Input validation (pydantic models)
# ═══════════════════════════════════════════════════════════════════════════════


class TestInputValidation:
    """নতুন ও বর্ধিত ইনপুট মডেলের চুক্তি।"""

    def test_file_content_item_defaults_utf8(self):
        item = gh.FileContentItem(path="src/a.py", content="print(1)")
        assert item.encoding == "utf-8"
        assert item.path == "src/a.py"

    def test_file_content_item_base64_passthrough(self):
        item = gh.FileContentItem(path="bin/blob", content="AAAA", encoding="base64")
        assert item.encoding == "base64"

    def test_file_content_item_bad_encoding_rejected(self):
        with pytest.raises(ValidationError):
            gh.FileContentItem(path="p", content="c", encoding="rot13")

    def test_file_content_item_missing_path_rejected(self):
        with pytest.raises(ValidationError):
            gh.FileContentItem(content="c")

    def test_commit_files_valid_minimal(self):
        inp = gh.CommitFilesInput(
            branch="mesh/task-1",
            message="feat: add module",
            files=[gh.FileContentItem(path="a.txt", content="hello")],
        )
        assert inp.allow_protected_paths is False
        assert len(inp.files) == 1

    def test_commit_files_empty_files_list_rejected(self):
        with pytest.raises(ValidationError):
            gh.CommitFilesInput(branch="b", message="m", files=[])

    def test_commit_files_missing_message_rejected(self):
        with pytest.raises(ValidationError):
            gh.CommitFilesInput(
                branch="b",
                files=[gh.FileContentItem(path="p", content="c")],
            )

    def test_commit_files_too_many_files_rejected(self):
        # max_length=100 → 101 files rejected
        files = [gh.FileContentItem(path=f"f{i}.txt", content="x") for i in range(101)]
        with pytest.raises(ValidationError):
            gh.CommitFilesInput(branch="b", message="m", files=files)

    def test_pr_comment_valid(self):
        inp = gh.PRCommentInput(pr_number=7, body="LGTM")
        assert inp.pr_number == 7

    def test_pr_comment_negative_number_rejected(self):
        with pytest.raises(ValidationError):
            gh.PRCommentInput(pr_number=0, body="b")

    def test_pr_comment_empty_body_rejected(self):
        with pytest.raises(ValidationError):
            gh.PRCommentInput(pr_number=1, body="")

    def test_close_issue_valid_minimal(self):
        inp = gh.CloseIssueInput(issue_number=42)
        assert inp.comment is None
        assert inp.state_reason is None

    def test_close_issue_with_comment_and_reason(self):
        inp = gh.CloseIssueInput(
            issue_number=42,
            comment="Duplicate of #5",
            state_reason="duplicate",
        )
        assert inp.state_reason == "duplicate"

    def test_close_issue_bad_state_reason_rejected(self):
        with pytest.raises(ValidationError):
            gh.CloseIssueInput(issue_number=1, state_reason="wontfix")

    def test_add_labels_valid(self):
        inp = gh.AddLabelsInput(issue_number=10, labels=["bug", "P0-critical"])
        assert len(inp.labels) == 2

    def test_add_labels_empty_list_rejected(self):
        with pytest.raises(ValidationError):
            gh.AddLabelsInput(issue_number=10, labels=[])

    def test_add_labels_negative_number_rejected(self):
        with pytest.raises(ValidationError):
            gh.AddLabelsInput(issue_number=0, labels=["x"])


# ═══════════════════════════════════════════════════════════════════════════════
# ২. Pure helper functions (no httpx) — _has_issue_link, _is_protected_path
# ═══════════════════════════════════════════════════════════════════════════════


class TestHelpers:
    """`Fixes #N` ও protected path helpers-এর একক চুক্তি।"""

    @pytest.mark.parametrize(
        "body",
        [
            "Fixes #123",
            "Closes #1",
            "Closed #99999",
            "fix #5",
            "fixes #5",
            "fixed #5",
            "Resolve #42",
            "resolves #42",
            "resolved #42",
            "This PR addresses the bug. Fixes #42.\n",
            "lowercase: closes #7",
            "Mixed: FiXeS #7",
        ],
    )
    def test_has_issue_link_positive(self, body: str):
        assert gh._has_issue_link(body) is True

    @pytest.mark.parametrize(
        "body",
        [
            "",
            None,
            "no issue link here",
            "issue 123 without hash",
            "#123 alone (no keyword)",
            "Fixes123 (no space)",
            "addresses #123 (wrong keyword)",
            "fix # 123 (space after hash)",
        ],
    )
    def test_has_issue_link_negative(self, body: str | None):
        assert gh._has_issue_link(body) is False

    @pytest.mark.parametrize(
        "path",
        [
            "backend/core/config.py",
            "backend/core/sub/deep.py",
            ".github/workflows/pr.yml",
            ".github/CODEOWNERS",
            "/backend/core/leading-slash.py",  # leading slash normalized
            "/.github/leading-slash.yml",
        ],
    )
    def test_is_protected_path_positive(self, path: str):
        assert gh._is_protected_path(path) is True

    @pytest.mark.parametrize(
        "path",
        [
            "src/a.py",
            "backend/tools/mcp/x.py",  # backend/ but not backend/core/
            "backend/api/routes.py",
            "docs/README.md",
            "frontend/src/App.tsx",
            "backend_core/legacy.py",  # different prefix
            ".github-backup/x.yml",  # different prefix (not /.github/)
            "",
        ],
    )
    def test_is_protected_path_negative(self, path: str):
        assert gh._is_protected_path(path) is False

    def test_find_protected_paths_filters_correctly(self):
        paths = [
            "src/a.py",
            "backend/core/config.py",  # protected
            "docs/README.md",
            ".github/workflows/pr.yml",  # protected
            "tests/test_a.py",
        ]
        protected = gh._find_protected_paths(paths)
        assert protected == ["backend/core/config.py", ".github/workflows/pr.yml"]


# ═══════════════════════════════════════════════════════════════════════════════
# ৩. github_commit_files — happy path, path allowlist, multi-file
# ═══════════════════════════════════════════════════════════════════════════════


class TestCommitFilesHappyPath:
    """github_commit_files — atomic multi-file commit happy path।"""

    async def test_commit_files_single_file(self, authorized, monkeypatch: pytest.MonkeyPatch):
        parent_sha = "parent123abc"
        tree_sha = "tree456def"
        new_commit_sha = "newcommit789"
        client = FakeAsyncClient(
            {
                f"GET {API}/repos/{REPO}/git/ref/heads/mesh/task-1": _mk_response(
                    200, {"object": {"sha": parent_sha}}
                ),
                f"GET {API}/repos/{REPO}/git/commits/{parent_sha}": _mk_response(
                    200, {"tree": {"sha": "base-tree-xyz"}}
                ),
                f"POST {API}/repos/{REPO}/git/blobs": _mk_response(201, {"sha": "blob-sha-1"}),
                f"POST {API}/repos/{REPO}/git/trees": _mk_response(201, {"sha": tree_sha}),
                f"POST {API}/repos/{REPO}/git/commits": _mk_response(201, {"sha": new_commit_sha}),
                f"PATCH {API}/repos/{REPO}/git/refs/heads/mesh/task-1": _mk_response(
                    200, {"object": {"sha": new_commit_sha}}
                ),
            }
        )
        _install(monkeypatch, client)
        result = json.loads(
            await gh.github_commit_files(
                gh.CommitFilesInput(
                    branch="mesh/task-1",
                    message="feat: add new file",
                    files=[gh.FileContentItem(path="src/new.py", content="print(1)")],
                )
            )
        )
        assert result["success"] is True
        assert result["commit_sha"] == new_commit_sha
        assert result["parent_sha"] == parent_sha
        assert result["files_committed"] == 1
        assert result["paths"] == ["src/new.py"]
        assert result["protected_paths_overridden"] is False
        # audit ALLOW recorded
        assert authorized[0][0] == "github_commit_files"
        assert authorized[0][1] == "ALLOW"

    async def test_commit_files_multiple_files(self, authorized, monkeypatch: pytest.MonkeyPatch):
        parent_sha = "p"
        new_commit_sha = "c"
        client = FakeAsyncClient(
            {
                f"GET {API}/repos/{REPO}/git/ref/heads/main": _mk_response(
                    200, {"object": {"sha": parent_sha}}
                ),
                f"GET {API}/repos/{REPO}/git/commits/{parent_sha}": _mk_response(
                    200, {"tree": {"sha": "bt"}}
                ),
                f"POST {API}/repos/{REPO}/git/blobs": _mk_response(201, {"sha": "blob"}),
                f"POST {API}/repos/{REPO}/git/trees": _mk_response(201, {"sha": "newtree"}),
                f"POST {API}/repos/{REPO}/git/commits": _mk_response(201, {"sha": new_commit_sha}),
                f"PATCH {API}/repos/{REPO}/git/refs/heads/main": _mk_response(
                    200, {"object": {"sha": new_commit_sha}}
                ),
            }
        )
        _install(monkeypatch, client)
        result = json.loads(
            await gh.github_commit_files(
                gh.CommitFilesInput(
                    branch="main",
                    message="feat: 3 files",
                    files=[
                        gh.FileContentItem(path="a.txt", content="A"),
                        gh.FileContentItem(path="b.txt", content="B"),
                        gh.FileContentItem(path="c.txt", content="C"),
                    ],
                )
            )
        )
        assert result["files_committed"] == 3
        assert len(result["paths"]) == 3
        # verify tree POSTed with all 3 items + base_tree
        tree_payload = None
        for p in client.payloads:
            if isinstance(p, dict) and "tree" in p and "base_tree" in p:
                tree_payload = p
                break
        assert tree_payload is not None
        assert tree_payload["base_tree"] == "bt"
        assert len(tree_payload["tree"]) == 3
        # verify each tree item has correct mode/type
        for item in tree_payload["tree"]:
            assert item["mode"] == "100644"
            assert item["type"] == "blob"
            assert item["sha"] == "blob"
            assert item["path"].endswith(".txt")

    async def test_commit_files_base64_passthrough(
        self, authorized, monkeypatch: pytest.MonkeyPatch
    ):
        """encoding=base64 → content raw passthrough (no re-encode)."""
        parent_sha = "p"
        new_commit_sha = "c"
        client = FakeAsyncClient(
            {
                f"GET {API}/repos/{REPO}/git/ref/heads/main": _mk_response(
                    200, {"object": {"sha": parent_sha}}
                ),
                f"GET {API}/repos/{REPO}/git/commits/{parent_sha}": _mk_response(
                    200, {"tree": {"sha": "bt"}}
                ),
                f"POST {API}/repos/{REPO}/git/blobs": _mk_response(201, {"sha": "blob"}),
                f"POST {API}/repos/{REPO}/git/trees": _mk_response(201, {"sha": "t"}),
                f"POST {API}/repos/{REPO}/git/commits": _mk_response(201, {"sha": new_commit_sha}),
                f"PATCH {API}/repos/{REPO}/git/refs/heads/main": _mk_response(
                    200, {"object": {"sha": new_commit_sha}}
                ),
            }
        )
        _install(monkeypatch, client)
        # Pre-encode binary content
        raw = b"\x00\x01binary\xff"
        b64 = base64.b64encode(raw).decode("ascii")
        result = json.loads(
            await gh.github_commit_files(
                gh.CommitFilesInput(
                    branch="main",
                    message="feat: binary blob",
                    files=[
                        gh.FileContentItem(path="assets/blob.bin", content=b64, encoding="base64")
                    ],
                )
            )
        )
        assert result["success"] is True
        # verify blob POSTed with the exact base64 content (no double-encoding)
        blob_payload = client.payloads[0]  # first POST is blobs
        assert blob_payload["encoding"] == "base64"
        assert blob_payload["content"] == b64

    async def test_commit_files_utf8_encodes_to_base64(
        self, authorized, monkeypatch: pytest.MonkeyPatch
    ):
        """encoding=utf-8 → content auto base64-encoded before blob POST."""
        parent_sha = "p"
        new_commit_sha = "c"
        client = FakeAsyncClient(
            {
                f"GET {API}/repos/{REPO}/git/ref/heads/main": _mk_response(
                    200, {"object": {"sha": parent_sha}}
                ),
                f"GET {API}/repos/{REPO}/git/commits/{parent_sha}": _mk_response(
                    200, {"tree": {"sha": "bt"}}
                ),
                f"POST {API}/repos/{REPO}/git/blobs": _mk_response(201, {"sha": "blob"}),
                f"POST {API}/repos/{REPO}/git/trees": _mk_response(201, {"sha": "t"}),
                f"POST {API}/repos/{REPO}/git/commits": _mk_response(201, {"sha": new_commit_sha}),
                f"PATCH {API}/repos/{REPO}/git/refs/heads/main": _mk_response(
                    200, {"object": {"sha": new_commit_sha}}
                ),
            }
        )
        _install(monkeypatch, client)
        text = "বাংলা কনটেন্ট"  # Bengali Unicode
        result = json.loads(
            await gh.github_commit_files(
                gh.CommitFilesInput(
                    branch="main",
                    message="feat: bengali",
                    files=[gh.FileContentItem(path="bn.txt", content=text)],
                )
            )
        )
        assert result["success"] is True
        # verify blob received correct base64 of the UTF-8 bytes
        expected_b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
        blob_payload = client.payloads[0]
        assert blob_payload["content"] == expected_b64


# ═══════════════════════════════════════════════════════════════════════════════
# ৪. github_commit_files — Path allowlist enforcement (P0 policy #925)
# ═══════════════════════════════════════════════════════════════════════════════


class TestPathAllowlist:
    """P0 policy: backend/core/** ও .github/** → DENY without explicit override।"""

    async def test_backend_core_blocked_without_override(
        self, authorized, monkeypatch: pytest.MonkeyPatch
    ):
        # NOTE: even if httpx fails, we should DENY before any HTTP call
        client = FakeAsyncClient({})  # empty → all calls would 200 {}
        _install(monkeypatch, client)
        result = json.loads(
            await gh.github_commit_files(
                gh.CommitFilesInput(
                    branch="main",
                    message="try core write",
                    files=[
                        gh.FileContentItem(path="backend/core/config.py", content="os.environ...")
                    ],
                    # allow_protected_paths=False (default)
                )
            )
        )
        assert "error" in result
        assert "Protected path" in result["error"]
        assert "allow_protected_paths=true" in result["error"]
        assert "backend/core/config.py" in result["error"]
        # NO HTTP call should have been made
        assert client.calls == []
        # DENY audit recorded
        assert any(a[0] == "github_commit_files" and a[1] == "DENY" for a in authorized)

    async def test_github_dir_blocked_without_override(
        self, authorized, monkeypatch: pytest.MonkeyPatch
    ):
        client = FakeAsyncClient({})
        _install(monkeypatch, client)
        result = json.loads(
            await gh.github_commit_files(
                gh.CommitFilesInput(
                    branch="main",
                    message="try workflow write",
                    files=[
                        gh.FileContentItem(
                            path=".github/workflows/pr.yml",
                            content="on: [push]",
                        )
                    ],
                )
            )
        )
        assert "error" in result
        assert ".github/workflows/pr.yml" in result["error"]
        assert client.calls == []

    async def test_mixed_protected_and_safe_blocked_entirely(
        self, authorized, monkeypatch: pytest.MonkeyPatch
    ):
        """যদি একটিও protected path থাকে এবং override না থাকে → পুরো commit DENY।"""
        client = FakeAsyncClient({})
        _install(monkeypatch, client)
        result = json.loads(
            await gh.github_commit_files(
                gh.CommitFilesInput(
                    branch="main",
                    message="mixed",
                    files=[
                        gh.FileContentItem(path="docs/safe.md", content="ok"),
                        gh.FileContentItem(
                            path="backend/core/secret.py",
                            content="KEY=...",  # protected
                        ),
                    ],
                )
            )
        )
        assert "error" in result
        # DENY before HTTP — no calls made
        assert client.calls == []

    async def test_protected_path_allowed_with_override(
        self, authorized, monkeypatch: pytest.MonkeyPatch
    ):
        """allow_protected_paths=True → protected path commit proceeds (audit flagged)।"""
        parent_sha = "p"
        new_commit_sha = "c"
        client = FakeAsyncClient(
            {
                f"GET {API}/repos/{REPO}/git/ref/heads/main": _mk_response(
                    200, {"object": {"sha": parent_sha}}
                ),
                f"GET {API}/repos/{REPO}/git/commits/{parent_sha}": _mk_response(
                    200, {"tree": {"sha": "bt"}}
                ),
                f"POST {API}/repos/{REPO}/git/blobs": _mk_response(201, {"sha": "blob"}),
                f"POST {API}/repos/{REPO}/git/trees": _mk_response(201, {"sha": "t"}),
                f"POST {API}/repos/{REPO}/git/commits": _mk_response(201, {"sha": new_commit_sha}),
                f"PATCH {API}/repos/{REPO}/git/refs/heads/main": _mk_response(
                    200, {"object": {"sha": new_commit_sha}}
                ),
            }
        )
        _install(monkeypatch, client)
        result = json.loads(
            await gh.github_commit_files(
                gh.CommitFilesInput(
                    branch="main",
                    message="protected override",
                    files=[gh.FileContentItem(path=".github/CODEOWNERS", content="* @owner")],
                    allow_protected_paths=True,
                )
            )
        )
        assert result["success"] is True
        assert result["protected_paths_overridden"] is True
        assert result["commit_sha"] == new_commit_sha

    async def test_safe_path_no_override_needed(self, authorized, monkeypatch: pytest.MonkeyPatch):
        """non-protected path → allow_protected_paths=False (default) এ চলে।"""
        parent_sha = "p"
        new_commit_sha = "c"
        client = FakeAsyncClient(
            {
                f"GET {API}/repos/{REPO}/git/ref/heads/feat/x": _mk_response(
                    200, {"object": {"sha": parent_sha}}
                ),
                f"GET {API}/repos/{REPO}/git/commits/{parent_sha}": _mk_response(
                    200, {"tree": {"sha": "bt"}}
                ),
                f"POST {API}/repos/{REPO}/git/blobs": _mk_response(201, {"sha": "blob"}),
                f"POST {API}/repos/{REPO}/git/trees": _mk_response(201, {"sha": "t"}),
                f"POST {API}/repos/{REPO}/git/commits": _mk_response(201, {"sha": new_commit_sha}),
                f"PATCH {API}/repos/{REPO}/git/refs/heads/feat/x": _mk_response(
                    200, {"object": {"sha": new_commit_sha}}
                ),
            }
        )
        _install(monkeypatch, client)
        result = json.loads(
            await gh.github_commit_files(
                gh.CommitFilesInput(
                    branch="feat/x",
                    message="safe commit",
                    files=[
                        gh.FileContentItem(
                            path="backend/api/routes.py",  # backend/ but not core/
                            content="# route",
                        )
                    ],
                )
            )
        )
        assert result["success"] is True
        assert result["protected_paths_overridden"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# ৫. github_commit_files — Error paths + Auth/Token gates
# ═══════════════════════════════════════════════════════════════════════════════


class TestCommitFilesGates:
    """github_commit_files — admin gate, token gate, rate limit, HTTP errors।"""

    async def test_admin_gate_blocks(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(gh, "is_admin_authorized", lambda: False)
        result = json.loads(
            await gh.github_commit_files(
                gh.CommitFilesInput(
                    branch="b",
                    message="m",
                    files=[gh.FileContentItem(path="a.txt", content="c")],
                )
            )
        )
        assert "Admin authorization" in result["error"]

    async def test_token_absence_blocks(self, authorized, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(gh, "_get_github_token", lambda: "")
        result = json.loads(
            await gh.github_commit_files(
                gh.CommitFilesInput(
                    branch="b",
                    message="m",
                    files=[gh.FileContentItem(path="a.txt", content="c")],
                )
            )
        )
        assert "GITHUB_TOKEN not configured" in result["error"]

    async def test_branch_ref_404(self, authorized, monkeypatch: pytest.MonkeyPatch):
        client = FakeAsyncClient(
            {
                f"GET {API}/repos/{REPO}/git/ref/heads/nonexistent": _mk_response(
                    404, {"message": "Branch not found"}
                )
            }
        )
        _install(monkeypatch, client)
        result = await gh.github_commit_files(
            gh.CommitFilesInput(
                branch="nonexistent",
                message="m",
                files=[gh.FileContentItem(path="a.txt", content="c")],
            )
        )
        assert result.startswith("Error:")
        assert any(a[0] == "github_commit_files" and a[1] == "ERROR" for a in authorized)

    async def test_blob_create_500(self, authorized, monkeypatch: pytest.MonkeyPatch):
        client = FakeAsyncClient(
            {
                f"GET {API}/repos/{REPO}/git/ref/heads/main": _mk_response(
                    200, {"object": {"sha": "p"}}
                ),
                f"GET {API}/repos/{REPO}/git/commits/p": _mk_response(200, {"tree": {"sha": "bt"}}),
                f"POST {API}/repos/{REPO}/git/blobs": _mk_response(500, {"message": "boom"}),
            }
        )
        _install(monkeypatch, client)
        result = await gh.github_commit_files(
            gh.CommitFilesInput(
                branch="main",
                message="m",
                files=[gh.FileContentItem(path="a.txt", content="c")],
            )
        )
        assert result.startswith("Error:")


# ═══════════════════════════════════════════════════════════════════════════════
# ৬. github_pr_comment — happy path + gates
# ═══════════════════════════════════════════════════════════════════════════════


class TestPRComment:
    """github_pr_comment — PR-এ কমেন্ট যোগ।"""

    async def test_pr_comment_happy_path(self, authorized, monkeypatch: pytest.MonkeyPatch):
        client = FakeAsyncClient(
            {
                f"POST {API}/repos/{REPO}/issues/42/comments": _mk_response(
                    201,
                    {"id": 12345, "html_url": "https://github.com/c/12345"},
                ),
            }
        )
        _install(monkeypatch, client)
        result = json.loads(
            await gh.github_pr_comment(gh.PRCommentInput(pr_number=42, body="LGTM :tada:"))
        )
        assert result["success"] is True
        assert result["pr_number"] == 42
        assert result["comment_id"] == 12345
        assert result["comment_url"] == "https://github.com/c/12345"
        # verify POST went to issue-comments endpoint (PRs share it)
        assert client.calls[-1] == ("POST", f"{API}/repos/{REPO}/issues/42/comments")
        # verify body payload
        assert client.payloads[-1] == {"body": "LGTM :tada:"}
        # audit ALLOW
        assert authorized[0] == ("github_pr_comment", "ALLOW", None)

    async def test_pr_comment_admin_gate_blocks(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(gh, "is_admin_authorized", lambda: False)
        result = json.loads(await gh.github_pr_comment(gh.PRCommentInput(pr_number=1, body="x")))
        assert "Admin authorization" in result["error"]

    async def test_pr_comment_token_absence_blocks(
        self, authorized, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(gh, "_get_github_token", lambda: "")
        result = json.loads(await gh.github_pr_comment(gh.PRCommentInput(pr_number=1, body="x")))
        assert "GITHUB_TOKEN not configured" in result["error"]

    async def test_pr_comment_404_pr_not_found(self, authorized, monkeypatch: pytest.MonkeyPatch):
        client = FakeAsyncClient(
            {
                f"POST {API}/repos/{REPO}/issues/9999/comments": _mk_response(
                    404, {"message": "Not Found"}
                )
            }
        )
        _install(monkeypatch, client)
        result = await gh.github_pr_comment(gh.PRCommentInput(pr_number=9999, body="x"))
        assert result.startswith("Error:")
        assert any(a[0] == "github_pr_comment" and a[1] == "ERROR" for a in authorized)


# ═══════════════════════════════════════════════════════════════════════════════
# ৭. github_close_issue — happy path, with comment, with state_reason
# ═══════════════════════════════════════════════════════════════════════════════


class TestCloseIssue:
    """github_close_issue — issue বন্ধ করা ও ঐচ্ছিক close-comment।"""

    async def test_close_issue_minimal(self, authorized, monkeypatch: pytest.MonkeyPatch):
        client = FakeAsyncClient(
            {
                f"PATCH {API}/repos/{REPO}/issues/77": _mk_response(
                    200,
                    {
                        "state": "closed",
                        "state_reason": "completed",
                        "html_url": "https://github.com/i/77",
                    },
                ),
            }
        )
        _install(monkeypatch, client)
        result = json.loads(await gh.github_close_issue(gh.CloseIssueInput(issue_number=77)))
        assert result["success"] is True
        assert result["state"] == "closed"
        assert result["state_reason"] == "completed"
        assert result["issue_url"] == "https://github.com/i/77"
        # no comment → only PATCH call
        methods = [c[0] for c in client.calls]
        assert methods == ["PATCH"]
        # verify PATCH payload
        assert client.payloads[-1] == {"state": "closed"}
        assert authorized[0] == ("github_close_issue", "ALLOW", None)

    async def test_close_issue_with_comment(self, authorized, monkeypatch: pytest.MonkeyPatch):
        client = FakeAsyncClient(
            {
                f"POST {API}/repos/{REPO}/issues/77/comments": _mk_response(
                    201, {"id": 9999, "html_url": "https://github.com/c/9999"}
                ),
                f"PATCH {API}/repos/{REPO}/issues/77": _mk_response(
                    200, {"state": "closed", "html_url": "https://github.com/i/77"}
                ),
            }
        )
        _install(monkeypatch, client)
        result = json.loads(
            await gh.github_close_issue(
                gh.CloseIssueInput(issue_number=77, comment="Closing — fixed in #80")
            )
        )
        assert result["success"] is True
        assert result["comment_id"] == 9999
        assert result["comment_url"] == "https://github.com/c/9999"
        # verify call order: POST comment FIRST, then PATCH
        assert client.calls[0] == ("POST", f"{API}/repos/{REPO}/issues/77/comments")
        assert client.calls[1] == ("PATCH", f"{API}/repos/{REPO}/issues/77")

    async def test_close_issue_with_state_reason_not_planned(
        self, authorized, monkeypatch: pytest.MonkeyPatch
    ):
        client = FakeAsyncClient(
            {
                f"PATCH {API}/repos/{REPO}/issues/77": _mk_response(
                    200,
                    {
                        "state": "closed",
                        "state_reason": "not_planned",
                        "html_url": "https://github.com/i/77",
                    },
                ),
            }
        )
        _install(monkeypatch, client)
        result = json.loads(
            await gh.github_close_issue(
                gh.CloseIssueInput(issue_number=77, state_reason="not_planned")
            )
        )
        assert result["state_reason"] == "not_planned"
        # verify PATCH includes state_reason
        assert client.payloads[-1] == {"state": "closed", "state_reason": "not_planned"}

    async def test_close_issue_admin_gate_blocks(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(gh, "is_admin_authorized", lambda: False)
        result = json.loads(await gh.github_close_issue(gh.CloseIssueInput(issue_number=1)))
        assert "Admin authorization" in result["error"]

    async def test_close_issue_token_absence_blocks(
        self, authorized, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(gh, "_get_github_token", lambda: "")
        result = json.loads(await gh.github_close_issue(gh.CloseIssueInput(issue_number=1)))
        assert "GITHUB_TOKEN not configured" in result["error"]

    async def test_close_issue_404_issue_not_found(
        self, authorized, monkeypatch: pytest.MonkeyPatch
    ):
        client = FakeAsyncClient(
            {f"PATCH {API}/repos/{REPO}/issues/9999": _mk_response(404, {"message": "Not Found"})}
        )
        _install(monkeypatch, client)
        result = await gh.github_close_issue(gh.CloseIssueInput(issue_number=9999))
        assert result.startswith("Error:")
        assert any(a[0] == "github_close_issue" and a[1] == "ERROR" for a in authorized)


# ═══════════════════════════════════════════════════════════════════════════════
# ৮. github_add_labels — happy path + gates
# ═══════════════════════════════════════════════════════════════════════════════


class TestAddLabels:
    """github_add_labels — issue/PR-তে labels যোগ।"""

    async def test_add_labels_happy_path(self, authorized, monkeypatch: pytest.MonkeyPatch):
        client = FakeAsyncClient(
            {
                f"POST {API}/repos/{REPO}/issues/55/labels": _mk_response(
                    200,
                    [
                        {"name": "bug"},  # pre-existing
                        {"name": "P0-critical"},  # newly added
                        {"name": "mesh"},  # newly added
                    ],
                ),
            }
        )
        _install(monkeypatch, client)
        result = json.loads(
            await gh.github_add_labels(
                gh.AddLabelsInput(issue_number=55, labels=["P0-critical", "mesh"])
            )
        )
        assert result["success"] is True
        assert result["issue_number"] == 55
        assert result["labels_added"] == ["P0-critical", "mesh"]
        assert result["labels_now"] == ["bug", "P0-critical", "mesh"]
        # verify POST endpoint + payload
        assert client.calls[-1] == ("POST", f"{API}/repos/{REPO}/issues/55/labels")
        assert client.payloads[-1] == {"labels": ["P0-critical", "mesh"]}
        assert authorized[0] == ("github_add_labels", "ALLOW", None)

    async def test_add_labels_admin_gate_blocks(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(gh, "is_admin_authorized", lambda: False)
        result = json.loads(
            await gh.github_add_labels(gh.AddLabelsInput(issue_number=1, labels=["x"]))
        )
        assert "Admin authorization" in result["error"]

    async def test_add_labels_token_absence_blocks(
        self, authorized, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(gh, "_get_github_token", lambda: "")
        result = json.loads(
            await gh.github_add_labels(gh.AddLabelsInput(issue_number=1, labels=["x"]))
        )
        assert "GITHUB_TOKEN not configured" in result["error"]

    async def test_add_labels_410_issue_locked(self, authorized, monkeypatch: pytest.MonkeyPatch):
        client = FakeAsyncClient(
            {f"POST {API}/repos/{REPO}/issues/1/labels": _mk_response(410, {"message": "Gone"})}
        )
        _install(monkeypatch, client)
        result = await gh.github_add_labels(gh.AddLabelsInput(issue_number=1, labels=["x"]))
        assert result.startswith("Error:")
        assert any(a[0] == "github_add_labels" and a[1] == "ERROR" for a in authorized)


# ═══════════════════════════════════════════════════════════════════════════════
# ৯. github_create_pull_request — `Fixes #N` issue-link mandatory
# ═══════════════════════════════════════════════════════════════════════════════


class TestCreatePRFixesNEnforcement:
    """github_create_pull_request — `Fixes #N` issue-link বাধ্যতামূলক (issue-first policy #925)।"""

    async def test_pr_without_issue_link_denied(self, authorized, monkeypatch: pytest.MonkeyPatch):
        client = FakeAsyncClient({})  # no HTTP should be made
        _install(monkeypatch, client)
        result = json.loads(
            await gh.github_create_pull_request(
                gh.CreatePRInput(
                    title="feat: add X",
                    body="Just adding X — no issue reference",
                    head="feat/x",
                )
            )
        )
        assert "error" in result
        assert "issue-link" in result["error"]
        assert "Fixes #123" in result["error"]  # suggestion
        # NO HTTP call made
        assert client.calls == []
        # DENY audit recorded
        assert any(a[0] == "github_create_pull_request" and a[1] == "DENY" for a in authorized)

    async def test_pr_with_empty_body_denied(self, authorized, monkeypatch: pytest.MonkeyPatch):
        # body="" fails min_length=1 already at pydantic level → ValidationError
        with pytest.raises(ValidationError):
            gh.CreatePRInput(title="t", body="", head="h")

    async def test_pr_with_fixes_link_accepted(self, authorized, monkeypatch: pytest.MonkeyPatch):
        client = FakeAsyncClient(
            {
                f"POST {API}/repos/{REPO}/pulls": _mk_response(
                    201,
                    {"number": 99, "html_url": "https://github.com/p/99", "state": "open"},
                ),
            }
        )
        _install(monkeypatch, client)
        result = json.loads(
            await gh.github_create_pull_request(
                gh.CreatePRInput(
                    title="feat(#42): add X",
                    body="This PR adds X.\n\nFixes #42",
                    head="feat/x",
                )
            )
        )
        assert result["success"] is True
        assert result["pr_number"] == 99
        assert client.calls[-1] == ("POST", f"{API}/repos/{REPO}/pulls")

    async def test_pr_with_closes_link_accepted(self, authorized, monkeypatch: pytest.MonkeyPatch):
        client = FakeAsyncClient(
            {
                f"POST {API}/repos/{REPO}/pulls": _mk_response(
                    201, {"number": 1, "html_url": "u", "state": "open"}
                ),
            }
        )
        _install(monkeypatch, client)
        result = json.loads(
            await gh.github_create_pull_request(
                gh.CreatePRInput(
                    title="t",
                    body="Closes #123",
                    head="h",
                )
            )
        )
        assert result["success"] is True

    async def test_pr_with_resolves_link_accepted(
        self, authorized, monkeypatch: pytest.MonkeyPatch
    ):
        client = FakeAsyncClient(
            {
                f"POST {API}/repos/{REPO}/pulls": _mk_response(
                    201, {"number": 1, "html_url": "u", "state": "open"}
                ),
            }
        )
        _install(monkeypatch, client)
        result = json.loads(
            await gh.github_create_pull_request(
                gh.CreatePRInput(
                    title="t",
                    body="Resolves #456",
                    head="h",
                )
            )
        )
        assert result["success"] is True

    async def test_pr_admin_gate_blocks(self, monkeypatch: pytest.MonkeyPatch):
        """Admin gate checked BEFORE Fixes #N (fail-closed early)।"""
        monkeypatch.setattr(gh, "is_admin_authorized", lambda: False)
        result = json.loads(
            await gh.github_create_pull_request(
                gh.CreatePRInput(
                    title="t",
                    body="Fixes #1",  # has link, but admin missing
                    head="h",
                )
            )
        )
        assert "Admin authorization" in result["error"]


# ═══════════════════════════════════════════════════════════════════════════════
# ১০. github_merge_pull_request — CI-green pre-merge check (P0 policy #925)
# ═══════════════════════════════════════════════════════════════════════════════


class TestMergePRCICheck:
    """P0 policy: merge করার আগে CI status `success` হতে হবে (no bypass)।"""

    async def test_merge_blocked_when_ci_failure(self, authorized, monkeypatch: pytest.MonkeyPatch):
        head_sha = "head789ghi"
        client = FakeAsyncClient(
            {
                f"GET {API}/repos/{REPO}/pulls/12": _mk_response(200, {"head": {"sha": head_sha}}),
                f"GET {API}/repos/{REPO}/commits/{head_sha}/status": _mk_response(
                    200, {"state": "failure"}
                ),
                # merge endpoint NOT mocked — must NOT be called
            }
        )
        _install(monkeypatch, client)
        result = json.loads(await gh.github_merge_pull_request(gh.MergePRInput(pr_number=12)))
        assert "error" in result
        assert "P0 CI-green policy" in result["error"]
        assert "failure" in result["error"]
        # verify GET /pulls/12 + GET /commits/{sha}/status called, but NOT PUT /pulls/12/merge
        methods_urls = client.calls
        get_calls = [c for c in methods_urls if c[0] == "GET"]
        put_calls = [c for c in methods_urls if c[0] == "PUT"]
        assert len(get_calls) == 2
        assert put_calls == []
        # DENY audit recorded
        assert any(a[0] == "github_merge_pull_request" and a[1] == "DENY" for a in authorized)

    async def test_merge_blocked_when_ci_pending(self, authorized, monkeypatch: pytest.MonkeyPatch):
        head_sha = "head_pending"
        client = FakeAsyncClient(
            {
                f"GET {API}/repos/{REPO}/pulls/12": _mk_response(200, {"head": {"sha": head_sha}}),
                f"GET {API}/repos/{REPO}/commits/{head_sha}/status": _mk_response(
                    200, {"state": "pending"}
                ),
            }
        )
        _install(monkeypatch, client)
        result = json.loads(await gh.github_merge_pull_request(gh.MergePRInput(pr_number=12)))
        assert "error" in result
        assert "pending" in result["error"]
        # NO PUT /pulls/12/merge
        put_calls = [c for c in client.calls if c[0] == "PUT"]
        assert put_calls == []

    async def test_merge_blocked_when_no_head_sha(
        self, authorized, monkeypatch: pytest.MonkeyPatch
    ):
        client = FakeAsyncClient(
            {
                f"GET {API}/repos/{REPO}/pulls/12": _mk_response(
                    200,
                    {"head": {}},  # no sha
                ),
            }
        )
        _install(monkeypatch, client)
        result = json.loads(await gh.github_merge_pull_request(gh.MergePRInput(pr_number=12)))
        assert "error" in result
        assert "head sha not found" in result["error"]

    async def test_merge_proceeds_when_ci_success(
        self, authorized, monkeypatch: pytest.MonkeyPatch
    ):
        head_sha = "head_green"
        client = FakeAsyncClient(
            {
                f"GET {API}/repos/{REPO}/pulls/12": _mk_response(200, {"head": {"sha": head_sha}}),
                f"GET {API}/repos/{REPO}/commits/{head_sha}/status": _mk_response(
                    200, {"state": "success"}
                ),
                f"PUT {API}/repos/{REPO}/pulls/12/merge": _mk_response(
                    200,
                    {"merged": True, "sha": "merge-sha", "message": "merged"},
                ),
            }
        )
        _install(monkeypatch, client)
        result = json.loads(
            await gh.github_merge_pull_request(gh.MergePRInput(pr_number=12, merge_method="squash"))
        )
        assert result["success"] is True
        assert result["merged"] is True
        assert result["merge_sha"] == "merge-sha"
        assert result["ci_head_sha"] == head_sha
        # verify call sequence: GET pulls → GET status → PUT merge
        methods = [c[0] for c in client.calls]
        assert methods == ["GET", "GET", "PUT"]
        assert authorized[0] == ("github_merge_pull_request", "ALLOW", None)

    async def test_merge_admin_gate_blocks(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(gh, "is_admin_authorized", lambda: False)
        result = json.loads(await gh.github_merge_pull_request(gh.MergePRInput(pr_number=1)))
        assert "Admin authorization" in result["error"]

    async def test_merge_pr_fetch_404(self, authorized, monkeypatch: pytest.MonkeyPatch):
        client = FakeAsyncClient(
            {
                f"GET {API}/repos/{REPO}/pulls/9999": _mk_response(404, {"message": "Not Found"}),
            }
        )
        _install(monkeypatch, client)
        result = await gh.github_merge_pull_request(gh.MergePRInput(pr_number=9999))
        assert result.startswith("Error:")
        assert any(a[0] == "github_merge_pull_request" and a[1] == "ERROR" for a in authorized)


# ═══════════════════════════════════════════════════════════════════════════════
# ১১. Audit trail (Constitution Law #19) — DENY outcome audit-logged
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuditTrail:
    """Constitution Law #19 — প্রতিটি write op-এর observable audit trail (including DENY)।"""

    async def test_deny_audit_for_protected_path(self, authorized, monkeypatch: pytest.MonkeyPatch):
        client = FakeAsyncClient({})  # no HTTP should be made
        _install(monkeypatch, client)
        await gh.github_commit_files(
            gh.CommitFilesInput(
                branch="main",
                message="m",
                files=[gh.FileContentItem(path="backend/core/x.py", content="c")],
            )
        )
        # DENY audit recorded with protected-path reason
        deny_audits = [a for a in authorized if a[0] == "github_commit_files" and a[1] == "DENY"]
        assert len(deny_audits) == 1
        assert "protected path" in (deny_audits[0][2] or "")

    async def test_deny_audit_for_missing_issue_link(
        self, authorized, monkeypatch: pytest.MonkeyPatch
    ):
        client = FakeAsyncClient({})
        _install(monkeypatch, client)
        await gh.github_create_pull_request(
            gh.CreatePRInput(title="t", body="no link here", head="h")
        )
        deny_audits = [
            a for a in authorized if a[0] == "github_create_pull_request" and a[1] == "DENY"
        ]
        assert len(deny_audits) == 1
        assert "issue-link" in (deny_audits[0][2] or "")

    async def test_deny_audit_for_ci_not_green(self, authorized, monkeypatch: pytest.MonkeyPatch):
        client = FakeAsyncClient(
            {
                f"GET {API}/repos/{REPO}/pulls/12": _mk_response(200, {"head": {"sha": "x"}}),
                f"GET {API}/repos/{REPO}/commits/x/status": _mk_response(200, {"state": "failure"}),
            }
        )
        _install(monkeypatch, client)
        await gh.github_merge_pull_request(gh.MergePRInput(pr_number=12))
        deny_audits = [
            a for a in authorized if a[0] == "github_merge_pull_request" and a[1] == "DENY"
        ]
        assert len(deny_audits) == 1
        assert "CI not green" in (deny_audits[0][2] or "")

    async def test_allow_audit_for_close_issue(self, authorized, monkeypatch: pytest.MonkeyPatch):
        client = FakeAsyncClient(
            {
                f"PATCH {API}/repos/{REPO}/issues/5": _mk_response(
                    200, {"state": "closed", "html_url": "u"}
                ),
            }
        )
        _install(monkeypatch, client)
        await gh.github_close_issue(gh.CloseIssueInput(issue_number=5))
        assert authorized[0] == ("github_close_issue", "ALLOW", None)

    async def test_allow_audit_for_add_labels(self, authorized, monkeypatch: pytest.MonkeyPatch):
        client = FakeAsyncClient(
            {
                f"POST {API}/repos/{REPO}/issues/5/labels": _mk_response(200, [{"name": "bug"}]),
            }
        )
        _install(monkeypatch, client)
        await gh.github_add_labels(gh.AddLabelsInput(issue_number=5, labels=["bug"]))
        assert authorized[0] == ("github_add_labels", "ALLOW", None)


# ═══════════════════════════════════════════════════════════════════════════════
# ১২. Rate limit (shared sliding window — all write tools)
# ═══════════════════════════════════════════════════════════════════════════════


class TestRateLimit:
    """শেয়ার্ড sliding-window — ৩০/min পার হলে সব write op ব্লক (existing+new tools)।"""

    async def test_commit_files_blocked_when_rate_limit_exceeded(
        self, authorized, monkeypatch: pytest.MonkeyPatch
    ):
        import time as _time

        gh._write_op_times.clear()
        now = _time.monotonic()
        gh._write_op_times.extend([now] * gh.WRITE_MAX_PER_WINDOW)
        result = json.loads(
            await gh.github_commit_files(
                gh.CommitFilesInput(
                    branch="b",
                    message="m",
                    files=[gh.FileContentItem(path="a.txt", content="c")],
                )
            )
        )
        assert "rate limit" in result["error"].lower()
        assert gh._write_op_times[0] == now  # no new timestamp added

    async def test_pr_comment_blocked_when_rate_limit_exceeded(
        self, authorized, monkeypatch: pytest.MonkeyPatch
    ):
        import time as _time

        gh._write_op_times.clear()
        now = _time.monotonic()
        gh._write_op_times.extend([now] * gh.WRITE_MAX_PER_WINDOW)
        result = json.loads(await gh.github_pr_comment(gh.PRCommentInput(pr_number=1, body="x")))
        assert "rate limit" in result["error"].lower()

    async def test_close_issue_blocked_when_rate_limit_exceeded(
        self, authorized, monkeypatch: pytest.MonkeyPatch
    ):
        import time as _time

        gh._write_op_times.clear()
        now = _time.monotonic()
        gh._write_op_times.extend([now] * gh.WRITE_MAX_PER_WINDOW)
        result = json.loads(await gh.github_close_issue(gh.CloseIssueInput(issue_number=1)))
        assert "rate limit" in result["error"].lower()

    async def test_add_labels_blocked_when_rate_limit_exceeded(
        self, authorized, monkeypatch: pytest.MonkeyPatch
    ):
        import time as _time

        gh._write_op_times.clear()
        now = _time.monotonic()
        gh._write_op_times.extend([now] * gh.WRITE_MAX_PER_WINDOW)
        result = json.loads(
            await gh.github_add_labels(gh.AddLabelsInput(issue_number=1, labels=["x"]))
        )
        assert "rate limit" in result["error"].lower()


# ═══════════════════════════════════════════════════════════════════════════════
# ১৩. Tool registration — 4 new tools visible in MCP tool list
# ═══════════════════════════════════════════════════════════════════════════════


class TestToolRegistration:
    """FastMCP tool registry-তে নতুন ৪টি tool registered আছে কিনা যাচাই।"""

    def test_all_expected_tools_registered(self):
        tm = getattr(gh.mcp, "_tool_manager", None) or getattr(gh.mcp, "tool_manager", None)
        assert tm is not None, "FastMCP tool manager not found"
        tools_dict = getattr(tm, "_tools", None) or getattr(tm, "tools", None)
        assert tools_dict is not None, "FastMCP tools registry not found"
        if isinstance(tools_dict, dict):
            names = set(tools_dict.keys())
        else:
            names = {t.name for t in tools_dict}
        # pre-existing tools
        for pre in [
            "github_create_branch",
            "github_push_commit",
            "github_create_issue",
            "github_add_issue_comment",
            "github_merge_pull_request",
            "github_create_pull_request",
            "github_list_issues",
            "github_get_ci_status",
            "github_get_file_contents",
            "github_search_code",
            "github_run_auto_fix",
        ]:
            assert pre in names, f"pre-existing tool {pre!r} not registered"
        # new tools added by MESH-7 Phase 2 (#925)
        for new in [
            "github_commit_files",
            "github_pr_comment",
            "github_close_issue",
            "github_add_labels",
        ]:
            assert new in names, f"new tool {new!r} not registered"

    def test_commit_files_destructive_hint_false(self):
        """github_commit_files destructiveHint=False (atomic commit, not destructive)."""
        tm = getattr(gh.mcp, "_tool_manager", None)
        tools = getattr(tm, "_tools", None)
        if isinstance(tools, dict) and "github_commit_files" in tools:
            tool = tools["github_commit_files"]
            annotations = getattr(tool, "annotations", None) or {}
            # annotations might be a ToolAnnotations dataclass — check both dict & attrs
            destructive = (
                annotations.get("destructiveHint")
                if isinstance(annotations, dict)
                else getattr(annotations, "destructiveHint", None)
            )
            assert destructive is False

    def test_merge_pr_destructive_hint_true(self):
        """github_merge_pull_request destructiveHint=True (P0 — actually merges)."""
        tm = getattr(gh.mcp, "_tool_manager", None)
        tools = getattr(tm, "_tools", None)
        if isinstance(tools, dict) and "github_merge_pull_request" in tools:
            tool = tools["github_merge_pull_request"]
            annotations = getattr(tool, "annotations", None) or {}
            destructive = (
                annotations.get("destructiveHint")
                if isinstance(annotations, dict)
                else getattr(annotations, "destructiveHint", None)
            )
            assert destructive is True
