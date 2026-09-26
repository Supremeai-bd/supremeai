"""Root acceptance tests for issue #1575 — Part 6: Git Verifier internals
(worktree mechanics, default check wiring) — complements
``tests/test_artifact_bridge.py`` which covers the bounded repair loop and
the PR lifecycle end-to-end.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from external_agents.verification.artifact_bridge import ArtifactBridge
from external_agents.verification.git_verifier import (
    CheckResult,
    GitVerifier,
    default_checks,
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout


@pytest.fixture()
def repo(tmp_path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "agent@example.com")
    _git(repo, "config", "user.name", "Agent")
    (repo / "pkg.py").write_text("X = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    _git(repo, "checkout", "-q", "-b", "task/verify-me")
    (repo / "pkg.py").write_text("X = 2\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "change")
    _git(
        repo, "checkout", "-q", "main"
    )  # keep main checked out — worktree add refuses otherwise
    return repo


def test_worktree_created_and_removed_around_verification(repo):
    observed = {}

    def probe(worktree: Path) -> CheckResult:
        observed["exists_during"] = worktree.exists()
        observed["content"] = (worktree / "pkg.py").read_text()
        return CheckResult(name="probe", passed=True)

    verifier = GitVerifier(repo_root=repo, checks=[probe], worktree_parent=repo.parent)
    artifact = ArtifactBridge(repo_root=repo).extract_artifact(
        "t", "task/verify-me", "main"
    )
    report = verifier.verify(artifact)

    assert report.status == "PASS"
    assert observed["exists_during"] is True
    assert observed["content"] == "X = 2\n", "worktree holds the BRANCH content"
    # after verification: worktree gone + git worktree list clean
    worktrees = _git(repo, "worktree", "list")
    assert "verify-" not in worktrees, "worktree must be pruned after verification"
    assert (repo / "pkg.py").read_text() == "X = 1\n", "main worktree untouched"


def test_default_checks_wiring():
    checks = default_checks()
    assert len(checks) == 2  # pytest + ruff
    # verify the commands they build reference pytest & ruff (smoke: inspect names)
    import inspect

    src = inspect.getsource(checks[0])
    assert "pytest" in src
    src2 = inspect.getsource(checks[1])
    assert "ruff" in src2


def test_missing_branch_reports_setup_failure_honestly(repo):
    def never(worktree: Path) -> CheckResult:  # pragma: no cover
        return CheckResult(name="x", passed=True)

    verifier = GitVerifier(repo_root=repo, checks=[never], worktree_parent=repo.parent)
    artifact = ArtifactBridge(repo_root=repo).extract_artifact(
        "t", "task/verify-me", "main"
    )
    artifact.branch = "task/does-not-exist"
    report = verifier.verify(artifact)

    assert report.status == "FAILED"
    assert report.failure_contexts[0].stage == "setup"
    assert "worktree add failed" in report.failure_contexts[0].summary
