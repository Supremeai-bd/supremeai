#!/usr/bin/env python3
"""
Shared Render deploy trigger script used by all CI deploy jobs
(Core / Worker / Scraper / MCP Control Tower).

Reads configuration from environment variables so no secret interpolation
or f-string quoting inside a `python -c "..."` YAML block is ever needed:

    RENDER_API_KEY   - Render API key (required to actually trigger a deploy)
    RENDER_SVC_ID    - Render service ID to deploy (if unset, the job is skipped)

Exits 0 when a deploy is skipped (missing service id) or successfully
triggered. Exits non-zero after exhausting retries on failure.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

MAX_ATTEMPTS = 5
RETRY_DELAY_SECONDS = 10


def main() -> int:
    svc_id = os.environ.get("RENDER_SVC_ID", "").strip()
    if not svc_id:
        print("Skipping Render deploy - service ID not set")
        return 0

    api_key = os.environ.get("RENDER_API_KEY", "").strip()
    if not api_key:
        print("Skipping Render deploy - RENDER_API_KEY not set")
        return 0

    url = f"https://api.render.com/v1/services/{svc_id}/deploys"
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
        method="POST",
    )

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request) as response:
                body = response.read().decode()
                print("Deploy triggered:", body)
            return 0
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace") if exc.fp else ""
            print(f"Attempt {attempt}/{MAX_ATTEMPTS} failed with {exc}: {detail}")
            if attempt == MAX_ATTEMPTS:
                return 1
            time.sleep(RETRY_DELAY_SECONDS)
        except urllib.error.URLError as exc:
            print(f"Attempt {attempt}/{MAX_ATTEMPTS} network error: {exc}")
            if attempt == MAX_ATTEMPTS:
                return 1
            time.sleep(RETRY_DELAY_SECONDS)

    return 1


if __name__ == "__main__":
    sys.exit(main())
