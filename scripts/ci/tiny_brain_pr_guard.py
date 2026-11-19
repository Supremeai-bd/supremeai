#!/usr/bin/env python3
"""Read-only landing decision for the unified PR workflow; no model or approval API."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Callable

REPO = "Supremeai-bd/supremeai"
AUTO_MERGE = "AUTO_MERGE"
BLOCKED = "BLOCKED"
OWNER_REVIEW = "OWNER_REVIEW"

RESOLVE = "resolve-execution-tier"
LOCAL = "render-heavy-gate"
RENDER = "render-heavy-gate-render-ci"
FALLBACK = "render-heavy-gate-fallback"
HEAVY_JOBS = {
    "local-self-hosted": LOCAL,
    "render-ci-runner": RENDER,
    "github-ubuntu-render-backend": FALLBACK,
    "github-ubuntu-emergency": "render-heavy-gate-emergency",
}

# Paths with authority over approval, credentials, data isolation or production.
# No diff-size or model-confidence inputs to the owner decision.
PROTECTED_PREFIXES = (
    ".github/workflows/",
    ".github/actions/",
    ".github/constitution/",
    ".github/codeql/",
    ".github/scripts/constitution/",
    "core/security/",
    "core/services/hitl/",
    "gateway/middleware/",
    "core/alembic_migrations/",
    "core/database/migrations/",
    "core/database/supabase/",
    "core/scripts/migrations/",
    "infrastructure/supabase/",
    "infrastructure/mcp-control-plane/src/policy/",
    "infrastructure/mcp-control-plane/src/tenancy/",
    "migrations/",
    "liquibase/",
    "scripts/deploy/",
    "scripts/ops/deploy/",
)
PROTECTED_PATHS = {
    ".github/codeowners",
    "config/ci/pr-battery.args",
    "config/service_registry.yaml",
    "core/config/service_topology.yaml",
    "core/api/dependencies.py",
    "core/api/routes/admin_auth.py",
    "core/api/routes/api_keys.py",
    "core/api/routes/auth.py",
    "core/api/routes/keys.py",
    "core/api/routes/tenant_admin.py",
    "core/cache/multi_layer_cache.py",  # Stores tenant/user-scoped sessions.
    "core/middleware/cors_policy.py",
    "core/middleware/security.py",
    # Provider core: a single bad edit here silently degrades every chat
    # request (transport URLs, failover order, circuit breaker, rate limits).
    # Every path below has live-customer blast radius, so it needs a human.
    "gateway/provider_chain.py",
    "gateway/circuit_breaker.py",
    "gateway/routing_policy.json",
    "gateway/main.py",
    "gateway/config.py",
    "gateway/service/providers/adapters.py",
    "gateway/service/providers/pool.py",
    "gateway/service/admin_auth.py",
    "gateway/service/auth_identity.py",
    "gateway/service/keygen.py",
    "gateway/service/passkey_auth.py",
    "infrastructure/mcp-control-plane/src/guardian/policy.ts",
    "render.yaml",
    "scripts/ci/ai_auto_approver.py",
    "scripts/ci/ai_pr_evaluator.py",
    "scripts/ci/ai_semantic_pr_verifier.py",
    "scripts/ci/infisical_loader.py",
    "scripts/ci/merge_gate.py",
    "scripts/ci/plan_render_deploys.py",
    "scripts/ci/production_release_gate.py",
    "scripts/ci/readiness_contract.py",
    "scripts/ci/render_canary.py",
    "scripts/ci/render_deploy_attestation.py",
    "scripts/ci/render_trigger_deploy.py",
    "scripts/ci/resolve_execution_tier.py",
    "scripts/ci/tiny_brain_pr_guard.py",
    "scripts/lib/render_client.py",
    "scripts/runtime/infisical_bootstrap.py",
}

Api = Callable[[str], Any]


def read_api(endpoint: str) -> Any:
    result = subprocess.run(
        ["gh", "api", "--method", "GET", endpoint],
        check=True, capture_output=True, text=True, timeout=20,
    )
    return json.loads(result.stdout)


def ci_block_reason(needs: dict | None, merge_sha: str) -> str | None:
    """Require named successes in this run, with only the configured Render alternative."""
    if not isinstance(needs, dict):
        return "ci_evidence_invalid"

    def result(job: str) -> str | None:
        return needs.get(job, {}).get("result")

    def not_successful(jobs: tuple[str, ...]) -> str | None:
        return next((f"ci_not_success:{job}" for job in jobs if result(job) != "success"), None)

    reason = not_successful((RESOLVE, "syntax-and-governance-gate", "golden-eval-gate"))
    if reason:
        return reason
    tier = needs[RESOLVE].get("outputs", {}).get("execution_tier")
    heavy_job = HEAVY_JOBS.get(tier)
    if heavy_job is None:
        return "unknown_execution_tier"
    if heavy_job == LOCAL:
        return not_successful((LOCAL,))
    if heavy_job == RENDER:
        render_outputs = needs.get(RENDER, {}).get("outputs", {})
        if result(RENDER) == "failure" and render_outputs.get("fallback_allowed") == "true":
            heavy_job = FALLBACK
        elif result(RENDER) == "success" and render_outputs.get("verified_sha") != merge_sha:
            return "render_tested_sha_missing_or_mismatched"
    return not_successful(("fast-gate", "runtime-readiness", heavy_job))


class BlockLanding(ValueError):
    """Known, actionable reason to do nothing, not to ask the owner."""


def _current_pr(pr_number: int, *, repo: str, head_sha: str, base_sha: str, merge_sha: str, api: Api) -> dict:
    if not all(re.fullmatch(r"[0-9a-f]{40}", sha) for sha in (head_sha, base_sha, merge_sha)):
        raise BlockLanding("candidate_sha_missing_or_invalid")
    pr = api(f"repos/{repo}/pulls/{pr_number}")
    if pr.get("number") != pr_number or pr.get("state") != "open" or pr.get("draft") is not False:
        raise BlockLanding("pr_not_open_and_ready")
    head, base = pr["head"], pr["base"]
    if head["repo"]["full_name"].lower() != repo.lower() or base["repo"]["full_name"].lower() != repo.lower():
        raise BlockLanding("pr_not_same_repository")
    if base["ref"] != "main":
        raise BlockLanding("pr_not_targeting_main")
    if head["sha"] != head_sha:
        raise BlockLanding("pr_head_changed")
    if base["sha"] != base_sha or api(f"repos/{repo}/git/ref/heads/main")["object"]["sha"] != base_sha:
        raise BlockLanding("pr_base_changed")
    if pr.get("mergeable") is not True or pr.get("merge_commit_sha") != merge_sha:
        raise BlockLanding("tested_merge_revision_not_current")
    return pr


def _changed_paths(endpoint: str, count: int, api: Api) -> set[str]:
    # GitHub's PR files endpoint caps the list at 3,000. Never classify a partial diff.
    if type(count) is not int or not 0 < count <= 3000:
        raise BlockLanding("changed_paths_incomplete")
    filenames: set[str] = set()
    previous: set[str] = set()
    for page in range(1, (count + 99) // 100 + 1):
        items = api(f"{endpoint}/files?per_page=100&page={page}")
        if not isinstance(items, list) or len(items) != min(100, count - 100 * (page - 1)):
            raise BlockLanding("changed_paths_incomplete")
        for item in items:
            filename = item["filename"]
            old_name = item.get("previous_filename")
            if not isinstance(filename, str) or not filename or filename in filenames:
                raise BlockLanding("changed_paths_incomplete")
            if old_name is not None or item.get("status") == "renamed":
                if not isinstance(old_name, str) or not old_name:
                    raise BlockLanding("changed_paths_incomplete")
                previous.add(old_name)
            filenames.add(filename)
    return filenames | previous


def is_protected_path(path: str) -> bool:
    path = path.lower()
    return path.startswith(PROTECTED_PREFIXES) or path in PROTECTED_PATHS or path.rsplit("/", 1)[-1].startswith(".env")


def evaluate(
    pr_number: int, *, needs: dict | None, head_sha: str, base_sha: str, merge_sha: str,
    repo: str = REPO, api: Api = read_api, recheck: bool = False,
) -> dict:
    candidate = dict(repo=repo, head_sha=head_sha, base_sha=base_sha, merge_sha=merge_sha, api=api)
    try:
        if recheck:
            _current_pr(pr_number, **candidate)
            return {"reason": "tested_candidate_current"}

        reason = ci_block_reason(needs, merge_sha)
        if reason:
            raise BlockLanding(reason)
        pr = _current_pr(pr_number, **candidate)
        merge = api(f"repos/{repo}/git/commits/{merge_sha}")
        if merge["sha"] != merge_sha or [p["sha"] for p in merge["parents"]] != [base_sha, head_sha]:
            raise BlockLanding("tested_merge_parents_mismatch")
        paths = _changed_paths(f"repos/{repo}/pulls/{pr_number}", pr["changed_files"], api)
        # PR files are mutable API data. Re-read the PR after pagination.
        _current_pr(pr_number, **candidate)
        protected = sorted(p for p in paths if is_protected_path(p))
        if protected:
            return {"decision": OWNER_REVIEW, "reason": "protected_paths_changed", "paths": protected}
        return {"decision": AUTO_MERGE, "reason": "required_ci_passed_routine_scope"}
    except BlockLanding as exc:
        return {"decision": BLOCKED, "reason": str(exc)}
    except (AttributeError, KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError):
        return {"decision": BLOCKED, "reason": "candidate_or_ci_evidence_unavailable"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY", REPO))
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--merge-sha", required=True)
    parser.add_argument("--recheck-candidate", action="store_true")
    args = parser.parse_args(argv)
    try:
        needs = {} if args.recheck_candidate else json.loads(os.getenv("PR_GATE_RESULTS", "{}"))
    except ValueError:
        needs = None
    result = evaluate(
        args.pr, needs=needs, repo=args.repo, head_sha=args.head_sha,
        base_sha=args.base_sha, merge_sha=args.merge_sha, recheck=args.recheck_candidate,
    )
    print(json.dumps(result))
    if not args.recheck_candidate and (output := os.getenv("GITHUB_OUTPUT")):
        with Path(output).open("a", encoding="utf-8") as stream:
            stream.write(f"decision={result['decision']}\nreason={result['reason']}\n")
    if result.get("decision") == BLOCKED:
        print(f"::error::PR landing blocked: {result['reason']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
