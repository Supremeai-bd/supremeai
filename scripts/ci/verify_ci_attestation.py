#!/usr/bin/env python3
"""Verify a signed-by-transport CI attestation from MCP Tower.

Used by the Autonomous Auto-Landing gate or out-of-band landing orchestrator
to verify that an authoritative heavy verification battery (local self-hosted
or Render CI runner) completed successfully for the target commit SHA within
an acceptable freshness window.

Environment:
  MCP_TOWER_ATTESTATION_URL  (endpoint e.g. https://supremeai-mcp-tower.onrender.com/api/ci/attestation)
  MCP_TOWER_AUTH_TOKEN       (bearer auth token)
  EXPECTED_SHA               (target commit SHA)
  GITHUB_REPOSITORY          (repo e.g. Supremeai-bd/supremeai)
  ALLOWED_RUNNERS            (optional comma-separated list of acceptable runner targets)
  MAX_AGE_SECONDS            (freshness window in seconds, default: 7200)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request

DEFAULT_ALLOWED_RUNNERS = {
    "local-self-hosted",
    "render-ci-runner",
    "github-ubuntu-render-backend",
    "github-ubuntu-emergency",
}


def fail(message: str) -> int:
    print(f"::error::{message}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify CI attestation from MCP Tower")
    parser.add_argument("--sha", default=None, help="Target commit SHA")
    parser.add_argument("--repo", default=None, help="Target repository")
    parser.add_argument("--allowed-runners", default=None, help="Comma-separated allowed runner targets")
    parser.add_argument("--max-age", type=int, default=7200, help="Max attestation age in seconds")
    args = parser.parse_args()

    url = (os.environ.get("MCP_TOWER_ATTESTATION_URL") or "").strip()
    token = (os.environ.get("MCP_TOWER_AUTH_TOKEN") or "").strip()
    expected_sha = (args.sha or os.environ.get("EXPECTED_SHA") or os.environ.get("GITHUB_SHA") or "").strip()
    repo = (args.repo or os.environ.get("GITHUB_REPOSITORY") or "Supremeai-bd/supremeai").strip()

    if not expected_sha:
        return fail("EXPECTED_SHA must be provided via env or --sha")

    allowed_runners = DEFAULT_ALLOWED_RUNNERS
    if args.allowed_runners:
        allowed_runners = {r.strip() for r in args.allowed_runners.split(",") if r.strip()}
    elif os.environ.get("ALLOWED_RUNNERS"):
        allowed_runners = {r.strip() for r in os.environ["ALLOWED_RUNNERS"].split(",") if r.strip()}

    if not url:
        print("::warning::MCP_TOWER_ATTESTATION_URL not configured; fail-closed verification refuses unverified landing")
        return fail("Attestation URL not configured")

    query = urllib.parse.urlencode({"sha": expected_sha, "repo": repo})
    full_url = f"{url}?{query}" if "?" not in url else f"{url}&{query}"

    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(full_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status != 200:
                return fail(f"MCP Tower returned HTTP {resp.status} for attestation query")
            body = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return fail(f"Failed to query attestation from MCP Tower: {exc}")

    attestation = body.get("attestation") if isinstance(body, dict) else None
    if not attestation or not isinstance(attestation, dict):
        return fail(f"No attestation found for SHA {expected_sha}")

    result = attestation.get("result")
    if result != "success":
        return fail(f"Attestation result for SHA {expected_sha} is not successful (result: {result})")

    target = attestation.get("runner_target", "unknown")
    if target not in allowed_runners:
        return fail(
            f"Attestation runner_target '{target}' is not in allowed list: {sorted(allowed_runners)}"
        )

    ts = float(attestation.get("timestamp") or 0.0)
    now = time.time()
    if ts <= 0 or (now - ts) > args.max_age:
        age_m = (now - ts) / 60.0 if ts > 0 else -1
        return fail(
            f"Attestation for SHA {expected_sha} is expired or timestamp invalid (age: {age_m:.1f}m, limit: {args.max_age/60:.1f}m)"
        )

    print(
        f"CI attestation verified: SHA={expected_sha} runner={target} result=success (age: {(now - ts):.1f}s)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

