"""Secret naming guard (Phase 6 #23): report usage of non-canonical (alias) secret names.

Uses scripts/ci/secret_canonical_registry.json to identify aliases.
Exit 0 always (report-only); --strict fails if any alias usage found.

Usage:
  python scripts/ci/secret_naming_guard.py --check
  python scripts/ci/secret_naming_guard.py --self-test
  python scripts/ci/secret_naming_guard.py --strict
"""
import argparse
import json
import os
import re
import sys

REGISTRY = "scripts/ci/canonical_name_registry.json"


def load_registry():
    with open(REGISTRY, encoding="utf-8") as fh:
        return json.load(fh)


def build_alias_map(reg):
    """Return {alias: canonical} dict."""
    amap = {}
    for fam, info in reg.get("families", {}).items():
        for canon, aliases in info.get("canonical", {}).items():
            for a in aliases:
                amap[a] = canon
    return amap


def scan(alias_map):
    """Return list of (file, line, alias, canonical) for alias usage in tracked-ish files."""
    findings = []
    roots = [".github", "core", "gateway", "scripts", "studio", "browser", "vscode", "infrastructure"]
    skip = {"node_modules", ".git", "__pycache__", "dist", "build", ".next", "target", "venv", ".venv"}
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, files in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in skip]
            for fn in files:
                if not fn.endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".yml", ".yaml", ".env", ".sh")):
                    continue
                p = os.path.join(dirpath, fn)
                if os.path.getsize(p) > 500000:
                    continue
                try:
                    lines = open(p, encoding="utf-8", errors="replace").read().splitlines()
                except Exception:
                    continue
                for i, line in enumerate(lines, 1):
                    for alias, canon in alias_map.items():
                        if re.search(r"\b" + re.escape(alias) + r"\b", line):
                            findings.append((p, i, alias, canon))
    return findings


def self_test():
    import tempfile
    reg = {"families": {"X": {"canonical": {"CANON": ["ALIAS1"]}}}}
    amap = build_alias_map(reg)
    assert amap == {"ALIAS1": "CANON"}, amap
    print("self-test: PASS (1/1)")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.check:
        ap.print_help()
        return 0

    reg = load_registry()
    amap = build_alias_map(reg)
    findings = scan(amap)

    # aggregate by alias
    from collections import Counter
    c = Counter(f[2] for f in findings)
    print(f"== alias usage: {len(findings)} occurrence(s) across {len(c)} alias(es)")
    for alias, canon in sorted(amap.items()):
        n = c.get(alias, 0)
        if n:
            print(f"   {alias} -> {canon}: {n} occurrence(s)")
    # show a few example locations
    shown = 0
    for p, i, alias, canon in findings:
        if shown < 15:
            print(f"      {p}:{i}")
            shown += 1
    if len(findings) > shown:
        print(f"      ... and {len(findings)-shown} more")

    if args.strict and findings:
        print(f"FAIL (strict): {len(findings)} alias occurrence(s)")
        return 1
    print("OK (report-only)" if not args.strict else "OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
