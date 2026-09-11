#!/usr/bin/env python3
"""Build a local, non-secret release evidence bundle for candidate releases."""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def git_value(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def build(root: Path) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "commit": git_value(root, "rev-parse", "HEAD"),
        "branch": git_value(root, "branch", "--show-current"),
        "working_tree_clean": not bool(git_value(root, "status", "--porcelain")),
        "evidence": {
            "ci": {"status": "manual_pending", "source": "GitHub Actions"},
            "security": {"status": "manual_pending", "source": "CI security jobs"},
            "schema": {"status": "manual_pending", "source": "read-only environment verification"},
            "smoke_tests": {"status": "manual_pending", "source": "staging smoke runner"},
            "rollback": {"status": "manual_pending", "source": "release owner confirmation"},
        },
        "production_mutation_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("ci-reports/release-evidence.json"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(build(root), indent=2) + "\n", encoding="utf-8")
    print(f"release evidence written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
