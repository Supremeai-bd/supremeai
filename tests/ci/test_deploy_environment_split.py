"""Pin the approval split in `.github/workflows/unified-pipeline.yml`.

GitHub pauses every job that declares an `environment` carrying required
reviewers. The `production` environment **has** required reviewers, so each job
that declares `environment: production` costs a human click — per job, per run.
Ten jobs carried it, which turned every pull request into ten "Review
deployments" prompts. The jobs below never needed the environment; they used it
as secret scoping and paid a reviewer for it.

The rule these tests now enforce:

* **No PR-reachable job may declare an `environment`.** Anything that can fire on
  `pull_request` must be machine-decidable. This is the regression that made the
  gate unlivable, and it is silent — CI just sits in `waiting`.
* `production-approval` (the approval-bearing environment reserved for the owner
  path) is used by exactly one job: `auto-merge-high-risk`. Moving it re-gates
  deploys/merges, or un-gates protected changes.
* `production` may only be declared by main-only platform deploys that consume
  environment-scoped credentials — clicking approve once per deploy is a
  deliberate cost, clicking approve per PR is not.

Two failures stay silent until production:

1. **Deploys re-gated.** Putting `production-approval` on a deploy or merge job
   re-introduces a manual approval on every merge, so auto-deploy stalls and
   the queue backs up.
2. **Protected merges ungated.** Moving `auto-merge-high-risk` off
   `production-approval` means a protected PR (provider core, auth, workflows,
   registry/blueprint) lands on a green CI signal alone.

Upstream owns the exact environment names (`tests/test_tiny_brain_guard.py`
asserts the gate's name), so this suite asserts the *relationship* between them
rather than a hardcoded total.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

PIPELINE = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "unified-pipeline.yml"
GATE_JOB = "auto-merge-high-risk"
APPROVAL_ENV = "production-approval"
SCOPING_ENV = "production"

# The complete set of jobs that may pause for a human, and why.
APPROVAL_ALLOWLIST = {
    GATE_JOB: APPROVAL_ENV,                  # owner review for protected changes
    "deploy-and-verify": SCOPING_ENV,        # vars.RENDER_*_SERVICE_ID, main-only
    "deploy-render-services": SCOPING_ENV,   # production RENDER_API_KEY_*, main-only
    "deploy-cloudflare": SCOPING_ENV,        # env-scoped Cloudflare credentials, main-only
    "deploy-vercel": SCOPING_ENV,            # env-scoped Vercel credentials, main-only
}

DEPLOY_JOBS = (
    "deploy-render-services",
    "deploy-cloudflare",
    "deploy-vercel",
    "deploy-and-verify",
    "merge-verified-pr",
)


@pytest.fixture(scope="module")
def jobs() -> dict:
    return yaml.safe_load(PIPELINE.read_text(encoding="utf-8"))["jobs"]


@pytest.fixture(scope="module")
def pipeline_text() -> str:
    return PIPELINE.read_text(encoding="utf-8")


def test_pipeline_parses(jobs):
    assert GATE_JOB in jobs
    assert "ai-evaluate-and-approve" in jobs


def test_only_the_owner_gate_uses_the_approval_environment(jobs):
    gated = {name: spec.get("environment") for name, spec in jobs.items()
             if spec.get("environment") == APPROVAL_ENV}
    assert gated == {GATE_JOB: APPROVAL_ENV}, (
        f"`{APPROVAL_ENV}` carries the required reviewer; gating a deploy or "
        "merge job with it stalls auto-deploy, and un-gating the owner path "
        "lets protected changes land on CI signal alone"
    )


def test_only_allowlisted_jobs_may_pause_for_a_human(jobs):
    """Any new `environment:` is a new manual approval — it must be deliberate."""
    pausing = {name: spec.get("environment")
               for name, spec in jobs.items() if spec.get("environment")}
    assert pausing == APPROVAL_ALLOWLIST, (
        "`production` has required reviewers, so every job that declares an "
        "environment stops the run until a human approves it. Add a job here "
        "only if it genuinely needs an environment-scoped credential (and never "
        "if it can fire on pull_request). See the ENVIRONMENT RULE comment in "
        "unified-pipeline.yml."
    )


def test_scoping_environment_stays_on_the_main_only_deploy_path(jobs):
    """The regression: a PR check that waits for a human is not a check.

    `production` is used as credential scoping, not as a review gate. Because it
    also carries required reviewers, any job using it that can fire on a pull
    request turns that PR into a "Review deployments" prompt. The owner gate is
    the one deliberate exception — it *is* the reviewer, and it only runs for
    OWNER_REVIEW decisions.
    """
    offenders = []
    for name, spec in jobs.items():
        if spec.get("environment") != SCOPING_ENV:
            continue
        condition = str(spec.get("if") or "")
        # A job is PR-reachable unless it is pinned to pushes on main.
        if "refs/heads/main" not in condition:
            offenders.append(name)
    assert not offenders, (
        f"{offenders} declare `environment: {SCOPING_ENV}` but are not pinned to "
        "main; GitHub will hold every pull request they touch at "
        "'Review deployments'. Drop the environment (it only scoped secrets) or "
        "pin the job to main."
    )


@pytest.mark.parametrize("name", DEPLOY_JOBS)
def test_deploy_and_merge_jobs_are_not_human_gated(jobs, name):
    assert jobs[name].get("environment") != APPROVAL_ENV


def test_gate_job_only_runs_for_owner_review(jobs):
    condition = jobs[GATE_JOB]["if"]
    assert "OWNER_REVIEW" in condition
    assert "AUTO_MERGE" not in condition


def test_gate_job_cannot_merge_or_push(jobs):
    """The approval gate is a reviewer ping, not a machine — no write scope."""
    assert jobs[GATE_JOB].get("permissions") == {}


def test_environment_rule_is_documented_in_the_workflow(pipeline_text):
    """The rule must be readable where the mistake gets made."""
    assert "ENVIRONMENT RULE" in pipeline_text
    assert "REQUIRED REVIEWERS" in pipeline_text


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
