#!/usr/bin/env python3
"""Build the deterministic AST graph required by root diagnostics.

The command fails loudly when graphify is unavailable. It never creates an
empty placeholder graph, because an empty graph would create false confidence.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "graph.json"


def main() -> int:
    graphify = shutil.which("graphify")
    if not graphify:
        print("graphify is not installed; graph remains unavailable", file=sys.stderr)
        return 2
    extract = subprocess.run(
        [graphify, "extract", ".", "--output", str(OUT)],
        cwd=ROOT,
        text=True,
    )
    if extract.returncode != 0 or not OUT.exists():
        print("graphify extraction failed; no placeholder graph was created", file=sys.stderr)
        return extract.returncode or 3
    payload = json.loads(OUT.read_text())
    if not isinstance(payload, dict) or not payload:
        print("graphify produced an empty graph; refusing to mark intelligence ready", file=sys.stderr)
        return 4
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

