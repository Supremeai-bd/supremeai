#!/usr/bin/env python3
"""Run safe, read-only staging contract probes.

The runner never mutates data. Authentication, billing, and agent write flows
remain explicit opt-in checks owned by the staging release operator.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass


@dataclass
class Probe:
    path: str
    status: str
    http_status: int | None = None
    detail: str | None = None


def request(base_url: str, path: str, timeout: float) -> Probe:
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            code = response.status
            return Probe(path, "passed" if 200 <= code < 300 else "failed", code)
    except urllib.error.HTTPError as exc:
        return Probe(path, "failed", exc.code, "HTTP error")
    except (urllib.error.URLError, TimeoutError) as exc:
        return Probe(path, "failed", detail=type(exc).__name__)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.getenv("STAGING_BASE_URL"))
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--output", default="ci-reports/staging-smoke.json")
    args = parser.parse_args()
    if not args.base_url:
        print("STAGING_BASE_URL or --base-url is required", file=sys.stderr)
        return 2

    probes = [request(args.base_url, path, args.timeout) for path in ("/api/v1/health/live", "/api/v1/health/ready")]
    payload = {
        "schema_version": "1.0",
        "base_url": args.base_url,
        "read_only": True,
        "probes": [asdict(probe) for probe in probes],
        "status": "passed" if all(probe.status == "passed" for probe in probes) else "blocked",
    }
    output = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
