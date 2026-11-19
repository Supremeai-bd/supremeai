"""Pin the deploy/approval split in `.github/workflows/unified-pipeline.yml`.

Two failures are possible here and both are silent until production:

1. **Deploys re-gated.** Adding `environment: production` to a deploy job
   re-introduces a human approval on every merge, so auto-deploy dies and the
   queue backs up — the exact regression `bea2978` fixed.
2. **Protected merges ungated.** Removing `environment: production` from the
   owner-review job means a protected PR (provider core, workflows, auth)
   lands on a green CI signal alone.

So the invariant is: exactly one job carries a `production` environment, and
it is the owner-review gate that runs only on an OWNER_REVIEW decision.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

PIPELINE = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "unified-pipeline.yml"
GATE_JOB = "auto-merge-high-risk"
DEPLOY_JOBS = ("deploy-render-services", "deploy-cloudflare", "deploy-and-verify",
               "merge-verified-pr")


@pytest.fixture(scope="module")
def jobs() -> dict:
    return yaml.safe_load(PIPELINE.read_text(encoding="utf-8"))["jobs"]


def test_pipeline_parses(jobs):
    assert GATE_JOB in jobs
    assert "ai-evaluate-and-approve" in jobs


def test_exactly_one_job_requires_the_production_environment(jobs):
    gated = {name: spec.get("environment") for name, spec in jobs.items()
             if spec.get("environment")}
    assert gated == {"auto-merge-high-risk": "production"}, (
        "only the owner-review gate may carry `environment: production`; "
        "deploy jobs must stay un-gated or auto-deploy stalls"
    )


@pytest.mark.parametrize("name", DEPLOY_JOBS)
def test_deploy_and_merge_jobs_are_not_human_gated(jobs, name):
    assert jobs[name].get("environment") is None


def test_gate_job_only_runs_for_owner_review(jobs):
    condition = jobs[GATE_JOB]["if"]
    assert "OWNER_REVIEW" in condition
    assert "AUTO_MERGE" not in condition


def test_gate_job_cannot_merge_or_push(jobs):
    """The approval gate is a reviewer ping, not a machine — no write scope."""
    assert jobs[GATE_JOB].get("permissions") == {}


def test_landing_decision_runs_from_the_trusted_base_commit(jobs):
    steps = jobs["ai-evaluate-and-approve"]["steps"]
    setup = [s for s in steps if (s.get("with") or {}).get("path") == "_verifier-base"]
    assert setup, "the decision must be evaluated by the base commit's policy"
    assert "pull_request.base.sha" in str((setup[0].get("with") or {}).get("ref"))


def test_advisor_is_wired_downgrade_only(jobs):
    script = "".join(s.get("run", "") for s in jobs["ai-evaluate-and-approve"]["steps"])
    assert "landing_decision_compose.py" in script
    assert "ai_pr_evaluator.py" in script
    # The advisor must never be able to promote a decision.
    assert "decision=AUTO_MERGE" not in script
