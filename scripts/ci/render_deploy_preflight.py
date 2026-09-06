#!/usr/bin/env python3
"""Dynamic Render deployment preflight.

The production source of truth is the MCP/backend preflight endpoint. A direct
Render API fallback is retained for bootstrap and requires explicit per-account
configuration; it never invents a shared quota for different Render plans.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any


def get_json(url: str, key: str | None = None) -> Any:
    headers = {"Accept": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def usage_minutes(deploys: list[dict]) -> float:
    now = datetime.now(timezone.utc)
    total = 0.0
    for item in deploys:
        deploy = item.get("deploy", item)
        created, finished = deploy.get("createdAt"), deploy.get("finishedAt")
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


def account_config() -> list[dict[str, Any]]:
    raw = os.getenv("RENDER_ACCOUNTS_JSON", "[]")
    try:
        accounts = json.loads(raw)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"RENDER_ACCOUNTS_JSON is invalid: {error}") from error
    if not isinstance(accounts, list):
        raise RuntimeError("RENDER_ACCOUNTS_JSON must be a JSON array")
    return [item for item in accounts if isinstance(item, dict)]


def remote_preflight() -> list[dict[str, Any]] | None:
    url = os.getenv("RENDER_PREFLIGHT_URL")
    token = os.getenv("RENDER_PREFLIGHT_TOKEN")
    if not url or not token:
        return None
    payload = get_json(url, token)
    results = payload.get("accounts", payload) if isinstance(payload, dict) else payload
    return results if isinstance(results, list) else None


def direct_preflight() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for account in account_config():
        role = str(account.get("role", account.get("account_key", "unknown")))
        service_id = account.get("service_id")
        key = os.getenv(str(account.get("api_key_env", ""))) if account.get("api_key_env") else None
        cap = account.get("safe_build_minutes")
        if not service_id or not key or not isinstance(cap, (int, float)):
            results.append({"role": role, "status": "unknown", "reason": "incomplete account configuration; use MCP preflight"})
            continue
        try:
            payload = get_json(f"https://api.render.com/v1/services/{service_id}/deploys?limit=100", key)
            deploys = payload if isinstance(payload, list) else payload.get("deploys", [])
            minutes = usage_minutes(deploys)
            results.append({"role": role, "status": "blocked" if minutes >= cap else "ready", "minutes": round(minutes, 2), "cap": cap, "plan": account.get("plan", "configured")})
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as error:
            results.append({"role": role, "status": "unknown", "reason": str(error)[:160]})
    return results


def main() -> int:
    required = {role.strip() for role in os.getenv("RENDER_REQUIRED_ROLES", "").split(",") if role.strip()}
    try:
        results = remote_preflight() or direct_preflight()
    except (RuntimeError, urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as error:
        results = [{"role": "preflight", "status": "unknown", "reason": str(error)[:160]}]

    blocked = not results
    if not results:
        results = [{"role": "preflight", "status": "unknown", "reason": "no Render accounts returned"}]
    for result in results:
        role = str(result.get("role", "unknown"))
        status = str(result.get("status", "unknown"))
        if (not required or role in required) and status != "ready":
            blocked = True
        print(f"[RENDER_PREFLIGHT] {json.dumps(result, sort_keys=True)}")

    output = os.getenv("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as stream:
            stream.write(f"build_allowed={'false' if blocked else 'true'}\n")
            stream.write(f"status={'blocked' if blocked else 'ready'}\n")
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as stream:
            stream.write("\n### Render deploy preflight\n\n| Account | Plan | Status | Usage | Reason |\n|---|---|---|---:|---|\n")
            for result in results:
                stream.write(f"| {result.get('role')} | {result.get('plan', 'unknown')} | {result.get('status')} | {result.get('minutes', 'unknown')} | {result.get('reason', '')} |\n")
    if blocked:
        print("::error::A required Render account is not ready; deployment/build is blocked.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
