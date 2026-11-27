#!/usr/bin/env python3
"""Send one alert to the Studio alert hub from CI (e.g. a failed nightly backup).

বাংলা মন্তব্য: শুধু stdlib। টোকেন (SUPREMEAI_API_TOKEN) infisical_bootstrap থেকে আসে।
সবসময় exit 0 — অ্যালার্ট পাঠাতে না পারলে মূল job-এর ফলাফল বদলায় না।

    python scripts/runtime/infisical_bootstrap.py python scripts/ops/send_alert.py \
        --severity critical --source db-backup --title "Nightly DB backup failed" \
        --body "$RUN_URL" --dedupe db-backup-failed
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request

DEFAULT_INGEST_URL = "https://supremeai-studio.pages.dev/api/internal/alerts"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--severity", choices=("info", "warning", "critical"), default="warning")
    parser.add_argument("--source", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--body", default="")
    parser.add_argument("--dedupe", default="")
    args = parser.parse_args()

    token = os.getenv("SUPREMEAI_API_TOKEN") or os.getenv("SUPREMEAI_API_KEY") or ""
    if not token:
        print("send_alert: SUPREMEAI_API_TOKEN not available; skipping")
        return 0
    payload = {"severity": args.severity, "source": args.source[:60], "title": args.title[:200]}
    if args.body:
        payload["body"] = args.body[:2000]
    if args.dedupe:
        payload["dedupeKey"] = args.dedupe[:200]
    url = os.getenv("ALERT_INGEST_URL", "").strip() or DEFAULT_INGEST_URL
    if not url.startswith("https://"):
        print("send_alert: ALERT_INGEST_URL must be https; skipping")
        return 0
    request = urllib.request.Request(  # noqa: S310 - https enforced above
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as res:  # noqa: S310
            print(f"send_alert: hub answered HTTP {res.status}")
    except urllib.error.HTTPError as exc:
        print(f"send_alert: hub returned HTTP {exc.code}")
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"send_alert: hub unreachable ({type(exc).__name__})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
