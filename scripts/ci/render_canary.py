#!/usr/bin/env python3
"""Smoke-check only Render URLs explicitly configured by the deployment owner.

Expected GitHub Actions variable:
  RENDER_CANARY_URLS_JSON='[{"name":"primary","url":"https://.../health/live"}]'

An empty value is a hard failure. This prevents an old hard-coded list of
non-existent services from masking which production services are authoritative.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request


def main() -> int:
    raw = os.environ.get("RENDER_CANARY_URLS_JSON", "").strip()
    if not raw:
        print("RENDER_CANARY_URLS_JSON is not configured; refusing an unverified canary.", file=sys.stderr)
        return 1
    try:
        targets = json.loads(raw)
    except json.JSONDecodeError as exc:
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
        for attempt in range(1, 4):
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
                if attempt < 3:
                    time.sleep(10)
        if not ok:
            failed.append(f"{name}: {last_error}")

    if failed:
        print("Render canary failed:", *failed, sep="\n- ", file=sys.stderr)
        return 1
    print("Render canary passed for all configured authoritative targets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

