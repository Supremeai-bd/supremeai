#!/usr/bin/env python3
"""Evaluate runner availability and compute the execution target for CI/CD and Audits.

Evaluation logic (4-Tier SSOT per docs/PR_TO_PRODUCTION_LIFECYCLE.md):
  - Priority 1: Local PC online -> 'local-self-hosted' (0 cloud/render mins)
  - Priority 2: Local offline + Render quota > 50m remaining -> 'render-ci-runner'
  - Priority 3: Local offline + Render CI worker busy but quota < 450m used -> 'github-ubuntu-render-backend'
  - Priority 4: Local offline + Render quota exhausted (>= 450m used) -> 'github-ubuntu-emergency'

Job 1 budget: probes run in parallel with tight timeouts to stay <10s.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from pathlib import Path

# Reuse the canonical local-runner probe to avoid code duplication (Zero-Recurrence Invariant).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_opportunistic_audit import is_local_runner_online  # noqa: E402

PROBE_TIMEOUT_S = 4.0
PROBE_BUDGET_S = 7.0
QUOTA_UNKNOWN_REMAINING = 120.0  # transient probe failure: avoid P4 jump, still block P2 unless worker+quota known safe


def _render_api_key() -> str | None:
    for name in (
        "RENDER_API_KEY_PAYKARI",
        "RENDER_API_KEY",
        "RENDER_API_KEY_1",
        "RENDER_API_KEY_2",
        "RENDER_API_KEY_3",
        "RENDER_API_KEY_4",
        "RENDER_API_KEY_5",
        "RENDER_API_KEY_6",
    ):
        val = (os.environ.get(name) or "").strip()
        if val:
            return val
    return None


def get_render_quota_remaining() -> tuple[float, bool]:
    """Return (remaining_minutes, known). known=False on probe failure/missing key."""
    api_key = _render_api_key()
    if not api_key:
        print("::warning::Render quota key missing; treating quota as unknown (no P2)", file=sys.stderr)
        return QUOTA_UNKNOWN_REMAINING, False

    try:
        req = urllib.request.Request(
            "https://api.render.com/v1/billing/usage",
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=PROBE_TIMEOUT_S) as resp:
            data = json.loads(resp.read().decode())
        limit = float(data.get("limit") or data.get("monthlyLimit") or 500.0)
        used = float(data.get("used") or data.get("usedMinutes") or 0.0)
        return max(0.0, limit - used), True
    except Exception as exc:
        print(
            f"::warning::Render quota probe failed ({exc}); quota unknown (no P2, prefer P3 over P4)",
            file=sys.stderr,
        )
        return QUOTA_UNKNOWN_REMAINING, False


def is_render_ci_worker_available() -> bool:
    """Check if the Render CI runner service is reachable with valid credentials."""
    api_key = _render_api_key()
    svc_id = (os.environ.get("RENDER_CI_RUNNER_SERVICE_ID") or "srv-dbl8tbmtlv9c73bbkvqg").strip()
    if not api_key or not svc_id:
        return False
    try:
        req = urllib.request.Request(
            f"https://api.render.com/v1/services/{svc_id}",
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=PROBE_TIMEOUT_S) as resp:
            if resp.status >= 400:
                return False
            data = json.loads(resp.read().decode())
        obj = data.get("service", data) if isinstance(data, dict) else {}
        if isinstance(obj, dict):
            suspended = str(obj.get("suspended") or "").lower() in ("suspended", "true", "1")
            if suspended:
                return False
        return True
    except Exception as exc:
        print(f"::warning::Render CI worker probe failed ({exc}); not selecting Priority 2", file=sys.stderr)
        return False


def resolve_tier() -> str:
    # Priority 1: Local PC Online (fast path)
    try:
        if is_local_runner_online():
            return "local-self-hosted"
    except Exception as exc:
        print(f"::warning::Local runner probe error ({exc}); continuing to cloud tiers", file=sys.stderr)

    # Parallel quota + worker probes with budget
    remaining, quota_known = QUOTA_UNKNOWN_REMAINING, False
    worker_ok = False
    try:
        with ThreadPoolExecutor(max_workers=2) as ex:
            fq = ex.submit(get_render_quota_remaining)
            fw = ex.submit(is_render_ci_worker_available)
            try:
                remaining, quota_known = fq.result(timeout=PROBE_BUDGET_S)
            except FuturesTimeout:
                print("::warning::Quota probe budget exceeded; quota unknown", file=sys.stderr)
                remaining, quota_known = QUOTA_UNKNOWN_REMAINING, False
            except Exception as exc:
                print(f"::warning::Quota probe error ({exc}); quota unknown", file=sys.stderr)
                remaining, quota_known = QUOTA_UNKNOWN_REMAINING, False
            try:
                worker_ok = bool(fw.result(timeout=max(0.5, PROBE_BUDGET_S - 0.5)))
            except FuturesTimeout:
                print("::warning::Worker probe budget exceeded; worker unavailable", file=sys.stderr)
                worker_ok = False
            except Exception as exc:
                print(f"::warning::Worker probe error ({exc}); worker unavailable", file=sys.stderr)
                worker_ok = False
    except Exception as exc:
        print(f"::warning::Parallel probe execution failed ({exc}); using safe defaults", file=sys.stderr)

    used = 500.0 - remaining

    # Priority 2: Render CI Runner (quota > 50m remaining AND known)
    if quota_known and remaining >= 50.0 and worker_ok:
        return "render-ci-runner"

    # Priority 3: GitHub Ubuntu + Render backend free build time (< 450m used) or quota unknown (prefer P3 over P4)
    if used < 450.0 or not quota_known:
        return "github-ubuntu-render-backend"

    # Priority 4: GitHub Ubuntu Emergency (quota exhausted, known)
    return "github-ubuntu-emergency"


def main() -> int:
    tier = resolve_tier()
    print(f"SELECTED_EXECUTION_TIER={tier}")

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"execution_tier={tier}\n")
            f.write(f"is_local_online={'true' if tier == 'local-self-hosted' else 'false'}\n")
            f.write(f"render_quota_exhausted={'true' if tier == 'github-ubuntu-emergency' else 'false'}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
