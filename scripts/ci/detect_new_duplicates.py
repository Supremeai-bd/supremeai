#!/usr/bin/env python3
"""Fail a pull request when it introduces genuinely new code clones.

This is a small, dependency-free wrapper around jscpd. It compares the
checkout against the pull request base ref and runs two passes:

* exact token clones, which catch copied blocks;
* AST-similar clones, which catch renamed/reworded implementations.

A clone is reported as *new* only when the two files did **not** already clone
each other in the base ref. This is deliberately *relationship*-aware rather
than *content*-aware: editing a file that already participates in a pre-existing
duplication (for example a hygiene/import-cleanup PR) must not fail the gate,
while introducing duplication between two files that were previously distinct
still does. The base ref's clone set is computed once by scanning a throwaway
``git worktree`` of the base ref.

Typical GitHub Actions usage::

    python scripts/ci/detect_new_duplicates.py \
      --base-ref "origin/${GITHUB_BASE_REF}" \
      --max-new 0

The script exits 1 when the number of genuinely new clone records is greater
than ``--max-new``. It emits GitHub Actions warnings for each new clone when
running inside GitHub Actions and always writes a JSON summary when
``--report-dir`` is provided.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

# browser/url_policy.py is an INTENTIONAL, byte-identical mirror of
# core/url_policy.py (SSRF policy). It exists only because `render.yaml` builds
# the scraper service with `dockerContext: browser` and `browser/Dockerfile`
# does `COPY *.py ./`, so that image cannot import `core` at all. Byte identity
# is enforced by tests/test_url_policy_single_source.py — a strictly stronger
# check than jscpd's 90%-similarity pass, and that guard also fails if the
# mirror stops being necessary (dockerContext changes) so the exemption cannot
# outlive its reason.
DEFAULT_IGNORES = (
    "**/archive/**,"
    "**/node_modules/**,"
    "**/__pycache__/**,"
    "**/.venv/**,"
    "**/venv/**,"
    "**/dist/**,"
    "**/build/**,"
    "**/.next/**,"
    "**/coverage/**,"
    "**/*.min.js,"
    "**/*.min.css,"
    "**/generated/**,"
    "**/.github/workflows/**,"
    "**/package-lock.json,"
    "**/*lock.json,"
    "**/*lock.yaml,"
    "**/*.lock,"
    "**/_verifier-base/**,"
    "browser/url_policy.py,"  # intentional SSRF mirror — see note below
    # studio/** is third-party Open WebUI foundation (#557); vendored clones are excluded
    "studio/**,"
    # core/github/** is governance mirror (#549, plan_duplicate_refactors.py)
    "core/github/**,"
    # scripts/ops/** is an intentional mirror of scripts/** (tracked by
    # scripts/ci/mirror_drift_guard.py). Mirror similarity is expected, not a
    # defect, so it is excluded here; drift itself is covered by that guard.
    "scripts/ops/**,"
    "docs/**,"
    ".agents/**,"
    "**/*.md,"
    "tests/fixtures/**"
)

SOURCE_EXTENSIONS = frozenset({
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".mjs",
    ".cjs",
    ".sql",
    ".sh",
    ".bash",
    ".ps1",
    ".html",
    ".css",
    ".scss",
    ".go",
    ".rs",
    ".java",
    ".c",
    ".cpp",
})


@dataclass(frozen=True)
class Clone:
    kind: str
    format: str
    lines: int
    tokens: int
    file_a: str
    start_a: int
    end_a: int
    file_b: str
    start_b: int
    end_b: int

    def pair(self) -> tuple[str, str]:
        a, b = self.file_a, self.file_b
        return (a, b) if a <= b else (b, a)


@dataclass(frozen=True)
class PassResult:
    name: str
    clones: list[Clone]
    new_clones: list[Clone]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-ref",
        default=None,
        help=(
            "Git ref used as the baseline. Defaults to origin/$GITHUB_BASE_REF "
            "in Actions, otherwise origin/main."
        ),
    )
    parser.add_argument(
        "--max-new",
        type=int,
        default=0,
        help="Maximum number of genuinely new clone records allowed; default: 0.",
    )
    parser.add_argument(
        "--min-lines", type=int, default=8, help="Minimum clone length; default: 8."
    )
    parser.add_argument(
        "--min-tokens", type=int, default=50, help="Minimum clone tokens; default: 50."
    )
    parser.add_argument(
        "--similarity",
        type=float,
        default=0.90,
        help="AST similarity threshold from 0 to 1; default: 0.90.",
    )
    parser.add_argument(
        "--passes",
        choices=("exact", "ast", "both"),
        default="both",
        help="Clone passes to run; default: both.",
    )
    parser.add_argument(
        "--jscpd",
        default=os.environ.get("JSCPD_BIN", "jscpd"),
        help="jscpd executable or command; default: JSCPD_BIN or jscpd.",
    )
    parser.add_argument(
        "--no-npx-fallback",
        action="store_true",
        help="Do not use npx --yes jscpd when jscpd is not on PATH.",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=None,
        help="Persist JSON reports and summary in this directory.",
    )
    parser.add_argument(
        "--ignore",
        default=DEFAULT_IGNORES,
        help="Comma-separated jscpd ignore globs.",
    )
    return parser.parse_args(argv)


def default_base_ref() -> str:
    base = os.environ.get("GITHUB_BASE_REF", "").strip()
    if base:
        return f"origin/{base}"
    return "origin/main"


def resolve_jscpd(command: str, allow_npx: bool) -> list[str]:
    parts = command.split()
    if parts and (shutil.which(parts[0]) or shutil.which(f"{parts[0]}.cmd")):
        return parts
    npx_bin = shutil.which("npx") or shutil.which("npx.cmd")
    if allow_npx and npx_bin:
        return [npx_bin, "--yes", "jscpd"]
    raise RuntimeError(
        "jscpd was not found. Install it with `npm install --save-dev jscpd`, "
        "or make it available on PATH."
    )


def run_command(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    print("[duplicate-regression] $", " ".join(command))
    use_shell = sys.platform == "win32"
    return subprocess.run(command, cwd=cwd, text=True, check=False, shell=use_shell)


def _norm(path_str: str) -> str:
    """Normalise a jscpd-reported path to a repo-relative, forward-slash path."""
    p = path_str.replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p


def clone_from_json(item: dict[str, Any], kind: str) -> Clone:
    first = item["firstFile"]
    second = item["secondFile"]
    return Clone(
        kind=kind,
        format=str(item.get("format", "unknown")),
        lines=int(item.get("lines", 0)),
        tokens=int(item.get("tokens", 0)),
        file_a=_norm(str(first.get("name", ""))),
        start_a=int(first.get("start", 0)),
        end_a=int(first.get("end", 0)),
        file_b=_norm(str(second.get("name", ""))),
        start_b=int(second.get("start", 0)),
        end_b=int(second.get("end", 0)),
    )


def _changed_files_against_base(base_ref: str, root: Path) -> set[str] | None:
    for diff_spec in (f"{base_ref}...HEAD", base_ref):
        res = subprocess.run(
            ["git", "diff", "--name-only", diff_spec],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            return {
                _norm(line.strip())
                for line in res.stdout.splitlines()
                if line.strip()
            }
    return None


def _load_clones(report_path: Path, kind: str) -> list[Clone]:
    if not report_path.exists():
        raise RuntimeError(f"jscpd did not produce its JSON report: {report_path}")
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    return [clone_from_json(item, kind) for item in payload.get("duplicates", [])]


def emit_annotation(clone: Clone, pass_name: str) -> None:
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    message = (
        f"new {pass_name} duplicate: {clone.file_a}:{clone.start_a}-{clone.end_a} "
        f"matches {clone.file_b}:{clone.start_b}-{clone.end_b} "
        f"({clone.lines} lines, {clone.tokens} tokens)"
    )
    print(f"::warning file={clone.file_a},line={clone.start_a}::{message}")


def scan_clones(
    *,
    kind: str,
    jscpd: list[str],
    scan_root: Path,
    args: argparse.Namespace,
    output_dir: Path,
    report_name: str,
) -> list[Clone]:
    command = [
        *jscpd,
        str(scan_root),
        "--reporters",
        "json",
        "--output",
        str(output_dir),
        "--report-name",
        report_name,
        "--min-lines",
        str(args.min_lines),
        "--min-tokens",
        str(args.min_tokens),
        "--ignore",
        args.ignore,
        "--kind",
        kind,
        "--similarity",
        str(args.similarity),
    ]
    run_command(command, scan_root)
    return _load_clones(output_dir / f"{report_name}.json", kind)


def _isolated_clone_exists(
    *,
    iso_parent: Path,
    root: Path,
    base_ref: str,
    clone: Clone,
    jscpd: list[str],
    args: argparse.Namespace,
) -> bool:
    """Return True when the two files already clone each other in ``base_ref``.

    jscpd reports clones relative to the whole scanned file set, so two
    independent full scans (working tree vs base worktree) are not always
    directly comparable: a clone can be reported in one scan and absorbed into a
    larger clone group in the other. To decide whether a clone pair is genuinely
    new we therefore re-scan just that pair at the base ref, in isolation, and
    trust only that result.
    """
    pair_dir = Path(tempfile.mkdtemp(prefix="pair-", dir=iso_parent))
    try:
        for rel in (clone.file_a, clone.file_b):
            res = subprocess.run(
                ["git", "show", f"{base_ref}:{rel}"],
                cwd=root,
                capture_output=True,
                check=False,
            )
            if res.returncode != 0:
                # File does not exist at the base ref -> cannot be a pre-existing clone.
                return False
            dest = pair_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(res.stdout)
        out_dir = Path(tempfile.mkdtemp(prefix="out-", dir=iso_parent))
        report = out_dir / "iso.json"
        command = [
            *jscpd,
            str(pair_dir),
            "--reporters",
            "json",
            "--output",
            str(out_dir),
            "--report-name",
            "iso",
            "--min-lines",
            str(args.min_lines),
            "--min-tokens",
            str(args.min_tokens),
            "--ignore",
            args.ignore,
            "--kind",
            clone.kind,
            "--similarity",
            str(args.similarity),
        ]
        run_command(command, pair_dir)
        return len(_load_clones(report, clone.kind)) > 0
    finally:
        shutil.rmtree(pair_dir, ignore_errors=True)


def run_pass(
    *,
    name: str,
    kind: str,
    jscpd: list[str],
    root: Path,
    base_ref: str,
    baseline_root: Path,
    changed_files: set[str] | None,
    args: argparse.Namespace,
    output_dir: Path,
) -> PassResult:
    current = scan_clones(
        kind=kind,
        jscpd=jscpd,
        scan_root=root,
        args=args,
        output_dir=output_dir,
        report_name=f"jscpd-{name}",
    )
    baseline = scan_clones(
        kind=kind,
        jscpd=jscpd,
        scan_root=baseline_root,
        args=args,
        output_dir=output_dir,
        report_name=f"jscpd-{name}-baseline",
    )
    baseline_pairs = {clone.pair() for clone in baseline}

    iso_parent = Path(tempfile.mkdtemp(prefix="jscpd-iso-"))
    new_clones: list[Clone] = []
    try:
        for clone in current:
            if clone.pair() in baseline_pairs:
                continue
            if changed_files is not None and (
                clone.file_a not in changed_files and clone.file_b not in changed_files
            ):
                continue
            # Confirm against the base ref in isolation to avoid the whole-set
            # grouping false positive described in _isolated_clone_exists.
            if _isolated_clone_exists(
                iso_parent=iso_parent,
                root=root,
                base_ref=base_ref,
                clone=clone,
                jscpd=jscpd,
                args=args,
            ):
                continue
            new_clones.append(clone)
    finally:
        shutil.rmtree(iso_parent, ignore_errors=True)

    for clone in new_clones:
        emit_annotation(clone, name)
    return PassResult(name=name, clones=current, new_clones=new_clones)


def write_summary(path: Path, base_ref: str, results: Iterable[PassResult]) -> None:
    result_list = [asdict(result) for result in results]
    payload = {
        "base_ref": base_ref,
        "new_clone_count": sum(len(result.new_clones) for result in results),
        "passes": result_list,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _add_baseline_worktree(base_ref: str, root: Path) -> Path:
    parent = Path(tempfile.mkdtemp(prefix="jscpd-baseline-"))
    wt_path = parent / "wt"
    res = subprocess.run(
        ["git", "worktree", "add", "--detach", str(wt_path), base_ref],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        shutil.rmtree(parent, ignore_errors=True)
        raise RuntimeError(
            f"git worktree add failed for {base_ref!r}: {res.stderr.strip()}"
        )
    return wt_path


def _remove_baseline_worktree(wt_path: Path, root: Path) -> None:
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(wt_path)],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    shutil.rmtree(wt_path.parent, ignore_errors=True)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.max_new < 0:
        print("--max-new must be >= 0", file=sys.stderr)
        return 2
    if not 0 < args.similarity <= 1:
        print("--similarity must be > 0 and <= 1", file=sys.stderr)
        return 2

    root = Path.cwd().resolve()
    base_ref = args.base_ref or default_base_ref()

    changed_files = _changed_files_against_base(base_ref, root)
    if changed_files is not None and not any(
        Path(f).suffix.lower() in SOURCE_EXTENSIONS for f in changed_files
    ):
        print(
            f"[duplicate-regression] No source code files modified against {base_ref}; "
            "skipping jscpd scan."
        )
        print(f"[duplicate-regression] base={base_ref} new_clones=0 allowed={args.max_new}")
        print("[duplicate-regression] PASS")
        return 0

    try:
        jscpd = resolve_jscpd(args.jscpd, not args.no_npx_fallback)
    except RuntimeError as exc:
        print(f"[duplicate-regression] ERROR: {exc}", file=sys.stderr)
        return 2

    report_dir = args.report_dir
    temporary = None
    if report_dir is None:
        temporary = tempfile.TemporaryDirectory(prefix="jscpd-duplicate-regression-")
        report_dir = Path(temporary.name)
    report_dir.mkdir(parents=True, exist_ok=True)

    pass_specs = []
    if args.passes in ("exact", "both"):
        pass_specs.append(("exact", "exact"))
    if args.passes in ("ast", "both"):
        pass_specs.append(("ast", "ast"))

    results: list[PassResult] = []
    baseline_root: Path | None = None
    try:
        baseline_root = _add_baseline_worktree(base_ref, root)
        for name, kind in pass_specs:
            results.append(
                run_pass(
                    name=name,
                    kind=kind,
                    jscpd=jscpd,
                    root=root,
                    base_ref=base_ref,
                    baseline_root=baseline_root,
                    changed_files=changed_files,
                    args=args,
                    output_dir=report_dir,
                )
            )
    except (OSError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"[duplicate-regression] ERROR: {exc}", file=sys.stderr)
        return 2
    finally:
        if baseline_root is not None:
            _remove_baseline_worktree(baseline_root, root)
        if temporary is not None and args.report_dir is None:
            # Reports are intentionally temporary unless --report-dir is supplied.
            temporary.cleanup()

    total_new = sum(len(result.new_clones) for result in results)
    if args.report_dir is not None:
        write_summary(args.report_dir / "duplicate-regression-summary.json", base_ref, results)
    print(
        f"[duplicate-regression] base={base_ref} "
        f"new_clones={total_new} allowed={args.max_new}"
    )
    if total_new > args.max_new:
        print(
            "[duplicate-regression] FAILED: remove the duplicate, reuse the existing "
            "implementation, or document why the clone is an intentional mirror.",
            file=sys.stderr,
        )
        return 1
    print("[duplicate-regression] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())