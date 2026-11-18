#!/usr/bin/env python3
"""AI Auto-Approver for gated production deployments (AI-Gated Auto-Merge).

Classifies a PR as LOW/HIGH risk using scripts.ci.ai_pr_evaluator.classify_pr_risk.
For LOW risk + green CI, approves the pending production deployment via GitHub API
and posts an audit-trail comment. For HIGH risk, escalates to human reviewers.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

try:
    from ai_pr_evaluator import classify_pr_risk, checks_verdict, checks_pending, real_api as _eval_real_api
except Exception:  # noqa: BLE001
    try:
        from scripts.ci.ai_pr_evaluator import classify_pr_risk, checks_verdict, checks_pending, real_api as _eval_real_api
    except Exception:  # noqa: BLE001
        classify_pr_risk = None
        checks_verdict = None
        checks_pending = None
        _eval_real_api = None

REPO = os.environ.get("GITHUB_REPOSITORY") or os.environ.get("GH_REPO") or "Supremeai-bd/supremeai"
HUMAN_REVIEWERS = ("SaifulHaqueNiloy", "paykaribazaronline")


def real_api(endpoint: str, method: str = "GET", payload: dict | None = None) -> Any:
    if _eval_real_api is not None and _eval_real_api is not real_api:
        try:
            return _eval_real_api(endpoint, method, payload)
        except Exception:
            pass
    token = (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or "").strip()
    import urllib.request
    req = urllib.request.Request(
        f"https://api.github.com/{endpoint.lstrip('/')}",
        data=__import__("json").dumps(payload).encode() if payload is not None else None,
        method=method,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode()
    return json.loads(raw) if raw.strip() else None


if _eval_real_api is None:
    _eval_real_api = real_api


Api = Callable[[str, str, Any], Any]


def _checks_green(pr: dict) -> bool:
    if checks_verdict is None or checks_pending is None:
        checks = pr.get("statusCheckRollup") or []
        if not checks:
            return False
        failed = [c for c in checks if c.get("conclusion") and c["conclusion"] not in ("SUCCESS", "SKIPPED", "NEUTRAL")]
        pending = any(not c.get("conclusion") for c in checks)
        return (not failed) and (not pending)
    green, _failed = checks_verdict(pr)
    pending = checks_pending(pr)
    return bool(green) and (not pending)


def fetch_pr(pr_number: int, api: Api = real_api) -> dict:
    pr = api(f"repos/{REPO}/pulls/{pr_number}") or {}
    if not isinstance(pr, dict):
        pr = {}
    files = None
    try:
        files = api(f"repos/{REPO}/pulls/{pr_number}/files?per_page=100")
    except Exception:  # noqa: BLE001
        files = None
    if isinstance(files, list):
        pr.setdefault("files", files)
    elif isinstance(files, dict):
        pr.setdefault("files", files.get("items") or files.get("files") or [])
    else:
        pr.setdefault("files", pr.get("files") or [])
    if "statusCheckRollup" not in pr:
        sha = (pr.get("head") or {}).get("sha")
        if sha:
            try:
                data = api(f"repos/{REPO}/commits/{sha}/check-runs?per_page=100") or {}
                runs = data.get("check_runs", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                pr["statusCheckRollup"] = [
                    {
                        "name": c.get("name", "?"),
                        "conclusion": (str(c.get("conclusion")).upper() if c.get("conclusion") is not None else None)
                        if c.get("status") == "completed" else None,
                    }
                    for c in (runs or [])
                ]
            except Exception:  # noqa: BLE001
                pr["statusCheckRollup"] = []
    return pr


def _production_environment_id(api: Api = real_api) -> int | None:
    try:
        data = api(f"repos/{REPO}/environments")
        envs = data.get("environments", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        for env in envs or []:
            if isinstance(env, dict) and env.get("name") == "production":
                return env.get("id")
    except Exception:  # noqa: BLE001
        pass
    try:
        data = api(f"repos/{REPO}/environments/production")
        if isinstance(data, dict):
            return data.get("id")
    except Exception:  # noqa: BLE001
        pass
    return None


def approve_pending_deployment(run_id: int, api: Api = real_api, comment: str | None = None) -> bool:
    env_id = _production_environment_id(api)
    ids = [env_id] if env_id is not None else []
    payload = {
        "environment_ids": ids,
        "state": "approved",
        "comment": comment or "AI Approver: Low risk PR verified & approved.",
    }
    try:
        api(f"repos/{REPO}/actions/runs/{run_id}/pending_deployments", "POST", payload)
        return True
    except Exception:  # noqa: BLE001
        return False


def post_pr_comment(pr_number: int, body: str, api: Api = real_api) -> bool:
    try:
        api(f"repos/{REPO}/issues/{pr_number}/comments", "POST", {"body": body})
        return True
    except Exception:  # noqa: BLE001
        return False


def evaluate(pr_number: int, run_id: int | None = None, api: Api = real_api,
             dry_run: bool = False) -> dict[str, Any]:
    pr = fetch_pr(pr_number, api)
    files = pr.get("files") or []
    diff = "\n".join(
        (f.get("patch") if isinstance(f, dict) else str(f)) or ""
        for f in files
    )
    risk = classify_pr_risk(files, diff, pr) if classify_pr_risk is not None else "HIGH"
    green = _checks_green(pr)
    result = {
        "pr": pr_number,
        "risk": risk,
        "checks_green": green,
        "run_id": run_id,
    }
    if risk == "LOW" and green:
        if not dry_run:
            if run_id is not None:
                approve_pending_deployment(int(run_id), api=api)
            post_pr_comment(
                pr_number,
                "AI Review Verdict: Low Risk (Confidence: high). Auto-approving merge.",
                api,
            )
    elif risk == "HIGH":
        if not dry_run:
            post_pr_comment(
                pr_number,
                "🚨 Major Decision Detected (Auth/DB/CI changes). Escalating to "
                "@SaifulHaqueNiloy & @paykaribazaronline for manual review.",
                api,
            )
    else:
        if not dry_run:
            post_pr_comment(
                pr_number,
                "⏳ AI Auto-Approver: CI not 100% green; holding auto-approval.",
                api,
            )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI PR Auto-Approver")
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--run-id", type=int, default=None, dest="run_id")
    parser.add_argument("--repo", default=None)
    parser.add_argument("--dry-run", action="store_true", dest="dry_run")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    global REPO
    if args.repo:
        REPO = args.repo

    result = evaluate(args.pr, args.run_id, real_api, args.dry_run)
    if args.as_json:
        print(json.dumps(result))
    else:
        print(f"PR #{result['pr']}: risk={result['risk']} checks_green={result['checks_green']}")
    return 0


# Backwards/alias exports for callers and tests
classify_risk = classify_pr_risk
run = evaluate
approve = approve_pending_deployment
