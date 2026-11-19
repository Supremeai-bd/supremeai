"""`core/llm/top_ai_detector.py` is deprecated dead code — keep it that way.

It duplicates the provider-health policy that `gateway/circuit_breaker.py` +
`gateway/provider_chain.py` now implement for real (that pair is wired into
`execute_chain`; this module has zero production callers). If a production
module ever imports it, we have two competing health policies and the one that
is *not* consulted by the request path is a trap — this test fails so the
decision is made explicitly instead of by accident.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET = "top_ai_detector"
ALLOWED_PREFIXES = ("tests/", "core/llm/top_ai_detector.py")
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "dist", "build"}


def _iter_sources():
    for path in REPO_ROOT.rglob("*.py"):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if rel.startswith(ALLOWED_PREFIXES):
            continue
        yield rel, path


def test_no_production_import_of_the_deprecated_detector():
    pattern = re.compile(rf"^\s*(from\s+\S*{TARGET}\s+import|import\s+\S*{TARGET}\b)", re.MULTILINE)
    offenders = [rel for rel, path in _iter_sources()
                 if pattern.search(path.read_text(encoding="utf-8", errors="replace"))]
    assert offenders == [], (
        "top_ai_detector is deprecated (see its module docstring). Either adopt it "
        f"deliberately or delete it — do not wire a second health policy: {offenders}"
    )


def test_docstring_declares_the_deprecation():
    text = (REPO_ROOT / "core" / "llm" / "top_ai_detector.py").read_text(encoding="utf-8")
    assert "deprecated::" in text[:2000]
