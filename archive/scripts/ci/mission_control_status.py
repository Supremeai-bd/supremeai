#!/usr/bin/env python3
"""mission_control_status.py — OS pillar: aggregate Guardian/Memory gate status.

Produces a single Mission Control status proof (JSON) from a list of gate
results. Pure functions so the aggregator is offline-testable.

Gate result shape: {"name": str, "ok": bool, "details": str (optional)}
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def aggregate(gates: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(gates or [])
    passed = sum(1 for g in (gates or []) if g.get("ok") is True)
    failed = [g.get("name", "?") for g in (gates or []) if g.get("ok") is not True]
    status = "GREEN" if (total > 0 and passed == total) else ("YELLOW" if passed > 0 else "RED")
    if total == 0:
        status = "UNKNOWN"
    return {
        "status": status,
        "total": total,
        "passed": passed,
        "failed": failed,
        "ok": total > 0 and passed == total,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [f"# Mission Control Status: {report['status']}",
             f"- Gates: {report['passed']}/{report['total']} passed"]
    if report["failed"]:
        lines.append("- Failed: " + ", ".join(report["failed"]))
    return "\n".join(lines)


def load_input(path: str) -> list[dict[str, Any]]:
    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    data = json.loads(raw)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("gates", "results", "checks"):
            if key in data and isinstance(data[key], list):
                return data[key]
    return []


def self_test() -> int:
    fails = 0
    green = [{"name": "g1", "ok": True}, {"name": "g2", "ok": True}]
    r = aggregate(green)
    if r["status"] != "GREEN" or not r["ok"]:
        fails += 1
        print("FAIL green", r)
    else:
        print("PASS green")
    red = [{"name": "g1", "ok": False}]
    r2 = aggregate(red)
    if r2["status"] != "RED":
        fails += 1
        print("FAIL red", r2)
    else:
        print("PASS red")
    empty = aggregate([])
    if empty["status"] != "UNKNOWN":
        fails += 1
        print("FAIL empty", empty)
    else:
        print("PASS empty")
    md = render_markdown(aggregate(green))
    if "GREEN" not in md:
        fails += 1
        print("FAIL md")
    else:
        print("PASS md")
    print("self-test: %d failure(s)" % fails)
    return 0 if fails == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=None)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--markdown", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.input:
        print("mission_control_status: provide --input or --self-test", file=sys.stderr)
        return 2
    gates = load_input(args.input)
    report = aggregate(gates)
    if args.markdown:
        print(render_markdown(report))
    else:
        print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
