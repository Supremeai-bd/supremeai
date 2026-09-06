#!/usr/bin/env python3
"""Capability-aware Render preflight used before any Docker build.

Unknown provider/account state never counts as zero usage. It blocks an
unnecessary build and emits a manual-review reason instead.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

CAP_MINUTES = float(os.getenv("RENDER_SAFE_BUILD_MINUTES", "450"))
SERVICES = [
    ("core", "RENDER_API_KEY_1", "RENDER_API_KEY", "RENDER_PRIMARY_SVC_ID"),
    ("worker", "RENDER_API_KEY_2", "RENDER_API_KEY_BACKUP", "RENDER_WORKER_SVC_ID"),
    ("scraper", "RENDER_API_KEY_3", "RENDER_BACKUP_API_KEY_2", "RENDER_SCRAPER_SVC_ID"),
    ("mcp", "RENDER_API_KEY_4", "", "RENDER_MCP_SVC_ID"),
]


def get_json(url: str, key: str) -> list[dict] | dict:
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def usage_minutes(deploys: list[dict]) -> float:
    now = datetime.now(timezone.utc)
    total = 0.0
    for item in deploys:
        deploy = item.get("deploy", item)
        created = deploy.get("createdAt")
        finished = deploy.get("finishedAt")
        if not created or not finished:
            continue
        try:
            started = datetime.fromisoformat(created.replace("Z", "+00:00"))
            ended = datetime.fromisoformat(finished.replace("Z", "+00:00"))
            if started.year == now.year and started.month == now.month:
                total += max(0.0, (ended - started).total_seconds() / 60)
        except (TypeError, ValueError):
            continue
    return total


def main() -> int:
    results: list[dict[str, object]] = []
    blocked = False
    for role, key_name, fallback_name, service_name in SERVICES:
        key = os.getenv(key_name) or os.getenv(fallback_name)
        service_id = os.getenv(service_name)
        if not key or not service_id:
            results.append({"role": role, "status": "unknown", "reason": "missing API key or service id"})
            # Some Render/MCP accounts intentionally expose no quota API. Unknown
            # is reported for review but must not pretend usage is zero or block
            # unrelated services from deploying.

            continue
        try:
            payload = get_json(f"https://api.render.com/v1/services/{service_id}/deploys?limit=100", key)
            minutes = usage_minutes(payload if isinstance(payload, list) else payload.get("deploys", []))
            over = minutes >= CAP_MINUTES
            results.append({"role": role, "status": "blocked" if over else "ready", "minutes": round(minutes, 2), "cap": CAP_MINUTES})
            blocked = blocked or over
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as error:
            results.append({"role": role, "status": "unknown", "reason": str(error)[:160]})
            blocked = True

    for result in results:
        print(f"[RENDER_PREFLIGHT] {json.dumps(result, sort_keys=True)}")
    output = os.getenv("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as stream:
            stream.write(f"build_allowed={'false' if blocked else 'true'}\n")
            stream.write(f"status={'blocked' if blocked else 'ready'}\n")
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as stream:
            stream.write("\n### Render deploy preflight\n\n")
            stream.write("| Account | Status | Usage | Reason |\n|---|---|---:|---|\n")
            for result in results:
                stream.write(f"| {result['role']} | {result['status']} | {result.get('minutes', 'unknown')} | {result.get('reason', '')} |\n")
    if blocked:
        print("::error::One or more Render accounts are over the safe build budget; Docker image builds are blocked.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
