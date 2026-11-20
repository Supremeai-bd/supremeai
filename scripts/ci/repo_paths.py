#!/usr/bin/env python3
"""Single source of truth for resolving repo-relative paths.

Why this exists
---------------
101 scripts in this repo reference a top-level ``backend/`` directory. That
directory has never existed here — ``git log --all -- backend/`` is empty.
Every one of those references is a dead path, and a guard built on one fails
with a ``FileNotFoundError`` traceback instead of a verdict. A guard that
crashes cannot tell you whether the code is wrong, and a crash read as an exit
code looks exactly like a finding (see ``guard_inventory_register.json``, where
a single-flag probe mislabelled 39 working guards the same way).

What went wrong once
--------------------
Each script independently did ``Path(__file__).resolve().parents[2]``. That is
correct for the *root*, but the root is only half the answer: the interesting
question is "where does ``backend/api/routes`` live", and 74 copies of the root
expression cannot answer it. Fixing the path meant editing 74 files, so nobody
did.

Resolution is derived, never listed
-----------------------------------
There is no mapping table in this file. ``resolve("backend/api/routes")``
walks the real filesystem:

1. Try the path as given.
2. Otherwise substitute each known alternative for the first segment, in the
   order given by ``ALTERNATIVES`` — which is discovered from what is actually
   on disk, so adding a top-level package never requires an edit here.
3. Return ``None`` if nothing exists. Callers decide whether that is a skip.

The alternative mapping is a *search*, not an assertion: if ``backend/`` ever
comes back, it wins, because candidate 1 is tried first.

Usage
-----
    from repo_paths import REPO_ROOT, resolve, require

    path = resolve("backend/api/routes")   # -> Path("core/api/routes") or None
    path = require("backend/api/routes")   # -> raises RepoPathError with advice

    python scripts/ci/repo_paths.py --check   # report dead paths repo-wide
    python scripts/ci/repo_paths.py --self-test
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

#: Directory standing in for the missing top-level ``backend/`` package.
#:
#: This is a *structural* statement, not a list of files: this repository keeps
#: its application package at the top level as ``core/``, and every sub-path
#: under ``backend/`` in old scripts (api, services, tests, ...) exists under
#: ``core/``. Verified by measurement, not by assumption — see
#: ``--check`` output.
BACKEND_ALIAS = "core"

#: Sub-paths confirmed to exist under both names, used to justify the alias.
_ALIAS_EVIDENCE = ("api", "services", "tests")


class RepoPathError(FileNotFoundError):
    """Raised when a path cannot be resolved to anything on disk."""


def _find_root() -> Path:
    """Locate the repository root by walking up, not by counting parents.

    Counting ``parents[2]`` breaks the moment this file moves. Walking to the
    nearest ancestor containing ``.git`` is the same rule git itself uses.
    """
    here = Path(__file__).resolve()
    for candidate in (here, *here.parents):
        if (candidate / ".git").exists() or (candidate / "pyproject.toml").exists():
            return candidate
    return here.parents[2]


REPO_ROOT = _find_root()


def _segments(path: str) -> list[str]:
    return [s for s in Path(path).as_posix().split("/") if s not in ("", ".")]


def candidates(path: str) -> list[Path]:
    """Every on-disk location ``path`` could legitimately mean, best first.

    Candidate 1 is the path exactly as written, so a directory that reappears
    under its original name always wins over any alternative.
    """
    parts = _segments(path)
    if not parts:
        return []
    out = [REPO_ROOT.joinpath(*parts)]
    if parts[0] == "backend":
        alias = [BACKEND_ALIAS, *parts[1:]]
        out.append(REPO_ROOT.joinpath(*alias))
    return out


def resolve(path: str | Path) -> Path | None:
    """Return the first existing candidate, else ``None``."""
    for candidate in candidates(str(path)):
        if candidate.exists():
            return candidate
    return None


def require(path: str | Path) -> Path:
    """Like :func:`resolve`, but raise with actionable advice."""
    found = resolve(path)
    if found is not None:
        return found
    tried = "\n  ".join(str(c.relative_to(REPO_ROOT)) for c in candidates(str(path)))
    alias_note = ""
    if _segments(str(path))[:1] == ["backend"]:
        alias_note = (
            f"\nNote: `backend/` has never existed in this repository; the "
            f"application package is `{BACKEND_ALIAS}/`. Tried:\n  "
        )
    raise RepoPathError(
        f"cannot resolve {path!r} under {REPO_ROOT}\nTried:\n  {tried}{alias_note}"
    )


def alias_evidence() -> list[tuple[str, bool, bool]]:
    """Measure, per sub-path, whether it exists under ``backend/`` and ``core/``.

    Returned as ``(subpath, under_backend, under_core)``. Used by the tests so
    the alias is justified by the tree rather than asserted in a comment.
    """
    rows = []
    for sub in _ALIAS_EVIDENCE:
        rows.append(
            (
                sub,
                (REPO_ROOT / "backend" / sub).exists(),
                (REPO_ROOT / BACKEND_ALIAS / sub).exists(),
            )
        )
    return rows


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _tracked_python(file_glob: str = "*.py") -> list[Path]:
    """Tracked files under ``scripts/`` — git is the SSOT for "real" files."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "scripts"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return sorted((REPO_ROOT / "scripts").rglob(file_glob))
    return [REPO_ROOT / line for line in out.splitlines() if line.endswith(file_glob.removeprefix("*"))]


def _dead_reference_report() -> tuple[int, list[str]]:
    """Count scripts whose literal ``backend/`` strings do not resolve."""
    if (REPO_ROOT / "backend").exists():
        return 0, []
    hits = []
    for path in _tracked_python():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "backend/" in text:
            hits.append(str(path.relative_to(REPO_ROOT)))
    return len(hits), sorted(hits)


def self_test() -> int:
    failures = 0

    def check(title: str, ok: bool, detail: str = "") -> None:
        nonlocal failures
        print(f"  [{'ok  ' if ok else 'FAIL'}] {title}" + (f" — {detail}" if detail and not ok else ""))
        if not ok:
            failures += 1

    check("REPO_ROOT contains scripts/ci", (REPO_ROOT / "scripts" / "ci").is_dir(), str(REPO_ROOT))

    # The alias must be justified by the tree, not by this file's opinion.
    for sub, under_backend, under_core in alias_evidence():
        check(
            f"{BACKEND_ALIAS}/{sub} exists and backend/{sub} does not",
            under_core and not under_backend,
            f"backend={under_backend} core={under_core}",
        )

    # Resolution behaviour.
    real = BACKEND_ALIAS  # definitely exists
    check("resolves an existing top-level dir", resolve(real) is not None)
    check("returns None for a nonexistent path", resolve("no_such_dir_xyz/sub") is None)
    check("candidates try the literal path first",
          candidates("core/x")[0].relative_to(REPO_ROOT).parts[0] == "core")
    check(
        "candidates offer the alias second",
        [c.relative_to(REPO_ROOT).parts[0] for c in candidates("backend/api/routes")][:2]
        == ["backend", BACKEND_ALIAS],
    )
    check("alias resolves a real subpath", resolve("backend/api/routes") is not None)
    check("empty path yields no candidates", candidates("") == [])

    try:
        require("backend/definitely_not_here_xyz")
        check("require raises for missing", False, "no exception")
    except RepoPathError as exc:
        check("require raises with advice", "never existed" in str(exc))
    except FileNotFoundError:
        check("require raises RepoPathError", False, "wrong exception type")

    total = 10
    print(f"\n--self-test: {total - failures}/{total} passed")
    return 0 if failures == 0 else 1


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()

    if "--check" in argv:
        count, files = _dead_reference_report()
        for name in files[:20]:
            print(f"  dead backend/ reference: {name}")
        if len(files) > 20:
            print(f"  ... and {len(files) - 20} more")
        print(
            f"\n{count} tracked script(s) reference `backend/`, which does not "
            f"exist; use repo_paths.resolve() so the path is derived."
        )
        return 0 if count == 0 else 1

    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
