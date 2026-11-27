#!/usr/bin/env python3
"""Bounded ZAP passive inspection of one operator-authorized HTTPS origin.

Only two GETs to / are sent (ordinary and cross-origin). No spider, redirects,
POSTs, authentication, API/active scan or load test. ZAP must already be
listening on loopback port 8090. This is intentionally narrower than the ZAP
baseline script; it does not discover application routes.
"""
from __future__ import annotations

import ipaddress
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener

API = "http://127.0.0.1:8090"
OPENER = build_opener(ProxyHandler({}))


def validate_origin(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment
            or not re.fullmatch(r"[A-Za-z0-9.-]+", parsed.hostname)):
        raise ValueError("PRODUCTION_URL must be one HTTPS origin without credentials, path, query or fragment")
    try:
        port = parsed.port
    except ValueError:
        raise ValueError("Invalid production port") from None
    host = parsed.hostname.lower().rstrip(".")
    try:
        is_ip = bool(ipaddress.ip_address(host))
    except ValueError:
        is_ip = False
    if is_ip:
        raise ValueError("PRODUCTION_URL must use a public hostname, not an IP address")
    if host in ("localhost", "local") or host.endswith((".localhost", ".local", ".internal")):
        raise ValueError("PRODUCTION_URL must use a public hostname")
    return f"https://{host}" + (f":{port}" if port else "") + "/"


def zap_json(path: str) -> dict:
    with OPENER.open(API + path, timeout=5) as response:
        value = json.load(response)
    if not isinstance(value, dict):
        raise RuntimeError("Invalid ZAP API response")
    return value


def wait_ready() -> None:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            if zap_json("/JSON/core/view/version/").get("version"):
                return
        except (OSError, ValueError, URLError):
            time.sleep(1)
    raise RuntimeError("ZAP did not become ready")


def passive_wait() -> None:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        value = zap_json("/JSON/pscan/view/recordsToScan/").get("recordsToScan")
        if value is None:
            raise RuntimeError("ZAP did not report passive queue status")
        if int(value) == 0:
            return
        time.sleep(1)
    raise RuntimeError("ZAP passive scan did not complete")


def request(origin: str, cors: bool) -> tuple[int, dict[str, str]]:
    cmd = ["curl", "--silent", "--show-error", "--insecure", "--noproxy", "",
           "--proxy", "http://127.0.0.1:8090", "--connect-timeout", "10", "--max-time", "30",
           "--max-filesize", "5242880", "--output", os.devnull, "--dump-header", "-",
           "--write-out", "\nZAP_HTTP_STATUS:%{http_code}"]
    if cors:
        cmd += ["--header", "Origin: https://zap-test.invalid"]
    cmd += ["--", origin]
    # curl does not follow redirects without --location; no request body or credentials.
    result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=35)
    headers, sep, status = result.stdout.rpartition("\nZAP_HTTP_STATUS:")
    if not sep or not re.fullmatch(r"[1-5][0-9][0-9]", status):
        raise RuntimeError("No HTTP response received")
    # Ignore the proxy CONNECT response; use the last HTTP response header block.
    blocks = re.split(r"\r?\n\r?\n", headers.strip())
    selected: dict[str, str] = {}
    allowed = {"cache-control", "access-control-allow-origin", "access-control-allow-credentials",
               "content-security-policy", "x-frame-options", "x-content-type-options", "strict-transport-security"}
    for line in blocks[-1].splitlines()[1:]:
        key, delimiter, value = line.partition(":")
        key = key.strip().lower()
        if delimiter and key in allowed:
            selected[key] = value.strip()
    return int(status), selected


def header_summary(headers: dict[str, str]) -> dict:
    origin = headers.get("access-control-allow-origin", "")
    cors = "wildcard" if origin == "*" else "reflects-test-origin" if origin == "https://zap-test.invalid" else "other" if origin else "absent"
    directives = re.findall(r"(?<![a-z-])(no-store|no-cache|private|public|must-revalidate|s-maxage|max-age)(?:\s*=\s*([0-9]+))?", headers.get("cache-control", "").lower())
    return {"cors_allow_origin": cors,
            "cors_credentials": headers.get("access-control-allow-credentials", "").lower() == "true",
            "cache_directives": [key + ("=" + val if val else "") for key, val in directives],
            "security_headers_present": [key for key in ("content-security-policy", "x-frame-options", "x-content-type-options", "strict-transport-security") if key in headers]}


def run() -> None:
    origin = validate_origin(os.environ.get("PRODUCTION_URL", ""))
    wait_ready()
    responses = [request(origin, False), request(origin, True)]
    statuses = [status for status, _ in responses]
    summaries = [header_summary(headers) for _, headers in responses]
    passive_wait()
    result = zap_json("/JSON/core/view/alerts/?start=0&count=500")
    alerts = result.get("alerts")
    if not isinstance(alerts, list):
        raise RuntimeError("ZAP alerts unavailable")
    if len(alerts) >= 500:
        raise RuntimeError("ZAP alert result truncated")
    report = {"coverage": "two unauthenticated GET requests to /, no spider or redirects",
              "statuses": statuses, "header_summaries": summaries, "alerts": alerts}
    Path("zap-passive-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    # Annotations omit URLs, request data and evidence; the artifact is access-controlled.
    for alert in alerts:
        if not isinstance(alert, dict):
            raise RuntimeError("Invalid ZAP alert")
        risk = re.sub(r"[^a-zA-Z ]", "", str(alert.get("risk", "Unknown")))[:20]
        name = re.sub(r"[^a-zA-Z0-9 ._()/:-]", "", str(alert.get("alert", "Unknown")))[:160]
        print(f"::warning::ZAP passive ({risk}): {name}")
    print(f"::notice::ZAP passive completed; HTTP statuses {statuses}, {len(alerts)} alerts; root-only coverage")
    print(f"::notice::Root cache and security header summary: {json.dumps(summaries[0])}")
    print(f"::notice::Test-origin CORS summary: {json.dumps(summaries[1])}")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        # Do not include URLs, curl stderr or other sensitive upstream data.
        print(f"::error::Passive scan incomplete ({type(exc).__name__}); no security conclusion", file=sys.stderr)
        sys.exit(1)
