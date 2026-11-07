#!/usr/bin/env python3
"""dependency_parasite_guard.py — Guardian gate: detect parasitic/unpinned deps.

Pure functions operate on dependency lists so the gate is offline-testable. Flags:
  - unpinned specifiers (no version constraint)
  - known parasitic/risky packages
  - duplicate (normalized) dependency names
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# Packages considered parasitic / high-risk in this federation.
PARASITE_PACKAGES = {
    "event-stream", "flatmap-stream", "eslint-scope", "getcookies",
    "crossenv", "babelcli", "cross-env.js",
}

NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+")


def normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name.strip().lower())


def parse_requirements(text: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # strip inline comments
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        # name + specifier
        m = re.match(r"^([A-Za-z0-9_.-]+)\s*(.*)$", line)
        if not m:
            continue
        name = m.group(1)
        spec = m.group(2).strip()
        out.append({"name": name, "spec": spec})
    return out


def parse_package_json(data: Any) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if not isinstance(data, dict):
        return out
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        deps = data.get(section)
        if not isinstance(deps, dict):
            continue
        for name, spec in deps.items():
            out.append({"name": str(name), "spec": str(spec) if spec is not None else ""})
    return out


def audit_dependencies(deps: list[dict[str, str]]) -> list[str]:
    errs: list[str] = []
    seen: dict[str, int] = {}
    for d in deps or []:
        name = d.get("name", "")
        spec = (d.get("spec") or "").strip()
        norm = normalize_name(name)
        if norm in PARASITE_PACKAGES:
            errs.append(f"parasitic dependency: {name}")
        if not spec:
            errs.append(f"unpinned dependency: {name}")
        seen[norm] = seen.get(norm, 0) + 1
    for norm, count in seen.items():
        if count > 1:
            errs.append(f"duplicate dependency: {norm} (x{count})")
    return errs


def audit_requirements_text(text: str) -> list[str]:
    return audit_dependencies(parse_requirements(text))


def audit_package_json_text(text: str) -> list[str]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return ["invalid package.json"]
    return audit_dependencies(parse_package_json(data))


def self_test() -> int:
    fails = 0
    clean = "requests==2.31.0\nflask>=2.0\n"
    if audit_requirements_text(clean):
        fails += 1
        print("FAIL clean-reqs", audit_requirements_text(clean))
    else:
        print("PASS clean-reqs")
    dirty = "requests\nflask==1.0\nrequests==2.0\n"
    v = audit_requirements_text(dirty)
    if not (any("unpinned" in e for e in v) and any("duplicate" in e for e in v)):
        fails += 1
        print("FAIL dirty-reqs", v)
    else:
        print("PASS dirty-reqs")
    pj = json.dumps({"dependencies": {"lodash": "^4.0.0", "event-stream": "3.3.6"}})
    v2 = audit_package_json_text(pj)
    if not any("parasitic" in e for e in v2):
        fails += 1
        print("FAIL parasite-pj", v2)
    else:
        print("PASS parasite-pj")
    if audit_package_json_text("{bad"):
        # should report invalid
        print("PASS invalid-json")
    else:
        fails += 1
        print("FAIL invalid-json")
    print("self-test: %d failure(s)" % fails)
    return 0 if fails == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", default=[])
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.paths:
        print("dependency_parasite_guard: provide paths or --self-test", file=sys.stderr)
        return 2
    errs: list[str] = []
    for p in args.paths:
        path = Path(p)
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if path.name == "package.json":
            errs.extend(f"{path}: {e}" for e in audit_package_json_text(text))
        else:
            errs.extend(f"{path}: {e}" for e in audit_requirements_text(text))
    if errs:
        print("dependency_parasite_guard: FAIL")
        for e in errs:
            print(" -", e)
        return 1
    print("dependency_parasite_guard: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
