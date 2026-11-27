#!/usr/bin/env python3
"""The two SSOT files must not disagree about where a service is deployed.

`core/config/service_topology.yaml` (watch paths / deploy keys) and
`config/service_registry.yaml` (runtime identity / platform / hosts) both
declare a `platform` per service. They disagreed on `frontend`: the topology
said **vercel** while the registry said **cloudflare**, and the Vercel hosting
is retired (ECOSYSTEM_MAP.md:24 records the build as an archived console).

That disagreement is not cosmetic. It is the shape of the failure this whole
change is about: a retired platform stayed wired, and the live one could not
deploy.

The comparison is derived from the two files, so a future service addition or
migration is checked automatically — no list to update.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
TOPOLOGY = REPO_ROOT / "core" / "config" / "service_topology.yaml"
REGISTRY = REPO_ROOT / "config" / "service_registry.yaml"
PIPELINE = REPO_ROOT / ".github" / "workflows" / "unified-pipeline.yml"


def _services(path: Path) -> dict:
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("services") or {}


def test_platforms_agree_across_both_ssot_files():
    topology = _services(TOPOLOGY)
    registry = _services(REGISTRY)
    assert topology, "topology declares no services"
    assert registry, "registry declares no services"

    disagreements = [
        f"{name}: topology={topology[name].get('platform')!r} "
        f"registry={registry[name].get('platform')!r}"
        for name in sorted(set(topology) & set(registry))
        if topology[name].get("platform") != registry[name].get("platform")
    ]
    assert not disagreements, "SSOT platform drift: " + "; ".join(disagreements)


def test_frontend_is_not_on_the_retired_platform():
    registry = _services(REGISTRY)
    assert registry["frontend"]["platform"] != "vercel", (
        "frontend is declared on Vercel again, but that hosting is retired"
    )


def test_cloudflare_deploy_runs_on_push_when_the_proxy_changes():
    """`inputs.target_service` is EMPTY on push, so a condition written only
    against inputs can never fire from main — which is how the edge proxy never
    picked up its own origin change while the retired Vercel job did."""
    job = yaml.safe_load(PIPELINE.read_text(encoding="utf-8"))["jobs"]["deploy-cloudflare"]
    condition = str(job.get("if") or "")
    assert "github.event_name == 'push'" in condition, (
        "deploy-cloudflare cannot run on push — it will never deploy the proxy"
    )
    # 2026-11-27: `join(github.event.commits.*.modified, ' ')` is a list of
    # LISTS — join() stringifies each inner list as "Array", so a contains()
    # path check there is ALWAYS false and the job was skipped on every push
    # (keep-warm worker + proxy never auto-deployed). The path filter must be a
    # real `git diff` inside the job, never this expression.
    assert "join(github.event.commits" not in condition, (
        "deploy-cloudflare uses join(github.event.commits.*.X) — always false; filter with git diff in a step"
    )
    steps = {str(s.get("name")): s for s in job.get("steps", [])}
    detect = str(steps["Detect Cloudflare-relevant changes"].get("run") or "")
    assert 'git diff --name-only "$BASE" "$HEAD"' in detect
    # Per-worker flags: each worker deploys when ITS directory changed
    # (added/modified/removed all show up in git diff --name-only).
    for flag, path in (("KEEPWARM", "infrastructure/cloudflare-render-keepwarm/"),
                       ("PROXY", "infrastructure/cloudflare-studio-proxy/")):
        assert f"grep -qE '^{path}'" in detect, f"detect step ignores {path}"
        assert f'{flag}="true"' in detect
    assert steps["Deploy Keep-Warm Worker"].get("if") == "steps.cf_changes.outputs.keepwarm == 'true'"
    assert steps["Deploy Studio Edge Proxy"].get("if") == "steps.cf_changes.outputs.proxy == 'true'"


def test_vercel_auto_deploy_is_retired():
    """The retired platform must not be redeployed by a path match."""
    job = yaml.safe_load(PIPELINE.read_text(encoding="utf-8"))["jobs"]["deploy-vercel"]
    condition = str(job.get("if") or "")
    assert "github.event.commits" not in condition, (
        "deploy-vercel still auto-deploys on push path matches; Vercel hosting is retired"
    )
    assert "workflow_dispatch" in condition, (
        "deploy-vercel should remain reachable by an explicit dispatch"
    )


def test_no_job_condition_contains_a_comment_line():
    """A `#` inside an `if: |` block scalar is EXPRESSION TEXT, not a comment.

    Exactly this shipped in #723: explanatory comments were placed inside
    deploy-vercel's `if: |`, so the condition began with "# Vercel hosting…".
    GitHub rejected the workflow at parse time — the run failed with ZERO jobs
    and no annotation, which reads like an infra outage rather than a typo.
    Comments belong above the `if:` key.
    """
    jobs = yaml.safe_load(PIPELINE.read_text(encoding="utf-8"))["jobs"]
    offenders = [
        name
        for name, spec in jobs.items()
        if any(
            line.strip().startswith("#")
            for line in str((spec or {}).get("if") or "").splitlines()
        )
    ]
    assert not offenders, (
        "these jobs put comments inside their `if:` expression (GitHub will "
        f"reject the whole workflow): {offenders}"
    )


def test_every_job_condition_is_a_single_expression():
    """Guard the same class from the other side: no stray prose in `if:`."""
    jobs = yaml.safe_load(PIPELINE.read_text(encoding="utf-8"))["jobs"]
    for name, spec in jobs.items():
        condition = (spec or {}).get("if")
        if condition is None:
            continue
        text = str(condition).strip()
        assert text, f"{name} has an empty if:"
        assert "This job" not in text and "RETIRED:" not in text, (
            f"{name}'s if: contains prose — it must be an expression only"
        )
