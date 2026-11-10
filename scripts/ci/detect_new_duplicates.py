#!/usr/bin/env python3
"""Fail a pull request when it introduces new code clones.

This is a small, dependency-free wrapper around jscpd. It compares the
checkout against the pull request base ref using jscpd's ``--baseline-from-ref``
mode and runs two passes:

* exact token clones, which catch copied blocks;
* AST-similar clones, which catch renamed/reworded implementations.

Typical GitHub Actions usage::

    python scripts/ci/detect_new_duplicates.py \
      --base-ref "origin/${GITHUB_BASE_REF}" \
      --max-new 0

The script exits 1 when the number of new clone records is greater than
``--max-new``. It emits GitHub Actions warnings for each new clone when running
inside GitHub Actions and always writes a JSON summary when ``--report-dir`` is
provided.
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
    # studio/** is third-party Open WebUI foundation (#557); vendored clones are excluded
    "studio/**"
)


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


@dataclass(frozen=True)
class PassResult:
    name: str
    command: list[str]
    returncode: int
    report_path: str
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
        help="Maximum number of new clone records allowed; default: 0.",
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


def clone_from_json(item: dict[str, Any]) -> Clone:
    first = item["firstFile"]
    second = item["secondFile"]
    return Clone(
        kind=str(item.get("kind", "unknown")),
        format=str(item.get("format", "unknown")),
        lines=int(item.get("lines", 0)),
        tokens=int(item.get("tokens", 0)),
        file_a=str(first.get("name", "")),
        start_a=int(first.get("start", 0)),
        end_a=int(first.get("end", 0)),
        file_b=str(second.get("name", "")),
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
                line.strip().replace("\\", "/")
                for line in res.stdout.splitlines()
                if line.strip()
            }
    return None


def _rel_norm(path_str: str, root: Path) -> str:
    p = Path(path_str)
    try:
        rel = p.resolve().relative_to(root.resolve())
        return str(rel).replace("\\", "/")
    except ValueError:
        return path_str.replace("\\", "/").lstrip("./")


def load_report(
    path: Path,
    changed_files: set[str] | None = None,
    root: Path | None = None,
) -> tuple[list[Clone], list[Clone]]:
    if not path.exists():
        raise RuntimeError(f"jscpd did not produce its JSON report: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    clones = [clone_from_json(item) for item in payload.get("duplicates", [])]
    raw_new = [
        clone_from_json(item)
        for item in payload.get("duplicates", [])
        if item.get("isNew") is True
    ]
    if changed_files is not None and root is not None:
        new_clones = [
            c
            for c in raw_new
            if _rel_norm(c.file_a, root) in changed_files
            or _rel_norm(c.file_b, root) in changed_files
        ]
    else:
        new_clones = raw_new
    return clones, new_clones


def emit_annotation(clone: Clone, pass_name: str) -> None:
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    message = (
        f"new {pass_name} duplicate: {clone.file_a}:{clone.start_a}-{clone.end_a} "
        f"matches {clone.file_b}:{clone.start_b}-{clone.end_b} "
        f"({clone.lines} lines, {clone.tokens} tokens)"
    )
    print(f"::warning file={clone.file_a},line={clone.start_a}::{message}")


def run_pass(
    *,
    name: str,
    kind: str,
    jscpd: list[str],
    base_ref: str,
    root: Path,
    args: argparse.Namespace,
    output_dir: Path,
) -> PassResult:
    report_name = f"jscpd-{name}"
    command = [
        *jscpd,
        str(root),
        "--reporters",
        "json",
        "--output",
        str(output_dir),
        "--report-name",
        report_name,
        "--baseline-from-ref",
        base_ref,
        "--fail-on-new-clones=0",
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
    completed = run_command(command, root)
    report_path = output_dir / f"{report_name}.json"
    changed_files = _changed_files_against_base(base_ref, root)
    clones, new_clones = load_report(report_path, changed_files=changed_files, root=root)
    for clone in new_clones:
        emit_annotation(clone, name)
    return PassResult(
        name=name,
        command=command,
        returncode=completed.returncode,
        report_path=str(report_path),
        clones=clones,
        new_clones=new_clones,
    )


def write_summary(path: Path, base_ref: str, results: Iterable[PassResult]) -> None:
    result_list = [asdict(result) for result in results]
    payload = {
        "base_ref": base_ref,
        "new_clone_count": sum(len(result.new_clones) for result in results),
        "passes": result_list,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


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
    try:
        for name, kind in pass_specs:
            results.append(
                run_pass(
                    name=name,
                    kind=kind,
                    jscpd=jscpd,
                    base_ref=base_ref,
                    root=root,
                    args=args,
                    output_dir=report_dir,
                )
            )
    except (OSError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"[duplicate-regression] ERROR: {exc}", file=sys.stderr)
        return 2
    finally:
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
