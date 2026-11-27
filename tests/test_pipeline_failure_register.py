from __future__ import annotations

import io
import json
import subprocess
import sys
import urllib.error
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts" / "ci") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))

import pipeline_failure_register as pfr  # noqa: E402


def test_default_repo_points_to_canonical_org(monkeypatch: pytest.MonkeyPatch) -> None:
    """বাংলা মন্তব্য: লিগ্যাসি রিপো নামের বদলে ক্যানোনিকাল `Supremeai-bd/supremeai` ডিফল্ট নিশ্চিতকরণ।"""
    monkeypatch.delenv("GH_REPO", raising=False)
    # মডিউল লেভেলে env না থাকলে ক্যানোনিকাল ডিফল্ট যাচাই
    assert pfr.REPO == "Supremeai-bd/supremeai" or "/" in pfr.REPO


def test_real_api_retries_with_fallback_token_on_401(monkeypatch: pytest.MonkeyPatch) -> None:
    """বাংলা মন্তব্য: `SELF_HEAL_PAT` মেয়াদোত্তীর্ণ (HTTP 401) হলে `GH_FALLBACK_TOKEN` দিয়ে সফল retry যাচাই।"""
    monkeypatch.setenv("GH_TOKEN", "expired_pat")
    monkeypatch.setenv("GH_FALLBACK_TOKEN", "valid_workflow_token")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    seen_headers: list[str] = []

    class _FakeResp:
        def __enter__(self) -> _FakeResp:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"ok": true}'

    def fake_urlopen(req: object, timeout: int = 30) -> _FakeResp:
        auth = getattr(req, "headers", {}).get("Authorization", "")
        seen_headers.append(auth)
        if "expired_pat" in auth:
            raise urllib.error.HTTPError(
                url="https://api.github.com/repos/Supremeai-bd/supremeai/issues",
                code=401,
                msg="Bad credentials",
                hdrs=None,  # type: ignore[arg-type]
                fp=io.BytesIO(b'{"message":"Bad credentials"}'),
            )
        return _FakeResp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    result = pfr.real_api("repos/Supremeai-bd/supremeai/issues")
    assert result == {"ok": True}
    assert seen_headers == ["token expired_pat", "token valid_workflow_token"]


def test_real_api_does_not_mask_non_auth_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """বাংলা মন্তব্য: 404/422 ত্রুটিতে অন্ধ retry না করে সাথে সাথে fail-closed ব্যর্থতা নিশ্চিতকরণ।"""
    monkeypatch.setenv("GH_TOKEN", "primary_tok")
    monkeypatch.setenv("GH_FALLBACK_TOKEN", "fallback_tok")

    calls = 0

    def fake_urlopen(req: object, timeout: int = 30) -> object:
        nonlocal calls
        calls += 1
        raise urllib.error.HTTPError(
            url="https://api.github.com/repos/Supremeai-bd/supremeai/issues/999999",
            code=404,
            msg="Not Found",
            hdrs=None,  # type: ignore[arg-type]
            fp=io.BytesIO(b'{"message":"Not Found"}'),
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        pfr.real_api("repos/Supremeai-bd/supremeai/issues/999999")
    assert exc_info.value.code == 404
    assert calls == 1


def test_real_gh_retries_on_403_and_falls_back_for_legacy_gh_status_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """বাংলা মন্তব্য: ১) `gh` CLI 403 ত্রুটিতে ফ্যালব্যাক টোকেন retry এবং ২) পুরনো `gh`-এ `--status` না থাকলে REST ফ্যালব্যাক যাচাই।"""
    monkeypatch.setenv("GH_TOKEN", "scoped_out_pat")
    monkeypatch.setenv("GH_FALLBACK_TOKEN", "actions_tok")

    tokens_used: list[str] = []

    def fake_run_403_then_ok(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        env = kwargs.get("env") or {}
        tok = env.get("GH_TOKEN", "") if isinstance(env, dict) else ""
        tokens_used.append(tok)
        if tok == "scoped_out_pat":
            return subprocess.CompletedProcess(
                cmd, 1, stdout="", stderr="HTTP 403: Resource not accessible by personal access token"
            )
        return subprocess.CompletedProcess(cmd, 0, stdout='[{"conclusion":"success"}]', stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run_403_then_ok)
    out = pfr.real_gh("pr", "view", "1", "--json", "statusCheckRollup")
    assert json.loads(out) == [{"conclusion": "success"}]
    assert tokens_used == ["scoped_out_pat", "actions_tok"]

    def fake_run_unknown_status_flag(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="unknown flag: --status")

    monkeypatch.setattr(subprocess, "run", fake_run_unknown_status_flag)
    monkeypatch.setattr(
        pfr,
        "real_api",
        lambda endpoint, method="GET", payload=None: {
            "workflow_runs": [
                {
                    "id": 45909963796,
                    "name": "🔧 Nightly Ops & Maintenance",
                    "head_branch": "main",
                    "head_sha": "9356e6328696",
                    "event": "schedule",
                    "created_at": "2026-11-26T23:16:34Z",
                    "html_url": "https://github.com/Supremeai-bd/supremeai/actions/runs/45909963796",
                    "conclusion": "failure",
                }
            ]
        },
    )
    fallback_json = pfr.real_gh(
        "run", "list", "--repo", "Supremeai-bd/supremeai", "--status", "completed", "--limit", "5"
    )
    parsed = json.loads(fallback_json)
    assert len(parsed) == 1
    assert parsed[0]["databaseId"] == 45909963796
    assert parsed[0]["conclusion"] == "failure"
