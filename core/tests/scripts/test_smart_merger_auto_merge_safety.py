# বাংলা মন্তব্য: Issue #2630 — ১০০% নিরাপদ auto-merge চুক্তির গার্ড টেস্ট।
"""Regression tests for the safe auto-merge contract (#2630).

মূল চুক্তি: **অটোমেশন নিজের নিয়ম নিজে বদলাতে পারবে না** — protected-paths
গার্ড সব-সবুজ PR-কেও আটকাবে যদি সেটি `.github/workflows/**`, constitution,
gate-script বা merge-policy স্পর্শ করে (privilege-escalation প্রতিরোধ)। সাথে
বিদ্যমান গেট-রোলআপ চুক্তি (#2571) অক্ষত থাকা যাচাই।

মডিউলটি import-সময়ে শুধু stdlib ব্যবহার করে (নেটওয়ার্ক/gh CLI নয়) — তাই
importlib-লোড নিরাপদ; `--noconftest` সামঞ্জস্যপূর্ণ (#2620 প্যাটার্ন)।
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

MERGER_PATH = Path(__file__).resolve().parents[3] / "scripts" / "ci" / "smart_priority_merger.py"

_EVIDENCE_BODY = (
    "## Test Evidence\n\n"
    "```\n"
    "python3 -m pytest backend/tests/scripts/test_smart_merger_auto_merge_safety.py\n"
    "→ 10 passed in 2.00s (exit=0)\n"
    "```\n"
)


def _load_merger_module() -> Any:
    spec = importlib.util.spec_from_file_location("smart_priority_merger_under_test", MERGER_PATH)
    assert spec and spec.loader, "merger module spec লোড ব্যর্থ"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mod = _load_merger_module()


def _pr(
    files: list[str],
    labels: tuple[str, ...] = ("queue:hold",),
    rollup: list[dict[str, Any]] | None = None,
    body: str = _EVIDENCE_BODY,
    mergeable: str = "MERGEABLE",
) -> dict[str, Any]:
    """সব-সবুজ ডিফল্টসহ ন্যূনতম PR fixture।"""
    if rollup is None:
        rollup = [{"name": name, "conclusion": "SUCCESS"} for name in mod._DEFAULT_REQUIRED_CHECKS]
    return {
        "number": 1,
        "title": "fix(backend): t",
        "author": {"login": "someone"},
        "labels": [{"name": label} for label in labels],
        "mergeable": mergeable,
        "isDraft": False,
        "body": body,
        "files": [{"path": path} for path in files],
        "statusCheckRollup": rollup,
    }


# ── find_protected_path_hits (pure) ──────────────────────────────────────────


def test_workflow_path_is_protected() -> None:
    hits = mod.find_protected_path_hits(
        [".github/workflows/deploy-train.yml", "backend/app.py"],
        mod._PROTECTED_PATHS,
    )
    assert hits == [".github/workflows/deploy-train.yml"]


def test_constitution_and_policy_paths_are_protected() -> None:
    hits = mod.find_protected_path_hits(
        [
            ".github/constitution/rules.yml",
            "config/merge_policy_registry.json",
            "AGENTS.md",
        ],
        mod._PROTECTED_PATHS,
    )
    assert len(hits) == 3


def test_normal_code_paths_are_not_protected() -> None:
    hits = mod.find_protected_path_hits(
        ["backend/core/service.py", "frontend/src/App.tsx", "docs/README.md"],
        mod._PROTECTED_PATHS,
    )
    assert hits == []


def test_matching_is_case_insensitive() -> None:
    hits = mod.find_protected_path_hits([".GitHub/Workflows/ci.yml"], [".github/workflows/*"])
    assert hits == [".GitHub/Workflows/ci.yml"]


def test_empty_inputs_are_safe() -> None:
    assert mod.find_protected_path_hits([], mod._PROTECTED_PATHS) == []
    assert mod.find_protected_path_hits(["backend/app.py"], []) == []


# ── _load_protected_paths (registry override ও fallback) ─────────────────────


def test_registry_override_loads(tmp_path: Path) -> None:
    fake_root = tmp_path / "repo"
    (fake_root / "config").mkdir(parents=True)
    (fake_root / "config" / "merge_policy_registry.json").write_text(
        '{"auto_merge": {"protected_paths": ["secret/*.key"]}}', encoding="utf-8"
    )
    original = mod.REPO_ROOT
    try:
        mod.REPO_ROOT = fake_root
        assert mod._load_protected_paths() == ["secret/*.key"]
    finally:
        mod.REPO_ROOT = original


def test_fallback_when_registry_missing(tmp_path: Path) -> None:
    original = mod.REPO_ROOT
    try:
        mod.REPO_ROOT = tmp_path  # config ফাইল নেই
        assert mod._load_protected_paths() == list(mod._PROTECTED_PATHS_FALLBACK)
    finally:
        mod.REPO_ROOT = original


# ── evaluate_pr_checks ইন্টিগ্রেশন ───────────────────────────────────────────


def test_all_green_non_protected_pr_is_ready_with_holds_allowed() -> None:
    summary, is_ready, _held, evidence, reasons = mod.evaluate_pr_checks(
        _pr(["backend/core/service.py", "frontend/src/x.tsx"]), allow_holds=True
    )
    assert is_ready is True, reasons
    assert evidence.startswith("PASS")
    assert reasons == []
    assert summary == "GREEN"


def test_all_green_but_protected_path_blocks_merge() -> None:
    summary, is_ready, _held, _evidence, reasons = mod.evaluate_pr_checks(
        _pr([".github/workflows/deploy-train.yml"]), allow_holds=True
    )
    assert is_ready is False
    assert summary == "PROTECTED_PATHS"
    assert any("Protected paths" in reason for reason in reasons)


def test_held_pr_still_blocked_without_allow_holds() -> None:
    _summary, is_ready, held, _evidence, reasons = mod.evaluate_pr_checks(
        _pr(["backend/app.py"]), allow_holds=False
    )
    assert held is True
    assert is_ready is False
    assert any("queue:hold active" in reason for reason in reasons)


def test_failing_gate_still_blocks() -> None:
    rollup = [{"name": name, "conclusion": "SUCCESS"} for name in mod._DEFAULT_REQUIRED_CHECKS]
    rollup[0]["conclusion"] = "FAILURE"
    _summary, is_ready, _held, _evidence, reasons = mod.evaluate_pr_checks(
        _pr(["backend/app.py"], rollup=rollup), allow_holds=True
    )
    assert is_ready is False
    assert any("CI Failing" in reason for reason in reasons)


def test_missing_evidence_still_blocks() -> None:
    _summary, is_ready, _held, _evidence, reasons = mod.evaluate_pr_checks(
        _pr(["backend/app.py"], body="just a description, no evidence"),
        allow_holds=True,
    )
    assert is_ready is False
    assert any("Evidence" in reason for reason in reasons)
