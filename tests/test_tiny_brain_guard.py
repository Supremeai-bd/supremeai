"""Offline regressions for run-scoped CI evidence and the landing decision."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from scripts.ci import tiny_brain_pr_guard as guard

REPO = "Supremeai-bd/supremeai"
HEAD, BASE, MERGE, OTHER = (char * 40 for char in "abcd")
ROOT = Path(__file__).resolve().parents[1]
PROTECTED = ".github/workflows/unified-pipeline.yml"


def job_results(tier="local-self-hosted"):
    results = {
        job: {"result": "skipped"}
        for job in {"fast-gate", "runtime-readiness", *guard.HEAVY_JOBS.values()}
    }
    results.update({
        "resolve-execution-tier": {"result": "success", "outputs": {"execution_tier": tier}},
        "syntax-and-governance-gate": {"result": "success"},
        "golden-eval-gate": {"result": "success"},
    })
    results[guard.HEAVY_JOBS[tier]]["result"] = "success"
    if tier != "local-self-hosted":
        for job in ("fast-gate", "runtime-readiness"):
            results[job]["result"] = "success"
    if tier == "render-ci-runner":
        results[guard.RENDER]["outputs"] = {"verified_sha": MERGE}
    return results


@pytest.fixture
def snapshot():
    return {
        "number": 1,
        "state": "open",
        "draft": False,
        "head": {"sha": HEAD, "repo": {"full_name": REPO}},
        "base": {"sha": BASE, "ref": "main", "repo": {"full_name": REPO}},
        "mergeable": True,
        "merge_commit_sha": MERGE,
        "changed_files": 1,
        "additions": 5000,
    }


def decide(snapshot, files, *, needs=None, base_tip=BASE, merge_parents=(BASE, HEAD), recheck=False):
    def api(endpoint):
        if endpoint == f"repos/{REPO}/pulls/1":
            return snapshot
        if endpoint == f"repos/{REPO}/git/ref/heads/main":
            return {"object": {"sha": base_tip}}
        if endpoint == f"repos/{REPO}/git/commits/{MERGE}":
            return {"sha": MERGE, "parents": [{"sha": sha} for sha in merge_parents]}
        assert endpoint.startswith(f"repos/{REPO}/pulls/1/files?per_page=100&page=")
        start = (int(endpoint.rsplit("=", 1)[-1]) - 1) * 100
        return files[start : start + 100]

    return guard.evaluate(
        1, api=api, repo=REPO, needs=job_results() if needs is None else needs,
        head_sha=HEAD, base_sha=BASE, merge_sha=MERGE, recheck=recheck,
    )


@pytest.mark.parametrize("tier", list(guard.HEAVY_JOBS))
@pytest.mark.parametrize("path", ["docs/INDEX.md", "tests/test_something.py", "gateway/service/app.py"])
def test_routine_changes_land_with_only_the_selected_lane(snapshot, tier, path):
    result = decide(snapshot, [{"filename": path}], needs=job_results(tier))
    assert result["decision"] == "AUTO_MERGE"


@pytest.mark.parametrize("job", [guard.RESOLVE, "syntax-and-governance-gate", "golden-eval-gate", guard.LOCAL])
@pytest.mark.parametrize("status", [None, "pending", "skipped", "neutral", "failure", "cancelled"])
def test_non_successful_required_checks_block_before_any_review(job, status):
    def unexpected_call(_endpoint):
        pytest.fail("Must not ask for review when required CI has not succeeded")

    needs = job_results()
    if status is None:
        del needs[job]
    else:
        needs[job]["result"] = status
    result = guard.evaluate(1, api=unexpected_call, needs=needs, head_sha=HEAD, base_sha=BASE, merge_sha=MERGE)
    assert result == {"decision": "BLOCKED", "reason": f"ci_not_success:{job}"}


@pytest.mark.parametrize(("job", "status"), [
    ("fast-gate", "pending"), ("runtime-readiness", "skipped"), (guard.FALLBACK, "failure"),
])
def test_cloud_gates_are_required_even_if_other_heavy_lanes_pass(snapshot, job, status):
    needs = job_results("github-ubuntu-render-backend")
    needs[guard.LOCAL]["result"] = "success"
    needs[job]["result"] = status
    assert decide(snapshot, [{"filename": PROTECTED}], needs=needs)["decision"] == "BLOCKED"


def test_unknown_tier_does_not_authorize_landing(snapshot):
    needs = job_results()
    needs[guard.RESOLVE]["outputs"]["execution_tier"] = "unexpected"
    assert decide(snapshot, [{"filename": PROTECTED}], needs=needs)["reason"] == "unknown_execution_tier"


@pytest.mark.parametrize(("render_status", "fallback_allowed", "fallback_status", "tested_sha", "decision"), [
    ("success", "", "skipped", MERGE, "AUTO_MERGE"),
    ("success", "", "skipped", HEAD, "BLOCKED"),
    ("success", "", "skipped", "", "BLOCKED"),
    ("failure", "true", "success", "", "AUTO_MERGE"),
    ("failure", "true", "skipped", "", "BLOCKED"),
    ("failure", "false", "success", "", "BLOCKED"),
    ("cancelled", "true", "success", "", "BLOCKED"),
    ("skipped", "true", "success", "", "BLOCKED"),
])
def test_render_requires_exact_sha_or_an_eligible_successful_fallback(
    snapshot, render_status, fallback_allowed, fallback_status, tested_sha, decision,
):
    needs = job_results("render-ci-runner")
    needs[guard.RENDER] = {
        "result": render_status,
        "outputs": {"fallback_allowed": fallback_allowed, "verified_sha": tested_sha},
    }
    needs[guard.FALLBACK]["result"] = fallback_status
    assert decide(snapshot, [{"filename": "README.md"}], needs=needs)["decision"] == decision


@pytest.mark.parametrize("path", [
    PROTECTED, "scripts/ci/tiny_brain_pr_guard.py", "core/alembic_migrations/example.py",
    "gateway/service/keygen.py", "scripts/runtime/infisical_bootstrap.py", "render.yaml",
    "core/api/dependencies.py",
    # Provider core: one bad edit degrades every chat request.
    "gateway/provider_chain.py", "gateway/circuit_breaker.py",
    "gateway/routing_policy.json", "gateway/config.py",
    "gateway/service/providers/adapters.py", "gateway/service/providers/pool.py",
])
def test_verified_protected_changes_need_owner_review(snapshot, path):
    result = decide(snapshot, [{"filename": path}])
    assert result == {"decision": "OWNER_REVIEW", "reason": "protected_paths_changed", "paths": [path]}


def test_protected_rename_on_second_page_is_not_missed(snapshot):
    files = [{"filename": f"docs/example_{i}.md"} for i in range(100)]
    files.append({"filename": "docs/old-policy.yml", "status": "renamed", "previous_filename": PROTECTED})
    snapshot["changed_files"] = len(files)
    assert decide(snapshot, files)["decision"] == "OWNER_REVIEW"
    assert decide(snapshot, files[:-1])["decision"] == "BLOCKED"


@pytest.mark.parametrize("change", ["head", "base", "merge", "mergeable", "draft", "fork", "closed", "retargeted"])
def test_candidate_changes_block_both_decision_and_post_approval_merge(snapshot, change):
    if change in {"head", "base"}:
        snapshot[change]["sha"] = OTHER
    elif change == "merge":
        snapshot["merge_commit_sha"] = OTHER
    elif change == "mergeable":
        snapshot["mergeable"] = None
    elif change == "draft":
        snapshot["draft"] = True
    elif change == "fork":
        snapshot["head"]["repo"]["full_name"] = "other/fork"
    elif change == "retargeted":
        snapshot["base"]["ref"] = "different"
    else:
        snapshot["state"] = "closed"
    for recheck in (False, True):
        assert decide(snapshot, [{"filename": PROTECTED}], recheck=recheck)["decision"] == "BLOCKED"


def test_checks_on_stale_base_or_wrong_merge_parents_do_not_count(snapshot):
    files = [{"filename": PROTECTED}]
    assert decide(snapshot, files, merge_parents=(OTHER, HEAD))["reason"] == "tested_merge_parents_mismatch"
    assert decide(snapshot, files, base_tip=OTHER)["reason"] == "pr_base_changed"
    assert decide(snapshot, files, base_tip=OTHER, recheck=True)["decision"] == "BLOCKED"
    assert decide(snapshot, files, recheck=True) == {"reason": "tested_candidate_current"}


def test_head_changes_while_reading_paths(snapshot):
    class MovingFiles(list):
        def __getitem__(self, position):
            snapshot["head"]["sha"] = OTHER
            return super().__getitem__(position)

    result = decide(snapshot, MovingFiles([{"filename": PROTECTED}]))
    assert result == {"decision": "BLOCKED", "reason": "pr_head_changed"}


def test_fetch_failure_blocks():
    def failed_get(_endpoint):
        raise OSError("fixture unavailable")

    result = guard.evaluate(1, api=failed_get, needs=job_results(), head_sha=HEAD, base_sha=BASE, merge_sha=MERGE)
    assert result["decision"] == "BLOCKED"


@pytest.fixture
def jobs():
    path = ROOT / ".github/workflows/unified-pipeline.yml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))["jobs"]


@pytest.mark.parametrize(("contract", "guard_exit", "exit_code"), [
    ("legacy", 0, 0), ("current", 0, 0), ("current", 1, 1), ("partial", 0, 1),
])
def test_trusted_guard_cli_rollout(jobs, tmp_path, contract, guard_exit, exit_code):
    script = tmp_path / "scripts/ci/tiny_brain_pr_guard.py"
    script.parent.mkdir(parents=True)
    output = tmp_path / "output"
    calls = tmp_path / "calls"
    current = ["--head-sha", "--base-sha", "--merge-sha", "--recheck-candidate"]
    legacy = ["--run-id", "--brain-url", "--dry-run", "--json"]
    flags = {"legacy": legacy, "current": current, "partial": legacy + current[:1]}[contract]
    script.write_text(
        "import json, sys\nfrom pathlib import Path\n"
        f"if sys.argv[1:] == ['--help']:\n    print({' '.join(flags)!r})\n"
        f"else:\n    Path({str(calls)!r}).write_text(json.dumps(sys.argv[1:]))\n    sys.exit({guard_exit})\n",
        encoding="utf-8",
    )
    step = jobs["ai-evaluate-and-approve"]["steps"][-1]
    start, *python, end = step["run"].splitlines()
    assert (start, end) == ("python3 - <<'PY'", "PY")
    result = subprocess.run(
        [sys.executable, "-c", "\n".join(python)],
        cwd=tmp_path,
        env={
            **os.environ, "GITHUB_OUTPUT": str(output), "PR_NUMBER": "1",
            "EXPECTED_HEAD_SHA": HEAD, "EXPECTED_BASE_SHA": BASE, "TESTED_MERGE_SHA": MERGE,
        },
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == exit_code, result.stderr
    if contract == "current":
        assert json.loads(calls.read_text(encoding="utf-8")) == [
            "--pr", "1", "--head-sha", HEAD, "--base-sha", BASE, "--merge-sha", MERGE,
        ]
    else:
        assert not calls.exists()  # Never evaluate a legacy or partially upgraded guard.
    if contract == "legacy":
        assert output.read_text(encoding="utf-8") == "decision=BLOCKED\nreason=legacy_trusted_base_guard\n"
        assert "normal owner review" in result.stdout
    else:
        assert not output.exists()


def test_required_ci_and_candidate_bindings_are_from_this_run(jobs):
    decision = jobs["ai-evaluate-and-approve"]
    assert set(decision["needs"]) == set(job_results()) | {"verify-pr"}
    assert "needs.verify-pr.result == 'success'" in decision["if"]
    for job in (decision, jobs["merge-verified-pr"]):
        checkout, run = job["steps"]
        assert checkout["with"]["ref"] == "${{ github.event.pull_request.base.sha }}"
        assert checkout["with"]["persist-credentials"] is False
        assert run["env"]["EXPECTED_HEAD_SHA"] == "${{ github.event.pull_request.head.sha }}"
        assert run["env"]["EXPECTED_BASE_SHA"] == "${{ github.event.pull_request.base.sha }}"
        assert run["env"]["TESTED_MERGE_SHA"] == "${{ github.sha }}"
    assert decision["permissions"] == {"contents": "read", "pull-requests": "read"}
    assert decision["steps"][-1]["env"]["PR_GATE_RESULTS"] == "${{ toJSON(needs) }}"
    render = next(step for step in jobs[guard.RENDER]["steps"] if step.get("id") == "render-ci")
    assert render["env"]["EXPECTED_SHA"] == "${{ github.sha }}"
    assert "PR_HEAD_SHA" not in render["env"]
    assert jobs[guard.RENDER]["outputs"]["verified_sha"] == "${{ steps.render-ci.outputs.verified_sha }}"


def test_drafts_skip_landing_but_ready_for_review_runs_it(jobs):
    assert "github.event.pull_request.draft == false" in jobs["ai-evaluate-and-approve"]["if"]
    path = ROOT / ".github/workflows/unified-pipeline.yml"
    # PyYAML SafeLoader treats the workflow key `on` as the boolean True.
    events = yaml.safe_load(path.read_text(encoding="utf-8"))[True]
    assert "ready_for_review" in events["pull_request"]["types"]


def test_workflow_has_one_merge_path_and_positive_owner_gate(jobs):
    owner = jobs["auto-merge-high-risk"]
    assert owner["environment"] == "production-approval"
    assert owner["permissions"] == {}
    assert "needs.ai-evaluate-and-approve.result == 'success'" in owner["if"]
    assert "decision == 'OWNER_REVIEW'" in owner["if"] and "!=" not in owner["if"]
    merge = jobs["merge-verified-pr"]
    assert set(merge["needs"]) == {"auto-merge-high-risk", "ai-evaluate-and-approve"}
    assert "needs.ai-evaluate-and-approve.result == 'success'" in merge["if"]
    assert "decision == 'AUTO_MERGE'" in merge["if"]
    assert "needs.auto-merge-high-risk.result == 'success'" in merge["if"]
    commands = [step.get("run", "") for job in jobs.values() for step in job.get("steps", [])]
    assert not any("--auto-rebase" in command for command in commands)
    merges = [command for command in commands if "gh pr merge" in command]
    assert len(merges) == 1
    assert merges[0].index("--recheck-candidate") < merges[0].index("gh pr merge")
    assert '--match-head-commit "$EXPECTED_HEAD_SHA"' in merges[0]
    assert "--auto" not in merges[0] and "--admin" not in merges[0]


@pytest.mark.parametrize(("failed_result", "tier", "expected"), [
    ("success", "github-ubuntu-render-backend", 0),
    ("skipped", "github-ubuntu-render-backend", 1),
    ("failure", "github-ubuntu-render-backend", 1),
    ("success", "local-self-hosted", 1),
])
def test_hosted_pr_verdict_requires_success_on_the_tested_lane(jobs, failed_result, tier, expected):
    job = jobs["verify-pr"]
    assert job["if"] == "${{ always() && github.event_name == 'pull_request' }}"
    assert job["permissions"] == {}
    outcomes = {name: {"result": "success"} for name in job["needs"]}
    outcomes["render-heavy-gate-fallback"]["result"] = failed_result
    start, *python, end = job["steps"][0]["run"].splitlines()
    assert (start, end) == ("python3 - <<'PY'", "PY")
    result = subprocess.run(
        [sys.executable, "-c", "\n".join(python)],
        env={**os.environ, "RESULTS": json.dumps(outcomes), "TIER": tier, "GITHUB_SHA": MERGE},
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == expected, result.stderr
    if expected == 0:
        assert MERGE in result.stdout
