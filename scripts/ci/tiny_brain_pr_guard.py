#!/usr/bin/env python3
"""SupremeAI Tiny Brain PR Guard — AI-Gated Auto-Merge client.

Tier 1: deterministic hard guard (forbidden paths + diff size floor).
Tier 2: SupremeAI Tiny Brain backend (/v1/brain/pr-risk).
Tier 3: human escalation comment when not auto-approved.
Fail-closed when Tiny Brain is unreachable.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

try:
    from ai_pr_evaluator import classify_pr_risk
except Exception:  # noqa: BLE001
    try:
        from scripts.ci.ai_pr_evaluator import classify_pr_risk
    except Exception:  # noqa: BLE001
        classify_pr_risk = None

try:
    from ai_auto_approver import approve_pending_deployment, post_pr_comment
except Exception:  # noqa: BLE001
    try:
        from scripts.ci.ai_auto_approver import approve_pending_deployment, post_pr_comment
    except Exception:  # noqa: BLE001
        approve_pending_deployment = None
        post_pr_comment = None

REPO = os.environ.get("GITHUB_REPOSITORY") or os.environ.get("GH_REPO") or "Supremeai-bd/supremeai"
DIFF_SIZE_FLOOR = 500
FORBIDDEN_PATH_PREFIXES = (
    "gateway/middleware/",
    "infrastructure/supabase/",
    "core/database/migrations/",
    "migrations/",
    "liquibase/",
    ".github/workflows/",
    "scripts/ci/render_",
    "scripts/ci/ai_",
)
FORBIDDEN_PATH_EXACT = {"gateway/service/keygen.py", "admin_auth.py", "render.yaml"}


def real_api(endpoint: str, method: str = "GET", payload: Any = None) -> Any:
    token = (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or "").strip()
    req = urllib.request.Request(
        f"https://api.github.com/{endpoint.lstrip('/')}",
        data=json.dumps(payload).encode() if payload is not None else None,
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


Api = Callable[[str, str, Any], Any]


def is_forbidden_path(path: str) -> bool:
    p = str(path or "").replace("\\", "/").strip().lstrip("/").lower()
    if not p:
        return False
    base = p.rsplit("/", 1)[-1]
    if p in FORBIDDEN_PATH_EXACT or base in FORBIDDEN_PATH_EXACT:
        return True
    if any("auth" in base for _ in [0]) and "auth" in base:
        # auth-related files
        pass
    if "auth" in base or "permission" in p or "keygen" in base:
        return True
    if "infisical" in p:
        return True
    if base.startswith(".env"):
        return True
    if any(k in p for k in ("payment", "billing", "quota", "rate_limit", "rate-limit")):
        return True
    for prefix in FORBIDDEN_PATH_PREFIXES:
        if p.startswith(prefix):
            return True
    return False


def tier1_violations(files: Any, diff_stats: dict | None = None) -> list[str]:
    paths = []
    if isinstance(files, list):
        for f in files:
            if isinstance(f, str):
                paths.append(f)
            elif isinstance(f, dict):
                paths.append(f.get("path") or f.get("filename") or f.get("name") or "")
    violations = [p for p in paths if is_forbidden_path(p)]
    stats = diff_stats or {}
    try:
        if int(stats.get("additions", 0) or 0) > DIFF_SIZE_FLOOR:
            violations.append(f"diff_size_floor_exceeded:{stats.get('additions')}")
    except (TypeError, ValueError):
        pass
    return violations


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
    else:
        pr.setdefault("files", pr.get("files") or [])
    if "statusCheckRollup" not in pr:
        sha = (pr.get("head") or {}).get("sha")
        if sha:
            try:
                data = api(f"repos/{REPO}/commits/{sha}/check-runs?per_page=100") or {}
                runs = data.get("check_runs", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                pr["statusCheckRollup"] = [
                    {"name": c.get("name", "?"),
                     "conclusion": (str(c.get("conclusion")).upper() if c.get("conclusion") is not None else None)
                     if c.get("status") == "completed" else None}
                    for c in (runs or [])
                ]
            except Exception:  # noqa: BLE001
                pr["statusCheckRollup"] = []
    return pr


def _checks_green(pr: dict) -> bool:
    checks = pr.get("statusCheckRollup") or []
    if not checks:
        return False
    failed = [c for c in checks if c.get("conclusion") and c["conclusion"] not in ("SUCCESS", "SKIPPED", "NEUTRAL")]
    pending = any(not c.get("conclusion") for c in checks)
    return (not failed) and (not pending)


def call_tiny_brain(pr_number: int, files: list[str], diff_stats: dict, ci_status: str,
                    url: str, token: str | None = None, timeout: int = 8) -> dict | None:
    payload = {
        "pr_number": pr_number,
        "files": files,
        "diff_stats": diff_stats,
        "ci_test_status": ci_status,
    }
    headers = {"Content-Type": "application/json"}
    if token:
        headers["x-brain-token"] = token
    try:
        req = urllib.request.Request(
            f"{url.rstrip('/')}/v1/brain/pr-risk",
            data=json.dumps(payload).encode(),
            method="POST",
            headers=headers,
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:  # noqa: BLE001
        return None


def register_hitl_request(
    pr_number: int,
    run_id: int | None,
    reason: str,
    violations: list[str],
    pr: dict[str, Any],
    gateway_url: str | None = None,
) -> bool:
    url_base = gateway_url or os.environ.get("GATEWAY_URL", "https://supremeai-api.onrender.com")
    url = f"{url_base.rstrip('/')}/api/v1/hitl/register"
    title = str(pr.get("title") or f"PR #{pr_number}")
    user = pr.get("user")
    author = user.get("login") if isinstance(user, dict) else "unknown"
    head_sha = ""
    if isinstance(pr.get("head"), dict):
        head_sha = pr["head"].get("sha", "")

    payload = {
        "id": f"pr-{pr_number}",
        "action_name": f"Auto-Merge Review Required for PR #{pr_number}",
        "command": f"gh pr merge {pr_number} --auto --squash",
        "module": "ci/tiny_brain_guard",
        "severity": "high",
        "context": {
            "pr_number": pr_number,
            "run_id": run_id,
            "title": title,
            "author": author,
            "reason": reason,
            "violations": violations,
            "head_sha": head_sha,
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    admin_key = os.environ.get("SUPREMEAI_ADMIN_KEY") or os.environ.get("MCP_ADMIN_KEY") or ""
    if admin_key:
        req.add_header("X-SupremeAI-Key", admin_key)
        req.add_header("Authorization", f"Bearer {admin_key}")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status in (200, 201)
    except Exception as e:
        print(f"Note: HITL registration on Gateway ({url}) skipped or deferred: {e}", file=sys.stderr)
        return False


def evaluate(pr_number: int, run_id: int | None = None, api: Api = real_api,
             brain_url: str | None = None, brain_token: str | None = None,
             dry_run: bool = False,
             gateway_url: str | None = None) -> dict[str, Any]:
    url = brain_url or os.environ.get("TINY_BRAIN_URL", "https://supremeai-tiny-brain.onrender.com")
    token = brain_token if brain_token is not None else os.environ.get("BRAIN_AUTH_TOKEN")
    pr = fetch_pr(pr_number, api)
    files = pr.get("files") or []
    paths = [ (f.get("path") or f.get("filename") or f.get("name")) if isinstance(f, dict) else str(f) for f in files ]
    paths = [p for p in paths if p]
    diff_stats = {"additions": pr.get("additions", 0), "deletions": pr.get("deletions", 0)}
    ci_status = "100%_PASS" if _checks_green(pr) else "FAIL"

    violations = tier1_violations(paths, diff_stats)
    if violations:
        reason_msg = f"tier1_forbidden ({', '.join(violations[:3])})"
        if not dry_run:
            post_pr_comment(pr_number, "🚨 **Human Review Required (Major Decision Detected)**: "
                            f"PR touches sensitive domain ({', '.join(violations[:3])}). "
                            "Escalated to @SaifulHaqueNiloy and @paykaribazaronline.", api)
            register_hitl_request(pr_number, run_id, reason_msg, violations, pr, gateway_url)
        return {"pr": pr_number, "verdict": "HUMAN_REVIEW", "risk": "HIGH",
                "reason": "tier1_forbidden", "violations": violations}

    if ci_status != "100%_PASS":
        if not dry_run:
            post_pr_comment(pr_number, "⏳ Tiny Brain: CI not fully green; holding auto-approval.", api)
            register_hitl_request(pr_number, run_id, "CI not fully green", [], pr, gateway_url)
        return {"pr": pr_number, "verdict": "HUMAN_REVIEW", "risk": "HIGH",
                "reason": "ci_not_green"}

    decision = call_tiny_brain(pr_number, paths, diff_stats, ci_status, url, token)
    if not decision:
        # fail-closed
        if not dry_run:
            post_pr_comment(pr_number, "⚠️  Tiny Brain unreachable; failing closed to human review.", api)
            register_hitl_request(pr_number, run_id, "Tiny Brain service unreachable (fail-closed)", [], pr, gateway_url)
        return {"pr": pr_number, "verdict": "HUMAN_REVIEW", "risk": "HIGH",
                "reason": "brain_unreachable"}

    verdict = str(decision.get("verdict", "HUMAN_REVIEW"))
    confidence = float(decision.get("confidence", 0.0) or 0.0)
    if verdict == "AUTO_MERGE" and confidence >= 0.90:
        if not dry_run:
            if run_id is not None:
                approve_pending_deployment(int(run_id), api=api)
            post_pr_comment(pr_number, f"✅ Tiny AI Brain Approved (Confidence: {confidence*100:.1f}%): Auto-landing enabled.", api)
        return {"pr": pr_number, "verdict": "AUTO_MERGE", "risk": "LOW",
                "confidence": confidence, "reasoning": decision.get("reasoning")}
    if not dry_run:
        post_pr_comment(pr_number, "⚠️ Tiny AI Brain requested manual review due to low confidence or complexity.", api)
    return {"pr": pr_number, "verdict": "HUMAN_REVIEW", "risk": "HIGH",
            "confidence": confidence, "reasoning": decision.get("reasoning")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="SupremeAI Tiny Brain PR Guard")
    ap.add_argument("--pr", type=int, required=True, help="Target PR number")
    ap.add_argument("--run-id", type=int, default=None, dest="run_id")
    ap.add_argument("--repo", default=None, help="Target repository override")
    ap.add_argument("--brain-url", default=None, dest="brain_url")
    ap.add_argument("--brain-token", default=None, dest="brain_token")
    ap.add_argument("--gateway-url", default=None, dest="gateway_url")
    ap.add_argument("--dry-run", action="store_true", dest="dry_run")
    ap.add_argument("--json", action="store_true", dest="as_json")
    opts = ap.parse_args(argv)

    if opts.repo:
        globals()["REPO"] = opts.repo

    result = evaluate(
        pr_number=opts.pr,
        run_id=opts.run_id,
        api=real_api,
        brain_url=opts.brain_url,
        brain_token=opts.brain_token,
        dry_run=opts.dry_run,
        gateway_url=opts.gateway_url,
    )
    # Emit GitHub Actions output for downstream job gating
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        try:
            with open(gh_out, "a", encoding="utf-8") as fh:
                fh.write("is_low_risk={}\n".format("true" if result.get("verdict") == "AUTO_MERGE" else "false"))
        except Exception:  # noqa: BLE001
            pass
    if opts.as_json:
        print(json.dumps(result))
    else:
        print(f"PR #{result['pr']}: verdict={result['verdict']} risk={result.get('risk')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
