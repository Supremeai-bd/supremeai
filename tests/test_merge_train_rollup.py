"""Tests for Batch PR Consolidation Engine (Merge Train & Rollup Consolidator).
=============================================================================
Tests:
- Issue keyword regex extraction
- Filtering queued PRs and label scoping
- Pairwise collision detection
- Greedy candidate selection with batch caps and collision deferrals
- Bisect split logic for fault isolation
- Post-merge landing and cascade auto-close of linked issues
"""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

from scripts.ci.merge_train_rollup import (
    QueuedPR,
    RollupEngine,
    extract_linked_issues,
    fetch_open_prs,
    filter_queued_prs,
    find_pairwise_collisions,
    select_batch_candidates,
    split_batch_for_bisect,
)
from scripts.git.cross_pr_collision_detector import CollisionItem, CollisionReport


def test_extract_linked_issues():
    body = (
        "This resolves #100 and fixes #102.\n"
        "Also closes #100 again (duplicate).\n"
        "Random text: 1234, #abc, issue #999 without keyword."
    )
    linked = extract_linked_issues(body)
    assert linked == [100, 102]


def test_filter_queued_prs_label_and_draft():
    prs = [
        {
            "number": 1,
            "title": "feat: A",
            "isDraft": False,
            "labels": [{"name": "queue:pending-rollup"}],
            "files": [{"path": "backend/a.py"}],
            "body": "Fixes #10",
        },
        {
            "number": 2,
            "title": "feat: B (Draft)",
            "isDraft": True,
            "labels": [{"name": "queue:pending-rollup"}],
            "files": [{"path": "backend/b.py"}],
        },
        {
            "number": 3,
            "title": "feat: C (Not queued)",
            "isDraft": False,
            "labels": [{"name": "enhancement"}],
            "files": [{"path": "backend/c.py"}],
        },
        {
            "number": 4,
            "title": "feat: D (On hold)",
            "isDraft": False,
            "labels": [{"name": "queue:pending-rollup"}, {"name": "queue:hold"}],
            "files": [{"path": "backend/d.py"}],
        },
    ]

    queued = filter_queued_prs(prs, required_label="queue:pending-rollup")
    assert len(queued) == 1
    assert queued[0].number == 1
    assert queued[0].files == ["backend/a.py"]
    assert queued[0].linked_issues == [10]


def test_find_pairwise_collisions():
    pr1 = QueuedPR(number=1, title="1", head_branch="b1", files=["a.py", "common.py"])
    pr2 = QueuedPR(number=2, title="2", head_branch="b2", files=["b.py"])
    pr3 = QueuedPR(number=3, title="3", head_branch="b3", files=["c.py", "common.py"])

    collisions = find_pairwise_collisions([pr1, pr2, pr3])
    assert collisions[1] == {3}
    assert collisions[2] == set()
    assert collisions[3] == {1}


def test_select_batch_candidates_fifo_and_deferral():
    pr1 = QueuedPR(number=1, title="1", head_branch="b1", files=["shared.py", "x.py"])
    pr2 = QueuedPR(number=2, title="2", head_branch="b2", files=["y.py"])
    pr3 = QueuedPR(number=3, title="3", head_branch="b3", files=["shared.py", "z.py"])
    pr4 = QueuedPR(number=4, title="4", head_branch="b4", files=["w.py"])

    # max_batch_size = 2
    selected, deferred = select_batch_candidates([pr1, pr2, pr3, pr4], max_batch_size=2)

    # pr1 selected
    # pr2 selected (max batch 2 reached)
    # pr3 deferred (both collision with pr1 and batch cap)
    # pr4 deferred (batch cap)
    assert [p.number for p in selected] == [1, 2]
    assert [p.number for p in deferred] == [3, 4]


def test_split_batch_for_bisect():
    assert split_batch_for_bisect([]) == ([], [])
    assert split_batch_for_bisect([42]) == ([42], [])
    assert split_batch_for_bisect([1, 2, 3, 4]) == ([1, 2], [3, 4])
    assert split_batch_for_bisect([1, 2, 3]) == ([1], [2, 3])


def test_rollup_engine_plan(monkeypatch):
    mock_prs = [
        {
            "number": 10,
            "title": "PR 10",
            "headRefName": "feat/10",
            "isDraft": False,
            "labels": [{"name": "queue:pending-rollup"}],
            "files": [{"path": "f1.py"}],
            "body": "Fixes #101",
        },
        {
            "number": 11,
            "title": "PR 11",
            "headRefName": "feat/11",
            "isDraft": False,
            "labels": [{"name": "queue:pending-rollup"}],
            "files": [{"path": "f2.py"}],
            "body": "Fixes #102",
        },
    ]

    with patch("scripts.ci.merge_train_rollup.fetch_open_prs", return_value=mock_prs):
        engine = RollupEngine()
        plan = engine.plan(required_label="queue:pending-rollup", max_batch=5)
        assert plan["total_queued"] == 2
        assert plan["selected_prs"] == [10, 11]
        assert plan["deferred_prs"] == []
        assert plan["linked_issues_to_close"] == [101, 102]
        assert len(plan["selected_details"]) == 2


def test_rollup_engine_land_cascade(monkeypatch):
    engine = RollupEngine()

    def mock_run_cmd(cmd, check=True):
        res = MagicMock()
        res.returncode = 0
        if "view" in cmd:
            res.stdout = json.dumps({
                "title": "Feature PR",
                "body": "Fixes #500 and Closes #501",
                "state": "OPEN",
            })
        else:
            res.stdout = ""
        return res

    monkeypatch.setattr(engine, "_run_cmd", mock_run_cmd)

    land_res = engine.land_rollup(pr_numbers=[99], batch_pr_number=1000)
    assert land_res["merged_member_prs"] == [99]
    assert land_res["closed_issues"] == [500, 501]


# ─────────────────────────────────────────────────────────────────────────────
# Queue discovery: the enriched fetch must carry labels/body/createdAt,
# because queue filtering and issue cascade-close depend on them.
# ─────────────────────────────────────────────────────────────────────────────


def test_fetch_open_prs_requests_rollup_fields():
    payload = [
        {
            "number": 7,
            "title": "queued",
            "headRefName": "feat/7",
            "labels": [{"name": "queue:pending-rollup"}],
            "body": "Fixes #70",
            "createdAt": "2026-09-26T09:00:00Z",
        }
    ]
    completed = MagicMock(returncode=0, stdout=json.dumps(payload), stderr="")
    with patch("scripts.ci.merge_train_rollup.subprocess.run", return_value=completed) as mock_run:
        result = fetch_open_prs()

    assert result == payload
    cmd = mock_run.call_args.args[0]
    assert cmd[:3] == ["gh", "pr", "list"]
    requested_fields = cmd[-1]
    for field in ("labels", "body", "createdAt", "files", "headRefName"):
        assert field in requested_fields


def test_fetch_open_prs_falls_back_when_gh_missing():
    with (
        patch(
            "scripts.ci.merge_train_rollup.subprocess.run",
            side_effect=FileNotFoundError("gh not installed"),
        ),
        patch(
            "scripts.ci.merge_train_rollup.fetch_open_prs_legacy",
            return_value=[{"number": 99}],
        ),
    ):
        assert fetch_open_prs() == [{"number": 99}]


def test_fetch_open_prs_falls_back_on_timeout_and_nonzero_rc():
    completed = MagicMock(returncode=1, stdout="", stderr="auth required")
    with (
        patch(
            "scripts.ci.merge_train_rollup.subprocess.run",
            side_effect=subprocess.TimeoutExpired("gh", 30),
        ),
        patch("scripts.ci.merge_train_rollup.fetch_open_prs_legacy", return_value=[]) as legacy,
    ):
        assert fetch_open_prs() == []
        legacy.assert_called_once()

    with (
        patch("scripts.ci.merge_train_rollup.subprocess.run", return_value=completed),
        patch(
            "scripts.ci.merge_train_rollup.fetch_open_prs_legacy",
            return_value=[{"number": 3}],
        ),
    ):
        assert fetch_open_prs() == [{"number": 3}]


def test_fetch_open_prs_survives_none_stdout_from_decode_failure():
    """Regression: cp1252 decode failure leaves stdout=None (Windows)."""
    completed = MagicMock(returncode=0, stdout=None, stderr=None)
    with (
        patch("scripts.ci.merge_train_rollup.subprocess.run", return_value=completed),
        patch(
            "scripts.ci.merge_train_rollup.fetch_open_prs_legacy",
            return_value=[{"number": 42}],
        ),
    ):
        assert fetch_open_prs() == [{"number": 42}]


def test_fetch_open_prs_returns_empty_without_any_source():
    with (
        patch(
            "scripts.ci.merge_train_rollup.subprocess.run",
            side_effect=FileNotFoundError("gh not installed"),
        ),
        patch("scripts.ci.merge_train_rollup.fetch_open_prs_legacy", None),
    ):
        assert fetch_open_prs() == []


# ─────────────────────────────────────────────────────────────────────────────
# FIFO ordering by real enqueue time
# ─────────────────────────────────────────────────────────────────────────────


def test_filter_queued_prs_is_fifo_by_created_at():
    prs = [
        {
            "number": 50,
            "title": "created later",
            "headRefName": "b50",
            "isDraft": False,
            "labels": [{"name": "queue:pending-rollup"}],
            "files": [{"path": "f50.py"}],
            "createdAt": "2026-09-26T10:00:00Z",
        },
        {
            "number": 60,
            "title": "created earlier",
            "headRefName": "b60",
            "isDraft": False,
            "labels": [{"name": "queue:pending-rollup"}],
            "files": [{"path": "f60.py"}],
            "createdAt": "2026-09-26T09:00:00Z",
        },
    ]

    queued = filter_queued_prs(prs)
    assert [p.number for p in queued] == [60, 50]
    assert queued[0].created_at == "2026-09-26T09:00:00Z"


def test_filter_queued_prs_without_timestamp_sorts_after_timestamped():
    prs = [
        {
            "number": 1,
            "title": "no timestamp",
            "headRefName": "b1",
            "isDraft": False,
            "labels": [{"name": "queue:pending-rollup"}],
            "files": [{"path": "f1.py"}],
        },
        {
            "number": 2,
            "title": "timestamped",
            "headRefName": "b2",
            "isDraft": False,
            "labels": [{"name": "queue:pending-rollup"}],
            "files": [{"path": "f2.py"}],
            "createdAt": "2026-01-01T00:00:00Z",
        },
    ]

    assert [p.number for p in filter_queued_prs(prs)] == [2, 1]


# ─────────────────────────────────────────────────────────────────────────────
# Canonical collision-detector reuse (Ecosystem-First integration)
# ─────────────────────────────────────────────────────────────────────────────


def _collision(file_path, pr_num, branch, colliding_pr, colliding_branch, author="agent-x"):
    return CollisionItem(
        file_path=file_path,
        target_pr=pr_num,
        target_branch=branch,
        colliding_pr=colliding_pr,
        colliding_branch=colliding_branch,
        colliding_author=author,
    )


def test_validate_batch_collisions_ignores_intra_batch_reports_external():
    pr1 = QueuedPR(number=10, title="10", head_branch="b10", files=["a.py"])
    pr2 = QueuedPR(number=11, title="11", head_branch="b11", files=["b.py"])

    reports = {
        10: CollisionReport(
            target_branch="b10",
            target_pr=10,
            direct_collisions=[
                # Same batch member -> already handled by batch scheduling.
                _collision("a.py", 10, "b10", 11, "b11"),
                # Outsider -> must be reported as a drift risk.
                _collision("a.py", 10, "b10", 77, "feat/outsider"),
            ],
        ),
        11: CollisionReport(target_branch="b11", target_pr=11),
    }

    def fake_detect(target_branch, target_pr_num=None, target_files=None):
        return reports[target_pr_num]

    with patch("scripts.ci.merge_train_rollup.detect_collisions", side_effect=fake_detect):
        conflicts = RollupEngine().validate_batch_collisions([pr1, pr2])

    assert conflicts == {10: ["PR #77"]}


def test_validate_batch_collisions_reports_branch_only_conflicts():
    pr1 = QueuedPR(number=10, title="10", head_branch="b10", files=["a.py"])
    report = CollisionReport(
        target_branch="b10",
        target_pr=10,
        direct_collisions=[_collision("a.py", 10, "b10", None, "agent-6-coder-2")],
    )

    with patch(
        "scripts.ci.merge_train_rollup.detect_collisions",
        side_effect=lambda target_branch, target_pr_num=None, target_files=None: report,
    ):
        conflicts = RollupEngine().validate_batch_collisions([pr1])

    assert conflicts == {10: ["branch agent-6-coder-2"]}


def test_validate_batch_collisions_noop_without_detector():
    with patch("scripts.ci.merge_train_rollup.detect_collisions", None):
        assert RollupEngine().validate_batch_collisions([QueuedPR(1, "t", "b")]) == {}


def test_validate_batch_collisions_passes_batch_files_to_detector():
    pr1 = QueuedPR(number=10, title="10", head_branch="b10", files=["a.py"])
    captured: dict = {}

    def fake_detect(target_branch, target_pr_num=None, target_files=None):
        captured["branch"] = target_branch
        captured["files"] = target_files
        return CollisionReport(target_branch=target_branch, target_pr=target_pr_num)

    with patch("scripts.ci.merge_train_rollup.detect_collisions", side_effect=fake_detect):
        RollupEngine().validate_batch_collisions([pr1])

    assert captured == {"branch": "b10", "files": ["a.py"]}


# ─────────────────────────────────────────────────────────────────────────────
# Rollup branch construction (git-level batch assembly)
# ─────────────────────────────────────────────────────────────────────────────


def _ok_cmd(returncode=0, stdout="", stderr=""):
    res = MagicMock()
    res.returncode = returncode
    res.stdout = stdout
    res.stderr = stderr
    return res


def test_create_rollup_branch_builds_named_batch_and_reports_collisions(monkeypatch):
    engine = RollupEngine()
    issued: list = []
    raw = [
        {
            "number": 5,
            "title": "t5",
            "headRefName": "b5",
            "isDraft": False,
            "labels": [{"name": "queue:pending-rollup"}],
            "files": [{"path": "x.py"}],
            "body": "",
        }
    ]
    report = CollisionReport(
        target_branch="b5",
        target_pr=5,
        direct_collisions=[_collision("x.py", 5, "b5", 88, "feat/peer")],
    )

    def fake_run(cmd, check=True):
        issued.append(" ".join(cmd))
        return _ok_cmd()

    monkeypatch.setattr(engine, "_run_cmd", fake_run)
    monkeypatch.setattr("scripts.ci.merge_train_rollup.fetch_open_prs", lambda *a, **k: raw)
    monkeypatch.setattr(
        "scripts.ci.merge_train_rollup.detect_collisions",
        lambda target_branch, target_pr_num=None, target_files=None: report,
    )

    result = engine.create_rollup_branch([5], timestamp="20260101-000000")

    assert result["batch_branch"] == "batch/rollup-20260101-000000"
    assert result["merged_prs"] == [5]
    assert result["failed_prs"] == []
    assert result["success"] is True
    assert result["external_collisions"] == {5: ["PR #88"]}
    assert "git fetch origin pull/5/head:pr-5-head" in issued
    assert any(c.startswith("git checkout -B batch/rollup-20260101-000000") for c in issued)
    assert any(c.startswith("git merge --no-ff") for c in issued)


def test_create_rollup_branch_defers_conflicting_prs(monkeypatch):
    engine = RollupEngine()

    def fake_run(cmd, check=True):
        joined = " ".join(cmd)
        if "pull/9/head" in joined:
            return _ok_cmd(returncode=1, stderr="could not find remote ref")
        if joined.startswith("git merge"):
            return _ok_cmd(returncode=1, stderr="CONFLICT")
        return _ok_cmd()

    monkeypatch.setattr(engine, "_run_cmd", fake_run)

    result = engine.create_rollup_branch([9], deep_validate=False)

    assert result["merged_prs"] == []
    assert result["failed_prs"] == [9]
    assert result["success"] is False


def test_create_rollup_branch_aborts_merge_on_conflict(monkeypatch):
    engine = RollupEngine()
    issued: list = []

    def fake_run(cmd, check=True):
        joined = " ".join(cmd)
        issued.append(joined)
        if joined.startswith("git merge --no-ff"):
            return _ok_cmd(returncode=1, stderr="CONFLICT")
        return _ok_cmd()

    monkeypatch.setattr(engine, "_run_cmd", fake_run)

    engine.create_rollup_branch([12], deep_validate=False)

    assert "git merge --abort" in issued


def test_create_rollup_branch_rejects_empty_input():
    try:
        RollupEngine().create_rollup_branch([])
    except ValueError as exc:
        assert "No PR numbers" in str(exc)
    else:  # pragma: no cover - guard against silent regression
        raise AssertionError("expected ValueError for an empty rollup batch")


# ─────────────────────────────────────────────────────────────────────────────
# Single-flight state machine: an in-flight member can never be re-batched,
# and landing clears both queue states.
# ─────────────────────────────────────────────────────────────────────────────


def test_filter_queued_prs_excludes_in_flight_batch_members():
    prs = [
        {
            "number": 5,
            "title": "already consolidated",
            "headRefName": "b5",
            "isDraft": False,
            "labels": [
                {"name": "queue:pending-rollup"},
                {"name": "queue:in-batch"},
            ],
            "files": [{"path": "f.py"}],
        }
    ]

    # Without the guard the next scheduler tick would roll the same PR twice.
    assert filter_queued_prs(prs) == []


def test_land_rollup_clears_both_queue_labels_and_closes_issues(monkeypatch):
    engine = RollupEngine()
    issued: list = []

    def fake_run(cmd, check=True):
        joined = " ".join(cmd)
        issued.append(joined)
        res = MagicMock()
        res.returncode = 0
        res.stderr = ""
        if joined.startswith("gh pr view"):
            res.stdout = json.dumps(
                {"title": "Feature", "body": "Fixes #7", "state": "OPEN"}
            )
        else:
            res.stdout = ""
        return res

    monkeypatch.setattr(engine, "_run_cmd", fake_run)

    result = engine.land_rollup(pr_numbers=[5], batch_pr_number=900)

    assert result["merged_member_prs"] == [5]
    assert result["closed_issues"] == [7]
    assert any("--remove-label queue:pending-rollup" in c for c in issued)
    assert any("--remove-label queue:in-batch" in c for c in issued)
    assert any(c.startswith("gh issue close 7") for c in issued)
    assert any(c.startswith("gh pr close 5") for c in issued)


def test_land_rollup_keeps_already_merged_members(monkeypatch):
    engine = RollupEngine()

    def fake_run(cmd, check=True):
        res = MagicMock()
        res.returncode = 0
        res.stderr = ""
        if "view" in cmd:
            res.stdout = json.dumps({"title": "T", "body": "", "state": "MERGED"})
        else:
            res.stdout = ""
        return res

    monkeypatch.setattr(engine, "_run_cmd", fake_run)

    result = engine.land_rollup(pr_numbers=[8], batch_pr_number=None)

    assert result["merged_member_prs"] == [8]
    assert result["closed_issues"] == []


def test_create_rollup_branch_allow_partial(monkeypatch):
    engine = RollupEngine()

    def fake_run(cmd, check=True):
        joined = " ".join(cmd)
        if "pull/10/head" in joined:
            return _ok_cmd(returncode=1, stderr="merge conflict")
        return _ok_cmd()

    monkeypatch.setattr(engine, "_run_cmd", fake_run)

    # Without allow_partial, fails
    res_strict = engine.create_rollup_branch([1, 10], deep_validate=False, allow_partial=False)
    assert res_strict["success"] is False
    assert res_strict["merged_prs"] == [1]
    assert res_strict["failed_prs"] == [10]

    # With allow_partial, succeeds since at least 1 PR merged
    res_partial = engine.create_rollup_branch([1, 10], deep_validate=False, allow_partial=True)
    assert res_partial["success"] is True
    assert res_partial["merged_prs"] == [1]
    assert res_partial["failed_prs"] == [10]






