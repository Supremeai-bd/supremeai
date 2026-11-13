#!/usr/bin/env python3
"""Smoke-check only Render URLs explicitly configured by the deployment owner.

Expected GitHub Actions variable:
  RENDER_CANARY_URLS_JSON='[{"name":"primary","url":"https://.../health/live"}]'
  (Also tolerates PowerShell-stripped unquoted object syntax such as
   '[{name:primary,url:https://.../health/live}]'.)

An empty value is a hard failure. This prevents an old hard-coded list of
non-existent services from masking which production services are authoritative.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from typing import Any


def parse_canary_targets(raw: str) -> list[dict[str, Any]]:
    """Parse RENDER_CANARY_URLS_JSON, tolerating unquoted keys/values when set via CLI."""
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass

    # Fallback: parse `{name:...,url:...}` items stripped of quotes by PowerShell/CLI
    targets: list[dict[str, Any]] = []
    for obj_match in re.finditer(r"\{([^{}]+)\}", raw):
        body = obj_match.group(1)
        item: dict[str, str] = {}
        for pair in body.split(","):
            if ":" not in pair:
                continue
            k, v = pair.split(":", 1)
            key = k.strip().strip('"').strip("'")
            val = v.strip().strip('"').strip("'")
            if key:
                item[key] = val
        if "url" in item:
            targets.append(item)
    if targets:
        return targets
    raise ValueError(f"Unable to parse RENDER_CANARY_URLS_JSON: {raw!r}")


def main() -> int:
    raw = os.environ.get("RENDER_CANARY_URLS_JSON", "").strip()
    if not raw:
        print("RENDER_CANARY_URLS_JSON is not configured; refusing an unverified canary.", file=sys.stderr)
        return 1
    try:
        targets = parse_canary_targets(raw)
    except ValueError as exc:
        print(f"Invalid RENDER_CANARY_URLS_JSON: {exc}", file=sys.stderr)
        return 1
    if not isinstance(targets, list) or not targets:
        print("RENDER_CANARY_URLS_JSON must be a non-empty list.", file=sys.stderr)
        return 1

    failed: list[str] = []
    for target in targets:
        name = str(target.get("name", "unnamed"))
        url = str(target.get("url", ""))
        if not url.startswith("https://"):
            failed.append(f"{name}: invalid URL")
            continue
        ok = False
        last_error = "unknown error"
        is_auxiliary = name in ("ci-runner", "supremeai-ci-runner") or target.get("critical") is False
        max_attempts = 5 if is_auxiliary else 4
        for attempt in range(1, max_attempts + 1):
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "SupremeAI-Canary/2.0"})
                with urllib.request.urlopen(request, timeout=45) as response:
                    body = response.read(4096).decode("utf-8", errors="replace")
                    if response.status != 200:
                        raise RuntimeError(f"HTTP {response.status}: {body[:200]}")
                print(f"OK {name}: {url}")
                ok = True
                break
            except (OSError, urllib.error.URLError, RuntimeError) as exc:
                last_error = str(exc)
                if attempt < max_attempts:
                    time.sleep(12)
        if not ok:
            if is_auxiliary:
                print(
                    f"WARN [Auxiliary/Batch Runner Degraded] {name}: {last_error} (non-blocking for user-facing production traffic)",
                    file=sys.stderr,
                )
            else:
                failed.append(f"{name}: {last_error}")

    if failed:
        print("Render canary failed:", *failed, sep="\n- ", file=sys.stderr)
        return 1
    print("Render canary passed for all configured authoritative targets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
