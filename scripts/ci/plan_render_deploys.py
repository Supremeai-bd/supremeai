#!/usr/bin/env python3
"""Plan changed Render services from the commit diff.

The script emits GitHub Actions output:
  matrix={"include":[{"service":"core", "service_id":"..."}]}
  has_services=true|false
  unregistered=service:env_name,...

Service IDs are read from GitHub Actions variables, not committed source:
  RENDER_CORE_SERVICE_ID
  RENDER_API_SERVICE_ID
  RENDER_BROWSER_SERVICE_ID
  RENDER_MCP_SERVICE_ID

Failure policy (run 41918034520 root cause):
  A topology change (render.yaml, this planner) previously required EVERY
  declared service ID to be configured, and failed the whole job when any one
  was missing. That is fail-closed to the point of self-sabotage: the planner
  could not run at all until an operator manually configured four variables,
  so no deployment ever happened and the job stayed red.

  New policy: a missing ID is never a workflow failure. The affected service is
  marked UNREGISTERED and skipped from the deploy matrix, but the skip is
  LOUD — written to GITHUB_OUTPUT as `unregistered` and printed as a
  GitHub warning. Silence is the bug we are fixing; a skipped service must be
  visible in the run log and in MCP Tower attestation, not invisible.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


SERVICE_RULES = {
    "core": (
        "RENDER_CORE_SERVICE_ID",
        "RENDER_API_KEY",
        ("core/", "requirements", "pyproject.toml", "Dockerfile", "scripts/lib/", "scripts/runtime/"),
    ),
    "api": (
        "RENDER_API_SERVICE_ID",
        "RENDER_API_KEY_5",
        ("gateway/", "config/routing_policy", "render.yaml", "scripts/lib/"),
    ),
    "scraper": (
        "RENDER_SCRAPER_SERVICE_ID",
        "RENDER_API_KEY_3",
        ("browser/", "core/", "render.yaml", "scripts/lib/", "scripts/runtime/"),
    ),
    "mcp": (
        "RENDER_MCP_SERVICE_ID",
        "RENDER_API_KEY_4",
        ("infrastructure/mcp-control-plane/", "scripts/runtime/", "render.yaml"),
    ),
    "worker": (
        "RENDER_WORKER_SERVICE_ID",
        "RENDER_API_KEY_2",
        ("core/", "scripts/lib/", "scripts/runtime/"),
    ),
    "brain": (
        "RENDER_BRAIN_SERVICE_ID",
        "RENDER_API_KEY_6",
        ("core/services/brain/", "core/", "scripts/lib/"),
    ),
    "ci-runner": (
        "RENDER_CI_RUNNER_SERVICE_ID",
        "RENDER_API_KEY_PAYKARI",
        ("scripts/ci/", "scripts/ops/", "scripts/lib/"),
    ),
}

# Files that widen the contract: when any of these change, every declared
# service must be re-verified even if its own paths did not change.
TOPOLOGY_FILES = {"render.yaml", "scripts/ci/plan_render_deploys.py"}


def changed_files(base: str, head: str) -> list[str]:
    if not base or set(base) == {"0"}:
        base = subprocess.check_output(["git", "rev-parse", f"{head}^"], text=True).strip()
    result = subprocess.check_output(
        ["git", "diff", "--name-only", base, head], text=True
    )
    return [line.strip() for line in result.splitlines() if line.strip()]


def _matches(path: str, prefixes) -> bool:
    return any(path == prefix or path.startswith(prefix) for prefix in prefixes)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    files = changed_files(args.base, args.head)
    topology_changed = any(path in TOPOLOGY_FILES for path in files)

    selected: list[dict[str, str]] = []
    unregistered: list[str] = []

    services = list(SERVICE_RULES.items())
    if topology_changed:
        # Widen: every declared service is a candidate, regardless of paths.
        candidates = services
    else:
        candidates = [
            (service, rule)
            for service, rule in services
            if any(_matches(path, rule[2]) for path in files)
        ]

    for service, (env_name, api_key_env, _prefixes) in candidates:
        service_id = os.environ.get(env_name, "").strip()
        if not service_id:
            unregistered.append(f"{service}:{env_name}")
            print(
                f"::warning::{service} changed but {env_name} is not configured — "
                f"marking UNREGISTERED and skipping deploy (visible, not silent)",
                file=sys.stderr,
            )
        else:
            selected.append({"service": service, "service_id": service_id, "api_key_env": api_key_env})

    matrix = json.dumps({"include": selected}, separators=(",", ":"))
    output = args.output or os.environ.get("GITHUB_OUTPUT", "")
    if output:
        with Path(output).open("a", encoding="utf-8") as handle:
            handle.write(f"matrix={matrix}\n")
            handle.write(f"has_services={'true' if selected else 'false'}\n")
            handle.write(
                f"unregistered={json.dumps(unregistered, separators=(',', ':'))}\n"
            )
    print(json.dumps({"changed_files": files, "matrix": json.loads(matrix)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())