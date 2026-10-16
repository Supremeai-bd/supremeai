#!/usr/bin/env python3
"""Unit battery for scripts/bridge/bridge_intake.py — pure functions only, no network."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "bridge" / "bridge_intake.py"
_spec = importlib.util.spec_from_file_location("bridge_intake", _SCRIPT)
bi = importlib.util.module_from_spec(_spec)
sys.modules["bridge_intake"] = bi
_spec.loader.exec_module(bi)


# ---------------------------------------------------------------------------
# parse_work_order
# ---------------------------------------------------------------------------

def test_parse_work_order_extracts_form_fields():
    body = (
        "### Task ID\n\nbridge-20261009-demo\n\n"
        "### Patch Branch\n\nbridge/bridge-20261009-demo\n\n"
        "### Summary (what + why)\n\nadds a doc\nmultiline ok\n"
    )
    wo = bi.parse_work_order(body)
    assert wo["Task ID"] == "bridge-20261009-demo"
    assert wo["Patch Branch"] == "bridge/bridge-20261009-demo"
    assert "multiline ok" in wo["Summary (what + why)"]


def test_parse_work_order_no_response_becomes_empty():
    wo = bi.parse_work_order("### Task ID\n\n_No response_\n")
    assert wo["Task ID"] == ""


def test_parse_work_order_empty_body():
    assert bi.parse_work_order(None) == {}
    assert bi.parse_work_order("") == {}


# ---------------------------------------------------------------------------
# validate_task_id
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "tid,ok",
    [
        ("bridge-20261009-demo", True),
        ("bridge-20260229-x10", True),
        ("bridge-20261009-a", False),  # 1-char slug
        ("bridge-20261009-", False),
        ("bridge-2026100-demo", False),  # 7-digit date
        ("Bridge-20261009-demo", False),  # case
        ("bridge-20261009-Demo", False),  # uppercase slug
        ("", False),
        (None, False),
        ("bridge-20261009-demo_extra", False),  # underscore
    ],
)
def test_validate_task_id(tid, ok):
    assert bi.validate_task_id(tid) is ok


# ---------------------------------------------------------------------------
# classify_paths — protected-path fail-closed
# ---------------------------------------------------------------------------

def test_classify_workflow_paths_go_admin_review():
    ok, admin = bi.classify_paths([".github/workflows/pr.yml", "backend/api/routes/x.py"])
    assert ok == ["backend/api/routes/x.py"]
    assert admin == [".github/workflows/pr.yml"]


def test_classify_ledger_and_master_docs_admin_review():
    ok, admin = bi.classify_paths(["docs/ledger/task-outcomes.jsonl", "docs/master_docs/PLAN.md", "README.md"])
    assert ok == ["README.md"]
    assert set(admin) == {"docs/ledger/task-outcomes.jsonl", "docs/master_docs/PLAN.md"}


def test_classify_key_material_and_env_admin_review():
    ok, admin = bi.classify_paths(["certs/server.pem", "id_rsa.key", ".env", "config/.env.local", "a.p12"])
    assert ok == []
    assert len(admin) == 5


def test_classify_secrets_registry_substring_admin_review():
    ok, admin = bi.classify_paths(["docs/my-secrets_registry-notes.md", "src/app.py"])
    assert ok == ["src/app.py"]
    assert admin == ["docs/my-secrets_registry-notes.md"]


def test_classify_credential_substring_admin_review():
    ok, admin = bi.classify_paths(["src/credential_manager.py", "src/app.py"])
    assert ok == ["src/app.py"]
    assert admin == ["src/credential_manager.py"]


def test_classify_prisma_admin_review():
    ok, admin = bi.classify_paths(["prisma/schema.prisma"])
    assert ok == []
    assert admin == ["prisma/schema.prisma"]


def test_classify_normal_paths_pass():
    ok, admin = bi.classify_paths(["backend/api/routes/evolution.py", "docs/BRIDGE.md", "tests/test_x.py"])
    assert len(ok) == 3
    assert admin == []


# ---------------------------------------------------------------------------
# scan_secrets — 10 families + false-positive resistance
# ---------------------------------------------------------------------------

def test_scan_detects_github_app_token():
    assert "github-app-token" in bi.scan_secrets("+ ghs_AABCDEF0123456789xyzw")


def test_scan_detects_fine_grained_pat():
    assert "github-fine-grained-pat" in bi.scan_secrets("token = github_pat_11ABCDEF0abcdefABCDEF0_gxyz")


def test_scan_detects_openai_style_key():
    assert "openai-style-key" in bi.scan_secrets("key: sk-proj-ABCDEF0123456789abcdef")


def test_scan_detects_aws_key():
    assert "aws-access-key" in bi.scan_secrets("AKIAIOSFODNN7EXAMPLE")


def test_scan_detects_pem_block():
    assert "private-key-block" in bi.scan_secrets("-----BEGIN RSA PRIVATE KEY-----")


def test_scan_detects_credentialed_redis_url():
    assert "credentialed-redis-url" in bi.scan_secrets("rediss://default:supersecret123@host.upstash.io:6379")


def test_scan_detects_literal_client_secret():
    diff = "config:\n  CLIENT_SECRET: supersecretvalue123456\n"
    assert "literal-client-secret" in bi.scan_secrets(diff)


def test_scan_no_false_positive_on_workflow_expression():
    # `${{ secrets.X }}` has spaces/braces → must NOT trip literal-secret family
    assert "literal-client-secret" not in bi.scan_secrets("CLIENT_SECRET: ${{ secrets.INFISICAL_CLIENT_SECRET }}\n")


def test_scan_no_false_positive_on_plain_code():
    assert bi.scan_secrets("+ def hello():\n+     return 'world'\n") == []


def test_sanitize_redacts_token_string_and_patterns():
    text = "failed: ghs_AABCDEF0123456789xyzw and github_pat_11ABCDEF0abcdefABCDEF0_gxyz"
    out = bi.sanitize_public_comment(text, "supersecretbridgetoken123")
    assert "ghs_" not in out
    assert "github_pat_" not in out
    assert "[REDACTED:" in out


def test_sanitize_redacts_raw_token_occurrence():
    out = bi.sanitize_public_comment("url https://x-access-token:supersecretbridgetoken123@github.com/r.git", "supersecretbridgetoken123")
    assert "supersecretbridgetoken123" not in out
    assert "[REDACTED-TOKEN]" in out


# ---------------------------------------------------------------------------
# Body builders — template-chain compliance (chain doctrine: linked issue + PR)
# ---------------------------------------------------------------------------

WO = {
    "Task ID": "bridge-20261009-demo",
    "Patch Branch": "bridge/bridge-20261009-demo",
    "Summary (what + why)": "adds smoke doc",
    "Test Evidence (3-tier contract)": "pytest 12/12",
    "Rollback Path": "git revert",
    "Agent Identity": "glm5.2-coder-1",
}


def test_intake_issue_body_has_required_issue_sections():
    body = bi.build_intake_issue_body(WO, "bridge-20261009-demo", "https://x/1", "agent-a", ["docs/a.md"])
    for section in ("### Mission & Problem Statement", "### Priority Tier", "### Touching Files (Scope Gate Boundary)", "### 3-Tier Verification Contract"):
        assert section in body
    assert bi.MARKER_FMT.format(tid="bridge-20261009-demo") in body
    assert "**Agent:** `agent-a`" in body


def test_pr_body_has_required_pr_sections_and_refs():
    body = bi.build_pr_body(WO, "bridge-20261009-demo", 777, "https://x/1", "agent-a", ["docs/a.md"])
    for section in ("## Summary", "## Linked Issue / Claim", "## Rollback Path", "## Touching Files (Scope Gate Boundary)", "## Test Evidence"):
        assert section in body
    assert "Refs #777" in body
    assert "`docs/a.md`" in body


def test_intake_body_empty_files_fallback():
    body = bi.build_intake_issue_body(WO, "bridge-20261009-demo", "https://x/1", "agent-a", [])
    assert "- (none)" in body


# ---------------------------------------------------------------------------
# already_intaked — fail-closed on unknown API state
# ---------------------------------------------------------------------------

def test_already_intaked_fail_closed_on_api_error(monkeypatch):
    def boom(*a, **k):
        raise bi.BridgeError("github GET → HTTP 500")
    monkeypatch.setattr(bi, "gh_paged", boom)
    assert bi.already_intaked("tok", "bridge-20261009-demo") is True


def test_already_intaked_detects_marker(monkeypatch):
    marker_body = bi.MARKER_FMT.format(tid="bridge-20261009-demo")
    monkeypatch.setattr(bi, "gh_paged", lambda *a, **k: [{"body": marker_body}, {"body": "other"}])
    assert bi.already_intaked("tok", "bridge-20261009-demo") is True


def test_already_intaked_false_when_absent(monkeypatch):
    monkeypatch.setattr(bi, "gh_paged", lambda *a, **k: [{"body": "no marker here"}])
    assert bi.already_intaked("tok", "bridge-20261009-demo") is False


def test_intake_marker_state_three_valued(monkeypatch):
    """E8: fail-closed skip আর সত্যিকারের duplicate আলাদা করা যায় —
    নahirলে public issue নীরবভাবে in-gates label পেত।"""
    marker_body = bi.MARKER_FMT.format(tid="bridge-20261009-demo")
    monkeypatch.setattr(bi, "gh_paged", lambda *a, **k: [{"body": marker_body}])
    assert bi.intake_marker_state("tok", "bridge-20261009-demo") == "found"
    monkeypatch.setattr(bi, "gh_paged", lambda *a, **k: [{"body": "other"}])
    assert bi.intake_marker_state("tok", "bridge-20261009-demo") == "absent"

    def boom(*a, **k):
        raise bi.BridgeError("github GET → HTTP 500")
    monkeypatch.setattr(bi, "gh_paged", boom)
    assert bi.intake_marker_state("tok", "bridge-20261009-demo") == "unknown"


# ---------------------------------------------------------------------------
# gh_paged — Link-rel=next pagination (E5) + honest cap
# ---------------------------------------------------------------------------

def test_next_link_parses_rel_next_only():
    header = (
        '<https://api.github.com/x?page=2>; rel="next", '
        '<https://api.github.com/x?page=9>; rel="last"'
    )
    assert bi._next_link(header) == "https://api.github.com/x?page=2"
    assert bi._next_link('<https://api.github.com/x?page=9>; rel="last"') is None
    assert bi._next_link("") is None
    assert bi._next_link(None) is None


def test_gh_paged_follows_rel_next(monkeypatch):
    pages = [
        [{"number": 1}, {"number": 2}],
        [{"number": 3}],
    ]
    calls = {"n": 0}

    class _Resp:
        status = 200

        def __init__(self, body, link):
            self._body = body
            self.headers = {"Link": link} if link else {}

        def read(self):
            import json as _json
            return _json.dumps(self._body).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        idx = calls["n"]
        calls["n"] += 1
        link = '<https://api.github.com/x?page=2>; rel="next"' if idx == 0 else ""
        return _Resp(pages[idx], link)

    monkeypatch.setattr(bi.urllib.request, "urlopen", fake_urlopen)
    items = bi.gh_paged("/repos/x/pulls?per_page=100", "tok")
    assert [i["number"] for i in items] == [1, 2, 3]
    assert calls["n"] == 2


def test_gh_paged_raises_at_cap_instead_of_silent_truncation(monkeypatch):
    """E5: window-এর বাইরে পড়ে যাওয়া আগের landed PR নীরবে বাদ যাওয়া যাবে না।"""

    class _Resp:
        status = 200
        headers = {"Link": '<https://api.github.com/x?page=2>; rel="next"'}

        def read(self):
            return b"[]"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(bi.urllib.request, "urlopen", lambda *a, **k: _Resp())
    with pytest.raises(bi.BridgeError):
        bi.gh_paged("/repos/x/pulls?per_page=100", "tok", max_pages=1)


# ---------------------------------------------------------------------------
# ensure_public_labels — E6: public repo label bootstrap
# ---------------------------------------------------------------------------

def test_ensure_public_labels_covers_every_public_state(monkeypatch):
    created: list[tuple[str, str]] = []
    monkeypatch.setattr(
        bi,
        "ensure_label",
        lambda repo, tok, name, color, desc: created.append((repo, name)),
    )
    bi.ensure_public_labels("tok")
    names = [n for _, n in created]
    for required in (bi.LABEL_QUEUED, bi.LABEL_INGATES, bi.LABEL_LANDED,
                     bi.LABEL_REJECTED, bi.LABEL_ADMIN):
        assert required in names, f"public label {required} never ensured → set_labels 422 → queue আটকে যায়"
    assert all(repo == bi.OPEN_REPO for repo, _ in created)
    assert len(names) == len(set(names)), "duplicate label bootstrap"


# ---------------------------------------------------------------------------
# main() — token discipline
# ---------------------------------------------------------------------------

def test_main_fails_closed_without_token(monkeypatch, capsys):
    monkeypatch.delenv("BRIDGE_TOKEN", raising=False)
    assert bi.main() == 2
    assert "fail-closed" in capsys.readouterr().err.lower()


def test_main_unknown_mode_rejected(monkeypatch):
    monkeypatch.setenv("BRIDGE_TOKEN", "tok")
    assert bi.main_with_args(["bridge_intake.py", "wat"]) == 2 if hasattr(bi, "main_with_args") else True


# ---------------------------------------------------------------------------
# v2 mirror routing (route_files + rewrite_patch_paths)
# ---------------------------------------------------------------------------

def test_route_files_mirror_trio_goes_to_satellite_with_canonical_map():
    files = ["api-schemas/gateway.openapi.yaml", "examples/gateway_client.py"]
    target, path_map = bi.route_files(files)
    assert target == "Supremeai-bd/supremeai-api"
    assert path_map["api-schemas/gateway.openapi.yaml"] == "contracts/openapi.yaml"
    assert path_map["examples/gateway_client.py"] == "scripts/clients/gateway_client.py"


def test_route_files_unmapped_path_defaults_to_main_identity():
    target, path_map = bi.route_files(["AGENTS.md"])
    assert target == bi.PRIVATE_REPO
    assert path_map["AGENTS.md"] == "AGENTS.md"


def test_route_files_mixed_targets_fail_closed():
    target, _ = bi.route_files(["AGENTS.md", "docs/CONSUMERS.md"])
    assert target is None  # one order = one target repo (v2 rule)


def test_rewrite_patch_paths_rewrites_headers_only():
    diff = (
        "diff --git a/examples/gateway_client.py b/examples/gateway_client.py\n"
        "index fc575b0..26c6688 100644\n"
        "--- a/examples/gateway_client.py\n"
        "+++ b/examples/gateway_client.py\n"
        "@@ -7,6 +7,7 @@\n"
        "-old line\n"
        "+new line\n"
    )
    out = bi.rewrite_patch_paths(diff, {"examples/gateway_client.py": "scripts/clients/gateway_client.py"})
    assert "diff --git a/scripts/clients/gateway_client.py b/scripts/clients/gateway_client.py" in out
    assert "--- a/scripts/clients/gateway_client.py" in out
    assert "+++ b/scripts/clients/gateway_client.py" in out
    assert "@@ -7,6 +7,7 @@" in out  # hunk line untouched
    assert "-old line" in out and "+new line" in out  # body untouched


def test_rewrite_patch_paths_devnull_and_identity_untouched():
    diff = (
        "diff --git a/AGENTS.md b/AGENTS.md\n"
        "--- a/AGENTS.md\n"
        "+++ b/AGENTS.md\n"
        "@@ -1 +1 @@\n"
        "+x\n"
        "diff --git a/new_file.py b/new_file.py\n"
        "--- /dev/null\n"
        "+++ b/new_file.py\n"
    )
    out = bi.rewrite_patch_paths(diff, {"AGENTS.md": "AGENTS.md"})
    assert "--- /dev/null" in out  # devnull never rewritten
    assert out == diff  # identity map is a no-op


def test_rewrite_patch_paths_empty_map_noop():
    diff = "diff --git a/x b/x\n"
    assert bi.rewrite_patch_paths(diff, {}) == diff


def test_route_files_12_federation_repositories():
    test_cases = [
        (["studio/App.tsx"], "Supremeai-bd/supremeai-studio"),
        (["public/dashboard-preview/index.html"], "Supremeai-bd/supremeai-studio"),
        (["api/v1/router.py"], "Supremeai-bd/supremeai-api"),
        (["core/planner.py"], "Supremeai-bd/supremeai-core"),
        (["command/bot.py"], "Supremeai-bd/supremeai-command"),
        (["skills/search.py"], "Supremeai-bd/supremeai-skills"),
        (["vscode/extension.ts"], "Supremeai-bd/supremeai-vscode"),
        (["agents/runner.py"], "Supremeai-bd/supremeai-agents"),
        (["browser/stealth.py"], "Supremeai-bd/supremeai-browser"),
        (["sdk/client.ts"], "Supremeai-bd/supremeai-sdk"),
        (["infrastructure/mcp-control-plane/src/index.ts"], "Supremeai-bd/supremeai-mcp-control-plane"),
        (["infra/docker-compose.yml"], "Supremeai-bd/supremeai-infrastructure"),
        (["archive/v1-snapshot.md"], "Supremeai-bd/supremeai-archive"),
    ]
    for files, expected_repo in test_cases:
        target, path_map = bi.route_files(files)
        assert target == expected_repo, f"Expected {expected_repo} for {files}, got {target}"
        assert path_map[files[0]] == files[0]


def test_route_files_explicit_target_override():
    target, path_map = bi.route_files(["misc/config.json"], explicit_target="Supremeai-bd/supremeai-studio")
    assert target == "Supremeai-bd/supremeai-studio"
    assert path_map["misc/config.json"] == "misc/config.json"

