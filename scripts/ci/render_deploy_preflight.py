#!/usr/bin/env python3
"""Dynamic Render deployment preflight.

The production source of truth is the MCP/backend preflight endpoint. A direct
Render API fallback is retained for bootstrap and requires explicit per-account
configuration; it never invents a shared quota for different Render plans.
"""
from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
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
    raw = os.getenv("RENDER_ACCOUNTS_JSON", "").strip()
    if raw:
        try:
            accounts = json.loads(raw)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"RENDER_ACCOUNTS_JSON is invalid: {error}") from error
        if not isinstance(accounts, list):
            raise RuntimeError("RENDER_ACCOUNTS_JSON must be a JSON array")
        return [item for item in accounts if isinstance(item, dict)]

    # Fallback to standard 4 nodes if JSON not provided or empty
    node_defs = [
        ("core", "RENDER_PRIMARY_SVC_ID", "RENDER_API_KEY_1", 450.0, "free"),
        ("worker", "RENDER_WORKER_SVC_ID", "RENDER_API_KEY_2", 450.0, "free"),
        ("scraper", "RENDER_SCRAPER_SVC_ID", "RENDER_API_KEY_3", 450.0, "free"),
        ("mcp", "RENDER_MCP_SVC_ID", "RENDER_API_KEY_4", 450.0, "free"),
    ]
    accounts = []
    for role, svc_env, key_env, default_cap, plan in node_defs:
        svc_id = os.getenv(svc_env)
        # Check fallback key names if specific numbered key not set
        key = os.getenv(key_env)
        if not key and role == "core":
            key_env = "RENDER_API_KEY" if os.getenv("RENDER_API_KEY") else key_env
        elif not key and role == "worker":
            key_env = "RENDER_API_KEY_BACKUP" if os.getenv("RENDER_API_KEY_BACKUP") else key_env
        if svc_id:
            accounts.append({
                "role": role,
                "service_id": svc_id,
                "api_key_env": key_env,
                "safe_build_minutes": default_cap,
                "plan": plan,
            })
    return accounts


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


def route_inventory_evidence() -> dict[str, Any]:
    path = Path(os.getenv("ROUTE_INVENTORY_PATH", "docs/generated/route_inventory.json"))
    if not path.exists():
        return {"status": "missing", "path": str(path)}
    payload = path.read_bytes()
    try:
        inventory = json.loads(payload)
    except json.JSONDecodeError:
        return {"status": "invalid", "path": str(path), "sha256": hashlib.sha256(payload).hexdigest()}
    return {
        "status": "valid",
        "path": str(path),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "route_count": inventory.get("route_count"),
        "source_sha256": inventory.get("source_sha256"),
    }


def write_evidence(results: list[dict[str, Any]], blocked: bool) -> None:
    destination = os.getenv("PREFLIGHT_EVIDENCE_PATH")
    if not destination:
        return
    evidence = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "blocked" if blocked else "ready",
        "required_roles": sorted(role.strip() for role in os.getenv("RENDER_REQUIRED_ROLES", "").split(",") if role.strip()),
        "accounts": results,
        "route_inventory": route_inventory_evidence(),
    }
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    Path(destination).write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    required = {role.strip() for role in os.getenv("RENDER_REQUIRED_ROLES", "").split(",") if role.strip()}
    try:
        results = remote_preflight() or direct_preflight()
    except (RuntimeError, urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as error:
        results = [{"role": "preflight", "status": "unknown", "reason": str(error)[:160]}]

    # If no accounts were configured/returned:
    # If specific roles were required (RENDER_REQUIRED_ROLES), block because required accounts are missing.
    # If no roles were required and no accounts were configured, treat as unconfigured (skipped/ready)
    # so downstream Docker image builds are not blocked when Render deployment is not in use.
    if not results:
        if required:
            blocked = True
            results = [{"role": "preflight", "status": "unknown", "reason": f"required Render roles {required} not configured"}]
        else:
            blocked = False
            results = [{"role": "preflight", "status": "ready", "reason": "no Render accounts configured; preflight skipped"}]
    else:
        blocked = False
        for result in results:
            role = str(result.get("role", "unknown"))
            status = str(result.get("status", "unknown"))
            if (not required or role in required) and status != "ready":
                blocked = True

    for result in results:
        print(f"[RENDER_PREFLIGHT] {json.dumps(result, sort_keys=True)}")

    write_evidence(results, blocked)

    output = os.getenv("GITHUB_OUTPUT")
    if output:
        blocked_accounts_list = [str(r.get("role")) for r in results if str(r.get("status")) != "ready"]
        rechecks = [str(r.get("recheck_at")) for r in results if r.get("recheck_at")]
        earliest_recheck = sorted(rechecks)[0] if rechecks else ""

        with open(output, "a", encoding="utf-8") as stream:
            stream.write(f"build_allowed={'false' if blocked else 'true'}\n")
            stream.write(f"status={'blocked' if blocked else 'ready'}\n")
            stream.write(f"blocked_accounts={','.join(blocked_accounts_list)}\n")
            stream.write(f"recheck_at={earliest_recheck}\n")
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
