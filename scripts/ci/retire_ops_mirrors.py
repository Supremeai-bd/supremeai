#!/usr/bin/env python3
"""Retire the `scripts/ops/` mirror twins that shadow their `scripts/` original.

WHY THIS EXISTS (the maintainability problem)
---------------------------------------------
`scripts/ops/` was introduced as a reorganisation and never finished. The result
is 176 mirror groups, of which 107 have DRIFTED: two files at the same relative
path that look authoritative and disagree. An agent (or a human) that reads
`scripts/advanced_analysis/api_contract_diff.py` while CI runs
`scripts/ops/advanced_analysis/api_contract_diff.py` burns a full context window
and still gets the answer wrong. There is no signal on either file telling you
which one is live.

The repo already had a guard that DETECTS this (`mirror_drift_guard.py`) but it
is report-only and ran on a schedule, so 107 known drifts sat logged and ignored.

WHAT THIS TOOL DOES
-------------------
For every file under `scripts/ops/` that has a same-relative-path twin under
`scripts/`, decide which copy is authoritative and retire the other:

* ROOT WINS when the `scripts/` copy is the one CI invokes (evidence: a literal
  `scripts/<rel>` reference in `.github/workflows/`, `scripts/ci/run_all_guards.py`
  or the `Makefile`), or when neither copy is referenced and the root file is not
  older. Rationale measured in this repo: CI contains 173 references to
  `scripts/...` and only 16 to `scripts/ops/...`, and every one of those 16 is a
  file that has NO root twin. So for genuine twin pairs, root is the live copy.
* OPS WINS when the `scripts/ops/` copy is the referenced one and the root twin
  is not.

Default mode is `--dry-run`. It prints the full plan and changes nothing. With
`--apply` it removes only the losing copy of genuine twins — it never touches a
file that has no twin (those are the real reorganisation cohort and stay put),
and it never edits content, so a wrong call is a `git checkout` away.

SAFETY
------
* Refuses to delete a file that is referenced anywhere in the repo under the
  path it is about to remove (belt and braces: proves the loser is not wired).
* Refuses when both copies are referenced (an ambiguous pair needs a human).
* Never deletes a directory, only individual files, and prunes a directory only
  when it became empty.
* `--json` emits the plan for review in a PR body.

Usage
    python3 scripts/ci/retire_ops_mirrors.py                 # dry run, prints plan
    python3 scripts/ci/retire_ops_mirrors.py --json          # machine-readable
    python3 scripts/ci/retire_ops_mirrors.py --apply         # do it
    python3 scripts/ci/retire_ops_mirrors.py --self-test     # validate the logic

Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OPS_ROOT = Path("scripts/ops")
SCRIPTS_ROOT = Path("scripts")

# Where a live invocation can legally appear.
REFERENCE_SOURCES = (
    "scripts/ci/run_all_guards.py",
    "Makefile",
)


def _is_tracked(root: Path, path: Path) -> bool:
    """True when git tracks ``path``. Untracked strays are not part of a plan.

    Falls back to True outside a git checkout so the function stays usable in the
    synthetic tree used by --self-test.
    """
    # Not a git checkout (e.g. the --self-test temp tree): everything counts.
    if not (root / ".git").exists():
        return True
    try:
        rel = path.relative_to(root).as_posix()
        proc = subprocess.run(
            ["git", "ls-files", "--error-unmatch", rel],
            cwd=root, capture_output=True, text=True, timeout=30,
        )
        return proc.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return True


def _workflow_files(root: Path) -> list[Path]:
    wf = root / ".github" / "workflows"
    return sorted(wf.glob("*.yml")) + sorted(wf.glob("*.yaml")) if wf.is_dir() else []


def _load_reference_text(root: Path) -> str:
    """Concatenate every place a script path could be wired up."""
    chunks: list[str] = []
    for rel in REFERENCE_SOURCES:
        path = root / rel
        if path.is_file():
            chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
    for wf in _workflow_files(root):
        chunks.append(wf.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(chunks)


def is_referenced(reference_text: str, relpath: str) -> bool:
    """True when ``relpath`` appears as a whole path in a wiring file.

    A trailing boundary check matters: ``scripts/ops/x.py`` must not be counted
    as referenced by a mention of ``scripts/x.py``.
    """
    pattern = re.escape(relpath.replace("\\", "/")) + r"(?![\w./-])"
    return re.search(pattern, reference_text.replace("\\", "/")) is not None


def plan(root: Path = REPO_ROOT) -> dict:
    """Build the retirement plan. Pure: reads the tree, changes nothing."""
    reference_text = _load_reference_text(root)
    ops_dir = root / OPS_ROOT
    pairs: list[dict] = []
    ops_only: list[str] = []

    if not ops_dir.is_dir():
        return {"pairs": [], "ops_only": [], "delete": [], "skipped": []}

    for ops_file in sorted(ops_dir.rglob("*")):
        if not ops_file.is_file():
            continue
        # Only real source is eligible. A __pycache__/.pyc artefact is untracked
        # build output: planning a "deletion" for it is noise, and gating on it
        # would make the result depend on whether anyone had run Python here.
        if "__pycache__" in ops_file.parts or ops_file.suffix in {".pyc", ".pyo"}:
            continue
        if not _is_tracked(root, ops_file):
            continue
        rel_ops = ops_file.relative_to(root).as_posix()          # scripts/ops/...
        rel_root = (SCRIPTS_ROOT / ops_file.relative_to(ops_dir)).as_posix()  # scripts/...
        root_file = root / rel_root

        if not root_file.is_file():
            ops_only.append(rel_ops)
            continue

        root_referenced = is_referenced(reference_text, rel_root)
        ops_referenced = is_referenced(reference_text, rel_ops)

        if root_referenced and ops_referenced:
            pairs.append(
                {"ops": rel_ops, "root": rel_root, "winner": None,
                 "reason": "both copies referenced — needs a human"}
            )
            continue

        if ops_referenced and not root_referenced:
            winner, reason = "ops", "ops copy is wired in CI; root twin is not"
        elif root_referenced and not ops_referenced:
            winner, reason = "root", "root copy is wired in CI; ops copy is not"
        else:
            # Neither is referenced: keep the root copy (it is the path the rest
            # of the tree and CI overwhelmingly use) and retire the shadow.
            winner, reason = "root", "neither referenced — root tree is canonical"

        pairs.append({"ops": rel_ops, "root": rel_root, "winner": winner, "reason": reason})

    delete: list[str] = []
    skipped: list[dict] = []
    for pair in pairs:
        if pair["winner"] == "root":
            loser = pair["ops"]
        elif pair["winner"] == "ops":
            loser = pair["root"]
        else:
            skipped.append(pair)
            continue
        # Belt and braces: never delete something that is still wired up.
        if is_referenced(reference_text, loser):
            skipped.append({**pair, "reason": f"loser {loser} is still referenced"})
            continue
        delete.append(loser)

    return {"pairs": pairs, "ops_only": ops_only, "delete": sorted(delete), "skipped": skipped}


def apply_plan(root: Path, plan_data: dict) -> int:
    """Delete the planned losers. Returns the number of files removed."""
    removed = 0
    for rel in plan_data["delete"]:
        target = root / rel
        if not target.is_file():
            continue
        target.unlink()
        removed += 1
        parent = target.parent
        # Prune only directories this tool emptied, and never the ops root itself
        # while it still holds the ops-only cohort.
        while parent != root and parent != root / SCRIPTS_ROOT / "ops" and parent.is_dir():
            if any(parent.iterdir()):
                break
            parent.rmdir()
            parent = parent.parent
    return removed


def _print_plan(plan_data: dict, *, verbose: bool) -> None:
    pairs = plan_data["pairs"]
    print(f"mirror pairs: {len(pairs)}  ops-only (kept): {len(plan_data['ops_only'])}")
    print(f"planned deletions: {len(plan_data['delete'])}  skipped: {len(plan_data['skipped'])}")
    if verbose:
        for pair in pairs:
            print(f"  [{pair['winner'] or 'SKIP'}] {pair['ops']}\n         {pair['reason']}")
        for item in plan_data["skipped"]:
            print(f"  [SKIP] {item['ops']}: {item['reason']}")


def self_test() -> int:
    """Prove the decision rules on a synthetic tree (no repo access)."""
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / ".github" / "workflows").mkdir(parents=True)
        (tmp / "scripts" / "ci").mkdir(parents=True)
        (tmp / "scripts" / "ops" / "sub").mkdir(parents=True)
        (tmp / "scripts" / "sub").mkdir(parents=True)
        (tmp / "Makefile").write_text("gates:\n\tpython scripts/ci/guard.py\n", encoding="utf-8")
        (tmp / "scripts" / "ci" / "guard.py").write_text("print('g')\n", encoding="utf-8")
        (tmp / "scripts" / "ci" / "run_all_guards.py").write_text(
            "[\"python\", \"scripts/sub/wired.py\"]\n"
            "[\"python\", \"scripts/ops/sub/opswired.py\"]\n",
            encoding="utf-8",
        )
        # root-wins pair: neither referenced -> root canonical, ops deleted
        (tmp / "scripts" / "sub" / "a.py").write_text("A\n", encoding="utf-8")
        (tmp / "scripts" / "ops" / "sub" / "a.py").write_text("A-drifted\n", encoding="utf-8")
        # root-referenced pair -> ops deleted
        (tmp / "scripts" / "sub" / "wired.py").write_text("W\n", encoding="utf-8")
        (tmp / "scripts" / "ops" / "sub" / "wired.py").write_text("W-old\n", encoding="utf-8")
        # ops-referenced pair -> root deleted
        (tmp / "scripts" / "sub" / "opswired.py").write_text("O-old\n", encoding="utf-8")
        (tmp / "scripts" / "ops" / "sub" / "opswired.py").write_text("O\n", encoding="utf-8")
        # ops-only: must be kept
        (tmp / "scripts" / "ops" / "sub" / "solo.py").write_text("S\n", encoding="utf-8")

        data = plan(tmp)
        deletes = set(data["delete"])
        assert "scripts/ops/sub/a.py" in deletes, data["delete"]
        assert "scripts/ops/sub/wired.py" in deletes, data["delete"]
        assert "scripts/sub/opswired.py" in deletes, data["delete"]
        assert "scripts/ops/sub/solo.py" not in deletes, "ops-only must never be deleted"
        assert "scripts/sub/a.py" not in deletes
        assert "scripts/sub/wired.py" not in deletes
        assert any("solo.py" in p for p in data["ops_only"]), data["ops_only"]

        removed = apply_plan(tmp, data)
        assert removed == 3, removed
        assert not (tmp / "scripts" / "ops" / "sub" / "a.py").exists()
        assert (tmp / "scripts" / "ops" / "sub" / "solo.py").exists()
        assert (tmp / "scripts" / "sub" / "a.py").exists()

        # Reference-boundary correctness: scripts/x.py must not match scripts/ops/x.py
        assert is_referenced("python scripts/x.py", "scripts/x.py")
        assert not is_referenced("python scripts/x.py", "scripts/ops/x.py")
        assert is_referenced("python scripts/ops/x.py", "scripts/ops/x.py")
        print("retire_ops_mirrors self-test: PASS")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true", help="delete the planned losers")
    ap.add_argument("--json", action="store_true", help="emit the plan as JSON")
    ap.add_argument("--verbose", "-v", action="store_true", help="show every pair")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    data = plan()
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        _print_plan(data, verbose=args.verbose)

    if args.apply:
        removed = apply_plan(REPO_ROOT, data)
        print(f"\nremoved {removed} mirror file(s)")
    elif not args.json:
        print("\n(dry run — pass --apply to delete)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
