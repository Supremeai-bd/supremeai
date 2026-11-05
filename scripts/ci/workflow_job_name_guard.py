"""Guard: every job in .github/workflows/*.yml must declare a `name:` field.

Exit codes: 0 = OK, 1 = violations found.
"""
import argparse
import glob
import os
import sys

try:
    import yaml
except ImportError:
    yaml = None


def check_file(path):
    violations = []
    if yaml is None:
        return violations
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    jobs = data.get("jobs") or {}
    for job_id, job in jobs.items():
        if not isinstance(job, dict):
            continue
        if not job.get("name"):
            violations.append((path, job_id))
    return violations


def self_test():
    import tempfile
    good = "jobs:\n  a:\n    name: A\n    runs-on: ubuntu-latest\n"
    bad = "jobs:\n  b:\n    runs-on: ubuntu-latest\n"
    d = tempfile.mkdtemp()
    gp = os.path.join(d, "good.yml")
    bp = os.path.join(d, "bad.yml")
    open(gp, "w").write(good)
    open(bp, "w").write(bad)
    v_good = check_file(gp)
    v_bad = check_file(bp)
    assert v_good == [], v_good
    assert v_bad == [(bp, "b")], v_bad
    print("self-test: PASS (2/2)")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="run check on workflows")
    ap.add_argument("--self-test", action="store_true", help="run self-test")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if args.check:
        all_v = []
        for path in sorted(glob.glob(".github/workflows/*.yml")) + sorted(glob.glob(".github/workflows/*.yaml")):
            all_v.extend(check_file(path))
        if all_v:
            for path, job_id in all_v:
                print(f"::error file={path}::job '{job_id}' missing 'name:' field")
            print(f"FAIL: {len(all_v)} job(s) without name")
            return 1
        print("OK: all workflow jobs declare a name")
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
PY