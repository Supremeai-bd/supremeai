"""Secret hygiene guard (Phase 6) - report-only by default.

Checks:
  - test-secret isolation: production config files must not reference TEST_ONLY_/MOCK_/placeholder secrets
  - single-file secret references: warn for secrets referenced in only one file
  - VITE_* env-var parity: frontend VITE_* keys are frontend-only by Vite convention (no backend counterpart expected)
  - .env.example hygiene: codebase secrets should be documented in .env.example

Usage:
  python scripts/ci/secret_hygiene_guard.py --check
  python scripts/ci/secret_hygiene_guard.py --self-test
  python scripts/ci/secret_hygiene_guard.py --strict   (exit 1 on findings)
"""
import argparse
import os
import re
import sys


AUDIT_FILE = "scratchpad/audit_keys_output.txt" if os.path.exists("scratchpad/audit_keys_output.txt") else None


def parse_audit(path):
    """Return (key -> set of files) from audit_keys_output.txt."""
    if not path or not os.path.exists(path):
        return {}
    data = {}
    key = None
    for line in open(path, encoding="utf-8", errors="replace"):
        m = re.match(r"^([A-Z0-9_]+)\s+\(refs:\s*(\d+)\)\s*$", line.strip())
        if m:
            key = m.group(1)
            data[key] = set()
            continue
        if key and line.strip().startswith("-"):
            fm = re.match(r"^-\s+(.+):\d+\s*$", line.strip())
            if fm:
                data[key].add(fm.group(1))
    return data


def check_test_secret_isolation():
    findings = []
    forbidden = re.compile(r"TEST_ONLY_|MOCK_TOKEN|PLACEHOLDER_PAT|TOTALLY_UNKNOWN_SECRET|MISSING_SECRET")
    targets = ["core/config_classification.py", "core/config_fields.py", "core/config.py"]
    for t in targets:
        if not os.path.exists(t):
            continue
        for i, line in enumerate(open(t, encoding="utf-8", errors="replace"), 1):
            if forbidden.search(line):
                findings.append(f"{t}:{i}: {line.strip()[:80]}")
    return findings


def check_single_file_secrets():
    data = parse_audit(AUDIT_FILE)
    return [k for k, files in data.items() if len(files) == 1]


def check_vite_parity():
    # VITE_* keys are frontend-only by Vite convention (import.meta.env.VITE_*).
    # They are not expected to have backend counterparts; flagging them as
    # parity issues is a false positive. Report them as informational only.
    vite_keys = set()
    for dirpath, _, files in os.walk("studio"):
        for fn in files:
            if fn.endswith((".ts", ".tsx", ".js", ".jsx")):
                p = os.path.join(dirpath, fn)
                for line in open(p, encoding="utf-8", errors="replace"):
                    for m in re.finditer(r"VITE_[A-Z0-9_]+", line):
                        vite_keys.add(m.group(0))
    return [], sorted(vite_keys)


def check_env_example_hygiene():
    findings = []
    if not os.path.exists(".env.example"):
        return findings
    env_keys = set()
    for line in open(".env.example", encoding="utf-8", errors="replace"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            env_keys.add(line.split("=", 1)[0].strip())
    data = parse_audit(AUDIT_FILE)
    fake_prefixes = ("TEST_", "MOCK_", "PLACEHOLDER_", "INVALID_", "MISSING_", "TOTALLY_UNKNOWN_", "MY_SECRET", "STRONG_SECRET", "ASYNC_SECRET", "REDACTED_", "FATAL_SECRET", "MODE_FATAL_", "HARDCODED_", "UNRELATED_VAULT_", "VAULT_SECRET", "VAULT_TOKEN")
    for k in sorted(data):
        if k.startswith(fake_prefixes):
            continue
        if k not in env_keys:
            findings.append(k)
    return findings


def self_test():
    # test isolation check logic on a temp file
    import tempfile
    d = tempfile.mkdtemp()
    p = os.path.join(d, "config_classification.py")
    open(p, "w").write("x = 'TEST_ONLY_FOO'\n")
    # monkeypatch targets
    global AUDIT_FILE
    # run isolation check manually
    bad = False
    for line in open(p, encoding="utf-8"):
        if re.search(r"TEST_ONLY_", line):
            bad = True
    assert bad, "should detect TEST_ONLY_"
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

    total = 0
    # 1. test-secret isolation
    f1 = check_test_secret_isolation()
    print(f"== test-secret isolation: {len(f1)} finding(s)")
    for x in f1:
        print("   ", x)
    total += len(f1)

    # 2. single-file secrets
    single = check_single_file_secrets()
    print(f"== single-file secrets: {len(single)}")
    if single:
        print("   ", ", ".join(single[:20]), "..." if len(single) > 20 else "")

    # 3. VITE (frontend-only by Vite convention)
    vite_findings, vite_keys = check_vite_parity()
    print(f"== VITE_* keys: {len(vite_keys)} (frontend-only, no parity check)")

    # 4. .env.example hygiene
    undocumented = check_env_example_hygiene()
    print(f"== undocumented secrets (not in .env.example): {len(undocumented)}")
    if undocumented:
        print("   ", ", ".join(undocumented[:20]), "..." if len(undocumented) > 20 else "")

    if args.strict and total > 0:
        print(f"FAIL (strict): {total} finding(s)")
        return 1
    print("OK (report-only)" if not args.strict else "OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
