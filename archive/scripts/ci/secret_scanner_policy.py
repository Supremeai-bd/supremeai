#!/usr/bin/env python3
"""secret_scanner_policy.py — Guardian gate: scan text/files for leaked secrets.

Pure functions operate on strings so the gate is offline-testable. Patterns are a
conservative subset (AWS, GitHub tokens, generic private keys, Supabase service
role). An allowlist of literal substrings suppresses known-safe fixtures.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github_pat", re.compile(r"ghp_[A-Za-z0-9]{36,}")),
    ("github_fine_grained", re.compile(r"github_pat_[A-Za-z0-9_]{40,}")),
    ("github_oauth", re.compile(r"gho_[A-Za-z0-9]{36,}")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("supabase_service_role", re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}")),
    ("generic_api_key", re.compile(r"(?i)(?:api[_-]?key|secret|token)\s*[:=]\s*['\"][A-Za-z0-9_\-]{24,}['\"]")),
]

DEFAULT_ALLOWLIST = [
    "example",
    "placeholder",
    "YOUR_",
    "xxxx",
    "test-",
]


def scan_text(text: str, allowlist: list[str] | None = None) -> list[dict[str, str]]:
    allow = allowlist if allowlist is not None else DEFAULT_ALLOWLIST
    findings: list[dict[str, str]] = []
    for name, pat in PATTERNS:
        for m in pat.finditer(text or ""):
            snippet = m.group(0)
            if any(a in snippet or a in text[max(0, m.start() - 40):m.start()] for a in allow):
                continue
            findings.append({"rule": name, "match": snippet[:12] + "…"})
    # dedupe by (rule, match-prefix)
    seen = set()
    out = []
    for f in findings:
        key = (f["rule"], f["match"])
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out


def scan_file(path: str, allowlist: list[str] | None = None) -> list[dict[str, str]]:
    p = Path(path)
    if not p.is_file():
        return []
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return scan_text(text, allowlist)


def scan_paths(paths: list[str], allowlist: list[str] | None = None) -> dict[str, Any]:
    results: dict[str, list[dict[str, str]]] = {}
    total = 0
    for p in paths:
        fs = scan_file(p, allowlist)
        if fs:
            results[p] = fs
            total += len(fs)
    return {"files": results, "total": total, "ok": total == 0}


def self_test() -> int:
    fails = 0
    clean = "x = 1\napi_key = 'example-placeholder'\n"
    if scan_text(clean):
        fails += 1
        print("FAIL clean-text", scan_text(clean))
    else:
        print("PASS clean-text")
    dirty = "TOKEN=ghp_" + "A" * 36 + "\n"
    f = scan_text(dirty)
    if not any(x["rule"] == "github_pat" for x in f):
        fails += 1
        print("FAIL dirty-text", f)
    else:
        print("PASS dirty-text")
    pk = "-----BEGIN RSA " + "PRIVATE KEY-----\nMIIE...\n"
    if not any(x["rule"] == "private_key" for x in scan_text(pk)):
        fails += 1
        print("FAIL private-key")
    else:
        print("PASS private-key")
    print("self-test: %d failure(s)" % fails)
    return 0 if fails == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", default=[])
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.paths:
        print("secret_scanner_policy: provide paths or --self-test", file=sys.stderr)
        return 2
    res = scan_paths(args.paths)
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        if res["ok"]:
            print("secret_scanner_policy: PASS")
        else:
            print("secret_scanner_policy: FAIL")
            for p, fs in res["files"].items():
                for f in fs:
                    print(f" - {p}: {f['rule']}")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
