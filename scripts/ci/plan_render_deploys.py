#!/usr/bin/env python3
"""Plan Render deploy and rollback matrices from the canonical service registry."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from fnmatch import fnmatchcase
from pathlib import Path

import yaml

REGISTRY = Path(__file__).resolve().parents[2] / "config" / "service_registry.yaml"
# Blueprint changes warrant checking all registered targets. CI logic and
# registry metadata alone are not runtime source changes.
TOPOLOGY_FILES = {"render.yaml", "core/config/service_topology.yaml"}


def render_services() -> dict:
    services = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["services"]
    return {name: spec for name, spec in services.items() if spec["platform"] == "render"}


def changed_files(base: str, head: str) -> list[str]:
    if not base or set(base) == {"0"}:
        base = subprocess.check_output(["git", "rev-parse", f"{head}^"], text=True).strip()
    return subprocess.check_output(["git", "diff", "--name-only", base, head], text=True).splitlines()


def resolve_service_id(spec: dict) -> str:
    for name in (spec["canonical_service_id_env"], *spec.get("service_id_aliases", ())):
        if value := os.environ.get(name, "").strip():
            return value
    return ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--targets", default="", help="Comma-separated targets or 'all'")
    parser.add_argument("--require-configured", action="store_true", help="Fail on missing targets (rollback)")
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    files = [] if args.force else changed_files(args.base, args.head)
    targets = {t.strip().lower() for t in args.targets.split(",") if t.strip()}
    services = render_services()
    configured_ids = {name: resolve_service_id(spec) for name, spec in services.items()}
    all_targets = not targets or bool(targets & {"all", "render-all"})
    if args.require_configured and not (targets and targets <= services.keys()):
        parser.error("strict planning requires explicit, known Render targets")

    selected: list[dict[str, str]] = []
    unregistered: list[str] = []
    for service, spec in services.items():
        # The suspended CI runner is not a production runtime. No builds for
        # it unless explicitly selected in a forced dispatch.
        if service == "ci-runner" and not (args.force and service in targets):
            continue
        if not all_targets and service not in targets:
            continue
        if not (args.force or TOPOLOGY_FILES.intersection(files) or any(
            any(fnmatchcase(path, pattern) for pattern in spec["watch_paths"])
            and not any(fnmatchcase(path, pattern) for pattern in spec.get("exclude_paths", ()))
            for path in files
        )):
            continue
        service_id = configured_ids[service]
        id_env = spec["canonical_service_id_env"]
        if not re.fullmatch(r"srv-[a-z0-9]+", service_id):
            unregistered.append(f"{service}:{id_env}")
            print(f"::warning::{service}: missing or invalid {id_env}; UNREGISTERED", file=sys.stderr)
            continue
        api_key_env = spec["canonical_api_key_env"]
        selected.append({
            "service": service,
            "service_id": service_id,
            "api_key_env": api_key_env,
            "api_key_alias_env": next(iter(spec.get("api_key_aliases", ())), api_key_env),
            "health_path": spec.get("liveness_path") or spec.get("health_path", ""),
        })

    # Check inactive roles as well: e.g. the separate auxiliary CI runner is
    # never a valid MCP replacement even when only MCP is being deployed.
    for entry in selected:
        if any(name != entry["service"] and sid == entry["service_id"] for name, sid in configured_ids.items()):
            parser.error(f"{entry['service']} resolves to a service ID registered to another role")
    if args.require_configured and unregistered:
        parser.error("rollback targets are not configured: " + ", ".join(unregistered))

    matrix = {"include": selected}
    if output := args.output or os.environ.get("GITHUB_OUTPUT"):
        with Path(output).open("a", encoding="utf-8") as handle:
            handle.write(f"matrix={json.dumps(matrix, separators=(',', ':'))}\n")
            handle.write(f"has_services={'true' if selected else 'false'}\n")
            handle.write(f"unregistered={json.dumps(unregistered, separators=(',', ':'))}\n")
    print(json.dumps({"changed_files": files, "matrix": matrix, "unregistered": unregistered}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
