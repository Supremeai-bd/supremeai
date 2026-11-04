#!/usr/bin/env python3
"""Plan changed Render services from the commit diff.

The script emits GitHub Actions output:
  matrix={"include":[{"service":"core", "service_id":"..."}]}
  has_services=true|false

Service IDs are read from GitHub Actions variables, not committed source:
  RENDER_CORE_SERVICE_ID
  RENDER_API_SERVICE_ID
  RENDER_BROWSER_SERVICE_ID
  RENDER_MCP_SERVICE_ID

If a service's files changed but its ID is not configured, the workflow fails
loudly instead of silently deploying the wrong service.
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
        ("core/", "requirements", "pyproject.toml", "Dockerfile", "scripts/lib/", "scripts/runtime/"),
    ),
    "api": (
        "RENDER_API_SERVICE_ID",
        ("gateway/", "config/routing_policy", "render.yaml", "scripts/lib/"),
    ),
    "browser": (
        "RENDER_BROWSER_SERVICE_ID",
        ("browser/", "render.yaml", "scripts/lib/"),
    ),
    "mcp": (
        "RENDER_MCP_SERVICE_ID",
        ("infrastructure/mcp-control-plane/", "scripts/runtime/", "render.yaml"),
    ),
}


def changed_files(base: str, head: str) -> list[str]:
    if not base or set(base) == {"0"}:
        base = subprocess.check_output(["git", "rev-parse", f"{head}^"], text=True).strip()
    result = subprocess.check_output(
        ["git", "diff", "--name-only", base, head], text=True
    )
    return [line.strip() for line in result.splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    files = changed_files(args.base, args.head)
    selected: list[dict[str, str]] = []
    missing: list[str] = []

    for service, (env_name, prefixes) in SERVICE_RULES.items():
        if not any(path == prefix or path.startswith(prefix) for path in files for prefix in prefixes):
            continue
        service_id = os.environ.get(env_name, "").strip()
        if not service_id:
            missing.append(f"{service} ({env_name})")
        else:
            selected.append({"service": service, "service_id": service_id})

    if missing:
        print("Missing service IDs for changed Render targets: " + ", ".join(missing), file=sys.stderr)
        return 1

    # A repository-wide deployment contract change must refresh all declared
    # services, but ordinary studio/docs-only changes must not build backends.
    if any(path in {"render.yaml", "scripts/ci/plan_render_deploys.py"} for path in files):
        selected = []
        for service, (env_name, _prefixes) in SERVICE_RULES.items():
            service_id = os.environ.get(env_name, "").strip()
            if service_id:
                selected.append({"service": service, "service_id": service_id})
            else:
                missing.append(f"{service} ({env_name})")
        if missing:
            print("Missing service IDs for topology change: " + ", ".join(missing), file=sys.stderr)
            return 1

    matrix = json.dumps({"include": selected}, separators=(",", ":"))
    output = args.output or os.environ.get("GITHUB_OUTPUT", "")
    if output:
        with Path(output).open("a", encoding="utf-8") as handle:
            handle.write(f"matrix={matrix}\n")
            handle.write(f"has_services={'true' if selected else 'false'}\n")
    print(json.dumps({"changed_files": files, "matrix": json.loads(matrix)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

