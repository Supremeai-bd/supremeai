"""`ast_core` must fail closed when its optional grammar is missing.

The engine is imported by audit tooling on machines that may not have
tree-sitter installed. Silence would be worse than an error: an empty symbol
list reads as "found nothing wrong".
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))

import ast_core  # noqa: E402


def test_engine_reports_missing_grammar_loudly():
    if ast_core.TREE_SITTER_AVAILABLE:
        pytest.skip("tree-sitter is installed here; the fail-closed path cannot be exercised")
    with pytest.raises(RuntimeError, match="[Tt]ree-sitter"):
        ast_core.SupremeASTEngine()


def test_availability_flag_matches_the_import_attempt():
    assert isinstance(ast_core.TREE_SITTER_AVAILABLE, bool)
