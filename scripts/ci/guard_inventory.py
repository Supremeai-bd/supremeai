#!/usr/bin/env python3
"""guard_inventory.py — no guard may exist without a caller.

The failure this prevents
------------------------
On 2026-11-20 the repo held 261 modules in ``scripts/ci``. Exactly 38 were
reachable from any workflow, and 94 of the guard-named ones were reachable from
*neither* a workflow nor the roster. Each had been written to catch a specific
regression, reviewed, merged — and never executed. One of them
(``check_hardcoded_deployment_config.py``) reported a real hardcoded production
URL the moment it was finally run.

The pattern is the point: a file called ``*_guard.py`` that nothing calls looks
identical in review to one that gates merges. This tool makes the difference
visible and keeps it in the ratchet.

Modes
-----
``--check``      fail if a guard has no caller outside the frozen register
``--list``       print every guard and where it is called from
``--baseline``   rewrite the register from the current tree (deliberate commits only)

Classification is derived, never listed: a file is guard-like if its *name* says
so or if it advertises ``--check``/``--self-test`` in its own source. Adding a
new guard therefore needs no change here — it is either wired or it fails.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CI_DIR = REPO_ROOT / "scripts" / "ci"
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
ROSTER = CI_DIR / "run_all_guards.py"
REGISTER = REPO_ROOT / "scripts" / "ops" / "guard_inventory_register.json"

#: Names that mark a module as a guard rather than a library/tool.
_GUARD_NAME_MARKERS = (
    "_guard",
    "check_",
    "audit_",
    "gate",
    "sentinel",
    "probe",
    "watchdog",
    "census",
    "parity",
    "invariant",
)

#: Flags that mean "this module can be used as a gate".
_GUARD_FLAGS = ("--check", "--self-test", "--from-strict")


def is_guard(path: Path) -> bool:
    """Derived, not listed: name marker OR self-advertised gate flags."""
    if any(marker in path.name for marker in _GUARD_NAME_MARKERS):
        return True
    try:
        head = path.read_text(encoding="utf-8", errors="ignore")[:4000]
    except OSError:
        return False
    return any(flag in head for flag in _GUARD_FLAGS)


def callers() -> dict[str, list[str]]:
    """Map guard module name -> the places that invoke it."""
    found: dict[str, list[str]] = {}

    roster_src = ROSTER.read_text(encoding="utf-8", errors="ignore") if ROSTER.exists() else ""
    for name in re.findall(r"scripts/ci/([A-Za-z0-9_]+\.py)", roster_src):
        found.setdefault(name, []).append("run_all_guards.py")

    for wf in sorted(WORKFLOW_DIR.glob("*.yml")):
        text = wf.read_text(encoding="utf-8", errors="ignore")
        for name in re.findall(r"scripts/ci/([A-Za-z0-9_]+\.py)", text):
            found.setdefault(name, []).append(f".github/workflows/{wf.name}")

    # Other in-tree callers (Makefile, docs scripts, other guards).
    for extra in ("Makefile",):
        p = REPO_ROOT / extra
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        for name in re.findall(r"scripts/ci/([A-Za-z0-9_]+\.py)", text):
            found.setdefault(name, []).append(extra)

    return found


def load_register() -> dict:
    if not REGISTER.exists():
        return {
            "_comment": (
                "Guards with no caller, frozen with a reason. Every entry here is a rule "
                "nobody enforces. Removing an entry (after wiring the guard) is the "
                "desired direction."
            ),
            "known_orphans": {},
        }
    return json.loads(REGISTER.read_text(encoding="utf-8"))


def scan() -> tuple[list[str], dict[str, list[str]], dict[str, list[str]]]:
    guards = sorted(p.name for p in CI_DIR.glob("*.py") if is_guard(p))
    called = callers()
    wired = {g: called[g] for g in guards if g in called}
    orphans = [g for g in guards if g not in called]
    return orphans, wired, called


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail on new orphans")
    parser.add_argument("--list", action="store_true", help="show the full inventory")
    parser.add_argument("--baseline", action="store_true", help="rewrite the register")
    args = parser.parse_args(argv)

    orphans, wired, _ = scan()
    register = load_register()
    known = register.get("known_orphans", {})

    if args.list:
        print(f"guards: {len(wired) + len(orphans)}  wired: {len(wired)}  orphan: {len(orphans)}")
        for name, where in sorted(wired.items()):
            print(f"  WIRED   {name:52} <- {', '.join(sorted(set(where)))}")
        for name in orphans:
            tag = "KNOWN" if name in known else "NEW"
            print(f"  {tag:6}  {name:52} <- (no caller)")
        return 0

    if args.baseline:
        payload = {
            "_comment": register.get("_comment", ""),
            "_note": (
                "Each entry is a rule nobody enforces. Prefer wiring the guard into "
                "run_all_guards.py over adding it here."
            ),
            "_count": len(orphans),
            "known_orphans": {
                name: known.get(name, "unwired at freeze; rationale not recorded")
                for name in orphans
            },
        }
        REGISTER.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"register written: {len(orphans)} known orphan(s)")
        return 0

    if not args.check:
        parser.print_help()
        return 0

    new = [o for o in orphans if o not in known]
    fixed = [k for k in known if k not in orphans]

    print(f"guard inventory: {len(wired)} wired, {len(orphans)} orphan "
          f"({len(known)} known, {len(new)} new)")
    if fixed:
        print(f"\n{len(fixed)} guard(s) wired since the freeze — remove from the register:")
        for name in fixed:
            print(f"  + {name}")
    if new:
        print(f"\n::error::{len(new)} guard(s) have no caller and are not in the register:")
        for name in new:
            print(f"  - {name}")
        print(
            "\nWire it into run_all_guards.py, or record it in "
            "scripts/ops/guard_inventory_register.json with a reason."
        )
        return 1

    print("OK: no unwired guards beyond the frozen register")
    return 0


if __name__ == "__main__":
    sys.exit(main())
