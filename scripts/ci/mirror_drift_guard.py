"""Guard: detect mirror/duplicate script files across scripts/, scripts/ops/, scripts/security/.

Reports pairs of files sharing a basename and whether they are identical or drifted.
Exit 0 always (report-only); use --strict to fail on drift.
"""
import argparse
import hashlib
import os
import sys
from collections import defaultdict


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def find_mirrors(roots):
    by_name = defaultdict(list)
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _, files in os.walk(root):
            for fn in files:
                if fn.endswith(".py"):
                    by_name[fn].append(os.path.join(dirpath, fn))
    return {k: v for k, v in by_name.items() if len(v) > 1}


def self_test():
    import tempfile
    d = tempfile.mkdtemp()
    a = os.path.join(d, "a", "x.py")
    b = os.path.join(d, "b", "x.py")
    os.makedirs(os.path.dirname(a))
    os.makedirs(os.path.dirname(b))
    open(a, "w").write("same")
    open(b, "w").write("same")
    pairs = find_mirrors([os.path.join(d, "a"), os.path.join(d, "b")])
    assert "x.py" in pairs and len(pairs["x.py"]) == 2
    assert sha256(pairs["x.py"][0]) == sha256(pairs["x.py"][1])
    print("self-test: PASS (1/1)")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--roots", nargs="+", default=["scripts", "scripts/ops", "scripts/security", "scripts/ops/security", ".github/scripts"])
    ap.add_argument("--strict", action="store_true", help="exit 1 on any drift")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    pairs = find_mirrors(args.roots)
    drift = 0
    for name in sorted(pairs):
        paths = pairs[name]
        hashes = [sha256(p) for p in paths]
        identical = len(set(hashes)) == 1
        status = "IDENTICAL" if identical else "DRIFT"
        if not identical:
            drift += 1
        print(f"{status}: {name}")
        for p, h in zip(paths, hashes):
            print(f"   {p}  {h[:12]}")
    print(f"\nTotal mirror groups: {len(pairs)}, drifted: {drift}")
    if args.strict and drift:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
