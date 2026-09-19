#!/usr/bin/env python3
"""
Shared Render deploy trigger script used by all CI deploy jobs
(Core / Worker / Scraper / MCP Control Tower).

Reads configuration from environment variables so no secret interpolation
or f-string quoting inside a `python -c "..."` YAML block is ever needed:

    RENDER_API_KEY   - Render API key (required to actually trigger a deploy)
    RENDER_SVC_ID    - Render service ID to deploy (if unset, the job is skipped)

Note: For the Service Modularization/OOM Mitigation feature, ensure that the
Render Dashboard is configured with the `SUPREMEAI_SERVICE_ROLE` environment
variable for each respective service (`core`, `worker`, `scraper`).

Exits 0 when a deploy is skipped (missing service id) or successfully
triggered. Exits non-zero after exhausting retries on failure.

DRY Phase 2-C3: transport migrated onto scripts/lib/render_client.py —
the retry policy (5 attempts / 10 s) stays here because it is this job's
own concern; auth/URL/error normalization is the client's.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from render_client import RenderApiError, RenderClient  # noqa: E402

MAX_ATTEMPTS = 5
RETRY_DELAY_SECONDS = 10


def main() -> int:
    svc_id = os.environ.get("RENDER_SVC_ID", "").strip()
    api_key = os.environ.get("RENDER_API_KEY", "").strip()

    if not svc_id:
        print("Skipping Render deploy - service ID not set")
        return 0

    if not api_key:
        print("Skipping Render deploy - RENDER_API_KEY not set")
        return 0

    client = RenderClient(api_key=api_key, service_id=svc_id)

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            body = client.trigger_deploy(svc_id)
            print("Deploy triggered:", body)
            return 0
        except RenderApiError as exc:
            print(f"Attempt {attempt}/{MAX_ATTEMPTS} failed with HTTP {exc.status}: {exc.body or exc}")
            if attempt == MAX_ATTEMPTS:
                return 1
            time.sleep(RETRY_DELAY_SECONDS)
        except Exception as exc:  # noqa: BLE001 - intentional retry-all policy
            print(f"Attempt {attempt}/{MAX_ATTEMPTS} unexpected transport error: {exc}")
            if attempt == MAX_ATTEMPTS:
                return 1
            time.sleep(RETRY_DELAY_SECONDS)

    return 1


if __name__ == "__main__":
    sys.exit(main())
