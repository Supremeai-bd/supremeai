"""Runner-hierarchy guard: long ubuntu jobs must be gated by the preflight.

The guard is a Tier-1 check ("4-Level Runner Hierarchy Preflight", <10s) whose
job-splitting is regex-based, so a workflow-formatting change can blind it
without failing anything. `split_jobs` is the fragile part and is pinned here.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))

import runner_hierarchy_guard as guard  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "runner_hierarchy_guard.py"

WORKFLOW = """name: x
jobs:
  short-job:
    runs-on: ubuntu-24.04
    timeout-minutes: 5
    steps:
      - run: echo hi
  long-ungated:
    runs-on: ubuntu-24.04
    timeout-minutes: 30
    steps:
      - run: sleep 1
  long-gated:
    needs: [resolve-execution-tier]
    runs-on: ubuntu-24.04
    timeout-minutes: 60
    steps:
      - run: sleep 1
"""


def test_split_jobs_finds_every_top_level_job():
    jobs = guard.split_jobs(WORKFLOW)
    assert set(jobs) == {"short-job", "long-ungated", "long-gated"}
    assert "timeout-minutes: 30" in jobs["long-ungated"]


def test_deploy_like_jobs_are_exempt_by_name():
    assert guard.DEPLOY_NAME_RE.search("deploy-render")
    assert guard.DEPLOY_NAME_RE.search("verify-render-service")
    assert not guard.DEPLOY_NAME_RE.search("unit-tests")


def test_allowlist_and_gate_markers_exist():
    assert "resolve-execution-tier" in guard.ALLOW
    # `hierarchy-exception:` in a job block is a documented escape hatch.
    assert "timeout-minutes: 60" in guard.split_jobs(WORKFLOW)["long-gated"]


def test_guard_passes_on_the_live_workflows():
    """Non-strict mode must stay green; --strict drift would already fail CI.

    Runs as a subprocess because `main()` parses `sys.argv` (pytest's own flags
    would otherwise be read as guard arguments).
    """
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=120, check=False,
    )
    assert result.returncode == 0, (result.stdout + result.stderr)[-1500:]
