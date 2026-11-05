"""Build a central secret registry manifest from audit + vault reconcile data.

Produces scripts/ci/secret_registry.json (a living manifest of all codebase secrets).
"""
import json
import os
import re
import sys

AUDIT = "scratchpad/audit_keys_output.txt"
RECONCILE = "scratchpad/vault_reconcile.json"
CANON = "scripts/ci/canonical_name_registry.json"
OUT = "scripts/ci/env_registry.json"


def parse_audit(path):
    data = {}
    key = None
    for line in open(path, encoding="utf-8", errors="replace"):
        m = re.match(r"^([A-Z0-9_]+)\s+\(refs:\s*(\d+)\)\s*$", line.strip())
        if m:
            key = m.group(1)
            data[key] = {"refs": int(m.group(2)), "files": []}
            continue
        if key and line.strip().startswith("-"):
            fm = re.match(r"^-\s+(.+):\d+\s*$", line.strip())
            if fm:
                data[key]["files"].append(fm.group(1))
    return data


def load_canonical_aliases():
    amap = {}
    if os.path.exists(CANON):
        reg = json.load(open(CANON, encoding="utf-8"))
        for fam, info in reg.get("families", {}).items():
            for canon, aliases in info.get("canonical", {}).items():
                for a in aliases:
                    amap[a] = canon
    return amap


def is_fake(k):
    return k.startswith(("TEST_", "MOCK_", "PLACEHOLDER_", "INVALID_", "MISSING_", "TOTALLY_UNKNOWN_", "MY_SECRET", "STRONG_SECRET", "ASYNC_SECRET", "REDACTED_", "FATAL_SECRET", "MODE_FATAL_", "HARDCODED_", "UNRELATED_VAULT_", "VAULT_SECRET", "VAULT_TOKEN"))


def main():
    if not os.path.exists(AUDIT):
        print("audit file missing")
        return 1
    audit = parse_audit(AUDIT)
    reconcile = json.load(open(RECONCILE, encoding="utf-8")) if os.path.exists(RECONCILE) else {}
    vault_keys = set(reconcile.get("vault", []))
    amap = load_canonical_aliases()

    registry = {}
    for k, d in audit.items():
        files = sorted(set(d["files"]))
        registry[k] = {
            "refs": d["refs"],
            "file_count": len(files),
            "files": files,
            "in_vault": k in vault_keys,
            "is_placeholder_or_test": is_fake(k),
            "canonical": amap.get(k, k),
            "is_alias": k in amap,
        }

    json.dump(registry, open(OUT, "w", encoding="utf-8"), indent=1, sort_keys=True)
    print(f"registry written: {len(registry)} secrets -> {OUT}")
    print("in_vault:", sum(1 for v in registry.values() if v["in_vault"]))
    print("aliases:", sum(1 for v in registry.values() if v["is_alias"]))
    print("single-file:", sum(1 for v in registry.values() if v["file_count"] == 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
PY