"""Root acceptance tests for issue #1575 — Part 6: Artifact Bridge & Git Verifier.

Covers (per the issue's acceptance criteria):
* Artifact bridge extracts REAL git commits, patch diffs, branch references
  and changed-file lists from completed coder jobs.
* Resource boundary validation — files outside the declared task scope fail.
* Git verification runs inside an ISOLATED worktree — the main working
  directory is never touched.
* Test failures trigger a structured FailureContext feedback loop that is
  HARD-BOUNDED (max 3 repair rounds) — no runaway retry loops.
* PR lifecycle: atomic PR only after verification PASS; ownership lock released.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from external_agents.contracts.code_artifact import CodeArtifact
from external_agents.control.state_manager import AgentStateManager, InMemoryStore
from external_agents.verification.artifact_bridge import ArtifactBridge
from external_agents.verification.git_verifier import (
    CheckResult,
    FailureContext,
    GitVerifier,
)
from external_agents.verification.pr_manager import OwnershipLocks, PrManager


# ---------------------------------------------------------------------------
# Helpers — a real throwaway git repository
# ---------------------------------------------------------------------------
def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )
    return result.stdout


@pytest.fixture()
def repo(tmp_path) -> Path:
    """A real git repo: main with one commit + a task branch with 2 changes."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "agent@example.com")
    _git(repo, "config", "user.name", "Agent")
    (repo / "backend").mkdir()
    (repo / "backend" / "core.py").write_text("VALUE = 1\n")
    (repo / "backend" / "helpers.py").write_text("def help():\n    return 0\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "initial")
    _git(repo, "checkout", "-q", "-b", "task/widget")
    (repo / "backend" / "widget.py").write_text("WIDGET = 'new'\n")
    (repo / "backend" / "core.py").write_text("VALUE = 2\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "feat: widget implementation")
    # leave main checked out in the main worktree — git refuses to add a
    # worktree for a branch that is already checked out elsewhere
    _git(repo, "checkout", "-q", "main")
    return repo


@pytest.fixture()
def artifact(repo) -> CodeArtifact:
    bridge = ArtifactBridge(repo_root=repo)
    return bridge.extract_artifact(
        task_id="task-widget",
        branch="task/widget",
        base="main",
        allowed_roots=["backend"],
    )


# ---------------------------------------------------------------------------
# 1. Artifact bridge — real git extraction
# ---------------------------------------------------------------------------
def test_bridge_extracts_real_changeset(artifact):
    assert artifact.commit_sha
    assert artifact.branch == "task/widget"
    paths = artifact.touched_paths()
    assert "backend/widget.py" in paths  # added
    assert "backend/core.py" in paths  # modified
    widget = next(f for f in artifact.changed_files if f.path == "backend/widget.py")
    assert widget.change_type == "A"
    core = next(f for f in artifact.changed_files if f.path == "backend/core.py")
    assert core.change_type == "M" and core.additions == 1 and core.deletions == 1
    assert "WIDGET = 'new'" in artifact.diff, "real patch diff must be captured"
    assert artifact.extra["boundary_ok"] is True


def test_bridge_boundary_violation_detected(repo):
    # agent also modified a file OUTSIDE the declared scope (on the task branch)
    _git(repo, "checkout", "-q", "task/widget")
    (repo / "frontend").mkdir(exist_ok=True)
    (repo / "frontend" / "leak.js").write_text("console.log('oops')\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "scope leak")
    _git(repo, "checkout", "-q", "main")
    bridge = ArtifactBridge(repo_root=repo)
    artifact = bridge.extract_artifact(
        task_id="task-widget",
        branch="task/widget",
        base="main",
        allowed_roots=["backend"],
    )
    assert artifact.extra["boundary_ok"] is False
    assert artifact.extra["boundary_offenders"] == ["frontend/leak.js"]
    report = bridge.validate_boundaries(artifact, ["backend"])
    assert report.ok is False
    assert report.offending_files == ["frontend/leak.js"]


def test_bridge_missing_branch_fails_honestly(repo):
    bridge = ArtifactBridge(repo_root=repo)
    with pytest.raises(RuntimeError):
        bridge.extract_artifact(task_id="t", branch="task/ghost", base="main")


# ---------------------------------------------------------------------------
# 2. Git verifier — isolated worktree + bounded repair loop
# ---------------------------------------------------------------------------
def _pass_check(worktree: Path) -> CheckResult:
    return CheckResult(name="pytest", passed=True, exit_code=0)


def test_worktree_isolates_verification_from_main_workdir(repo):
    sentinel = repo / "backend" / "core.py"
    original = sentinel.read_text()
    seen = {}

    def probe(worktree: Path) -> CheckResult:
        seen["worktree_path"] = str(worktree)
        seen["worktree_is_main"] = worktree.resolve() == repo.resolve()
        # the worktree shows the BRANCH content, the main dir stays on main
        seen["worktree_value"] = (worktree / "backend" / "widget.py").read_text()
        seen["main_value"] = sentinel.read_text()
        return CheckResult(name="pytest", passed=True)

    verifier = GitVerifier(repo_root=repo, checks=[probe], worktree_parent=repo.parent)
    artifact = ArtifactBridge(repo_root=repo).extract_artifact(
        "t", "task/widget", "main"
    )
    report = verifier.verify(artifact)

    assert report.status == "PASS"
    assert seen["worktree_is_main"] is False, (
        "verification must run in an isolated worktree"
    )
    assert "WIDGET" in seen["worktree_value"]
    assert not (repo / "backend" / "widget.py").exists(), "main working dir untouched"
    assert sentinel.read_text() == original
    assert report.worktree_path is None or not Path(seen["worktree_path"]).exists(), (
        "worktree cleaned up"
    )


def test_failure_triggers_structured_feedback_and_repair(repo):
    calls = {"checks": 0, "repairs": 0}

    def flaky_check(worktree: Path) -> CheckResult:
        calls["checks"] += 1
        # fails on round 1, passes after the repair lands
        return CheckResult(
            name="pytest",
            passed=calls["checks"] > 1,
            exit_code=0 if calls["checks"] > 1 else 1,
            output=""
            if calls["checks"] > 1
            else "FAILED tests/test_widget.py::test_it",
        )

    def repair(context: FailureContext) -> None:
        calls["repairs"] += 1
        assert context.stage == "tests"
        assert context.attempt == 1
        assert "test_widget" in context.output_tail

    verifier = GitVerifier(
        repo_root=repo, checks=[flaky_check], worktree_parent=repo.parent
    )
    artifact = ArtifactBridge(repo_root=repo).extract_artifact(
        "t", "task/widget", "main"
    )
    report = verifier.verify(artifact, repair_fn=repair)

    assert report.status == "PASS"
    assert calls["repairs"] == 1
    assert report.rounds_used == 2
    assert len(report.failure_contexts) == 1
    assert report.failure_contexts[0].task_id == "t"


def test_repair_loop_is_bounded_at_three_rounds(repo):
    def always_fails(worktree: Path) -> CheckResult:
        return CheckResult(
            name="pytest", passed=False, exit_code=1, output="still broken"
        )

    repairs = {"count": 0}

    def repair(context: FailureContext) -> None:
        repairs["count"] += 1

    verifier = GitVerifier(
        repo_root=repo,
        checks=[always_fails],
        worktree_parent=repo.parent,
        max_repair_rounds=3,
    )
    artifact = ArtifactBridge(repo_root=repo).extract_artifact(
        "t", "task/widget", "main"
    )
    report = verifier.verify(artifact, repair_fn=repair)

    assert report.status == "FAILED"
    assert report.rounds_used == 4  # initial + 3 bounded repairs
    assert repairs["count"] == 3, (
        "repair loop must be hard-bounded at max_repair_rounds"
    )
    assert len(report.failure_contexts) == 4
    assert report.failure_contexts[-1].attempt == 4


def test_boundary_failure_blocks_verification_before_checks(repo):
    checked = {"called": False}

    def spy(worktree: Path) -> CheckResult:
        checked["called"] = True
        return CheckResult(name="pytest", passed=True)

    # leak a file outside backend scope (on the task branch)
    _git(repo, "checkout", "-q", "task/widget")
    (repo / "frontend").mkdir(exist_ok=True)
    (repo / "frontend" / "leak.js").write_text("x\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "leak")
    _git(repo, "checkout", "-q", "main")

    verifier = GitVerifier(
        repo_root=repo,
        checks=[spy],
        worktree_parent=repo.parent,
        boundary_roots=["backend"],
    )
    artifact = ArtifactBridge(repo_root=repo).extract_artifact(
        "t", "task/widget", "main"
    )
    report = verifier.verify(artifact)

    assert report.status == "BOUNDARY_FAILED"
    assert checked["called"] is False, "no check may run when boundaries fail"
    assert report.failure_contexts[0].stage == "boundary"


# ---------------------------------------------------------------------------
# 3. PR lifecycle — atomic PR only after PASS, ownership lock released
# ---------------------------------------------------------------------------
class FakeGitHub:
    def __init__(self):
        self.calls: list[dict] = []

    def create_pr(self, head, base, title, body):
        self.calls.append({"head": head, "base": base, "title": title})
        return {"ok": True, "number": 42, "html_url": "https://github.com/x/pull/42"}


class FailingGitHub(FakeGitHub):
    def create_pr(self, head, base, title, body):
        return {"ok": False, "error": "422: no commits between main and task/widget"}


def _make_verifier(repo: Path, check) -> GitVerifier:
    return GitVerifier(repo_root=repo, checks=[check], worktree_parent=repo.parent)


def test_pr_opened_only_after_verification_pass(repo):
    # make the repo pushable: add a bare remote
    bare = repo.parent / "remote.git"
    _git(repo.parent, "init", "-q", "--bare", str(bare))
    _git(repo, "remote", "add", "origin", str(bare))

    github = FakeGitHub()
    manager = PrManager(
        verifier=_make_verifier(repo, _pass_check),
        github=github,
        state_manager=AgentStateManager(store=InMemoryStore()),
        repo_root=repo,
    )
    manager.locks.acquire("task-widget", owner="zcode-1")
    artifact = ArtifactBridge(repo_root=repo).extract_artifact(
        "task-widget", "task/widget", "main"
    )
    verification = manager.verifier.verify(artifact)
    result = manager.finalize_task(artifact, verification)

    assert result.ok is True
    assert result.pushed is True
    assert result.pr_number == 42
    assert github.calls[0]["head"] == "task/widget"
    assert manager.locks.owner("task-widget") is None, "ownership lock must be released"


def test_pr_refused_when_verification_failed(repo):
    github = FakeGitHub()

    def fail_check(worktree: Path) -> CheckResult:
        return CheckResult(name="pytest", passed=False, exit_code=1)

    manager = PrManager(
        verifier=_make_verifier(repo, fail_check),
        github=github,
        repo_root=repo,
    )
    artifact = ArtifactBridge(repo_root=repo).extract_artifact(
        "task-widget", "task/widget", "main"
    )
    verification = manager.verifier.verify(artifact)
    result = manager.finalize_task(artifact, verification)

    assert result.ok is False
    assert "PR refused" in result.reason
    assert github.calls == [], "no PR may be created without a verification PASS"


def test_pr_lifecycle_completes_task_in_state_manager(repo):
    bare = repo.parent / "remote2.git"
    _git(repo.parent, "init", "-q", "--bare", str(bare))
    _git(repo, "remote", "add", "origin", str(bare))

    sm = AgentStateManager(store=InMemoryStore())
    from external_agents.contracts.task_contract import AgentProvider, TaskContract

    task = TaskContract(goal="ship", allowed_providers=[AgentProvider.ZCODE])
    sm.create_task(task)
    sm.claim(task.task_id, worker_id="zcode-1")
    sm.start(task.task_id)

    github = FakeGitHub()
    manager = PrManager(
        verifier=_make_verifier(repo, _pass_check),
        github=github,
        state_manager=sm,
        repo_root=repo,
    )
    artifact = ArtifactBridge(repo_root=repo).extract_artifact(
        task.task_id, "task/widget", "main"
    )
    verification = manager.verifier.verify(artifact)
    result = manager.finalize_task(artifact, verification)

    assert result.ok is True
    from external_agents.contracts.task_contract import TaskState

    assert sm.get(task.task_id).state is TaskState.COMPLETED
    assert sm.get(task.task_id).result["pr"]["number"] == 42


def test_ownership_locks_exclusive():
    locks = OwnershipLocks()
    assert locks.acquire("t1", "zcode") is True
    assert locks.acquire("t1", "chatgpt") is False  # held by zcode
    assert locks.owner("t1") == "zcode"
    assert locks.release("t1", owner="chatgpt") is False  # wrong owner
    assert locks.release("t1") is True
    assert locks.release("t1") is False
